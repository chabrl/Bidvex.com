"""
iter217 Phase 5 Hotfix v5b — Broker Ecosystem API.

Three groups of endpoints:

  1. Broker self-service:
     - POST /api/brokers/apply           (logged-in user applies)
     - GET  /api/brokers                 (public directory of approved brokers)
     - GET  /api/brokers/me              (broker dashboard data)
     - GET  /api/brokers/{id}            (public profile)
     - PATCH /api/brokers/settings       (update fee structure / settings)

  2. Buyer ↔ broker relationships:
     - POST /api/broker-relationships/request           (buyer)
     - GET  /api/broker-relationships/my-broker         (buyer)
     - GET  /api/broker-relationships/my-buyers         (broker)
     - POST /api/broker-relationships/{id}/approve      (broker)
     - POST /api/broker-relationships/{id}/reject       (broker)
     - PATCH /api/broker-relationships/{id}/bid-limit   (broker)
     - POST /api/broker-relationships/{id}/release-deposit (broker)
     - POST /api/broker-relationships/{id}/capture-deposit (broker+admin)
     - POST /api/broker-relationships/{id}/terminate    (broker)
     - POST /api/broker-relationships/{id}/suspend      (broker)

  3. Broker bidding:
     - POST /api/vehicle-auctions/{id}/bid-via-broker   (buyer)
     - GET  /api/broker-bids/audit                      (admin)

  4. Admin:
     - GET   /api/admin/brokers
     - PATCH /api/admin/brokers/{id}/approve
     - PATCH /api/admin/brokers/{id}/reject
     - PATCH /api/admin/brokers/{id}/suspend
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, require_admin, User
from models.broker_models import (
    BrokerCreate, BrokerFeeStructure, RelationshipRequest,
    make_broker_doc, make_relationship_doc, make_broker_bid_doc,
)
from services.broker_conflict_guard import check_intra_broker_conflict
from services.broker_fee_engine import calculate_broker_transaction

logger = logging.getLogger("broker_routes")

brokers_router = APIRouter(prefix="/api", tags=["brokers"])

DEFAULT_DEPOSIT_CAD = 500.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _exclude_id(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if d is None:
        return None
    d.pop("_id", None)
    return d


# ── 1. Broker self-service ─────────────────────────────────────────────
@brokers_router.post("/brokers/apply")
async def apply_to_become_broker(payload: BrokerCreate, current_user: User = Depends(get_current_user)):
    db = get_db()
    # User can have at most one broker record
    existing = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1, "verification_status": 1})
    if existing:
        raise HTTPException(status_code=400, detail={
            "error": "broker_application_exists",
            "message_en": "You already have a broker application on file.",
            "message_fr": "Vous avez déjà une demande de courtier au dossier.",
            "broker_id": existing["id"],
            "verification_status": existing["verification_status"],
        })
    # Cannot be a partner and a broker simultaneously
    if (current_user.account_type or "").lower() in ("partner", "vehicle_dealer", "storage_facility"):
        raise HTTPException(status_code=400, detail={
            "error": "incompatible_account_type",
            "message_en": "Partner accounts cannot also be brokers. Please contact support to convert your account.",
            "message_fr": "Les comptes partenaires ne peuvent pas être courtiers. Veuillez contacter le support.",
        })

    doc = make_broker_doc(user_id=current_user.id, payload=payload)
    await db.brokers.insert_one(doc)

    # Bind broker_id on the user record
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"broker_id": doc["id"], "account_type": "broker"}},
    )

    # Admin notification (best-effort)
    try:
        await db.admin_notifications.insert_one({
            "id":         doc["id"] + ":apply",
            "type":       "broker_application",
            "title":      f"New broker application — {doc['legal_business_name']}",
            "broker_id":  doc["id"],
            "user_id":    current_user.id,
            "created_at": _utcnow(),
            "read":       False,
        })
    except Exception as e:
        logger.warning("admin_notifications insert failed: %s", e)

    return {"success": True, "broker_id": doc["id"], "verification_status": doc["verification_status"]}


@brokers_router.get("/brokers")
async def list_brokers_public(province: Optional[str] = None, limit: int = 50):
    """Public directory — approved brokers only."""
    db = get_db()
    query: Dict[str, Any] = {"verification_status": "approved"}
    if province:
        query["operating_province"] = province.strip().upper()
    rows: List[Dict[str, Any]] = []
    async for d in db.brokers.find(query, {"_id": 0}).limit(limit):
        # Mask the broker license number (last 4 visible)
        lic = d.get("broker_license_number") or ""
        d["broker_license_number_masked"] = ("•" * max(0, len(lic) - 4)) + lic[-4:] if lic else ""
        d.pop("broker_license_number", None)
        d.pop("license_document_url", None)
        d.pop("registration_document_url", None)
        d.pop("additional_documents", None)
        d.pop("verification_notes", None)
        rows.append(d)
    return {"data": rows, "count": len(rows)}


@brokers_router.get("/brokers/me")
async def get_my_broker(current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    return broker


@brokers_router.get("/brokers/{broker_id}")
async def get_broker_public(broker_id: str):
    db = get_db()
    d = await db.brokers.find_one({"id": broker_id, "verification_status": "approved"}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    lic = d.get("broker_license_number") or ""
    d["broker_license_number_masked"] = ("•" * max(0, len(lic) - 4)) + lic[-4:] if lic else ""
    d.pop("broker_license_number", None)
    return d


class _SettingsUpdate(BaseModel):
    fee_structure: Optional[BrokerFeeStructure] = None
    default_deposit_amount_cad: Optional[float] = None


@brokers_router.patch("/brokers/settings")
async def update_broker_settings(payload: _SettingsUpdate, current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1, "verification_status": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    update: Dict[str, Any] = {"updated_at": _utcnow()}
    if payload.fee_structure is not None:
        update["fee_structure"] = payload.fee_structure.dict()
    if payload.default_deposit_amount_cad is not None:
        if payload.default_deposit_amount_cad < 100:
            raise HTTPException(status_code=422, detail={"error": "deposit_min_100_cad"})
        update["default_deposit_amount_cad"] = float(payload.default_deposit_amount_cad)
    await db.brokers.update_one({"id": broker["id"]}, {"$set": update})
    return {"success": True}


# ── 2. Buyer ↔ broker relationships ────────────────────────────────────
@brokers_router.post("/broker-relationships/request")
async def request_broker_partnership(
    request: Request,
    payload: RelationshipRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db()

    # Broker must exist and be approved
    broker = await db.brokers.find_one({"id": payload.broker_id, "verification_status": "approved"}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found_or_not_approved"})

    # Buyer cannot bind to multiple brokers at once
    existing = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": {"$in": ["pending", "approved", "active"]}},
        {"_id": 0, "id": 1, "broker_id": 1, "status": 1},
    )
    if existing:
        raise HTTPException(status_code=400, detail={
            "error": "already_bound",
            "current_broker_id": existing["broker_id"],
            "current_status": existing["status"],
        })

    deposit_amount = float(broker.get("default_deposit_amount_cad") or DEFAULT_DEPOSIT_CAD)
    rel = make_relationship_doc(
        broker_id          = payload.broker_id,
        buyer_user_id      = current_user.id,
        deposit_amount_cad = deposit_amount,
    )
    await db.broker_buyer_relationships.insert_one(rel)

    # Authorize Stripe deposit hold (best-effort — if stripe fails we
    # leave deposit_status="pending" and the broker can retry).
    pi_data = None
    try:
        from services.broker_deposit_service import authorize_deposit
        pi_data = authorize_deposit(
            amount_cad        = deposit_amount,
            customer_email    = current_user.email,
            payment_method_id = payload.payment_method_id,
            relationship_id   = rel["id"],
            broker_id         = payload.broker_id,
            buyer_user_id     = current_user.id,
        )
        await db.broker_buyer_relationships.update_one(
            {"id": rel["id"]},
            {"$set": {
                "deposit_stripe_payment_intent_id": pi_data["payment_intent_id"],
                "deposit_status":                  "held" if pi_data["status"] in ("requires_capture", "succeeded") else "pending",
                "deposit_held_at":                 _utcnow() if pi_data["status"] == "requires_capture" else None,
                "updated_at":                      _utcnow(),
            }},
        )
    except Exception as e:
        logger.warning("stripe deposit authorize failed for rel=%s: %s", rel["id"], e)

    return {
        "success":         True,
        "relationship_id": rel["id"],
        "deposit": (
            {
                "amount_cad":        deposit_amount,
                "payment_intent_id": pi_data["payment_intent_id"] if pi_data else None,
                "client_secret":     pi_data["client_secret"] if pi_data else None,
                "status":            pi_data["status"] if pi_data else "pending",
            }
        ),
    }


@brokers_router.get("/broker-relationships/my-broker")
async def get_my_broker_binding(current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": {"$in": ["pending", "approved", "active"]}},
        {"_id": 0},
    )
    if not rel:
        return {"data": None}
    broker = await db.brokers.find_one({"id": rel["broker_id"]}, {"_id": 0})
    return {"data": {"relationship": rel, "broker": _exclude_id(broker)}}


@brokers_router.get("/broker-relationships/my-buyers")
async def get_my_buyers(current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    rows: List[Dict[str, Any]] = []
    async for d in db.broker_buyer_relationships.find({"broker_id": broker["id"]}, {"_id": 0}):
        # Hydrate buyer email
        u = await db.users.find_one({"id": d["buyer_user_id"]}, {"_id": 0, "email": 1, "name": 1, "full_name": 1})
        d["buyer_email"]     = (u or {}).get("email")
        d["buyer_full_name"] = (u or {}).get("full_name") or (u or {}).get("name")
        rows.append(d)
    return {"data": rows, "count": len(rows)}


async def _require_broker_owns_relationship(db, rel_id: str, user_id: str) -> Dict[str, Any]:
    rel = await db.broker_buyer_relationships.find_one({"id": rel_id}, {"_id": 0})
    if not rel:
        raise HTTPException(status_code=404, detail={"error": "relationship_not_found"})
    broker = await db.brokers.find_one({"id": rel["broker_id"]}, {"_id": 0, "id": 1, "user_id": 1})
    if not broker or broker["user_id"] != user_id:
        raise HTTPException(status_code=403, detail={"error": "not_your_relationship"})
    return rel


@brokers_router.post("/broker-relationships/{rel_id}/approve")
async def approve_buyer(rel_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    if rel["status"] not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail={"error": "invalid_state", "current_status": rel["status"]})
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"status": "active", "can_bid": True, "updated_at": _utcnow()}},
    )
    await db.users.update_one(
        {"id": rel["buyer_user_id"]},
        {"$set": {"bound_broker_id": rel["broker_id"], "broker_binding_status": "active", "can_bid_on_vehicles": True}},
    )
    await db.brokers.update_one({"id": rel["broker_id"]}, {"$inc": {"total_buyers_managed": 1}})
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/reject")
async def reject_buyer(rel_id: str, reason: str = Body("", embed=True), current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    # Release the deposit hold
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    if pi_id:
        try:
            from services.broker_deposit_service import release_deposit
            release_deposit(pi_id)
        except Exception as e:
            logger.warning("release_deposit on reject failed: %s", e)
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {
            "status":              "rejected",
            "deposit_status":      "released",
            "deposit_released_at": _utcnow(),
            "updated_at":          _utcnow(),
            "rejection_reason":    reason,
        }},
    )
    return {"success": True}


@brokers_router.patch("/broker-relationships/{rel_id}/bid-limit")
async def set_bid_limit(rel_id: str, max_bid_amount_cad: float = Body(..., embed=True), current_user: User = Depends(get_current_user)):
    db = get_db()
    await _require_broker_owns_relationship(db, rel_id, current_user.id)
    if max_bid_amount_cad < 0:
        raise HTTPException(status_code=422, detail={"error": "negative_limit"})
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"max_bid_amount_cad": float(max_bid_amount_cad), "updated_at": _utcnow()}},
    )
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/release-deposit")
async def release_deposit_endpoint(rel_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    if not pi_id:
        raise HTTPException(status_code=400, detail={"error": "no_deposit_on_file"})
    try:
        from services.broker_deposit_service import release_deposit
        release_deposit(pi_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": "stripe_release_failed", "message": str(e)})
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"deposit_status": "released", "deposit_released_at": _utcnow(), "updated_at": _utcnow()}},
    )
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/terminate")
async def terminate_relationship(rel_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    # Release the deposit if still held
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    if pi_id and rel.get("deposit_status") == "held":
        try:
            from services.broker_deposit_service import release_deposit
            release_deposit(pi_id)
        except Exception as e:
            logger.warning("release on terminate failed: %s", e)
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"status": "terminated", "can_bid": False, "deposit_status": "released",
                  "deposit_released_at": _utcnow(), "updated_at": _utcnow()}},
    )
    await db.users.update_one(
        {"id": rel["buyer_user_id"]},
        {"$set": {"bound_broker_id": None, "broker_binding_status": "none", "can_bid_on_vehicles": False}},
    )
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/suspend")
async def suspend_relationship(rel_id: str, reason: str = Body("", embed=True), current_user: User = Depends(get_current_user)):
    db = get_db()
    await _require_broker_owns_relationship(db, rel_id, current_user.id)
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"status": "suspended", "can_bid": False, "suspended_reason": reason, "updated_at": _utcnow()}},
    )
    return {"success": True}


# ── 3. Broker bidding ──────────────────────────────────────────────────
class _BrokerBidIn(BaseModel):
    bid_amount_cad: float = Field(..., gt=0)
    broker_confirmation: bool = False


@brokers_router.post("/vehicle-auctions/{listing_id}/bid-via-broker")
async def place_bid_via_broker(
    listing_id: str,
    request: Request,
    payload: _BrokerBidIn,
    current_user: User = Depends(get_current_user),
):
    db = get_db()

    # 1. Buyer must have an active broker relationship
    rel = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": "active", "can_bid": True},
        {"_id": 0},
    )
    if not rel:
        raise HTTPException(status_code=403, detail={
            "error": "no_active_broker",
            "message_en": "You must be connected to an approved broker to bid on vehicles in your province.",
            "message_fr": "Vous devez être connecté à un courtier approuvé pour enchérir sur des véhicules.",
        })

    # 2. Broker still approved?
    broker = await db.brokers.find_one(
        {"id": rel["broker_id"], "verification_status": "approved"},
        {"_id": 0},
    )
    if not broker:
        raise HTTPException(status_code=403, detail={
            "error": "broker_not_active",
            "message_en": "Your broker is no longer authorized to place bids on your behalf.",
            "message_fr": "Votre courtier n'est plus autorisé à enchérir en votre nom.",
        })

    # 3. Bid limit check
    if rel.get("max_bid_amount_cad") is not None:
        if payload.bid_amount_cad > rel["max_bid_amount_cad"]:
            raise HTTPException(status_code=400, detail={
                "error": "bid_exceeds_broker_limit",
                "max_bid_amount_cad": rel["max_bid_amount_cad"],
            })

    # 4. Intra-broker conflict
    conflict = await check_intra_broker_conflict(
        db,
        vehicle_listing_id = listing_id,
        broker_id          = rel["broker_id"],
        new_buyer_id       = current_user.id,
    )
    if conflict.conflict:
        raise HTTPException(status_code=409, detail={
            "error":            "intra_broker_conflict",
            "message_en":       conflict.message_en,
            "message_fr":       conflict.message_fr,
            "blocking_buyer_id": conflict.blocking_buyer_id,
        })

    # 5. Snapshot the auction state
    snapshot: Dict[str, Any] = {}
    try:
        listing = await db.vehicle_listings.find_one({"id": listing_id}, {"_id": 0, "current_bid": 1, "highest_bidder_id": 1, "bid_count": 1})
        if listing:
            snapshot = {
                "current_bid":       listing.get("current_bid"),
                "highest_bidder_id": listing.get("highest_bidder_id"),
                "bid_count":         listing.get("bid_count"),
            }
    except Exception:
        pass

    # 6. Write immutable audit row
    bid_doc = make_broker_bid_doc(
        vehicle_listing_id          = listing_id,
        broker_id                   = rel["broker_id"],
        broker_license_number       = broker["broker_license_number"],
        broker_legal_business_name  = broker["legal_business_name"],
        buyer_user_id               = current_user.id,
        bid_amount_cad              = payload.bid_amount_cad,
        ip_address                  = request.client.host if request.client else None,
        user_agent                  = request.headers.get("user-agent"),
        session_id                  = request.headers.get("x-session-id"),
        auction_state_snapshot      = snapshot,
    )
    await db.broker_bids.insert_one(bid_doc)

    # 7. Outbid any previous broker bids on this listing
    await db.broker_bids.update_many(
        {"vehicle_listing_id": listing_id, "id": {"$ne": bid_doc["id"]}, "status": "placed"},
        {"$set": {"status": "outbid", "outbid_at": _utcnow()}},
    )

    # 8. Mirror into the standard vehicle bid stream (best-effort)
    try:
        await db.vehicle_listings.update_one(
            {"id": listing_id},
            {
                "$push": {"bids_via_broker": bid_doc["id"]},
                "$set": {
                    "current_bid":               payload.bid_amount_cad,
                    "highest_bidder_id":         current_user.id,
                    "highest_bidder_display":    broker["legal_business_name"],
                    "highest_bidder_via_broker": rel["broker_id"],
                    "updated_at":                _utcnow(),
                },
                "$inc": {"bid_count": 1},
            },
        )
    except Exception as e:
        logger.warning("vehicle_listings mirror failed for %s: %s", listing_id, e)

    return {
        "success":               True,
        "bid_id":                bid_doc["id"],
        "broker_display_name":   broker["legal_business_name"],
        "broker_license_number": broker["broker_license_number"],
    }


@brokers_router.get("/broker-bids/audit")
async def audit_broker_bids(
    broker_id:    Optional[str] = None,
    buyer_id:     Optional[str] = None,
    listing_id:   Optional[str] = None,
    limit:        int = 200,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    q: Dict[str, Any] = {}
    if broker_id:  q["broker_id"]         = broker_id
    if buyer_id:   q["buyer_user_id"]     = buyer_id
    if listing_id: q["vehicle_listing_id"] = listing_id
    rows = []
    async for d in db.broker_bids.find(q, {"_id": 0}).sort("placed_at", -1).limit(limit):
        rows.append(d)
    return {"data": rows, "count": len(rows)}


# ── 4. Admin ───────────────────────────────────────────────────────────
@brokers_router.get("/admin/brokers")
async def admin_list_brokers(
    status: Optional[str] = None,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    q: Dict[str, Any] = {}
    if status: q["verification_status"] = status
    rows = []
    async for d in db.brokers.find(q, {"_id": 0}).sort("created_at", -1):
        u = await db.users.find_one({"id": d["user_id"]}, {"_id": 0, "email": 1, "full_name": 1, "name": 1})
        d["user_email"] = (u or {}).get("email")
        d["user_name"]  = (u or {}).get("full_name") or (u or {}).get("name")
        rows.append(d)
    return {"data": rows, "count": len(rows)}


@brokers_router.patch("/admin/brokers/{broker_id}/approve")
async def admin_approve_broker(broker_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    res = await db.brokers.update_one(
        {"id": broker_id},
        {"$set": {
            "verification_status": "approved",
            "verified_at":         _utcnow(),
            "verified_by":         current_user.email,
            "updated_at":          _utcnow(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    return {"success": True}


@brokers_router.patch("/admin/brokers/{broker_id}/reject")
async def admin_reject_broker(broker_id: str, reason: str = Body("", embed=True), current_user: User = Depends(require_admin)):
    db = get_db()
    res = await db.brokers.update_one(
        {"id": broker_id},
        {"$set": {
            "verification_status": "rejected",
            "rejection_reason":    reason,
            "verified_by":         current_user.email,
            "updated_at":          _utcnow(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    return {"success": True}


@brokers_router.patch("/admin/brokers/{broker_id}/suspend")
async def admin_suspend_broker(broker_id: str, reason: str = Body("", embed=True), current_user: User = Depends(require_admin)):
    db = get_db()
    res = await db.brokers.update_one(
        {"id": broker_id},
        {"$set": {
            "verification_status": "suspended",
            "suspended_at":        _utcnow(),
            "suspended_reason":    reason,
            "updated_at":          _utcnow(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    return {"success": True}


# ── 5. Fee preview endpoint (public, no auth) ──────────────────────────
@brokers_router.post("/brokers/{broker_id}/fee-preview")
async def fee_preview(broker_id: str, hammer_price: float = Body(..., embed=True), buyer_province: Optional[str] = Body(None, embed=True)):
    db = get_db()
    broker = await db.brokers.find_one({"id": broker_id, "verification_status": "approved"}, {"_id": 0, "fee_structure": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    bd = calculate_broker_transaction(
        hammer_price         = hammer_price,
        broker_fee_structure = broker["fee_structure"],
        buyer_province       = buyer_province,
    )
    return bd.as_dict()
