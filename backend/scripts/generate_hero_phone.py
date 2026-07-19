"""
iter363 — Generate the hero phone mockup PNGs showing a NEUTRAL auction
listing inside a phone frame (not the BidVex homepage — that caused the
recursive-mirror effect where French UI showed even on English pages).

Outputs (both idempotent):
  /app/frontend/public/static/hero-phone-en.png   (460 × 945)
  /app/frontend/public/static/hero-phone-fr.png   (460 × 945)

Content:
  • Dark navy #0B2545 phone frame with subtle rounded corners
  • Notch cutout at top
  • Inside the screen: a clean "auction card" mockup showing
    - BidVex wordmark (top)
    - Sample item: "2024 Ford F-150" (EN) / "Ford F-150 2024" (FR)
    - Current bid + BID button
    - No BidVex UI chrome, so no recursive-mirror problem
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

NAVY   = (11, 37, 69)      # #0B2545
BLUE   = (43, 143, 208)    # #2B8FD0
WHITE  = (255, 255, 255)
GREY_LIGHT = (241, 245, 249)   # slate-100
GREY_MED   = (100, 116, 139)   # slate-500
GREY_DARK  = (30, 41, 59)      # slate-800
GREEN  = (16, 185, 129)    # emerald-500

W, H = 460, 945
SCREEN_W, SCREEN_H = 400, 850
SCREEN_X = (W - SCREEN_W) // 2
SCREEN_Y = (H - SCREEN_H) // 2


def _load_fonts():
    try:
        return {
            "logo":    ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26),
            "title":   ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20),
            "label":   ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12),
            "price":   ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28),
            "sub":     ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13),
            "button":  ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16),
            "meta":    ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11),
        }
    except Exception:
        f = ImageFont.load_default()
        return {k: f for k in ("logo", "title", "label", "price", "sub", "button", "meta")}


def _draw_rounded_rect(d, xy, radius, fill=None, outline=None, width=1):
    """PIL doesn't have rounded_rectangle on older versions — use fallback."""
    try:
        d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    except AttributeError:
        d.rectangle(xy, fill=fill, outline=outline, width=width)


def _draw_phone_shell(img):
    """Dark phone frame + notch. No trademark elements."""
    d = ImageDraw.Draw(img, "RGBA")

    # Phone body — rounded rect
    _draw_rounded_rect(d, [(SCREEN_X - 12, SCREEN_Y - 22), (SCREEN_X + SCREEN_W + 12, SCREEN_Y + SCREEN_H + 22)],
                       radius=44, fill=(15, 23, 42, 255))  # slate-900

    # Screen area
    _draw_rounded_rect(d, [(SCREEN_X, SCREEN_Y), (SCREEN_X + SCREEN_W, SCREEN_Y + SCREEN_H)],
                       radius=28, fill=WHITE)

    # Notch at top of screen
    notch_w = 140
    notch_h = 22
    notch_x = SCREEN_X + (SCREEN_W - notch_w) // 2
    _draw_rounded_rect(d, [(notch_x, SCREEN_Y), (notch_x + notch_w, SCREEN_Y + notch_h)],
                       radius=11, fill=(15, 23, 42, 255))


def _draw_auction_content(img, lang):
    """Draw the auction card inside the phone screen. Language-aware."""
    fonts = _load_fonts()
    d = ImageDraw.Draw(img)

    # ── Header bar (BidVex wordmark) ─────────────────────────────
    header_y = SCREEN_Y + 40
    d.text((SCREEN_X + 24, header_y), "BidVex", fill=NAVY, font=fonts["logo"])
    # Small live indicator
    dot_r = 4
    dot_x = SCREEN_X + SCREEN_W - 90
    dot_y = header_y + 12
    d.ellipse([(dot_x - dot_r, dot_y - dot_r), (dot_x + dot_r, dot_y + dot_r)], fill=GREEN)
    d.text((dot_x + 10, header_y + 4),
           "LIVE" if lang == "en" else "EN DIRECT", fill=GREEN, font=fonts["meta"])

    # Divider
    d.line([(SCREEN_X + 24, header_y + 42), (SCREEN_X + SCREEN_W - 24, header_y + 42)],
           fill=GREY_LIGHT, width=1)

    # ── Category badge ───────────────────────────────────────────
    badge_y = header_y + 60
    badge_text = "VEHICLE AUCTION" if lang == "en" else "ENCHÈRE VÉHICULE"
    bbox = d.textbbox((0, 0), badge_text, font=fonts["meta"])
    badge_w = bbox[2] - bbox[0] + 16
    _draw_rounded_rect(d, [(SCREEN_X + 24, badge_y), (SCREEN_X + 24 + badge_w, badge_y + 20)],
                       radius=10, fill=BLUE)
    d.text((SCREEN_X + 32, badge_y + 4), badge_text, fill=WHITE, font=fonts["meta"])

    # ── Vehicle image placeholder ────────────────────────────────
    img_y = badge_y + 34
    img_h = 200
    _draw_rounded_rect(d, [(SCREEN_X + 24, img_y), (SCREEN_X + SCREEN_W - 24, img_y + img_h)],
                       radius=12, fill=(226, 232, 240))  # slate-200

    # Draw a simple stylized truck silhouette (rectangles + circles)
    truck_y = img_y + img_h - 100
    truck_x = SCREEN_X + 60
    truck_w = SCREEN_W - 24 * 2 - 72
    # Cab
    _draw_rounded_rect(d, [(truck_x, truck_y), (truck_x + 60, truck_y + 55)], radius=6, fill=NAVY)
    # Bed
    _draw_rounded_rect(d, [(truck_x + 60, truck_y + 20), (truck_x + truck_w, truck_y + 55)],
                       radius=6, fill=(51, 65, 85))  # slate-700
    # Wheels
    wheel_r = 12
    for wx in (truck_x + 15, truck_x + truck_w - 25):
        d.ellipse([(wx - wheel_r, truck_y + 45), (wx + wheel_r, truck_y + 45 + wheel_r * 2)],
                  fill=(30, 41, 59))

    # ── Vehicle title ────────────────────────────────────────────
    title_y = img_y + img_h + 18
    title = "2024 Ford F-150 Lariat" if lang == "en" else "Ford F-150 Lariat 2024"
    d.text((SCREEN_X + 24, title_y), title, fill=GREY_DARK, font=fonts["title"])
    # Sub
    sub = "72,400 km · SAAQ verified" if lang == "en" else "72 400 km · Vérifié SAAQ"
    d.text((SCREEN_X + 24, title_y + 30), sub, fill=GREY_MED, font=fonts["sub"])

    # ── Current bid block ────────────────────────────────────────
    bid_y = title_y + 70
    _draw_rounded_rect(d, [(SCREEN_X + 24, bid_y), (SCREEN_X + SCREEN_W - 24, bid_y + 80)],
                       radius=12, fill=GREY_LIGHT)
    d.text((SCREEN_X + 36, bid_y + 10),
           "CURRENT BID" if lang == "en" else "MISE ACTUELLE",
           fill=GREY_MED, font=fonts["label"])
    d.text((SCREEN_X + 36, bid_y + 28), "$34,250", fill=NAVY, font=fonts["price"])
    d.text((SCREEN_X + 200, bid_y + 46), "CAD", fill=GREY_MED, font=fonts["sub"])
    d.text((SCREEN_X + 36, bid_y + 62),
           "14 bids · ends in 02h 37m" if lang == "en" else "14 mises · reste 02h 37m",
           fill=GREY_MED, font=fonts["meta"])

    # ── BID button ───────────────────────────────────────────────
    btn_y = bid_y + 96
    _draw_rounded_rect(d, [(SCREEN_X + 24, btn_y), (SCREEN_X + SCREEN_W - 24, btn_y + 52)],
                       radius=26, fill=BLUE)
    btn_text = "PLACE BID" if lang == "en" else "MISER MAINTENANT"
    bbox = d.textbbox((0, 0), btn_text, font=fonts["button"])
    btn_tw = bbox[2] - bbox[0]
    d.text((SCREEN_X + (SCREEN_W - btn_tw) // 2, btn_y + 16),
           btn_text, fill=WHITE, font=fonts["button"])

    # ── Bottom nav hints (5 icons) ───────────────────────────────
    nav_y = SCREEN_Y + SCREEN_H - 60
    d.line([(SCREEN_X + 12, nav_y - 8), (SCREEN_X + SCREEN_W - 12, nav_y - 8)],
           fill=GREY_LIGHT, width=1)
    nav_labels_en = ["Home", "Auctions", "Watch", "Bids", "Profile"]
    nav_labels_fr = ["Accueil", "Enchères", "Suivi", "Mises", "Profil"]
    labels = nav_labels_fr if lang == "fr" else nav_labels_en
    for i, label in enumerate(labels):
        cx = SCREEN_X + 12 + (SCREEN_W - 24) * (i + 0.5) / 5
        # Circle icon
        r = 8
        d.ellipse([(cx - r, nav_y - r), (cx + r, nav_y + r)],
                  fill=BLUE if i == 1 else (203, 213, 225))
        # Label
        bbox = d.textbbox((0, 0), label, font=fonts["meta"])
        lw = bbox[2] - bbox[0]
        d.text((cx - lw // 2, nav_y + 12), label,
               fill=BLUE if i == 1 else GREY_MED, font=fonts["meta"])


def build(lang: str, out_path: Path):
    """Generate one language-variant PNG."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_phone_shell(img)
    _draw_auction_content(img, lang)

    # Composite onto white background, save as PNG-8 with alpha
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path.stat().st_size


def main():
    outputs = [
        ("en", Path("/app/frontend/public/static/hero-phone-en.png")),
        ("fr", Path("/app/frontend/public/static/hero-phone-fr.png")),
    ]
    for lang, path in outputs:
        size = build(lang, path)
        print(f"[iter363] Generated {path} ({size:,} bytes, lang={lang})")


if __name__ == "__main__":
    main()
