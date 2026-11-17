# Daftar Berkas Biner — Tidak Ikut di Repo

_Dicatat 17 November 2026. Konektor GitHub yang dipakai hanya menerima berkas teks (UTF-8), jadi berkas biner di bawah ini tidak ter-push. Daftar ini mencatat keberadaannya (nama, ukuran, sidik jari SHA-256 parsial 16 hex) supaya bisa diverifikasi bila diarsipkan ke tempat lain. Lokasi asal: folder layanan ASMR di VM (`asmr-service/`) dan clone repo (`projects/asmr-tools/`)._

## A. Audio pustaka aktif (berlisensi bersih, kredit di KATALOG.md)

| Berkas | Ukuran (byte) | SHA-256 (16) |
|---|---|---|
| library/api/Bones breaking wood fire ice crackling.ogg | 2.401.748 | b226630ca2a7454e |
| library/api/Campfire sound ambience.ogg | 554.608 | 2237dd545ca990b6 |
| library/air/433589 jackthemurray stream-river-water-up-close.wav | 19.841.038 | be201d2fd0d110fc |
| library/air/Oceanwavescrushing.ogg | 2.849.514 | 2a56648817264b6c |
| library/air/Water flowing pouring trickling.ogg | 4.765.503 | 39b32876bab48f0e |
| library/air/Waterfall and birds sounds.wav | 7.238.352 | e621af3ce6904843 |
| library/air/layer_433589 jackthemurray stream-river-water-up-close.m4a | 119.889.508 | 921d81523ebdec15 |
| library/petir/Mansoura city weather, Heavy rains and thunder.flac | 3.788.205 | defa49664dcbeb28 |
| library/petir/Nosferatu thunderclap - Richard Humphries.wav | 4.814.152 | 338c2d76c4457403 |
| library/petir/Thunder.wav | 6.190.364 | 93b679a7707052ad |
| library/burung/404114 felix-blume toucans-singing-in-the-amazonian-rainforest-brazil.ogg | 7.160.067 | ae89c56723bb7cff |
| library/burung/Birdsong morning 01.ogg | 4.544.824 | 18dde37fcbd85f3d |
| library/burung/Early morning Birdsong Leersum.wav | 71.775.820 | 63c3a5afb1245b70 |
| library/tambahan/Night original format.wav | 5.292.044 | b2fb1630abf14bca |

## B. Audio karantina (tidak lolos kurasi — mengandung suara orang / seri bermasalah)

| Berkas | Ukuran (byte) | SHA-256 (16) |
|---|---|---|
| karantina/WWS Bonfireburning.ogg | 603.446 | 2ceef6d0766ac9c7 |
| karantina/Leaves in the wind (Gravity Sound).wav | 35.343.812 | 8ad10b0b78b4cf65 |
| karantina/Wind in forest (Gravity Sound).wav | 13.778.554 | 125ad683b7a0840b |
| karantina/Wind outside atmosphere (Gravity Sound).wav | 3.938.518 | 3fb6011a73b74466 |
| karantina/Forest ambience (Gravity Sound).wav | 8.744.482 | ee6a2377fd73ec99 |

## C. Gambar

| Berkas | Ukuran (byte) |
|---|---|
| work/intro_text.png (kartu teks video 1 jam) | 90.290 |
| work/thumb_base.png (frame dasar thumbnail) | 1.118.172 |
| work/logo_lama.jpg (logo channel lama) | 241.939 |
| output/rain-sounds-for-sleep-rain-falling-in-a-quiet-garden-1-hour.jpg (thumbnail final) | 238.388 |
| output/rain-sounds-for-sleep-rain-falling-in-a-quiet-garden-3-hours.jpg (thumbnail 3 jam) | 238.725 |
| output/logo-extra-dimension-final.png (draf logo, tidak dipakai) | 760.549 |
| projects/asmr-tools/media/video/thumbs/Rain_falling_in_garden_7f0c1a96_720p.jpg | 221.166 |

## D. Video — dikecualikan dari push atas instruksi pemilik

- Hasil render: `output/…-1-hour.mp4` (1.904.325.106 byte), `output/…-3-hours.mp4` (5.666.449.529 byte).
- Segmen render di `work/` (seg1–seg4, s3h_*) masing-masing ±410–476 MB.
- Berkas video di clone repo `media/video/`: sumber loop 720p (5,3 MB), loop 1 jam (1,84 GB), merge (1,96 GB), final 1 jam (1,90 GB), input00.mp4 (7,4 MB), loop-ba.mp4 (16,5 MB).

## E. Secret — tidak pernah masuk repo

- Kredensial OAuth YouTube (client secret + token) tetap di brankas aman, folder `secrets/` di VM (izin 600/700). Tidak dicatat di berkas mana pun di repo ini.
