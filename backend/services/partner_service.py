"""
BidVex — Partner & Verification Service
Handles Stripe Pro tier checks, is_verified_firm helper, badge logic,
and aggregated partner stats.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Tiers that qualify as "Pro"
PRO_TIERS = {"partner_pro", "vip", "vip_elite"}


def is_verified_firm(user: Dict[str, Any]) -> bool:
    """
    A firm is verified when ALL of the following are true:
      1. is_partner == True
      2. platform_fee_paid == True (annual fee settled via Stripe)
      3. partner_verification_status == "approved"
    """
    return (
        user.get("is_partner", False)
        and user.get("platform_fee_paid", False)
        and user.get("partner_verification_status") == "approved"
    )


def get_partner_tier(user: Dict[str, Any]) -> str:
    """Return the effective partner tier: 'pro', 'vip', or 'free'."""
    tier = (user.get("subscription_tier") or "free").lower()
    if tier in ("vip", "vip_elite"):
        return "vip"
    if tier == "partner_pro":
        return "pro"
    return "free"


def get_badge_type(user: Dict[str, Any]) -> Optional[str]:
    """
    Determine the badge to display next to a seller's name.
    Returns None if no badge qualifies.
    """
    if is_verified_firm(user):
        tier = get_partner_tier(user)
        if tier == "vip":
            return "verified_vip"
        return "verified_firm"
    if user.get("is_partner") and user.get("partner_verification_status") == "approved":
        return "approved_partner"
    return None


async def get_partner_stats(db) -> Dict[str, Any]:
    """
    Aggregated partner metrics for the admin/partner stats dashboard.
    """
    total_partners = await db.users.count_documents({"is_partner": True})
    verified_partners = await db.users.count_documents({
        "is_partner": True,
        "partner_verification_status": "approved",
    })
    pending_applications = await db.users.count_documents({
        "partner_verification_status": "pending",
    })
    fee_paid = await db.users.count_documents({
        "is_partner": True,
        "platform_fee_paid": True,
    })

    # Pro tier breakdown
    pro_count = await db.users.count_documents({
        "is_partner": True,
        "subscription_tier": {"$in": list(PRO_TIERS)},
    })
    trialing_count = await db.users.count_documents({
        "subscription_status": "trialing",
        "subscription_source": "trial",
    })

    # Revenue proxy: count active partner listings
    partner_ids_cursor = db.users.find(
        {"is_partner": True},
        {"_id": 0, "id": 1},
    )
    partner_ids = [doc["id"] async for doc in partner_ids_cursor]

    active_partner_listings = 0
    total_partner_listings = 0
    if partner_ids:
        active_partner_listings = await db.listings.count_documents({
            "seller_id": {"$in": partner_ids},
            "status": "active",
        })
        total_partner_listings = await db.listings.count_documents({
            "seller_id": {"$in": partner_ids},
        })

    return {
        "total_partners": total_partners,
        "verified_partners": verified_partners,
        "pending_applications": pending_applications,
        "fee_paid_partners": fee_paid,
        "pro_subscribers": pro_count,
        "trialing": trialing_count,
        "active_partner_listings": active_partner_listings,
        "total_partner_listings": total_partner_listings,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
