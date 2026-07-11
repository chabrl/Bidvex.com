"""
iter340 P1 — "Share My Projection" social card generator.

Reuses the iter297 Pillow pipeline conventions (same font helpers, same
brand palette). 600×315 (standard OG share size), generated on demand —
never stored in S3. QR via the `qrcode` lib (already in requirements).
"""
from __future__ import annotations

import io
import logging
import os
from typing import Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

CARD_W, CARD_H = 600, 315

_BG     = (0x0B, 0x25, 0x45)   # BidVex dark navy
_BLUE   = (0x2B, 0x8F, 0xD0)   # BidVex blue accent
_FG     = (0xFF, 0xFF, 0xFF)
_MUTED  = (0xCB, 0xD5, 0xE1)

# Canonical CDN logo from iter314 — DO NOT swap to bidvex.com/assets.
BIDVEX_CDN_LOGO_URL = (
    "http://cdn.mcauto-images-production.sendgrid.net/"
    "4fbf02710175d39f/91d027c2-73da-4510-9bce-ee1ce34f16a7/4500x1080.png"
)

_FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_FONT_BODY_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_LOGO_CACHE: Optional[Image.Image] = None

TEXTS = {
    "en": {
        "tagline": "I'm earning with BidVex Auctions",
        "projected": "/ month projected",
        "sub": "Lifetime commissions — 3% of every sale from my referred network",
        "scan": "Scan to join",
    },
    "fr": {
        "tagline": "Je gagne avec BidVex Enchères",
        "projected": "/ mois projeté",
        "sub": "Commissions à vie — 3 % de chaque vente de mon réseau référé",
        "scan": "Scannez pour rejoindre",
    },
}


def _font(paths, size: int) -> ImageFont.ImageFont:
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _get_logo() -> Optional[Image.Image]:
    global _LOGO_CACHE
    if _LOGO_CACHE is not None:
        return _LOGO_CACHE
    try:
        import requests
        r = requests.get(BIDVEX_CDN_LOGO_URL, timeout=10)
        r.raise_for_status()
        logo = Image.open(io.BytesIO(r.content)).convert("RGBA")
        h = 36
        w = int(logo.width * (h / logo.height))
        _LOGO_CACHE = logo.resize((w, h), Image.LANCZOS)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[share-card] logo fetch failed — using wordmark: {e}")
        _LOGO_CACHE = None
    return _LOGO_CACHE


def _fmt_amount(v: float) -> str:
    return f"${v:,.0f}" if float(v) == int(v) else f"${v:,.2f}"


def build_share_card_png(projected_monthly: float, referral_url: str,
                         lang: str = "en") -> bytes:
    """Pure renderer — unit-testable, no DB/network besides cached logo."""
    t = TEXTS["fr" if str(lang).lower().startswith("fr") else "en"]
    img = Image.new("RGB", (CARD_W, CARD_H), _BG)
    draw = ImageDraw.Draw(img)

    # Top: logo (CDN) or text wordmark fallback.
    logo = _get_logo()
    if logo is not None:
        img.paste(logo, (30, 22), logo)
    else:
        draw.text((30, 22), "BidVex", fill=_FG, font=_font(_FONT_BOLD_PATHS, 30))

    # Thin blue rule under the header.
    draw.rectangle([30, 70, CARD_W - 30, 72], fill=_BLUE)

    # Center tagline.
    tagline_font = _font(_FONT_BOLD_PATHS, 24)
    draw.text((30, 92), t["tagline"], fill=_FG, font=tagline_font)

    # Large projected figure.
    amount = _fmt_amount(max(0.0, float(projected_monthly or 0)))
    big_font = _font(_FONT_BOLD_PATHS, 40)
    small_font = _font(_FONT_BODY_PATHS, 18)
    draw.text((30, 136), amount, fill=_BLUE, font=big_font)
    aw = draw.textlength(amount, font=big_font)
    draw.text((30 + aw + 12, 154), t["projected"], fill=_MUTED, font=small_font)

    # Sub-text (wrap into up to 2 lines within left column).
    sub_font = _font(_FONT_BODY_PATHS, 15)
    max_w = CARD_W - 30 - 150  # leave room for QR on the right
    words, lines, cur = t["sub"].split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if draw.textlength(cand, font=sub_font) <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    y = 196
    for line in lines[:2]:
        draw.text((30, y), line, fill=_MUTED, font=sub_font)
        y += 20

    # Bottom-left: referral link.
    link_font = _font(_FONT_BOLD_PATHS, 19)
    display_link = referral_url.replace("https://", "").replace("http://", "")
    draw.text((30, CARD_H - 45), display_link, fill=_BLUE, font=link_font)

    # Bottom-right: QR code for the referral URL.
    qr = qrcode.QRCode(box_size=3, border=1)
    qr.add_data(referral_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_size = 96
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
    qx, qy = CARD_W - qr_size - 26, CARD_H - qr_size - 26
    img.paste(qr_img, (qx, qy))
    scan_font = _font(_FONT_BODY_PATHS, 11)
    sw = draw.textlength(t["scan"], font=scan_font)
    draw.text((qx + (qr_size - sw) / 2, qy + qr_size + 4), t["scan"], fill=_MUTED, font=scan_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
