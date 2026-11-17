"""Audio processing: loop seamless BENARAN (teknik rakit_audio.sh Mas Arif).

Teknik yang diterapkan (dari setiajiekaputra01-cmd/tools-asmr):
sumber dipotong 3 (head / tengah / tail), tail + head di-acrossfade menjadi
satu tile yang ujungnya menyatu dengan awalnya, lalu tile itu di-aloop
secara sample-accurate. Versi lama hanya memakai `-stream_loop` (hard cut
di setiap sambungan) — di ASMR sambungan itu terdengar sebagai klik.

Render dijalankan sebagai Job (core/jobs.py): tiling dipecah menjadi
chunk sejajar grid tile, terlepas dari request, bisa dilanjutkan bila
service dimulai ulang. Event SSE yang dialirkan sama persis dengan
versi lama.
"""
import os
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/audio", tags=["audio"])

CODEC_MAP = {
    "mp3":  {"ext": ".mp3",  "args": ["-c:a", "libmp3lame", "-q:a", "0"]},
    "aac":  {"ext": ".m4a",  "args": ["-c:a", "aac", "-b:a", "320k"]},
    "flac": {"ext": ".flac", "args": ["-c:a", "flac", "-compression_level", "5"]},
    "wav":  {"ext": ".wav",  "args": ["-c:a", "pcm_s24le"]},
}


async def get_audio_duration(input_path: str) -> float:
    """Dapatkan durasi audio via ffprobe."""
    info = await get_audio_stream_info(input_path)
    return info["duration"]


async def get_audio_stream_info(input_path: str):
    """Info stream audio: duration (s), sample_rate (Hz), total_samples.

    total_samples dibaca dari duration_ts stream (persis cara
    rakit_audio.sh) agar perhitungan aloop sample-accurate; bila
    duration_ts tidak tersedia, diturunkan dari duration x sample_rate.
    """
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate,duration_ts:format=duration",
        "-of", "default=noprint_wrappers=1",
        input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    fields = {}
    for line in stdout.decode(errors="ignore").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    try:
        duration = float(fields.get("duration", 0) or 0)
    except ValueError:
        duration = 0.0
    try:
        sample_rate = int(fields.get("sample_rate", 0) or 0)
    except ValueError:
        sample_rate = 0
    total_samples = 0
    raw_ts = fields.get("duration_ts", "")
    if raw_ts.lstrip("-").isdigit():
        total_samples = int(raw_ts)
    if total_samples <= 0 and sample_rate > 0 and duration > 0:
        total_samples = int(round(duration * sample_rate))
    return {
        "duration": duration,
        "sample_rate": sample_rate,
        "total_samples": total_samples,
    }


@router.post("/loop")
async def loop_audio(request: Request):
    """Loop audio seamless ke durasi target.

    Payload:
      input    : str   — source audio path
      output   : str   — output path
      duration : int   — target durasi detik (default 3600)
      xfade    : float — durasi crossfade sambungan loop detik (default 2.0;
                         sumber <= 10 detik dibatasi 1 detik, ala rakit_audio.sh)
      format   : str   — mp3 | aac | flac | wav (default aac)
      fade_in  : float — fade-in awal detik (default 0)
      fade_out : float — fade-out akhir detik (default: sama dengan xfade efektif)
    """
    from api.jobs import create_job_with_plan
    from api.utils import fmt_duration
    from core.jobs import attach_stream
    from core.runners import plan_audio_loop

    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid JSON payload: {str(e)}"}
        )

    input_path = data.get("input", "")
    if not input_path:
        return JSONResponse(
            status_code=400,
            content={"error": "Input file path is required"}
        )

    basename = os.path.splitext(os.path.basename(input_path))[0]
    try:
        duration = int(data.get("duration", 3600))
    except (TypeError, ValueError):
        duration = 3600
    label = f"Audio Loop · {basename} → {fmt_duration(duration)}"
    try:
        record = await create_job_with_plan(
            "audio-loop", label, data, plan_audio_loop)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    return StreamingResponse(
        attach_stream(record["id"]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
