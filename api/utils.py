"""Shared utilities: FFmpeg runner, file helpers, formatters."""
import asyncio
import json
import os
import time
from datetime import datetime


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


def fmt_elapsed(elapsed: float) -> str:
    """Format elapsed seconds jadi string singkat."""
    s = int(elapsed)
    if s < 60:
        return f"{s}s"
    m = s // 60
    sec = s % 60
    return f"{m}m {sec:02d}s"


def now_ts() -> str:
    """Timestamp HH:MM:SS untuk prefix log."""
    return datetime.now().strftime("%H:%M:%S")


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


async def run_ffmpeg_stream(cmd: list, label: str = ""):
    """Async generator: stream FFmpeg stderr sebagai SSE.
    
    Setiap log line diberi prefix timestamp [HH:MM:SS].
    Setiap 3 detik kirim heartbeat ping supaya frontend tahu proses masih jalan.
    Kirim elapsed_sec di setiap event supaya frontend bisa tampilkan timer.
    """
    limit = 10 * 1024 * 1024
    start_time = time.time()
    last_heartbeat = start_time

    # Kirim event start
    yield f"data: {json.dumps({'status': 'start', 'ts': now_ts(), 'label': label, 'elapsed': 0})}\n\n"

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=limit,
    )

    leftover = b""
    while True:
        # Cek heartbeat setiap iterasi
        now = time.time()
        elapsed = now - start_time

        try:
            chunk = await asyncio.wait_for(process.stderr.read(4096), timeout=1.0)
        except asyncio.TimeoutError:
            # Timeout 1 detik — tidak ada output baru
            # Kirim heartbeat kalau sudah 3 detik sejak heartbeat terakhir
            if now - last_heartbeat >= 3.0:
                last_heartbeat = now
                yield f"data: {json.dumps({'status': 'ping', 'ts': now_ts(), 'elapsed': round(elapsed, 1)})}\n\n"
            # Cek apakah proses sudah selesai
            if process.returncode is not None:
                break
            continue
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
                elapsed = time.time() - start_time
                yield f"data: {json.dumps({'log': decoded, 'ts': now_ts(), 'elapsed': round(elapsed, 1)})}\n\n"

        # Heartbeat setelah burst log
        if time.time() - last_heartbeat >= 3.0:
            last_heartbeat = time.time()
            elapsed = time.time() - start_time
            yield f"data: {json.dumps({'status': 'ping', 'ts': now_ts(), 'elapsed': round(elapsed, 1)})}\n\n"

    # Flush leftover
    if leftover:
        decoded = leftover.decode("utf-8", errors="ignore").strip()
        if decoded:
            elapsed = time.time() - start_time
            yield f"data: {json.dumps({'log': decoded, 'ts': now_ts(), 'elapsed': round(elapsed, 1)})}\n\n"

    await process.wait()
    rc = process.returncode
    elapsed = round(time.time() - start_time, 1)

    if rc == 0:
        yield f"data: {json.dumps({'status': 'done', 'code': 0, 'ts': now_ts(), 'elapsed': elapsed})}\n\n"
    else:
        yield f"data: {json.dumps({'status': 'error', 'code': rc, 'ts': now_ts(), 'elapsed': elapsed})}\n\n"
