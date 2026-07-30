"""
iter420 — Admin Vehicle Dealer Management
==========================================

Three capabilities under a single admin sub-tab. Reuses:
- `require_admin` from `admin_user_helpers` (auth middleware).
- `record_admin_action` for audit rows (same table other admin tabs use).
- Existing dealer / broker collections — no schema mutation.
- Existing vehicle-approve WebSocket ping (`notification_manager`) so the
  dealer's Vehicle Dashboard link flips on live without a refresh.

Endpoints (all mounted at `/api/admin/vehicle-dealers/...`):
    GET  /                             — list dealers + brokers, filterable
    GET  /{user_id}                    — profile detail (license + docs + status)
    GET  /{user_id}/activity           — sales history (auctions, sold lots, buyers)
    POST /{user_id}/approve            — approve pending dealer/broker
    POST /{user_id}/suspend            — suspend
    POST /{user_id}/reinstate          — reinstate

The verification pipeline itself (document review, admin_verified flow) is
intentionally untouched — this manager consumes the same `verification_status`
field the existing flow already writes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from deps import User, get_db
from routes.admin_user_helpers import record_admin_action, require_admin


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/vehicle-dealers",
    tags=["admin-vehicle-dealers"],
)


# ── Helpers ──────────────────────────────────────────────────────────

def _iso(dt: Any) -> Optional[str]:
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt


def _pick(d: Optional[dict], keys: List[str]) -> Dict[str, Any]:
    if not d:
        return {}
    return {k: d.get(k) for k in keys if k in d}


async def _resolve_dealer(db, user_id: str) -> Dict[str, Any]:
    """Return {user, seller, broker, kind} for a given user_id.

    Raises 404 if the user is neither a vehicle dealer nor a broker.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    seller = await db.vehicle_sellers.find_one({"user_id": user_id}, {"_id": 0})
    broker = await db.brokers.find_one({"user_id": user_id}, {"_id": 0})

    is_dealer = bool(seller) or bool(user.get("is_vehicle_dealer"))
    is_broker = bool(broker) or user.get("account_type") == "broker"

    if not (is_dealer or is_broker):
        raise HTTPException(
            status_code=404,
            detail="This user is neither a vehicle dealer nor a broker.",
        )

    kind = "broker" if (is_broker and not is_dealer) else "dealer"
    return {"user": user, "seller": seller, "broker": broker, "kind": kind}


def _dealer_row(user: dict, seller: Optional[dict], broker: Optional[dict]) -> Dict[str, Any]:
    """Compact record used by the dealer list table."""
    if broker and not seller:
        kind = "broker"
        business_name = broker.get("legal_business_name")
        license_number = broker.get("broker_license_number")
        license_province = broker.get("operating_province")
        verification_status = broker.get("verification_status") or "pending"
        registered_at = broker.get("created_at") or user.get("created_at")
    else:
        kind = "dealer"
        business_name = (seller or {}).get("business_name") or user.get("company_name")
        license_number = (seller or {}).get("license_number") or user.get("dealer_license_number")
        license_province = (seller or {}).get("license_province") or user.get("dealer_license_province")
        verification_status = (seller or {}).get("verification_status") or (
            "approved" if user.get("is_vehicle_dealer") else "pending"
        )
        registered_at = (seller or {}).get("created_at") or user.get("created_at")

    # Suspension flag lives on the user document (single source of truth).
    if user.get("vehicle_dealer_suspended"):
        verification_status = "suspended"

    return {
        "user_id": user.get("id"),
        "name": user.get("name") or user.get("full_name") or "",
        "email": user.get("email") or "",
        "kind": kind,
        "business_name": business_name or "",
        "license_number": license_number or "",
        "license_province": license_province or "",
        "verification_status": verification_status,
        "registered_at": _iso(registered_at),
        "suspended": bool(user.get("vehicle_dealer_suspended")),
    }


# ── LIST ─────────────────────────────────────────────────────────────

@router.get("")
async def list_dealers(
    status: Optional[str] = Query(None, description="pending|approved|rejected|suspended|all"),
    kind: str = Query("all", description="all|dealer|broker"),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db=Depends(get_db),
):
    """List all users who are vehicle dealers or brokers, with their
    verification status, registration date, and license info."""
    rows: List[Dict[str, Any]] = []

    # 1. Dealers: user_ids from `vehicle_sellers` (canonical) plus any
    # user whose is_vehicle_dealer flag was set without a matching seller
    # doc (edge case from earlier backfills).
    dealer_user_ids: set = set()
    if kind in ("all", "dealer"):
        seller_cursor = db.vehicle_sellers.find({}, {"_id": 0})
        async for s in seller_cursor:
            dealer_user_ids.add(s["user_id"])
        # Backfill: users flagged as dealer but no seller row.
        async for u in db.users.find({"is_vehicle_dealer": True}, {"_id": 0, "id": 1}):
            dealer_user_ids.add(u["id"])

    # 2. Brokers: user_ids from `brokers` plus any user with account_type=broker.
    broker_user_ids: set = set()
    if kind in ("all", "broker"):
        async for b in db.brokers.find({}, {"_id": 0, "user_id": 1}):
            broker_user_ids.add(b["user_id"])
        async for u in db.users.find({"account_type": "broker"}, {"_id": 0, "id": 1}):
            broker_user_ids.add(u["id"])

    all_ids = list(dealer_user_ids | broker_user_ids)
    if not all_ids:
        return {"data": [], "total": 0}

    # Fetch all matching users in one round-trip
    user_map: Dict[str, dict] = {}
    async for u in db.users.find({"id": {"$in": all_ids}}, {"_id": 0}):
        user_map[u["id"]] = u

    # Fetch matching seller + broker docs
    seller_map: Dict[str, dict] = {}
    async for s in db.vehicle_sellers.find({"user_id": {"$in": all_ids}}, {"_id": 0}):
        seller_map[s["user_id"]] = s

    broker_map: Dict[str, dict] = {}
    async for b in db.brokers.find({"user_id": {"$in": all_ids}}, {"_id": 0}):
        broker_map[b["user_id"]] = b

    # Compose rows
    for uid in all_ids:
        u = user_map.get(uid)
        if not u:
            continue
        s = seller_map.get(uid)
        b = broker_map.get(uid)
        # If kind filter is set, skip rows that don't match.
        if kind == "dealer" and not s and not u.get("is_vehicle_dealer"):
            continue
        if kind == "broker" and not b and u.get("account_type") != "broker":
            continue
        row = _dealer_row(u, s, b)

        if status and status != "all":
            if row["verification_status"] != status:
                continue

        if search:
            needle = search.strip().lower()
            haystack = " ".join([
                row["name"], row["email"], row["business_name"],
                row["license_number"], row["license_province"],
            ]).lower()
            if needle not in haystack:
                continue

        rows.append(row)

    # Newest first, then paginate
    rows.sort(key=lambda r: r.get("registered_at") or "", reverse=True)
    total = len(rows)
    rows = rows[skip:skip + limit]
    return {"data": rows, "total": total}


# ── PROFILE DETAIL ───────────────────────────────────────────────────

@router.get("/{user_id}")
async def get_dealer_profile(
    user_id: str,
    admin: User = Depends(require_admin),
    db=Depends(get_db),
):
    """Full profile: user identity + license/registration info + documents +
    current status. Purely read-only — the verification flow is elsewhere."""
    resolved = await _resolve_dealer(db, user_id)
    user, seller, broker, kind = (
        resolved["user"], resolved["seller"], resolved["broker"], resolved["kind"],
    )

    profile: Dict[str, Any] = {
        "user_id": user.get("id"),
        "kind": kind,
        "identity": {
            "name": user.get("name") or user.get("full_name") or "",
            "email": user.get("email") or "",
            "phone": user.get("phone") or user.get("personal_phone_number") or "",
            "province": user.get("province") or "",
            "address": user.get("address") or "",
            "language": user.get("language") or "en",
            "created_at": _iso(user.get("created_at")),
            "last_login_at": _iso(user.get("last_login_at") or user.get("last_login")),
            "email_verified": bool(user.get("email_verified")),
            "phone_verified": bool(user.get("phone_verified")),
        },
        "status": {
            "verification_status": _dealer_row(user, seller, broker)["verification_status"],
            "suspended": bool(user.get("vehicle_dealer_suspended")),
            "suspended_at": _iso(user.get("vehicle_dealer_suspended_at")),
            "suspended_reason": user.get("vehicle_dealer_suspended_reason"),
            "is_vehicle_dealer": bool(user.get("is_vehicle_dealer")),
            "account_type": user.get("account_type"),
        },
    }

    if seller:
        profile["dealer_registration"] = {
            "seller_id": seller.get("id"),
            "business_name": seller.get("business_name"),
            "business_phone": seller.get("business_phone"),
            "business_address": seller.get("business_address"),
            "description": seller.get("description"),
            "website": seller.get("website"),
            "seller_type": seller.get("seller_type"),
            "license_number": seller.get("license_number"),
            "license_province": seller.get("license_province"),
            "license_expiry": _iso(seller.get("license_expiry")),
            "tax_id": seller.get("tax_id"),
            "created_at": _iso(seller.get("created_at")),
            "approved_at": _iso(seller.get("approved_at")),
            "approved_by": seller.get("approved_by"),
            "rejection_reason": seller.get("rejection_reason"),
            "rejected_at": _iso(seller.get("rejected_at")),
            "rejected_by": seller.get("rejected_by"),
        }

    if broker:
        profile["broker_registration"] = {
            "broker_id": broker.get("id"),
            "legal_business_name": broker.get("legal_business_name"),
            "operating_province": broker.get("operating_province"),
            "regulatory_body": broker.get("regulatory_body"),
            "broker_license_number": broker.get("broker_license_number"),
            "corporate_registration_number": broker.get("corporate_registration_number"),
            "permit_type": broker.get("permit_type"),
            "default_deposit_amount_cad": broker.get("default_deposit_amount_cad"),
            "created_at": _iso(broker.get("created_at")),
            "verified_at": _iso(broker.get("verified_at")),
            "verified_by": broker.get("verified_by"),
            "rejection_reason": broker.get("rejection_reason"),
            "suspended_at": _iso(broker.get("suspended_at")),
            "suspended_reason": broker.get("suspended_reason"),
        }

    # Verification documents — dealer docs live in `vehicle_seller_documents`
    # (canonical) with a fallback to legacy inline `seller.documents`. Broker
    # docs are direct URL fields on the broker record.
    documents: List[Dict[str, Any]] = []
    if seller:
        async for d in db.vehicle_seller_documents.find(
            {"seller_id": seller.get("id")},
            {"_id": 0},
        ):
            documents.append({
                "id": d.get("id"),
                "document_type": d.get("document_type"),
                "file_name": d.get("file_name"),
                "status": d.get("status"),
                "uploaded_at": _iso(d.get("uploaded_at") or d.get("created_at")),
                "reviewed_at": _iso(d.get("reviewed_at")),
                "reviewer_notes": d.get("reviewer_notes"),
            })
        for legacy in (seller.get("documents") or []):
            documents.append({
                "id": legacy.get("id"),
                "document_type": legacy.get("document_type"),
                "file_name": legacy.get("file_name"),
                "status": legacy.get("status") or "unknown",
                "uploaded_at": _iso(legacy.get("uploaded_at")),
                "legacy_inline": True,
            })
    if broker:
        if broker.get("license_document_url"):
            documents.append({
                "document_type": "broker_license",
                "file_url": broker["license_document_url"],
                "status": "on_file",
            })
        if broker.get("registration_document_url"):
            documents.append({
                "document_type": "corporate_registration",
                "file_url": broker["registration_document_url"],
                "status": "on_file",
            })
        for extra in (broker.get("additional_documents") or []):
            documents.append({
                "document_type": extra.get("document_type") or "supplementary",
                "file_url": extra.get("url"),
                "file_name": extra.get("file_name"),
                "status": extra.get("status") or "on_file",
            })

    profile["documents"] = documents
    return profile


# ── ACTIVITY HISTORY ─────────────────────────────────────────────────

@router.get("/{user_id}/activity")
async def get_dealer_activity(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db=Depends(get_db),
):
    """Sales history for a dealer/broker:
      • Auctions created (single vehicle + multi-lot events)
      • Vehicles sold with final prices
      • Buyer interactions (unique buyers, total bids received)
    """
    await _resolve_dealer(db, user_id)  # 404 if not a dealer/broker

    # Single-vehicle listings
    single_listings: List[Dict[str, Any]] = []
    async for v in db.vehicle_listings.find(
        {"seller_user_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit):
        single_listings.append({
            "listing_id": v.get("id"),
            "type": "single_vehicle",
            "title": v.get("title") or f"{v.get('year','')} {v.get('make','')} {v.get('model','')}".strip(),
            "status": v.get("status"),
            "current_bid": float(v.get("current_bid") or 0),
            "final_price": (float(v["final_price"]) if v.get("final_price") not in (None, "") else None),
            "bid_count": int(v.get("bid_count") or 0),
            "buyer_id": v.get("winner_id") or v.get("buyer_id"),
            "created_at": _iso(v.get("created_at")),
            "end_time": _iso(v.get("end_time")),
            "sold_at": _iso(v.get("sold_at")),
        })

    # Multi-lot events (sold_price + winner is per lot inside the event)
    multi_events: List[Dict[str, Any]] = []
    async for ev in db.vehicle_multi_lot_auctions.find(
        {"seller_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit):
        lots = ev.get("lots") or []
        sold_lots = [lt for lt in lots if lt.get("winner_user_id")]
        total_final = sum(float(lt.get("current_bid") or 0) for lt in sold_lots)
        multi_events.append({
            "event_id": ev.get("id"),
            "type": "multi_lot_event",
            "title": ev.get("title"),
            "status": ev.get("status"),
            "lot_count": len(lots),
            "sold_lot_count": len(sold_lots),
            "gross_hammer": total_final,
            "created_at": _iso(ev.get("created_at")),
            "start_time": _iso(ev.get("start_time")),
        })

    # Buyer interactions
    listing_ids = [x["listing_id"] for x in single_listings]
    bid_stats = {"total_bids": 0, "unique_buyers": 0}
    recent_buyers: List[Dict[str, Any]] = []
    if listing_ids:
        bid_stats["total_bids"] = await db.vehicle_bids.count_documents(
            {"vehicle_id": {"$in": listing_ids}}
        )
        buyer_ids: set = set()
        async for bid in db.vehicle_bids.find(
            {"vehicle_id": {"$in": listing_ids}},
            {"_id": 0, "bidder_id": 1, "amount": 1, "created_at": 1, "vehicle_id": 1, "status": 1},
        ).sort("created_at", -1).limit(20):
            if bid.get("bidder_id"):
                buyer_ids.add(bid["bidder_id"])
            recent_buyers.append({
                "bidder_id": bid.get("bidder_id"),
                "vehicle_id": bid.get("vehicle_id"),
                "amount": float(bid.get("amount") or 0),
                "status": bid.get("status"),
                "created_at": _iso(bid.get("created_at")),
            })
        bid_stats["unique_buyers"] = len(buyer_ids)

    # Also count multi-lot buyers (embedded per event)
    ml_buyer_ids: set = set()
    async for ev in db.vehicle_multi_lot_auctions.find(
        {"seller_id": user_id},
        {"_id": 0, "bids": 1},
    ):
        for b in (ev.get("bids") or []):
            if b.get("user_id"):
                ml_buyer_ids.add(b["user_id"])
    if ml_buyer_ids:
        bid_stats["unique_buyers"] += len(ml_buyer_ids)

    # Totals
    sold_single = [x for x in single_listings if x.get("final_price")]
    total_sold_count = len(sold_single) + sum(m["sold_lot_count"] for m in multi_events)
    total_gross = sum(x["final_price"] or 0 for x in sold_single) + sum(
        m["gross_hammer"] for m in multi_events
    )

    return {
        "user_id": user_id,
        "summary": {
            "auctions_created": len(single_listings) + len(multi_events),
            "single_vehicle_listings": len(single_listings),
            "multi_lot_events": len(multi_events),
            "vehicles_sold": total_sold_count,
            "gross_hammer_cad": round(total_gross, 2),
            "total_bids_received": bid_stats["total_bids"],
            "unique_buyers": bid_stats["unique_buyers"],
        },
        "single_listings": single_listings,
        "multi_lot_events": multi_events,
        "recent_bids": recent_buyers,
    }


# ── QUICK ACTIONS ────────────────────────────────────────────────────

class ActionPayload(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


@router.post("/{user_id}/approve")
async def approve_dealer(
    user_id: str,
    admin: User = Depends(require_admin),
    db=Depends(get_db),
):
    """Approve a pending vehicle dealer. Reuses the same fields the
    existing document-review flow writes so the dealer's dashboard,
    listing badge, and fee schedule pick it up instantly."""
    resolved = await _resolve_dealer(db, user_id)
    seller, broker = resolved["seller"], resolved["broker"]
    now = datetime.now(timezone.utc)

    updates_summary: Dict[str, Any] = {}

    if seller:
        await db.vehicle_sellers.update_one(
            {"id": seller["id"]},
            {"$set": {
                "verification_status": "approved",
                "approved_at": now,
                "approved_by": admin.id,
                "updated_at": now,
            }},
        )
        updates_summary["vehicle_seller"] = seller["id"]

    if broker:
        await db.brokers.update_one(
            {"id": broker["id"]},
            {"$set": {
                "verification_status": "approved",
                "verified_at": now,
                "verified_by": admin.email or admin.id,
                "updated_at": now,
            }},
        )
        updates_summary["broker"] = broker["id"]

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_vehicle_dealer": True,
            "vehicle_dealer_approved_at": now.isoformat(),
            "vehicle_dealer_approved_by": admin.id,
            "vehicle_dealer_suspended": False,
        }, "$unset": {
            "vehicle_dealer_suspended_at": "",
            "vehicle_dealer_suspended_reason": "",
        }},
    )

    # Ping the dealer's WS so the Vehicle Dashboard link appears in
    # nav without a manual refresh. Best-effort — never raises.
    try:
        from routes.notifications import notification_manager
        await notification_manager.send_to_user(user_id, {
            "type": "verification_updated",
            "subject": "vehicle_dealer",
            "is_vehicle_dashboard_eligible": True,
        })
    except Exception:  # noqa: BLE001
        pass

    await record_admin_action(
        db,
        admin_id=admin.id,
        admin_email=admin.email or "",
        action="vehicle_dealer_approve",
        target_user_id=user_id,
        content=updates_summary,
    )
    return {"ok": True, "status": "approved", **updates_summary}


@router.post("/{user_id}/suspend")
async def suspend_dealer(
    user_id: str,
    payload: ActionPayload,
    admin: User = Depends(require_admin),
    db=Depends(get_db),
):
    """Suspend a dealer/broker. Blocks new listings + bidding by flipping
    the user-level `vehicle_dealer_suspended` flag (single source of
    truth used elsewhere in the codebase)."""
    resolved = await _resolve_dealer(db, user_id)
    seller, broker = resolved["seller"], resolved["broker"]
    now = datetime.now(timezone.utc)
    reason = (payload.reason or "Suspended by admin").strip()

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "vehicle_dealer_suspended": True,
            "vehicle_dealer_suspended_at": now.isoformat(),
            "vehicle_dealer_suspended_reason": reason,
        }},
    )
    if seller:
        await db.vehicle_sellers.update_one(
            {"id": seller["id"]},
            {"$set": {"verification_status": "suspended", "updated_at": now}},
        )
    if broker:
        await db.brokers.update_one(
            {"id": broker["id"]},
            {"$set": {
                "verification_status": "suspended",
                "suspended_at": now,
                "suspended_reason": reason,
                "updated_at": now,
            }},
        )

    try:
        from routes.notifications import notification_manager
        await notification_manager.send_to_user(user_id, {
            "type": "verification_updated",
            "subject": "vehicle_dealer",
            "is_vehicle_dashboard_eligible": False,
        })
    except Exception:  # noqa: BLE001
        pass

    await record_admin_action(
        db,
        admin_id=admin.id,
        admin_email=admin.email or "",
        action="vehicle_dealer_suspend",
        target_user_id=user_id,
        content={"reason": reason},
    )
    return {"ok": True, "status": "suspended", "reason": reason}


@router.post("/{user_id}/reinstate")
async def reinstate_dealer(
    user_id: str,
    admin: User = Depends(require_admin),
    db=Depends(get_db),
):
    """Reinstate a previously suspended dealer/broker. Restores the
    verification_status the user had before suspension (approved by
    default; if their license was rejected we send them back to pending
    so they must resubmit)."""
    resolved = await _resolve_dealer(db, user_id)
    seller, broker = resolved["seller"], resolved["broker"]
    now = datetime.now(timezone.utc)

    # Choose the reinstated status: if a prior approval timestamp exists,
    # go back to approved; otherwise re-open review.
    prior_seller_status = "approved" if (seller and seller.get("approved_at")) else "pending"
    prior_broker_status = "approved" if (broker and broker.get("verified_at")) else "pending_review"

    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "vehicle_dealer_suspended": False,
                "is_vehicle_dealer": prior_seller_status == "approved" if seller else bool(broker),
            },
            "$unset": {
                "vehicle_dealer_suspended_at": "",
                "vehicle_dealer_suspended_reason": "",
            },
        },
    )
    if seller:
        await db.vehicle_sellers.update_one(
            {"id": seller["id"]},
            {"$set": {"verification_status": prior_seller_status, "updated_at": now}},
        )
    if broker:
        await db.brokers.update_one(
            {"id": broker["id"]},
            {"$set": {
                "verification_status": prior_broker_status,
                "suspended_at": None,
                "suspended_reason": None,
                "updated_at": now,
            }},
        )

    try:
        from routes.notifications import notification_manager
        await notification_manager.send_to_user(user_id, {
            "type": "verification_updated",
            "subject": "vehicle_dealer",
            "is_vehicle_dashboard_eligible": prior_seller_status == "approved" or prior_broker_status == "approved",
        })
    except Exception:  # noqa: BLE001
        pass

    await record_admin_action(
        db,
        admin_id=admin.id,
        admin_email=admin.email or "",
        action="vehicle_dealer_reinstate",
        target_user_id=user_id,
        content={"new_status_dealer": prior_seller_status, "new_status_broker": prior_broker_status},
    )
    return {
        "ok": True,
        "dealer_status": prior_seller_status if seller else None,
        "broker_status": prior_broker_status if broker else None,
    }
