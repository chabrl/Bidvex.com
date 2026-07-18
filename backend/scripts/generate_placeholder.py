"""
iter361 — Generate /static/placeholder.png fallback image.

400×300 navy (#0B2545) tile with the BidVex wordmark centered.
Referenced by SafeImage.jsx onError handler and every listing card.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

NAVY = (11, 37, 69)      # #0B2545
BLUE = (43, 143, 208)    # #2B8FD0
GREY = (203, 213, 225)   # #CBD5E1

OUT = Path("/app/frontend/public/static/placeholder.png")
OUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 400, 300
img = Image.new("RGB", (W, H), NAVY)
d = ImageDraw.Draw(img)

# Rounded corner effect via border
d.rectangle([(0, 0), (W - 1, H - 1)], outline=BLUE, width=2)

# Draw a stylized "gavel" icon area
cx, cy = W // 2, H // 2 - 20
d.ellipse((cx - 32, cy - 32, cx + 32, cy + 32), fill=(255, 255, 255, 30), outline=BLUE, width=3)

# Wordmark text
try:
    font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except Exception:
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

text = "BidVex"
tb = d.textbbox((0, 0), text, font=font_big)
tw, th = tb[2] - tb[0], tb[3] - tb[1]
d.text(((W - tw) // 2, cy + 22), text, fill=(255, 255, 255), font=font_big)

sub = "image loading…"
tb = d.textbbox((0, 0), sub, font=font_small)
sw = tb[2] - tb[0]
d.text(((W - sw) // 2, H - 40), sub, fill=GREY, font=font_small)

img.save(OUT, "PNG", optimize=True)
size = OUT.stat().st_size
print(f"[iter361] Placeholder generated: {OUT} ({size:,} bytes)")
