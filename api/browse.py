"""File/folder browse dialogs via tkinter.

On a headless server (no $DISPLAY) the native dialog cannot open.
Instead of a 500, return HTTP 200 with an "error" message the UI shows
as a toast, pointing the user at the sound-library dropdown.
"""
import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["browse"])

HEADLESS_MSG = (
    "Dialog berkas tidak tersedia saat tool berjalan sebagai server. "
    "Pilih suara lewat dropdown Pustaka Suara."
)


def _open_tk():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    return root


def _dialog(kind, title, filetypes=None):
    if not os.environ.get("DISPLAY"):
        return JSONResponse({"path": "", "error": HEADLESS_MSG})
    try:
        from tkinter import filedialog
        root = _open_tk()
        if kind == "folder":
            path = filedialog.askdirectory(title=title)
        else:
            path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        root.destroy()
        return {"path": path.replace("/", os.sep) if path else ""}
    except Exception:
        return JSONResponse({"path": "", "error": HEADLESS_MSG})


@router.get("/browse")
async def browse_video():
    return _dialog("file", "Pilih Video",
                   [("Video", "*.mp4 *.mov *.avi *.mkv *.webm"), ("All", "*.*")])


@router.get("/browse-audio")
async def browse_audio():
    return _dialog("file", "Pilih Audio",
                   [("Audio", "*.mp3 *.wav *.ogg *.flac *.m4a"), ("All", "*.*")])


@router.get("/browse-folder")
async def browse_folder():
    return _dialog("folder", "Pilih Output Folder")
