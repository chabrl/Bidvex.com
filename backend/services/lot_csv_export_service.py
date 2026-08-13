"""
iter482+ — Canonical Lot CSV Export Service
===========================================

**Single source of truth** for exporting lot data across every BidVex
auction type.  Callers MUST route all CSV exports through:

    lot_csv_export_service.generate_csv(
        db,
        auction_id,
        surface,       # 'seller' | 'public' | 'admin'
        current_user,  # None for public
    )

which returns a ``(filename, csv_bytes)`` tuple.  Bytes are UTF-8 with
a BOM so Excel opens them without corrupting French accents.

Design principles
-----------------
* **Read-only.**  Never mutates any collection.  Never touches payment
  / tax / fee / settlement logic.
* **Canonical column order** (approved by product owner):

      auction_id, auction_name, lot_number, title, description,
      quantity, starting_bid, category, condition, current_bid,
      status, listing_url, image_urls

* **Field normalisation** — every auction type maps its schema onto
  the canonical column set so a single downstream CSV works.
* **Access control lives here.**  Routes are thin.  ``surface`` is the
  only field that determines redaction rules.
* **Surface-specific redaction**

    ``public``    — the 13 canonical columns.  Never emits any of the
                    forbidden fields (seller_id / seller_email /
                    seller_phone / winner_user_id / hammer_price /
                    reserve_price / internal_notes / moderation_status
                    / payment / invoices / commission).
    ``seller``    — the 13 canonical columns.  Same non-sensitive set;
                    ownership is enforced at the route layer.
    ``admin``     — the 13 canonical columns **plus** four additional
                    admin-only columns: ``winner_user_id``,
                    ``hammer_price``, ``sold_at``, ``seller_id``.
                    Per spec: “No additional internal fields.”

* **Status filter (default 5a)** — draft lots are hidden by default.
  Callers may pass ``include_drafts=True`` (only meaningful for
  ``seller`` / ``admin`` surfaces).

Auction-type coverage
---------------------
============================  =============================  ==========
Collection                    Shape                          Auction type
============================  =============================  ==========
``listings``                  1 doc == 1 lot                 general
``multi_item_listings``       1 doc, ``lots[]`` array        multi_item
``vehicle_listings``          1 doc, ``lots[]`` array        vehicle
``vehicle_multi_lot_listings``1 doc, ``lots[]`` array        vehicle_multi_lot
``storage_auctions``          1 doc == 1 lot                 storage
``partner_auctions``          1 doc, ``lots[]`` array        partner
============================  =============================  ==========

Additional auction types can be onboarded by extending
``_AUCTION_COLLECTIONS`` and — if the schema differs — adding a
``_normalize_*_lot`` helper.
"""

from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional


# ═════════════════════════════════════════════════════════════════════
#  Public API
# ═════════════════════════════════════════════════════════════════════

CANONICAL_COLUMNS: list[str] = [
    "auction_id",
    "auction_name",
    "lot_number",
    "title",
    "description",
    "quantity",
    "starting_bid",
    "category",
    "condition",
    "current_bid",
    "status",
    "listing_url",
    "image_urls",
]

ADMIN_EXTRA_COLUMNS: list[str] = [
    # Per spec: admin surface may additionally expose ONLY these.
    "winner_user_id",
    "hammer_price",
    "sold_at",
    "seller_id",
]

_HIDDEN_STATUSES_BY_DEFAULT: set[str] = {"draft", "pending_review", "deleted"}

_VALID_SURFACES: set[str] = {"seller", "public", "admin"}


@dataclass(frozen=True)
class ExportResolution:
    """The result of resolving an auction_id to a concrete document."""

    auction_type: str          # "general" | "multi_item" | "vehicle" | ...
    collection_name: str       # Mongo collection the doc came from
    document: dict             # the auction document (never mutated)


# ─────────────────────────────────────────────────────────────────────
#  Auction-collection registry
# ─────────────────────────────────────────────────────────────────────
#  Order matters — resolution stops at the first collection that has a
#  document with ``id == auction_id``.  All collections are queried;
#  each collection maps to (auction_type, is_multi_lot).
_AUCTION_COLLECTIONS: list[tuple[str, str, bool]] = [
    ("listings",                    "general",           False),
    ("multi_item_listings",         "multi_item",        True),
    ("vehicle_listings",            "vehicle",           True),
    ("vehicle_multi_lot_listings",  "vehicle_multi_lot", True),
    ("storage_auctions",            "storage",           False),
    ("partner_auctions",            "partner",           True),
]


# ═════════════════════════════════════════════════════════════════════
#  Helpers
# ═════════════════════════════════════════════════════════════════════

def _first(*values: Any) -> Any:
    """Return the first value that is not None and not empty-string."""
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and v == "":
            continue
        return v
    return None


def _bilingual(en_key: str, fr_key: str, doc: dict) -> Any:
    """Return the English variant when both are present."""
    return _first(doc.get(en_key), doc.get(fr_key), doc.get(en_key.replace("_en", "")))


def _stringify_images(images: Any) -> str:
    """Normalise every possible image-field shape to `url|url|url`."""
    if not images:
        return ""
    if isinstance(images, str):
        return images
    urls: list[str] = []
    for entry in images if isinstance(images, list) else [images]:
        if entry is None:
            continue
        if isinstance(entry, str):
            urls.append(entry)
            continue
        if isinstance(entry, dict):
            u = _first(entry.get("url"), entry.get("src"), entry.get("path"))
            if u:
                urls.append(str(u))
    return "|".join(urls)


def _listing_url(base_url: str, auction_type: str, auction_id: str,
                 lot_number: Any = None) -> str:
    """Produce a canonical public URL for the auction / lot."""
    base = (base_url or "").rstrip("/")
    if auction_type == "storage":
        return f"{base}/storage/auction/{auction_id}"
    if auction_type in {"multi_item", "vehicle", "vehicle_multi_lot", "partner"}:
        # Multi-lot auctions link to the parent auction page (lot deeplink
        # varies per surface and is not universal).
        return f"{base}/auction/{auction_id}"
    return f"{base}/listing/{auction_id}"


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        # CSV-friendly numeric — no scientific notation for cents.
        return format(v, ".2f") if isinstance(v, float) else str(v)
    return str(v)


# ═════════════════════════════════════════════════════════════════════
#  Lot normalisers
# ═════════════════════════════════════════════════════════════════════

def _normalize_single_doc_as_lot(
    doc: dict, auction_type: str
) -> list[dict]:
    """Auction types where the parent document *is* the lot."""
    title = _first(
        doc.get("title"), doc.get("title_en"), doc.get("title_fr"),
        doc.get("unit_number") and f"Storage Unit {doc.get('unit_number')}",
    )
    description = _first(
        doc.get("description"),
        doc.get("description_en"),
        doc.get("description_fr"),
    )
    return [{
        "lot_number":    _first(doc.get("lot_number"), 1),
        "title":         title,
        "description":   description,
        "quantity":      _first(doc.get("quantity"), 1),
        "starting_bid":  _first(doc.get("starting_bid"),
                                doc.get("starting_price"),
                                doc.get("start_price")),
        "category":      _first(doc.get("category"), doc.get("categories") and
                                (doc["categories"][0] if isinstance(doc["categories"], list) and doc["categories"] else None)),
        "condition":     doc.get("condition"),
        "current_bid":   _first(doc.get("current_bid"),
                                doc.get("current_price"),
                                doc.get("winning_bid")),
        "status":        _first(doc.get("status"), doc.get("lot_status")),
        "images":        _first(doc.get("images"), doc.get("photos"),
                                doc.get("image_urls")),
        "winner_user_id": _first(doc.get("winner_user_id"),
                                 doc.get("winner_id"),
                                 doc.get("winning_bidder_id"),
                                 doc.get("highest_bidder_id")),
        "hammer_price":  _first(doc.get("hammer_price"),
                                doc.get("final_price")),
        "sold_at":       doc.get("sold_at"),
    }]


def _normalize_embedded_lot(lot: dict) -> dict:
    """Auction types with a lots[] array."""
    return {
        "lot_number":    _first(lot.get("lot_number"), lot.get("number")),
        "title":         _first(lot.get("title"),
                                lot.get("title_en"),
                                lot.get("title_fr")),
        "description":   _first(lot.get("description"),
                                lot.get("description_en"),
                                lot.get("description_fr")),
        "quantity":      _first(lot.get("quantity"),
                                lot.get("available_quantity"), 1),
        "starting_bid":  _first(lot.get("starting_bid"),
                                lot.get("starting_price")),
        "category":      lot.get("category"),
        "condition":     lot.get("condition"),
        "current_bid":   _first(lot.get("current_bid"),
                                lot.get("current_price")),
        "status":        _first(lot.get("status"), lot.get("lot_status")),
        "images":        _first(lot.get("images"), lot.get("photos")),
        "winner_user_id": _first(lot.get("winner_user_id"),
                                 lot.get("winning_bidder_id"),
                                 lot.get("highest_bidder_id")),
        "hammer_price":  _first(lot.get("hammer_price"),
                                lot.get("final_price")),
        "sold_at":       lot.get("sold_at"),
    }


# ═════════════════════════════════════════════════════════════════════
#  Public API — resolution, permission, generation
# ═════════════════════════════════════════════════════════════════════

async def resolve_auction(db, auction_id: str) -> Optional[ExportResolution]:
    """Locate the auction document across all supported collections."""
    if not auction_id:
        return None
    for coll, atype, _is_multi in _AUCTION_COLLECTIONS:
        doc = await db[coll].find_one({"id": auction_id}, {"_id": 0})
        if doc:
            return ExportResolution(auction_type=atype,
                                    collection_name=coll,
                                    document=doc)
    return None


def _is_admin(user: Any) -> bool:
    if user is None:
        return False
    if isinstance(user, dict):
        return bool(user.get("is_admin") or "admin" in (user.get("roles") or []))
    return bool(getattr(user, "is_admin", False))


def _user_id(user: Any) -> Optional[str]:
    if user is None:
        return None
    if isinstance(user, dict):
        return user.get("id") or user.get("_id")
    return getattr(user, "id", None)


class ExportAccessDenied(Exception):
    """Raised when the caller does not have permission for the surface."""

    def __init__(self, reason: str, status: int = 403):
        super().__init__(reason)
        self.reason = reason
        self.status = status


class ExportNotFound(Exception):
    """Raised when auction_id could not be resolved."""


def _check_permission(
    resolution: ExportResolution,
    surface: str,
    current_user: Any,
) -> None:
    if surface not in _VALID_SURFACES:
        raise ExportAccessDenied(
            f"Invalid surface: {surface!r}", status=400)

    if surface == "public":
        return

    if surface == "admin":
        if not _is_admin(current_user):
            raise ExportAccessDenied("Admin access required", status=403)
        return

    # surface == "seller"
    if current_user is None:
        raise ExportAccessDenied("Authentication required", status=401)
    if _is_admin(current_user):
        return  # admins can export as any seller
    doc_seller_id = resolution.document.get("seller_id")
    if not doc_seller_id:
        raise ExportAccessDenied(
            "Auction has no owner (cannot verify seller)", status=403)
    if doc_seller_id != _user_id(current_user):
        raise ExportAccessDenied(
            "You are not the owner of this auction", status=403)


def _lots_for(resolution: ExportResolution) -> list[dict]:
    doc = resolution.document
    atype = resolution.auction_type
    if atype in {"general", "storage"}:
        return _normalize_single_doc_as_lot(doc, atype)
    raw_lots = doc.get("lots") or []
    if not isinstance(raw_lots, list):
        return []
    return [_normalize_embedded_lot(lot) for lot in raw_lots if isinstance(lot, dict)]


def _filter_and_sort_lots(
    lots: list[dict],
    surface: str,
    include_drafts: bool,
) -> list[dict]:
    def _keep(lot: dict) -> bool:
        st = (lot.get("status") or "").strip().lower()
        if not include_drafts and st in _HIDDEN_STATUSES_BY_DEFAULT:
            return False
        return True

    # Public callers ALWAYS filter out draft-ish statuses regardless of
    # include_drafts (defensive — the flag is only honoured for seller/admin).
    if surface == "public":
        include_drafts = False

    keep = [lot for lot in lots if _keep(lot)]

    # Stable sort by lot_number where numeric-like, else by title.
    def _sort_key(lot: dict):
        ln = lot.get("lot_number")
        try:
            return (0, int(str(ln))) if ln is not None else (1, str(lot.get("title") or ""))
        except (TypeError, ValueError):
            return (1, str(ln))

    return sorted(keep, key=_sort_key)


def _auction_name(doc: dict) -> str:
    return _safe_str(_first(
        doc.get("title"),
        doc.get("title_en"),
        doc.get("title_fr"),
        doc.get("auction_name"),
        doc.get("unit_number") and f"Storage Unit {doc.get('unit_number')}",
    ))


def _row_for_surface(
    surface: str,
    auction_id: str,
    auction_name: str,
    auction_type: str,
    base_url: str,
    lot: dict,
) -> dict:
    row = {
        "auction_id":   auction_id,
        "auction_name": auction_name,
        "lot_number":   _safe_str(lot.get("lot_number")),
        "title":        _safe_str(lot.get("title")),
        "description":  _safe_str(lot.get("description")),
        "quantity":     _safe_str(lot.get("quantity") or 1),
        "starting_bid": _safe_str(lot.get("starting_bid")),
        "category":     _safe_str(lot.get("category")),
        "condition":    _safe_str(lot.get("condition")),
        "current_bid":  _safe_str(lot.get("current_bid")),
        "status":       _safe_str(lot.get("status")),
        "listing_url":  _listing_url(base_url, auction_type, auction_id,
                                     lot.get("lot_number")),
        "image_urls":   _stringify_images(lot.get("images")),
    }
    if surface == "admin":
        row["winner_user_id"] = _safe_str(lot.get("winner_user_id"))
        row["hammer_price"]   = _safe_str(lot.get("hammer_price"))
        row["sold_at"]        = _safe_str(lot.get("sold_at"))
        # seller_id is a document-level property on all collections.
        # It will be filled in by generate_csv().
        row["seller_id"] = ""
    return row


def _filename(auction_id: str, surface: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", auction_id or "auction")
    return f"bidvex_lots_{safe}_{surface}.csv"


async def generate_csv(
    db,
    auction_id: str,
    surface: str,
    current_user: Any = None,
    *,
    include_drafts: bool = False,
    base_url: Optional[str] = None,
) -> tuple[str, bytes]:
    """
    Canonical single-entry-point CSV generator.

    Parameters
    ----------
    db              : Motor database handle.
    auction_id      : Auction UUID (searched across all supported
                      collections).
    surface         : ``'seller'`` | ``'public'`` | ``'admin'``.
    current_user    : Authenticated user (dict or Pydantic).  ``None``
                      is allowed only for ``surface='public'``.
    include_drafts  : When ``True`` (seller/admin only), draft lots
                      are included.  Public surface always hides drafts.
    base_url        : Frontend base URL used to build ``listing_url``.
                      Defaults to ``FRONTEND_BASE_URL`` env or
                      ``https://bidvex.ca``.

    Returns
    -------
    (filename, csv_bytes)   csv_bytes are UTF-8 encoded with a BOM so
                            Excel opens them cleanly.

    Raises
    ------
    ExportNotFound          Auction ID not found in any collection.
    ExportAccessDenied      Caller lacks permission for the surface.
    """
    if surface not in _VALID_SURFACES:
        raise ExportAccessDenied(
            f"Invalid surface: {surface!r}", status=400)

    resolution = await resolve_auction(db, auction_id)
    if resolution is None:
        raise ExportNotFound(f"Auction not found: {auction_id!r}")

    _check_permission(resolution, surface, current_user)

    base_url = base_url or os.environ.get("FRONTEND_BASE_URL") \
                        or "https://bidvex.ca"

    lots = _lots_for(resolution)
    lots = _filter_and_sort_lots(lots, surface, include_drafts)

    auction_name = _auction_name(resolution.document)

    columns = list(CANONICAL_COLUMNS)
    if surface == "admin":
        columns.extend(ADMIN_EXTRA_COLUMNS)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore",
                            quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()

    for lot in lots:
        row = _row_for_surface(
            surface=surface,
            auction_id=auction_id,
            auction_name=auction_name,
            auction_type=resolution.auction_type,
            base_url=base_url,
            lot=lot,
        )
        if surface == "admin":
            row["seller_id"] = _safe_str(resolution.document.get("seller_id"))
        writer.writerow(row)

    # UTF-8 BOM so Excel treats the file as UTF-8 by default.
    payload = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return _filename(auction_id, surface), payload


async def stream_csv(
    db,
    auction_id: str,
    surface: str,
    current_user: Any = None,
    *,
    include_drafts: bool = False,
    base_url: Optional[str] = None,
    chunk_lots: int = 500,
):
    """
    Async generator yielding CSV bytes in chunks.  Kept simple —
    delegates to ``generate_csv`` but chunks the result so large
    auctions don't force the caller to hold the full payload in memory.
    """
    filename, payload = await generate_csv(
        db, auction_id, surface, current_user,
        include_drafts=include_drafts, base_url=base_url,
    )
    _ = chunk_lots  # (accepted for future re-streamed implementation)
    for i in range(0, len(payload), 65536):
        yield payload[i:i + 65536]


__all__ = [
    "CANONICAL_COLUMNS",
    "ADMIN_EXTRA_COLUMNS",
    "ExportAccessDenied",
    "ExportNotFound",
    "ExportResolution",
    "generate_csv",
    "stream_csv",
    "resolve_auction",
]
