# Product Requirements Document (PRD) — Fitur Loop B+A (Video Segment Swap)

| Field | Details |
|---|---|
| **Feature Name** | Loop B+A (Video Segment Swap) |
| **Status** | Draft |
| **Author** | Antigravity AI |
| **Versi** | 1.0 |
| **Tanggal** | 16 Juni 2026 |
| **Target Tool** | Loop B+A Panel (`#tool-loop-ba`) |

---

## 1. Overview & Executive Summary

Fitur **Loop B+A** adalah tool baru di ASMR Tools yang mengambil 1 file video, memotongnya tepat di titik **50% durasi** secara otomatis menjadi dua segmen (A = paruh pertama, B = paruh kedua), lalu menukar posisinya menjadi **B → A**. Output adalah satu file video final tanpa audio, dengan opsi transisi crossfade di titik sambungan B→A.

Fitur ini berguna untuk creator yang ingin menciptakan efek "reverse reveal" atau "seamless loop" khas konten ASMR dan ambient video — tanpa perlu software editing eksternal.

---

## 2. Problem Statement

Teknik swap segmen video (B+A loop) adalah teknik populer di konten ASMR dan ambient untuk menciptakan video yang terasa "seamless" atau memiliki struktur naratif terbalik. Saat ini creator harus melakukannya secara manual di editor video eksternal: import → split → swap → export. ASMR Tools belum memiliki tool khusus untuk alur kerja ini, padahal bisa diotomasi sepenuhnya dengan FFmpeg dalam beberapa detik.

---

## 3. Goals & Success Metrics (KPI/OKR)

| Tujuan | Metrik Sukses |
|---|---|
| Otomasi proses swap segmen | User selesai dari upload hingga download dalam < 1 menit |
| Eliminasi software eksternal | 0 langkah yang memerlukan editor video pihak ketiga |
| Output siap pakai | File output MP4 tanpa audio, langsung bisa di-upload ke platform |
| Stabilitas render | 0 error tak tertangani dalam 100 proses render |

---

## 4. Target Users & Personas

**Persona — ASMR & Ambient Video Creator**
- Membuat konten loop / ambient untuk YouTube, Instagram, atau TikTok
- Sering menggunakan teknik segment swap untuk variasi konten
- Tidak perlu presisi titik potong — cukup 50% otomatis
- Pain point: proses swap manual di DaVinci / Premiere memakan waktu untuk task yang sebenarnya sederhana

---

## 5. Scope

### ✅ In-Scope (v1)
- Upload 1 file video (MP4, MKV, MOV, AVI)
- Potong otomatis tepat di 50% durasi → Segmen A + Segmen B
- Tukar urutan: output = B → A
- Strip audio (output tanpa suara)
- Opsi toggle: **Hard Cut** atau **Crossfade** di titik sambungan B→A
- Input durasi crossfade (jika dipilih)
- Output 1 file MP4 tanpa audio
- Progress bar + Download hasil
- Integrasi metadata injection (konsisten dengan `prd-metadata.md`)

### ❌ Out-of-Scope (v1 — kandidat v2/v3)
- Titik potong custom (selain 50%)
- Potong menjadi lebih dari 2 segmen
- Preview sebelum render
- Mempertahankan audio di output
- Loop/repeat output N kali
- Trim sebelum swap

---

## 6. User Stories & Acceptance Criteria

### US-01 — Upload Video
> *As a creator, I want to upload a single video file, so that the tool can process it for segment swapping.*

**Acceptance Criteria:**
- [ ] User dapat upload 1 file video (MP4, MKV, MOV, AVI)
- [ ] Setelah upload, tampilkan: nama file, durasi total, ukuran file
- [ ] Tampilkan preview info segmen: **"A: 0:00 – X:XX"** dan **"B: X:XX – Y:YY"** (dihitung otomatis dari 50% durasi)
- [ ] File non-video ditolak dengan pesan error yang jelas

---

### US-02 — Preview Info Segmen
> *As a creator, I want to see where the video will be split, so that I can confirm the 50% cut point before rendering.*

**Acceptance Criteria:**
- [ ] Setelah upload, sistem otomatis probe durasi video via `api/probe.py`
- [ ] Tampilkan breakdown segmen:
  - `Segmen A: 00:00:00 → 00:02:30` (paruh pertama)
  - `Segmen B: 00:02:30 → 00:05:00` (paruh kedua)
- [ ] Label jelas: **"Output akan dirender sebagai: B → A"**
- [ ] Info ini muncul sebelum tombol render aktif

---

### US-03 — Pilih Mode Transisi
> *As a creator, I want to choose between a hard cut or crossfade at the swap point, so that the join feels natural for my content.*

**Acceptance Criteria:**
- [ ] Toggle/radio button: **"Hard Cut"** (default) vs **"Crossfade"**
- [ ] Jika Crossfade dipilih, tampilkan input durasi (default: 1 detik, range: 0.5–5 detik)
- [ ] Jika Hard Cut, input durasi disembunyikan
- [ ] Pilihan ini hanya berlaku pada satu titik sambungan B→A

---

### US-04 — Render & Download
> *As a creator, I want to render the swapped video and download it, so that I have a ready-to-use output file.*

**Acceptance Criteria:**
- [ ] Tombol **"Render B+A"** aktif setelah video terupload
- [ ] Progress bar aktif selama FFmpeg berjalan
- [ ] Output **tanpa audio** (audio di-strip otomatis, tidak perlu konfirmasi user)
- [ ] Nama file output default: `loop_ba_YYYYMMDD_HHMMSS.mp4`
- [ ] Tombol Download aktif setelah render selesai
- [ ] Error FFmpeg ditampilkan sebagai pesan user-friendly dalam Bahasa Indonesia

---

## 7. Functional Requirements

| ID | Requirement | Prioritas |
|---|---|---|
| FR-01 | Upload 1 file video (MP4, MKV, MOV, AVI) | Must Have |
| FR-02 | Auto-probe durasi video setelah upload | Must Have |
| FR-03 | Display info segmen A dan B (titik potong 50%) | Must Have |
| FR-04 | Toggle Hard Cut / Crossfade | Must Have |
| FR-05 | Input durasi crossfade (0.5–5 detik) | Must Have (jika crossfade) |
| FR-06 | Strip audio otomatis pada output | Must Have |
| FR-07 | Progress bar render | Must Have |
| FR-08 | Download file MP4 output | Must Have |
| FR-09 | Integrasi metadata injection | Should Have |
| FR-10 | Validasi format file di frontend sebelum upload | Must Have |
| FR-11 | Tampilkan durasi total output (= durasi input - durasi crossfade overlap) | Nice to Have |

---

## 8. Non-Functional Requirements

- **Performance:** Proses split + swap + strip audio menggunakan FFmpeg — estimasi render < 30 detik untuk video ≤ 10 menit pada hardware standar (hard cut tanpa re-encode).
- **Security:** Validasi MIME type di backend, file temp dihapus otomatis setelah download via `api/cleanup.py`.
- **Accuracy:** Titik potong 50% dihitung dari durasi presisi hasil `ffprobe` (bukan estimasi), akurasi hingga milidetik.
- **Compatibility:** Output H.264 MP4 tanpa audio stream — kompatibel dengan YouTube, Instagram Reels, TikTok.
- **Error Handling:** Semua FFmpeg error di-catch, diterjemahkan ke Bahasa Indonesia.

---

## 9. Technical Considerations

Stack: **FastAPI (Python) + FFmpeg + Frontend HTML/JS**

### File Baru
- `api/loop_ba.py` — router dan logic backend

### Daftarkan di `api/router.py`
```python
from api import loop_ba
router.include_router(loop_ba.router)
```

### Alur Backend

**Step 1 — Probe durasi (reuse `api/probe.py`):**
```python
duration = probe_video_duration(input_path)  # float, dalam detik
midpoint = duration / 2
```

**Step 2 — Split menjadi A dan B:**
```bash
# Segmen A: dari awal sampai midpoint
ffmpeg -i input.mp4 -t {midpoint} -an -c:v copy segment_a.mp4

# Segmen B: dari midpoint sampai akhir
ffmpeg -i input.mp4 -ss {midpoint} -an -c:v copy segment_b.mp4
```

**Step 3a — Hard Cut (B → A, tanpa re-encode):**
```bash
# list_ba.txt: file segment_b.mp4 \n file segment_a.mp4
ffmpeg -f concat -safe 0 -i list_ba.txt -c copy output.mp4
```

**Step 3b — Crossfade (B → A, dengan re-encode):**
```bash
ffmpeg -i segment_b.mp4 -i segment_a.mp4 \
  -filter_complex \
    "[0][1]xfade=transition=fade:duration={cf_dur}:offset={b_duration - cf_dur}[v]" \
  -map "[v]" -an output.mp4
```

### Catatan Implementasi
- Gunakan `-an` flag di semua tahap untuk strip audio secara konsisten.
- Hard cut: gunakan `-c:v copy` (tanpa re-encode) → sangat cepat.
- Crossfade: wajib re-encode; offset = `durasi_B − durasi_crossfade`.
- Validasi: `durasi_crossfade` tidak boleh > `durasi_B` — return error 400 jika terjadi.
- Reuse `api/probe.py` untuk mendapatkan durasi — tidak perlu logic baru.
- Endpoint baru: `POST /api/loop-ba/render` dan `GET /api/loop-ba/download/{job_id}`.
- Temp files (`segment_a`, `segment_b`, `list_ba.txt`) dihapus otomatis setelah output siap.
- Validasi versi FFmpeg ≥ 4.3 (xfade tersedia sejak 4.3).

---

## 10. UI/UX Requirements & Wireframe Notes

```
┌─────────────────────────────────────────────┐
│  🔄 LOOP B+A                                │
├─────────────────────────────────────────────┤
│  📂 Upload Video                            │
│  [ Pilih File... ] (single file)            │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ 🎬 ambient_forest.mp4               │   │
│  │ Durasi: 05:00  •  Ukuran: 250MB     │   │
│  │                                     │   │
│  │  Titik Potong (otomatis 50%):       │   │
│  │  [====|====] ← 02:30  (read-only)  │   │
│  │                                     │   │
│  │  Segmen A : 00:00 → 02:30          │   │
│  │  Segmen B : 02:30 → 05:00          │   │
│  │                                     │   │
│  │  Output   : B (02:30) → A (02:30)  │   │
│  │  🔇 Audio akan dihilangkan          │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  Transisi di Titik Sambungan:              │
│  ● Hard Cut  ○ Crossfade                   │
│  [Durasi: 1.0 detik ___] (jika CF)         │
│                                             │
│  ▼ 🏷️ Metadata (Opsional) [accordion]     │
│                                             │
│  [ 🔄 Render B+A ]                         │
│                                             │
│  ██████████░░░░░ 70% — Estimasi: 0:12      │
│  [ ⬇ Download hasil ]                      │
└─────────────────────────────────────────────┘
```

**Catatan UI:**
- Bar `[====|====]` bersifat **read-only** di v1 — hanya visualisasi, tidak bisa di-drag
- Label **"🔇 Audio akan dihilangkan"** selalu tampil sebagai informasi pasif, bukan warning/konfirmasi
- Naming panel: `#tool-loop-ba` — konsisten dengan pola `#tool-video`, `#tool-merge`, dst.

---

## 11. Dependencies & Risks

| Item | Tipe | Detail |
|---|---|---|
| **`api/probe.py`** | Dependency internal | Reuse untuk probe durasi — tidak perlu logic baru |
| **FFmpeg ≥ 4.3** | Dependency | xfade filter untuk crossfade mode |
| **Hard cut di non-keyframe** | Risk 🔴 | `-c:v copy` di titik non-keyframe bisa menghasilkan artefak — perlu force keyframe atau fallback re-encode |
| **Crossfade offset negatif** | Risk 🟡 | Jika `durasi_crossfade > durasi_B` → offset negatif, FFmpeg error — wajib validasi di backend sebelum eksekusi |
| **Durasi float precision** | Risk 🟡 | Video durasi tidak genap (mis. 5:00.123) — titik potong harus float presisi dari ffprobe, bukan integer |
| **File besar** | Risk 🟢 | Single file upload, lebih mudah dikontrol dibanding multi-file |

---

## 12. Timeline & Milestones

| Milestone | Estimasi | Deliverable |
|---|---|---|
| M1 — Backend Core | 2 hari | `api/loop_ba.py`: probe + split + swap + strip audio (hard cut) |
| M2 — Crossfade Integration | 1 hari | Mode crossfade dengan kalkulasi offset otomatis + validasi |
| M3 — Frontend Panel | 2 hari | UI `#tool-loop-ba` + visualisasi info segmen |
| M4 — Error Handling & Cleanup | 1 hari | Validasi, pesan error Bahasa Indonesia, cleanup temp files |
| M5 — Testing & QA | 1 hari | Test: hard cut, crossfade, video durasi ganjil, video tanpa keyframe di midpoint |
| **Total** | **~7 hari kerja** | Feature ready untuk production |

---

## 13. Open Questions

1. Apakah di v2 perlu opsi **titik potong custom** (misalnya slider 30%/50%/70%)?
2. Apakah perlu opsi **loop output N kali** (B+A diulang 3x untuk video ambient panjang)?
3. Apakah **"🔇 Audio dihilangkan"** perlu opsi override di v2 (tetap pertahankan audio)?
4. Apakah nama fitur di tab navigasi: **"Loop B+A"** atau **"Swap Segmen"**?

---

## Ringkasan untuk Stakeholder

### Top 3 Risiko Terbesar
1. 🔴 Hard cut di non-keyframe → artefak video — perlu force keyframe atau fallback re-encode
2. 🟡 Crossfade offset negatif jika `durasi_crossfade > durasi_B` — wajib validasi di backend
3. 🟡 Titik potong float precision — gunakan hasil `ffprobe` bukan estimasi manual

### Rekomendasi MVP v1

| Fitur | Status |
|---|---|
| Upload single video | ✅ Must |
| Auto-split 50% + display info segmen | ✅ Must |
| Swap B→A + strip audio | ✅ Must |
| Hard cut output | ✅ Must |
| Crossfade di titik sambungan | ✅ Must |
| Download MP4 | ✅ Must |

### Ditunda ke v2/v3
- Titik potong custom (slider %)
- Loop output N kali
- Opsi pertahankan audio
- Preview sebelum render
