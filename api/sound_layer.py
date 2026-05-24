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


@router.post("/preview")
async def preview_placement(request: Request):
    """
    Generate placement plan.
    Accepts new per-sound optional_sounds[] array.
    Each item: { path, volume, fade_in, fade_out, occurrence_count,
                 min_duration, max_duration, time_window_start,
                 time_window_end, min_gap, overlap_mode }
    """
    try:
        data = await request.json()
        main_sounds = data.get("main_sounds", [])
        if not main_sounds:
            return JSONResponse({"error": "At least one main sound is required"}, status_code=400)

        optional_sounds = data.get("optional_sounds", [])
        target_duration = float(data.get("target_duration", 3600.0))
        loop_xfade      = float(data.get("loop_xfade", 2.0))
        output_format   = data.get("output_format", "aac")

        all_placements = []

        # Generate plan per sound
        for snd in optional_sounds:
            path = snd.get("path", "")
            if not path or not os.path.exists(path):
                continue

            config = LayerConfig(
                main_sounds=main_sounds,
                optional_sounds_folder="",
                output_path="",
                target_duration=target_duration,
                loop_xfade=loop_xfade,
                output_format=output_format,
                occurrence_count=int(snd.get("occurrence_count", 10)),
                time_window_start=float(snd.get("time_window_start", 0.0)),
                time_window_end=float(snd.get("time_window_end", 0.0)),
                min_duration=float(snd.get("min_duration", 3.0)),
                max_duration=float(snd.get("max_duration", 15.0)),
                min_gap=float(snd.get("min_gap", 0.0)),
                overlap_mode=snd.get("overlap_mode", "full"),
                fade_duration=max(
                    float(snd.get("fade_in", 1.5)),
                    float(snd.get("fade_out", 1.5))
                ),
                silence_threshold=-50.0,
            )

            engine = SoundLayerEngine(config)
            engine.optional_sound_files = [path]
            plan = await engine.generate_placement_plan()

            # Patch fade_in / fade_out individually per placement
            fi = float(snd.get("fade_in", 1.5))
            fo = float(snd.get("fade_out", 1.5))
            vol = int(snd.get("volume", 80))
            for p in plan.placements:
                p.fade_in  = fi
                p.fade_out = fo
                # Store volume in trimmed_start field is not clean;
                # use a custom attr via dict later when building final plan
                p._volume = vol  # temporary attr

            all_placements.extend(plan.placements)

        # Sort all placements by start time
        all_placements.sort(key=lambda p: p.start_time)

        # Build merged plan
        merged = PlacementPlan(
            version="1.0",
            main_sounds=main_sounds,
            optional_sounds_folder="",
            target_duration=target_duration,
            placements=all_placements,
        )

        result = json.loads(merged.to_json())

        # Inject volume into each placement for the renderer
        for i, p in enumerate(all_placements):
            result["placements"][i]["volume"] = getattr(p, '_volume', 80)

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/render")
async def render_mix(request: Request):
    try:
        data = await request.json()
        plan_data = data.get("plan")
        output_path      = data.get("output_path", "")
        preview_mode     = bool(data.get("preview_mode", False))
        output_format    = data.get("output_format", "aac").lower()
        loop_xfade       = float(data.get("loop_xfade", 2.0))
        target_duration  = float(data.get("target_duration", 3600.0))
        silence_threshold = -50.0  # hardcoded

        if not plan_data:
            return JSONResponse({"error": "Placement plan is required"}, status_code=400)

        plan = PlacementPlan.from_json(json.dumps(plan_data))

        if not output_path:
            base = os.path.splitext(plan.main_sounds[0]["path"])[0] if plan.main_sounds else "mix"
            if preview_mode:
                output_path = os.path.join(os.path.dirname(base), "preview_mix_temp." + output_format)
            else:
                output_path = base + "._layered." + output_format
        else:
            output_path = os.path.splitext(output_path)[0] + "." + output_format

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        config = LayerConfig(
            main_sounds=plan.main_sounds,
            optional_sounds_folder=plan.optional_sounds_folder,
            output_path=output_path,
            target_duration=target_duration,
            loop_xfade=loop_xfade,
            output_format=output_format,
            silence_threshold=silence_threshold,
        )
        engine = SoundLayerEngine(config)
        cmd = engine.build_ffmpeg_command(plan, preview_mode=preview_mode)

        async def stream_render():
            import time
            from api.utils import now_ts
            start = time.time()
            yield f"data: {json.dumps({'status': 'start', 'ts': now_ts(), 'label': 'Sound Layer Render', 'elapsed': 0})}\n\n"
            yield f"data: {json.dumps({'log': f'Rendering {len(plan.placements)} placements...', 'ts': now_ts(), 'elapsed': 0})}\n\n"
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
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".m4a", ".mp3", ".wav", ".ogg", ".aac"):
        raise HTTPException(status_code=400, detail="Only audio files allowed")
    media_type = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav",
                  ".ogg": "audio/ogg", ".aac": "audio/aac"}.get(ext, "audio/mpeg")
    return FileResponse(path, media_type=media_type)
