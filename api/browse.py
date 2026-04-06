"""File/folder browse dialogs via tkinter."""
import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["browse"])


def _open_tk():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    return root


@router.get("/browse")
async def browse_video():
    try:
        from tkinter import filedialog
        root = _open_tk()
        path = filedialog.askopenfilename(
            title="Pilih Video",
            filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv *.webm"), ("All", "*.*")],
        )
        root.destroy()
        return {"path": path.replace("/", os.sep) if path else ""}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/browse-audio")
async def browse_audio():
    try:
        from tkinter import filedialog
        root = _open_tk()
        path = filedialog.askopenfilename(
            title="Pilih Audio",
            filetypes=[("Audio", "*.mp3 *.wav *.ogg *.flac *.m4a"), ("All", "*.*")],
        )
        root.destroy()
        return {"path": path.replace("/", os.sep) if path else ""}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/browse-folder")
async def browse_folder():
    try:
        from tkinter import filedialog
        root = _open_tk()
        path = filedialog.askdirectory(title="Pilih Output Folder")
        root.destroy()
        return {"path": path.replace("/", os.sep) if path else ""}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
