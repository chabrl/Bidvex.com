"""
BidVex — Admin Deposit Management
POST /api/admin/vehicle-deposits/{deposit_id}/release → cancel Stripe hold
POST /api/admin/vehicle-deposits/{deposit_id}/capture → charge $500 as penalty
GET  /api/admin/vehicle-deposits                       → list all (with filters)
GET  /api/admin/vehicle-deposits/{deposit_id}          → single deposit detail

All routes require admin. Uses PaymentService.process_deposit_refund /
PaymentService.capture_deposit from services/vehicle_payment.py.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
import logging

from deps import get_db, require_admin, User
from services.vehicle_payment import get_payment_service

logger = logging.getLogger(__name__)
admin_deposits_router = APIRouter(tags=["Admin Deposits"])


@admin_deposits_router.get("/admin/vehicle-deposits")
async def admin_list_vehicle_deposits(
    status: Optional[str] = Query(None, description="pending|paid|authorized|released|refunded|captured|expired"),
    vehicle_id: Optional[str] = None,
    bidder_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_admin),
):
    """List vehicle bid deposits (admin only)."""
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if vehicle_id:
        q["vehicle_id"] = vehicle_id
    if bidder_id:
        q["bidder_id"] = bidder_id

    deposits = (
        await db.vehicle_bid_deposits.find(q, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )

    # Enrich with buyer email + vehicle title (best-effort)
    bidder_ids = list({d.get("bidder_id") for d in deposits if d.get("bidder_id")})
    vehicle_ids = list({d.get("vehicle_id") for d in deposits if d.get("vehicle_id")})

    users_by_id, vehicles_by_id = {}, {}
    if bidder_ids:
        async for u in db.users.find(
            {"id": {"$in": bidder_ids}},
            {"_id": 0, "id": 1, "email": 1, "full_name": 1, "name": 1},
        ):
            users_by_id[u["id"]] = u
    if vehicle_ids:
        async for v in db.vehicle_listings.find(
            {"id": {"$in": vehicle_ids}},
            {"_id": 0, "id": 1, "make": 1, "model": 1, "year": 1, "title": 1},
        ):
            vehicles_by_id[v["id"]] = v

    for d in deposits:
        u = users_by_id.get(d.get("bidder_id"))
        if u:
            d["buyer_email"] = u.get("email")
            d["buyer_name"] = u.get("full_name") or u.get("name")
        v = vehicles_by_id.get(d.get("vehicle_id"))
        if v:
            d["vehicle_title"] = (
                v.get("title")
                or f"{v.get('year','')} {v.get('make','')} {v.get('model','')}".strip()
            )

    return {"count": len(deposits), "deposits": deposits}


@admin_deposits_router.get("/admin/vehicle-deposits/{deposit_id}")
async def admin_get_vehicle_deposit(
    deposit_id: str,
    current_user: User = Depends(require_admin),
):
    """Get one deposit with full audit trail."""
    db = get_db()
    deposit = await db.vehicle_bid_deposits.find_one({"id": deposit_id}, {"_id": 0})
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    audit = (
        await db.vehicle_audit_logs.find(
            {"entity_type": "deposit", "entity_id": deposit_id},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(50)
    )
    return {"deposit": deposit, "audit_log": audit}


@admin_deposits_router.post("/admin/vehicle-deposits/{deposit_id}/release")
async def admin_release_vehicle_deposit(
    deposit_id: str,
    reason: Optional[str] = Query("admin_manual_release"),
    current_user: User = Depends(require_admin),
):
    """
    Cancel the Stripe PaymentIntent hold → no funds move.
    Used for non-winners or for winners after their fee invoice is paid.
    """
    db = get_db()
    deposit = await db.vehicle_bid_deposits.find_one({"id": deposit_id})
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    if deposit.get("status") not in ("paid", "authorized"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot release deposit with status: {deposit.get('status')}",
        )

    svc = get_payment_service()
    try:
        result = await svc.process_deposit_refund(db, deposit_id, reason=reason)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception(f"[ADMIN] release deposit {deposit_id} failed")
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    # Admin audit
    await db.vehicle_audit_logs.insert_one({
        "entity_type": "deposit",
        "entity_id": deposit_id,
        "action": "admin_deposit_released",
        "performed_by": current_user.id,
        "performed_by_role": "admin",
        "performed_by_email": getattr(current_user, "email", None),
        "new_value": result,
        "created_at": datetime.now(timezone.utc),
    })
    logger.info(f"[ADMIN] {current_user.id} released deposit {deposit_id}: {reason}")
    return result


@admin_deposits_router.post("/admin/vehicle-deposits/{deposit_id}/capture")
async def admin_capture_vehicle_deposit(
    deposit_id: str,
    reason: Optional[str] = Query("admin_manual_capture"),
    current_user: User = Depends(require_admin),
):
    """
    Capture the $500 deposit hold as a penalty (only valid when the buyer
    missed their platform-fee invoice deadline). This IS the charge path.
    """
    db = get_db()
    deposit = await db.vehicle_bid_deposits.find_one({"id": deposit_id})
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    if deposit.get("status") not in ("paid", "authorized"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot capture deposit with status: {deposit.get('status')}",
        )

    svc = get_payment_service()
    try:
        result = await svc.capture_deposit(db, deposit_id, reason=reason)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception(f"[ADMIN] capture deposit {deposit_id} failed")
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    await db.vehicle_audit_logs.insert_one({
        "entity_type": "deposit",
        "entity_id": deposit_id,
        "action": "admin_deposit_captured",
        "performed_by": current_user.id,
        "performed_by_role": "admin",
        "performed_by_email": getattr(current_user, "email", None),
        "new_value": result,
        "created_at": datetime.now(timezone.utc),
    })
    logger.warning(
        f"[ADMIN] {current_user.id} CAPTURED deposit {deposit_id}: {reason}"
    )
    return result
