# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""The face's clock and stats for tools/make_media.sh (docs/media/face_ui.png).

Takes a 416px capture of the face from the simulator, with the dog's box
blacked out, and redraws the clock from the app's own bitmap font, centred at
the top as the face draws it (so no stray dog shows under it):

    uv run tools/face_ui.py capture.png resources-round-416x416/fonts 10:09 docs/media/face_ui.png
"""
import re, sys
from PIL import Image, ImageDraw
face = Image.open(sys.argv[1]).convert("RGB")
font_dir, text, out = sys.argv[2], sys.argv[3], sys.argv[4]
sheet = Image.open(f"{font_dir}/clock_0.png").convert("RGBA")
chars = {}
for line in open(f"{font_dir}/clock.fnt"):
    if line.startswith("char "):
        f = dict(re.findall(r"(\w+)=(-?\d+)", line))
        chars[chr(int(f["id"]))] = {k: int(v) for k, v in f.items()}
# Clear the old clock (and anything under it), then draw the new one
ImageDraw.Draw(face).rectangle([40, 52, 376, 137], fill=(0, 0, 0))
width = sum(chars[c]["xadvance"] for c in text)
x, top = 208 - width // 2, round(416 * 0.145)
for c in text:
    g = chars[c]
    glyph = sheet.crop((g["x"], g["y"], g["x"] + g["width"], g["y"] + g["height"]))
    face.paste(glyph, (x + g["xoffset"], top + g["yoffset"]), glyph)
    x += g["xadvance"]
face.save(out)
