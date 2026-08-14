"""
iter483.3 — Unified Auction Requests API
=========================================

Endpoints:

  Seller
    POST   /api/auctions/{auction_id}/requests
    GET    /api/auctions/{auction_id}/requests

  Admin
    GET    /api/admin/auction-requests
    POST   /api/admin/auction-requests/{request_id}/approve
    POST   /api/admin/auction-requests/{request_id}/deny
    PATCH  /api/admin/lots/reserve-price
"""
from __future__ import annotations
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from services import auction_requests_service as ars
from services.live_edit_service import LiveEditError


seller_router = APIRouter(prefix="/api/auctions",
                          tags=["seller-auction-requests"])
admin_router  = APIRouter(prefix="/api/admin/auction-requests",
                          tags=["admin-auction-requests"])
admin_reserve_router = APIRouter(prefix="/api/admin",
                                 tags=["admin-reserve-price"])
security = HTTPBearer(auto_error=False)


_state: dict = {"db": None, "auth": None}


def set_db(db):   _state["db"]   = db
def set_auth(fn): _state["auth"] = fn


def _db():
    return _state["db"]


async def _current_user(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Any:
    if credentials is None or _state["auth"] is None:
        return None
    try:
        return await _state["auth"](credentials)
    except HTTPException:
        return None
    except Exception:
        return None


def _handle_err(exc: LiveEditError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.reason)


# ═════════════════════════════════════════════════════════════════════
#  Schemas
# ═════════════════════════════════════════════════════════════════════

class CreateRequestBody(BaseModel):
    request_type: str = Field(..., description="end_time | reserve_price | edit")
    target:       str = Field("auction", description="'auction' or lot_id/lot_number")
    payload:      dict = Field(..., description="Type-specific fields")
    reason:       str = Field(..., min_length=1)


class AdminNote(BaseModel):
    admin_note: Optional[str] = Field(None, max_length=2000)


class ReservePriceBody(BaseModel):
    auction_id:          str
    target:              str = "auction"
    reserve_price_cents: Optional[int] = None


# ═════════════════════════════════════════════════════════════════════
#  Seller endpoints
# ═════════════════════════════════════════════════════════════════════

@seller_router.post("/{auction_id}/requests")
async def submit_request(
    auction_id: str,
    body: CreateRequestBody,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await ars.create_request(
            _db(), auction_id, user,
            request_type=body.request_type,
            target=body.target,
            payload=body.payload,
            reason=body.reason,
        )
    except LiveEditError as e:
        raise _handle_err(e)


@seller_router.get("/{auction_id}/requests")
async def list_own_requests(
    auction_id: str,
    status: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        rows = await ars.list_requests_for_seller(
            _db(), auction_id, user, status=status)
        return {"auction_id": auction_id, "rows": rows}
    except LiveEditError as e:
        raise _handle_err(e)


# ═════════════════════════════════════════════════════════════════════
#  Admin endpoints
# ═════════════════════════════════════════════════════════════════════

@admin_router.get("")
async def admin_list_requests(
    status: Optional[str] = Query("pending"),
    request_type: Optional[str] = Query(None),
    auction_id: Optional[str] = Query(None),
    seller_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        rows = await ars.list_requests_admin(
            _db(), user,
            status=status, request_type=request_type,
            auction_id=auction_id, seller_id=seller_id,
            limit=limit)
        return {"rows": rows, "count": len(rows)}
    except LiveEditError as e:
        raise _handle_err(e)


@admin_router.post("/{request_id}/approve")
async def admin_approve_request(
    request_id: str,
    body: AdminNote,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await ars.approve_request(_db(), request_id, user, body.admin_note)
    except LiveEditError as e:
        raise _handle_err(e)


@admin_router.post("/{request_id}/deny")
async def admin_deny_request(
    request_id: str,
    body: AdminNote,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await ars.deny_request(_db(), request_id, user, body.admin_note)
    except LiveEditError as e:
        raise _handle_err(e)


# ═════════════════════════════════════════════════════════════════════
#  Admin — Reserve price setter (admin-only)
# ═════════════════════════════════════════════════════════════════════

@admin_reserve_router.patch("/lots/reserve-price")
async def admin_set_reserve_price(
    body: ReservePriceBody,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await ars.admin_set_reserve_price(
            _db(),
            auction_id=body.auction_id,
            target=body.target,
            reserve_price_cents=body.reserve_price_cents,
            current_user=user,
        )
    except LiveEditError as e:
        raise _handle_err(e)


__all__ = ["seller_router", "admin_router", "admin_reserve_router",
           "set_db", "set_auth"]
