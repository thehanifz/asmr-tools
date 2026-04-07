"""Denoise audio via noisereduce (Python 3.12 subprocess worker)."""
import os
import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

router = APIRouter(tags=["denoise"])

WORKER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "denoise_worker.py")


@router.post("/denoise")
async def denoise_audio(request: Request):
    """Denoise audio using noisereduce library (runs in Python 3.12 subprocess).

    Payload:
      input    : str   - source audio path
      output   : str   - output path (.wav recommended)
      strength : float - prop_decrease 0.0-1.0 (default 0.75)
      chunk    : int   - chunk_size for RAM safety (default 30000)

    Streams SSE progress events.
    """
    data     = await request.json()
    input_p  = data["input"]
    output_p = data["output"]
    strength = float(data.get("strength", 0.75))
    chunk    = int(data.get("chunk", 30000))

    if not os.path.exists(input_p):
        return JSONResponse({"error": f"File tidak ditemukan: {input_p}"}, status_code=400)

    async def run():
        yield f"data: {json.dumps({'log': f'Memulai denoise: {os.path.basename(input_p)}'})}\n\n"
        yield f"data: {json.dumps({'log': f'Strength: {strength:.0%} | Chunk: {chunk}'})}\n\n"

        # Try py -3.12 first, then python3.12, then python
        for py_cmd in ["py", "python3.12", "python"]:
            args = [py_cmd]
            if py_cmd == "py":
                args += ["-3.12"]
            args += [WORKER, input_p, output_p, str(strength), str(chunk)]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode == 0:
                    try:
                        result = json.loads(stdout.decode().strip())
                        size = os.path.getsize(output_p) if os.path.exists(output_p) else 0
                        size_str = f"{size/1024/1024:.1f} MB" if size >= 1024*1024 else f"{size/1024:.0f} KB"
                        yield f"data: {json.dumps({'status': 'done', 'output': output_p, 'size': size_str})}\n\n"
                    except Exception:
                        yield f"data: {json.dumps({'status': 'done', 'output': output_p})}\n\n"
                    return
                else:
                    err = stderr.decode(errors="ignore").strip()
                    # If py -3.12 not found, try next command
                    if "not recognized" in err or "not found" in err or proc.returncode == 9009:
                        continue
                    # Real error from worker
                    yield f"data: {json.dumps({'log': err[-500:] if err else 'Unknown error'})}\n\n"
                    yield f"data: {json.dumps({'status': 'error', 'message': err[-200:]})}\n\n"
                    return
            except FileNotFoundError:
                continue

        yield f"data: {json.dumps({'status': 'error', 'message': 'Python 3.12 tidak ditemukan. Install via Microsoft Store.'})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
