"""
Admin Charge Log — observability surface for the strict payment system.
Lists every payment_charge row with filters by status / charge_type / auction_id
+ payment_events stream (DUPLICATE_CHARGE_BLOCKED / ROLLBACK_REFUND / WINNER_MISMATCH_BLOCKED)
+ deposit_refund_queue stats.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from routes.payments_shared import get_current_user_wrapper, get_db

security = HTTPBearer(auto_error=False)

admin_charges_router = APIRouter(prefix="/admin/payment-charges", tags=["AdminPaymentCharges"])


async def _require_admin(credentials):
    fn = get_current_user_wrapper()
    if not credentials or fn is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await fn(credentials)
    if getattr(user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@admin_charges_router.get("")
async def list_charges(
    status: Optional[str] = Query(None),
    charge_type: Optional[str] = Query(None),
    auction_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    await _require_admin(credentials)
    db = get_db()
    q: dict = {}
    if status:
        q["status"] = status
    if charge_type:
        q["charge_type"] = charge_type
    if auction_id:
        q["auction_id"] = auction_id
    if user_id:
        q["user_id"] = user_id
    cursor = (
        db.payment_charges.find(q, {"_id": 0})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )
    rows = await cursor.to_list(limit)
    total = await db.payment_charges.count_documents(q)
    # Aggregate counts by status
    pipeline = [
        {"$match": q} if q else {"$match": {}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}}},
    ]
    agg = await db.payment_charges.aggregate(pipeline).to_list(20)
    summary = {r["_id"]: {"count": r["count"], "amount": round(r.get("amount", 0), 2)} for r in agg}
    return {"rows": rows, "total": total, "summary": summary}


@admin_charges_router.get("/events")
async def list_events(
    event: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Stream of important events: DUPLICATE_CHARGE_BLOCKED, ROLLBACK_REFUND, WINNER_MISMATCH_BLOCKED."""
    await _require_admin(credentials)
    db = get_db()
    q = {"event": event} if event else {}
    rows = await (
        db.payment_events.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    )
    return {"events": rows, "count": len(rows)}


@admin_charges_router.get("/refund-queue")
async def refund_queue_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Live stats of the deposit refund queue (60-second SLA)."""
    await _require_admin(credentials)
    db = get_db()
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "amount": {"$sum": "$amount"}}}
    ]
    agg = await db.deposit_refund_queue.aggregate(pipeline).to_list(20)
    by_status = {r["_id"]: {"count": r["count"], "amount": round(r.get("amount", 0), 2)} for r in agg}
    failed = await (
        db.deposit_refund_queue.find({"status": "failed"}, {"_id": 0}).limit(50).to_list(50)
    )
    return {"by_status": by_status, "failed_jobs": failed}
