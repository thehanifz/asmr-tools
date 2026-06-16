# Product Requirements Document (PRD) — Fitur Gabung Klip (Clip Concatenator)

| Field | Details |
|---|---|
| **Feature Name** | Gabung Klip (Clip Concatenator) |
| **Status** | Draft |
| **Author** | Antigravity AI |
| **Versi** | 1.0 |
| **Tanggal** | 16 Juni 2026 |
| **Target Tool** | Gabung Klip Panel (`#tool-concat`) |

---

## 1. Overview & Executive Summary

Fitur **Gabung Klip** (*Clip Concatenator*) adalah tool baru di ASMR Tools yang memungkinkan creator menggabungkan beberapa klip video secara berurutan menjadi satu file video panjang. User dapat mengatur ulang urutan klip via drag-and-drop dan memilih apakah antar klip menggunakan transisi (crossfade) atau disambung langsung (*hard cut*).

Fitur ini sepenuhnya terpisah dari tool **Merge** yang sudah ada:
- **Merge** = menggabungkan 1 video + 1 audio track
- **Gabung Klip** = menggabungkan multi-video menjadi 1 output panjang

---

## 2. Problem Statement

Creator ASMR sering merekam konten dalam beberapa segmen pendek (misalnya: intro ambience, main trigger, outro) dan harus menggabungkannya secara manual menggunakan software eksternal seperti DaVinci Resolve atau Adobe Premiere sebelum di-render final. Proses ini menyebabkan *friction* yang tidak perlu karena ASMR Tools seharusnya bisa menangani seluruh pipeline produksi dalam satu aplikasi.

---

## 3. Goals & Success Metrics (KPI/OKR)

| Tujuan | Metrik Sukses |
|---|---|
| Mengurangi ketergantungan software eksternal | 80% creator tidak perlu keluar dari ASMR Tools untuk concat |
| Proses gabung klip cepat | Render selesai ≤ 2x durasi total video pada hardware standar |
| Kemudahan penggunaan | User dapat menggabungkan 3+ klip dalam < 2 menit tanpa dokumentasi |
| Stabilitas | 0 file corrupt / error tak tertangani dalam 100 proses render |

---

## 4. Target Users & Personas

**Persona Utama — ASMR Creator Independen**
- Merekam konten dalam segmen terpisah (multiple takes/scenes)
- Tidak memiliki latar belakang editing profesional
- Menggunakan ASMR Tools sebagai satu-satunya pipeline produksi
- Pain point: harus pindah software hanya untuk concat klip sederhana

---

## 5. Scope

### ✅ In-Scope (v1)
- Upload multiple file video (MP4, MKV, MOV, AVI)
- Reorder klip via drag-and-drop
- Pilihan: transisi **crossfade** atau **hard cut**
- Konfigurasi durasi transisi (jika crossfade dipilih)
- Output satu file MP4
- Integrasi metadata injection (konsisten dengan `prd-metadata.md`)
- Progress bar render
- Download file hasil

### ❌ Out-of-Scope (v1 — kandidat v2/v3)
- Trim / cut klip sebelum digabung
- Transisi selain crossfade (wipe, zoom, dll.)
- Preview real-time sebelum render
- Gabung klip audio-only
- Batch output (multiple output format sekaligus)
- Normalisasi LUFS otomatis antar klip
- Undo/redo history

---

## 6. User Stories & Use Cases

### US-01 — Upload Klip
> *As a creator, I want to upload multiple video files at once, so that I can prepare all clips without uploading one by one.*

**Acceptance Criteria:**
- [ ] User dapat select/upload ≥ 2 file video sekaligus
- [ ] Format yang diterima: MP4, MKV, MOV, AVI
- [ ] Setiap klip menampilkan: nama file, durasi, ukuran file
- [ ] Maksimal upload: 20 klip per sesi
- [ ] File yang tidak didukung ditolak dengan pesan error yang jelas

---

### US-02 — Atur Urutan via Drag-and-Drop
> *As a creator, I want to reorder clips by dragging them, so that I can control the final sequence without deleting and re-uploading.*

**Acceptance Criteria:**
- [ ] Setiap item klip dapat di-drag secara vertikal
- [ ] Urutan nomor (1, 2, 3...) diperbarui otomatis setelah drop
- [ ] Tersedia tombol ↑ / ↓ sebagai fallback untuk pengguna non-mouse (keyboard/tablet)
- [ ] Urutan drag-and-drop dipertahankan saat render dimulai

---

### US-03 — Pilih Mode Transisi
> *As a creator, I want to choose between crossfade or hard cut transitions, so that I can match the mood of my ASMR content.*

**Acceptance Criteria:**
- [ ] Terdapat toggle/radio button: **"Hard Cut"** (default) vs **"Crossfade"**
- [ ] Jika Crossfade dipilih, muncul input durasi transisi (default: 1 detik, range: 0.5–5 detik)
- [ ] Jika Hard Cut dipilih, input durasi disembunyikan
- [ ] Pilihan transisi berlaku global untuk semua sambungan antar klip

---

### US-04 — Render & Download
> *As a creator, I want to see progress while rendering and download the result, so that I know the process is running and can retrieve my file.*

**Acceptance Criteria:**
- [ ] Progress bar aktif selama proses FFmpeg berjalan
- [ ] Estimasi waktu tersisa ditampilkan (jika bisa dihitung dari durasi)
- [ ] Setelah selesai, tombol **"Download"** aktif
- [ ] Nama file output default: `gabung_klip_YYYYMMDD_HHMMSS.mp4`
- [ ] Jika terjadi error, tampilkan pesan error yang actionable (bukan raw FFmpeg log)

---

## 7. Functional Requirements

| ID | Requirement | Prioritas |
|---|---|---|
| FR-01 | Upload multi-file video (≥ 2 file, ≤ 20 file) | Must Have |
| FR-02 | Display daftar klip dengan nama, durasi, ukuran | Must Have |
| FR-03 | Drag-and-drop reorder dengan visual feedback | Must Have |
| FR-04 | Tombol ↑/↓ sebagai fallback reorder | Should Have |
| FR-05 | Toggle Hard Cut / Crossfade | Must Have |
| FR-06 | Input durasi crossfade (0.5–5 detik) | Must Have (jika crossfade) |
| FR-07 | Tombol hapus klip dari daftar | Must Have |
| FR-08 | Progress bar dengan persentase | Must Have |
| FR-09 | Download file output MP4 | Must Have |
| FR-10 | Integrasi metadata injection (title, artist, genre, comment) | Should Have |
| FR-11 | Validasi format file di sisi frontend sebelum upload | Must Have |
| FR-12 | Tampilkan total durasi gabungan | Nice to Have |

---

## 8. Non-Functional Requirements

- **Performance:** Proses concat tanpa transcoding (FFmpeg concat demuxer) untuk video dengan spesifikasi sama → near-realtime. Jika ada crossfade, gunakan filter complex dengan transcoding minimal.
- **Security:** File upload divalidasi MIME type di backend, tidak hanya ekstensi. File temp dihapus otomatis setelah download (konsisten dengan `api/cleanup.py`).
- **Scalability:** Mendukung total ukuran file input hingga **10 GB** per sesi (batas hardware lokal).
- **Error Handling:** Semua error FFmpeg di-catch dan diterjemahkan ke pesan user-friendly dalam Bahasa Indonesia.
- **Compatibility:** Output MP4 kompatibel dengan YouTube, Instagram, dan player standar (H.264 + AAC).

---

## 9. Technical Considerations

Stack: **FastAPI (Python) + FFmpeg + Frontend HTML/JS**

### File Baru yang Perlu Dibuat
- `api/concat.py` — router dan logic backend
- Panel `#tool-concat` di frontend

### Daftarkan di `api/router.py`
```python
from api import concat
router.include_router(concat.router)
```

### Strategi FFmpeg

**Hard Cut** (tanpa re-encode, cepat — bila codec sama):
```bash
# Buat concat list
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
```

**Hard Cut dengan re-encode** (fallback bila resolusi/codec beda):
```bash
ffmpeg -i clip1.mp4 -i clip2.mp4 \
  -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" output.mp4
```

**Crossfade** (re-encode, untuk N klip dibangun programatik):
```bash
ffmpeg -i clip1.mp4 -i clip2.mp4 \
  -filter_complex \
    "[0][1]xfade=transition=fade:duration=1:offset=<end_of_clip1>[v]; \
     [0:a][1:a]acrossfade=d=1[a]" \
  -map "[v]" -map "[a]" output.mp4
```

### Catatan Implementasi
- Hard Cut: auto-detect codec/resolusi tiap klip. Bila semua sama → concat demuxer. Bila beda → fallback re-encode dengan `-vf scale=1920:1080`.
- Crossfade: wajib re-encode, estimasi durasi render ~1–3x durasi total tergantung CPU.
- Untuk N klip crossfade, bangun `filter_complex` secara programatik via loop.
- Validasi versi FFmpeg ≥ 4.3 saat startup (xfade tersedia sejak 4.3).
- Set `max_upload_size` di FastAPI config untuk mendukung file besar.

---

## 10. UI/UX Requirements & Wireframe Notes

```
┌─────────────────────────────────────────────┐
│  🎬 GABUNG KLIP                             │
├─────────────────────────────────────────────┤
│  📂 Upload Klip Video                       │
│  [ Pilih File... ] (multi-select)           │
│                                             │
│  Daftar Klip (drag untuk atur urutan):      │
│  ┌─────────────────────────────────────┐   │
│  │ ⠿ 1. intro_ambience.mp4  02:15  45MB│   │
│  │ ⠿ 2. main_trigger.mp4    08:30 180MB│   │
│  │ ⠿ 3. outro_rain.mp4      01:45  38MB│   │
│  └─────────────────────────────────────┘   │
│  Total durasi: ~12:30                       │
│                                             │
│  Transisi Antar Klip:                       │
│  ● Hard Cut  ○ Crossfade                    │
│  [Durasi: 1.0 detik ___] (muncul jika CF)  │
│                                             │
│  ▼ 🏷️ Metadata (Opsional) [accordion]      │
│                                             │
│  [ 🎬 Gabung Sekarang ]                     │
│                                             │
│  ████████████░░░░░ 65% — Estimasi: 0:45    │
│  [ ⬇ Download hasil ]                       │
└─────────────────────────────────────────────┘
```

**Library Frontend:**
- Gunakan **SortableJS** (ringan ~45KB) untuk drag-and-drop list
- Load via CDN atau bundle lokal, konsisten dengan dependency frontend existing
- Naming panel: `#tool-concat` — konsisten dengan pola `#tool-video`, `#tool-merge`, dst.

---

## 11. Dependencies & Risks

| Item | Tipe | Detail |
|---|---|---|
| **SortableJS** | Dependency | Library drag-and-drop frontend, load via CDN atau bundle lokal |
| **FFmpeg ≥ 4.3** | Dependency | xfade filter tersedia sejak versi 4.3 — validasi versi saat startup |
| **Klip beda resolusi/codec** | Risk 🔴 | Hard cut tanpa re-encode akan gagal → wajib auto-detect + fallback ke re-encode |
| **Crossfade N klip** | Risk 🟡 | Membangun filter_complex programatik untuk banyak klip — butuh unit test ≥ 5 klip |
| **Upload file besar** | Risk 🟡 | Upload 10+ klip besar bisa timeout → set `max_upload_size` di FastAPI config |
| **Audio codec mismatch** | Risk 🟡 | Klip dari sumber berbeda bisa punya audio codec berbeda → normalize ke AAC sebelum concat |

---

## 12. Timeline & Milestones

| Milestone | Estimasi | Deliverable |
|---|---|---|
| M1 — Setup & Backend Core | 3 hari | `api/concat.py` dengan hard cut working |
| M2 — Frontend Panel | 2 hari | UI panel `#tool-concat` + drag-and-drop (SortableJS) |
| M3 — Crossfade Integration | 2 hari | Crossfade filter untuk N klip (programatik) |
| M4 — Error Handling & Cleanup | 1 hari | Validasi, pesan error, auto-cleanup temp file |
| M5 — Testing & QA | 2 hari | Test 3 skenario: hard cut, crossfade, mixed codec |
| **Total** | **~10 hari kerja** | Feature ready untuk production |

---

## 13. Open Questions

1. Apakah output harus selalu **MP4**, atau perlu opsi MKV juga?
2. Apakah crossfade harus **per-sambungan** (bisa berbeda durasi antar klip) di v2, atau tetap global?
3. Apakah perlu **normalisasi audio loudness** (LUFS) otomatis antar klip sebelum digabung? (saat ini out-of-scope v1)
4. Apakah fitur ini perlu support **Google Colab** (`start_colab.py`), dan jika ya, apakah ada batasan ukuran file yang perlu dipertimbangkan?

---

## Ringkasan untuk Stakeholder

### Top 3 Risiko Terbesar
1. 🔴 Klip beda resolusi/codec menyebabkan hard cut gagal — **wajib** ada auto-detect + fallback re-encode
2. 🟡 Membangun FFmpeg `filter_complex` untuk crossfade N klip secara programatik — butuh unit test khusus
3. 🟡 Upload file besar (>1GB per klip) bisa timeout di FastAPI default config — perlu set `max_upload_size`

### Rekomendasi MVP v1
| Fitur | Status |
|---|---|
| Upload multi-file | ✅ Must |
| Drag-and-drop reorder | ✅ Must |
| Hard cut concat | ✅ Must |
| Crossfade (durasi global) | ✅ Must |
| Download output MP4 | ✅ Must |

### Ditunda ke v2/v3
- Trim klip sebelum gabung
- Transisi per-sambungan (durasi berbeda)
- Preview real-time
- Normalisasi LUFS otomatis
- Support format output selain MP4
