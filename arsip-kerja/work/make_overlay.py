from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
REG  = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
f_title = ImageFont.truetype(BOLD, 47)
f_desc  = ImageFont.truetype(BOLD, 28)
f_sound = ImageFont.truetype(REG, 27)

lines = [
    ("Rain Falling in a Quiet Garden", f_title, (255, 255, 255, 255)),
    ("Pure nature sounds for sleep and relaxation", f_desc, (240, 243, 250, 245)),
    ("Flowing water  ·  Light rain  ·  Birdsong in some segments", f_sound, (215, 228, 245, 240)),
]
gap_after = [16, 10, 0]

measure = ImageDraw.Draw(Image.new("RGBA", (W, H)))
heights = []
for text, font, _ in lines:
    b = measure.textbbox((0, 0), text, font=font)
    heights.append(b[3] - b[1])
block_h = sum(heights) + sum(gap_after)
x = 64
y = H - 84 - block_h

def render_layer(draw_fn):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    yy = y
    for (text, font, _), h, g in zip(lines, heights, gap_after):
        draw_fn(d, yy, text, font)
        yy += h + g
    return layer

soft = render_layer(lambda d, yy, t, f: d.text((x + 3, yy + 4), t, font=f, fill=(0, 0, 0, 200))).filter(ImageFilter.GaussianBlur(5))
hard = render_layer(lambda d, yy, t, f: d.text((x + 2, yy + 2), t, font=f, fill=(0, 0, 0, 230)))
high = render_layer(lambda d, yy, t, f: d.text((x - 1, yy - 1), t, font=f, fill=(255, 255, 255, 110)))
main = Image.new("RGBA", (W, H), (0, 0, 0, 0))
md = ImageDraw.Draw(main)
yy = y
for (text, font, color), h, g in zip(lines, heights, gap_after):
    md.text((x, yy), text, font=font, fill=color)
    yy += h + g

img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
for layer in (soft, hard, high, main):
    img = Image.alpha_composite(img, layer)
img.save("/home/hatch/workspace/asmr-service/work/intro_text.png")
print("overlay saved")
