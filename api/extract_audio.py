"""Extract audio from video file using FFmpeg."""
import asyncio
import os
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from api.utils import stream_lines

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
    async def run():
        input_path = Path(req.input_path.strip())
        if not input_path.exists():
            yield f"[ERROR] File tidak ditemukan: {input_path}\n"
            return

        fmt = req.format.lower() if req.format.lower() in FORMAT_EXT else "mp3"

        if req.output_path.strip():
            output_path = Path(req.output_path.strip())
        else:
            base_dir = Path(req.workspace.strip()) if req.workspace.strip() else input_path.parent
            output_path = base_dir / f"{input_path.stem}_audio.{fmt}"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        codec_args = FORMAT_EXT[fmt]
        cmd = ["ffmpeg", "-y", "-i", str(input_path)] + codec_args + [str(output_path)]

        yield f"[INFO] Input  : {input_path}\n"
        yield f"[INFO] Output : {output_path}\n"
        yield f"[INFO] Format : {fmt.upper()}\n"
        yield f"[RUN] {' '.join(cmd)}\n"

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async for line in stream_lines(proc):
            yield line

        await proc.wait()

        if proc.returncode == 0 and output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            yield f"[DONE] Selesai! Output: {output_path} ({size_mb:.2f} MB)\n"
        else:
            yield f"[ERROR] Gagal extract audio (exit code {proc.returncode})\n"

    return StreamingResponse(run(), media_type="text/plain")
