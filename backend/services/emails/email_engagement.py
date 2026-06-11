"""
services/emails/email_engagement.py — iter300

Engagement / lifecycle emails:
  • Top Seller badge congratulations (bilingual)
  • Followed-seller new listing alert (bilingual)
  • Overdue payment final warning (bilingual)
  • Bidding privileges suspended (bilingual)

All templates are STRICT Outlook-safe table layouts (inline CSS, no
div/flex/grid/gradients) — enforced by test_email_templates_are_table_only.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from services.emails._email_core import _base_template, send_email

logger = logging.getLogger(__name__)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")


def _cta(url: str, label: str, bg: str = "#2563eb") -> str:
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td align="center" style="padding:18px 0;">
        <a href="{url}" style="display:inline-block;padding:12px 28px;background-color:{bg};color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;">
          {label}
        </a>
      </td></tr>
    </table>
    """


def _bi_block(en_html: str, fr_html: str) -> str:
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="color:#334155;font-size:14px;line-height:1.6;">{en_html}</td></tr>
      <tr><td style="padding:12px 0;"><hr style="border:none;border-top:1px solid #e2e8f0;"/></td></tr>
      <tr><td style="color:#334155;font-size:14px;line-height:1.6;">{fr_html}</td></tr>
    </table>
    """


async def send_top_seller_congrats_email(*, to_email: str, to_name: str,
                                         lang: str = "en", store_url_path: str = "") -> Dict[str, Any]:
    url = f"{FRONTEND_URL}{store_url_path}"
    content = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td bgcolor="#fffbeb" align="center" style="background-color:#fffbeb;border:2px solid #f59e0b;border-radius:12px;padding:20px;">
        <p style="margin:0;font-size:30px;">⭐</p>
        <h2 style="margin:8px 0 2px 0;color:#92400e;font-size:22px;">Top Seller / Meilleur Vendeur</h2>
        <p style="margin:0;color:#b45309;font-size:12px;letter-spacing:1px;">BIDVEX MERIT BADGE</p>
      </td></tr>
      <tr><td style="height:16px;line-height:16px;font-size:1px;">&nbsp;</td></tr>
    </table>
    {_bi_block(
        f"<p style='margin:0 0 8px 0;'>Hi <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>Congratulations — you are now one of BidVex's <strong>Top Sellers</strong>! "
        f"This merit badge is awarded to our five highest sellers by total sales volume and now appears "
        f"on your public storefront and on all of your active listings. Keep up the great work!</p>",
        f"<p style='margin:0 0 8px 0;'>Bonjour <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>Félicitations — vous faites maintenant partie des <strong>Meilleurs Vendeurs</strong> BidVex ! "
        f"Cet insigne de mérite est décerné à nos cinq meilleurs vendeurs par volume de ventes et apparaît "
        f"désormais sur votre vitrine publique et sur toutes vos annonces actives. Continuez votre excellent travail !</p>",
    )}
    {_cta(url, "View my storefront · Voir ma vitrine", "#d97706")}
    """
    subject = ("⭐ Félicitations — vous êtes un Meilleur Vendeur BidVex !"
               if (lang or "en").startswith("fr")
               else "⭐ Congratulations — you're a BidVex Top Seller!")
    return await send_email(
        to_email=to_email, subject=subject,
        html_content=_base_template(content, title="Top Seller"),
        categories=["top_seller"])


async def send_followed_seller_new_listing_email(*, to_email: str, to_name: str,
                                                 seller_name: str, listing_title: str,
                                                 url_path: str) -> Dict[str, Any]:
    url = f"{FRONTEND_URL}{url_path}"
    content = f"""
    {_bi_block(
        f"<p style='margin:0 0 8px 0;'>Hi <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'><strong>{seller_name}</strong> just listed "
        f"<strong>{listing_title}</strong> — bid now before it's gone!</p>",
        f"<p style='margin:0 0 8px 0;'>Bonjour <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'><strong>{seller_name}</strong> vient de publier "
        f"<strong>{listing_title}</strong> — misez maintenant avant qu'il ne soit trop tard !</p>",
    )}
    {_cta(url, "Bid now · Miser maintenant")}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td align="center" style="font-size:11px;color:#94a3b8;">
        You receive this because you follow {seller_name} on BidVex. Manage follows in your buyer dashboard.<br/>
        Vous recevez ceci car vous suivez {seller_name} sur BidVex. Gérez vos abonnements dans votre tableau de bord.
      </td></tr>
    </table>
    """
    return await send_email(
        to_email=to_email,
        subject=f"🔔 {seller_name} just listed: {listing_title}",
        html_content=_base_template(content, title="New listing from a seller you follow"),
        categories=["followed_seller_new_listing"])


async def send_payment_final_warning_email(*, to_email: str, to_name: str,
                                           listing_title: str, amount: float,
                                           attempt: int, max_attempts: int = 3) -> Dict[str, Any]:
    url = f"{FRONTEND_URL}/dashboard/buyer"
    content = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td bgcolor="#fef2f2" style="background-color:#fef2f2;border:2px solid #dc2626;border-radius:10px;padding:16px;">
        <p style="margin:0;color:#991b1b;font-weight:700;font-size:15px;">⚠️ FINAL WARNING — Payment Overdue / DERNIER AVERTISSEMENT — Paiement en retard</p>
        <p style="margin:6px 0 0 0;color:#7f1d1d;font-size:13px;">Attempt {attempt} of {max_attempts} · Tentative {attempt} de {max_attempts}</p>
      </td></tr>
      <tr><td style="height:14px;line-height:14px;font-size:1px;">&nbsp;</td></tr>
    </table>
    {_bi_block(
        f"<p style='margin:0 0 8px 0;'>Hi <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>Your payment of <strong>CA${amount:,.2f}</strong> for "
        f"<strong>{listing_title}</strong> is overdue and our automatic charge attempt failed. "
        f"<strong>Your account may be suspended if this is not resolved within 24 hours.</strong> "
        f"Please update your payment method or settle the balance immediately.</p>",
        f"<p style='margin:0 0 8px 0;'>Bonjour <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>Votre paiement de <strong>{amount:,.2f} $ CAD</strong> pour "
        f"<strong>{listing_title}</strong> est en retard et notre tentative de prélèvement automatique a échoué. "
        f"<strong>Votre compte pourrait être suspendu si la situation n'est pas résolue dans les 24 heures.</strong> "
        f"Veuillez mettre à jour votre méthode de paiement ou régler le solde immédiatement.</p>",
    )}
    {_cta(url, "Resolve now · Régler maintenant", "#dc2626")}
    """
    return await send_email(
        to_email=to_email,
        subject=f"⚠️ FINAL WARNING — payment overdue for {listing_title}",
        html_content=_base_template(content, title="Payment Overdue"),
        categories=["payment_final_warning"])


async def send_bidding_suspended_email(*, to_email: str, to_name: str,
                                       listing_title: str) -> Dict[str, Any]:
    content = f"""
    {_bi_block(
        f"<p style='margin:0 0 8px 0;'>Hi <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>After three failed payment attempts for <strong>{listing_title}</strong>, "
        f"your bidding privileges on BidVex have been <strong>suspended</strong>. "
        f"To restore your account, settle your outstanding balance and contact "
        f"<a href='mailto:support@bidvex.com'>support@bidvex.com</a>.</p>",
        f"<p style='margin:0 0 8px 0;'>Bonjour <strong>{to_name}</strong>,</p>"
        f"<p style='margin:0;'>Après trois tentatives de paiement échouées pour <strong>{listing_title}</strong>, "
        f"vos privilèges d'enchères sur BidVex ont été <strong>suspendus</strong>. "
        f"Pour rétablir votre compte, réglez votre solde impayé et contactez "
        f"<a href='mailto:support@bidvex.com'>support@bidvex.com</a>.</p>",
    )}
    """
    return await send_email(
        to_email=to_email,
        subject="Your BidVex bidding privileges have been suspended",
        html_content=_base_template(content, title="Bidding Suspended"),
        categories=["bidding_suspended"])
