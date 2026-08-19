"""iter498 — Admin Pending Payouts view + manual release.
iter499 — Adds filters, CSV export, Stripe Connect onboarding nudge, and
Payout History + audit timeline.

Backs the "Pending Payouts" and "Payout History" tabs in the Admin
Dashboard's Escrow & Settlements section. Endpoints (all
``require_admin``-gated):

  * ``GET  /api/admin/payouts/pending``       — list `seller_payouts`
    rows whose ``status`` is ``pending`` or ``requires_review``, with
    optional ``status`` / ``min_amount`` / ``max_amount`` server-side
    filters.  Enriched with seller name + email + Connect readiness and
    listing title.
  * ``POST /api/admin/payouts/{payout_id}/release`` — re-attempts the
    Stripe Connect transfer via the same happy path used by the
    automatic settlement flow. Uses the SAME Stripe idempotency key as
    the initial attempt (``payout-{listing_id}-{lot_number}``) so a
    real double-fire is deduped by Stripe.
  * ``POST /api/admin/payouts/{payout_id}/send-connect-onboarding``
    (iter499) — creates a Stripe Express Connect account if missing,
    generates an ``AccountLink`` and emails the seller. Records the
    action in ``admin_logs`` and short-circuits when the seller already
    has usable Connect readiness. Reuses the exact Express-account +
    AccountLink pattern from
    ``routes/admin_oversight.send_stripe_onboarding_link``.
  * ``GET  /api/admin/payouts/history`` (iter499) — list `seller_payouts`
    rows whose ``status`` is ``sent`` (or optionally ``requires_review``)
    sorted by ``sent_at`` desc, with the same server-side filters + a
    ``search`` query.
  * ``GET  /api/admin/payouts/{payout_id}/timeline`` (iter499) —
    reconstructs an audit timeline for a single payout by walking the
    row's own timestamps and the ``admin_logs`` collection. No
    fabricated events — only what is genuinely recorded.
  * ``GET  /api/admin/payouts/export.csv`` (iter499) — streams a CSV
    of the current filtered dataset (``scope=pending|history|all``).
    Uses Python's stdlib ``csv`` writer so quotes, commas and
    newlines are safely escaped.

Design notes:
  * The service layer (``services/seller_payouts.process_seller_payout``)
    already inserts a row with status ``pending`` and handles both
    Connect + fallback paths. We reuse it by directly invoking Stripe
    ``Transfer.create`` on retry so we don't re-insert a duplicate
    payout row — the existing row is upserted to ``sent`` instead.
  * All CSV bytes come from an in-memory ``StringIO`` — never a
    user-controlled buffer — with ``csv.writer`` handling escaping.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

admin_payouts_router = APIRouter(
    prefix="/admin/payouts",
    tags=["Admin — Payouts"],
)


PENDING_STATUSES = ("pending", "requires_review")
# iter499 — filter allow-list. "all" is not stored on the row; when the
# caller asks for it we simply don't apply a status filter.
ALLOWED_FILTER_STATUSES = ("pending", "requires_review", "sent")


class PendingPayoutRow(BaseModel):
    payout_id: str
    listing_id: str
    listing_title: Optional[str] = None
    lot_number: Optional[Any] = None
    seller_id: Optional[str] = None
    seller_name: Optional[str] = None
    seller_email: Optional[str] = None
    seller_has_connect: bool = False
    amount: float
    currency: str = "CAD"
    status: str
    created_at: Optional[str] = None
    section: Optional[str] = None
    source_transaction_id: Optional[str] = None
    # iter499 — extra history fields (populated for history rows; None on pending)
    sent_at: Optional[str] = None
    stripe_transfer_id: Optional[str] = None
    released_by_admin_id: Optional[str] = None
    released_by_admin_email: Optional[str] = None


class PendingPayoutsResponse(BaseModel):
    total: int
    rows: List[PendingPayoutRow]


class ReleasePayoutResponse(BaseModel):
    payout_id: str
    status: str  # sent | still_pending | not_found | already_sent
    stripe_transfer_id: Optional[str] = None
    error: Optional[str] = None


# iter499 — Send-Connect-onboarding envelope
class ConnectOnboardingResponse(BaseModel):
    payout_id: str
    seller_id: str
    status: str  # sent | already_connected | error
    onboarding_url: Optional[str] = None
    stripe_connect_account_id: Optional[str] = None
    email_dispatched: bool = False
    error: Optional[str] = None


class TimelineEvent(BaseModel):
    at: str
    kind: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    detail: Optional[str] = None


class PayoutTimelineResponse(BaseModel):
    payout_id: str
    events: List[TimelineEvent]


# ─────────────────────────── helpers (iter499) ──────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape_regex(value: str) -> str:
    return re.escape(value)


def _build_query(
    *,
    status: Optional[str],
    default_statuses: List[str],
    min_amount: Optional[float],
    max_amount: Optional[float],
    search: Optional[str],
) -> Dict[str, Any]:
    """Build a MongoDB filter matching the frontend controls. Rejects any
    status value not in the allow-list — never trust the client to
    invent a payout state."""
    query: Dict[str, Any] = {}
    if status and status.strip().lower() != "all":
        s = status.strip().lower()
        if s not in ALLOWED_FILTER_STATUSES:
            raise HTTPException(status_code=400, detail=f"invalid_status:{s}")
        query["status"] = s
    else:
        query["status"] = {"$in": default_statuses}
    if min_amount is not None or max_amount is not None:
        amt: Dict[str, float] = {}
        if min_amount is not None:
            amt["$gte"] = float(min_amount)
        if max_amount is not None:
            amt["$lte"] = float(max_amount)
        query["amount"] = amt
    if search:
        s = _escape_regex(search.strip())
        if s:
            query["$or"] = [
                {"listing_id": {"$regex": s, "$options": "i"}},
                {"listing_title": {"$regex": s, "$options": "i"}},
                {"seller_id": {"$regex": s, "$options": "i"}},
            ]
    return query


async def _fetch_payouts(
    db,
    query: Dict[str, Any],
    *,
    limit: int,
    sort_field: str = "created_at",
) -> tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    cursor = db.seller_payouts.find(query, {"_id": 0}).sort(sort_field, -1).limit(limit)
    payouts: List[Dict[str, Any]] = await cursor.to_list(length=limit)
    seller_ids = list({p.get("seller_id") for p in payouts if p.get("seller_id")})
    sellers_by_id: Dict[str, Dict[str, Any]] = {}
    if seller_ids:
        async for s in db.users.find(
            {"id": {"$in": seller_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1,
             "stripe_connect_account_id": 1,
             "stripe_connect_payouts_enabled": 1,
             "stripe_connect_onboarding_complete": 1},
        ):
            sellers_by_id[s["id"]] = s
    return payouts, sellers_by_id


def _row_from_payout(p: Dict[str, Any], seller: Dict[str, Any]) -> PendingPayoutRow:
    has_connect = bool(
        seller.get("stripe_connect_account_id")
        and (
            seller.get("stripe_connect_payouts_enabled")
            or seller.get("stripe_connect_onboarding_complete")
        )
    )
    return PendingPayoutRow(
        payout_id=str(p.get("id") or ""),
        listing_id=str(p.get("listing_id") or ""),
        listing_title=p.get("listing_title"),
        lot_number=p.get("lot_number"),
        seller_id=p.get("seller_id"),
        seller_name=seller.get("name"),
        seller_email=seller.get("email"),
        seller_has_connect=has_connect,
        amount=float(p.get("amount") or 0.0),
        currency=str(p.get("currency") or "CAD"),
        status=str(p.get("status") or "pending"),
        created_at=p.get("created_at"),
        section=p.get("section"),
        source_transaction_id=p.get("source_transaction_id"),
        sent_at=p.get("sent_at"),
        stripe_transfer_id=p.get("stripe_transfer_id"),
        released_by_admin_id=p.get("released_by_admin_id"),
        released_by_admin_email=p.get("released_by_admin_email"),
    )


def _rows_from_payouts(
    payouts: List[Dict[str, Any]],
    sellers_by_id: Dict[str, Dict[str, Any]],
) -> List[PendingPayoutRow]:
    return [
        _row_from_payout(p, sellers_by_id.get(p.get("seller_id") or "") or {})
        for p in payouts
    ]


@admin_payouts_router.get(
    "/pending",
    response_model=PendingPayoutsResponse,
    summary="List seller_payouts rows awaiting manual release",
)
async def list_pending_payouts(
    limit: int = Query(200, ge=1, le=1000),
    status: Optional[str] = Query(None, description="pending | requires_review | all"),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None, max_length=200),
    current_user: User = Depends(require_admin),
) -> PendingPayoutsResponse:
    """Return the queue of payouts that need admin attention.

    Server-side filters (iter499):
      * ``status`` — one of ``pending``, ``requires_review``, or
        ``all`` (default: both pending + requires_review).
      * ``min_amount`` / ``max_amount`` — inclusive CAD bounds.
      * ``search`` — case-insensitive contains on listing_id,
        listing_title, or seller_id.

    A row lands here when:
      * the seller does not have a Stripe Connect account yet, OR
      * the initial ``Transfer.create`` failed and the row was flagged
        ``requires_review`` by a downstream job.

    Results are newest-first so ops can process the freshest cases.
    """
    db = get_db()
    query = _build_query(status=status, default_statuses=list(PENDING_STATUSES),
                         min_amount=min_amount, max_amount=max_amount, search=search)
    payouts, sellers_by_id = await _fetch_payouts(db, query, limit=limit, sort_field="created_at")
    rows = _rows_from_payouts(payouts, sellers_by_id)
    return PendingPayoutsResponse(total=len(rows), rows=rows)


@admin_payouts_router.post(
    "/{payout_id}/release",
    response_model=ReleasePayoutResponse,
    summary="Manually release a pending seller payout via Stripe Connect",
)
async def release_pending_payout(
    payout_id: str,
    current_user: User = Depends(require_admin),
) -> ReleasePayoutResponse:
    """Re-run the Stripe Connect transfer for a payout row.

    The endpoint is idempotent: Stripe's ``idempotency_key`` guarantees
    that a re-attempt on an already-transferred amount returns the
    original transfer instead of double-paying. On success we update the
    row to ``status=sent`` with ``stripe_transfer_id``, ``sent_at``, and
    an ``admin_released_by`` audit stamp. A ``payout_released_manually``
    row is appended to ``admin_logs``.
    """
    db = get_db()
    payout = await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not payout:
        raise HTTPException(status_code=404, detail="payout_not_found")

    current_status = str(payout.get("status") or "")
    if current_status == "sent":
        return ReleasePayoutResponse(
            payout_id=payout_id,
            status="already_sent",
            stripe_transfer_id=payout.get("stripe_transfer_id"),
        )
    if current_status not in PENDING_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"payout_not_in_pending_state (current={current_status})",
        )

    seller_id = payout.get("seller_id")
    if not seller_id:
        raise HTTPException(status_code=400, detail="payout_missing_seller_id")

    seller = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1,
         "stripe_connect_account_id": 1,
         "stripe_connect_payouts_enabled": 1,
         "stripe_connect_onboarding_complete": 1},
    )
    acct = (seller or {}).get("stripe_connect_account_id")
    connect_ready = bool(
        acct and (
            (seller or {}).get("stripe_connect_payouts_enabled")
            or (seller or {}).get("stripe_connect_onboarding_complete")
        )
    )
    if not connect_ready:
        return ReleasePayoutResponse(
            payout_id=payout_id,
            status="still_pending",
            error="seller_has_no_active_stripe_connect_account",
        )

    listing_id = str(payout.get("listing_id") or "")
    lot_number = payout.get("lot_number")
    amount = float(payout.get("amount") or 0.0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="payout_amount_not_positive")

    transfer_id: Optional[str] = None
    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
        transfer = stripe.Transfer.create(
            amount=int(round(amount * 100)),
            currency=str(payout.get("currency") or "CAD").lower(),
            destination=acct,
            metadata={
                "listing_id": listing_id,
                "section": payout.get("section") or "",
                "seller_id": seller_id,
                "platform": "bidvex",
                "released_by_admin_id": getattr(current_user, "id", None) or "",
                "manual_release": "true",
            },
            idempotency_key=f"payout-{listing_id}-{lot_number or 0}",
        )
        transfer_id = getattr(transfer, "id", None) or (
            transfer.get("id") if isinstance(transfer, dict) else None
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[admin_payouts] manual release Stripe error for %s: %s", payout_id, exc)
        # Record the failure so ops can see the reason
        try:
            await db.seller_payouts.update_one(
                {"id": payout_id},
                {"$set": {
                    "status": "requires_review",
                    "last_error": f"{type(exc).__name__}: {exc}",
                    "last_error_at": _now_iso(),
                    "last_attempted_by_admin_id": getattr(current_user, "id", None),
                }},
            )
        except Exception:  # pragma: no cover — defensive
            pass
        return ReleasePayoutResponse(
            payout_id=payout_id,
            status="still_pending",
            error=f"stripe_transfer_failed: {type(exc).__name__}",
        )

    if not transfer_id:
        return ReleasePayoutResponse(
            payout_id=payout_id,
            status="still_pending",
            error="stripe_returned_no_transfer_id",
        )

    now = _now_iso()
    await db.seller_payouts.update_one(
        {"id": payout_id},
        {"$set": {
            "status": "sent",
            "stripe_transfer_id": transfer_id,
            "sent_at": now,
            "released_by_admin_id": getattr(current_user, "id", None),
            "released_by_admin_email": getattr(current_user, "email", None),
            "released_at": now,
        }},
    )
    # Best-effort: stamp listing status and drop any stale pending_payouts row
    try:
        section = payout.get("section") or ""
        collections = {
            "marketplace": "listings",
            "lots": "multi_item_listings",
            "storage": "storage_auctions",
            "vehicles": "vehicle_listings",
        }
        coll = collections.get(section, "listings")
        await db[coll].update_one(
            {"id": listing_id},
            {"$set": {"payout_status": "payout_sent", "payout_status_at": now}},
        )
        await db.pending_payouts.update_many(
            {"listing_id": listing_id, "seller_id": seller_id, "lot_number": lot_number},
            {"$set": {"status": "released", "released_at": now,
                      "released_by_admin_id": getattr(current_user, "id", None)}},
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("[admin_payouts] post-release housekeeping warning: %s", exc)

    # Notify the seller (bell + email) via the existing helper so branding is uniform
    try:
        from services.seller_payouts import _notify_seller_payout_sent
        await _notify_seller_payout_sent(
            db,
            seller,
            payout.get("listing_title") or listing_id,
            amount,
            transfer_id,
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("[admin_payouts] seller notify skipped: %s", exc)

    # Audit trail
    try:
        await db.admin_logs.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": getattr(current_user, "id", None),
            "admin_email": getattr(current_user, "email", None),
            "action": "payout.manual_release",
            "target_type": "seller_payout",
            "target_id": payout_id,
            "timestamp": datetime.now(timezone.utc),
            "details": {
                "listing_id": listing_id,
                "seller_id": seller_id,
                "amount": amount,
                "stripe_transfer_id": transfer_id,
            },
        })
    except Exception as exc:  # pragma: no cover — audit best-effort
        logger.warning("[admin_payouts] audit log insert failed: %s", exc)

    return ReleasePayoutResponse(
        payout_id=payout_id,
        status="sent",
        stripe_transfer_id=transfer_id,
    )


# ══════════════════════════════════════════════════════════════════
# iter499 — History, timeline, CSV export, Connect onboarding nudge
# ══════════════════════════════════════════════════════════════════

@admin_payouts_router.get(
    "/history",
    response_model=PendingPayoutsResponse,
    summary="List seller_payouts rows already released (sent) — with filters",
)
async def list_payout_history(
    limit: int = Query(200, ge=1, le=1000),
    status: Optional[str] = Query("sent", description="sent | requires_review | all"),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None, max_length=200),
    current_user: User = Depends(require_admin),
) -> PendingPayoutsResponse:
    """Audit view of sent payouts (or every status when ``status=all``).

    The primary use case is ops-side reconciliation: which admin
    released which transfer, when, for how much. Sorted by
    ``sent_at`` desc so the most recent release is on top.
    """
    db = get_db()
    query = _build_query(status=status, default_statuses=["sent"],
                         min_amount=min_amount, max_amount=max_amount, search=search)
    payouts, sellers_by_id = await _fetch_payouts(db, query, limit=limit, sort_field="sent_at")
    rows = _rows_from_payouts(payouts, sellers_by_id)
    return PendingPayoutsResponse(total=len(rows), rows=rows)


@admin_payouts_router.get(
    "/{payout_id}/timeline",
    response_model=PayoutTimelineResponse,
    summary="Reconstruct an audit timeline for a single payout",
)
async def payout_timeline(
    payout_id: str,
    current_user: User = Depends(require_admin),
) -> PayoutTimelineResponse:
    """Walks the payout row's own timestamps and the ``admin_logs``
    collection to build a chronological audit trail. **No fabricated
    events** — every entry corresponds to a genuine timestamped record.
    """
    db = get_db()
    payout = await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not payout:
        raise HTTPException(status_code=404, detail="payout_not_found")

    events: List[TimelineEvent] = []

    def _push(at: Optional[str], kind: str, actor_id: Optional[str] = None,
              actor_email: Optional[str] = None, detail: Optional[str] = None):
        if not at:
            return
        events.append(TimelineEvent(
            at=str(at), kind=kind, actor_id=actor_id,
            actor_email=actor_email, detail=detail,
        ))

    _push(payout.get("created_at"), "payout_created",
          detail=f"amount=${float(payout.get('amount') or 0):.2f} {payout.get('currency') or 'CAD'} · status=pending")
    _push(payout.get("last_error_at"), "payout_marked_requires_review",
          actor_id=payout.get("last_attempted_by_admin_id"),
          detail=payout.get("last_error"))
    _push(payout.get("sent_at"), "payout_released",
          actor_id=payout.get("released_by_admin_id"),
          actor_email=payout.get("released_by_admin_email"),
          detail=f"stripe_transfer_id={payout.get('stripe_transfer_id')}")
    _push(payout.get("onboarding_link_sent_at"), "onboarding_link_sent",
          actor_id=payout.get("onboarding_link_sent_by_admin_id"),
          actor_email=payout.get("onboarding_link_sent_by_admin_email"),
          detail=payout.get("onboarding_link_last_url"))

    # admin_logs entries targeted at this payout
    async for log in db.admin_logs.find(
        {"target_type": "seller_payout", "target_id": payout_id},
        {"_id": 0, "action": 1, "admin_id": 1, "admin_email": 1,
         "timestamp": 1, "details": 1},
    ):
        ts = log.get("timestamp")
        ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else (str(ts) if ts else None)
        detail = None
        d = log.get("details")
        if isinstance(d, dict):
            # Keep the payload short + safe (no secrets)
            keys = ("stripe_transfer_id", "onboarding_url", "amount", "reason")
            short = {k: d.get(k) for k in keys if k in d}
            if short:
                detail = ", ".join(f"{k}={v}" for k, v in short.items())
        _push(ts_iso, f"admin.{log.get('action') or 'action'}",
              actor_id=log.get("admin_id"),
              actor_email=log.get("admin_email"),
              detail=detail)

    # Sort oldest → newest so the UI can render top-down
    events.sort(key=lambda e: e.at)
    return PayoutTimelineResponse(payout_id=payout_id, events=events)


@admin_payouts_router.get(
    "/export.csv",
    summary="Export the filtered payout dataset as CSV",
)
async def export_payouts_csv(
    scope: str = Query("pending", description="pending | history | all"),
    status: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None, max_length=200),
    limit: int = Query(1000, ge=1, le=5000),
    current_user: User = Depends(require_admin),
) -> StreamingResponse:
    """Stream the filtered payouts as CSV.

    Column set is intentionally locked so the export never leaks
    Stripe secrets, tokens, or internal-only metadata. ``csv.writer``
    handles quote/comma/newline escaping.
    """
    db = get_db()
    scope_l = (scope or "pending").strip().lower()
    if scope_l == "pending":
        defaults = list(PENDING_STATUSES)
        sort_field = "created_at"
    elif scope_l == "history":
        defaults = ["sent"]
        sort_field = "sent_at"
    elif scope_l == "all":
        defaults = list(ALLOWED_FILTER_STATUSES)
        sort_field = "created_at"
    else:
        raise HTTPException(status_code=400, detail="invalid_scope")

    query = _build_query(status=status, default_statuses=defaults,
                         min_amount=min_amount, max_amount=max_amount, search=search)
    payouts, sellers_by_id = await _fetch_payouts(db, query, limit=limit, sort_field=sort_field)
    rows = _rows_from_payouts(payouts, sellers_by_id)

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "payout_id", "auction_id", "listing_title", "lot_number",
        "seller_id", "seller_name", "seller_email",
        "amount", "currency", "status", "created_at",
        "sent_at", "stripe_transfer_id",
        "released_by_admin_id", "released_by_admin_email",
    ])
    for r in rows:
        writer.writerow([
            r.payout_id, r.listing_id, r.listing_title or "", r.lot_number or "",
            r.seller_id or "", r.seller_name or "", r.seller_email or "",
            f"{r.amount:.2f}", r.currency, r.status, r.created_at or "",
            r.sent_at or "", r.stripe_transfer_id or "",
            r.released_by_admin_id or "", r.released_by_admin_email or "",
        ])
    csv_bytes = buf.getvalue().encode("utf-8-sig")  # BOM for Excel
    filename = f"bidvex_payouts_{scope_l}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@admin_payouts_router.post(
    "/{payout_id}/send-connect-onboarding",
    response_model=ConnectOnboardingResponse,
    summary="Create/refresh a Stripe Connect Express onboarding link and email the seller",
)
async def send_connect_onboarding(
    payout_id: str,
    current_user: User = Depends(require_admin),
) -> ConnectOnboardingResponse:
    """Kicks off the seller's Stripe Express onboarding so a stuck
    payout can be settled next cycle.

    Behavior:
      * 404 if the payout row doesn't exist.
      * 400 if the payout has no seller_id (data corruption).
      * ``status=already_connected`` (no Stripe call, no email) if the
        seller's Connect account is already usable — this protects
        both the seller (no spam) and BidVex from accidental account
        churn. This mirrors the "safe rejection" contract in the spec.
      * Otherwise: creates a Stripe Express account on-demand (only
        when the seller doesn't already have a ``stripe_connect_account_id``),
        generates a fresh ``AccountLink`` (Stripe treats these as
        short-lived so refreshing is safe), emails the seller via the
        existing ``send_unified_email`` new_feature template, stamps
        the payout row with ``onboarding_link_sent_at`` +
        ``onboarding_link_sent_by_admin_id/email`` (so the timeline
        endpoint can show the event without an additional collection),
        and writes an ``admin_logs`` audit row.
    """
    db = get_db()
    payout = await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
    if not payout:
        raise HTTPException(status_code=404, detail="payout_not_found")
    seller_id = payout.get("seller_id")
    if not seller_id:
        raise HTTPException(status_code=400, detail="payout_missing_seller_id")

    seller = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1,
         "stripe_connect_account_id": 1,
         "stripe_connect_payouts_enabled": 1,
         "stripe_connect_onboarding_complete": 1},
    )
    if not seller:
        raise HTTPException(status_code=404, detail="seller_not_found")
    if not seller.get("email"):
        raise HTTPException(status_code=400, detail="seller_missing_email")

    already_connected = bool(
        seller.get("stripe_connect_account_id")
        and (
            seller.get("stripe_connect_payouts_enabled")
            or seller.get("stripe_connect_onboarding_complete")
        )
    )
    if already_connected:
        return ConnectOnboardingResponse(
            payout_id=payout_id,
            seller_id=seller_id,
            status="already_connected",
            stripe_connect_account_id=seller.get("stripe_connect_account_id"),
            email_dispatched=False,
        )

    # Create/refresh the AccountLink — same shape as the affiliate flow
    onboarding_url: Optional[str] = None
    connect_id: Optional[str] = seller.get("stripe_connect_account_id")
    try:
        import stripe as _stripe
        _stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
        if not connect_id:
            account = _stripe.Account.create(
                type="express",
                country="CA",
                email=seller["email"],
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers":     {"requested": True},
                },
                business_type="individual",
                metadata={
                    "user_id": seller_id,
                    "platform": "bidvex",
                    "source": "admin_payout_onboarding_nudge",
                    "payout_id": payout_id,
                },
            )
            connect_id = account.id
            await db.users.update_one(
                {"id": seller_id},
                {"$set": {
                    "stripe_connect_account_id": connect_id,
                    "stripe_connect_onboarding_complete": False,
                    "updated_at": _now_iso(),
                }},
            )

        base_url = (
            os.environ.get("PUBLIC_BASE_URL")
            or os.environ.get("REACT_APP_BACKEND_URL")
            or "https://bidvex.com"
        ).rstrip("/")
        link = _stripe.AccountLink.create(
            account=connect_id,
            refresh_url=f"{base_url}/seller/dashboard?stripe_refresh=true",
            return_url=f"{base_url}/seller/dashboard?stripe=connected",
            type="account_onboarding",
            collection_options={"fields": "eventually_due"},
        )
        onboarding_url = getattr(link, "url", None) or (link.get("url") if isinstance(link, dict) else None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[admin_payouts] onboarding link create failed for %s: %s", payout_id, exc)
        return ConnectOnboardingResponse(
            payout_id=payout_id,
            seller_id=seller_id,
            status="error",
            error=f"stripe_error: {type(exc).__name__}",
        )

    if not onboarding_url:
        return ConnectOnboardingResponse(
            payout_id=payout_id,
            seller_id=seller_id,
            status="error",
            error="stripe_returned_no_onboarding_url",
        )

    # Best-effort email dispatch
    email_dispatched = False
    try:
        from services.emails._email_core import send_unified_email
        amount = float(payout.get("amount") or 0.0)
        currency = str(payout.get("currency") or "CAD")
        listing_title = payout.get("listing_title") or "your BidVex auction"
        await send_unified_email(
            email_type="new_feature",
            user=seller,
            data={
                "subject_override": "💰 Connect Your Stripe Account to Receive Your BidVex Payout",
                "headline": "Connect Stripe to receive your payout",
                "subheadline": "One quick step to get your funds transferred.",
                "body_html": (
                    f"<p>Hi {seller.get('name', 'Seller')},</p>"
                    f"<p>Your BidVex payout of "
                    f"<strong>${amount:.2f} {currency}</strong> for "
                    f"<strong>{listing_title}</strong> is ready to be transferred.</p>"
                    "<p>Before we can send it, please finish setting up your Stripe "
                    "Express account — it takes less than 2 minutes.</p>"
                    "<p>Click the secure link below to complete onboarding. The link "
                    "is short-lived; you can request a fresh one anytime from your "
                    f"<a href='{base_url}/seller/dashboard'>Seller Dashboard</a>.</p>"
                ),
                "cta_label": "Connect Stripe Account →",
                "cta_url":   onboarding_url,
            },
        )
        email_dispatched = True
    except Exception as exc:  # noqa: BLE001 — email is best-effort
        logger.warning("[admin_payouts] onboarding email send failed for %s: %s", payout_id, exc)

    now = _now_iso()
    # Stamp the payout row so the timeline endpoint surfaces the action
    await db.seller_payouts.update_one(
        {"id": payout_id},
        {"$set": {
            "onboarding_link_sent_at": now,
            "onboarding_link_sent_by_admin_id": getattr(current_user, "id", None),
            "onboarding_link_sent_by_admin_email": getattr(current_user, "email", None),
            "onboarding_link_last_url": onboarding_url,
        }},
    )
    # Audit trail
    try:
        await db.admin_logs.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": getattr(current_user, "id", None),
            "admin_email": getattr(current_user, "email", None),
            "action": "payout.send_connect_onboarding",
            "target_type": "seller_payout",
            "target_id": payout_id,
            "timestamp": datetime.now(timezone.utc),
            "details": {
                "seller_id": seller_id,
                "stripe_connect_account_id": connect_id,
                "email_dispatched": email_dispatched,
                # NOTE: not logging the raw onboarding_url to keep the log lean
            },
        })
    except Exception as exc:  # pragma: no cover — audit best-effort
        logger.warning("[admin_payouts] audit log insert failed: %s", exc)

    return ConnectOnboardingResponse(
        payout_id=payout_id,
        seller_id=seller_id,
        status="sent",
        onboarding_url=onboarding_url,
        stripe_connect_account_id=connect_id,
        email_dispatched=email_dispatched,
    )


__all__ = ["admin_payouts_router"]
