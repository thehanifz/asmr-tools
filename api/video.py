"""Video processing: crop (4-side), upscale, loop + optional xfade loop."""
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
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
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
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-maxrate", "8000k", "-bufsize", "16000k",
        "-c:a", "copy",
        output_path,
    ]


def cmd_loop(input_path, output_path, duration, video_duration, keep_audio=False):
    """Loop cepat pakai stream_copy (tanpa xfade)."""
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


def cmd_loop_xfade(input_path, output_path, duration, video_duration,
                   xfade_duration=1.0, keep_audio=False):
    """
    Buat satu segment loopable dengan crossfade di titik seam:

      ┌───────────────────────────────────┬──────────┐
      │  body  (0 → video_dur - xd)      │  tail xd │  ← klip A (trim)
      └───────────────────────────────────┴──────────┘
      ┌──────────┬────────────────────────────────────┐
      │  head xd │  (dibuang)                        │  ← klip B (trim)
      └──────────┴────────────────────────────────────┘

    → concat(body_A, xfade(tail_A, head_B))
    → loop segment ke durasi target

    Hasilnya: titik akhir klip meleleh mulus ke awal klip berikutnya.
    """
    vd  = max(video_duration, 0.5)
    xd  = max(0.1, min(float(xfade_duration), vd * 0.45))  # maks 45% durasi
    body_end   = vd - xd        # detik akhir bagian body (= awal tail)
    seg_dur    = vd - xd        # panjang segment hasil = body + 1 xfade region
    # Durasi loopable segment = video_dur - xd
    # Ketika loop, awal setiap iterasi langsung tersambung ke akhir iterasi sebelumnya
    # karena tail sudah di-blend ke head.

    output_dir = os.path.dirname(output_path) or os.path.dirname(input_path)
    basename   = os.path.splitext(os.path.basename(input_path))[0]
    seg_path   = os.path.join(output_dir, f"_tmp_xseg_{basename}.mp4")

    # Filter graph:
    #   [0:v] trim body  : 0  → body_end,  setpts reset
    #   [1:v] trim tail  : body_end → vd,  setpts reset  (= xd detik)
    #   [2:v] trim head  : 0  → xd,        setpts reset  (= xd detik)
    #   xfade [tail][head] offset=0 (keduanya sudah mulai dari PTS 0)
    #   concat body + xfade_result
    filter_str = (
        f"[0:v]trim=start=0:end={body_end},setpts=PTS-STARTPTS,format=yuv420p[body];"
        f"[1:v]trim=start={body_end}:end={vd},setpts=PTS-STARTPTS,format=yuv420p[tail];"
        f"[2:v]trim=start=0:end={xd},setpts=PTS-STARTPTS,format=yuv420p[head];"
        f"[tail][head]xfade=transition=fade:duration={xd}:offset=0,format=yuv420p[seam];"
        f"[body][seam]concat=n=2:v=1:a=0,format=yuv420p[vout]"
    )

    cmd_seg = [
        "ffmpeg", "-y",
        "-i", input_path,   # [0]
        "-i", input_path,   # [1]
        "-i", input_path,   # [2]
        "-filter_complex", filter_str,
        "-map", "[vout]",
        "-an",
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        "-preset", "fast",
        "-movflags", "+faststart",
        seg_path,
    ]

    loops = max(1, int(duration / max(seg_dur, 0.1)) + 10)
    cmd_final = [
        "ffmpeg", "-y",
        "-stream_loop", str(loops), "-i", seg_path,
        "-t", str(duration),
        "-an",
        "-c:v", "copy",
        output_path,
    ]

    label_seg = f"\U0001f500 XFade seam (tail\u2192head fade {xd:.1f}s, body {body_end:.1f}s)"
    label_fin = f"\U0001f501 Loop xfade \u2192 {fmt_duration(duration)}"
    return [
        (cmd_seg,   label_seg, seg_path),
        (cmd_final, label_fin, output_path),
    ], seg_path


@router.post("/pipeline")
async def video_pipeline(request: Request):
    data = await request.json()
    input_path   = data["input"]
    final_output = data["output"]
    output_dir   = os.path.dirname(final_output) or os.path.dirname(input_path)
    basename     = os.path.splitext(os.path.basename(input_path))[0]

    crop_top    = int(data.get("crop_top", 0))
    crop_bottom = int(data.get("crop_bottom", 0))
    crop_left   = int(data.get("crop_left", 0))
    crop_right  = int(data.get("crop_right", 0))
    upscale_res = data.get("upscale") or ""
    duration    = int(data.get("duration", 3600))
    video_dur   = float(data.get("video_duration", 8))
    crf         = int(data.get("crf", 23))
    keep_audio  = bool(data.get("keep_audio", False))
    xfade_enabled  = bool(data.get("xfade_enabled", False))
    xfade_duration = float(data.get("xfade_duration", 1.0))

    do_crop    = any([crop_top, crop_bottom, crop_left, crop_right])
    do_upscale = bool(upscale_res)

    cropped  = os.path.join(output_dir, f"_tmp_{basename}_crop.mp4")
    upscaled = os.path.join(output_dir, f"_tmp_{basename}_up.mp4")

    steps = []
    prev = input_path

    if do_crop:
        steps.append((
            cmd_crop(prev, cropped, crop_top, crop_bottom, crop_left, crop_right),
            f"\u2702\ufe0f Crop ({crop_top}/{crop_bottom}/{crop_left}/{crop_right}px)",
            cropped,
        ))
        prev = cropped

    if do_upscale:
        steps.append((
            cmd_upscale(prev, upscaled, upscale_res, crf=crf),
            f"\u2b06\ufe0f Upscale \u2192 {upscale_res.replace(':', '\u00d7')}",
            upscaled,
        ))
        prev = upscaled

    cleanup = []
    if xfade_enabled:
        xfade_steps, xfade_seg_path = cmd_loop_xfade(
            prev, final_output, duration, video_dur, xfade_duration, keep_audio
        )
        steps.extend(xfade_steps)
        cleanup.append(xfade_seg_path)
    else:
        steps.append((
            cmd_loop(prev, final_output, duration, video_dur, keep_audio),
            f"\U0001f501 Loop \u2192 {fmt_duration(duration)} {'(+ audio)' if keep_audio else '(no audio)'}",
            final_output,
        ))

    if do_crop:
        cleanup.append(cropped)
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
                parsed = json.loads(chunk[6:])
                if parsed.get("status") == "error":
                    error_occurred = True
                    yield chunk
                    break
                yield chunk

            if error_occurred:
                yield f"data: {json.dumps({'type': 'step_error', 'step': i+1, 'label': label})}\n\n"
                return

            elapsed = time.time() - t_start
            size_str = get_file_size_str(out_file) if os.path.exists(out_file) else "?"
            yield f"data: {json.dumps({'type': 'step_done', 'step': i+1, 'label': label, 'elapsed': fmt_duration(elapsed), 'output_size': size_str})}\n\n"

        for f in cleanup:
            safe_remove_file(f)

        total_elapsed = time.time() - total_start
        final_size = get_file_size_str(final_output) if os.path.exists(final_output) else "?"
        yield f"data: {json.dumps({'status': 'all_done', 'output': final_output, 'final_size': final_size, 'total_elapsed': fmt_duration(total_elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
