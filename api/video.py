"""Video processing: crop (4-side), upscale, loop + optional keep audio."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file

router = APIRouter(prefix="/video", tags=["video"])


def cmd_crop(input_path, output_path, top=0, bottom=0, left=0, right=0):
    vf = f"crop=in_w-{left}-{right}:in_h-{top}-{bottom}:{left}:{top}"
    return [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]


def _parse_res(res_str):
    sep = ":" if ":" in res_str else "x"
    w, h = res_str.split(sep)
    return int(w), int(h)


def cmd_upscale(input_path, output_path, resolution="1920:1080", algo="lanczos", crf=23):
    w, h = _parse_res(resolution)
    return [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={w}:{h}:flags={algo}",
        "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
        "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "copy",
        output_path,
    ]


def cmd_loop(input_path, output_path, duration, video_duration, keep_audio=False):
    loops = max(1, int(duration / max(video_duration, 0.1)) + 10)
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", str(loops), "-i", input_path,
        "-t", str(duration),
    ]
    if keep_audio:
        cmd += ["-c:v", "copy", "-c:a", "copy"]
    else:
        cmd += ["-an", "-c:v", "copy"]
    cmd.append(output_path)
    return cmd


@router.post("/pipeline")
async def video_pipeline(request: Request):
    data = await request.json()
    input_path   = data["input"]
    final_output = data["output"]
    output_dir   = os.path.dirname(final_output) or os.path.dirname(input_path)
    basename     = os.path.splitext(os.path.basename(input_path))[0]

    crop_top    = int(data.get("crop_top",    0))
    crop_bottom = int(data.get("crop_bottom", 0))
    crop_left   = int(data.get("crop_left",   0))
    crop_right  = int(data.get("crop_right",  0))
    upscale_res = data.get("upscale") or ""
    duration    = int(data.get("duration",    3600))
    video_dur   = float(data.get("video_duration", 8))
    crf         = int(data.get("crf", 23))
    keep_audio  = bool(data.get("keep_audio", False))

    do_crop    = any([crop_top, crop_bottom, crop_left, crop_right])
    do_upscale = bool(upscale_res)

    cropped  = os.path.join(output_dir, f"_tmp_{basename}_crop.mp4")
    upscaled = os.path.join(output_dir, f"_tmp_{basename}_up.mp4")

    steps = []
    prev  = input_path

    if do_crop:
        steps.append((cmd_crop(prev, cropped, crop_top, crop_bottom, crop_left, crop_right),
                      f"✂️ Crop ({crop_top}/{crop_bottom}/{crop_left}/{crop_right}px)", cropped))
        prev = cropped

    if do_upscale:
        steps.append((cmd_upscale(prev, upscaled, upscale_res, crf=crf),
                      f"⬆️ Upscale → {upscale_res.replace(':', '×')}", upscaled))
        prev = upscaled

    steps.append((cmd_loop(prev, final_output, duration, video_dur, keep_audio),
                  f"🔁 Loop → {fmt_duration(duration)} {'(+ audio)' if keep_audio else '(no audio)'}",
                  final_output))

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

            if error_occurred:
                yield f"data: {json.dumps({'type': 'step_error', 'step': i+1, 'label': label})}\n\n"
                return

            elapsed  = time.time() - t_start
            size_str = get_file_size_str(out_file) if os.path.exists(out_file) else "?"
            yield f"data: {json.dumps({'type': 'step_done', 'step': i+1, 'label': label, 'elapsed': fmt_duration(elapsed), 'output_size': size_str})}\n\n"

        for f in cleanup:
            safe_remove_file(f)

        total_elapsed = time.time() - total_start
        final_size = get_file_size_str(final_output) if os.path.exists(final_output) else "?"
        yield f"data: {json.dumps({'status': 'all_done', 'output': final_output, 'final_size': final_size, 'total_elapsed': fmt_duration(total_elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
