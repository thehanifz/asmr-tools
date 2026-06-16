"""Clip Concatenator (Gabung Klip) backend logic."""
import os
import json
import time
import subprocess
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file
from core.env import get_thread_flags, video_encoder_flags, USE_NVENC

router = APIRouter(prefix="/concat", tags=["concat"])


def _open_tk():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    return root


@router.get("/browse-videos")
async def browse_videos():
    try:
        from tkinter import filedialog
        root = _open_tk()
        paths = filedialog.askopenfilenames(
            title="Pilih File Video (Bisa Multi-Select)",
            filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv *.webm"), ("All", "*.*")],
        )
        root.destroy()
        return {"paths": [p.replace("/", os.sep) for p in paths] if paths else []}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def probe_single_video(path: str) -> dict:
    if not os.path.exists(path):
        return {"path": path, "error": "File tidak ditemukan"}
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries",
            "format=duration,size"
            ":stream=width,height,codec_name,codec_type",
            "-of", "json", path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if not result.stdout.strip():
            return {"path": path, "error": "ffprobe tidak return output"}
        info = json.loads(result.stdout)
        fmt = info.get("format", {})
        streams = info.get("streams", [])
        
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
        
        duration = float(fmt.get("duration", 0))
        size = int(fmt.get("size", 0))
        
        h = int(duration // 3600)
        m = int((duration % 3600) // 60)
        s = int(duration % 60)
        dur_str = f"{h}j {m:02d}m {s:02d}s" if h else (f"{m}m {s:02d}s" if m else f"{s}s")
        
        return {
            "path": path,
            "filename": os.path.basename(path),
            "duration": round(duration, 2),
            "duration_str": dur_str,
            "size": size,
            "size_str": f"{size/1024/1024:.1f} MB" if size >= 1024*1024 else f"{size/1024:.0f} KB",
            "width": video_stream.get("width") if video_stream else None,
            "height": video_stream.get("height") if video_stream else None,
            "video_codec": video_stream.get("codec_name") if video_stream else None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "has_video": bool(video_stream),
            "has_audio": bool(audio_stream)
        }
    except Exception as e:
        return {"path": path, "error": str(e)}


@router.post("/probe-videos")
async def probe_videos(request: Request):
    try:
        data = await request.json()
        paths = data.get("paths", [])
        results = [probe_single_video(p) for p in paths]
        return {"paths": results}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/render")
async def render_concat(request: Request):
    try:
        data = await request.json()
        video_paths = data.get("video_paths", [])
        transition_type = data.get("transition_type", "hard_cut")
        transition_duration = float(data.get("transition_duration", 1.0))
        output_path = data.get("output_path", "")

        if len(video_paths) < 2:
            return JSONResponse({"error": "Minimal 2 file video diperlukan untuk menggabungkan klip"}, status_code=400)

        # Probe all videos
        probed_videos = []
        for p in video_paths:
            info = probe_single_video(p)
            if "error" in info:
                return JSONResponse({"error": f"Gagal membaca file: {info['path']} ({info['error']})"}, status_code=400)
            probed_videos.append(info)

        # Output folder setup
        first_input = video_paths[0]
        output_dir = os.path.dirname(first_input)
        if not output_path:
            ts_str = time.strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"gabung_klip_{ts_str}.mp4")

        # Analyze codecs & resolution
        has_audios = [v["has_audio"] for v in probed_videos]
        durations = [v["duration"] for v in probed_videos]
        widths = [v["width"] for v in probed_videos if v["has_video"]]
        heights = [v["height"] for v in probed_videos if v["has_video"]]
        video_codecs = [v["video_codec"] for v in probed_videos if v["has_video"]]
        audio_codecs = [v["audio_codec"] for v in probed_videos if v["has_audio"]]

        # Default fallback target resolution is the smallest video resolution (smallest area)
        target_w, target_h = 1920, 1080
        if widths and heights:
            min_area = float("inf")
            for w, h in zip(widths, heights):
                if w and h:
                    area = w * h
                    if area < min_area:
                        min_area = area
                        target_w, target_h = w, h

        # Check if they are all identical
        same_res = len(set(zip(widths, heights))) <= 1
        same_vcodec = len(set(video_codecs)) <= 1
        same_acodec = len(set(audio_codecs)) <= 1 if audio_codecs else True
        same_audio_presence = len(set(has_audios)) <= 1

        all_identical = same_res and same_vcodec and same_acodec and same_audio_presence

        cmd = []
        cleanup_files = []
        
        # Determine final expected duration
        N = len(video_paths)
        if transition_type == "crossfade":
            final_duration = sum(durations) - (N - 1) * transition_duration
        else:
            final_duration = sum(durations)

        # Decide FFmpeg command structure
        if transition_type == "hard_cut" and all_identical:
            # Concat demuxer (ultra fast, copy-paste)
            temp_list_path = os.path.join(output_dir, f"_tmp_concat_list_{int(time.time())}.txt")
            with open(temp_list_path, "w", encoding="utf-8") as f:
                for p in video_paths:
                    p_esc = p.replace("\\", "/")
                    f.write(f"file '{p_esc}'\n")
            cleanup_files.append(temp_list_path)

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", temp_list_path,
                "-c", "copy",
                output_path
            ]
            label = f"🎬 Gabung Klip (Hard Cut - Fast Copy) → {fmt_duration(final_duration)}"
        else:
            # Falls back to re-encoding because transition_type == "crossfade" or mismatched video formats
            filter_parts = []
            
            # 1. Normalize video (scale to smallest resolution, set format to yuv420p) and audio (resample to stereo 48000Hz)
            for i in range(N):
                filter_parts.append(f"[{i}:v]scale={target_w}:{target_h},format=yuv420p[v{i}]")
                if not has_audios[i]:
                    filter_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={durations[i]}[a_silence{i}]")
                    filter_parts.append(f"[a_silence{i}]acopy[a{i}]")
                else:
                    filter_parts.append(f"[{i}:a]aresample=async=1,aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
            
            if transition_type == "crossfade":
                CD = transition_duration
                # Chain video xfade
                current_v_in = "v0"
                running_duration = durations[0]
                for i in range(1, N):
                    offset = running_duration - CD
                    out_v = f"v_temp{i}" if i < N - 1 else "vout"
                    filter_parts.append(f"[{current_v_in}][v{i}]xfade=transition=fade:duration={CD}:offset={offset:.6f}[{out_v}]")
                    current_v_in = out_v
                    running_duration = running_duration + durations[i] - CD

                # Chain audio acrossfade
                current_a_in = "a0"
                for i in range(1, N):
                    out_a = f"a_temp{i}" if i < N - 1 else "aout"
                    filter_parts.append(f"[{current_a_in}][a{i}]acrossfade=d={CD}:c1=tri:c2=tri[{out_a}]")
                    current_a_in = out_a
                
                label = f"🎬 Gabung Klip (Crossfade {CD}s) → {fmt_duration(final_duration)}"
            else:
                # Hard Cut re-encode due to mismatched formats
                concat_inputs = ""
                for i in range(N):
                    concat_inputs += f"[v{i}][a{i}]"
                filter_parts.append(f"{concat_inputs}concat=n={N}:v=1:a=1[vout][aout]")
                label = f"🎬 Gabung Klip (Hard Cut - Re-encode Fallback to {target_w}x{target_h}) → {fmt_duration(final_duration)}"

            filter_complex = ";".join(filter_parts)

            cmd = ["ffmpeg", "-y", *get_thread_flags()]
            for p in video_paths:
                cmd.extend(["-i", p])
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "[aout]",
                *video_encoder_flags(crf=23, preset="fast"),
                "-c:a", "aac", "-b:a", "192k",
                output_path
            ])

        async def stream_render():
            yield f"data: {json.dumps({'type': 'step_start', 'label': label})}\n\n"
            try:
                async for chunk in run_ffmpeg_stream(cmd, label="Clip Concatenator", target_duration=final_duration):
                    yield chunk
            finally:
                for tf in cleanup_files:
                    try:
                        safe_remove_file(tf)
                    except Exception as e:
                        print(f"[WARN] Gagal menghapus temp file {tf}: {e}")
            
            if os.path.exists(output_path):
                size_str = get_file_size_str(output_path)
                yield f"data: {json.dumps({'status': 'all_done', 'output': output_path, 'final_size': size_str})}\n\n"

        return StreamingResponse(
            stream_render(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/download")
async def download_file(path: str = Query(..., description="Absolute path to file")):
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    filename = os.path.basename(path)
    return FileResponse(path, media_type="application/octet-stream", filename=filename)
