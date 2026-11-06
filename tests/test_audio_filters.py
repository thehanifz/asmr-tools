"""
Tests for core/audio_filters.py — pan (qipadd) + seamless loop math (Mas Arif).

Run: python tests/test_audio_filters.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.audio_filters import (
    effective_crossfade,
    loopable_samples,
    normalize_pan,
    pan_factors,
    pan_filter,
)


def test_normalize_pan():
    assert normalize_pan("left") == -1.0
    assert normalize_pan("Kiri") == -1.0
    assert normalize_pan("center") == 0.0
    assert normalize_pan("tengah") == 0.0
    assert normalize_pan("right") == 1.0
    assert normalize_pan("kanan") == 1.0
    assert normalize_pan(0.5) == 0.5
    assert normalize_pan(-2) == -1.0  # clamp
    assert normalize_pan(99) == 1.0   # clamp
    assert normalize_pan(None) == 0.0
    assert normalize_pan("acak") == 0.0
    print("  normalize_pan OK")


def test_pan_factors_match_qipadd():
    # Pemetaan diskret qipadd: left=(1,0), center=(1,1), right=(0,1)
    assert pan_factors("left") == (1.0, 0.0)
    assert pan_factors("center") == (1.0, 1.0)
    assert pan_factors("right") == (0.0, 1.0)
    # Versi kontinu: -0.5 -> (1.0, 0.5)
    assert pan_factors(-0.5) == (1.0, 0.5)
    assert pan_factors(0.5) == (0.5, 1.0)
    print("  pan_factors OK")


def test_pan_filter():
    assert pan_filter("center") is None
    assert pan_filter(0) is None
    assert pan_filter("left") == "pan=stereo|c0=1.000*c0|c1=0.000*c1"
    assert pan_filter("right") == "pan=stereo|c0=0.000*c0|c1=1.000*c1"
    print("  pan_filter OK")


def test_effective_crossfade():
    # Sumber panjang: nilai pengguna dihormati
    assert effective_crossfade(60, 2.0) == 2.0
    # Sumber pendek (<=10s): dibatasi 1 detik ala rakit_audio.sh
    assert effective_crossfade(8, 3.0) == 1.0
    # Pengaman 40% durasi sumber
    assert effective_crossfade(4, 3.0) == 1.0  # min(1.0 pendek, 40%*4=1.6)
    assert effective_crossfade(20, 10.0) == 8.0
    # Request 0 / None -> default 3 detik (sumber panjang)
    assert effective_crossfade(60, 0) == 3.0
    print("  effective_crossfade OK")


def test_loopable_samples():
    # 10 detik @48k = 480000 sampel; xfade 3s -> tile 480000-144000
    assert loopable_samples(480000, 48000, 3.0) == 336000
    assert loopable_samples(100, 48000, 3.0) == 1  # tidak pernah <= 0
    print("  loopable_samples OK")


def test_seamless_filter_structure():
    from core.audio_filters import build_seamless_loop_filter

    fc, tile_dur = build_seamless_loop_filter(
        src_dur=10.0, total_samples=480000, sample_rate=48000,
        duration=30.0, xfade=2.0,
    )
    assert "acrossfade=d=2.000:c1=tri:c2=tri" in fc
    assert "aloop=loop=" in fc
    assert "size=384000" in fc  # 480000 - 2*48000
    assert abs(tile_dur - 8.0) < 1e-9
    print("  build_seamless_loop_filter OK")


if __name__ == "__main__":
    test_normalize_pan()
    test_pan_factors_match_qipadd()
    test_pan_filter()
    test_effective_crossfade()
    test_loopable_samples()
    test_seamless_filter_structure()
    print("All audio_filters tests passed.")
