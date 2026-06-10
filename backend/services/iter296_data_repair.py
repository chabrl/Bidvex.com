"""
services/iter296_data_repair.py — one-shot backfill on startup

Repairs marketplace + multi-item listings that ended BEFORE the
iter296 fix shipped but never got `winner_user_id`, `sold_at` or
`final_price` stamps. Without these stamps:
  - the seller dashboard's "Sold" counter showed 0
  - the union query `{status: ended, winner_user_id: {exists}}` missed
    them
  - downstream invoice / pickup-code flows could not resolve the winner

The repair is idempotent — once a listing has been backfilled, the
selector skips it on every subsequent run.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def run_iter296_listing_repair(db) -> dict:
    """Stamp `winner_user_id` / `sold_at` / `final_price` on every
    ended listing that has a `highest_bidder_id` but is missing one of
    the iter296 fields. Returns a summary dict for logging."""
    out = {"marketplace": 0, "multi_item": 0, "skipped_no_winner": 0}
    try:
        # ── Marketplace single listings ──
        cursor = db.listings.find({
            "status": "ended",
            "highest_bidder_id": {"$exists": True, "$ne": None},
            "$or": [
                {"winner_user_id": {"$exists": False}},
                {"winner_user_id": None},
            ],
        }, {"_id": 0, "id": 1, "highest_bidder_id": 1, "current_price": 1, "ended_at": 1})
        async for doc in cursor:
            winner = doc.get("highest_bidder_id")
            if not winner:
                out["skipped_no_winner"] += 1
                continue
            await db.listings.update_one(
                {"id": doc["id"]},
                {"$set": {
                    "winner_user_id": winner,
                    "sold_at": doc.get("ended_at") or datetime.now(timezone.utc).isoformat(),
                    "final_price": float(doc.get("current_price") or 0),
                }},
            )
            out["marketplace"] += 1

        # ── Multi-item listings ──
        cursor = db.multi_item_listings.find({
            "status": "ended",
            "lots.highest_bidder_id": {"$exists": True},
        }, {"_id": 0, "id": 1, "lots": 1, "ended_at": 1})
        async for doc in cursor:
            ts = doc.get("ended_at") or datetime.now(timezone.utc).isoformat()
            patched = False
            for lot in (doc.get("lots") or []):
                if lot.get("highest_bidder_id") and not lot.get("winner_user_id"):
                    await db.multi_item_listings.update_one(
                        {"id": doc["id"], "lots.lot_number": lot.get("lot_number")},
                        {"$set": {
                            "lots.$.winner_user_id": lot["highest_bidder_id"],
                            "lots.$.sold_at": ts,
                            "lots.$.final_price": float(lot.get("current_price") or 0),
                            "lots.$.status": "sold",
                        }},
                    )
                    patched = True
            if patched:
                await db.multi_item_listings.update_one(
                    {"id": doc["id"]},
                    {"$set": {"sold_at": ts}},
                )
                out["multi_item"] += 1

        if out["marketplace"] or out["multi_item"]:
            logger.info(f"[iter296_repair] backfilled: {out}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[iter296_repair] failed: {e}")
        out["error"] = str(e)
    return out
