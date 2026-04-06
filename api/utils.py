"""Shared utilities: FFmpeg runner, file helpers, formatters."""
import asyncio
import json
import os
import time


def fmt_duration(seconds: float) -> str:
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}j {m:02d}m {sec:02d}s"
    elif m > 0:
        return f"{m}m {sec:02d}s"
    else:
        return f"{sec}s"


def get_file_size_str(path: str) -> str:
    try:
        size = os.path.getsize(path)
        if size >= 1024 ** 3:
            return f"{size / 1024 ** 3:.2f} GB"
        elif size >= 1024 ** 2:
            return f"{size / 1024 ** 2:.1f} MB"
        else:
            return f"{size / 1024:.0f} KB"
    except Exception:
        return "?"


def escape_font_path(path: str) -> str:
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = path[0] + "\\:" + path[2:]
    return path


def safe_remove_file(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    for _ in range(3):
        try:
            os.remove(path)
            return
        except PermissionError:
            time.sleep(0.5)
        except Exception:
            return


async def run_ffmpeg_stream(cmd: list):
    """Async generator: stream FFmpeg stderr as SSE data events."""
    limit = 10 * 1024 * 1024
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=limit,
    )
    leftover = b""
    while True:
        try:
            chunk = await process.stderr.read(4096)
        except Exception:
            break
        if not chunk:
            break
        data = leftover + chunk
        lines = data.split(b"\n")
        leftover = lines[-1]
        for line in lines[:-1]:
            decoded = line.decode("utf-8", errors="ignore").strip()
            if decoded:
                yield f"data: {json.dumps({'log': decoded})}\n\n"
    if leftover:
        decoded = leftover.decode("utf-8", errors="ignore").strip()
        if decoded:
            yield f"data: {json.dumps({'log': decoded})}\n\n"
    await process.wait()
    rc = process.returncode
    if rc == 0:
        yield f"data: {json.dumps({'status': 'done', 'code': 0})}\n\n"
    else:
        yield f"data: {json.dumps({'status': 'error', 'code': rc})}\n\n"
