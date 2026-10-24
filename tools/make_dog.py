# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10"]
# ///
"""Draw the dog artwork for the watch face.

Writes resources/drawables/dog_{awake,happy,sleepy}.png and launcher_icon.png.
The face picks one of the three moods at runtime. Tweak the colors and shapes
below, then rerun:

    uv run tools/make_dog.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "resources" / "drawables"
SIZE = 400  # final PNG size; the resource compiler scales it per device
SS = 4  # supersampling factor for smooth edges

FUR = (196, 132, 72)
EAR = (120, 72, 36)
MUZZLE = (250, 236, 214)
NOSE = (30, 24, 22)
EYE = (30, 24, 22)
TONGUE = (236, 96, 120)
CHEEK = (240, 150, 140)
ZZZ = (170, 200, 255)


def s(*vals):
    """Scale coordinates from the 400px design grid to the supersampled canvas."""
    return [v * SS for v in vals]


def draw_dog(mood: str) -> Image.Image:
    img = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = 6 * SS  # outline width

    # Floppy ears behind the head
    d.ellipse(s(40, 90, 150, 300), fill=EAR, outline=NOSE, width=w)
    d.ellipse(s(250, 90, 360, 300), fill=EAR, outline=NOSE, width=w)

    # Head and muzzle
    d.ellipse(s(80, 60, 320, 330), fill=FUR, outline=NOSE, width=w)
    d.ellipse(s(130, 190, 270, 320), fill=MUZZLE, outline=NOSE, width=w)

    # Eyes
    if mood == "awake":
        for cx in (155, 245):
            d.ellipse(s(cx - 18, 150, cx + 18, 190), fill=EYE)
            d.ellipse(s(cx - 6, 157, cx + 4, 169), fill=(255, 255, 255))
    elif mood == "happy":
        for cx in (155, 245):
            d.arc(s(cx - 22, 152, cx + 22, 192), 200, 340, fill=EYE, width=w)
    else:  # sleepy
        for cx in (155, 245):
            d.arc(s(cx - 22, 150, cx + 22, 180), 20, 160, fill=EYE, width=w)

    # Cheeks
    d.ellipse(s(108, 205, 138, 225), fill=CHEEK)
    d.ellipse(s(262, 205, 292, 225), fill=CHEEK)

    # Nose and mouth
    d.ellipse(s(178, 200, 222, 232), fill=NOSE)
    d.line(s(200, 232, 200, 255), fill=NOSE, width=w)
    if mood == "sleepy":
        d.arc(s(180, 245, 220, 270), 20, 160, fill=NOSE, width=w)
    else:
        d.arc(s(160, 230, 200, 270), 20, 160, fill=NOSE, width=w)
        d.arc(s(200, 230, 240, 270), 20, 160, fill=NOSE, width=w)
    if mood == "happy":
        d.rounded_rectangle(s(184, 258, 216, 300), radius=16 * SS, fill=TONGUE, outline=NOSE, width=w)

    # Zzz for the sleepy dog
    if mood == "sleepy":
        for x, y, z in ((300, 70, 30), (335, 30, 22), (362, 0, 16)):
            pts = [(x, y), (x + z, y), (x, y + z), (x + z, y + z)]
            d.line([v * SS for p in pts for v in p], fill=ZZZ, width=w)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for mood in ("awake", "happy", "sleepy"):
        draw_dog(mood).save(OUT / f"dog_{mood}.png")
    icon = Image.new("RGBA", (60, 60), (0, 0, 0, 255))
    icon.alpha_composite(draw_dog("happy").resize((60, 60), Image.LANCZOS))
    icon.save(OUT / "launcher_icon.png")
    print(f"Wrote dog artwork to {OUT}")


if __name__ == "__main__":
    main()
