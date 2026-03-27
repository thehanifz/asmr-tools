@echo off
chcp 65001 >nul
title ASMR Video Tool

echo ============================================
echo   ASMR Video Tool - Auto Setup ^& Start
echo ============================================
echo.

:: Cek Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan! Install Python 3.10+ dulu.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python ditemukan

:: Cek FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg tidak ditemukan di PATH!
    echo Download: https://ffmpeg.org/download.html
    echo Lanjut tetapi processing tidak akan berjalan...
    echo.
) else (
    echo [OK] FFmpeg ditemukan
)

:: Buat venv jika belum ada
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Membuat virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Gagal membuat venv!
        pause
        exit /b 1
    )
    echo [OK] venv berhasil dibuat
)

:: Activate venv
call venv\Scripts\activate.bat
echo [OK] venv aktif

:: Cek dan install dependencies
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Menginstall dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Gagal install dependencies!
        pause
        exit /b 1
    )
    echo [OK] Dependencies terinstall
) else (
    echo [OK] Dependencies sudah terinstall
)

echo.
echo [START] Menjalankan server...
echo [INFO] Buka browser: http://localhost:8000
echo [INFO] Tekan Ctrl+C untuk stop server
echo.

:: Buka browser setelah 2 detik
start /B cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Jalankan server
python server.py

pause
