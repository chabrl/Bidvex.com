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
import traceback
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
    # iter346 — canonical admin+super_admin check.
    if getattr(user, "role", None) not in ("admin", "super_admin") and not getattr(user, "is_admin", False):
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

    # iter260 — Hard-fail with a clear message when the caller sends a
    # garbage path param. The admin UI may pass `undefined` / empty /
    # `null` when the user row it was rendered for has no `id` field
    # (e.g. marketing-list "contact-only" stubs). The previous behavior
    # was a generic 404 "User not found" which the admin saw in the
    # toast as "Failed to create payment request".
    clean_uid = (user_id or "").strip()
    if not clean_uid or clean_uid.lower() in ("undefined", "null", "none"):
        raise HTTPException(
            status_code=400,
            detail=(
                "This user has no account ID (likely a contact-only "
                "stub from a marketing list). Request Payment is only "
                "available for registered users."
            ),
        )

    target = await db.users.find_one({"id": clean_uid}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail=f"User not found: {clean_uid}")
    # iter260 — Use the cleaned uid everywhere downstream.
    user_id = clean_uid

    try:
        return await _build_payment_request(db, user_id, body, current_user, target)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        # iter260 — Full traceback to backend logs + structured 500
        # surfacing the real exception type to the admin so the popup
        # doesn't lie about the cause.
        traceback.print_exc()
        logger.exception(f"[request-payment] internal error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error in request_payment: {type(e).__name__}: {str(e)[:200]}",
        )


async def _build_payment_request(
    db,
    user_id: str,
    body: "RequestPaymentBody",
    current_user: "User",
    target: Dict[str, Any],
):
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
        # Stripe PaymentLinks do not accept an `expires_at` parameter
        # (passing it triggers `parameter_unknown` 400 errors). We
        # store the expiry in the MongoDB `payment_requests` document
        # and the `/pay/:id` page enforces it server-side — that is
        # the canonical source of truth.
        # We still respect the same 30-min minimum / 24-day maximum
        # window for parity with what Stripe historically allowed.
        seconds = max(30 * 60, body.expiry_hours * 3600)
        seconds = min(seconds, 24 * 24 * 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)

    try:
        link = stripe.PaymentLink.create(**create_kwargs)
        stripe_payment_link_url = link.url
        stripe_payment_link_id = link.id
        stripe_warning = None
    except Exception as e:  # noqa: BLE001 — stripe SDK errors are not a single class
        # iter259 — Never crash the request payment flow on Stripe
        # misconfig. Persist the request with `stripe_payment_link=None`
        # and surface a warning the admin can act on. Modern Stripe
        # Python SDK (v8+) exposes errors as `stripe.StripeError` (not
        # the deprecated `stripe.error.StripeError`); catching the
        # broad `Exception` covers both shapes + Stripe key absence.
        logger.warning(f"Stripe PaymentLink.create failed: {e}")
        stripe_payment_link_url = None
        stripe_payment_link_id = None
        stripe_warning = f"Stripe not configured — link not generated ({type(e).__name__})"

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
        "stripe_payment_link": stripe_payment_link_url,
        "stripe_payment_link_id": stripe_payment_link_id,
        "status": "pending",
        "expiry_hours": body.expiry_hours,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "expiry_label": expiry_label,
        "created_at": now.isoformat(),
        "paid_at": None,
    }
    await db.payment_requests.insert_one(doc)

    # iter261 — Always compose a payment URL. Even when Stripe is
    # misconfigured (no STRIPE_SECRET_KEY in preview, or rate-limited)
    # the user gets a clickable BidVex-hosted fallback Pay page that
    # creates a Checkout session on demand. The email previously had
    # `cta_url: None` → button hidden → user had no way to pay.
    bidvex_pay_url = f"{_PUBLIC_URL}/pay/{request_id}"
    final_payment_url = stripe_payment_link_url or bidvex_pay_url

    # iter258 — Fan-out: email + in-app notification (both opt-in).
    if body.send_email:
        try:
            from services.emails._email_core import send_unified_email
            await send_unified_email(
                user=dict(target),
                email_type="payment_request",
                data={
                    "total_amount": f"{float(body.total_amount):.2f}",
                    "description": body.description,
                    "expiry_label": expiry_label,
                    "payment_link": final_payment_url,
                    "cta_url": final_payment_url,
                    "cta_label": f"💳 Pay Now — ${float(body.total_amount):.2f} CAD",
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
                "body": (
                    f"Pending payment of ${float(body.total_amount):.2f} CAD. "
                    f"Reason: {body.description[:80]}"
                ),
                "link": final_payment_url,
                "amount_cad": float(body.total_amount),
                "is_read": False,
                "created_at": now.isoformat(),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"payment_request notification insert failed: {exc}")

    return {
        "success": True,
        "id": request_id,
        "payment_link": stripe_payment_link_url,
        "payment_url": final_payment_url,
        "stripe_payment_link_id": stripe_payment_link_id,
        "total_amount": float(body.total_amount),
        "expiry_label": expiry_label,
        "warning": stripe_warning,
    }


@admin_payment_requests_router.get("/users/{user_id}/payment-requests")
async def get_user_payment_requests(
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
    # iter262 — Surface a `payment_url` on every row so the admin
    # history tab can copy a single canonical link (the BidVex-hosted
    # `/pay/{id}` fallback when Stripe didn't issue a Payment Link).
    now = datetime.now(timezone.utc)
    for it in items:
        if it.get("status") == "pending" and it.get("expires_at"):
            try:
                ts = datetime.fromisoformat(str(it["expires_at"]).replace("Z", "+00:00"))
                if ts < now:
                    it["status"] = "expired"
            except Exception:
                pass
        rid = it.get("id")
        it["payment_url"] = it.get("stripe_payment_link") or f"{_PUBLIC_URL}/pay/{rid}"
    return {"items": items, "total": len(items)}


__all__ = ["admin_payment_requests_router"]
