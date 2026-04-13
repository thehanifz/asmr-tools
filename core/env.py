"""Environment detection & GPU capability resolver.

Import dari mana saja:
    from core.env import IS_COLAB, USE_NVENC, HAS_RIFE, resolve_output_path, PUBLIC_URL
"""
import os
import shutil
import subprocess
from functools import lru_cache

# ── 1. Deteksi environment ─────────────────────────────────────────────────────
def _detect_colab() -> bool:
    try:
        import google.colab  # noqa: F401
        return True
    except ImportError:
        pass
    # Fallback: cek env var yang Colab selalu set
    return os.environ.get("COLAB_GPU") is not None or os.path.isdir("/content")

IS_COLAB: bool = _detect_colab()

# ── 2. Deteksi NVENC (GPU encoder) ────────────────────────────────────────────
@lru_cache(maxsize=1)
def _check_nvenc() -> bool:
    """Return True jika FFmpeg tersedia dan support nvenc."""
    if shutil.which("ffmpeg") is None:
        return False
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False

USE_NVENC: bool = IS_COLAB and _check_nvenc()

# ── 3. Deteksi RIFE ───────────────────────────────────────────────────────────
def _check_rife() -> bool:
    rife_dir = "/content/Practical-RIFE"
    model_dir = os.path.join(rife_dir, "train_log")
    script    = os.path.join(rife_dir, "inference_video.py")
    return (
        IS_COLAB
        and os.path.isdir(rife_dir)
        and os.path.exists(model_dir)
        and os.path.isfile(script)
    )

HAS_RIFE: bool = _check_rife()

# ── 4. Public URL (diisi oleh start_colab.py saat tunnel aktif) ───────────────
PUBLIC_URL: str = os.environ.get("ASMR_PUBLIC_URL", "")

# ── 5. Path resolver ──────────────────────────────────────────────────────────
def resolve_output_path(filename: str, subdir: str = "outputs") -> str:
    """Return path output yang sesuai environment.

    - Colab  : /content/drive/MyDrive/RIFE/{subdir}/{filename}
    - Lokal  : path filename apa adanya (sudah diisi frontend)
    """
    if IS_COLAB:
        base = f"/content/drive/MyDrive/RIFE/{subdir}"
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, filename)
    return filename

# ── 6. Encoder helper ─────────────────────────────────────────────────────────
def video_encoder_flags(crf: int = 23, preset: str = "fast") -> list[str]:
    """Return FFmpeg encoder flags yang optimal untuk environment saat ini.

    - NVENC tersedia : h264_nvenc dengan cq (quality target)
    - Fallback       : libx264 dengan crf
    """
    if USE_NVENC:
        # NVENC: -cq setara crf, -preset p4 = medium quality/speed balance
        nvenc_preset_map = {
            "ultrafast": "p1", "superfast": "p2", "veryfast": "p3",
            "faster": "p3",   "fast": "p4",      "medium": "p5",
            "slow": "p6",     "slower": "p7",    "veryslow": "p7",
        }
        np_ = nvenc_preset_map.get(preset, "p4")
        return [
            "-c:v", "h264_nvenc",
            "-preset", np_,
            "-cq", str(crf),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]
    else:
        return [
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]

def audio_thread_flags() -> list[str]:
    """Return FFmpeg threading flags untuk audio processing."""
    # -threads 0 = auto-detect jumlah core, membantu operasi audio panjang
    return ["-threads", "0"]
