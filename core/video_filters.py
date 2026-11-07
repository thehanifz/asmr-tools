"""Helper murni untuk fade video per segmen (tanpa re-encode penuh).

Strategi: hasil loop (stream copy) dipotong di batas kelipatan tile.
Hanya segmen kepala (fade-in) dan ekor (fade-out) yang di-encode ulang;
segmen tengah disalin apa adanya (stream copy) lalu ketiganya digabung
dengan concat demuxer. Karena potongan jatuh tepat di batas tile —
yang juga posisi keyframe pada file hasil loop — concat copy tetap
presisi dan kualitas segmen tengah identik bit-for-bit dengan sumber.
"""
import math

SEGMENT_TARGET = 15.0   # target panjang segmen kepala/ekor (detik)
MIN_DURATION = 120.0    # fade segmen hanya untuk target >= nilai ini


def segment_length(tile_len: float, target: float = SEGMENT_TARGET) -> float:
    """Panjang segmen terkecil yang merupakan kelipatan tile dan >= target."""
    tile = max(float(tile_len), 0.1)
    return max(tile, math.ceil(target / tile) * tile)


def fade_segment_lengths(duration, tile_len, fade_in, fade_out,
                         target=SEGMENT_TARGET, min_duration=MIN_DURATION):
    """Hitung (head, mid, tail) untuk fade segmen.

    head/tail = 0 bila fade bersangkutan tidak aktif. Mengembalikan None
    bila fade segmen tidak layak (tidak ada fade, target terlalu pendek,
    atau segmen tengah habis) — pemanggil harus fallback ke fade penuh.
    """
    duration = float(duration)
    fi = float(fade_in or 0)
    fo = float(fade_out or 0)
    if fi <= 0 and fo <= 0:
        return None
    if duration < float(min_duration):
        return None
    head = segment_length(tile_len, target) if fi > 0 else 0.0
    tail = segment_length(tile_len, target) if fo > 0 else 0.0
    mid = duration - head - tail
    if mid <= 0:
        return None
    return (head, mid, tail)
