"""
iter482 P5.1 + P6 — Admin Stripe Reconciliation API
====================================================

Read-only endpoints exposing the canonical
``payment_processing_reconciliation`` collection so administrators can
audit:

  * every buyer / seller / partner Stripe payment
  * estimated fee vs payer-borne recovery vs actual Stripe BalanceTransaction fee
  * variance and reconciliation status (RECONCILED / VARIANCE / SHORTFALL / PENDING / ERROR)
  * card country resolved from Stripe payment_method_details

Endpoints
---------

    GET /api/admin/stripe-reconciliation/summary
        Aggregate totals with the P6-canonical vocabulary and legacy
        internal counts.

    GET /api/admin/stripe-reconciliation
        Filters (all optional):
            status         RECONCILED|VARIANCE|SHORTFALL|PENDING|ERROR
            jurisdiction   domestic|international
            payer_role     buyer|seller|partner|platform
            date_from      ISO timestamp (inclusive)
            date_to        ISO timestamp (inclusive)
            search         substring of payment_intent_id / charge_id /
                           balance_transaction_id / listing_id / invoice_id /
                           seller_id / buyer_id / payer_id / reference
            limit          1…500 (default 100)
            since          legacy alias for date_from
        Returns most-recent-first list.

    GET /api/admin/stripe-reconciliation/{payment_intent_id}
        Single reconciliation row.
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any

from routes.payments import _auth
from services.stripe_reconciliation_service import (
    STATUS_ALIASES,
    public_status,
)

router = APIRouter(prefix="/api/admin/stripe-reconciliation", tags=["admin-reconciliation"])
security = HTTPBearer(auto_error=False)

_db_ref = {"db": None}


def set_db(db):
    _db_ref["db"] = db


def _db():
    return _db_ref["db"]


# ─────────────────────────────────────────────────────────────────
# P6 canonical status vocabulary that the admin dashboard consumes.
# The internal storage keeps the legacy COVERED/UNKNOWN values for
# backwards compat; we translate on the way out via ``public_status``
# and translate incoming filters on the way in via the inverse map.
# ─────────────────────────────────────────────────────────────────
_STATUS_PUBLIC_TO_INTERNAL: Dict[str, str] = {
    "RECONCILED": "COVERED",
    "VARIANCE":   "COVERED",  # any covered row with variance != 0 is a "VARIANCE" bucket UI-side
    "SHORTFALL":  "SHORTFALL",
    "PENDING":    "UNKNOWN",
    "ERROR":      "ERROR",
}


async def _require_admin(credentials: HTTPAuthorizationCredentials):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await _auth(credentials)
    if getattr(user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def _decorate_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Attach the P6-canonical public status + a UI-derived variance
    subtype for RECONCILED rows that still have a non-zero variance.
    """
    internal = (row.get("reconciliation_status") or "").upper()
    row["reconciliation_status_public"] = public_status(internal)
    # UI hint — a positive variance on a covered row (BidVex over-collected)
    # is still worth surfacing separately from a zero-variance perfect
    # match. Frontend uses this to colour the row amber vs green.
    if internal == "COVERED" and (row.get("variance_cents") or 0) != 0:
        row["reconciliation_status_ui"] = "VARIANCE"
    else:
        row["reconciliation_status_ui"] = row["reconciliation_status_public"]
    return row


@router.get("/summary")
async def summary(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Aggregate totals — exposes both P6-canonical (reconciled/variance/
    shortfall/pending/error) and legacy internal (covered/…) counts so
    the admin dashboard renders correctly without refactoring existing
    callers.
    """
    await _require_admin(credentials)
    db = _db()

    total = await db.payment_processing_reconciliation.count_documents({})
    covered = await db.payment_processing_reconciliation.count_documents(
        {"reconciliation_status": "COVERED"}
    )
    shortfall = await db.payment_processing_reconciliation.count_documents(
        {"reconciliation_status": "SHORTFALL"}
    )
    unknown = await db.payment_processing_reconciliation.count_documents(
        {"reconciliation_status": "UNKNOWN"}
    )
    error = await db.payment_processing_reconciliation.count_documents(
        {"reconciliation_status": "ERROR"}
    )
    variance = await db.payment_processing_reconciliation.count_documents(
        {"reconciliation_status": "COVERED", "variance_cents": {"$ne": 0}}
    )
    reconciled = max(covered - variance, 0)

    async def _sum(pipeline):
        async for r in db.payment_processing_reconciliation.aggregate(pipeline):
            return int(r.get("sum") or 0)
        return 0

    variance_covered = await _sum([
        {"$match": {"reconciliation_status": "COVERED"}},
        {"$group": {"_id": None, "sum": {"$sum": "$variance_cents"}}},
    ])
    variance_shortfall = await _sum([
        {"$match": {"reconciliation_status": "SHORTFALL"}},
        {"$group": {"_id": None, "sum": {"$sum": "$variance_cents"}}},
    ])
    total_actual = await _sum([
        {"$group": {"_id": None, "sum": {"$sum": "$actual_cents"}}},
    ])
    total_estimated = await _sum([
        {"$group": {"_id": None, "sum": {"$sum": "$estimated_cents"}}},
    ])
    total_recovery = await _sum([
        {"$group": {"_id": None, "sum": {"$sum": "$recovery_cents"}}},
    ])

    return {
        # P6-canonical vocabulary (used by the admin dashboard).
        "total_rows": total,
        "reconciled": reconciled,
        "variance":   variance,
        "shortfall":  shortfall,
        "pending":    unknown,
        "error":      error,
        # Cent totals — never round on the frontend, backend is
        # authoritative.
        "estimated_cents_total":  total_estimated,
        "recovery_cents_total":   total_recovery,
        "actual_cents_total":     total_actual,
        "variance_cents_covered": variance_covered,
        "variance_cents_shortfall": variance_shortfall,
        # Legacy fields — retained so existing callers keep working.
        "covered": covered,
        "unknown": unknown,
        "engine_version": "iter482-P6-v1",
    }


@router.get("")
async def list_reconciliations(
    status: Optional[str] = Query(default=None),
    jurisdiction: Optional[str] = Query(
        default=None, regex="^(domestic|international)$"
    ),
    payer_role: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=120),
    since: Optional[str] = Query(default=None),  # legacy alias
    limit: int = Query(default=100, ge=1, le=500),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    await _require_admin(credentials)
    db = _db()
    q: Dict[str, Any] = {}

    # Status filter — accepts both P6-canonical + legacy vocabulary.
    if status:
        s = status.upper()
        if s in STATUS_ALIASES.values() or s in STATUS_ALIASES:
            # Convert P6 canonical → internal; VARIANCE = COVERED w/ non-zero
            if s == "VARIANCE":
                q["reconciliation_status"] = "COVERED"
                q["variance_cents"] = {"$ne": 0}
            elif s == "RECONCILED":
                q["reconciliation_status"] = "COVERED"
                # RECONCILED = COVERED with zero variance for the strict UI view.
                # Loose interpretation (all covered) is available under status=COVERED.
                q["variance_cents"] = 0
            else:
                internal = _STATUS_PUBLIC_TO_INTERNAL.get(s, s)
                q["reconciliation_status"] = internal
        else:
            # Silently ignore unknown status — the frontend uses a fixed
            # menu, so this only happens on hand-crafted requests.
            pass

    if jurisdiction:
        q["resolved_jurisdiction"] = jurisdiction.lower()

    if payer_role:
        q["payer_role"] = payer_role.lower()

    # Date filters (updated_at is stored as ISO-8601 string; ISO strings
    # sort lexicographically so $gte/$lte work directly).
    date_range: Dict[str, Any] = {}
    if date_from:
        date_range["$gte"] = date_from
    elif since:
        date_range["$gte"] = since
    if date_to:
        date_range["$lte"] = date_to
    if date_range:
        q["updated_at"] = date_range

    # Free-text search across the identifier columns. Case-insensitive
    # substring — projection is limited to indexed / low-cardinality
    # fields to keep this cheap.
    if search:
        s = search.strip()
        if s:
            escaped = _regex_escape(s)
            q["$or"] = [
                {"payment_intent_id":       {"$regex": escaped, "$options": "i"}},
                {"charge_id":               {"$regex": escaped, "$options": "i"}},
                {"balance_transaction_id":  {"$regex": escaped, "$options": "i"}},
                {"listing_id":              {"$regex": escaped, "$options": "i"}},
                {"invoice_id":              {"$regex": escaped, "$options": "i"}},
                {"seller_id":               {"$regex": escaped, "$options": "i"}},
                {"buyer_id":                {"$regex": escaped, "$options": "i"}},
                {"payer_id":                {"$regex": escaped, "$options": "i"}},
                {"reference":               {"$regex": escaped, "$options": "i"}},
            ]

    cur = (
        db.payment_processing_reconciliation
        .find(q, {"_id": 0})
        .sort("updated_at", -1)
        .limit(limit)
    )
    rows = [_decorate_row(r) async for r in cur]
    return {"rows": rows, "count": len(rows), "filter": q}


def _regex_escape(s: str) -> str:
    """Escape user-supplied search substring for MongoDB $regex."""
    return "".join(("\\" + ch) if ch in r".^$*+?()[]{}|\\" else ch for ch in s)


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
    return _decorate_row(row)
