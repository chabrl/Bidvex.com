"""
HOTFIX (AI Watchdog Infinite Re-flag Loop) / FIX 3
One-shot startup migration: stamp `watchdog_exempt=True` on every listing
that was ever admin-approved through the listing_reviews queue.

This protects against future cold-start scenarios where the safety watchdog
runs BEFORE all historical approval state has been mirrored onto the listing
docs themselves.

Idempotent — re-running matches the same rows and is a no-op for already-stamped
listings.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def backfill_watchdog_exempt(db) -> dict:
    """Returns {'approved_count': N, 'listings_modified': N, 'multi_modified': N,
    'restored_to_active': N}."""
    now = datetime.now(timezone.utc)

    # 1) Every listing_id where the review system marked status=approved
    approved_ids: set[str] = set()
    async for r in db.listing_reviews.find({"status": "approved"}, {"_id": 0, "listing_id": 1}):
        lid = r.get("listing_id")
        if lid:
            approved_ids.add(lid)

    # 2) Listings already carrying the admin_approved_override passport
    async for d in db.listings.find({"admin_approved_override": True}, {"_id": 0, "id": 1}):
        approved_ids.add(d["id"])
    async for d in db.multi_item_listings.find({"admin_approved_override": True}, {"_id": 0, "id": 1}):
        approved_ids.add(d["id"])

    if not approved_ids:
        return {
            "approved_count": 0,
            "listings_modified": 0,
            "multi_modified": 0,
            "restored_to_active": 0,
        }

    update_doc = {"$set": {
        "watchdog_exempt": True,
        "watchdog_exempt_at": now,
        "watchdog_exempt_by": "backfill_migration",
        "paused_by_watchdog": False,
    }}
    r1 = await db.listings.update_many(
        {"id": {"$in": list(approved_ids)}, "watchdog_exempt": {"$ne": True}},
        update_doc,
    )
    r2 = await db.multi_item_listings.update_many(
        {"id": {"$in": list(approved_ids)}, "watchdog_exempt": {"$ne": True}},
        update_doc,
    )

    # Bounce previously paused-by-watchdog rows back to active.
    restored = await db.listings.update_many(
        {
            "id": {"$in": list(approved_ids)},
            "status": {"$in": ["pending_review", "paused", "pending_ai_review"]},
        },
        {"$set": {
            "status": "active",
            "is_published": True,
            "paused_by": None,
            "paused_reason": None,
        }},
    )

    logger.info(
        "[watchdog_exempt_backfill] approved=%s listings_modified=%s multi_modified=%s restored=%s",
        len(approved_ids), r1.modified_count, r2.modified_count, restored.modified_count,
    )
    return {
        "approved_count": len(approved_ids),
        "listings_modified": r1.modified_count,
        "multi_modified": r2.modified_count,
        "restored_to_active": restored.modified_count,
    }
