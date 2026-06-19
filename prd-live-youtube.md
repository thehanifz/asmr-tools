# Product Requirements Document (PRD) — Fitur Live to YouTube (ASMR Loop Streamer)

| Field | Details |
|---|---|
| **Feature Name** | Live to YouTube (ASMR Loop Streamer) |
| **Status** | Draft |
| **Author** | Antigravity AI |
| **Versi** | 1.1 |
| **Tanggal** | 19 Juni 2026 |
| **Target Tool** | Live Panel (`#tool-live`) |

---

## 1. Overview & Executive Summary

Fitur **Live to YouTube** memungkinkan creator ASMR melakukan live streaming ke YouTube dengan memutar video secara loop tanpa henti hingga tombol Stop ditekan. Video dan audio berjalan **independen** — masing-masing di-loop sendiri tanpa sinkronisasi durasi. User dapat memilih video dari file lokal atau library app, menambahkan audio terpisah (opsional), mengisi Stream Key, memilih kualitas, lalu mulai stream. Backend menggunakan FFmpeg dengan RTMP push ke YouTube. Auto-reconnect aktif jika koneksi terputus sementara.

---

## 2. Problem Statement

Creator ASMR sering melakukan live stream berjam-jam dengan loop video ambient + audio terpisah (misalnya: video api unggun + audio hujan). Saat ini mereka harus setup OBS dengan multiple source, audio mixer, dan stream settings — kompleks untuk task yang sebenarnya sederhana. ASMR Tools dapat menyelesaikan ini dalam satu panel tanpa konfigurasi rumit, dengan video dan audio loop independen sehingga creator bebas memilih kombinasi apapun tanpa khawatir sinkronisasi durasi.

---

## 3. Goals & Success Metrics (KPI/OKR)

| Tujuan | Metrik Sukses |
|---|---|
| Gantikan OBS untuk use case loop sederhana | User bisa mulai live stream dalam < 3 menit dari buka panel |
| Stream stabil dengan auto-reconnect | Koneksi pulih otomatis dalam < 30 detik setelah network blip |
| Library mudah dikelola | Tambah/hapus video & audio dalam < 30 detik |
| Kualitas terkontrol | User memilih kualitas tanpa error konfigurasi |

---

## 4. Target Users & Personas

**Persona — ASMR Live Streamer**
- Rutin live stream konten ambient/ASMR di YouTube berjam-jam
- Ingin kombinasi video + audio yang fleksibel (video api + audio hujan, dll.)
- Tidak ingin setup OBS yang kompleks
- Pain point: OBS terlalu berat, multi-source setup memakan waktu hanya untuk loop 2 file

---

## 5. Scope

### ✅ In-Scope (v1)
- 2 sumber video: **File Lokal** (upload saat itu) & **Library App** (`media/video/`)
- 3 sumber audio: **Audio dari Video** (gunakan audio track video) / **Audio Terpisah** (file dari `media/audio/`) / **Tanpa Audio (Mute)**
- Manajemen Library Video (`media/video/`): tambah, hapus, lihat daftar
- Manajemen Library Audio (`media/audio/`): tambah, hapus, lihat daftar
- Video dan audio di-loop **independen** — masing-masing loop sendiri, berhenti hanya saat Stop
- Input Stream Key (per sesi, **tidak disimpan ke disk**)
- Input RTMP URL (pre-filled, editable)
- Dropdown kualitas stream (dinamis berdasarkan resolusi video)
- Auto-reconnect RTMP (retry setiap 5 detik, tanpa batas, hingga berhasil atau Stop)
- Status indicator real-time via SSE: `Idle` / `Connecting` / `Reconnecting` / `🔴 Live` / `Error`
- Live duration counter (HH:MM:SS)
- Log output FFmpeg real-time (collapsible, stream key di-mask)

### ❌ Out-of-Scope (v1 — kandidat v2/v3)
- OAuth / YouTube API login (judul stream, jadwal)
- Multi-platform streaming (Twitch, Facebook)
- Playlist loop (beberapa video bergantian)
- Audio mixing / volume control per track
- Overlay teks / watermark
- Notifikasi desktop
- Simpan Stream Key antar sesi

---

## 6. User Stories & Acceptance Criteria

### US-01 — Pilih Sumber Video
> *As a creator, I want to choose a video from local file or app library, so that I can quickly start streaming without re-uploading every time.*

**Acceptance Criteria:**
- [ ] Radio button: **"File Lokal"** vs **"Library App"**
- [ ] File Lokal: file picker (MP4, MKV, MOV), tampilkan nama/durasi/resolusi setelah dipilih
- [ ] Library App: tampilkan daftar video dari `media/video/` dengan thumbnail, nama, durasi, resolusi
- [ ] Dropdown kualitas diupdate otomatis berdasarkan resolusi video yang dipilih

---

### US-02 — Pilih Sumber Audio
> *As a creator, I want to control the audio source independently from video, so that I can combine any video with any audio without worrying about duration sync.*

**Acceptance Criteria:**
- [ ] 3 pilihan sumber audio (radio button):
  - **"Audio dari Video"** — gunakan audio track bawaan video
  - **"Audio Terpisah"** — pilih file dari library `media/audio/` (MP3, WAV, M4A, FLAC)
  - **"Tanpa Audio (Mute)"** — stream tanpa audio (FFmpeg generate silent audio via `anullsrc`)
- [ ] Jika **"Audio Terpisah"**: tampilkan daftar file dari `media/audio/` dengan nama, durasi, format
- [ ] Video dan audio di-loop **independen** — masing-masing loop sendiri tanpa sinkronisasi
- [ ] Jika pilih "Audio dari Video" tapi video tidak punya audio track → auto-fallback ke Mute + warning
- [ ] Kedua loop hanya berhenti saat tombol **Stop Live** ditekan

---

### US-03 — Kelola Library Video & Audio
> *As a creator, I want to manage video and audio files in the app library, so that my streaming content is organized and ready to use.*

**Acceptance Criteria:**
- [ ] Section terpisah untuk **Library Video** (`media/video/`) dan **Library Audio** (`media/audio/`)
- [ ] Tombol **"+ Tambah"** di masing-masing library untuk upload file baru
- [ ] Tombol **"🗑 Hapus"** per item dengan konfirmasi dialog
- [ ] Library persisten antar restart app (metadata di `media/video/index.json` dan `media/audio/index.json`)
- [ ] Thumbnail video = frame pertama (generated via FFmpeg saat upload)
- [ ] Audio: tampilkan icon + nama + durasi + format (tidak perlu thumbnail)

---

### US-04 — Konfigurasi Stream
> *As a creator, I want to configure stream quality and credentials, so that my stream goes to the right channel at the right quality.*

**Acceptance Criteria:**
- [ ] Input **RTMP URL** (pre-filled: `rtmp://a.rtmp.youtube.com/live2`, editable)
- [ ] Input **Stream Key** (tipe `password`, toggle show/hide 👁, tidak disimpan ke disk)
- [ ] Stream Key di-mask sebagai `****STREAM_KEY****` di semua log output
- [ ] Dropdown **Kualitas Stream** dinamis:

| Resolusi Video | Opsi Tersedia |
|---|---|
| 1080p+ | 1080p (8 Mbps), 720p (5 Mbps), 480p (2.5 Mbps) |
| 720p | 720p (5 Mbps), 480p (2.5 Mbps) |
| < 720p | 480p (2.5 Mbps), 360p (1 Mbps) |

- [ ] Warning UI jika pilih 1080p: "Membutuhkan koneksi upload ≥ 10 Mbps"
- [ ] Tombol **"Mulai Live"** disabled jika video atau stream key belum diisi

---

### US-05 — Live Stream dengan Auto-Reconnect
> *As a creator, I want the stream to automatically reconnect if the connection drops, so that my live doesn't end unexpectedly due to a temporary network issue.*

**Acceptance Criteria:**
- [ ] Klik **"Mulai Live"** → status: `Connecting...`
- [ ] Setelah FFmpeg terhubung → status: `🔴 LIVE`, timer berjalan
- [ ] Jika koneksi terputus → status: `🔄 Reconnecting...`, FFmpeg restart otomatis
- [ ] Auto-reconnect: retry setiap 5 detik, tanpa batas, hingga berhasil atau Stop ditekan
- [ ] Setiap attempt reconnect tercatat di log: `[HH:MM:SS] Koneksi terputus, mencoba reconnect... (attempt #N)`
- [ ] Klik **"Stop Live"** → FFmpeg dihentikan permanen, status: `Idle`, timer reset

---

## 7. Functional Requirements

| ID | Requirement | Prioritas |
|---|---|---|
| FR-01 | Dua sumber video: File Lokal & Library App | Must Have |
| FR-02 | Tiga sumber audio: Audio Video / Audio Terpisah / Mute | Must Have |
| FR-03 | Video dan audio loop independen, berhenti saat Stop | Must Have |
| FR-04 | Library Video (`media/video/`): tambah, hapus, daftar | Must Have |
| FR-05 | Library Audio (`media/audio/`): tambah, hapus, daftar | Must Have |
| FR-06 | Library persisten via `index.json` per folder | Must Have |
| FR-07 | Thumbnail video auto-generated saat upload | Must Have |
| FR-08 | Input RTMP URL (pre-filled, editable) | Must Have |
| FR-09 | Input Stream Key (password + show/hide, tidak disimpan disk) | Must Have |
| FR-10 | Stream Key di-mask di semua log | Must Have |
| FR-11 | Dropdown kualitas dinamis berdasarkan resolusi video | Must Have |
| FR-12 | Tombol Mulai Live + Stop Live | Must Have |
| FR-13 | Auto-reconnect RTMP (retry setiap 5 detik, tanpa batas) | Must Have |
| FR-14 | Status SSE real-time: Idle/Connecting/Reconnecting/Live/Error | Must Have |
| FR-15 | Timer durasi live (HH:MM:SS) | Must Have |
| FR-16 | Log FFmpeg real-time collapsible (stream key di-mask) | Should Have |
| FR-17 | Validasi FFmpeg libx264 tersedia saat startup | Must Have |
| FR-18 | PID tracking + zombie process cleanup saat app restart | Must Have |
| FR-19 | Warning UI jika pilih bitrate tinggi (1080p ≥ 10 Mbps) | Should Have |
| FR-20 | Auto-fallback ke Mute jika video tidak punya audio track | Must Have |

---

## 8. Non-Functional Requirements

- **Security:** Stream Key hanya di memory session, tidak pernah ditulis ke disk atau muncul di log dalam bentuk plain text. Masking wajib di semua output teks.
- **Stability:** Auto-reconnect tanpa batas dengan jeda 5 detik antar retry. FFmpeg menggunakan flag `-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5` untuk RTMP resilience.
- **Performance:** Encode menggunakan `libx264 preset veryfast` — CPU usage < 80% pada hardware standar. Video dan audio loop independen dihandle sebagai dua input `-stream_loop -1` terpisah di FFmpeg.
- **Compatibility:** Output H.264 + AAC — kompatibel penuh dengan YouTube Live. Silent audio (`anullsrc`) untuk mode Mute.
- **Error Handling:** Semua error FFmpeg/network diterjemahkan ke pesan Bahasa Indonesia yang actionable di log real-time.

---

## 9. Technical Considerations

Stack: **FastAPI (Python) + FFmpeg + Frontend HTML/JS**

### Struktur Folder Baru
```
media/
├── video/
│   ├── index.json          ← metadata library video
│   ├── rain_loop.mp4
│   ├── thumbs/
│   │   └── rain_loop.jpg   ← thumbnail frame pertama
│   └── ...
└── audio/
    ├── index.json          ← metadata library audio
    ├── rain_sound.mp3
    └── ...
```

### File Baru
- `api/live.py` — router, stream logic, library management

### Daftarkan di `api/router.py`
```python
from api import live
router.include_router(live.router)
```

### Endpoint API

| Method | Endpoint | Fungsi |
|---|---|---|
| `POST` | `/api/live/start` | Mulai stream |
| `POST` | `/api/live/stop` | Stop stream |
| `GET` | `/api/live/status/stream` | SSE status real-time |
| `GET` | `/api/live/library/video` | Daftar library video |
| `POST` | `/api/live/library/video/add` | Upload video ke library |
| `DELETE` | `/api/live/library/video/{filename}` | Hapus video dari library |
| `GET` | `/api/live/library/audio` | Daftar library audio |
| `POST` | `/api/live/library/audio/add` | Upload audio ke library |
| `DELETE` | `/api/live/library/audio/{filename}` | Hapus audio dari library |

### Perintah FFmpeg — 3 Mode Audio

**Mode 1: Audio dari Video**
```bash
ffmpeg \
  -stream_loop -1 -re -i "{video_path}" \
  -c:v libx264 -preset veryfast \
  -b:v {bitrate} -maxrate {bitrate} -bufsize {bufsize} \
  -vf "scale={width}:{height}" -r 30 \
  -c:a aac -b:a 128k -ar 44100 \
  -f flv "{rtmp_url}/{stream_key}"
```

**Mode 2: Audio Terpisah (loop independen)**
```bash
ffmpeg \
  -stream_loop -1 -re -i "{video_path}" \
  -stream_loop -1 -i "{audio_path}" \
  -map 0:v -map 1:a \
  -c:v libx264 -preset veryfast \
  -b:v {bitrate} -maxrate {bitrate} -bufsize {bufsize} \
  -vf "scale={width}:{height}" -r 30 \
  -c:a aac -b:a 128k -ar 44100 \
  -f flv "{rtmp_url}/{stream_key}"
# Video dan audio masing-masing -stream_loop -1 → loop independen
# Output berjalan hingga proses di-SIGTERM (Stop Live)
```

**Mode 3: Mute (silent audio)**
```bash
ffmpeg \
  -stream_loop -1 -re -i "{video_path}" \
  -f lavfi -i anullsrc=r=44100:cl=stereo \
  -map 0:v -map 1:a \
  -c:v libx264 -preset veryfast \
  -b:v {bitrate} -maxrate {bitrate} -bufsize {bufsize} \
  -vf "scale={width}:{height}" -r 30 \
  -c:a aac -b:a 128k \
  -f flv "{rtmp_url}/{stream_key}"
```

### Auto-Reconnect Logic
```python
async def stream_with_reconnect(config: dict, stream_key: str):
    attempt = 0
    global stop_requested
    stop_requested = False

    while not stop_requested:
        attempt += 1
        log(f"[{now()}] Memulai stream (attempt #{attempt})...")
        update_status("connecting")

        process = await start_ffmpeg(config, stream_key)
        await process.wait()

        if stop_requested:
            log(f"[{now()}] Stream dihentikan oleh user.")
            update_status("idle")
            break

        log(f"[{now()}] Koneksi terputus. Reconnect dalam 5 detik... (attempt #{attempt + 1})")
        update_status("reconnecting")
        await asyncio.sleep(5)
```

### Stream Key Masking
```python
def mask_log(line: str, stream_key: str) -> str:
    if stream_key and stream_key in line:
        return line.replace(stream_key, "****STREAM_KEY****")
    return line
```

### Konfigurasi Kualitas
```python
QUALITY_PRESETS = {
    "1080p": {"width": 1920, "height": 1080, "bitrate": "8000k", "bufsize": "16000k"},
    "720p":  {"width": 1280, "height": 720,  "bitrate": "5000k", "bufsize": "10000k"},
    "480p":  {"width": 854,  "height": 480,  "bitrate": "2500k", "bufsize": "5000k"},
    "360p":  {"width": 640,  "height": 360,  "bitrate": "1000k", "bufsize": "2000k"},
}

def get_quality_options(video_height: int) -> list:
    if video_height >= 1080:
        return ["1080p", "720p", "480p"]
    elif video_height >= 720:
        return ["720p", "480p"]
    else:
        return ["480p", "360p"]
```

### SSE Status Stream
```python
@router.get("/api/live/status/stream")
async def live_status_sse():
    async def event_generator():
        while True:
            yield f"data: {json.dumps(get_live_status())}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
# Heartbeat ping setiap 15 detik untuk cegah SSE timeout
```

---

## 10. UI/UX Requirements & Wireframe Notes

```
┌──────────────────────────────────────────────────────┐
│  📡 LIVE TO YOUTUBE                                  │
├──────────────────────────────────────────────────────┤
│                                                      │
│  [VIDEO] ─────────────────────────────────────────  │
│  Sumber: ● File Lokal  ○ Library App                │
│                                                      │
│  Library Video:                   [+ Tambah Video]  │
│  ┌────────────────────────────────────────────────┐ │
│  │[▶] rain_loop.mp4    05:00  1080p  250MB   [🗑] │ │
│  │[▶] forest_loop.mp4  08:00  1080p  400MB   [🗑] │ │
│  │[▶] fire_loop.mp4    03:30   720p  180MB   [🗑] │ │
│  └────────────────────────────────────────────────┘ │
│  ✓ Dipilih: rain_loop.mp4 (1080p, 05:00)            │
│                                                      │
│  [AUDIO] ─────────────────────────────────────────  │
│  Sumber Audio:                                       │
│  ○ Audio dari Video  ● Audio Terpisah  ○ Mute        │
│                                                      │
│  Library Audio:                   [+ Tambah Audio]  │
│  ┌────────────────────────────────────────────────┐ │
│  │ ♪ rain_sound.mp3   10:00  MP3   8MB      [🗑] │ │
│  │ ♪ thunder.wav      05:30  WAV  45MB      [🗑] │ │
│  └────────────────────────────────────────────────┘ │
│  ✓ Dipilih: rain_sound.mp3 (loop independen 🔁)     │
│                                                      │
│  [KONFIGURASI] ───────────────────────────────────  │
│  Kualitas:  [ 1080p (8 Mbps)                  ▼ ]  │
│  ⚠ Membutuhkan koneksi upload ≥ 10 Mbps            │
│  RTMP URL:  [ rtmp://a.rtmp.youtube.com/live2    ] │
│  Stream Key:[ ●●●●●●●●●●●●●●●●●●●●●      👁 ]    │
│                                                      │
│  ──────────────────────────────────────────────────  │
│  [ 🔴 Mulai Live ]          [ ⏹ Stop Live ]        │
│                                                      │
│  Status: 🔴 LIVE  •  01:24:38                       │
│  Video: rain_loop.mp4 🔁  |  Audio: rain_sound.mp3 🔁│
│                                                      │
│  ▼ Log Output [collapsible]                         │
│  ┌────────────────────────────────────────────────┐ │
│  │[01:24:35] frame=152480 fps=30 bitrate=8011k/s  │ │
│  │[01:24:36] Streaming ke rtmp://a.rtmp.you...    │ │
│  │[01:24:37] Video loop #18 | Audio loop #9       │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

**Catatan UI:**
- Status bar warna: abu-abu (Idle), kuning pulse (Connecting/Reconnecting), merah solid (🔴 Live)
- Saat `Reconnecting`: tampilkan `🔄 Reconnecting... attempt #3 (5 detik lagi)`
- Log real-time auto-scroll ke bawah, max 200 baris (oldest entries discarded)
- Warning bandwidth muncul di bawah dropdown kualitas hanya saat pilih 1080p
- Naming panel: `#tool-live` — konsisten dengan pola `#tool-video`, `#tool-merge`, dst.

---

## 11. Dependencies & Risks

| Item | Tipe | Detail |
|---|---|---|
| **FFmpeg `libx264`** | Dependency | Wajib tersedia — validasi saat startup, tampilkan error jika tidak ada |
| **Stream Key exposure** | Risk 🔴 | Credential sensitif — di-mask di semua log, tidak pernah ditulis ke disk |
| **Upload bandwidth user** | Risk 🔴 | 1080p butuh ≥ 10 Mbps upload — warning UI saat pilih bitrate tinggi |
| **FFmpeg zombie process** | Risk 🟡 | App crash saat live → FFmpeg terus jalan → PID tracking + cleanup wajib di startup |
| **Video tanpa audio track** | Risk 🟡 | Pilih "Audio dari Video" tapi video tanpa audio → auto-fallback ke Mute + warning |
| **Audio/video drift persepsi** | Risk 🟡 | Loop independen = drift alami seiring waktu — ini by design untuk ASMR, dokumentasikan di UI |
| **SSE timeout** | Risk 🟢 | Browser/proxy putus SSE setelah idle → heartbeat ping setiap 15 detik |
| **YouTube RTMP bitrate instability** | Risk 🟢 | Bitrate tidak stabil ditolak YouTube → `-bufsize` = 2x `-b:v` sudah handle ini |

---

## 12. Timeline & Milestones

| Milestone | Estimasi | Deliverable |
|---|---|---|
| M1 — Struktur Folder & Library CRUD | 2 hari | `media/video/`, `media/audio/`, `index.json`, thumbnail gen, endpoint CRUD |
| M2 — FFmpeg Stream Core | 2 hari | 3 mode audio, loop independen, stream key masking, kualitas preset |
| M3 — Auto-Reconnect & SSE | 2 hari | Reconnect loop, SSE status, timer, log streaming real-time |
| M4 — Frontend Panel | 3 hari | UI `#tool-live`: semua section, status bar, log view |
| M5 — Error Handling & Cleanup | 1 hari | Zombie PID cleanup, validasi startup, fallback audio track, warning bandwidth |
| M6 — Testing & QA | 2 hari | Test: 3 mode audio, reconnect, stop mid-stream, video tanpa audio, 1080p/720p |
| **Total** | **~12 hari kerja** | Feature ready untuk production |

---

## 13. Open Questions (Resolved)

| # | Pertanyaan | Keputusan |
|---|---|---|
| 1 | Simpan Stream Key? | ❌ Tidak disimpan — input ulang setiap sesi |
| 2 | Notifikasi desktop? | ❌ Tidak perlu — cukup status + log real-time |
| 3 | Folder library? | ✅ `media/video/` dan `media/audio/` (folder baru) |
| 4 | Auto-reconnect? | ✅ Wajib — retry setiap 5 detik, tanpa batas, hingga Stop |
| 5 | Durasi video ≠ audio? | ✅ Loop independen — keduanya loop sendiri, berhenti saat Stop |
| 6 | Sumber audio terpisah? | ✅ File audio tersendiri dari `media/audio/` (MP3, WAV, M4A, FLAC) |

---

## Ringkasan untuk Stakeholder

### Top 3 Risiko Terbesar
1. 🔴 **Stream Key exposure** — wajib di-mask semua output, tidak boleh tersimpan di disk
2. 🔴 **Upload bandwidth** — 1080p butuh ≥ 10 Mbps; tampilkan warning saat pilih bitrate tinggi
3. 🟡 **FFmpeg zombie process** — PID tracking + auto-cleanup saat app restart wajib diimplementasi

### Rekomendasi MVP v1

| Fitur | Status |
|---|---|
| Video loop dari File Lokal & Library | ✅ Must |
| Audio: dari video / terpisah / mute | ✅ Must |
| Loop independen video & audio | ✅ Must |
| Library `media/video/` & `media/audio/` | ✅ Must |
| Stream Key input per sesi | ✅ Must |
| Auto-reconnect RTMP | ✅ Must |
| Status SSE + Timer + Log real-time | ✅ Must |

### Ditunda ke v2/v3
- OAuth YouTube API (judul stream, jadwal otomatis)
- Multi-platform (Twitch, Facebook, dll.)
- Volume control per track (audio mixer)
- Overlay teks / watermark
- Playlist loop (beberapa video bergantian)
