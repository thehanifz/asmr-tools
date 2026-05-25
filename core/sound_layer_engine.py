"""
Sound Layer Engine - 2-Pass Optimized Render

Pass 1 : Build optional layer  (all placements → temp PCM wav)
Pass 2 : Loop main sounds + mix with optional layer → final output

Optimisasi:
- Setiap unique source di-decode sekali ke PCM temp sebelum build filter
- Optional placements di-batch maks 32 per amix group (tree mixing)
- Pass-1 output adalah PCM s16le 44100Hz (lossless intermediate)
- Pass-2 hanya mix 3 stream (main_A, main_B, opt_layer) → sangat ringan
- Thread flags dari env.py diterapkan di setiap subprocess
"""

from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict, Optional, Any
import json
import os
import math
import asyncio
import tempfile
import sys

# ─── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class Placement:
    source_file: str
    start_time: float
    duration: float
    fade_in: float
    fade_out: float
    trimmed_start: float = 0.0
    trimmed_end: float = 0.0
    volume: int = 80


@dataclass
class PlacementPlan:
    version: str = "1.0"
    main_sounds: List[Dict[str, Any]] = field(default_factory=list)
    optional_sounds_folder: str = ""
    placements: List[Placement] = field(default_factory=list)
    target_duration: float = 3600.0

    def to_json(self) -> str:
        data = {
            "version": self.version,
            "main_sounds": self.main_sounds,
            "optional_sounds_folder": self.optional_sounds_folder,
            "target_duration": self.target_duration,
            "placements": [asdict(p) for p in self.placements],
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PlacementPlan":
        try:
            data = json.loads(json_str)
            placements = [Placement(**p) for p in data.get("placements", [])]
            return cls(
                version=data.get("version", "1.0"),
                main_sounds=data.get("main_sounds", []),
                optional_sounds_folder=data.get("optional_sounds_folder", ""),
                target_duration=data.get("target_duration", 3600.0),
                placements=placements,
            )
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            raise ValueError(f"Invalid PlacementPlan JSON: {e}")


@dataclass
class LayerConfig:
    main_sounds: List[Dict[str, Any]]
    optional_sounds_folder: str
    output_path: str
    target_duration: float = 3600.0
    loop_xfade: float = 2.0
    output_format: str = "aac"
    occurrence_count: int = 10
    time_window_start: float = 0.0
    time_window_end: float = 0.0
    min_duration: float = 3.0
    max_duration: float = 10.0
    min_gap: float = 2.0
    overlap_mode: str = "none"
    fade_duration: float = 0.5
    silence_threshold: float = -50.0


# ─── Helpers ──────────────────────────────────────────────────────────────────

AMIX_BATCH = 32          # maks input per satu amix node
PCM_SR     = 44100       # sample-rate PCM intermediate
PCM_FMT    = "s16le"     # format PCM intermediate
PCM_CH     = 2           # channels


def _pcm_args() -> list:
    """Argumen codec untuk PCM intermediate."""
    return ["-ar", str(PCM_SR), "-ac", str(PCM_CH), "-c:a", f"pcm_{PCM_FMT}", "-f", PCM_FMT]


def _escape_filter_path(path: str) -> str:
    path = path.replace("\\", "/")
    if len(path) >= 2 and path[1] == ":":
        path = path[0] + "\\:" + path[2:]
    for ch in ["'", "[", "]", ",", ";"]:
        path = path.replace(ch, f"\\{ch}")
    return path


def _batch_amix(labels: List[str]) -> Tuple[List[str], str]:
    """
    Buat tree-style amix dari sejumlah label.
    Return (filter_parts, final_label).
    """
    if not labels:
        raise ValueError("No labels to mix")
    if len(labels) == 1:
        return [], labels[0]

    parts: List[str] = []
    current = labels[:]
    gen = 0

    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), AMIX_BATCH):
            batch = current[i : i + AMIX_BATCH]
            if len(batch) == 1:
                next_level.append(batch[0])
                continue
            out_label = f"batch_{gen}_{i // AMIX_BATCH}"
            inp = "".join(f"[{l}]" for l in batch)
            parts.append(
                f"{inp}amix=inputs={len(batch)}:duration=first:normalize=0[{out_label}]"
            )
            next_level.append(out_label)
        current = next_level
        gen += 1

    return parts, current[0]


# ─── Engine ───────────────────────────────────────────────────────────────────

class SoundLayerEngine:
    """
    Core engine – 2-pass optimised render.
    """

    def __init__(self, config: LayerConfig):
        self.config = config
        self.optional_sound_files: List[str] = []
        self.main_duration: float = 0.0
        self.silence_cache: Dict[str, Tuple[float, float]] = {}
        self._pcm_cache: Dict[str, str] = {}   # source_path → temp pcm path
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None

    # ── Temp dir management ──────────────────────────────────────────────────

    def _get_temp_dir(self) -> str:
        if self._temp_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="asmr_sl_")
        return self._temp_dir.name

    def cleanup(self):
        """Hapus semua temp file. Panggil setelah render selesai."""
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass
            self._temp_dir = None
        self._pcm_cache.clear()

    # ── FFprobe / silence helpers ────────────────────────────────────────────

    async def get_audio_duration(self, path: str) -> float:
        if not os.path.exists(path):
            raise ValueError(f"File tidak ada: {path}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            s = stdout.decode().strip()
            return max(0.0, float(s)) if s else 0.0
        except Exception as e:
            print(f"[duration] error {path}: {e}", file=sys.stderr)
            return 0.0

    async def detect_silence(self, path: str) -> Tuple[float, float]:
        import re
        duration = await self.get_audio_duration(path)
        if duration == 0.0:
            return (0.0, 0.0)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-i", path,
                "-af", f"silencedetect=n={self.config.silence_threshold}dB:d=0.1",
                "-f", "null", "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            text = stderr.decode()
            starts = [float(m.group(1)) for m in re.finditer(r"silence_start:\s*([\d.]+)", text)]
            ends   = [float(m.group(1)) for m in re.finditer(r"silence_end:\s*([\d.]+)",   text)]
            s_trim = ends[0]   if (starts and ends and starts[0] < 2.0) else 0.0
            e_trim = (duration - starts[-1]) if (ends and ends[-1] > duration - 2.0 and len(starts) >= len(ends)) else 0.0
            return (s_trim, e_trim)
        except Exception as e:
            print(f"[silence] error {path}: {e}", file=sys.stderr)
            return (0.0, 0.0)

    async def detect_silence_cached(self, path: str) -> Tuple[float, float]:
        if not os.path.exists(path):
            raise ValueError(f"File tidak ada: {path}")
        mtime = os.path.getmtime(path)
        key = f"{path}:{mtime}"
        if key not in self.silence_cache:
            self.silence_cache[key] = await self.detect_silence(path)
        return self.silence_cache[key]

    # ── Pre-decode unique sources ke PCM ────────────────────────────────────

    async def _predecode_source(self, path: str) -> str:
        """
        Decode satu file audio ke PCM WAV temp.
        Return path temp PCM.
        """
        if path in self._pcm_cache:
            return self._pcm_cache[path]

        tmp_path = os.path.join(
            self._get_temp_dir(),
            f"src_{abs(hash(path)) % 10**8}.pcm.wav"
        )

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", path,
            "-ar", str(PCM_SR), "-ac", str(PCM_CH),
            "-c:a", "pcm_s16le",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        self._pcm_cache[path] = tmp_path
        return tmp_path

    async def predecode_all(self, plan: PlacementPlan, yield_progress=None):
        """
        Pre-decode semua unique optional sound ke PCM.
        yield_progress(done, total) dipanggil tiap file selesai.
        """
        unique = list({p.source_file for p in plan.placements})
        total = len(unique)
        for i, src in enumerate(unique):
            await self._predecode_source(src)
            if yield_progress:
                yield_progress(i + 1, total)

    # ── Scan optional sounds ─────────────────────────────────────────────────

    def scan_optional_sounds(self) -> List[str]:
        folder = self.config.optional_sounds_folder
        if not os.path.isdir(folder):
            raise ValueError(f"Folder tidak ada: {folder}")
        exts = {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg"}
        files = []
        for fn in os.listdir(folder):
            _, ext = os.path.splitext(fn)
            if ext.lower() in exts:
                fp = os.path.abspath(os.path.join(folder, fn))
                if os.path.isfile(fp):
                    files.append(fp)
        files.sort()
        self.optional_sound_files = files
        return files

    # ── Overlap helpers ──────────────────────────────────────────────────────

    def _check_overlap_constraint_none(self, ns, nd, placements):
        ne = ns + nd
        mg = self.config.min_gap
        for p in placements:
            pe = p.start_time + p.duration
            if ne <= p.start_time:
                if ne + mg > p.start_time: return False
            elif ns >= pe:
                if ns < pe + mg: return False
            else:
                return False
        return True

    def _check_overlap_constraint_partial(self, ns, nd, placements):
        ne = ns + nd
        for p in placements:
            pe = p.start_time + p.duration
            ov = max(0, min(ne, pe) - max(ns, p.start_time))
            if ov > 0 and ov > min(nd, p.duration) * 0.5:
                return False
        return True

    def _check_overlap_constraint_full(self, ns, nd, placements):
        return True

    # ── Placement plan ───────────────────────────────────────────────────────

    async def generate_placement_plan(self) -> PlacementPlan:
        import random
        self.main_duration = self.config.target_duration
        if self.main_duration <= 0:
            raise ValueError("target_duration harus > 0")
        if not self.optional_sound_files:
            return PlacementPlan(
                main_sounds=self.config.main_sounds,
                optional_sounds_folder=self.config.optional_sounds_folder,
                target_duration=self.main_duration,
            )

        tw_start = self.config.time_window_start
        tw_end   = self.config.time_window_end or self.main_duration
        tw_end   = min(tw_end, self.main_duration)
        if tw_end <= tw_start:
            raise ValueError("time_window_end harus > time_window_start")

        mode_map = {
            "none":    self._check_overlap_constraint_none,
            "partial": self._check_overlap_constraint_partial,
            "full":    self._check_overlap_constraint_full,
        }
        check = mode_map.get(self.config.overlap_mode)
        if check is None:
            raise ValueError(f"Invalid overlap_mode: {self.config.overlap_mode}")

        placements: List[Placement] = []
        MAX_TRIES = 10

        for idx in range(self.config.occurrence_count):
            placed = False
            for _ in range(MAX_TRIES):
                src = random.choice(self.optional_sound_files)
                try:
                    ts, te = await self.detect_silence_cached(src)
                    dur_src = await self.get_audio_duration(src)
                except Exception:
                    continue
                avail = dur_src - ts - te
                if avail < 0.1:
                    continue
                max_d = min(self.config.max_duration, avail)
                min_d = min(self.config.min_duration, max_d)
                if min_d > max_d:
                    continue
                dur = random.uniform(min_d, max_d)
                max_st = tw_end - dur
                if max_st < tw_start:
                    continue
                st = random.uniform(tw_start, max_st)
                if check(st, dur, placements):
                    placements.append(Placement(
                        source_file=src,
                        start_time=st,
                        duration=dur,
                        fade_in=self.config.fade_duration,
                        fade_out=self.config.fade_duration,
                        trimmed_start=ts,
                        trimmed_end=te,
                    ))
                    placed = True
                    break
            if not placed:
                print(f"[plan] skip occurrence {idx+1} setelah {MAX_TRIES} percobaan", file=sys.stderr)

        placements.sort(key=lambda p: p.start_time)
        return PlacementPlan(
            main_sounds=self.config.main_sounds,
            optional_sounds_folder=self.config.optional_sounds_folder,
            target_duration=self.main_duration,
            placements=placements,
        )

    # ── 2-Pass FFmpeg command builder ────────────────────────────────────────

    def _calculate_max_overlap_count(self, placements: List[Placement]) -> int:
        if not placements: return 1
        events = []
        for p in placements:
            events.append((p.start_time, 1))
            events.append((p.start_time + p.duration, -1))
        events.sort()
        cur = mx = 0
        for _, d in events:
            cur += d
            mx = max(mx, cur)
        return max(1, mx)

    def build_pass1_command(
        self,
        plan: PlacementPlan,
        out_pcm: str,
        preview_mode: bool = False,
        preview_duration: float = 30.0,
    ) -> list:
        """
        Pass 1: Render semua optional placements ke satu PCM track.
        Input: PCM temp files (sudah di-predecode).
        Output: PCM WAV (s16le 44100Hz 2ch).
        """
        if not plan.placements:
            return []

        target_dur = plan.target_duration
        if preview_mode:
            target_dur = min(target_dur, preview_duration)

        # Hitung volume normalisasi
        max_ov = self._calculate_max_overlap_count(plan.placements)
        vol_factor = 1.0 / math.sqrt(max_ov) if max_ov > 1 else 1.0

        # Build unique sources map (pakai PCM cache jika ada)
        unique_sources: Dict[str, int] = {}
        cmd = ["ffmpeg", "-y"]
        idx = 0
        for p in plan.placements:
            src = p.source_file
            if src not in unique_sources:
                pcm_src = self._pcm_cache.get(src, src)
                cmd.extend(["-i", pcm_src])
                unique_sources[src] = idx
                idx += 1

        # Tambah silent input untuk anchor durasi
        cmd.extend(["-f", "lavfi", "-t", str(target_dur), "-i", f"aevalsrc=0:c=stereo:r={PCM_SR}"])
        silence_idx = idx

        # Filter complex
        fp: List[str] = []
        delayed: List[str] = []

        for i, p in enumerate(plan.placements):
            if p.start_time >= target_dur:
                continue
            in_idx  = unique_sources[p.source_file]
            label   = f"opt{i}"
            trim_end = p.trimmed_start + p.duration
            fo_st    = p.duration - p.fade_out
            vol_val  = (p.volume / 100.0) * vol_factor

            chain  = f"[{in_idx}:a]"
            chain += f"atrim=start={p.trimmed_start}:end={trim_end},asetpts=PTS-STARTPTS,"
            chain += f"afade=t=in:d={p.fade_in},"
            chain += f"afade=t=out:st={fo_st:.4f}:d={p.fade_out}"
            if abs(vol_val - 1.0) > 0.001:
                chain += f",volume={vol_val:.4f}"
            chain += f"[{label}]"
            fp.append(chain)

            delay_ms = int(p.start_time * 1000)
            dlabel   = f"{label}_d"
            fp.append(f"[{label}]adelay={delay_ms}|{delay_ms}[{dlabel}]")
            delayed.append(dlabel)

        if not delayed:
            return []

        # Tree-style batched amix
        batch_parts, final_opt_label = _batch_amix(delayed)
        fp.extend(batch_parts)

        # Mix dengan silent anchor untuk memastikan durasi output = target_dur
        fp.append(
            f"[{silence_idx}:a][{final_opt_label}]"
            f"amix=inputs=2:duration=first:normalize=0[optout]"
        )

        from core.env import get_thread_flags
        cmd.extend(get_thread_flags())
        cmd.extend(["-filter_complex", ";".join(fp)])
        cmd.extend(["-map", "[optout]"])
        cmd.extend(["-ar", str(PCM_SR), "-ac", str(PCM_CH), "-c:a", "pcm_s16le"])
        cmd.append(out_pcm)
        return cmd

    def build_pass2_command(
        self,
        plan: PlacementPlan,
        opt_pcm: str,
        out_final: str,
        preview_mode: bool = False,
        preview_duration: float = 30.0,
    ) -> list:
        """
        Pass 2: Loop main sounds + mix dengan optional PCM layer.
        Input: opt_pcm (Pass-1 output), main sounds (stream_loop).
        Output: file final (AAC/WAV).
        """
        target_dur = plan.target_duration
        if preview_mode:
            target_dur = min(target_dur, preview_duration)

        xfade = min(self.config.loop_xfade, target_dur * 0.4)

        cmd = ["ffmpeg", "-y"]

        # Main sounds – looped
        for ms in self.config.main_sounds:
            cmd.extend(["-stream_loop", "-1", "-i", ms["path"]])

        # Optional layer PCM
        cmd.extend(["-i", opt_pcm])
        opt_idx = len(self.config.main_sounds)

        fp: List[str] = []
        main_labels: List[str] = []

        for i, ms in enumerate(self.config.main_sounds):
            vol = ms.get("volume", 100) / 100.0
            chain = (
                f"[{i}:a]atrim=duration={target_dur:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=out:st={target_dur - xfade:.3f}:d={xfade:.3f}"
            )
            if abs(vol - 1.0) > 0.001:
                chain += f",volume={vol:.4f}"
            lbl = f"main{i}"
            chain += f"[{lbl}]"
            fp.append(chain)
            main_labels.append(lbl)

        # Optional layer: trim ke target_dur saja
        fp.append(
            f"[{opt_idx}:a]atrim=duration={target_dur:.3f},"
            f"asetpts=PTS-STARTPTS[optlayer]"
        )

        all_inputs = main_labels + ["optlayer"]
        if len(all_inputs) > 1:
            inp_str = "".join(f"[{l}]" for l in all_inputs)
            fp.append(
                f"{inp_str}amix=inputs={len(all_inputs)}:duration=first:normalize=0[aout]"
            )
        else:
            fp.append(f"[{all_inputs[0]}]acopy[aout]")

        from core.env import get_thread_flags
        cmd.extend(get_thread_flags())
        cmd.extend(["-filter_complex", ";".join(fp)])
        cmd.extend(["-map", "[aout]"])

        fmt = self.config.output_format.lower()
        if fmt == "wav":
            cmd.extend(["-c:a", "pcm_s24le"])
        else:
            cmd.extend(["-c:a", "aac", "-b:a", "256k"])

        cmd.append(out_final)
        return cmd

    # ── Legacy single-pass (fallback, tidak dipakai oleh API baru) ───────────

    def build_ffmpeg_command(
        self,
        plan: PlacementPlan,
        preview_mode: bool = False,
        preview_duration: float = 30.0,
    ) -> list:
        """
        Single-pass fallback – hanya dipakai bila plan.placements sangat sedikit.
        Untuk performa optimal, gunakan build_pass1_command + build_pass2_command.
        """
        # Jika <= 32 placements, single-pass masih OK
        # Lebih dari itu, panggil 2-pass via API render
        target_dur = self.config.target_duration
        if preview_mode:
            target_dur = min(target_dur, preview_duration)
        xfade = min(self.config.loop_xfade, target_dur * 0.4)

        cmd = ["ffmpeg", "-y"]
        for ms in self.config.main_sounds:
            cmd.extend(["-stream_loop", "-1", "-i", ms["path"]])

        unique: Dict[str, int] = {}
        in_idx = len(self.config.main_sounds)
        for p in plan.placements:
            if p.source_file not in unique:
                pcm = self._pcm_cache.get(p.source_file, p.source_file)
                cmd.extend(["-i", pcm])
                unique[p.source_file] = in_idx
                in_idx += 1

        if not self.config.main_sounds:
            raise ValueError("No main sounds provided.")

        max_ov = self._calculate_max_overlap_count(plan.placements)
        vol_factor = 1.0 / math.sqrt(max_ov) if max_ov > 1 else 1.0

        fp: List[str] = []
        delayed: List[str] = []

        for i, p in enumerate(plan.placements):
            ii      = unique[p.source_file]
            label   = f"opt{i}"
            trim_end = p.trimmed_start + p.duration
            fo_st    = p.duration - p.fade_out
            vol_val  = (p.volume / 100.0) * vol_factor

            chain  = f"[{ii}:a]"
            chain += f"atrim=start={p.trimmed_start}:end={trim_end},asetpts=PTS-STARTPTS,"
            chain += f"afade=t=in:d={p.fade_in},afade=t=out:st={fo_st:.4f}:d={p.fade_out}"
            if abs(vol_val - 1.0) > 0.001:
                chain += f",volume={vol_val:.4f}"
            chain += f"[{label}]"
            fp.append(chain)

            dm = int(p.start_time * 1000)
            dl = f"{label}_d"
            fp.append(f"[{label}]adelay={dm}|{dm}[{dl}]")
            delayed.append(dl)

        main_labels = []
        for i, ms in enumerate(self.config.main_sounds):
            vol = ms.get("volume", 100) / 100.0
            chain = (
                f"[{i}:a]atrim=duration={target_dur:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=out:st={target_dur - xfade:.3f}:d={xfade:.3f}"
            )
            if abs(vol - 1.0) > 0.001:
                chain += f",volume={vol:.4f}"
            lbl = f"main{i}"
            chain += f"[{lbl}]"
            fp.append(chain)
            main_labels.append(lbl)

        batch_parts, final_opt = _batch_amix(delayed) if delayed else ([], None)
        fp.extend(batch_parts)

        all_in = main_labels + ([final_opt] if final_opt else [])
        if len(all_in) > 1:
            inp_str = "".join(f"[{l}]" for l in all_in)
            fp.append(f"{inp_str}amix=inputs={len(all_in)}:duration=first:normalize=0[aout]")
        else:
            fp.append(f"[{all_in[0]}]acopy[aout]")

        from core.env import get_thread_flags
        cmd.extend(get_thread_flags())
        cmd.extend(["-filter_complex", ";".join(fp)])
        cmd.extend(["-map", "[aout]"])

        fmt = self.config.output_format.lower()
        if fmt == "wav":
            cmd.extend(["-c:a", "pcm_s24le"])
        else:
            cmd.extend(["-c:a", "aac", "-b:a", "256k"])
        cmd.append(self.config.output_path)
        return cmd
