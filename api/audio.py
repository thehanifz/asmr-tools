"""Audio processing: loop seamless BENARAN (teknik rakit_audio.sh Mas Arif).

Teknik yang diterapkan (dari setiajiekaputra01-cmd/tools-asmr):
sumber dipotong 3 (head / tengah / tail), tail + head di-acrossfade menjadi
satu tile yang ujungnya menyatu dengan awalnya, lalu tile itu di-aloop
secara sample-accurate. Versi lama hanya memakai `-stream_loop` (hard cut
di setiap sambungan) — di ASMR sambungan itu terdengar sebagai klik.
"""
import os
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from api.utils import run_ffmpeg_stream, get_file_size_str
from core.audio_filters import build_seamless_loop_filter, effective_crossfade
from core.env import get_thread_flags

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


async def stream_audio_loop(input_path, output_path, duration, xfade, fmt,
                            fade_in=0.0, fade_out=None):
    """Generator: loop audio seamless ke durasi target (acrossfade head-tail)."""
    import json, time
    from api.utils import now_ts, fmt_elapsed

    codec_info = CODEC_MAP.get(fmt, CODEC_MAP["mp3"])
    codec_args = codec_info["args"]
    start = time.time()

    yield f"data: {json.dumps({'status': 'start', 'ts': now_ts(), 'label': f'Audio Loop → {fmt.upper()}', 'elapsed': 0})}\n\n"

    # Dapatkan info sumber (durasi + sample rate + total sampel)
    info = await get_audio_stream_info(input_path)
    src_dur = info["duration"]
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
        if fade_in and fade_in > 0:
            filter_str += f",afade=t=in:d={fade_in:.3f}:curve=tri"
        eff_out = xfade if fade_out is None else fade_out
        if eff_out and eff_out > 0 and duration > eff_out:
            filter_str += f",afade=t=out:st={duration - eff_out:.3f}:d={eff_out:.3f}:curve=tri"
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            *get_thread_flags(),
            "-i", input_path,
            "-af", filter_str,
            *codec_args,
            output_path,
        ]
    else:
        # Seamless loop BENARAN ala rakit_audio.sh:
        # acrossfade tail+head -> tile loopable -> aloop sample-accurate.
        # Bukan -stream_loop lagi (itu hard cut di setiap sambungan).
        xfade_eff = effective_crossfade(src_dur, xfade)
        filter_complex, tile_dur = build_seamless_loop_filter(
            src_dur, info["total_samples"], info["sample_rate"],
            duration, xfade_eff, fade_in=fade_in, fade_out=fade_out,
        )
        yield f"data: {json.dumps({'log': f'Seamless loop: crossfade efektif {xfade_eff:.2f}s, tile {tile_dur:.3f}s ({info['total_samples']} sampel @ {info['sample_rate']} Hz)', 'ts': now_ts(), 'elapsed': 0})}\n\n"
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            *get_thread_flags(),
            "-i", input_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
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
      xfade    : float — durasi crossfade sambungan loop detik (default 2.0;
                         sumber <= 10 detik dibatasi 1 detik, ala rakit_audio.sh)
      format   : str   — mp3 | aac | flac | wav (default aac)
      fade_in  : float — fade-in awal detik (default 0)
      fade_out : float — fade-out akhir detik (default: sama dengan xfade efektif)
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
    fade_in     = float(data.get("fade_in", 0) or 0)
    fade_out    = data.get("fade_out", None)
    fade_out    = None if fade_out is None else float(fade_out)

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
        output_dir = os.path.dirname(input_path)
        basename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"loop_{basename}{CODEC_MAP[fmt]['ext']}")
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
        stream_audio_loop(input_path, output_path, duration, xfade, fmt,
                          fade_in=fade_in, fade_out=fade_out),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
