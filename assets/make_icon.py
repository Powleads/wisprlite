"""Generate assets/wisprlite.ico — a dark disc with a teal microphone.

Run:  python assets/make_icon.py
Produces a multi-resolution .ico (16/32/48/64/128/256). Drawn supersampled
then downscaled for crisp small sizes.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw

S = 1024  # supersample canvas
BG_TOP = (27, 30, 41, 255)     # #1b1e29
BG_BOT = (17, 19, 26, 255)     # #11131a
ACCENT = (52, 211, 153, 255)   # #34d399
RING = (52, 211, 153, 90)


def _disc() -> Image.Image:
    # vertical gradient
    grad = Image.new("RGBA", (S, S), BG_BOT)
    top = Image.new("RGBA", (S, S), BG_TOP)
    mask = Image.new("L", (1, S))
    for y in range(S):
        mask.putpixel((0, y), int(255 * (1 - y / S)))
    grad.paste(top, (0, 0), mask.resize((S, S)))

    # circular clip
    circle = Image.new("L", (S, S), 0)
    ImageDraw.Draw(circle).ellipse((8, 8, S - 8, S - 8), fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(grad, (0, 0), circle)

    d = ImageDraw.Draw(out)
    d.ellipse((8, 8, S - 8, S - 8), outline=RING, width=14)
    return out


def _mic(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    cx = S // 2
    # capsule body
    bw, top, bot = 150, 300, 560
    d.rounded_rectangle((cx - bw // 2, top, cx + bw // 2, bot), radius=bw // 2, fill=ACCENT)
    # arc cradle
    d.arc((cx - 150, 360, cx + 150, 660), start=20, end=160, fill=ACCENT, width=34)
    # stem
    d.line((cx, 660, cx, 740), fill=ACCENT, width=34)
    # base
    d.line((cx - 110, 745, cx + 110, 745), fill=ACCENT, width=34)


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    img = _disc()
    _mic(img)
    sizes = [16, 32, 48, 64, 128, 256]
    icons = [img.resize((s, s), Image.LANCZOS) for s in sizes]
    out_ico = os.path.join(here, "wisprlite.ico")
    icons[-1].save(out_ico, format="ICO", sizes=[(s, s) for s in sizes])
    # also a PNG for any non-Windows use
    icons[-1].save(os.path.join(here, "wisprlite.png"), format="PNG")
    print("wrote", out_ico)


if __name__ == "__main__":
    main()
