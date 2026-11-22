#!/usr/bin/env python3
"""Render a time-lapse of one tree growing to docs/demo.gif (needs Pillow).

    python3 tools/make_demo_gif.py [seed]
"""

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from idle_garden.plants import PALETTE, Plant  # noqa: E402

COLS, ROWS = 100, 34
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_SIZE = 13
GROW = 2400.0  # the real default: 40 minutes
GROW_FRAMES = 120  # time-lapse frames
LIVE_FRAMES = 30  # frames showing the finished plant still "breathing"
FRAME_MS = 70


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    small = ImageFont.truetype(FONT_PATH.replace("-Bold", ""), 12)
    cw = font.getlength("M")
    ch = FONT_SIZE + 3
    pad = 14
    w, h = int(COLS * cw + 2 * pad), int(ROWS * ch + 2 * pad)

    plant = Plant(COLS, ROWS, random.Random(seed), grow_seconds=GROW)
    frames = []

    def render(label):
        img = Image.new("RGB", (w, h), (0, 0, 0))
        d = ImageDraw.Draw(img)
        rows: dict[tuple[str, int], list[str]] = {}
        for (x, y), (c, color) in plant.cells.items():
            line = rows.setdefault((color, y), [" "] * COLS)
            line[x] = c
        for (color, y), chars in rows.items():
            d.text((pad, pad + y * ch), "".join(chars), font=font, fill=PALETTE[color])
        d.text((w - pad, h - 6), label, font=small, fill=(110, 118, 129), anchor="rd")
        frames.append(img)

    # time-lapse: spread the frames over the whole growth period
    # (more frames early on, where the shape is forming)
    total = GROW * 1.05
    for i in range(1, GROW_FRAMES + 1):
        target = total * (i / GROW_FRAMES) ** 1.4
        step = target - plant.clock
        for _ in range(10):  # small slices keep the leaf colours ageing naturally
            plant.update(step / 10)
        minutes = int(plant.clock // 60)
        render(f"{minutes} min" if not plant.done else "overgrown")
    while not plant.done:
        plant.update(30)
    # the overgrown plant keeps renewing its leaves (shown faster than real time)
    for _ in range(LIVE_FRAMES):
        plant.update(1.2)
        render("still alive")

    durations = [FRAME_MS] * len(frames)
    durations[0] = 900
    durations[-1] = 2500
    pal = [f.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    out = ROOT / "docs" / "demo.gif"
    out.parent.mkdir(exist_ok=True)
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True)
    print(out, f"{out.stat().st_size / 1e6:.1f} MB", len(frames), "frames")


if __name__ == "__main__":
    main()
