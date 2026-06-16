"""
iter307 — Admin Compliance Dashboard (single page, 5 stacked sections).

Endpoints (all under /api/admin/compliance, admin-only):

  GET    /flagged-listings              Section 1 — AI Watchdog flagged
  POST   /flagged-listings/{id}/approve Approve & Exempt (watchdog_exempt=true)
  POST   /flagged-listings/{id}/reject  Remove + notify seller

  GET    /bidding-suspended             Section 2 — bidding-suspended users
  POST   /bidding-suspended/{user_id}/reinstate

  GET    /overdue-payments              Section 3 — transactions w/ overdue or final-failed payments
  POST   /overdue-payments/{listing_id}/retry        Stripe charge retry
  POST   /overdue-payments/{listing_id}/mark-resolved
  POST   /overdue-payments/{listing_id}/flag-account Suspend buyer bidding

  GET    /escalated-disputes            Section 4 — disputes in `escalated`
  POST   /escalated-disputes/{dispute_id}/note      Add admin note

  GET    /bill96-violations             Section 5 — QC listings missing title_fr
  POST   /bill96-violations/{listing_id}/notify     Send "fix within 48h or auto-suspend" email

Bill 96 auto-suspend (after 48h with no fix) is wired into the scheduler
in server.py (job: `bill96_autosuspend_sweep`).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

compliance_router = APIRouter(prefix="/admin/compliance", tags=["admin", "compliance"])

_LISTING_COLLECTIONS = [
    ("listings", "marketplace"),
    ("multi_item_listings", "lots"),
    ("storage_auctions", "storage"),
    ("vehicle_listings", "vehicles"),
]


def _require_admin(current_user: User) -> None:
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _log_admin_action(db, current_user: User, action: str, **payload):
    try:
        await db.admin_action_logs.insert_one({
            "ts": _now().isoformat(),
            "admin_id": current_user.id,
            "admin_email": getattr(current_user, "email", "") or "",
            "admin_name": getattr(current_user, "name", "") or "",
            "action": action,
            **payload,
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[compliance] action log failed ({action}): {e}")


# ─────────────────────────────────────────────────────────────────────
# Section 1 — AI Watchdog Flagged Listings
# ─────────────────────────────────────────────────────────────────────

@compliance_router.get("/flagged-listings")
async def list_flagged(current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    items: List[Dict[str, Any]] = []
    for coll, section in _LISTING_COLLECTIONS:
        cursor = db[coll].find(
            {"watchdog_flagged": True, "watchdog_exempt": {"$ne": True}},
            {"_id": 0, "id": 1, "title": 1, "seller_id": 1, "seller_name": 1,
             "watchdog_flag_reason": 1, "watchdog_flagged_at": 1, "created_at": 1},
        ).sort("watchdog_flagged_at", -1).limit(200)
        async for d in cursor:
            d["section"] = section
            items.append(d)
    return {"items": items, "total": len(items)}


@compliance_router.post("/flagged-listings/{listing_id}/approve")
async def approve_flagged(listing_id: str, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    updated = 0
    for coll, _ in _LISTING_COLLECTIONS:
        r = await db[coll].update_one(
            {"id": listing_id},
            {"$set": {"watchdog_exempt": True, "watchdog_reviewed_at": _now().isoformat(),
                      "watchdog_reviewed_by": current_user.id}},
        )
        if r.matched_count:
            updated = 1
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Listing not found")
    await _log_admin_action(db, current_user, "watchdog_approve_exempt", listing_id=listing_id)
    return {"success": True}


@compliance_router.post("/flagged-listings/{listing_id}/reject")
async def reject_flagged(listing_id: str, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    listing_doc = None
    target_coll = None
    for coll, _ in _LISTING_COLLECTIONS:
        d = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if d:
            listing_doc, target_coll = d, coll
            break
    if not listing_doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db[target_coll].update_one(
        {"id": listing_id},
        {"$set": {"status": "removed_by_admin", "removed_at": _now().isoformat(),
                  "removed_by": current_user.id, "watchdog_reviewed_at": _now().isoformat()}},
    )
    # Notify seller (best-effort bilingual bell notification)
    try:
        from services.notifications_i18n import create_notification
        await create_notification(
            db, user_id=listing_doc.get("seller_id"), kind="listing_removed_by_watchdog",
            params={"title": listing_doc.get("title", "Listing"),
                    "reason": listing_doc.get("watchdog_flag_reason", "policy violation")},
            data={"listing_id": listing_id},
        )
    except Exception:
        pass
    await _log_admin_action(db, current_user, "watchdog_reject_remove", listing_id=listing_id)
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────
# Section 2 — Bidding-Suspended Users
# ─────────────────────────────────────────────────────────────────────

@compliance_router.get("/bidding-suspended")
async def list_bidding_suspended(current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    cursor = db.users.find(
        {"bidding_suspended": True},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "province": 1,
         "bidding_suspended_reason": 1, "bidding_suspended_at": 1,
         "bidding_suspension_count": 1},
    ).sort("bidding_suspended_at", -1).limit(500)
    items = await cursor.to_list(500)
    return {"items": items, "total": len(items)}


@compliance_router.post("/bidding-suspended/{user_id}/reinstate")
async def reinstate_user(user_id: str, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    r = await db.users.update_one(
        {"id": user_id},
        {"$set": {"bidding_suspended": False, "bidding_reinstated_at": _now().isoformat(),
                  "bidding_reinstated_by": current_user.id},
         "$unset": {"bidding_suspended_reason": ""}},
    )
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="User not found")
    await _log_admin_action(db, current_user, "bidding_reinstate", target_user_id=user_id)
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────
# Section 3 — Overdue Payments
# ─────────────────────────────────────────────────────────────────────

_OVERDUE_STATUSES = ("payment_overdue", "payment_failed_final")


@compliance_router.get("/overdue-payments")
async def list_overdue_payments(current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    items: List[Dict[str, Any]] = []
    for coll, section in _LISTING_COLLECTIONS:
        cursor = db[coll].find(
            {"$or": [
                {"status": {"$in": list(_OVERDUE_STATUSES)}},
                {"payment_status": {"$in": list(_OVERDUE_STATUSES)}},
            ]},
            {"_id": 0, "id": 1, "title": 1, "winner_id": 1, "buyer_id": 1,
             "final_price": 1, "hammer_price": 1, "current_price": 1,
             "payment_status": 1, "status": 1, "payment_overdue_at": 1,
             "auto_charge_retry_count": 1, "ended_at": 1},
        ).sort("payment_overdue_at", -1).limit(300)
        async for d in cursor:
            d["section"] = section
            items.append(d)
    return {"items": items, "total": len(items)}


@compliance_router.post("/overdue-payments/{listing_id}/retry")
async def retry_overdue_payment(listing_id: str, current_user: User = Depends(get_current_user)):
    """Trigger an immediate Stripe off-session re-charge of the saved card.

    Uses the same code path as the scheduled auto-charge, just invoked
    on-demand by the admin.
    """
    _require_admin(current_user)
    db = get_db()
    try:
        from services.payments import auto_charge_listing
    except Exception:
        # Fallback if the service isn't available — defer to manual marking
        raise HTTPException(status_code=501, detail="Auto-charge service unavailable")
    try:
        result = await auto_charge_listing(db, listing_id, triggered_by="admin_retry")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[compliance] retry charge failed {listing_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    await _log_admin_action(db, current_user, "overdue_retry_charge",
                            listing_id=listing_id, result=str(result)[:200])
    return {"success": True, "result": result}


@compliance_router.post("/overdue-payments/{listing_id}/mark-resolved")
async def mark_overdue_resolved(listing_id: str, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    for coll, _ in _LISTING_COLLECTIONS:
        r = await db[coll].update_one(
            {"id": listing_id},
            {"$set": {"payment_status": "payment_collected_manual",
                      "status": "payment_collected",
                      "payment_resolved_manually_at": _now().isoformat(),
                      "payment_resolved_by": current_user.id}},
        )
        if r.matched_count:
            await _log_admin_action(db, current_user, "overdue_mark_resolved", listing_id=listing_id)
            return {"success": True}
    raise HTTPException(status_code=404, detail="Listing not found")


@compliance_router.post("/overdue-payments/{listing_id}/flag-account")
async def flag_buyer_account(listing_id: str, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    listing_doc = None
    for coll, _ in _LISTING_COLLECTIONS:
        d = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if d:
            listing_doc = d
            break
    if not listing_doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    buyer_id = listing_doc.get("winner_id") or listing_doc.get("buyer_id")
    if not buyer_id:
        raise HTTPException(status_code=400, detail="No buyer to flag")
    await db.users.update_one(
        {"id": buyer_id},
        {"$set": {"bidding_suspended": True,
                  "bidding_suspended_at": _now().isoformat(),
                  "bidding_suspended_reason": f"Non-payment on listing {listing_doc.get('title','')}",
                  "bidding_suspended_by": current_user.id},
         "$inc": {"bidding_suspension_count": 1}},
    )
    await _log_admin_action(db, current_user, "overdue_flag_buyer",
                            listing_id=listing_id, buyer_id=buyer_id)
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────
# Section 4 — Escalated Disputes
# ─────────────────────────────────────────────────────────────────────

@compliance_router.get("/escalated-disputes")
async def list_escalated_disputes(current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    cursor = db.disputes.find(
        {"status": "escalated"},
        {"_id": 0},
    ).sort("escalated_at", -1).limit(200)
    items = await cursor.to_list(200)
    return {"items": items, "total": len(items)}


@compliance_router.post("/escalated-disputes/{dispute_id}/note")
async def add_dispute_note(dispute_id: str, payload: Dict[str, Any],
                            current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    note = (payload.get("note") or "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="Note is required")
    db = get_db()
    r = await db.disputes.update_one(
        {"id": dispute_id},
        {"$push": {"admin_notes": {
            "ts": _now().isoformat(),
            "admin_id": current_user.id,
            "admin_name": getattr(current_user, "name", "") or "",
            "note": note[:2000],
        }}},
    )
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Dispute not found")
    await _log_admin_action(db, current_user, "dispute_add_note", dispute_id=dispute_id)
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────
# Section 5 — Bill 96 Violations (QC listings missing title_fr)
# ─────────────────────────────────────────────────────────────────────

@compliance_router.get("/bill96-violations")
async def list_bill96_violations(current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    items: List[Dict[str, Any]] = []
    for coll, section in _LISTING_COLLECTIONS:
        cursor = db[coll].find(
            {
                "province": "QC",
                "status": {"$in": ["active", "pending_review", "pending"]},
                "$or": [
                    {"title_fr": {"$exists": False}},
                    {"title_fr": None},
                    {"title_fr": ""},
                ],
            },
            {"_id": 0, "id": 1, "title": 1, "seller_id": 1, "seller_name": 1,
             "created_at": 1, "bill96_notified_at": 1},
        ).sort("created_at", -1).limit(200)
        async for d in cursor:
            d["section"] = section
            items.append(d)
    return {"items": items, "total": len(items)}


@compliance_router.post("/bill96-violations/{listing_id}/notify")
async def notify_bill96_violation(listing_id: str, current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    db = get_db()
    listing_doc = None
    target_coll = None
    for coll, _ in _LISTING_COLLECTIONS:
        d = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if d:
            listing_doc, target_coll = d, coll
            break
    if not listing_doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    seller_id = listing_doc.get("seller_id")
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1, "name": 1}) if seller_id else None
    if not seller or not seller.get("email"):
        raise HTTPException(status_code=400, detail="Seller has no email on file")

    title = listing_doc.get("title", "your listing")
    edit_url = f"{os.environ.get('PUBLIC_HOST', 'https://bidvex.com').rstrip('/')}/listings/{listing_id}/edit"
    subject = "Action required: Bill 96 — French title needed within 48h / Action requise : Loi 96 — titre français requis sous 48 h"
    body = (
        f"Hello {seller.get('name','')},\n\n"
        f"Your Quebec listing '{title}' is missing a French title (`title_fr`).\n"
        f"Bill 96 (Charter of the French Language) requires bilingual product descriptions for QC sellers.\n"
        f"Please add a French title within 48 hours, otherwise this listing will be automatically suspended.\n\n"
        f"Edit the listing here: {edit_url}\n\n"
        f"— BidVex Compliance\n\n"
        f"— — —\n\n"
        f"Bonjour {seller.get('name','')},\n\n"
        f"Votre annonce au Québec « {title} » n'a pas de titre français (`title_fr`).\n"
        f"La Loi 96 (Charte de la langue française) exige des descriptions bilingues pour les vendeurs QC.\n"
        f"Veuillez ajouter un titre français dans les 48 heures, sinon cette annonce sera automatiquement suspendue.\n\n"
        f"Modifier l'annonce ici : {edit_url}\n\n"
        f"— Conformité BidVex\n"
    )
    try:
        from services.emails._email_core import send_email
        html_body = body.replace("\n", "<br>")
        await send_email(to_email=seller["email"], subject=subject, html_content=html_body)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[compliance] bill96 notify email failed for {listing_id}: {e}")

    await db[target_coll].update_one(
        {"id": listing_id},
        {"$set": {"bill96_notified_at": _now().isoformat(),
                  "bill96_notified_by": current_user.id}},
    )
    await _log_admin_action(db, current_user, "bill96_notify_seller",
                            listing_id=listing_id, seller_email=seller["email"])
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────
# Auto-suspend sweep (called from scheduled jobs in server.py)
# ─────────────────────────────────────────────────────────────────────

async def bill96_autosuspend_sweep(db) -> int:
    """Auto-suspend Bill 96 violations notified > 48h ago and still missing title_fr.

    Returns count of newly-suspended listings.
    """
    cutoff_iso = (_now() - timedelta(hours=48)).isoformat()
    suspended = 0
    for coll, _ in _LISTING_COLLECTIONS:
        async for doc in db[coll].find(
            {
                "province": "QC",
                "status": {"$in": ["active", "pending_review", "pending"]},
                "bill96_notified_at": {"$lt": cutoff_iso},
                "$or": [
                    {"title_fr": {"$exists": False}},
                    {"title_fr": None},
                    {"title_fr": ""},
                ],
            },
            {"_id": 0, "id": 1, "seller_id": 1, "title": 1},
        ):
            await db[coll].update_one(
                {"id": doc["id"]},
                {"$set": {"status": "suspended_bill96",
                          "suspended_at": _now().isoformat(),
                          "suspension_reason": "Bill 96 — missing French title (48h notice elapsed)"}},
            )
            suspended += 1
            try:
                from services.notifications_i18n import create_notification
                await create_notification(
                    db, user_id=doc.get("seller_id"),
                    kind="listing_suspended_bill96",
                    params={"title": doc.get("title", "Listing")},
                    data={"listing_id": doc["id"]},
                )
            except Exception:
                pass
    return suspended
