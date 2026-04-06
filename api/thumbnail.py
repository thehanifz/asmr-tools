"""Extract thumbnail from video with optional text overlay."""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, escape_font_path

router = APIRouter(tags=["thumbnail"])


def _esc(s: str) -> str:
    return s.replace("\\", "/").replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")


@router.post("/thumbnail")
async def extract_thumbnail(request: Request):
    data = await request.json()
    input_path = data["input"]
    output_path = data["output"]
    frame_time = data.get("frame_time", 1)
    text1 = _esc(data.get("text1", ""))
    text2 = _esc(data.get("text2", ""))
    raw_font = data.get("font", "C:/Windows/Fonts/arialbd.ttf")
    font = escape_font_path(raw_font)
    color = data.get("color", "white")
    size1 = data.get("size1", 72)
    size2 = data.get("size2", 40)

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
        "-ss", str(frame_time), "-i", input_path,
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "1",
        output_path,
    ]
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")
