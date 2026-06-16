import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import asyncio
import subprocess

# Generate a 6-second dummy video with audio
def generate_dummy():
    print("Generating dummy 6-second video...")
    # duration = 6.0s, resolution = 640x360, audio = 48000Hz stereo
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=25",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", "test_input.mp4"
    ], capture_output=True)
    print("test_input.mp4 generated successfully.")


async def test_probe():
    print("\n--- Testing Probing of Input ---")
    from api.concat import probe_single_video
    info = probe_single_video("test_input.mp4")
    print("Input Info:", json.dumps(info, indent=2))
    assert info["duration"] == 6.0
    assert info["has_audio"] is True
    assert info["has_video"] is True


async def test_loop_ba_hard_cut():
    print("\n--- Testing Loop B+A Hard Cut (fast split + copy) ---")
    from api.loop_ba import render_loop_ba
    class DummyRequest:
        async def json(self):
            return {
                "input_path": "test_input.mp4",
                "transition_type": "hard_cut",
                "output_path": "test_out_hard_cut.mp4"
            }
            
    response = await render_loop_ba(DummyRequest())
    print("Response type:", type(response))
    
    async for chunk in response.body_iterator:
        val = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        print("SSE chunk:", val.strip())
        
    assert os.path.exists("test_out_hard_cut.mp4")
    
    # Probe final output to verify it has NO audio
    from api.concat import probe_single_video
    out_info = probe_single_video("test_out_hard_cut.mp4")
    print("Output Hard Cut Info:", json.dumps(out_info, indent=2))
    assert out_info["has_audio"] is False
    assert out_info["has_video"] is True
    # Due to keyframes split-seek, duration might vary slightly but it should be close to 6.0s
    assert abs(out_info["duration"] - 6.0) < 1.0


async def test_loop_ba_crossfade():
    print("\n--- Testing Loop B+A Crossfade (re-encode) ---")
    from api.loop_ba import render_loop_ba
    class DummyRequest:
        async def json(self):
            return {
                "input_path": "test_input.mp4",
                "transition_type": "crossfade",
                "transition_duration": 1.0,
                "output_path": "test_out_xfade.mp4"
            }
            
    response = await render_loop_ba(DummyRequest())
    
    async for chunk in response.body_iterator:
        val = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        print("SSE chunk:", val.strip())
        
    assert os.path.exists("test_out_xfade.mp4")
    
    from api.concat import probe_single_video
    out_info = probe_single_video("test_out_xfade.mp4")
    print("Output Crossfade Info:", json.dumps(out_info, indent=2))
    assert out_info["has_audio"] is False
    assert out_info["has_video"] is True
    # Output duration should be total_duration - transition_duration = 6.0 - 1.0 = 5.0s
    assert abs(out_info["duration"] - 5.0) < 0.2
    print("Crossfade duration verified successfully.")


def cleanup():
    print("\nCleaning up temp files...")
    for f in ["test_input.mp4", "test_out_hard_cut.mp4", "test_out_xfade.mp4"]:
        if os.path.exists(f):
            os.remove(f)
    print("Cleanup done.")


async def main():
    generate_dummy()
    try:
        await test_probe()
        await test_loop_ba_hard_cut()
        await test_loop_ba_crossfade()
        print("\nALL LOOP B+A TESTS PASSED SUCCESSFULLY!")
    finally:
        cleanup()

if __name__ == "__main__":
    asyncio.run(main())
