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

REQUEST_TYPES = {"end_time", "reserve_price", "edit", "reserve_not_met"}
STATUSES = {"pending", "approved", "denied"}

MIN_REASON_LENGTH = 20

# iter484 — System-generated request types skip seller-facing checks
# (ownership, reason min-length, active-status).
SYSTEM_GENERATED_TYPES = {"reserve_not_met"}


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


def _validate_reserve_not_met_payload(payload: dict) -> dict:
    """iter484 — System-generated payload written when settlement halts.

    Required keys:
        hammer_price   : float / int  (dollars)
        reserve_price  : float / int  (dollars)
        winner_user_id : str
    """
    if not isinstance(payload, dict):
        raise InvalidField("payload must be a dict")
    hp = payload.get("hammer_price")
    rp = payload.get("reserve_price")
    wu = payload.get("winner_user_id")
    if hp is None or rp is None:
        raise InvalidField("hammer_price and reserve_price are required")
    try:
        hp_f = float(hp)
        rp_f = float(rp)
    except (TypeError, ValueError):
        raise InvalidField("hammer_price and reserve_price must be numeric")
    if hp_f < 0 or rp_f < 0:
        raise InvalidField("prices must be >= 0")
    if not wu:
        raise InvalidField("winner_user_id is required")
    return {
        "hammer_price":   round(hp_f, 2),
        "reserve_price":  round(rp_f, 2),
        "winner_user_id": str(wu),
        # Optional passthrough fields.
        "lot_number":     payload.get("lot_number"),
        "collection":     payload.get("collection"),
        "currency":       payload.get("currency") or "CAD",
    }


PAYLOAD_VALIDATORS = {
    "end_time":         _validate_end_time_payload,
    "reserve_price":    _validate_reserve_payload,
    "edit":             _validate_edit_payload,
    "reserve_not_met":  _validate_reserve_not_met_payload,
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
# iter484 — System-generated request (reserve_not_met)
# ═════════════════════════════════════════════════════════════════════

async def create_system_reserve_not_met_request(
    db,
    auction_id: str,
    target: str,
    hammer_price: float,
    reserve_price: float,
    winner_user_id: str,
    seller_id: Optional[str] = None,
    lot_number: Any = None,
    collection: Optional[str] = None,
    currency: str = "CAD",
) -> dict:
    """Insert a ``reserve_not_met`` row into the unified auction_requests
    queue.  Idempotent — a pending row for the same (auction_id, target)
    returns the existing row instead of duplicating.

    Notes
    -----
    * Bypasses ownership checks (created by the settlement pipeline).
    * ``target`` is ``"auction"`` for single-listing flows or
      ``str(lot_number)`` for multi-lot flows.
    * The row is created without touching the caller's transaction —
      any DB error is swallowed so a bookkeeping failure never blocks
      the auction-close pipeline.
    """
    normalised_target = (target or "auction").strip() or "auction"
    payload = {
        "hammer_price":   round(float(hammer_price), 2),
        "reserve_price":  round(float(reserve_price), 2),
        "winner_user_id": winner_user_id,
        "lot_number":     lot_number,
        "collection":     collection,
        "currency":       currency,
    }
    validated = _validate_reserve_not_met_payload(payload)

    # Idempotency — pending row wins.
    existing = await db[COLLECTION].find_one(
        {
            "auction_id":   auction_id,
            "request_type": "reserve_not_met",
            "target":       normalised_target,
            "status":       "pending",
        },
        {"_id": 0},
    )
    if existing:
        return existing

    # Resolve auction_title + seller (best-effort).
    auction_title = ""
    _seller_id = seller_id
    try:
        _, doc = await resolve_auction(db, auction_id)
        auction_title = (doc.get("title") or "").strip()
        if not _seller_id:
            _seller_id = doc.get("seller_id")
    except Exception:
        pass

    row = {
        "id":            str(uuid.uuid4()),
        "auction_id":    auction_id,
        "auction_title": auction_title,
        "seller_id":     _seller_id,
        "request_type":  "reserve_not_met",
        "target":        normalised_target,
        "payload":       validated,
        "reason":        (
            f"System — reserve not met: hammer "
            f"${validated['hammer_price']:.2f} < reserve "
            f"${validated['reserve_price']:.2f}"
        ),
        "status":        "pending",
        "submitted_at":  _now_iso(),
        "submitted_by":  "system",
        "reviewed_at":   None,
        "reviewed_by":   None,
        "admin_note":    None,
    }
    try:
        await db[COLLECTION].insert_one(row)
    except Exception:
        return existing or row

    # Best-effort admin email — routed through the shared outbox so
    # dedupe keys prevent duplicate sends on scheduler retries.
    await _queue_email(
        db,
        kind="auction_request_submitted:reserve_not_met",
        dedupe_key=f"reserve_not_met_admin:{auction_id}:{normalised_target}",
        context={
            "request_id":    row["id"],
            "auction_id":    auction_id,
            "auction_title": auction_title,
            "target":        normalised_target,
            "payload":       validated,
            "reason":        row["reason"],
        },
    )

    # Neutral bilingual buyer email — "your bid is under review".
    if winner_user_id:
        await _queue_email(
            db,
            kind="reserve_not_met_buyer_under_review",
            dedupe_key=(
                f"reserve_not_met_buyer:{auction_id}:{normalised_target}:{winner_user_id}"
            ),
            context={
                "request_id":    row["id"],
                "auction_id":    auction_id,
                "auction_title": auction_title,
                "target":        normalised_target,
                # Deliberately DO NOT include reserve amount in the
                # buyer-facing context.
                "hammer_price":  validated["hammer_price"],
                "currency":      validated["currency"],
            },
            to_user_id=winner_user_id,
        )

    row.pop("_id", None)
    return row

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

    elif request_type == "reserve_not_met":
        # iter484 — Admin ACCEPTED the sale below reserve.  Re-run the
        # settlement pipeline with ``bypass_reserve=True`` so the buyer
        # is charged and the payout is queued exactly as if the reserve
        # had been met.  All bookkeeping / notifications / receipts
        # cascade from the standard settlement path.
        await _apply_reserve_not_met_approval(db, req, current_user)


async def _apply_reserve_not_met_approval(db, req: dict, current_user: Any) -> None:
    """iter484 — On admin approval of a ``reserve_not_met`` row, re-run
    the auction settlement with the reserve gate bypassed. Best-effort;
    any failure is logged and swallowed so the request row still
    resolves to ``approved`` in the queue."""
    import logging
    logger = logging.getLogger(__name__)

    auction_id = req.get("auction_id")
    payload = req.get("payload") or {}
    target = req.get("target") or "auction"
    hammer = payload.get("hammer_price")
    reserve = payload.get("reserve_price")
    winner_user_id = payload.get("winner_user_id")
    lot_number = payload.get("lot_number")
    if not auction_id or hammer is None or not winner_user_id:
        return

    try:
        collection, doc = await resolve_auction(db, auction_id)
    except Exception:
        return

    seller_id = doc.get("seller_id")
    if not seller_id:
        return

    # Flip status back to something the settlement code accepts.
    if target == "auction":
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {"status": "ended", "updated_at": _now_iso()}},
        )
    else:
        # Lot-level — flip that lot's status to "sold" so the settlement
        # path can pick it up.  Uses the same positional-op trick used
        # elsewhere in this service.
        try:
            _lot_num_int = int(lot_number)
        except (TypeError, ValueError):
            _lot_num_int = lot_number
        await db[collection].update_one(
            {"id": auction_id, "lots.lot_number": _lot_num_int},
            {"$set": {
                "lots.$.status": "sold",
                "lots.$.sold_at": _now_iso(),
                "lots.$.winner_user_id": winner_user_id,
                "lots.$.final_price": float(hammer),
            }},
        )

    # Audit log entry.
    try:
        from services.live_edit_service import _append_history, _make_history_entry
        await _append_history(
            db, collection, auction_id,
            _make_history_entry(
                "reserve_not_met_approved_by_admin",
                {"reserve_price": reserve},
                {"hammer_price": float(hammer),
                 "target": target,
                 "winner_user_id": winner_user_id},
                _user_id(current_user) or "admin",
                extra={
                    "request_id": req.get("id"),
                    "lot_number": lot_number,
                },
            ),
        )
    except Exception:
        pass

    # Re-run settlement with the reserve bypass.
    try:
        from services.auction_settlement import settle_auction
        from services.payment_collection import finalize_auction_payment

        # Reload the (possibly updated) auction/lot document.
        _, doc2 = await resolve_auction(db, auction_id)
        if target == "auction":
            settle_listing = {
                **doc2,
                "winner_id": winner_user_id,
                "seller_id": seller_id,
                "current_price": float(hammer),
                "final_price":   float(hammer),
                "payment_method": doc2.get("payment_method", "stripe"),
                "currency":       doc2.get("currency", payload.get("currency") or "CAD"),
            }
            settlement = await settle_auction(
                db,
                auction_id=auction_id,
                listing=settle_listing,
                bypass_reserve=True,
            )
            await finalize_auction_payment(
                db,
                listing={**settle_listing, "id": auction_id,
                         "winner_user_id": winner_user_id},
                collection=collection,
                settlement=settlement,
                section="marketplace",
            )
        else:
            from services.live_edit_service import _find_lot
            lot = _find_lot(doc2, target) or {}
            lot_title = f"{doc2.get('title', 'Auction')} — Lot #{lot.get('lot_number', target)}"
            _lot_synthetic = {
                "id":              f"{auction_id}:lot{lot.get('lot_number', target)}",
                "title":           lot_title,
                "winner_id":       winner_user_id,
                "seller_id":       seller_id,
                "final_price":     float(hammer),
                "current_price":   float(hammer),
                "payment_method":  doc2.get("payment_method", "stripe"),
                "currency":        doc2.get("currency", payload.get("currency") or "CAD"),
                "auction_end_date": doc2.get("auction_end_date"),
                "listing_type":    "lots",
            }
            settlement = await settle_auction(
                db,
                auction_id=_lot_synthetic["id"],
                listing=_lot_synthetic,
                bypass_reserve=True,
            )
            await finalize_auction_payment(
                db,
                listing={**_lot_synthetic, "id": auction_id,
                         "winner_user_id": winner_user_id},
                collection=collection,
                settlement=settlement,
                section="lots",
                lot_number=lot.get("lot_number"),
                listing_title=lot_title,
                hammer_override=float(hammer),
                winner_override=winner_user_id,
            )
    except Exception as e:  # noqa: BLE001
        logger.exception(
            f"[reserve_not_met_approve] settlement re-run failed for {auction_id}/{target}: {e}"
        )


async def _apply_denial_side_effects(db, req: dict, current_user: Any) -> None:
    """iter484 — On admin denial of a ``reserve_not_met`` row, mark the
    listing/lot as ``ended_reserve_not_met`` and record the audit trail.
    No financial actions.  Non-``reserve_not_met`` denials fall through
    with no side effects (their default lifecycle is enough)."""
    if req.get("request_type") != "reserve_not_met":
        return

    auction_id = req.get("auction_id")
    target = req.get("target") or "auction"
    payload = req.get("payload") or {}
    if not auction_id:
        return

    try:
        collection, doc = await resolve_auction(db, auction_id)
    except Exception:
        return

    if target == "auction":
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {
                "status": "ended_reserve_not_met",
                "end_reason": "reserve_not_met",
                "updated_at": _now_iso(),
            }},
        )
    else:
        try:
            _lot_num_int = int(payload.get("lot_number") or target)
        except (TypeError, ValueError):
            _lot_num_int = payload.get("lot_number") or target
        await db[collection].update_one(
            {"id": auction_id, "lots.lot_number": _lot_num_int},
            {"$set": {
                "lots.$.status": "ended_reserve_not_met",
                "lots.$.end_reason": "reserve_not_met",
            }},
        )

    try:
        from services.live_edit_service import _append_history, _make_history_entry
        await _append_history(
            db, collection, auction_id,
            _make_history_entry(
                "reserve_not_met_denied_by_admin",
                {"reserve_price": payload.get("reserve_price")},
                {"hammer_price": payload.get("hammer_price"),
                 "target": target,
                 "winner_user_id": payload.get("winner_user_id")},
                _user_id(current_user) or "admin",
                extra={"request_id": req.get("id"),
                       "lot_number": payload.get("lot_number")},
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
    elif new_status == "denied":
        await _apply_denial_side_effects(db, resolved, current_user)

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
    "COLLECTION", "REQUEST_TYPES", "STATUSES", "SYSTEM_GENERATED_TYPES",
    "create_request",
    "create_system_reserve_not_met_request",
    "list_requests_for_seller", "list_requests_admin",
    "approve_request", "deny_request",
    "admin_set_reserve_price",
]
