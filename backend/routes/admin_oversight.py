"""
iter264 Mission 4 — Admin oversight surfaces.

Three thin admin sections that the UI screenshots referenced but were
never fully implemented as generic admin tabs:

  • DISPUTES (generic — different from broker_invoice disputes which
    live in broker_compliance.py). A buyer-facing "Report a Dispute"
    pipeline against any listing/order.
  • COMPLIANCE ALERTS — system-generated warnings (vehicle without
    broker, high-value listing with unverified seller, runaway unpaid
    bids). Admins resolve from a single table.
  • MANAGE ALL AUCTIONS — cross-platform listings table with End Now /
    Extend / Feature / Remove actions.

All endpoints under `/api/admin/...`. Collections (auto-created on
first write per the global constraints):
  - `disputes`
  - `compliance_alerts`
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

admin_oversight_router = APIRouter(prefix="/admin", tags=["Admin Oversight"])
public_disputes_router = APIRouter(tags=["Disputes (public)"])


def _require_admin(user: User) -> None:
    if getattr(user, "role", None) != "admin" and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")


# ─── DISPUTES ────────────────────────────────────────────────────────

_DISPUTE_STATUSES = ("open", "under_review", "resolved", "closed")


class DisputeCreate(BaseModel):
    listing_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=4, max_length=2000)
    seller_id: Optional[str] = None


class DisputePatch(BaseModel):
    status: Literal["open", "under_review", "resolved", "closed"]
    resolution_notes: Optional[str] = Field(None, max_length=4000)


@public_disputes_router.post("/disputes")
async def file_dispute(
    body: DisputeCreate,
    current_user: User = Depends(get_current_user),
):
    """Authenticated buyer files a dispute against a listing/order."""
    db = get_db()
    listing = await db.listings.find_one({"id": body.listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "listing_id": body.listing_id,
        "buyer_id": current_user.id,
        "seller_id": body.seller_id or listing.get("seller_id") or listing.get("created_by"),
        "reason": body.reason.strip(),
        "status": "open",
        "created_at": now,
        "resolved_at": None,
        "resolution_notes": None,
        "admin_id": None,
    }
    await db.disputes.insert_one(doc)
    return {"success": True, "id": doc["id"], "status": doc["status"]}


@admin_oversight_router.get("/disputes")
async def list_disputes(
    status: Optional[str] = Query(None),
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if status and status in _DISPUTE_STATUSES:
        q["status"] = status
    page = max(1, int(page))
    limit = max(1, min(100, int(limit)))
    skip = (page - 1) * limit
    cursor = db.disputes.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items: List[Dict[str, Any]] = await cursor.to_list(length=limit)
    total = await db.disputes.count_documents(q)
    # Hydrate buyer/seller emails so the admin table renders one-shot.
    user_ids = list({u for it in items for u in (it.get("buyer_id"), it.get("seller_id")) if u})
    user_map: Dict[str, Dict[str, Any]] = {}
    if user_ids:
        async for u in db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "email": 1, "name": 1}):
            user_map[u["id"]] = u
    listing_ids = list({it.get("listing_id") for it in items if it.get("listing_id")})
    listing_map: Dict[str, Dict[str, Any]] = {}
    if listing_ids:
        async for li in db.listings.find({"id": {"$in": listing_ids}}, {"_id": 0, "id": 1, "title": 1}):
            listing_map[li["id"]] = li
    for it in items:
        it["buyer"] = user_map.get(it.get("buyer_id")) or {}
        it["seller"] = user_map.get(it.get("seller_id")) or {}
        it["listing_title"] = (listing_map.get(it.get("listing_id")) or {}).get("title") or "—"
    return {"items": items, "total": total, "page": page, "limit": limit}


@admin_oversight_router.patch("/disputes/{dispute_id}")
async def patch_dispute(
    dispute_id: str,
    body: DisputePatch,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    doc = await db.disputes.find_one({"id": dispute_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dispute not found")
    update: Dict[str, Any] = {
        "status": body.status,
        "admin_id": current_user.id,
    }
    if body.resolution_notes is not None:
        update["resolution_notes"] = body.resolution_notes
    if body.status == "resolved":
        update["resolved_at"] = datetime.now(timezone.utc).isoformat()
    await db.disputes.update_one({"id": dispute_id}, {"$set": update})
    return {"success": True, "id": dispute_id, "status": body.status}


# ─── COMPLIANCE ALERTS ───────────────────────────────────────────────

class ComplianceAlertCreate(BaseModel):
    type: str = Field(..., min_length=2, max_length=80)
    listing_id: Optional[str] = None
    user_id: Optional[str] = None
    description: str = Field(..., min_length=4, max_length=2000)
    severity: Literal["low", "medium", "high"] = "medium"


async def _create_alert(db, *, type_: str, description: str, **fields) -> str:
    """Internal helper for system-generated alerts (called from scan)."""
    doc = {
        "id": str(uuid.uuid4()),
        "type": type_,
        "description": description,
        "severity": fields.pop("severity", "medium"),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        **fields,
    }
    await db.compliance_alerts.insert_one(doc)
    return doc["id"]


@admin_oversight_router.get("/compliance-alerts")
async def list_compliance_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if status in ("open", "resolved"):
        q["status"] = status
    if severity in ("low", "medium", "high"):
        q["severity"] = severity
    page = max(1, int(page))
    limit = max(1, min(100, int(limit)))
    skip = (page - 1) * limit
    cursor = db.compliance_alerts.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.compliance_alerts.count_documents(q)
    open_count = await db.compliance_alerts.count_documents({"status": "open"})
    return {"items": items, "total": total, "open_count": open_count, "page": page, "limit": limit}


@admin_oversight_router.patch("/compliance-alerts/{alert_id}/resolve")
async def resolve_compliance_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    doc = await db.compliance_alerts.find_one({"id": alert_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.compliance_alerts.update_one(
        {"id": alert_id},
        {"$set": {
            "status": "resolved",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": current_user.id,
        }},
    )
    return {"success": True, "id": alert_id, "status": "resolved"}


@admin_oversight_router.post("/compliance-alerts/scan")
async def run_compliance_scan(current_user: User = Depends(get_current_user)):
    """Idempotent scan that surfaces the 3 spec-rules as alerts.
    Re-running the scan does NOT duplicate alerts — we keep one open
    alert per (type, listing_id|user_id) pair."""
    _require_admin(current_user)
    db = get_db()
    created = 0

    # Rule 1 — Vehicle listing without a broker assigned.
    async for v in db.listings.find(
        {
            "listing_type": {"$in": ["vehicle", "vehicle_auction"]},
            "status": "active",
            "$or": [
                {"assigned_broker_id": {"$in": [None, ""]}},
                {"assigned_broker_id": {"$exists": False}},
            ],
        },
        {"_id": 0, "id": 1, "title": 1},
    ):
        existing = await db.compliance_alerts.find_one({
            "type": "vehicle_without_broker",
            "listing_id": v["id"],
            "status": "open",
        })
        if not existing:
            await _create_alert(
                db,
                type_="vehicle_without_broker",
                description=f"Vehicle listing '{v.get('title', '')[:80]}' has no assigned broker.",
                listing_id=v["id"],
                severity="high",
            )
            created += 1

    # Rule 2 — High-value listing with unverified seller.
    async for li in db.listings.find(
        {
            "status": "active",
            "$or": [
                {"current_price": {"$gt": 10_000}},
                {"starting_price": {"$gt": 10_000}},
            ],
        },
        {"_id": 0, "id": 1, "title": 1, "seller_id": 1, "created_by": 1},
    ):
        seller_id = li.get("seller_id") or li.get("created_by")
        if not seller_id:
            continue
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "is_verified": 1})
        if seller and not seller.get("is_verified"):
            existing = await db.compliance_alerts.find_one({
                "type": "high_value_unverified_seller",
                "listing_id": li["id"],
                "status": "open",
            })
            if not existing:
                await _create_alert(
                    db,
                    type_="high_value_unverified_seller",
                    description=f"Listing '{li.get('title', '')[:80]}' is >$10K but seller is not verified.",
                    listing_id=li["id"],
                    user_id=seller_id,
                    severity="medium",
                )
                created += 1

    # Rule 3 — User with > 10 unpaid winning bids.
    pipeline = [
        {"$match": {"status": "won", "is_paid": {"$ne": True}}},
        {"$group": {"_id": "$winner_id", "n": {"$sum": 1}}},
        {"$match": {"n": {"$gt": 10}}},
    ]
    try:
        async for row in db.bids.aggregate(pipeline):
            uid = row["_id"]
            if not uid:
                continue
            existing = await db.compliance_alerts.find_one({
                "type": "runaway_unpaid_bids",
                "user_id": uid,
                "status": "open",
            })
            if not existing:
                await _create_alert(
                    db,
                    type_="runaway_unpaid_bids",
                    description=f"User has {row['n']} unpaid winning bids — risk of non-payment pattern.",
                    user_id=uid,
                    severity="medium",
                )
                created += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[compliance-scan] rule 3 aggregation skipped: {exc}")

    return {"created": created}


# ─── MANAGE ALL AUCTIONS ─────────────────────────────────────────────

class AdminAuctionAction(BaseModel):
    action: Literal["end", "extend", "feature", "remove"]
    extend_hours: Optional[int] = Field(None, ge=1, le=720)


@admin_oversight_router.get("/auctions")
async def list_admin_auctions(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if category:
        q["category"] = category
    if search:
        q["title"] = {"$regex": search.strip()[:80], "$options": "i"}
    page = max(1, int(page))
    limit = max(1, min(100, int(limit)))
    skip = (page - 1) * limit
    cursor = db.listings.find(
        q,
        {
            "_id": 0, "id": 1, "title": 1, "seller_id": 1, "created_by": 1,
            "category": 1, "current_price": 1, "starting_price": 1,
            "auction_end_time": 1, "auction_end_date": 1, "status": 1,
            "is_promoted": 1, "bid_count": 1,
        },
    ).sort("created_at", -1).skip(skip).limit(limit)
    items: List[Dict[str, Any]] = await cursor.to_list(length=limit)
    total = await db.listings.count_documents(q)

    seller_ids = list({it.get("seller_id") or it.get("created_by") for it in items if (it.get("seller_id") or it.get("created_by"))})
    seller_map: Dict[str, Dict[str, Any]] = {}
    if seller_ids:
        async for u in db.users.find({"id": {"$in": seller_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}):
            seller_map[u["id"]] = u
    for it in items:
        sid = it.get("seller_id") or it.get("created_by")
        it["seller"] = seller_map.get(sid) or {}
    return {"items": items, "total": total, "page": page, "limit": limit}


@admin_oversight_router.patch("/auctions/{listing_id}/action")
async def patch_admin_auction(
    listing_id: str,
    body: AdminAuctionAction,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    doc = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")

    now = datetime.now(timezone.utc)
    update: Dict[str, Any] = {}
    if body.action == "end":
        update["status"] = "ended"
        update["auction_end_time"] = now.isoformat()
        update["ended_by_admin"] = current_user.id
    elif body.action == "extend":
        if not body.extend_hours:
            raise HTTPException(status_code=400, detail="extend_hours required")
        raw_end = doc.get("auction_end_time") or doc.get("auction_end_date")
        try:
            current_end = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00")) if raw_end else now
        except Exception:
            current_end = now
        new_end = max(current_end, now) + timedelta(hours=int(body.extend_hours))
        update["auction_end_time"] = new_end.isoformat()
        update["auction_end_date"] = new_end.isoformat()
    elif body.action == "feature":
        update["is_promoted"] = True
        sections = doc.get("promotion_sections") or []
        if "marketplace" not in sections:
            sections = list(sections) + ["marketplace"]
        update["promotion_sections"] = sections
        update["promoted_at"] = now.isoformat()
    elif body.action == "remove":
        update["status"] = "removed"
        update["removed_by_admin"] = current_user.id
        update["removed_at"] = now.isoformat()
    await db.listings.update_one({"id": listing_id}, {"$set": update})
    return {"success": True, "id": listing_id, "applied": update}


__all__ = ["admin_oversight_router", "public_disputes_router"]
