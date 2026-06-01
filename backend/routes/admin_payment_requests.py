"""
iter258 Mission 1 — Admin "Request Payment" pipeline.

Endpoints (all under `/api`):
  POST /admin/users/{user_id}/request-payment
       Creates a Stripe Payment Link, stores a `payment_requests`
       doc, optionally fans out an email + in-app notification.

  GET  /admin/users/{user_id}/payment-requests
       Returns the user's payment-request history (DESC).

Stripe webhook integration: see `routes/webhooks.py` —
`session_type == "payment_request"` flips the matching doc to
`status: paid` and fires a `payment_confirmed` email.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

admin_payment_requests_router = APIRouter(prefix="/admin", tags=["Admin Payment Requests"])

_PUBLIC_URL = os.environ.get("PUBLIC_HOST", os.environ.get("REACT_APP_BACKEND_URL", "https://bidvex.com")).rstrip("/")

_TAX_RATES: Dict[str, float] = {
    "none":     0.0,
    "gst":      5.0,
    "qst":      9.975,
    "gst_qst":  14.975,
    "hst_on":   13.0,
    # `custom` honors `custom_tax_rate` from the payload.
}


def _require_admin(user: User) -> None:
    if getattr(user, "role", None) != "admin" and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")


class RequestPaymentBody(BaseModel):
    subtotal: float = Field(..., gt=0)
    tax_type: str = Field("none")
    custom_tax_rate: Optional[float] = None
    total_amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=2, max_length=400)
    internal_notes: str = Field("", max_length=2000)
    send_email: bool = True
    send_notification: bool = True
    expiry_hours: Optional[int] = None


def _resolve_tax_rate(tax_type: str, custom_tax_rate: Optional[float]) -> float:
    if tax_type == "custom":
        if custom_tax_rate is None:
            raise HTTPException(status_code=400, detail="custom_tax_rate is required when tax_type='custom'")
        return max(0.0, float(custom_tax_rate))
    if tax_type not in _TAX_RATES:
        raise HTTPException(
            status_code=400,
            detail=f"tax_type must be one of {sorted(list(_TAX_RATES.keys()) + ['custom'])}",
        )
    return _TAX_RATES[tax_type]


@admin_payment_requests_router.post("/users/{user_id}/request-payment")
async def request_payment(
    user_id: str,
    body: RequestPaymentBody,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()

    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    tax_rate = _resolve_tax_rate(body.tax_type, body.custom_tax_rate)

    # Stripe Payment Link
    line_item = {
        "price_data": {
            "currency": "cad",
            "unit_amount": int(round(body.total_amount * 100)),
            "product_data": {"name": body.description[:120] or "BidVex Payment Request"},
        },
        "quantity": 1,
    }
    request_id = str(uuid.uuid4())
    metadata = {
        "user_id": user_id,
        "admin_id": current_user.id,
        "type": "payment_request",
        "payment_request_id": request_id,
        "admin_note": (body.internal_notes or "")[:480],
        "requested_by": "admin",
    }
    create_kwargs: Dict[str, Any] = {
        "line_items": [line_item],
        "metadata": metadata,
        "after_completion": {
            "type": "redirect",
            "redirect": {"url": f"{_PUBLIC_URL}/payment-confirmed?ref={request_id}"},
        },
    }
    expires_at: Optional[datetime] = None
    if body.expiry_hours and body.expiry_hours > 0:
        # Stripe enforces a 30-min minimum and 24-day maximum on expires_at.
        seconds = max(30 * 60, body.expiry_hours * 3600)
        seconds = min(seconds, 24 * 24 * 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        create_kwargs["expires_at"] = int(expires_at.timestamp())

    try:
        link = stripe.PaymentLink.create(**create_kwargs)
    except stripe.error.StripeError as e:  # type: ignore[attr-defined]
        logger.error(f"Stripe PaymentLink.create failed: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)[:200]}")

    now = datetime.now(timezone.utc)
    expiry_label = (
        "no expiry"
        if expires_at is None
        else expires_at.strftime("%Y-%m-%d %H:%M UTC")
    )
    doc = {
        "id": request_id,
        "user_id": user_id,
        "admin_id": current_user.id,
        "subtotal": float(body.subtotal),
        "tax_type": body.tax_type,
        "tax_rate": tax_rate,
        "total_amount": float(body.total_amount),
        "description": body.description,
        "internal_notes": body.internal_notes,
        "stripe_payment_link": link.url,
        "stripe_payment_link_id": link.id,
        "status": "pending",
        "expiry_hours": body.expiry_hours,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "expiry_label": expiry_label,
        "created_at": now.isoformat(),
        "paid_at": None,
    }
    await db.payment_requests.insert_one(doc)

    # iter258 — Fan-out: email + in-app notification (both opt-in).
    if body.send_email:
        try:
            from services.email_notifications import send_unified_email
            await send_unified_email(
                user=dict(target),
                email_type="payment_request",
                data={
                    "total_amount": f"{float(body.total_amount):.2f}",
                    "description": body.description,
                    "expiry_label": expiry_label,
                    "payment_link": link.url,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"payment_request email dispatch failed: {exc}")

    if body.send_notification:
        try:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": "payment_request",
                "title": "💳 Payment Required",
                "body": f"An outstanding balance of ${float(body.total_amount):.2f} CAD requires your attention.",
                "link": link.url,
                "is_read": False,
                "created_at": now.isoformat(),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"payment_request notification insert failed: {exc}")

    return {
        "success": True,
        "id": request_id,
        "payment_link": link.url,
        "stripe_payment_link_id": link.id,
        "total_amount": float(body.total_amount),
        "expiry_label": expiry_label,
    }


@admin_payment_requests_router.get("/users/{user_id}/payment-requests")
async def list_payment_requests(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    cursor = db.payment_requests.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(200)
    items: List[Dict[str, Any]] = await cursor.to_list(length=200)
    # iter258 — Mark expired rows on read (stateless).
    now = datetime.now(timezone.utc)
    for it in items:
        if it.get("status") == "pending" and it.get("expires_at"):
            try:
                ts = datetime.fromisoformat(str(it["expires_at"]).replace("Z", "+00:00"))
                if ts < now:
                    it["status"] = "expired"
            except Exception:
                pass
    return {"items": items, "total": len(items)}


__all__ = ["admin_payment_requests_router"]
