"""
iter500 — Accept Below Reserve

Adds a seller-facing (and admin) endpoint that lets the auction owner
accept the offered hammer price when the reserve was not met.

Reuses the existing settle_auction ``bypass_reserve`` path via
``auction_requests_service._apply_reserve_not_met_approval`` so the
buyer is charged and the payout row is created exactly as the admin
approval flow does today. Zero changes to fee, settlement, tax, or
Stripe code.

Endpoints:
    GET  /api/auctions/{auction_id}/reserve-not-met-eligibility
    POST /api/auctions/{auction_id}/accept-below-reserve
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from services import auction_requests_service as ars
from services.live_edit_service import (
    resolve_auction,
    _is_admin,
    _user_id,
    _now_iso,
    LiveEditError,
    AccessDenied,
    NotFoundError,
)


router = APIRouter(prefix="/api/auctions", tags=["accept-below-reserve"])
security = HTTPBearer(auto_error=False)


_state: dict = {"db": None, "auth": None}


def set_db(db):
    _state["db"] = db


def set_auth(fn):
    _state["auth"] = fn


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


# ═════════════════════════════════════════════════════════════════════
#  Schemas
# ═════════════════════════════════════════════════════════════════════

class AcceptBody(BaseModel):
    lot_number: Optional[int] = None


# ═════════════════════════════════════════════════════════════════════
#  Helpers
# ═════════════════════════════════════════════════════════════════════

def _find_lot(doc: dict, lot_number: Any) -> Optional[dict]:
    lots = doc.get("lots") or []
    try:
        ln = int(lot_number)
    except (TypeError, ValueError):
        ln = lot_number
    for lot in lots:
        if lot.get("lot_number") == ln or str(lot.get("lot_number")) == str(ln):
            return lot
    return None


def _extract_context(doc: dict, lot_number: Optional[int]) -> dict:
    """Return the (status, sold_quantity, winner_user_id, hammer_price,
    reserve_price, item_name, lot_number, target, currency) for either
    the top-level listing or a specific lot."""
    if lot_number is not None:
        lot = _find_lot(doc, lot_number)
        if not lot:
            raise NotFoundError(f"Lot #{lot_number} not found")
        winner_user_id = (
            lot.get("winner_user_id")
            or lot.get("winner_id")
            or lot.get("highest_bidder_id")
        )
        hammer = (
            lot.get("final_price")
            or lot.get("current_price")
            or lot.get("highest_bid")
        )
        return {
            "target": str(lot.get("lot_number")),
            "status": (lot.get("status") or "").lower(),
            "sold_quantity": int(lot.get("sold_quantity") or 0),
            "winner_user_id": winner_user_id,
            "hammer_price": float(hammer) if hammer is not None else None,
            "reserve_price": lot.get("reserve_price"),
            "item_name": lot.get("title") or doc.get("title"),
            "lot_number": lot.get("lot_number"),
            "currency": doc.get("currency", "CAD"),
        }
    winner_user_id = (
        doc.get("winner_user_id")
        or doc.get("winner_id")
        or doc.get("highest_bidder_id")
    )
    hammer = (
        doc.get("final_price")
        or doc.get("current_price")
        or doc.get("highest_bid")
    )
    return {
        "target": "auction",
        "status": (doc.get("status") or "").lower(),
        "sold_quantity": int(doc.get("sold_quantity") or 0),
        "winner_user_id": winner_user_id,
        "hammer_price": float(hammer) if hammer is not None else None,
        "reserve_price": doc.get("reserve_price"),
        "item_name": doc.get("title"),
        "lot_number": None,
        "currency": doc.get("currency", "CAD"),
    }


async def _has_saved_payment_method(db, user_id: str) -> bool:
    """True iff the given user has any saved payment method row with a
    stripe_payment_method_id. Matches the check used by
    ``bid_authorization_service._get_default_payment_method``."""
    if not user_id:
        return False
    pm = await db.payment_methods.find_one(
        {"user_id": user_id},
        {"_id": 0, "stripe_payment_method_id": 1},
    )
    return bool(pm and pm.get("stripe_payment_method_id"))


async def _get_buyer_display(db, user_id: str) -> str:
    if not user_id:
        return ""
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "name": 1, "email": 1})
    if not u:
        return ""
    return (u.get("name") or u.get("email") or "").strip()


def _authorize(doc: dict, user: Any) -> None:
    if user is None:
        raise AccessDenied("Authentication required")
    if _is_admin(user):
        return
    if doc.get("seller_id") != _user_id(user):
        raise AccessDenied("You are not the owner of this auction")


# ═════════════════════════════════════════════════════════════════════
#  Endpoints
# ═════════════════════════════════════════════════════════════════════

@router.get("/{auction_id}/reserve-not-met-eligibility")
async def get_eligibility(
    auction_id: str,
    lot_number: Optional[int] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Returns whether the Accept-Below-Reserve action is available for
    this listing/lot. Cheap read used to hydrate the button."""
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = _db()
    try:
        collection, doc = await resolve_auction(db, auction_id)
    except LiveEditError as e:
        raise HTTPException(status_code=e.status, detail=e.reason)

    try:
        _authorize(doc, user)
    except LiveEditError as e:
        raise HTTPException(status_code=e.status, detail=e.reason)

    try:
        ctx = _extract_context(doc, lot_number)
    except LiveEditError as e:
        raise HTTPException(status_code=e.status, detail=e.reason)

    has_pm = await _has_saved_payment_method(db, ctx["winner_user_id"] or "")
    buyer_name = await _get_buyer_display(db, ctx["winner_user_id"] or "")

    eligible = (
        ctx["status"] == "reserve_not_met"
        and ctx["sold_quantity"] == 0
        and bool(ctx["winner_user_id"])
        and ctx["hammer_price"] is not None
        and float(ctx["hammer_price"]) > 0
        and has_pm
    )

    reason = None
    if not eligible:
        if ctx["status"] != "reserve_not_met":
            reason = "status_not_reserve_not_met"
        elif ctx["sold_quantity"] > 0:
            reason = "already_sold"
        elif not ctx["winner_user_id"]:
            reason = "no_winning_bid"
        elif not has_pm:
            reason = "no_saved_payment_method"
        else:
            reason = "not_eligible"

    return {
        "eligible": eligible,
        "reason": reason,
        "lot_number": ctx["lot_number"],
        "item_name": ctx["item_name"],
        "hammer_price": ctx["hammer_price"],
        "buyer_name": buyer_name,
        "buyer_user_id": ctx["winner_user_id"],
        "currency": ctx["currency"],
        "has_saved_payment_method": has_pm,
    }


@router.post("/{auction_id}/accept-below-reserve")
async def accept_below_reserve(
    auction_id: str,
    body: AcceptBody,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Reuse the existing bypass_reserve settlement path to charge the
    buyer at the offered hammer price. Only callable when
    status=reserve_not_met, sold_quantity=0, and the winning bidder has
    a saved payment method on file."""
    user = await _current_user(credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = _db()
    try:
        collection, doc = await resolve_auction(db, auction_id)
    except LiveEditError as e:
        raise HTTPException(status_code=e.status, detail=e.reason)

    try:
        _authorize(doc, user)
    except LiveEditError as e:
        raise HTTPException(status_code=e.status, detail=e.reason)

    try:
        ctx = _extract_context(doc, body.lot_number)
    except LiveEditError as e:
        raise HTTPException(status_code=e.status, detail=e.reason)

    if ctx["status"] != "reserve_not_met":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "STATUS_NOT_RESERVE_NOT_MET",
                "message": (
                    f"This listing/lot is not in 'reserve_not_met' "
                    f"status (current: {ctx['status'] or 'unknown'})."
                ),
            },
        )
    if ctx["sold_quantity"] > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "ALREADY_SOLD",
                "message": "This lot has already been sold.",
            },
        )
    if not ctx["winner_user_id"] or ctx["hammer_price"] is None or float(ctx["hammer_price"]) <= 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "NO_WINNING_BID",
                "message": "No valid winning bid was recorded for this lot.",
            },
        )

    has_pm = await _has_saved_payment_method(db, ctx["winner_user_id"])
    if not has_pm:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "NO_SAVED_PAYMENT_METHOD",
                "message": (
                    "The winning bidder does not have a saved payment "
                    "method on file. They must add a card before the "
                    "sale can be finalised."
                ),
            },
        )

    # Locate the pending reserve_not_met request row that the settlement
    # pipeline creates when a lot ends below reserve. If, for any reason,
    # it is missing (out-of-order delivery, back-filled data), we
    # synthesize the row before approving so the standard downstream
    # side-effects still fire.
    request_row = await db[ars.COLLECTION].find_one(
        {
            "auction_id": auction_id,
            "request_type": "reserve_not_met",
            "target": ctx["target"],
            "status": "pending",
        },
        {"_id": 0},
    )
    if not request_row:
        try:
            request_row = await ars.create_system_reserve_not_met_request(
                db,
                auction_id=auction_id,
                target=ctx["target"],
                hammer_price=float(ctx["hammer_price"]),
                reserve_price=float(ctx["reserve_price"] or 0),
                winner_user_id=ctx["winner_user_id"],
                seller_id=doc.get("seller_id"),
                lot_number=ctx["lot_number"],
                collection=collection,
                currency=ctx["currency"],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "REQUEST_ROW_CREATE_FAILED",
                    "message": f"Could not create reserve_not_met request row: {e}",
                },
            )

    # Flip the request row to approved *before* invoking the side-effect
    # so the standard email + audit trail runs. Reuses the same fields
    # the admin approve endpoint would set.
    reviewer = _user_id(user) or ("admin" if _is_admin(user) else "seller")
    await db[ars.COLLECTION].update_one(
        {"id": request_row["id"]},
        {"$set": {
            "status": "approved",
            "reviewed_at": _now_iso(),
            "reviewed_by": reviewer,
            "admin_note": (
                "Accepted below reserve via seller dashboard"
                if not _is_admin(user)
                else "Accepted below reserve via admin panel"
            ),
        }},
    )

    # Reload resolved row and invoke the shared side-effect that
    # re-runs settle_auction(bypass_reserve=True) + finalize_auction_payment.
    resolved = await db[ars.COLLECTION].find_one(
        {"id": request_row["id"]}, {"_id": 0}
    )
    try:
        await ars._apply_reserve_not_met_approval(db, resolved, user)
    except Exception as e:
        # Roll the request row back to pending so a retry stays possible.
        await db[ars.COLLECTION].update_one(
            {"id": request_row["id"]},
            {"$set": {
                "status": "pending",
                "reviewed_at": None,
                "reviewed_by": None,
                "admin_note": None,
            }},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "SETTLEMENT_FAILED",
                "message": f"Settlement re-run failed: {e}",
            },
        )

    # Reload the (possibly-updated) auction/lot to report back the new
    # status the client should render immediately.
    _, doc_after = await resolve_auction(db, auction_id)
    ctx_after = _extract_context(doc_after, body.lot_number)
    return {
        "success": True,
        "request_id": request_row["id"],
        "auction_id": auction_id,
        "lot_number": ctx["lot_number"],
        "hammer_price": ctx["hammer_price"],
        "buyer_user_id": ctx["winner_user_id"],
        "status_after": ctx_after["status"],
    }


__all__ = ["router", "set_db", "set_auth"]
