"""Draw idle-garden.ico (a sprout on a patch of earth) with Pillow, for the .exe.

    python packaging/windows/make_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([8, 8, S - 8, S - 8], radius=48, fill=(14, 20, 16, 255))
d.ellipse([36, 196, 220, 300], fill=(132, 92, 58, 255))          # earth (clipped below)
d.line([(128, 214), (128, 110)], fill=(140, 100, 62, 255), width=14)  # stem
d.ellipse([52, 70, 132, 128], fill=(104, 190, 80, 255))           # left leaf
d.ellipse([124, 40, 214, 104], fill=(150, 215, 90, 255))          # right leaf
d.ellipse([110, 96, 146, 128], fill=(66, 158, 64, 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([8, 8, S - 8, S - 8], radius=48, fill=255)
out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
out.paste(img, (0, 0), mask)
path = Path(__file__).with_name("idle-garden.ico")
out.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(path)
