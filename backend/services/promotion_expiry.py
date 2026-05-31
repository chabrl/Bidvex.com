"""
iter241 Mission 1 — Promotion expiry sweeper.

Runs hourly. For every listing whose `promotion_end` (or `promoted_until`)
is in the past AND `is_promoted` is still true, flip the listing back to
unpromoted and notify the seller they can renew. Idempotent — safe to
re-run on the same minute.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Listing collections that can hold a promotion.
PROMOTABLE_COLLECTIONS = [
    "listings",
    "multi_item_listings",
    "vehicle_listings",
    "storage_auctions",
]


async def expire_listing_promotions(db) -> Dict[str, Any]:
    """Sweep all promotable collections for expired promotions.

    Returns a stats dict for log/observability:
        {expired_count: int, by_collection: {coll: count}, errors: [...]}
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    stats: Dict[str, Any] = {
        "expired_count": 0,
        "by_collection": {},
        "errors": [],
        "ran_at": now_iso,
    }

    for coll_name in PROMOTABLE_COLLECTIONS:
        coll = db[coll_name]
        # Match docs that are still flagged as promoted but past their end date.
        # We tolerate both `promotion_end` (legacy) and `promoted_until` (new).
        query = {
            "is_promoted": True,
            "$or": [
                {"promotion_end": {"$lt": now_iso}},
                {"promoted_until": {"$lt": now_iso}},
            ],
        }
        try:
            expired_docs: List[Dict[str, Any]] = await coll.find(
                query,
                {"_id": 0, "id": 1, "title": 1, "seller_id": 1,
                 "promotion_tier": 1, "promotion_end": 1, "promoted_until": 1},
            ).to_list(length=500)

            if not expired_docs:
                continue

            ids = [d["id"] for d in expired_docs if d.get("id")]
            if not ids:
                continue

            await coll.update_many(
                {"id": {"$in": ids}},
                {"$set": {
                    "is_promoted": False,
                    "is_featured": False,
                    "promotion_tier": None,
                    "promotion_tier_weight": 0,
                    "promotion_features": [],
                    "promoted_sections": [],
                    "promotion_expired_at": now_iso,
                }},
            )
            stats["by_collection"][coll_name] = len(ids)
            stats["expired_count"] += len(ids)

            # Best-effort renewal email per seller.
            for doc in expired_docs:
                seller_id = doc.get("seller_id")
                if not seller_id:
                    continue
                try:
                    user = await db.users.find_one(
                        {"id": seller_id}, {"_id": 0, "email": 1, "first_name": 1, "name": 1}
                    )
                    if not user or not user.get("email"):
                        continue
                    from services.email_notifications import send_unified_email
                    await send_unified_email(
                        "promotion_expired",
                        user={
                            "email": user["email"],
                            "first_name": user.get("first_name") or user.get("name") or "",
                        },
                        data={
                            "listing_title": doc.get("title", "Your listing"),
                            "listing_id": doc.get("id"),
                            "tier": doc.get("promotion_tier") or "",
                            "secondary_info": (
                                "Renew your promotion to keep it featured at the top of search."
                            ),
                        },
                    )
                except Exception as e:  # noqa: BLE001
                    stats["errors"].append({
                        "listing_id": doc.get("id"),
                        "seller_id": seller_id,
                        "error": f"{type(e).__name__}: {e}",
                    })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[promo-expiry] {coll_name} sweep failed: {e}")
            stats["errors"].append({"collection": coll_name, "error": str(e)})

    if stats["expired_count"] > 0:
        logger.info(
            f"[promo-expiry] expired {stats['expired_count']} listing(s) "
            f"across {len(stats['by_collection'])} collection(s)"
        )
    return stats


__all__ = ["expire_listing_promotions"]
