"""Endpoint untuk expose environment info ke frontend."""
from fastapi import APIRouter
from core.env import IS_COLAB, USE_NVENC, HAS_RIFE, PUBLIC_URL

router = APIRouter(prefix="/env", tags=["env"])

@router.get("/info")
async def env_info():
    """Return environment capabilities untuk frontend."""
    mode = "colab" if IS_COLAB else "local"
    return {
        "mode": mode,
        "is_colab": IS_COLAB,
        "use_nvenc": USE_NVENC,
        "has_rife": HAS_RIFE,
        "public_url": PUBLIC_URL,
        "encoder": "h264_nvenc" if USE_NVENC else "libx264",
    }
