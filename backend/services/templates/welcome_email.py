"""
BidVex — Production HTML fallback templates for V9 email kinds + Welcome email.

When SendGrid Dynamic Templates are NOT configured (missing
SENDGRID_TEMPLATE_<KIND>_<EN|FR> env var), the email_delivery_worker
falls back to these inline HTML templates and ships them via SendGrid's
plain HTML `Mail` payload. This guarantees emails are delivered live —
they no longer mark `stubbed_no_template` in the email_outbox.

Each renderer accepts a `dynamic_data` dict and returns a complete HTML
document string. The template lives 100 % in code so we never depend on
the filesystem and the SendGrid templates page being in sync.

Bilingual (EN/FR) rendering follows the same convention as the dynamic
templates: the rendered HTML shows BOTH languages stacked (matching the
operational Welcome layout). The `lang` field merely determines the
subject line and section order.
"""
from __future__ import annotations

from typing import Any, Dict
from datetime import datetime


# ─── Branding tokens (single source of truth — change here, applies everywhere) ───
_BRAND_NAVY     = "#0B2545"
_BRAND_CYAN     = "#3FB4CB"
_BRAND_BUTTON   = "#2186C6"
_BRAND_BG       = "#F0F4F8"
_BRAND_ACCENT   = "#F0F8FF"
_BRAND_AMBER    = "#F59E0B"
_BRAND_GREEN    = "#10B981"
_BRAND_TEXT     = "#1E293B"
_BRAND_MUTED    = "#64748B"
_LOGO_TOP       = ("http://cdn.mcauto-images-production.sendgrid.net/"
                   "4fbf02710175d39f/9dc6a7c3-8237-4a66-b82b-0d9abc165b44/4500x1080.png")
_LOGO_FOOTER    = ("http://cdn.mcauto-images-production.sendgrid.net/"
                   "4fbf02710175d39f/31636d5f-c160-446b-b715-bcf542e9607e/4500x1080.png")

_FONT_STACK = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def _safe(v: Any) -> str:
    """Minimal HTML-escape for template substitutions."""
    if v is None:
        return ""
    s = str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _shell(*, headline_en: str, headline_fr: str, hero_emoji: str,
           body_en: str, body_fr: str,
           cta_label_en: str, cta_label_fr: str, cta_url: str,
           accent_box_en: str = "", accent_box_fr: str = "",
           accent_border_color: str | None = None) -> str:
    """Master shell used by all v9 fallback templates + Welcome.

    Renders header → bilingual headline → English body block (+ optional
    accent box) → divider → French body block (+ optional accent box)
    → primary CTA button → footer.
    """
    border_color = accent_border_color or _BRAND_BUTTON
    accent_en = f"""
            <table cellpadding="0" cellspacing="0" style="background-color:#F8FAFC;border-left:4px solid {border_color};padding:16px;width:100%;margin-bottom:20px;">
              <tr>
                <td style="font-family:{_FONT_STACK};font-size:14px;color:{_BRAND_NAVY};line-height:1.5;">
                  {accent_box_en}
                </td>
              </tr>
            </table>""" if accent_box_en else ""
    accent_fr = f"""
            <table cellpadding="0" cellspacing="0" style="background-color:#F8FAFC;border-left:4px solid {border_color};padding:16px;width:100%;margin-bottom:12px;">
              <tr>
                <td style="font-family:{_FONT_STACK};font-size:14px;color:{_BRAND_NAVY};line-height:1.5;">
                  {accent_box_fr}
                </td>
              </tr>
            </table>""" if accent_box_fr else ""
    cta_html = f"""
        <tr>
          <td style="padding:8px 30px 32px;text-align:center;">
            <table cellpadding="0" cellspacing="0" align="center">
              <tr>
                <td style="background-color:{_BRAND_BUTTON};border-radius:8px;padding:14px 32px;">
                  <a href="{cta_url}" style="color:#FFFFFF;font-family:{_FONT_STACK};font-size:15px;font-weight:bold;text-decoration:none;display:inline-block;" target="_blank">{cta_label_en} / {cta_label_fr}</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>""" if cta_url and cta_label_en else ""
    current_year = datetime.now().year
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>@media (max-width:600px){{.outer-table{{width:100%!important}}.body-cell{{padding:24px 16px!important}}h1{{font-size:20px!important}}}}</style>
</head><body style="margin:0;padding:0;background-color:{_BRAND_BG};font-family:{_FONT_STACK};">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BRAND_BG};padding:24px 12px;">
<tr><td align="center">
<table class="outer-table" width="600" cellpadding="0" cellspacing="0" style="background-color:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">
        <tr>
          <td style="background-color:{_BRAND_NAVY};padding:24px 0;text-align:center;border-bottom:3px solid {_BRAND_CYAN};">
            <img src="{_LOGO_TOP}" alt="BidVex" width="150" style="display:inline-block;width:150px;height:auto;" />
          </td>
        </tr>
        <tr>
          <td style="background-color:{_BRAND_NAVY};padding:32px 30px;text-align:center;">
            <p style="margin:0 0 8px;font-size:48px;line-height:1;">{hero_emoji}</p>
            <h1 style="margin:0;font-family:{_FONT_STACK};font-size:24px;font-weight:bold;color:#FFFFFF;">{headline_en}</h1>
            <p style="margin:8px 0 0;font-family:{_FONT_STACK};font-size:16px;color:rgba(255,255,255,0.7);">{headline_fr}</p>
          </td>
        </tr>
        <tr>
          <td class="body-cell" style="padding:32px 30px;">
            <p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{_BRAND_BUTTON};font-weight:700;font-family:{_FONT_STACK};">ENGLISH</p>
            <p style="margin:0 0 14px;font-family:{_FONT_STACK};font-size:15px;line-height:1.6;color:{_BRAND_TEXT};">{body_en}</p>
            {accent_en}
            <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
              <tr><td style="border-top:2px solid #E2E8F0;height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>
            </table>
            <p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{_BRAND_BUTTON};font-weight:700;font-family:{_FONT_STACK};">FRANÇAIS</p>
            <p style="margin:0 0 14px;font-family:{_FONT_STACK};font-size:15px;line-height:1.6;color:{_BRAND_TEXT};">{body_fr}</p>
            {accent_fr}
            <p style="margin:12px 0 0;font-family:{_FONT_STACK};font-size:12px;color:{_BRAND_MUTED};">
              BidVex uses smart automation systems for instant categorization, fraud detection, and case triage.
              You can request human review of any AI decision at <a href="mailto:privacy@bidvex.com" style="color:{_BRAND_BUTTON};">privacy@bidvex.com</a> (Law&nbsp;25).
              <br/><br/>BidVex utilise des systèmes d'automatisation intelligente. Vous pouvez demander une révision humaine à
              <a href="mailto:privacy@bidvex.com" style="color:{_BRAND_BUTTON};">privacy@bidvex.com</a> (Loi&nbsp;25).
            </p>
          </td>
        </tr>
        {cta_html}
        <tr>
          <td style="background-color:{_BRAND_NAVY};padding:28px 30px;text-align:center;">
            <img src="{_LOGO_FOOTER}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:12px;" /><br/>
            <p style="margin:0 0 6px;font-family:{_FONT_STACK};font-size:12px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>
            <p style="margin:0 0 6px;font-family:{_FONT_STACK};font-size:12px;color:rgba(255,255,255,0.5);"><a href="mailto:service@bidvex.com" style="color:{_BRAND_CYAN};text-decoration:none;">service@bidvex.com</a></p>
            <p style="margin:0;font-family:{_FONT_STACK};font-size:11px;color:rgba(255,255,255,0.35);"><a href="https://bidvex.com/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Privacy</a> &nbsp;|&nbsp; <a href="https://bidvex.com/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Terms</a></p>
            <p style="margin:8px 0 0;font-family:{_FONT_STACK};font-size:11px;color:rgba(255,255,255,0.3);">&copy; {current_year} BidVex Inc.</p>
          </td>
        </tr>
</table></td></tr></table></body></html>"""


# ───────────────────────────────────────────────────────────────────────
# WELCOME EMAIL (Phase 5.3 — Task 4)
# Replaces the prior welcome layout. Always renders both EN+FR stacked,
# Law-25 footer, /how-it-works CTA module, and a 2-card "Featured
# Marketplace Spheres" grid that is rock-solid across email clients.
# ───────────────────────────────────────────────────────────────────────

def render_welcome_email(*, first_name: str = "", marketplace_url: str = "https://bidvex.com/marketplace",
                          how_it_works_url: str = "https://bidvex.com/how-it-works") -> str:
    """Render the v9.3 welcome email with bilingual structure, Law 25
    footer, dual How-It-Works CTA and a 2-card Featured Marketplace
    Spheres grid."""
    fn = _safe(first_name) or "there"
    fn_fr = _safe(first_name) or "à vous"
    current_year = datetime.now().year
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @media (max-width:600px){{
      .outer-table{{width:100%!important}}
      .body-cell{{padding:24px 16px!important}}
      h1{{font-size:20px!important}}
      .grid-item{{width:100%!important; padding-right:0!important; margin-bottom:16px!important;}}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:{_BRAND_BG};font-family:{_FONT_STACK};">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BRAND_BG};padding:24px 12px;">
  <tr>
    <td align="center">
      <table class="outer-table" width="600" cellpadding="0" cellspacing="0" style="background-color:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">

        <tr>
          <td style="background-color:{_BRAND_NAVY};padding:24px 0;text-align:center;border-bottom:3px solid {_BRAND_CYAN};">
            <img src="{_LOGO_TOP}" alt="BidVex" width="150" style="display:inline-block;width:150px;height:auto;" />
          </td>
        </tr>

        <tr>
          <td style="background-color:{_BRAND_NAVY};padding:32px 30px;text-align:center;">
            <p style="margin:0 0 8px;font-size:48px;line-height:1;">&#127881;</p>
            <h1 style="margin:0;font-family:{_FONT_STACK};font-size:24px;font-weight:bold;color:#FFFFFF;">Welcome to BidVex, {fn}!</h1>
            <p style="margin:8px 0 0;font-family:{_FONT_STACK};font-size:16px;color:rgba(255,255,255,0.7);">Bienvenue chez BidVex, {fn_fr} !</p>
          </td>
        </tr>

        <tr>
          <td class="body-cell" style="padding:32px 30px;">
            <p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{_BRAND_BUTTON};font-weight:700;font-family:{_FONT_STACK};">ENGLISH</p>
            <p style="margin:0 0 20px;font-family:{_FONT_STACK};font-size:15px;line-height:1.6;color:{_BRAND_TEXT};">You've just joined North America's most advanced all-in-one auction marketplace. Whether you're partnering with an authorized broker to acquire commercial vehicles or looking to scale your portfolio &mdash; BidVex is built to handle it all.</p>

            <table cellpadding="0" cellspacing="0" style="background-color:#F8FAFC;border-left:4px solid {_BRAND_BUTTON};padding:16px;width:100%;margin-bottom:28px;">
              <tr>
                <td style="font-family:{_FONT_STACK};font-size:14px;color:{_BRAND_NAVY};line-height:1.5;">
                  <strong>New to Broker-Proxy Bidding?</strong> Discover our streamlined 7-step transaction pipeline to place legal bids safely.
                  <br/>
                  <a href="{how_it_works_url}" style="color:{_BRAND_BUTTON};font-weight:bold;text-decoration:none;display:inline-block;margin-top:6px;" target="_blank">Read the How-It-Works Guide &rarr;</a>
                </td>
              </tr>
            </table>

            <p style="margin:0 0 16px;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:{_BRAND_NAVY};font-weight:700;font-family:{_FONT_STACK};border-bottom:1px solid #E2E8F0;padding-bottom:6px;">&#9889; Featured Marketplace Spheres / Catégories en Vedette</p>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
              <tr>
                <td valign="top">
                  <table class="grid-item" width="48%" align="left" cellpadding="0" cellspacing="0" style="background-color:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin-bottom:14px;">
                    <tr><td style="background-color:#E2E8F0;text-align:center;padding:20px;font-size:32px;">&#128663;</td></tr>
                    <tr>
                      <td style="padding:12px;font-family:{_FONT_STACK};">
                        <h4 style="margin:0 0 4px;font-size:13px;color:{_BRAND_NAVY};">Vehicle Auctions</h4>
                        <p style="margin:0;font-size:11px;color:{_BRAND_MUTED};line-height:1.4;">Automotive fleets, clean titles, salvage assets.</p>
                      </td>
                    </tr>
                  </table>

                  <table class="grid-item" width="48%" align="right" cellpadding="0" cellspacing="0" style="background-color:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin-bottom:14px;">
                    <tr><td style="background-color:#E2E8F0;text-align:center;padding:20px;font-size:32px;">&#128230;</td></tr>
                    <tr>
                      <td style="padding:12px;font-family:{_FONT_STACK};">
                        <h4 style="margin:0 0 4px;font-size:13px;color:{_BRAND_NAVY};">Multi-Lot Industrial</h4>
                        <p style="margin:0;font-size:11px;color:{_BRAND_MUTED};line-height:1.4;">Commercial closeouts, bulk goods, business clearings.</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <p style="margin:24px 0 0;font-family:{_FONT_STACK};font-size:12px;color:{_BRAND_MUTED};">BidVex uses smart automation systems for instant structural sorting and protective risk controls. You can request direct human review of processing flags any time at <a href="mailto:privacy@bidvex.com" style="color:{_BRAND_BUTTON};">privacy@bidvex.com</a> (Law 25).</p>

            <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
              <tr><td style="border-top:2px solid #E2E8F0;height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>
            </table>

            <p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{_BRAND_BUTTON};font-weight:700;font-family:{_FONT_STACK};">FRANÇAIS</p>
            <p style="margin:0 0 20px;font-family:{_FONT_STACK};font-size:15px;line-height:1.6;color:{_BRAND_TEXT};">Vous venez de rejoindre la plateforme de vente aux enchères tout-en-un la plus avancée en Amérique du Nord. Que vous vous associiez à un courtier agréé pour acquérir des véhicules ou que vous souhaitiez liquider des lots entiers &mdash; BidVex est conçu pour tout gérer.</p>

            <table cellpadding="0" cellspacing="0" style="background-color:#F8FAFC;border-left:4px solid {_BRAND_BUTTON};padding:16px;width:100%;margin-bottom:12px;">
              <tr>
                <td style="font-family:{_FONT_STACK};font-size:14px;color:{_BRAND_NAVY};line-height:1.5;">
                  <strong>Nouveau aux enchères par courtier&nbsp;?</strong> Découvrez notre parcours simplifié en 7 étapes pour placer vos offres en toute sécurité.
                  <br/>
                  <a href="{how_it_works_url}" style="color:{_BRAND_BUTTON};font-weight:bold;text-decoration:none;display:inline-block;margin-top:6px;" target="_blank">Consulter le guide de fonctionnement &rarr;</a>
                </td>
              </tr>
            </table>

            <p style="margin:12px 0 0;font-family:{_FONT_STACK};font-size:12px;color:{_BRAND_MUTED};">BidVex utilise des outils automatisés intelligents pour la catégorisation et la détection des fraudes. Vous pouvez demander une révision humaine de toute décision automatisée à <a href="mailto:privacy@bidvex.com" style="color:{_BRAND_BUTTON};">privacy@bidvex.com</a> (Loi 25).</p>
          </td>
        </tr>

        <tr>
          <td style="padding:8px 30px 32px;text-align:center;">
            <table cellpadding="0" cellspacing="0" align="center">
              <tr>
                <td style="background-color:{_BRAND_BUTTON};border-radius:8px;padding:14px 32px;">
                  <a href="{marketplace_url}" style="color:#FFFFFF;font-family:{_FONT_STACK};font-size:15px;font-weight:bold;text-decoration:none;display:inline-block;" target="_blank">Explore the Marketplace / Explorer le marché</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="background-color:{_BRAND_NAVY};padding:28px 30px;text-align:center;">
            <img src="{_LOGO_FOOTER}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:12px;" /><br/>
            <p style="margin:0 0 6px;font-family:{_FONT_STACK};font-size:12px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>
            <p style="margin:0 0 6px;font-family:{_FONT_STACK};font-size:12px;color:rgba(255,255,255,0.5);"><a href="mailto:service@bidvex.com" style="color:{_BRAND_CYAN};text-decoration:none;">service@bidvex.com</a></p>
            <p style="margin:0;font-family:{_FONT_STACK};font-size:11px;color:rgba(255,255,255,0.35);"><a href="https://bidvex.com/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Privacy</a> &nbsp;|&nbsp; <a href="https://bidvex.com/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Terms</a></p>
            <p style="margin:8px 0 0;font-family:{_FONT_STACK};font-size:11px;color:rgba(255,255,255,0.3);">&copy; {current_year} BidVex Inc.</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ───────────────────────────────────────────────────────────────────────
# V9 FALLBACK RENDERERS — one per kind. All return full HTML strings.
# ───────────────────────────────────────────────────────────────────────

def _render_auction_end_time_changed(role: str, dd: Dict[str, Any]) -> str:
    """role ∈ {seller, bidder, watchlist}. The body copy varies slightly per role."""
    title = _safe(dd.get("listing_title") or "your auction")
    new_end = _safe(dd.get("new_end_time") or dd.get("context", {}).get("new_end_time", ""))
    old_end = _safe(dd.get("old_end_time") or dd.get("context", {}).get("old_end_time", ""))
    cta_url = _safe(dd.get("cta_url") or "https://bidvex.com/marketplace")
    role_copy = {
        "seller":    ("Your auction end time was updated by an administrator.",
                      "L'heure de fin de votre enchère a été modifiée par un administrateur."),
        "bidder":    ("An auction you bid on has a new end time.",
                      "Une enchère sur laquelle vous avez enchéri a une nouvelle heure de fin."),
        "watchlist": ("An auction in your watchlist has a new end time.",
                      "Une enchère de votre liste de suivi a une nouvelle heure de fin."),
    }.get(role, ("End time updated.", "Heure de fin mise à jour."))
    body_en = (
        f"{role_copy[0]}<br/><br/>"
        f"<strong>Auction:</strong> {title}<br/>"
        f"<strong>New end time (UTC):</strong> {new_end}<br/>"
        + (f"<strong>Previous end time (UTC):</strong> {old_end}<br/>" if old_end else "")
    )
    body_fr = (
        f"{role_copy[1]}<br/><br/>"
        f"<strong>Enchère :</strong> {title}<br/>"
        f"<strong>Nouvelle heure de fin (UTC) :</strong> {new_end}<br/>"
        + (f"<strong>Heure de fin précédente (UTC) :</strong> {old_end}<br/>" if old_end else "")
    )
    return _shell(
        headline_en="Auction end time updated",
        headline_fr="Heure de fin mise à jour",
        hero_emoji="&#9202;",
        body_en=body_en, body_fr=body_fr,
        cta_label_en="View Auction", cta_label_fr="Voir l'enchère",
        cta_url=cta_url,
        accent_border_color=_BRAND_AMBER,
    )


def render_auction_end_time_changed_seller(dd):    return _render_auction_end_time_changed("seller", dd)
def render_auction_end_time_changed_bidder(dd):    return _render_auction_end_time_changed("bidder", dd)
def render_auction_end_time_changed_watchlist(dd): return _render_auction_end_time_changed("watchlist", dd)


def render_ai_review_admin_alert(dd: Dict[str, Any]) -> str:
    title = _safe(dd.get("listing_title") or "(no title)")
    seller_cat = _safe(dd.get("seller_category") or "—")
    sugg_cat = _safe(dd.get("suggested_category") or "—")
    cta_url = _safe(dd.get("cta_url") or "https://bidvex.com/admin?tab=flagged-listings")
    return _shell(
        headline_en="A listing needs your review",
        headline_fr="Une annonce nécessite votre examen",
        hero_emoji="&#128737;",
        body_en=(
            f"The AI watchdog flagged a possible category mismatch.<br/><br/>"
            f"<strong>Listing:</strong> {title}<br/>"
            f"<strong>Seller's category:</strong> {seller_cat}<br/>"
            f"<strong>AI suggested category:</strong> {sugg_cat}"
        ),
        body_fr=(
            f"Le système IA a signalé une possible incohérence de catégorie.<br/><br/>"
            f"<strong>Annonce :</strong> {title}<br/>"
            f"<strong>Catégorie du vendeur :</strong> {seller_cat}<br/>"
            f"<strong>Catégorie suggérée par l'IA :</strong> {sugg_cat}"
        ),
        cta_label_en="Open Admin Panel", cta_label_fr="Ouvrir le panneau admin",
        cta_url=cta_url,
        accent_border_color=_BRAND_AMBER,
    )


def render_ai_review_admin_escalation(dd: Dict[str, Any]) -> str:
    title = _safe(dd.get("listing_title") or "(no title)")
    minutes_open = _safe(dd.get("minutes_open") or 60)
    cta_url = _safe(dd.get("cta_url") or "https://bidvex.com/admin?tab=flagged-listings")
    return _shell(
        headline_en=f"AI review still open after {minutes_open} minutes",
        headline_fr=f"Examen IA toujours ouvert depuis plus de {minutes_open} minutes",
        hero_emoji="&#9889;",
        body_en=(
            f"Listing <strong>{title}</strong> has been awaiting admin review for over "
            f"{minutes_open} minutes. Please action it as soon as possible to keep the marketplace healthy."
        ),
        body_fr=(
            f"L'annonce <strong>{title}</strong> attend un examen administrateur depuis plus de "
            f"{minutes_open} minutes. Veuillez la traiter dès que possible afin de maintenir la place de marché en bonne santé."
        ),
        cta_label_en="Open Admin Panel", cta_label_fr="Ouvrir le panneau admin",
        cta_url=cta_url,
        accent_border_color=_BRAND_AMBER,
    )


def render_ai_review_approved(dd: Dict[str, Any]) -> str:
    title = _safe(dd.get("listing_title") or "(no title)")
    admin_note = _safe(dd.get("admin_note") or "")
    cta_url = _safe(dd.get("cta_url") or "https://bidvex.com/seller/dashboard")
    note_block_en = f"<br/><br/><em>Admin note:</em> {admin_note}" if admin_note else ""
    note_block_fr = f"<br/><br/><em>Note de l'administrateur :</em> {admin_note}" if admin_note else ""
    return _shell(
        headline_en="Your listing has been approved",
        headline_fr="Votre annonce a été approuvée",
        hero_emoji="&#9989;",
        body_en=(
            f"Good news &mdash; <strong>{title}</strong> has been approved by our team and is now visible on the marketplace.{note_block_en}"
        ),
        body_fr=(
            f"Bonne nouvelle &mdash; <strong>{title}</strong> a été approuvée par notre équipe et est maintenant visible sur la place de marché.{note_block_fr}"
        ),
        cta_label_en="View My Listings", cta_label_fr="Voir mes annonces",
        cta_url=cta_url,
        accent_border_color=_BRAND_GREEN,
    )


def render_ai_review_rejected(dd: Dict[str, Any]) -> str:
    title = _safe(dd.get("listing_title") or "(no title)")
    admin_note = _safe(dd.get("admin_note") or "")
    cta_url = _safe(dd.get("cta_url") or "https://bidvex.com/seller/dashboard")
    note_block_en = f"<br/><br/><em>Admin note:</em> {admin_note}" if admin_note else ""
    note_block_fr = f"<br/><br/><em>Note de l'administrateur :</em> {admin_note}" if admin_note else ""
    return _shell(
        headline_en="Your listing was rejected after review",
        headline_fr="Votre annonce a été rejetée après examen",
        hero_emoji="&#10060;",
        body_en=(
            f"After review, <strong>{title}</strong> could not be approved as-is.{note_block_en}"
            f"<br/><br/>You can fix the category from your dashboard and resubmit it &mdash; or contact support if you believe this is a mistake."
        ),
        body_fr=(
            f"Après examen, <strong>{title}</strong> n'a pas pu être approuvée telle quelle.{note_block_fr}"
            f"<br/><br/>Vous pouvez modifier la catégorie depuis votre tableau de bord et la soumettre à nouveau &mdash; ou contacter le support si vous pensez qu'il s'agit d'une erreur."
        ),
        cta_label_en="Open Dashboard", cta_label_fr="Ouvrir le tableau de bord",
        cta_url=cta_url,
        accent_border_color=_BRAND_AMBER,
    )


# Optional: invoice with quantity multiplier — placeholder for the 7th category mentioned in spec.
def render_quantity_invoice(dd: Dict[str, Any]) -> str:
    title = _safe(dd.get("listing_title") or "(no title)")
    qty = _safe(dd.get("quantity") or 1)
    base_amount = _safe(dd.get("base_amount") or "")
    cta_url = _safe(dd.get("cta_url") or "https://bidvex.com/my-receipt")
    return _shell(
        headline_en="Your invoice is ready",
        headline_fr="Votre facture est prête",
        hero_emoji="&#129534;",
        body_en=(
            f"Your invoice for <strong>{title}</strong> is ready.<br/>"
            f"<strong>Quantity:</strong> {qty}<br/>"
            f"<strong>Base amount (hammer × qty):</strong> CA${base_amount}<br/>"
            f"All platform &amp; broker fees have been calculated against the full base amount as you opted in for per-unit hammer pricing."
        ),
        body_fr=(
            f"Votre facture pour <strong>{title}</strong> est prête.<br/>"
            f"<strong>Quantité :</strong> {qty}<br/>"
            f"<strong>Montant de base (marteau × qté) :</strong> CA${base_amount}<br/>"
            f"Tous les frais de plateforme &amp; courtier ont été calculés sur le montant de base complet, conformément à votre choix de prix marteau par unité."
        ),
        cta_label_en="View Invoice", cta_label_fr="Voir la facture",
        cta_url=cta_url,
        accent_border_color=_BRAND_BUTTON,
    )


# ───────────────────────────────────────────────────────────────────────
# REGISTRY — kind ↔ renderer mapping used by the email_delivery_worker.
# ───────────────────────────────────────────────────────────────────────

HTML_FALLBACK_RENDERERS = {
    "auction_end_time_changed_seller":    render_auction_end_time_changed_seller,
    "auction_end_time_changed_bidder":    render_auction_end_time_changed_bidder,
    "auction_end_time_changed_watchlist": render_auction_end_time_changed_watchlist,
    "ai_review_admin_alert":              render_ai_review_admin_alert,
    "ai_review_admin_escalation":         render_ai_review_admin_escalation,
    "ai_review_approved":                 render_ai_review_approved,
    "ai_review_rejected":                 render_ai_review_rejected,
    "quantity_invoice":                   render_quantity_invoice,
}


def render_kind_html(kind: str, dynamic_data: Dict[str, Any]) -> str | None:
    """Return an HTML string for the given kind, or None if no fallback exists."""
    fn = HTML_FALLBACK_RENDERERS.get(kind)
    if not fn:
        return None
    try:
        return fn(dynamic_data or {})
    except Exception:
        # Never raise out of a template — caller will see None and stub-handle.
        return None
