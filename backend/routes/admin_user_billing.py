"""
iter310 — Admin user-billing routes (split out of admin_user_actions.py)
========================================================================

Endpoints handling tier modifications, subscription overrides, and
platform-fee/transaction visibility for the Admin → Users tab.

Routes (all mounted at `/api/admin/users/{user_id}/...`):
  • POST /change-tier            — set the user's buyer_tier (standard / premium / vip_elite)
  • GET  /transactions           — buyer + seller transaction history
  • GET  /subscription-status    — composite snapshot of dealer / partner / storage flags

These were factored out as part of the iter310 admin refactor — billing
operations have their own audit cadence and tend to be touched together
during platform-fee work, while account CRUD lives in
`admin_user_management.py`. The `admin_user_actions.py` shim re-exports
`router` that includes both for backwards compatibility with existing
imports in `server.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import User, get_db
from routes.admin_user_helpers import record_admin_action, require_admin


router = APIRouter(
    prefix="/admin/users",
    tags=["admin-user-billing"],
)


# ─── Change buyer tier ────────────────────────────────────────────────


class ChangeTierPayload(BaseModel):
    tier: str  # standard | premium | vip_elite


_VALID_TIERS = {"standard", "premium", "vip_elite"}


@router.post("/{user_id}/change-tier")
async def admin_change_buyer_tier(
    user_id: str,
    payload: ChangeTierPayload,
    current_user: User = Depends(require_admin),
):
    """Change an individual user's buyer tier (persists to MongoDB)."""
    if payload.tier not in _VALID_TIERS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_tier",
                "message_en": f"Tier must be one of {sorted(_VALID_TIERS)}",
                "message_fr": f"Le niveau doit être l'un de {sorted(_VALID_TIERS)}",
            },
        )
    db = get_db()
    user_doc = await db.users.find_one(
        {"id": user_id}, {"_id": 0, "buyer_tier": 1, "email": 1}
    )
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    prev = user_doc.get("buyer_tier") or "standard"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "buyer_tier": payload.tier,
            "buyer_tier_updated_at": datetime.now(timezone.utc).isoformat(),
            "buyer_tier_updated_by": current_user.id,
        }},
    )
    await record_admin_action(
        db,
        admin_id=current_user.id,
        admin_email=current_user.email,
        action="change_tier",
        target_user_id=user_id,
        content={"from": prev, "to": payload.tier},
    )
    return {"success": True, "from": prev, "to": payload.tier}


# ─── Transactions list ────────────────────────────────────────────────


@router.get("/{user_id}/transactions")
async def admin_user_transactions(
    user_id: str,
    limit: int = 50,
    current_user: User = Depends(require_admin),
):
    """List transactions (buyer + seller side) for the user."""
    db = get_db()
    rows = await db.transactions.find(
        {"$or": [{"buyer_id": user_id}, {"seller_id": user_id}]},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"total": len(rows), "transactions": rows}


# ─── Subscription status snapshot ─────────────────────────────────────


@router.get("/{user_id}/subscription-status")
async def admin_user_subscription_status(
    user_id: str,
    current_user: User = Depends(require_admin),
):
    """Compose a snapshot of the user's subscription flags for the admin
    "View Subscription Status" modal. Works for dealer, partner, and
    storage-facility accounts."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {
        "_id": 0,
        # Dealer
        "dealer_subscription_active": 1, "dealer_subscription_status": 1,
        "dealer_subscription_renewal": 1, "dealer_subscription_start": 1,
        "dealer_subscription_manual_method": 1, "dealer_subscription_manual_reference": 1,
        "vehicle_dealer_suspended": 1,
        # Partner
        "partner_subscription_active": 1, "partner_subscription_status": 1,
        "partner_subscription_renewal": 1, "partner_subscription_start": 1,
        # Storage facility
        "storage_subscription_active": 1, "storage_subscription_status": 1,
        "storage_subscription_renewal": 1,
        # Account flags
        "is_vehicle_dealer": 1, "is_licensed_partner": 1, "is_storage_facility": 1,
        "buyer_tier": 1, "account_type": 1,
    }) or {}
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    return user_doc
