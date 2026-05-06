"""
BidVex — Down Payment HTTP routes
==================================
Public buyer/seller-facing endpoints for the post-auction down payment.

Routes (all under /api):
    GET  /down-payments/me                          — my open down payments
    GET  /down-payments/{auction_id}                — status for a specific auction
    POST /down-payments/{auction_id}/checkout       — start Stripe checkout
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from deps import get_db, get_current_user, User
from rate_limit import limiter as _limiter
from services.down_payment_service import (
    create_stripe_checkout_for_down_payment,
)


down_payments_router = APIRouter(prefix="/down-payments", tags=["Down Payments"])


class CheckoutRequest(BaseModel):
    return_url: Optional[str] = None


@down_payments_router.get("/me")
@_limiter.limit("60/minute")
async def my_down_payments(request: Request, current_user: User = Depends(get_current_user)):
    """Open + recently-paid down payments for the current buyer."""
    db = get_db()
    cursor = db.down_payments.find(
        {"buyer_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1).limit(50)
    rows = await cursor.to_list(50)
    return {"items": rows, "count": len(rows)}


@down_payments_router.get("/{auction_id}")
@_limiter.limit("120/minute")
async def get_down_payment_for_auction(
    request: Request,
    auction_id: str,
    current_user: User = Depends(get_current_user),
):
    """Fetch the down payment row for a specific auction.
    Visible to either the buyer (winner) or the seller / facility owner.
    """
    db = get_db()
    dp = await db.down_payments.find_one({"auction_id": auction_id}, {"_id": 0})
    if not dp:
        raise HTTPException(status_code=404, detail="No down payment recorded for this auction")
    if dp["buyer_id"] != current_user.id and dp.get("seller_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    # Compute remaining time
    try:
        deadline = datetime.fromisoformat(dp["deadline_at"].replace("Z", "+00:00"))
        seconds_left = max(0, int((deadline - datetime.now(timezone.utc)).total_seconds()))
        dp["seconds_left"] = seconds_left
        dp["is_overdue"] = seconds_left == 0 and dp["status"] == "pending"
    except Exception:
        pass
    return dp


@down_payments_router.post("/{auction_id}/checkout")
@_limiter.limit("10/minute")
async def start_down_payment_checkout(
    request: Request,
    auction_id: str,
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """Buyer starts the Stripe Checkout flow to settle their down payment."""
    db = get_db()
    dp = await db.down_payments.find_one(
        {"auction_id": auction_id, "buyer_id": current_user.id},
        {"_id": 0},
    )
    if not dp:
        raise HTTPException(status_code=404, detail="No down payment for this auction")
    if dp["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Down payment already {dp['status']}")

    return_url = payload.return_url or f"https://bidvex.com/account/down-payments/{dp['id']}"
    out = await create_stripe_checkout_for_down_payment(
        db, down_payment_id=dp["id"], return_url=return_url
    )
    return {**out, "down_payment_id": dp["id"], "amount": dp["amount"], "currency": dp["currency"]}
