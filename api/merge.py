"""Merge video + audio into final MP4."""
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str

router = APIRouter(tags=["merge"])


@router.post("/merge")
async def merge_video_audio(request: Request):
    """
    Merge a pre-processed video file (no audio) with a pre-processed audio file.
    Both inputs should already be at the target duration.
    Uses stream copy — extremely fast, no quality loss.
    """
    data = await request.json()
    video_path = data["video"]   # _video_looped.mp4
    audio_path = data["audio"]   # _audio_looped.m4a
    output_path = data["output"] # final.mp4

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "copy",
        "-shortest",
        output_path,
    ]

    async def run():
        t_start = time.time()
        yield f"data: {json.dumps({'type': 'step_start', 'label': '🔧 Mux video + audio'})}\n\n"
        async for chunk in run_ffmpeg_stream(cmd):
            yield chunk
        elapsed = time.time() - t_start
        size_str = get_file_size_str(output_path) if os.path.exists(output_path) else "?"
        yield f"data: {json.dumps({'type': 'done', 'output': output_path, 'size': size_str, 'elapsed': fmt_duration(elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
