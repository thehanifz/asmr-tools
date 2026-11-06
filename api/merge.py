"""Merge video + multi-audio layers into final MP4.

Perubahan audio-first:
- Pan per layer ala qipadd/asmr-mix-tools: tiap layer bisa ditempatkan
  left / center / right (atau angka -1..1) di ruang stereo, bukan cuma volume.
- Jalur copy ala tools-asmr (Mas Arif): bila hanya ada 1 layer tanpa
  pengolahan (volume 100%, pan tengah) dan codec-nya sudah AAC, audio
  di-stream-copy (`-c:a copy`) — tidak di-encode ulang sama sekali.
- Bila harus encode, bitrate AAC naik 192k -> 320k agar detail ASMR
  (frekuensi tinggi, transien pelan) tidak rontok sebelum upload YouTube.
"""
import asyncio
import os
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str
from core.audio_filters import normalize_pan, pan_filter
from core.env import get_thread_flags

router = APIRouter(tags=["merge"])


async def _probe_audio_codec(path: str) -> str:
    """Codec audio stream pertama (mis. 'aac', 'mp3'), '' bila gagal probe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode(errors="ignore").strip().lower()
    except Exception:
        return ""


def _layer_filter(idx: int, layer: dict) -> str:
    """Filter chain satu layer: aformat stereo -> volume -> pan (urutan qipadd)."""
    vol = layer.get("volume", 100) / 100.0
    pan_f = pan_filter(layer.get("pan", "center"))
    segments = []
    if pan_f:
        segments.append("aformat=channel_layouts=stereo")
    segments.append(f"volume={vol}")
    if pan_f:
        segments.append(pan_f)
    return f"[{idx}:a]" + ",".join(segments) + f"[a{idx}]"


@router.post("/merge")
async def merge_video_audio(request: Request):
    """Merge 1 video + 1-4 audio layers with per-layer volume + pan control.

    Payload:
      video        : str  — video file path (no audio / audio will be replaced)
      audio_layers : list — [{path: str, volume: int (0-200),
                              pan: "left"|"center"|"right" | float -1..1}]
      output       : str  — final output path

    Also supports legacy format: { video, audio, output }
    """
    data = await request.json()
    video_path  = data["video"]
    output_path = data.get("output", "")
    if not output_path:
        output_dir = os.path.dirname(video_path)
        basename = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(output_dir, f"merge_{basename}.mp4")

    # Support legacy single-audio format
    if "audio" in data and "audio_layers" not in data:
        layers = [{"path": data["audio"], "volume": 100, "pan": "center"}]
    else:
        layers = data.get("audio_layers", [])

    layers = [l for l in layers if l.get("path")]  # filter empty
    if not layers:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Minimal 1 audio layer diperlukan"}, status_code=400)
    for l in layers:
        l.setdefault("volume", 100)
        l.setdefault("pan", "center")

    n = len(layers)

    # Jalur copy (Mas Arif): 1 layer, tanpa pengolahan, codec sudah AAC,
    # output MP4 -> audio disalin apa adanya, nol generasi encode hilang.
    use_copy = False
    if (
        n == 1
        and layers[0]["volume"] == 100
        and normalize_pan(layers[0].get("pan")) == 0.0
        and os.path.splitext(output_path)[1].lower() in (".mp4", ".m4v", ".mov")
    ):
        use_copy = (await _probe_audio_codec(layers[0]["path"])) == "aac"

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y", *get_thread_flags(), "-i", video_path]
    for l in layers:
        cmd += ["-i", l["path"]]

    if use_copy:
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
        cmd += ["-c:v", "copy", "-c:a", "copy", output_path]
    elif n == 1:
        # Single audio — filter hanya bila volume / pan memang diubah
        vol = layers[0]["volume"] / 100.0
        pan_f = pan_filter(layers[0].get("pan"))
        if vol != 1.0 or pan_f:
            segments = []
            if pan_f:
                segments.append("aformat=channel_layouts=stereo")
            if vol != 1.0:
                segments.append(f"volume={vol}")
            if pan_f:
                segments.append(pan_f)
            cmd += [
                "-filter_complex", f"[1:a]{','.join(segments)}[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
            ]
        else:
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "320k", output_path]
    else:
        # Multi-audio — amix dengan volume + pan per layer,
        # normalize=0 ala qipadd agar dinamika tidak dipotong otomatis.
        filter_parts = []
        mix_inputs = ""
        for i, l in enumerate(layers):
            filter_parts.append(_layer_filter(i + 1, l))
            mix_inputs += f"[a{i+1}]"

        filter_parts.append(
            f"{mix_inputs}amix=inputs={n}:duration=first:normalize=0[aout]"
        )
        filter_complex = ";".join(filter_parts)

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[aout]",
        ]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "320k", output_path]

    async def run():
        t_start = time.time()

        def _desc(l):
            pan = l.get("pan", "center")
            suffix = "" if normalize_pan(pan) == 0.0 else f", pan {pan}"
            return f"{os.path.basename(l['path'])} ({l['volume']}%{suffix})"

        layer_desc = ", ".join([_desc(l) for l in layers])
        yield f"data: {json.dumps({'type': 'step_start', 'label': f'🔧 Mux video + {n} audio layer(s)'})}\n\n"
        yield f"data: {json.dumps({'log': f'Layers: {layer_desc}'})}\n\n"
        if use_copy:
            yield f"data: {json.dumps({'log': 'Audio: stream copy (tanpa re-encode) — codec AAC dipertahankan apa adanya'})}\n\n"

        async for chunk in run_ffmpeg_stream(cmd):
            yield chunk

        elapsed  = time.time() - t_start
        size_str = get_file_size_str(output_path) if os.path.exists(output_path) else "?"
        yield f"data: {json.dumps({'type': 'done', 'output': output_path, 'size': size_str, 'elapsed': fmt_duration(elapsed)})}\n\n"

    return StreamingResponse(run(), media_type="text/event-stream")
