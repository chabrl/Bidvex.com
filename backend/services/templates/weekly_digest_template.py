"""
iter378 — Weekly digest email template (EN/FR).

Renders a self-contained HTML string. The universal CASL footer + manage-
preferences URL + List-Unsubscribe headers are added by
`services.emails._email_core.send_email(is_marketing=True)`, so we don't
duplicate them here.
"""

from __future__ import annotations

import html
import os
from typing import Any, Dict, List

FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "https://www.bidvex.com").rstrip("/")


# ─── Copy blocks ─────────────────────────────────────────────────────

_COPY = {
    "en": {
        "subject_full":       "Your weekly BidVex picks — new lots waiting for you",
        "subject_watchlist":  "Your BidVex weekly — watchlist updates inside",
        "subject_sellers":    "Your BidVex weekly — new lots from sellers you follow",
        "subject_generic":    "Your BidVex weekly picks are here",
        "preheader":          "New listings from sellers you follow, watchlist updates, and picks for you.",
        "hi":                 "Hi",
        "hero_title":         "This week on BidVex",
        "hero_lead":          "Handpicked lots based on what you're watching and who you follow.",
        "sellers_h":          "New from sellers you follow",
        "sellers_empty":      "",  # section is hidden when empty
        "watchlist_h":        "Watchlist updates",
        "watchlist_sub":      "These lots are still live — jump back in before they close.",
        "interests_h":        "Matches for your interests",
        "interests_sub":      "Fresh listings in the categories you browse most.",
        "current_bid":        "Current bid",
        "starting_at":        "Starting at",
        "ends_in":            "Ends in",
        "days":               "d",
        "hours":              "h",
        "minutes":            "m",
        "ended":              "Closes soon",
        "no_bids":            "No bids yet",
        "cta_view":           "View lot",
        "cta_browse":         "Browse all live auctions",
        "footer_intro":       "You're receiving this because you have a BidVex account and haven't opted out of weekly picks.",
    },
    "fr": {
        "subject_full":       "Vos sélections BidVex de la semaine — de nouveaux lots vous attendent",
        "subject_watchlist":  "Votre BidVex hebdomadaire — mises à jour de votre liste",
        "subject_sellers":    "Votre BidVex hebdomadaire — nouveaux lots des vendeurs suivis",
        "subject_generic":    "Vos sélections BidVex hebdomadaires sont arrivées",
        "preheader":          "Nouveaux lots de vos vendeurs, mises à jour de votre liste et suggestions pour vous.",
        "hi":                 "Bonjour",
        "hero_title":         "Cette semaine sur BidVex",
        "hero_lead":          "Une sélection de lots basée sur ce que vous surveillez et les vendeurs que vous suivez.",
        "sellers_h":          "Nouveautés des vendeurs suivis",
        "sellers_empty":      "",
        "watchlist_h":        "Mises à jour de votre liste",
        "watchlist_sub":      "Ces lots sont encore ouverts — retournez-y avant la fermeture.",
        "interests_h":        "Correspondances avec vos intérêts",
        "interests_sub":      "De nouvelles annonces dans les catégories que vous parcourez.",
        "current_bid":        "Mise actuelle",
        "starting_at":        "Départ à",
        "ends_in":            "Se termine dans",
        "days":               "j",
        "hours":              "h",
        "minutes":            "min",
        "ended":              "Ferme bientôt",
        "no_bids":            "Aucune mise",
        "cta_view":           "Voir le lot",
        "cta_browse":         "Voir toutes les enchères",
        "footer_intro":       "Vous recevez ce courriel parce que vous avez un compte BidVex et n'avez pas désactivé la sélection hebdomadaire.",
    },
}


# ─── Utility ─────────────────────────────────────────────────────────

def _fmt_price(amount) -> str:
    try:
        return f"${float(amount):,.0f} CAD" if float(amount) == int(float(amount)) else f"${float(amount):,.2f} CAD"
    except Exception:
        return "—"


def _fmt_time_remaining(secs: int, lang: str) -> str:
    c = _COPY[lang]
    if not secs or secs <= 0:
        return c["ended"]
    days = secs // 86400
    hours = (secs % 86400) // 3600
    mins = (secs % 3600) // 60
    if days > 0:
        return f"{days}{c['days']} {hours}{c['hours']}"
    if hours > 0:
        return f"{hours}{c['hours']} {mins}{c['minutes']}"
    return f"{mins}{c['minutes']}"


def _image_for(listing: Dict[str, Any]) -> str:
    img = listing.get("image_url")
    if not img:
        images = listing.get("images") or []
        if images and isinstance(images, list):
            first = images[0]
            if isinstance(first, str):
                img = first
            elif isinstance(first, dict):
                img = first.get("url") or first.get("src")
    return img or f"{FRONTEND_URL}/logo-bidvex-email.png"


def _listing_url(listing: Dict[str, Any], lang: str) -> str:
    lid = listing.get("id") or ""
    return f"{FRONTEND_URL}/{lang}/listing/{lid}"


# ─── Card renderer ───────────────────────────────────────────────────

def _render_card(listing: Dict[str, Any], lang: str, *, show_time: bool = True) -> str:
    c = _COPY[lang]
    title = html.escape(str(listing.get("title") or "Untitled lot"))
    price = listing.get("current_bid") or listing.get("price") or listing.get("starting_price")
    price_label = c["current_bid"] if listing.get("current_bid") else c["starting_at"]
    price_str = _fmt_price(price) if price else c["no_bids"]
    image = _image_for(listing)
    url = _listing_url(listing, lang)
    time_html = ""
    if show_time and listing.get("ends_in_seconds") is not None:
        time_html = (
            f'<div style="margin-top:6px;color:#dc2626;font-size:12px;font-weight:600;">'
            f'{c["ends_in"]} {_fmt_time_remaining(int(listing["ends_in_seconds"]), lang)}'
            f'</div>'
        )
    seller_line = ""
    if listing.get("seller_name"):
        seller_line = (
            f'<div style="color:#64748b;font-size:12px;margin-top:4px;">'
            f'{html.escape(listing["seller_name"])}</div>'
        )

    return f'''
<td style="width:50%;padding:8px;vertical-align:top;" valign="top">
  <a href="{url}" style="text-decoration:none;color:inherit;display:block;">
    <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;background:#fff;">
      <img src="{image}" alt="{title}" width="240" height="150" style="width:100%;height:150px;object-fit:cover;display:block;border:0;" />
      <div style="padding:12px 14px;">
        <div style="font-weight:700;font-size:14px;color:#0f172a;line-height:1.35;min-height:36px;">
          {title[:70]}{"…" if len(title) > 70 else ""}
        </div>
        {seller_line}
        <div style="margin-top:8px;color:#334155;font-size:13px;">
          <span style="color:#64748b;">{price_label}:</span>
          <strong style="color:#0891b2;">{price_str}</strong>
        </div>
        {time_html}
        <div style="margin-top:10px;">
          <span style="display:inline-block;padding:6px 12px;border-radius:6px;background:#0891b2;color:#fff;font-size:12px;font-weight:600;">
            {c["cta_view"]} →
          </span>
        </div>
      </div>
    </div>
  </a>
</td>'''.strip()


def _render_section(title: str, subtitle: str, cards: List[str]) -> str:
    if not cards:
        return ""
    # 2-column grid via nested tables (email-client safe).
    rows = []
    for i in range(0, len(cards), 2):
        pair = cards[i:i + 2]
        while len(pair) < 2:
            pair.append('<td style="width:50%;padding:8px;"></td>')
        rows.append("<tr>" + "".join(pair) + "</tr>")
    sub_html = (
        f'<p style="margin:0 0 14px;color:#64748b;font-size:14px;">{html.escape(subtitle)}</p>'
        if subtitle else ""
    )
    return f'''
<div style="margin-top:32px;">
  <h2 style="margin:0 0 4px;color:#0f172a;font-size:20px;font-weight:800;">{html.escape(title)}</h2>
  {sub_html}
  <table role="presentation" cellspacing="0" cellpadding="0" width="100%" style="border-collapse:separate;border-spacing:0;">
    {"".join(rows)}
  </table>
</div>'''.strip()


# ─── Public API ──────────────────────────────────────────────────────

def render_weekly_digest_subject(payload: Dict[str, Any]) -> str:
    lang = payload.get("lang", "en")
    c = _COPY.get(lang, _COPY["en"])
    has_s = bool(payload.get("seller_listings"))
    has_w = bool(payload.get("watchlist_updates"))
    if has_s and has_w:
        return c["subject_full"]
    if has_w:
        return c["subject_watchlist"]
    if has_s:
        return c["subject_sellers"]
    return c["subject_generic"]


def render_weekly_digest_html(payload: Dict[str, Any]) -> str:
    lang = payload.get("lang", "en")
    c = _COPY.get(lang, _COPY["en"])
    name = html.escape(str(payload.get("name") or "")).strip()
    greeting = f"{c['hi']} {name}," if name else f"{c['hi']}!"

    sellers_section = _render_section(
        c["sellers_h"],
        "",
        [_render_card(l, lang) for l in payload.get("seller_listings", [])],
    )
    watchlist_section = _render_section(
        c["watchlist_h"],
        c["watchlist_sub"],
        [_render_card(l, lang) for l in payload.get("watchlist_updates", [])],
    )
    interests_section = _render_section(
        c["interests_h"],
        c["interests_sub"],
        [_render_card(l, lang, show_time=False) for l in payload.get("interest_listings", [])],
    )

    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{html.escape(render_weekly_digest_subject(payload))}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;">
  <!-- preheader: hidden preview text -->
  <div style="display:none;font-size:1px;color:#f1f5f9;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">
    {html.escape(c["preheader"])}
  </div>

  <table role="presentation" cellspacing="0" cellpadding="0" width="100%" style="background:#f1f5f9;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" cellspacing="0" cellpadding="0" width="640" style="max-width:640px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 12px rgba(15,23,42,0.06);">
        <!-- Brand bar -->
        <tr>
          <td style="background:linear-gradient(135deg,#0B2345 0%,#2B8FD0 100%);padding:24px 28px;">
            <div style="color:#fff;font-size:22px;font-weight:800;letter-spacing:-0.02em;">BidVex</div>
            <div style="color:#a9e4f0;font-size:13px;margin-top:2px;">{html.escape(c["hero_title"])}</div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px;">
            <p style="margin:0 0 6px;font-size:16px;color:#0f172a;">{greeting}</p>
            <p style="margin:0 0 12px;color:#475569;font-size:15px;line-height:1.6;">{html.escape(c["hero_lead"])}</p>

            {sellers_section}
            {watchlist_section}
            {interests_section}

            <div style="margin-top:32px;text-align:center;">
              <a href="{FRONTEND_URL}/{lang}/browse" style="display:inline-block;padding:14px 26px;background:linear-gradient(135deg,#2B8FD0,#3FB4CB);color:#fff;text-decoration:none;font-weight:700;border-radius:10px;font-size:15px;">
                {html.escape(c["cta_browse"])} →
              </a>
            </div>

            <p style="margin:32px 0 0;color:#94a3b8;font-size:12px;line-height:1.6;text-align:center;">
              {html.escape(c["footer_intro"])}
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''


__all__ = [
    "render_weekly_digest_html",
    "render_weekly_digest_subject",
]
