"""Video processing: crop (4-side), upscale, loop."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file

router = APIRouter(prefix="/video", tags=["video"])


# ── FFmpeg command builders ──────────────────────────────────────────────

def cmd_crop(input_path: str, output_path: str,
             top: int = 0, bottom: int = 0,
             left: int = 0, right: int = 0) -> list:
    """Crop by removing N pixels from each side."""
    # crop=w:h:x:y
    vf = f"crop=in_w-{left}-{right}:in_h-{top}-{bottom}:{left}:{top}"
    return [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]


def _parse_resolution(res_str: str) -> tuple[int, int]:
    """Parse '1920:1080' or '1920x1080' into (w, h)."""
    sep = ":" if ":" in res_str else "x"
    parts = res_str.split(sep)
    return int(parts[0]), int(parts[1])


def cmd_upscale(input_path: str, output_path: str,
                resolution: str = "1920:1080",
                algo: str = "lanczos", crf: int = 23) -> list:
    w, h = _parse_resolution(resolution)
    return [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={w}:{h}:flags={algo}",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
        "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "copy",
        output_path,
    ]


def cmd_loop_copy(input_path: str, output_path: str,
                  duration: int, video_duration: float) -> list:
    """Loop video using stream copy (no re-encode). Audio stripped."""
    loops = max(1, int(duration / max(video_duration, 0.1)) + 10)
    return [
        "ffmpeg", "-y",
        "-stream_loop", str(loops), "-i", input_path,
        "-t", str(duration),
        "-an", "-c:v", "copy",
        output_path,
    ]


# ── Individual endpoints ──────────────────────────────────────────────────

@router.post("/crop")
async def crop_video(request: Request):
    data = await request.json()
    cmd = cmd_crop(
        data["input"], data["output"],
        int(data.get("crop_top", 0)), int(data.get("crop_bottom", 0)),
        int(data.get("crop_left", 0)), int(data.get("crop_right", 0)),
    )
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")


@router.post("/upscale")
async def upscale_video(request: Request):
    data = await request.json()
    cmd = cmd_upscale(
        data["input"], data["output"],
        data.get("upscale", "1920:1080"),
        data.get("algo", "lanczos"),
        int(data.get("crf", 23)),
    )
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")


@router.post("/loop")
async def loop_video(request: Request):
    data = await request.json()
    cmd = cmd_loop_copy(
        data["input"], data["output"],
        int(data.get("duration", 3600)),
        float(data.get("video_duration", 8)),
    )
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")


# ── Pipeline: Crop → Upscale → Loop ────────────────────────────────────────

@router.post("/pipeline")
async def video_pipeline(request: Request):
    """Crop → Upscale → Loop in sequence. Streams SSE progress.

    Payload fields:
      input          : str   — source video path
      output         : str   — final output path (full path incl. filename)
      crop_top       : int   — pixels to remove from top    (default 0)
      crop_bottom    : int   — pixels to remove from bottom (default 0)
      crop_left      : int   — pixels to remove from left   (default 0)
      crop_right     : int   — pixels to remove from right  (default 0)
      upscale        : str   — target resolution e.g. '1920:1080', or null/empty to skip
      duration       : int   — loop target in seconds (default 3600)
      video_duration : float — source video duration in seconds (default 8)
      crf            : int   — CRF for encode steps (default 23)
    """
    data = await request.json()
    input_path = data["input"]
    final_output = data["output"]
    output_dir = os.path.dirname(final_output) or os.path.dirname(input_path)
    basename = os.path.splitext(os.path.basename(input_path))[0]

    crop_top    = int(data.get("crop_top",    0))
    crop_bottom = int(data.get("crop_bottom", 0))
    crop_left   = int(data.get("crop_left",   0))
    crop_right  = int(data.get("crop_right",  0))
    upscale_res = data.get("upscale") or ""          # empty / null → skip
    duration    = int(data.get("duration", 3600))
    video_dur   = float(data.get("video_duration", 8))
    crf         = int(data.get("crf", 23))

    do_crop    = any([crop_top, crop_bottom, crop_left, crop_right])
    do_upscale = bool(upscale_res)
    do_loop    = bool(duration)

    # Build temp file paths
    cropped  = os.path.join(output_dir, f"_tmp_{basename}_cropped.mp4")
    upscaled = os.path.join(output_dir, f"_tmp_{basename}_upscaled.mp4")

    # Determine pipeline steps dynamically
    steps = []
    prev = input_path

    if do_crop:
        steps.append((
            cmd_crop(prev, cropped, crop_top, crop_bottom, crop_left, crop_right),
            f"✂️ Crop ({crop_top}/{crop_bottom}/{crop_left}/{crop_right}px)",
            cropped,
        ))
        prev = cropped

    if do_upscale:
        steps.append((
            cmd_upscale(prev, upscaled, upscale_res, crf=crf),
            f"⬆️ Upscale → {upscale_res.replace(':', '×')}",
            upscaled,
        ))
        prev = upscaled

    if do_loop:
        steps.append((
            cmd_loop_copy(prev, final_output, duration, video_dur),
            f"🔁 Loop → {fmt_duration(duration)}",
            final_output,
        ))
    else:
        # No loop: just copy prev to final output
        steps.append((
            ["ffmpeg", "-y", "-i", prev, "-c", "copy", final_output],
            "💾 Finalize (copy)",
            final_output,
        ))

    cleanup = []
    if do_crop:    cleanup.append(cropped)
    if do_upscale: cleanup.append(upscaled)

    async def run():
        total_start = time.time()
        yield f"data: {json.dumps({'type': 'pipeline_start', 'total_steps': len(steps)})}\n\n"

        for i, (cmd, label, out_file) in enumerate(steps):
            t_start = time.time()
            yield f"data: {json.dumps({'type': 'step_start', 'step': i+1, 'total': len(steps), 'label': label})}\n\n"
            error_occurred = False

            async for chunk in run_ffmpeg_stream(cmd):
                parsed = json.loads(chunk[6:])
                if parsed.get("status") == "error":
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

        # Cleanup intermediates
        for f in cleanup:
            safe_remove_file(f)

        total_elapsed = time.time() - total_start
        final_size = get_file_size_str(final_output) if os.path.exists(final_output) else "?"
        yield f"data: {json.dumps({'status': 'all_done', 'output': final_output, 'final_size': final_size, 'total_elapsed': fmt_duration(total_elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
