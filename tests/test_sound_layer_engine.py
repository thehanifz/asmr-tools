"""
Basic validation tests for Sound Layer Engine core functionality.

Feature: sound-layering-smart-merge
Task: 5. Checkpoint - Ensure core engine tests pass
"""

import os
import sys
import asyncio
import tempfile
import json
from pathlib import Path

# Add parent directory to path to import core module
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sound_layer_engine import (
    Placement,
    PlacementPlan,
    LayerConfig,
    SoundLayerEngine
)


def test_placement_dataclass():
    """Test Placement dataclass creation and attributes."""
    print("Testing Placement dataclass...")
    
    placement = Placement(
        source_file="/path/to/sound.mp3",
        start_time=5.0,
        duration=10.0,
        fade_in=0.5,
        fade_out=0.5,
        trimmed_start=0.2,
        trimmed_end=0.3
    )
    
    assert placement.source_file == "/path/to/sound.mp3"
    assert placement.start_time == 5.0
    assert placement.duration == 10.0
    assert placement.fade_in == 0.5
    assert placement.fade_out == 0.5
    assert placement.trimmed_start == 0.2
    assert placement.trimmed_end == 0.3
    
    print("✓ Placement dataclass works correctly")


def test_placement_plan_serialization():
    """Test PlacementPlan serialization and deserialization."""
    print("\nTesting PlacementPlan serialization...")
    
    # Create a placement plan
    placements = [
        Placement(
            source_file="/path/to/sound1.mp3",
            start_time=5.0,
            duration=10.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.2,
            trimmed_end=0.3
        ),
        Placement(
            source_file="/path/to/sound2.mp3",
            start_time=20.0,
            duration=8.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.1,
            trimmed_end=0.1
        )
    ]
    
    plan = PlacementPlan(
        version="1.0",
        main_sound_path="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        placements=placements
    )
    
    # Serialize to JSON
    json_str = plan.to_json()
    assert isinstance(json_str, str)
    assert len(json_str) > 0
    
    # Verify JSON structure
    data = json.loads(json_str)
    assert data["version"] == "1.0"
    assert data["main_sound_path"] == "/path/to/main.mp3"
    assert data["optional_sounds_folder"] == "/path/to/optional"
    assert len(data["placements"]) == 2
    
    # Deserialize from JSON
    restored_plan = PlacementPlan.from_json(json_str)
    assert restored_plan.version == plan.version
    assert restored_plan.main_sound_path == plan.main_sound_path
    assert restored_plan.optional_sounds_folder == plan.optional_sounds_folder
    assert len(restored_plan.placements) == len(plan.placements)
    
    # Verify placements match
    for i, (orig, restored) in enumerate(zip(plan.placements, restored_plan.placements)):
        assert restored.source_file == orig.source_file
        assert restored.start_time == orig.start_time
        assert restored.duration == orig.duration
        assert restored.fade_in == orig.fade_in
        assert restored.fade_out == orig.fade_out
        assert restored.trimmed_start == orig.trimmed_start
        assert restored.trimmed_end == orig.trimmed_end
    
    print("✓ PlacementPlan serialization round-trip works correctly")


def test_layer_config_dataclass():
    """Test LayerConfig dataclass with default values."""
    print("\nTesting LayerConfig dataclass...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a"
    )
    
    # Check required fields
    assert config.main_sound == "/path/to/main.mp3"
    assert config.optional_sounds_folder == "/path/to/optional"
    assert config.output_path == "/path/to/output.m4a"
    
    # Check default values
    assert config.occurrence_count == 10
    assert config.time_window_start == 0.0
    assert config.time_window_end == 0.0
    assert config.min_duration == 3.0
    assert config.max_duration == 10.0
    assert config.min_gap == 2.0
    assert config.overlap_mode == "none"
    assert config.fade_duration == 0.5
    assert config.silence_threshold == -50.0
    
    print("✓ LayerConfig dataclass works correctly with defaults")


def test_sound_layer_engine_initialization():
    """Test SoundLayerEngine initialization."""
    print("\nTesting SoundLayerEngine initialization...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a"
    )
    
    engine = SoundLayerEngine(config)
    
    assert engine.config == config
    assert engine.optional_sound_files == []
    assert engine.main_duration == 0.0
    assert engine.silence_cache == {}
    
    print("✓ SoundLayerEngine initializes correctly")


def test_scan_optional_sounds_with_temp_folder():
    """Test scan_optional_sounds with a temporary folder containing audio files."""
    print("\nTesting scan_optional_sounds with temporary folder...")
    
    # Create temporary directory with audio files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some dummy audio files
        audio_files = [
            "sound1.mp3",
            "sound2.wav",
            "sound3.m4a",
            "sound4.flac",
            "not_audio.txt",  # Should be ignored
            "image.png"  # Should be ignored
        ]
        
        for filename in audio_files:
            file_path = os.path.join(temp_dir, filename)
            Path(file_path).touch()
        
        # Create engine and scan
        config = LayerConfig(
            main_sound="/path/to/main.mp3",
            optional_sounds_folder=temp_dir,
            output_path="/path/to/output.m4a"
        )
        
        engine = SoundLayerEngine(config)
        discovered_files = engine.scan_optional_sounds()
        
        # Verify only audio files are discovered
        assert len(discovered_files) == 4
        
        # Verify files are sorted
        basenames = [os.path.basename(f) for f in discovered_files]
        assert basenames == sorted(basenames)
        
        # Verify all discovered files have audio extensions
        for file_path in discovered_files:
            ext = os.path.splitext(file_path)[1].lower()
            assert ext in {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}
        
        # Verify engine cached the results
        assert engine.optional_sound_files == discovered_files
        
        print(f"✓ scan_optional_sounds discovered {len(discovered_files)} audio files correctly")


def test_scan_optional_sounds_error_handling():
    """Test scan_optional_sounds error handling for non-existent folder."""
    print("\nTesting scan_optional_sounds error handling...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/nonexistent/folder",
        output_path="/path/to/output.m4a"
    )
    
    engine = SoundLayerEngine(config)
    
    try:
        engine.scan_optional_sounds()
        assert False, "Expected ValueError for non-existent folder"
    except ValueError as e:
        assert "does not exist" in str(e)
        print(f"✓ scan_optional_sounds raises ValueError for non-existent folder: {e}")


def test_overlap_constraint_none():
    """Test overlap constraint checking for mode='none'."""
    print("\nTesting overlap constraint checking (mode='none')...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a",
        overlap_mode="none",
        min_gap=2.0
    )
    
    engine = SoundLayerEngine(config)
    
    # Create existing placements
    placements = [
        Placement(
            source_file="/path/to/sound1.mp3",
            start_time=5.0,
            duration=10.0,
            fade_in=0.5,
            fade_out=0.5
        ),
        Placement(
            source_file="/path/to/sound2.mp3",
            start_time=20.0,
            duration=8.0,
            fade_in=0.5,
            fade_out=0.5
        )
    ]
    
    # Test valid placement (after second placement with min_gap)
    assert engine._check_overlap_constraint_none(30.0, 5.0, placements) == True
    
    # Test invalid placement (overlaps with first placement)
    assert engine._check_overlap_constraint_none(10.0, 5.0, placements) == False
    
    # Test invalid placement (too close to first placement, violates min_gap)
    assert engine._check_overlap_constraint_none(15.5, 3.0, placements) == False
    
    # Test valid placement (before first placement with min_gap)
    assert engine._check_overlap_constraint_none(0.0, 3.0, placements) == True
    
    print("✓ Overlap constraint checking (mode='none') works correctly")


def test_overlap_constraint_partial():
    """Test overlap constraint checking for mode='partial'."""
    print("\nTesting overlap constraint checking (mode='partial')...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a",
        overlap_mode="partial"
    )
    
    engine = SoundLayerEngine(config)
    
    # Create existing placement
    placements = [
        Placement(
            source_file="/path/to/sound1.mp3",
            start_time=10.0,
            duration=10.0,  # ends at 20.0
            fade_in=0.5,
            fade_out=0.5
        )
    ]
    
    # Test valid placement (overlap <= 50% of shorter duration)
    # New placement: start=15.0, duration=6.0 (ends at 21.0)
    # Overlap: 15.0 to 20.0 = 5.0 seconds
    # Max allowed: min(10.0, 6.0) * 0.5 = 3.0 seconds
    # This should FAIL (5.0 > 3.0)
    assert engine._check_overlap_constraint_partial(15.0, 6.0, placements) == False
    
    # Test valid placement (overlap <= 50%)
    # New placement: start=17.0, duration=6.0 (ends at 23.0)
    # Overlap: 17.0 to 20.0 = 3.0 seconds
    # Max allowed: min(10.0, 6.0) * 0.5 = 3.0 seconds
    # This should PASS (3.0 <= 3.0)
    assert engine._check_overlap_constraint_partial(17.0, 6.0, placements) == True
    
    # Test no overlap (should always pass)
    assert engine._check_overlap_constraint_partial(25.0, 5.0, placements) == True
    
    print("✓ Overlap constraint checking (mode='partial') works correctly")


def test_overlap_constraint_full():
    """Test overlap constraint checking for mode='full'."""
    print("\nTesting overlap constraint checking (mode='full')...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a",
        overlap_mode="full"
    )
    
    engine = SoundLayerEngine(config)
    
    # Create existing placements
    placements = [
        Placement(
            source_file="/path/to/sound1.mp3",
            start_time=5.0,
            duration=10.0,
            fade_in=0.5,
            fade_out=0.5
        )
    ]
    
    # All placements should be valid in full overlap mode
    assert engine._check_overlap_constraint_full(5.0, 10.0, placements) == True
    assert engine._check_overlap_constraint_full(10.0, 5.0, placements) == True
    assert engine._check_overlap_constraint_full(0.0, 20.0, placements) == True
    
    print("✓ Overlap constraint checking (mode='full') works correctly")


def test_escape_filter_path():
    """Test path escaping for FFmpeg filter_complex."""
    print("\nTesting _escape_filter_path...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a"
    )
    
    engine = SoundLayerEngine(config)
    
    # Test backslash to forward slash conversion
    assert engine._escape_filter_path("C:\\Users\\test\\file.mp3") == "C\\:/Users/test/file.mp3"
    
    # Test special character escaping
    assert engine._escape_filter_path("/path/to/file's.mp3") == "/path/to/file\\'s.mp3"
    assert engine._escape_filter_path("/path/to/file[1].mp3") == "/path/to/file\\[1\\].mp3"
    assert engine._escape_filter_path("/path/to/file,name.mp3") == "/path/to/file\\,name.mp3"
    
    # Test Linux path (no changes needed)
    assert engine._escape_filter_path("/home/user/file.mp3") == "/home/user/file.mp3"
    
    print("✓ _escape_filter_path works correctly")


def test_quote_input_path():
    """Test path quoting for FFmpeg input."""
    print("\nTesting _quote_input_path...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a"
    )
    
    engine = SoundLayerEngine(config)
    
    # Test path quoting (platform-specific)
    import platform
    
    if platform.system() == "Windows":
        # Windows uses double quotes
        assert engine._quote_input_path("C:\\Users\\test\\file.mp3") == '"C:\\Users\\test\\file.mp3"'
    else:
        # Linux uses single quotes
        assert engine._quote_input_path("/home/user/file.mp3") == "'/home/user/file.mp3'"
        # Test single quote escaping
        result = engine._quote_input_path("/home/user/file's.mp3")
        assert result.startswith("'")
        assert result.endswith("'")
    
    print("✓ _quote_input_path works correctly")


def test_calculate_max_overlap_count():
    """Test calculation of maximum overlap count."""
    print("\nTesting _calculate_max_overlap_count...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a"
    )
    
    engine = SoundLayerEngine(config)
    
    # Test with no placements
    assert engine._calculate_max_overlap_count([]) == 1
    
    # Test with non-overlapping placements
    placements = [
        Placement(source_file="s1.mp3", start_time=0.0, duration=5.0, fade_in=0.5, fade_out=0.5),
        Placement(source_file="s2.mp3", start_time=10.0, duration=5.0, fade_in=0.5, fade_out=0.5),
    ]
    assert engine._calculate_max_overlap_count(placements) == 1
    
    # Test with 2 overlapping placements
    placements = [
        Placement(source_file="s1.mp3", start_time=0.0, duration=10.0, fade_in=0.5, fade_out=0.5),
        Placement(source_file="s2.mp3", start_time=5.0, duration=10.0, fade_in=0.5, fade_out=0.5),
    ]
    assert engine._calculate_max_overlap_count(placements) == 2
    
    # Test with 3 overlapping placements
    placements = [
        Placement(source_file="s1.mp3", start_time=0.0, duration=15.0, fade_in=0.5, fade_out=0.5),
        Placement(source_file="s2.mp3", start_time=5.0, duration=15.0, fade_in=0.5, fade_out=0.5),
        Placement(source_file="s3.mp3", start_time=10.0, duration=10.0, fade_in=0.5, fade_out=0.5),
    ]
    assert engine._calculate_max_overlap_count(placements) == 3
    
    # Test with complex overlap pattern
    placements = [
        Placement(source_file="s1.mp3", start_time=0.0, duration=5.0, fade_in=0.5, fade_out=0.5),
        Placement(source_file="s2.mp3", start_time=2.0, duration=5.0, fade_in=0.5, fade_out=0.5),
        Placement(source_file="s3.mp3", start_time=4.0, duration=5.0, fade_in=0.5, fade_out=0.5),
        Placement(source_file="s4.mp3", start_time=10.0, duration=5.0, fade_in=0.5, fade_out=0.5),
    ]
    # At time 4.0-5.0: s1, s2, s3 overlap (3 sounds)
    assert engine._calculate_max_overlap_count(placements) == 3
    
    print("✓ _calculate_max_overlap_count works correctly")


def test_build_ffmpeg_command_no_placements():
    """Test FFmpeg command builder with no placements."""
    print("\nTesting build_ffmpeg_command with no placements...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a"
    )
    
    engine = SoundLayerEngine(config)
    
    plan = PlacementPlan(
        version="1.0",
        main_sound_path="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        placements=[]
    )
    
    cmd = engine.build_ffmpeg_command(plan)
    
    # Verify basic command structure
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "-i" in cmd
    assert "/path/to/main.mp3" in cmd
    assert "-c:a" in cmd
    assert "aac" in cmd
    assert "-b:a" in cmd
    assert "256k" in cmd
    assert cmd[-1] == "/path/to/output.m4a"
    
    # Should not have filter_complex for no placements
    assert "-filter_complex" not in cmd
    
    print("✓ build_ffmpeg_command works correctly with no placements")


def test_build_ffmpeg_command_single_placement():
    """Test FFmpeg command builder with single placement."""
    print("\nTesting build_ffmpeg_command with single placement...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a",
        fade_duration=0.5
    )
    
    engine = SoundLayerEngine(config)
    
    placements = [
        Placement(
            source_file="/path/to/sound1.mp3",
            start_time=5.0,
            duration=10.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.2,
            trimmed_end=0.3
        )
    ]
    
    plan = PlacementPlan(
        version="1.0",
        main_sound_path="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        placements=placements
    )
    
    cmd = engine.build_ffmpeg_command(plan)
    
    # Verify basic command structure
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    
    # Verify inputs
    assert cmd.count("-i") == 2  # main + 1 optional
    assert "/path/to/main.mp3" in cmd
    assert "/path/to/sound1.mp3" in cmd
    
    # Verify filter_complex exists
    assert "-filter_complex" in cmd
    filter_idx = cmd.index("-filter_complex")
    filter_complex = cmd[filter_idx + 1]
    
    # Verify filter contains expected components
    assert "atrim" in filter_complex
    assert "asetpts" in filter_complex
    assert "afade=t=in" in filter_complex
    assert "afade=t=out" in filter_complex
    assert "adelay" in filter_complex
    assert "amix" in filter_complex
    
    # Verify output mapping
    assert "-map" in cmd
    assert "[aout]" in cmd
    
    # Verify codec settings
    assert "-c:a" in cmd
    assert "aac" in cmd
    assert "-b:a" in cmd
    assert "256k" in cmd
    
    # Verify output path
    assert cmd[-1] == "/path/to/output.m4a"
    
    print("✓ build_ffmpeg_command works correctly with single placement")


def test_build_ffmpeg_command_multiple_placements():
    """Test FFmpeg command builder with multiple placements."""
    print("\nTesting build_ffmpeg_command with multiple placements...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a",
        fade_duration=0.5
    )
    
    engine = SoundLayerEngine(config)
    
    placements = [
        Placement(
            source_file="/path/to/sound1.mp3",
            start_time=5.0,
            duration=10.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.2,
            trimmed_end=0.3
        ),
        Placement(
            source_file="/path/to/sound2.mp3",
            start_time=20.0,
            duration=8.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.1,
            trimmed_end=0.1
        ),
        Placement(
            source_file="/path/to/sound1.mp3",  # Reuse same file
            start_time=35.0,
            duration=6.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.2,
            trimmed_end=0.3
        )
    ]
    
    plan = PlacementPlan(
        version="1.0",
        main_sound_path="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        placements=placements
    )
    
    cmd = engine.build_ffmpeg_command(plan)
    
    # Verify inputs (main + 2 unique optional sounds)
    assert cmd.count("-i") == 3
    assert "/path/to/main.mp3" in cmd
    assert "/path/to/sound1.mp3" in cmd
    assert "/path/to/sound2.mp3" in cmd
    
    # Verify filter_complex exists
    assert "-filter_complex" in cmd
    filter_idx = cmd.index("-filter_complex")
    filter_complex = cmd[filter_idx + 1]
    
    # Verify filter contains 3 placement chains (one per placement)
    assert filter_complex.count("atrim") == 3
    assert filter_complex.count("adelay") == 3
    
    # Verify amix has correct input count (main + 3 placements = 4)
    assert "amix=inputs=4" in filter_complex
    
    print("✓ build_ffmpeg_command works correctly with multiple placements")


def test_build_ffmpeg_command_with_overlaps():
    """Test FFmpeg command builder with overlapping placements (volume normalization)."""
    print("\nTesting build_ffmpeg_command with overlapping placements...")
    
    config = LayerConfig(
        main_sound="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        output_path="/path/to/output.m4a",
        fade_duration=0.5
    )
    
    engine = SoundLayerEngine(config)
    
    # Create overlapping placements
    placements = [
        Placement(
            source_file="/path/to/sound1.mp3",
            start_time=5.0,
            duration=10.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.0,
            trimmed_end=0.0
        ),
        Placement(
            source_file="/path/to/sound2.mp3",
            start_time=10.0,  # Overlaps with first placement
            duration=10.0,
            fade_in=0.5,
            fade_out=0.5,
            trimmed_start=0.0,
            trimmed_end=0.0
        )
    ]
    
    plan = PlacementPlan(
        version="1.0",
        main_sound_path="/path/to/main.mp3",
        optional_sounds_folder="/path/to/optional",
        placements=placements
    )
    
    cmd = engine.build_ffmpeg_command(plan)
    
    # Verify filter_complex exists
    assert "-filter_complex" in cmd
    filter_idx = cmd.index("-filter_complex")
    filter_complex = cmd[filter_idx + 1]
    
    # Verify volume normalization is applied
    # Max overlap count = 2, so volume factor = 1/sqrt(2) ≈ 0.707
    assert "volume=" in filter_complex
    
    # Check that volume factor is approximately 0.707
    import re
    volume_matches = re.findall(r'volume=([\d.]+)', filter_complex)
    assert len(volume_matches) == 2  # One for each placement
    
    for volume_str in volume_matches:
        volume = float(volume_str)
        expected_volume = 1.0 / (2 ** 0.5)  # 1/sqrt(2)
        assert abs(volume - expected_volume) < 0.01, f"Volume {volume} not close to {expected_volume}"
    
    print("✓ build_ffmpeg_command applies volume normalization correctly")


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("Sound Layer Engine - Core Validation Tests")
    print("=" * 60)
    
    try:
        test_placement_dataclass()
        test_placement_plan_serialization()
        test_layer_config_dataclass()
        test_sound_layer_engine_initialization()
        test_scan_optional_sounds_with_temp_folder()
        test_scan_optional_sounds_error_handling()
        test_overlap_constraint_none()
        test_overlap_constraint_partial()
        test_overlap_constraint_full()
        test_escape_filter_path()
        test_quote_input_path()
        test_calculate_max_overlap_count()
        test_build_ffmpeg_command_no_placements()
        test_build_ffmpeg_command_single_placement()
        test_build_ffmpeg_command_multiple_placements()
        test_build_ffmpeg_command_with_overlaps()
        
        print("\n" + "=" * 60)
        print("✓ All core engine tests passed!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
