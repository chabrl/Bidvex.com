"""services/emails/email_vehicles.py — iter295 P2

Vehicle-specific email senders. Function bodies physically
migrated from services/email_notifications.py."""
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from services.emails._email_core import (
    SENDGRID_API_KEY, SENDGRID_AVAILABLE, sg, FRONTEND_URL,
    FROM_EMAIL, FROM_NAME,
    TRANSACTIONAL_FROM_EMAIL, TRANSACTIONAL_FROM_NAME,
    TRANSACTIONAL_REPLY_TO, TRANSACTIONAL_REPLY_TO_NAME,
    B2B_PARTNER_FROM_EMAIL, B2B_PARTNER_FROM_NAME,
    B2B_PARTNER_REPLY_TO, B2B_PARTNER_REPLY_TO_NAME,
    MARKETING_REPLY_TO, MARKETING_REPLY_TO_NAME,
    _format_currency, _format_date, _format_currency_fr,
    _detect_language, _section_label, _base_template, _storage_panel,
    send_email, send_unified_email, _send_via_unified,
)
import os as _os

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# iter175 — Vehicle deposit auto-captured (bilingual EN+FR per Bill 96)
# ─────────────────────────────────────────────────────────────
async def send_vehicle_deposit_captured_email(
    buyer: dict,
    invoice: dict,
    deposit: dict,
    captured_amount: float,
) -> bool:
    """
    Sent automatically when the auto-capture cron job captures a $500 vehicle
    bidding deposit because the winner's 2.5% platform-fee invoice remained
    unpaid past `payment_deadline + 48h`. EN+FR per Bill 96.
    """
    if not buyer or not buyer.get("email"):
        return False

    inv_no = invoice.get("invoice_number", "—")
    veh_title = invoice.get("vehicle_title", "your vehicle")
    fee_total = invoice.get("total_amount") or invoice.get("platform_fee") or 0
    amt = captured_amount or deposit.get("amount") or 500.0

    body_en = (
        f"Your $500 bidding deposit for <strong>{veh_title}</strong> has been "
        f"captured because invoice <strong>{inv_no}</strong> "
        f"(${fee_total:.2f} CAD platform fee) was not paid within 48 hours of "
        f"the deadline. Amount captured: <strong>${amt:.2f} CAD</strong>. "
        f"This brings your account into good standing — no further action is required. "
        f"If you believe this was in error, contact support@bidvex.com within 14 days."
    )
    body_fr = (
        f"Votre dépôt d'enchère de 500 $ pour <strong>{veh_title}</strong> a été "
        f"saisi parce que la facture <strong>{inv_no}</strong> "
        f"({fee_total:.2f} $ CAD de frais de plateforme) n'a pas été payée dans les "
        f"48 heures suivant l'échéance. Montant saisi : <strong>{amt:.2f} $ CAD</strong>. "
        f"Votre compte est maintenant en règle — aucune autre action requise. "
        f"Si vous croyez qu'il s'agit d'une erreur, contactez support@bidvex.com dans les 14 jours."
    )

    html = _storage_panel(
        "Bidding deposit captured",
        "Dépôt d'enchère saisi",
        body_en,
        body_fr,
        cta_url="https://www.bidvex.com/profile/settings?tab=billing",
        cta_en="View invoices",
        cta_fr="Voir les factures",
    )
    return await _send_via_unified(
        to_email=buyer["email"],
        subject=f"[BidVex] Bidding deposit captured · Dépôt saisi — Invoice {inv_no}",
        html_content=html,
    )


async def send_seller_auction_sold_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    hammer_price: float,
    platform_fee: float,
    net_payout: float,
    winning_bidder_alias: str,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Sent to the seller when their auction ends with at least one bid."""
    label = _section_label(auction_type)
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🏁 Your auction ended — item sold / Votre enchère est terminée</h2>

    <p style="color: #475569; line-height: 1.6;">Hi {seller_name},</p>

    <p style="color: #475569; line-height: 1.6;">
        Great news — your {label['name_en']} auction ended and the item has sold.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #ecfdf5; border: 2px solid #10b981; border-radius: 8px; padding: 25px;">
        <p style="margin: 0 0 12px 0; color: #065f46; font-size: 18px; font-weight: bold;">{listing_title}</p>
        <table width="100%" style="font-size: 14px; color: #1e293b;">
          <tr><td style="padding: 6px 0;">Hammer Price:</td>
              <td style="padding: 6px 0; text-align: right; font-weight: bold;">{_format_currency(hammer_price)}</td></tr>
          <tr><td style="padding: 6px 0;">Platform Fee:</td>
              <td style="padding: 6px 0; text-align: right; color: #dc2626;">−{_format_currency(platform_fee)}</td></tr>
          <tr><td style="padding: 6px 0; border-top: 1px solid #d1fae5;"><strong>Your Payout (est.):</strong></td>
              <td style="padding: 6px 0; text-align: right; border-top: 1px solid #d1fae5; font-size: 18px; color: #065f46; font-weight: bold;">{_format_currency(net_payout)}</td></tr>
          <tr><td style="padding: 6px 0;">Winning Bidder:</td>
              <td style="padding: 6px 0; text-align: right; color: #475569;">{winning_bidder_alias}</td></tr>
        </table>
      </td></tr>
    </table>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
        <a href="{FRONTEND_URL}/dashboard/sales" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">Open Seller Dashboard</a>
      </td></tr>
    </table>

    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        Your payout will be transferred to your connected Stripe account once the buyer completes payment (typically within 2–5 business days).
    </p>

    <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#475569;line-height:1.6;">
        Bonjour {seller_name}, votre enchère {label['name_fr']} s'est terminée et l'article a été vendu pour {_format_currency(hammer_price)}.
        Votre paiement sera transféré sur votre compte Stripe connecté une fois que l'acheteur aura payé.
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"Your auction ended — {listing_title} sold for {_format_currency(hammer_price)} | {label['name_en']}",
        html_content=_base_template(content, "Auction Ended — Item Sold", auction_type=auction_type),
    )


async def send_seller_auction_no_bids_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    auction_type: Optional[str] = None,
    auction_end_time: Optional[str] = None,
    bid_count: int = 0,
) -> Dict[str, Any]:
    """Sent to the seller when their auction ends with zero bids.

    iter298 BUG 2 — Includes auction end time + final bid count and three
    clear CTAs: Relist Now · Edit & Relist · Promote This Listing. All
    three deep-link into the seller dashboard's Ended tab where the
    one-click actions live."""
    label = _section_label(auction_type)
    end_h = _format_date(auction_end_time) if auction_end_time else "—"
    dash = f"{FRONTEND_URL}/seller/dashboard?filter=ended"

    def _cta(href: str, text_en: str, text_fr: str, bg: str) -> str:
        return f"""
      <td align="center" style="padding: 0 6px;">
        <table cellpadding="0" cellspacing="0" border="0"><tr>
          <td align="center" style="background-color: {bg}; padding: 12px 18px; border-radius: 8px;">
            <a href="{href}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 14px;">{text_en}<br/><span style="font-weight: 400; font-size: 12px;">{text_fr}</span></a>
          </td>
        </tr></table>
      </td>"""

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">Your auction ended — no bids / Votre enchère s'est terminée sans enchères</h2>

    <p style="color: #475569; line-height: 1.6;">Hi {seller_name},</p>
    <p style="color: #475569; line-height: 1.6;">
        Your {label['name_en']} auction for <strong>{listing_title}</strong> ended without any bids.
        Relist it to reach more buyers — sometimes a fresh title, better photos, or a lower starting price makes the difference.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 16px 0;">
      <tr>
        <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Item / Article</td>
        <td align="right" style="padding: 6px 0; color: #0f172a; font-size: 13px; font-weight: 700;">{listing_title}</td>
      </tr>
      <tr>
        <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Auction ended / Fin de l'enchère</td>
        <td align="right" style="padding: 6px 0; color: #0f172a; font-size: 13px; font-weight: 700;">{end_h}</td>
      </tr>
      <tr>
        <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Final bid count / Nombre de mises</td>
        <td align="right" style="padding: 6px 0; color: #0f172a; font-size: 13px; font-weight: 700;">{bid_count}</td>
      </tr>
    </table>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 26px auto;">
      <tr>
        {_cta(f"{dash}&action=relist&listing={listing_id}", "Relist Now", "Republier", "#0ea5e9")}
        {_cta(f"{dash}&action=edit_relist&listing={listing_id}", "Edit &amp; Relist", "Modifier et republier", "#6366f1")}
        {_cta(f"{dash}&action=promote&listing={listing_id}", "Promote This Listing", "Promouvoir", "#f59e0b")}
      </tr>
    </table>

    <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#475569;line-height:1.6;">
        Bonjour {seller_name}, votre enchère {label['name_fr']} pour <strong>{listing_title}</strong> s'est terminée sans enchères ({bid_count} mise).
        Republiez-la pour atteindre plus d'acheteurs — depuis l'onglet « Terminées » de votre tableau de bord vendeur.
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"Your auction ended with no bids — {listing_title}",
        html_content=_base_template(content, "Auction Ended — No Bids", auction_type=auction_type),
    )


async def send_dealer_license_approved_email(user: dict, license_doc: dict) -> bool:
    """Notify a buyer their dealer-license verification is approved."""
    if not user or not user.get("email"):
        return False
    license_no = license_doc.get("license_number", "")[:32]
    jurisdiction = license_doc.get("jurisdiction", "")
    body_en = (
        f"Your dealer license has been verified. You can now bid on licensed-only vehicle "
        f"auctions on BidVex.<br/><br/>"
        f"License #: <strong>{license_no}</strong> ({jurisdiction})<br/>"
        f"Status: <strong style='color:#059669;'>Approved</strong>"
    )
    body_fr = (
        f"Votre permis de concessionnaire a été vérifié. Vous pouvez maintenant enchérir "
        f"sur les enchères de véhicules réservées aux concessionnaires sur BidVex.<br/><br/>"
        f"N° de permis : <strong>{license_no}</strong> ({jurisdiction})<br/>"
        f"Statut : <strong style='color:#059669;'>Approuvé</strong>"
    )
    # iter249 Mission 3 — Language-aware subject (body already bilingual).
    _dl_lang = _detect_language(user)
    subject_dl = (
        "✅ Permis de concessionnaire vérifié"
        if _dl_lang == "fr"
        else "✅ Dealer License Verified · Permis de concessionnaire vérifié"
    )
    return await _send_via_unified(
        to_email=user["email"],
        subject=subject_dl,
        html_content=_storage_panel(
            "Dealer License Approved", "Permis de concessionnaire approuvé",
            body_en, body_fr,
            cta_url="https://bidvex.com/vehicle-auctions",
            cta_en="Browse Vehicle Auctions",
            cta_fr="Parcourir les enchères de véhicules",
        ),
    )


async def send_dealer_license_rejected_email(user: dict, license_doc: dict, reason: str = "") -> bool:
    """Notify a buyer their dealer-license verification was rejected."""
    if not user or not user.get("email"):
        return False
    license_no = license_doc.get("license_number", "")[:32]
    reason_en = reason or "Please contact support for more information."
    reason_fr = reason or "Veuillez contacter le support pour plus d'informations."
    body_en = (
        f"Your dealer license submission was reviewed and unfortunately could not be approved.<br/><br/>"
        f"License #: <strong>{license_no}</strong><br/>"
        f"Reason: <em>{reason_en}</em><br/><br/>"
        f"You may resubmit a corrected license at any time."
    )
    body_fr = (
        f"Votre soumission de permis de concessionnaire a été examinée et n'a malheureusement pas pu être approuvée.<br/><br/>"
        f"N° de permis : <strong>{license_no}</strong><br/>"
        f"Raison : <em>{reason_fr}</em><br/><br/>"
        f"Vous pouvez soumettre à nouveau un permis corrigé à tout moment."
    )
    return await _send_via_unified(
        to_email=user["email"],
        subject="Dealer License Verification — Action Required · Action requise",
        html_content=_storage_panel(
            "License Verification Rejected", "Vérification du permis rejetée",
            body_en, body_fr,
            cta_url="https://bidvex.com/vehicle-auctions/dealer-license",
            cta_en="Resubmit Dealer License",
            cta_fr="Resoumettre le permis",
        ),
    )


async def send_dealer_license_expired_email(user: dict, license_doc: dict) -> bool:
    """Notify a buyer their dealer-license verification has expired."""
    if not user or not user.get("email"):
        return False
    license_no = license_doc.get("license_number", "")[:32]
    expiry = license_doc.get("expiry_date", "")
    if hasattr(expiry, "strftime"):
        expiry = expiry.strftime("%Y-%m-%d")
    body_en = (
        f"Your dealer license on file has expired. To continue bidding on licensed-only "
        f"vehicle auctions, please submit your renewed license.<br/><br/>"
        f"License #: <strong>{license_no}</strong><br/>"
        f"Expired on: <strong>{expiry}</strong>"
    )
    body_fr = (
        f"Votre permis de concessionnaire enregistré a expiré. Pour continuer à enchérir "
        f"sur les enchères réservées aux concessionnaires, veuillez soumettre votre permis renouvelé.<br/><br/>"
        f"N° de permis : <strong>{license_no}</strong><br/>"
        f"Expiré le : <strong>{expiry}</strong>"
    )
    return await _send_via_unified(
        to_email=user["email"],
        subject="⚠️ Dealer License Expired · Permis de concessionnaire expiré",
        html_content=_storage_panel(
            "Dealer License Expired", "Permis expiré",
            body_en, body_fr,
            cta_url="https://bidvex.com/vehicle-auctions/dealer-license",
            cta_en="Renew License",
            cta_fr="Renouveler le permis",
        ),
    )


async def send_listing_requires_action_email(
    recipient: dict,
    listing_title: str,
    listing_id: str,
    reason_code: str = "iter201_phase2_compliance_fields_required",
) -> bool:
    """
    iter201 — Phase 2 — Notify a seller that one of their pre-existing vehicle
    listings has been flagged `requires_seller_action` because new mandatory
    compliance fields (category, condition matrix, accident/lien/use, payment
    methods) need to be filled in before the listing can return to the
    public marketplace.
    """
    if not recipient or not recipient.get("email"):
        return False

    safe_title = (listing_title or "Untitled vehicle").strip().replace("<", "&lt;").replace(">", "&gt;")
    cta_url = f"https://bidvex.com/vehicle-auctions/edit/{listing_id}"

    body_en = (
        f"BidVex has updated its vehicle listing requirements to comply with provincial dealer regulations across Canada. "
        f"Your existing listing <strong>{safe_title}</strong> needs a few additional fields filled in before it can return to the public marketplace.<br/><br/>"
        f"<strong>What's needed (≈2 minutes):</strong>"
        f"<ul style='margin:8px 0 8px 20px;padding:0;'>"
        f"<li>Vehicle category (cars, SUVs, trucks, etc.)</li>"
        f"<li>Condition (Excellent / Good / Fair / Salvage / Parts)</li>"
        f"<li>Accident history, lien status, previous use</li>"
        f"<li>Payment methods accepted, deposit requirement</li>"
        f"</ul>"
        f"Until then, your listing has been hidden from public view but is preserved as a draft."
    )
    body_fr = (
        f"BidVex a mis à jour ses exigences de listing de véhicules pour se conformer aux règlements provinciaux des concessionnaires partout au Canada. "
        f"Votre annonce existante <strong>{safe_title}</strong> nécessite quelques champs supplémentaires avant de pouvoir réapparaître publiquement.<br/><br/>"
        f"<strong>Ce qu'il faut faire (≈2 minutes) :</strong>"
        f"<ul style='margin:8px 0 8px 20px;padding:0;'>"
        f"<li>Catégorie du véhicule (voitures, VUS, camionnettes, etc.)</li>"
        f"<li>État (Excellent / Bon / Moyen / Récupération / Pièces)</li>"
        f"<li>Historique d'accidents, privilèges, usage antérieur</li>"
        f"<li>Modes de paiement acceptés, exigence de dépôt</li>"
        f"</ul>"
        f"En attendant, votre annonce est masquée du public mais conservée en tant que brouillon."
    )

    return await _send_via_unified(
        to_email=recipient["email"],
        subject="🛠️ Action required: update your BidVex vehicle listing · Mise à jour requise",
        html_content=_storage_panel(
            "Action required on your vehicle listing",
            "Action requise sur votre annonce de véhicule",
            body_en, body_fr,
            cta_url=cta_url,
            cta_en="Update Listing",
            cta_fr="Mettre à jour l'annonce",
        ),
    )


async def send_buyer_verification_decision_email(
    recipient: dict,
    decision: str,            # "approve" | "reject"
    province: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    verification_type: Optional[str] = None,  # "dealer" | "dealer_representative"
) -> bool:
    """iter201 — Phase 3 / 3B — Bilingual buyer-verification decision email.

    Mirrors the polish of `send_dealer_license_approved_email` /
    `send_dealer_license_rejected_email`: structured body, regulator-aware
    province name, action-oriented CTA, masked status callouts.
    """
    if not recipient or not recipient.get("email"):
        return False
    province_code = (province or "your province").upper()
    province_label_en = {
        "ON": "Ontario", "NB": "New Brunswick", "NS": "Nova Scotia",
        "PE": "Prince Edward Island", "NL": "Newfoundland and Labrador",
        "BC": "British Columbia", "AB": "Alberta", "SK": "Saskatchewan",
        "MB": "Manitoba", "QC": "Quebec",
        "YT": "Yukon", "NT": "Northwest Territories", "NU": "Nunavut",
    }.get(province_code, province_code)
    province_label_fr = {
        "ON": "Ontario", "NB": "Nouveau-Brunswick", "NS": "Nouvelle-Écosse",
        "PE": "Île-du-Prince-Édouard", "NL": "Terre-Neuve-et-Labrador",
        "BC": "Colombie-Britannique", "AB": "Alberta", "SK": "Saskatchewan",
        "MB": "Manitoba", "QC": "Québec",
        "YT": "Yukon", "NT": "Territoires du Nord-Ouest", "NU": "Nunavut",
    }.get(province_code, province_code)
    type_label_en = "Dealer Representative" if verification_type == "dealer_representative" else "Licensed Dealer"
    type_label_fr = "Représentant de concessionnaire" if verification_type == "dealer_representative" else "Concessionnaire licencié"

    if decision == "approve":
        subject = "✅ Buyer Verification Approved · Vérification d'acheteur approuvée"
        body_en = (
            f"Your buyer verification for <strong>{province_label_en}</strong> has been approved. "
            f"You can now bid on dealer vehicle auctions in {province_label_en}.<br/><br/>"
            f"Verification type: <strong>{type_label_en}</strong><br/>"
            f"Status: <strong style='color:#059669;'>Approved</strong>"
        )
        body_fr = (
            f"Votre vérification d'acheteur pour <strong>{province_label_fr}</strong> a été approuvée. "
            f"Vous pouvez maintenant enchérir sur les enchères de véhicules de concessionnaires en {province_label_fr}.<br/><br/>"
            f"Type de vérification : <strong>{type_label_fr}</strong><br/>"
            f"Statut : <strong style='color:#059669;'>Approuvé</strong>"
        )
        cta_en, cta_fr = "Browse Vehicle Auctions", "Parcourir les enchères de véhicules"
        cta_url = "https://bidvex.com/vehicle-auctions"
        title_en, title_fr = "Buyer Verification Approved", "Vérification d'acheteur approuvée"
    else:
        reason = (rejection_reason or "").strip() or (
            "Documents could not be verified."
        )
        reason_fr = (rejection_reason or "").strip() or (
            "Les documents n'ont pas pu être vérifiés."
        )
        subject = "❌ Buyer Verification Update · Mise à jour de la vérification"
        body_en = (
            f"Your buyer-verification submission for <strong>{province_label_en}</strong> was reviewed "
            f"and unfortunately could not be approved at this time.<br/><br/>"
            f"Reason: <em>{reason}</em><br/><br/>"
            f"You may resubmit with updated documents at any time."
        )
        body_fr = (
            f"Votre demande de vérification d'acheteur pour <strong>{province_label_fr}</strong> a été examinée "
            f"et n'a malheureusement pas pu être approuvée pour le moment.<br/><br/>"
            f"Raison : <em>{reason_fr}</em><br/><br/>"
            f"Vous pouvez resoumettre avec des documents mis à jour à tout moment."
        )
        cta_en, cta_fr = "Resubmit Verification", "Resoumettre la vérification"
        cta_url = "https://bidvex.com/profile/verification"
        title_en, title_fr = "Buyer Verification Update", "Mise à jour de la vérification d'acheteur"

    return await _send_via_unified(
        to_email=recipient["email"],
        subject=subject,
        html_content=_storage_panel(
            title_en, title_fr,
            body_en, body_fr,
            cta_url=cta_url,
            cta_en=cta_en,
            cta_fr=cta_fr,
        ),
    )


async def send_dealer_license_expiring_email(recipient: dict, days_until_expiry: int) -> bool:
    """iter201 — Phase 3 / 3C — 30-day warning before dealer licence expires."""
    if not recipient or not recipient.get("email"):
        return False
    return await _send_via_unified(
        to_email=recipient["email"],
        subject=f"⚠️ Your dealer licence expires in {days_until_expiry} days — BidVex · Licence expire bientôt",
        html_content=_storage_panel(
            "Your dealer licence expires soon",
            "Votre licence de concessionnaire expire bientôt",
            f"Your provincial dealer licence will expire in <strong>{days_until_expiry} days</strong>. "
            f"To keep your vehicle listings active, please upload your renewed licence document before the expiry date.",
            f"Votre licence provinciale de concessionnaire expirera dans <strong>{days_until_expiry} jours</strong>. "
            f"Pour garder vos annonces actives, veuillez téléverser votre licence renouvelée avant la date d'expiration.",
            cta_url="https://bidvex.com/seller/dealer-license",
            cta_en="Upload Renewed Licence",
            cta_fr="Téléverser la licence renouvelée",
        ),
    )


async def send_seller_license_expired_email(recipient: dict, suspended_count: int = 0) -> bool:
    """iter201 — Phase 3 / 3C — Hard expiry: SELLER licence expired, listings suspended.

    Distinct from `send_dealer_license_expired_email` which targets buyers
    whose iter195 dealer-license-verification record expired.
    """
    if not recipient or not recipient.get("email"):
        return False
    return await _send_via_unified(
        to_email=recipient["email"],
        subject="🚫 Your dealer licence has expired — listings suspended · Licence expirée",
        html_content=_storage_panel(
            "Your dealer licence has expired",
            "Votre licence de concessionnaire a expiré",
            f"Your provincial dealer licence has expired. To comply with provincial regulations, "
            f"BidVex has suspended <strong>{suspended_count}</strong> of your active vehicle listings. "
            f"Upload your renewed licence to reactivate them.",
            f"Votre licence provinciale de concessionnaire a expiré. Conformément aux règlements provinciaux, "
            f"BidVex a suspendu <strong>{suspended_count}</strong> de vos annonces actives. "
            f"Téléversez votre licence renouvelée pour les réactiver.",
            cta_url="https://bidvex.com/seller/dealer-license",
            cta_en="Upload Renewed Licence",
            cta_fr="Téléverser la licence renouvelée",
        ),
    )




# ─────────────────────────────────────────────────────────────
# iter304 — "Email to a Friend" share email (Outlook-safe tables)
# ─────────────────────────────────────────────────────────────
async def send_vehicle_email_to_friend(
    recipient_email: str,
    sender_first_name: str,
    listing: dict,
    message: str = "",
    lang: str = "en",
) -> bool:
    """Bilingual share email — Outlook-safe (tables only, no flex/grid)."""
    if not SENDGRID_AVAILABLE:
        logger.warning("send_vehicle_email_to_friend skipped — SendGrid disabled")
        return False
    is_fr = (lang or "en").startswith("fr")
    listing_id = listing.get("id") or ""
    title = listing.get("title") or f"{listing.get('year','')} {listing.get('make','')} {listing.get('model','')}".strip()
    title_fr = listing.get("title_fr") or title
    display_title = title_fr if is_fr else title
    photo_url = ""
    media = listing.get("media") or []
    if media and isinstance(media, list):
        first = media[0]
        if isinstance(first, dict):
            photo_url = first.get("url") or ""
    if not photo_url:
        photos = listing.get("images") or []
        if photos and isinstance(photos, list):
            photo_url = (photos[0] if isinstance(photos[0], str) else photos[0].get("url", ""))
    current_bid = listing.get("current_bid") or listing.get("starting_price") or 0
    listing_url = f"{FRONTEND_URL}/vehicle-auctions/{listing_id}"

    if is_fr:
        subject = f"{sender_first_name} pense que ce véhicule sur BidVex pourrait vous intéresser"
        intro = f"<strong>{sender_first_name}</strong> vous a envoyé ce véhicule à découvrir sur BidVex&nbsp;:"
        bid_label = "Enchère actuelle"
        cta = "Voir l'annonce sur BidVex"
        footer = "Cette annonce est régie par les enchères BidVex Vehicle. Aucune obligation pour vous."
        msg_label = "Message :"
    else:
        subject = f"{sender_first_name} thought you'd be interested in this vehicle on BidVex"
        intro = f"<strong>{sender_first_name}</strong> sent you this vehicle on BidVex:"
        bid_label = "Current bid"
        cta = "View Listing on BidVex"
        footer = "This listing runs on BidVex Vehicle Auctions — no obligation to bid."
        msg_label = "Message:"

    photo_block = (
        f'<tr><td style="padding:0 0 18px 0;"><img src="{photo_url}" alt="" width="560" '
        f'style="display:block;max-width:100%;height:auto;border-radius:8px;border:0;"/></td></tr>'
    ) if photo_url else ""

    msg_block = (
        f'<tr><td style="padding:8px 0 16px 0;"><table role="presentation" width="100%" '
        f'style="background-color:#f1f5f9;border-left:4px solid #0ea5e9;border-radius:6px;">'
        f'<tr><td style="padding:12px 16px;font-family:Arial,sans-serif;font-size:14px;color:#334155;">'
        f'<strong style="color:#0f172a;">{msg_label}</strong><br/>'
        f'<span style="white-space:pre-wrap;">{message}</span>'
        f'</td></tr></table></td></tr>'
    ) if message else ""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/><title>{subject}</title></head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f8fafc;padding:20px 0;">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"
      style="background-color:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0;">
      <tr><td style="padding:24px 28px 8px 28px;font-family:Arial,sans-serif;color:#0f172a;font-size:15px;line-height:22px;">
        {intro}
      </td></tr>
      <tr><td style="padding:8px 28px 0 28px;font-family:Arial,sans-serif;color:#0f172a;font-size:18px;font-weight:bold;">
        {display_title}
      </td></tr>
      <tr><td style="padding:6px 28px 16px 28px;font-family:Arial,sans-serif;color:#475569;font-size:14px;">
        {bid_label}: <strong style="color:#0ea5e9;">${current_bid:,.0f} CAD</strong>
      </td></tr>
      <tr><td style="padding:0 28px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          {photo_block}
          {msg_block}
          <tr><td align="center" style="padding:14px 0 24px 0;">
            <a href="{listing_url}" style="display:inline-block;padding:12px 28px;background-color:#0ea5e9;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:600;font-family:Arial,sans-serif;font-size:14px;">{cta}</a>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:14px 28px 22px 28px;border-top:1px solid #e2e8f0;font-family:Arial,sans-serif;font-size:12px;color:#94a3b8;text-align:center;">
        {footer}
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

    res = await send_unified_email(
        "new_feature",
        user={"email": recipient_email, "first_name": ""},
        data={
            "html_full_override": html,
            "subject_override": subject,
        },
        is_marketing=False,
        categories=["share-to-friend", "vehicles"],
    )
    return bool(res and res.get("success"))

