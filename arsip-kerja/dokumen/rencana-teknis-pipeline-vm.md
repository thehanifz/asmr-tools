# Rencana Teknis — Pipeline ASMR di VM Muse + Ganti Nama Channel
Disusun: Minggu, 15 Nov 2026 (atas keputusan Kevin malam ini)
Status: RENCANA — belum ada yang dipasang/diubah. Eksekusi menunggu kata Kevin.
Dokumen induk: rencana-hidupkan-xtra-dimention.md (jadwal & eksperimen)
 dan standar-seo-xtra-dimention.md (metadata).

## 0. Keputusan yang melandasi rencana ini
1. Nama channel DIGANTI (keputusan Kevin 15 Nov ~21:00 WIB). Nama baru belum
   dipilih — prosesnya di bagian 7, dikerjakan di Fase 0 (16–18 Nov),
   sebelum upload pertama 20 Nov.
2. Produksi & upload pindah ke VM Muse (bukan PC Kevin, bukan CasaOS):
   alasan Kevin — pakai koneksi internet VM untuk upload, dan berkas video
   berjam-jam terlalu besar untuk dipindah-pindah.
3. UI diakses Kevin lewat tunnel Cloudflare di domainnya sendiri.

## 1. Koreksi topologi penting (temuan verifikasi, bukan pendapat)

Usulan awal: service listen 0.0.0.0 di VM, lalu CasaOS men-tunnel-nya
pakai Cloudflare. Jalur itu TIDAK bisa jalan, karena:

- Klien Tailscale di VM Muse bersifat CLIENT-ONLY (dokumentasi konektor
  Tailscale): hanya membuat koneksi KELUAR, tidak menerima koneksi masuk,
  tidak meng-host apa pun. Jadi CasaOS tidak bisa menjangkau service di VM
  lewat Tailscale, dari arah mana pun.
- VM juga tidak punya alamat publik yang bisa dihubungi masuk; internetnya
  hanya keluar (egress).

Topologi yang BENAR dan mencapai tujuan yang sama persis:

    Browser Kevin
        │  https://asmr.thehanifz.my.id  (nama usulan, Kevin yang putuskan)
        ▼
    Cloudflare Edge ──(Cloudflare Access: hanya email Kevin)──
        │  tunnel keluar (outbound) yang dibuka dari VM
        ▼
    cloudflared DI DALAM VM Muse  ──►  http://127.0.0.1:8320
        ▼
    Service asmr-tools (FastAPI) di VM Muse
        ├── Render worker (ffmpeg, pipeline yang sudah terpasang)
        ├── Penyimpanan kerja lokal VM (disk 144 GB bebas)
        └── Uploader YouTube API (resumable) ──► YouTube
                (upload langsung dari VM, berkas tidak pernah
                 meninggalkan VM sebelum jadi video YouTube)

Perbedaan dari usulan Kevin hanya SATU: program tunnel-nya (cloudflared)
berjalan di VM, bukan di CasaOS. Dari sisi Kevin hasilnya identik:
satu hostname di domainnya, diatur dari dashboard Zero Trust miliknya,
dan CasaOS tidak terlibat sama sekali (tidak terbebani render/upload).
cloudflared di CasaOS yang sekarang (mode token, untuk WordPress) TIDAK
disentuh dan tidak dipakai untuk ini — ini tunnel terpisah.

Konsekuensi listen: service cukup listen di 127.0.0.1:8320 (paling aman —
hanya cloudflared yang bisa menjangkaunya). Bila Kevin tetap ingin
0.0.0.0, bisa, tapi tidak menambah jangkauan apa pun (VM tetap tidak bisa
dihubungi masuk dari luar) dan hanya membuka permukaan di dalam VM.
Rekomendasi rencana ini: 127.0.0.1 + tunnel + Access.

## 2. Kondisi nyata VM (diverifikasi 15 Nov 2026 ~21:05 WIB)

- CPU 4 core, RAM total ±7,7 GB (sel bersama — ffmpeg dibatasi 2 thread
  dan prioritas rendah agar tidak mengganggu cron SkorNalar tiap jam)
- Disk: 150 GB total, 144 GB bebas — cukup untuk antrean kerja, BUKAN
  untuk arsip permanen (aturan hapus di bagian 5)
- ffmpeg 8.1.2 dan Python 3.12.3 sudah terpasang
- Clone repo sudah ada dan bersih: ~/workspace/projects/asmr-tools
  di commit ac86354 (sudah termasuk patch seamless loop + fade segmen)
- systemd user tersedia (untuk service yang hidup lagi setelah restart)
- cloudflared BELUM terpasang (dipasang di Fase B, di ~/workspace/tools
  agar selamat dari penggantian VM — home VM persisten)
- Kecepatan upload VM BELUM pernah diukur ke YouTube — wajib diukur di
  Fase A sebelum jadwal upload dikunci (lihat gerbang Fase A)

Ukuran berkas patokan (klip grain ekstrem 8,6 Mbps, kasus terburuk):
1 jam ±3,9 GB · 3 jam ±11,6 GB · 10 jam ±38 GB.
Adegan ambience nyata (banyak diam/statis, CRF 18–20) diperkirakan jauh
lebih kecil; angka pastinya dari render uji Fase A, dan patokan ukuran
resmi eksperimen ditulis dari angka itu, bukan dari perkiraan ini.

## 3. Komponen yang dibangun

A. Service UI — asmr-tools apa adanya (FastAPI + frontend repo Kevin).
   Dijalankan sebagai systemd user service `asmr-tools-vm`, listen
   127.0.0.1:8320, Restart=always. Tidak ada perubahan fitur repo di fase
   ini selain konfigurasi jalan (host/port/path data).
B. Tunnel — cloudflared (binary resmi, di ~/workspace/tools/cloudflared),
   systemd user service `cloudflared-asmr`, mode token. Token tunnel
   adalah kredensial: disimpan di berkas env izin 600 di luar repo,
   tidak ditulis di chat/memory/git. Kevin membuat tunnel-nya dari
   dashboard Zero Trust (tunnel CasaOS membuktikan rute token hanya bisa
   diatur dari dashboard Kevin — untuk tunnel VM ini sama).
C. Gerbang akses — Cloudflare Access pada hostname itu: kebijakan hanya
   alamat email Kevin (OTP/Google). WAJIB aktif sebelum hostname diumumkan
   jalan: UI asmr-tools tidak punya login sendiri, dan di dalamnya nanti
   ada tombol upload ke YouTube — tidak boleh terbuka publik.
   Lapisan kedua: service hanya listen localhost (bagian 1).
D. Modul uploader BARU — `api/youtube_upload.py` di clone lokal
   (belum ada di repo; modul live yang ada itu streaming, bukan upload):
   - YouTube Data API v3, endpoint videos.insert, protokol RESUMABLE
     upload: berkas dikirim per potongan, sesi upload (URI) disimpan di
     manifes job, sehingga upload yang terputus (VM diganti, service
     restart, jaringan putus) DILANJUTKAN, bukan diulang dari nol.
   - Sekali jalan juga: thumbnails.set (thumbnail kustom dari paket SEO),
     metadata dari paket SEO (judul/deskripsi/tag/kategori/bahasa),
     status terjadwal (publishAt sesuai jadwal Selasa/Jumat 19.30 WIB —
     video boleh diupload lebih awal sebagai private terjadwal),
     containsSyntheticMedia bila videonya hasil AI, dan
     playlistItems.insert ke playlist serinya.
   - OAuth: Kevin menyetujui SEKALI lewat layar consent Google
     (scope youtube.upload + youtube). Token refresh disimpan terenkripsi
     di luar repo (izin 600), tidak pernah masuk git/chat.
   - Google Cloud project: dibuat Kevin (atau L memandu langkahnya) —
     API ini gratis; kuota upload 100 panggilan/hari di bucket terpisah
     (terverifikasi 6 Nov 2026). Catatan kebijakan per revisi 2 Nov 2026:
     project API yang belum diaudit TIDAK lagi dipaksa private.
E. Manifes job — satu berkas JSON per video di
   ~/workspace/asmr-service/jobs/<id>.json: sumber, parameter render,
   tahap (render/upload/terjadwal/terbit), URI sesi resumable, ID video
   YouTube hasil, dan cap waktu. Inilah yang membuat pekerjaan selamat
   dari restart: service bangun → baca manifes → lanjutkan tahap terakhir.
   Render memakai pipeline fade-segmen yang sudah ada (kepala/ekor
   di-encode, tengah stream-copy) — segmen adalah checkpoint alaminya.
F. Penjadwalan — tahap awal manual dari UI / perintah Kevin di chat.
   Otomatisasi penuh (cron render+upload sendiri) BUKAN bagian rencana
   ini; ditimbang ulang setelah 2 upload pertama terbukti mulus.

## 4. Alur kerja satu video (sesudah semua fase jalan)

1. Kevin (atau L) menaruh bahan di UI: klip sumber pendek + audio eksternal
   ±3 menit — berkas kecil, naik lewat tunnel dalam hitungan menit.
   (Bahan TIDAK perlu diunduh Kevin dari mana pun sesudah jadi.)
2. Di UI: pilih preset eksperimen (durasi 1 jam / 3 jam, pola judul &
   paket SEO dari standar-seo-xtra-dimention.md bagian 11).
3. Render jalan di VM (patokan lama: ±9–10 menit per jam di VM uji untuk
   jalur ramping; angka resmi dari Fase A). Progres terlihat di UI
   (log SSE yang sudah ada di repo).
4. QC: L memeriksa frame + sambungan loop secara visual dari hasil render
   (aturan lama: verifikasi tampilan itu visual, bukan teks).
5. Upload resumable dari VM langsung ke YouTube sebagai private terjadwal
   (publishAt = jadwal tayang), lengkap dengan thumbnail + playlist.
6. L memverifikasi di Studio/halaman publik: judul, thumbnail, status
   terjadwal, playlist — lalu melapor ke Kevin dengan ID video + tautan.
7. Berkas hasil di VM dihapus 7 hari sesudah terbit terverifikasi
   (bagian 5). Yang disimpan permanen hanya manifes + log.

## 5. Aturan penyimpanan (disk 144 GB, jangan sampai penuh)

- Folder kerja: ~/workspace/asmr-service/{inbox,work,output,jobs,logs}
- Batas kerja: total output belum terbit maksimal 60 GB; pekerjaan baru
  tidak dimulai bila bebas disk < 30 GB (service menolak + melapor).
- Output terbit & terverifikasi: hapus otomatis pada hari ke-7.
- Inbox sumber: hapus setelah video terkait terbit.
- TIDAK ada salinan hasil render yang dikirim ke CasaOS/Drive —
  YouTube adalah arsipnya; sumber asli tetap milik Kevin di tempatnya.

## 6. Fase eksekusi & gerbang lolos (urutan wajib)

Fase A — Uji dasar (tugas L, ±1 sesi):
  A1. Ukur kecepatan upload nyata VM: unggah uji resumable 1 berkas
      ±1 GB sebagai video PRIVATE ke channel (sesudah Fase C OAuth siap;
      bila OAuth belum siap, ukur ke endpoint uji Google/resumable lain
      dan tandai sebagai perkiraan).
      → Sebenarnya A1 bergantung C; urutan praktis: C dulu sebagian.
  A2. Render uji 1 jam dari loop hujan 5 menit yang sudah jadi:
      catat waktu render, ukuran berkas nyata, RAM/CPU terpakai.
  GERBANG A: waktu render 1 jam ≤ 30 menit DAN perkiraan upload 1 jam
  ≤ 60 menit. Bila gagal: jadwal eksperimen disesuaikan (upload malam
  sebelumnya sebagai private terjadwal — memang desain D sudah begitu),
  bukan dipaksakan.

Fase B — Service + tunnel (L memasang, Kevin membuat tunnel & Access):
  STATUS 15 Nov ~21:12 — TOPOLOGI DIGANTI (v2, terverifikasi ujung ke
  ujung), karena jalur cloudflared-dari-VM terbukti BUNTU:
  cloudflared 2026.11.0 memang terpasang di VM (sha256 cocok digest
  GitHub) dan token tunnel baru dari Kevin sudah dicoba, tetapi jaringan
  VM memblokir edge Cloudflare: UDP 7844 dilarang ("operation not
  permitted"), TCP 7844 dialihkan gateway ke proxy internal dan TLS-nya
  timeout; cloudflared tidak bisa memakai HTTP proxy untuk koneksi
  edge-nya. Token tunnel baru SUDAH DIHAPUS dari VM dan service
  cloudflared-asmr dimatikan — tunnel baru itu sebaiknya dihapus Kevin
  dari dashboard (tidak terpakai).
  JALUR v2 YANG JALAN (desain asli Kevin: tunnel dari CasaOS):
    Browser → Cloudflare → cloudflared CasaOS (tunnel LAMA Kevin)
      → http://192.168.100.3:18320 (origin)
      → service CasaOS `asmr-fwd` (socat LAN:18320 → 127.0.0.1:18320)
      → jembatan reverse SSH `vm-reverse-asmr` di VM
        (ssh -R 127.0.0.1:18320:127.0.0.1:8320 ke endpoint SSH CasaOS,
         systemd, Restart=always, kunci khusus yang sudah ada)
      → service asmr-tools VM di 127.0.0.1:8320.
  Kedua service jembatan SUDAH terpasang + aktif + terverifikasi:
  server uji di VM:8320 menjawab 200 dari 127.0.0.1:18320 CasaOS DAN
  dari 192.168.100.3:18320 (alamat origin persis yang dipakai
  cloudflared CasaOS). Catatan lomba start pertama: start perdana
  vm-reverse-asmr sempat balapan dengan ssh uji manual sehingga
  forward tidak terbentuk walau service "active" — sesudah restart
  bersih normal; health-check wajib memeriksa LISTENER di CasaOS,
  bukan hanya status service.
  SISA Fase B di tangan Kevin: tambah public hostname
  asmr.thehanifz.my.id pada tunnel CasaOS yang LAMA → origin
  http://192.168.100.3:18320, plus kebijakan Access email Kevin.
  Sesudah itu L verifikasi dari internet publik.
  STATUS FASE B SELESAI 15 Nov ~21:20: Kevin memasang hostname +
  Access (sempat keliru origin https://localhost:18320 → 502 TLS;
  diperbaiki Kevin menjadi http://192.168.100.3:18320 atas diagnosis
  dari log cloudflared CasaOS). Service asmr-tools ASLI sudah dipasang
  L sebagai systemd `asmr-tools-vm` (venv di clone repo, uvicorn
  127.0.0.1:8320, WorkingDirectory repo). Terverifikasi tiga lapis:
  lokal VM 200 (judul "ASMR Tools"), origin CasaOS 192.168.100.3:18320
  200, publik tanpa login 302 ke Cloudflare Access
  (thehanifz97.cloudflareaccess.com) dan dari browser Kevin yang
  lolos Access menampilkan UI. GERBANG B LOLOS.
  B1. Pasang cloudflared + dua systemd user service; service lokal
      menjawab di 127.0.0.1:8320 dari dalam VM.
  B2. Kevin: buat tunnel baru di Zero Trust + public hostname
      (usulan asmr.thehanifz.my.id) → localhost:8320, lalu kebijakan
      Access khusus email Kevin. (Token tunnel Kevin serahkan lewat
      jalur aman, bukan ditempel di chat biasa bila bisa dihindari.)
  B3. Uji dari HP/PC Kevin: hostname membuka UI sesudah login Access;
      tanpa login Access DITOLAK. Uji juga sesudah service di-restart:
      tunnel & UI pulih sendiri.
  GERBANG B: kedua uji B3 lolos. Bila tunnel dari VM ternyata diblokir
  jaringan VM, rencana cadangan: UI tetap dipakai lewat L (Kevin perintah
  lewat chat, L yang mengoperasikan UI lokal) — produksi tidak berhenti,
  hanya akses langsung Kevin yang tertunda.

Fase C — YouTube API (Kevin consent, L membangun modul):
  C1. Google Cloud project + aktifkan YouTube Data API v3 + layar consent.
  C2. Kevin menyetujui OAuth sekali (akun pemilik channel).
  C3. Modul uploader selesai + uji: upload video uji PRIVATE 10 menit
      dengan thumbnail & metadata paket SEO; matikan service di tengah
      upload, nyalakan lagi — upload WAJIB melanjutkan dan selesai.
  GERBANG C: uji putus-nyambung lolos + video uji tampil benar di Studio.

Fase D — Ganti nama + Fase 0 channel (bagian 7) — sejajar dengan B/C,
  selesai paling lambat Rabu 18 Nov.

Fase E — Upload pertama sungguhan: video #1 eksperimen (Jumat 20 Nov)
  lewat pipa penuh (render VM → upload terjadwal → terbit 19.30 WIB).
  GERBANG E: terbit dengan metadata persis paket SEO #1 + terverifikasi
  publik oleh L. Sesudah itu ritme Selasa/Jumat berjalan seperti dokumen
  rencana, dan kegagalan satu tahap dilaporkan dengan tahapnya, bukan
  sebagai "gagal upload" umum.

## 7. Ganti nama channel (keputusan sudah diambil; nama belum)

1. L menyiapkan 5–8 kandidat nama: pola [kata niche] + Dimension
   (mempertahankan akar brand lama, ejaan dibetulkan) DAN pola deskriptif
   penuh; tiap kandidat dicek: (a) handle @-nya bebas di YouTube,
   (b) pencarian nama persisnya tidak bertabrakan dengan channel besar,
   (c) lolos tes sekali dengar → bisa diketik benar.
2. Kevin memilih satu (keputusan nama tetap milik Kevin).
3. Perubahan dikerjakan di Studio saat Fase 0: nama + handle baru,
   banner & avatar disesuaikan (teks nama di banner diganti), About versi
   baru (sudah disiapkan di dokumen rencana), kata kunci channel versi
   standar SEO. Video lama TIDAK diedit massal; boilerplate deskripsi
   lama yang menyebut nama lama dibiarkan (biaya edit 28 video tidak
   sebanding) kecuali 3 video teratas.
4. Catatan teknis: mengganti nama/handle tidak menghapus subscriber,
   video, atau view; URL berbasis channel ID tetap. Handle lama bisa
   diklaim pihak lain sesudah masa tenggang — diterima sebagai biaya
   keputusan, dicatat di sini agar tidak kaget.
5. Dokumen rencana & SEO diperbarui dengan nama baru pada hari yang sama
   (tag merek di set tag diganti: nama baru + "xtra dimention" tetap
   dipertahankan sebagai tag salah eja warisan selama eksperimen).

## 8. Risiko yang sudah dikenali & penangannya
- VM Muse bisa diganti runtime sewaktu-waktu (proses mati, home tetap):
  ditangani systemd Restart=always + manifes job + upload resumable +
  render per segmen. Diverifikasi paksa di gerbang C3/B3, bukan diasumsikan.
- CPU/RAM VM berbagi dengan cron berita SkorNalar: ffmpeg dibatasi
  2 thread + nice rendah; render panjang (3 jam) dijadwalkan di luar
  jam pantauan padat bila terbukti mengganggu (diukur di Fase A2).
- Token OAuth/tunnel bocor = orang bisa upload ke channel: token di luar
  repo, izin 600, tidak dicatat di memory/chat; Access membatasi UI.
- Kuota/kebijakan YouTube berubah: pipa ini memakai API resmi, bukan
  otomasi browser Studio — jalur browser tetap ada sebagai cadangan
  manual terakhir, bukan andalan.
- Tunnel bergantung internet VM & Cloudflare: bila tunnel mati, service
  lokal dan antrean job TIDAK hilang; upload tetap bisa jalan dari VM
  (yang butuh tunnel hanya UI Kevin, bukan uploader-nya).

## 9. Yang harus Kevin lakukan (sisanya L)
1. Pilih nama baru dari kandidat (bagian 7.1).
2. Buat tunnel + hostname + kebijakan Access di Zero Trust (dipandu L
   langkah demi langkah; ±10 menit).
3. Buat/setujui Google Cloud project + consent OAuth sekali (±10 menit).
4. Menyetujui mulai eksekusi Fase A–C (rencana ini sendiri belum
   memasang apa pun).
