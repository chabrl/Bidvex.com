"""
iter483.3 — Auction Requests Service (unified)
=============================================

Consolidates the previous end-time-only workflow into a single
"Auction Request" surface supporting three request types:

  * end_time      — seller asks to move the auction's end_time
  * reserve_price — seller asks for a reserve price on a lot / auction
                    (admin still SETs the actual price manually — this
                    approval is only the "go-ahead" signal)
  * edit          — seller asks to change a locked field (title,
                    description, schedule, pickup, shipping) once the
                    auction has bids

Persistence: ``auction_requests`` collection (new).  The legacy
``auction_end_time_requests`` collection is bridged in ``list_requests``
so pre-iter483.3 rows continue to appear in the admin queue.

Every request follows the same lifecycle:
    pending  →  (approved | denied)
Approving an ``end_time`` request updates the auction's end_time.
Approving an ``edit`` request applies the requested_new_value to the
matching field via ``live_edit_service.live_edit`` (admin bypass).
Approving a ``reserve_price`` request just records the ACK — admins
apply the actual price via their own admin panel.

All lifecycle events queue a bilingual email through the existing
``email_outbox`` bridge (see live_edit_service._queue_email).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from services.live_edit_service import (
    AccessDenied, Conflict, InvalidField, NotFoundError, LiveEditError,
    resolve_auction, _is_admin, _user_id, _now_iso, _queue_email,
    live_edit, AUCTION_BID_LOCKED_FIELDS,
)


COLLECTION = "auction_requests"
LEGACY_END_TIME_COLLECTION = "auction_end_time_requests"

REQUEST_TYPES = {"end_time", "reserve_price", "edit"}
STATUSES = {"pending", "approved", "denied"}

MIN_REASON_LENGTH = 20


# ═════════════════════════════════════════════════════════════════════
# Payload validators (per request type)
# ═════════════════════════════════════════════════════════════════════

def _validate_end_time_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise InvalidField("payload must be a dict")
    ret_iso = payload.get("requested_end_time")
    if not ret_iso:
        raise InvalidField("requested_end_time is required")
    if isinstance(ret_iso, datetime):
        ret_dt = ret_iso if ret_iso.tzinfo else ret_iso.replace(tzinfo=timezone.utc)
    else:
        try:
            ret_dt = datetime.fromisoformat(str(ret_iso).replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidField(f"requested_end_time not ISO-8601: {exc}")
        if ret_dt.tzinfo is None:
            ret_dt = ret_dt.replace(tzinfo=timezone.utc)
    if ret_dt <= datetime.now(timezone.utc):
        raise InvalidField("requested_end_time must be in the future")
    return {"requested_end_time": ret_dt.isoformat()}


def _validate_reserve_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise InvalidField("payload must be a dict")
    price = payload.get("requested_reserve_price")
    if price is None:
        raise InvalidField("requested_reserve_price is required")
    try:
        v = float(price)
    except (TypeError, ValueError):
        raise InvalidField("requested_reserve_price must be numeric")
    if v < 0:
        raise InvalidField("requested_reserve_price must be >= 0")
    return {"requested_reserve_price": round(v, 2)}


ALLOWED_EDIT_FIELDS = sorted(AUCTION_BID_LOCKED_FIELDS)  # title, description, schedule, pickup, shipping


def _validate_edit_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise InvalidField("payload must be a dict")
    field_name = payload.get("field_name")
    new_value = payload.get("requested_new_value")
    if field_name not in AUCTION_BID_LOCKED_FIELDS:
        raise InvalidField(
            f"field_name must be one of {ALLOWED_EDIT_FIELDS}")
    if new_value is None:
        raise InvalidField("requested_new_value is required")
    return {"field_name": field_name, "requested_new_value": new_value}


PAYLOAD_VALIDATORS = {
    "end_time":      _validate_end_time_payload,
    "reserve_price": _validate_reserve_payload,
    "edit":          _validate_edit_payload,
}


# ═════════════════════════════════════════════════════════════════════
# Create
# ═════════════════════════════════════════════════════════════════════

async def create_request(
    db,
    auction_id: str,
    current_user: Any,
    request_type: str,
    target: str,
    payload: dict,
    reason: str,
) -> dict:
    """Create a new auction request (any type).

    ``target``: ``"auction"`` for auction-level requests, or the lot_id
    / str(lot_number) for lot-level ones.
    """
    if request_type not in REQUEST_TYPES:
        raise InvalidField(
            f"request_type must be one of {sorted(REQUEST_TYPES)}")
    if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON_LENGTH:
        raise InvalidField(
            f"reason must be at least {MIN_REASON_LENGTH} characters")

    collection, doc = await resolve_auction(db, auction_id)

    # Ownership: only the seller of an active auction (or an admin) can
    # submit.  The live_edit_service helper does the same checks.
    if not _is_admin(current_user):
        if doc.get("seller_id") != _user_id(current_user):
            raise AccessDenied("You are not the owner of this auction")
        status = (doc.get("status") or "").lower()
        if status not in {"active", "live"}:
            raise InvalidField(
                f"Auction status {status!r} does not accept requests")

    normalised_target = (target or "auction").strip() or "auction"

    # Payload validation (type-specific)
    validator = PAYLOAD_VALIDATORS[request_type]
    validated_payload = validator(payload or {})

    # Duplicate-pending guard
    existing = await db[COLLECTION].find_one(
        {
            "auction_id":   auction_id,
            "request_type": request_type,
            "target":       normalised_target,
            "status":       "pending",
        },
        {"_id": 0, "id": 1},
    )
    if existing:
        raise Conflict(
            f"A pending {request_type} request already exists for this "
            f"auction/target — request_id={existing.get('id')}")

    seller_id = doc.get("seller_id")
    row = {
        "id":            str(uuid.uuid4()),
        "auction_id":    auction_id,
        "auction_title": doc.get("title") or "",
        "seller_id":     seller_id,
        "request_type":  request_type,
        "target":        normalised_target,
        "payload":       validated_payload,
        "reason":        reason.strip(),
        "status":        "pending",
        "submitted_at":  _now_iso(),
        "submitted_by":  _user_id(current_user) or seller_id,
        "reviewed_at":   None,
        "reviewed_by":   None,
        "admin_note":    None,
    }
    await db[COLLECTION].insert_one(row)

    # Best-effort email to sellers admin roster
    await _queue_email(
        db,
        kind=f"auction_request_submitted:{request_type}",
        dedupe_key=f"req_submit:{row['id']}",
        context={
            "request_id":    row["id"],
            "auction_id":    auction_id,
            "auction_title": row["auction_title"],
            "request_type":  request_type,
            "target":        normalised_target,
            "payload":       validated_payload,
            "reason":        row["reason"],
        },
    )

    row.pop("_id", None)
    return row


# ═════════════════════════════════════════════════════════════════════
# List
# ═════════════════════════════════════════════════════════════════════

async def _hydrate_row(db, row: dict) -> dict:
    """Attach seller_email + auction_title if missing (best-effort)."""
    row = {k: v for k, v in row.items() if k != "_id"}
    seller_id = row.get("seller_id")
    if seller_id and "seller_email" not in row:
        try:
            u = await db.users.find_one(
                {"id": seller_id}, {"_id": 0, "email": 1, "name": 1})
            if u:
                row["seller_email"] = u.get("email")
                row["seller_name"] = u.get("name")
        except Exception:
            pass
    return row


async def _bridge_legacy_end_time_rows(db, filter_q: dict) -> list[dict]:
    """Yield legacy end-time-only rows in the unified shape so the admin
    queue never loses pre-iter483.3 requests."""
    try:
        cursor = db[LEGACY_END_TIME_COLLECTION].find({}, {"_id": 0})
        legacy = await cursor.to_list(length=500)
    except Exception:
        return []

    bridged: list[dict] = []
    for r in legacy:
        row = {
            "id":            r.get("id") or str(uuid.uuid4()),
            "auction_id":    r.get("auction_id"),
            "auction_title": r.get("auction_title") or "",
            "seller_id":     r.get("seller_id"),
            "request_type":  "end_time",
            "target":        "auction",
            "payload": {
                "requested_end_time": r.get("requested_end_time"),
                "current_end_time":   r.get("current_end_time"),
            },
            "reason":       r.get("reason") or "",
            "status":       r.get("status") or "pending",
            "submitted_at": r.get("submitted_at") or r.get("created_at"),
            "reviewed_at":  r.get("reviewed_at"),
            "reviewed_by":  r.get("reviewed_by"),
            "admin_note":   r.get("admin_note"),
            "_legacy":      True,
        }
        # Apply filter
        keep = True
        for k, v in filter_q.items():
            if v is None: continue
            if row.get(k) != v:
                keep = False
                break
        if keep:
            bridged.append(row)
    return bridged


async def list_requests_for_seller(
    db, auction_id: str, current_user: Any,
    status: Optional[str] = None,
) -> list[dict]:
    """Seller reads their own requests for a given auction."""
    _, doc = await resolve_auction(db, auction_id)
    if not _is_admin(current_user):
        if doc.get("seller_id") != _user_id(current_user):
            raise AccessDenied("You are not the owner of this auction")

    q: dict = {"auction_id": auction_id}
    if status:
        q["status"] = status

    cursor = db[COLLECTION].find(q, {"_id": 0}).sort("submitted_at", -1)
    rows = await cursor.to_list(length=500)
    rows = [await _hydrate_row(db, r) for r in rows]

    # Bridge legacy end-time rows for this auction
    legacy = await _bridge_legacy_end_time_rows(
        db, {"auction_id": auction_id, "status": status})
    rows.extend([await _hydrate_row(db, r) for r in legacy])

    return rows


async def list_requests_admin(
    db,
    current_user: Any,
    status: Optional[str] = "pending",
    request_type: Optional[str] = None,
    auction_id: Optional[str] = None,
    seller_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Admin reads the unified queue."""
    if not _is_admin(current_user):
        raise AccessDenied("Admins only")

    q: dict = {}
    if status:        q["status"] = status
    if request_type:  q["request_type"] = request_type
    if auction_id:    q["auction_id"] = auction_id
    if seller_id:     q["seller_id"] = seller_id

    cursor = db[COLLECTION].find(q, {"_id": 0}).sort("submitted_at", -1).limit(limit)
    rows = await cursor.to_list(length=limit)
    rows = [await _hydrate_row(db, r) for r in rows]

    # Legacy bridge — only when request_type filter is missing OR ==end_time
    if not request_type or request_type == "end_time":
        legacy = await _bridge_legacy_end_time_rows(
            db, {"status": status, "auction_id": auction_id,
                 "seller_id": seller_id})
        rows.extend([await _hydrate_row(db, r) for r in legacy])

    return rows


# ═════════════════════════════════════════════════════════════════════
# Approve / Deny
# ═════════════════════════════════════════════════════════════════════

async def _load_request(db, request_id: str) -> dict:
    row = await db[COLLECTION].find_one({"id": request_id}, {"_id": 0})
    if row:
        return row
    # Legacy bridge fallback
    legacy = await db[LEGACY_END_TIME_COLLECTION].find_one(
        {"id": request_id}, {"_id": 0})
    if legacy:
        return {
            "id":            legacy.get("id"),
            "auction_id":    legacy.get("auction_id"),
            "auction_title": legacy.get("auction_title") or "",
            "seller_id":     legacy.get("seller_id"),
            "request_type":  "end_time",
            "target":        "auction",
            "payload": {
                "requested_end_time": legacy.get("requested_end_time"),
                "current_end_time":   legacy.get("current_end_time"),
            },
            "reason":       legacy.get("reason") or "",
            "status":       legacy.get("status") or "pending",
            "submitted_at": legacy.get("submitted_at"),
            "reviewed_at":  legacy.get("reviewed_at"),
            "reviewed_by":  legacy.get("reviewed_by"),
            "admin_note":   legacy.get("admin_note"),
            "_legacy":      True,
        }
    raise NotFoundError(f"Request {request_id!r} not found")


async def _apply_approval_side_effects(db, req: dict, current_user: Any) -> None:
    """Runs after status flips to 'approved'.  Per type behavior."""
    request_type = req.get("request_type")
    auction_id = req.get("auction_id")
    payload = req.get("payload") or {}
    if not auction_id:
        return

    if request_type == "end_time":
        # Update the auction's end_time to the requested value.
        collection, doc = await resolve_auction(db, auction_id)
        new_end = payload.get("requested_end_time")
        if isinstance(new_end, datetime):
            new_end = new_end.isoformat()
        if not new_end:
            return
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {
                "end_time":         new_end,
                "auction_end_date": new_end,
                # iter483.3 — reset soft-close if the auction uses it
                "soft_close_extended_at": None,
                "updated_at":       _now_iso(),
            }},
        )
        # Append audit entry
        try:
            from services.live_edit_service import _append_history, _make_history_entry
            await _append_history(
                db, collection, auction_id,
                _make_history_entry(
                    "end_time",
                    doc.get("end_time") or doc.get("auction_end_date"),
                    new_end,
                    _user_id(current_user) or "admin",
                    extra={"request_id": req.get("id")},
                ),
            )
        except Exception:
            pass

    elif request_type == "edit":
        # Apply the requested change through the live_edit service —
        # admin bypasses the bid-lock in live_edit.
        field_name = payload.get("field_name")
        new_value = payload.get("requested_new_value")
        try:
            await live_edit(db, auction_id, current_user, field_name, new_value)
        except LiveEditError:
            # Never fail the approval itself; the admin can retry.
            pass

    elif request_type == "reserve_price":
        # This is an ACK only — admins set the actual price manually
        # through the admin lot editor's Reserve Price field. No auction
        # mutation here beyond the audit trail.
        try:
            from services.live_edit_service import _append_history, _make_history_entry
            collection, _ = await resolve_auction(db, auction_id)
            await _append_history(
                db, collection, auction_id,
                _make_history_entry(
                    "reserve_price_requested_ack",
                    None,
                    {"target": req.get("target"),
                     "requested_reserve_price": payload.get("requested_reserve_price")},
                    _user_id(current_user) or "admin",
                    extra={"request_id": req.get("id")},
                ),
            )
        except Exception:
            pass


async def _decide(
    db, request_id: str, current_user: Any,
    action: str, admin_note: Optional[str],
) -> dict:
    if not _is_admin(current_user):
        raise AccessDenied("Admins only")
    if action not in {"approve", "deny"}:
        raise InvalidField("action must be 'approve' or 'deny'")

    req = await _load_request(db, request_id)
    if req.get("status") != "pending":
        raise Conflict(f"Request already resolved (status={req.get('status')!r})")

    new_status = "approved" if action == "approve" else "denied"
    reviewer = _user_id(current_user) or "admin"
    reviewed_at = _now_iso()

    if req.get("_legacy"):
        # Legacy row — update in the old collection so historical writes
        # remain observable in that store, but ALSO copy into the new
        # collection so future admin panels see everything in one place.
        await db[LEGACY_END_TIME_COLLECTION].update_one(
            {"id": request_id},
            {"$set": {
                "status":      new_status,
                "reviewed_at": reviewed_at,
                "reviewed_by": reviewer,
                "admin_note":  admin_note,
            }},
        )
        # Mirror
        mirror = {k: v for k, v in req.items() if k != "_legacy"}
        mirror.update({
            "status":      new_status,
            "reviewed_at": reviewed_at,
            "reviewed_by": reviewer,
            "admin_note":  admin_note,
        })
        await db[COLLECTION].update_one(
            {"id": request_id}, {"$set": mirror}, upsert=True)
    else:
        await db[COLLECTION].update_one(
            {"id": request_id},
            {"$set": {
                "status":      new_status,
                "reviewed_at": reviewed_at,
                "reviewed_by": reviewer,
                "admin_note":  admin_note,
            }},
        )

    # Re-load the resolved row
    resolved = await _load_request(db, request_id)

    if new_status == "approved":
        await _apply_approval_side_effects(db, resolved, current_user)

    await _queue_email(
        db,
        kind=f"auction_request_{new_status}:{req.get('request_type')}",
        dedupe_key=f"req_decide:{request_id}:{new_status}",
        context={
            "request_id":    request_id,
            "auction_id":    req.get("auction_id"),
            "auction_title": req.get("auction_title"),
            "request_type":  req.get("request_type"),
            "target":        req.get("target"),
            "status":        new_status,
            "admin_note":    admin_note,
        },
        to_user_id=req.get("seller_id"),
    )

    return resolved


async def approve_request(db, request_id: str, current_user: Any,
                          admin_note: Optional[str] = None) -> dict:
    return await _decide(db, request_id, current_user, "approve", admin_note)


async def deny_request(db, request_id: str, current_user: Any,
                       admin_note: Optional[str] = None) -> dict:
    return await _decide(db, request_id, current_user, "deny", admin_note)


# ═════════════════════════════════════════════════════════════════════
# Reserve price — admin-only field mutation (per lot or auction)
# ═════════════════════════════════════════════════════════════════════

async def admin_set_reserve_price(
    db,
    auction_id: str,
    target: str,           # "auction" or lot_id/lot_number
    reserve_price_cents: Optional[int],
    current_user: Any,
) -> dict:
    """Admin sets/clears a reserve price on a lot (or the auction).

    ``reserve_price_cents``: pass ``None`` to CLEAR the reserve price.
    """
    if not _is_admin(current_user):
        raise AccessDenied("Admins only")

    if reserve_price_cents is not None:
        try:
            cents = int(reserve_price_cents)
        except (TypeError, ValueError):
            raise InvalidField("reserve_price_cents must be integer or null")
        if cents < 0:
            raise InvalidField("reserve_price_cents must be >= 0")
        reserve = round(cents / 100, 2)
    else:
        reserve = None

    collection, doc = await resolve_auction(db, auction_id)
    editor = _user_id(current_user) or "admin"

    from services.live_edit_service import _find_lot, _append_history, _make_history_entry

    if target in {None, "auction", ""}:
        old = doc.get("reserve_price")
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {"reserve_price": reserve, "updated_at": _now_iso()}},
        )
        await _append_history(
            db, collection, auction_id,
            _make_history_entry(
                "reserve_price", old, reserve, editor,
                extra={"target": "auction"},
            ),
        )
        return {"success": True, "auction_id": auction_id,
                "target": "auction", "reserve_price": reserve}

    lot = _find_lot(doc, target)
    if lot is None:
        raise NotFoundError(f"Lot {target!r} not found")
    old = lot.get("reserve_price")

    lot_number = lot.get("lot_number")
    lot_id = lot.get("id")
    filter_q: dict = {"id": auction_id}
    if lot_id is not None:
        filter_q["lots.id"] = lot_id
    else:
        filter_q["lots.lot_number"] = lot_number

    await db[collection].update_one(
        filter_q,
        {"$set": {"lots.$.reserve_price": reserve,
                  "updated_at": _now_iso()}},
    )
    await _append_history(
        db, collection, auction_id,
        _make_history_entry(
            "reserve_price", old, reserve, editor,
            extra={"target": target,
                   "lot_number": lot_number,
                   "lot_id": lot_id},
        ),
    )
    return {"success": True, "auction_id": auction_id,
            "target": target, "lot_number": lot_number,
            "reserve_price": reserve}


__all__ = [
    "COLLECTION", "REQUEST_TYPES", "STATUSES",
    "create_request",
    "list_requests_for_seller", "list_requests_admin",
    "approve_request", "deny_request",
    "admin_set_reserve_price",
]
