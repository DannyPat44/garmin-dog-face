"""The store's on-device icons from a render of Millie (tools/render_rig.sh):
head, hat and chest, 128x128.

    python tools/make_icons.py [frame.png]

- store/icon_128.png: full colour on a dark navy glow (AMOLED watches)
- store/icon_128_64colors.png: dithered to Garmin's 64-colour palette (each
  channel 0x00, 0x55, 0xAA or 0xFF) on black (memory-in-pixel watches)

Needs Pillow (pip install pillow).
"""
import sys

from PIL import Image, ImageDraw, ImageFilter

FRAME = sys.argv[1] if len(sys.argv) > 1 else "build/frames/rig/millie/awake/0001.png"
SIZE = 128
# Head, hat and chest in a 300 px render: a square from just above the hat
CROP = (64, 44, 64 + 178, 44 + 178)

dog = Image.open(FRAME).convert("RGBA").crop(CROP).resize((SIZE, SIZE), Image.LANCZOS)

# Full colour: a soft navy glow behind the dog
glow = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
draw = ImageDraw.Draw(glow)
draw.ellipse((-20, -10, SIZE + 20, SIZE + 30), fill=(22, 30, 58))
glow = glow.filter(ImageFilter.GaussianBlur(22))
full = glow.convert("RGBA")
full.alpha_composite(dog)
full.convert("RGB").save("store/icon_128.png", optimize=True)

# 64 colours: the dog on black, Floyd-Steinberg dithered to the palette
levels = [0x00, 0x55, 0xAA, 0xFF]
palette = [c for r in levels for g in levels for b in levels for c in (r, g, b)]
pal = Image.new("P", (1, 1))
pal.putpalette(palette + [0] * (768 - len(palette)))
black = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
black.alpha_composite(dog)
black.convert("RGB").quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB").save(
    "store/icon_128_64colors.png", optimize=True)
print("store/icon_128.png, store/icon_128_64colors.png")
