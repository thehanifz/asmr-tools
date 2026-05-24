"""Video processing: crop/upscale, loop + optional xfade loop + fade in/out."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file
from core.env import get_thread_flags, video_encoder_flags, USE_NVENC

router = APIRouter(prefix="/video", tags=["video"])


def cmd_crop(input_path, output_path, top=0, bottom=0, left=0, right=0):
    vf = f"crop=in_w-{left}-{right}:in_h-{top}-{bottom}:{left}:{top}"
    return [
        "ffmpeg", "-y", *get_thread_flags(), "-i", input_path,
        "-vf", vf,
        *video_encoder_flags(crf=23, preset="fast"),
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
        "ffmpeg", "-y", *get_thread_flags(), "-i", input_path,
        "-vf", f"scale={w}:{h}:flags={algo}",
        *video_encoder_flags(crf=crf, preset="fast"),
        "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "copy",
        output_path,
    ]


def cmd_loop(input_path, output_path, duration, video_duration, keep_audio=False):
    """Loop cepat pakai stream_copy (tanpa xfade)."""
    loops = max(1, int(duration / max(video_duration, 0.1)) + 10)
    cmd = [
        "ffmpeg", "-y", *get_thread_flags(),
        "-stream_loop", str(loops), "-i", input_path,
        "-t", str(duration),
    ]
    if keep_audio:
        cmd += ["-c:v", "copy", "-c:a", "copy"]
    else:
        cmd += ["-an", "-c:v", "copy"]
    cmd.append(output_path)
    return cmd


def cmd_fade_video(input_path, output_path, duration, fade_in=0.0, fade_out=0.0):
    filters = []
    if fade_in > 0:
        filters.append(f"fade=t=in:st=0:d={fade_in}")
    if fade_out > 0:
        fo_start = max(0.0, duration - fade_out)
        filters.append(f"fade=t=out:st={fo_start}:d={fade_out}")
    vf = ",".join(filters) if filters else "copy"
    return [
        "ffmpeg", "-y", *get_thread_flags(), "-i", input_path,
        "-vf", vf,
        *video_encoder_flags(crf=23, preset="fast"),
        "-an",
        output_path,
    ]


def cmd_loop_xfade(input_path, output_path, duration, video_duration,
                   xfade_duration=1.0, crf=23):
    vd = max(float(video_duration), 0.5)
    xd = max(0.1, min(float(xfade_duration), vd * 0.45))

    output_dir = os.path.dirname(output_path) or os.path.dirname(input_path)
    basename   = os.path.splitext(os.path.basename(input_path))[0]

    seamless_clip = os.path.join(output_dir, f"_tmp_seamless_{basename}.mp4")
    offset = vd - 2 * xd

    filter_complex = (
        f"[0:v]trim=start={xd}:end={vd},setpts=PTS-STARTPTS,format=yuv420p[v1];"
        f"[0:v]trim=start=0:end={xd},setpts=PTS-STARTPTS,format=yuv420p[v2];"
        f"[v1][v2]xfade=transition=fade:duration={xd}:offset={offset:.6f}[vout]"
    )

    cmd_seamless = [
        "ffmpeg", "-y",
        *get_thread_flags(),
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-an",
        *video_encoder_flags(crf=crf, preset="fast"),
        seamless_clip
    ]

    cmd_lp = cmd_loop(seamless_clip, output_path, duration, vd - xd, keep_audio=False)

    steps_list = [
        (cmd_seamless, f"🔄 Create seamless loop clip ({vd:.1f}s → {vd-xd:.1f}s, xfade {xd:.1f}s)", seamless_clip),
        (cmd_lp, f"⚡ Stream-copy loop seamless clip → {fmt_duration(duration)}", output_path)
    ]

    return steps_list, [seamless_clip]


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: Crop & Upscale (standalone, tanpa loop)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/crop")
async def video_crop(request: Request):
    """Crop dan/atau upscale video tanpa loop.

    Payload:
      input       : str  — source video path
      output      : str  — output path (opsional)
      crop_top    : int  — pixel crop atas
      crop_bottom : int  — pixel crop bawah
      crop_left   : int  — pixel crop kiri
      crop_right  : int  — pixel crop kanan
      upscale     : str  — resolusi target, misal '1920:1080' (opsional)
      crf         : int  — quality (default 23)
    """
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON: {e}"})

    input_path  = data.get("input", "")
    output_path = data.get("output", "")
    crop_top    = int(data.get("crop_top", 0))
    crop_bottom = int(data.get("crop_bottom", 0))
    crop_left   = int(data.get("crop_left", 0))
    crop_right  = int(data.get("crop_right", 0))
    upscale_res = data.get("upscale") or ""
    crf         = int(data.get("crf", 23))

    if not input_path or not os.path.exists(input_path):
        return JSONResponse(status_code=400, content={"error": "Input file tidak ditemukan"})

    do_crop    = any([crop_top, crop_bottom, crop_left, crop_right])
    do_upscale = bool(upscale_res)

    if not do_crop and not do_upscale:
        return JSONResponse(status_code=400, content={"error": "Tidak ada operasi crop maupun upscale yang aktif"})

    output_dir = os.path.dirname(os.path.abspath(input_path))
    basename   = os.path.splitext(os.path.basename(input_path))[0]

    if not output_path:
        suffix = "_cropped" if do_crop and not do_upscale else ("_upscaled" if not do_crop else "_crop_up")
        output_path = os.path.join(output_dir, f"{basename}{suffix}.mp4")

    # tmp untuk pipeline 2-step (crop → upscale)
    tmp_crop = os.path.join(output_dir, f"_tmp_{basename}_crop.mp4")

    steps   = []
    cleanup = []
    prev    = input_path

    if do_crop:
        out = tmp_crop if do_upscale else output_path
        steps.append((
            cmd_crop(prev, out, crop_top, crop_bottom, crop_left, crop_right),
            f"✂️ Crop ({crop_top}/{crop_bottom}/{crop_left}/{crop_right}px)",
            out,
        ))
        if do_upscale:
            cleanup.append(tmp_crop)
        prev = out

    if do_upscale:
        steps.append((
            cmd_upscale(prev, output_path, upscale_res, crf=crf),
            f"⬆️ Upscale → {upscale_res.replace(':', '×')}",
            output_path,
        ))

    async def run():
        total_start = time.time()
        encoder_name = "h264_nvenc ⚡" if USE_NVENC else "libx264 🖥"
        yield f"data: {json.dumps({'log': f'Encoder: {encoder_name}'})}\n\n"
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
        final_size = get_file_size_str(output_path) if os.path.exists(output_path) else "?"
        yield f"data: {json.dumps({'status': 'all_done', 'output': output_path, 'final_size': final_size, 'total_elapsed': fmt_duration(total_elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT: Video Loop Pipeline (loop + xfade + fade — tanpa crop)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/pipeline")
async def video_pipeline(request: Request):
    """Loop video ke durasi target dengan xfade dan fade in/out.

    Payload:
      input            : str   — source video path
      output           : str   — output path
      duration         : int   — target durasi detik (default 3600)
      video_duration   : float — durasi klip sumber (detik)
      keep_audio       : bool  — pertahankan audio original
      crf              : int   — quality (default 23)
      xfade_enabled    : bool
      xfade_duration   : float
      fade_in_enabled  : bool
      fade_in_duration : float
      fade_out_enabled : bool
      fade_out_duration: float
    """
    data = await request.json()
    input_path   = data["input"]
    final_output = data["output"]
    output_dir   = os.path.dirname(final_output) or os.path.dirname(input_path)
    basename     = os.path.splitext(os.path.basename(input_path))[0]

    duration    = int(data.get("duration", 3600))
    video_dur   = float(data.get("video_duration", 8))
    crf         = int(data.get("crf", 23))
    keep_audio  = bool(data.get("keep_audio", False))

    xfade_enabled  = bool(data.get("xfade_enabled", False))
    xfade_duration = float(data.get("xfade_duration", 1.0))

    fade_in_enabled  = bool(data.get("fade_in_enabled", False))
    fade_out_enabled = bool(data.get("fade_out_enabled", False))
    fade_in_dur      = float(data.get("fade_in_duration", 3.0))
    fade_out_dur     = float(data.get("fade_out_duration", 3.0))

    do_fade = fade_in_enabled or fade_out_enabled

    looped  = os.path.join(output_dir, f"_tmp_{basename}_loop.mp4")

    steps   = []
    cleanup = []

    if xfade_enabled:
        xfade_out = final_output if not do_fade else looped
        if do_fade:
            cleanup.append(looped)

        xfade_steps, xfade_cleanup = cmd_loop_xfade(
            input_path, xfade_out, duration, video_dur, xfade_duration, crf=crf
        )
        steps.extend(xfade_steps)
        cleanup.extend(xfade_cleanup)

        if do_fade:
            fi = fade_in_dur  if fade_in_enabled  else 0.0
            fo = fade_out_dur if fade_out_enabled else 0.0
            label_parts = []
            if fi > 0: label_parts.append(f"fade-in {fi}s")
            if fo > 0: label_parts.append(f"fade-out {fo}s")
            steps.append((
                cmd_fade_video(looped, final_output, duration, fi, fo),
                f"🌟 Fade video: {' + '.join(label_parts)}",
                final_output,
            ))
    else:
        loop_out = final_output if not do_fade else looped
        if do_fade:
            cleanup.append(looped)

        steps.append((
            cmd_loop(input_path, loop_out, duration, video_dur, keep_audio),
            f"🔁 Loop → {fmt_duration(duration)} {'(+ audio)' if keep_audio else '(no audio)'}",
            loop_out,
        ))

        if do_fade:
            fi = fade_in_dur  if fade_in_enabled  else 0.0
            fo = fade_out_dur if fade_out_enabled else 0.0
            label_parts = []
            if fi > 0: label_parts.append(f"fade-in {fi}s")
            if fo > 0: label_parts.append(f"fade-out {fo}s")
            steps.append((
                cmd_fade_video(looped, final_output, duration, fi, fo),
                f"🌟 Fade video: {' + '.join(label_parts)}",
                final_output,
            ))

    async def run():
        total_start = time.time()
        encoder_name = "h264_nvenc ⚡" if USE_NVENC else "libx264 🖥"
        yield f"data: {json.dumps({'log': f'Encoder: {encoder_name}'})}\n\n"
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
