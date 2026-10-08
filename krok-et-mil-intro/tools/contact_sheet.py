"""Planche contact d'une séquence d'images (contrôle visuel de l'animation).
Usage : python3 tools/contact_sheet.py build/frames out.png START END STEP [COLS]"""
import os, sys
from PIL import Image, ImageDraw

d, out, a, b, step = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
cols = int(sys.argv[6]) if len(sys.argv) > 6 else 5
files = sorted(f for f in os.listdir(d) if f.endswith(('.png', '.jpeg', '.jpg')))
idx = list(range(a, min(b, len(files) - 1) + 1, step))
tw, th = 384, 216
rows = (len(idx) + cols - 1) // cols
sheet = Image.new('RGB', (cols * tw, rows * (th + 18)), (20, 20, 20))
dr = ImageDraw.Draw(sheet)
for k, i in enumerate(idx):
    im = Image.open(os.path.join(d, files[i])).convert('RGB').resize((tw, th), Image.LANCZOS)
    x, y = (k % cols) * tw, (k // cols) * (th + 18)
    sheet.paste(im, (x, y + 18))
    dr.text((x + 4, y + 3), f'f{i}  {i / 30:.3f}s', fill=(255, 255, 0))
sheet.save(out)
