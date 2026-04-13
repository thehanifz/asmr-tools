"""Extract audio from video file using FFmpeg."""
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from api.utils import run_ffmpeg_stream

router = APIRouter()

FORMAT_EXT = {
    "mp3":  ["-vn", "-acodec", "libmp3lame", "-q:a", "2"],
    "wav":  ["-vn", "-acodec", "pcm_s16le"],
    "aac":  ["-vn", "-acodec", "aac", "-b:a", "192k"],
    "flac": ["-vn", "-acodec", "flac"],
    "ogg":  ["-vn", "-acodec", "libvorbis", "-q:a", "5"],
}


class ExtractAudioRequest(BaseModel):
    input_path: str
    output_path: str = ""
    format: str = "mp3"   # mp3 | wav | aac | flac | ogg
    workspace: str = ""


# FIX: hapus prefix /api/ — server.py sudah include_router dengan prefix='/api'
# sehingga route ini terdaftar sebagai /api/extract-audio (bukan /api/api/extract-audio)
@router.post("/extract-audio")
async def extract_audio(req: ExtractAudioRequest):
    input_path = Path(req.input_path.strip())

    fmt = req.format.lower() if req.format.lower() in FORMAT_EXT else "mp3"

    # Tentukan output path
    if req.output_path.strip():
        output_path = Path(req.output_path.strip())
        # Paksa ekstensi sesuai format yang dipilih
        if output_path.suffix.lstrip(".").lower() != fmt:
            output_path = output_path.with_suffix(f".{fmt}")
    else:
        base_dir = Path(req.workspace.strip()) if req.workspace.strip() else input_path.parent
        output_path = base_dir / f"{input_path.stem}_audio.{fmt}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    codec_args = FORMAT_EXT[fmt]

    cmd = [
        "ffmpeg", "-y",
        "-nostdin",
        "-stats_period", "0.5",
        "-i", str(input_path),
    ] + codec_args + [str(output_path)]

    return StreamingResponse(
        run_ffmpeg_stream(cmd, label=f"Extract Audio \u2192 {fmt.upper()} \u2192 {output_path.name}"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
