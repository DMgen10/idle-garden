#!/usr/bin/env python3
"""Render three growth stages of one plant to docs/preview.svg for the README.

    python3 tools/make_preview.py [seed]
"""

import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from idle_garden.plants import PALETTE, Plant  # noqa: E402

CW, CH = 8.4, 16  # cell size in px
COLS, ROWS = 76, 30
GROW = 2400.0
STAGES = ((480, "8 min"), (900, "15 min"), (GROW + 60, "40 min — overgrown"))


def panel(cells, ox, oy):
    out = []
    for (x, y), (ch, color) in sorted(cells.items(), key=lambda i: (i[0][1], i[0][0])):
        if ch == " ":
            continue
        r, g, b = PALETTE[color]
        out.append(f'<text x="{ox + x * CW:.1f}" y="{oy + (y + 1) * CH - 4:.1f}" '
                   f'fill="rgb({r},{g},{b})">{escape(ch)}</text>')
    return "\n".join(out)


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    pad, label_h = 18, 26
    pw, ph = COLS * CW, ROWS * CH
    w = int(3 * pw + 4 * pad)
    h = int(ph + 2 * pad + label_h)
    parts = []
    for i, (sec, label) in enumerate(STAGES):
        plant = Plant(COLS, ROWS, random.Random(seed), grow_seconds=GROW)
        t = 0.0
        while t < sec:  # step in small chunks so leaf colours age naturally
            plant.update(min(2.0, sec - t))
            t += 2.0
        ox = pad + i * (pw + pad)
        parts.append(f'<rect x="{ox - 6}" y="{pad - 6}" width="{pw + 12}" height="{ph + 12}" rx="8" fill="#000"/>')
        parts.append(panel(plant.cells, ox, pad))
        parts.append(f'<text x="{ox + pw / 2:.0f}" y="{pad + ph + label_h:.0f}" fill="#8b949e" '
                     f'font-weight="normal" text-anchor="middle">{escape(label)}</text>')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<rect width="100%" height="100%" rx="14" fill="#0d1117"/>
<g font-family="DejaVu Sans Mono, Menlo, Consolas, monospace" font-size="14" font-weight="bold" xml:space="preserve">
{chr(10).join(parts)}
</g>
</svg>
"""
    out = Path(__file__).resolve().parent.parent / "docs" / "preview.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(svg)
    print(out)


if __name__ == "__main__":
    main()
