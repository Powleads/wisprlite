"""Build assets/wisprlite.ico from assets/pipevoice-source.png — the Pipevoice
mic-"P" logo on a dark rounded tile.

If the committed wisprlite.ico already exists this is a no-op, so CI ships the
exact committed artwork (no PIL needed on that path). Regeneration runs only when
the .ico is missing (e.g. after deleting it), rebuilding it from the source PNG.

Run:  python assets/make_icon.py
"""

from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ICO = os.path.join(HERE, "wisprlite.ico")
PNG = os.path.join(HERE, "wisprlite.png")
SRC = os.path.join(HERE, "pipevoice-source.png")

TILE = (21, 23, 31, 255)        # #15171f-ish dark squircle
BORDER = (224, 108, 117, 77)    # faint coral edge (#e06c75 @ ~0.30)
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _mark_from_source():
    """Extract the logo from the source PNG (warm art on pure black) by keying the
    alpha off the red channel — keeps the whole mark, incl. the dark maroon mic
    base, with smooth edges. Returns a tight-cropped RGBA image."""
    from PIL import Image

    src = Image.open(SRC).convert("RGB")
    r, _g, _b = src.split()
    lo, hi = 8, 107  # red < lo -> transparent, > hi -> opaque, ramp between
    alpha = r.point(lambda v: 0 if v <= lo else (255 if v >= hi else int((v - lo) * 255 / (hi - lo))))
    mark = src.convert("RGBA")
    mark.putalpha(alpha)
    box = mark.getbbox()
    return mark.crop(box) if box else mark


def regenerate() -> None:
    from PIL import Image, ImageDraw

    ss = 1024
    tile = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    mask = Image.new("L", (ss, ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, ss - 1, ss - 1], radius=224, fill=255)
    tile.paste(Image.new("RGBA", (ss, ss), TILE), (0, 0), mask)
    ImageDraw.Draw(tile).rounded_rectangle([7, 7, ss - 8, ss - 8], radius=218, outline=BORDER, width=7)

    mark = _mark_from_source()
    mh = int(ss * 0.68)
    mw = int(mark.width * mh / mark.height)
    tile.alpha_composite(mark.resize((mw, mh), Image.LANCZOS), ((ss - mw) // 2, (ss - mh) // 2))

    tile.resize((256, 256), Image.LANCZOS).save(PNG)
    tile.save(ICO, sizes=ICO_SIZES)


if __name__ == "__main__":
    if os.path.exists(ICO):
        print("wisprlite.ico present — keeping committed Pipevoice artwork.")
    elif os.path.exists(SRC):
        print("regenerating wisprlite.ico from pipevoice-source.png")
        regenerate()
    else:
        print("WARNING: no wisprlite.ico and no pipevoice-source.png to build from.")
