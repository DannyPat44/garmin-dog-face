# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""Convert Fredoka (tools/fonts, SIL OFL) into a Connect IQ bitmap font for the clock.

Writes resources/fonts/clock.fnt (AngelCode BMFont text format) and clock_0.png
with just the digits and colon. Metrics are trimmed to the digit height so the
clock centres exactly with TEXT_JUSTIFY_VCENTER.

    uv run tools/make_font.py [--size 104] [--weight 700]
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CHARS = "0123456789:"
PAD = 2
TRACKING = 4  # extra space between digits


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--size", type=int, default=104)
    p.add_argument("--weight", type=int, default=700)
    args = p.parse_args()

    font = ImageFont.truetype(str(ROOT / "tools/fonts/Fredoka.ttf"), args.size)
    font.set_variation_by_axes([args.weight, 100])  # weight, width

    boxes = {c: font.getbbox(c) for c in CHARS}
    top = min(b[1] for b in boxes.values())
    bottom = max(b[3] for b in boxes.values())
    height = bottom - top

    # Pack glyphs in a single row
    x = 0
    placed = {}
    for c in CHARS:
        l, t, r, b = boxes[c]
        placed[c] = (x, l, t, r - l, b - t)
        x += r - l + PAD * 2
    sheet = Image.new("RGBA", (x, height + PAD * 2), (255, 255, 255, 0))
    draw = ImageDraw.Draw(sheet)
    for c, (gx, l, t, w, h) in placed.items():
        draw.text((gx + PAD - l, PAD + (t - top) - t), c, font=font, fill=(255, 255, 255, 255))

    out = ROOT / "resources/fonts"
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "clock_0.png")
    lines = [
        f'info face="Fredoka" size={args.size} bold=1 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1',
        f"common lineHeight={height} base={height} scaleW={sheet.width} scaleH={sheet.height} pages=1 packed=0",
        'page id=0 file="clock_0.png"',
        f"chars count={len(CHARS)}",
    ]
    for c, (gx, l, t, w, h) in placed.items():
        lines.append(
            f"char id={ord(c)} x={gx + PAD} y={PAD + t - top} width={w} height={h} "
            f"xoffset={l} yoffset={t - top} xadvance={round(font.getlength(c)) + TRACKING} page=0 chnl=15"
        )
    (out / "clock.fnt").write_text("\n".join(lines) + "\n")
    print(f"clock font: {height}px tall, sheet {sheet.width}x{sheet.height}")


if __name__ == "__main__":
    main()
