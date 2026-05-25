"""Shared utilities: FFmpeg runner, file helpers, formatters."""
import asyncio
import json
import os
import re
import time
from datetime import datetime


def fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}j {m:02d}m {sec:02d}s"
    elif m > 0:
        return f"{m}m {sec:02d}s"
    else:
        return f"{sec}s"


def fmt_elapsed(elapsed: float) -> str:
    s = int(elapsed)
    if s < 60:
        return f"{s}s"
    m = s // 60
    sec = s % 60
    return f"{m}m {sec:02d}s"


def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def get_file_size_str(path: str) -> str:
    try:
        size = os.path.getsize(path)
        if size >= 1024 ** 3:
            return f"{size / 1024 ** 3:.2f} GB"
        elif size >= 1024 ** 2:
            return f"{size / 1024 ** 2:.1f} MB"
        else:
            return f"{size / 1024:.0f} KB"
    except Exception:
        return "?"


def escape_font_path(path: str) -> str:
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = path[0] + "\\:" + path[2:]
    return path


def safe_remove_file(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    for _ in range(3):
        try:
            os.remove(path)
            return
        except PermissionError:
            time.sleep(0.5)
        except Exception:
            return


# Regex untuk parse "time=HH:MM:SS.xx" dari stderr FFmpeg
_RE_TIME = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


def _parse_ffmpeg_time(line: str) -> float | None:
    """Ekstrak posisi waktu (detik) dari baris stderr FFmpeg."""
    m = _RE_TIME.search(line)
    if m:
        h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mn * 60 + s
    return None


async def run_ffmpeg_stream(
    cmd: list,
    label: str = "",
    progress_start: int = 0,
    progress_end: int = 100,
    target_duration: float = 0.0,
):
    """
    Async generator: stream FFmpeg stderr sebagai SSE.

    - Kirim log line-by-line dari stderr.
    - Kirim `progress` (0-100) berdasarkan waktu render vs target_duration.
      Jika target_duration=0, progress dihitung dari elapsed time heuristic.
    - progress_start / progress_end: range progress untuk multi-pass render.
      Contoh: Pass-1 pakai (22, 60), Pass-2 pakai (64, 98).
    """
    limit = 10 * 1024 * 1024
    start_time = time.time()
    last_heartbeat = start_time
    last_ffmpeg_time = 0.0

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=limit,
    )

    def _calc_progress(ffmpeg_pos: float, elapsed: float) -> int:
        prange = progress_end - progress_start
        if target_duration > 0 and ffmpeg_pos > 0:
            ratio = min(ffmpeg_pos / target_duration, 1.0)
        else:
            # Heuristic: gunakan sqrt(elapsed/120) sebagai estimasi kasar
            ratio = min((elapsed / 120) ** 0.5, 0.98)
        return progress_start + int(ratio * prange)

    leftover = b""
    while True:
        now = time.time()
        elapsed = now - start_time

        try:
            chunk = await asyncio.wait_for(process.stderr.read(4096), timeout=1.0)
        except asyncio.TimeoutError:
            if now - last_heartbeat >= 3.0:
                last_heartbeat = now
                prog = _calc_progress(last_ffmpeg_time, elapsed)
                yield f"data: {json.dumps({'status': 'ping', 'ts': now_ts(), 'elapsed': round(elapsed, 1), 'progress': prog})}\n\n"
            if process.returncode is not None:
                break
            continue
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

            # Parse FFmpeg time position
            ft = _parse_ffmpeg_time(decoded)
            if ft is not None:
                last_ffmpeg_time = ft

            prog = _calc_progress(last_ffmpeg_time, elapsed)
            yield f"data: {json.dumps({'log': decoded, 'ts': now_ts(), 'elapsed': round(elapsed, 1), 'progress': prog})}\n\n"

        if time.time() - last_heartbeat >= 3.0:
            last_heartbeat = time.time()
            elapsed = time.time() - start_time
            prog = _calc_progress(last_ffmpeg_time, elapsed)
            yield f"data: {json.dumps({'status': 'ping', 'ts': now_ts(), 'elapsed': round(elapsed, 1), 'progress': prog})}\n\n"

    # Flush leftover
    if leftover:
        decoded = leftover.decode("utf-8", errors="ignore").strip()
        if decoded:
            elapsed = time.time() - start_time
            prog = _calc_progress(last_ffmpeg_time, elapsed)
            yield f"data: {json.dumps({'log': decoded, 'ts': now_ts(), 'elapsed': round(elapsed, 1), 'progress': prog})}\n\n"

    await process.wait()
    rc = process.returncode
    elapsed = round(time.time() - start_time, 1)

    if rc == 0:
        yield f"data: {json.dumps({'status': 'done', 'code': 0, 'ts': now_ts(), 'elapsed': elapsed, 'progress': progress_end})}\n\n"
    else:
        yield f"data: {json.dumps({'status': 'error', 'code': rc, 'ts': now_ts(), 'elapsed': elapsed})}\n\n"
