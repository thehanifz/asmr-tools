"""Sound Layer API router for FastAPI."""
import os
import json
import asyncio
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from core.sound_layer_engine import LayerConfig, SoundLayerEngine, PlacementPlan
from api.utils import run_ffmpeg_stream

router = APIRouter(prefix="/sound-layer", tags=["sound-layer"])


def _open_tk():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    return root


@router.get("/browse-folder-audio")
async def browse_folder_audio():
    try:
        from tkinter import filedialog
        root = _open_tk()
        path = filedialog.askdirectory(title="Pilih Folder Pool Optional Sounds")
        root.destroy()
        if not path:
            return {"path": "", "files": []}
        
        # Scan folder for audio files
        config = LayerConfig(main_sound="", optional_sounds_folder=path, output_path="")
        engine = SoundLayerEngine(config)
        files = engine.scan_optional_sounds()
        
        # Get duration for each file
        file_list = []
        for f in files:
            dur = await engine.get_audio_duration(f)
            file_list.append({
                "path": f,
                "name": os.path.basename(f),
                "duration": dur
            })
            
        return {"path": path.replace("/", os.sep), "files": file_list}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/preview")
async def preview_placement(request: Request):
    try:
        data = await request.json()
        main_sound = data.get("main_sound", "")
        optional_sounds_folder = data.get("optional_sounds_folder", "")
        included_files = data.get("included_files", [])
        
        if not main_sound:
            return JSONResponse({"error": "Main sound is required"}, status_code=400)
        if not optional_sounds_folder:
            return JSONResponse({"error": "Optional sounds folder is required"}, status_code=400)
        if not included_files:
            return JSONResponse({"error": "At least one optional sound must be selected"}, status_code=400)

        # Build config
        config = LayerConfig(
            main_sound=main_sound,
            optional_sounds_folder=optional_sounds_folder,
            output_path="",
            occurrence_count=int(data.get("occurrence_count", 10)),
            time_window_start=float(data.get("time_window_start", 0.0)),
            time_window_end=float(data.get("time_window_end", 0.0)),
            min_duration=float(data.get("min_duration", 3.0)),
            max_duration=float(data.get("max_duration", 10.0)),
            min_gap=float(data.get("min_gap", 2.0)),
            overlap_mode=data.get("overlap_mode", "none"),
            fade_duration=float(data.get("fade_duration", 0.5)),
            silence_threshold=float(data.get("silence_threshold", -50.0))
        )
        
        engine = SoundLayerEngine(config)
        engine.scan_optional_sounds()
        
        # Filter files to only what is included by user
        engine.optional_sound_files = [f for f in engine.optional_sound_files if f in included_files]
        if not engine.optional_sound_files:
            return JSONResponse({"error": "None of the selected files are valid or exist in the folder"}, status_code=400)
            
        plan = await engine.generate_placement_plan()
        return JSONResponse(json.loads(plan.to_json()))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/render")
async def render_mix(request: Request):
    try:
        data = await request.json()
        plan_data = data.get("plan")
        output_path = data.get("output_path", "")
        silence_threshold = float(data.get("silence_threshold", -50.0))
        
        if not plan_data:
            return JSONResponse({"error": "Placement plan is required"}, status_code=400)
            
        plan = PlacementPlan.from_json(json.dumps(plan_data))
        
        if not output_path:
            base = os.path.splitext(plan.main_sound_path)[0]
            output_path = base + "._layered.m4a"
        else:
            name_without_ext = os.path.splitext(output_path)[0]
            output_path = name_without_ext + ".m4a"
            
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        config = LayerConfig(
            main_sound=plan.main_sound_path,
            optional_sounds_folder=plan.optional_sounds_folder,
            output_path=output_path,
            silence_threshold=silence_threshold
        )
        engine = SoundLayerEngine(config)
        cmd = engine.build_ffmpeg_command(plan)
        
        async def stream_render():
            import time
            from api.utils import now_ts
            
            start = time.time()
            yield f"data: {json.dumps({'status': 'start', 'ts': now_ts(), 'label': 'Sound Layer Render', 'elapsed': 0})}\n\n"
            yield f"data: {json.dumps({'log': f'Rendering sound layer mix with {len(plan.placements)} placements...', 'ts': now_ts(), 'elapsed': 0})}\n\n"
            
            async for chunk in run_ffmpeg_stream(cmd, label="Sound Layer Render"):
                yield chunk
                
            if os.path.exists(output_path):
                from api.utils import get_file_size_str
                size_str = get_file_size_str(output_path)
                yield f"data: {json.dumps({'status': 'done', 'output': output_path, 'size': size_str, 'ts': now_ts()})}\n\n"
                
        return StreamingResponse(
            stream_render(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/play")
async def play_audio(path: str = Query(..., description="Absolute path to audio file")):
    """Serve an audio file directly to the browser for playing.
    GET /api/sound-layer/play?path=...
    """
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".m4a", ".mp3", ".wav", ".ogg", ".aac"):
        raise HTTPException(status_code=400, detail="Only audio files allowed")
        
    media_type = {
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".aac": "audio/aac",
    }.get(ext, "audio/mpeg")
    
    return FileResponse(path, media_type=media_type)

