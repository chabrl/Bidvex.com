"""iter210 Step 3 — Admin Pricing Engine HTTP endpoints."""
from fastapi import APIRouter, Body, Depends, HTTPException, Path

from deps import get_current_user, get_db, User

pricing_engine_router = APIRouter(tags=["Pricing Engine"])

VALID_KEYS = {"vehicle_dealer_annual_fee", "partner_annual_fee"}


async def _require_admin(current_user: User):
    db = get_db()
    admin = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1, "email": 1})
    if not admin or admin.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")
    return admin


@pricing_engine_router.get("/admin/pricing-engine")
async def list_pricing(current_user: User = Depends(get_current_user)):
    await _require_admin(current_user)
    db = get_db()
    from services.pricing_engine_service import read_pricing
    return {key: await read_pricing(db, key) for key in VALID_KEYS}


@pricing_engine_router.get("/admin/pricing-engine/{key}")
async def get_one_pricing(
    key: str = Path(...),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    if key not in VALID_KEYS:
        raise HTTPException(status_code=404, detail="unknown_pricing_key")
    db = get_db()
    from services.pricing_engine_service import read_pricing
    return await read_pricing(db, key)


@pricing_engine_router.put("/admin/pricing-engine/{key}")
async def update_one_pricing(
    key: str = Path(...),
    base_price_cad: float | None = Body(None),
    launch_discount_percent: float | None = Body(None),
    launch_window_days: int | None = Body(None),
    current_user: User = Depends(get_current_user),
):
    admin = await _require_admin(current_user)
    if key not in VALID_KEYS:
        raise HTTPException(status_code=404, detail="unknown_pricing_key")
    db = get_db()
    from services.pricing_engine_service import update_pricing
    try:
        return await update_pricing(
            db, key,
            base_price_cad=base_price_cad,
            launch_discount_percent=launch_discount_percent,
            launch_window_days=launch_window_days,
            admin_email=admin.get("email"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Public read — used by the dealer registration page to render the launch banner
@pricing_engine_router.get("/pricing-engine/public/{key}")
async def get_public_pricing(key: str = Path(...)):
    if key not in VALID_KEYS:
        raise HTTPException(status_code=404, detail="unknown_pricing_key")
    db = get_db()
    from services.pricing_engine_service import read_pricing
    doc = await read_pricing(db, key)
    # Strip Stripe IDs from public response
    return {
        "key": doc["key"],
        "base_price_cad": doc["base_price_cad"],
        "launch_discount_percent": doc["launch_discount_percent"],
        "launch_window_days": doc["launch_window_days"],
        "launch_cutoff_date": doc["launch_cutoff_date"],
        "effective_price_cad": doc["effective_price_cad"],
        "is_within_launch_window": doc["is_within_launch_window"],
    }
