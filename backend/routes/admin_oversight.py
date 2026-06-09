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
    return await execute_compliance_scan(db)


async def execute_compliance_scan(db) -> Dict[str, Any]:
    """iter265 Mission 5 — Callable compliance scan, used by both the
    admin HTTP endpoint and the APScheduler daily cron at 06:00 UTC."""
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
    section: Optional[str] = Query(
        None,
        description="Optional filter — marketplace | vehicle | storage | lots",
    ),
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """
    iter290 — Multi-collection admin auctions panel. The old endpoint
    only walked `db.listings`, hiding every vehicle / storage / lot
    auction from the Manage All Auctions screen. Now we aggregate
    every collection an admin needs to oversee:

      • db.listings              → "marketplace"
      • db.vehicle_listings      → "vehicle"
      • db.storage_auctions      → "storage"
      • db.multi_item_listings   → "lots"

    Each row is tagged with `_section` and `_collection` so the
    frontend can render the right badge + route the View / Edit /
    delete CTAs at the proper detail page + collection.
    """
    _require_admin(current_user)
    db = get_db()

    # ── Build a per-collection query. Search has to map onto the
    # field names each collection actually uses (vehicles store the
    # display string under `make` + `model`, storage under
    # `unit_number` + `facility_name`, etc.). ────────────────────
    q_base: Dict[str, Any] = {}
    if status:
        q_base["status"] = status
    if category:
        q_base["category"] = category
    safe_search = (search or "").strip()[:80]

    def _q_with_search(searchable_fields: List[str]) -> Dict[str, Any]:
        q = dict(q_base)
        if safe_search:
            q["$or"] = [
                {f: {"$regex": safe_search, "$options": "i"}}
                for f in searchable_fields
            ]
        return q

    SECTION_SPECS = [
        ("marketplace",       "listings",                    ["title", "category"]),
        ("vehicle",           "vehicle_listings",            ["title", "make", "model", "vin"]),
        ("storage",           "storage_auctions",            ["unit_number", "facility_name", "facility_city"]),
        ("lots",              "multi_item_listings",         ["title", "category"]),
        # iter293 — Multi-Lot Vehicle Auction events surface here so
        # admins can pause / cancel / inspect the whole sequence and
        # individual lots from the central oversight panel.
        ("vehicle_multi_lot", "vehicle_multi_lot_auctions",  ["title"]),
    ]
    # Optional section filter — keep the list ordered + idempotent.
    if section:
        section_norm = {"vehicles": "vehicle"}.get(section.lower().strip(), section.lower().strip())
        SECTION_SPECS = [s for s in SECTION_SPECS if s[0] == section_norm]

    # ── Walk every collection, tag each doc, and merge. ─────────
    merged: List[Dict[str, Any]] = []
    for sec, coll_name, searchable in SECTION_SPECS:
        try:
            cursor = db[coll_name].find(
                _q_with_search(searchable),
                {
                    "_id": 0, "id": 1, "title": 1, "seller_id": 1, "created_by": 1,
                    "category": 1, "current_price": 1, "starting_price": 1,
                    "current_bid": 1,
                    "auction_end_time": 1, "auction_end_date": 1, "end_time": 1,
                    "status": 1, "is_promoted": 1, "bid_count": 1,
                    "created_at": 1, "auction_start": 1, "quantity": 1,
                    # Section-specific display fields for the table row.
                    "make": 1, "model": 1, "year": 1, "vin": 1,                # vehicle
                    "unit_number": 1, "facility_name": 1, "facility_city": 1,   # storage
                },
            )
            docs = await cursor.to_list(length=1000)
        except Exception:
            docs = []  # Collection may not exist yet — never block the panel.

        for doc in docs:
            doc["_section"]    = sec
            doc["_collection"] = coll_name
            # Vehicles/storage rarely have a `title` — synthesize one
            # so the UI row never renders an empty cell.
            if not doc.get("title"):
                if sec == "vehicle":
                    parts = [str(doc.get("year") or ""), doc.get("make") or "", doc.get("model") or ""]
                    doc["title"] = " ".join(p for p in parts if p).strip() or "Vehicle Listing"
                elif sec == "storage":
                    doc["title"] = (
                        f"Storage Unit #{doc.get('unit_number') or '—'} · "
                        f"{doc.get('facility_name') or doc.get('facility_city') or 'Facility'}"
                    )
            merged.append(doc)

    # Sort newest-first across collections.
    def _sort_key(it: Dict[str, Any]):
        return str(it.get("created_at") or it.get("auction_start") or "")
    merged.sort(key=_sort_key, reverse=True)

    total = len(merged)
    page  = max(1, int(page))
    limit = max(1, min(100, int(limit)))
    skip  = (page - 1) * limit
    items = merged[skip:skip + limit]

    # ── Single sellers lookup across the merged page. ───────────
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
    """
    iter290 — Cross-collection action dispatcher. End / extend /
    feature / remove now resolve the source collection and update
    the right table so vehicle + storage + lot rows respond to the
    admin Manage All Auctions panel actions.
    """
    _require_admin(current_user)
    db = get_db()

    # ── Resolve which collection owns this listing id. ──────────
    COLLECTIONS = [
        ("listings",            "marketplace"),
        ("vehicle_listings",    "vehicle"),
        ("storage_auctions",    "storage"),
        ("multi_item_listings", "lots"),
    ]
    doc = None
    coll_name = None
    for name, _sec in COLLECTIONS:
        try:
            d = await db[name].find_one({"id": listing_id}, {"_id": 0})
        except Exception:
            d = None
        if d:
            doc = d
            coll_name = name
            break
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found in any collection")

    now = datetime.now(timezone.utc)
    update: Dict[str, Any] = {}
    if body.action == "end":
        update["status"] = "ended"
        update["auction_end_time"] = now.isoformat()
        update["ended_by_admin"] = current_user.id
    elif body.action == "extend":
        if not body.extend_hours:
            raise HTTPException(status_code=400, detail="extend_hours required")
        raw_end = doc.get("auction_end_time") or doc.get("auction_end_date") or doc.get("end_time")
        try:
            current_end = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00")) if raw_end else now
        except Exception:
            current_end = now
        new_end = max(current_end, now) + timedelta(hours=int(body.extend_hours))
        update["auction_end_time"] = new_end.isoformat()
        update["auction_end_date"] = new_end.isoformat()
        # Vehicle / storage collections track the end in `end_time`.
        update["end_time"] = new_end.isoformat()
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

    await db[coll_name].update_one({"id": listing_id}, {"$set": update})
    return {
        "success":    True,
        "id":         listing_id,
        "collection": coll_name,
        "applied":    update,
    }


# ─── iter265 Mission 2 — Live email test endpoint ────────────────────

@admin_oversight_router.get("/test-email")
async def admin_test_email(
    to: Optional[str] = Query(None, description="Recipient (defaults to current admin)"),
    type: str = Query("transactional", description="transactional | marketing | partner"),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """iter265 Mission 2 — Send a live test email through the unified
    SendGrid pipeline. Verifies:
      • `SENDGRID_API_KEY` is configured
      • `build_email_payload()` renders correctly
      • SendGrid returns a 202 (live send) or fallback `logged`

    iter270 — Now accepts a `type` parameter so admins can confirm
    each of the three classification paths (transactional / marketing /
    partner) lands correctly. The unified pipeline applies the
    appropriate Reply-To, categories, and List-Unsubscribe header.
    """
    _require_admin(current_user)
    recipient = (to or getattr(current_user, "email", "")).strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="No recipient email available")

    import os
    sg_key = os.environ.get("SENDGRID_API_KEY") or ""
    sg_configured = bool(sg_key) and sg_key != "SG.your-actual-sendgrid-key-here"

    flavor = (type or "transactional").lower().strip()
    if flavor not in ("transactional", "marketing", "partner"):
        flavor = "transactional"

    if flavor == "marketing":
        subject = "🎉 BidVex SendGrid Live Test — Marketing"
        body_html = (
            "<p>This is a <strong>marketing</strong> test email.</p>"
            "<p>It should arrive in your Gmail Promotions tab with a "
            "List-Unsubscribe header and a <code>marketing</code> + "
            "<code>promotional</code> SendGrid category.</p>"
            "<p style='font-size:11px;color:#666;text-align:center;margin-top:24px;'>"
            "BidVex Inc. | Sherbrooke, QC, Canada<br>"
            "You received this email because you registered on BidVex.<br>"
            f"<a href='https://bidvex.com/unsubscribe?email={recipient}' style='color:#666;'>"
            "Unsubscribe / Se désabonner</a></p>"
        )
        send_kwargs = {
            "is_marketing": True,
            "reply_to": "support@bidvex.com",
            "reply_to_name": "BidVex Support",
            "categories": ["marketing", "promotional", "iter270-test"],
        }
    elif flavor == "partner":
        subject = "🤝 BidVex SendGrid Live Test — Partner"
        body_html = (
            "<p>This is a <strong>partner</strong> test email.</p>"
            "<p>From: <code>noreply@bidvex.com</code> · Reply-To: "
            "<code>partners@bidvex.ca</code>.</p>"
        )
        send_kwargs = {
            "is_marketing": True,
            "reply_to": "partners@bidvex.ca",
            "reply_to_name": "BidVex Partner Team",
            "from_name": "BidVex Canada",
            "categories": ["partner", "marketing", "iter270-test"],
        }
    else:
        subject = "✅ BidVex SendGrid Live Test — Transactional"
        body_html = (
            "<p>This is a <strong>transactional</strong> test email.</p>"
            "<p>From: <code>noreply@bidvex.com</code> · Reply-To: "
            "<code>support@bidvex.com</code> · Category: <code>transactional</code>.</p>"
        )
        send_kwargs = {
            "reply_to": "support@bidvex.com",
            "reply_to_name": "BidVex Support",
            "categories": ["transactional", "iter270-test"],
        }

    try:
        from services.email_notifications import send_unified_email
        result = await send_unified_email(
            email_type="new_feature",
            user={"email": recipient, "first_name": "Admin", "name": "Admin"},
            data={
                "subject_override": subject,
                "headline": "SendGrid Live Test",
                "subheadline": "End-to-end pipeline verified.",
                "body_html": body_html,
                "cta_label": "Open BidVex",
                "cta_url": "https://bidvex.com",
            },
            **send_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[test-email] dispatch failed: {exc}")
        raise HTTPException(status_code=500, detail=f"dispatch error: {exc}") from exc

    return {
        "success": (result or {}).get("status") in ("sent", "logged"),
        "type": flavor,
        "sendgrid_configured": sg_configured,
        "from_email": os.environ.get("SENDGRID_FROM_EMAIL"),
        "to": recipient,
        "result": result,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── iter266 Mission 1 — Affiliate Payouts oversight tab ─────────────


class AffiliatePayoutReject(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


def _payout_status_normalize(s: Any) -> str:
    s = (str(s or "pending")).strip().lower()
    if s in ("approved", "paid"):
        return "paid"
    if s in ("rejected", "denied"):
        return "rejected"
    return "pending"


async def _enrich_payouts(db, payouts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Hydrate each payout row with affiliate user info + referral count."""
    user_ids = list({p.get("user_id") or p.get("affiliate_id") for p in payouts if (p.get("user_id") or p.get("affiliate_id"))})
    users_by_id: Dict[str, Dict[str, Any]] = {}
    if user_ids:
        async for u in db.users.find(
            {"id": {"$in": user_ids}},
            {
                "_id": 0, "id": 1, "name": 1, "email": 1,
                "affiliate_code": 1, "preferred_language": 1,
                # iter267 Mission 1 — Stripe Connect flag for the admin UI.
                "stripe_connect_account_id": 1,
                "stripe_connect_onboarding_complete": 1,
            },
        ):
            users_by_id[u["id"]] = u
    for p in payouts:
        uid = p.get("user_id") or p.get("affiliate_id")
        u = users_by_id.get(uid, {})
        p["affiliate_name"] = u.get("name") or "Unknown"
        p["affiliate_email"] = u.get("email") or "—"
        p["affiliate_code"] = u.get("affiliate_code")
        p["status_norm"] = _payout_status_normalize(p.get("status"))
        # iter267 Mission 1 — Stripe Connect state surfaced to the UI.
        p["has_stripe_connect"] = bool(u.get("stripe_connect_account_id"))
        p["stripe_onboarding_complete"] = bool(u.get("stripe_connect_onboarding_complete"))
        # Referrals count for this affiliate.
        try:
            p["referrals_count"] = await db.affiliate_referrals.count_documents({"affiliate_id": uid})
        except Exception:
            p["referrals_count"] = 0
    return payouts


@admin_oversight_router.get("/affiliate-payouts")
async def list_affiliate_payouts(
    status: Optional[str] = Query(None),
    page: int = 1,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """iter266 Mission 1 — Affiliate payout queue + summary cards."""
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        norm = _payout_status_normalize(status)
        if norm == "paid":
            q["status"] = {"$in": ["paid", "approved"]}
        elif norm == "rejected":
            q["status"] = {"$in": ["rejected", "denied"]}
        else:
            q["status"] = {"$in": ["pending", None, ""]}
    page = max(1, int(page))
    limit = max(1, min(200, int(limit)))
    skip = (page - 1) * limit
    cursor = db.affiliate_payouts.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items: List[Dict[str, Any]] = await cursor.to_list(length=limit)
    items = await _enrich_payouts(db, items)
    total = await db.affiliate_payouts.count_documents(q)

    # ── Summary cards ──
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pending_sum_pipeline = [
        {"$match": {"status": {"$in": ["pending", None, ""]}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    paid_month_pipeline = [
        {"$match": {
            "status": {"$in": ["paid", "approved"]},
            "$or": [
                {"paid_at": {"$gte": month_start.isoformat()}},
                {"approved_at": {"$gte": month_start.isoformat()}},
            ],
        }},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    pending_total = 0.0
    paid_this_month = 0.0
    try:
        async for r in db.affiliate_payouts.aggregate(pending_sum_pipeline):
            pending_total = float(r.get("total") or 0)
        async for r in db.affiliate_payouts.aggregate(paid_month_pipeline):
            paid_this_month = float(r.get("total") or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[affiliate-payouts] summary aggregation skipped: {exc}")

    active_affiliates = 0
    try:
        active_affiliates = await db.users.count_documents({"is_affiliate": True})
        if active_affiliates == 0:
            # Fallback: count distinct users with at least one referral.
            distinct = await db.affiliate_referrals.distinct("affiliate_id")
            active_affiliates = len([d for d in distinct if d])
    except Exception:
        active_affiliates = 0

    referrals_this_month = 0
    try:
        referrals_this_month = await db.affiliate_referrals.count_documents({
            "created_at": {"$gte": month_start.isoformat()},
        })
    except Exception:
        referrals_this_month = 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "summary": {
            "pending_total_cad":   round(pending_total, 2),
            "paid_this_month_cad": round(paid_this_month, 2),
            "active_affiliates":   active_affiliates,
            "referrals_this_month": referrals_this_month,
        },
    }


@admin_oversight_router.patch("/affiliate-payouts/{payout_id}/approve")
async def approve_affiliate_payout(
    payout_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """iter266 Mission 1 — Approve a pending payout. Marks as paid,
    stamps paid_at, sends confirmation email to the affiliate."""
    _require_admin(current_user)
    db = get_db()
    payout = await db.affiliate_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    if _payout_status_normalize(payout.get("status")) == "paid":
        raise HTTPException(status_code=400, detail="Payout already paid")

    # iter267 Mission 1 — Fire a real Stripe Connect transfer if the
    # affiliate has linked a Connect account. If not, return a
    # spec-aligned envelope so the admin UI can prompt onboarding.
    uid = payout.get("user_id") or payout.get("affiliate_id")
    affiliate = await db.users.find_one(
        {"id": uid},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "preferred_language": 1, "stripe_connect_account_id": 1},
    ) if uid else None

    if not affiliate or not affiliate.get("stripe_connect_account_id"):
        return {
            "success": False,
            "error": "affiliate_no_stripe_connect",
            "message_en": (
                "This affiliate has not connected a Stripe account. "
                "Send them the Stripe Connect onboarding link first."
            ),
            "message_fr": (
                "Cet affilié n'a pas connecté de compte Stripe. "
                "Envoyez-lui d'abord le lien d'intégration Stripe."
            ),
            "affiliate_id": uid,
            "affiliate_email": (affiliate or {}).get("email"),
        }

    transfer_id = None
    transfer_error = None
    try:
        import stripe as _stripe  # noqa: WPS433
        amount_cents = int(round(float(payout.get("amount") or 0) * 100))
        if amount_cents <= 0:
            raise ValueError("Amount must be > 0")
        transfer = _stripe.Transfer.create(
            amount=amount_cents,
            currency=(payout.get("currency") or "cad").lower(),
            destination=affiliate["stripe_connect_account_id"],
            description=f"BidVex affiliate commission payout — {payout_id}",
            metadata={
                "payout_id": str(payout_id),
                "affiliate_user_id": str(uid),
                "approved_by": current_user.email or current_user.id,
            },
        )
        transfer_id = getattr(transfer, "id", None)
    except Exception as exc:  # noqa: BLE001
        transfer_error = str(exc)
        logger.warning(f"[affiliate-payout-approve] stripe.Transfer failed: {exc}")

    now_iso = datetime.now(timezone.utc).isoformat()
    set_fields = {
        "status":       "paid" if transfer_id else "pending",
        "approved_by":  current_user.id,
        "approved_at":  now_iso,
    }
    if transfer_id:
        set_fields["paid_at"]            = now_iso
        set_fields["stripe_transfer_id"] = transfer_id
    if transfer_error:
        set_fields["last_transfer_error"] = transfer_error
    await db.affiliate_payouts.update_one(
        {"id": payout_id},
        {"$set": set_fields},
    )

    if transfer_error:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "stripe_transfer_failed",
                "message_en": "Stripe failed to process the transfer. Please retry.",
                "message_fr": "Stripe n'a pas pu traiter le virement. Veuillez réessayer.",
                "stripe_error": transfer_error,
            },
        )

    user = affiliate  # alias used by email block below.
    if user and user.get("email"):
        try:
            from services.email_notifications import send_unified_email
            await send_unified_email(
                email_type="payment_confirmed",
                user=user,
                data={
                    "subject_override": "✅ Your BidVex Affiliate Payout Has Been Approved",
                    "headline": "Payout Approved",
                    "subheadline": "Your affiliate earnings are on the way.",
                    "body_html": (
                        f"<p>Hi {user.get('name', 'Partner')},</p>"
                        f"<p>Your affiliate payout request for <strong>${float(payout.get('amount') or 0):,.2f} "
                        f"{payout.get('currency', 'CAD')}</strong> has been <strong>approved</strong> "
                        f"and is being processed via Stripe Connect.</p>"
                        f"<p><strong>Transfer ID:</strong> <code>{transfer_id}</code></p>"
                        "<p>You will receive the funds within 1-3 business days.</p>"
                    ),
                    "cta_label": "Open Affiliate Dashboard",
                    "cta_url": "https://bidvex.com/affiliate",
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[affiliate-payout-approve] email failed: {exc}")

    return {
        "success": True,
        "id": payout_id,
        "status": "paid",
        "paid_at": now_iso,
        "stripe_transfer_id": transfer_id,
    }


@admin_oversight_router.patch("/affiliate-payouts/{payout_id}/reject")
async def reject_affiliate_payout(
    payout_id: str,
    body: AffiliatePayoutReject,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """iter266 Mission 1 — Reject a payout with a reason."""
    _require_admin(current_user)
    db = get_db()
    payout = await db.affiliate_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    if _payout_status_normalize(payout.get("status")) != "pending":
        raise HTTPException(status_code=400, detail="Only pending payouts can be rejected")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.affiliate_payouts.update_one(
        {"id": payout_id},
        {"$set": {
            "status": "rejected",
            "rejected_by": current_user.id,
            "rejected_at": now_iso,
            "rejection_reason": body.reason,
        }},
    )

    uid = payout.get("user_id") or payout.get("affiliate_id")
    user = await db.users.find_one(
        {"id": uid},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "preferred_language": 1},
    ) if uid else None
    if user and user.get("email"):
        try:
            from services.email_notifications import send_unified_email
            await send_unified_email(
                email_type="new_feature",
                user=user,
                data={
                    "subject_override": "BidVex Affiliate Payout Update",
                    "headline": "Payout Request Update",
                    "subheadline": "We were unable to process your payout.",
                    "body_html": (
                        f"<p>Hi {user.get('name', 'Partner')},</p>"
                        f"<p>Your recent affiliate payout request for <strong>"
                        f"${float(payout.get('amount') or 0):,.2f} {payout.get('currency', 'CAD')}</strong> "
                        "could not be processed.</p>"
                        f"<p><strong>Reason:</strong> {body.reason}</p>"
                        "<p>Please reach out to <a href='mailto:support@bidvex.com'>support@bidvex.com</a> "
                        "if you'd like to discuss this decision.</p>"
                    ),
                    "cta_label": "Open Affiliate Dashboard",
                    "cta_url": "https://bidvex.com/affiliate",
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[affiliate-payout-reject] email failed: {exc}")

    return {"success": True, "id": payout_id, "status": "rejected", "rejected_at": now_iso, "reason": body.reason}


# ─── iter268 Mission 1 — Re-issue a failed/reversed Stripe transfer ──

@admin_oversight_router.post("/affiliate-payouts/{payout_id}/reissue")
async def reissue_affiliate_payout(
    payout_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """iter268 Mission 1 — Create a fresh Stripe Transfer for the same
    amount when the original one was `failed` or `reversed`."""
    _require_admin(current_user)
    db = get_db()
    payout = await db.affiliate_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    prev_status = (payout.get("stripe_transfer_status") or "").lower()
    if prev_status not in ("failed", "reversed"):
        raise HTTPException(
            status_code=400,
            detail=f"Only failed/reversed transfers can be reissued (was: {prev_status or 'none'})",
        )

    uid = payout.get("user_id") or payout.get("affiliate_id")
    affiliate = await db.users.find_one(
        {"id": uid},
        {"_id": 0, "stripe_connect_account_id": 1},
    ) if uid else None
    connect_id = (affiliate or {}).get("stripe_connect_account_id")
    if not connect_id:
        raise HTTPException(status_code=400, detail="Affiliate has no Stripe Connect account")

    try:
        import stripe as _stripe  # noqa: WPS433
        amount_cents = int(round(float(payout.get("amount") or 0) * 100))
        if amount_cents <= 0:
            raise ValueError("Amount must be > 0")
        transfer = _stripe.Transfer.create(
            amount=amount_cents,
            currency=(payout.get("currency") or "cad").lower(),
            destination=connect_id,
            description=f"BidVex affiliate payout RE-ISSUE — {payout_id}",
            metadata={
                "payout_id": str(payout_id),
                "reissue_of": payout.get("stripe_transfer_id") or "",
                "affiliate_user_id": str(uid),
                "reissued_by": current_user.email or current_user.id,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[affiliate-payout-reissue] stripe.Transfer failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}") from exc

    now_iso = datetime.now(timezone.utc).isoformat()
    history = list(payout.get("stripe_transfer_history") or [])
    if payout.get("stripe_transfer_id"):
        history.append({
            "transfer_id": payout.get("stripe_transfer_id"),
            "status":      payout.get("stripe_transfer_status"),
            "reason":      payout.get("stripe_transfer_failure_reason"),
            "ended_at":    now_iso,
        })

    await db.affiliate_payouts.update_one(
        {"id": payout_id},
        {"$set": {
            "stripe_transfer_id":             transfer.id,
            "stripe_transfer_status":         "created",
            "stripe_transfer_updated_at":     now_iso,
            "stripe_transfer_failure_reason": None,
            "stripe_transfer_history":        history,
            "status":                         "paid",
            "reissued_by":                    current_user.id,
            "reissued_at":                    now_iso,
        }},
    )
    return {
        "success":            True,
        "id":                 payout_id,
        "stripe_transfer_id": transfer.id,
        "status":             "paid",
        "stripe_transfer_status": "created",
    }



# ─── iter267 Mission 1 — Email a Stripe Connect onboarding link to an affiliate ──

@admin_oversight_router.post("/affiliates/{user_id}/send-stripe-onboarding")
async def send_stripe_onboarding_link(
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """iter267 Mission 1 — Used when admin tries to approve a payout
    but the affiliate has no Stripe Connect account. Creates an Express
    account + AccountLink and sends the affiliate an email."""
    _require_admin(current_user)
    db = get_db()
    affiliate = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "stripe_connect_account_id": 1, "preferred_language": 1},
    )
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    if not affiliate.get("email"):
        raise HTTPException(status_code=400, detail="Affiliate has no email on file")

    try:
        import stripe as _stripe  # noqa: WPS433
        connect_id = affiliate.get("stripe_connect_account_id")
        if not connect_id:
            account = _stripe.Account.create(
                type="express",
                country="CA",
                email=affiliate["email"],
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers":     {"requested": True},
                },
                business_type="individual",
                metadata={"user_id": user_id, "platform": "bidvex", "source": "admin_payout_request"},
            )
            connect_id = account.id
            await db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "stripe_connect_account_id": connect_id,
                    "stripe_connect_onboarding_complete": False,
                    "is_affiliate": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )

        base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://bidvex.com")
        link = _stripe.AccountLink.create(
            account=connect_id,
            refresh_url=f"{base_url}/affiliate?stripe_refresh=true",
            return_url=f"{base_url}/affiliate?stripe=connected",
            type="account_onboarding",
            collection_options={"fields": "eventually_due"},
        )
        onboarding_url = link.url
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[stripe-onboarding] account/link create failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}") from exc

    try:
        from services.email_notifications import send_unified_email
        await send_unified_email(
            email_type="new_feature",
            user=affiliate,
            data={
                "subject_override": "💰 Connect Your Stripe Account to Receive BidVex Payouts",
                "headline": "Connect Stripe to Get Paid",
                "subheadline": "One quick step to receive your affiliate commissions.",
                "body_html": (
                    f"<p>Hi {affiliate.get('name', 'Partner')},</p>"
                    "<p>You've earned affiliate commissions on BidVex! Before we can transfer "
                    "your funds we need you to set up a Stripe Express account — it takes "
                    "less than 2 minutes.</p>"
                    f"<p>Click the secure link below to complete onboarding. The link expires "
                    f"in a few hours; you can request a fresh one anytime from your "
                    f"<a href='{base_url}/affiliate'>Affiliate Dashboard</a>.</p>"
                ),
                "cta_label": "Connect Stripe Account →",
                "cta_url":   onboarding_url,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[stripe-onboarding] email send failed: {exc}")

    return {
        "success":        True,
        "affiliate_id":   user_id,
        "onboarding_url": onboarding_url,
        "stripe_connect_account_id": connect_id,
    }


import os  # noqa: E402 — kept low to avoid top-of-file churn.


__all__ = ["admin_oversight_router", "public_disputes_router", "execute_compliance_scan"]
