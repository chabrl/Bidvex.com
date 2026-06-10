"""
BidVex — Admin Deposit Management
POST /api/admin/vehicle-deposits/{deposit_id}/release → cancel Stripe hold
POST /api/admin/vehicle-deposits/{deposit_id}/capture → charge $500 as penalty
GET  /api/admin/vehicle-deposits                       → list all (with filters)
GET  /api/admin/vehicle-deposits/{deposit_id}          → single deposit detail

All routes require admin. Uses PaymentService.process_deposit_refund /
PaymentService.capture_deposit from services/vehicle_payment.py.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
import logging

from deps import get_db, require_admin, User
from services.vehicle_payment import get_payment_service

logger = logging.getLogger(__name__)
admin_deposits_router = APIRouter(tags=["Admin Deposits"])


@admin_deposits_router.get("/admin/vehicle-deposits")
async def admin_list_vehicle_deposits(
    status: Optional[str] = Query(None, description="pending|paid|authorized|released|refunded|captured|expired"),
    vehicle_id: Optional[str] = None,
    bidder_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_admin),
):
    """List vehicle bid deposits (admin only)."""
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if vehicle_id:
        q["vehicle_id"] = vehicle_id
    if bidder_id:
        q["bidder_id"] = bidder_id

    deposits = (
        await db.vehicle_bid_deposits.find(q, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )

    # Enrich with buyer email + vehicle title (best-effort)
    bidder_ids = list({d.get("bidder_id") for d in deposits if d.get("bidder_id")})
    vehicle_ids = list({d.get("vehicle_id") for d in deposits if d.get("vehicle_id")})

    users_by_id, vehicles_by_id = {}, {}
    if bidder_ids:
        async for u in db.users.find(
            {"id": {"$in": bidder_ids}},
            {"_id": 0, "id": 1, "email": 1, "full_name": 1, "name": 1},
        ):
            users_by_id[u["id"]] = u
    if vehicle_ids:
        async for v in db.vehicle_listings.find(
            {"id": {"$in": vehicle_ids}},
            {"_id": 0, "id": 1, "make": 1, "model": 1, "year": 1, "title": 1},
        ):
            vehicles_by_id[v["id"]] = v

    for d in deposits:
        u = users_by_id.get(d.get("bidder_id"))
        if u:
            d["buyer_email"] = u.get("email")
            d["buyer_name"] = u.get("full_name") or u.get("name")
        v = vehicles_by_id.get(d.get("vehicle_id"))
        if v:
            d["vehicle_title"] = (
                v.get("title")
                or f"{v.get('year','')} {v.get('make','')} {v.get('model','')}".strip()
            )

    return {"count": len(deposits), "deposits": deposits}


@admin_deposits_router.get("/admin/vehicle-deposits/{deposit_id}")
async def admin_get_vehicle_deposit(
    deposit_id: str,
    current_user: User = Depends(require_admin),
):
    """Get one deposit with full audit trail."""
    db = get_db()
    deposit = await db.vehicle_bid_deposits.find_one({"id": deposit_id}, {"_id": 0})
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")

    audit = (
        await db.vehicle_audit_logs.find(
            {"entity_type": "deposit", "entity_id": deposit_id},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(50)
    )
    return {"deposit": deposit, "audit_log": audit}


@admin_deposits_router.post("/admin/vehicle-deposits/{deposit_id}/release")
async def admin_release_vehicle_deposit(
    deposit_id: str,
    reason: Optional[str] = Query("admin_manual_release"),
    current_user: User = Depends(require_admin),
):
    """
    Cancel the Stripe PaymentIntent hold → no funds move.
    Used for non-winners or for winners after their fee invoice is paid.
    """
    db = get_db()
    deposit = await db.vehicle_bid_deposits.find_one({"id": deposit_id})
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    if deposit.get("status") not in ("paid", "authorized"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot release deposit with status: {deposit.get('status')}",
        )

    svc = get_payment_service()
    try:
        result = await svc.process_deposit_refund(db, deposit_id, reason=reason)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception(f"[ADMIN] release deposit {deposit_id} failed")
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    # Admin audit
    await db.vehicle_audit_logs.insert_one({
        "entity_type": "deposit",
        "entity_id": deposit_id,
        "action": "admin_deposit_released",
        "performed_by": current_user.id,
        "performed_by_role": "admin",
        "performed_by_email": getattr(current_user, "email", None),
        "new_value": result,
        "created_at": datetime.now(timezone.utc),
    })
    logger.info(f"[ADMIN] {current_user.id} released deposit {deposit_id}: {reason}")
    return result


@admin_deposits_router.post("/admin/vehicle-deposits/{deposit_id}/capture")
async def admin_capture_vehicle_deposit(
    deposit_id: str,
    reason: Optional[str] = Query("admin_manual_capture"),
    current_user: User = Depends(require_admin),
):
    """
    Capture the $500 deposit hold as a penalty (only valid when the buyer
    missed their platform-fee invoice deadline). This IS the charge path.
    """
    db = get_db()
    deposit = await db.vehicle_bid_deposits.find_one({"id": deposit_id})
    if not deposit:
        raise HTTPException(status_code=404, detail="Deposit not found")
    if deposit.get("status") not in ("paid", "authorized"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot capture deposit with status: {deposit.get('status')}",
        )

    svc = get_payment_service()
    try:
        result = await svc.capture_deposit(db, deposit_id, reason=reason)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception(f"[ADMIN] capture deposit {deposit_id} failed")
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    await db.vehicle_audit_logs.insert_one({
        "entity_type": "deposit",
        "entity_id": deposit_id,
        "action": "admin_deposit_captured",
        "performed_by": current_user.id,
        "performed_by_role": "admin",
        "performed_by_email": getattr(current_user, "email", None),
        "new_value": result,
        "created_at": datetime.now(timezone.utc),
    })
    logger.warning(
        f"[ADMIN] {current_user.id} CAPTURED deposit {deposit_id}: {reason}"
    )
    return result


# ═════════════════ Vehicle Invoice Admin Actions ════════════════════════════

@admin_deposits_router.post("/admin/vehicle-invoices/{invoice_id}/mark-paid")
async def admin_mark_invoice_paid(
    invoice_id: str,
    note: Optional[str] = Query("admin_manual_payment"),
    current_user: User = Depends(require_admin),
):
    """
    Admin override: mark a vehicle invoice as paid (e.g. buyer paid the 2.5%
    platform fee via offline e-transfer, or admin is settling manually).
    This does NOT charge anything — it just updates the invoice status.
    """
    db = get_db()
    invoice = await db.vehicle_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Invoice already paid")

    now = datetime.now(timezone.utc)
    total = invoice.get("total_amount") or 0
    await db.vehicle_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "payment_status": "paid",
            "paid_at": now,
            "paid_amount": total,
            "payment_method": "admin_override",
            "admin_payment_note": note,
            "admin_payment_by": current_user.id,
        }},
    )
    await db.vehicle_audit_logs.insert_one({
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "action": "admin_mark_invoice_paid",
        "performed_by": current_user.id,
        "performed_by_role": "admin",
        "performed_by_email": getattr(current_user, "email", None),
        "new_value": {"note": note, "amount": total},
        "created_at": now,
    })
    logger.info(f"[ADMIN] {current_user.id} marked invoice {invoice_id} PAID ({note})")
    return {"success": True, "invoice_id": invoice_id, "status": "paid", "amount": total}


@admin_deposits_router.post("/admin/vehicle-invoices/{invoice_id}/send-reminder")
async def admin_send_invoice_reminder(
    invoice_id: str,
    current_user: User = Depends(require_admin),
):
    """Send a payment-reminder email to the invoice's buyer."""
    db = get_db()
    invoice = await db.vehicle_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    buyer = await db.users.find_one(
        {"id": invoice.get("buyer_id")},
        {"_id": 0, "email": 1, "full_name": 1, "name": 1},
    )
    if not buyer or not buyer.get("email"):
        raise HTTPException(status_code=400, detail="Buyer email not found")

    # Reminder via existing transactional email service
    try:
        from services.emails._email_core import send_email, _base_template, _format_currency
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email service unavailable: {e}")

    amount_due = (
        float(invoice.get("total_amount") or 0)
        + float(invoice.get("penalty_amount") or 0)
        - float(invoice.get("paid_amount") or 0)
    )
    buyer_name = buyer.get("full_name") or buyer.get("name") or buyer.get("email")
    content = f"""
    <h2 style="color: #dc2626;">Payment Reminder — BidVex</h2>
    <p>Hi {buyer_name},</p>
    <p>This is a reminder that your BidVex invoice <strong>{invoice.get('id')}</strong>
       is currently <strong>{invoice.get('payment_status')}</strong>.</p>
    <p>Amount due: <strong>{_format_currency(amount_due)}</strong></p>
    <p>Please log in to pay: <a href="https://www.bidvex.com/dashboard/invoices" clicktracking=off>View Invoice</a></p>
    <p style="margin-top: 24px;">— BidVex Canada, Sherbrooke, QC</p>
    """
    await send_email(
        to_email=buyer["email"],
        subject=f"Payment Reminder — Invoice {invoice.get('id')}",
        html_content=_base_template(content, "Payment Reminder"),
    )
    await db.vehicle_audit_logs.insert_one({
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "action": "admin_send_invoice_reminder",
        "performed_by": current_user.id,
        "performed_by_role": "admin",
        "new_value": {"recipient": buyer["email"], "amount_due": amount_due},
        "created_at": datetime.now(timezone.utc),
    })
    return {"success": True, "sent_to": buyer["email"], "amount_due": amount_due}
