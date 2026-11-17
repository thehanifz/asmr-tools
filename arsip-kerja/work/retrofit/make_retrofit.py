from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

def compose(base_path, out_path, title, sub, band_rgb, badge_text="1 HOUR"):
    base = Image.open(base_path).convert("RGB")
    W, H = base.size
    img = base.convert("RGBA")
    grad = Image.new("L", (1, H), 0)
    for yy in range(H):
        grad.putpixel((0, yy), 0 if yy < H * 0.40 else int(150 * (yy - H * 0.40) / (H * 0.60)))
    grad = grad.resize((W, H))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    img = Image.composite(black, img, grad.point(lambda a: int(a * 0.55))).convert("RGBA")

    f_title = ImageFont.truetype(BOLD, 112)
    f_sub = ImageFont.truetype(BOLD, 40)
    f_badge = ImageFont.truetype(BOLD, 44)

    x = 54
    tb = ImageDraw.Draw(img).textbbox((0, 0), title, font=f_title)
    sb = ImageDraw.Draw(img).textbbox((0, 0), sub, font=f_sub)
    title_h, sub_h = tb[3] - tb[1], sb[3] - sb[1]
    title_y = H - 64 - title_h
    sub_y = title_y - 18 - sub_h
    sub_color = tuple(list(band_rgb) + [255])
    band = tuple(list(band_rgb) + [255])

    def layer(fn, blur=0):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        fn(d)
        return lay.filter(ImageFilter.GaussianBlur(blur)) if blur else lay

    for lay in (
        layer(lambda d: (d.text((x + 4, sub_y + 4), sub, font=f_sub, fill=(0, 0, 0, 210)),
                         d.text((x + 4, title_y + 5), title, font=f_title, fill=(0, 0, 0, 210))), 6),
        layer(lambda d: (d.text((x + 3, sub_y + 3), sub, font=f_sub, fill=(0, 0, 0, 235)),
                         d.text((x + 3, title_y + 3), title, font=f_title, fill=(0, 0, 0, 235)))),
        layer(lambda d: (d.text((x - 1, sub_y - 1), sub, font=f_sub, fill=(255, 255, 255, 110)),
                         d.text((x - 2, title_y - 2), title, font=f_title, fill=(255, 255, 255, 120)))),
        layer(lambda d: (d.text((x, sub_y), sub, font=f_sub, fill=sub_color),
                         d.text((x, title_y), title, font=f_title, fill=(255, 255, 255, 255)))),
    ):
        img = Image.alpha_composite(img, lay)

    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), badge_text, font=f_badge)
    bw, bh = bb[2] - bb[0] + 44, bb[3] - bb[1] + 26
    bx, by = W - 46 - bw, 40
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=16, fill=band)
    d.text((bx + 22 - bb[0], by + 13 - bb[1]), badge_text, font=f_badge, fill=(10, 35, 60, 255))
    d.rectangle([0, H - 18, W, H], fill=band)

    out = img.convert("RGB")
    out.save(out_path, quality=90)
    out.resize((128, 72)).save(out_path.replace(".jpg", "_small.png"))
    print("saved", out_path)

BLUE = (124, 199, 255)
ORANGE = (255, 170, 80)
compose("/home/hatch/workspace/asmr-service/work/retrofit/zdDhAgTYvIo.jpg",
        "/home/hatch/workspace/asmr-service/work/retrofit/thumb_goldengate.jpg",
        "GOLDEN GATE", "RAIN SOUNDS", BLUE)
compose("/home/hatch/workspace/asmr-service/work/retrofit/qHZCotPqvzs.jpg",
        "/home/hatch/workspace/asmr-service/work/retrofit/thumb_campfire.jpg",
        "CAMPFIRE RIVER", "CRACKLING FIRE · RIVER", ORANGE)
