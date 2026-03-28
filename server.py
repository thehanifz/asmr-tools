from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import asyncio
import os
import json
import platform
import time

app = FastAPI(title="ASMR Video Tool")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="."), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


# ── Browse dialog via tkinter ───────────────────────────────────
@app.get("/api/browse")
async def browse_file():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', True)
        file_path = filedialog.askopenfilename(
            title="Pilih Video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.avi *.mkv *.webm"),
                ("All files", "*.*")
            ]
        )
        root.destroy()
        if file_path:
            return {"path": file_path.replace("/", os.sep)}
        return {"path": ""}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/browse-folder")
async def browse_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', True)
        folder_path = filedialog.askdirectory(title="Pilih Output Folder")
        root.destroy()
        if folder_path:
            return {"path": folder_path.replace("/", os.sep)}
        return {"path": ""}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/probe")
async def probe_video(request: Request):
    data = await request.json()
    path = data.get("path", "").strip()
    if not os.path.exists(path):
        return JSONResponse({"error": "File tidak ditemukan"}, status_code=404)
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size,bit_rate:stream=width,height,r_frame_rate,codec_name",
            "-of", "json", path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        info = json.loads(result.stdout)
        fmt = info.get("format", {})
        streams = info.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_name") not in ["aac", "mp3", "opus"]), {})
        duration = float(fmt.get("duration", 0))
        size = int(fmt.get("size", 0))
        fps_raw = video_stream.get("r_frame_rate", "24/1")
        fps_parts = fps_raw.split("/")
        fps = round(int(fps_parts[0]) / int(fps_parts[1]), 2)
        width = video_stream.get("width", 0)
        height = video_stream.get("height", 0)
        return {
            "duration": round(duration, 2),
            "duration_str": f"{int(duration//3600)}j {int((duration%3600)//60)}m {int(duration%60)}s",
            "size": size,
            "size_str": f"{size/1024/1024:.1f} MB",
            "width": width,
            "height": height,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "filename": os.path.basename(path)
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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
        if size >= 1024**3:
            return f"{size/1024**3:.2f} GB"
        elif size >= 1024**2:
            return f"{size/1024**2:.1f} MB"
        else:
            return f"{size/1024:.0f} KB"
    except:
        return "?"


def escape_font_path(path: str) -> str:
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = path[0] + "\\:" + path[2:]
    return path


def build_ffmpeg_cmd(action: str, params: dict) -> list:
    input_path = params["input"]
    output_path = params["output"]

    if action == "crop":
        px = params.get("pixels", 50)
        # FIX #1: pakai preset fast (bukan default slow) — crop cuma potong frame, tidak perlu slow
        return [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"crop=in_w:in_h-{px}:0:0",
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]

    elif action == "upscale":
        algo = params.get("algo", "lanczos")
        # FIX #2: CRF default 23 (bukan 18), preset fast, maxrate 8Mbps agar file tidak meledak
        crf = params.get("crf", 23)
        return [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale=1920:1080:flags={algo}",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
            "-maxrate", "8000k", "-bufsize", "16000k",
            "-c:a", "copy",
            output_path
        ]

    elif action == "loop":
        duration = int(params.get("duration", 3600))
        video_duration = float(params.get("video_duration", 8))
        fps = float(params.get("fps", 24))
        noise_color = params.get("noise", "brown")
        mode = params.get("mode", "hq")
        frame_size = round(video_duration * fps)
        loops = max(1, int(duration // video_duration) + 1)

        if mode == "fast":
            return [
                "ffmpeg", "-y",
                "-stream_loop", str(loops), "-i", input_path,
                "-filter_complex", f"anoisesrc=color={noise_color}:duration={duration}[a]",
                "-map", "0:v", "-map", "[a]",
                "-t", str(duration),
                "-c:v", "copy", "-c:a", "aac",
                output_path
            ]
        else:
            return [
                "ffmpeg", "-y", "-i", input_path,
                "-filter_complex",
                f"[0:v]loop=loop={loops}:size={frame_size}:start=0[v];anoisesrc=color={noise_color}:duration={duration}[a]",
                "-map", "[v]", "-map", "[a]",
                "-t", str(duration),
                "-c:v", "libx264", "-crf", "23", "-preset", "fast", "-c:a", "aac",
                output_path
            ]

    elif action == "audio":
        noise_color = params.get("noise", "brown")
        duration = float(params.get("duration", 3600))
        if params.get("custom_audio"):
            audio_input = params["custom_audio"]
            return [
                "ffmpeg", "-y", "-i", input_path,
                "-stream_loop", "-1", "-i", audio_input,
                "-map", "0:v", "-map", "1:a",
                "-shortest", "-c:v", "copy", "-c:a", "aac",
                output_path
            ]
        else:
            return [
                "ffmpeg", "-y", "-i", input_path,
                "-filter_complex", f"anoisesrc=color={noise_color}:duration={duration}[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac",
                output_path
            ]

    elif action == "thumbnail":
        frame_time = params.get("frame_time", 1)

        def esc(s):
            return s.replace("\\", "/").replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

        text1 = esc(params.get("text1", ""))
        text2 = esc(params.get("text2", ""))
        raw_font = params.get("font", "C:/Windows/Fonts/arialbd.ttf")
        font = escape_font_path(raw_font)
        color = params.get("color", "white")
        size1 = params.get("size1", 72)
        size2 = params.get("size2", 40)

        if text1:
            vf = f"drawtext=text='{text1}':fontfile='{font}':fontsize={size1}:fontcolor={color}:x=50:y=50:shadowcolor=black:shadowx=3:shadowy=3"
            if text2:
                vf += f",drawtext=text='{text2}':fontfile='{font}':fontsize={size2}:fontcolor=yellow:x=50:y={50+size1+10}:shadowcolor=black:shadowx=2:shadowy=2"
        else:
            vf = "scale=iw:ih"

        return [
            "ffmpeg", "-y", "-ss", str(frame_time), "-i", input_path,
            "-frames:v", "1", "-vf", vf, "-q:v", "1",
            output_path
        ]

    return []


def build_loop_v2_steps(params: dict):
    input_path = params["input"]
    output_path = params["output"]
    duration = int(params.get("duration", 3600))
    video_duration = float(params.get("video_duration", 8))
    crossfade = float(params.get("crossfade", 0.3))
    loops = max(1, int(duration / video_duration) + 10)

    out_dir = os.path.dirname(output_path)
    base = os.path.splitext(os.path.basename(input_path))[0]

    video_1h = os.path.join(out_dir, f"{base}_video_1h.mp4")
    audio_wav = os.path.join(out_dir, f"{base}_audio.wav")
    audio_1h  = os.path.join(out_dir, f"{base}_audio_1h.m4a")

    fade_out_start = duration - crossfade

    step1 = ["ffmpeg", "-y", "-stream_loop", str(loops), "-i", input_path,
              "-t", str(duration), "-an", "-c:v", "copy", video_1h]
    step2 = ["ffmpeg", "-y", "-i", input_path,
              "-vn", "-acodec", "pcm_s16le", audio_wav]
    step3 = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", audio_wav,
              "-filter_complex",
              f"atrim=duration={duration},asetpts=PTS-STARTPTS,"
              f"afade=t=in:st=0:d={crossfade},"
              f"afade=t=out:st={fade_out_start}:d={crossfade}",
              "-c:a", "aac", "-b:a", "192k", audio_1h]
    step4 = ["ffmpeg", "-y", "-i", video_1h, "-i", audio_1h,
              "-map", "0:v:0", "-map", "1:a:0",
              "-c:v", "copy", "-c:a", "copy", "-shortest", output_path]

    return [step1, step2, step3, step4], {
        "video_1h": video_1h, "audio_wav": audio_wav, "audio_1h": audio_1h
    }


async def run_ffmpeg_stream(cmd: list):
    limit = 10 * 1024 * 1024
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=limit
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


@app.post("/api/process")
async def process_video(request: Request):
    data = await request.json()
    action = data.get("action")
    params = data.get("params", {})
    cmd = build_ffmpeg_cmd(action, params)
    if not cmd:
        return JSONResponse({"error": "Action tidak valid"}, status_code=400)
    return StreamingResponse(run_ffmpeg_stream(cmd), media_type="text/event-stream")


@app.post("/api/loop-v2")
async def loop_v2(request: Request):
    data = await request.json()
    params = data.get("params", {})
    steps, tmp_files = build_loop_v2_steps(params)
    step_labels = [
        "Loop video (copy, tanpa re-encode)",
        "Extract audio asli → WAV",
        "Loop audio + crossfade (AAC 192k)",
        "Mux video + audio → final"
    ]

    async def run_v2():
        total_start = time.time()
        for i, cmd in enumerate(steps):
            t_start = time.time()
            out_file = cmd[-1]
            yield f"data: {json.dumps({'step': i+1, 'total': len(steps), 'label': step_labels[i], 'cmd': ' '.join(cmd[:6]), 'timing': 'start'})}\n\n"
            error_occurred = False
            async for chunk in run_ffmpeg_stream(cmd):
                d = json.loads(chunk[6:])
                if d.get('status') == 'error':
                    error_occurred = True
                    yield chunk
                    break
                yield chunk
            elapsed = time.time() - t_start
            size_str = get_file_size_str(out_file) if os.path.exists(out_file) else "?"
            if error_occurred:
                yield f"data: {json.dumps({'status': 'error', 'step': i+1, 'label': step_labels[i]})}\n\n"
                return
            yield f"data: {json.dumps({'step_done': i+1, 'label': step_labels[i], 'elapsed': fmt_duration(elapsed), 'output_file': os.path.basename(out_file), 'output_size': size_str})}\n\n"

        total_elapsed = time.time() - total_start
        output = params.get('output', '')
        final_size = get_file_size_str(output) if os.path.exists(output) else "?"
        yield f"data: {json.dumps({'status': 'all_done', 'output': output, 'final_size': final_size, 'total_elapsed': fmt_duration(total_elapsed), 'tmp': tmp_files})}\n\n"

    return StreamingResponse(run_v2(), media_type="text/event-stream")


@app.post("/api/process-all")
async def process_all(request: Request):
    data = await request.json()
    input_path  = data["input"]
    output_dir  = data["output_dir"]
    basename    = os.path.splitext(os.path.basename(input_path))[0]
    video_duration  = float(data.get("video_duration", 8))
    fps             = float(data.get("fps", 24))
    target_duration = int(data.get("target_duration", 3600))
    crop_px     = int(data.get("crop_px", 50))
    noise_color = data.get("noise_color", "brown")
    do_upscale  = data.get("upscale", True)
    loop_mode   = data.get("loop_mode", "v2")
    crossfade   = float(data.get("crossfade", 0.3))
    # FIX #3: ambil crf dari request, default 23
    upscale_crf = int(data.get("upscale_crf", 23))

    cropped  = os.path.join(output_dir, f"{basename}_cropped.mp4")
    upscaled = os.path.join(output_dir, f"{basename}_1080p.mp4") if do_upscale else cropped
    final    = os.path.join(output_dir, f"{basename}_final.mp4")
    thumb    = os.path.join(output_dir, f"{basename}_thumbnail.jpg")

    steps = []
    step_labels = []
    step_outputs = []

    # Step: Crop
    steps.append(build_ffmpeg_cmd("crop", {"input": input_path, "output": cropped, "pixels": crop_px}))
    step_labels.append(f"✂️  Crop watermark {crop_px}px dari bawah")
    step_outputs.append(cropped)

    # Step: Upscale (optional) — FIX: pakai crf dari param, preset fast, maxrate 8M
    if do_upscale:
        steps.append(build_ffmpeg_cmd("upscale", {
            "input": cropped, "output": upscaled,
            "crf": upscale_crf
        }))
        step_labels.append(f"⬆️  Upscale ke 1080p (lanczos, crf {upscale_crf}, maxrate 8Mbps)")
        step_outputs.append(upscaled)

    # Step: Loop V2 atau mode lain
    if loop_mode == "v2":
        v2_steps, tmp_files = build_loop_v2_steps({
            "input": upscaled, "output": final,
            "duration": target_duration,
            "video_duration": video_duration,
            "crossfade": crossfade
        })
        v2_labels = [
            f"🔁  Loop video copy ({fmt_duration(target_duration)})",
            "🎧  Extract audio asli → WAV",
            f"🌀  Loop audio + crossfade {crossfade}s",
            "🔧  Mux video + audio → final"
        ]
        v2_outputs = [tmp_files["video_1h"], tmp_files["audio_wav"], tmp_files["audio_1h"], final]
        steps.extend(v2_steps)
        step_labels.extend(v2_labels)
        step_outputs.extend(v2_outputs)
    else:
        steps.append(build_ffmpeg_cmd("loop", {
            "input": upscaled, "output": final,
            "duration": target_duration, "video_duration": video_duration,
            "fps": fps, "noise": noise_color, "mode": loop_mode
        }))
        step_labels.append(f"🔁  Loop {loop_mode} → {fmt_duration(target_duration)}")
        step_outputs.append(final)

    # Step: Thumbnail
    steps.append(build_ffmpeg_cmd("thumbnail", {
        "input": input_path, "output": thumb,
        "text1": data.get("thumb_text1", ""),
        "text2": data.get("thumb_text2", "")
    }))
    step_labels.append("🖼️  Extract thumbnail")
    step_outputs.append(thumb)

    total_steps = len(steps)

    async def run_all():
        total_start = time.time()
        input_size  = get_file_size_str(input_path)
        target_str  = fmt_duration(target_duration)

        yield f"data: {json.dumps({'type': 'pipeline_start', 'total_steps': total_steps, 'input': os.path.basename(input_path), 'input_size': input_size, 'target': target_str, 'loop_mode': loop_mode})}\n\n"

        for i, cmd in enumerate(steps):
            t_start  = time.time()
            label    = step_labels[i]
            out_file = step_outputs[i]

            yield f"data: {json.dumps({'type': 'step_start', 'step': i+1, 'total': total_steps, 'label': label, 'cmd': ' '.join(cmd[:6])})}\n\n"

            error_occurred = False
            async for chunk in run_ffmpeg_stream(cmd):
                d = json.loads(chunk[6:])
                if d.get('status') == 'error':
                    error_occurred = True
                    yield chunk
                    break
                yield chunk

            elapsed  = time.time() - t_start
            size_str = get_file_size_str(out_file) if os.path.exists(out_file) else "?"

            if error_occurred:
                yield f"data: {json.dumps({'type': 'step_error', 'step': i+1, 'label': label, 'elapsed': fmt_duration(elapsed)})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'step_done', 'step': i+1, 'total': total_steps, 'label': label, 'elapsed': fmt_duration(elapsed), 'output_file': os.path.basename(out_file), 'output_size': size_str})}\n\n"

        total_elapsed = time.time() - total_start
        final_size    = get_file_size_str(final) if os.path.exists(final) else "?"
        thumb_size    = get_file_size_str(thumb) if os.path.exists(thumb) else "?"

        yield f"data: {json.dumps({'status': 'all_done', 'output': final, 'thumbnail': thumb, 'final_size': final_size, 'thumb_size': thumb_size, 'total_elapsed': fmt_duration(total_elapsed)})}\n\n"

    return StreamingResponse(run_all(), media_type="text/event-stream")


@app.post("/api/open-folder")
async def open_folder(request: Request):
    data = await request.json()
    folder = data.get("folder", "")
    if not os.path.exists(folder):
        return JSONResponse({"error": "Folder tidak ditemukan"}, status_code=404)
    if platform.system() == "Windows":
        os.startfile(folder)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
