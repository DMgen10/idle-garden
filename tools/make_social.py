#!/usr/bin/env python3
"""Render the 1280x640 GitHub social preview to docs/social-preview.png (needs Pillow)."""

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from idle_garden.plants import PALETTE, Plant  # noqa: E402

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SANS_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    W, H = 1280, 640
    img = Image.new("RGB", (W, H), (5, 7, 10))
    d = ImageDraw.Draw(img)

    # the tree on the right half, about 15 minutes into its growth
    font = ImageFont.truetype(MONO, 12)
    cw, ch = font.getlength("M"), 15
    cols, rows = int(560 / cw), int((H - 20) / ch)
    plant = Plant(cols, rows, random.Random(seed), grow_seconds=2400)
    while plant.clock < 16 * 60:
        plant.update(2)
    ox, oy = W - cols * cw - 10, H - rows * ch - 6
    lines: dict[tuple[str, int], list[str]] = {}
    for (x, y), (c, color) in plant.cells.items():
        lines.setdefault((color, y), [" "] * cols)[x] = c
    for (color, y), chars in lines.items():
        d.text((ox, oy + y * ch), "".join(chars), font=font, fill=PALETTE[color])

    # soft fade so the text side stays clean
    fade = Image.new("L", (W, H), 0)
    fd = ImageDraw.Draw(fade)
    for x in range(690, 790):
        fd.line([(x, 0), (x, H)], fill=int(255 * (x - 690) / 100))
    fd.rectangle([790, 0, W, H], fill=255)
    bg = Image.new("RGB", (W, H), (5, 7, 10))
    img = Image.composite(img, bg, fade)
    d = ImageDraw.Draw(img)

    d.text((80, 190), "Idle Garden", font=ImageFont.truetype(SANS, 76), fill=(236, 240, 236))
    tag = ImageFont.truetype(SANS_REG, 30)
    for k, line in enumerate(("Step away from your computer —", "and an ASCII tree slowly grows", "over your screen.")):
        d.text((84, 305 + k * 42), line, font=tag, fill=(170, 180, 175))
    d.text((84, 470), "Ubuntu · GNOME · Wayland & X11", font=ImageFont.truetype(MONO, 22), fill=PALETTE["leaf_light"])

    out = ROOT / "docs" / "social-preview.png"
    img.save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
