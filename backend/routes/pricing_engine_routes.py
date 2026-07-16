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


# ─────────────────────────────────────────────────────────────────────
# iter350 — Admin: CRA-compliant Tax Rate Configuration
# GET /api/admin/pricing/tax-rates          → list all 14 rows
# GET /api/admin/pricing/tax-rates/{prov}   → single row
# PUT /api/admin/pricing/tax-rates/{prov}   → update GST/QST/HST/label
#   Body: {"gst": 0.05, "qst": 0.09975, "hst": 0.0, "label": "GST + QST (14.975%)"}
# Every mutation snapshots the previous row into `tax_rate_config_history`.
# ─────────────────────────────────────────────────────────────────────

@pricing_engine_router.get("/admin/pricing/tax-rates")
async def list_tax_rates(current_user: User = Depends(get_current_user)):
    """List all configured tax rate rows (14 provinces + INTL)."""
    await _require_admin(current_user)
    db = get_db()
    from services.tax_rate_config import refresh_cache_from_db, BOOTSTRAP_RATES
    await refresh_cache_from_db(db)
    docs = await db.tax_rate_config.find({}, {"_id": 0}).to_list(length=100)
    # Ensure every canonical province is represented even if freshly seeded
    seen = {d["province"] for d in docs}
    for code in BOOTSTRAP_RATES:
        if code not in seen:
            row = BOOTSTRAP_RATES[code]
            docs.append({
                "province": code,
                "gst": str(row["gst"]), "qst": str(row["qst"]), "hst": str(row["hst"]),
                "combined": str(row["combined"]), "label": str(row["label"]),
                "source": "bootstrap_only",
            })
    return {"tax_rates": docs, "count": len(docs)}


@pricing_engine_router.get("/admin/pricing/tax-rates/{province}")
async def get_tax_rate_admin(
    province: str = Path(..., description="Province code, e.g. QC/ON/AB/INTL"),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    db = get_db()
    from services.tax_rate_config import normalize_province
    code = normalize_province(province)
    doc = await db.tax_rate_config.find_one({"province": code}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"tax_rate_not_configured:{code}")
    return doc


@pricing_engine_router.put("/admin/pricing/tax-rates/{province}")
async def update_tax_rate_admin(
    province: str = Path(...),
    gst: float | None = Body(None, ge=0, le=1),
    qst: float | None = Body(None, ge=0, le=1),
    hst: float | None = Body(None, ge=0, le=1),
    label: str | None = Body(None),
    current_user: User = Depends(get_current_user),
):
    """Update a tax rate row. Snapshots prior row to `tax_rate_config_history`.
    In-memory cache is invalidated immediately (next call refreshes)."""
    admin = await _require_admin(current_user)
    db = get_db()
    from decimal import Decimal
    from services.tax_rate_config import update_tax_rate
    result = await update_tax_rate(
        db,
        province,
        gst=Decimal(str(gst)) if gst is not None else None,
        qst=Decimal(str(qst)) if qst is not None else None,
        hst=Decimal(str(hst)) if hst is not None else None,
        label=label,
        updated_by_user_id=str(admin.get("email") or current_user.id),
    )
    return result


@pricing_engine_router.get("/admin/pricing/tax-rates-history/{province}")
async def tax_rate_history(
    province: str = Path(...),
    current_user: User = Depends(get_current_user),
):
    """Immutable audit trail of every rate mutation for a given province."""
    await _require_admin(current_user)
    db = get_db()
    from services.tax_rate_config import normalize_province
    code = normalize_province(province)
    rows = await db.tax_rate_config_history.find(
        {"province": code}, {"_id": 0}
    ).sort("effective_to", -1).to_list(length=200)
    return {"province": code, "history": rows, "count": len(rows)}
