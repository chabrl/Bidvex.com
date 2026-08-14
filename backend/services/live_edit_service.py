"""
iter483 — Seller Live Auction Edit Service
==========================================

Canonical single-entry-point for the "limited-edit" capabilities on
active auctions.  Read-only for financial state; mutates only
non-financial fields.

Collections supported (searched in order — first hit wins):

    listings, multi_item_listings, vehicle_listings,
    vehicle_multi_lot_listings, storage_auctions, partner_auctions

Permitted edit fields (per iter483 spec):

    title, description
    images                         (add / remove-own / replace)
    schedule                       (preview / open-house)
    pickup                         (location, window, instructions)
    shipping                       (available / notes / estimate_cost)
    lot_added                      (append new lot, status=draft →
                                    pending_admin_review)

End-time is handled through a formal *request* workflow that requires
admin approval — see :func:`create_end_time_request` /
:func:`approve_end_time_request` / :func:`deny_end_time_request`.

Every mutation appends an entry to ``edited_history`` on the auction
document.  The log is append-only.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional


# ═════════════════════════════════════════════════════════════════════
#  Constants
# ═════════════════════════════════════════════════════════════════════

# Order matters — first collection with a matching `id` wins.
AUCTION_COLLECTIONS: list[str] = [
    "listings",
    "multi_item_listings",
    "vehicle_listings",
    "vehicle_multi_lot_listings",
    "storage_auctions",
    "partner_auctions",
]

ACTIVE_STATUSES: set[str] = {"active", "live"}

# Non-active statuses where seller edits MUST be rejected.
REJECT_STATUSES: set[str] = {
    "draft", "closed", "cancelled", "pending_admin_review",
    "settled", "ended", "completed", "archived", "rejected", "paused",
}

PERMITTED_FIELDS: set[str] = {
    "title", "description",
    "images",
    "schedule", "pickup", "shipping",
    # iter483.3 — Per-lot image add/remove (multi-lot auctions only)
    "lot_image_add", "lot_image_remove",
}

# iter483.3 — Fields that become locked at the auction level once
# ANY bid has been placed on ANY lot of the auction. Sellers must
# route requests through the Request Center for these instead.
AUCTION_BID_LOCKED_FIELDS: set[str] = {
    "title", "description", "schedule", "pickup", "shipping",
}

MIN_REASON_LENGTH = 20


# ═════════════════════════════════════════════════════════════════════
#  Exceptions
# ═════════════════════════════════════════════════════════════════════

class LiveEditError(Exception):
    """Base error for the live-edit service."""

    def __init__(self, reason: str, status: int = 400):
        super().__init__(reason)
        self.reason = reason
        self.status = status


class NotFoundError(LiveEditError):
    def __init__(self, msg: str = "Auction not found"):
        super().__init__(msg, status=404)


class AccessDenied(LiveEditError):
    def __init__(self, msg: str):
        super().__init__(msg, status=403)


class InvalidField(LiveEditError):
    def __init__(self, msg: str):
        super().__init__(msg, status=400)


class Conflict(LiveEditError):
    def __init__(self, msg: str):
        super().__init__(msg, status=409)


# ═════════════════════════════════════════════════════════════════════
#  Auction resolution + permission
# ═════════════════════════════════════════════════════════════════════

async def resolve_auction(db, auction_id: str) -> tuple[str, dict]:
    """Return (collection_name, doc) or raise NotFoundError."""
    if not auction_id:
        raise NotFoundError()
    for coll in AUCTION_COLLECTIONS:
        try:
            doc = await db[coll].find_one({"id": auction_id}, {"_id": 0})
        except Exception:
            doc = None
        if doc:
            return coll, doc
    raise NotFoundError()


def _is_admin(user: Any) -> bool:
    if user is None:
        return False
    if isinstance(user, dict):
        role = (user.get("role") or "").lower()
        return role in ("admin", "super_admin") or bool(user.get("is_admin"))
    role = getattr(user, "role", None)
    return bool(role and str(role).lower() in ("admin", "super_admin"))


def _user_id(user: Any) -> Optional[str]:
    if user is None:
        return None
    if isinstance(user, dict):
        return user.get("id")
    return getattr(user, "id", None)


def _user_email(user: Any) -> Optional[str]:
    if user is None:
        return None
    if isinstance(user, dict):
        return user.get("email")
    return getattr(user, "email", None)


def _require_seller_of_active(doc: dict, user: Any) -> None:
    """Enforce seller-owner-only on active auctions.  Admin bypass."""
    if _is_admin(user):
        return
    if user is None:
        raise AccessDenied("Authentication required")
    if doc.get("seller_id") != _user_id(user):
        raise AccessDenied("You are not the owner of this auction")
    status = (doc.get("status") or "").lower()
    if status not in ACTIVE_STATUSES:
        raise AccessDenied(
            f"Live edits are only permitted while the auction is active "
            f"(current status: {status or 'unknown'})"
        )


# ═════════════════════════════════════════════════════════════════════
#  edited_history helpers
# ═════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_history_entry(
    field: str,
    old_value: Any,
    new_value: Any,
    edited_by: str,
    extra: Optional[dict] = None,
) -> dict:
    entry = {
        "id":         str(uuid.uuid4()),
        "field":      field,
        "old_value":  old_value,
        "new_value":  new_value,
        "edited_by":  edited_by,
        "edited_at":  _now_iso(),
    }
    if extra:
        entry.update(extra)
    return entry


async def _append_history(
    db, collection: str, auction_id: str, entry: dict,
) -> None:
    await db[collection].update_one(
        {"id": auction_id},
        {"$push": {"edited_history": entry}},
    )


# ═════════════════════════════════════════════════════════════════════
# iter483.3 — Bid-count helpers (lot-level + auction-level lock)
# ═════════════════════════════════════════════════════════════════════

async def _auction_bid_count(db, collection: str, doc: dict) -> int:
    """Return total bids across all lots (or the auction itself).

    Reads from three sources — first non-zero wins:
      1) top-level ``bid_count`` field (fastest path if kept in sync)
      2) sum of ``lots[].bid_count``
      3) live count from ``db.bids`` collection (listing_id match)
    """
    top = doc.get("bid_count")
    if isinstance(top, (int, float)) and top > 0:
        return int(top)
    lots = doc.get("lots") or []
    if lots:
        total = sum(int(l.get("bid_count") or 0) for l in lots if isinstance(l, dict))
        if total > 0:
            return total
    try:
        return await db.bids.count_documents({"listing_id": doc.get("id")})
    except Exception:
        return 0


async def _lot_bid_count(db, doc: dict, lot: dict) -> int:
    """Bids received by a single lot within a multi-lot auction."""
    v = lot.get("bid_count")
    if isinstance(v, (int, float)) and v > 0:
        return int(v)
    try:
        return await db.bids.count_documents({
            "listing_id": doc.get("id"),
            "lot_number": lot.get("lot_number"),
        })
    except Exception:
        return 0


def _find_lot(doc: dict, lot_ref: Any) -> Optional[dict]:
    """Resolve a lot by id OR lot_number within an auction doc."""
    for lot in doc.get("lots") or []:
        if not isinstance(lot, dict):
            continue
        if lot.get("id") == lot_ref:
            return lot
        try:
            if int(lot.get("lot_number")) == int(lot_ref):
                return lot
        except (TypeError, ValueError):
            continue
    return None


# ═════════════════════════════════════════════════════════════════════
#  Live-edit main entry point
# ═════════════════════════════════════════════════════════════════════

async def live_edit(
    db,
    auction_id: str,
    current_user: Any,
    field: str,
    value: Any,
) -> dict:
    """Apply a permitted non-financial edit to an active auction.

    Parameters
    ----------
    db            : Motor DB.
    auction_id    : Auction UUID.
    current_user  : Authenticated user (dict or Pydantic).
    field         : One of ``PERMITTED_FIELDS``.
    value         : New value.  For ``images`` value is a dict:
                    ``{"add": [url, ...], "remove": [url, ...]}``.

    Returns
    -------
    dict  ``{"success": True, "auction_id": ..., "field": ..., "new_value": ...}``

    Raises
    ------
    NotFoundError, AccessDenied, InvalidField
    """
    if field not in PERMITTED_FIELDS:
        raise InvalidField(
            f"Field {field!r} is not permitted for live edit "
            f"(allowed: {sorted(PERMITTED_FIELDS)})"
        )

    collection, doc = await resolve_auction(db, auction_id)
    _require_seller_of_active(doc, current_user)

    editor = _user_id(current_user) or "unknown"

    # ── iter483.3 · Auction-level bid lock ─────────────────────────
    # Once ANY bid has been placed on the auction (single-lot or any
    # lot of a multi-lot), the seller can NO LONGER directly edit the
    # locked fields — they must submit an edit request via the Request
    # Center.  Admins bypass this rule.  Auction-level images remain
    # editable so sellers can still swap the hero photo etc.  Per-lot
    # edits (lot_image_add / lot_image_remove) are gated separately
    # in their handlers below.
    if (
        field in AUCTION_BID_LOCKED_FIELDS
        and not _is_admin(current_user)
    ):
        bid_count = await _auction_bid_count(db, collection, doc)
        if bid_count > 0:
            raise AccessDenied(
                "auction_has_bids — use request flow "
                f"(field={field!r}, bids={bid_count})"
            )

    # ── title / description ─────────────────────────────────────────
    if field == "title":
        v = str(value or "").strip()
        if not v:
            raise InvalidField("Title must not be empty")
        if len(v) > 300:
            raise InvalidField("Title too long (max 300 chars)")
        old = doc.get("title")
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {"title": v, "updated_at": _now_iso()}},
        )
        await _append_history(
            db, collection, auction_id,
            _make_history_entry("title", old, v, editor),
        )
        return {"success": True, "auction_id": auction_id, "field": "title",
                "new_value": v}

    if field == "description":
        v = str(value or "")
        if len(v) > 20_000:
            raise InvalidField("Description too long (max 20 000 chars)")
        old = doc.get("description")
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {"description": v, "updated_at": _now_iso()}},
        )
        await _append_history(
            db, collection, auction_id,
            _make_history_entry("description", old, v, editor),
        )
        return {"success": True, "auction_id": auction_id,
                "field": "description", "new_value": v}

    # ── images ──────────────────────────────────────────────────────
    if field == "images":
        if not isinstance(value, dict):
            raise InvalidField("images payload must be a dict with add/remove/reorder keys")
        current_imgs: list = list(doc.get("images") or doc.get("photos") or [])
        image_field = "images" if "images" in doc else "photos"
        if image_field not in doc:
            image_field = "images"
        add_urls  = value.get("add") or []
        remove_urls = value.get("remove") or []
        reorder   = value.get("reorder")
        # normalise entries to plain strings
        def _url(x):
            return x if isinstance(x, str) else (x.get("url") if isinstance(x, dict) else None)

        old_urls = [_url(x) for x in current_imgs if _url(x)]

        if reorder and isinstance(reorder, list):
            # Only accept URLs that already exist — no injection.
            new_urls = [u for u in reorder if u in old_urls]
        else:
            new_urls = list(old_urls)

        for u in remove_urls:
            if u in new_urls:
                # Admin-added images cannot be removed by seller — we key on
                # a companion `image_meta` collection when it exists.
                is_admin_added = await _is_admin_added_image(
                    db, auction_id, u)
                if is_admin_added and not _is_admin(current_user):
                    raise AccessDenied(
                        f"Cannot remove image {u!r} — added by admin")
                new_urls.remove(u)
        for u in add_urls:
            if u and u not in new_urls:
                new_urls.append(u)

        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {image_field: new_urls, "updated_at": _now_iso()}},
        )
        await _append_history(
            db, collection, auction_id,
            _make_history_entry("images", old_urls, new_urls, editor),
        )
        return {"success": True, "auction_id": auction_id,
                "field": "images", "new_value": new_urls}

    # ── schedule / pickup / shipping ───────────────────────────────
    # All three are stored as nested dicts on the doc.  We upsert
    # top-level keys under a mnemonic parent key.
    if field == "schedule":
        allowed = {"preview_date", "preview_time", "open_house_date",
                   "open_house_time", "location", "notes"}
        v = _coerce_dict_subset(value, allowed)
        old = doc.get("schedule")
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {"schedule": v, "updated_at": _now_iso()}},
        )
        await _append_history(db, collection, auction_id,
            _make_history_entry("schedule", old, v, editor))
        return {"success": True, "auction_id": auction_id,
                "field": "schedule", "new_value": v}

    if field == "pickup":
        allowed = {"location", "window_start", "window_end", "instructions"}
        v = _coerce_dict_subset(value, allowed)
        old = doc.get("pickup")
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {"pickup": v, "updated_at": _now_iso()}},
        )
        await _append_history(db, collection, auction_id,
            _make_history_entry("pickup", old, v, editor))
        return {"success": True, "auction_id": auction_id,
                "field": "pickup", "new_value": v}

    if field == "shipping":
        allowed = {"available", "notes", "estimated_cost", "carrier"}
        v = _coerce_dict_subset(value, allowed)
        # Estimated cost is display-only; guard it as string label.
        if "estimated_cost" in v and v["estimated_cost"] is not None:
            v["estimated_cost"] = str(v["estimated_cost"])
        v["is_estimate_only"] = True   # explicit flag — never a Stripe charge
        old = doc.get("shipping")
        await db[collection].update_one(
            {"id": auction_id},
            {"$set": {"shipping": v, "updated_at": _now_iso()}},
        )
        await _append_history(db, collection, auction_id,
            _make_history_entry("shipping", old, v, editor))
        return {"success": True, "auction_id": auction_id,
                "field": "shipping", "new_value": v}

    # ── iter483.3 · Per-lot images (multi-lot auctions only) ───────
    if field in {"lot_image_add", "lot_image_remove"}:
        if not isinstance(value, dict):
            raise InvalidField(
                f"{field} payload must be a dict with lot_id + image_url")
        lot_ref = value.get("lot_id") or value.get("lot_number")
        image_url = value.get("image_url") or value.get("url")
        if not lot_ref:
            raise InvalidField("lot_id (or lot_number) is required")
        if not image_url or not isinstance(image_url, str):
            raise InvalidField("image_url must be a non-empty string")

        lots = list(doc.get("lots") or [])
        if not lots:
            raise InvalidField(
                "Per-lot images are only supported on multi-lot auctions")

        target = _find_lot(doc, lot_ref)
        if target is None:
            raise NotFoundError(f"Lot {lot_ref!r} not found in auction")

        # Bid-lock: a lot that has received bids is fully locked for
        # seller editing (admins bypass).
        if not _is_admin(current_user):
            lot_bids = await _lot_bid_count(db, doc, target)
            if lot_bids > 0:
                raise AccessDenied(
                    f"lot_has_bids — lot={target.get('lot_number')} "
                    f"bids={lot_bids}")

        lot_imgs = list(target.get("images") or [])
        old_imgs = list(lot_imgs)

        if field == "lot_image_add":
            if image_url not in lot_imgs:
                lot_imgs.append(image_url)
        else:  # lot_image_remove
            lot_imgs = [u for u in lot_imgs if u != image_url]

        # Positional update on the matched lot.
        # We match by lot_number (stable) OR by embedded id.
        lot_number = target.get("lot_number")
        lot_id = target.get("id")
        filter_q: dict = {"id": auction_id}
        arr_filter: dict
        if lot_id is not None:
            filter_q["lots.id"] = lot_id
            arr_filter = {"lots.$.images": lot_imgs}
        else:
            filter_q["lots.lot_number"] = lot_number
            arr_filter = {"lots.$.images": lot_imgs}

        await db[collection].update_one(
            filter_q,
            {"$set": {**arr_filter, "updated_at": _now_iso()}},
        )
        await _append_history(
            db, collection, auction_id,
            _make_history_entry(field, old_imgs, lot_imgs, editor,
                                extra={"lot_number": lot_number,
                                       "lot_id": lot_id,
                                       "image_url": image_url}),
        )
        return {"success": True, "auction_id": auction_id, "field": field,
                "lot_number": lot_number, "lot_id": lot_id,
                "new_value": lot_imgs}

    raise InvalidField(f"Unhandled field {field!r}")


def _coerce_dict_subset(value: Any, allowed: set[str]) -> dict:
    if not isinstance(value, dict):
        raise InvalidField("Value must be a dict")
    return {k: v for k, v in value.items() if k in allowed}


async def _is_admin_added_image(db, auction_id: str, url: str) -> bool:
    """Best-effort check against a companion `image_meta` collection."""
    try:
        rec = await db.image_meta.find_one(
            {"auction_id": auction_id, "url": url},
            {"_id": 0, "added_by_role": 1},
        )
        if not rec:
            return False
        return (rec.get("added_by_role") or "").lower() in ("admin", "super_admin")
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════════════
#  Add-lot (multi-lot auctions only)
# ═════════════════════════════════════════════════════════════════════

async def add_lot(
    db,
    auction_id: str,
    current_user: Any,
    lot_data: dict,
) -> dict:
    """Append a new lot to an active multi-lot auction.

    New lot enters as ``status='draft'`` and ``moderation_status
    ='pending_admin_review'``.  Existing lots + bids are UNTOUCHED.
    """
    if not isinstance(lot_data, dict):
        raise InvalidField("lot_data must be a dict")

    collection, doc = await resolve_auction(db, auction_id)
    _require_seller_of_active(doc, current_user)

    if "lots" not in doc and doc.get("lots") is None:
        # Single-lot collections can't accept new lots.
        if collection in {"listings", "storage_auctions"}:
            raise InvalidField(
                f"Add-lot is not supported for {collection!r} auctions")

    editor = _user_id(current_user) or "unknown"

    existing_lots = list(doc.get("lots") or [])
    next_lot_number = 1
    if existing_lots:
        nums = []
        for lot in existing_lots:
            n = lot.get("lot_number") if isinstance(lot, dict) else None
            try:
                nums.append(int(n))
            except (TypeError, ValueError):
                pass
        if nums:
            next_lot_number = max(nums) + 1

    # Sanitize incoming keys — never accept price/bid mutation.
    banned = {"current_price", "current_bid", "highest_bidder_id",
              "winner_user_id", "winning_bidder_id", "final_price",
              "hammer_price", "sold_at", "payment_status", "bid_count"}
    new_lot = {k: v for k, v in lot_data.items() if k not in banned}
    new_lot["id"] = new_lot.get("id") or str(uuid.uuid4())
    new_lot["lot_number"] = new_lot.get("lot_number") or next_lot_number
    new_lot["status"] = "draft"
    new_lot["moderation_status"] = "pending_admin_review"
    new_lot["created_at"] = _now_iso()
    new_lot["created_by"] = editor
    new_lot["current_price"] = new_lot.get("current_price",
                                            new_lot.get("starting_price", 0))
    # sensible defaults
    new_lot.setdefault("quantity", 1)
    new_lot.setdefault("condition", "unknown")
    new_lot.setdefault("category", "other")
    new_lot.setdefault("images", [])

    await db[collection].update_one(
        {"id": auction_id},
        {"$push": {"lots": new_lot},
         "$set":  {"updated_at": _now_iso()}},
    )
    await _append_history(
        db, collection, auction_id,
        _make_history_entry("lot_added", None, {
            "lot_number": new_lot["lot_number"],
            "title":      new_lot.get("title"),
        }, editor),
    )
    return {"success": True, "auction_id": auction_id, "lot": new_lot}


# ═════════════════════════════════════════════════════════════════════
#  End-time change request workflow
# ═════════════════════════════════════════════════════════════════════

REQUEST_COLLECTION = "auction_end_time_requests"


async def create_end_time_request(
    db,
    auction_id: str,
    current_user: Any,
    requested_end_time: datetime,
    reason: str,
) -> dict:
    """Create a pending end-time change request.  Only ONE pending
    request allowed per auction — returns 409 if one exists."""
    collection, doc = await resolve_auction(db, auction_id)
    _require_seller_of_active(doc, current_user)

    if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON_LENGTH:
        raise InvalidField(
            f"Reason must be at least {MIN_REASON_LENGTH} characters")

    if not isinstance(requested_end_time, datetime):
        raise InvalidField("requested_end_time must be a datetime")

    req_end = requested_end_time
    if req_end.tzinfo is None:
        req_end = req_end.replace(tzinfo=timezone.utc)
    if req_end <= datetime.now(timezone.utc):
        raise InvalidField("requested_end_time must be in the future")

    # Enforce single-pending
    existing = await db[REQUEST_COLLECTION].find_one({
        "auction_id": auction_id,
        "status": "pending",
    }, {"_id": 0})
    if existing:
        raise Conflict("A pending end-time change request already exists")

    current_end = doc.get("auction_end_date") or doc.get("end_time")
    if isinstance(current_end, datetime):
        current_end = current_end.isoformat()

    row = {
        "id":                    str(uuid.uuid4()),
        "auction_id":            auction_id,
        "auction_collection":   collection,
        "auction_title":        doc.get("title") or doc.get("title_en") or "",
        "seller_id":             _user_id(current_user),
        "seller_email":          _user_email(current_user),
        "current_end_time":      current_end,
        "requested_end_time":    req_end.isoformat(),
        "reason":                reason.strip(),
        "status":                "pending",
        "submitted_at":          _now_iso(),
        "reviewed_at":           None,
        "reviewed_by":           None,
        "admin_note":            None,
    }
    # Motor's insert_one mutates the row to include an ObjectId `_id`
    # which is not JSON-serialisable.  Store the ObjectId-free copy
    # for downstream callers.
    to_persist = dict(row)
    await db[REQUEST_COLLECTION].insert_one(to_persist)

    # Queue admin alert email (idempotent via `dedupe_key`)
    await _queue_email(
        db,
        kind="end_time_request_submitted_admin",
        dedupe_key=f"etr_admin_{row['id']}",
        context={
            "request_id":         row["id"],
            "auction_id":         auction_id,
            "auction_title":      row["auction_title"],
            "seller_email":       row["seller_email"] or "",
            "current_end_time":   row["current_end_time"] or "",
            "requested_end_time": row["requested_end_time"],
            "reason":             row["reason"],
        },
    )
    return {k: v for k, v in row.items()}


async def get_end_time_request(
    db, auction_id: str, current_user: Any,
) -> Optional[dict]:
    """Return the CURRENT pending (or most recent) request for the
    auction, or None."""
    _coll, doc = await resolve_auction(db, auction_id)
    # Seller can only see their own auction's request
    if not _is_admin(current_user):
        if doc.get("seller_id") != _user_id(current_user):
            raise AccessDenied("You are not the owner of this auction")

    row = await db[REQUEST_COLLECTION].find_one(
        {"auction_id": auction_id, "status": "pending"}, {"_id": 0})
    if row:
        return row
    # Fall through to the most-recent-non-pending
    cursor = db[REQUEST_COLLECTION].find(
        {"auction_id": auction_id}, {"_id": 0}
    ).sort("submitted_at", -1).limit(1)
    docs = await cursor.to_list(length=1)
    return docs[0] if docs else None


async def approve_end_time_request(
    db, request_id: str, admin_user: Any, admin_note: Optional[str] = None,
) -> dict:
    """Approve a pending request → update the auction end time and
    email the seller.  Idempotent — returns 409 if already resolved."""
    if not _is_admin(admin_user):
        raise AccessDenied("Admin access required")

    req = await db[REQUEST_COLLECTION].find_one(
        {"id": request_id}, {"_id": 0})
    if not req:
        raise NotFoundError("Request not found")
    if req.get("status") != "pending":
        raise Conflict(f"Request already {req.get('status')}")

    collection = req["auction_collection"]
    auction_id = req["auction_id"]

    # Update auction end time (both field names — matches admin_end_time.py).
    new_end_iso = req["requested_end_time"]
    await db[collection].update_one(
        {"id": auction_id},
        {"$set": {
            "auction_end_date":        new_end_iso,
            "end_time":                new_end_iso,
            "end_time_last_edited_by": _user_email(admin_user),
            "end_time_last_edited_at": _now_iso(),
            "updated_at":              _now_iso(),
        }},
    )
    # Reset soft-close snipe protection window bookkeeping — the existing
    # engine reads from auction_end_date on each tick, so no explicit reset
    # is required.  We flag it so downstream consumers know we changed it.
    await db[collection].update_one(
        {"id": auction_id},
        {"$set": {"soft_close_reset_by_request_id": request_id}},
    )

    # Mark request resolved
    await db[REQUEST_COLLECTION].update_one(
        {"id": request_id},
        {"$set": {
            "status":       "approved",
            "reviewed_at":  _now_iso(),
            "reviewed_by":  _user_email(admin_user),
            "admin_note":   (admin_note or "").strip() or None,
        }},
    )
    # Append audit
    await _append_history(
        db, collection, auction_id,
        _make_history_entry(
            "end_time",
            req.get("current_end_time"),
            new_end_iso,
            f"admin:{_user_email(admin_user)}"),
    )
    # Queue seller confirmation email (idempotent)
    await _queue_email(
        db,
        kind="end_time_request_approved_seller",
        dedupe_key=f"etr_approved_{request_id}",
        to_user_id=req.get("seller_id"),
        context={
            "auction_id":     auction_id,
            "auction_title":  req.get("auction_title", ""),
            "new_end_time":   new_end_iso,
            "admin_note":     admin_note or "",
        },
    )
    return {"success": True, "status": "approved",
            "request_id": request_id, "new_end_time": new_end_iso}


async def deny_end_time_request(
    db, request_id: str, admin_user: Any, admin_note: Optional[str] = None,
) -> dict:
    """Deny a pending request.  End time unchanged.  Email the seller."""
    if not _is_admin(admin_user):
        raise AccessDenied("Admin access required")

    req = await db[REQUEST_COLLECTION].find_one(
        {"id": request_id}, {"_id": 0})
    if not req:
        raise NotFoundError("Request not found")
    if req.get("status") != "pending":
        raise Conflict(f"Request already {req.get('status')}")

    await db[REQUEST_COLLECTION].update_one(
        {"id": request_id},
        {"$set": {
            "status":       "denied",
            "reviewed_at":  _now_iso(),
            "reviewed_by":  _user_email(admin_user),
            "admin_note":   (admin_note or "").strip() or None,
        }},
    )
    await _queue_email(
        db,
        kind="end_time_request_denied_seller",
        dedupe_key=f"etr_denied_{request_id}",
        to_user_id=req.get("seller_id"),
        context={
            "auction_id":     req["auction_id"],
            "auction_title":  req.get("auction_title", ""),
            "current_end_time": req.get("current_end_time") or "",
            "admin_note":     admin_note or "",
        },
    )
    return {"success": True, "status": "denied", "request_id": request_id}


async def list_end_time_requests(
    db, admin_user: Any, status: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    if not _is_admin(admin_user):
        raise AccessDenied("Admin access required")
    q: dict = {}
    if status:
        q["status"] = status
    cursor = db[REQUEST_COLLECTION].find(q, {"_id": 0}) \
        .sort("submitted_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


# ═════════════════════════════════════════════════════════════════════
#  edited_history reader
# ═════════════════════════════════════════════════════════════════════

async def get_edited_history(
    db, auction_id: str, current_user: Any,
) -> list[dict]:
    coll, doc = await resolve_auction(db, auction_id)
    if not _is_admin(current_user):
        if doc.get("seller_id") != _user_id(current_user):
            raise AccessDenied("You are not the owner of this auction")
    return list(doc.get("edited_history") or [])


# ═════════════════════════════════════════════════════════════════════
#  Editable field snapshot — iter483.2 (Description Refresh)
# ═════════════════════════════════════════════════════════════════════

async def get_edit_state(
    db, auction_id: str, current_user: Any,
) -> dict:
    """Return the current DB values of every editable field so the modal
    can render the true saved state on re-open (no stale placeholders).

    iter483.3 additions: `bid_count` (auction-level lock signal), plus
    per-lot `bid_count` inside each lot summary so the UI can render
    lock badges + disable inputs on locked lots.
    """
    coll, doc = await resolve_auction(db, auction_id)
    if not _is_admin(current_user):
        if doc.get("seller_id") != _user_id(current_user):
            raise AccessDenied("You are not the owner of this auction")

    # Roll up bid counts
    auction_bids = await _auction_bid_count(db, coll, doc)
    lots_summary = []
    for lot in (doc.get("lots") or []):
        if not isinstance(lot, dict):
            continue
        bc = await _lot_bid_count(db, doc, lot)
        lots_summary.append({
            "id":              lot.get("id"),
            "lot_number":      lot.get("lot_number"),
            "title":           lot.get("title") or "",
            "description":     lot.get("description") or "",
            "quantity":        lot.get("quantity"),
            "starting_price":  lot.get("starting_price"),
            "reserve_price":   lot.get("reserve_price"),   # may be None
            "current_price":   lot.get("current_price"),
            "status":          lot.get("status"),
            "images":          list(lot.get("images") or []),
            "bid_count":       bc,
            "locked":          bc > 0,
        })

    return {
        "auction_id":  auction_id,
        "collection":  coll,
        "title":       doc.get("title") or "",
        "description": doc.get("description") or "",
        "images":      list(doc.get("images") or doc.get("photos") or []),
        "schedule":    dict(doc.get("schedule") or {}),
        "pickup":      dict(doc.get("pickup") or {}),
        "shipping":    dict(doc.get("shipping") or {}),
        "status":      doc.get("status"),
        "end_time":    doc.get("end_time") or doc.get("auction_end_date"),
        # iter483.3 lock signals
        "bid_count":            auction_bids,
        "auction_locked":       auction_bids > 0,
        "locked_fields":        (
            sorted(AUCTION_BID_LOCKED_FIELDS) if auction_bids > 0 else []
        ),
        "lots":                 lots_summary,
    }


# ═════════════════════════════════════════════════════════════════════
#  Email queue helper — idempotent via dedupe_key.
# ═════════════════════════════════════════════════════════════════════

async def _queue_email(
    db,
    kind: str,
    dedupe_key: str,
    context: dict,
    to_user_id: Optional[str] = None,
) -> None:
    """Insert an email_outbox row keyed on ``dedupe_key`` so that a
    retry does not queue a second copy."""
    try:
        existing = await db.email_outbox.find_one(
            {"dedupe_key": dedupe_key}, {"_id": 0, "id": 1})
        if existing:
            return
        await db.email_outbox.insert_one({
            "id":         str(uuid.uuid4()),
            "kind":       kind,
            "dedupe_key": dedupe_key,
            "to_user_id": to_user_id,
            "context":    context,
            "queued_at":  datetime.now(timezone.utc),
        })
    except Exception:
        # Never fail the caller because of an email hiccup.
        pass


__all__ = [
    "AUCTION_COLLECTIONS", "PERMITTED_FIELDS", "MIN_REASON_LENGTH",
    "REQUEST_COLLECTION",
    "LiveEditError", "NotFoundError", "AccessDenied", "InvalidField",
    "Conflict",
    "resolve_auction", "live_edit", "add_lot",
    "create_end_time_request", "get_end_time_request",
    "approve_end_time_request", "deny_end_time_request",
    "list_end_time_requests",
    "get_edited_history",
    "get_edit_state",
]
