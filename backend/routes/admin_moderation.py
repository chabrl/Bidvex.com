"""
routes/admin_moderation.py — iter299 P1

Marketplace Listings Moderation panel.

New listings from non-trusted sellers land in `pending_review`
(see services.listings_service.resolve_listing_status). Admins
approve (→ active + seller email/notification + seller becomes
trusted) or reject with a reason (→ rejected + seller email with
the reason + notification).

Vehicle listings keep their own dedicated review pipeline
(AI watchdog / dealer compliance) — they are NOT handled here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)
moderation_router = APIRouter(prefix="/admin/moderation", tags=["admin-moderation"])

_PENDING_STATUSES = ["pending", "pending_review"]
_COLLECTIONS = (("listings", "marketplace"), ("multi_item_listings", "lots"))


class RejectPayload(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


async def _resolve_pending(db, listing_id: str):
    for coll_name, section in _COLLECTIONS:
        doc = await db[coll_name].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return coll_name, section, doc
    return None, None, None


@moderation_router.get("/count")
async def pending_count(admin: User = Depends(require_admin)):
    """Badge count for the admin nav."""
    db = get_db()
    total = 0
    for coll_name, _ in _COLLECTIONS:
        total += await db[coll_name].count_documents({"status": {"$in": _PENDING_STATUSES}})
    return {"pending_review": total}


@moderation_router.get("/pending")
async def pending_listings(admin: User = Depends(require_admin)):
    db = get_db()
    rows = []
    for coll_name, section in _COLLECTIONS:
        docs = await db[coll_name].find(
            {"status": {"$in": _PENDING_STATUSES}},
            {"_id": 0, "id": 1, "title": 1, "title_fr": 1, "category": 1,
             "starting_price": 1, "current_price": 1, "images": 1,
             "seller_id": 1, "created_at": 1, "region": 1, "city": 1,
             "description": 1, "status": 1},
        ).sort("created_at", -1).to_list(200)
        for d in docs:
            d["section"] = section
            rows.append(d)

    # Enrich with seller identity.
    seller_ids = list({r.get("seller_id") for r in rows if r.get("seller_id")})
    sellers = {}
    if seller_ids:
        docs = await db.users.find(
            {"id": {"$in": seller_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "province": 1, "trusted_seller": 1},
        ).to_list(len(seller_ids))
        sellers = {u["id"]: u for u in docs}
    for r in rows:
        s = sellers.get(r.get("seller_id")) or {}
        r["seller_name"] = s.get("name")
        r["seller_email"] = s.get("email")
        r["seller_province"] = s.get("province")

    rows.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return {"listings": rows, "total": len(rows)}


@moderation_router.post("/{listing_id}/approve")
async def approve_listing(listing_id: str, admin: User = Depends(require_admin)):
    db = get_db()
    coll_name, section, doc = await _resolve_pending(db, listing_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    if doc.get("status") not in _PENDING_STATUSES:
        raise HTTPException(status_code=409, detail=f"Listing is not pending review (status={doc.get('status')})")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db[coll_name].update_one(
        {"id": listing_id},
        {"$set": {"status": "active", "approved_at": now_iso,
                  "approved_by": admin.id, "updated_at": now_iso}},
    )

    # First approval makes the seller trusted — future listings go live
    # directly (admin can revoke the flag on the user).
    seller_id = doc.get("seller_id")
    if seller_id:
        await db.users.update_one(
            {"id": seller_id, "trusted_seller": {"$ne": True}},
            {"$set": {"trusted_seller": True, "trusted_seller_since": now_iso}},
        )
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0}) or {}
        if seller.get("email"):
            try:
                from services.emails.email_system import send_listing_approved_email
                await send_listing_approved_email(
                    seller=seller, listing_title=doc.get("title", "Listing"),
                    listing_id=listing_id, section=section,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[moderation] approval email failed: {e}")
        try:
            from services.notifications_i18n import create_notification
            await create_notification(
                db, user_id=seller_id, kind="listing_approved",
                params={"title": doc.get("title", "Listing")},
                data={"listing_id": listing_id,
                      "action_url": f"/listing/{listing_id}" if section == "marketplace" else f"/lots/{listing_id}"},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[moderation] approval notification failed: {e}")

    try:
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()
    except Exception:  # noqa: BLE001
        pass
    logger.info(f"[moderation] {listing_id} APPROVED by {admin.email}")
    return {"success": True, "listing_id": listing_id, "status": "active"}


@moderation_router.post("/{listing_id}/reject")
async def reject_listing(listing_id: str, payload: RejectPayload,
                         admin: User = Depends(require_admin)):
    db = get_db()
    coll_name, section, doc = await _resolve_pending(db, listing_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    if doc.get("status") not in _PENDING_STATUSES:
        raise HTTPException(status_code=409, detail=f"Listing is not pending review (status={doc.get('status')})")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db[coll_name].update_one(
        {"id": listing_id},
        {"$set": {"status": "rejected", "rejected_at": now_iso,
                  "rejected_by": admin.id,
                  "rejection_reason": payload.reason.strip(),
                  "updated_at": now_iso}},
    )

    seller_id = doc.get("seller_id")
    if seller_id:
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0}) or {}
        if seller.get("email"):
            try:
                from services.emails.email_system import send_listing_rejected_email
                await send_listing_rejected_email(
                    seller=seller, listing_title=doc.get("title", "Listing"),
                    listing_id=listing_id, reason=payload.reason.strip(),
                    section=section,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[moderation] rejection email failed: {e}")
        try:
            from services.notifications_i18n import create_notification
            await create_notification(
                db, user_id=seller_id, kind="listing_rejected",
                params={"title": doc.get("title", "Listing"),
                        "reason": payload.reason.strip()},
                data={"listing_id": listing_id, "action_url": "/seller/dashboard"},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[moderation] rejection notification failed: {e}")

    logger.info(f"[moderation] {listing_id} REJECTED by {admin.email}: {payload.reason[:80]}")
    return {"success": True, "listing_id": listing_id, "status": "rejected"}
