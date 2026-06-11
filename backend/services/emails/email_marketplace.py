"""services/emails/email_marketplace.py — iter295 P2

Marketplace + lots + storage email senders. Function bodies
physically migrated from services/email_notifications.py."""
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


async def send_auction_sold_email(
    seller_email: str,
    seller_name: str,
    vehicle_title: str,
    final_price: float,
    commission: float,
    net_payout: float
) -> Dict[str, Any]:
    """Send email to seller when vehicle is sold"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🎉 Your Vehicle Sold!</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Congratulations {seller_name}!
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your vehicle has been successfully sold at auction:
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 25px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 18px; font-weight: bold;">
            {vehicle_title}
        </p></td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Sale Price:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_currency(final_price)}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>BidVex Commission:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #dc2626;">-{_format_currency(commission)}</td>
            </tr>
            <tr style="border-top: 2px solid #2563eb;">
                <td style="padding: 12px 0;"><strong>Your Payout:</strong></td>
                <td style="padding: 12px 0; text-align: right; font-size: 20px; color: #10b981; font-weight: bold;">
                    {_format_currency(net_payout)}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        Your payout will be processed once the buyer completes payment (typically within 14 days).
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/seller/financials" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Financials</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"🎉 Sold! {vehicle_title} - {_format_currency(final_price)}",
        html_content=_base_template(content, "Vehicle Sold")
    )


async def send_bid_placed_email(
    bidder_email: str,
    bidder_name: str,
    listing_title: str,
    bid_amount: float,
    listing_id: str,
    auction_end_date: str,
    is_leading: bool = True,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """iter239 Mission 6 — Refactored to route through `send_unified_email`.

    Original signature preserved for backward-compat. `auction_type` is still
    accepted but the unified BidVex template uses a single master layout.
    The bidding context (lead/outbid messaging) is surfaced via
    `secondary_info` rather than per-section custom HTML.
    """
    _ = auction_type  # legacy arg, retained for callers
    secondary = (
        "✓ You are currently the highest bidder. We'll notify you if someone outbids you."
        if is_leading else
        "Your bid has been recorded, but you're not currently leading the auction."
    )
    deadline_str = _format_date(auction_end_date) if auction_end_date else ""
    return await send_unified_email(
        "bid_placed",
        user={"email": bidder_email, "first_name": bidder_name},
        data={
            "bid_amount": f"{float(bid_amount):,.2f}",
            "listing_title": listing_title,
            "listing_id": listing_id,
            "secondary_info": f"{secondary}<br><strong>Auction ends:</strong> {deadline_str}" if deadline_str else secondary,
        },
    )


async def send_seller_bid_received_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    bid_amount: float,
    bidder_alias: str,
    auction_end_date: str,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Notify the seller that a new bid was placed on their listing.

    Uses a privacy-preserving alias for the bidder (not full name/email).
    """
    label = _section_label(auction_type)
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #0ea5e9;">🔔 New Bid on Your Listing / Nouvelle enchère sur votre annonce</h2>

    <p style="color: #475569; line-height: 1.6;">Hi {seller_name},</p>

    <p style="color: #475569; line-height: 1.6;">
        A new bid has just been placed on your {label['name_en']} listing.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #f0f9ff; border: 2px solid #0ea5e9; border-radius: 8px; padding: 25px;">
        <p style="margin: 0 0 12px 0; color: #0c4a6e; font-size: 18px; font-weight: bold;">{listing_title}</p>
        <table width="100%" style="font-size: 14px; color: #1e293b;">
          <tr><td style="padding: 6px 0;"><strong>New Bid:</strong></td>
              <td style="padding: 6px 0; text-align: right; font-size: 20px; color: #0ea5e9; font-weight: bold;">{_format_currency(bid_amount)}</td></tr>
          <tr><td style="padding: 6px 0;"><strong>Bidder:</strong></td>
              <td style="padding: 6px 0; text-align: right; color: #475569;">{bidder_alias}</td></tr>
          <tr><td style="padding: 6px 0;"><strong>Auction Ends:</strong></td>
              <td style="padding: 6px 0; text-align: right; color: #dc2626;">{_format_date(auction_end_date)}</td></tr>
        </table>
      </td></tr>
    </table>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #0ea5e9; padding: 14px 30px; border-radius: 8px;">
        <a href="{FRONTEND_URL}/listing/{listing_id}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">View Your Listing</a>
      </td></tr>
    </table>

    <hr style="border:0; border-top:1px solid #e2e8f0; margin: 24px 0;" />

    <p style="color: #475569; line-height: 1.6;">Bonjour {seller_name},</p>
    <p style="color: #475569; line-height: 1.6;">
        Une nouvelle enchère vient d'être placée sur votre annonce {label['name_fr']}.
        L'identifiant de l'enchérisseur est affiché sous forme d'alias pour protéger sa vie privée.
    </p>

    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        <strong>Tip:</strong> Log in to your seller dashboard to follow live bid activity.
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"🔔 New bid on your listing — {listing_title} | {label['name_en']}",
        html_content=_base_template(content, "New Bid Received", auction_type=auction_type),
    )


async def send_outbid_email(
    user_email: str,
    user_name: str,
    listing_title: str,
    their_bid: float,
    new_high_bid: float,
    listing_id: str,
    auction_end_date: str,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """iter239 Mission 6 — Refactored to route through `send_unified_email`.

    Signature preserved for backward compatibility. `auction_type` retained
    but the unified template uses a single master layout.
    """
    _ = auction_type  # legacy arg, retained
    suggested = new_high_bid + 1
    deadline_str = _format_date(auction_end_date) if auction_end_date else ""
    secondary = (
        f"Your bid: <strike>{_format_currency(their_bid)}</strike>"
        f"<br>Suggested next bid: <strong>{_format_currency(suggested)}</strong> or higher."
    )
    if deadline_str:
        secondary += f"<br><strong>Auction ends:</strong> {deadline_str}"
    return await send_unified_email(
        "outbid",
        user={"email": user_email, "first_name": user_name},
        data={
            "current_bid": f"{float(new_high_bid):,.2f}",
            "listing_title": listing_title,
            "listing_id": listing_id,
            "secondary_info": secondary,
        },
    )


async def send_auction_won_email(
    to_email: str = "",
    to_name: str = "",
    auction_id: str = "",
    item_name: str = "",
    hammer_price: float = 0.0,
    platform_fee: float = 0.0,
    seller_name: str = "",
    seller_contact: str = "",
    is_vehicle: bool = False,
    is_cross_border: bool = False,
    buyer_province: str = "QC",
    payment_deadline: Optional[str] = None,
    # --- Back-compat aliases (older callers) ---
    winner_email: Optional[str] = None,
    winner_name: Optional[str] = None,
    item_title: Optional[str] = None,
    final_price: Optional[float] = None,
    listing_id: Optional[str] = None,
    buyer_email: Optional[str] = None,
    buyer_name: Optional[str] = None,
    vehicle_title: Optional[str] = None,
    invoice_id: Optional[str] = None,
    buyers_premium_rate: Optional[float] = None,  # noqa: ARG001 — legacy, ignored
) -> Dict[str, Any]:
    """
    Send 'You Won!' email to auction winner.

    Legal-compliant behavior:
      - For vehicles (is_vehicle=True), injects a bilingual EN/FR notice that
        the hammer price is settled DIRECTLY between buyer and seller and that
        BidVex only charges the 2.5% platform fee + taxes.
      - For non-vehicles, shows the standard checkout CTA (BidVex collects full
        hammer via Stripe Connect).
      - For cross-border (is_cross_border=True), appends the cross-border
        compliance notice in both languages.
    """
    # Back-compat normalization
    to_email = to_email or winner_email or buyer_email or ""
    to_name = to_name or winner_name or buyer_name or ""
    item_name = item_name or item_title or vehicle_title or "Item"
    auction_id = auction_id or listing_id or invoice_id or ""
    if hammer_price in (None, 0.0) and final_price is not None:
        hammer_price = final_price

    checkout_url = f"{FRONTEND_URL}/checkout/{auction_id}"
    invoice_url = f"{FRONTEND_URL}/vehicle-auctions/invoices/{auction_id}"
    hammer_display = _format_currency(hammer_price)
    fee_display = _format_currency(platform_fee)
    # French Canadian currency: "10 000,00 $" — suffix style
    def _fr_currency(amount):
        s = f"{float(amount):,.2f}"  # 10,000.00
        return s.replace(",", " ").replace(".", ",") + " $"
    hammer_display_fr = _fr_currency(hammer_price)
    fee_display_fr = _fr_currency(platform_fee)
    deadline_display = _format_date(payment_deadline) if payment_deadline else "14 days"

    # ── Vehicle-specific payment notice (EN + FR) ──
    vehicle_notice = ""
    if is_vehicle:
        seller_contact_line = seller_contact or "Available in your BidVex dashboard"
        seller_display = seller_name or "Seller"
        vehicle_notice = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold; font-size: 15px;">
          ⚠️ VEHICLE PAYMENT NOTICE
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Payment for the vehicle (<strong>{hammer_display}</strong>) is arranged directly
          between you and the seller. BidVex does not process or hold vehicle purchase funds.
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          <strong>Seller Contact:</strong> {seller_display} | {seller_contact_line}
        </p>
        <p style="margin: 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          BidVex Platform Fee of 2.5% (<strong>{fee_display}</strong>) has been charged
          separately to your card on file. This is the only amount BidVex collects.
        </p>
      </td></tr>
    </table>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold; font-size: 15px;">
          ⚠️ AVIS DE PAIEMENT DU VÉHICULE
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Le paiement du véhicule (<strong>{hammer_display_fr}</strong>) est organisé
          directement entre vous et le vendeur. BidVex ne traite pas et ne détient pas
          les fonds d'achat de véhicules.
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          <strong>Contact du vendeur :</strong> {seller_display} | {seller_contact_line}
        </p>
        <p style="margin: 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Les frais de plateforme BidVex de 2,5 % (<strong>{fee_display_fr}</strong>) ont été
          débités séparément de votre carte enregistrée. C'est le seul montant que BidVex perçoit.
        </p>
      </td></tr>
    </table>
    """

    # ── Cross-border compliance notice (EN + FR) ──
    cross_border_notice = ""
    if is_cross_border:
        cross_border_notice = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #eff6ff; border-left: 4px solid #2563eb; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 8px 0; color: #1e40af; font-weight: bold; font-size: 14px;">
          🌐 Cross-Border Purchase Notice
        </p>
        <p style="margin: 0 0 8px 0; color: #1e293b; font-size: 13px; line-height: 1.6;">
          This purchase crosses provincial or international borders. You may be responsible
          for additional import duties, brokerage, GST/HST/QST on import, and compliance
          with your province's ({buyer_province}) vehicle registration rules.
        </p>
        <p style="margin: 0; color: #1e293b; font-size: 13px; line-height: 1.6;">
          Cet achat franchit des frontières provinciales ou internationales. Vous pourriez
          être responsable des droits d'importation, du courtage, de la TPS/TVH/TVQ à
          l'importation, et de la conformité aux règles d'immatriculation de votre
          province ({buyer_province}).
        </p>
      </td></tr>
    </table>
    """

    # ── CTA button ──
    cta_url = invoice_url if is_vehicle else checkout_url
    cta_label = "View Fee Invoice" if is_vehicle else "Complete Payment"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">Congratulations! You Won!</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {to_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        You've won the auction for <strong>{item_name}</strong>!
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #ecfdf5; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Item:</td>
                        <td style="color: #065f46; font-size: 14px; font-weight: bold; text-align: right;">{item_name}</td>
                    </tr>
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Winning Bid:</td>
                        <td style="color: #065f46; font-size: 24px; font-weight: bold; text-align: right;">{hammer_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Payment Due By:</td>
                        <td style="color: #dc2626; font-size: 14px; font-weight: bold; text-align: right;">{deadline_display}</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    {vehicle_notice}
    {cross_border_notice}

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{cta_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;" data-testid="auction-won-cta">{cta_label}</a>
            </td>
        </tr>
    </table>

    <p style="color: #94a3b8; font-size: 12px; text-align: center;">
        If the button doesn't work, copy this link: {cta_url}
    </p>
    """

    # iter249 Mission 3 — Language-aware subject (auction_won already
    # renders bilingual EN+FR bodies for vehicles; the subject now
    # follows the recipient's language preference too).
    _aw_lang = _detect_language(buyer_province)
    if _aw_lang == "fr":
        subject = (
            f"Vous avez gagné ! Véhicule {item_name} — Facture des frais prête"
            if is_vehicle
            else f"Vous avez gagné ! Effectuez le paiement pour {item_name}"
        )
    else:
        subject = (
            f"You Won! Vehicle {item_name} — Fee Invoice Ready"
            if is_vehicle
            else f"You Won! Complete Payment for {item_name}"
        )

    return await _send_via_unified(
        to_email=to_email,
        subject=subject,
        html_content=_base_template(content, "Auction Won")
    )


async def send_storage_bid_placed_email(buyer: dict, auction: dict, bid_state: dict) -> bool:
    """iter239 Mission 6 — Routes through `send_unified_email("bid_placed")`."""
    if not buyer or not buyer.get("email"):
        return False
    a_id = (auction or {}).get("id", "")
    cur = bid_state.get("current_bid", 0)
    winning = bid_state.get("you_are_winning")
    secondary = (
        "You are currently winning the auction."
        if winning else
        "You are NOT currently winning — your maximum was outbid."
    )
    result = await send_unified_email(
        "bid_placed",
        user={"email": buyer["email"], "first_name": buyer.get("name") or buyer.get("full_name") or ""},
        data={
            "bid_amount": f"{float(cur):,.2f}",
            "listing_title": f"Storage Unit Auction #{a_id[:8]}",
            "listing_id": a_id,
            "secondary_info": secondary,
        },
    )
    return result.get("status") in ("sent", "logged")


async def send_storage_outbid_email(buyer: dict, auction: dict, new_current: float) -> bool:
    """iter239 Mission 6 — Routes through `send_unified_email("outbid")`."""
    if not buyer or not buyer.get("email"):
        return False
    a_id = (auction or {}).get("id", "")
    result = await send_unified_email(
        "outbid",
        user={"email": buyer["email"], "first_name": buyer.get("name") or buyer.get("full_name") or ""},
        data={
            "current_bid": f"{float(new_current):,.2f}",
            "listing_title": f"Storage Unit Auction #{a_id[:8]}",
            "listing_id": a_id,
            "secondary_info": "Place a higher max bid to retake the lead.",
        },
    )
    return result.get("status") in ("sent", "logged")


async def send_storage_auction_won_email(buyer: dict, auction: dict, facility: dict, pricing: dict = None) -> bool:
    """
    Bilingual winner email. Branches on auction.payment_method:
      • stripe   → BidVex charged buyer card (5% + stripe + tax); buyer pays hammer via Stripe to facility
      • cash     → buyer pays hammer CASH directly to facility
      • etransfer→ buyer sends Interac e-Transfer to facility's registered email

    Always includes a cleanup-deadline warning with forfeit clause.
    """
    if not buyer or not buyer.get("email"):
        return False

    unit = auction.get("unit_number", "—")
    bid = float(auction.get("winning_bid") or auction.get("current_bid") or 0)
    pm = (auction.get("payment_method") or "stripe").lower()
    fac_name = facility.get("company_name", "—")
    fac_contact = facility.get("contact_name", "—")
    fac_phone = facility.get("phone", "—")
    fac_email = facility.get("email", "—")
    pay_deadline = auction.get("payment_deadline") or auction.get("cleanup_deadline", "—")
    cleanup_deadline = auction.get("cleanup_deadline", "—")
    cleanup_deposit = float(auction.get("cleanup_deposit", 0) or 0)
    buyer_name = buyer.get("name") or buyer.get("full_name") or "—"

    # Optional BidVex charge (for Stripe path only)
    buyer_stripe_charge = 0.0
    if pricing and pricing.get("buyer_invoice"):
        # stripe path: platform_fee + stripe_recovery + tax (BidVex-collected portion)
        bi = pricing["buyer_invoice"]
        buyer_stripe_charge = float(bi.get("platform_fee", 0)) + float(bi.get("stripe_recovery", 0)) + float(bi.get("tax", 0))

    # ── Per-method body ──
    if pm == "stripe":
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong>.<br/>"
            f"Your winning bid: <strong>${bid:,.2f}</strong><br/><br/>"
            f"BidVex has charged your card <strong>${buyer_stripe_charge:,.2f}</strong> (platform fee + Stripe + taxes).<br/>"
            f"You must pay <strong>${bid:,.2f}</strong> to the facility via Stripe before <strong>{pay_deadline}</strong>.<br/><br/>"
            f"<strong>Facility contact:</strong> {fac_contact} | {fac_phone} | {fac_email}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong>.<br/>"
            f"Votre offre gagnante : <strong>{bid:,.2f} $</strong><br/><br/>"
            f"BidVex a débité <strong>{buyer_stripe_charge:,.2f} $</strong> sur votre carte (frais de plateforme + Stripe + taxes).<br/>"
            f"Vous devez payer <strong>{bid:,.2f} $</strong> à la facilité via Stripe avant le <strong>{pay_deadline}</strong>.<br/><br/>"
            f"<strong>Contact facilité :</strong> {fac_contact} | {fac_phone} | {fac_email}<br/>"
        )
    elif pm == "cash":
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong> for "
            f"<strong>${bid:,.2f}</strong>.<br/><br/>"
            f"You must pay <strong>${bid:,.2f} CASH</strong> directly to the facility.<br/>"
            f"Contact the facility to arrange payment and pickup:<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone} | {fac_email}<br/>"
            f"<strong>Payment deadline:</strong> {pay_deadline}<br/>"
            f"<strong>Cleanup deadline:</strong> {cleanup_deadline}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong> pour "
            f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
            f"Vous devez payer <strong>{bid:,.2f} $ COMPTANT</strong> directement à la facilité.<br/>"
            f"Contactez la facilité pour organiser le paiement et le ramassage :<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone} | {fac_email}<br/>"
            f"<strong>Date limite de paiement :</strong> {pay_deadline}<br/>"
            f"<strong>Date limite de nettoyage :</strong> {cleanup_deadline}<br/>"
        )
    else:  # etransfer
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong> for "
            f"<strong>${bid:,.2f}</strong>.<br/><br/>"
            f"Send <strong>${bid:,.2f}</strong> via <strong>Interac e-Transfer</strong> to: <strong>{fac_email}</strong><br/>"
            f"<strong>Reference:</strong> BidVex Unit #{unit} — {buyer_name}<br/>"
            f"Contact the facility to confirm receipt:<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone}<br/>"
            f"<strong>Payment deadline:</strong> {pay_deadline}<br/>"
            f"<strong>Cleanup deadline:</strong> {cleanup_deadline}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong> pour "
            f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
            f"Envoyez <strong>{bid:,.2f} $</strong> par <strong>virement Interac</strong> à : <strong>{fac_email}</strong><br/>"
            f"<strong>Référence :</strong> BidVex Unité #{unit} — {buyer_name}<br/>"
            f"Contactez la facilité pour confirmer la réception :<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone}<br/>"
            f"<strong>Date limite de paiement :</strong> {pay_deadline}<br/>"
            f"<strong>Date limite de nettoyage :</strong> {cleanup_deadline}<br/>"
        )

    # ── Cleanup / forfeit notice (always appended, bilingual) ──
    pickup_code = auction.get("pickup_code")
    pickup_en = ""
    pickup_fr = ""
    if pickup_code:
        # Generate inline base64 QR image so it renders in every email client
        qr_img_tag = ""
        try:
            import base64 as _b64
            from routes.storage_auctions import _generate_pickup_qr_png_bytes
            qr_bytes = _generate_pickup_qr_png_bytes(pickup_code)
            qr_b64 = _b64.b64encode(qr_bytes).decode("ascii")
            qr_img_tag = (
                f"<table role='presentation' cellpadding='0' cellspacing='0' border='0' align='center' style='margin:12px auto;'>"
                f"<tr><td bgcolor='#FFFFFF' style='background-color:#FFFFFF;"
                f"padding:12px;border-radius:8px;border:2px solid #fde68a'>"
                f"<img src='data:image/png;base64,{qr_b64}' alt='Scan for pickup verification / Scanner pour vérification de ramassage' "
                f"width='180' height='180' "
                f"style='display:block;width:180px;height:180px;image-rendering:pixelated;background:#FFFFFF'/>"
                f"</td></tr></table>"
            )
        except Exception as e:
            logger.error(f"[STORAGE_EMAIL] QR embed failed: {e}")

        pickup_en = (
            f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
            f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0' style='margin:12px 0'>"
            f"<tr><td bgcolor='#fef3c7' align='center' style='background-color:#fef3c7;border:2px dashed #d97706;border-radius:10px;padding:16px'>"
            f"<p style='margin:0;font-size:11px;letter-spacing:2px;color:#92400e;font-weight:700'>YOUR PICKUP CODE</p>"
            f"<p style='margin:6px 0 0 0;font-size:28px;font-weight:900;color:#78350f;letter-spacing:3px;font-family:monospace'>{pickup_code}</p>"
            f"{qr_img_tag}"
            f"<p style='margin:4px 0 0 0;font-size:11px;color:#92400e'>Scan at pickup · Show code to staff</p>"
            f"</td></tr></table>"
            f"Present this code (or the QR) to facility staff when you arrive for pickup. "
            f"The facility will mark this code as used upon verification. "
            f"<strong>Do not share this code</strong> — it authorizes access to the unit."
        )
        pickup_fr = (
            f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
            f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0' style='margin:12px 0'>"
            f"<tr><td bgcolor='#fef3c7' align='center' style='background-color:#fef3c7;border:2px dashed #d97706;border-radius:10px;padding:16px'>"
            f"<p style='margin:0;font-size:11px;letter-spacing:2px;color:#92400e;font-weight:700'>VOTRE CODE DE RÉCUPÉRATION</p>"
            f"<p style='margin:6px 0 0 0;font-size:28px;font-weight:900;color:#78350f;letter-spacing:3px;font-family:monospace'>{pickup_code}</p>"
            f"{qr_img_tag}"
            f"<p style='margin:4px 0 0 0;font-size:11px;color:#92400e'>Scanner à la récupération · Présentez le code</p>"
            f"</td></tr></table>"
            f"Présentez ce code (ou le QR) au personnel de la facilité lors de votre arrivée. "
            f"La facilité marquera ce code comme utilisé après vérification. "
            f"<strong>Ne partagez pas ce code</strong> — il autorise l'accès à l'unité."
        )

    cleanup_en = (
        f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
        f"⚠️ <strong>IMPORTANT:</strong> You must completely empty the unit by "
        f"<strong>{cleanup_deadline}</strong>. Failure to empty the unit forfeits your "
        f"cleaning deposit of <strong>${cleanup_deposit:.2f}</strong> and will result in "
        f"account suspension.<br/>"
        f"Cleaning deposit: <strong>${cleanup_deposit:.2f}</strong> (refunded after the unit is confirmed empty)."
    )
    cleanup_fr = (
        f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
        f"⚠️ <strong>IMPORTANT :</strong> Vous devez vider complètement l'unité avant "
        f"<strong>{cleanup_deadline}</strong>. Le non-respect de cette date limite entraîne la "
        f"perte de votre dépôt de nettoyage de <strong>{cleanup_deposit:.2f} $</strong> et la "
        f"suspension de votre compte.<br/>"
        f"Dépôt de nettoyage : <strong>{cleanup_deposit:.2f} $</strong> (remboursé après confirmation que l'unité est vide)."
    )

    return bool(await _send_via_unified(
        to_email=buyer["email"],
        subject=f"🎉 You won — Storage Auction Unit #{unit}",
        html_content=_storage_panel(
            "You won the auction",
            "Vous avez gagné l'enchère",
            body_en + pickup_en + cleanup_en,
            body_fr + pickup_fr + cleanup_fr,
            cta_url=f"https://www.bidvex.com/storage-auctions/{auction.get('id','')}",
            cta_en="View auction",
            cta_fr="Voir l'enchère",
        ),
    ))


async def send_storage_auction_sold_email(facility: dict, auction: dict, buyer: dict) -> bool:
    """Bilingual notification to the facility when their unit sells."""
    if not facility or not facility.get("email"):
        return False
    a_id = auction.get("id", "")[:8]
    unit = auction.get("unit_number", "—")
    bid = float(auction.get("winning_bid") or auction.get("current_bid") or 0)
    pm = (auction.get("payment_method") or "stripe").lower()
    pm_label_en = {"stripe": "Stripe (online)", "cash": "Cash", "etransfer": "Interac e-Transfer"}.get(pm, pm)
    pm_label_fr = {"stripe": "Stripe (en ligne)", "cash": "Comptant", "etransfer": "Virement Interac"}.get(pm, pm)

    buyer_name = buyer.get("name") or buyer.get("full_name") or "—"
    buyer_email = buyer.get("email", "—")
    buyer_phone = buyer.get("phone", "—")

    body_en = (
        f"Storage auction for Unit <strong>#{unit}</strong> (#{a_id}) sold for "
        f"<strong>${bid:,.2f}</strong>.<br/><br/>"
        f"<strong>Payment method:</strong> {pm_label_en}<br/>"
        f"<strong>Winning bidder:</strong> {buyer_name} &lt;{buyer_email}&gt;<br/>"
        f"<strong>Phone:</strong> {buyer_phone}<br/><br/>"
        f"Contact the winner to coordinate payment and pickup. "
        f"Your BidVex commission invoice (5% + Stripe + applicable tax) will arrive separately."
    )
    body_fr = (
        f"L'enchère pour l'unité <strong>#{unit}</strong> (#{a_id}) a été vendue pour "
        f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
        f"<strong>Mode de paiement :</strong> {pm_label_fr}<br/>"
        f"<strong>Enchérisseur gagnant :</strong> {buyer_name} &lt;{buyer_email}&gt;<br/>"
        f"<strong>Téléphone :</strong> {buyer_phone}<br/><br/>"
        f"Contactez le gagnant pour organiser le paiement et le ramassage. "
        f"Votre facture de commission BidVex (5 % + Stripe + taxes applicables) suivra séparément."
    )
    return bool(await _send_via_unified(
        to_email=facility["email"],
        subject=f"✅ Sold — Storage Auction Unit #{unit}",
        html_content=_storage_panel("Auction sold", "Enchère vendue", body_en, body_fr),
    ))


async def send_storage_ending_soon_email(buyer: dict, auction: dict) -> bool:
    """iter239 Mission 6 — Routes through `send_unified_email("auction_ending_soon")`."""
    if not buyer or not buyer.get("email"):
        return False
    a_id = auction.get("id", "")
    result = await send_unified_email(
        "auction_ending_soon",
        user={"email": buyer["email"], "first_name": buyer.get("name") or buyer.get("full_name") or ""},
        data={
            "listing_title": f"Storage Unit Auction #{a_id[:8]}",
            "listing_id": a_id,
            "time_remaining": "under 1 hour",
            "current_bid": f"{float(auction.get('current_bid', 0)):,.2f}",
            "secondary_info": "Place your final max bid now to stay in the lead.",
        },
    )
    return result.get("status") in ("sent", "logged")


async def send_storage_facility_approved_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        f"Welcome to BidVex Storage Auctions, <strong>{facility.get('company_name','')}</strong>! "
        f"Your facility has been verified. You can now log in and create your first storage unit auction. "
        f"BidVex charges a flat 5% commission on each successful sale — buyers pay no platform fee."
    )
    body_fr = (
        f"Bienvenue chez BidVex Enchères d'entreposage, <strong>{facility.get('company_name','')}</strong>! "
        f"Votre facilité a été vérifiée. Vous pouvez maintenant vous connecter et créer votre première enchère. "
        f"BidVex facture une commission fixe de 5% sur chaque vente réussie — les acheteurs ne paient aucun frais de plateforme."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="✅ Your BidVex Storage Facility account is approved",
        html_content=_storage_panel("Facility approved", "Facilité approuvée", body_en, body_fr,
                                    cta_url="https://www.bidvex.com/storage-dashboard",
                                    cta_en="Open dashboard", cta_fr="Ouvrir le tableau de bord"),
    )


async def send_storage_seller_commission_invoice(facility: dict, auction: dict, pricing: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    s = pricing["seller_invoice"]
    a_id = auction.get("id", "")[:8]
    body_en = (
        f"BidVex commission invoice for storage auction <strong>#{a_id}</strong>:<br/>"
        f"• Commission (5%): <strong>${s['commission']:.2f}</strong><br/>"
        f"• Stripe processing: ${s['stripe_recovery']:.2f}<br/>"
        f"• Tax — {s['tax_label']}: ${s['tax']:.2f}<br/>"
        f"<strong>Total due to BidVex: ${s['total']:.2f}</strong>"
    )
    body_fr = (
        f"Facture de commission BidVex pour l'enchère <strong>#{a_id}</strong> :<br/>"
        f"• Commission (5 %) : <strong>{s['commission']:.2f} $</strong><br/>"
        f"• Frais Stripe : {s['stripe_recovery']:.2f} $<br/>"
        f"• Taxe — {s['tax_label']} : {s['tax']:.2f} $<br/>"
        f"<strong>Total dû à BidVex : {s['total']:.2f} $</strong>"
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject=f"BidVex Commission Invoice — Storage Auction #{a_id}",
        html_content=_storage_panel("Commission invoice", "Facture de commission", body_en, body_fr),
    )


async def send_storage_facility_registration_admin_alert(facility: dict) -> bool:
    admin_email = (
        _os.environ.get("ADMIN_NOTIFICATION_EMAIL")
        or _os.environ.get("ADMIN_EMAIL")
        or "charbel911@gmail.com"
    )
    body_en = (
        f"New storage facility registration awaiting verification:<br/>"
        f"<strong>{facility.get('company_name','—')}</strong><br/>"
        f"Contact: {facility.get('contact_name','—')} &lt;{facility.get('email','—')}&gt;<br/>"
        f"Phone: {facility.get('phone','—')}<br/>"
        f"Location: {facility.get('city','—')}, {facility.get('province','')}<br/>"
        f"Units available: {facility.get('units_available',0)}"
    )
    body_fr = "Nouvelle facilité d'entreposage en attente de vérification."
    return await _send_via_unified(
        to_email=admin_email,
        subject=f"[Storage Facility] New registration — {facility.get('company_name','')}",
        html_content=_storage_panel("New facility registration", "Nouvelle facilité", body_en, body_fr,
                                    cta_url="https://www.bidvex.com/admin", cta_en="Review", cta_fr="Examiner"),
    )


async def send_storage_facility_pending_user_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        "Thanks for registering your storage facility with BidVex! Your application "
        "is under review by our team. You'll receive a confirmation email within "
        "1–2 business days once your account is verified."
    )
    body_fr = (
        "Merci d'avoir inscrit votre facilité d'entreposage chez BidVex! Votre demande "
        "est en cours d'examen par notre équipe. Vous recevrez un courriel de confirmation "
        "dans 1 à 2 jours ouvrables une fois votre compte vérifié."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="Application received — BidVex Storage Auctions",
        html_content=_storage_panel("Application received", "Demande reçue", body_en, body_fr),
    )


async def send_buyer_pickup_code_email(
    *, buyer: dict, seller: dict, listing_title: str, hammer_price: float,
    pickup_code: str, payment_method: str, transaction_id: str,
) -> bool:
    if not buyer or not buyer.get("email") or not pickup_code:
        return False
    method_label_en = "Interac e-Transfer" if payment_method == "etransfer" else "Cash"
    method_label_fr = "Virement Interac" if payment_method == "etransfer" else "Comptant"
    seller_name = (seller or {}).get("name") or "the seller"
    seller_contact = (seller or {}).get("email") or (seller or {}).get("phone") or "—"
    html = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f8fafc;">
      <tr><td align="center" style="padding:20px;">
        <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;font-family:Arial,sans-serif;">
          <tr><td style="padding:24px;">
        <h2 style="color:#1e40af;margin:0 0 8px;">🎉 Congratulations — you won an auction!</h2>
        <p style="color:#475569;margin:0 0 12px;">Item: <strong>{listing_title}</strong> · Final bid: <strong>CA${hammer_price:,.2f}</strong></p>
        <p style="color:#475569;margin:0 0 16px;">Payment method: <strong>{method_label_en}</strong> — pay <strong>{seller_name}</strong> directly ({seller_contact}).</p>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:16px 0;">
          <tr><td bgcolor="#fffbeb" align="center" style="background-color:#fffbeb;border:2px solid #f59e0b;border-radius:12px;padding:18px;">
            <p style="margin:0;color:#92400e;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;font-weight:bold;">🔑 Pickup Code / Code de collecte</p>
            <p style="margin:8px 0 4px;font-size:28px;font-weight:bold;color:#1e3a8a;letter-spacing:0.15em;font-family:'Courier New',monospace;">{pickup_code}</p>
            <p style="margin:0;color:#92400e;font-size:11px;">Transaction #{transaction_id[:8]}</p>
          </td></tr>
        </table>

        <p style="color:#334155;line-height:1.6;font-size:13px;">
          <strong>EN:</strong> Share this code with the seller <strong>ONLY after</strong> you have completed your payment.
          The seller must enter this code on BidVex to confirm receipt of payment and release your funds.
          Do <strong>NOT</strong> share before payment.
        </p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:14px 0;">
        <p style="color:#334155;line-height:1.6;font-size:13px;">
          <strong>FR :</strong> Partagez ce code avec le vendeur <strong>UNIQUEMENT après</strong> avoir effectué votre paiement.
          Le vendeur doit saisir ce code sur BidVex pour confirmer la réception du paiement et libérer les fonds.
          <strong>NE PARTAGEZ PAS</strong> ce code avant le paiement.
        </p>

        <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:24px;">
          BidVex Inc. · GST# 706766367RT0001 · QST# 1233530880TQ0001 · All amounts in CAD<br>
          ({method_label_fr} — Montants en CAD)
        </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    return await _send_via_unified(
        to_email=buyer["email"],
        subject=f"🔑 Your pickup code · Votre code de collecte — {pickup_code}",
        html_content=html,
    )


async def send_seller_pickup_instructions_email(
    *, seller: dict, listing_title: str, hammer_price: float,
    payment_method: str, transaction_id: str,
) -> bool:
    if not seller or not seller.get("email"):
        return False
    method_label_en = "Interac e-Transfer" if payment_method == "etransfer" else "Cash"
    method_label_fr = "Virement Interac" if payment_method == "etransfer" else "Comptant"
    html = f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f8fafc;">
      <tr><td align="center" style="padding:20px;">
        <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;font-family:Arial,sans-serif;">
          <tr><td style="padding:24px;">
        <h2 style="color:#16a34a;margin:0 0 8px;">✅ Your item has sold!</h2>
        <p style="color:#475569;margin:0 0 12px;">Item: <strong>{listing_title}</strong> · Sold for: <strong>CA${hammer_price:,.2f}</strong></p>
        <p style="color:#475569;margin:0 0 16px;">Payment method chosen by the buyer: <strong>{method_label_en}</strong>.</p>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:16px 0;">
          <tr><td bgcolor="#ecfdf5" style="background-color:#ecfdf5;border:2px solid #16a34a;border-radius:12px;padding:18px;">
            <p style="margin:0 0 8px;color:#166534;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;font-weight:bold;">🔑 How to release your funds / Libération des fonds</p>
            <p style="color:#334155;line-height:1.6;font-size:13px;margin:0 0 10px;">
              <strong>EN:</strong> Once you have received payment from the buyer, ask them for their <strong>Pickup Code</strong>
              (format <code>BVX-XXXXXXXX</code>) and enter it at
              <a href="https://www.bidvex.com/confirm-payment">bidvex.com/confirm-payment</a>.
              This confirms payment received and completes the transaction on BidVex.
              Your funds will be marked as settled.
            </p>
            <p style="color:#334155;line-height:1.6;font-size:13px;margin:0;">
              <strong>FR :</strong> Une fois le paiement reçu, demandez le <strong>Code de collecte</strong> à l'acheteur
              et saisissez-le sur
              <a href="https://www.bidvex.com/confirmer-paiement">bidvex.com/confirmer-paiement</a>.
              Cela confirme la réception et complète la transaction.
            </p>
          </td></tr>
        </table>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td bgcolor="#fef3c7" style="background-color:#fef3c7;padding:12px;border-radius:6px;color:#92400e;font-size:12px;">
            ⚠️ The BidVex commission will be charged to your card on file within 24 hours of pickup-code confirmation.<br>
            La commission BidVex sera prélevée sur votre carte enregistrée dans les 24 heures.
          </td></tr>
        </table>

        <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:24px;">
          BidVex Inc. · GST# 706766367RT0001 · QST# 1233530880TQ0001 · Tx #{transaction_id[:8]}<br>
          ({method_label_fr})
        </p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject="✅ Item sold — pickup-code instructions · Article vendu — Instructions",
        html_content=html,
    )


async def send_storage_facility_registration_verified_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        f"Good news, <strong>{facility.get('company_name','')}</strong>! "
        f"Your business-registration document has been verified by BidVex. "
        f"As soon as your overall facility status is approved, you'll be able to list storage units."
    )
    body_fr = (
        f"Bonne nouvelle, <strong>{facility.get('company_name','')}</strong>! "
        f"Votre document d'enregistrement d'entreprise a été vérifié par BidVex. "
        f"Dès que le statut global de votre facilité sera approuvé, vous pourrez lister des unités."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="✅ Business registration verified — BidVex Storage Auctions",
        html_content=_storage_panel(
            "Registration verified", "Enregistrement vérifié",
            body_en, body_fr,
            cta_url="https://www.bidvex.com/storage-dashboard",
            cta_en="Open dashboard", cta_fr="Ouvrir le tableau de bord",
        ),
    )


async def send_storage_facility_registration_rejected_email(facility: dict, reason: str) -> bool:
    if not facility or not facility.get("email"):
        return False
    safe_reason = (reason or "").strip() or "Document did not meet our verification requirements."
    body_en = (
        f"Hi <strong>{facility.get('company_name','')}</strong>,<br/><br/>"
        f"Your business-registration document was <strong>not accepted</strong> by our verification team.<br/><br/>"
        f"<strong>Reason from BidVex:</strong> {safe_reason}<br/><br/>"
        f"Please return to your registration page, upload a corrected document, "
        f"and resubmit. We'll review the new document within 1–2 business days."
    )
    body_fr = (
        f"Bonjour <strong>{facility.get('company_name','')}</strong>,<br/><br/>"
        f"Votre document d'enregistrement d'entreprise <strong>n'a pas été accepté</strong> par notre équipe de vérification.<br/><br/>"
        f"<strong>Motif de BidVex :</strong> {safe_reason}<br/><br/>"
        f"Veuillez retourner à votre page d'inscription, téléverser un document corrigé "
        f"et le soumettre à nouveau. Nous examinerons le nouveau document sous 1 à 2 jours ouvrables."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="⚠️ Action required — Business registration not accepted",
        html_content=_storage_panel(
            "Registration not accepted", "Enregistrement non accepté",
            body_en, body_fr,
            cta_url="https://www.bidvex.com/storage-auctions/register-facility?resubmit=1",
            cta_en="Resubmit document", cta_fr="Soumettre à nouveau",
        ),
    )



# ═══════════════════════════════════════════════════════════════════
# iter299 P1 — "Last Chance" 1-hour nudge (watchers + trailing bidders)
# ═══════════════════════════════════════════════════════════════════

async def send_last_chance_email(
    user: dict, listing_title: str, listing_id: str, action_url: str,
) -> Dict[str, Any]:
    """⏰ Sent when an auction the user watches (or bid on without
    leading) ends within the next hour. Single-language per the user's
    platform setting. Table-only layout (Outlook-safe)."""
    lang = _detect_language(user)
    link = f"{FRONTEND_URL}{action_url}"

    if lang == "fr":
        subject = f"⏰ Dernière chance — {listing_title} se termine dans moins d'une heure"
        heading = "Derni&egrave;re chance de miser&nbsp;!"
        body = (f"L'ench&egrave;re pour <strong>{listing_title}</strong> se termine dans "
                f"<strong>moins d'une heure</strong>. C'est votre derni&egrave;re chance de placer une mise.")
        cta = "Miser maintenant"
    else:
        subject = f"⏰ Last Chance — {listing_title} ends in under 1 hour"
        heading = "Last chance to bid!"
        body = (f"The auction for <strong>{listing_title}</strong> ends in "
                f"<strong>under 1 hour</strong>. This is your last chance to place a bid.")
        cta = "Bid Now"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #d97706;">{heading}</h2>
    <p style="color: #475569; line-height: 1.6;">{body}</p>
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #2B8FD0; padding: 14px 30px; border-radius: 8px;">
        <a href="{link}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">{cta}</a>
      </td></tr>
    </table>
    <p style="color: #94a3b8; font-size: 12px; text-align: center;">BidVex — {listing_id}</p>
    """
    return await _send_via_unified(
        to_email=user["email"],
        subject=subject,
        html_content=_base_template(content, heading),
    )

