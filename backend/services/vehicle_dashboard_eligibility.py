"""
iter413 — Vehicle Dashboard eligibility helper.

Access rule (any ONE is sufficient):
  1. user.account_type == "broker"
  2. user.partner_verification_status in {"approved", "verified"}
  3. a matching row exists in `vehicle_sellers` with
     verification_status == "approved"

The helper is used by:
  * `GET /api/auth/me` — hydrates the `is_vehicle_dashboard_eligible`
    flag on the user payload so the frontend nav/dropdown gate can
    read it directly.
  * The `/vehicle-dashboard` route guard — same evaluation, same DB
    hit path, no drift possible.

Kept in its own module so both call sites (auth + route guard) import
the SAME function — this is the single source of truth.
"""
from __future__ import annotations
from typing import Any, Dict, Optional


async def is_vehicle_dashboard_eligible(db, user: Dict[str, Any]) -> bool:
    """Return True iff the user qualifies for the Vehicle Dashboard.

    Fails safe (returns False) when either arg is falsy or the DB
    lookup raises — never propagates exceptions up to the auth path.
    """
    if not user:
        return False

    # (1) Explicit broker account.
    if (user.get("account_type") or "").lower() == "broker":
        return True

    # (2) Approved partner (covers brokers/dealers marked via the
    #     Partner admin surface).
    if (user.get("partner_verification_status") or "").lower() in ("approved", "verified"):
        return True

    # (3) Approved row in vehicle_sellers. This is the canonical signal
    #     for licensed vehicle dealers vetted through the /vehicle-admin
    #     approval flow (routes/vehicles_admin.py::approve_seller).
    user_id: Optional[str] = user.get("id") or user.get("_id")
    if not user_id or db is None:
        return False
    try:
        seller = await db.vehicle_sellers.find_one(
            {"user_id": user_id, "verification_status": "approved"},
            {"_id": 1},  # any hit is enough — projection kept tiny
        )
        return seller is not None
    except Exception:
        return False
