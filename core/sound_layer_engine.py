"""
Sound Layer Engine - Core module for sound layering and smart merge functionality.

This module provides data structures and the engine for generating placement plans
for optional sounds, detecting silence, building FFmpeg commands, and rendering
layered audio outputs.

Feature: sound-layering-smart-merge
"""

from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict, Optional, Any
import json


@dataclass
class Placement:
    """
    Represents a single optional sound placement in the timeline.
    
    Attributes:
        source_file: Path to the optional sound file
        start_time: Start position in the timeline (seconds)
        duration: Duration of the placement (seconds)
        fade_in: Fade-in duration (seconds)
        fade_out: Fade-out duration (seconds)
        trimmed_start: Silence trimmed from start (seconds)
        trimmed_end: Silence trimmed from end (seconds)
    """
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
    """
    Represents a complete placement plan for optional sounds.
    
    Attributes:
        version: Schema version for serialization compatibility
        main_sound_path: Path to the main audio file (base layer)
        optional_sounds_folder: Path to folder containing optional sounds
        placements: List of Placement objects, sorted by start_time
    """
    version: str = "1.0"
    main_sounds: List[Dict[str, Any]] = field(default_factory=list)
    optional_sounds_folder: str = ""
    placements: List[Placement] = field(default_factory=list)
    target_duration: float = 3600.0
    
    def to_json(self) -> str:
        """
        Serialize PlacementPlan to JSON string.
        
        Returns:
            JSON string representation of the placement plan
        """
        data = {
            "version": self.version,
            "main_sounds": self.main_sounds,
            "optional_sounds_folder": self.optional_sounds_folder,
            "target_duration": self.target_duration,
            "placements": [asdict(p) for p in self.placements]
        }
        return json.dumps(data, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PlacementPlan':
        """
        Deserialize PlacementPlan from JSON string.
        
        Args:
            json_str: JSON string representation of a placement plan
            
        Returns:
            PlacementPlan object
            
        Raises:
            ValueError: If JSON is invalid or missing required fields
        """
        try:
            data = json.loads(json_str)
            placements = [Placement(**p) for p in data.get("placements", [])]
            return cls(
                version=data.get("version", "1.0"),
                main_sounds=data.get("main_sounds", []),
                optional_sounds_folder=data.get("optional_sounds_folder", ""),
                target_duration=data.get("target_duration", 3600.0),
                placements=placements
            )
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            raise ValueError(f"Invalid PlacementPlan JSON: {e}")


@dataclass
class LayerConfig:
    """
    Configuration for sound layering operations.
    
    Attributes:
        main_sounds: List of dicts with 'path' and 'volume' (0-100) for base layers
        optional_sounds_folder: Path to folder with optional sounds
        output_path: Output file path for rendered audio
        target_duration: Total duration of the mix (seconds)
        loop_xfade: Crossfade duration for looping main sounds (seconds)
        output_format: Output format extension (e.g. "aac", "wav")
        occurrence_count: Number of optional sound placements
        time_window_start: Start of placement window (seconds)
        time_window_end: End of placement window (seconds, 0 = auto/full duration)
        min_duration: Minimum placement duration (seconds)
        max_duration: Maximum placement duration (seconds)
        min_gap: Minimum gap between placements (seconds)
        overlap_mode: Overlap constraint mode ("none", "partial", "full")
        fade_duration: Fade in/out duration (seconds)
        silence_threshold: Silence detection threshold (dB)
    """
    main_sounds: List[Dict[str, Any]]
    optional_sounds_folder: str
    output_path: str
    target_duration: float = 3600.0
    loop_xfade: float = 2.0
    output_format: str = "aac"
    occurrence_count: int = 10
    time_window_start: float = 0.0
    time_window_end: float = 0.0  # 0 = auto (use target duration)
    min_duration: float = 3.0
    max_duration: float = 10.0
    min_gap: float = 2.0
    overlap_mode: str = "none"  # "none", "partial", "full"
    fade_duration: float = 0.5
    silence_threshold: float = -50.0


class SoundLayerEngine:
    """
    Core engine for sound layering operations.
    
    This engine handles:
    - Scanning optional sound files
    - Detecting and trimming silence
    - Generating placement plans with randomization
    - Building FFmpeg commands for rendering
    - Rendering audio with progress streaming
    """
    
    def __init__(self, config: LayerConfig):
        """
        Initialize the sound layer engine with configuration.
        
        Args:
            config: LayerConfig object with all parameters
        """
        self.config = config
        self.optional_sound_files: List[str] = []
        self.main_duration: float = 0.0
        self.silence_cache: Dict[str, Tuple[float, float]] = {}
        self.temp_files: List[str] = []
        
    def __del__(self):
        """Cleanup any remaining temporary files."""
        for tf in getattr(self, "temp_files", []):
            try:
                import os
                if os.path.exists(tf):
                    os.remove(tf)
            except Exception:
                pass
    
    def scan_optional_sounds(self) -> List[str]:
        """
        Scan folder for audio files with supported extensions.
        
        Scans the optional_sounds_folder for audio files with extensions:
        .mp3, .m4a, .aac, .wav, .flac, .ogg
        
        Returns:
            Sorted list of absolute file paths for discovered audio files
            
        Raises:
            ValueError: If folder does not exist
            
        Requirements: 2.2, 2.3, 11.1, 11.2
        """
        import os
        
        folder = self.config.optional_sounds_folder
        
        # Validate folder exists
        if not os.path.exists(folder):
            raise ValueError(f"Optional sounds folder does not exist: {folder}")
        
        if not os.path.isdir(folder):
            raise ValueError(f"Path is not a directory: {folder}")
        
        # Supported audio extensions
        supported_extensions = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}
        
        # Scan folder for audio files
        audio_files = []
        
        try:
            for filename in os.listdir(folder):
                # Get file extension (lowercase for case-insensitive matching)
                _, ext = os.path.splitext(filename)
                ext_lower = ext.lower()
                
                # Check if extension is supported
                if ext_lower in supported_extensions:
                    # Build full path and normalize it
                    full_path = os.path.join(folder, filename)
                    normalized_path = os.path.normpath(full_path)
                    
                    # Convert to absolute path
                    absolute_path = os.path.abspath(normalized_path)
                    
                    # Only add if it's a file (not a directory)
                    if os.path.isfile(absolute_path):
                        audio_files.append(absolute_path)
        
        except PermissionError as e:
            raise ValueError(f"Permission denied accessing folder: {folder}") from e
        except OSError as e:
            raise ValueError(f"Error reading folder: {folder}") from e
        
        # Sort files for consistent ordering
        audio_files.sort()
        
        # Cache the results
        self.optional_sound_files = audio_files
        
        return audio_files
    
    async def get_audio_duration(self, path: str) -> float:
        """
        Get audio duration using ffprobe.
        
        Uses ffprobe to extract the duration of an audio file in seconds.
        Follows the pattern from api/audio.py.
        
        Args:
            path: Path to the audio file
            
        Returns:
            Duration in seconds as a float, or 0.0 if duration cannot be determined
            
        Raises:
            ValueError: If file does not exist
            
        Requirements: 1.3, 11.6
        """
        import os
        import asyncio
        
        # Validate file exists
        if not os.path.exists(path):
            raise ValueError(f"Audio file does not exist: {path}")
        
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        
        try:
            # Execute ffprobe to get duration
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await proc.communicate()
            
            # Parse stdout to float
            duration_str = stdout.decode().strip()
            
            if not duration_str:
                # If no output, return 0.0
                return 0.0
            
            duration = float(duration_str)
            
            # Validate duration is non-negative
            if duration < 0:
                return 0.0
            
            return duration
            
        except ValueError:
            # Failed to parse duration as float
            return 0.0
        except Exception as e:
            # Other errors (e.g., ffprobe not found, file read error)
            # Log the error but return 0.0 for graceful handling
            import sys
            print(f"Error getting audio duration for {path}: {e}", file=sys.stderr)
            return 0.0
    
    async def detect_silence(self, path: str) -> Tuple[float, float]:
        """
        Detect silence at start and end of audio file using FFmpeg silencedetect filter.
        
        Uses FFmpeg silencedetect filter to find silence regions at the beginning
        and end of an audio file. Silence is detected using a threshold of -50dB
        and minimum duration of 0.1 seconds.
        
        Algorithm:
        1. Run ffmpeg with silencedetect filter (threshold=-50dB, duration=0.1s)
        2. Parse stderr output for silence_start and silence_end markers
        3. Identify silence at start (if silence_start < 2.0)
        4. Identify silence at end (if silence_end > duration - 2.0)
        5. Return (start_silence_duration, end_silence_duration)
        
        Example FFmpeg command:
        ffmpeg -i input.mp3 -af silencedetect=n=-50dB:d=0.1 -f null -
        
        Example output parsing:
        [silencedetect @ ...] silence_start: 0
        [silencedetect @ ...] silence_end: 0.523 | silence_duration: 0.523
        [silencedetect @ ...] silence_start: 45.234
        [silencedetect @ ...] silence_end: 47.891 | silence_duration: 2.657
        
        Args:
            path: Path to the audio file
            
        Returns:
            Tuple of (start_silence_duration, end_silence_duration) in seconds.
            Returns (0.0, 0.0) if no silence detected or on error.
            
        Raises:
            ValueError: If file does not exist
            
        Requirements: 5.1, 5.2, 16.1, 16.2, 16.3
        """
        import os
        import asyncio
        import re
        
        # Validate file exists
        if not os.path.exists(path):
            raise ValueError(f"Audio file does not exist: {path}")
        
        if not os.path.isfile(path):
            raise ValueError(f"Path is not a file: {path}")
        
        try:
            # Get audio duration first
            duration = await self.get_audio_duration(path)
            
            if duration == 0.0:
                # Cannot detect silence if duration is unknown
                return (0.0, 0.0)
            
            # Build FFmpeg command for silence detection
            # Use silencedetect filter with threshold=-50dB and min duration=0.1s
            cmd = [
                "ffmpeg",
                "-i", path,
                "-af", f"silencedetect=n={self.config.silence_threshold}dB:d=0.1",
                "-f", "null",
                "-"
            ]
            
            # Execute FFmpeg
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await proc.communicate()
            
            # Parse stderr for silence markers
            stderr_text = stderr.decode()
            
            # Regex patterns for silence detection output
            # Example: [silencedetect @ 0x...] silence_start: 0
            # Example: [silencedetect @ 0x...] silence_end: 0.523 | silence_duration: 0.523
            silence_start_pattern = re.compile(r'silence_start:\s*([\d.]+)')
            silence_end_pattern = re.compile(r'silence_end:\s*([\d.]+)')
            
            # Find all silence regions
            silence_starts = [float(m.group(1)) for m in silence_start_pattern.finditer(stderr_text)]
            silence_ends = [float(m.group(1)) for m in silence_end_pattern.finditer(stderr_text)]
            
            # Identify silence at start and end
            start_silence_duration = 0.0
            end_silence_duration = 0.0
            
            # Check for silence at start (silence_start < 2.0)
            if silence_starts and silence_ends:
                # Find the first silence region
                if silence_starts[0] < 2.0:
                    # Silence at start detected
                    # Find corresponding silence_end
                    if len(silence_ends) > 0:
                        start_silence_duration = silence_ends[0]
            
            # Check for silence at end (silence_end > duration - 2.0)
            if silence_ends:
                # Find the last silence region
                last_silence_end = silence_ends[-1]
                
                if last_silence_end > duration - 2.0:
                    # Silence at end detected
                    # Find corresponding silence_start
                    if len(silence_starts) >= len(silence_ends):
                        # Last silence_start corresponds to last silence_end
                        last_silence_start = silence_starts[-1]
                        end_silence_duration = duration - last_silence_start
            
            return (start_silence_duration, end_silence_duration)
            
        except Exception as e:
            # Log error and return no silence detected
            import sys
            print(f"Error detecting silence for {path}: {e}", file=sys.stderr)
            return (0.0, 0.0)
    
    async def detect_silence_cached(self, path: str) -> Tuple[float, float]:
        """
        Detect silence with caching to avoid redundant FFmpeg executions.
        
        Caches silence detection results per optional sound file using the
        file path and modification time as the cache key. This prevents
        redundant silence detection when the same file is used multiple times
        in a placement plan.
        
        Cache key format: "{path}:{modification_time}"
        
        Args:
            path: Path to the audio file
            
        Returns:
            Tuple of (start_silence_duration, end_silence_duration) in seconds.
            Returns cached result if available, otherwise calls detect_silence()
            and caches the result.
            
        Raises:
            ValueError: If file does not exist
            
        Requirements: 8.4
        """
        import os
        
        # Validate file exists
        if not os.path.exists(path):
            raise ValueError(f"Audio file does not exist: {path}")
        
        # Build cache key: path + modification time
        try:
            mtime = os.path.getmtime(path)
            cache_key = f"{path}:{mtime}"
        except OSError as e:
            raise ValueError(f"Cannot access file: {path}") from e
        
        # Check cache
        if cache_key in self.silence_cache:
            return self.silence_cache[cache_key]
        
        # Cache miss - await async detect_silence directly (no event loop needed)
        result = await self.detect_silence(path)
        
        # Cache the result
        self.silence_cache[cache_key] = result
        
        return result
    
    def _check_overlap_constraint_none(
        self,
        new_start: float,
        new_duration: float,
        placements: List[Placement]
    ) -> bool:
        """
        Check if a new placement satisfies overlap_mode="none" constraints.
        
        For overlap_mode="none", placements must not overlap and must maintain
        min_gap between consecutive placements.
        
        Constraint: new_start >= prev_end + min_gap AND new_end + min_gap <= next_start
        
        Args:
            new_start: Start time of the new placement
            new_duration: Duration of the new placement
            placements: List of existing placements (sorted by start_time)
            
        Returns:
            True if constraints are satisfied, False otherwise
            
        Requirements: 6.5
        """
        new_end = new_start + new_duration
        min_gap = self.config.min_gap
        
        # Check against all existing placements
        for placement in placements:
            existing_start = placement.start_time
            existing_end = placement.start_time + placement.duration
            
            # Check if new placement is before existing placement
            if new_end <= existing_start:
                # New placement ends before existing starts
                # Check min_gap constraint
                if new_end + min_gap > existing_start:
                    return False
            # Check if new placement is after existing placement
            elif new_start >= existing_end:
                # New placement starts after existing ends
                # Check min_gap constraint
                if new_start < existing_end + min_gap:
                    return False
            else:
                # Placements overlap - not allowed for mode="none"
                return False
        
        return True
    
    def _check_overlap_constraint_partial(
        self,
        new_start: float,
        new_duration: float,
        placements: List[Placement]
    ) -> bool:
        """
        Check if a new placement satisfies overlap_mode="partial" constraints.
        
        For overlap_mode="partial", overlaps are allowed up to 50% of the
        shorter sound duration.
        
        Constraint: overlap_amount <= min(new_duration, existing_duration) * 0.5
        
        Args:
            new_start: Start time of the new placement
            new_duration: Duration of the new placement
            placements: List of existing placements (sorted by start_time)
            
        Returns:
            True if constraints are satisfied, False otherwise
            
        Requirements: 6.6
        """
        new_end = new_start + new_duration
        
        # Check against all existing placements
        for placement in placements:
            existing_start = placement.start_time
            existing_end = placement.start_time + placement.duration
            existing_duration = placement.duration
            
            # Calculate overlap amount
            overlap_start = max(new_start, existing_start)
            overlap_end = min(new_end, existing_end)
            overlap_amount = max(0, overlap_end - overlap_start)
            
            if overlap_amount > 0:
                # Calculate max allowed overlap (50% of shorter duration)
                max_overlap = min(new_duration, existing_duration) * 0.5
                
                # Check if overlap exceeds limit
                if overlap_amount > max_overlap:
                    return False
        
        return True
    
    def _check_overlap_constraint_full(
        self,
        new_start: float,
        new_duration: float,
        placements: List[Placement]
    ) -> bool:
        """
        Check if a new placement satisfies overlap_mode="full" constraints.
        
        For overlap_mode="full", any overlap is allowed. This method always
        returns True.
        
        Args:
            new_start: Start time of the new placement
            new_duration: Duration of the new placement
            placements: List of existing placements (sorted by start_time)
            
        Returns:
            Always True (no constraints for full overlap mode)
            
        Requirements: 6.7
        """
        # No constraints for full overlap mode
        return True
    
    def _escape_filter_path(self, path: str) -> str:
        """
        Escape path for FFmpeg filter_complex.
        
        FFmpeg filter_complex requires special escaping for paths:
        - Convert backslashes to forward slashes
        - Escape colons for Windows drive letters (C: → C\\:)
        - Escape special characters: ', [, ], ,, ;
        
        Args:
            path: File path to escape
            
        Returns:
            Escaped path suitable for FFmpeg filter_complex
            
        Requirements: 11.3, 11.4, 11.5, 18.6
        """
        # Convert to forward slashes
        path = path.replace("\\", "/")
        
        # Escape colons (Windows drive letters)
        if len(path) >= 2 and path[1] == ":":
            path = path[0] + "\\:" + path[2:]
        
        # Escape special characters
        for char in ["'", "[", "]", ",", ";"]:
            path = path.replace(char, f"\\{char}")
        
        return path
    
    def _quote_input_path(self, path: str) -> str:
        """
        Quote path for FFmpeg input.
        
        Platform-specific quoting:
        - Windows: use double quotes
        - Linux: use single quotes and escape single quotes
        
        Args:
            path: File path to quote
            
        Returns:
            Quoted path suitable for FFmpeg input
            
        Requirements: 11.2, 11.3
        """
        import platform
        
        if platform.system() == "Windows":
            # Windows: use double quotes
            return f'"{path}"'
        else:
            # Linux: use single quotes and escape single quotes
            return f"'{path.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
    
    async def generate_placement_plan(self) -> PlacementPlan:
        """
        Generate random placement plan based on configuration.
        
        Random placement algorithm with gap/overlap constraints.
        
        Algorithm:
        1. Initialize empty placements list
        2. Determine time_window_end (use main_duration if not specified)
        3. For each occurrence (up to occurrence_count):
            a. Randomly select optional sound file from pool
            b. Detect and cache silence for selected file
            c. Randomly select duration between min_duration and max_duration
            d. Randomly select start_time within time_window
            e. Check constraints based on overlap_mode
            f. If constraints satisfied: add placement
            g. If constraints violated: retry with new random values (max 10 attempts)
            h. If max attempts exceeded: skip occurrence and log warning
        4. Sort placements by start_time ascending
        5. Return PlacementPlan
        
        Returns:
            PlacementPlan with sorted placements
            
        Raises:
            ValueError: If optional_sound_files is empty or main_duration is 0
            
        Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10
        """
        import random
        import sys
        
        # Get target duration directly from config
        self.main_duration = self.config.target_duration
        
        if self.main_duration <= 0:
            raise ValueError(f"Target duration must be > 0: {self.main_duration}")
            
        # If no optional sounds, just return an empty plan
        if not self.optional_sound_files:
            return PlacementPlan(
                version="1.0",
                main_sounds=self.config.main_sounds,
                optional_sounds_folder=self.config.optional_sounds_folder,
                target_duration=self.main_duration,
                placements=[]
            )
        
        # Determine time window end (use target_duration if not specified)
        time_window_start = self.config.time_window_start
        time_window_end = self.config.time_window_end
        
        if time_window_end == 0:
            time_window_end = self.main_duration
        
        # Validate time window
        if time_window_end <= time_window_start:
            raise ValueError(
                f"Invalid time window: end ({time_window_end}) must be > start ({time_window_start})"
            )
        
        if time_window_start < 0:
            raise ValueError(f"Invalid time window start: {time_window_start} (must be >= 0)")
        
        if time_window_end > self.main_duration:
            time_window_end = self.main_duration
        
        # Initialize placements list
        placements: List[Placement] = []
        
        # Select constraint checking function based on overlap_mode
        if self.config.overlap_mode == "none":
            check_constraint = self._check_overlap_constraint_none
        elif self.config.overlap_mode == "partial":
            check_constraint = self._check_overlap_constraint_partial
        elif self.config.overlap_mode == "full":
            check_constraint = self._check_overlap_constraint_full
        else:
            raise ValueError(
                f"Invalid overlap_mode: {self.config.overlap_mode}. "
                f"Must be 'none', 'partial', or 'full'"
            )
        
        # Generate placements
        max_attempts_per_occurrence = 10
        skipped_count = 0
        
        for occurrence_idx in range(self.config.occurrence_count):
            placed = False
            
            for attempt in range(max_attempts_per_occurrence):
                # Randomly select optional sound file
                source_file = random.choice(self.optional_sound_files)
                
                # Detect and cache silence
                try:
                    trimmed_start, trimmed_end = await self.detect_silence_cached(source_file)
                except Exception as e:
                    # If silence detection fails, skip this file and try another
                    print(
                        f"Warning: Silence detection failed for {source_file}: {e}",
                        file=sys.stderr
                    )
                    continue
                
                # Get source file duration
                try:
                    source_duration = await self.get_audio_duration(source_file)
                except Exception as e:
                    print(
                        f"Warning: Failed to get duration for {source_file}: {e}",
                        file=sys.stderr
                    )
                    continue
                
                # Calculate available duration after trimming
                available_duration = source_duration - trimmed_start - trimmed_end
                
                # Skip if file is entirely silence or too short
                if available_duration < 0.1:
                    print(
                        f"Warning: File is entirely silence or too short: {source_file}",
                        file=sys.stderr
                    )
                    continue
                
                # Randomly select duration between min_duration and max_duration
                # Constrain by available duration
                max_possible_duration = min(self.config.max_duration, available_duration)
                min_possible_duration = min(self.config.min_duration, max_possible_duration)
                
                if min_possible_duration > max_possible_duration:
                    # Cannot satisfy duration constraints with this file
                    continue
                
                duration = random.uniform(min_possible_duration, max_possible_duration)
                
                # Randomly select start_time within time_window
                # Ensure placement doesn't extend beyond time_window_end
                max_start_time = time_window_end - duration
                
                if max_start_time < time_window_start:
                    # Cannot fit placement in time window
                    continue
                
                start_time = random.uniform(time_window_start, max_start_time)
                
                # Check constraints
                if check_constraint(start_time, duration, placements):
                    # Constraints satisfied - add placement
                    placement = Placement(
                        source_file=source_file,
                        start_time=start_time,
                        duration=duration,
                        fade_in=self.config.fade_duration,
                        fade_out=self.config.fade_duration,
                        trimmed_start=trimmed_start,
                        trimmed_end=trimmed_end
                    )
                    placements.append(placement)
                    placed = True
                    break
            
            if not placed:
                # Max attempts exceeded - skip this occurrence
                skipped_count += 1
                print(
                    f"Warning: Could not place occurrence {occurrence_idx + 1} "
                    f"after {max_attempts_per_occurrence} attempts. Skipping.",
                    file=sys.stderr
                )
        
        # Log warning if some occurrences were skipped
        if skipped_count > 0:
            print(
                f"Warning: Could only place {len(placements)} of {self.config.occurrence_count} "
                f"occurrences due to time/gap constraints.",
                file=sys.stderr
            )
        
        # Sort placements by start_time ascending
        placements.sort(key=lambda p: p.start_time)
        
        # Create and return PlacementPlan
        plan = PlacementPlan(
            version="1.0",
            main_sounds=self.config.main_sounds,
            optional_sounds_folder=self.config.optional_sounds_folder,
            placements=placements
        )
        
        return plan
    
    def build_ffmpeg_command(self, plan: PlacementPlan, preview_mode: bool = False, preview_duration: float = 30.0) -> list:
        """
        Build FFmpeg command from placement plan.
        
        Constructs FFmpeg command with filter_complex for audio mixing.
        
        Command Structure:
        ffmpeg -y -i main.mp3 -i opt1.mp3 -i opt2.mp3 ... 
               -filter_complex "[complex_filter]" 
               -c:a aac -b:a 256k output.m4a
        
        Filter Complex Structure (example with 2 placements):
        
        # Trim silence and apply fades to each optional sound
        [1:a]atrim=start=0.5:end=8.3,asetpts=PTS-STARTPTS,
             afade=t=in:d=0.5,afade=t=out:st=7.3:d=0.5[opt1];
        
        [2:a]atrim=start=0.2:end=6.7,asetpts=PTS-STARTPTS,
             afade=t=in:d=0.5,afade=t=out:st=5.7:d=0.5[opt2];
        
        # Delay each optional sound to its start position
        [opt1]adelay=5000|5000[opt1_delayed];
        [opt2]adelay=12000|12000[opt2_delayed];
        
        # Mix main sound with all delayed optional sounds
        [0:a][opt1_delayed][opt2_delayed]amix=inputs=3:duration=first:normalize=0[aout]
        
        Key Filters:
        - atrim: Trim silence from start/end based on silence detection
        - asetpts: Reset timestamps after trim
        - afade: Apply fade-in (t=in) and fade-out (t=out) with triangular curve
        - adelay: Delay audio to start_time position (milliseconds, both channels)
        - amix: Mix multiple audio streams (normalize=0 to prevent auto-volume adjustment)
        
        Volume Normalization (to prevent clipping):
        - Calculate max_overlap_count (maximum simultaneous optional sounds)
        - Apply volume factor: 1/sqrt(max_overlap_count) to each optional sound
        - Example: If max 4 sounds overlap, volume = 1/sqrt(4) = 0.5
        - Insert volume filter before adelay: [opt1]volume=0.5[opt1_vol];[opt1_vol]adelay=...
        
        Args:
            plan: PlacementPlan object with placements
            
        Returns:
            List of command arguments for FFmpeg
            
        Requirements: 7.2, 7.3, 7.4, 7.5, 7.6, 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 19.1, 19.2, 19.3, 19.4
        """
        import math
        
        # Start building command
        cmd = ["ffmpeg", "-y"]
        
        # Apply preview mode constraint
        target_dur = self.config.target_duration
        if preview_mode:
            target_dur = min(target_dur, preview_duration)
            
        xfade = min(self.config.loop_xfade, target_dur * 0.4)
            
        # Add main sound inputs
        # Loop main sounds endlessly, they will be trimmed by atrim
        for main_sound in self.config.main_sounds:
            cmd.extend(["-stream_loop", "-1", "-i", main_sound["path"]])
            
        # Build map of unique source files to input indices
        unique_sources = {}
        input_index = len(self.config.main_sounds)  # Start after main sounds
        
        for placement in plan.placements:
            if placement.source_file not in unique_sources:
                unique_sources[placement.source_file] = input_index
                cmd.extend(["-i", placement.source_file])
                input_index += 1
        
        # If no main sounds provided, return early or error
        if not self.config.main_sounds:
            raise ValueError("No main sounds provided.")
        
        # Calculate max overlap count for volume normalization
        max_overlap_count = self._calculate_max_overlap_count(plan.placements)
        
        # Calculate volume normalization factor
        if max_overlap_count > 1:
            volume_factor = 1.0 / math.sqrt(max_overlap_count)
        else:
            volume_factor = 1.0
        
        # Build filter_complex chain
        filter_parts = []
        delayed_labels = []
        
        for idx, placement in enumerate(plan.placements):
            input_idx = unique_sources[placement.source_file]
            label = f"opt{idx}"
            
            # Calculate trim end time (start + duration after trimming)
            trim_end = placement.trimmed_start + placement.duration
            
            # Build filter chain for this placement:
            # 1. Trim silence from start/end
            # 2. Reset timestamps
            # 3. Apply fade-in
            # 4. Apply fade-out
            filter_chain = f"[{input_idx}:a]"
            filter_chain += f"atrim=start={placement.trimmed_start}:end={trim_end},"
            filter_chain += "asetpts=PTS-STARTPTS,"
            filter_chain += f"afade=t=in:d={placement.fade_in},"
            
            # Calculate fade-out start time (relative to trimmed audio)
            fade_out_start = placement.duration - placement.fade_out
            filter_chain += f"afade=t=out:st={fade_out_start}:d={placement.fade_out}"
            
            # Apply volume (user setting * overlap normalization factor)
            vol_val = (placement.volume / 100.0) * volume_factor
            if vol_val != 1.0:
                filter_chain += f",volume={vol_val:.3f}"
            
            filter_chain += f"[{label}]"
            filter_parts.append(filter_chain)
            
            # Add delay filter to position at start_time
            delay_ms = int(placement.start_time * 1000)
            delay_label = f"{label}_delayed"
            filter_parts.append(f"[{label}]adelay={delay_ms}|{delay_ms}[{delay_label}]")
            delayed_labels.append(delay_label)
        
        main_labels = []
        for i, ms in enumerate(self.config.main_sounds):
            label = f"main{i}"
            vol = ms.get("volume", 100) / 100.0
            
            # Trim to target duration, reset pts, apply fade out, apply volume
            chain = (
                f"[{i}:a]atrim=duration={target_dur:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=out:st={target_dur - xfade:.3f}:d={xfade:.3f}"
            )
            if vol != 1.0:
                chain += f",volume={vol}"
            chain += f"[{label}]"
            
            filter_parts.append(chain)
            main_labels.append(label)
        
        # Build amix filter to combine all main sounds with all delayed optional sounds
        amix_inputs = main_labels + delayed_labels
        amix_filter = "".join([f"[{label}]" for label in amix_inputs])
        
        if len(amix_inputs) > 1:
            amix_filter += f"amix=inputs={len(amix_inputs)}:duration=first:normalize=0[aout]"
            filter_parts.append(amix_filter)
        else:
            # Only one input, no need to mix, just rename label to [aout]
            # Actually, we can just map it directly later if it's the only one, 
            # but for simplicity we can use a dummy copy filter
            amix_filter += "acopy[aout]"
            filter_parts.append(amix_filter)
        
        # Join all filter parts with semicolons
        filter_complex = ";".join(filter_parts)
        
        # Add thread configuration (PO-01 & PO-02)
        from core.env import get_thread_flags
        cmd.extend(get_thread_flags())
        
        # Write filter complex to file on Windows or if it is very long to prevent command-line length limits (WinError 206)
        import tempfile
        import os
        
        out_dir = os.path.dirname(os.path.abspath(self.config.output_path)) if self.config.output_path else None
        if not out_dir or not os.path.exists(out_dir):
            out_dir = tempfile.gettempdir()
            
        try:
            fd, temp_file_path = tempfile.mkstemp(suffix=".txt", prefix="fc_sl_", dir=out_dir)
            os.close(fd)
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(filter_complex)
            if not hasattr(self, "temp_files"):
                self.temp_files = []
            self.temp_files.append(temp_file_path)
            cmd.extend(["-filter_complex_script", temp_file_path])
        except Exception as e:
            print(f"TEMPFILE ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            # Fallback to direct filter complex if temp file creation fails
            cmd.extend(["-filter_complex", filter_complex])
        
        # Map output audio
        cmd.extend(["-map", "[aout]"])
        
        # Add output codec arguments
        fmt = self.config.output_format.lower()
        if fmt == "wav":
            cmd.extend(["-c:a", "pcm_s24le"])
        else:
            # Default to AAC
            cmd.extend(["-c:a", "aac", "-b:a", "256k"])
        
        # Add output path
        cmd.append(self.config.output_path)
        
        return cmd
    
    def _calculate_max_overlap_count(self, placements: List[Placement]) -> int:
        """
        Calculate maximum number of simultaneous optional sounds at any point in time.
        
        This is used for volume normalization to prevent clipping when multiple
        sounds overlap.
        
        Algorithm:
        1. Create list of events: (time, +1 for start, -1 for end)
        2. Sort events by time
        3. Track current overlap count
        4. Return maximum overlap count seen
        
        Args:
            placements: List of Placement objects
            
        Returns:
            Maximum overlap count (minimum 1)
            
        Requirements: 19.2
        """
        if not placements:
            return 1
        
        # Create events: (time, delta)
        events = []
        for placement in placements:
            events.append((placement.start_time, 1))  # Start event
            events.append((placement.start_time + placement.duration, -1))  # End event
        
        # Sort events by time
        events.sort(key=lambda e: e[0])
        
        # Track current and maximum overlap count
        current_count = 0
        max_count = 0
        
        for time, delta in events:
            current_count += delta
            max_count = max(max_count, current_count)
        
        return max(1, max_count)
