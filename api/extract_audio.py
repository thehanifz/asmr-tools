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


@router.post("/api/extract-audio")
async def extract_audio(req: ExtractAudioRequest):
    input_path = Path(req.input_path.strip())

    fmt = req.format.lower() if req.format.lower() in FORMAT_EXT else "mp3"

    # --- Tentukan output path ---
    if req.output_path.strip():
        output_path = Path(req.output_path.strip())
        # BUG A FIX: Paksa ekstensi sesuai format yang dipilih.
        # Kasus umum: user pilih format WAV tapi output_path masih .mp3
        # karena autoFillOutputs() selalu generate _audio.mp3.
        if output_path.suffix.lstrip(".").lower() != fmt:
            output_path = output_path.with_suffix(f".{fmt}")
    else:
        base_dir = Path(req.workspace.strip()) if req.workspace.strip() else input_path.parent
        output_path = base_dir / f"{input_path.stem}_audio.{fmt}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    codec_args = FORMAT_EXT[fmt]

    # BUG B FIX: Tambah -stats_period 0.5 agar FFmpeg kirim progress
    # ke stderr setiap 0.5 detik (default FFmpeg hanya update sekali di akhir
    # untuk audio-only job pendek, sehingga UI terlihat bisu).
    # -nostdin mencegah FFmpeg menunggu stdin yang tidak ada di server context.
    cmd = [
        "ffmpeg", "-y",
        "-nostdin",
        "-stats_period", "0.5",
        "-i", str(input_path),
    ] + codec_args + [str(output_path)]

    return StreamingResponse(
        run_ffmpeg_stream(cmd, label=f"Extract Audio → {fmt.upper()} → {output_path.name}"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Output-Path": str(output_path),   # info tambahan untuk debugging
        },
    )
