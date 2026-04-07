"""Central router — includes all sub-routers."""
from fastapi import APIRouter
from api import probe, browse, video, audio, merge, thumbnail, system, denoise, extract_audio

router = APIRouter()

router.include_router(probe.router)
router.include_router(browse.router)
router.include_router(video.router)
router.include_router(audio.router)
router.include_router(merge.router)
router.include_router(thumbnail.router)
router.include_router(system.router)
router.include_router(denoise.router)
router.include_router(extract_audio.router)
