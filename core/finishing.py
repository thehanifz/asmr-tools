"""Finishing: intro card + fade in/out + thumbnail baku untuk video final.

Standar channel (dari video pertama "Rain Falling in a Quiet Garden",
16 Nov 2026; resep asli tersimpan di arsip-kerja/work/render_final.sh,
make_overlay.py, make_thumb2.py):

VIDEO
- Fade in video 2 detik dari hitam di awal + audio fade in 3 detik.
- Intro card 3 baris di kiri bawah, muncul (fade in) detik 2-4,
  tampil penuh sampai detik 10, menghilang (fade out) detik 10-12:
    baris 1 = judul adegan            (diisi user, sekali)
    baris 2 = janji suasana (BAKU)    "Pure nature sounds for sleep and relaxation"
    baris 3 = elemen suara            (otomatis dari job Sound Layer)
- Fade out di akhir: video 5 detik, audio 10 detik.
- Yang di-encode ulang hanya kepala (s.d. keyframe pertama >= 13 dtk)
  dan ekor (dari keyframe terakhir <= durasi-15 dtk); tengah stream-copy,
  lalu concat — jadi finishing video 3 jam hanya butuh beberapa menit.

THUMBNAIL (dari frame bersih video jadi, detik 13)
- Badge pil biru #7CC7FF teks dongker #0A233C di kanan atas = durasi.
- Baris elemen suara #AAD8FF di atas judul, judul adegan PENDEK putih
  besar ber-outline hitam di kiri bawah, strip #7CC7FF di tepi bawah.
"""
import json
import os
import re
import subprocess

# ── Konstanta baku channel ──────────────────────────────────────────────
MOOD_LINE = "Pure nature sounds for sleep and relaxation"
BLUE_STRIP = (124, 199, 255)   # #7CC7FF badge + strip bawah
BLUE_TEXT = (170, 216, 255)    # #AAD8FF baris elemen suara di thumbnail
NAVY = (10, 35, 60)            # #0A233C teks di dalam badge
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# ── Label tampilan untuk file pustaka ───────────────────────────────────
# stem (tanpa awalan grup) -> (label intro, label thumbnail)
_LABELS = {
    "water_river": ("River", "RIVER"),
    "water_waterfall": ("Waterfall", "WATERFALL"),
    "water_stream": ("Stream", "STREAM"),
    "water_lake": ("Lake water", "LAKE"),
    "water_drops": ("Water drops", "DROPS"),
    "water_rain_puddle": ("Rain puddles", "RAIN"),
    "frogs_crickets": ("Frogs and crickets", "FROGS & CRICKETS"),
    "crickets": ("Crickets", "CRICKETS"),
    "frogs": ("Frogs", "FROGS"),
    "birds": ("Birdsong", "BIRDSONG"),
    "birdsong": ("Birdsong", "BIRDSONG"),
    "rain_light": ("Light rain", "RAIN"),
    "rain_heavy": ("Heavy rain", "RAIN"),
    "rain_leaves": ("Rain on leaves", "RAIN"),
    "rain_roof": ("Rain on roof", "RAIN"),
    "rain_window": ("Rain on window", "RAIN"),
    "thunder_distant": ("Distant thunder", "THUNDER"),
    "thunder": ("Thunder", "THUNDER"),
    "ocean_waves": ("Ocean waves", "WAVES"),
    "waves": ("Ocean waves", "WAVES"),
    "fire_crackle": ("Campfire", "CAMPFIRE"),
    "campfire": ("Campfire", "CAMPFIRE"),
    "wind_soft": ("Soft wind", "WIND"),
    "wind_trees": ("Wind in trees", "WIND"),
    "night_crickets": ("Night crickets", "CRICKETS"),
}


def _stem_label(path: str) -> tuple[str, str]:
    """Nama file pustaka -> (label intro, label thumbnail)."""
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    if stem in _LABELS:
        return _LABELS[stem]
    parts = stem.split("_")
    # Buang awalan grup yang terduplikasi, mis. nature_night_frogs_crickets
    # -> frogs_crickets; air/water_river -> water_river (tetap dikenal).
    # Cek dari sufiks TERPANJANG dulu agar frasa utuh menang.
    for n in range(1, len(parts)):
        cand = "_".join(parts[n:])
        if cand in _LABELS:
            return _LABELS[cand]
    # Fallback: rapikan nama file apa adanya.
    words = [p for p in parts if p not in ("nature", "day", "night", "water", "air")]
    if not words:
        words = parts
    intro = " ".join(words).capitalize()
    return intro, intro.upper()


def compose_sound_lines(plan: dict) -> tuple[str, str]:
    """Susun baris elemen suara dari plan Sound Layer.

    Mengembalikan (baris intro, baris thumbnail). Suara utama disebut
    apa adanya; suara sisipan (placements) dirangkum dengan imbuhan
    "in some segments" di baris intro.
    """
    mains: list[tuple[str, str]] = []
    seen = set()
    for s in plan.get("main_sounds", []):
        lab = _stem_label(s.get("path", ""))
        if lab[0] not in seen:
            seen.add(lab[0])
            mains.append(lab)
    opts: list[tuple[str, str]] = []
    for p in plan.get("placements", []):
        lab = _stem_label(p.get("source_file", ""))
        if lab[0] not in seen:
            seen.add(lab[0])
            opts.append(lab)
    intro_parts = [m[0] for m in mains] + [o[0] for o in opts]
    intro = "  ·  ".join(intro_parts)
    if opts and intro:
        intro += " in some segments"
    thumb = "  ·  ".join([m[1] for m in mains] + [o[1] for o in opts])
    return intro, thumb


def find_sound_layer_plan(audio_path: str, jobs_dir: str) -> dict | None:
    """Cari plan Sound Layer yang menghasilkan file audio ini."""
    if not audio_path or not os.path.isdir(jobs_dir):
        return None
    target = os.path.abspath(audio_path)
    try:
        names = sorted(os.listdir(jobs_dir), reverse=True)
    except OSError:
        return None
    for name in names:
        if not (name.startswith("job_") and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(jobs_dir, name)) as f:
                job = json.load(f)
        except Exception:
            continue
        out = job.get("output_path") or (job.get("payload") or {}).get("output_path")
        if out and os.path.abspath(out) == target:
            plan = (job.get("payload") or {}).get("plan")
            if plan:
                return plan
    return None


def duration_badge(seconds: float) -> str:
    """Teks badge durasi: jam penuh untuk >= 1 jam, selain itu menit."""
    if seconds >= 3600:
        h = int(round(seconds / 3600))
        return f"{h} HOUR" if h == 1 else f"{h} HOURS"
    m = int(round(seconds / 60))
    return f"{m} MINUTES"


# ── Probe ───────────────────────────────────────────────────────────────
def probe_video(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,avg_frame_rate,sample_rate",
         "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, timeout=120,
    )
    data = json.loads(out.stdout)
    info = {"duration": float(data["format"]["duration"])}
    for st in data["streams"]:
        if st["codec_type"] == "video":
            info["width"] = st["width"]
            info["height"] = st["height"]
            num, den = st["avg_frame_rate"].split("/")
            info["fps"] = float(num) / float(den or 1)
        elif st["codec_type"] == "audio":
            info["sample_rate"] = int(st["sample_rate"])
    return info


def keyframes_in(path: str, start: float, length: float) -> list[float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v",
         "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
         "-of", "csv=p=0", "-read_intervals", f"{start}%+{length}", path],
        capture_output=True, text=True, timeout=300,
    )
    times = []
    for line in out.stdout.splitlines():
        line = line.strip().rstrip(",")
        if line:
            try:
                times.append(float(line))
            except ValueError:
                pass
    return sorted(times)


# ── Gambar: overlay intro + thumbnail ───────────────────────────────────
def make_overlay_png(path: str, width: int, height: int,
                     line1: str, line2: str, line3: str) -> str:
    """PNG RGBA intro card, pola persis make_overlay.py (diskalakan)."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    s = width / 1280.0
    f_title = ImageFont.truetype(FONT_BOLD, max(12, int(47 * s)))
    f_desc = ImageFont.truetype(FONT_BOLD, max(10, int(28 * s)))
    f_sound = ImageFont.truetype(FONT_REG, max(10, int(27 * s)))
    lines = []
    if line1:
        lines.append((line1, f_title, (255, 255, 255, 255)))
    if line2:
        lines.append((line2, f_desc, (240, 243, 250, 245)))
    if line3:
        lines.append((line3, f_sound, (215, 228, 245, 240)))
    gaps = [int(16 * s), int(10 * s), 0][:len(lines)]

    measure = ImageDraw.Draw(Image.new("RGBA", (width, height)))
    heights = []
    for text, font, _ in lines:
        b = measure.textbbox((0, 0), text, font=font)
        heights.append(b[3] - b[1])
    block_h = sum(heights) + sum(gaps[:len(lines)])
    x = int(64 * s)
    y = height - int(84 * s) - block_h

    def render(draw_fn):
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        yy = y
        for (text, font, _), h, g in zip(lines, heights, gaps):
            draw_fn(d, yy, text, font)
            yy += h + g
        return layer

    soft = render(lambda d, yy, t, f: d.text(
        (x + 3 * s, yy + 4 * s), t, font=f, fill=(0, 0, 0, 200))
    ).filter(ImageFilter.GaussianBlur(max(1, int(5 * s))))
    hard = render(lambda d, yy, t, f: d.text(
        (x + 2 * s, yy + 2 * s), t, font=f, fill=(0, 0, 0, 230)))
    high = render(lambda d, yy, t, f: d.text(
        (x - 1 * s, yy - 1 * s), t, font=f, fill=(255, 255, 255, 110)))
    main = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    md = ImageDraw.Draw(main)
    yy = y
    for (text, font, color), h, g in zip(lines, heights, gaps):
        md.text((x, yy), text, font=font, fill=color)
        yy += h + g

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for layer in (soft, hard, high, main):
        img = Image.alpha_composite(img, layer)
    img.save(path)
    return path


def make_thumbnail(frame_path: str, out_path: str, badge: str,
                   sound_line: str, title: str) -> str:
    """Thumbnail baku channel, pola persis make_thumb2.py (diskalakan)."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    base = Image.open(frame_path).convert("RGB")
    W, H = base.size
    img = base.convert("RGBA")

    # Gradien gelap lembut di bagian bawah untuk kontras teks
    grad = Image.new("L", (1, H), 0)
    for yy in range(H):
        grad.putpixel((0, yy), 0 if yy < H * 0.40 else int(150 * (yy - H * 0.40) / (H * 0.60)))
    grad = grad.resize((W, H))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img = Image.composite(black, img, grad.point(lambda a: int(a * 0.55))).convert("RGBA")

    s = W / 1280.0
    f_badge = ImageFont.truetype(FONT_BOLD, max(12, int(44 * s)))
    f_sound = ImageFont.truetype(FONT_BOLD, max(10, int(40 * s)))

    def fit_font(text: str, start: int, max_w: int):
        size = start
        d = ImageDraw.Draw(img)
        while size > 24:
            f = ImageFont.truetype(FONT_BOLD, int(size * s))
            if d.textbbox((0, 0), text, font=f, stroke_width=int(8 * s))[2] <= max_w:
                return f
            size -= 6
        return ImageFont.truetype(FONT_BOLD, int(24 * s))

    f_title = fit_font(title, 118, W - int(108 * s))

    def layer(draw_fn, blur=0):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        draw_fn(d)
        return lay.filter(ImageFilter.GaussianBlur(blur)) if blur else lay

    x = int(54 * s)
    d0 = ImageDraw.Draw(img)
    sb = d0.textbbox((0, 0), sound_line, font=f_sound)
    tb = d0.textbbox((0, 0), title, font=f_title, stroke_width=int(8 * s))
    sound_h, title_h = sb[3] - sb[1], tb[3] - tb[1]
    gap = int(18 * s)
    title_y = H - int(64 * s) - title_h
    sound_y = title_y - gap - sound_h
    BLUE = BLUE_TEXT + (255,)

    for lay in (
        layer(lambda d: (d.text((x + 4, sound_y + 4), sound_line, font=f_sound, fill=(0, 0, 0, 210)),
                         d.text((x + 4, title_y + 5), title, font=f_title, fill=(0, 0, 0, 210))), 6),
        layer(lambda d: (d.text((x + 3, sound_y + 3), sound_line, font=f_sound, fill=(0, 0, 0, 235)),
                         d.text((x + 3, title_y + 3), title, font=f_title, fill=(0, 0, 0, 235)))),
        layer(lambda d: (d.text((x - 1, sound_y - 1), sound_line, font=f_sound, fill=(255, 255, 255, 110)),
                         d.text((x - 2, title_y - 2), title, font=f_title, fill=(255, 255, 255, 120)))),
        layer(lambda d: (d.text((x, sound_y), sound_line, font=f_sound, fill=BLUE),
                         d.text((x, title_y), title, font=f_title, fill=(255, 255, 255, 255),
                                stroke_width=int(8 * s), stroke_fill=(0, 0, 0)))),
    ):
        img = Image.alpha_composite(img, lay)

    bd = ImageDraw.Draw(img)
    bb = bd.textbbox((0, 0), badge, font=f_badge)
    bw, bh = bb[2] - bb[0] + int(44 * s), bb[3] - bb[1] + int(26 * s)
    bx, by = W - int(46 * s) - bw, int(40 * s)
    bd.rounded_rectangle([bx, by, bx + bw, by + bh], radius=int(16 * s), fill=BLUE_STRIP + (255,))
    bd.text((bx + int(22 * s) - bb[0], by + int(13 * s) - bb[1]), badge,
            font=f_badge, fill=NAVY + (255,))
    bd.rectangle([0, H - int(18 * s), W, H], fill=BLUE_STRIP + (255,))

    img.convert("RGB").save(out_path, quality=92)
    return out_path


# ── Perintah ffmpeg ─────────────────────────────────────────────────────
def head_command(src: str, overlay: str, out: str, head_end: float,
                 fps: float, sample_rate: int) -> list[str]:
    fc = ("[1:v]format=rgba,fade=t=in:st=2:d=2:alpha=1,"
          "fade=t=out:st=10:d=2:alpha=1[ov];"
          "[0:v]fade=t=in:st=0:d=2[vf];[vf][ov]overlay=0:0[vout];"
          "[0:a]afade=t=in:st=0:d=3[aout]")
    return ["ffmpeg", "-y", "-v", "error",
            "-ss", "0", "-t", f"{head_end:.4f}", "-i", src,
            "-loop", "1", "-t", f"{head_end:.4f}", "-i", overlay,
            "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-crf", "19", "-preset", "medium",
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
            "-c:a", "aac", "-b:a", "320k", "-ar", str(sample_rate), out]


def middle_command(src: str, out: str, head_end: float, tail_start: float) -> list[str]:
    return ["ffmpeg", "-y", "-v", "error",
            "-ss", f"{head_end:.4f}", "-i", src,
            "-t", f"{tail_start - head_end:.4f}", "-c", "copy", out]


def tail_command(src: str, out: str, tail_start: float, tail_len: float,
                 fps: float, sample_rate: int) -> list[str]:
    v_st = max(0.0, tail_len - 5)
    a_st = max(0.0, tail_len - 10)
    return ["ffmpeg", "-y", "-v", "error",
            "-ss", f"{tail_start:.4f}", "-i", src,
            "-vf", f"fade=t=out:st={v_st:.3f}:d=5",
            "-af", f"afade=t=out:st={a_st:.3f}:d=10",
            "-c:v", "libx264", "-crf", "19", "-preset", "medium",
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
            "-c:a", "aac", "-b:a", "320k", "-ar", str(sample_rate), out]


def single_command(src: str, overlay: str, out: str, duration: float,
                   fps: float, sample_rate: int) -> list[str]:
    """Video pendek (< 90 dtk): satu kali encode untuk seluruh file."""
    v_st = max(0.0, duration - 5)
    a_st = max(0.0, duration - 10)
    fc = ("[1:v]format=rgba,fade=t=in:st=2:d=2:alpha=1,"
          "fade=t=out:st=10:d=2:alpha=1[ov];"
          f"[0:v]fade=t=in:st=0:d=2,fade=t=out:st={v_st:.3f}:d=5[vf];"
          "[vf][ov]overlay=0:0[vout];"
          f"[0:a]afade=t=in:st=0:d=3,afade=t=out:st={a_st:.3f}:d=10[aout]")
    return ["ffmpeg", "-y", "-v", "error",
            "-i", src, "-loop", "1", "-i", overlay,
            "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-crf", "19", "-preset", "medium",
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
            "-c:a", "aac", "-b:a", "320k", "-ar", str(sample_rate),
            "-shortest", out]


def plan_segments(duration: float, kfs_head: list[float],
                  kfs_tail: list[float]) -> tuple[float, float]:
    """Pilih titik potong: kepala = keyframe pertama >= 13 dtk;
    ekor = keyframe terakhir dengan panjang ekor >= 15 dtk."""
    head_end = next((t for t in kfs_head if t >= 13.0), None)
    tail_start = None
    for t in kfs_tail:
        if duration - t >= 15.0:
            tail_start = t
    if head_end is None or tail_start is None or tail_start <= head_end:
        raise ValueError("Keyframe tidak cukup untuk segmentasi finishing")
    return head_end, tail_start


def default_scene_title(video_path: str) -> str:
    stem = os.path.splitext(os.path.basename(video_path))[0]
    stem = re.sub(r"^(merge|loop|crop|final)[_\-\s]*", "", stem, flags=re.I)
    stem = re.sub(r"^[a-f0-9]{8,}[_\-\s]*", "", stem)
    words = [w for w in re.split(r"[_\-]+", stem) if w and not w.isdigit()]
    return " ".join(words).title()


def default_thumb_title(scene_title: str) -> str:
    words = [w for w in re.split(r"\s+", scene_title.strip()) if w]
    return " ".join(words[:2]).upper() if words else ""
