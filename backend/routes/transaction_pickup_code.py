"""
iter214 P1 — Individual-Seller Pickup-Code System
======================================================
For non-Stripe payment methods (cash, Interac e-Transfer) where the buyer
pays the seller DIRECTLY, BidVex needs a verifiable proof-of-payment
mechanism before it triggers commission collection from the seller.

Flow:
  1. Auction closes → invoice generated → unique pickup code
     `BVX-XXXXXXXX` stored on the transaction document.
  2. Buyer receives the code in their invoice email.
  3. Seller receives "How to release funds" instructions in their statement.
  4. Buyer pays seller (cash hand-off or Interac e-Transfer).
  5. Buyer shares the code with the seller AFTER payment.
  6. Seller enters the code on /confirm-payment.
  7. POST /api/transactions/confirm-pickup-code marks the txn paid and
     triggers commission charge to the seller's card on file.

Limited to:
  - Individual seller → any buyer
  - Payment method: "cash" or "etransfer"
  (Partner and Vehicle Dealer auctions handle their own off-platform
   payments — no pickup code per the spec.)
"""
from datetime import datetime, timezone
from typing import Optional
import secrets
import string
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["pickup-code"])


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def generate_pickup_code() -> str:
    """`BVX-XXXXXXXX` (8 uppercase alphanumerics) — same format as iter172
    storage pickup codes for consistency."""
    alphabet = string.ascii_uppercase + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"BVX-{body}"


async def ensure_pickup_code_on_transaction(db, transaction_id: str, *, payment_method: str, seller_id: str, listing_id: str) -> Optional[str]:
    """Create a pickup code on the transaction document if not already present.

    Returns the code (newly created or pre-existing) or None when it doesn't
    apply (e.g. Stripe transactions). Idempotent.
    """
    if payment_method not in {"cash", "etransfer"}:
        return None
    txn = await db.transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not txn:
        return None
    if txn.get("pickup_code"):
        return txn["pickup_code"]
    code = generate_pickup_code()
    await db.transactions.update_one(
        {"id": transaction_id},
        {"$set": {
            "pickup_code": code,
            "pickup_code_seller_id": seller_id,
            "pickup_code_listing_id": listing_id,
            "pickup_code_confirmed_at": None,
            "pickup_code_confirmed_by": None,
        }},
    )
    return code


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────

class ConfirmPickupPayload(BaseModel):
    pickup_code: str = Field(..., min_length=8, max_length=20)


@router.post("/confirm-pickup-code")
async def confirm_pickup_code(
    payload: ConfirmPickupPayload,
    current_user: User = Depends(get_current_user),
):
    """Seller enters the buyer-provided pickup code to confirm payment.

    On success: marks txn paid, triggers commission charge to the seller's
    card on file (best-effort; failure does NOT roll back confirmation —
    the admin can retry).
    """
    db = get_db()
    code = (payload.pickup_code or "").strip().upper()
    if not code.startswith("BVX-"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_code_format",
                "message_en": "Pickup codes start with 'BVX-' followed by 8 characters.",
                "message_fr": "Les codes commencent par « BVX- » suivi de 8 caractères.",
            },
        )

    txn = await db.transactions.find_one({"pickup_code": code}, {"_id": 0})
    if not txn:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "code_not_found",
                "message_en": "No transaction matches that pickup code. Double-check with the buyer.",
                "message_fr": "Aucune transaction ne correspond à ce code. Vérifiez auprès de l'acheteur.",
            },
        )

    # Only the seller of the txn may confirm
    if txn.get("pickup_code_seller_id") and txn["pickup_code_seller_id"] != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "not_seller",
                "message_en": "Only the seller may confirm this pickup code.",
                "message_fr": "Seul le vendeur peut confirmer ce code.",
            },
        )

    # Idempotency — already confirmed
    if txn.get("pickup_code_confirmed_at"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "already_confirmed",
                "confirmed_at": txn["pickup_code_confirmed_at"],
                "message_en": "This pickup code was already confirmed.",
                "message_fr": "Ce code a déjà été confirmé.",
            },
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.transactions.update_one(
        {"id": txn["id"]},
        {"$set": {
            "pickup_code_confirmed_at": now,
            "pickup_code_confirmed_by": current_user.id,
            "payment_confirmed": True,
            "payment_confirmed_at": now,
        }},
    )

    # Best-effort commission charge to seller card on file. The hybrid
    # manual-settlement queue from iter211 will handle Stripe failures by
    # creating an outstanding-balance entry that admins can review.
    try:
        from services.manual_settlement_service import enqueue_manual_commission
        hammer = float(txn.get("hammer_price") or 0)
        commission_cad = round(hammer * 0.05, 2)  # individual default — refine via fee_calculator if needed
        if commission_cad > 0:
            await enqueue_manual_commission(
                db,
                user_id=current_user.id,
                auction_id=txn.get("auction_id"),
                listing_id=txn.get("pickup_code_listing_id") or txn.get("listing_id"),
                listing_title=txn.get("listing_title", "Auction item"),
                commission_amount_cad=commission_cad,
                notes=f"Pickup-code confirmed for transaction {txn['id']}",
            )
    except Exception as e:
        logger.warning(f"[pickup_code] commission enqueue failed (will retry later): {e}")

    # Notify both parties — best-effort email
    try:
        from services.emails._email_core import send_email
        body = (
            f"<p>Pickup code <code>{code}</code> was confirmed at {now}.</p>"
            f"<p>The seller has confirmed payment. The BidVex commission will "
            f"be charged to the seller card on file within 24 hours.</p>"
        )
        if txn.get("buyer_email"):
            await send_email(
                to_email=txn["buyer_email"],
                subject="✅ Payment confirmed · Paiement confirmé — BidVex",
                html_content=body,
            )
        if txn.get("seller_email"):
            await send_email(
                to_email=txn["seller_email"],
                subject="✅ Pickup code confirmed · Code de collecte confirmé — BidVex",
                html_content=body,
            )
    except Exception as e:
        logger.warning(f"[pickup_code] confirmation emails failed: {e}")

    return {
        "success": True,
        "transaction_id": txn["id"],
        "confirmed_at": now,
        "message_en": "Pickup code confirmed. Funds will be marked as settled and your card on file will be charged for the commission within 24 hours.",
        "message_fr": "Code de collecte confirmé. Les fonds seront marqués comme réglés et la commission sera prélevée sur votre carte enregistrée dans les 24 heures.",
    }


@router.get("/{transaction_id}/pickup-code")
async def get_pickup_code_for_buyer(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
):
    """Buyer retrieves their pickup code (also embedded in the invoice email)."""
    db = get_db()
    txn = await db.transactions.find_one({"id": transaction_id}, {"_id": 0})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn.get("buyer_id") != current_user.id and getattr(current_user, "role", None) not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Not your transaction")
    return {
        "transaction_id": transaction_id,
        "pickup_code": txn.get("pickup_code"),
        "payment_method": txn.get("payment_method"),
        "is_confirmed": bool(txn.get("pickup_code_confirmed_at")),
        "confirmed_at": txn.get("pickup_code_confirmed_at"),
    }
