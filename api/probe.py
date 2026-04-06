"""Probe video or audio file using ffprobe."""
import json
import os
import subprocess
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["probe"])


@router.post("/probe")
async def probe_file(request: Request):
    data = await request.json()
    path = data.get("path", "").strip()
    if not os.path.exists(path):
        return JSONResponse({"error": "File tidak ditemukan"}, status_code=404)
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=width,height,r_frame_rate,codec_name,codec_type,channels,sample_rate",
            "-of", "json", path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if not result.stdout.strip():
            return JSONResponse(
                {"error": "ffprobe tidak return output. Pastikan ffprobe terinstall."},
                status_code=500,
            )
        info = json.loads(result.stdout)
        fmt = info.get("format", {})
        streams = info.get("streams", [])

        audio_codecs = {"aac", "mp3", "opus", "vorbis", "flac", "pcm_s16le", "pcm_s24le"}
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

        duration = float(fmt.get("duration", 0))
        size = int(fmt.get("size", 0))

        resp = {
            "duration": round(duration, 2),
            "duration_str": f"{int(duration//3600)}j {int((duration%3600)//60)}m {int(duration%60)}s",
            "size": size,
            "size_str": f"{size/1024/1024:.1f} MB",
            "filename": os.path.basename(path),
            "has_video": bool(video_stream),
            "has_audio": bool(audio_stream),
        }

        if video_stream:
            fps_raw = video_stream.get("r_frame_rate", "24/1")
            fps_parts = fps_raw.split("/")
            fps = round(int(fps_parts[0]) / int(fps_parts[1]), 2)
            resp.update({
                "width": video_stream.get("width", 0),
                "height": video_stream.get("height", 0),
                "fps": fps,
                "resolution": f"{video_stream.get('width',0)}x{video_stream.get('height',0)}",
                "video_codec": video_stream.get("codec_name", "-"),
            })

        if audio_stream:
            resp.update({
                "audio_codec": audio_stream.get("codec_name", "-"),
                "channels": audio_stream.get("channels", 0),
                "sample_rate": audio_stream.get("sample_rate", "-"),
            })

        return resp
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
