"""Persistent job system: renders run detached from HTTP requests.

Design (Nov 2026, resume-after-interruption):
- Every long render becomes a Job with a JSON record on disk in
  ASMR_JOBS_DIR (default ~/workspace/asmr-service/jobs — OUTSIDE the repo
  checkout, so it survives VM replacement and git operations).
- The runner is an asyncio Task owned by the app, NOT by the request
  handler: closing the browser tab or dropping the SSE connection does
  not stop the render. Progress can be re-attached via /api/jobs/<id>/stream.
- On app startup, jobs left in running/queued state are marked
  `interrupted` (startup sweep) and can be resumed; runners skip work
  whose checkpoint/segment already exists and is valid.
- Events emitted by runners use the SAME JSON shapes as the legacy SSE
  endpoints (log / step_start / step_done / done / all_done / error),
  so existing panels keep working unchanged when the legacy endpoint
  streams a job's events. A trailing {"type": "job_terminal"} sentinel
  marks the end of the stream (ignored by legacy consumers).

Security note: job records hold render payloads (paths, parameters,
placement plans). They must NEVER hold secrets — the Live stream key is
not a job payload and is never written here.
"""
import asyncio
import json
import os
import re
import signal
import time
import uuid
from datetime import datetime, timezone

JOBS_DIR = os.environ.get(
    "ASMR_JOBS_DIR", "/home/hatch/workspace/asmr-service/jobs"
)
MAX_EVENTS = 300
SAVE_THROTTLE_SEC = 1.5

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_INTERRUPTED = "interrupted"
STATUS_DONE = "done"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"

TERMINAL_STATUSES = {STATUS_DONE, STATUS_ERROR, STATUS_CANCELLED}
RESUMABLE_STATUSES = {STATUS_INTERRUPTED, STATUS_ERROR, STATUS_CANCELLED}


class JobCancelled(Exception):
    """Raised inside a runner when the job is cancelled."""


class JobError(Exception):
    """Runner failure with a user-facing message."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def job_workdir(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id)


def _record_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, f"{job_id}.json")


def _ensure_jobs_dir() -> None:
    os.makedirs(JOBS_DIR, exist_ok=True)


def _atomic_write_json(path: str, data: dict) -> None:
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Record CRUD (disk)
# ---------------------------------------------------------------------------

def create_job_record(job_type: str, label: str, payload: dict,
                      plan: dict, output_path: str) -> dict:
    """Create a job record on disk (status=queued) and its workdir."""
    _ensure_jobs_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = f"job_{stamp}_{uuid.uuid4().hex[:6]}"
    record = {
        "id": job_id,
        "type": job_type,
        "label": label,
        "status": STATUS_QUEUED,
        "progress": 0,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "started_at": None,
        "finished_at": None,
        "payload": payload,
        "plan": plan,
        "output_path": output_path,
        "segments_total": int(plan.get("segments_total", 0) or 0),
        "segments_done": [],
        "error": None,
        "events": [],
        "next_seq": 1,
    }
    os.makedirs(job_workdir(job_id), exist_ok=True)
    _atomic_write_json(_record_path(job_id), record)
    return record


def load_job_record(job_id: str) -> dict | None:
    try:
        with open(_record_path(job_id), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def save_job_record(record: dict) -> None:
    record["updated_at"] = _now_iso()
    _atomic_write_json(_record_path(record["id"]), record)


def list_job_records() -> list:
    """All job records, newest first. Corrupt files are skipped."""
    _ensure_jobs_dir()
    records = []
    for name in os.listdir(JOBS_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(JOBS_DIR, name), encoding="utf-8") as f:
                records.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


def delete_job_record(job_id: str) -> bool:
    """Delete record + workdir. Caller must ensure the job is not running."""
    import shutil
    ok = False
    try:
        os.remove(_record_path(job_id))
        ok = True
    except FileNotFoundError:
        pass
    shutil.rmtree(job_workdir(job_id), ignore_errors=True)
    return ok


def sweep_interrupted() -> list:
    """Startup sweep: jobs left running/queued died with the old process.

    Returns the list of job ids marked interrupted.
    """
    marked = []
    for record in list_job_records():
        if record.get("status") in (STATUS_RUNNING, STATUS_QUEUED):
            record["status"] = STATUS_INTERRUPTED
            record["error"] = "Terhenti: service dimulai ulang sebelum render selesai."
            _append_event(record, {
                "log": "⚠️ Job terhenti karena service dimulai ulang. Klik Lanjutkan untuk meneruskan dari checkpoint terakhir.",
                "ts": _now_ts(),
            })
            save_job_record(record)
            marked.append(record["id"])
    return marked


def _append_event(record: dict, event: dict) -> dict:
    """Append an event (with monotonic seq) to the record's buffer."""
    seq = int(record.get("next_seq", 1) or 1)
    event = dict(event)
    event["seq"] = seq
    record["next_seq"] = seq + 1
    events = record.setdefault("events", [])
    events.append(event)
    if len(events) > MAX_EVENTS:
        del events[: len(events) - MAX_EVENTS]
    return event


def append_record_event(record: dict, event: dict) -> dict:
    """Public wrapper for _append_event (record buffer only, no live fan-out)."""
    return _append_event(record, event)


# ---------------------------------------------------------------------------
# Live execution state (in-memory only)
# ---------------------------------------------------------------------------

class JobContext:
    """Handle passed to runners: emit events, track progress/segments."""

    def __init__(self, record: dict, live: "LiveJob"):
        self.record = record
        self.live = live
        self.job_id = record["id"]
        self.workdir = job_workdir(record["id"])
        self.cancel_event = live.cancel_event
        self.proc = None  # current asyncio subprocess, if any
        self._last_save = 0.0

    @property
    def segments_done(self) -> list:
        return list(self.record.get("segments_done", []))

    def emit(self, event: dict, force_save: bool = False) -> dict:
        stored = _append_event(self.record, event)
        for queue in list(self.live.queues):
            try:
                queue.put_nowait(stored)
            except asyncio.QueueFull:
                pass
        self._maybe_save(force_save)
        return stored

    def log(self, message: str, **extra) -> dict:
        event = {"log": message, "ts": _now_ts()}
        event.update(extra)
        return self.emit(event)

    def set_progress(self, progress: int) -> None:
        progress = max(0, min(100, int(progress)))
        if progress != self.record.get("progress"):
            self.record["progress"] = progress
            self._maybe_save(False)

    def mark_segment_done(self, index: int) -> None:
        done = self.record.setdefault("segments_done", [])
        if index not in done:
            done.append(index)
            done.sort()
        self._maybe_save(True)  # segment completion is resume-critical

    def _maybe_save(self, force: bool) -> None:
        now = time.monotonic()
        if force or now - self._last_save >= SAVE_THROTTLE_SEC:
            self._last_save = now
            try:
                save_job_record(self.record)
            except OSError:
                pass

    def save(self) -> None:
        self._maybe_save(True)

    def check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise JobCancelled("Job dibatalkan")


class LiveJob:
    def __init__(self, record: dict):
        self.record = record
        self.task: asyncio.Task | None = None
        self.ctx: JobContext | None = None
        self.cancel_event = asyncio.Event()
        self.queues: set[asyncio.Queue] = set()


_live: dict[str, LiveJob] = {}
_runners: dict[str, callable] = {}


def register_runner(job_type: str, fn: callable) -> None:
    _runners[job_type] = fn


def get_runner(job_type: str):
    return _runners.get(job_type)


def is_live(job_id: str) -> bool:
    live = _live.get(job_id)
    return bool(live and live.task and not live.task.done())


def get_live_job(job_id: str) -> LiveJob | None:
    return _live.get(job_id)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

async def _execute(job_id: str) -> None:
    live = _live.get(job_id)
    if live is None:
        return
    record = live.record
    ctx = live.ctx
    runner = get_runner(record["type"])
    try:
        if runner is None:
            raise JobError(f"Tidak ada runner untuk tipe job '{record['type']}'")
        record["status"] = STATUS_RUNNING
        record["error"] = None
        if not record.get("started_at"):
            record["started_at"] = _now_iso()
        ctx.save()
        output = await runner(ctx, record)
        record["status"] = STATUS_DONE
        record["progress"] = 100
        record["finished_at"] = _now_iso()
        if output:
            record["output_path"] = output
        done_event = {"status": "done", "output": record.get("output_path"),
                      "ts": _now_ts()}
        # Size under every key the legacy panels read (video: final_size,
        # audio/sound-layer: size).
        out_path = record.get("output_path")
        if out_path and os.path.exists(out_path):
            try:
                from api.utils import get_file_size_str
                size_str = get_file_size_str(out_path)
                done_event["final_size"] = size_str
                done_event["size"] = size_str
                done_event["size_str"] = size_str
            except Exception:
                pass
        ctx.emit(done_event, force_save=True)
    except JobCancelled:
        record["status"] = STATUS_CANCELLED
        record["finished_at"] = _now_iso()
        ctx.emit({"status": "error", "code": -9,
                  "log": "Job dibatalkan.", "ts": _now_ts()}, force_save=True)
    except asyncio.CancelledError:
        # Task cancelled from outside (e.g. shutdown): treat as interrupted
        # so the job can be resumed; the runner's finally already killed ffmpeg.
        record["status"] = STATUS_INTERRUPTED
        record["error"] = "Terhenti: task dibatalkan dari luar."
        try:
            save_job_record(record)
        except OSError:
            pass
        raise
    except Exception as e:  # noqa: BLE001 - runner failures become job errors
        record["status"] = STATUS_ERROR
        record["error"] = str(e)
        record["finished_at"] = _now_iso()
        ctx.emit({"status": "error", "code": -1,
                  "log": f"Error: {e}", "ts": _now_ts()}, force_save=True)
    finally:
        ctx.emit({"type": "job_terminal", "status": record["status"],
                  "ts": _now_ts()}, force_save=True)
        _live.pop(job_id, None)


def start_job(job_id: str) -> dict:
    """Start (or restart) the asyncio task for a job record.

    Raises ValueError if the record is missing or already live.
    """
    record = load_job_record(job_id)
    if record is None:
        raise ValueError(f"Job tidak ditemukan: {job_id}")
    if is_live(job_id):
        raise ValueError("Job sedang berjalan")
    live = LiveJob(record)
    live.ctx = JobContext(record, live)
    _live[job_id] = live
    live.task = asyncio.create_task(_execute(job_id))
    return record


async def cancel_job(job_id: str) -> dict | None:
    """Cancel a running job (kills its ffmpeg) or mark a queued job cancelled."""
    record = load_job_record(job_id)
    if record is None:
        return None
    live = _live.get(job_id)
    if live is not None and live.task and not live.task.done():
        live.cancel_event.set()
        if live.ctx is not None:
            _kill_proc(live.ctx.proc)
        try:
            await asyncio.wait_for(live.task, timeout=10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            live.task.cancel()
            try:
                await live.task
            except asyncio.CancelledError:
                pass
        return load_job_record(job_id)
    if record.get("status") in (STATUS_QUEUED, STATUS_RUNNING, STATUS_INTERRUPTED):
        record["status"] = STATUS_CANCELLED
        record["finished_at"] = _now_iso()
        save_job_record(record)
    return record


def _kill_proc(proc) -> None:
    if proc is None or proc.returncode is not None:
        return
    try:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)
                return
            except (ProcessLookupError, PermissionError, OSError):
                pass
        proc.kill()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# SSE attach (replay + live follow)
# ---------------------------------------------------------------------------

async def attach_stream(job_id: str, since_seq: int = 0):
    """Async generator of SSE `data:` lines for a job.

    Replays buffered events with seq > since_seq, then follows live events
    until the job_terminal sentinel. Ends immediately for terminal jobs
    once the buffer is drained.
    """
    record = load_job_record(job_id)
    if record is None:
        yield f"data: {json.dumps({'status': 'error', 'log': 'Job tidak ditemukan'})}\n\n"
        return

    last_seq = since_seq
    for event in record.get("events", []):
        if event.get("seq", 0) > since_seq:
            last_seq = max(last_seq, event["seq"])
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "job_terminal":
                return

    if record.get("status") in TERMINAL_STATUSES:
        return

    live = _live.get(job_id)
    if live is None:
        # Job exists but no live task (e.g. queued before start, or the
        # process restarted between load and attach): wait briefly for a
        # task, else end the stream — the client can poll the record.
        for _ in range(20):
            await asyncio.sleep(0.25)
            live = _live.get(job_id)
            if live is not None:
                break
            record = load_job_record(job_id)
            if record is None or record.get("status") in TERMINAL_STATUSES:
                return
        if live is None:
            return

    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    live.queues.add(queue)
    try:
        # Reload: events emitted between the first load and subscribing
        # are in the record but were not replayed yet.
        record = load_job_record(job_id)
        if record is not None:
            for event in record.get("events", []):
                if event.get("seq", 0) > last_seq:
                    last_seq = event["seq"]
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("type") == "job_terminal":
                        return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                record = load_job_record(job_id)
                if record is None or record.get("status") in TERMINAL_STATUSES:
                    return
                yield f"data: {json.dumps({'status': 'ping', 'ts': _now_ts()})}\n\n"
                continue
            if event.get("seq", 0) <= last_seq:
                continue
            last_seq = event["seq"]
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "job_terminal":
                return
    finally:
        live.queues.discard(queue)


# ---------------------------------------------------------------------------
# Tracked ffmpeg execution (adapted from api/utils.run_ffmpeg_stream)
# ---------------------------------------------------------------------------

_RE_TIME = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


def _parse_ffmpeg_time(line: str) -> float | None:
    m = _RE_TIME.search(line)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return None


async def run_ffmpeg_tracked(ctx: JobContext, cmd: list, *,
                             label: str = "",
                             target_duration: float = 0.0,
                             progress_start: int = 0,
                             progress_end: int = 100,
                             step_label: str | None = None) -> int:
    """Run ffmpeg, emitting log/progress events like run_ffmpeg_stream.

    Returns ffmpeg's return code. Raises JobCancelled (after killing the
    process) when the job is cancelled. Progress events update the job
    record's overall progress within [progress_start, progress_end].
    """
    from api.utils import now_ts as _now_ts_util

    start_time = time.time()
    last_heartbeat = start_time
    last_ffmpeg_time = 0.0
    limit = 10 * 1024 * 1024

    def calc_progress(ffmpeg_pos: float, elapsed: float) -> int:
        prange = progress_end - progress_start
        if target_duration > 0 and ffmpeg_pos > 0:
            ratio = min(ffmpeg_pos / target_duration, 1.0)
        else:
            ratio = min((elapsed / 120) ** 0.5, 0.98)
        return progress_start + int(ratio * prange)

    kwargs = {}
    if os.name == "posix":
        kwargs["start_new_session"] = True
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=limit,
            **kwargs,
        )
    except Exception as e:
        ctx.emit({"status": "error", "log": f"Failed to start FFmpeg: {e}",
                  "ts": _now_ts_util(), "elapsed": 0})
        return -1

    ctx.proc = proc
    leftover = b""
    rc = -1
    try:
        while True:
            ctx.check_cancelled()
            now = time.time()
            elapsed = now - start_time
            try:
                chunk = await asyncio.wait_for(proc.stderr.read(4096), timeout=1.0)
            except asyncio.TimeoutError:
                if now - last_heartbeat >= 3.0:
                    last_heartbeat = now
                    prog = calc_progress(last_ffmpeg_time, elapsed)
                    ctx.emit({"status": "ping", "ts": _now_ts_util(),
                              "elapsed": round(elapsed, 1), "progress": prog})
                    ctx.set_progress(prog)
                if proc.returncode is not None:
                    break
                continue
            except asyncio.CancelledError:
                raise
            except Exception:
                break

            if not chunk:
                break

            data = leftover + chunk
            lines = data.split(b"\n")
            leftover = lines[-1]
            for line in lines[:-1]:
                decoded = line.decode("utf-8", errors="ignore").strip()
                if not decoded:
                    continue
                elapsed = time.time() - start_time
                ft = _parse_ffmpeg_time(decoded)
                if ft is not None:
                    last_ffmpeg_time = ft
                prog = calc_progress(last_ffmpeg_time, elapsed)
                ctx.emit({"log": decoded, "ts": _now_ts_util(),
                          "elapsed": round(elapsed, 1), "progress": prog})
                ctx.set_progress(prog)

            if time.time() - last_heartbeat >= 3.0:
                last_heartbeat = time.time()
                elapsed = time.time() - start_time
                prog = calc_progress(last_ffmpeg_time, elapsed)
                ctx.emit({"status": "ping", "ts": _now_ts_util(),
                          "elapsed": round(elapsed, 1), "progress": prog})
                ctx.set_progress(prog)

        if leftover:
            decoded = leftover.decode("utf-8", errors="ignore").strip()
            if decoded:
                elapsed = time.time() - start_time
                prog = calc_progress(last_ffmpeg_time, elapsed)
                ctx.emit({"log": decoded, "ts": _now_ts_util(),
                          "elapsed": round(elapsed, 1), "progress": prog})

        await proc.wait()
        rc = proc.returncode
    except asyncio.CancelledError:
        # Task cancelled from outside (e.g. server shutdown): kill ffmpeg
        # and propagate the cancellation so the job is marked interrupted.
        _kill_proc(proc)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        raise
    except JobCancelled:
        _kill_proc(proc)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        raise
    finally:
        if ctx.proc is proc:
            ctx.proc = None

    # A cancel requested while ffmpeg was running kills the process; its
    # non-zero exit must surface as cancellation, not as a render error.
    if ctx.cancel_event.is_set():
        raise JobCancelled("Job dibatalkan.")

    elapsed = round(time.time() - start_time, 1)
    if rc == 0:
        ctx.emit({"status": "done", "code": 0, "ts": _now_ts_util(),
                  "elapsed": elapsed, "progress": progress_end})
        ctx.set_progress(progress_end)
    else:
        ctx.emit({"status": "error", "code": rc, "ts": _now_ts_util(),
                  "elapsed": elapsed})
    return rc
