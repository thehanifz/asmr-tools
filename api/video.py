"""Video processing: crop, upscale, loop."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file

router = APIRouter(prefix="/video", tags=["video"])


# ── FFmpeg command builders ──────────────────────────────────────

def cmd_crop(input_path: str, output_path: str, pixels: int = 50) -> list:
    return [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"crop=in_w:in_h-{pixels}:0:0",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]


def cmd_upscale(input_path: str, output_path: str, algo: str = "lanczos", crf: int = 23) -> list:
    return [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale=1920:1080:flags={algo}",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
        "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "copy",
        output_path,
    ]


def cmd_loop_copy(input_path: str, output_path: str, duration: int, video_duration: float) -> list:
    """Loop video using stream copy (no re-encode). Audio stripped."""
    loops = max(1, int(duration / video_duration) + 10)
    return [
        "ffmpeg", "-y",
        "-stream_loop", str(loops), "-i", input_path,
        "-t", str(duration),
        "-an", "-c:v", "copy",
        output_path,
    ]


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/crop")
async def crop_video(request: Request):
    data = await request.json()
    cmd = cmd_crop(
        data["input"], data["output"],
        int(data.get("pixels", 50)),
    )
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")


@router.post("/upscale")
async def upscale_video(request: Request):
    data = await request.json()
    cmd = cmd_upscale(
        data["input"], data["output"],
        data.get("algo", "lanczos"),
        int(data.get("crf", 23)),
    )
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")


@router.post("/loop")
async def loop_video(request: Request):
    """Loop video (stream copy, no audio) to target duration."""
    data = await request.json()
    cmd = cmd_loop_copy(
        data["input"], data["output"],
        int(data.get("duration", 3600)),
        float(data.get("video_duration", 8)),
    )
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")


@router.post("/pipeline")
async def video_pipeline(request: Request):
    """Crop → Upscale → Loop in sequence. Streams SSE progress."""
    data = await request.json()
    input_path = data["input"]
    output_dir = data["output_dir"]
    basename = os.path.splitext(os.path.basename(input_path))[0]
    crop_px = int(data.get("crop_px", 50))
    do_upscale = data.get("upscale", True)
    duration = int(data.get("duration", 3600))
    video_duration = float(data.get("video_duration", 8))
    crf = int(data.get("crf", 23))

    cropped = os.path.join(output_dir, f"{basename}_cropped.mp4")
    upscaled = os.path.join(output_dir, f"{basename}_1080p.mp4") if do_upscale else cropped
    looped = os.path.join(output_dir, f"{basename}_video_looped.mp4")

    steps = [
        (cmd_crop(input_path, cropped, crop_px), f"✂️ Crop {crop_px}px", cropped),
    ]
    if do_upscale:
        steps.append((cmd_upscale(cropped, upscaled, crf=crf), "⬆️ Upscale 1080p", upscaled))
    steps.append((cmd_loop_copy(upscaled, looped, duration, video_duration),
                  f"🔁 Loop video {fmt_duration(duration)}", looped))

    cleanup = [cropped]
    if do_upscale:
        cleanup.append(upscaled)

    async def run():
        total_start = time.time()
        yield f"data: {json.dumps({'type': 'pipeline_start', 'total_steps': len(steps)})}\n\n"
        for i, (cmd, label, out_file) in enumerate(steps):
            t_start = time.time()
            yield f"data: {json.dumps({'type': 'step_start', 'step': i+1, 'total': len(steps), 'label': label})}\n\n"
            error_occurred = False
            async for chunk in run_ffmpeg_stream(cmd):
                d = json.loads(chunk[6:])
                if d.get("status") == "error":
                    error_occurred = True
                    yield chunk
                    break
                yield chunk
            elapsed = time.time() - t_start
            size_str = get_file_size_str(out_file) if os.path.exists(out_file) else "?"
            if error_occurred:
                yield f"data: {json.dumps({'type': 'step_error', 'step': i+1, 'label': label})}\n\n"
                return
            yield f"data: {json.dumps({'type': 'step_done', 'step': i+1, 'label': label, 'elapsed': fmt_duration(elapsed), 'output_size': size_str})}\n\n"

        # cleanup intermediate files
        for f in cleanup:
            safe_remove_file(f)

        total_elapsed = time.time() - total_start
        final_size = get_file_size_str(looped) if os.path.exists(looped) else "?"
        yield f"data: {json.dumps({'status': 'all_done', 'output': looped, 'final_size': final_size, 'total_elapsed': fmt_duration(total_elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
