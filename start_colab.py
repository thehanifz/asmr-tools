"""Entrypoint khusus Google Colab.

Cara pakai di notebook:
    !git clone https://github.com/thehanifz/asmr-tools
    %cd asmr-tools
    !pip install -r requirements.txt -r requirements-colab.txt
    !python start_colab.py
"""
import os
import sys
import time
import subprocess
import threading

print("🚀 ASMR Tools — Colab Startup")
print("-" * 40)

# ── 1. Mount Google Drive ──────────────────────────────────────────────────────
print("📂 Mounting Google Drive...")
from google.colab import drive
drive.mount("/content/drive")

# Buat folder struktur di Drive
for folder in [
    "/content/drive/MyDrive/RIFE/models",
    "/content/drive/MyDrive/RIFE/outputs",
    "/content/drive/MyDrive/RIFE/input",
    "/content/temp_video",
]:
    os.makedirs(folder, exist_ok=True)
print("✅ Google Drive siap.")

# ── 2. Clone / Update Practical-RIFE ─────────────────────────────────────────
RIFE_DIR = "/content/Practical-RIFE"
if not os.path.isdir(RIFE_DIR):
    print("📥 Cloning Practical-RIFE...")
    subprocess.run(
        ["git", "clone", "-q", "https://github.com/hzwer/Practical-RIFE.git", RIFE_DIR],
        check=True
    )
    print("✅ Practical-RIFE berhasil di-clone.")
else:
    print("✅ Practical-RIFE sudah ada, skip clone.")

# ── 3. Patch NumPy deprecated aliases di RIFE ────────────────────────────────
print("🔧 Patching inference_video.py untuk NumPy >= 1.24...")
inference_path = os.path.join(RIFE_DIR, "inference_video.py")
if os.path.isfile(inference_path):
    with open(inference_path, "r") as f:
        content = f.read()
    content = content.replace("np.float = float", "np.float = np.float64")
    content = content.replace("np.int = int", "np.int = np.int64")
    content = content.replace("np.bool = bool", "np.bool = np.bool_")
    with open(inference_path, "w") as f:
        f.write(content)
    print("✅ Patch inference_video.py selesai.")

# ── 4. Patch scikit-video ─────────────────────────────────────────────────────
print("🔧 Patching scikit-video...")
import glob
count = 0
for pyfile in glob.glob("/usr/local/lib/python3.*/dist-packages/skvideo/**/*.py", recursive=True):
    with open(pyfile, "r", encoding="utf-8") as f:
        src = f.read()
    patched = src.replace("np.float(", "float(").replace("np.int(", "int(")
    if patched != src:
        with open(pyfile, "w", encoding="utf-8") as f:
            f.write(patched)
        count += 1
print(f"✅ Patched {count} file skvideo.")

# ── 5. Symlink Model RIFE dari Drive ──────────────────────────────────────────
gdrive_model = "/content/drive/MyDrive/RIFE/models/train_log"
local_model  = os.path.join(RIFE_DIR, "train_log")
if os.path.isdir(gdrive_model):
    if os.path.exists(local_model) or os.path.islink(local_model):
        subprocess.run(["rm", "-rf", local_model])
    os.symlink(gdrive_model, local_model)
    print("✅ Model RIFE terhubung dari Drive.")
else:
    print("⚠️  Model RIFE belum ada di Drive (MyDrive/RIFE/models/train_log).")
    print("   RIFE tidak akan tersedia sampai model di-upload.")

# ── 6. Install cloudflared ────────────────────────────────────────────────────
if not os.path.exists("/usr/local/bin/cloudflared"):
    print("📥 Menginstal cloudflared...")
    subprocess.run([
        "wget", "-q",
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        "-O", "/usr/local/bin/cloudflared"
    ], check=True)
    subprocess.run(["chmod", "+x", "/usr/local/bin/cloudflared"])
    print("✅ cloudflared terinstal.")
else:
    print("✅ cloudflared sudah ada.")

# ── 7. Start Cloudflare Tunnel ────────────────────────────────────────────────
try:
    from google.colab import userdata
    CF_TOKEN = userdata.get("token_cf")
except Exception:
    CF_TOKEN = os.environ.get("CF_TOKEN", "")

if not CF_TOKEN:
    print("⚠️  Secret 'token_cf' tidak ditemukan. Tunnel tidak akan aktif.")
    print("   App hanya bisa diakses via localhost:8000 di dalam Colab.")
else:
    def _run_tunnel():
        subprocess.run([
            "cloudflared", "tunnel", "--no-autoupdate",
            "run", "--token", CF_TOKEN
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    tunnel_thread = threading.Thread(target=_run_tunnel, daemon=True)
    tunnel_thread.start()
    time.sleep(3)  # Tunggu tunnel establish

    # Inject public URL ke environment agar core/env.py bisa baca
    public_url = os.environ.get("ASMR_PUBLIC_URL", "https://run.thehanifz.fun")
    os.environ["ASMR_PUBLIC_URL"] = public_url
    print(f"✅ Tunnel aktif: {public_url}")

# ── 8. Refresh HAS_RIFE setelah setup selesai ────────────────────────────────
# Reimport env agar deteksi RIFE menggunakan state terbaru
import importlib
if "core.env" in sys.modules:
    import core.env as env_mod
    env_mod.HAS_RIFE = env_mod._check_rife()

# ── 9. Jalankan ASMR Tools server ────────────────────────────────────────────
print()
print("=" * 40)
print("🎵 Starting ASMR Tools server...")
print("=" * 40)

os.system("fuser -k 8000/tcp 2>/dev/null")
time.sleep(1)

import uvicorn
uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
