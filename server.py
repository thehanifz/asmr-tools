from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import subprocess
import asyncio
import os
import json
import platform

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


def escape_font_path(path: str) -> str:
    """Escape font path untuk FFmpeg filter di Windows."""
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = path[0] + "\\:" + path[2:]
    return path


def build_ffmpeg_cmd(action: str, params: dict) -> list:
    input_path = params["input"]
    output_path = params["output"]

    if action == "crop":
        px = params.get("pixels", 50)
        return [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"crop=in_w:in_h-{px}:0:0",
            "-c:v", "libx264", "-crf", "23", "-c:a", "aac",
            output_path
        ]

    elif action == "upscale":
        algo = params.get("algo", "lanczos")
        crf = params.get("crf", 18)
        return [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale=1920:1080:flags={algo}",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
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


def build_loop_v2_steps(params: dict) -> list:
    """
    Loop V2 - 4 step pipeline:
    1. Loop video (stream_loop + -c:v copy, buang audio)
    2. Extract audio asli ke WAV
    3. Loop audio 1 jam + crossfade di loop point
    4. Mux video 1 jam + audio 1 jam
    """
    input_path = params["input"]
    output_path = params["output"]
    duration = int(params.get("duration", 3600))
    video_duration = float(params.get("video_duration", 8))
    crossfade = float(params.get("crossfade", 0.3))

    loops = max(1, int(duration / video_duration) + 10)

    out_dir = os.path.dirname(output_path)
    base = os.path.splitext(os.path.basename(input_path))[0]
    sep = os.sep

    video_1h = os.path.join(out_dir, f"{base}_video_1h.mp4")
    audio_wav = os.path.join(out_dir, f"{base}_audio.wav")
    audio_1h = os.path.join(out_dir, f"{base}_audio_1h.m4a")

    fade_out_start = duration - crossfade

    step1 = [
        "ffmpeg", "-y",
        "-stream_loop", str(loops), "-i", input_path,
        "-t", str(duration),
        "-an", "-c:v", "copy",
        video_1h
    ]

    step2 = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn", "-acodec", "pcm_s16le",
        audio_wav
    ]

    step3 = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", audio_wav,
        "-filter_complex",
        f"atrim=duration={duration},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={crossfade},"
        f"afade=t=out:st={fade_out_start}:d={crossfade}",
        "-c:a", "aac", "-b:a", "192k",
        audio_1h
    ]

    step4 = [
        "ffmpeg", "-y",
        "-i", video_1h, "-i", audio_1h,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "copy",
        "-shortest",
        output_path
    ]

    return [step1, step2, step3, step4], {
        "video_1h": video_1h,
        "audio_wav": audio_wav,
        "audio_1h": audio_1h
    }


async def run_ffmpeg_stream(cmd: list):
    """
    Baca stderr FFmpeg per CHUNK (bukan per line) untuk menghindari
    LimitOverrunError saat FFmpeg output baris sangat panjang (>64KB).
    Buffer dikumpulkan dan dipecah per newline secara manual.
    """
    limit = 10 * 1024 * 1024  # 10 MB
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
    """
    Loop V2: 4-step pipeline
    - Step 1: Loop video (copy, tanpa encode)
    - Step 2: Extract audio asli ke WAV
    - Step 3: Loop audio + crossfade
    - Step 4: Mux video + audio
    """
    data = await request.json()
    params = data.get("params", {})
    steps, tmp_files = build_loop_v2_steps(params)
    step_labels = [
        "Loop video (copy)",
        "Extract audio WAV",
        "Loop audio + crossfade",
        "Mux video + audio"
    ]

    async def run_v2():
        for i, cmd in enumerate(steps):
            yield f"data: {json.dumps({'step': i+1, 'total': len(steps), 'label': step_labels[i], 'cmd': ' '.join(cmd[:5])})}\n\n"
            error_occurred = False
            async for chunk in run_ffmpeg_stream(cmd):
                d = json.loads(chunk[6:])  # strip 'data: '
                if d.get('status') == 'error':
                    error_occurred = True
                    yield chunk
                    break
                yield chunk
            if error_occurred:
                yield f"data: {json.dumps({'status': 'error', 'step': i+1})}\n\n"
                return
        output = params.get('output', '')
        yield f"data: {json.dumps({'status': 'all_done', 'output': output, 'tmp': tmp_files})}\n\n"

    return StreamingResponse(run_v2(), media_type="text/event-stream")


@app.post("/api/process-all")
async def process_all(request: Request):
    data = await request.json()
    input_path = data["input"]
    output_dir = data["output_dir"]
    basename = os.path.splitext(os.path.basename(input_path))[0]
    video_duration = float(data.get("video_duration", 8))
    fps = float(data.get("fps", 24))
    target_duration = int(data.get("target_duration", 3600))
    crop_px = int(data.get("crop_px", 50))
    noise_color = data.get("noise_color", "brown")
    do_upscale = data.get("upscale", True)
    loop_mode = data.get("loop_mode", "hq")  # hq | fast | v2

    step1 = os.path.join(output_dir, f"{basename}_cropped.mp4")
    step2 = os.path.join(output_dir, f"{basename}_1080p.mp4") if do_upscale else step1
    step3 = os.path.join(output_dir, f"{basename}_final.mp4")
    thumb = os.path.join(output_dir, f"{basename}_thumbnail.jpg")

    steps = [
        build_ffmpeg_cmd("crop", {"input": input_path, "output": step1, "pixels": crop_px}),
    ]
    if do_upscale:
        steps.append(build_ffmpeg_cmd("upscale", {"input": step1, "output": step2}))

    if loop_mode == "v2":
        v2_steps, _ = build_loop_v2_steps({
            "input": step2, "output": step3,
            "duration": target_duration,
            "video_duration": video_duration,
        })
        steps.extend(v2_steps)
    else:
        steps.append(build_ffmpeg_cmd("loop", {
            "input": step2, "output": step3,
            "duration": target_duration, "video_duration": video_duration,
            "fps": fps, "noise": noise_color, "mode": loop_mode
        }))

    steps.append(build_ffmpeg_cmd("thumbnail", {
        "input": input_path, "output": thumb,
        "text1": data.get("thumb_text1", ""),
        "text2": data.get("thumb_text2", "")
    }))

    async def run_all():
        for i, cmd in enumerate(steps):
            yield f"data: {json.dumps({'step': i+1, 'total': len(steps), 'cmd': ' '.join(cmd[:4])})}\n\n"
            async for chunk in run_ffmpeg_stream(cmd):
                yield chunk
        yield f"data: {json.dumps({'status': 'all_done', 'output': step3, 'thumbnail': thumb})}\n\n"

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
