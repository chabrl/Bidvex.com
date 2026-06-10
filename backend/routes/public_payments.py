"""
iter261 Mission 1 — Public payment endpoints for the BidVex-hosted
fallback Pay page.

The admin-issued payment_requests collection holds:
  - `stripe_payment_link` (may be null when Stripe is misconfigured)
  - `total_amount`, `description`, `expires_at`, `status`
  - `user_id` (BidVex UUID, not Mongo ObjectId)

Endpoints (NO auth):
  GET  /api/pay/{payment_request_id}                — public payload
  POST /api/pay/{payment_request_id}/checkout-session — on-demand
       Stripe Checkout fallback when stripe_payment_link is null
  POST /api/pay/{payment_request_id}/confirm-success — success-page
       handshake that marks the request paid + fires confirmation
       email & in-app notification (idempotent)

Auth-required:
  GET  /api/my/payment-requests — current user's outstanding rows
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

public_payments_router = APIRouter(tags=["Public Payments"])

_PUBLIC_URL = os.environ.get(
    "PUBLIC_HOST",
    os.environ.get("REACT_APP_BACKEND_URL", "https://bidvex.com"),
).rstrip("/")


def _bidvex_pay_url(payment_request_id: str) -> str:
    return f"{_PUBLIC_URL}/pay/{payment_request_id}"


def _is_expired(doc: Dict[str, Any]) -> bool:
    raw = doc.get("expires_at")
    if not raw:
        return False
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return False
    return dt < datetime.now(timezone.utc)


def _safe_public_payload(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Surface only the fields a public, unauthenticated visitor may
    see. `internal_notes`, `admin_id`, and any user PII stay private."""
    return {
        "id": doc.get("id"),
        "total_amount": float(doc.get("total_amount") or 0),
        "description": doc.get("description") or "",
        "status": doc.get("status") or "pending",
        "stripe_payment_link": doc.get("stripe_payment_link"),
        "expires_at": doc.get("expires_at"),
        "expiry_label": doc.get("expiry_label"),
        "created_at": doc.get("created_at"),
    }


# ─── Public payload ──────────────────────────────────────────────────

@public_payments_router.get("/pay/{payment_request_id}")
async def get_public_payment_request(payment_request_id: str):
    db = get_db()
    doc = await db.payment_requests.find_one({"id": payment_request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment request not found")
    payload = _safe_public_payload(doc)
    if doc.get("status") == "pending" and _is_expired(doc):
        payload["status"] = "expired"
    return payload


# ─── On-demand Stripe Checkout fallback ──────────────────────────────

@public_payments_router.post("/pay/{payment_request_id}/checkout-session")
async def create_checkout_session_for_payment_request(payment_request_id: str):
    db = get_db()
    doc = await db.payment_requests.find_one({"id": payment_request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment request not found")
    if doc.get("status") == "paid":
        raise HTTPException(status_code=400, detail="This payment has already been completed")
    if _is_expired(doc):
        raise HTTPException(status_code=400, detail="This payment link has expired")

    # If a Stripe Payment Link was already issued, re-use it.
    if doc.get("stripe_payment_link"):
        return {"checkout_url": doc["stripe_payment_link"], "source": "payment_link"}

    description = doc.get("description") or "BidVex payment"
    total_amount = float(doc.get("total_amount") or 0)
    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid payment amount")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "unit_amount": int(round(total_amount * 100)),
                    "product_data": {
                        "name": f"BidVex Payment — {description[:80]}",
                        "description": f"Reference: {payment_request_id}",
                    },
                },
                "quantity": 1,
            }],
            success_url=f"{_PUBLIC_URL}/pay/{payment_request_id}/success",
            cancel_url=f"{_PUBLIC_URL}/pay/{payment_request_id}",
            metadata={
                "payment_request_id": payment_request_id,
                "user_id": str(doc.get("user_id") or ""),
                "type": "payment_request",
            },
        )
        # Persist the on-the-fly session id so the webhook can match
        # it back to this doc.
        await db.payment_requests.update_one(
            {"id": payment_request_id},
            {"$set": {"stripe_checkout_session_id": session.id}},
        )
        return {"checkout_url": session.url, "source": "checkout_session"}
    except Exception as e:  # noqa: BLE001 — Stripe SDK errors + missing key
        logger.warning(f"[iter261] on-demand checkout failed: {e}")
        return {
            "checkout_url": None,
            "manual_instructions": (
                "Please contact support@bidvex.com to arrange payment. "
                f"Reference ID: {payment_request_id}"
            ),
        }


# ─── Confirm-success handshake from the Pay success page ─────────────

@public_payments_router.post("/pay/{payment_request_id}/confirm-success")
async def confirm_payment_success(payment_request_id: str):
    """Idempotent. Marks the payment request paid AND fires the
    confirmation email + in-app notification — but only on the FIRST
    call (subsequent calls are no-ops)."""
    db = get_db()
    doc = await db.payment_requests.find_one({"id": payment_request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment request not found")
    if doc.get("status") == "paid":
        return {"success": True, "already_paid": True}

    now = datetime.now(timezone.utc)
    await db.payment_requests.update_one(
        {"id": payment_request_id},
        {"$set": {"status": "paid", "paid_at": now.isoformat()}},
    )
    target = await db.users.find_one({"id": doc.get("user_id")}, {"_id": 0}) if doc.get("user_id") else None
    if target:
        try:
            from services.emails._email_core import send_unified_email
            await send_unified_email(
                user=dict(target),
                email_type="payment_confirmed",
                data={
                    "total_amount": f"{float(doc.get('total_amount', 0)):.2f}",
                    "description": doc.get("description") or "BidVex payment",
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter261] payment_confirmed email failed: {exc}")
        try:
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": target.get("id"),
                "type": "payment_confirmed",
                "title": "✅ Payment Confirmed!",
                "body": f"Payment of ${float(doc.get('total_amount', 0)):.2f} CAD received.",
                "link": "/dashboard",
                "is_read": False,
                "created_at": now.isoformat(),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter261] payment_confirmed notification failed: {exc}")
    return {"success": True}


# ─── Authenticated: my outstanding payments ──────────────────────────

@public_payments_router.get("/my/payment-requests")
async def list_my_outstanding_payments(
    current_user: User = Depends(get_current_user),
):
    db = get_db()
    now = datetime.now(timezone.utc)
    cursor = db.payment_requests.find(
        {"user_id": current_user.id, "status": "pending"},
        {"_id": 0},
    ).sort("created_at", -1).limit(50)
    rows = await cursor.to_list(length=50)
    out: List[Dict[str, Any]] = []
    for r in rows:
        # Drop expired rows from the user-facing list (admins can still
        # see them via the admin history table).
        if _is_expired(r):
            continue
        rid = r.get("id")
        out.append({
            "id": rid,
            "total_amount": float(r.get("total_amount") or 0),
            "description": r.get("description") or "",
            "created_at": r.get("created_at"),
            "expires_at": r.get("expires_at"),
            "expiry_label": r.get("expiry_label"),
            "status": r.get("status") or "pending",
            "payment_url": r.get("stripe_payment_link") or _bidvex_pay_url(rid),
        })
    return {"items": out, "total": len(out)}


__all__ = ["public_payments_router"]
