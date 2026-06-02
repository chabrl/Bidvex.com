"""
iter265 Mission 1.4 — Per-listing geo notifications.

When a new listing is created with resolved coordinates, fan-out a
"nearby_listing" alert (bell notification + email) to every user
within 50km whose `notify_nearby` preference is not opted out.

This is the PER-CREATION notifier — distinct from the existing
daily geo_email_service.py digest job.

Dedup contract: at most ONE alert per (user, category) within a
24h sliding window, persisted to `recent_nearby_notifs`.
"""
from __future__ import annotations

import logging
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def _extract_coords(listing: Dict[str, Any]) -> Optional[tuple]:
    loc = (listing or {}).get("location") or {}
    coords = loc.get("coordinates")
    if not coords or not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None
    try:
        return float(coords[0]), float(coords[1])
    except (TypeError, ValueError):
        return None


async def notify_nearby_users(
    listing_id: str,
    listing: Dict[str, Any],
    db,
    radius_km: float = 50.0,
    max_recipients: int = 50,
) -> Dict[str, Any]:
    """Fan-out a per-listing alert. NEVER raises — always returns a
    structured result so it's safe to schedule via
    `asyncio.create_task()` from the listing-create endpoint."""
    try:
        coords = _extract_coords(listing)
        if not coords:
            return {"sent": 0, "skipped_reason": "no_coordinates"}
        lng, lat = coords

        seller_id = listing.get("seller_id") or listing.get("created_by")
        title = (listing.get("title") or "New Item")[:120]
        category = (listing.get("category") or "item")[:40]
        city = (((listing.get("location") or {}).get("city")) or "your area")[:80]
        current_bid = float(
            listing.get("current_bid")
            or listing.get("current_price")
            or listing.get("starting_price")
            or 0
        )
        listing_url = (
            listing.get("public_url")
            or f"https://bidvex.com/listing/{listing_id}"
        )

        # `$geoWithin` requires a `2dsphere` index on users.
        # location.coordinates. We create it on startup elsewhere.
        try:
            cursor = db.users.find({
                "location.coordinates": {
                    "$geoWithin": {
                        "$centerSphere": [[lng, lat], radius_km / 6371.0],
                    },
                },
                "id": {"$ne": seller_id} if seller_id else {"$exists": True},
                "$and": [
                    {"$or": [
                        {"notification_prefs.notify_nearby": True},
                        {"notification_prefs.notify_nearby": {"$exists": False}},
                    ]},
                    {"$or": [
                        {"notify_nearby": True},
                        {"notify_nearby": {"$exists": False}},
                    ]},
                ],
            }, {"_id": 0, "id": 1, "email": 1, "name": 1, "language": 1})
            nearby = await cursor.to_list(length=max_recipients * 4)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[geo-notify] $geoWithin failed: {exc}")
            return {"sent": 0, "skipped_reason": "geo_index_unavailable"}

        now = datetime.now(timezone.utc)
        sent = 0
        for user in nearby:
            uid = user.get("id")
            if not uid:
                continue
            dedup_key = f"{uid}_{category}"
            recent = await db.recent_nearby_notifs.find_one({
                "key": dedup_key,
                "sent_at": {"$gt": now - timedelta(hours=24)},
            })
            if recent:
                continue
            # Bell notification — non-blocking, always insert.
            try:
                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()),
                    "user_id": uid,
                    "type": "nearby_listing",
                    "title": f"📍 New {category} near you in {city}!",
                    "body": f'"{title}" — Current bid: ${current_bid:.2f} CAD',
                    "link": listing_url,
                    "listing_id": listing_id,
                    "is_read": False,
                    "created_at": now.isoformat(),
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[geo-notify] notif insert failed for {uid}: {exc}")
            # Email — fire-and-forget; honor the per-user nearby pref.
            try:
                from services.email_notifications import send_unified_email
                await send_unified_email(
                    user=dict(user),
                    email_type="nearby_listing",
                    data={
                        "listing_title": title,
                        "category": category,
                        "city": city,
                        "current_bid": f"{current_bid:.2f}",
                        "cta_url": listing_url,
                        "cta_label": "View This Listing →",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.info(f"[geo-notify] email skipped for {uid}: {exc}")
            # Mark dedup row.
            await db.recent_nearby_notifs.insert_one({
                "key": dedup_key,
                "user_id": uid,
                "listing_id": listing_id,
                "category": category,
                "sent_at": now.isoformat(),
            })
            sent += 1
            if sent >= max_recipients:
                break
        logger.info(f"[geo-notify] {sent} users alerted near listing {listing_id}")
        return {"sent": sent, "radius_km": radius_km}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[geo-notify] unhandled error for {listing_id}: {exc}")
        traceback.print_exc()
        return {"sent": 0, "skipped_reason": "exception"}


__all__ = ["notify_nearby_users"]
