"""
iter283-payments-audit Mission 1B — Idempotent Stripe Customer backfill.

Lazy-creates a `stripe.Customer` for every user that doesn't already
have one. Safe to run on every startup — only touches users where
`stripe_customer_id` is missing/null/empty.

This closes the gap where 16/18 production users had no Stripe
Customer assigned, which would force them through a customer-create
fallback EVERY time they touched a payment flow (deposit, card add,
etc.) — wasting Stripe API calls and risking race-condition
duplicates.

Defensive guards:
  • Skips users without an `email` (Stripe requires it).
  • Catches every Stripe error per-user — one failed customer
    creation NEVER aborts the boot.
  • Logs progress to the standard `[iter283-payments-audit]` channel.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import os

logger = logging.getLogger(__name__)


async def backfill_stripe_customers(db, *, max_users: int = 2000) -> dict:
    """Create Stripe Customers for users missing one. Returns counts."""
    counts = {"checked": 0, "created": 0, "skipped_no_email": 0, "errors": 0}
    try:
        import stripe
        if not (os.environ.get("STRIPE_API_KEY") or stripe.api_key):
            logger.info(
                "[iter283-payments-audit] Stripe not configured — "
                "customer backfill skipped."
            )
            return counts

        cursor = db.users.find(
            {
                "$or": [
                    {"stripe_customer_id": {"$exists": False}},
                    {"stripe_customer_id": None},
                    {"stripe_customer_id": ""},
                ]
            },
            {"_id": 0, "id": 1, "email": 1, "name": 1},
        ).limit(max_users)

        async for user in cursor:
            counts["checked"] += 1
            uid = user.get("id")
            email = (user.get("email") or "").strip()
            if not uid or not email:
                counts["skipped_no_email"] += 1
                continue
            try:
                customer = stripe.Customer.create(
                    email=email,
                    name=user.get("name") or email,
                    metadata={
                        "user_id": uid,
                        "platform": "bidvex",
                        "source": "iter283-backfill",
                    },
                )
                await db.users.update_one(
                    {"id": uid},
                    {"$set": {
                        "stripe_customer_id": customer.id,
                        "stripe_customer_backfilled_at":
                            datetime.now(timezone.utc).isoformat(),
                    }},
                )
                counts["created"] += 1
            except Exception as exc:  # noqa: BLE001 — per-user fault tolerance.
                counts["errors"] += 1
                logger.warning(
                    f"[iter283-payments-audit] customer-create failed "
                    f"for user {uid}: {exc}"
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter283-payments-audit] backfill aborted: {exc}")
    return counts


__all__ = ["backfill_stripe_customers"]
