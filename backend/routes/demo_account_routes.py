"""iter210 Step 5 — Demo Account admin HTTP endpoints."""
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Path

from deps import get_current_user, get_db, User

demo_accounts_router = APIRouter(tags=["Demo Accounts"])


async def _require_admin(current_user: User):
    db = get_db()
    admin = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1, "email": 1})
    if not admin or admin.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")
    return admin


@demo_accounts_router.get("/admin/demo-accounts")
async def list_demo_accounts(current_user: User = Depends(get_current_user)):
    await _require_admin(current_user)
    db = get_db()
    from services.demo_account_service import list_demo_accounts as _list
    return {"items": await _list(db)}


@demo_accounts_router.post("/admin/demo-accounts")
async def create_demo_account(
    account_type: str = Body(...),
    company_name: str = Body(...),
    contact_email: str = Body(...),
    province: str = Body(...),
    duration_days: int = Body(...),
    notes: str = Body(""),
    current_user: User = Depends(get_current_user),
):
    admin = await _require_admin(current_user)
    db = get_db()
    from services.demo_account_service import create_demo_account as _create
    try:
        return await _create(
            db,
            account_type=account_type,
            company_name=company_name,
            contact_email=contact_email,
            province=province,
            duration_days=duration_days,
            notes=notes,
            created_by_email=admin.get("email"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@demo_accounts_router.post("/admin/demo-accounts/{user_id}/extend")
async def extend_demo_account(
    user_id: str = Path(...),
    additional_days: int = Body(14, embed=True),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    db = get_db()
    from services.demo_account_service import extend_demo_account as _extend
    try:
        return await _extend(db, user_id, additional_days=additional_days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@demo_accounts_router.post("/admin/demo-accounts/{user_id}/convert-to-real")
async def convert_demo(
    user_id: str = Path(...),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    db = get_db()
    from services.demo_account_service import convert_demo_to_real
    try:
        return await convert_demo_to_real(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@demo_accounts_router.delete("/admin/demo-accounts/{user_id}")
async def delete_demo(
    user_id: str = Path(...),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(current_user)
    db = get_db()
    from services.demo_account_service import delete_demo_account as _delete
    try:
        return await _delete(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@demo_accounts_router.post("/admin/demo-accounts/check-expiry")
async def run_expiry_check(current_user: User = Depends(get_current_user)):
    """Admin manual trigger for the daily expiry job."""
    await _require_admin(current_user)
    db = get_db()
    from services.demo_account_service import check_demo_account_expiry
    return await check_demo_account_expiry(db)
