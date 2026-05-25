# Product Requirements Document (PRD) - Metadata Injection

| Field | Details |
|---|---|
| **Feature Name** | Metadata Injection in Audio/Video Processes |
| **Status** | Draft |
| **Author** | Antigravity AI |
| **Target Tools** | Video Loop, Audio Mix & Layer (Sound Layer), Merge (Video + Audio) |

---

## 1. Latar Belakang & Masalah
Saat ini, file media yang dihasilkan oleh aplikasi ASMR Tools (baik hasil render audio mix, video loop, maupun merge video+audio) tidak memiliki informasi metadata tersemat (*embedded metadata*). 

Hal ini menyebabkan file hasil render muncul sebagai file "Tanpa Judul" atau "Unknown Artist" ketika diputar di media player (VLC, Windows Media Player, HP) atau ketika dilihat melalui File Explorer (Properties -> Details). Creator harus menggunakan aplikasi pihak ketiga (seperti Mp3tag) untuk mengisi metadata tersebut secara manual setelah render selesai.

---

## 2. Tujuan Fitur
Menyediakan antarmuka (UI/UX) di setiap panel pemrosesan utama agar creator dapat mengisi metadata dasar (Judul, Pembuat, Genre, Keterangan) secara opsional, yang akan langsung di-inject secara otomatis oleh FFmpeg ke dalam file output selama proses render berlangsung.

---

## 3. Ruang Lingkup (Scope) & Kebutuhan Fitur

### 3.1. Metadata Fields yang Didukung
Fitur ini akan mendukung 4 tag metadata standar yang paling sering digunakan:

| Label di UI | Tag FFmpeg | Tipe Data | Keterangan |
|---|---|---|---|
| **Judul** | `title` | Teks | Nama/Judul trek atau video |
| **Artis / Pembuat** | `artist` | Teks | Nama creator/pembuat konten |
| **Genre** | `genre` | Teks | Aliran musik/tema (default: `ASMR` atau `Ambient`) |
| **Deskripsi / Komentar** | `comment` | Teks / Textarea | Keterangan tambahan mengenai file |

### 3.2. Penempatan Fitur di UI/UX (Frontend)
Untuk menjaga kebersihan tampilan UI, input metadata akan dimasukkan ke dalam komponen **Collapsible Section (Accordion)** bernama **"🏷️ Metadata (Opsional)"**. 

Setiap panel berikut akan mendapatkan section ini:
1. **Video Loop Panel (`#tool-video`)**: Diletakkan sebelum tombol proses.
2. **Audio Mix & Layer Panel (`#tool-sound-layer`)**: Diletakkan di bagian Output Settings.
3. **Merge Panel (`#tool-merge`)**: Diletakkan sebelum tombol proses merge.

### 3.3. Aliran Data & Integrasi Backend (FastAPI + FFmpeg)
1. **Frontend** mengumpulkan nilai input dari form metadata.
2. Form metadata dikirimkan sebagai objek JSON `metadata` dalam payload API POST:
   * `/api/video/pipeline`
   * `/api/sound-layer/render`
   * `/api/merge`
3. **Backend** memeriksa objek `metadata`. Jika ada nilai yang diisi, backend akan menambahkan argumen `-metadata` secara dinamis ke perintah FFmpeg:
   ```bash
   ffmpeg -i input.mp4 -metadata title="Judul" -metadata artist="Pembuat" -metadata genre="ASMR" -metadata comment="Komentar" ... output.mp4
   ```
4. Jika input dikosongkan (default), FFmpeg tidak akan meng-inject metadata kustom tambahan.

---

## 4. Spesifikasi Teknis & Kompatibilitas Format File
Injeksi metadata via FFmpeg mendukung berbagai jenis format wadah (*container*):
* **Video (MP4 / MKV)**: Mendukung penuh tag `title`, `artist`, `genre`, dan `comment`.
* **Audio Terkompresi (M4A / MP3 / FLAC)**: Mendukung penuh seluruh tag metadata di atas.
* **Audio Uncompressed (WAV)**: Format WAV memiliki keterbatasan dalam penanganan metadata standar di beberapa media player lama, namun FFmpeg tetap akan menulis tag ID3/LIST chunk untuk menjamin kompatibilitas terbaik.

---

## 5. Rencana Pengujian (Verification Plan)
* **Pengujian Input Form**: Memastikan form metadata dapat dibuka-tutup dengan lancar dan nilainya tidak ter-reset ketika ditutup.
* **Pengujian Integrasi FFmpeg**: 
  1. Melakukan render audio di Sound Layer dengan metadata terisi.
  2. Membuka properti file hasil render di Windows File Explorer (`Klik Kanan -> Properties -> Details`).
  3. Memastikan kolom *Title*, *Contributing Artists*, *Genre*, dan *Comments* terisi dengan benar sesuai input form.
  4. Melakukan hal yang sama pada hasil Video Loop dan Merge.
