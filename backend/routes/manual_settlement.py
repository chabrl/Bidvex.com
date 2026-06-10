"""
iter211 — Manual Settlement routes (admin + user-facing toggle)

Endpoints:
  Admin-only:
    POST   /api/admin/manual-settle/subscription
    GET    /api/admin/pending-commissions
    POST   /api/admin/pending-commissions/{id}/mark-paid
    GET    /api/admin/financial-ledger
  User-facing:
    GET    /api/users/me/commission-payout-method
    PUT    /api/users/me/commission-payout-method
    GET    /api/users/me/outstanding-commission
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from deps import get_current_user, User, get_db
from services.manual_settlement_service import (
    manual_settle_subscription,
    settle_pending_commission,
    user_is_blocked_by_outstanding_commission,
    SUBSCRIPTION_FIELDS,
    ALLOWED_PAYMENT_METHODS,
    MANUAL_COMMISSION_GATE_CAD,
    PENDING_COMMISSIONS_COLLECTION,
    LEDGER_COLLECTION,
)

logger = logging.getLogger(__name__)
manual_settlement_router = APIRouter(tags=["Manual Settlement"])

ALLOWED_COMMISSION_METHODS = ("auto", "manual")


async def _require_admin(current_user: User):
    db = get_db()
    me = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1})
    if not me or me.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")


# ─── Models ──────────────────────────────────────────────────────────────


class ManualSubscriptionSettleBody(BaseModel):
    target_user_id: str
    account_kind: str = Field(..., description="vehicle_dealer | partner | storage_facility")
    payment_method: str = Field(..., description="e_transfer | cheque | wire | cash")
    reference_number: str
    amount_cad: float = 100.0
    active_until: Optional[str] = None  # ISO datetime; defaults to +365 days
    notes: str = ""


class MarkPendingPaidBody(BaseModel):
    payment_method: str
    reference_number: str
    notes: str = ""


class CommissionPayoutMethodBody(BaseModel):
    method: str = Field(..., description="auto | manual")


# ─── Admin: manual subscription settle ──────────────────────────────────


@manual_settlement_router.post("/admin/manual-settle/subscription")
async def admin_manual_settle_subscription(
    body: ManualSubscriptionSettleBody,
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    if body.account_kind not in SUBSCRIPTION_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported account_kind. Allowed: {list(SUBSCRIPTION_FIELDS.keys())}",
        )
    pm = (body.payment_method or "").lower().strip().replace("-", "_")
    if pm not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported payment_method. Allowed: {sorted(ALLOWED_PAYMENT_METHODS)}",
        )
    try:
        result = await manual_settle_subscription(
            get_db(),
            target_user_id=body.target_user_id,
            admin_user_id=current_user.id,
            account_kind=body.account_kind,
            payment_method=pm,
            reference_number=body.reference_number,
            amount_cad=body.amount_cad,
            active_until=body.active_until,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Best-effort bilingual confirmation email
    try:
        await _send_manual_settlement_email(
            get_db(),
            user_id=body.target_user_id,
            kind="subscription",
            amount_cad=body.amount_cad,
            payment_method=pm,
            reference_number=body.reference_number,
            extra={"renewal_until": result["renewal_until"]},
        )
    except Exception as exc:
        logger.warning(f"[manual-settle] email failed: {exc}")

    return result


# ─── Admin: pending commissions queue ───────────────────────────────────


@manual_settlement_router.get("/admin/pending-commissions")
async def list_pending_commissions(
    status: str = Query("pending", description="pending | paid | all"),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    db = get_db()
    q: dict = {} if status == "all" else {"status": status}
    rows = await db[PENDING_COMMISSIONS_COLLECTION].find(q, {"_id": 0}).sort("created_at", -1).to_list(500)

    # Enrich each row with user info
    user_ids = list({r["user_id"] for r in rows if r.get("user_id")})
    users_by_id = {}
    if user_ids:
        async for u in db.users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "email": 1, "full_name": 1, "partner_company_name": 1,
             "commission_payout_method": 1, "outstanding_manual_commission_cad": 1},
        ):
            users_by_id[u["id"]] = u

    for r in rows:
        u = users_by_id.get(r["user_id"]) or {}
        r["user_email"] = u.get("email")
        r["user_name"] = u.get("full_name") or u.get("partner_company_name") or u.get("email")
        r["user_outstanding_cad"] = float(u.get("outstanding_manual_commission_cad") or 0)

    pending_sum = sum(r["commission_amount_cad"] for r in rows if r["status"] == "pending")
    return {
        "rows": rows,
        "summary": {
            "count": len(rows),
            "pending_count": sum(1 for r in rows if r["status"] == "pending"),
            "pending_total_cad": round(pending_sum, 2),
            "threshold_cad": float(MANUAL_COMMISSION_GATE_CAD),
        },
    }


@manual_settlement_router.post("/admin/pending-commissions/{pending_id}/mark-paid")
async def admin_mark_pending_commission_paid(
    pending_id: str,
    body: MarkPendingPaidBody,
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    pm = (body.payment_method or "").lower().strip().replace("-", "_")
    if pm not in ALLOWED_PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"Unsupported payment_method. Allowed: {sorted(ALLOWED_PAYMENT_METHODS)}")
    db = get_db()
    try:
        result = await settle_pending_commission(
            db,
            pending_id=pending_id,
            admin_user_id=current_user.id,
            payment_method=pm,
            reference_number=body.reference_number,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = await db[PENDING_COMMISSIONS_COLLECTION].find_one({"id": pending_id}, {"_id": 0})
    if row:
        try:
            await _send_manual_settlement_email(
                db,
                user_id=row["user_id"],
                kind="commission",
                amount_cad=row["commission_amount_cad"],
                payment_method=pm,
                reference_number=body.reference_number,
                extra={"listing_title": row.get("listing_title")},
            )
        except Exception as exc:
            logger.warning(f"[manual-commission] email failed: {exc}")

    return result


# ─── Admin: financial ledger view ───────────────────────────────────────


@manual_settlement_router.get("/admin/financial-ledger")
async def list_financial_ledger(
    kind: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    db = get_db()
    q: dict = {}
    if kind:
        q["kind"] = kind
    if user_id:
        q["user_id"] = user_id
    rows = await db[LEDGER_COLLECTION].find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"rows": rows, "count": len(rows)}


# ─── User: commission payout method toggle ──────────────────────────────


@manual_settlement_router.get("/users/me/commission-payout-method")
async def get_my_commission_payout_method(current_user: User = Depends(get_current_user)):
    db = get_db()
    u = await db.users.find_one({"id": current_user.id}, {"_id": 0, "commission_payout_method": 1})
    return {"method": (u or {}).get("commission_payout_method") or "auto"}


@manual_settlement_router.put("/users/me/commission-payout-method")
async def set_my_commission_payout_method(
    body: CommissionPayoutMethodBody,
    current_user: User = Depends(get_current_user),
):
    method = (body.method or "").lower().strip()
    if method not in ALLOWED_COMMISSION_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"method must be one of {list(ALLOWED_COMMISSION_METHODS)}",
        )
    db = get_db()
    # Only partner / storage facility / dealer accounts are allowed to opt out
    u = await db.users.find_one({"id": current_user.id}, {"_id": 0, "is_partner": 1, "is_vehicle_dealer": 1, "is_storage_facility": 1})
    if not u or not (u.get("is_partner") or u.get("is_vehicle_dealer") or u.get("is_storage_facility")):
        raise HTTPException(status_code=403, detail="manual_payout_not_available_for_account_type")
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "commission_payout_method": method,
            "commission_payout_method_set_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"ok": True, "method": method}


@manual_settlement_router.get("/users/me/outstanding-commission")
async def get_my_outstanding_commission(current_user: User = Depends(get_current_user)):
    db = get_db()
    info = await user_is_blocked_by_outstanding_commission(db, current_user.id)
    return info


# ─── Bilingual receipt email helper ─────────────────────────────────────


_METHOD_COPY = {
    "e_transfer": ("e-Transfer", "virement Interac"),
    "cheque":     ("cheque",     "chèque"),
    "wire":       ("wire transfer", "virement bancaire"),
    "cash":       ("cash",       "espèces"),
}


async def _send_manual_settlement_email(
    db, *, user_id: str, kind: str, amount_cad: float,
    payment_method: str, reference_number: str, extra: dict,
):
    """Send a bilingual receipt for either subscription or commission settle."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "full_name": 1, "preferred_language": 1})
    if not user or not user.get("email"):
        return False
    lang = (user.get("preferred_language") or "en").lower()
    is_fr = lang.startswith("fr")

    en_pm, fr_pm = _METHOD_COPY.get(payment_method, (payment_method, payment_method))

    if kind == "subscription":
        renewal = extra.get("renewal_until", "")
        try:
            renewal_display = datetime.fromisoformat(renewal.replace("Z", "+00:00")).strftime("%B %d, %Y") if renewal else "—"
        except ValueError:
            renewal_display = renewal
        subject = (
            f"Subscription activated — paid by {en_pm}"
            if not is_fr else
            f"Abonnement activé — payé par {fr_pm}"
        )
        body_en = (
            f"<p>Your BidVex annual subscription has been activated.</p>"
            f"<ul>"
            f"<li><strong>Payment method:</strong> Paid by {en_pm}</li>"
            f"<li><strong>Reference:</strong> {reference_number}</li>"
            f"<li><strong>Amount:</strong> ${amount_cad:.2f} CAD</li>"
            f"<li><strong>Active until:</strong> {renewal_display}</li>"
            f"</ul>"
            f"<p>Thank you!</p>"
        )
        body_fr = (
            f"<p>Votre abonnement annuel BidVex a été activé.</p>"
            f"<ul>"
            f"<li><strong>Mode de paiement :</strong> Payé par {fr_pm}</li>"
            f"<li><strong>Référence :</strong> {reference_number}</li>"
            f"<li><strong>Montant :</strong> {amount_cad:.2f} $ CAD</li>"
            f"<li><strong>Actif jusqu'au :</strong> {renewal_display}</li>"
            f"</ul>"
            f"<p>Merci !</p>"
        )
    else:  # commission
        listing_title = extra.get("listing_title", "")
        subject = (
            f"Commission settled — paid by {en_pm}"
            if not is_fr else
            f"Commission réglée — payée par {fr_pm}"
        )
        body_en = (
            f"<p>Your platform commission has been marked as paid.</p>"
            f"<ul>"
            f"{f'<li><strong>Listing:</strong> {listing_title}</li>' if listing_title else ''}"
            f"<li><strong>Payment method:</strong> Paid by {en_pm}</li>"
            f"<li><strong>Reference:</strong> {reference_number}</li>"
            f"<li><strong>Amount:</strong> ${amount_cad:.2f} CAD</li>"
            f"</ul>"
            f"<p>Thank you!</p>"
        )
        body_fr = (
            f"<p>Votre commission de plateforme a été réglée.</p>"
            f"<ul>"
            f"{f'<li><strong>Annonce :</strong> {listing_title}</li>' if listing_title else ''}"
            f"<li><strong>Mode de paiement :</strong> Payée par {fr_pm}</li>"
            f"<li><strong>Référence :</strong> {reference_number}</li>"
            f"<li><strong>Montant :</strong> {amount_cad:.2f} $ CAD</li>"
            f"</ul>"
            f"<p>Merci !</p>"
        )

    html = body_fr if is_fr else body_en
    try:
        from services.emails._email_core import send_email
        send_email(to_email=user["email"], subject=subject, html_content=html)
        return True
    except Exception as exc:
        logger.warning(f"[manual-settle] send_email failed: {exc}")
        return False
