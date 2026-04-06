"""Probe video or audio file using ffprobe."""
import json
import os
import subprocess
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["probe"])


def _fmt_bitrate(bps: int | str | None) -> str:
    try:
        b = int(bps or 0)
        if b >= 1_000_000:
            return f"{b/1_000_000:.1f} Mbps"
        elif b >= 1_000:
            return f"{b/1_000:.0f} kbps"
        return f"{b} bps"
    except Exception:
        return "-"


@router.post("/probe")
async def probe_file(request: Request):
    """Probe a video or audio file. Returns metadata as JSON.

    Payload: { "path": "C:/path/to/file.mp4" }
    """
    data = await request.json()
    path = data.get("path", "").strip()

    # Empty path — health check ping from frontend
    if not path:
        return JSONResponse({"status": "ok"})

    if not os.path.exists(path):
        return JSONResponse({"error": "File tidak ditemukan"}, status_code=404)

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries",
            "format=duration,size,bit_rate"
            ":stream=width,height,r_frame_rate,codec_name,codec_type,channels,sample_rate,bit_rate",
            "-of", "json", path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if not result.stdout.strip():
            return JSONResponse(
                {"error": "ffprobe tidak return output. Pastikan ffprobe terinstall."},
                status_code=500,
            )
        info = json.loads(result.stdout)
        fmt     = info.get("format", {})
        streams = info.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

        duration = float(fmt.get("duration", 0))
        size     = int(fmt.get("size", 0))
        bitrate  = fmt.get("bit_rate") or (
            video_stream.get("bit_rate") or audio_stream.get("bit_rate")
        )

        h = int(duration // 3600)
        m = int((duration % 3600) // 60)
        s = int(duration % 60)
        dur_str = f"{h}j {m:02d}m {s:02d}s" if h else (f"{m}m {s:02d}s" if m else f"{s}s")

        resp = {
            "duration":      round(duration, 2),
            "duration_str":  dur_str,
            "size":          size,
            "size_str":      f"{size/1024/1024:.1f} MB" if size >= 1024*1024 else f"{size/1024:.0f} KB",
            "bitrate_str":   _fmt_bitrate(bitrate),
            "filename":      os.path.basename(path),
            "has_video":     bool(video_stream),
            "has_audio":     bool(audio_stream),
        }

        if video_stream:
            fps_raw   = video_stream.get("r_frame_rate", "24/1")
            fps_parts = fps_raw.split("/")
            fps = round(int(fps_parts[0]) / max(int(fps_parts[1]), 1), 2)
            resp.update({
                "width":       video_stream.get("width", 0),
                "height":      video_stream.get("height", 0),
                "fps":         fps,
                "resolution":  f"{video_stream.get('width',0)}×{video_stream.get('height',0)}",
                "video_codec": video_stream.get("codec_name", "-"),
            })

        if audio_stream:
            resp.update({
                "audio_codec": audio_stream.get("codec_name", "-"),
                "channels":    audio_stream.get("channels", 0),
                "sample_rate": audio_stream.get("sample_rate", "-"),
            })

        return JSONResponse(resp)

    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "ffprobe timeout"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
