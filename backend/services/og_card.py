"""
iter341 P0/P1 — Summer Grand Opening OG card (1200×628).

Generated ONCE at backend startup (not per-request — it isn't personalized)
and written to /app/frontend/public/static/og/summer-launch-promo.png so it
is served publicly at https://bidvex.com/static/og/summer-launch-promo.png
without auth — social crawlers don't send auth headers. Same pattern as the
iter307 sitemap regen (backend writes into frontend/public).
"""
from __future__ import annotations

import io
import logging
import os

from PIL import Image, ImageDraw, ImageFont

from services.share_card import _font, _FONT_BOLD_PATHS, _FONT_BODY_PATHS, BIDVEX_CDN_LOGO_URL

logger = logging.getLogger(__name__)

OG_W, OG_H = 1200, 628
OG_CARD_PATH = "/app/frontend/public/static/og/summer-launch-promo.png"

_BG      = (0x0B, 0x25, 0x45)   # BidVex dark navy
_BLUE    = (0x2B, 0x8F, 0xD0)   # BidVex blue
_TEAL    = (0x3F, 0xB4, 0xCB)   # gradient end
_STRIP   = (0x1A, 0x3A, 0x5C)   # bottom strip navy
_FG      = (0xFF, 0xFF, 0xFF)
_MUTED   = (0x94, 0xA3, 0xB8)

_FONT_ITALIC_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
]


def _fetch_logo(height: int = 52):
    try:
        import requests
        r = requests.get(BIDVEX_CDN_LOGO_URL, timeout=10)
        r.raise_for_status()
        logo = Image.open(io.BytesIO(r.content)).convert("RGBA")
        w = int(logo.width * (height / logo.height))
        return logo.resize((w, height), Image.LANCZOS)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[og-card] logo fetch failed — using wordmark: {e}")
        return None


def build_summer_launch_og_png() -> bytes:
    img = Image.new("RGB", (OG_W, OG_H), _BG)
    draw = ImageDraw.Draw(img)

    # 3px horizontal gradient strip across the very top (#2B8FD0 → #3FB4CB).
    for x in range(OG_W):
        t = x / (OG_W - 1)
        col = tuple(int(_BLUE[i] + (_TEAL[i] - _BLUE[i]) * t) for i in range(3))
        draw.rectangle([x, 0, x, 3], fill=col)

    # Top-left: BidVex logo (CDN) or wordmark fallback.
    logo = _fetch_logo(52)
    if logo is not None:
        img.paste(logo, (56, 36), logo)
    else:
        draw.text((56, 36), "BidVex", fill=_FG, font=_font(_FONT_BOLD_PATHS, 46))

    # Top-right: "Summer 2026 / Été 2026" italic blue.
    season_font = _font(_FONT_ITALIC_PATHS, 26)
    season = "Summer 2026 / Été 2026"
    sw = draw.textlength(season, font=season_font)
    draw.text((OG_W - 56 - sw, 48), season, fill=_BLUE, font=season_font)

    # Center text block (left-aligned). A rocket-style accent chevron stands
    # in for the 🚀 emoji (emoji glyphs don't render in server-side TTFs).
    y = 168
    draw.polygon([(56, y + 34), (86, y + 18), (56, y + 2), (66, y + 18)], fill=(0xF4, 0x6A, 0x4E))
    line1_font = _font(_FONT_BOLD_PATHS, 40)
    draw.text((100, y - 4), "Grand Opening", fill=_FG, font=line1_font)

    line2_font = _font(_FONT_BOLD_PATHS, 88)
    draw.text((56, y + 54), "First Month FREE", fill=_BLUE, font=line2_font)

    line3_font = _font(_FONT_BODY_PATHS, 32)
    draw.text((56, y + 172), "Canada's Bilingual Auction Platform", fill=_FG, font=line3_font)

    line4_font = _font(_FONT_BODY_PATHS, 24)
    draw.text((56, y + 222), "Vehicles · Marketplace · Lots · Storage", fill=_MUTED, font=line4_font)

    # Bottom strip.
    strip_top = OG_H - 68
    draw.rectangle([0, strip_top, OG_W, OG_H], fill=_STRIP)
    strip_font = _font(_FONT_BOLD_PATHS, 24)
    draw.text((56, strip_top + 20), "bidvex.com", fill=_FG, font=strip_font)
    right_font = _font(_FONT_BODY_PATHS, 20)
    right_txt = "Offer ends Aug 31, 2026 / Offre se termine 31 août 2026"
    rw = draw.textlength(right_txt, font=right_font)
    draw.text((OG_W - 56 - rw, strip_top + 22), right_txt, fill=_MUTED, font=right_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def ensure_summer_og_card() -> str:
    """Generate + write the static OG card. Called once at backend startup."""
    os.makedirs(os.path.dirname(OG_CARD_PATH), exist_ok=True)
    png = build_summer_launch_og_png()
    with open(OG_CARD_PATH, "wb") as f:
        f.write(png)
    logger.info(f"[og-card] wrote {OG_CARD_PATH} ({len(png)} bytes)")
    return OG_CARD_PATH
