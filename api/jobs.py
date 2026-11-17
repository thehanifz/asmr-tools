"""Jobs API: persistent, resumable renders.

Endpoints:
  GET    /api/jobs                  list all jobs (newest first)
  GET    /api/jobs/{id}             one job + recent events
  GET    /api/jobs/{id}/stream      SSE attach (replay + live follow)
  POST   /api/jobs/{id}/resume      resume an interrupted/error/cancelled job
  POST   /api/jobs/{id}/cancel      cancel a running/queued job
  DELETE /api/jobs/{id}             delete record + workdir (refused while live)

Legacy render endpoints create jobs through create_job_with_plan() and
then stream attach_stream() so existing panels keep working unchanged.
"""
import inspect

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.utils import now_ts
from core.jobs import (
    RESUMABLE_STATUSES,
    STATUS_QUEUED,
    append_record_event,
    attach_stream,
    cancel_job,
    create_job_record,
    delete_job_record,
    is_live,
    list_job_records,
    load_job_record,
    save_job_record,
    job_workdir,
    start_job,
)
from core.runners import register_all_runners

register_all_runners()

router = APIRouter(prefix="/jobs", tags=["jobs"])

JOB_TYPE_LABELS = {
    "sound-layer": "Sound Layer",
    "video-pipeline": "Video Loop",
    "loop-ba": "Loop B+A",
    "audio-loop": "Audio Loop",
}


def public_job(record: dict, include_events: bool = False) -> dict:
    events = record.get("events", [])
    last_log = None
    for event in reversed(events):
        if event.get("log"):
            last_log = event["log"]
            break
    out = {
        "id": record.get("id"),
        "type": record.get("type"),
        "type_label": JOB_TYPE_LABELS.get(record.get("type"), record.get("type")),
        "label": record.get("label"),
        "status": record.get("status"),
        "progress": record.get("progress", 0),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "started_at": record.get("started_at"),
        "finished_at": record.get("finished_at"),
        "output_path": record.get("output_path"),
        "segments_total": record.get("segments_total", 0),
        "segments_done": record.get("segments_done", []),
        "segments_done_count": len(record.get("segments_done", [])),
        "error": record.get("error"),
        "live": is_live(record["id"]),
        "last_log": last_log,
    }
    if include_events:
        out["events"] = events[-80:]
    return out


async def create_job_with_plan(job_type: str, label: str, payload: dict,
                               planner) -> dict:
    """Create a record, run the planner against its workdir, start the job.

    ``planner`` is ``(payload, workdir) -> plan`` (sync or async). On
    planner failure the empty shell record is removed and the exception
    propagates (the caller maps ValueError to HTTP 400).
    """
    record = create_job_record(job_type, label, payload, {}, "")
    try:
        plan = planner(payload, job_workdir(record["id"]))
        if inspect.isawaitable(plan):
            plan = await plan
    except Exception:
        delete_job_record(record["id"])
        raise
    record["plan"] = plan
    record["output_path"] = plan.get("output_path", "")
    record["segments_total"] = int(plan.get("segments_total", 0) or 0)
    save_job_record(record)
    start_job(record["id"])
    return record


@router.get("")
async def list_jobs():
    return {"jobs": [public_job(r) for r in list_job_records()]}


@router.get("/{job_id}")
async def get_job(job_id: str):
    record = load_job_record(job_id)
    if record is None:
        return JSONResponse({"error": "Job tidak ditemukan"}, status_code=404)
    return public_job(record, include_events=True)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, since: int = 0):
    if load_job_record(job_id) is None:
        return JSONResponse({"error": "Job tidak ditemukan"}, status_code=404)
    return StreamingResponse(
        attach_stream(job_id, since_seq=since),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{job_id}/resume")
async def resume_job(job_id: str):
    record = load_job_record(job_id)
    if record is None:
        return JSONResponse({"error": "Job tidak ditemukan"}, status_code=404)
    if is_live(job_id):
        return JSONResponse({"error": "Job sedang berjalan"}, status_code=409)
    if record.get("status") not in RESUMABLE_STATUSES:
        return JSONResponse(
            {"error": f"Job berstatus {record.get('status')} tidak bisa dilanjutkan"},
            status_code=409)
    record["status"] = STATUS_QUEUED
    record["error"] = None
    record["finished_at"] = None
    append_record_event(record, {
        "log": "▶ Job dilanjutkan dari checkpoint terakhir.",
        "ts": now_ts(),
    })
    save_job_record(record)
    try:
        start_job(job_id)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    return public_job(load_job_record(job_id))


@router.post("/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str):
    record = await cancel_job(job_id)
    if record is None:
        return JSONResponse({"error": "Job tidak ditemukan"}, status_code=404)
    return public_job(record)


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    record = load_job_record(job_id)
    if record is None:
        return JSONResponse({"error": "Job tidak ditemukan"}, status_code=404)
    if is_live(job_id):
        return JSONResponse(
            {"error": "Job sedang berjalan — batalkan dulu sebelum menghapus"},
            status_code=409)
    delete_job_record(job_id)
    return {"deleted": True, "id": job_id}
