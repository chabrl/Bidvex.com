"""
iter364 — Admin notification-bell summary endpoint.

Aggregates open counts for the four categories the admin console cares
about (flagged listings, dealer licence reviews, disputes, payment
failures) into one lightweight GET so the notification bell can poll
every 60s without opening four separate connections.

Returns:
    {
        "unread_flagged_listings": int,
        "pending_dealer_reviews":  int,
        "open_disputes":           int,
        "payment_failures":        int,
        "total_unread":            int,
        "generated_at":            ISO-8601 UTC
    }
"""

from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import logging

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

admin_notifications_router = APIRouter(prefix="/api/admin/notifications", tags=["admin-notifications"])


def _require_admin(user: User):
    if user.role not in ("admin", "super_admin"):
        # Match the existing 403 semantics used by other admin routes.
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")


@admin_notifications_router.get("/summary")
async def notifications_summary(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    _require_admin(current_user)

    # Four independent counters — issued in parallel would be ideal but
    # Motor's find().count_documents is already cheap and the collections
    # are small enough (< 100k docs) that sequential is fine here.
    unread_flagged = await db.fraud_flags.count_documents({"status": {"$in": ["pending", "investigating"]}})

    pending_licenses = await db.dealer_licenses.count_documents({"status": {"$in": ["pending", "submitted"]}})
    # Vehicle-listings collection also stores license-approval state on
    # some seed data; fall back to that if the dedicated collection is
    # empty (backward compatibility).
    if pending_licenses == 0:
        pending_licenses = await db.users.count_documents({
            "account_type": {"$in": ["vehicle_dealer", "dealer"]},
            "dealer_license_status": {"$in": ["pending", "submitted"]},
        })

    open_disputes = await db.disputes.count_documents({"status": {"$in": ["open", "under_review"]}})
    # Same fallback for the older disputed_settlements collection.
    if open_disputes == 0:
        open_disputes = await db.disputed_settlements.count_documents({"status": {"$in": ["open", "under_review", "pending"]}}) \
            if "disputed_settlements" in await db.list_collection_names() else 0

    payment_failures = await db.payment_transactions.count_documents({"status": {"$in": ["failed", "declined"]}}) \
        if "payment_transactions" in await db.list_collection_names() else 0

    total = unread_flagged + pending_licenses + open_disputes + payment_failures

    return {
        "unread_flagged_listings": unread_flagged,
        "pending_dealer_reviews":  pending_licenses,
        "open_disputes":           open_disputes,
        "payment_failures":        payment_failures,
        "total_unread":            total,
        "generated_at":            datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["admin_notifications_router"]
