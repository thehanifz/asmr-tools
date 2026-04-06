"""Extract thumbnail from video. Serve preview via GET endpoint."""
import os
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from api.utils import run_ffmpeg_stream

router = APIRouter(tags=["thumbnail"])


def _esc(s: str) -> str:
    """Escape special chars for ffmpeg drawtext filter."""
    return s.replace("\\", "/").replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")


@router.post("/thumbnail")
async def extract_thumbnail(request: Request):
    """Extract a single frame as JPEG thumbnail.

    Payload fields:
      input    : str   — source video path
      output   : str   — output JPEG path
      time_sec : float — timestamp in seconds (default 5)
      text1    : str   — optional overlay text line 1
      text2    : str   — optional overlay text line 2
      font     : str   — font path (default Arial Bold)
      color    : str   — text color (default 'white')
      size1    : int   — font size line 1 (default 72)
      size2    : int   — font size line 2 (default 40)

    Returns JSON: {"status": "done", "output": path} or {"error": msg}
    """
    data       = await request.json()
    input_path = data["input"]
    output_path = data["output"]
    time_sec   = float(data.get("time_sec", data.get("frame_time", 5)))  # accept both
    text1      = _esc(data.get("text1", ""))
    text2      = _esc(data.get("text2", ""))
    raw_font   = data.get("font", "C:/Windows/Fonts/arialbd.ttf")
    font       = raw_font.replace("\\", "/").replace(":", "\\:")
    color      = data.get("color", "white")
    size1      = int(data.get("size1", 72))
    size2      = int(data.get("size2", 40))

    if not os.path.exists(input_path):
        return JSONResponse({"error": f"File not found: {input_path}"}, status_code=400)

    # Build vf filter
    if text1:
        vf = (
            f"drawtext=text='{text1}':fontfile='{font}':fontsize={size1}"
            f":fontcolor={color}:x=50:y=50:shadowcolor=black:shadowx=3:shadowy=3"
        )
        if text2:
            vf += (
                f",drawtext=text='{text2}':fontfile='{font}':fontsize={size2}"
                f":fontcolor=yellow:x=50:y={50+size1+10}:shadowcolor=black:shadowx=2:shadowy=2"
            )
    else:
        vf = "scale=iw:ih"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time_sec), "-i", input_path,
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "2",
        output_path,
    ]

    # Run sync (thumbnail is fast, ~1s) via subprocess
    import subprocess
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            err = result.stderr.decode(errors="ignore").strip().splitlines()
            return JSONResponse({"error": err[-1] if err else "ffmpeg error"}, status_code=500)
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Timeout generating thumbnail"}, status_code=500)
    except FileNotFoundError:
        return JSONResponse({"error": "ffmpeg not found"}, status_code=500)

    size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    return JSONResponse({"status": "done", "output": output_path, "size": size})


@router.get("/thumbnail/preview")
async def thumbnail_preview(path: str = Query(..., description="Absolute path to thumbnail image")):
    """Serve a thumbnail image file directly to the browser.

    Used by the frontend to display the thumbnail preview.
    GET /api/thumbnail/preview?path=C:/path/to/thumbnail.jpg
    """
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    # Security: only serve image files
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(status_code=400, detail="Only image files allowed")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")

    return FileResponse(path, media_type=media_type)
