"""Central router — registers all sub-routers."""
from fastapi import APIRouter
from api import browse, probe, video, audio, merge, thumbnail, system

router = APIRouter()
router.include_router(browse.router)
router.include_router(probe.router)
router.include_router(video.router)
router.include_router(audio.router)
router.include_router(merge.router)
router.include_router(thumbnail.router)
router.include_router(system.router)
