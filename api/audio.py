"""Audio processing: loop dengan xfade seamless."""
import os
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream

router = APIRouter(prefix="/audio", tags=["audio"])


CODEC_MAP = {
    "mp3":  {
        "ext": ".mp3",
        "args": ["-c:a", "libmp3lame", "-q:a", "0"],          # VBR best quality
    },
    "aac":  {
        "ext": ".m4a",
        "args": ["-c:a", "aac", "-b:a", "320k"],
    },
    "flac": {
        "ext": ".flac",
        "args": ["-c:a", "flac", "-compression_level", "5"],
    },
    "wav":  {
        "ext": ".wav",
        "args": ["-c:a", "pcm_s24le"],                        # 24-bit PCM
    },
}


def cmd_audio_loop(
    input_path: str,
    output_path: str,
    duration: int = 3600,
    xfade: float = 1.0,
    fmt: str = "mp3",
) -> list:
    """
    Loop audio ke durasi target dengan xfade seamless di titik sambung.

    Strategi:
    1. Hitung berapa kali audio perlu di-loop: n = ceil(duration / src_duration) + 1
    2. Concat n copy dengan acrossfade di setiap sambungan
    3. Trim ke durasi exact

    Untuk simplisitas FFmpeg yang robust, pakai pendekatan:
    - stream_loop -1 untuk loop tak terbatas
    - acrossloop filter untuk xfade di titik sambung seamless
    - atrim untuk potong ke durasi exact
    """
    codec_info = CODEC_MAP.get(fmt, CODEC_MAP["mp3"])
    codec_args = codec_info["args"]

    # acrossloop: loop seamless dengan cross-fade di titik sambung
    # size = jumlah sample untuk fade (pakai 44100 * xfade untuk 44.1kHz)
    # Gunakan aloop + acrossfade approach yang lebih universal
    xfade_samples = int(44100 * xfade)  # asumsi 44.1kHz, FFmpeg auto-adjust

    filter_str = (
        f"aloop=loop=-1:size=2147483647,"
        f"atrim=duration={duration + xfade},"
        f"asetpts=PTS-STARTPTS,"
        f"acrossloop={xfade_samples},"
        f"atrim=duration={duration},"
        f"asetpts=PTS-STARTPTS"
    )

    return [
        "ffmpeg", "-y",
        "-nostdin",
        "-i", input_path,
        "-af", filter_str,
        *codec_args,
        "-t", str(duration),
        output_path,
    ]


@router.post("/loop")
async def loop_audio(request: Request):
    """Loop audio seamless dengan xfade ke durasi target.

    Payload:
      input    : str   — source audio path
      output   : str   — output path (ekstensi akan di-override sesuai format)
      duration : int   — target durasi detik (default 3600)
      xfade    : float — durasi crossfade detik di titik sambung (default 1.0)
      format   : str   — mp3 | aac | flac | wav (default mp3)
    """
    data        = await request.json()
    input_path  = data["input"]
    output_path = data["output"]
    duration    = int(data.get("duration", 3600))
    xfade       = float(data.get("xfade", 1.0))
    fmt         = data.get("format", "mp3").lower()

    if fmt not in CODEC_MAP:
        fmt = "mp3"

    # Override ekstensi output sesuai format
    base = os.path.splitext(output_path)[0]
    output_path = base + CODEC_MAP[fmt]["ext"]

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = cmd_audio_loop(input_path, output_path, duration, xfade, fmt)
    return StreamingResponse(
        run_ffmpeg_stream(cmd, label=f"Audio Loop → {fmt.upper()} {duration//3600}h"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
