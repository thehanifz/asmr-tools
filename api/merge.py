"""Merge video + multi-audio layers into final MP4."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str

router = APIRouter(tags=["merge"])


@router.post("/merge")
async def merge_video_audio(request: Request):
    """Merge 1 video + 1-4 audio layers with per-layer volume control.

    Payload:
      video        : str  — video file path (no audio / audio will be replaced)
      audio_layers : list — [{path: str, volume: int (0-200)}]
      output       : str  — final output path

    Also supports legacy format: { video, audio, output }
    """
    data = await request.json()
    video_path  = data["video"]
    output_path = data["output"]

    # Support legacy single-audio format
    if "audio" in data and "audio_layers" not in data:
        layers = [{"path": data["audio"], "volume": 100}]
    else:
        layers = data.get("audio_layers", [])

    layers = [l for l in layers if l.get("path")]  # filter empty
    if not layers:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Minimal 1 audio layer diperlukan"}, status_code=400)

    n = len(layers)

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y", "-i", video_path]
    for l in layers:
        cmd += ["-i", l["path"]]

    if n == 1:
        # Single audio — simple map, no filter needed
        vol = layers[0]["volume"] / 100.0
        if vol != 1.0:
            cmd += [
                "-filter_complex", f"[1:a]volume={vol}[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
            ]
        else:
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    else:
        # Multi-audio — amix with per-layer volume
        filter_parts = []
        mix_inputs = ""
        for i, l in enumerate(layers):
            vol = l["volume"] / 100.0
            label = f"a{i+1}"
            filter_parts.append(f"[{i+1}:a]volume={vol}[{label}]")
            mix_inputs += f"[{label}]"

        filter_parts.append(
            f"{mix_inputs}amix=inputs={n}:duration=first:normalize=0[aout]"
        )
        filter_complex = ";".join(filter_parts)

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[aout]",
        ]

    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", output_path]

    async def run():
        t_start = time.time()
        layer_desc = ", ".join([f"{os.path.basename(l['path'])} ({l['volume']}%)" for l in layers])
        yield f"data: {json.dumps({'type': 'step_start', 'label': f'🔧 Mux video + {n} audio layer(s)'})}\n\n"
        yield f"data: {json.dumps({'log': f'Layers: {layer_desc}'})}\n\n"

        async for chunk in run_ffmpeg_stream(cmd):
            yield chunk

        elapsed  = time.time() - t_start
        size_str = get_file_size_str(output_path) if os.path.exists(output_path) else "?"
        yield f"data: {json.dumps({'type': 'done', 'output': output_path, 'size': size_str, 'elapsed': fmt_duration(elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
