"""Sound library listing — server-side catalog for dropdown pickers.

Scans ASMR_LIBRARY_DIR (default: <repo>/library) whose
subfolders are sound elements (hujan, api, angin, air, petir, burung,
tambahan). Durations are probed once with ffprobe and cached on disk
next to the library so repeat calls are instant.
"""
import json
import os
import subprocess

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

router = APIRouter(tags=["library"])

# Default: <repo>/library (moved into the repo 17 Nov 2026; audio files are
# git-ignored). Same expression as REPO_ROOT below, kept inline because this
# constant is defined before it. A symlink at the old asmr-service/library
# path keeps old absolute paths working.
LIBRARY_DIR = os.environ.get(
    "ASMR_LIBRARY_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "library"),
)
CACHE_FILE = os.path.join(LIBRARY_DIR, ".durations.json")
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac"}
ELEMENT_LABELS = {
    "hujan": "Hujan",
    "api": "Api",
    "angin": "Angin",
    "air": "Air Mengalir",
    "petir": "Petir",
    "burung": "Burung",
    "tambahan": "Tambahan",
}
ELEMENT_ORDER = ["hujan", "api", "angin", "air", "petir", "burung", "tambahan"]


def _probe_duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=20,
        )
        return round(float(out.stdout.strip()), 1)
    except Exception:
        return 0.0


def _load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass


@router.get("/library/play")
async def library_play(path: str):
    """Stream one library file for in-browser preview.

    Only files physically inside LIBRARY_DIR may be served.
    FileResponse honours Range requests, so seeking works.
    """
    base = os.path.realpath(LIBRARY_DIR)
    full = os.path.realpath(path)
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        return JSONResponse({"error": "Berkas di luar pustaka"}, status_code=403)
    if os.path.splitext(full)[1].lower() not in AUDIO_EXTS:
        return JSONResponse({"error": "Bukan berkas audio"}, status_code=400)
    return FileResponse(full)


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_VIDEO_DIR = os.path.join(REPO_ROOT, "media", "video")
MEDIA_AUDIO_DIR = os.path.join(REPO_ROOT, "media", "audio")
MEDIA_CACHE_FILE = os.path.join(REPO_ROOT, "media", ".durations.json")
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _scan_media(folder, exts, cache, cache_prefix):
    items = []
    dirty = False
    if not os.path.isdir(folder):
        return items, dirty
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() not in exts:
            continue
        if name.startswith(("preview_", "fc_sl")):
            continue
        key = f"{cache_prefix}/{name}:{os.path.getmtime(path):.0f}"
        if key not in cache:
            cache[key] = _probe_duration(path)
            dirty = True
        items.append({
            "name": name,
            "path": path,
            "duration": cache[key],
            "size_mb": round(os.path.getsize(path) / 1_000_000, 1),
        })
    return items, dirty


@router.get("/library/files")
async def library_files(kind: str = "video"):
    """Server-side media catalog for the file picker (headless browse).

    kind=video -> media/video. kind=audio -> media/audio plus the
    ASMR sound library groups, so every panel can pick existing
    server files instead of a desktop file dialog.
    """
    try:
        with open(MEDIA_CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    groups = []
    if kind == "video":
        items, dirty = _scan_media(MEDIA_VIDEO_DIR, VIDEO_EXTS, cache, "video")
        if items:
            groups.append({"element": "media-video",
                           "label": "Video di Server", "items": items})
    else:
        items, dirty = _scan_media(MEDIA_AUDIO_DIR, AUDIO_EXTS, cache, "audio")
        if items:
            groups.append({"element": "media-audio",
                           "label": "Audio di Server", "items": items})
        sounds = await library_sounds()
        groups.extend(sounds.get("groups", []))
    if dirty:
        try:
            with open(MEDIA_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        except Exception:
            pass
    return {"groups": groups, "kind": kind}


@router.get("/library/stream")
async def library_stream(path: str, request: Request, dl: int = 0):
    """Range-capable streaming for media/ files (result preview).

    The /media StaticFiles mount in this Starlette version ignores
    Range requests, so browsers cannot seek in long videos. This
    endpoint serves media/video + media/audio files with proper
    206 partial responses. dl=1 forces a download disposition.
    """
    media_root = os.path.realpath(os.path.join(REPO_ROOT, "media"))
    full = os.path.realpath(path)
    if not full.startswith(media_root + os.sep) or not os.path.isfile(full):
        return JSONResponse({"error": "Berkas di luar folder media"}, status_code=403)
    ext = os.path.splitext(full)[1].lower()
    if ext not in VIDEO_EXTS | AUDIO_EXTS:
        return JSONResponse({"error": "Bukan berkas media"}, status_code=400)

    size = os.path.getsize(full)
    range_header = request.headers.get("range", "")
    start, end = 0, size - 1
    status = 200
    if range_header.startswith("bytes="):
        try:
            first, _, last = range_header[6:].partition("-")
            if first:
                start = int(first)
            if last:
                end = min(int(last), size - 1)
            status = 206
        except ValueError:
            start, end, status = 0, size - 1, 200
    length = end - start + 1

    def _chunks():
        with open(full, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    if dl:
        headers["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(full)}"'
        )
    media_type = "video/mp4" if ext in VIDEO_EXTS else "audio/mpeg"
    return StreamingResponse(_chunks(), status_code=status,
                             headers=headers, media_type=media_type)


@router.get("/library/sounds")
async def library_sounds():
    groups = []
    if not os.path.isdir(LIBRARY_DIR):
        return {"groups": [], "library_dir": LIBRARY_DIR}

    cache = _load_cache()
    dirty = False
    elements = [e for e in ELEMENT_ORDER if os.path.isdir(os.path.join(LIBRARY_DIR, e))]
    elements += sorted(
        d for d in os.listdir(LIBRARY_DIR)
        if os.path.isdir(os.path.join(LIBRARY_DIR, d)) and d not in elements
    )
    for element in elements:
        folder = os.path.join(LIBRARY_DIR, element)
        items = []
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            if os.path.splitext(name)[1].lower() not in AUDIO_EXTS:
                continue
            # Engine temp artifacts land next to source files; never list them
            # (preview_* covers preview_mix_temp; a "_temp" substring check
            # wrongly hid oriental_temple.ogg, so it was dropped 17 Nov 2026)
            if name.startswith(("preview_", "fc_sl")):
                continue
            key = f"{element}/{name}:{os.path.getmtime(path):.0f}"
            if key not in cache:
                cache[key] = _probe_duration(path)
                dirty = True
            items.append({
                "name": name,
                "path": path,
                "duration": cache[key],
            })
        if items:
            groups.append({
                "element": element,
                "label": ELEMENT_LABELS.get(element, element.title()),
                "items": items,
            })
    if dirty:
        _save_cache(cache)
    return {"groups": groups, "library_dir": LIBRARY_DIR}
