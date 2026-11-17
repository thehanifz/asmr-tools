# Plan Lanjut — ASMR Video Tool & Channel Extra Dimension

_Diperbarui: 17 November 2026. Berkas ini merangkum keadaan pekerjaan produksi konten ASMR/suara alam: apa yang sudah dikerjakan, apa yang belum, dan keputusan yang mengikat. Data kerja pendukung ada di folder `arsip-kerja/` di repo ini._

## Ringkasan

- **Tool:** ASMR Video Tool v2 (repo ini) — FastAPI + vanilla JS, berjalan sebagai layanan di VM dan bisa diakses lewat UI web.
- **Channel:** YouTube **Extra Dimension** (@extradimensionsounds) — suara alam murni untuk tidur, tanpa musik. Eksperimen 4 minggu: upload Selasa & Jumat pukul 19.30 WIB, penilaian akhir 18 Desember 2026 (gerbang: CTR ≥ 2,5%, view 28 hari ≥ 100, impressions ≥ 3.000, subscriber baru ≥ 5; cek tengah 4 Desember 2026).
- **Dokumen rencana lengkap:** `arsip-kerja/dokumen/` (rencana hidup channel, rencana teknis pipeline VM, rencana upload YouTube, standar SEO).

## Sudah dikerjakan

### Tool & pipeline
- Layanan tool berjalan di VM (systemd, uvicorn di 127.0.0.1:8320), UI dapat diakses publik lewat tunnel + Cloudflare Access di subdomain asmr pada domain pemilik.
- Perbaikan UI: pemilih berkas dari server (dialog berkas desktop tidak bisa dipakai di server tanpa layar), dropdown pustaka suara, preview/dengar suara sebelum dirender, endpoint streaming audio/video yang sadar Range.
- Perbaikan audio: seamless loop (acrossfade + aloop sample-accurate) dan pan per-track. Perbaikan video: fade antar-segmen pada hasil merge.
- Render panjang wajib per segmen 15 menit ke folder persisten lalu concat — render satu lintasan pernah mati di tengah karena restart runtime dan berkas di /tmp hilang.

### Channel (Fase 0 — selesai 16 Nov 2026)
- Nama channel diganti menjadi **Extra Dimension**, handle **@extradimensionsounds**, teks About baru tayang, kata kunci channel diganti ke set SEO baru — semuanya terverifikasi lewat API.
- Playlist diatur ulang: payung "Nature Sounds for Sleep" (24 video) + seri "Rain Sounds for Sleep" (12), "Campfire & Fireplace Sounds" (6), "Rain and Fire Sounds" (4). Playlist Clay Animation dijadikan unlisted (tidak dihapus).
- Retrofit thumbnail 2 video lama selesai (Golden Gate; Campfire and River) dengan pita seri berwarna. Dinilai dari CTR pada 25 November 2026.
- Logo: diputuskan tetap memakai logo lama (keputusan 16 Nov 2026). Jangan diangkat lagi kecuali pemilik yang membuka.

### Video pertama (selesai, terjadwal)
- "Rain Sounds for Sleep | Rain Falling in a Quiet Garden (1 Hour)" — render final 3.600 detik terverifikasi frame + audio, thumbnail v2, paket metadata lengkap (manifes: `arsip-kerja/jobs/rain-garden-1hour.json`).
- Terupload lewat YouTube API (videoId `kt2b-rsw9SU`), terjadwal tayang **Selasa 17 November 2026 pukul 19.30 WIB**.
- Parameter poles yang terkunci (untuk video berikutnya): kartu teks judul di kiri bawah (masuk detik 2–4, penuh s.d. detik 10, keluar 10–12), fade video masuk 0–2 detik dan keluar 5 detik terakhir, fade audio masuk 3 detik dan keluar 10 detik terakhir, render per segmen 900 detik CRF 19, audio AAC 256k. Skrip acuan: `arsip-kerja/work/render_final.sh` dan `arsip-kerja/work/make_thumb2.py`.

### Pustaka suara
- 13 berkas aktif berlisensi bersih (CC0/PD/CC BY/CC BY-SA), tercatat dengan kredit di `arsip-kerja/katalog/KATALOG.md`.
- Aturan kurasi permanen: setiap suara wajib lolos **dengar**, bukan hanya lolos metadata teknis. (Pelajaran 15 Nov 2026: berkas hujan pilihan ternyata mengandung musik dan seluruh seri hujan dihapus.)
- Keputusan riset 15 Nov 2026: katalog inti tetap 100% suara alam murni, tanpa musik.

## Belum dikerjakan

1. **OAuth YouTube permanen (paling mendesak — batas ±23 November 2026).** Aplikasi Google Cloud masih mode Testing, sehingga refresh token kedaluwarsa ±7 hari sejak otorisasi 16 Nov 2026. Jalur permanen: halaman privasi di subdomain asmr (PRIVACY.md sudah ada di repo ini) → Publish app → otorisasi ulang satu kali. Kredensial TIDAK disimpan di repo ini.
2. **Trailer channel** dari video terpopuler (Rainy Forest Ambience) — hanya bisa dipasang dari YouTube Studio, manual oleh pemilik.
3. **Panel Finalisasi + Panel Upload YouTube di UI tool** — belum dibangun. Bahan bakunya: parameter poles di atas + skrip upload di `arsip-kerja/skrip/youtube_upload.py`.
4. **Pustaka hujan dan angin masih kosong** — buru ulang rekaman lapangan murni (tanpa musik, tanpa suara orang, lolos dengar). Jalur Freesound memerlukan akun pemilik.
5. **Mastering audio** — loudnorm/EQ/mastering akhir belum dikerjakan; kualitas audio diprioritaskan di atas kecepatan sejak penilaian 7 Nov 2026.
6. **Video versi 3 jam** — DIPARKIR atas keputusan 16 Nov 2026. Berkasnya ada (10.800 detik) tetapi sambungan antar-jam belum mulus (ekor tiap jam memudar ke nyaris senyap lalu melonjak). Jangan dilanjutkan/di-upload tanpa instruksi baru. Manifes: `arsip-kerja/jobs/rain-garden-3hours.json`.
7. **Evaluasi terjadwal** — CTR retrofit 25 Nov 2026; cek tengah eksperimen 4 Des 2026; penilaian akhir 18 Des 2026.
8. **Arsip fisik berkas biner** — audio pustaka, gambar, dan berkas karantina tercatat di `arsip-kerja/DAFTAR-BERKAS-BINER.md` tetapi berkasnya sendiri tidak ikut di repo (konektor GitHub hanya menerima berkas teks). Arsip fisiknya direncanakan di CasaOS.

## Keputusan yang mengikat

- Satu video dikerjakan sampai tuntas (render, arsip, metadata) sebelum pindah ke video berikutnya.
- Setiap klaim soal tampilan wajib diverifikasi visual (screenshot/frame), bukan hanya dari teks/markup.
