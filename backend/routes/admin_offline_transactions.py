"""
iter310 — Admin "Record Offline Transaction"

Lets an admin manually record a sale that happened OUTSIDE the platform
(e.g. buyer + seller settled via cash / e-transfer directly) so it shows
up in books, tax exports, and seller payout flows without triggering a
real Stripe charge.

POST /api/admin/offline-transactions/record
GET  /api/admin/offline-transactions
GET  /api/admin/offline-transactions/{id}
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from deps import get_db, require_admin, User


admin_offline_tx_router = APIRouter(tags=["Admin Offline Transactions"])


class OfflineTxBody(BaseModel):
    listing_id:     str                          = Field(..., min_length=1)
    listing_kind:   Literal["listing", "vehicle", "multi_item", "storage"] = "listing"
    buyer_id:       Optional[str]                = None
    buyer_email:    Optional[str]                = None
    seller_id:      Optional[str]                = None
    amount:         float                        = Field(..., gt=0)
    currency:       str                          = Field(default="CAD", max_length=3)
    payment_method: Literal["cash", "etransfer", "wire", "cheque", "other"] = "cash"
    transaction_date: Optional[datetime]         = None
    admin_note:     Optional[str]                = Field(default=None, max_length=2000)
    trigger_payout_notification: bool            = True


@admin_offline_tx_router.post("/admin/offline-transactions/record")
async def admin_record_offline_transaction(
    payload: OfflineTxBody,
    current_user: User = Depends(require_admin),
):
    """Record a deal that closed outside the platform — bookkeeping only.

    Does NOT charge anyone via Stripe and does NOT email the buyer with a
    "you've been charged" notice (because no real charge happened). DOES
    optionally fire the seller payout notification flow so the seller
    knows the deal was logged.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    when = payload.transaction_date or now

    # Resolve listing (best-effort) — supports all 4 sections.
    listing_doc = None
    for coll in ("listings", "vehicle_listings", "multi_item_listings", "storage_auctions"):
        listing_doc = await db[coll].find_one({"id": payload.listing_id}, {"_id": 0})
        if listing_doc:
            break
    if not listing_doc:
        raise HTTPException(status_code=404, detail="listing_not_found")

    seller_id = payload.seller_id or listing_doc.get("seller_id")
    buyer_id = payload.buyer_id
    buyer_email = payload.buyer_email

    record = {
        "id":                str(uuid.uuid4()),
        "listing_id":        payload.listing_id,
        "listing_title":     listing_doc.get("title") or "",
        "listing_kind":      payload.listing_kind,
        "buyer_id":          buyer_id,
        "buyer_email":       buyer_email,
        "seller_id":         seller_id,
        "amount":            round(float(payload.amount), 2),
        "currency":          (payload.currency or "CAD").upper(),
        "payment_method":    payload.payment_method,
        "transaction_date":  when,
        "admin_note":        payload.admin_note,
        "recorded_by":       current_user.id,
        "recorded_by_email": getattr(current_user, "email", None),
        "recorded_at":       now,
        "status":            "recorded",
        "stripe_payment_intent_id": None,
        "is_offline":        True,
    }
    await db.admin_offline_transactions.insert_one(record)
    # Pop the mongo ObjectId injected by insert_one (not JSON-serializable).
    record.pop("_id", None)

    # Admin audit log.
    await db.admin_action_logs.insert_one({
        "id":              str(uuid.uuid4()),
        "admin_id":        current_user.id,
        "admin_email":     getattr(current_user, "email", None),
        "action":          "record_offline_transaction",
        "entity_type":     "offline_transaction",
        "entity_id":       record["id"],
        "details":         {"listing_id": payload.listing_id, "amount": record["amount"], "method": payload.payment_method},
        "created_at":      now,
    })

    # Optional: seller payout notification (no buyer email, no real charge).
    if payload.trigger_payout_notification and seller_id:
        try:
            seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1})
            if seller and seller.get("email"):
                await db.notifications.insert_one({
                    "id":         str(uuid.uuid4()),
                    "user_id":    seller_id,
                    "kind":       "offline_sale_recorded",
                    "title_en":   f"Offline sale recorded — ${record['amount']:.2f} {record['currency']}",
                    "title_fr":   f"Vente hors ligne enregistrée — {record['amount']:.2f} $ {record['currency']}",
                    "body_en":    f"Admin recorded an offline transaction for '{record['listing_title']}'.",
                    "body_fr":    f"L'admin a enregistré une transaction hors ligne pour « {record['listing_title']} ».",
                    "link":       f"/dashboard/sales/{record['id']}",
                    "is_read":    False,
                    "created_at": now,
                })
        except Exception:  # noqa: BLE001
            # Non-fatal — bookkeeping record is already saved.
            pass

    return {"status": "recorded", "transaction": record}


@admin_offline_tx_router.get("/admin/offline-transactions")
async def admin_list_offline_transactions(
    start_date: Optional[str] = Query(None),
    end_date:   Optional[str] = Query(None),
    listing_id: Optional[str] = Query(None),
    page:       int            = Query(1, ge=1),
    per_page:   int            = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    db = get_db()
    q: dict = {}
    if listing_id:
        q["listing_id"] = listing_id
    if start_date:
        try:
            q.setdefault("transaction_date", {})["$gte"] = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if end_date:
        try:
            q.setdefault("transaction_date", {})["$lt"] = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    skip = (page - 1) * per_page
    cursor = db.admin_offline_transactions.find(q, {"_id": 0}).sort("transaction_date", -1).skip(skip).limit(per_page)
    rows = await cursor.to_list(per_page)
    total = await db.admin_offline_transactions.count_documents(q)
    return {"count": total, "page": page, "per_page": per_page, "transactions": rows}


@admin_offline_tx_router.get("/admin/offline-transactions/{tx_id}")
async def admin_get_offline_transaction(tx_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    row = await db.admin_offline_transactions.find_one({"id": tx_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return row


__all__ = ["admin_offline_tx_router"]
