"""Loop B+A (Video Segment Swap) backend logic.

Dijalankan sebagai Job (core/jobs.py): render terlepas dari request,
checkpoint per langkah (hard-cut) atau satu segmen (crossfade), bisa
dilanjutkan bila service dimulai ulang. Event SSE yang dialirkan sama
persis dengan versi lama.
"""
import os
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse

router = APIRouter(prefix="/loop-ba", tags=["loop-ba"])


@router.post("/render")
async def render_loop_ba(request: Request):
    from api.jobs import create_job_with_plan
    from core.jobs import attach_stream
    from core.runners import plan_loop_ba

    try:
        data = await request.json()
        input_path = data.get("input_path", "").strip()
        basename = os.path.splitext(os.path.basename(input_path))[0]
        transition_type = data.get("transition_type", "hard_cut")
        label = f"Loop B+A · {basename or 'video'} ({transition_type})"
        record = await create_job_with_plan(
            "loop-ba", label, data, plan_loop_ba)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return StreamingResponse(
        attach_stream(record["id"]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/download")
async def download_file(path: str = Query(..., description="Absolute path to file")):
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    filename = os.path.basename(path)
    return FileResponse(path, media_type="application/octet-stream", filename=filename)
