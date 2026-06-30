"""
iter330 — Trial + First-Listing-Free service (Summer 2026 promo gate).

Centralizes the eligibility checks and idempotent "consume-once" semantics
for two cross-feature promo flags on the `users` collection:

    • trial_redeemed_at        : Optional[ISO datetime]   set when a user
                                 activates their 1-month free trial on ANY
                                 paid subscription tier. Lifetime one-time.
    • trial_redeemed_tier      : Optional[str]            which tier they
                                 redeemed the trial for (premium/vip/
                                 partner/partner_pro/vehicle_dealer/
                                 storage_facility).
    • first_listing_free_used  : bool (default False)     set when a seller
                                 has consumed their "first listing on us"
                                 promotional waiver.

These flags are independent — a user can claim a trial WITHOUT ever using
the first-listing-free benefit and vice versa.

Both flags are global per-user; we do NOT reset them on tier change or
subscription cancellation. That's intentional — these are launch promos,
not recurring benefits.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("trial_promo")

# Tiers that can claim the 1-month free trial.
TRIAL_ELIGIBLE_TIERS = (
    "premium", "vip", "partner", "partner_pro",
    "vehicle_dealer", "storage_facility",
)
TRIAL_DAYS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def is_trial_eligible(db, user_id: str, tier: Optional[str] = None) -> bool:
    """Return True iff this user has NEVER redeemed the trial and `tier` is
    one of the eligible tiers (free/basic always returns False).
    """
    if tier and tier.lower() not in TRIAL_ELIGIBLE_TIERS:
        return False
    user = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "trial_redeemed_at": 1},
    )
    if user is None:
        return False
    return not user.get("trial_redeemed_at")


async def mark_trial_redeemed(db, user_id: str, tier: str) -> bool:
    """Atomically stamp `trial_redeemed_at` + `trial_redeemed_tier`.

    Returns True if the stamp was written (first time), False if the user
    had already redeemed — caller can use this to detect race conditions.
    """
    now = _now_iso()
    res = await db.users.update_one(
        {"id": user_id, "trial_redeemed_at": {"$in": [None, "", False]}},
        {"$set": {"trial_redeemed_at": now, "trial_redeemed_tier": tier.lower()}},
    )
    # Also handle users where the field is genuinely missing.
    if res.matched_count == 0:
        res2 = await db.users.update_one(
            {"id": user_id, "trial_redeemed_at": {"$exists": False}},
            {"$set": {"trial_redeemed_at": now, "trial_redeemed_tier": tier.lower()}},
        )
        if res2.modified_count == 0:
            return False
        logger.info("[iter330] trial redeemed user=%s tier=%s", user_id, tier)
        return True
    logger.info("[iter330] trial redeemed user=%s tier=%s", user_id, tier)
    return True


async def is_first_listing_free_eligible(db, user_id: str) -> bool:
    """Return True iff this user has never consumed the first-listing-free waiver."""
    user = await db.users.find_one(
        {"id": user_id}, {"_id": 0, "first_listing_free_used": 1},
    )
    if user is None:
        return False
    return not bool(user.get("first_listing_free_used"))


async def try_consume_first_listing_free(db, user_id: str) -> bool:
    """Atomically mark the first-listing-free waiver as consumed.

    Returns True if the waiver was just now consumed (caller should waive
    the upcoming charge); False if it was already consumed previously.

    Idempotent — concurrent calls will result in exactly ONE returning True.
    """
    res = await db.users.update_one(
        {
            "id": user_id,
            "$or": [
                {"first_listing_free_used": {"$exists": False}},
                {"first_listing_free_used": False},
                {"first_listing_free_used": None},
            ],
        },
        {"$set": {
            "first_listing_free_used": True,
            "first_listing_free_consumed_at": _now_iso(),
        }},
    )
    consumed = res.modified_count > 0
    if consumed:
        logger.info("[iter330] first-listing-free CONSUMED for user=%s", user_id)
    return consumed


async def get_promo_state(db, user_id: str) -> dict:
    """Return the full promo state for a user — used by frontend banners."""
    user = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "trial_redeemed_at": 1, "trial_redeemed_tier": 1,
         "first_listing_free_used": 1, "first_listing_free_consumed_at": 1},
    )
    if user is None:
        return {
            "trial_eligible": False,
            "trial_redeemed_at": None,
            "trial_redeemed_tier": None,
            "first_listing_free_eligible": False,
            "first_listing_free_used": False,
        }
    return {
        "trial_eligible": not user.get("trial_redeemed_at"),
        "trial_redeemed_at": user.get("trial_redeemed_at"),
        "trial_redeemed_tier": user.get("trial_redeemed_tier"),
        "first_listing_free_eligible": not user.get("first_listing_free_used"),
        "first_listing_free_used": bool(user.get("first_listing_free_used")),
        "first_listing_free_consumed_at": user.get("first_listing_free_consumed_at"),
    }


__all__ = [
    "TRIAL_ELIGIBLE_TIERS",
    "TRIAL_DAYS",
    "is_trial_eligible",
    "mark_trial_redeemed",
    "is_first_listing_free_eligible",
    "try_consume_first_listing_free",
    "get_promo_state",
]
