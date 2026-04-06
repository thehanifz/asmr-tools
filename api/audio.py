"""Audio processing: loop, normalize (LUFS), fade."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str

router = APIRouter(prefix="/audio", tags=["audio"])


# ── FFmpeg command builder ─────────────────────────────────────────────────

def cmd_audio_loop(
    input_path: str,
    output_path: str,
    duration: int = 3600,
    lufs: float | None = None,
    fade_in: float = 3.0,
    fade_out: float = 5.0,
) -> list:
    """
    Loop + optional loudnorm + fade in/out.

    lufs  : target integrated loudness (e.g. -14). None = skip normalize.
    """
    fade_out_start = max(0, duration - fade_out)
    filters = []

    # Optional loudnorm
    if lufs is not None:
        filters.append(f"loudnorm=I={lufs}:TP=-1.5:LRA=11")

    # Trim to exact duration + reset timestamps
    filters.append(f"atrim=duration={duration},asetpts=PTS-STARTPTS")

    # Fades
    if fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={fade_in}")
    if fade_out > 0:
        filters.append(f"afade=t=out:st={fade_out_start}:d={fade_out}")

    filter_str = ",".join(filters)

    # Choose output codec from extension
    ext = os.path.splitext(output_path)[1].lower()
    codec_args = {
        ".flac": ["-c:a", "flac"],
        ".wav":  ["-c:a", "pcm_s24le"],
        ".m4a":  ["-c:a", "aac", "-b:a", "192k"],
        ".mp3":  ["-c:a", "libmp3lame", "-b:a", "192k"],
    }.get(ext, ["-c:a", "aac", "-b:a", "192k"])

    return [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", input_path,
        "-af", filter_str,
        *codec_args,
        "-t", str(duration),
        output_path,
    ]


# ── Endpoint ─────────────────────────────────────────────────────────────

@router.post("/loop")
async def loop_audio(request: Request):
    """Loop + normalize + fade audio to target duration.

    Payload fields:
      input    : str          — source audio path
      output   : str          — output path (.flac / .m4a / .mp3 / .wav)
      duration : int          — target duration in seconds (default 3600)
      lufs     : float|null   — target LUFS e.g. -14, or null to skip normalize
      fade_in  : float        — fade-in duration seconds (default 3)
      fade_out : float        — fade-out duration seconds (default 5)
    """
    data = await request.json()
    input_path  = data["input"]
    output_path = data["output"]
    duration    = int(data.get("duration", 3600))
    lufs_raw    = data.get("lufs")                          # None or float
    lufs        = float(lufs_raw) if lufs_raw is not None else None
    fade_in     = float(data.get("fade_in",  3.0))
    fade_out    = float(data.get("fade_out", 5.0))

    cmd = cmd_audio_loop(input_path, output_path, duration, lufs, fade_in, fade_out)
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")
