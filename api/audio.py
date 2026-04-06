"""Audio processing: loop, normalize, fade."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file

router = APIRouter(prefix="/audio", tags=["audio"])


# ── FFmpeg command builders ──────────────────────────────────────

def cmd_audio_loop(
    input_path: str,
    output_path: str,
    duration: int = 3600,
    volume_db: float = 0.0,
    fade_in: float = 2.0,
    fade_out: float = 3.0,
    normalize: bool = True,
) -> list:
    """
    Loop audio to target duration with:
    - volume adjustment
    - optional loudnorm (-14 LUFS YouTube standard)
    - fade in / fade out
    """
    fade_out_start = duration - fade_out
    filters = []

    if normalize:
        filters.append("loudnorm=I=-14:TP=-1.5:LRA=11")
    if volume_db != 0:
        filters.append(f"volume={volume_db}dB")
    filters.append(f"atrim=duration={duration},asetpts=PTS-STARTPTS")
    filters.append(f"afade=t=in:st=0:d={fade_in}")
    filters.append(f"afade=t=out:st={fade_out_start}:d={fade_out}")

    filter_str = ",".join(filters)
    return [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", input_path,
        "-filter_complex", filter_str,
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        output_path,
    ]


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/loop")
async def loop_audio(request: Request):
    """Loop + normalize + fade audio file to target duration."""
    data = await request.json()
    input_path = data["input"]
    output_path = data["output"]
    duration = int(data.get("duration", 3600))
    volume_db = float(data.get("volume_db", 0.0))
    fade_in = float(data.get("fade_in", 2.0))
    fade_out = float(data.get("fade_out", 3.0))
    normalize = bool(data.get("normalize", True))

    cmd = cmd_audio_loop(input_path, output_path, duration, volume_db, fade_in, fade_out, normalize)
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")
