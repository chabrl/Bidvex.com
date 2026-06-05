"""
iter283-hotfix-2 — Trusted-seller vehicle fast-track + system toggle defaults.

Idempotent at-startup repair for the "vehicles section empty"
production complaint:

  1. Any DRAFT/PENDING vehicle authored by a trusted seller (admin,
     verified partner, vehicle dealer, or storage facility) gets
     fast-tracked to ACTIVE. Same trust model as `db.listings`.

  2. The `vehicle_auctions_enabled` system toggle defaults to True
     when missing — the toggle exists for emergency pause, not for
     a permanent default-off state. Without this, even an
     admin-approved listing sits in APPROVED forever.

  3. Idempotent — every run only touches docs that match the
     fast-track criteria and aren't already ACTIVE.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


async def fast_track_trusted_drafts(db) -> dict:
    """Promote DRAFT/PENDING vehicle listings to ACTIVE for trusted sellers.

    A vehicle is trusted-fast-tracked when its `vehicle_sellers` doc has
    `verification_status: approved` (vetted out-of-band). The
    `vehicle_listings.seller_id` references `vehicle_sellers.id`, NOT
    `users.id` — that's the key distinction the earlier draft missed.
    """
    counts = {"promoted": 0, "approved_sellers": 0}
    try:
        approved_sellers = await db.vehicle_sellers.find(
            {"verification_status": "approved"},
            {"_id": 0, "id": 1, "user_id": 1},
        ).to_list(5000)
        seller_pids = [s["id"] for s in approved_sellers if s.get("id")]
        counts["approved_sellers"] = len(seller_pids)
        if not seller_pids:
            return counts

        now = datetime.now(timezone.utc)
        r = await db.vehicle_listings.update_many(
            {
                "seller_id": {"$in": seller_pids},
                "status": {"$in": ["draft", "pending_approval", "approved"]},
            },
            {"$set": {
                "status": "active",
                "approved_at": now,
                "updated_at": now,
            }},
        )
        counts["promoted"] = int(r.modified_count or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter283-hotfix-2] vehicle fast-track skipped: {exc}")
    return counts


async def ensure_vehicle_auctions_toggle_default(db) -> bool:
    """Make sure `vehicle_auctions_enabled` is set so admin-approved
    listings flip to ACTIVE on approval. Default to True when missing
    (the flag is an emergency pause, not a permanent gate)."""
    try:
        settings = await db.system_settings.find_one({})
        if settings is None:
            await db.system_settings.insert_one({
                "vehicle_auctions_enabled": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "created_by": "iter283-hotfix-2",
            })
            return True
        if "vehicle_auctions_enabled" not in settings:
            await db.system_settings.update_one(
                {"_id": settings["_id"]},
                {"$set": {
                    "vehicle_auctions_enabled": True,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter283-hotfix-2] vehicle toggle default skipped: {exc}")
    return False


__all__ = ["fast_track_trusted_drafts", "ensure_vehicle_auctions_toggle_default"]
