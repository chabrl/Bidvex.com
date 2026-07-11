"""
routes/receipts.py — iter298 BUG 4

Buyer receipts + seller statements surfaces.

GET /api/receipts/mine?role=buyer|seller — caller's records,
newest-first. Buyer dashboard → "My Purchases → Receipts",
seller dashboard → "My Sales → Statements".
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import get_db, get_current_user

logger = logging.getLogger(__name__)
receipts_router = APIRouter(prefix="/receipts", tags=["receipts"])


@receipts_router.get("/mine")
async def get_my_receipts(
    role: str = Query("buyer", pattern="^(buyer|seller)$"),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    db = get_db()
    user_id = user.id if hasattr(user, "id") else user.get("id")
    rtype = "buyer_receipt" if role == "buyer" else "seller_statement"
    rows = await db.receipts.find(
        {"user_id": user_id, "type": rtype}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    return {"receipts": rows, "total": len(rows), "role": role}


@receipts_router.get("/{receipt_id}")
async def get_receipt(receipt_id: str, user=Depends(get_current_user)):
    db = get_db()
    user_id = user.id if hasattr(user, "id") else user.get("id")
    row = await db.receipts.find_one({"id": receipt_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    is_admin = getattr(user, "role", None) in ("admin", "super_admin")
    if row.get("user_id") != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Not your receipt")
    return row
