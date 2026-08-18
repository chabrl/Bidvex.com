"""iter498 — Admin Pending Payouts view + manual release.

Backs the "Pending Payouts" tab in the Admin Dashboard's Escrow &
Settlements section. Two endpoints, both ``require_admin``-gated:

  * ``GET  /api/admin/payouts/pending``       — list `seller_payouts`
    rows whose ``status`` is ``pending`` or ``requires_review``,
    enriched with seller name + email and listing title.
  * ``POST /api/admin/payouts/{payout_id}/release`` — re-attempts the
    Stripe Connect transfer via the same happy path used by the
    automatic settlement flow. On success the row is updated to
    ``status=sent`` with a ``stripe_transfer_id``. When the seller
    still lacks Stripe Connect, the endpoint reports the reason so
    Ops know they need to nudge the seller to onboard.

Design notes:
  * The service layer (``services/seller_payouts.process_seller_payout``)
    already inserts a row with status ``pending`` and handles both
    Connect + fallback paths. We reuse it by directly invoking Stripe
    ``Transfer.create`` on retry so we don't re-insert a duplicate
    payout row — the existing row is upserted to ``sent`` instead.
  * The row's ``stripe_transfer_id`` uses the same idempotency-key
    shape as the initial attempt (`payout-{listing_id}-{lot_number}`)
    so Stripe safely dedupes a real double-fire.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

admin_payouts_router = APIRouter(
    prefix="/admin/payouts",
    tags=["Admin — Payouts"],
)


PENDING_STATUSES = ("pending", "requires_review")


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


class PendingPayoutsResponse(BaseModel):
    total: int
    rows: List[PendingPayoutRow]


class ReleasePayoutResponse(BaseModel):
    payout_id: str
    status: str  # sent | still_pending | not_found | already_sent
    stripe_transfer_id: Optional[str] = None
    error: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@admin_payouts_router.get(
    "/pending",
    response_model=PendingPayoutsResponse,
    summary="List seller_payouts rows awaiting manual release",
)
async def list_pending_payouts(
    limit: int = Query(200, ge=1, le=1000),
    current_user: User = Depends(require_admin),
) -> PendingPayoutsResponse:
    """Return the queue of payouts that need admin attention.

    A row lands here when:
      * the seller does not have a Stripe Connect account yet, OR
      * the initial ``Transfer.create`` failed and the row was flagged
        ``requires_review`` by a downstream job.

    Results are newest-first so ops can process the freshest cases.
    """
    db = get_db()
    cursor = (
        db.seller_payouts
        .find({"status": {"$in": list(PENDING_STATUSES)}}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    payouts: List[Dict[str, Any]] = await cursor.to_list(length=limit)

    # Batch-fetch seller profiles so the table can show names + Connect status
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

    rows: List[PendingPayoutRow] = []
    for p in payouts:
        seller = sellers_by_id.get(p.get("seller_id") or "") or {}
        has_connect = bool(
            seller.get("stripe_connect_account_id")
            and (
                seller.get("stripe_connect_payouts_enabled")
                or seller.get("stripe_connect_onboarding_complete")
            )
        )
        rows.append(PendingPayoutRow(
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
        ))

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


__all__ = ["admin_payouts_router"]
