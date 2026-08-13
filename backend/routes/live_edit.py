"""
iter483 — Live Edit routes (seller + admin)

Thin route wrappers around ``services/live_edit_service.py``.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from services import live_edit_service as les
from services.live_edit_service import (
    AccessDenied, Conflict, InvalidField, LiveEditError, NotFoundError,
)


# ─── Router setup ────────────────────────────────────────────────────

seller_router = APIRouter(prefix="/api/auctions", tags=["seller-live-edit"])
admin_router  = APIRouter(prefix="/api/admin/end-time-requests",
                          tags=["admin-end-time-requests"])
security = HTTPBearer(auto_error=False)


# ─── DI ──────────────────────────────────────────────────────────────
_state: dict = {"db": None, "auth": None, "admin_auth": None}


def set_db(db):                     _state["db"]         = db
def set_auth(fn):                   _state["auth"]       = fn
def set_admin_auth(fn):             _state["admin_auth"] = fn


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
#  Seller endpoints
# ═════════════════════════════════════════════════════════════════════

class LiveEditRequest(BaseModel):
    field: str = Field(..., description="One of: title, description, images, schedule, pickup, shipping")
    value: Any = Field(..., description="New value for the field")


@seller_router.patch("/{auction_id}/live-edit")
async def live_edit(
    auction_id: str,
    body: LiveEditRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await les.live_edit(_db(), auction_id, user, body.field, body.value)
    except LiveEditError as e:
        raise _handle_err(e)


class AddLotRequest(BaseModel):
    lot: dict = Field(..., description="Lot payload (title, description, images, quantity, starting_price, category, condition, etc.)")


@seller_router.post("/{auction_id}/lots")
async def add_lot(
    auction_id: str,
    body: AddLotRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await les.add_lot(_db(), auction_id, user, body.lot)
    except LiveEditError as e:
        raise _handle_err(e)


class EndTimeRequest(BaseModel):
    requested_end_time: datetime = Field(...)
    reason: str = Field(..., min_length=1)


@seller_router.post("/{auction_id}/end-time-request")
async def create_end_time_request(
    auction_id: str,
    body: EndTimeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await les.create_end_time_request(
            _db(), auction_id, user, body.requested_end_time, body.reason)
    except LiveEditError as e:
        raise _handle_err(e)


@seller_router.get("/{auction_id}/end-time-request")
async def get_end_time_request(
    auction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await les.get_end_time_request(_db(), auction_id, user)
    except LiveEditError as e:
        raise _handle_err(e)


@seller_router.get("/{auction_id}/edited-history")
async def get_edited_history(
    auction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        rows = await les.get_edited_history(_db(), auction_id, user)
        return {"auction_id": auction_id, "history": rows}
    except LiveEditError as e:
        raise _handle_err(e)


# ═════════════════════════════════════════════════════════════════════
#  Admin endpoints
# ═════════════════════════════════════════════════════════════════════

class AdminNote(BaseModel):
    admin_note: Optional[str] = Field(None, max_length=2000)


@admin_router.post("/{request_id}/approve")
async def approve_request(
    request_id: str,
    body: AdminNote,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await les.approve_end_time_request(
            _db(), request_id, user, body.admin_note)
    except LiveEditError as e:
        raise _handle_err(e)


@admin_router.post("/{request_id}/deny")
async def deny_request(
    request_id: str,
    body: AdminNote,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return await les.deny_end_time_request(
            _db(), request_id, user, body.admin_note)
    except LiveEditError as e:
        raise _handle_err(e)


@admin_router.get("")
async def list_requests(
    status: Optional[str] = Query(None, pattern="^(pending|approved|denied)$"),
    limit: int = Query(200, ge=1, le=1000),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        rows = await les.list_end_time_requests(
            _db(), user, status=status, limit=limit)
        return {"count": len(rows), "rows": rows}
    except LiveEditError as e:
        raise _handle_err(e)


__all__ = ["seller_router", "admin_router", "set_db", "set_auth"]
