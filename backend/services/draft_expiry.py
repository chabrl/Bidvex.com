"""
iter312 D3 — Universal Draft Expiry Scheduler

Drafts are not permanent. This module sweeps all listing collections
daily and:
  • At day 23 (7 days before expiry) — emails the seller a reminder +
    drops an in-app notification so the listing doesn't disappear without
    warning.
  • At day 30 — soft-archives the draft (sets status='draft_expired'
    + archived_at) so seller dashboards no longer count it but a future
    admin can restore it if needed (no hard delete to keep audit trail).

Countdown anchor: `updated_at` (or `created_at` when updated_at missing).
Editing a draft resets the clock because every PUT/PATCH bumps
`updated_at`. This matches the directive: "drafts being actively
worked on should not expire out from under someone".

Applies to:
  • listings (Marketplace)
  • multi_item_listings (Lots / Multi-Item)
  • vehicle_listings (Vehicle single)
  • vehicle_multi_lot_auctions (Vehicle multi-lot)
  • storage_auctions (Storage)

Scheduler job is registered from services.scheduler:run_daily_jobs.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone


logger = logging.getLogger(__name__)


DRAFT_COLLECTIONS = (
    "listings",
    "multi_item_listings",
    "vehicle_listings",
    "vehicle_multi_lot_auctions",
    "storage_auctions",
)

DRAFT_WARNING_DAYS = 23   # 7 days before expiry
DRAFT_MAX_AGE_DAYS = 30


def _draft_age_anchor(doc: dict) -> datetime | None:
    """Return the timestamp from which we compute draft age."""
    for k in ("updated_at", "created_at"):
        v = doc.get(k)
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, str):
            try:
                d = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return None


async def _warn_seller(db, doc: dict, days_left: int) -> None:
    """Drop an in-app notification + queue a bilingual email."""
    now = datetime.now(timezone.utc)
    seller_id = doc.get("seller_id")
    title = (doc.get("title") or "(untitled draft)")[:120]
    if not seller_id:
        return
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1, "preferred_language": 1})
    if not seller:
        return
    # In-app notification (idempotent — keyed on listing_id + warning marker)
    notif_id = f"draft-expiry-warn-{doc.get('id')}"
    await db.notifications.update_one(
        {"id": notif_id},
        {
            "$setOnInsert": {
                "id":           notif_id,
                "user_id":      seller_id,
                "kind":         "draft_expiry_warning",
                "title_en":     f"Your draft '{title}' expires in {days_left} day(s)",
                "title_fr":     f"Votre brouillon « {title} » expire dans {days_left} jour(s)",
                "body_en":      "Publish it now or it will be archived automatically.",
                "body_fr":      "Publiez-le maintenant ou il sera archivé automatiquement.",
                "link":         f"/seller/dashboard?listing={doc.get('id')}",
                "is_read":      False,
                "created_at":   now,
                "listing_id":   doc.get("id"),
            }
        },
        upsert=True,
    )
    # Email outbox (drained by SendGrid worker)
    await db.email_outbox.insert_one({
        "id":         str(uuid.uuid4()),
        "kind":       "draft_expiry_warning",
        "to_email":   seller.get("email"),
        "context":    {
            "seller_id":  seller_id,
            "listing_id": doc.get("id"),
            "title":      title,
            "days_left":  days_left,
        },
        "queued_at":  now,
    })
    # Idempotent marker on the listing itself.
    await db[doc["__collection"]].update_one(
        {"id": doc["id"]},
        {"$set": {"draft_expiry_warning_sent_at": now, "draft_expiry_warning_days": days_left}},
    )


async def _archive_draft(db, doc: dict) -> None:
    """Soft-archive: status='draft_expired', archived_at=now."""
    now = datetime.now(timezone.utc)
    await db[doc["__collection"]].update_one(
        {"id": doc["id"]},
        {"$set": {
            "status":             "draft_expired",
            "draft_expired_at":   now,
            "archived":           True,
        }},
    )
    # Final notification.
    seller_id = doc.get("seller_id")
    title = (doc.get("title") or "(untitled draft)")[:120]
    if seller_id:
        await db.notifications.insert_one({
            "id":         str(uuid.uuid4()),
            "user_id":    seller_id,
            "kind":       "draft_expired",
            "title_en":   f"Your draft '{title}' has expired",
            "title_fr":   f"Votre brouillon « {title} » a expiré",
            "body_en":    "It was archived after 30 days without publishing. Contact support to restore it.",
            "body_fr":    "Il a été archivé après 30 jours sans publication. Contactez le support pour le restaurer.",
            "is_read":    False,
            "created_at": now,
            "listing_id": doc.get("id"),
        })
    logger.info(f"[draft_expiry] archived draft {doc.get('id')} from {doc['__collection']}")


async def run_draft_expiry_sweep(db) -> dict:
    """Public entry point invoked by the daily scheduler.

    Returns a summary counter dict for log scraping.
    """
    now = datetime.now(timezone.utc)
    warn_cutoff = now - timedelta(days=DRAFT_WARNING_DAYS)   # older than 23 days
    expire_cutoff = now - timedelta(days=DRAFT_MAX_AGE_DAYS)  # older than 30 days

    summary = {"warnings_sent": 0, "drafts_archived": 0, "scanned": 0}

    for collection in DRAFT_COLLECTIONS:
        cursor = db[collection].find(
            {"status": "draft"},
            {"_id": 0, "id": 1, "seller_id": 1, "title": 1, "created_at": 1, "updated_at": 1,
             "draft_expiry_warning_sent_at": 1},
        )
        async for doc in cursor:
            summary["scanned"] += 1
            doc["__collection"] = collection
            anchor = _draft_age_anchor(doc)
            if not anchor:
                continue
            # Archive first (more recent decisions win).
            if anchor < expire_cutoff:
                await _archive_draft(db, doc)
                summary["drafts_archived"] += 1
                continue
            # 7-day warning (idempotent — skip if already sent within last 24h).
            already_warned = doc.get("draft_expiry_warning_sent_at")
            recently_warned = (
                isinstance(already_warned, datetime)
                and (now - (already_warned if already_warned.tzinfo else already_warned.replace(tzinfo=timezone.utc))) < timedelta(days=1)
            )
            if anchor < warn_cutoff and not recently_warned:
                days_left = max(1, DRAFT_MAX_AGE_DAYS - (now - anchor).days)
                await _warn_seller(db, doc, days_left)
                summary["warnings_sent"] += 1

    logger.info(f"[draft_expiry] sweep complete: {summary}")
    return summary


__all__ = ["run_draft_expiry_sweep", "DRAFT_COLLECTIONS", "DRAFT_WARNING_DAYS", "DRAFT_MAX_AGE_DAYS"]
