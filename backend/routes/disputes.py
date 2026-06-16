"""
routes/disputes.py — iter300 P1 Dispute Resolution

Buyer/seller side:
  GET  /api/disputes/eligibility/{listing_id}   can current user file? (7-day window)
  POST /api/disputes/file                       file a dispute on a payment_collected listing
  GET  /api/disputes/my                         my disputes (as buyer or seller)

Admin side:
  GET  /api/admin/disputes?status=open|escalated|resolved|all
  POST /api/admin/disputes/{dispute_id}/resolve   {action: release_to_seller|refund_buyer, note}
  POST /api/admin/disputes/{dispute_id}/escalate  {note}
  POST /api/admin/disputes/{dispute_id}/note      {note}   internal admin-only note

Collection: `disputes`
  {id, listing_id, collection, section, listing_title, buyer_id, seller_id,
   filed_by, filed_by_role, reason_category, details, hammer_price,
   status: open|escalated|resolved, outcome, resolution_note,
   internal_notes: [{by, by_email, at, text}], created_at, resolved_at}
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db, require_admin

logger = logging.getLogger(__name__)
disputes_router = APIRouter(tags=["disputes"])

ADMIN_EMAIL = "charbel911@gmail.com"
DISPUTE_WINDOW_DAYS = 7
REASON_CATEGORIES = {"item_not_as_described", "no_contact_from_seller", "payment_issue", "other"}

# Sections that use the generic dispute flow (vehicles have their own
# settlement-dispute pipeline in routes/vehicle_settlement.py).
_COLLECTION_BY_SECTION = {
    "marketplace": "listings",
    "lots": "multi_item_listings",
    "storage": "storage_auctions",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(v) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


class FileDisputePayload(BaseModel):
    listing_id: str
    section: str = "marketplace"
    reason_category: str
    details: str = Field(default="", max_length=2000)


class ResolvePayload(BaseModel):
    action: str  # release_to_seller | refund_buyer
    note: str = Field(min_length=5, max_length=2000)


class NotePayload(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


async def _find_listing(db, listing_id: str, section: str):
    coll = _COLLECTION_BY_SECTION.get(section)
    if coll:
        doc = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return coll, doc
    # fall back: scan generic collections
    for coll in _COLLECTION_BY_SECTION.values():
        doc = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return coll, doc
    return None, None


def _close_dt(listing) -> Optional[datetime]:
    return (_parse(listing.get("sold_at")) or _parse(listing.get("ended_at"))
            or _parse(listing.get("payment_collected_at"))
            or _parse(listing.get("auction_end_date")) or _parse(listing.get("end_time")))


def _eligibility(listing, user_id, existing) -> dict:
    buyer_id = (listing.get("winner_id") or listing.get("winner_user_id")
                or listing.get("winning_bidder_id"))
    seller_id = listing.get("seller_id") or listing.get("facility_owner_id")
    is_party = user_id in (buyer_id, seller_id)
    payment_collected = listing.get("payment_status") == "payment_collected"
    closed = _close_dt(listing)
    within_window = bool(closed and _now() <= closed + timedelta(days=DISPUTE_WINDOW_DAYS))
    return {
        "eligible": bool(is_party and payment_collected and within_window and not existing),
        "is_party": is_party,
        "role": "buyer" if user_id == buyer_id else ("seller" if user_id == seller_id else None),
        "payment_collected": payment_collected,
        "within_window": within_window,
        "window_closes_at": (closed + timedelta(days=DISPUTE_WINDOW_DAYS)).isoformat() if closed else None,
        "already_disputed": bool(existing),
        "dispute_id": (existing or {}).get("id"),
        "dispute_status": (existing or {}).get("status"),
    }


@disputes_router.get("/disputes/eligibility/{listing_id}")
async def dispute_eligibility(listing_id: str, section: str = "marketplace",
                              current_user: User = Depends(get_current_user)):
    db = get_db()
    _, listing = await _find_listing(db, listing_id, section)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    existing = await db.disputes.find_one(
        {"listing_id": listing_id, "status": {"$in": ["open", "escalated", "resolved"]}},
        {"_id": 0, "id": 1, "status": 1})
    return _eligibility(listing, current_user.id, existing)


@disputes_router.post("/disputes/file")
async def file_dispute(payload: FileDisputePayload,
                       current_user: User = Depends(get_current_user)):
    db = get_db()
    if payload.reason_category not in REASON_CATEGORIES:
        raise HTTPException(status_code=422, detail="Invalid reason category")
    coll, listing = await _find_listing(db, payload.listing_id, payload.section)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    existing = await db.disputes.find_one(
        {"listing_id": payload.listing_id, "status": {"$in": ["open", "escalated"]}},
        {"_id": 0, "id": 1, "status": 1})
    elig = _eligibility(listing, current_user.id, existing)
    if not elig["is_party"]:
        raise HTTPException(status_code=403, detail="Only the buyer or seller of this transaction can file a dispute")
    if existing:
        raise HTTPException(status_code=409, detail="A dispute is already open for this listing")
    if not elig["payment_collected"]:
        raise HTTPException(status_code=400, detail="Disputes can only be filed on payment-collected transactions")
    if not elig["within_window"]:
        raise HTTPException(status_code=400, detail=f"The {DISPUTE_WINDOW_DAYS}-day dispute window has closed")

    buyer_id = (listing.get("winner_id") or listing.get("winner_user_id")
                or listing.get("winning_bidder_id"))
    seller_id = listing.get("seller_id") or listing.get("facility_owner_id")
    hammer = float(listing.get("final_price") or listing.get("current_price") or 0)
    now_iso = _now().isoformat()
    dispute = {
        "id": str(uuid.uuid4()),
        "listing_id": payload.listing_id,
        "collection": coll,
        "section": payload.section,
        "listing_title": listing.get("title") or "Item",
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "filed_by": current_user.id,
        "filed_by_role": elig["role"],
        "reason_category": payload.reason_category,
        "details": payload.details.strip(),
        "hammer_price": hammer,
        "payment_transaction_id": listing.get("payment_transaction_id"),
        "status": "open",
        "outcome": None,
        "internal_notes": [],
        "created_at": now_iso,
    }
    await db.disputes.insert_one({**dispute})
    await db[coll].update_one(
        {"id": payload.listing_id},
        {"$set": {"dispute_status": "disputed", "dispute_id": dispute["id"],
                  "disputed_at": now_iso}})

    # ── Notifications + emails (best-effort) ──
    from services.notifications_i18n import create_notification
    users = {}
    async for u in db.users.find({"id": {"$in": [x for x in (buyer_id, seller_id) if x]}},
                                 {"_id": 0, "id": 1, "email": 1, "name": 1}):
        users[u["id"]] = u
    try:
        from services.emails.email_disputes import (
            send_dispute_ack_email, send_dispute_admin_alert_email,
        )
        for party_id in (buyer_id, seller_id):
            if not party_id:
                continue
            party = users.get(party_id) or {}
            await create_notification(
                db, user_id=party_id, kind="dispute_received",
                params={"title": dispute["listing_title"]},
                data={"listing_id": payload.listing_id, "dispute_id": dispute["id"]})
            if party.get("email"):
                await send_dispute_ack_email(
                    to_email=party["email"], to_name=party.get("name") or "User",
                    listing_title=dispute["listing_title"],
                    reason_key=payload.reason_category, details=payload.details,
                    is_filer=(party_id == current_user.id))
        # Admin alert
        admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0, "id": 1, "email": 1})
        if admin:
            await create_notification(
                db, user_id=admin["id"], kind="dispute_filed_admin",
                params={"title": dispute["listing_title"],
                        "filer": getattr(current_user, "name", None) or current_user.email},
                data={"dispute_id": dispute["id"], "listing_id": payload.listing_id,
                      "action_url": "/admin?tab=disputed-settlements"})
        await send_dispute_admin_alert_email(
            to_email=ADMIN_EMAIL, listing_title=dispute["listing_title"],
            filer_name=getattr(current_user, "name", None) or current_user.email,
            filer_role=elig["role"] or "party",
            reason_key=payload.reason_category, details=payload.details,
            hammer_price=hammer, dispute_id=dispute["id"])
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[disputes] notification fan-out failed: {e}")

    logger.info(f"[disputes] FILED {dispute['id']} on {payload.listing_id} by {current_user.email}")
    dispute.pop("internal_notes", None)  # never expose to parties
    return {"success": True, "dispute": dispute}


@disputes_router.get("/disputes/my")
async def my_disputes(current_user: User = Depends(get_current_user)):
    db = get_db()
    rows = await db.disputes.find(
        {"$or": [{"buyer_id": current_user.id}, {"seller_id": current_user.id}]},
        {"_id": 0, "internal_notes": 0},  # internal notes are admin-only
    ).sort("created_at", -1).to_list(100)
    return {"disputes": rows, "total": len(rows)}


# ───────────────────────── ADMIN ─────────────────────────

@disputes_router.get("/admin/disputes/queue")
async def admin_list_disputes(status: str = "open",
                              admin: User = Depends(require_admin)):
    """iter300 dispute queue. NOTE: path is /admin/disputes/queue because the
    legacy iter264 oversight API owns GET /admin/disputes (test-locked)."""
    db = get_db()
    query = {} if status == "all" else (
        {"status": {"$in": ["open", "escalated"]}} if status == "open"
        else {"status": status})
    rows = await db.disputes.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    user_ids = {x for r in rows for x in (r.get("buyer_id"), r.get("seller_id")) if x}
    users = {}
    if user_ids:
        async for u in db.users.find({"id": {"$in": list(user_ids)}},
                                     {"_id": 0, "id": 1, "name": 1, "email": 1}):
            users[u["id"]] = u
    for r in rows:
        r["buyer_name"] = (users.get(r.get("buyer_id")) or {}).get("name") or "—"
        r["buyer_email"] = (users.get(r.get("buyer_id")) or {}).get("email")
        r["seller_name"] = (users.get(r.get("seller_id")) or {}).get("name") or "—"
        r["seller_email"] = (users.get(r.get("seller_id")) or {}).get("email")
    open_count = await db.disputes.count_documents({"status": {"$in": ["open", "escalated"]}})
    return {"disputes": rows, "total": len(rows), "open_count": open_count}


async def _load_dispute_or_404(db, dispute_id: str):
    d = await db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return d


async def _notify_resolution(db, dispute, outcome: str, note: str):
    from services.notifications_i18n import create_notification
    try:
        from services.emails.email_disputes import send_dispute_resolved_email
        for party_id in (dispute.get("buyer_id"), dispute.get("seller_id")):
            if not party_id:
                continue
            await create_notification(
                db, user_id=party_id, kind="dispute_resolved",
                params={"title": dispute["listing_title"], "outcome": outcome},
                data={"dispute_id": dispute["id"], "listing_id": dispute["listing_id"]})

            # iter306 — Web Push
            try:
                from services.push_dispatcher import dispatch_push
                await dispatch_push(
                    db, user_id=party_id, kind="dispute_resolved",
                    title_item=dispute["listing_title"], outcome=outcome,
                    listing_id=dispute["listing_id"],
                    url=f"/disputes/{dispute['id']}",
                )
            except Exception:
                pass

            party = await db.users.find_one({"id": party_id}, {"_id": 0, "email": 1, "name": 1})
            if party and party.get("email"):
                await send_dispute_resolved_email(
                    to_email=party["email"], to_name=party.get("name") or "User",
                    listing_title=dispute["listing_title"], outcome=outcome, note=note)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[disputes] resolution notify failed: {e}")


@disputes_router.post("/admin/disputes/{dispute_id}/resolve")
async def admin_resolve_dispute(dispute_id: str, payload: ResolvePayload,
                                admin: User = Depends(require_admin)):
    if payload.action not in {"release_to_seller", "refund_buyer"}:
        raise HTTPException(status_code=422, detail="action must be release_to_seller or refund_buyer")
    db = get_db()
    dispute = await _load_dispute_or_404(db, dispute_id)
    if dispute.get("status") not in ("open", "escalated"):
        raise HTTPException(status_code=409, detail=f"Dispute is already {dispute.get('status')}")

    now_iso = _now().isoformat()
    refund_id = None

    if payload.action == "refund_buyer":
        pi = dispute.get("payment_transaction_id")
        if pi:
            try:
                import stripe
                stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
                refund = stripe.Refund.create(
                    payment_intent=pi,
                    metadata={"dispute_id": dispute_id, "listing_id": dispute["listing_id"]})
                refund_id = refund.id
            except Exception as e:  # noqa: BLE001
                raise HTTPException(status_code=502, detail=f"Stripe refund failed: {e}")
        # Stamp the listing + cancel any pending payout
        await db[dispute["collection"]].update_one(
            {"id": dispute["listing_id"]},
            {"$set": {"payment_status": "refunded", "refunded_at": now_iso,
                      "dispute_status": "resolved_refunded", "stripe_refund_id": refund_id}})
        await db.pending_payouts.update_many(
            {"listing_id": dispute["listing_id"], "status": "payout_pending"},
            {"$set": {"status": "cancelled_dispute_refund", "updated_at": now_iso}})
    else:  # release_to_seller
        await db[dispute["collection"]].update_one(
            {"id": dispute["listing_id"]},
            {"$set": {"dispute_status": "resolved_released"}})
        await db.pending_payouts.update_many(
            {"listing_id": dispute["listing_id"], "status": "payout_pending"},
            {"$set": {"status": "payout_approved", "approved_by": admin.id,
                      "updated_at": now_iso}})

    await db.disputes.update_one(
        {"id": dispute_id},
        {"$set": {"status": "resolved", "outcome": payload.action,
                  "resolution_note": payload.note.strip(),
                  "stripe_refund_id": refund_id,
                  "resolved_at": now_iso, "resolved_by": admin.id}})
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()), "action": f"dispute_{payload.action}",
        "target_type": "dispute", "target_id": dispute_id,
        "actor_id": admin.id, "actor_email": admin.email,
        "timestamp": now_iso, "notes": payload.note})
    await _notify_resolution(db, dispute, payload.action, payload.note)
    logger.info(f"[disputes] RESOLVED {dispute_id} → {payload.action} by {admin.email}")
    return {"success": True, "status": "resolved", "outcome": payload.action,
            "stripe_refund_id": refund_id}


@disputes_router.post("/admin/disputes/{dispute_id}/escalate")
async def admin_escalate_dispute(dispute_id: str, payload: NotePayload,
                                 admin: User = Depends(require_admin)):
    db = get_db()
    dispute = await _load_dispute_or_404(db, dispute_id)
    if dispute.get("status") == "resolved":
        raise HTTPException(status_code=409, detail="Dispute is already resolved")
    now_iso = _now().isoformat()
    await db.disputes.update_one(
        {"id": dispute_id},
        {"$set": {"status": "escalated", "escalated_at": now_iso,
                  "escalated_by": admin.id},
         "$push": {"internal_notes": {"by": admin.id, "by_email": admin.email,
                                      "at": now_iso, "text": payload.note.strip(),
                                      "kind": "escalation"}}})
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "dispute_escalated",
        "target_type": "dispute", "target_id": dispute_id,
        "actor_id": admin.id, "actor_email": admin.email,
        "timestamp": now_iso, "notes": payload.note})
    return {"success": True, "status": "escalated"}


@disputes_router.post("/admin/disputes/{dispute_id}/note")
async def admin_add_dispute_note(dispute_id: str, payload: NotePayload,
                                 admin: User = Depends(require_admin)):
    db = get_db()
    await _load_dispute_or_404(db, dispute_id)
    now_iso = _now().isoformat()
    await db.disputes.update_one(
        {"id": dispute_id},
        {"$push": {"internal_notes": {"by": admin.id, "by_email": admin.email,
                                      "at": now_iso, "text": payload.note.strip(),
                                      "kind": "note"}}})
    return {"success": True}
