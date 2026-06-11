"""
BidVex — Listings Service Layer
Extracted from routes/listings.py (Phase 5 refactor).
Contains shared validation, creation, and query logic for both single-item
and multi-item auction listings.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from fastapi import HTTPException
from deps import User
import logging
import uuid

logger = logging.getLogger(__name__)


# ─── Shared Validation ───────────────────────────────────────────────

async def validate_seller(db, current_user: User, agreement_accepted: bool):
    """
    Run all gatekeeping checks before a seller can create a listing.
    Raises HTTPException on failure; returns agreement_metadata on success.
    """
    is_admin = (getattr(current_user, "role", "") or "").lower() in ("admin", "superadmin")
    # iter223 — Demo accounts bypass all seller gatekeeping (partner fee,
    # phone verification, payment method on file). Their listings get
    # `is_demo_sandbox=true` server-side and are invisible to the public
    # marketplace, so the friction of these prereqs would only block the
    # demo experience without any business value.
    is_demo = bool(getattr(current_user, "is_demo_account", False))
    if not is_demo:
        # Some User models don't expose `is_demo_account` directly; fall
        # back to a fresh DB lookup so we never falsely demo-bypass.
        try:
            udoc = await db.users.find_one(
                {"id": current_user.id},
                {"_id": 0, "is_demo_account": 1},
            )
            is_demo = bool(udoc and udoc.get("is_demo_account"))
        except Exception:
            is_demo = False
    # Phase 6.0 hotfix — Admins skip the agreement_accepted check; their
    # role binds them organisationally and they may create listings on
    # behalf of facilities, sellers, or dealers.
    if not agreement_accepted and not is_admin and not is_demo:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "agreement_required",
                "msg": "You must accept the binding agreement to sell before creating a listing. "
                       "This agreement certifies you are the legal owner and will honor the winning bid.",
                "field": "agreement_accepted"
            }
        )

    if not is_admin and not is_demo:
        if current_user.is_partner and not current_user.platform_fee_paid:
            raise HTTPException(
                status_code=403,
                detail="Your annual partner fee is required to create listings. "
                       "Please complete your payment to activate your account."
            )
        if not current_user.phone_verified:
            raise HTTPException(
                status_code=403,
                detail="Phone verification required. Please verify your phone number before creating listings."
            )
        payment_methods = await db.payment_methods.count_documents({"user_id": current_user.id})
        if payment_methods == 0:
            raise HTTPException(
                status_code=403,
                detail="Payment method required. Please add a payment card before creating listings."
            )


def build_agreement_metadata(current_user: User, client_ip: str, user_agent: str) -> Dict[str, Any]:
    """Construct the legally-binding agreement metadata stamp."""
    return {
        "accepted": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": client_ip,
        "user_agent": user_agent,
        "user_id": current_user.id,
        "user_email": current_user.email,
    }


# ─── Single-Item Creation ────────────────────────────────────────────

async def apply_partner_tags(db, current_user: User, listing_dict: Dict, buyers_premium_rate):
    """
    Stamp listing with seller-type pricing context, partner flags, BP rate, and
    geo-sort coordinates copied from the seller user document.

    Validates that partner sellers must have a `partner_bp_rate` configured
    BEFORE creating a listing — required by the pricing engine.
    """
    from models.user_models import resolve_seller_type, SELLER_TYPE_PARTNER
    seller_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0}) or {}

    # iter211 — Manual-commission safety gate: block new listings when a user
    # has unpaid manual commissions above the threshold. Admins must settle
    # those rows in the Pending Commissions panel before the user can post again.
    from services.manual_settlement_service import user_is_blocked_by_outstanding_commission
    gate = await user_is_blocked_by_outstanding_commission(db, current_user.id)
    if gate["blocked"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "outstanding_manual_commission",
                "outstanding_cad": gate["outstanding_cad"],
                "threshold_cad": gate["threshold_cad"],
                "message_en": (
                    f"You have ${gate['outstanding_cad']:.2f} CAD in unpaid manual commissions. "
                    f"Please contact BidVex (partners@bidvex.ca) to settle the balance "
                    f"before posting new listings."
                ),
                "message_fr": (
                    f"Vous avez {gate['outstanding_cad']:.2f} $ CAD de commissions manuelles "
                    f"impayées. Veuillez contacter BidVex (partners@bidvex.ca) pour régler "
                    f"le solde avant de publier de nouvelles annonces."
                ),
            },
        )

    # ── Canonical seller_type (drives pricing engine + UI badge) ──
    seller_type = resolve_seller_type(seller_doc)
    listing_dict["seller_type"] = seller_type

    # ── Partner-specific BP rate (validated below) ──
    partner_bp_rate = seller_doc.get("partner_bp_rate")
    if seller_type == SELLER_TYPE_PARTNER:
        # iter223 — Demo accounts get an auto-assigned BP rate (5.0%) so the
        # partner gate doesn't block the sandbox creation flow.
        if partner_bp_rate is None and seller_doc.get("is_demo_account"):
            partner_bp_rate = 0.05
        if partner_bp_rate is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "partner_bp_rate_required",
                    "message_en": "Partner sellers must set a Buyer's Premium rate "
                                  "before creating a listing.",
                    "message_fr": "Les vendeurs partenaires doivent définir un taux de "
                                  "prime acheteur avant de créer une annonce.",
                }
            )
        listing_dict["partner_bp_rate"] = float(partner_bp_rate)
    else:
        listing_dict["partner_bp_rate"] = None

    # ── Geo-sort coordinates (province + city from seller profile) ──
    listing_dict["seller_province"] = (
        seller_doc.get("province")
        or listing_dict.get("region")  # fall back to listing's region
        or None
    )
    listing_dict["seller_city"] = (
        seller_doc.get("city")
        or listing_dict.get("city")
        or None
    )

    # ── Legacy partner-listing flag (kept for compatibility) ──
    if seller_doc.get("is_partner") and seller_doc.get("partner_verification_status") == "verified":
        listing_dict["is_partner_listing"] = True
        listing_dict["is_verified_firm"] = seller_doc.get("is_verified_firm", False)
        listing_dict["custom_buyer_premium_rate"] = (
            buyers_premium_rate if buyers_premium_rate is not None
            else seller_doc.get("custom_premium_rate")
        )
    else:
        listing_dict["is_partner_listing"] = False
        listing_dict["is_verified_firm"] = False
        listing_dict["custom_buyer_premium_rate"] = buyers_premium_rate


async def persist_listing(db, listing_dict: Dict, agreement_metadata: Dict) -> Dict:
    """Insert a single-item listing into MongoDB and return the clean dict."""
    listing_dict["agreement_metadata"] = agreement_metadata
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()

    # iter211 P4 — tag demo accounts' listings so public queries can filter them out
    from services.demo_filter import tag_listing_if_demo
    await tag_listing_if_demo(db, listing_dict.get("seller_id") or listing_dict.get("user_id"), listing_dict)

    await db.listings.insert_one(listing_dict)
    listing_dict.pop("_id", None)

    from services.api_cache import invalidate_listing_caches
    invalidate_listing_caches()

    return listing_dict


async def resolve_listing_status(db, current_user: User, settings: Dict) -> str:
    """
    Determine status for a NEW single-item listing.

    Rule (matches resolve_multi_item_status for multi-item):
    - If require_approval_new_sellers is ON in marketplace_settings AND the
      seller has zero previously-completed listings, status = 'pending'
      (admin must moderate before it goes live).
    - Admins always bypass moderation.
    - Otherwise status = 'active'.
    """
    if current_user.role == "admin":
        return "active"
    if not settings.get("require_approval_new_sellers", False):
        return "active"

    # New seller = zero completed listings (single OR multi)
    completed_single = await db.listings.count_documents({
        "seller_id": current_user.id,
        "status": "completed",
    })
    completed_multi = await db.multi_item_listings.count_documents({
        "seller_id": current_user.id,
        "status": "completed",
    })
    if (completed_single + completed_multi) < 1:
        logger.info(f"[MODERATION] New seller {current_user.email} → listing set to PENDING")
        return "pending"
    return "active"


# ─── Multi-Item Creation ─────────────────────────────────────────────

async def resolve_multi_item_status(db, current_user: User, listing_data, settings: Dict) -> str:
    """Determine listing status — iter299 P1: moderation always on for
    non-trusted sellers (mirrors resolve_listing_status)."""
    status = "active"
    if not await _is_trusted_marketplace_seller(db, current_user):
        status = "pending_review"
        logger.info(f"[MODERATION] Non-trusted seller {current_user.email} multi-item → PENDING_REVIEW")
    if listing_data.auction_start_date:
        now = datetime.now(timezone.utc)
        if listing_data.auction_start_date > now and status == "active":
            status = "upcoming"
    return status


def compute_promotion(current_user: User, listing_data) -> Dict[str, Any]:
    """Calculate promotion flags based on subscription tier and explicit promotion tier."""
    now = datetime.now(timezone.utc)
    is_featured = False
    promotion_expiry = None

    if current_user.subscription_tier == "premium":
        is_featured = True
        promotion_expiry = now + timedelta(days=3)
    elif current_user.subscription_tier == "vip":
        is_featured = True
        promotion_expiry = now + timedelta(days=7)

    promotion_tier = listing_data.promotion_tier
    is_promoted = listing_data.is_promoted
    promotion_start = None
    promotion_end = None

    if promotion_tier in ['premium', 'elite']:
        is_promoted = True
        promotion_start = now
        if promotion_tier == 'premium':
            promotion_end = now + timedelta(days=7)
        elif promotion_tier == 'elite':
            promotion_end = now + timedelta(days=14)
            is_featured = True
        logger.info(f"Seller promoted listing: tier={promotion_tier}, ends={promotion_end}")

    return {
        "is_featured": is_featured,
        "promotion_expiry": promotion_expiry,
        "is_promoted": is_promoted,
        "promotion_tier": promotion_tier,
        "promotion_start": promotion_start,
        "promotion_end": promotion_end,
    }


MAX_LOTS_PER_AUCTION = 500  # Hard ceiling — Lot 1 .. Lot 500 (industry standard)


def build_lots_with_end_time(lots, auction_end_date) -> list:
    """Assign staggered lot end times (1 minute apart) AND auto-number lots
    sequentially starting at 1. Any seller-supplied `lot_number` is overridden
    so the platform shows a uniform `Lot N` across every multi-item listing.

    Raises ValueError if the auction has more than MAX_LOTS_PER_AUCTION lots.
    """
    if len(lots) > MAX_LOTS_PER_AUCTION:
        raise ValueError(
            f"Maximum {MAX_LOTS_PER_AUCTION} lots allowed per auction "
            f"(received {len(lots)})."
        )
    result = []
    for idx, lot in enumerate(lots):
        lot_dict = lot.model_dump()
        # Force sequential numbering 1..N
        lot_dict['lot_number'] = idx + 1
        lot_dict['lot_end_time'] = auction_end_date + timedelta(minutes=idx)
        result.append(lot_dict)
    return result


def serialise_datetimes(listing_dict: Dict):
    """Convert all datetime fields to ISO strings in-place."""
    for key in ("auction_end_date", "created_at", "auction_start_date",
                "promotion_expiry", "promotion_start", "promotion_end"):
        if listing_dict.get(key):
            val = listing_dict[key]
            if hasattr(val, 'isoformat'):
                listing_dict[key] = val.isoformat()
    for lot in listing_dict.get("lots", []):
        if lot.get("lot_end_time") and hasattr(lot["lot_end_time"], 'isoformat'):
            lot["lot_end_time"] = lot["lot_end_time"].isoformat()


# ─── Read Helpers ─────────────────────────────────────────────────────

def parse_listing_dates(listing: Dict):
    """Convert ISO string dates back to datetime objects (in-place)."""
    for key in ("created_at", "auction_end_date", "auction_start_date"):
        if isinstance(listing.get(key), str):
            listing[key] = datetime.fromisoformat(listing[key])
    for lot in listing.get("lots", []):
        if isinstance(lot.get("lot_end_time"), str):
            lot["lot_end_time"] = datetime.fromisoformat(lot["lot_end_time"])
      if listing_dict.get(key):
            val = listing_dict[key]
            if hasattr(val, 'isoformat'):
                listing_dict[key] = val.isoformat()
    for lot in listing_dict.get("lots", []):
        if lot.get("lot_end_time") and hasattr(lot["lot_end_time"], 'isoformat'):
            lot["lot_end_time"] = lot["lot_end_time"].isoformat()


# ─── Read Helpers ─────────────────────────────────────────────────────

def parse_listing_dates(listing: Dict):
    """Convert ISO string dates back to datetime objects (in-place)."""
    for key in ("created_at", "auction_end_date", "auction_start_date"):
        if isinstance(listing.get(key), str):
            listing[key] = datetime.fromisoformat(listing[key])
    for lot in listing.get("lots", []):
        if isinstance(lot.get("lot_end_time"), str):
            lot["lot_end_time"] = datetime.fromisoformat(lot["lot_end_time"])
