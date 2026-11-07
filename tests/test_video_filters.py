"""Unit test helper fade segmen (core/video_filters.py)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.video_filters import fade_segment_lengths, segment_length


def test_segment_length_is_tile_multiple():
    assert segment_length(9.0) == 18.0    # ceil(15/9)=2 tile
    assert segment_length(10.0) == 20.0
    assert segment_length(20.0) == 20.0   # tile sudah >= target
    assert segment_length(3.0) == 15.0


def test_lengths_sum_to_duration():
    head, mid, tail = fade_segment_lengths(3600, 9.0, 3.0, 3.0)
    assert (head, tail) == (18.0, 18.0)
    assert head + mid + tail == 3600


def test_fade_in_only():
    head, mid, tail = fade_segment_lengths(600, 10.0, 2.0, 0)
    assert head == 20.0 and tail == 0.0 and mid == 580.0


def test_fade_out_only():
    head, mid, tail = fade_segment_lengths(600, 10.0, 0, 2.0)
    assert head == 0.0 and tail == 20.0 and mid == 580.0


def test_no_fade_returns_none():
    assert fade_segment_lengths(3600, 9.0, 0, 0) is None


def test_short_duration_returns_none():
    # Di bawah ambang 120 detik -> fallback fade penuh
    assert fade_segment_lengths(60, 9.0, 3.0, 3.0) is None
    assert fade_segment_lengths(119, 9.0, 3.0, 3.0) is None
    assert fade_segment_lengths(120, 9.0, 3.0, 3.0) is not None


def test_segments_must_leave_middle():
    # Kepala+ekor tidak boleh menghabiskan seluruh durasi
    assert fade_segment_lengths(120, 100.0, 3.0, 3.0) is None
