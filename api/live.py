"""Live to YouTube streaming endpoint with auto-reconnect, independent looping, and library CRUD."""
import os
import json
import time
import asyncio
import subprocess
import shutil
from fastapi import APIRouter, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from api.utils import now_ts, get_file_size_str

router = APIRouter(prefix="/live", tags=["live"])

PID_FILE = ".live_pid"
MEDIA_DIR = os.path.abspath("media")
VIDEO_DIR = os.path.join(MEDIA_DIR, "video")
AUDIO_DIR = os.path.join(MEDIA_DIR, "audio")
THUMBS_DIR = os.path.join(VIDEO_DIR, "thumbs")

# Ensure folders exist
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)

VIDEO_INDEX = os.path.join(VIDEO_DIR, "index.json")
AUDIO_INDEX = os.path.join(AUDIO_DIR, "index.json")

# Ensure indexes exist
if not os.path.exists(VIDEO_INDEX):
    with open(VIDEO_INDEX, "w", encoding="utf-8") as f:
        json.dump([], f)

if not os.path.exists(AUDIO_INDEX):
    with open(AUDIO_INDEX, "w", encoding="utf-8") as f:
        json.dump([], f)


def cleanup_zombie_process():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            
            import platform
            is_windows = platform.system() == "Windows"
            
            try:
                import psutil
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    if "ffmpeg" in proc.name().lower():
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        print(f"[Live Cleanup] Menghentikan proses zombie FFmpeg (psutil) PID: {pid}")
            except ImportError:
                # Fallback
                if is_windows:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                    print(f"[Live Cleanup] Menghentikan proses zombie FFmpeg (taskkill) PID: {pid}")
                else:
                    import signal
                    try:
                        os.kill(pid, signal.SIGKILL)
                        print(f"[Live Cleanup] Menghentikan proses zombie FFmpeg (os.kill) PID: {pid}")
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Live Cleanup] Gagal membersihkan zombie PID: {e}")
        finally:
            if os.path.exists(PID_FILE):
                try:
                    os.remove(PID_FILE)
                except Exception:
                    pass

# Cleanup any zombie process on startup/import
cleanup_zombie_process()


# Quality presets mapping
QUALITY_PRESETS = {
    "1080p": {"width": 1920, "height": 1080, "bitrate": "8000k", "bufsize": "16000k"},
    "720p":  {"width": 1280, "height": 720,  "bitrate": "5000k", "bufsize": "10000k"},
    "480p":  {"width": 854,  "height": 480,  "bitrate": "2500k", "bufsize": "5000k"},
    "360p":  {"width": 640,  "height": 360,  "bitrate": "1000k", "bufsize": "2000k"},
}


class LiveStreamState:
    def __init__(self):
        self.status = "idle"  # idle, connecting, live, reconnecting, error
        self.process = None
        self.task = None  # asyncio Task for reconnection loop
        self.start_time = None
        self.logs = []  # list of strings (capped at 200)
        self.reconnect_attempts = 0
        self.config = None
        self.stream_key = ""
        self.stop_requested = False
        self.error_message = ""

state = LiveStreamState()


def add_log(message: str):
    state.logs.append(message)
    if len(state.logs) > 200:
        state.logs.pop(0)


async def get_media_info(path: str, is_video: bool) -> dict:
    """Run ffprobe to get media information (duration, size, resolution, streams)."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size",
            "-show_streams",
            "-of", "json", path
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        info = json.loads(stdout.decode("utf-8", errors="ignore"))
        
        fmt = info.get("format", {})
        streams = info.get("streams", [])
        
        duration = float(fmt.get("duration", 0.0) or 0.0)
        size = int(fmt.get("size", 0) or 0)
        
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        
        res = {
            "duration": duration,
            "size": size,
            "has_video": has_video,
            "has_audio": has_audio
        }
        
        if is_video and has_video:
            video_stream = next(s for s in streams if s.get("codec_type") == "video")
            res["width"] = int(video_stream.get("width", 0) or 0)
            res["height"] = int(video_stream.get("height", 0) or 0)
            
        return res
    except Exception as e:
        print(f"[Probe Error] {e}")
        return {"duration": 0.0, "size": 0, "has_video": is_video, "has_audio": not is_video}


async def extract_thumbnail(video_path: str, thumb_path: str):
    """Extract frame at 0s of video as thumbnail."""
    try:
        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:00", "-i", video_path,
            "-vframes", "1", "-q:v", "2", thumb_path
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
    except Exception as e:
        print(f"[Thumbnail Error] {e}")


def build_ffmpeg_cmd(config: dict, rtmp_target: str) -> list:
    video_path = config["video_path"]
    audio_source = config["audio_source"]
    quality_preset = config["quality"]
    
    preset = QUALITY_PRESETS.get(quality_preset, QUALITY_PRESETS["720p"])
    width = preset["width"]
    height = preset["height"]
    bitrate = preset["bitrate"]
    bufsize = preset["bufsize"]
    
    cmd = ["ffmpeg", "-y", "-nostdin"]
    
    # Try importing logical threads flags
    try:
        from core.env import get_thread_flags
        cmd.extend(get_thread_flags())
    except ImportError:
        pass

    # Video input: infinite loop, native framerate
    cmd.extend(["-stream_loop", "-1", "-re", "-i", video_path])
    
    if audio_source == "video":
        # Mode 1: Audio from video (loop together)
        cmd.extend([
            "-c:v", "libx264", "-preset", "veryfast",
            "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bufsize,
            "-vf", f"scale={width}:{height}", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-f", "flv", rtmp_target
        ])
    elif audio_source == "library":
        # Mode 2: Audio terpisah (independent loop)
        audio_path = config["audio_path"]
        cmd.extend(["-stream_loop", "-1", "-i", audio_path])
        cmd.extend([
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast",
            "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bufsize,
            "-vf", f"scale={width}:{height}", "-r", "30",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-f", "flv", rtmp_target
        ])
    else:
        # Mode 3: Mute (silent audio)
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
        cmd.extend([
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast",
            "-b:v", bitrate, "-maxrate", bitrate, "-bufsize", bufsize,
            "-vf", f"scale={width}:{height}", "-r", "30",
            "-c:a", "aac", "-b:a", "128k",
            "-f", "flv", rtmp_target
        ])
        
    return cmd


async def read_stderr(stderr_stream, stream_key: str):
    leftover = b""
    while True:
        try:
            chunk = await stderr_stream.read(4096)
            if not chunk:
                break
        except Exception:
            break
            
        data = leftover + chunk
        lines = data.split(b"\n")
        leftover = lines[-1]
        
        for line in lines[:-1]:
            decoded = line.decode("utf-8", errors="ignore").strip()
            if not decoded:
                continue
            
            # Mask stream key
            masked = decoded
            if stream_key and stream_key in decoded:
                masked = decoded.replace(stream_key, "****STREAM_KEY****")
                
            add_log(masked)
            
            # Detect successful stream connection to transition status to "live"
            if "frame=" in decoded and state.status == "connecting":
                state.status = "live"
                # Start tracking elapsed time only from the first successful connection
                if not state.start_time:
                    state.start_time = time.time()


async def stream_with_reconnect(config: dict, stream_key: str):
    state.reconnect_attempts = 0
    state.stop_requested = False
    state.start_time = None
    state.status = "connecting"
    
    rtmp_url = config.get("rtmp_url", "rtmp://a.rtmp.youtube.com/live2")
    if rtmp_url.endswith("/"):
        rtmp_url = rtmp_url[:-1]
    
    rtmp_target = f"{rtmp_url}/{stream_key}"
    
    while not state.stop_requested:
        state.reconnect_attempts += 1
        attempt = state.reconnect_attempts
        
        add_log(f"[{now_ts()}] Memulai stream FFmpeg (Percobaan #{attempt})...")
        
        # Log parsed command (with masked stream key)
        cmd = build_ffmpeg_cmd(config, rtmp_target)
        masked_cmd = [x.replace(stream_key, "****STREAM_KEY****") if stream_key in x else x for x in cmd]
        add_log(f"[{now_ts()}] Command: {' '.join(masked_cmd)}")
        
        try:
            state.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=10 * 1024 * 1024
            )
            # Write PID
            with open(PID_FILE, "w") as f:
                f.write(str(state.process.pid))
        except Exception as e:
            add_log(f"[{now_ts()}] Gagal menjalankan FFmpeg: {str(e)}")
            state.status = "error"
            state.error_message = str(e)
            await asyncio.sleep(5)
            continue
            
        log_task = asyncio.create_task(read_stderr(state.process.stderr, stream_key))
        
        await state.process.wait()
        await log_task
        
        # Clean PID file
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass
                
        rc = state.process.returncode
        add_log(f"[{now_ts()}] FFmpeg keluar dengan return code {rc}")
        
        if state.stop_requested:
            break
            
        add_log(f"[{now_ts()}] Koneksi terputus. Mencoba reconnect dalam 5 detik... (Percobaan #{attempt + 1})")
        state.status = "reconnecting"
        
        # Sleep with early breakout if stop requested
        for _ in range(5):
            if state.stop_requested:
                break
            await asyncio.sleep(1)
            
    state.status = "idle"
    state.process = None
    state.task = None


# --- Library API ---

@router.get("/library/video")
async def list_videos():
    try:
        with open(VIDEO_INDEX, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to read video library: {e}"})


@router.post("/library/video/add")
async def add_video(file: UploadFile = File(...)):
    filename = file.filename
    filename = "".join(c for c in filename if c.isalnum() or c in "._-").strip()
    if not filename:
        return JSONResponse(status_code=400, content={"error": "Nama berkas tidak valid"})
        
    video_path = os.path.join(VIDEO_DIR, filename)
    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    # Extract metadata
    info = await get_media_info(video_path, is_video=True)
    
    # Generate thumbnail
    thumb_name = os.path.splitext(filename)[0] + ".jpg"
    thumb_path = os.path.join(THUMBS_DIR, thumb_name)
    await extract_thumbnail(video_path, thumb_path)
    
    # Update index
    with open(VIDEO_INDEX, "r+", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = []
        data = [x for x in data if x["filename"] != filename]
        data.append({
            "filename": filename,
            "title": os.path.splitext(filename)[0],
            "duration": info["duration"],
            "width": info.get("width", 0),
            "height": info.get("height", 0),
            "size": info["size"],
            "size_str": get_file_size_str(video_path),
            "thumbnail": f"media/video/thumbs/{thumb_name}",
            "has_audio": info["has_audio"]
        })
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return {"status": "success", "filename": filename}


@router.delete("/library/video/{filename}")
async def delete_video(filename: str):
    video_path = os.path.join(VIDEO_DIR, filename)
    if os.path.exists(video_path):
        os.remove(video_path)
        
    thumb_name = os.path.splitext(filename)[0] + ".jpg"
    thumb_path = os.path.join(THUMBS_DIR, thumb_name)
    if os.path.exists(thumb_path):
        os.remove(thumb_path)
        
    with open(VIDEO_INDEX, "r+", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = []
        data = [x for x in data if x["filename"] != filename]
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return {"status": "success"}


@router.get("/library/audio")
async def list_audios():
    try:
        with open(AUDIO_INDEX, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to read audio library: {e}"})


@router.post("/library/audio/add")
async def add_audio(file: UploadFile = File(...)):
    filename = file.filename
    filename = "".join(c for c in filename if c.isalnum() or c in "._-").strip()
    if not filename:
        return JSONResponse(status_code=400, content={"error": "Nama berkas tidak valid"})
        
    audio_path = os.path.join(AUDIO_DIR, filename)
    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    # Extract metadata
    info = await get_media_info(audio_path, is_video=False)
    
    # Update index
    with open(AUDIO_INDEX, "r+", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = []
        data = [x for x in data if x["filename"] != filename]
        data.append({
            "filename": filename,
            "title": os.path.splitext(filename)[0],
            "duration": info["duration"],
            "format": os.path.splitext(filename)[1][1:].lower(),
            "size": info["size"],
            "size_str": get_file_size_str(audio_path)
        })
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return {"status": "success", "filename": filename}


@router.delete("/library/audio/{filename}")
async def delete_audio(filename: str):
    audio_path = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    with open(AUDIO_INDEX, "r+", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = []
        data = [x for x in data if x["filename"] != filename]
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    return {"status": "success"}


# --- Streaming API ---

@router.post("/start")
async def start_live(request: Request, background_tasks: BackgroundTasks):
    if state.status in ["connecting", "live", "reconnecting"]:
        return JSONResponse(status_code=400, content={"error": "Streaming sudah berjalan"})
        
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Payload JSON tidak valid"})
        
    video_source = data.get("video_source", "local")  # local or library
    video_val = data.get("video_path", "").strip()
    audio_source = data.get("audio_source", "video")  # video, library, mute
    audio_val = data.get("audio_path", "").strip()
    quality = data.get("quality", "720p")
    rtmp_url = data.get("rtmp_url", "rtmp://a.rtmp.youtube.com/live2").strip()
    stream_key = data.get("stream_key", "").strip()
    
    if not video_val:
        return JSONResponse(status_code=400, content={"error": "Pilih video terlebih dahulu"})
        
    if not stream_key:
        return JSONResponse(status_code=400, content={"error": "Stream key tidak boleh kosong"})
        
    # Resolve video path
    if video_source == "library":
        video_path = os.path.join(VIDEO_DIR, video_val)
    else:
        video_path = video_val
        
    if not os.path.exists(video_path):
        return JSONResponse(status_code=400, content={"error": f"File video tidak ditemukan: {video_val}"})
        
    # Resolve audio path
    audio_path = ""
    if audio_source == "library":
        if not audio_val:
            return JSONResponse(status_code=400, content={"error": "Pilih audio dari library terlebih dahulu"})
        audio_path = os.path.join(AUDIO_DIR, audio_val)
        if not os.path.exists(audio_path):
            return JSONResponse(status_code=400, content={"error": f"File audio tidak ditemukan: {audio_val}"})
            
    # Check if video has audio
    info = await get_media_info(video_path, is_video=True)
    if audio_source == "video" and not info.get("has_audio", False):
        audio_source = "mute"
        add_log(f"[{now_ts()}] [Warning] Video tidak memiliki track audio. Fallback ke Mute.")
        
    config = {
        "video_path": video_path,
        "audio_source": audio_source,
        "audio_path": audio_path,
        "quality": quality,
        "rtmp_url": rtmp_url
    }
    
    state.config = config
    state.stream_key = stream_key
    state.logs = []
    state.error_message = ""
    
    # Start reconnection background loop
    state.task = asyncio.create_task(stream_with_reconnect(config, stream_key))
    
    return {"status": "success", "message": "Inisialisasi streaming dimulai"}


@router.post("/stop")
async def stop_live():
    if state.status == "idle":
        return JSONResponse(status_code=400, content={"error": "Streaming tidak aktif"})
        
    state.stop_requested = True
    add_log(f"[{now_ts()}] Menghentikan streaming atas permintaan pengguna...")
    
    # Terminate process
    if state.process:
        try:
            state.process.terminate()
            try:
                await asyncio.wait_for(state.process.wait(), timeout=3)
            except asyncio.TimeoutError:
                state.process.kill()
        except Exception as e:
            add_log(f"[{now_ts()}] Error saat menghentikan FFmpeg: {e}")
            
    # Cancel background task
    if state.task:
        state.task.cancel()
        try:
            await state.task
        except asyncio.CancelledError:
            pass
            
    # Clean PID file
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
            
    state.status = "idle"
    state.process = None
    state.task = None
    state.start_time = None
    add_log(f"[{now_ts()}] Live streaming berhasil dihentikan.")
    
    return {"status": "success"}


@router.get("/status/stream")
async def live_status_sse():
    async def event_generator():
        while True:
            duration = 0
            if state.status == "live" and state.start_time:
                duration = int(time.time() - state.start_time)
                
            payload = {
                "status": state.status,
                "duration": duration,
                "logs": state.logs,
                "reconnect_attempts": state.reconnect_attempts,
                "error_message": state.error_message
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(1)
            
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
