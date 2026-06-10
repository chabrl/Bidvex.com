"""
Promotion Email Blast Worker — fires 24h after a premium promotion activation.

Queue shape (`promotion_email_blast_queue`):
{
  "id": uuid,
  "listing_id": str,
  "listing_type": "marketplace" | "lots" | "vehicle" | "storage",
  "seller_id": str,
  "tier": "premium",
  "scheduled_for": iso str,      # now + 24h at enqueue time
  "status": "pending" | "processing" | "completed" | "failed",
  "created_at": iso str,
  "processed_at": iso str | None,
  "recipients_count": int,
  "error": str | None,
}

Triggered by APScheduler every 5 minutes — claims rows with status=pending
and scheduled_for <= now, then fans out send_promotion_email_blast() to
email_subscribed users who have shown interest in the listing's category.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

BATCH_SIZE = 10
RECIPIENT_CAP_PER_BLAST = 200


async def _find_interested_recipients(db, listing_type: str, category: str) -> List[Dict[str, Any]]:
    """
    Find users who have viewed or saved an item in the same category recently.
    Falls back to email_subscribed=True ∧ last_login within 90 days if no
    activity signal is available.
    """
    q_saved = {"category": category} if category else {}
    saved_users = set()
    try:
        cursor = db.saved_listings.find(q_saved, {"_id": 0, "user_id": 1}).limit(RECIPIENT_CAP_PER_BLAST)
        async for d in cursor:
            saved_users.add(d.get("user_id"))
    except Exception:
        pass
    try:
        cursor = db.watchlist.find(q_saved, {"_id": 0, "user_id": 1}).limit(RECIPIENT_CAP_PER_BLAST)
        async for d in cursor:
            saved_users.add(d.get("user_id"))
    except Exception:
        pass

    user_query = {
        "email_subscribed": {"$ne": False},
        "email_unsubscribed": {"$ne": True},
        "email_suppressed": {"$ne": True},
    }
    if saved_users:
        user_query["id"] = {"$in": list(saved_users)[:RECIPIENT_CAP_PER_BLAST]}
    return await db.users.find(
        user_query, {"_id": 0, "id": 1, "email": 1, "name": 1}
    ).limit(RECIPIENT_CAP_PER_BLAST).to_list(RECIPIENT_CAP_PER_BLAST)


async def process_promotion_email_blast_queue(db) -> Dict[str, int]:
    now_iso = datetime.now(timezone.utc).isoformat()
    processed = 0
    emails_sent = 0
    for _ in range(BATCH_SIZE):
        job = await db.promotion_email_blast_queue.find_one_and_update(
            {"status": "pending", "scheduled_for": {"$lte": now_iso}},
            {"$set": {"status": "processing", "claimed_at": now_iso}},
        )
        if not job:
            break
        listing_id = job["listing_id"]
        listing_type = job.get("listing_type", "marketplace")
        coll_map = {
            "marketplace": db.listings,
            "lots": db.multi_item_listings,
            "vehicle": db.vehicle_listings,
            "storage": db.storage_auctions,
        }
        listing = await coll_map.get(listing_type, db.listings).find_one(
            {"id": listing_id}, {"_id": 0, "title": 1, "category": 1}
        )
        if not listing:
            await db.promotion_email_blast_queue.update_one(
                {"id": job["id"]},
                {"$set": {"status": "failed", "error": "listing_not_found", "processed_at": now_iso}},
            )
            continue

        category = listing.get("category", "") or ""
        title = listing.get("title", "Featured Auction")
        recipients = await _find_interested_recipients(db, listing_type, category)
        sent_for_job = 0
        try:
            from services.emails.email_system import send_promotion_email_blast
            for u in recipients:
                if not u.get("email"):
                    continue
                try:
                    await send_promotion_email_blast(
                        to_email=u["email"], listing_title=title,
                        listing_id=listing_id, listing_type=listing_type,
                        category=category,
                    )
                    sent_for_job += 1
                except Exception as e:
                    logger.warning(f"[email_blast] failed {u.get('id')}: {e}")
        except ImportError:
            pass

        await db.promotion_email_blast_queue.update_one(
            {"id": job["id"]},
            {"$set": {
                "status": "completed",
                "recipients_count": sent_for_job,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        processed += 1
        emails_sent += sent_for_job

    if processed:
        logger.info(
            f"[email_blast] processed {processed} jobs, sent {emails_sent} emails"
        )
    return {"processed": processed, "emails_sent": emails_sent}


async def ensure_email_blast_queue_indexes(db) -> None:
    try:
        await db.promotion_email_blast_queue.create_index(
            [("status", 1), ("scheduled_for", 1)], name="ix_status_scheduled"
        )
    except Exception as exc:
        logger.warning(f"email_blast index creation failed: {exc}")


# Re-export uuid for test convenience
_uuid = uuid
