"""Sound Layer API router for FastAPI."""
import os
import json
import asyncio
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from core.sound_layer_engine import LayerConfig, SoundLayerEngine, PlacementPlan
from api.utils import run_ffmpeg_stream

router = APIRouter(prefix="/sound-layer", tags=["sound-layer"])


# ─── Preview / Plan ────────────────────────────────────────────────────────────

@router.post("/preview")
async def preview_placement(request: Request):
    """
    Generate placement plan.
    Accepts per-sound optional_sounds[] array.
    """
    try:
        data = await request.json()
        main_sounds     = data.get("main_sounds", [])
        if not main_sounds:
            return JSONResponse({"error": "At least one main sound is required"}, status_code=400)

        optional_sounds = data.get("optional_sounds", [])
        target_duration = float(data.get("target_duration", 3600.0))
        loop_xfade      = float(data.get("loop_xfade", 2.0))
        output_format   = data.get("output_format", "aac")

        all_placements = []

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
                    float(snd.get("fade_out", 1.5)),
                ),
                silence_threshold=-50.0,
            )

            engine = SoundLayerEngine(config)
            engine.optional_sound_files = [path]
            plan = await engine.generate_placement_plan()

            fi  = float(snd.get("fade_in", 1.5))
            fo  = float(snd.get("fade_out", 1.5))
            vol = int(snd.get("volume", 80))
            for p in plan.placements:
                p.fade_in  = fi
                p.fade_out = fo
                p.volume   = vol

            all_placements.extend(plan.placements)

        all_placements.sort(key=lambda p: p.start_time)

        merged = PlacementPlan(
            version="1.0",
            main_sounds=main_sounds,
            optional_sounds_folder="",
            target_duration=target_duration,
            placements=all_placements,
        )
        return JSONResponse(json.loads(merged.to_json()))

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Render (2-pass) ──────────────────────────────────────────────────────────

@router.post("/render")
async def render_mix(request: Request):
    try:
        data = await request.json()
        plan_data        = data.get("plan")
        output_path      = data.get("output_path", "")
        preview_mode     = bool(data.get("preview_mode", False))
        output_format    = data.get("output_format", "aac").lower()
        loop_xfade       = float(data.get("loop_xfade", 2.0))
        target_duration  = float(data.get("target_duration", 3600.0))
        preview_duration = float(data.get("preview_duration", 30.0))

        if not plan_data:
            return JSONResponse({"error": "Placement plan is required"}, status_code=400)

        plan = PlacementPlan.from_json(json.dumps(plan_data))

        # Resolve output path
        if not output_path:
            base = os.path.splitext(plan.main_sounds[0]["path"])[0] if plan.main_sounds else "mix"
            if preview_mode:
                output_path = os.path.join(os.path.dirname(base), f"preview_mix_temp.{output_format}")
            else:
                output_path = base + f"._layered.{output_format}"
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
            silence_threshold=-50.0,
        )
        engine = SoundLayerEngine(config)

        async def stream_render():
            from api.utils import now_ts, get_file_size_str
            import tempfile

            total_placements = len(plan.placements)
            use_2pass = total_placements > 0

            yield f"data: {json.dumps({'status': 'start', 'ts': now_ts(), 'label': 'Sound Layer Render', 'elapsed': 0})}\n\n"
            yield f"data: {json.dumps({'log': f'Memulai render {total_placements} placement ({"preview" if preview_mode else "full"})...', 'ts': now_ts(), 'progress': 0})}\n\n"

            if not use_2pass:
                # Tidak ada optional sounds — single-pass langsung
                cmd = engine.build_pass2_command(
                    plan,
                    opt_pcm="",   # tidak dipakai jika placements kosong
                    out_final=output_path,
                    preview_mode=preview_mode,
                    preview_duration=preview_duration,
                )
                async for chunk in run_ffmpeg_stream(cmd, label="Render (no optionals)"):
                    yield chunk
            else:
                # ── Step 1: Pre-decode unique sources ─────────────────────
                unique_srcs = list({p.source_file for p in plan.placements})
                total_srcs  = len(unique_srcs)
                yield f"data: {json.dumps({'log': f'[1/3] Pre-decode {total_srcs} sumber audio ke PCM...', 'progress': 2})}\n\n"

                for i, src in enumerate(unique_srcs):
                    yield f"data: {json.dumps({'log': f'  Decode {os.path.basename(src)} ({i+1}/{total_srcs})', 'progress': int(2 + (i+1)/total_srcs * 18)})}\n\n"
                    await engine._predecode_source(src)

                yield f"data: {json.dumps({'log': f'[1/3] Pre-decode selesai.', 'progress': 20})}\n\n"

                # ── Step 2: Pass-1 — Build optional layer ──────────────────
                tmp_pcm = os.path.join(
                    engine._get_temp_dir(),
                    "opt_layer.wav"
                )
                yield f"data: {json.dumps({'log': f'[2/3] Pass-1: Render optional layer ({total_placements} placement)...', 'progress': 22})}\n\n"

                cmd_p1 = engine.build_pass1_command(
                    plan, tmp_pcm,
                    preview_mode=preview_mode,
                    preview_duration=preview_duration,
                )

                if cmd_p1:
                    async for chunk in run_ffmpeg_stream(cmd_p1, label="Pass-1 Optional Layer", progress_start=22, progress_end=60):
                        yield chunk
                else:
                    # Buat file PCM kosong sebagai placeholder
                    proc = await asyncio.create_subprocess_exec(
                        "ffmpeg", "-y",
                        "-f", "lavfi", "-t", str(min(target_duration, preview_duration if preview_mode else target_duration)),
                        "-i", f"aevalsrc=0:c=stereo:r=44100",
                        "-c:a", "pcm_s16le", tmp_pcm,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    await proc.communicate()

                yield f"data: {json.dumps({'log': '[2/3] Pass-1 selesai.', 'progress': 62})}\n\n"

                # ── Step 3: Pass-2 — Mix main + optional layer ────────────
                yield f"data: {json.dumps({'log': '[3/3] Pass-2: Mix main sounds + optional layer...', 'progress': 64})}\n\n"

                cmd_p2 = engine.build_pass2_command(
                    plan, tmp_pcm, output_path,
                    preview_mode=preview_mode,
                    preview_duration=preview_duration,
                )

                async for chunk in run_ffmpeg_stream(cmd_p2, label="Pass-2 Final Mix", progress_start=64, progress_end=98):
                    yield chunk

            # ── Done ────────────────────────────────────────────────
            engine.cleanup()

            if os.path.exists(output_path):
                size_str = get_file_size_str(output_path)
                yield f"data: {json.dumps({'status': 'done', 'output': output_path, 'size': size_str, 'ts': now_ts(), 'progress': 100})}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'error', 'log': 'Output file tidak ditemukan setelah render.', 'ts': now_ts()})}\n\n"

        return StreamingResponse(
            stream_render(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Play ────────────────────────────────────────────────────────────────────

@router.get("/play")
async def play_audio(path: str = Query(..., description="Absolute path to audio file")):
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".m4a", ".mp3", ".wav", ".ogg", ".aac"):
        raise HTTPException(status_code=400, detail="Only audio files allowed")
    media_type = {
        ".m4a": "audio/mp4", ".mp3": "audio/mpeg",
        ".wav": "audio/wav", ".ogg": "audio/ogg", ".aac": "audio/aac",
    }.get(ext, "audio/mpeg")
    return FileResponse(path, media_type=media_type)
