from PIL import Image, ImageDraw, ImageFont, ImageFilter

base = Image.open("/home/hatch/workspace/asmr-service/work/thumb_base.png").convert("RGB")
W, H = base.size
img = base.convert("RGBA")

# soft dark gradient on lower part for text contrast
grad = Image.new("L", (1, H), 0)
for yy in range(H):
    grad.putpixel((0, yy), 0 if yy < H * 0.40 else int(150 * (yy - H * 0.40) / (H * 0.60)))
grad = grad.resize((W, H))
black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
img = Image.composite(black, img, grad.point(lambda a: int(a * 0.55))).convert("RGBA")

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
f_title = ImageFont.truetype(BOLD, 118)
f_sound = ImageFont.truetype(BOLD, 40)
f_badge = ImageFont.truetype(BOLD, 44)

def layer(draw_fn, blur=0):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    draw_fn(d)
    return lay.filter(ImageFilter.GaussianBlur(blur)) if blur else lay

# --- text block: sounds line above title, bottom-left ---
sound_text = "RAIN  ·  STREAM  ·  BIRDSONG"
title_text = "GARDEN RAIN"
x = 54
sb = ImageDraw.Draw(img).textbbox((0, 0), sound_text, font=f_sound)
tb = ImageDraw.Draw(img).textbbox((0, 0), title_text, font=f_title)
sound_h, title_h = sb[3] - sb[1], tb[3] - tb[1]
gap = 18
title_y = H - 64 - title_h
sound_y = title_y - gap - sound_h
BLUE = (170, 216, 255, 255)

for lay in (
    layer(lambda d: (d.text((x + 4, sound_y + 4), sound_text, font=f_sound, fill=(0, 0, 0, 210)),
                     d.text((x + 4, title_y + 5), title_text, font=f_title, fill=(0, 0, 0, 210))), 6),
    layer(lambda d: (d.text((x + 3, sound_y + 3), sound_text, font=f_sound, fill=(0, 0, 0, 235)),
                     d.text((x + 3, title_y + 3), title_text, font=f_title, fill=(0, 0, 0, 235)))),
    layer(lambda d: (d.text((x - 1, sound_y - 1), sound_text, font=f_sound, fill=(255, 255, 255, 110)),
                     d.text((x - 2, title_y - 2), title_text, font=f_title, fill=(255, 255, 255, 120)))),
    layer(lambda d: (d.text((x, sound_y), sound_text, font=f_sound, fill=BLUE),
                     d.text((x, title_y), title_text, font=f_title, fill=(255, 255, 255, 255)))),
):
    img = Image.alpha_composite(img, lay)

# --- duration badge: light-blue pill, top-right ---
badge_text = "1 HOUR"
bd = ImageDraw.Draw(img)
bb = bd.textbbox((0, 0), badge_text, font=f_badge)
bw, bh = bb[2] - bb[0] + 44, bb[3] - bb[1] + 26
bx, by = W - 46 - bw, 40
bd.rounded_rectangle([bx, by, bx + bw, by + bh], radius=16, fill=(124, 199, 255, 255))
bd.text((bx + 22 - bb[0], by + 13 - bb[1]), badge_text, font=f_badge, fill=(10, 35, 60, 255))

# --- series band along the bottom edge ---
bd.rectangle([0, H - 18, W, H], fill=(124, 199, 255, 255))

out = img.convert("RGB")
out.save("/home/hatch/workspace/asmr-service/output/rain-sounds-for-sleep-rain-falling-in-a-quiet-garden-1-hour.jpg", quality=90)
out.resize((128, 72)).save("/home/hatch/workspace/asmr-service/work/thumb_v2_small.png")
print("thumb v2 saved")
