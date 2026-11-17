# Rencana Teknis Upload YouTube — Fase C (15 Nov 2026)

Tujuan: video final hasil pipeline VM (finalisasi → thumbnail → metadata)
terupload ke channel XD dari VM Muse lewat YouTube Data API v3,
resumable, terjadwal, dengan thumbnail dan playlist — tanpa memindahkan
berkas besar ke perangkat Kevin.

## 1. Komponen yang dibangun

- Modul baru `api/youtube_upload.py` di repo asmr-tools (backend).
- Panel UI "Upload YouTube" (tahap sesudah Finalisasi): pilih berkas
  final dari pemilih berkas server, muat paket metadata, tombol upload,
  progress bar (SSE seperti panel lain), riwayat job.
- Manifes job per video: `~/workspace/asmr-service/jobs/<slug>.json`
  (metadata lengkap, session URI resumable, progres, videoId hasil).
- Rahasia di luar repo: `~/workspace/asmr-service/secrets/`
  (client_secret.json + token.json, izin 600).

## 2. Persiapan satu kali (Google Cloud + OAuth) — bagian Kevin, dipandu L

1. Buat Google Cloud project (akun xd.mangjon@gmail.com / pemilik channel).
2. Aktifkan YouTube Data API v3.
3. OAuth consent screen: External; **publikasikan ke Production**
   (bukan Testing) — refresh token mode Testing kedaluwarsa 7 hari;
   Production untuk pemakaian sendiri cukup melewati layar peringatan
   "unverified app" sekali, refresh token tidak kedaluwarsa berkala.
4. Buat OAuth client tipe Desktop, unduh client_secret.json → secrets/.
5. Otorisasi pertama: skrip L menampilkan URL → Kevin buka, setujui
   (scope `youtube.upload` + `youtube`), tempel kode → token.json
   tersimpan. Sesudah ini semua upload berjalan tanpa login lagi.
6. Kuota bawaan 10.000 unit/hari; videos.insert = 1.600 unit →
   ±6 upload/hari. Jadwal kita 2/minggu: sangat cukup.

## 3. Alur upload (resumable, tahan putus & tahan reboot VM)

- Library resmi: google-api-python-client + google-auth, MediaFileUpload
  chunk 8 MB, resumable=True, backoff eksponensial untuk error 5xx/jaringan.
- Session URI + byte terkirim dicatat ke manifes job tiap chunk berhasil;
  bila VM reboot atau koneksi putus, job dilanjutkan dari posisi terakhir
  (session resumable berlaku ±1 minggu), bukan dari nol.
- Berkas 1 jam ±1,96 GB; 3 jam ±11,6 GB; 10 jam ±38 GB (patokan grain
  8,6 Mbps). Upload pertama = pengukuran kecepatan nyata VM (gerbang
  Fase A tersisa: target upload 1 jam ≤ 60 menit).

## 4. Metadata yang diterapkan API

Dari paket metadata hasil Finalisasi (mengikuti standar SEO XD):
title, description (template 900–1.500 karakter + 3 hashtag), tags
(200–350 karakter), categoryId (usul: 10 Music — kategori lazim channel
ambience; keputusan Kevin), defaultLanguage/defaultAudioLanguage = en,
selfDeclaredMadeForKids = false, embeddable = true,
containsSyntheticMedia = true bila visual hasil generate AI
(wajib jujur; untuk footage stok murni = false).

- Privasi awal: **private**. Publikasi lewat `publishAt` terjadwal
  (Selasa & Jumat 19.30 WIB) — video terbit sendiri pada jamnya.
- Thumbnail: thumbnails.set (JPG 1280×720, <2 MB) sesudah insert selesai.
- Playlist: playlistItems.insert ke playlist seri yang sesuai
  (ID playlist disimpan di konfigurasi sesudah Fase 0 membuatnya).

## 5. Verifikasi sesudah upload

- videos.list: uploadStatus = processed, status privasi sesuai jadwal,
  thumbnail terpasang, durasi terbaca benar.
- videoId + URL dicatat ke manifes job + registry CSV sederhana
  di asmr-service (riwayat semua upload).
- TITIK CEK KEBIJAKAN: temuan riset 15 Nov mencatat revisi kebijakan
  2 Nov 2026 menghapus aturan "project API belum diaudit = video
  dipaksa private". Tetap diverifikasi pada upload pertama: bila video
  ternyata terkunci private oleh YouTube, jalur cadangan = ajukan
  audit project, atau upload berkas yang sama lewat Studio dari berkas
  yang sudah di VM (bukan alasan membatalkan Fase C).

## 6. Aturan penyimpanan

YouTube adalah arsip akhir. Berkas output lokal yang sudah terbit
dihapus hari ke-7 sesudah terbit (manifes job mencatat tanggalnya);
total output belum terbit dibatasi 60 GB; pekerjaan baru ditolak
bila disk bebas < 30 GB (sesuai rencana teknis pipeline VM).

## 7. Urutan bangun

1. Google Cloud + OAuth (Kevin ±15 menit, dipandu langkah demi langkah).
2. Modul upload + uji CLI: upload video final hujan kebun sebagai
   unlisted/private → ukur kecepatan (gerbang Fase A) + titik cek
   kebijakan privasi.
3. Balut jadi panel UI + SSE progres + riwayat job.
4. Uji putus-sambung: matikan koneksi di tengah upload, lanjutkan
   dari manifes.
5. Commit + push GitHub; perbarui dokumen pipeline.

## 8. Pembagian kerja

- Kevin: langkah Google Cloud/OAuth (login & persetujuan hanya bisa dia),
  memilih categoryId, menyetujui jadwal publishAt pertama.
- L: semua kode, pengujian, pengukuran, dokumentasi, verifikasi hasil.
