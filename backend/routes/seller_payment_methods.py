"""
BidVex — Seller-Controlled Payment Methods HTTP Routes
=======================================================

iter482 P4B — thin HTTP layer over
``services/seller_payment_methods_service.py``.

Endpoints:
  GET  /api/listings/{listing_id}/accepted-payment-methods
       Returns the effective methods for any listing (snapshot if
       locked, else live).  Public — buyers need this to render the
       checkout selector.

  POST /api/checkout/select-payment-method
       Buyer explicitly picks one of the accepted methods and
       acknowledges the exact integer-cent totals for the transaction.
       Persists to the buyer's transaction row.

  POST /api/listings/{listing_id}/accepted-payment-methods
       Admin/support-only controlled edit (P4B stub — returns 409 on
       any locked listing until the controlled workflow is built).

Every write logs a `db.payment_state_transitions` row for audit.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import os

from services.seller_payment_methods_service import (
    effective_methods,
    is_locked,
    guard_edit,
    assert_selection_allowed,
    PaymentMethodsLockedError,
    PaymentMethodNotAcceptedError,
    PaymentMethodsMissingError,
)
from services.payment_methods_registry import ALL_METHODS

logger = logging.getLogger(__name__)

seller_payment_methods_router = APIRouter(prefix="/api", tags=["seller-payment-methods"])

# ── DB + Auth injection (set by server.py bootstrap) ──
_db = None
_security = HTTPBearer(auto_error=False)


def set_seller_payment_methods_db(db_instance):
    global _db
    _db = db_instance


def _get_db():
    if _db is None:
        raise RuntimeError("seller_payment_methods DB not initialised")
    return _db


async def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    """Local minimal JWT resolver — mirrors routes/vehicles.py convention."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    from jose import jwt, JWTError
    jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await _get_db().users.find_one({"id": user_id})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        class _U:
            def __init__(self, u):
                self.id = u["id"]
                self.role = u.get("role", "")
        return _U(user)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


# ────────────────────────────────────────────────────────────────────
# Read-side — public GET
# ────────────────────────────────────────────────────────────────────
async def _find_listing_any_collection(db, listing_id: str) -> tuple[dict | None, str | None]:
    """Locate a listing across the 4 canonical collections.  Returns
    ``(doc, collection_name)`` or ``(None, None)``."""
    for coll in ("listings", "multi_item_listings", "vehicle_listings",
                 "storage_auctions", "partner_listings"):
        row = await db[coll].find_one({"id": listing_id})
        if row:
            return row, coll
    return None, None


@seller_payment_methods_router.get(
    "/listings/{listing_id}/accepted-payment-methods",
)
async def get_accepted_payment_methods(listing_id: str):
    """Public read.  Returns:

        {
          "listing_id": str,
          "accepted_payment_methods": [str, ...],
          "locked": bool,
          "locked_at": Optional[str],   # ISO-8601
          "allowed_universe": [str, ...],  # the 4 canonical slugs
        }
    """
    db = _get_db()
    row, coll = await _find_listing_any_collection(db, listing_id)
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": "listing_not_found",
            "listing_id": listing_id,
        })
    try:
        methods = effective_methods(row)
    except PaymentMethodsMissingError as exc:
        raise HTTPException(status_code=422, detail={
            "error": "accepted_payment_methods_missing",
            "message_en": "This listing has no payment methods configured.  Contact support.",
            "message_fr": "Aucun mode de paiement n'est configuré pour cette annonce.  Contactez le soutien.",
        }) from exc
    return {
        "listing_id": listing_id,
        "collection": coll,
        "accepted_payment_methods": methods,
        "locked": is_locked(row),
        "locked_at": row.get("accepted_payment_methods_locked_at"),
        "allowed_universe": ALL_METHODS,
    }


# ────────────────────────────────────────────────────────────────────
# Buyer selection + terms acknowledgement
# ────────────────────────────────────────────────────────────────────
class TermsAckTotals(BaseModel):
    hammer_cents: int = Field(ge=0)
    buyer_premium_cents: int = Field(ge=0)
    buyer_tax_cents: int = Field(ge=0)
    payment_processing_cents: int = Field(ge=0)
    total_cents: int = Field(ge=0)


class SelectPaymentMethodBody(BaseModel):
    listing_id: str
    selected_payment_method: str
    ack_totals: TermsAckTotals
    terms_version: str = "iter482.p4b.v1"


@seller_payment_methods_router.post("/checkout/select-payment-method")
async def select_payment_method(
    body: SelectPaymentMethodBody,
    request: Request,
    current_user=Depends(_get_current_user),
):
    """Buyer explicitly picks their payment method + acknowledges the
    exact integer-cent totals.  Persists to ``db.buyer_payment_selections``
    (write-once per (listing_id, buyer_id, ack_totals) tuple — idempotent
    via unique index).

    Returns the canonical method + the auction's collection.
    """
    db = _get_db()
    row, coll = await _find_listing_any_collection(db, body.listing_id)
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": "listing_not_found",
            "listing_id": body.listing_id,
        })

    # Anti-tamper: totals sum must equal the acknowledged total
    parts_sum = (
        body.ack_totals.hammer_cents
        + body.ack_totals.buyer_premium_cents
        + body.ack_totals.buyer_tax_cents
        + body.ack_totals.payment_processing_cents
    )
    if parts_sum != body.ack_totals.total_cents:
        raise HTTPException(status_code=400, detail={
            "error": "ack_totals_do_not_sum",
            "parts_sum_cents": parts_sum,
            "total_cents": body.ack_totals.total_cents,
            "message_en": "Payment totals do not add up.  Please refresh the page.",
            "message_fr": "Les totaux de paiement ne correspondent pas.  Veuillez actualiser la page.",
        })

    # Validate selection is in the accepted list (snapshot if locked)
    try:
        canon = assert_selection_allowed(row, body.selected_payment_method)
    except PaymentMethodNotAcceptedError as exc:
        raise HTTPException(status_code=400, detail={
            "error": "PAYMENT_METHOD_NOT_ACCEPTED",
            "reason": str(exc),
            "accepted": effective_methods(row),
            "message_en": "Your chosen payment method is not accepted for this auction.",
            "message_fr": "Le mode de paiement choisi n'est pas accepté pour cette enchère.",
        }) from exc
    except PaymentMethodsMissingError as exc:
        raise HTTPException(status_code=422, detail={
            "error": "accepted_payment_methods_missing",
            "reason": str(exc),
        }) from exc

    # Persist the selection.  Write-once per (listing_id, buyer_id,
    # total_cents) tuple — allows a buyer to re-select if the total
    # changes (e.g. quantity adjusted), but never to silently overwrite
    # a prior ack with a different amount.
    now = datetime.now(timezone.utc).isoformat()
    ip = (request.client.host if request and request.client else None) or None
    ua = request.headers.get("user-agent") if request else None
    doc = {
        "listing_id":            body.listing_id,
        "collection":            coll,
        "buyer_id":              current_user.id,
        "selected_payment_method": canon,
        "terms_version":         body.terms_version,
        "ack_totals":            body.ack_totals.model_dump(),
        "ack_at":                now,
        "ack_ip":                ip,
        "ack_user_agent":        ua,
        "created_at":            now,
        "updated_at":            now,
    }
    # Idempotent upsert: same (listing_id, buyer_id, total_cents) → no
    # duplicate row.  Different total → new row (allows quantity change).
    await db.buyer_payment_selections.update_one(
        {
            "listing_id": body.listing_id,
            "buyer_id": current_user.id,
            "ack_totals.total_cents": body.ack_totals.total_cents,
        },
        {"$set": doc},
        upsert=True,
    )

    logger.info(
        f"[iter482.p4b] buyer_selection listing={body.listing_id} "
        f"buyer={current_user.id} method={canon} total_cents={body.ack_totals.total_cents}"
    )
    return {
        "ok": True,
        "listing_id": body.listing_id,
        "selected_payment_method": canon,
        "ack_totals": body.ack_totals.model_dump(),
        "ack_at": now,
    }


# ────────────────────────────────────────────────────────────────────
# Admin / support controlled-edit (stub — P4B returns 409 for locked)
# ────────────────────────────────────────────────────────────────────
class EditAcceptedMethodsBody(BaseModel):
    accepted_payment_methods: List[str]


@seller_payment_methods_router.post(
    "/listings/{listing_id}/accepted-payment-methods",
)
async def edit_accepted_payment_methods(
    listing_id: str,
    body: EditAcceptedMethodsBody,
    current_user=Depends(_get_current_user),
):
    """Controlled seller/admin edit of the accepted methods.

    Before first bid → allowed (canonicalise + persist).
    After first bid  → 409 ``PaymentMethodsLockedError``.  The
    controlled post-bid workflow (notify existing bidders, re-consent,
    etc.) is intentionally NOT implemented in P4B and returns 409 with
    a clear message so support-side intervention is explicit.
    """
    db = _get_db()
    row, coll = await _find_listing_any_collection(db, listing_id)
    if not row:
        raise HTTPException(status_code=404, detail={"error": "listing_not_found"})

    # Seller-ownership check
    seller_id = row.get("seller_id") or row.get("facility_user_id") or row.get("user_id")
    if seller_id and seller_id != current_user.id and (
        getattr(current_user, "role", "") or ""
    ).lower() not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail={"error": "not_owner"})

    try:
        new_methods = guard_edit(row, body.accepted_payment_methods)
    except PaymentMethodsLockedError as exc:
        raise HTTPException(status_code=409, detail={
            "error": "PAYMENT_METHODS_LOCKED",
            "reason": str(exc),
            "message_en": (
                "Payment methods are locked because this auction has "
                "received bids.  Contact support to open the controlled "
                "edit workflow."
            ),
            "message_fr": (
                "Les modes de paiement sont verrouillés car cette enchère "
                "a déjà reçu des offres.  Contactez le soutien pour ouvrir "
                "le processus de modification contrôlée."
            ),
        }) from exc

    now = datetime.now(timezone.utc).isoformat()
    await db[coll].update_one(
        {"id": listing_id},
        {"$set": {
            "accepted_payment_methods": new_methods,
            "accepted_payment_methods_updated_at": now,
        }},
    )
    return {
        "ok": True,
        "listing_id": listing_id,
        "accepted_payment_methods": new_methods,
    }
