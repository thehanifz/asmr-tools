# PRD: ASMR Sound Editor — Fitur Sound Layering & Smart Merge
**Dokumen:** Product Requirements Document  
**Versi:** 1.0  
**Tanggal:** 22 Mei 2026  
**Repo:** https://github.com/thehanifz/asmr-tools  
**Status:** Draft — Menunggu Review

---

## 1. Overview & Executive Summary

ASMR Tools saat ini sudah bisa melakukan pipeline lengkap untuk video ASMR: crop, upscale, loop video, loop & normalize audio, merge, dan thumbnail — semua berbasis FFmpeg dengan UI 3-panel di browser.

Upgrade ini memfokuskan tools pada **editing suara yang lebih cerdas**, dengan menambahkan konsep **Sound Layering**: satu suara utama (main audio) yang berjalan full durasi, dan satu atau beberapa suara optional (layer) yang ditempatkan secara random — random posisi, random sound yang dipakai, random durasi aktif — dengan efek fade in/out yang halus di setiap layer. Output siap dipakai di YouTube (MP4 + M4A).

Fitur ini masuk sebagai panel baru di tab **Audio** yang diperluas, dan upgrade pada panel **Merge** untuk mendukung pemilihan suara utama vs optional.

---

## 2. Problem Statement

### Kondisi Saat Ini

Pipeline audio di v2 hanya menangani **satu file audio** yang di-loop dan di-normalize. Tidak ada mekanisme untuk:

- Menggabungkan dua layer suara (misalnya rain + paper crunching) secara otomatis
- Mengatur kapan suara sekunder muncul dan berapa lama
- Menambahkan variasi acak agar konten terasa alami, bukan repetitif
- Mengatur fade in/out per layer suara secara programatik

### Pain Point Spesifik

| # | Pain Point | Dampak |
|---|---|---|
| 1 | Harus edit audio di DAW eksternal (Audacity, dll.) sebelum masuk ke tools | Workflow terpotong, lambat |
| 2 | Tidak bisa mix beberapa suara ASMR dalam satu pass | Konten monoton, kurang dimensi |
| 3 | Penempatan suara sekunder butuh timing manual | Error-prone, memakan waktu |
| 4 | Tidak ada randomisasi — konten terdengar looping persis | Penonton bisa "ketahuan" pola loopnya |

---

## 3. Goals & Success Metrics

### Goals

1. **G1** — Kreator bisa mix suara utama + suara optional dalam satu workflow tanpa software eksternal
2. **G2** — Penempatan suara optional bersifat otomatis (random posisi, random sound, random durasi) dengan parameter yang bisa dikonfigurasi
3. **G3** — Setiap layer suara optional memiliki fade in/out yang smooth
4. **G4** — Output final siap upload YouTube (MP4 video + M4A audio, atau gabungan MP4)

### Success Metrics (KPI)

| Metric | Baseline | Target v1 |
|---|---|---|
| Jumlah langkah workflow untuk produce 1 video ASMR | 6+ langkah (termasuk DAW eksternal) | ≤ 4 langkah dalam tools |
| Waktu produksi 1 video (end-to-end) | ~30–45 menit | ≤ 20 menit |
| Berhasil generate audio layer tanpa artefak (kliping, silence gap) | N/A | 100% pass rate |
| Output MP4/M4A playable di YouTube tanpa re-encode | N/A | ✅ confirmed |

---

## 4. Target Users & Personas

### Primary Persona: Solo ASMR Creator

| Atribut | Detail |
|---|---|
| **Siapa** | Kreator konten ASMR indie, produksi sendiri |
| **Platform** | YouTube, loopable audio content |
| **Setup** | Windows, FFmpeg terinstall, browser-based workflow |
| **Skill Level** | Familiar dengan konsep audio (LUFS, fade, loop), tapi bukan audio engineer |
| **Pain Point Utama** | Workflow produksi terlalu panjang karena harus berpindah tools |
| **Goal** | Produce video ASMR berkualitas dengan variasi suara, minimal effort |

---

## 5. Scope

### ✅ In-Scope (MVP v1)

- Panel baru: **Sound Layer Editor** di tab Audio
- Pilih 1 file sebagai **Main Sound** (audio utama, full durasi)
- Pilih 1–5 file sebagai **Optional Sounds** (pool suara yang dipakai secara random)
- Konfigurasi parameter randomisasi: jumlah kejadian, rentang posisi (start-end window), rentang durasi per layer
- Fade in/out per optional sound layer (configurable duration)
- **Auto Cut**: deteksi & trim silence di awal/akhir optional sound sebelum di-place
- **Auto Place**: engine penempatan random berdasarkan parameter
- **Auto Duration**: jika durasi optional lebih panjang dari slot, dipotong sesuai; jika lebih pendek, looping atau stretch (configurable)
- Upgrade panel **Merge**: pilih apakah audio yang dipakai adalah output Sound Layer Editor atau file biasa
- Output format: M4A (audio only) dan MP4 (gabung dengan video)
- Real-time preview log (SSE) seperti pipeline lain
- Browse dialog untuk pilih folder pool optional sounds

### ❌ Out-of-Scope (v1)

- Visual timeline editor (drag & drop per layer)
- AI-based sound placement (beat detection, energy matching)
- Multi-track mixing lebih dari 2 layer simultan
- Support platform selain Windows dan Linux
- Cloud/remote processing
- Real-time audio preview di browser sebelum render
- Pitch shifting / time stretching
- Export ke format selain MP4 / M4A

---

## 6. User Stories & Use Cases

### US-01: Pilih Main Sound

> **As a** solo ASMR creator, **I want to** browse dan pilih satu file audio sebagai main sound, **so that** audio tersebut menjadi base layer yang berjalan full durasi output.

**Acceptance Criteria:**
- [ ] Ada tombol Browse untuk pilih file MP3/M4A/WAV/MP4 (audio-only extraction)
- [ ] Setelah dipilih, tool otomatis probe durasi & format file
- [ ] Durasi main sound = durasi output final
- [ ] Jika file lebih pendek dari target durasi, auto-loop (fitur loop sudah ada di v2, diintegrasikan)

---

### US-02: Pilih Pool Optional Sounds

> **As a** solo ASMR creator, **I want to** memilih satu folder berisi beberapa file audio sebagai pool optional sounds, **so that** tool bisa memilih secara random file mana yang dipakai di setiap kejadian.

**Acceptance Criteria:**
- [ ] Ada tombol Browse Folder untuk pilih folder
- [ ] Semua file audio valid di folder ditampilkan sebagai daftar (nama file + durasi)
- [ ] User bisa manually exclude file tertentu dari pool dengan checkbox
- [ ] Minimal 1 file di pool untuk bisa proceed

---

### US-03: Konfigurasi Randomisasi

> **As a** solo ASMR creator, **I want to** mengatur parameter random placement, **so that** suara optional muncul secara alami dan tidak terprediksi.

**Acceptance Criteria:**
- [ ] Input: **Jumlah Kejadian** (occurrence count) — berapa kali optional sound ditempatkan (range: 1–50)
- [ ] Input: **Window Start** & **Window End** — rentang posisi (dalam detik atau %) dimana optional sound boleh muncul. Default: 10% – 90% dari durasi main
- [ ] Input: **Min Duration** & **Max Duration** optional sound per kejadian (dalam detik)
- [ ] Input: **Min Gap** antar dua kejadian (untuk menghindari overlap) — default: 5 detik
- [ ] Checkbox: **Allow Overlap** — jika dicentang, kejadian boleh overlap satu sama lain
- [ ] Tombol **Randomize Preview** untuk generate placement plan tanpa render (tampil sebagai text log)

---

### US-04: Konfigurasi Fade In/Out

> **As a** solo ASMR creator, **I want to** mengatur fade in dan fade out per optional sound, **so that** kemunculan dan kepergian suara terasa halus dan tidak mengagetkan.

**Acceptance Criteria:**
- [ ] Input: **Fade In Duration** (detik) — default: 1.5s
- [ ] Input: **Fade Out Duration** (detik) — default: 1.5s
- [ ] Fade diterapkan ke setiap optional sound instance secara otomatis
- [ ] Jika durasi optional sound terlalu pendek untuk fade in + fade out, fade disesuaikan proporsional

---

### US-05: Auto Cut Silence

> **As a** solo ASMR creator, **I want to** tool otomatis memotong silence di awal dan akhir file optional sound, **so that** suara langsung bunyi tanpa dead air.

**Acceptance Criteria:**
- [ ] Tool deteksi silence di awal & akhir setiap file optional (threshold: -40 dBFS, configurable)
- [ ] Silence dipotong sebelum file di-place ke timeline
- [ ] Log menampilkan berapa ms yang dipotong per file

---

### US-06: Render & Output

> **As a** solo ASMR creator, **I want to** klik satu tombol untuk render hasil mix, **so that** saya mendapat file audio final yang siap di-merge dengan video.

**Acceptance Criteria:**
- [ ] Tombol **Render Mix** memulai proses FFmpeg
- [ ] Progress log real-time via SSE (seperti pipeline audio v2)
- [ ] Output: file M4A (AAC, 256kbps, stereo)
- [ ] Setelah selesai, path output otomatis ter-fill di panel Merge
- [ ] File playable langsung di browser via HTML5 audio element (preview sederhana)

---

### US-07: Upgrade Panel Merge

> **As a** solo ASMR creator, **I want to** di panel Merge bisa memilih apakah audio yang dipakai adalah hasil Sound Layer Editor atau file manual, **so that** workflow tetap fleksibel.

**Acceptance Criteria:**
- [ ] Panel Merge punya toggle: **"Use Layer Editor Output"** / **"Manual Browse"**
- [ ] Jika toggle = Layer Editor Output, path audio auto-filled dari hasil render US-06
- [ ] Jika toggle = Manual Browse, behavior sama seperti v2
- [ ] Output merge: MP4 (stream copy video + AAC audio, seperti v2)

---

## 7. Functional Requirements

### FR-01: Sound Layer Editor Panel

| ID | Requirement | Prioritas |
|---|---|---|
| FR-01.1 | Panel tersedia sebagai tab/section baru di area Audio | Must |
| FR-01.2 | Browse main sound file (MP3, M4A, WAV, MP4) | Must |
| FR-01.3 | Probe & tampilkan durasi + format main sound | Must |
| FR-01.4 | Browse folder untuk pool optional sounds | Must |
| FR-01.5 | List file di pool dengan checkbox exclude | Must |
| FR-01.6 | Form input konfigurasi randomisasi (occurrence, window, duration range, gap, overlap) | Must |
| FR-01.7 | Form input fade in/out duration | Must |
| FR-01.8 | Tombol Randomize Preview (dry-run, no render) | Should |
| FR-01.9 | Tombol Render Mix (trigger FFmpeg processing) | Must |
| FR-01.10 | Real-time SSE log progress | Must |
| FR-01.11 | Preview audio output via HTML5 `<audio>` tag | Should |

### FR-02: Auto Cut Engine

| ID | Requirement | Prioritas |
|---|---|---|
| FR-02.1 | Deteksi silence awal/akhir file optional dengan `silencedetect` filter FFmpeg | Must |
| FR-02.2 | Configurable silence threshold (dBFS) | Should |
| FR-02.3 | Log trim amount per file | Should |

### FR-03: Auto Place Engine (Backend)

| ID | Requirement | Prioritas |
|---|---|---|
| FR-03.1 | Generate random placement plan: list of `{file, start_time, duration, fade_in, fade_out}` | Must |
| FR-03.2 | Enforce minimum gap antar placements | Must |
| FR-03.3 | Respect window start/end boundaries | Must |
| FR-03.4 | Randomly pick file dari pool per placement | Must |
| FR-03.5 | Jika durasi file < requested duration: pilih loop atau pad silence (configurable) | Should |
| FR-03.6 | Jika durasi file > requested duration: trim file ke requested duration | Must |
| FR-03.7 | Return placement plan as JSON (untuk preview dan untuk di-pass ke render) | Must |

### FR-04: Render Engine (FFmpeg)

| ID | Requirement | Prioritas |
|---|---|---|
| FR-04.1 | Build FFmpeg filter_complex dari placement plan | Must |
| FR-04.2 | Terapkan `afade=in` dan `afade=out` per optional layer | Must |
| FR-04.3 | Mix main audio + semua optional layers dengan `amix` atau `amerge` | Must |
| FR-04.4 | Output: AAC 256kbps, stereo, M4A container | Must |
| FR-04.5 | Normalisasi akhir output ke target LUFS (inherit dari fitur loop audio v2) | Should |
| FR-04.6 | Stream via SSE ke frontend | Must |

### FR-05: Upgrade Merge Panel

| ID | Requirement | Prioritas |
|---|---|---|
| FR-05.1 | Toggle "Use Layer Editor Output" / "Manual Browse" di audio input merge | Must |
| FR-05.2 | Auto-fill path dari hasil render Sound Layer Editor | Must |

---

## 8. Non-Functional Requirements

| Kategori | Requirement |
|---|---|
| **Performance** | Render 60 menit audio dengan 20 optional placements ≤ 3 menit di hardware standard (i5/i7, 8GB RAM) |
| **Reliability** | FFmpeg error harus di-catch dan ditampilkan ke user, bukan crash silent |
| **Output Quality** | Output M4A harus lulus `ffprobe` tanpa warning; playable di YouTube tanpa re-encode |
| **Compatibility** | Windows 10/11 dan Linux distro umum (minimal Ubuntu/Debian-based); Python 3.10+; FFmpeg 6.x+ |
| **Usability** | User bisa selesai configure + render dalam ≤ 5 menit tanpa baca dokumentasi |
| **Maintainability** | Backend logic placement engine dipisahkan dari API handler (file `core/sound_layer.py`) |
| **Security** | Validasi path input: hanya izinkan ekstensi audio yang diketahui (whitelist) |

---

## 9. Technical Considerations

### 9.1 Stack

| Layer | Teknologi |
|---|---|
| Backend | Python 3.10+, FastAPI, FFmpeg CLI via subprocess |
| Frontend | Vanilla JS ES Modules (sesuai v2) |
| Audio processing | FFmpeg `filter_complex` — `afade`, `adelay`, `atrim`, `aloop`, `amix`, `silencedetect` |
| Streaming | SSE (Server-Sent Events) — pola yang sudah ada di v2 |

### 9.2 Arsitektur Backend Baru

```
api/
├── sound_layer.py          ← API handler: /api/sound-layer/preview, /api/sound-layer/render
core/
├── sound_layer_engine.py   ← Logic: placement plan generation, filter_complex builder
```

**Endpoint baru yang diusulkan:**

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/browse-folder-audio` | Browse folder, return list file audio valid |
| POST | `/api/sound-layer/preview` | Generate placement plan (JSON, no render) |
| POST | `/api/sound-layer/render` | Render mix via FFmpeg (SSE streaming) |

### 9.3 FFmpeg Filter Complex Pattern

Untuk N optional sounds yang ditempatkan secara random, filter_complex akan berbentuk:

```
# Main audio (input 0)
[0:a]aformat=sample_rates=44100:channel_layouts=stereo[main];

# Per optional sound (misal 3 placements)
[1:a]atrim=0:12,afade=t=in:d=1.5,afade=t=out:st=10.5:d=1.5,adelay=45000|45000[opt0];
[2:a]atrim=0:8,afade=t=in:d=1.5,afade=t=out:st=6.5:d=1.5,adelay=120000|120000[opt1];
[1:a]atrim=0:15,afade=t=in:d=1.5,afade=t=out:st=13.5:d=1.5,adelay=210000|210000[opt2];

# Mix semua
[main][opt0][opt1][opt2]amix=inputs=4:normalize=0[out]
```

> `adelay` dalam milidetik. `atrim` memotong durasi. `afade` handle fade per segment.

### 9.4 Auto Cut Silence — FFmpeg Filter

```bash
ffprobe -f lavfi -i "amovie=input.m4a,silencedetect=n=-40dB:d=0.1" -show_entries frame_tags=lavfi.silence_start,lavfi.silence_end -of json
```

Dari output JSON ini, engine bisa hitung berapa detik silence di awal/akhir dan build `atrim` yang tepat.

### 9.5 Frontend: JS Module Baru

```
frontend/js/
├── panel-sound-layer.js    ← Logic Sound Layer Editor panel
```

Tambahkan state baru di `state.js`:
```javascript
soundLayer: {
  mainFile: null,
  optionalPool: [],
  config: {},
  placementPlan: null,
  outputPath: null
}
```

### 9.6 Estimasi Kompleksitas

| Komponen | Kompleksitas | Alasan |
|---|---|---|
| Placement Engine (`core/sound_layer_engine.py`) | **High** | Random placement dengan constraint gap + overlap + window butuh logic teliti |
| FFmpeg filter_complex builder | **High** | Dynamic filter_complex dengan N inputs butuh string building yang precise |
| Auto Cut silence detection | **Medium** | Sudah ada pola `ffprobe` JSON parsing di codebase |
| Frontend Panel UI | **Medium** | Pola UI sudah ada, tinggal adaptasi |
| SSE streaming render | **Low** | Persis sama dengan pola di `api/audio.py` v2 |
| Upgrade Merge panel | **Low** | Toggle + auto-fill path, UI kecil |

---
### 9.7 Performance Optimization Requirements

Karena bottleneck utama proses sound editing ada di CPU-based audio filtering FFmpeg, desain v1 harus memasukkan optimasi performa sejak awal. Hardware acceleration FFmpeg umumnya membantu untuk video encode/decode, sedangkan mixing audio dan filter audio tetap bergantung pada CPU thread dan efisiensi filter graph. [web:21][web:24]

**Requirement performa yang diusulkan:**

| ID | Requirement | Prioritas |
|---|---|---|
| PO-01 | Semua render FFmpeg wajib memakai konfigurasi thread yang configurable: `-threads 0`, `-filter_threads`, `-filter_complex_threads` | Must |
| PO-02 | Backend harus menyediakan config default thread count yang aman untuk CPU umum (mis. min(8, logical_cpu)) | Must |
| PO-03 | Optional sound pool harus bisa dipre-process ke cache intermediate seragam (sample rate, channel layout, codec) sebelum render final | Must |
| PO-04 | Jika durasi output > 30 menit atau jumlah placement > 20, engine harus mendukung mode chunked rendering | Should |
| PO-05 | Placement plan wajib bisa di-split per chunk tanpa mengubah hasil akhir secara signifikan | Should |
| PO-06 | Merge final tetap mempertahankan `-c:v copy` agar video tidak ikut re-encode | Must |

**Strategi optimasi v1:**

1. **Thread tuning** — wrapper FFmpeg existing harus menerima parameter thread agar seluruh core CPU bisa dipakai lebih efektif. [web:21][web:22]
2. **Intermediate cache** — optional sounds dikonversi sekali ke format seragam, misalnya 44.1kHz stereo PCM WAV, untuk mengurangi decode berulang saat banyak placement. [web:21]
3. **Chunked rendering** — render audio panjang dibagi ke beberapa segmen 10–20 menit, diproses paralel, lalu di-concat di akhir. Ini menurunkan kompleksitas satu `filter_complex` besar menjadi beberapa job yang lebih kecil. [web:12][web:24]
4. **Preview vs final quality mode** — untuk iterasi cepat, sistem boleh menyediakan render preview dengan bitrate lebih rendah atau normalisasi yang lebih ringan; final render tetap pakai kualitas produksi. [web:21]

**Implementation note:**

- Tambahkan helper seperti `get_recommended_threads()` di `core/` yang membaca logical CPU count secara cross-platform.
- Tambahkan cache folder misalnya `temp_audio_cache/` yang dibersihkan otomatis per session atau per job.
- Tambahkan threshold switching: jika `duration_minutes >= 30` atau `occurrence_count > 20`, backend default ke chunk mode, tapi user tetap bisa override lewat advanced setting.

### 9.8 Cross-Platform Support (Windows + Linux)

Repo saat ini sudah memiliki entry point untuk Windows (`start.bat`) dan Linux (`start_linux.sh`), sehingga upgrade ini harus mempertahankan kompatibilitas dua platform tersebut. [cite:1][cite:2]

| Area | Requirement | Prioritas |
|---|---|---|
| Path handling | Semua path harus dibangun dengan `pathlib.Path`, bukan string hardcoded separator | Must |
| Subprocess | Semua pemanggilan FFmpeg/ffprobe harus memakai arg list (`subprocess.Popen([...])`), bukan shell command string | Must |
| Temp files | Gunakan direktori temp yang aman di Windows dan Linux (`tempfile`, `Path`) | Must |
| File dialog | Browse dialog tetap support perilaku existing; jika behavior GUI berbeda di Linux headless, tampilkan fallback error yang jelas | Must |
| Open folder | Endpoint open-folder harus punya implementasi terpisah per OS (`explorer`, `xdg-open`) | Must |
| Path quoting | Tidak boleh mengandalkan quote manual; biarkan subprocess menangani escaping | Must |
| Test coverage | Minimal smoke test render di Windows dan 1 distro Linux (Ubuntu) | Should |

**Guideline implementasi cross-platform:**

- Jangan gunakan API spesifik Windows di logic core sound engine.
- Pisahkan utilitas OS-dependent ke `api/system.py` atau helper util khusus.
- Semua file cache, output, dan temp harus lolos untuk path dengan spasi dan karakter non-ASCII.
- Dokumentasi setup harus diperbarui untuk Linux, termasuk dependency `ffmpeg`, `ffprobe`, dan jika diperlukan package GUI fallback.

---

## 10. UI/UX Requirements & Wireframe Notes

### 10.1 Layout

Panel Sound Layer Editor ditambahkan sebagai **tab ketiga** di area tengah, atau sebagai **ekspansi panel Audio** yang sudah ada. Rekomendasi: **tab terpisah** agar tidak crowded.

```
[Tab: Video] [Tab: Audio Loop] [Tab: Sound Layer ✨]  [Panel Merge →]
┌──────────────────────────────────────────────────────────────────┐
│ 🎵 SOUND LAYER EDITOR                                            │
│                                                                  │
│ MAIN SOUND                                                       │
│ [📁 Browse Main Sound]  path/to/rain.m4a  [90:00 | M4A | 256k]  │
│                                                                  │
│ OPTIONAL SOUND POOL                                              │
│ [📁 Browse Folder]                                               │
│ ☑ paper_crinkle.wav    [0:15]                                    │
│ ☑ keyboard_tap.m4a     [0:08]                                    │
│ ☐ glass_clink.mp3      [0:05]  ← excluded                       │
│ + 2 more files...                                                │
│                                                                  │
│ PLACEMENT CONFIG                                                 │
│ Occurrences: [12]   Min Gap: [5s]   ☐ Allow Overlap             │
│ Window:      [10%] ───────────────────── [90%]                   │
│ Duration:    Min [3s] — Max [20s]                                │
│                                                                  │
│ FADE CONFIG                                                      │
│ Fade In: [1.5s]    Fade Out: [1.5s]                             │
│                                                                  │
│ AUTO CUT SILENCE   Threshold: [-40 dBFS]                        │
│                                                                  │
│ [🎲 Preview Placement] [▶ Render Mix]                           │
│                                                                  │
│ ── LOG ────────────────────────────────────────────────────────  │
│ Placement plan generated: 12 events                             │
│ [opt0] paper_crinkle.wav → 00:03:12 – 00:03:27 (fade 1.5s)     │
│ ...                                                              │
│ ✅ Output: /output/layered_audio.m4a                             │
│ [▶ Preview Audio]                                               │
└──────────────────────────────────────────────────────────────────┘
```

### 10.2 UX Notes

- **Preview Placement** menampilkan placement plan di log area sebagai text table — user bisa review sebelum commit render
- **Tombol Render** disabled sampai main sound + minimal 1 optional sound dipilih
- Setelah render selesai, badge "✅ Ready" muncul di header tab Sound Layer
- Panel Merge: badge kecil di audio input field menunjukkan "from Layer Editor" jika toggle aktif
- Fade duration yang lebih besar dari slot duration: tampilkan warning inline (bukan toast)

---

## 11. Dependencies & Risks

### Dependencies

| Dependency | Status | Notes |
|---|---|---|
| FFmpeg 6.x+ | ✅ Already required | `filter_complex` dengan banyak inputs butuh versi cukup baru |
| FastAPI + Uvicorn | ✅ Already in requirements.txt | Tidak ada penambahan |
| Python `random`, `json`, `pathlib` | ✅ Built-in | Untuk placement engine |
| Frontend: Vanilla JS ES Modules | ✅ Already in use | Tidak ada framework baru |

### Risks

| # | Risk | Likelihood | Impact | Mitigasi |
|---|---|---|---|---|
| R1 | FFmpeg `filter_complex` dengan 20+ inputs menjadi sangat lambat atau gagal | Medium | High | Batasi max occurrences ke 50; test dengan edge cases |
| R2 | Overlap placements menyebabkan clipping audio | Medium | Medium | Normalize output akhir; beri option `amix normalize=1` |
| R3 | Path file dengan spasi/karakter khusus break FFmpeg command | Medium | Medium | Selalu wrap path dengan quotes di subprocess; validasi path |
| R4 | Silence detection `ffprobe` tidak akurat di semua format | Low | Medium | Fallback: jika probe gagal, skip auto-cut untuk file tersebut (log warning) |
| R5 | Duration mismatch antara main sound dan placement window | Low | Low | Validasi di backend sebelum render; return error JSON yang clear |

---

## 12. Timeline & Milestones

> Estimasi untuk 1 developer (solo), part-time.

| Milestone | Deliverable | Estimasi |
|---|---|---|
| **M1: Backend Foundation** | `core/sound_layer_engine.py` — placement plan generator + filter_complex builder (unit tested) | 3–4 hari |
| **M2: API Endpoints** | `api/sound_layer.py` — 3 endpoint: browse-folder, preview, render (SSE) | 2–3 hari |
| **M3: Frontend Panel** | `panel-sound-layer.js` + UI HTML/CSS di tab baru | 3–4 hari |
| **M4: Merge Panel Upgrade** | Toggle + auto-fill di `panel-merge.js` | 1 hari |
| **M5: Integration & QA** | End-to-end test, edge cases, output quality check | 2–3 hari |
| **M6: Docs Update** | Update README.md + UPDATE_LOG | 0.5 hari |
| **Total Estimasi** | | **~12–15 hari kerja** |

---

## 13. Open Questions

| # | Pertanyaan | Relevansi |
|---|---|---|
| OQ-01 | Apakah output akhir perlu melalui LUFS normalization setelah amix? Saat ini `api/audio.py` sudah punya LUFS normalize — apakah akan diintegrasikan ke Sound Layer pipeline juga? | Output quality |
| OQ-02 | Jika pool optional sounds berisi file stereo dan mono campur, bagaimana handling channel layout sebelum amix? | Audio artifact prevention |
| OQ-03 | Apakah "Random Sound" berarti satu file bisa dipakai lebih dari sekali dalam satu session? (Sampling with replacement) | Placement engine logic |
| OQ-04 | Apakah perlu menyimpan placement plan ke file JSON agar bisa di-reproduce (same seed)? Berguna untuk iterasi dengan tweak kecil | Reproducibility |
| OQ-05 | Apakah tools perlu support drag-and-drop file ke browser selain Browse dialog? | UX nicety untuk v1 atau v2? |
| OQ-06 | Apakah chunked rendering perlu selalu aktif untuk durasi panjang, atau cukup sebagai advanced setting? | Performance vs simplicity |

---

## Summary: Top 3 Risiko, MVP, dan Roadmap

### 🚨 Top 3 Risiko Terbesar

1. **FFmpeg filter_complex complexity** (R1) — makin banyak placement, makin kompleks command; potensi timeout atau error yang sulit di-debug
2. **Audio clipping saat overlap** (R2) — jika allow overlap aktif dan banyak layer bertumpuk, volume bisa meledak
3. **Path handling di Windows** (R3) — path dengan spasi adalah sumber bug klasik di FFmpeg subprocess call

### ✅ Rekomendasi MVP (v1 — harus ada)

- Main sound + Optional Pool browse
- Random placement engine dengan parameter dasar (occurrence, window, duration range, gap)
- Fade in/out per layer
- Render → M4A output
- SSE log real-time
- Upgrade Merge panel (toggle Layer Editor output)

### 🔮 Bisa Ditunda ke v2/v3

| Fitur | Versi |
|---|---|
| Visual timeline editor (drag & drop) | v2 |
| Real-time audio preview di browser sebelum render | v2 |
| Reproducible placement via seed/JSON export | v2 |
| LUFS normalization terintegrasi di Sound Layer pipeline | v2 |
| AI-based placement (energy-matched, beat-aligned) | v3 |
| Multi-platform support (macOS) | v2 |

---

*Apakah ada bagian yang perlu diubah atau ditambahkan?*
