"""Planche contact des images de contrôle : python3 tools/sheet.py out.jpg img1.png img2.png ..."""
import sys
from PIL import Image, ImageDraw
out, files = sys.argv[1], sys.argv[2:]
cols = 2
w, h = 960, 540
rows = (len(files) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w, rows * h), (0, 0, 0))
for k, f in enumerate(files):
    im = Image.open(f).convert('RGB').resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.text((10, 10), f.split('_')[-1].replace('.png', 's'), fill=(255, 80, 80))
    sheet.paste(im, ((k % cols) * w, (k // cols) * h))
sheet.save(out, quality=88)
