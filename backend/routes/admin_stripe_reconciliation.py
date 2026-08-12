"""
iter482 P5.1 — Admin Stripe Reconciliation API
==============================================

Read-only endpoints exposing the canonical
``payment_processing_reconciliation`` collection so administrators can
audit:

  * every buyer / seller / partner Stripe payment
  * estimated fee vs payer-borne recovery vs actual Stripe BalanceTransaction fee
  * variance and reconciliation status (COVERED / SHORTFALL / UNKNOWN)
  * card country resolved from Stripe payment_method_details

Endpoints
---------

    GET /api/admin/stripe-reconciliation
        Query params: ?status=COVERED|SHORTFALL|UNKNOWN|ERROR (optional),
                      ?limit=100 (default 100, max 500),
                      ?since=<iso-timestamp> (optional).
        Returns most-recent-first list.

    GET /api/admin/stripe-reconciliation/{payment_intent_id}
        Returns a single reconciliation row.

    GET /api/admin/stripe-reconciliation/summary
        Aggregate totals across the ledger:
        { "total_rows": ..., "covered": ..., "shortfall": ...,
          "unknown": ..., "variance_cents_covered": ...,
          "variance_cents_shortfall": ... }
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from routes.payments import _auth

router = APIRouter(prefix="/api/admin/stripe-reconciliation", tags=["admin-reconciliation"])
security = HTTPBearer(auto_error=False)

_db_ref = {"db": None}


def set_db(db):
    _db_ref["db"] = db


def _db():
    return _db_ref["db"]


async def _require_admin(credentials: HTTPAuthorizationCredentials):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await _auth(credentials)
    if getattr(user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/summary")
async def summary(credentials: HTTPAuthorizationCredentials = Depends(security)):
    await _require_admin(credentials)
    db = _db()
    total = await db.payment_processing_reconciliation.count_documents({})
    covered = await db.payment_processing_reconciliation.count_documents({"reconciliation_status": "COVERED"})
    shortfall = await db.payment_processing_reconciliation.count_documents({"reconciliation_status": "SHORTFALL"})
    unknown = await db.payment_processing_reconciliation.count_documents({"reconciliation_status": "UNKNOWN"})
    error = await db.payment_processing_reconciliation.count_documents({"reconciliation_status": "ERROR"})

    # Variance totals
    pipeline_covered = [
        {"$match": {"reconciliation_status": "COVERED"}},
        {"$group": {"_id": None, "sum": {"$sum": "$variance_cents"}}},
    ]
    pipeline_shortfall = [
        {"$match": {"reconciliation_status": "SHORTFALL"}},
        {"$group": {"_id": None, "sum": {"$sum": "$variance_cents"}}},
    ]
    async def _sum(pipeline):
        async for r in db.payment_processing_reconciliation.aggregate(pipeline):
            return int(r.get("sum") or 0)
        return 0
    variance_covered = await _sum(pipeline_covered)
    variance_shortfall = await _sum(pipeline_shortfall)

    return {
        "total_rows": total,
        "covered": covered,
        "shortfall": shortfall,
        "unknown": unknown,
        "error": error,
        "variance_cents_covered": variance_covered,
        "variance_cents_shortfall": variance_shortfall,
        "engine_version": "iter482-P5.1-v1",
    }


@router.get("")
async def list_reconciliations(
    status: Optional[str] = Query(default=None, regex="^(COVERED|SHORTFALL|UNKNOWN|ERROR)$"),
    limit: int = Query(default=100, ge=1, le=500),
    since: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    await _require_admin(credentials)
    db = _db()
    q = {}
    if status:
        q["reconciliation_status"] = status
    if since:
        q["updated_at"] = {"$gte": since}
    cur = db.payment_processing_reconciliation.find(q, {"_id": 0}).sort("updated_at", -1).limit(limit)
    rows = [r async for r in cur]
    return {"rows": rows, "count": len(rows), "filter": q}


@router.get("/{payment_intent_id}")
async def get_reconciliation(
    payment_intent_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    await _require_admin(credentials)
    db = _db()
    row = await db.payment_processing_reconciliation.find_one(
        {"payment_intent_id": payment_intent_id}, {"_id": 0}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    return row
