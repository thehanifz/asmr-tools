"""Job planners + runners: resumable execution for the four render paths.

Each path has a *planner* (validates the payload, computes segments/steps
and checkpoint paths — pure, no ffmpeg) and a *runner* (executes the
stored plan, skipping checkpoints that already exist and are valid).

Resume contract shared by all runners:
- A segment/step is marked done ONLY after its output file exists and
  its ffprobe duration matches the expected value (tolerance per path).
- On resume, done+valid segments are skipped; done+invalid segments are
  re-rendered; the final concat/encode step always re-runs (it is cheap
  and idempotent thanks to ``-y``).
- Checkpoints live in the job workdir (``~/workspace/asmr-service/jobs/<id>/``)
  and are kept on interrupt/error; they are removed only after a fully
  successful run.

Path designs (Nov 2026):
- Sound Layer: 60 s time windows (plus a split at the global fade start).
  Base loop phase is exact because each window is ``atrim``-ed from an
  ``aloop`` loop sized by the source's probed sample count (phase is
  automatic). ``-stream_loop`` must NOT be used for this: it eats
  128 samples at every Vorbis loop restart, so segments came out
  ~0.02 s short each and a 3 h render failed its final duration check
  by 3.4 s (fixed Nov 2026; segment validation tolerance is 0.01 s so
  pre-fix checkpoints are re-rendered on resume, not reused). Placements overlapping a
  window are trimmed AFTER their fades to the visible portion and
  delayed by (visible_start - t0). Volume factor comes from the FULL
  plan, never per-window. Segments are WAV; the final step concats them
  with the concat demuxer and encodes once (AAC 256k, or PCM for wav).
- Video Loop + Loop B+A: per-step checkpoints with deterministic names
  in the job workdir; a step is skipped when its output is valid.
- Audio Loop: chunks aligned to the tile grid (K whole tiles per chunk,
  K = round(60 / tile_dur)); each chunk is rendered with the SAME
  ``build_seamless_loop_filter`` call the single-pass path uses, with
  per-chunk duration/fades — so chunk joins are tile joins by
  construction. WAV intermediates + one final encode.
"""
import json
import math
import os
import subprocess
import time
from types import SimpleNamespace

from api.utils import fmt_duration, get_file_size_str, now_ts, safe_remove_file
from core.audio_filters import (
    build_seamless_loop_filter,
    effective_crossfade,
    loopable_samples,
    pan_filter,
)
from core.env import get_thread_flags
from core.jobs import JobContext, JobError, run_ffmpeg_tracked

DEFAULT_SEGMENT_SECONDS = 60.0


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def probe_duration(path: str) -> float | None:
    """Media duration in seconds via ffprobe; None on failure."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60,
        )
        return float(r.stdout.strip())
    except Exception:
        return None


def probe_sample_count(path: str) -> int | None:
    """Exact sample count of the first audio stream (ffprobe duration_ts).

    Needed for sample-exact looping with the ``aloop`` filter: looping an
    OGG/Vorbis input with ``-stream_loop`` instead loses 128 samples at
    every loop restart (decoder flush on seek-back), which made long
    Sound Layer renders finish short (181 segments x ~0.02 s = 3.4 s on
    a 3 h render — enough to fail the final duration check).
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=duration_ts",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60,
        )
        return int(r.stdout.strip())
    except Exception:
        return None


def validate_media(path: str, expect: float | None, tol: float) -> bool:
    """A checkpoint is usable when it exists, is non-empty, and (when an
    expected duration is known) its probed duration is within tolerance."""
    if not path or not os.path.exists(path):
        return False
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False
    if expect is None:
        return True
    d = probe_duration(path)
    return d is not None and abs(d - expect) <= tol


def probe_duration_decoded(path: str) -> float | None:
    """True duration by decoding the whole file (ground truth).

    Needed for containers whose header duration is a bitrate estimate:
    raw .aac (ADTS) overestimates by ~3% (measured: 3721.6 s reported
    for a 3599.8 s file). Slower (full decode); use only as a fallback.
    """
    import re

    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "info", "-i", path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=900,
        )
        times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", r.stderr)
        if not times:
            return None
        h, m, s = times[-1]
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return None


async def validate_final_output(path: str, expect: float, tol: float) -> bool:
    """Final-output validation: fast container probe first; when it
    disagrees with the expected duration, confirm with decode-based
    duration before failing (ADTS headers lie; decoded time does not)."""
    import asyncio

    if validate_media(path, expect, tol):
        return True
    decoded = await asyncio.to_thread(probe_duration_decoded, path)
    return decoded is not None and abs(decoded - expect) <= tol


def write_concat_list(paths: list, list_path: str) -> None:
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p}'\n")


# ---------------------------------------------------------------------------
# Sound Layer — time-window segments
# ---------------------------------------------------------------------------

def _sound_layer_windows(target_duration: float, xfade: float,
                         segment_seconds: float) -> list:
    """Window boundaries: multiples of segment_seconds, plus a split at
    the global fade start so no window ever starts mid-fade (the fade is
    then always a plain afade starting at/after the window start)."""
    bounds = [0.0]
    t = float(segment_seconds)
    while t < target_duration - 1e-9:
        bounds.append(round(t, 6))
        t += segment_seconds
    fade_start = target_duration - xfade
    if xfade > 0 and 1e-9 < fade_start < target_duration - 1e-9:
        if all(abs(b - fade_start) > 1e-6 for b in bounds):
            bounds.append(round(fade_start, 6))
    bounds = sorted(set(bounds))
    if bounds[-1] < target_duration - 1e-9:
        bounds.append(target_duration)
    windows = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    return [(t0, t1) for (t0, t1) in windows if t1 - t0 > 1e-6]


def _compute_volume_factor(plan, engine) -> float:
    """1/sqrt(max_overlap_count) from the FULL plan, using the engine's
    own ``_calculate_max_overlap_count`` (single source of truth — its
    event sweep has tie-order behaviour a reimplementation could miss).
    Must never be computed per-window: placements overlapping outside
    the window still affect the volume inside it."""
    max_overlap_count = engine._calculate_max_overlap_count(plan.placements)
    if max_overlap_count > 1:
        return 1.0 / math.sqrt(max_overlap_count)
    return 1.0


def plan_sound_layer(payload: dict, workdir: str) -> dict:
    """Validate payload + compute windows. Raises ValueError (→ HTTP 400)."""
    from core.sound_layer_engine import (
        LayerConfig,
        PlacementPlan,
        SoundLayerEngine,
    )

    plan_data = payload.get("plan")
    if not plan_data:
        raise ValueError("Placement plan is required")
    try:
        plan = PlacementPlan.from_json(json.dumps(plan_data))
    except Exception as e:
        raise ValueError(f"Placement plan tidak valid: {e}")
    if not plan.main_sounds:
        raise ValueError("Plan tidak punya main sound")

    output_format = str(payload.get("output_format", "aac")).lower()
    target_duration = float(payload.get("target_duration", 3600.0))
    loop_xfade = float(payload.get("loop_xfade", 2.0))
    segment_seconds = float(
        payload.get("segment_seconds", DEFAULT_SEGMENT_SECONDS)
        or DEFAULT_SEGMENT_SECONDS
    )
    if target_duration <= 0:
        raise ValueError("target_duration harus > 0")
    if segment_seconds <= 0:
        raise ValueError("segment_seconds harus > 0")

    output_path = payload.get("output_path", "")
    if not output_path:
        base = os.path.splitext(plan.main_sounds[0]["path"])[0]
        # Hasil render masuk folder media/audio — bukan folder sumber
        # suara (bisa jadi folder library, tempatnya file elemen) —
        # plus cap waktu supaya render berikutnya tidak menimpa.
        from datetime import datetime
        media_audio = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "media", "audio")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            media_audio,
            f"layer_{os.path.basename(base)}_{stamp}.{output_format}")
    else:
        output_path = os.path.splitext(output_path)[0] + "." + output_format
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Engine instance only to reuse its overlap-count method (same
    # construction as the legacy endpoint; the window builder below does
    # not use build_ffmpeg_command).
    engine = SoundLayerEngine(LayerConfig(
        main_sounds=plan.main_sounds,
        optional_sounds_folder=plan.optional_sounds_folder,
        output_path=output_path,
        target_duration=target_duration,
        loop_xfade=loop_xfade,
        output_format=output_format,
        silence_threshold=-50.0,
    ))

    xfade = min(loop_xfade, target_duration * 0.4)
    windows = _sound_layer_windows(target_duration, xfade, segment_seconds)
    return {
        "segments_total": len(windows),
        "windows": [[t0, t1] for t0, t1 in windows],
        "target_duration": target_duration,
        "loop_xfade": loop_xfade,
        "xfade": xfade,
        "output_format": output_format,
        "output_path": output_path,
        "volume_factor": _compute_volume_factor(plan, engine),
        "placements_count": len(plan.placements),
        # Exact decoded sample count per main sound, for sample-exact
        # aloop looping in the window builder (None = fall back to
        # -stream_loop for that sound).
        "main_sample_counts": [
            probe_sample_count(ms["path"]) for ms in plan.main_sounds
        ],
    }


def build_sound_layer_window_command(config, plan, t0: float, t1: float,
                                     volume_factor: float,
                                     segment_path: str, script_path: str) -> list:
    """One ffmpeg command rendering window [t0, t1) of the mix.

    Mirrors SoundLayerEngine.build_ffmpeg_command exactly, except:
    - main sounds are looped sample-exactly with ``aloop`` (sized by the
      probed sample count) and atrim-ed to the window from that loop
      (phase is automatic and continuous with neighbouring windows).
      ``-stream_loop`` is kept only as a fallback for sounds whose
      sample count could not be probed — it loses 128 samples per
      Vorbis loop restart and makes long renders finish short;
    - only placements overlapping the window are included, trimmed AFTER
      their fades to the visible portion and delayed to (visible_start - t0);
    - the global fade-out is applied only to windows reaching the fade
      region (windows are split at fade_start, so it is always a plain
      afade with st = fade_start - t0 >= 0).
    Output is always WAV (pcm_s24le); the final encode happens once,
    after concatenation.
    """
    target_dur = config.target_duration
    xfade = min(config.loop_xfade, target_dur * 0.4)
    fade_start = target_dur - xfade

    sample_counts = getattr(config, "main_sample_counts", None) or []
    cmd = ["ffmpeg", "-y"]
    for i, ms in enumerate(config.main_sounds):
        if i < len(sample_counts) and sample_counts[i]:
            cmd.extend(["-i", ms["path"]])
        else:
            cmd.extend(["-stream_loop", "-1", "-i", ms["path"]])

    overlapping = [p for p in plan.placements
                   if p.start_time < t1 and (p.start_time + p.duration) > t0]
    unique_sources = {}
    idx = len(config.main_sounds)
    for p in overlapping:
        if p.source_file not in unique_sources:
            unique_sources[p.source_file] = idx
            cmd.extend(["-i", p.source_file])
            idx += 1

    filter_parts = []
    delayed = []
    for i, p in enumerate(overlapping):
        input_idx = unique_sources[p.source_file]
        label = f"opt{i}"
        trim_end = p.trimmed_start + p.duration
        chain = (
            f"[{input_idx}:a]atrim=start={p.trimmed_start}:end={trim_end},"
            f"asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={p.fade_in},"
            f"afade=t=out:st={p.duration - p.fade_out}:d={p.fade_out}"
        )
        vol = (p.volume / 100.0) * volume_factor
        if vol != 1.0:
            chain += f",volume={vol:.3f}"
        pf = pan_filter(getattr(p, "pan", "center"))
        if pf:
            chain += f",{pf}"
        # Trim AFTER fades so the fade shape is preserved, then delay to
        # the visible portion's position inside the window.
        vis_start = max(p.start_time, t0)
        vis_end = min(p.start_time + p.duration, t1)
        skip = vis_start - p.start_time
        vis_len = vis_end - vis_start
        chain += (f",atrim=start={skip:.6f}:end={skip + vis_len:.6f},"
                  f"asetpts=PTS-STARTPTS[{label}]")
        filter_parts.append(chain)
        delay_ms = int((vis_start - t0) * 1000)
        filter_parts.append(f"[{label}]adelay={delay_ms}|{delay_ms}[{label}_delayed]")
        delayed.append(f"{label}_delayed")

    main_labels = []
    for i, ms in enumerate(config.main_sounds):
        label = f"main{i}"
        vol = ms.get("volume", 100) / 100.0
        chain = f"[{i}:a]"
        if i < len(sample_counts) and sample_counts[i]:
            chain += f"aloop=loop=-1:size={sample_counts[i]},"
        chain += (f"atrim=start={t0:.6f}:end={t1:.6f},"
                  f"asetpts=PTS-STARTPTS")
        if xfade > 0 and t1 > fade_start:
            chain += (f",afade=t=out:st={max(fade_start - t0, 0.0):.6f}:"
                      f"d={xfade:.6f}")
        if vol != 1.0:
            chain += f",volume={vol}"
        pf = pan_filter(ms.get("pan", "center"))
        if pf:
            chain += f",{pf}"
        chain += f"[{label}]"
        filter_parts.append(chain)
        main_labels.append(label)

    inputs = main_labels + delayed
    amix = "".join(f"[{lbl}]" for lbl in inputs)
    if len(inputs) > 1:
        amix += f"amix=inputs={len(inputs)}:duration=first:normalize=0[aout]"
    else:
        amix += "acopy[aout]"
    filter_parts.append(amix)

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(";".join(filter_parts))

    cmd.extend(get_thread_flags())
    cmd.extend(["-filter_complex_script", script_path,
                "-map", "[aout]", "-c:a", "pcm_s24le", segment_path])
    return cmd


async def run_sound_layer(ctx: JobContext, record: dict) -> str:
    from core.sound_layer_engine import PlacementPlan

    payload = record["payload"]
    plan = PlacementPlan.from_json(json.dumps(payload["plan"]))
    info = record["plan"]
    config = SimpleNamespace(
        main_sounds=plan.main_sounds,
        target_duration=info["target_duration"],
        loop_xfade=info["loop_xfade"],
        main_sample_counts=info.get("main_sample_counts") or [],
    )
    output_path = info["output_path"]
    output_format = info["output_format"]
    windows = info["windows"]
    total = len(windows)

    ctx.emit({"status": "start", "ts": now_ts(),
              "label": "Sound Layer Render", "elapsed": 0})
    ctx.log(f"Rendering {len(plan.placements)} placements... ({total} segmen)")

    done = set(ctx.segments_done)
    for i, (t0, t1) in enumerate(windows):
        t0, t1 = float(t0), float(t1)
        seg_path = os.path.join(ctx.workdir, f"seg_{i:03d}.wav")
        label = f"Segmen {i + 1}/{total} ({t0:.0f}–{t1:.0f} dtk)"
        # Tight tolerance on purpose: segments are sample-exact since
        # the aloop fix, and a loose one would happily reuse pre-fix
        # segments that are each ~0.02 s short (which adds up past the
        # final check on long renders).
        if i in done and validate_media(seg_path, t1 - t0, tol=0.01):
            ctx.log(f"⏭ {label} sudah ada, dilewati.")
            ctx.emit({"type": "step_done", "step": i + 1, "total": total,
                      "label": label, "elapsed": "0s",
                      "output_size": get_file_size_str(seg_path)})
            continue
        script_path = os.path.join(ctx.workdir, f"fc_seg_{i:03d}.txt")
        cmd = build_sound_layer_window_command(
            config, plan, t0, t1, info["volume_factor"], seg_path, script_path)
        ctx.emit({"type": "step_start", "step": i + 1, "total": total,
                  "label": label})
        p_start = int(i * 95 / total)
        p_end = int((i + 1) * 95 / total)
        rc = await run_ffmpeg_tracked(
            ctx, cmd, target_duration=t1 - t0,
            progress_start=p_start, progress_end=p_end)
        if rc != 0:
            raise JobError(f"ffmpeg gagal pada {label} (kode {rc})")
        if not validate_media(seg_path, t1 - t0, tol=0.01):
            raise JobError(f"{label} tidak valid (durasi tidak cocok)")
        ctx.mark_segment_done(i)
        ctx.emit({"type": "step_done", "step": i + 1, "total": total,
                  "label": label,
                  "output_size": get_file_size_str(seg_path)})

    # Final step: concat WAV segments + a single encode to the target format
    # (same codec choice as SoundLayerEngine.build_ffmpeg_command).
    list_path = os.path.join(ctx.workdir, "concat_list.txt")
    seg_paths = [os.path.join(ctx.workdir, f"seg_{i:03d}.wav")
                 for i in range(total)]
    write_concat_list(seg_paths, list_path)
    if output_format == "wav":
        codec_args = ["-c:a", "pcm_s24le"]
    else:
        codec_args = ["-c:a", "aac", "-b:a", "256k"]
    ctx.emit({"type": "step_start", "step": total + 1, "total": total + 1,
              "label": "Gabung segmen → output akhir"})
    cmd = ["ffmpeg", "-y", *get_thread_flags(),
           "-f", "concat", "-safe", "0", "-i", list_path,
           *codec_args, output_path]
    rc = await run_ffmpeg_tracked(
        ctx, cmd, target_duration=info["target_duration"],
        progress_start=95, progress_end=100)
    if rc != 0:
        raise JobError(f"ffmpeg gagal pada tahap gabung segmen (kode {rc})")
    if not await validate_final_output(output_path, info["target_duration"], tol=1.5):
        raise JobError("Output akhir tidak valid (durasi tidak cocok)")

    for p in seg_paths:
        safe_remove_file(p)
    ctx.log(f"✓ Sound Layer selesai: {output_path} ({get_file_size_str(output_path)})")
    return output_path


# ---------------------------------------------------------------------------
# Shared step executor (video pipeline + loop B+A)
# ---------------------------------------------------------------------------

async def _run_steps(ctx: JobContext, steps: list) -> None:
    """Execute plan steps, skipping checkpoints that already exist and
    are valid. Emits the legacy pipeline_start/step_start/step_done
    event shapes."""
    from core.env import USE_NVENC

    total = len(steps)
    encoder_name = "h264_nvenc ⚡" if USE_NVENC else "libx264 🖥"
    ctx.log(f"Encoder: {encoder_name}")
    ctx.emit({"type": "pipeline_start", "total_steps": total})
    done = set(ctx.segments_done)
    for i, step in enumerate(steps):
        cmd, label, out_file = step["cmd"], step["label"], step["out"]
        expect, tol = step.get("expect"), step.get("tol", 3.0)
        if i in done and validate_media(out_file, expect, tol):
            ctx.log(f"⏭ Langkah {i + 1}/{total} sudah ada, dilewati: {label}")
            ctx.emit({"type": "step_done", "step": i + 1, "label": label,
                      "elapsed": "0s",
                      "output_size": get_file_size_str(out_file)
                      if os.path.exists(out_file) else "?"})
            continue
        t_start = time.time()
        ctx.emit({"type": "step_start", "step": i + 1, "total": total,
                  "label": label})
        p_start = int(i * 100 / total)
        p_end = int((i + 1) * 100 / total)
        rc = await run_ffmpeg_tracked(
            ctx, cmd, target_duration=float(step.get("target") or 0),
            progress_start=p_start, progress_end=p_end)
        if rc != 0:
            ctx.emit({"type": "step_error", "step": i + 1, "label": label})
            raise JobError(f"ffmpeg gagal pada langkah {i + 1}/{total} "
                           f"({label}, kode {rc})")
        if not validate_media(out_file, expect, tol):
            ctx.emit({"type": "step_error", "step": i + 1, "label": label})
            raise JobError(f"Langkah {i + 1}/{total} menghasilkan file "
                           f"tidak valid: {label}")
        ctx.mark_segment_done(i)
        elapsed = time.time() - t_start
        ctx.emit({"type": "step_done", "step": i + 1, "label": label,
                  "elapsed": fmt_duration(elapsed),
                  "output_size": get_file_size_str(out_file)
                  if os.path.exists(out_file) else "?"})


# ---------------------------------------------------------------------------
# Video Loop pipeline — per-step checkpoints
# ---------------------------------------------------------------------------

def plan_video_pipeline(payload: dict, workdir: str) -> dict:
    """Replicates the step construction of the legacy /video/pipeline
    endpoint, with checkpoint paths inside the job workdir."""
    from api.video import cmd_fade_plan, cmd_loop, cmd_loop_xfade
    from core.video_filters import fade_segment_lengths

    input_path = payload.get("input", "")
    if not input_path or not os.path.exists(input_path):
        raise ValueError("Input file tidak ditemukan")
    basename = os.path.splitext(os.path.basename(input_path))[0]
    final_output = payload.get("output", "")
    if not final_output:
        final_output = os.path.join(os.path.dirname(input_path),
                                    f"loop_{basename}.mp4")

    duration = int(payload.get("duration", 3600))
    video_dur = float(payload.get("video_duration", 8))
    crf = int(payload.get("crf", 23))
    keep_audio = bool(payload.get("keep_audio", False))
    xfade_enabled = bool(payload.get("xfade_enabled", False))
    xfade_duration = float(payload.get("xfade_duration", 1.0))
    fade_in_enabled = bool(payload.get("fade_in_enabled", False))
    fade_out_enabled = bool(payload.get("fade_out_enabled", False))
    fade_in_dur = float(payload.get("fade_in_duration", 3.0))
    fade_out_dur = float(payload.get("fade_out_duration", 3.0))
    do_fade = fade_in_enabled or fade_out_enabled

    looped = os.path.join(workdir, "loop.mp4")
    steps = []
    cleanup = []
    fade_ctx = {}

    if xfade_enabled:
        xfade_out = final_output if not do_fade else looped
        if do_fade:
            cleanup.append(looped)
        xfade_steps, xfade_cleanup = cmd_loop_xfade(
            input_path, xfade_out, duration, video_dur, xfade_duration,
            crf=crf, workdir=workdir)
        vd = max(float(video_dur), 0.5)
        xd = max(0.1, min(float(xfade_duration), vd * 0.45))
        expects = [vd - xd, float(duration)]
        for (cmd, label, out_file), expect in zip(xfade_steps, expects):
            steps.append({"cmd": cmd, "label": label, "out": out_file,
                          "expect": expect, "tol": 3.0, "target": expect})
        cleanup.extend(xfade_cleanup)
        tile_len = video_dur - max(0.1, min(xfade_duration, video_dur * 0.45))
    else:
        loop_out = final_output if not do_fade else looped
        if do_fade:
            cleanup.append(looped)
        steps.append({
            "cmd": cmd_loop(input_path, loop_out, duration, video_dur, keep_audio),
            "label": f"🔁 Loop → {fmt_duration(duration)} "
                     f"{'(+ audio)' if keep_audio else '(no audio)'}",
            "out": loop_out, "expect": float(duration), "tol": 3.0,
            "target": float(duration),
        })
        tile_len = video_dur

    if do_fade:
        fi = fade_in_dur if fade_in_enabled else 0.0
        fo = fade_out_dur if fade_out_enabled else 0.0
        f_steps, f_cleanup, f_segment = cmd_fade_plan(
            looped, final_output, duration, tile_len, fi, fo, crf,
            workdir=workdir)
        if f_segment:
            lengths = fade_segment_lengths(duration, tile_len, fi, fo)
            if lengths is not None:
                head_len, mid_len, tail_len = lengths
                expects = []
                if fi > 0:
                    expects.append(head_len)
                expects.append(mid_len)
                if fo > 0:
                    expects.append(tail_len)
                expects.append(float(duration))
            else:
                expects = [float(duration)] * len(f_steps)
            for (cmd, label, out_file), expect in zip(f_steps, expects):
                steps.append({"cmd": cmd, "label": label, "out": out_file,
                              "expect": expect, "tol": 3.0, "target": expect})
            fade_ctx = {"fi": fi, "fo": fo}
        else:
            for cmd, label, out_file in f_steps:
                steps.append({"cmd": cmd, "label": label, "out": out_file,
                              "expect": float(duration), "tol": 3.0,
                              "target": float(duration)})
        cleanup.extend(f_cleanup)

    return {
        "segments_total": len(steps),
        "steps": steps,
        "cleanup": cleanup,
        "fade_ctx": fade_ctx,
        "looped": looped,
        "duration": duration,
        "output_path": final_output,
    }


async def run_video_pipeline(ctx: JobContext, record: dict) -> str:
    from api.video import cmd_fade_video

    info = record["plan"]
    start = time.time()
    await _run_steps(ctx, info["steps"])
    final_output = info["output_path"]
    duration = info["duration"]
    fade_ctx = info.get("fade_ctx") or {}
    if fade_ctx:
        # Same precision guard as the legacy endpoint: if the segmented
        # fade produced a wrong duration, fall back to a full re-encode.
        actual = probe_duration(final_output)
        if actual is None or abs(actual - duration) > 3:
            ctx.log("⚠️ Fade segmen tidak presisi — fallback ke fade penuh (re-encode)")
            legacy_cmd = cmd_fade_video(info["looped"], final_output,
                                        duration, fade_ctx["fi"], fade_ctx["fo"])
            rc = await run_ffmpeg_tracked(
                ctx, legacy_cmd, target_duration=float(duration),
                progress_start=90, progress_end=100)
            if rc != 0:
                ctx.emit({"type": "step_error", "step": len(info["steps"]),
                          "label": "Fade fallback"})
                raise JobError(f"ffmpeg gagal pada fade fallback (kode {rc})")
    for f in info.get("cleanup", []):
        safe_remove_file(f)
    total_elapsed = time.time() - start
    final_size = (get_file_size_str(final_output)
                  if os.path.exists(final_output) else "?")
    ctx.emit({"status": "all_done", "output": final_output,
              "final_size": final_size,
              "total_elapsed": fmt_duration(total_elapsed)})
    return final_output


# ---------------------------------------------------------------------------
# Loop B+A — per-step checkpoints (crossfade = one job segment)
# ---------------------------------------------------------------------------

def plan_loop_ba(payload: dict, workdir: str) -> dict:
    """Replicates the command construction of the legacy /loop-ba/render
    endpoint, with deterministic checkpoint paths in the job workdir
    (the legacy code used timestamped _tmp_ names next to the input)."""
    from api.concat import probe_single_video
    from core.env import get_thread_flags, video_encoder_flags

    input_path = payload.get("input_path", "").strip()
    if not input_path or not os.path.exists(input_path):
        raise ValueError("File input tidak ditemukan")
    info = probe_single_video(input_path)
    if "error" in info:
        raise ValueError(f"Gagal membaca info video: {info['error']}")
    duration = info["duration"]
    if duration <= 0:
        raise ValueError("Durasi video tidak valid (0 atau negatif)")

    transition_type = payload.get("transition_type", "hard_cut")
    transition_duration = float(payload.get("transition_duration", 1.0))
    output_path = payload.get("output_path", "").strip()
    midpoint = duration / 2.0
    output_dir = os.path.dirname(os.path.abspath(input_path))
    if not output_path:
        ts_str = time.strftime("%Y%m%d_%H%M%S")
        basename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"loop_ba_{ts_str}_{basename}.mp4")
    b_duration = duration - midpoint

    if transition_type == "crossfade":
        if transition_duration > b_duration:
            raise ValueError(
                f"Durasi crossfade ({transition_duration}s) tidak boleh melebihi "
                f"durasi segmen B ({b_duration:.2f}s)")
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
            output_path,
        ]
        label = (f"🔄 Loop B+A (Crossfade {transition_duration}s) → "
                 f"{fmt_duration(final_duration)}")
        steps = [{"cmd": cmd, "label": label, "out": output_path,
                  "expect": final_duration, "tol": 1.0,
                  "target": final_duration}]
        cleanup = []
    else:
        seg_a_path = os.path.join(workdir, "seg_a.mp4")
        seg_b_path = os.path.join(workdir, "seg_b.mp4")
        list_txt_path = os.path.join(workdir, "list_ba.txt")
        cmd_split_a = [
            "ffmpeg", "-y", *get_thread_flags(),
            "-ss", "0", "-i", input_path,
            "-t", f"{midpoint:.6f}",
            "-an", "-c:v", "copy",
            seg_a_path,
        ]
        cmd_split_b = [
            "ffmpeg", "-y", *get_thread_flags(),
            "-ss", f"{midpoint:.6f}", "-i", input_path,
            "-an", "-c:v", "copy",
            seg_b_path,
        ]
        with open(list_txt_path, "w", encoding="utf-8") as f:
            f.write(f"file '{seg_b_path.replace(chr(92), '/')}'\n")
            f.write(f"file '{seg_a_path.replace(chr(92), '/')}'\n")
        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_txt_path,
            "-c", "copy",
            output_path,
        ]
        steps = [
            {"cmd": cmd_split_a,
             "label": f"✂️ Split Segmen A (0.0s s/d {midpoint:.2f}s)",
             "out": seg_a_path, "expect": midpoint, "tol": 1.0,
             "target": midpoint},
            {"cmd": cmd_split_b,
             "label": f"✂️ Split Segmen B ({midpoint:.2f}s s/d {duration:.2f}s)",
             "out": seg_b_path, "expect": b_duration, "tol": 1.0,
             "target": b_duration},
            {"cmd": cmd_concat,
             "label": "🎬 Menggabungkan Segmen B + A (Hard Cut)",
             "out": output_path, "expect": duration, "tol": 2.0,
             "target": duration},
        ]
        cleanup = [seg_a_path, seg_b_path, list_txt_path]

    return {
        "segments_total": len(steps),
        "steps": steps,
        "cleanup": cleanup,
        "output_path": output_path,
        "duration": duration,
        "transition_type": transition_type,
    }


async def run_loop_ba(ctx: JobContext, record: dict) -> str:
    info = record["plan"]
    await _run_steps(ctx, info["steps"])
    for f in info.get("cleanup", []):
        safe_remove_file(f)
    output_path = info["output_path"]
    if os.path.exists(output_path):
        ctx.emit({"status": "all_done", "output": output_path,
                  "final_size": get_file_size_str(output_path)})
    return output_path


# ---------------------------------------------------------------------------
# Audio Loop — tile-aligned chunks
# ---------------------------------------------------------------------------

async def plan_audio_loop(payload: dict, workdir: str) -> dict:
    """Validate + compute chunks. Raises ValueError (→ HTTP 400).

    Seamless mode: chunk boundaries sit on the tile grid (K whole tiles
    per chunk, K = round(chunk_seconds / tile_dur)), so every chunk
    starts at tile phase 0 and chunk joins are tile joins.
    Trim mode (source >= target): plain atrim windows.
    """
    from api.audio import CODEC_MAP, get_audio_stream_info

    input_path = payload.get("input", "")
    if not input_path or not os.path.exists(input_path):
        raise ValueError(f"Input file does not exist: {input_path}")
    duration = int(payload.get("duration", 3600))
    xfade = float(payload.get("xfade", 2.0))
    fmt = str(payload.get("format", "aac")).lower()
    if fmt not in CODEC_MAP:
        fmt = "aac"
    fade_in = float(payload.get("fade_in", 0) or 0)
    fade_out = payload.get("fade_out", None)
    fade_out = None if fade_out is None else float(fade_out)

    output_path = payload.get("output", "")
    if not output_path:
        output_dir = os.path.dirname(input_path)
        basename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"loop_{basename}{CODEC_MAP[fmt]['ext']}")
    else:
        output_path = os.path.splitext(output_path)[0] + CODEC_MAP[fmt]["ext"]
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    info = await get_audio_stream_info(input_path)
    src_dur = info["duration"]
    if src_dur <= 0:
        raise ValueError("Gagal baca durasi file input")
    if duration <= 0:
        raise ValueError("Durasi target harus lebih dari 0")
    chunk_seconds = float(
        payload.get("chunk_seconds", DEFAULT_SEGMENT_SECONDS)
        or DEFAULT_SEGMENT_SECONDS)
    if chunk_seconds <= 0:
        raise ValueError("chunk_seconds harus > 0")

    base = {
        "src_dur": src_dur,
        "sample_rate": info["sample_rate"],
        "total_samples": info["total_samples"],
        "duration": duration,
        "fmt": fmt,
        "fade_in": fade_in,
        "fade_out": fade_out,
        "output_path": output_path,
        "input_path": input_path,
    }

    if src_dur >= duration:
        chunks = []
        t = 0.0
        while t < duration - 1e-9:
            ln = min(chunk_seconds, duration - t)
            chunks.append({"t0": round(t, 6), "length": round(ln, 6)})
            t += ln
        base.update({"mode": "trim", "chunks": chunks,
                     "segments_total": len(chunks),
                     "tile_dur": src_dur, "xfade_eff": xfade})
        return base

    xfade_eff = effective_crossfade(src_dur, xfade)
    if xfade_eff <= 0.05 or info["total_samples"] <= 0 or info["sample_rate"] <= 0:
        tile_dur = src_dur
        tile_samples = max(1, info["total_samples"])
    else:
        tile_samples = loopable_samples(info["total_samples"], info["sample_rate"],
                                        xfade_eff)
        tile_dur = tile_samples / info["sample_rate"]
    tiles_per_chunk = max(1, round(chunk_seconds / tile_dur)) if tile_dur > 0 else 1
    chunk_len = tiles_per_chunk * tile_dur
    n_chunks = max(1, math.ceil(duration / chunk_len))
    chunks = []
    for k in range(n_chunks):
        t0 = k * chunk_len
        ln = min(chunk_len, duration - t0)
        chunks.append({"t0": round(t0, 6), "length": round(ln, 6)})
    base.update({
        "mode": "seamless",
        "chunks": chunks,
        "segments_total": len(chunks),
        "tile_dur": tile_dur,
        "tile_samples": tile_samples,
        "tiles_per_chunk": tiles_per_chunk,
        "xfade_eff": xfade_eff,
    })
    return base


async def run_audio_loop(ctx: JobContext, record: dict) -> str:
    from api.audio import CODEC_MAP

    info = record["plan"]
    input_path = info["input_path"]
    output_path = info["output_path"]
    duration = info["duration"]
    fmt = info["fmt"]
    chunks = info["chunks"]
    total = len(chunks)

    ctx.emit({"status": "start", "ts": now_ts(),
              "label": f"Audio Loop → {fmt.upper()}", "elapsed": 0})
    ctx.log(f"Durasi sumber: {info['src_dur']:.2f}s, target: {duration}s, "
            f"xfade: {info['xfade_eff']:.2f}s ({total} chunk)")
    if info["mode"] == "seamless":
        ctx.log(f"Seamless loop: crossfade efektif {info['xfade_eff']:.2f}s, "
                f"tile {info['tile_dur']:.3f}s ({info['total_samples']} sampel "
                f"@ {info['sample_rate']} Hz)")

    done = set(ctx.segments_done)
    sr = info["sample_rate"]
    tile_samples = info.get("tile_samples", 0)
    tiles_per_chunk = info.get("tiles_per_chunk", 1)
    total_target_samples = round(duration * sr) if sr > 0 else 0
    for i, ch in enumerate(chunks):
        chunk_path = os.path.join(ctx.workdir, f"chunk_{i:03d}.wav")
        label = (f"Chunk {i + 1}/{total} "
                 f"({ch['t0']:.0f}–{ch['t0'] + ch['length']:.0f} dtk)")
        if i in done and validate_media(chunk_path, ch["length"], tol=0.5):
            ctx.log(f"⏭ {label} sudah ada, dilewati.")
            continue
        is_first = i == 0
        is_last = i == total - 1
        if info["mode"] == "seamless":
            # Same filter builder as the single-pass path, with per-chunk
            # duration/fades: fade-in only on the first chunk, fade-out
            # only on the last (None = default to xfade, as before).
            chunk_fade_in = info["fade_in"] if is_first else 0.0
            chunk_fade_out = info["fade_out"] if is_last else 0.0
            filter_complex, _ = build_seamless_loop_filter(
                info["src_dur"], info["total_samples"], info["sample_rate"],
                ch["length"], info["xfade_eff"],
                fade_in=chunk_fade_in, fade_out=chunk_fade_out)
            # Sample-exact trim: the tile construction's .3f-rounded
            # atrims make each rendered tile ~18 samples longer than
            # tile_samples; aloop discards the excess in single-pass
            # mode, but chunk renders keep it, which would shift every
            # join. Trimming to the exact sample count keeps chunk joins
            # phase-identical to tile joins.
            out_label = "out"
            exact = None
            if sr > 0 and tile_samples > 0:
                if is_last and total_target_samples > 0:
                    exact = total_target_samples - i * tiles_per_chunk * tile_samples
                else:
                    exact = tiles_per_chunk * tile_samples
                if exact is not None and exact > 0:
                    filter_complex += (f";[out]atrim=end_sample={exact},"
                                       f"asetpts=PTS-STARTPTS[out_trim]")
                    out_label = "out_trim"
            cmd = ["ffmpeg", "-y", "-nostdin", *get_thread_flags(),
                   "-i", input_path,
                   "-filter_complex", filter_complex, "-map", f"[{out_label}]",
                   "-c:a", "pcm_s24le", chunk_path]
        else:
            filter_str = (f"atrim=start={ch['t0']:.6f}:duration={ch['length']:.6f},"
                          f"asetpts=PTS-STARTPTS")
            if is_first and info["fade_in"] and info["fade_in"] > 0:
                filter_str += f",afade=t=in:d={info['fade_in']:.3f}:curve=tri"
            eff_out = info["xfade_eff"] if info["fade_out"] is None else info["fade_out"]
            if is_last and eff_out and eff_out > 0 and duration > eff_out:
                filter_str += (f",afade=t=out:st={duration - eff_out - ch['t0']:.3f}:"
                               f"d={eff_out:.3f}:curve=tri")
            if sr > 0:
                exact = round(ch["length"] * sr)
                if exact > 0:
                    filter_str += (f",atrim=end_sample={exact},"
                                   f"asetpts=PTS-STARTPTS")
            cmd = ["ffmpeg", "-y", "-nostdin", *get_thread_flags(),
                   "-i", input_path,
                   "-af", filter_str, "-c:a", "pcm_s24le", chunk_path]
        ctx.emit({"type": "step_start", "step": i + 1, "total": total,
                  "label": label})
        p_start = int(i * 95 / total)
        p_end = int((i + 1) * 95 / total)
        rc = await run_ffmpeg_tracked(
            ctx, cmd, target_duration=ch["length"],
            progress_start=p_start, progress_end=p_end)
        if rc != 0:
            raise JobError(f"ffmpeg gagal pada {label} (kode {rc})")
        if not validate_media(chunk_path, ch["length"], tol=0.5):
            raise JobError(f"{label} tidak valid (durasi tidak cocok)")
        ctx.mark_segment_done(i)
        ctx.emit({"type": "step_done", "step": i + 1, "total": total,
                  "label": label,
                  "output_size": get_file_size_str(chunk_path)})

    list_path = os.path.join(ctx.workdir, "concat_list.txt")
    chunk_paths = [os.path.join(ctx.workdir, f"chunk_{i:03d}.wav")
                   for i in range(total)]
    write_concat_list(chunk_paths, list_path)
    codec_args = CODEC_MAP[fmt]["args"]
    ctx.emit({"type": "step_start", "step": total + 1, "total": total + 1,
              "label": "Gabung chunk → output akhir"})
    cmd = ["ffmpeg", "-y", *get_thread_flags(),
           "-f", "concat", "-safe", "0", "-i", list_path,
           *codec_args, output_path]
    rc = await run_ffmpeg_tracked(
        ctx, cmd, target_duration=float(duration),
        progress_start=95, progress_end=100)
    if rc != 0:
        raise JobError(f"ffmpeg gagal pada tahap gabung chunk (kode {rc})")
    if not await validate_final_output(output_path, float(duration), tol=1.0):
        raise JobError("Output akhir tidak valid (durasi tidak cocok)")
    for p in chunk_paths:
        safe_remove_file(p)
    ctx.log(f"✓ Audio Loop selesai: {output_path} ({get_file_size_str(output_path)})")
    return output_path


# ---------------------------------------------------------------------------
# Runner registry
# ---------------------------------------------------------------------------

def register_all_runners() -> None:
    from core.jobs import register_runner
    register_runner("sound-layer", run_sound_layer)
    register_runner("video-pipeline", run_video_pipeline)
    register_runner("loop-ba", run_loop_ba)
    register_runner("audio-loop", run_audio_loop)
