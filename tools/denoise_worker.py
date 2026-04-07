"""Denoise worker — run via: py -3.12 tools/denoise_worker.py <input> <output> <strength> <chunk>

Requirements (install once):
    py -3.12 -m pip install noisereduce scipy soundfile
"""
import sys
import json

def main():
    if len(sys.argv) < 5:
        print(json.dumps({"error": "Usage: denoise_worker.py <input> <output> <strength> <chunk>"}))
        sys.exit(1)

    input_path  = sys.argv[1]
    output_path = sys.argv[2]
    strength    = float(sys.argv[3])
    chunk_size  = int(sys.argv[4])

    try:
        import noisereduce as nr
        import soundfile as sf
    except ImportError as e:
        print(json.dumps({"error": f"Missing dependency: {e}. Run: py -3.12 -m pip install noisereduce scipy soundfile"}))
        sys.exit(1)

    data, rate = sf.read(input_path)

    # Handle stereo (prevents 147 GB memory error)
    if data.ndim == 2:
        y       = data.T                    # (channels, samples)
        noise   = y[:, :rate]               # first second as noise profile
    else:
        y       = data
        noise   = y[:rate]

    reduced = nr.reduce_noise(
        y=y,
        sr=rate,
        y_noise=noise,
        prop_decrease=strength,
        chunk_size=chunk_size,
        padding=1000,
    )

    # Write back
    if data.ndim == 2:
        sf.write(output_path, reduced.T, rate)
    else:
        sf.write(output_path, reduced, rate)

    print(json.dumps({"status": "done", "output": output_path}))


if __name__ == "__main__":
    main()
