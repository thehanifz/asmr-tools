"""Shared audio helpers: stereo pan (qipadd-style) + seamless loop math.

Dua teknik yang diadopsi dari repo ASMR lain (lihat README / kredit):

1. Pan per-track ala qipadd/asmr-mix-tools — setiap track bisa ditempatkan
   di kiri / tengah / kanan ruang stereo, bukan cuma diatur volumenya.
   Implementasi di sini adalah versi kontinu dari pemetaan qipadd:
   qipadd memakai faktor diskret left=(1,0), center=(1,1), right=(0,1);
   di sini nilai pan -1.0..1.0 diinterpolasi linier di antara titik itu.

2. Seamless loop ala setiajiekaputra01-cmd/tools-asmr (rakit_audio.sh) —
   perhitungan crossfade adaptif + jumlah sampel tile yang bisa di-loop,
   supaya `aloop` bekerja sample-accurate (bukan kira-kira per detik).
"""

import math
from typing import Optional, Tuple, Union

PanValue = Union[str, int, float, None]

_PAN_WORDS = {
    "left": -1.0,
    "kiri": -1.0,
    "l": -1.0,
    "center": 0.0,
    "centre": 0.0,
    "tengah": 0.0,
    "c": 0.0,
    "right": 1.0,
    "kanan": 1.0,
    "r": 1.0,
}


def normalize_pan(pan: PanValue) -> float:
    """Normalisasi nilai pan apa pun menjadi float -1.0 (kiri) .. 1.0 (kanan).

    Menerima: "left"/"kiri", "center"/"tengah", "right"/"kanan",
    angka -1..1, atau string numerik. Nilai tak dikenal -> 0.0 (tengah).
    """
    if pan is None:
        return 0.0
    if isinstance(pan, (int, float)):
        value = float(pan)
    else:
        text = str(pan).strip().lower()
        if text in _PAN_WORDS:
            return _PAN_WORDS[text]
        try:
            value = float(text)
        except ValueError:
            return 0.0
    return max(-1.0, min(1.0, value))


def pan_factors(pan: PanValue) -> Tuple[float, float]:
    """Faktor (kiri, kanan) untuk nilai pan — interpolasi dari peta qipadd.

    left -> (1.0, 0.0), center -> (1.0, 1.0), right -> (0.0, 1.0).
    """
    p = normalize_pan(pan)
    if p <= 0:
        return (1.0, 1.0 + p)
    return (1.0 - p, 1.0)


def pan_filter(pan: PanValue) -> Optional[str]:
    """Filter FFmpeg `pan` untuk nilai pan, atau None bila tengah (no-op).

    Bentuknya sama seperti yang dibangkitkan qipadd/asmr-mix-tools:
    pan=stereo|c0=<L>*c0|c1=<R>*c1  (aformat stereo diasumsikan oleh pemanggil
    bila sumbernya mungkin bukan stereo).
    """
    if normalize_pan(pan) == 0.0:
        return None
    left, right = pan_factors(pan)
    return f"pan=stereo|c0={left:.3f}*c0|c1={right:.3f}*c1"


def effective_crossfade(src_duration: float, requested: float) -> float:
    """Durasi crossfade efektif ala rakit_audio.sh (Mas Arif).

    - Default Mas Arif: 3 detik, tetapi sumber pendek (<= 10 detik) cukup 1 detik.
    - Nilai yang diminta pengguna dihormati, dengan dua pengaman:
      sumber pendek dibatasi 1 detik, dan crossfade tidak boleh
      melebihi 40% durasi sumber (tile loop butuh sisa bagian tengah).
    """
    base = requested if requested and requested > 0 else 3.0
    if src_duration <= 10:
        base = min(base, 1.0)
    return max(0.0, min(base, src_duration * 0.40))


def loopable_samples(total_samples: int, sample_rate: int, xfade: float) -> int:
    """Jumlah sampel satu tile loopable = total sampel - sampel crossfade.

    Persis perhitungan rakit_audio.sh: LOOPABLE_SAMPLES = TOTAL - (XF * SR).
    Hasil selalu >= 1.
    """
    xfade_samples = int(round(xfade * sample_rate)) if sample_rate > 0 else 0
    return max(1, total_samples - xfade_samples)


def build_seamless_loop_filter(src_dur, total_samples, sample_rate, duration, xfade,
                               fade_in=0.0, fade_out=None):
    """Filter_complex seamless loop ala rakit_audio.sh.

    Langkah:
      1. asplit 3 -> part1 (head, sepanjang xfade), part2 (tengah),
         part3 (tail, sepanjang xfade)
      2. [part3][part1] acrossfade (tri/tri) -> [t] sepanjang xfade
      3. [t][part2] concat -> [loopable], durasinya src_dur - xfade
      4. aloop sample-accurate sebanyak yang dibutuhkan -> trim ke target
      5. fade in/out akhir (fade_out default = xfade, perilaku lama)

    Mengembalikan (filter_complex, durasi_tile_detik).
    Bila data sampel tidak tersedia / crossfade tidak layak (<= 0.05s),
    tile = sumber utuh tanpa acrossfade.
    """
    if fade_out is None:
        fade_out = xfade

    tail_filters = f"atrim=duration={duration:.3f},asetpts=PTS-STARTPTS"
    if fade_in and fade_in > 0:
        tail_filters += f",afade=t=in:d={fade_in:.3f}:curve=tri"
    if fade_out and fade_out > 0 and duration > fade_out:
        tail_filters += f",afade=t=out:st={duration - fade_out:.3f}:d={fade_out:.3f}:curve=tri"

    if xfade <= 0.05 or total_samples <= 0 or sample_rate <= 0:
        tile_samples = max(1, total_samples)
        tiles_needed = math.ceil(duration / src_dur) if src_dur > 0 else 1
        parts = ["[0:a]asetpts=PTS-STARTPTS[loopable]"]
        last = "loopable"
        if tiles_needed > 1 and tile_samples > 1:
            parts.append(
                f"[loopable]aloop=loop={tiles_needed - 1}:size={tile_samples}:start=0[looped]"
            )
            last = "looped"
        parts.append(f"[{last}]{tail_filters}[out]")
        return ";".join(parts), src_dur

    tile_samples = loopable_samples(total_samples, sample_rate, xfade)
    tile_dur = tile_samples / sample_rate
    tiles_needed = math.ceil(duration / tile_dur) if tile_dur > 0 else 1

    mid_end = src_dur - xfade
    parts = [
        "[0:a]asplit=3[s1][s2][s3]",
        f"[s1]atrim=start=0:end={xfade:.3f},asetpts=PTS-STARTPTS[part1]",
        f"[s2]atrim=start={xfade:.3f}:end={mid_end:.3f},asetpts=PTS-STARTPTS[part2]",
        f"[s3]atrim=start={mid_end:.3f}:end={src_dur:.3f},asetpts=PTS-STARTPTS[part3]",
        f"[part3][part1]acrossfade=d={xfade:.3f}:c1=tri:c2=tri[t]",
        "[t][part2]concat=n=2:v=0:a=1[loopable]",
    ]
    last = "loopable"
    if tiles_needed > 1:
        parts.append(
            f"[loopable]aloop=loop={tiles_needed - 1}:size={tile_samples}:start=0[looped]"
        )
        last = "looped"
    parts.append(f"[{last}]{tail_filters}[out]")
    return ";".join(parts), tile_dur
