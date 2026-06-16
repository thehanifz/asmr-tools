"""Loop B+A (Video Segment Swap) backend logic."""
import os
import json
import time
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str, safe_remove_file
from core.env import get_thread_flags, video_encoder_flags
from api.concat import probe_single_video

router = APIRouter(prefix="/loop-ba", tags=["loop-ba"])


@router.post("/render")
async def render_loop_ba(request: Request):
    try:
        data = await request.json()
        input_path = data.get("input_path", "").strip()
        transition_type = data.get("transition_type", "hard_cut")
        transition_duration = float(data.get("transition_duration", 1.0))
        output_path = data.get("output_path", "").strip()

        if not input_path or not os.path.exists(input_path):
            return JSONResponse({"error": "File input tidak ditemukan"}, status_code=400)

        # Probe video
        info = probe_single_video(input_path)
        if "error" in info:
            return JSONResponse({"error": f"Gagal membaca info video: {info['error']}"}, status_code=400)

        duration = info["duration"]
        if duration <= 0:
            return JSONResponse({"error": "Durasi video tidak valid (0 atau negatif)"}, status_code=400)

        midpoint = duration / 2.0
        output_dir = os.path.dirname(os.path.abspath(input_path))
        
        if not output_path:
            ts_str = time.strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"loop_ba_{ts_str}.mp4")

        # Segmen B duration
        b_duration = duration - midpoint

        if transition_type == "crossfade":
            if transition_duration > b_duration:
                return JSONResponse({"error": f"Durasi crossfade ({transition_duration}s) tidak boleh melebihi durasi segmen B ({b_duration:.2f}s)"}, status_code=400)
            
            # Crossfade mode: re-encode in one pass using trim and xfade
            offset = b_duration - transition_duration
            final_duration = duration - transition_duration
            
            filter_complex = (
                f"[0:v]trim=start={midpoint:.6f}:end={duration:.6f},setpts=PTS-STARTPTS[v_b]; "
                f"[0:v]trim=start=0:end={midpoint:.6f},setpts=PTS-STARTPTS[v_a]; "
                f"[v_b][v_a]xfade=transition=fade:duration={transition_duration:.6f}:offset={offset:.6f}[vout]"
            )
            cmd = [
                "ffmpeg", "-y", *get_thread_flags(),
                "-i", input_path,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-an",
                *video_encoder_flags(crf=23, preset="fast"),
                output_path
            ]
            label = f"🔄 Loop B+A (Crossfade {transition_duration}s) → {fmt_duration(final_duration)}"

            async def run_single_step():
                yield f"data: {json.dumps({'type': 'step_start', 'label': label})}\n\n"
                async for chunk in run_ffmpeg_stream(cmd, label="Loop B+A", target_duration=final_duration):
                    yield chunk
                if os.path.exists(output_path):
                    size_str = get_file_size_str(output_path)
                    yield f"data: {json.dumps({'status': 'all_done', 'output': output_path, 'final_size': size_str})}\n\n"

            return StreamingResponse(
                run_single_step(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        else:
            # Hard Cut mode (Stream Copy via split and concat)
            seg_a_path = os.path.join(output_dir, f"_tmp_seg_a_{int(time.time())}.mp4")
            seg_b_path = os.path.join(output_dir, f"_tmp_seg_b_{int(time.time())}.mp4")
            list_txt_path = os.path.join(output_dir, f"_tmp_list_ba_{int(time.time())}.txt")
            
            cmd_split_a = [
                "ffmpeg", "-y", *get_thread_flags(),
                "-ss", "0", "-i", input_path,
                "-t", f"{midpoint:.6f}",
                "-an", "-c:v", "copy",
                seg_a_path
            ]
            cmd_split_b = [
                "ffmpeg", "-y", *get_thread_flags(),
                "-ss", f"{midpoint:.6f}", "-i", input_path,
                "-an", "-c:v", "copy",
                seg_b_path
            ]
            
            with open(list_txt_path, "w", encoding="utf-8") as f:
                f.write(f"file '{seg_b_path.replace('\\', '/')}'\n")
                f.write(f"file '{seg_a_path.replace('\\', '/')}'\n")
                
            cmd_concat = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_txt_path,
                "-c", "copy",
                output_path
            ]
            
            cleanup_files = [seg_a_path, seg_b_path, list_txt_path]
            steps = [
                (cmd_split_a, f"✂️ Split Segmen A (0.0s s/d {midpoint:.2f}s)"),
                (cmd_split_b, f"✂️ Split Segmen B ({midpoint:.2f}s s/d {duration:.2f}s)"),
                (cmd_concat, f"🎬 Menggabungkan Segmen B + A (Hard Cut)")
            ]
            
            async def run_multi_steps():
                total_steps = len(steps)
                yield f"data: {json.dumps({'type': 'pipeline_start', 'total_steps': total_steps})}\n\n"
                
                for i, (step_cmd, step_label) in enumerate(steps):
                    yield f"data: {json.dumps({'type': 'step_start', 'step': i+1, 'total': total_steps, 'label': step_label})}\n\n"
                    error_occurred = False
                    
                    p_start = int((i / total_steps) * 100)
                    p_end = int(((i + 1) / total_steps) * 100)
                    step_dur = midpoint if i == 0 else (duration - midpoint if i == 1 else duration)
                    
                    async for chunk in run_ffmpeg_stream(
                        step_cmd,
                        label=step_label,
                        progress_start=p_start,
                        progress_end=p_end,
                        target_duration=step_dur
                    ):
                        parsed = json.loads(chunk[6:])
                        if parsed.get("status") == "error":
                            error_occurred = True
                            yield chunk
                            break
                        yield chunk
                        
                    if error_occurred:
                        yield f"data: {json.dumps({'type': 'step_error', 'step': i+1, 'label': step_label})}\n\n"
                        # Cleanup on error
                        for f in cleanup_files:
                            safe_remove_file(f)
                        return
                        
                for f in cleanup_files:
                    try:
                        safe_remove_file(f)
                    except Exception as e:
                        print(f"[WARN] Failed cleanup: {e}")
                        
                if os.path.exists(output_path):
                    size_str = get_file_size_str(output_path)
                    yield f"data: {json.dumps({'status': 'all_done', 'output': output_path, 'final_size': size_str})}\n\n"
                    
            return StreamingResponse(
                run_multi_steps(),
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
