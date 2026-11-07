# 🎵 ASMR Video Tool v2

Tool lokal untuk memproses video ASMR secara otomatis:
**Crop → Upscale → Loop video** + **Loop & normalize audio** + **Merge** + **Thumbnail**

Dibangun dengan FastAPI (backend) + vanilla JS ES Modules (frontend).

> Last sync: 2026-04-06

---

## ✅ Fitur

| Fitur | Detail |
|---|---|
| **Crop video** | Hapus N pixel dari atas/bawah/kiri/kanan |
| **Upscale** | Scale ke FHD / QHD / 4K (lanczos) |
| **Loop video** | Stream copy ke durasi target (tanpa re-encode) |
| **Loop audio** | Loop seamless acrossfade head-tail + fade in/out |
| **Merge** | Mux video + audio multi-layer (volume + pan per layer, stream copy bila memungkinkan) |
| **Thumbnail** | Ekstrak frame + preview langsung di browser |
| **Real-time log** | SSE streaming log FFmpeg per panel |
| **Auto-suggest path** | Output path otomatis terisi dari input |

---

## 🎧 Pembaruan Audio-First (Nov 2026)

ASMR intinya suara, jadi jalur audio diperbaiki dengan teknik dari repo ASMR lain:

- **Seamless loop benaran** (teknik `rakit_audio.sh` dari
  [setiajiekaputra01-cmd/tools-asmr](https://github.com/setiajiekaputra01-cmd/tools-asmr)):
  sumber dipotong head/tengah/tail, tail+head di-`acrossfade` menjadi tile
  loopable, lalu di-`aloop` sample-accurate (sampel dihitung dari
  sample_rate + duration_ts ffprobe). Crossfade adaptif: sumber ≤ 10 detik
  dibatasi 1 detik. Menggantikan `-stream_loop` lama yang hard-cut.
  Terukur: lonjakan amplitudo di sambungan turun dari 0.749 → 0.029.
- **Merge tanpa re-encode** (pola yang sama dari tools-asmr): 1 layer audio
  AAC tanpa pengolahan (volume 100%, pan tengah) kini di-`-c:a copy`.
- **Fade video per segmen**: fade-in/out pada pipeline video tidak lagi
  me-re-encode seluruh video. Hanya segmen kepala & ekor (kelipatan tile,
  ±15 detik) yang di-encode; bagian tengah stream copy lalu digabung
  (concat). Kualitas tengah identik bit-for-bit dan waktu render video
  panjang (1–3 jam) turun drastis. Target < 120 detik atau segmen tidak
  layak otomatis fallback ke fade penuh lama, dengan verifikasi durasi
  hasil sebelum selesai.
  Bila harus encode, bitrate AAC naik 192k → 320k.
- **Pan per layer** (dari [qipadd/asmr-mix-tools](https://github.com/qipadd/asmr-mix-tools)):
  setiap layer di Merge dan setiap placement + main sound di Sound Layer
  bisa ditempatkan Kiri / Tengah / Kanan di ruang stereo
  (`pan=stereo`, `amix normalize=0`), bukan cuma volume.
- Helper bersama di `core/audio_filters.py`, tes di `tests/test_audio_filters.py`.

---

## 🚀 Cara Pakai

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Jalankan server

```bash
# Windows
start.bat

# Manual
python server.py
```

### 3. Buka browser

```
http://localhost:8000
```

---

## 📱 Alur Kerja

```
Panel Kiri (Video)          Panel Tengah (Audio)        Panel Kanan (Merge)
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│ Browse video.mp4  │        │ Browse audio.mp3  │        │ Video (auto-fill) │
│ Probe info        │        │ Probe info        │        │ Audio (auto-fill) │
│ Set crop px       │        │ Set loop duration │   ►    │ Output path       │
│ Set upscale res   │        │ Set LUFS target   │        │ [Merge]           │
│ Set loop duration │        │ Set fade in/out   │        │                   │
│ [Proses Video]    │        │ [Proses Audio]    │        │ Thumbnail section │
└──────────────────┘        └──────────────────┘        └──────────────────┘
```

Setelah Video (✅) dan Audio (✅) selesai → path otomatis ter-fill di panel Merge.

---

## 📁 Struktur Proyek

```
asmr-tools/
├── server.py              # FastAPI entry point
├── start.bat              # Auto-setup & start (Windows)
├── requirements.txt
├── api/
│   ├── router.py           # Include semua sub-router
│   ├── probe.py            # /api/probe
│   ├── browse.py           # /api/browse, /api/browse-audio, /api/browse-folder
│   ├── video.py            # /api/video/pipeline (crop+upscale+loop)
│   ├── audio.py            # /api/audio/loop
│   ├── merge.py            # /api/merge
│   ├── thumbnail.py        # /api/thumbnail + /api/thumbnail/preview
│   ├── system.py           # /api/open-folder
│   └── utils.py            # fmt_duration, get_file_size_str, run_ffmpeg_stream
└── frontend/
    ├── index.html          # UI — 3-panel layout
    ├── style.css           # Dark design system
    └── js/
        ├── main.js         # Entry point
        ├── state.js        # Global state + emit()
        ├── api.js          # Semua fetch + SSE calls
        ├── ui.js           # Per-panel log, progress, toast
        ├── panel-video.js  # Logic panel Video
        ├── panel-audio.js  # Logic panel Audio
        └── panel-merge.js  # Logic panel Merge & Export
```

---

## 🔧 Requirements

- Python 3.10+
- FFmpeg + ffprobe (ada di PATH)
- Windows (browse dialog pakai `tkinter`)

```txt
fastapi
uvicorn
```

---

## 🎯 API Endpoints

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/api/probe` | Probe file video/audio |
| GET | `/api/browse` | Dialog pilih video |
| GET | `/api/browse-audio` | Dialog pilih audio |
| GET | `/api/browse-folder` | Dialog pilih folder |
| POST | `/api/video/pipeline` | Crop → Upscale → Loop (SSE) |
| POST | `/api/audio/loop` | Loop + normalize + fade (SSE) |
| POST | `/api/merge` | Merge video + audio (SSE) |
| POST | `/api/thumbnail` | Extract thumbnail (JSON) |
| GET | `/api/thumbnail/preview` | Serve thumbnail image |
| POST | `/api/open-folder` | Buka folder di Explorer |

---

## ⚠️ Troubleshooting

**Port 8000 sudah dipakai:**
```cmd
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

**FFmpeg tidak ditemukan:**
Pastikan `ffmpeg` dan `ffprobe` ada di PATH Windows.
Download: https://ffmpeg.org/download.html

**Browse dialog tidak muncul:**
Pastikan server dijalankan dari desktop (bukan SSH/headless), karena dialog butuh GUI.
