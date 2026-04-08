"""Video processing: crop (4-side), upscale, loop + optional xfade loop."""
import os
import math
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file

router = APIRouter(prefix="/video", tags=["video"])

MAX_XFADE_SEGMENTS = 120   # batas iterasi agar filter_complex tidak kehabisan memori


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


def build_xfade_filter(n_clips, xd, vd):
    """
    Bangun filter_complex untuk N klip identik yang disambung
    dengan xfade di setiap titik sambungan.

    Setiap klip efektif berkontribusi (vd - xd) detik ke timeline,
    kecuali klip terakhir yang berkontribusi penuh vd detik.

    Offset xfade ke-i = i * (vd - xd)
    """
    parts = []
    # Label setiap input: [0:v] s/d [n-1:v], format dulu
    for i in range(n_clips):
        parts.append(f"[{i}:v]setpts=PTS-STARTPTS,format=yuv420p[c{i}]")

    # Chain xfade: c0 xfade c1 -> xf0, xf0 xfade c2 -> xf1, dst.
    step = vd - xd
    prev = "c0"
    for i in range(1, n_clips):
        offset = round(i * step, 6)
        out    = f"xf{i}" if i < n_clips - 1 else "vout"
        parts.append(
            f"[{prev}][c{i}]xfade=transition=fade:duration={xd}:offset={offset}[{out}]"
        )
        prev = out

    return ";".join(parts)


def cmd_loop_xfade(input_path, output_path, duration, video_duration,
                   xfade_duration=1.0):
    """
    Buat output berdurasi `duration` detik dengan xfade di setiap
    titik sambungan loop. Seluruh timeline dirender dalam satu
    filter_complex — tidak ada stream_loop — sehingga tidak ada
    lompatan PTS antar iterasi.

    Strategi:
      - Hitung jumlah iterasi (n) yang dibutuhkan.
      - Jika n > MAX_XFADE_SEGMENTS, potong menjadi beberapa
        “block” dan concat block-block tersebut.
    """
    vd = max(float(video_duration), 0.5)
    xd = max(0.1, min(float(xfade_duration), vd * 0.45))
    step = vd - xd   # setiap klip menyumbang sebanyak ini ke timeline

    n_total = math.ceil(duration / step) + 1  # klip terakhir untuk menutup sisa
    n_total = max(2, n_total)

    output_dir = os.path.dirname(output_path) or os.path.dirname(input_path)
    basename   = os.path.splitext(os.path.basename(input_path))[0]

    enc_flags = [
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        "-preset", "fast",
        "-movflags", "+faststart",
    ]

    if n_total <= MAX_XFADE_SEGMENTS:
        # ── Single pass ──────────────────────────────────────
        fc = build_xfade_filter(n_total, xd, vd)
        cmd = (
            ["ffmpeg", "-y"]
            + ["-i", input_path] * n_total
            + ["-filter_complex", fc,
               "-map", "[vout]",
               "-t", str(duration),
               "-an"]
            + enc_flags
            + [output_path]
        )
        label = f"\U0001f500 XFade full render ({n_total} iter, fade {xd:.1f}s)"
        return [(cmd, label, output_path)], []

    else:
        # ── Multi-block pass ─────────────────────────────────
        # Bagi n_total ke blok-blok MAX_XFADE_SEGMENTS klip.
        # Setiap blok menghasilkan file sementara, lalu di-concat.
        blocks    = []
        block_paths = []
        start_clip  = 0
        block_idx   = 0
        steps_list  = []

        while start_clip < n_total:
            end_clip   = min(start_clip + MAX_XFADE_SEGMENTS, n_total)
            n_block    = end_clip - start_clip
            blk_path   = os.path.join(output_dir, f"_tmp_xblk{block_idx}_{basename}.mp4")
            block_paths.append(blk_path)

            # Hitung ulang offset relatif dalam blok ini
            fc_block = build_xfade_filter(n_block, xd, vd)

            cmd_blk = (
                ["ffmpeg", "-y"]
                + ["-i", input_path] * n_block
                + ["-filter_complex", fc_block,
                   "-map", "[vout]",
                   "-an"]
                + enc_flags
                + [blk_path]
            )
            lbl = f"\U0001f500 XFade block {block_idx+1} ({n_block} iter)"
            steps_list.append((cmd_blk, lbl, blk_path))

            start_clip += n_block
            block_idx  += 1

        # concat semua blok
        concat_list = os.path.join(output_dir, f"_tmp_xconcat_{basename}.txt")
        with open(concat_list, "w") as f:
            for bp in block_paths:
                f.write(f"file '{bp}'\n")

        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-t", str(duration),
            "-an",
            "-c:v", "copy",
            output_path,
        ]
        steps_list.append((cmd_concat, "\U0001f4ce Concat blocks", output_path))

        cleanup = block_paths + [concat_list]
        return steps_list, cleanup


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

    steps   = []
    cleanup = []
    prev    = input_path

    if do_crop:
        steps.append((
            cmd_crop(prev, cropped, crop_top, crop_bottom, crop_left, crop_right),
            f"\u2702\ufe0f Crop ({crop_top}/{crop_bottom}/{crop_left}/{crop_right}px)",
            cropped,
        ))
        cleanup.append(cropped)
        prev = cropped

    if do_upscale:
        steps.append((
            cmd_upscale(prev, upscaled, upscale_res, crf=crf),
            f"\u2b06\ufe0f Upscale \u2192 {upscale_res.replace(':', '\u00d7')}",
            upscaled,
        ))
        cleanup.append(upscaled)
        prev = upscaled

    if xfade_enabled:
        xfade_steps, xfade_cleanup = cmd_loop_xfade(
            prev, final_output, duration, video_dur, xfade_duration
        )
        steps.extend(xfade_steps)
        cleanup.extend(xfade_cleanup)
    else:
        steps.append((
            cmd_loop(prev, final_output, duration, video_dur, keep_audio),
            f"\U0001f501 Loop \u2192 {fmt_duration(duration)} {'(+ audio)' if keep_audio else '(no audio)'}",
            final_output,
        ))

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
