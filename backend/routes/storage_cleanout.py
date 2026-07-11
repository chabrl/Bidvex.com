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
from typing import Any, Dict, List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_db, get_current_user, require_admin, User
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
    except stripe.InvalidRequestError:
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
    except stripe.StripeError as exc:
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


# ─────────────────────────────────────────────────────────────────────
# Phase 6.2 Task 4 — Buyer "Mark Unit as Cleared" endpoint.
# Sets the hold into `pending_verification` so the admin desk surfaces
# the row for approval. The buyer's deposit is NOT released yet — admin
# verification is still required.
# ─────────────────────────────────────────────────────────────────────
class BuyerClearanceRequest(BaseModel):
    notes: Optional[str] = None
    # Phase 6.3 Task 3 — Mandatory broom-swept proof photos (base64 data URLs
    # OR https URLs; the storage backfill helper will promote base64 to S3
    # in the background). At least one photo is required; client enforces the
    # UI gate, but we re-validate here for defence-in-depth.
    photos: Optional[List[str]] = None


@storage_cleanout_router.post("/storage-cleanout/{invoice_id}/request-clearance")
async def buyer_request_clearance(
    invoice_id: str,
    payload: BuyerClearanceRequest = None,
    current_user: User = Depends(get_current_user),
):
    """Buyer marks their unit as fully cleared. Flips the cleanout hold into
    `pending_verification` so the admin Storage Settlements desk picks it up.

    Phase 6.3 Task 3 — Now requires at least one broom-swept proof photo.
    """
    db = get_db()
    hold = await db.storage_cleanout_holds.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not hold:
        raise HTTPException(status_code=404, detail={
            "error": "no_cleanout_hold",
            "message_en": "No cleanout hold exists for this invoice.",
            "message_fr": "Aucune retenue de sécurité n'existe pour cette facture.",
        })
    if hold.get("buyer_id") != current_user.id and (getattr(current_user, "role", "") or "").lower() not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the buyer or an admin can request clearance.")
    if hold.get("status") in {"released", "forfeited", "captured", "pending_verification"}:
        # Idempotent — return current state.
        return {"status": hold.get("status"), "already_requested": True, "hold": hold}

    # Phase 6.3 Task 3 — Photo requirement enforcement.
    photos = (payload.photos if payload else None) or []
    if not photos:
        raise HTTPException(status_code=400, detail={
            "error": "photos_required",
            "message_en": "Please attach at least one photo of the empty, broom-swept unit before requesting clearance.",
            "message_fr": "Veuillez joindre au moins une photo du casier vidé et balayé avant de demander la libération.",
        })

    now = datetime.now(timezone.utc)
    notes = (payload.notes if payload else None) or ""
    await db.storage_cleanout_holds.update_one(
        {"invoice_id": invoice_id},
        {"$set": {
            "status": "pending_verification",
            "clearance_requested_at": now,
            "clearance_requested_by": current_user.email,
            "clearance_notes": notes,
            # Phase 6.3 Task 3 — store the proof photos so admin can review.
            "clearance_photos": photos,
            "clearance_photo_count": len(photos),
        }},
    )
    # Mirror onto the invoice for buyer-facing visibility.
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"cleanout_hold_status": "pending_verification"}},
    )
    # Notify the admin desk via email_outbox so the BidVex inbox sees it.
    try:
        await db.email_outbox.insert_one({
            "id": str(uuid.uuid4()),
            "kind": "storage_cleanout_pending_verification",
            "to_email": "charbel911@gmail.com",
            "context": {
                "invoice_id": invoice_id,
                "buyer_email": current_user.email,
                "facility_name": hold.get("facility_name", ""),
                "amount_cad": hold.get("amount_cad", 0),
                "admin_review_url": f"https://bidvex.com/admin/storage-management?invoice_id={invoice_id}",
            },
            "queued_at": now,
        })
    except Exception as exc:
        logger.warning(f"[storage_cleanout] pending_verification email queue failed: {exc}")
    logger.info(f"[storage_cleanout] buyer {current_user.email} requested clearance invoice={invoice_id}")
    return {"status": "pending_verification", "requested_at": now.isoformat()}


@storage_cleanout_router.get("/storage-cleanout/{invoice_id}/status")
async def buyer_get_cleanout_status(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
):
    """Buyer-facing endpoint — returns the cleanout hold record + countdown.

    Used by the invoice detail page to render the live ticker without exposing
    admin-only fields.
    """
    db = get_db()
    hold = await db.storage_cleanout_holds.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not hold:
        return {"has_hold": False}
    invoice = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if hold.get("buyer_id") != current_user.id and (getattr(current_user, "role", "") or "").lower() not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Compute deadline
    deadline_hours = hold.get("cleanout_deadline_hours") or 72
    created_at = hold.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            created_at = None
    deadline_at = None
    if isinstance(created_at, datetime):
        from datetime import timedelta
        deadline_at = created_at + timedelta(hours=deadline_hours)

    return {
        "has_hold": True,
        "status": hold.get("status"),
        "amount_cad": hold.get("amount_cad"),
        "facility_name": hold.get("facility_name"),
        "cleanout_deadline_hours": deadline_hours,
        "deadline_at": deadline_at.isoformat() if deadline_at else None,
        "clearance_requested_at": (
            hold["clearance_requested_at"].isoformat()
            if isinstance(hold.get("clearance_requested_at"), datetime)
            else hold.get("clearance_requested_at")
        ),
        "invoice_status": (invoice or {}).get("status"),
    }


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
    except stripe.StripeError as exc:
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


# ───────────────────────────────────────────────────────────────────────
# Phase 6.0 hotfix — Admin power-user storage dashboard
# Global GET of every active storage cleanout hold across all facilities,
# so admins can monitor + override without being scoped to a single
# facility-manager view.
# ───────────────────────────────────────────────────────────────────────

@storage_cleanout_router.get("/admin/storage-auctions/cleanout-holds")
async def admin_list_all_cleanout_holds(
    status: Optional[str] = None,
    facility_name: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: User = Depends(require_admin),
):
    """Admin global dashboard — lists every cleanout hold across every
    facility/seller. Supports optional filter by `status` (held|released|
    forfeited|captured) and case-insensitive `facility_name` substring."""
    db = get_db()
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if facility_name:
        query["facility_name"] = {"$regex": facility_name, "$options": "i"}
    cur = db.storage_cleanout_holds.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    rows = await cur.to_list(length=limit)
    for r in rows:
        for k in ("created_at", "released_at", "forfeited_at"):
            v = r.get(k)
            if isinstance(v, datetime):
                r[k] = v.isoformat()
    total = await db.storage_cleanout_holds.count_documents(query)
    return {"rows": rows, "total": total, "filters": {"status": status, "facility_name": facility_name}}


class AdminEditCleanoutRequest(BaseModel):
    cleanout_deadline_hours: Optional[int] = None
    security_deposit_amount: Optional[float] = None
    facility_manager_email: Optional[str] = None
    facility_manager_phone: Optional[str] = None
    notes: Optional[str] = None


@storage_cleanout_router.patch("/admin/storage-auctions/listings/{listing_id}/storage-metadata")
async def admin_edit_storage_metadata(
    listing_id: str,
    payload: AdminEditCleanoutRequest,
    current_user: User = Depends(require_admin),
):
    """Phase 6.0 hotfix — admin-only superuser endpoint to edit cleanout
    variables on any storage_locker listing. Bypasses facility-manager role
    locks since admins have absolute authority."""
    db = get_db()
    # Locate the listing in either collection
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    collection = "listings"
    if not listing:
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        collection = "multi_item_listings"
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if (listing.get("listing_type") or "").lower() != "storage_locker":
        raise HTTPException(status_code=400, detail="Listing is not a storage_locker")

    meta = dict(listing.get("storage_metadata") or {})
    updates: Dict[str, Any] = {}
    if payload.cleanout_deadline_hours is not None:
        meta["cleanout_deadline_hours"] = max(1, int(payload.cleanout_deadline_hours))
    if payload.security_deposit_amount is not None:
        meta["security_deposit_amount"] = max(0.0, float(payload.security_deposit_amount))
    if payload.facility_manager_email is not None:
        meta["facility_manager_email"] = payload.facility_manager_email[:200]
    if payload.facility_manager_phone is not None:
        meta["facility_manager_phone"] = payload.facility_manager_phone[:30]
    if payload.notes is not None:
        meta["notes"] = (payload.notes or "")[:1000]
    meta["last_admin_edit_at"] = datetime.now(timezone.utc).isoformat()
    meta["last_admin_edit_by"] = current_user.email
    updates["storage_metadata"] = meta

    await db[collection].update_one({"id": listing_id}, {"$set": updates})
    logger.info(f"[storage_locker] admin edit by {current_user.email} on listing={listing_id} → {list(payload.dict(exclude_unset=True).keys())}")
    return {"success": True, "listing_id": listing_id, "storage_metadata": meta}

