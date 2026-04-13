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
    """Generator: loop audio seamless ke durasi target."""
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

    # Validasi duration
    if duration <= 0:
        yield f"data: {json.dumps({'status': 'error', 'code': -2, 'log': 'Durasi target harus lebih dari 0'})}\n\n"
        return

    yield f"data: {json.dumps({'log': f'Durasi sumber: {src_dur:.2f}s, target: {duration}s, xfade: {xfade}s', 'ts': now_ts(), 'elapsed': 0})}\n\n"

    # Jika source sudah lebih panjang dari target, langsung trim tanpa loop
    if src_dur >= duration:
        filter_str = f"atrim=duration={duration},asetpts=PTS-STARTPTS"
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", input_path,
            "-af", filter_str,
            *codec_args,
            output_path,
        ]
    else:
        # Loop dengan crossfade di akhir
        xfade_safe = min(xfade, src_dur * 0.45)  # max 45% dari durasi sumber

        # Filter: infinite loop → trim ke durasi target + fade out → fade out di akhir
        filter_str = (
            f"aloop=loop=-1:size=2147483647,"
            f"atrim=duration={duration:.3f},"
            f"asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={duration - xfade_safe:.3f}:d={xfade_safe:.3f}:curve=tri"
        )

        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-stream_loop", "-1",
            "-i", input_path,
            "-af", filter_str,
            *codec_args,
            output_path,
        ]

    yield f"data: {json.dumps({'log': f'Menjalankan FFmpeg...', 'ts': now_ts(), 'elapsed': round(time.time()-start,1)})}\n\n"

    # Stream FFmpeg
    async for chunk in run_ffmpeg_stream(cmd, label=f"Audio Loop → {fmt.upper()} {duration//3600}h"):
        yield chunk

    # Kirim final output path ke frontend
    import os
    if os.path.exists(output_path):
        size_str = get_file_size_str(output_path)
        yield f"data: {json.dumps({'status': 'done', 'output': output_path, 'size': size_str, 'ts': now_ts()})}\n\n"


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
    import json
    
    try:
        data = await request.json()
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid JSON payload: {str(e)}"}
        )
    
    input_path  = data.get("input", "")
    output_path = data.get("output", "")
    duration    = int(data.get("duration", 3600))
    xfade       = float(data.get("xfade", 2.0))
    fmt         = data.get("format", "aac").lower()

    if not input_path:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"error": "Input file path is required"}
        )

    if not os.path.exists(input_path):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"error": f"Input file does not exist: {input_path}"}
        )

    if fmt not in CODEC_MAP:
        fmt = "aac"

    # Tentukan output path:
    # - Jika user tidak kasih output, pakai default dari input path
    # - Jika user kasih output, ganti ekstensi sesuai format yang dipilih
    if not output_path:
        base = os.path.splitext(input_path)[0]
        output_path = base + "._looped" + CODEC_MAP[fmt]["ext"]
    else:
        # Ganti ekstensi sesuai format, tapi tetap filename user
        name_without_ext = os.path.splitext(output_path)[0]
        output_path = name_without_ext + CODEC_MAP[fmt]["ext"]

    output_dir = os.path.dirname(os.path.abspath(output_path))
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"error": f"Cannot create output directory: {str(e)}"}
        )

    return StreamingResponse(
        stream_audio_loop(input_path, output_path, duration, xfade, fmt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
