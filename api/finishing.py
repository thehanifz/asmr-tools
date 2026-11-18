"""Finishing: intro card + fade in/out + thumbnail baku (standar channel).

Dijalankan setelah Merge, pada file hasil merge. Lihat core/finishing.py
untuk standar lengkapnya. Endpoint SSE mengikuti pola /api/merge.

Payload:
  input        : str  — video hasil merge (video+audio final)
  output       : str  — opsional; default <stem>_intro.mp4 di folder sama
  audio_path   : str  — opsional; file hasil Sound Layer untuk menyusun
                        baris elemen suara otomatis dari job-nya
  scene_title  : str  — baris 1 intro card + dasar judul thumbnail
  sound_line   : str  — opsional; kosong = otomatis dari job Sound Layer
  thumb_title  : str  — opsional; kosong = 2 kata pertama judul adegan
  make_thumbnail: bool — default true; thumbnail di <stem>_intro.jpg
"""
import asyncio
import json
import os
import shutil
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.utils import run_ffmpeg_stream, fmt_duration, get_file_size_str
from core import finishing as fin
from core.jobs import JOBS_DIR

router = APIRouter(tags=["finishing"])


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _streamable(cmd: list[str]) -> list[str]:
    """Buang '-v error' agar progres ffmpeg bisa distream ke UI."""
    out, skip = [], False
    for a in cmd:
        if skip:
            skip = False
            continue
        if a == "-v":
            skip = True
            continue
        out.append(a)
    return out


async def _run_step(cmd, label, p0, p1, target=0.0):
    async for chunk in run_ffmpeg_stream(_streamable(cmd), label, p0, p1, target):
        yield chunk


def _ok_file(path: str) -> bool:
    return os.path.exists(path) and os.path.getsize(path) > 0


@router.post("/finishing")
async def finishing_endpoint(request: Request):
    data = await request.json()
    src = data.get("input", "")
    if not src or not os.path.exists(src):
        return JSONResponse({"error": f"File tidak ditemukan: {src}"}, status_code=400)

    stem = os.path.splitext(src)[0]
    output = data.get("output") or f"{stem}_intro.mp4"
    thumb_out = os.path.splitext(output)[0] + ".jpg"
    make_thumb = data.get("make_thumbnail", True)

    scene_title = (data.get("scene_title") or "").strip() or fin.default_scene_title(src)
    thumb_title = (data.get("thumb_title") or "").strip() or fin.default_thumb_title(scene_title)

    # Baris elemen suara: manual bila diisi, selain itu otomatis dari job
    # Sound Layer yang menghasilkan audio_path.
    sound_intro = (data.get("sound_line") or "").strip()
    sound_thumb = ""
    auto_note = ""
    if not sound_intro and data.get("audio_path"):
        plan = fin.find_sound_layer_plan(data["audio_path"], JOBS_DIR)
        if plan:
            sound_intro, sound_thumb = fin.compose_sound_lines(plan)
            auto_note = " (otomatis dari job Sound Layer)"
    if sound_intro and not sound_thumb:
        sound_thumb = sound_intro.upper().replace(" IN SOME SEGMENTS", "")

    async def run():
        t_start = time.time()
        workdir = f"{stem}_finwork"
        try:
            info = fin.probe_video(src)
            dur = info["duration"]
            fps = info.get("fps", 24.0)
            sr = info.get("sample_rate", 44100)
            w, h = info["width"], info["height"]
            yield _sse({"type": "step_start",
                        "label": f"🎬 Finishing: intro card + fade ({w}x{h}, {fmt_duration(dur)})"})
            yield _sse({"log": f"Judul adegan: {scene_title}"})
            yield _sse({"log": f"Elemen suara: {sound_intro or '(kosong)'}{auto_note}"})

            os.makedirs(workdir, exist_ok=True)
            overlay = os.path.join(workdir, "intro_text.png")
            fin.make_overlay_png(overlay, w, h, scene_title, fin.MOOD_LINE, sound_intro)
            yield _sse({"log": "Intro card dibuat"})

            if dur >= 90:
                kfs_head = fin.keyframes_in(src, 10, 40)
                kfs_tail = fin.keyframes_in(src, max(0.0, dur - 60), 60)
                head_end, tail_start = fin.plan_segments(dur, kfs_head, kfs_tail)
                tail_len = dur - tail_start
                yield _sse({"log": f"Segmen: kepala 0–{head_end:.2f} dtk · "
                                   f"tengah salin · ekor {tail_len:.2f} dtk"})

                head = os.path.join(workdir, "head.mp4")
                yield _sse({"type": "step_start", "label": "✂️ Kepala: fade in + intro card"})
                async for c in _run_step(fin.head_command(src, overlay, head, head_end, fps, sr),
                                         "head", 5, 25, head_end):
                    yield c
                if not _ok_file(head):
                    raise RuntimeError("Render segmen kepala gagal")

                middle = os.path.join(workdir, "middle.mp4")
                yield _sse({"type": "step_start", "label": "📦 Tengah: stream copy"})
                async for c in _run_step(fin.middle_command(src, middle, head_end, tail_start),
                                         "middle", 25, 80, tail_start - head_end):
                    yield c
                if not _ok_file(middle):
                    raise RuntimeError("Salin segmen tengah gagal")

                tail = os.path.join(workdir, "tail.mp4")
                yield _sse({"type": "step_start", "label": "✂️ Ekor: fade out"})
                async for c in _run_step(fin.tail_command(src, tail, tail_start, tail_len, fps, sr),
                                         "tail", 80, 90, tail_len):
                    yield c
                if not _ok_file(tail):
                    raise RuntimeError("Render segmen ekor gagal")

                lst = os.path.join(workdir, "concat.txt")
                with open(lst, "w") as f:
                    f.write("file 'head.mp4'\nfile 'middle.mp4'\nfile 'tail.mp4'\n")
                yield _sse({"type": "step_start", "label": "🔗 Gabung segmen"})
                async for c in _run_step(
                        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                         "-c", "copy", output], "concat", 90, 97, dur):
                    yield c
            else:
                yield _sse({"type": "step_start", "label": "✂️ Video pendek: satu kali encode"})
                async for c in _run_step(fin.single_command(src, overlay, output, dur, fps, sr),
                                         "single", 5, 97, dur):
                    yield c

            if not _ok_file(output):
                raise RuntimeError("File hasil finishing tidak terbentuk")
            out_dur = fin.probe_video(output)["duration"]
            if abs(out_dur - dur) > 1.5:
                raise RuntimeError(
                    f"Durasi hasil menyimpang: {out_dur:.2f} vs sumber {dur:.2f} detik")

            thumb_msg = ""
            if make_thumb:
                frame = os.path.join(workdir, "frame.jpg")
                r = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-v", "error", "-ss", "13", "-i", output,
                    "-frames:v", "1", "-q:v", "3", frame,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await r.communicate()
                if _ok_file(frame):
                    fin.make_thumbnail(frame, thumb_out, fin.duration_badge(dur),
                                       sound_thumb, thumb_title)
                    thumb_msg = thumb_out
                    yield _sse({"log": f"Thumbnail dibuat: {os.path.basename(thumb_out)} "
                                       f"(badge {fin.duration_badge(dur)})"})

            shutil.rmtree(workdir, ignore_errors=True)
            elapsed = time.time() - t_start
            yield _sse({"type": "done", "output": output, "thumbnail": thumb_msg,
                        "size": get_file_size_str(output),
                        "elapsed": fmt_duration(elapsed)})
        except Exception as e:
            yield _sse({"log": f"❌ Finishing gagal: {e} (folder kerja dipertahankan: {workdir})"})
            yield _sse({"type": "error", "error": str(e)})

    return StreamingResponse(run(), media_type="text/event-stream")
