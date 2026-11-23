#!/usr/bin/env python3
"""Render docs/themes.png: the same tree in the dark and the light theme.

    python3 tools/make_themes.py [seed]     (needs Pillow and DejaVu fonts)
"""

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from idle_garden.plants import Plant  # noqa: E402
from idle_garden.themes import DEFAULT_BACKGROUND, THEMES, hex_to_rgb  # noqa: E402

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
COLS, ROWS = 70, 30
GROW, AT = 2400.0, 760


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    plant = Plant(COLS, ROWS, random.Random(seed), grow_seconds=GROW)
    t = 0.0
    while t < AT:  # small steps so leaf colours age naturally
        plant.update(2.0)
        t += 2.0

    font = ImageFont.truetype(MONO, 13)
    cw, ch = font.getlength("M"), 16
    pw, ph = int(COLS * cw), ROWS * ch
    pad, label = 24, 34
    img = Image.new("RGB", (2 * pw + 3 * pad, ph + 2 * pad + label), (255, 255, 255))
    img.putalpha(0)
    for i, name in enumerate(("dark", "light")):
        palette, bg = THEMES[name], hex_to_rgb(DEFAULT_BACKGROUND[name])
        panel = Image.new("RGBA", (pw, ph), bg + (255,))
        d = ImageDraw.Draw(panel)
        for (x, y), (c, color) in plant.cells.items():
            d.text((x * cw, y * ch), c, font=font, fill=palette[color])
        mask = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=14, fill=255)
        ox = pad + i * (pw + pad)
        img.paste(panel, (ox, pad), mask)
        ImageDraw.Draw(img).text((ox + pw / 2, pad + ph + 22), f"{name} theme", anchor="mm",
                                 font=ImageFont.truetype(SANS, 18), fill=(128, 136, 144, 255))
    out = ROOT / "docs" / "themes.png"
    img.save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
