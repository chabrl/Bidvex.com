"""
iter330 — Partner-tier launch coupon (PARTNER50).

Mirrors the LAUNCH50 coupon used by the vehicle dealer subscription path.
PARTNER50 is a 50%-off Stripe Coupon applied to net-new Partner-tier
subscribers (`subscription_pricing.DEFAULT_PLANS["partner"]`).

This module is **read/write to Stripe** — it idempotently creates the
Coupon on first invocation and caches the ID in
`db.stripe_settings` (id="partner_subscription") so subsequent boot-ups
are zero-cost.

If the Stripe API key is invalid (preview env), `ensure_partner50_coupon`
returns `None` and the caller should not apply any discount. CI builds
should verify a real Stripe key reaches the script.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import stripe

from services.subscription_pricing import DEFAULT_PLANS

logger = logging.getLogger("partner_coupon")

stripe.api_key = (
    os.environ.get("STRIPE_API_KEY")
    or os.environ.get("STRIPE_SECRET_KEY")
    or ""
)

COUPON_ID = "PARTNER50"
COUPON_PERCENT_OFF = 50.0
COUPON_DURATION = "once"   # First-year only — encourages annual conversion
SETTINGS_DOC_ID = "partner_subscription"


async def ensure_partner50_coupon(db) -> Optional[str]:
    """Idempotently ensure the PARTNER50 coupon exists in Stripe.

    Returns the coupon ID on success, None on Stripe failure (e.g. preview
    env with invalid API key). Caller is responsible for skipping the
    discount when this returns None — never blocks subscription creation.
    """
    settings_doc = await db.stripe_settings.find_one({"id": SETTINGS_DOC_ID})
    if settings_doc and settings_doc.get("coupon_id"):
        return settings_doc["coupon_id"]

    try:
        existing = stripe.Coupon.retrieve(COUPON_ID)
        coupon_id = existing.id
    except stripe.InvalidRequestError:
        try:
            c = stripe.Coupon.create(
                id=COUPON_ID,
                percent_off=COUPON_PERCENT_OFF,
                duration=COUPON_DURATION,
                name="BidVex Partner Program Launch (50% off first year)",
                metadata={"bidvex_role": "partner_subscription", "bidvex_iter": "iter330"},
            )
            coupon_id = c.id
        except Exception as exc:
            logger.warning(f"[iter330] PARTNER50 coupon create failed (preview env?): {exc}")
            return None
    except Exception as exc:
        logger.warning(f"[iter330] PARTNER50 coupon retrieve failed: {exc}")
        return None

    await db.stripe_settings.update_one(
        {"id": SETTINGS_DOC_ID},
        {"$set": {
            "id": SETTINGS_DOC_ID,
            "coupon_id": coupon_id,
            "percent_off": COUPON_PERCENT_OFF,
            "duration": COUPON_DURATION,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return coupon_id


async def should_apply_partner_coupon(db, user_id: str) -> bool:
    """Return True iff this user is a net-new Partner-tier subscriber.

    Net-new = no `stripe_subscription_id` AND no `partner_subscription_id`
    on their user document. This prevents stacking PARTNER50 across
    consecutive Partner subscriptions or upgrade paths.
    """
    user = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "stripe_subscription_id": 1, "partner_subscription_id": 1,
         "partner_coupon_redeemed_at": 1},
    )
    if not user:
        return False
    if user.get("partner_coupon_redeemed_at"):
        return False
    if user.get("stripe_subscription_id") or user.get("partner_subscription_id"):
        return False
    return True


async def mark_partner_coupon_applied(db, user_id: str) -> None:
    """Stamp the user as having consumed PARTNER50 — prevents re-use."""
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"partner_coupon_redeemed_at": datetime.now(timezone.utc).isoformat()}},
    )
    logger.info("[iter330] PARTNER50 applied for user=%s", user_id)


__all__ = [
    "COUPON_ID",
    "COUPON_PERCENT_OFF",
    "ensure_partner50_coupon",
    "should_apply_partner_coupon",
    "mark_partner_coupon_applied",
]
