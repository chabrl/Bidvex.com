"""
BidVex — Phase 6.0 / Task 5
Storage Cleanout Security Hold + Admin release/forfeit endpoint.

When a buyer wins a `listing_type="storage_locker"` auction:
  - Standard service fees + taxes + commissions are captured immediately
    via the existing Stripe checkout flow (no change).
  - The `storage_metadata.security_deposit_amount` is held SEPARATELY via a
    Stripe PaymentIntent with `capture_method="manual"` — labelled in the
    line-item metadata as "Storage Cleanout Security Hold".
  - The hold can be released (canceled) OR forfeited (captured) by an
    admin / facility manager once the unit has been verified.

Endpoints:
  POST /api/admin/storage-auctions/{invoice_id}/release-deposit
       body: {forfeit_deposit: bool, reason?: str}

  POST /api/admin/storage-auctions/{invoice_id}/create-cleanout-hold
       (internal — usually invoked by the checkout flow but exposed for
        recovery scenarios when an invoice was created before the hold was
        in place).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_db, require_admin, User
from services.storage_locker import (
    is_storage_locker, storage_deposit_amount_for_listing,
)

logger = logging.getLogger(__name__)

storage_cleanout_router = APIRouter(tags=["Storage Cleanout"])


def _stripe():
    """Returns the stripe module bound to the API key — raises 503 if absent."""
    key = os.environ.get("STRIPE_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail={
            "error": "stripe_not_configured",
            "message_en": "Stripe API key is not configured on the server.",
            "message_fr": "La clé API Stripe n'est pas configurée sur le serveur.",
        })
    stripe.api_key = key
    return stripe


class ReleaseDepositRequest(BaseModel):
    forfeit_deposit: bool = False
    reason: Optional[str] = None


async def _resolve_listing_for_invoice(db, invoice: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Look up the listing tied to an invoice (single or multi-item)."""
    listing_id = invoice.get("listing_id") or invoice.get("auction_id")
    if not listing_id:
        return None
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if listing:
        return listing
    return await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})


async def create_storage_cleanout_hold(
    db,
    invoice_id: str,
    buyer_id: str,
    payment_method_id: str,
) -> Dict[str, Any]:
    """Create a Stripe PaymentIntent with `capture_method="manual"` for the
    cleanout security deposit amount carried on the listing's
    `storage_metadata.security_deposit_amount`.

    Idempotent: if a cleanout hold already exists for this invoice it is
    returned unchanged.
    """
    invoice = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    listing = await _resolve_listing_for_invoice(db, invoice)
    if not listing or not is_storage_locker(listing):
        raise HTTPException(status_code=400, detail={
            "error": "not_storage_locker",
            "message_en": "This invoice is not tied to a storage_locker listing.",
            "message_fr": "Cette facture n'est pas liée à une annonce de casier de stockage.",
        })

    # Idempotency
    existing = await db.storage_cleanout_holds.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if existing:
        return existing

    amount_cad = storage_deposit_amount_for_listing(listing)
    amount_cents = int(round(amount_cad * 100))

    sg = _stripe()
    user = await db.users.find_one({"id": buyer_id}, {"_id": 0, "stripe_customer_id": 1, "email": 1})
    customer_id = (user or {}).get("stripe_customer_id")
    if not customer_id:
        cust = sg.Customer.create(email=(user or {}).get("email") or "", metadata={"buyer_id": buyer_id})
        customer_id = cust.id
        await db.users.update_one({"id": buyer_id}, {"$set": {"stripe_customer_id": customer_id}})
    try:
        sg.PaymentMethod.attach(payment_method_id, customer=customer_id)
    except stripe.error.InvalidRequestError:
        # already attached
        pass

    try:
        pi = sg.PaymentIntent.create(
            amount=amount_cents,
            currency="cad",
            customer=customer_id,
            payment_method=payment_method_id,
            confirm=True,
            capture_method="manual",
            description="Storage Cleanout Security Hold",
            statement_descriptor_suffix="BIDVEX CLNUT",
            metadata={
                "kind":             "storage_cleanout_security_hold",
                "label":            "Storage Cleanout Security Hold",
                "invoice_id":       invoice_id,
                "listing_id":       listing.get("id"),
                "buyer_id":         buyer_id,
                "facility_name":    (listing.get("storage_metadata") or {}).get("facility_name", ""),
                "deadline_hours":   str((listing.get("storage_metadata") or {}).get("cleanout_deadline_hours", 72)),
            },
        )
    except stripe.error.StripeError as exc:
        logger.error(f"[storage_cleanout] Stripe error creating hold: {exc}")
        raise HTTPException(status_code=502, detail={
            "error":      "stripe_create_failed",
            "message_en": str(exc),
        })

    now = datetime.now(timezone.utc)
    hold = {
        "id":                       str(uuid.uuid4()),
        "kind":                     "storage_cleanout_security_hold",
        "invoice_id":               invoice_id,
        "listing_id":               listing.get("id"),
        "buyer_id":                 buyer_id,
        "stripe_customer_id":       customer_id,
        "stripe_payment_intent_id": pi.id,
        "stripe_status":            pi.status,
        "amount_cents":             amount_cents,
        "amount_cad":               amount_cad,
        "currency":                 "CAD",
        "label":                    "Storage Cleanout Security Hold",
        "facility_name":            (listing.get("storage_metadata") or {}).get("facility_name", ""),
        "status":                   "held",
        "created_at":               now,
        "released_at":              None,
        "forfeited_at":             None,
        "resolved_by":              None,
        "reason":                   None,
    }
    await db.storage_cleanout_holds.insert_one(hold)
    # Stamp invoice with the hold id for quick lookup
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "cleanout_hold_id":   hold["id"],
            "cleanout_hold_pi":   pi.id,
            "cleanout_hold_status": "held",
        }},
    )
    logger.info(f"[storage_cleanout] HOLD created invoice={invoice_id} pi={pi.id} ${amount_cad}")
    return {**hold, "_id": None}


@storage_cleanout_router.post("/admin/storage-auctions/{invoice_id}/release-deposit")
async def admin_release_cleanout_deposit(
    invoice_id: str,
    payload: ReleaseDepositRequest,
    current_user: User = Depends(require_admin),
):
    """Admin / Facility Manager endpoint.

    - `forfeit_deposit=False` → cancel the Stripe auth hold (buyer keeps their money).
    - `forfeit_deposit=True`  → capture the full amount (buyer is penalised
                                 for leaving items behind).
    """
    db = get_db()
    hold = await db.storage_cleanout_holds.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not hold:
        raise HTTPException(status_code=404, detail={
            "error": "no_cleanout_hold",
            "message_en": f"No cleanout hold exists for invoice {invoice_id}.",
            "message_fr": f"Aucune retenue de sécurité n'existe pour la facture {invoice_id}.",
        })
    if hold.get("status") in {"released", "forfeited", "captured"}:
        raise HTTPException(status_code=400, detail={
            "error": "already_resolved",
            "message_en": f"This hold is already {hold['status']}.",
            "message_fr": f"Cette retenue est déjà {hold['status']}.",
        })

    sg = _stripe()
    pi_id = hold["stripe_payment_intent_id"]
    now = datetime.now(timezone.utc)

    try:
        if payload.forfeit_deposit:
            # Capture the full authorized amount
            pi = sg.PaymentIntent.capture(pi_id)
            new_status = "forfeited"
            update_extra = {
                "forfeited_at": now,
                "stripe_status": pi.status,
                "captured_amount_cents": pi.amount_received,
            }
        else:
            # Release the hold (cancel)
            pi = sg.PaymentIntent.cancel(pi_id)
            new_status = "released"
            update_extra = {
                "released_at": now,
                "stripe_status": pi.status,
            }
    except stripe.error.StripeError as exc:
        logger.error(f"[storage_cleanout] Stripe error during release: {exc}")
        raise HTTPException(status_code=502, detail={
            "error":      "stripe_action_failed",
            "message_en": str(exc),
        })

    await db.storage_cleanout_holds.update_one(
        {"id": hold["id"]},
        {"$set": {
            "status":      new_status,
            "resolved_by": current_user.email,
            "reason":      (payload.reason or "")[:500],
            **update_extra,
        }},
    )
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "cleanout_hold_status": new_status,
            "cleanout_resolved_at": now,
            "cleanout_resolved_by": current_user.email,
        }},
    )
    logger.info(f"[storage_cleanout] {new_status.upper()} invoice={invoice_id} by {current_user.email}")
    return {
        "success":     True,
        "invoice_id":  invoice_id,
        "hold_id":     hold["id"],
        "new_status":  new_status,
        "forfeit_deposit": payload.forfeit_deposit,
        "reason":      (payload.reason or "")[:500],
    }


@storage_cleanout_router.get("/admin/storage-auctions/{invoice_id}/cleanout-hold")
async def admin_get_cleanout_hold(
    invoice_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    hold = await db.storage_cleanout_holds.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not hold:
        raise HTTPException(status_code=404, detail="No cleanout hold for this invoice")
    # Normalise datetime fields for the JSON response
    for k in ("created_at", "released_at", "forfeited_at"):
        v = hold.get(k)
        if isinstance(v, datetime):
            hold[k] = v.isoformat()
    return hold
