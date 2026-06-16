import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import asyncio
import subprocess
import shutil

# Generate dummy video clips using ffmpeg lavfi
def generate_dummies():
    print("Generating dummy video files...")
    # clip 1: 640x360, duration 3s, with audio
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=640x360:rate=25",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "clip1.mp4"
    ], capture_output=True)

    # clip 2: 640x360 (identical format), duration 2s, with audio
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=640x360:rate=25",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "clip2.mp4"
    ], capture_output=True)

    # clip 3: 320x180 (different resolution), duration 2s, with audio
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x180:rate=25",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "clip3.mp4"
    ], capture_output=True)
    print("Dummy files generated successfully.")


async def test_probing():
    print("\n--- Testing Probing ---")
    from api.concat import probe_single_video
    
    info1 = probe_single_video("clip1.mp4")
    print("Clip 1 Info:", json.dumps(info1, indent=2))
    assert info1["width"] == 640
    assert info1["height"] == 360
    assert info1["duration"] == 3.0
    
    info3 = probe_single_video("clip3.mp4")
    print("Clip 3 Info:", json.dumps(info3, indent=2))
    assert info3["width"] == 320
    assert info3["height"] == 180


async def test_identical_hard_cut():
    print("\n--- Testing Identical format Hard Cut ---")
    from api.concat import render_concat
    # We will mock Request object
    class DummyRequest:
        async def json(self):
            return {
                "video_paths": ["clip1.mp4", "clip2.mp4"],
                "transition_type": "hard_cut",
                "output_path": "output_hard_cut_fast.mp4"
            }
    
    response = await render_concat(DummyRequest())
    print("Response type:", type(response))
    
    # Read stream chunks
    async for chunk in response.body_iterator:
        val = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        print("SSE chunk:", val.strip())
        
    assert os.path.exists("output_hard_cut_fast.mp4")
    print("output_hard_cut_fast.mp4 created successfully.")


async def test_mismatched_hard_cut():
    print("\n--- Testing Mismatched format Hard Cut (should re-encode to smallest resolution) ---")
    from api.concat import render_concat
    class DummyRequest:
        async def json(self):
            return {
                "video_paths": ["clip1.mp4", "clip3.mp4"],
                "transition_type": "hard_cut",
                "output_path": "output_hard_cut_reencode.mp4"
            }
            
    response = await render_concat(DummyRequest())
    async for chunk in response.body_iterator:
         val = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
         print("SSE chunk:", val.strip())
         
    assert os.path.exists("output_hard_cut_reencode.mp4")
    from api.concat import probe_single_video
    info = probe_single_video("output_hard_cut_reencode.mp4")
    print("Output resolution:", info["width"], "x", info["height"])
    # Smallest input resolution is 320x180 (clip3.mp4)
    assert info["width"] == 320
    assert info["height"] == 180
    print("Mismatched format successfully scaled to smallest resolution.")


async def test_crossfade():
    print("\n--- Testing Crossfade (should re-encode and merge with crossfade) ---")
    from api.concat import render_concat
    class DummyRequest:
        async def json(self):
            return {
                "video_paths": ["clip1.mp4", "clip2.mp4"],
                "transition_type": "crossfade",
                "transition_duration": 1.0,
                "output_path": "output_crossfade.mp4"
            }
            
    response = await render_concat(DummyRequest())
    async for chunk in response.body_iterator:
         val = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
         print("SSE chunk:", val.strip())
         
    assert os.path.exists("output_crossfade.mp4")
    print("output_crossfade.mp4 created successfully.")


def cleanup():
    print("\nCleaning up temp files...")
    for f in ["clip1.mp4", "clip2.mp4", "clip3.mp4", "output_hard_cut_fast.mp4", "output_hard_cut_reencode.mp4", "output_crossfade.mp4"]:
        if os.path.exists(f):
            os.remove(f)
    print("Cleanup done.")


async def main():
    generate_dummies()
    try:
        await test_probing()
        await test_identical_hard_cut()
        await test_mismatched_hard_cut()
        await test_crossfade()
        print("\nALL TESTS PASSED SUCCESSFULLY!")
    finally:
        cleanup()

if __name__ == "__main__":
    asyncio.run(main())
