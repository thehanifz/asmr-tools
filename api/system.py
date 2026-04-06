"""System utilities: open folder."""
import os
import platform
import subprocess
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["system"])


@router.post("/open-folder")
async def open_folder(request: Request):
    data = await request.json()
    folder = data.get("folder", "")
    if not os.path.exists(folder):
        return JSONResponse({"error": "Folder tidak ditemukan"}, status_code=404)
    if platform.system() == "Windows":
        os.startfile(folder)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])
    return {"status": "ok"}
