"""
BidVex — FEATURE PATCH v9 / Feature 1
Admin Edit Auction End Time.

PATCH /api/admin/auctions/{listing_id}/end-time

Allows admin/superadmin to extend or change the end time of a single-item
listing or multi-item auction. Produces an immutable audit trail and queues
bilingual notification emails to the seller, all bidders (active + outbid),
and watchlist subscribers.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

admin_end_time_router = APIRouter(tags=["Admin End-Time"])


class EndTimeUpdate(BaseModel):
    new_end_time: datetime = Field(..., description="New auction end time (UTC ISO 8601)")
    reason: Optional[str] = Field(None, max_length=500, description="Admin-supplied reason for the audit log")
    listing_type: Optional[str] = Field("single", description="'single' or 'multi'")


async def _resolve_collection(db, listing_id: str) -> tuple[str, dict]:
    """Locate the listing in any directory collection (marketplace,
    multi-item, vehicle, storage). iter290 — vehicles + storage rows
    surface in the Manage All Auctions table and must respond to
    end-time edits the same way marketplace + lots do."""
    for coll in ("listings", "multi_item_listings", "vehicle_listings", "storage_auctions"):
        try:
            doc = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        except Exception:
            doc = None
        if doc:
            return (coll, doc)
    raise HTTPException(status_code=404, detail="Auction not found")


async def _collect_notification_recipients(db, listing_id: str, seller_id: str) -> dict:
    """Returns dict with seller_id, bidder_user_ids[], watchlist_user_ids[]."""
    bidder_ids: set[str] = set()
    # Active + outbid bidders — anyone who placed a bid on this listing.
    async for b in db.bids.find({"listing_id": listing_id}, {"_id": 0, "bidder_id": 1}):
        if b.get("bidder_id"):
            bidder_ids.add(b["bidder_id"])
    # Watchlist subscribers
    watch_ids: set[str] = set()
    async for w in db.watchlist.find({"listing_id": listing_id}, {"_id": 0, "user_id": 1}):
        if w.get("user_id"):
            watch_ids.add(w["user_id"])
    # Avoid double-emailing: bidders take priority over watchers if same user
    watch_ids -= bidder_ids
    # Seller stays alone
    bidder_ids.discard(seller_id)
    watch_ids.discard(seller_id)
    return {
        "seller_id": seller_id,
        "bidder_user_ids": list(bidder_ids),
        "watchlist_user_ids": list(watch_ids),
    }


async def _queue_notification_emails(
    db,
    listing_id: str,
    listing_title: str,
    old_end_time: Optional[datetime],
    new_end_time: datetime,
    recipients: dict,
):
    """Insert one row per recipient into email_outbox; safe-no-op if mongo write fails."""
    now = datetime.now(timezone.utc)
    context_base = {
        "listing_id": listing_id,
        "listing_title": listing_title or "",
        "old_end_time": old_end_time.isoformat() if isinstance(old_end_time, datetime) else (old_end_time or ""),
        "new_end_time": new_end_time.isoformat(),
    }

    rows = []
    # Seller row
    if recipients.get("seller_id"):
        rows.append({
            "id":         str(uuid.uuid4()),
            "kind":       "auction_end_time_changed_seller",
            "to_user_id": recipients["seller_id"],
            "context":    context_base,
            "queued_at":  now,
        })
    # Bidder rows (active + outbid)
    for uid in recipients.get("bidder_user_ids", []):
        rows.append({
            "id":         str(uuid.uuid4()),
            "kind":       "auction_end_time_changed_bidder",
            "to_user_id": uid,
            "context":    context_base,
            "queued_at":  now,
        })
    # Watchlist rows
    for uid in recipients.get("watchlist_user_ids", []):
        rows.append({
            "id":         str(uuid.uuid4()),
            "kind":       "auction_end_time_changed_watchlist",
            "to_user_id": uid,
            "context":    context_base,
            "queued_at":  now,
        })
    if rows:
        try:
            await db.email_outbox.insert_many(rows)
        except Exception as exc:
            logger.warning(f"[end_time] email_outbox.insert_many failed: {exc}")

    # In-app notifications collection (cheap mirror)
    if rows:
        try:
            await db.notifications.insert_many([{
                "id":         r["id"],
                "user_id":    r["to_user_id"],
                "type":       "auction_end_time_changed",
                "title_en":   "Auction end time updated by admin",
                "title_fr":   "Heure de fin de l'enchère mise à jour par l'administrateur",
                "message_en": f"The end time of '{listing_title}' has been changed to {new_end_time.isoformat()}.",
                "message_fr": f"L'heure de fin de l'enchère « {listing_title} » a été modifiée pour {new_end_time.isoformat()}.",
                "context":    r["context"],
                "read":       False,
                "created_at": now,
            } for r in rows])
        except Exception as exc:
            logger.warning(f"[end_time] notifications.insert_many failed: {exc}")


@admin_end_time_router.patch("/admin/auctions/{listing_id}/end-time")
async def admin_update_auction_end_time(
    listing_id: str,
    payload: EndTimeUpdate,
    current_user: User = Depends(require_admin),
):
    """Update the end time of an auction. Validates future time, status,
    writes audit log, and queues notifications. Returns updated metadata."""
    db = get_db()
    collection, doc = await _resolve_collection(db, listing_id)

    status = (doc.get("status") or "").lower()
    if status in {"closed", "settled", "ended", "completed", "archived", "rejected"}:
        raise HTTPException(status_code=400, detail={
            "error": "auction_closed",
            "message_en": f"Cannot edit end time — auction status is '{status}'.",
            "message_fr": f"Impossible de modifier l'heure de fin — le statut de l'enchère est « {status} ».",
        })

    # Normalise new_end_time to UTC-aware
    new_end = payload.new_end_time
    if new_end.tzinfo is None:
        new_end = new_end.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if new_end <= now:
        raise HTTPException(status_code=400, detail={
            "error": "end_time_in_past",
            "message_en": "New end time must be in the future.",
            "message_fr": "La nouvelle heure de fin doit être dans le futur.",
        })

    old_end = doc.get("auction_end_date") or doc.get("end_time")
    if isinstance(old_end, str):
        try:
            old_end = datetime.fromisoformat(old_end)
        except Exception:
            old_end = None

    # iter290 — Different collections store the end timestamp under
    # different field names. Update both so reads from any code path
    # see the new value.
    end_field_writes = {
        "auction_end_date":        new_end,
        "end_time":                new_end,
        "end_time_last_edited_by": current_user.email,
        "end_time_last_edited_at": now,
    }
    # Update the auction
    await db[collection].update_one(
        {"id": listing_id},
        {"$set": end_field_writes},
    )

    # Audit log
    audit_row = {
        "id":                   str(uuid.uuid4()),
        "action":               "admin_edit_auction_end_time",
        "listing_id":           listing_id,
        "collection":           collection,
        "admin_id":             current_user.id,
        "admin_email":          current_user.email,
        "old_end_time":         old_end.isoformat() if isinstance(old_end, datetime) else (old_end or None),
        "new_end_time":         new_end.isoformat(),
        "reason":               (payload.reason or "").strip()[:500],
        "timestamp":            now,
    }
    try:
        await db.auction_end_time_audit.insert_one(audit_row)
    except Exception as exc:
        logger.warning(f"[end_time] audit insert failed: {exc}")
    # Also mirror into the generic admin_logs collection for the existing admin log viewer
    try:
        await db.admin_logs.insert_one({
            "id":           audit_row["id"],
            "action":       audit_row["action"],
            "admin_email":  audit_row["admin_email"],
            "admin_id":     audit_row["admin_id"],
            "details":      {
                "listing_id":     listing_id,
                "old_end_time":   audit_row["old_end_time"],
                "new_end_time":   audit_row["new_end_time"],
                "reason":         audit_row["reason"],
            },
            "timestamp":    now.isoformat(),
        })
    except Exception:
        pass

    # Recipients + emails + in-app notifications
    recipients = await _collect_notification_recipients(db, listing_id, doc.get("seller_id", ""))
    await _queue_notification_emails(
        db,
        listing_id=listing_id,
        listing_title=doc.get("title", ""),
        old_end_time=old_end,
        new_end_time=new_end,
        recipients=recipients,
    )

    logger.info(
        f"[end_time] admin={current_user.email} listing={listing_id} "
        f"{audit_row['old_end_time']} → {audit_row['new_end_time']} "
        f"notified_bidders={len(recipients['bidder_user_ids'])} "
        f"notified_watchers={len(recipients['watchlist_user_ids'])}"
    )
    return {
        "success":       True,
        "listing_id":    listing_id,
        "collection":    collection,
        "old_end_time":  audit_row["old_end_time"],
        "new_end_time":  new_end.isoformat(),
        "notified": {
            "seller":     1 if recipients["seller_id"] else 0,
            "bidders":    len(recipients["bidder_user_ids"]),
            "watchlist":  len(recipients["watchlist_user_ids"]),
        },
    }


@admin_end_time_router.get("/admin/auctions/{listing_id}/end-time-history")
async def admin_get_end_time_history(
    listing_id: str,
    current_user: User = Depends(require_admin),
):
    """Returns all end-time edit audit rows for an auction (most recent first)."""
    db = get_db()
    cursor = db.auction_end_time_audit.find(
        {"listing_id": listing_id},
        {"_id": 0},
    ).sort("timestamp", -1)
    rows = await cursor.to_list(length=200)
    # ISO-ify any datetime fields
    for r in rows:
        ts = r.get("timestamp")
        if isinstance(ts, datetime):
            r["timestamp"] = ts.isoformat()
    return {"listing_id": listing_id, "history": rows}
