#!/bin/bash
echo "============================================"
echo "  ASMR Video Tool - Auto Setup & Start"
echo "============================================"
echo

# Cek Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 tidak ditemukan!"
    echo "Install: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
echo "[OK] Python3 ditemukan: $(python3 --version)"

# Cek FFmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "[WARNING] FFmpeg tidak ditemukan!"
    echo "Install: sudo apt install ffmpeg"
else
    echo "[OK] FFmpeg ditemukan"
fi

# Buat venv jika belum ada
if [ ! -f "venv/bin/activate" ]; then
    echo "[SETUP] Membuat virtual environment..."
    python3 -m venv venv
    echo "[OK] venv dibuat"
fi

# Activate venv
source venv/bin/activate
echo "[OK] venv aktif"

# Install dependencies jika belum
if ! python -c "import fastapi" &>/dev/null; then
    echo "[SETUP] Menginstall dependencies..."
    pip install -r requirements.txt
    echo "[OK] Dependencies terinstall"
else
    echo "[OK] Dependencies sudah terinstall"
fi

echo
echo "[START] Menjalankan server..."
echo "[INFO] Buka browser: http://localhost:8000"
echo

# Buka browser
(sleep 2 && xdg-open http://localhost:8000 2>/dev/null || true) &

# Jalankan server
python server.py
