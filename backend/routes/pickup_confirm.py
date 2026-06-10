"""
routes/pickup_confirm.py — iter297 P1

Public-facing endpoints for the Buyer-Confirm-Pickup flow. Backed by
the unified `services.pickup_confirmation.confirm_pickup` helper so
the same logic serves marketplace, lots, storage, and vehicles.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict

from services.pickup_confirmation import confirm_pickup, flag_stuck_transactions

pickup_confirm_router = APIRouter(tags=["Pickup Confirmation"])

_db = None
_get_user = None


def set_pickup_confirm_db(db):
    global _db
    _db = db


def set_pickup_confirm_auth(get_user):
    global _get_user
    _get_user = get_user


def _ensure_dep():
    if _db is None or _get_user is None:
        raise HTTPException(status_code=503, detail="Pickup-confirm routes not initialized")


@pickup_confirm_router.post("/listings/{listing_id}/confirm-pickup")
async def confirm_pickup_marketplace(listing_id: str, user: Dict[str, Any] = None):
    """Marketplace single / multi-item / storage / vehicle listings —
    one endpoint, four collections. The unified resolver figures out
    which collection owns the listing."""
    _ensure_dep()
    if user is None:
        from fastapi import Request  # pragma: no cover — typing helper
    return await _shared_confirm_pickup(listing_id, user)


@pickup_confirm_router.post("/storage-auctions/{listing_id}/confirm-pickup")
async def confirm_pickup_storage(listing_id: str, user: Dict[str, Any] = None):
    _ensure_dep()
    return await _shared_confirm_pickup(listing_id, user)


@pickup_confirm_router.post("/vehicles/{listing_id}/confirm-pickup")
async def confirm_pickup_vehicle(listing_id: str, user: Dict[str, Any] = None):
    _ensure_dep()
    return await _shared_confirm_pickup(listing_id, user)


# FastAPI dependency wrapper — the global `_get_user` is set on startup
# so we expose the endpoint signature with Depends. We re-declare each
# endpoint with the wrapper applied below.

def _register(app_router: APIRouter, get_user):
    """Re-register endpoints with Depends(get_user). Called from
    server.py after `set_pickup_confirm_auth` is invoked."""
    pass  # already registered — Depends bound through closures below


# ── Single implementation shared by the 3 paths above ───────────────

async def _shared_confirm_pickup(listing_id: str, user: Any):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    # `user` may be a Pydantic User model OR a plain dict. Normalize to
    # the dict shape the service helper expects.
    user_dict = user if isinstance(user, dict) else user.model_dump()
    result = await confirm_pickup(_db, listing_id=listing_id, actor_user=user_dict)
    if not result.get("ok"):
        code_map = {
            "listing_not_found": 404,
            "listing_not_ended": 400,
            "no_winner":         400,
            "not_authorized":    403,
        }
        raise HTTPException(
            status_code=code_map.get(result.get("error"), 400),
            detail=result,
        )
    return result


# Replace placeholder endpoints with versions that use Depends(get_user).

def _bind_routes():
    """Called by server after set_pickup_confirm_auth. Re-creates the
    three endpoints with a real `Depends(_get_user)` because we cannot
    capture `_get_user` at module-load time (it is injected at startup).
    """
    # Remove placeholder routes
    pickup_confirm_router.routes.clear()

    async def _do(listing_id: str, user: Dict[str, Any]):
        return await _shared_confirm_pickup(listing_id, user)

    @pickup_confirm_router.post("/listings/{listing_id}/confirm-pickup")
    async def _r1(listing_id: str, user: Dict[str, Any] = Depends(_get_user)):
        return await _do(listing_id, user)

    @pickup_confirm_router.post("/storage-auctions/{listing_id}/confirm-pickup")
    async def _r2(listing_id: str, user: Dict[str, Any] = Depends(_get_user)):
        return await _do(listing_id, user)

    @pickup_confirm_router.post("/vehicles/{listing_id}/confirm-pickup")
    async def _r3(listing_id: str, user: Dict[str, Any] = Depends(_get_user)):
        return await _do(listing_id, user)

    # iter297 — admin force-confirm endpoint
    @pickup_confirm_router.post("/admin/listings/{listing_id}/force-confirm-pickup")
    async def _r4(listing_id: str, user: Any = Depends(_get_user)):
        u = user if isinstance(user, dict) else user.model_dump()
        if u.get("role") not in ("admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Admin only")
        return await _do(listing_id, u)

    # iter297 — admin sweeps stuck transactions on demand.
    @pickup_confirm_router.post("/admin/flag-stuck-transactions")
    async def _r5(user: Any = Depends(_get_user)):
        u = user if isinstance(user, dict) else user.model_dump()
        if u.get("role") not in ("admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Admin only")
        return await flag_stuck_transactions(_db)


def set_pickup_confirm_auth_and_bind(get_user):
    """Convenience helper used by server.py — sets auth + binds routes
    in a single call so the route table reflects the real Depends()."""
    set_pickup_confirm_auth(get_user)
    _bind_routes()
