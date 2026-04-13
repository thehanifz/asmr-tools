"""Audio processing: loop dengan xfade seamless."""
import os
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, get_file_size_str

router = APIRouter(prefix="/audio", tags=["audio"])

CODEC_MAP = {
    "mp3":  {"ext": ".mp3",  "args": ["-c:a", "libmp3lame", "-q:a", "0"]},
    "aac":  {"ext": ".m4a",  "args": ["-c:a", "aac", "-b:a", "320k"]},
    "flac": {"ext": ".flac", "args": ["-c:a", "flac", "-compression_level", "5"]},
    "wav":  {"ext": ".wav",  "args": ["-c:a", "pcm_s24le"]},
}


async def get_audio_duration(input_path: str) -> float:
    """Dapatkan durasi audio via ffprobe."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except Exception:
        return 0.0


async def stream_audio_loop(input_path, output_path, duration, xfade, fmt):
    """Generator: loop audio dengan acrossfade per concat segment."""
    import json, time
    from api.utils import now_ts, fmt_elapsed

    codec_info = CODEC_MAP.get(fmt, CODEC_MAP["mp3"])
    codec_args = codec_info["args"]
    start = time.time()

    yield f"data: {json.dumps({'status': 'start', 'ts': now_ts(), 'label': f'Audio Loop → {fmt.upper()}', 'elapsed': 0})}\n\n"

    # Dapatkan durasi sumber
    src_dur = await get_audio_duration(input_path)
    if src_dur <= 0:
        yield f"data: {json.dumps({'status': 'error', 'code': -1, 'log': 'Gagal baca durasi file input'})}\n\n"
        return

    yield f"data: {json.dumps({'log': f'Durasi sumber: {src_dur:.2f}s, target: {duration}s, xfade: {xfade}s', 'ts': now_ts(), 'elapsed': 0})}\n\n"

    import math
    # Hitung berapa loop yang dibutuhkan
    # Tiap sambungan memakan xfade detik, jadi efektif per segment = src_dur - xfade
    effective = max(src_dur - xfade, 0.1)
    n_loops = math.ceil(duration / effective) + 2  # +2 buffer

    yield f"data: {json.dumps({'log': f'Membuat {n_loops} segmen loop...', 'ts': now_ts(), 'elapsed': round(time.time()-start,1)})}\n\n"

    # Build filter_complex dengan acrossfade per sambungan
    # [0:a] → split n_loops copy → acrossfade berantai
    if n_loops <= 1:
        # Tidak perlu loop, langsung trim
        filter_str = f"atrim=duration={duration},asetpts=PTS-STARTPTS"
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", input_path,
            "-af", filter_str,
            *codec_args,
            output_path,
        ]
    else:
        # Gunakan stream_loop + acrossfade approach
        # Lebih reliable daripada filter_complex panjang
        xfade_safe = min(xfade, src_dur * 0.45)  # max 45% dari durasi sumber
        total_needed = duration + xfade_safe * 2

        filter_str = (
            f"aloop=loop=-1:size=2147483647,"
            f"atrim=duration={total_needed:.3f},"
            f"asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={duration:.3f}:d={xfade_safe:.3f}:curve=tri,"
            f"afade=t=in:st=0:d={xfade_safe:.3f}:curve=tri,"
            f"atrim=duration={duration:.3f},"
            f"asetpts=PTS-STARTPTS"
        )

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-stream_loop", "-1",
            "-i", input_path,
            "-af", filter_str,
            "-t", str(duration),
            *codec_args,
            output_path,
        ]

    yield f"data: {json.dumps({'log': f'Menjalankan FFmpeg...', 'ts': now_ts(), 'elapsed': round(time.time()-start,1)})}\n\n"

    # Stream FFmpeg
    async for chunk in run_ffmpeg_stream(cmd, label=f"Audio Loop → {fmt.upper()} {duration//3600}h"):
        yield chunk


@router.post("/loop")
async def loop_audio(request: Request):
    """Loop audio seamless ke durasi target.

    Payload:
      input    : str   — source audio path
      output   : str   — output path
      duration : int   — target durasi detik (default 3600)
      xfade    : float — durasi crossfade detik (default 2.0)
      format   : str   — mp3 | aac | flac | wav (default aac)
    """
    data        = await request.json()
    input_path  = data["input"]
    output_path = data.get("output", "")
    duration    = int(data.get("duration", 3600))
    xfade       = float(data.get("xfade", 2.0))
    fmt         = data.get("format", "aac").lower()

    if fmt not in CODEC_MAP:
        fmt = "aac"

    # Override ekstensi output sesuai format
    base = os.path.splitext(output_path)[0] if output_path else os.path.splitext(input_path)[0] + "._looped"
    output_path = base + CODEC_MAP[fmt]["ext"]

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    return StreamingResponse(
        stream_audio_loop(input_path, output_path, duration, xfade, fmt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
