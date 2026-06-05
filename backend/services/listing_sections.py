"""
iter283 — Section routing & seller-context inference for listings.

Single source of truth for:
  • Which `listing_type` aliases belong to which section page.
  • Which seller badge context to render on a given listing
    (vehicle / storage / general).

Used by:
  • routes/listings.py    — creation auto-tagging + GET context
  • routes/marketplace.py — section-specific queries
  • startup backfill in server.py
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# ── Listing-type → section slug ───────────────────────────────────────

# Storage facility / storage unit aliases.
STORAGE_TYPES = (
    "storage_auction",
    "storage",
    "storage_locker",
    "unit",
    "unit_auction",
)

# Vehicle auction aliases.
VEHICLE_TYPES = (
    "vehicle_auction",
    "vehicles",
    "vehicle",
)

# Lots / multi-item auction aliases.
LOT_TYPES = (
    "lot_auction",
    "lots",
    "multi_lot",
    "multi_item",
)

# Canonical (single) listing_type written by NEW creations.
CANONICAL_TYPE = {
    "storage": "storage_locker",
    "vehicle": "vehicle_auction",
    "lots":    "lot_auction",
    "marketplace": "marketplace",
}


# ── Category → section inference ──────────────────────────────────────

# Categories that imply a section even when listing_type is missing.
# Used at create-time auto-tagging and idempotent backfill.
STORAGE_CATEGORIES = ("storage", "storage_locker", "unit")
VEHICLE_CATEGORIES = (
    "vehicles", "vehicle", "vehicle parts", "cars",
    "motorcycles", "trucks", "boats", "rvs", "trailers",
)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def infer_section(listing: Dict[str, Any]) -> str:
    """Return the canonical section slug for a listing dict.

    Priority chain — listing_type > category > quantity heuristic > marketplace.
    """
    if not listing:
        return "marketplace"
    lt = _norm(listing.get("listing_type"))
    cat = _norm(listing.get("category"))
    if lt in STORAGE_TYPES or cat in STORAGE_CATEGORIES:
        return "storage"
    if lt in VEHICLE_TYPES or cat in VEHICLE_CATEGORIES:
        return "vehicles"
    if lt in LOT_TYPES:
        return "lots"
    try:
        qty = int(listing.get("quantity") or 1)
    except (TypeError, ValueError):
        qty = 1
    if qty > 1:
        return "lots"
    return "marketplace"


def infer_seller_context(listing: Dict[str, Any]) -> str:
    """Return the seller-badge `listing_context` for the enrichment service.

    Maps section → enrichment-service context vocabulary:
      storage → "storage"
      vehicles → "vehicle"
      everything else → "general"
    """
    section = infer_section(listing)
    if section == "storage":
        return "storage"
    if section == "vehicles":
        return "vehicle"
    return "general"


def section_query_filter(section: str) -> Dict[str, Any]:
    """Return a MongoDB filter snippet that matches every listing whose
    `listing_type` belongs to the given section.

    Example:
        section_query_filter("storage")
        # → {"listing_type": {"$in": ("storage_auction","storage",
        #                              "storage_locker","unit","unit_auction")}}
    """
    section = section.lower().strip()
    if section == "storage":
        return {"listing_type": {"$in": list(STORAGE_TYPES)}}
    if section in ("vehicle", "vehicles"):
        return {"listing_type": {"$in": list(VEHICLE_TYPES)}}
    if section == "lots":
        return {"listing_type": {"$in": list(LOT_TYPES)}}
    if section == "marketplace":
        # Marketplace shows EVERY active listing regardless of type.
        return {}
    return {}


async def backfill_listing_sections(db) -> Dict[str, int]:
    """Idempotent — set canonical `listing_type` + `section` on every
    listings doc that's missing it. Safe to run at every startup.

    Returns counts per bucket so the boot log captures rollout state.
    """
    counts = {"storage": 0, "vehicles": 0, "lots": 0, "marketplace": 0}

    # 1) Storage by category match (only when listing_type is NOT already a
    #    canonical storage alias).
    r = await db.listings.update_many(
        {
            "category": {"$regex": r"^(storage|unit)$", "$options": "i"},
            "$or": [
                {"listing_type": {"$nin": list(STORAGE_TYPES)}},
                {"listing_type": {"$exists": False}},
                {"listing_type": None},
            ],
        },
        {"$set": {"listing_type": CANONICAL_TYPE["storage"], "section": "storage"}},
    )
    counts["storage"] = int(r.modified_count or 0)

    # 2) Vehicle by category match.
    r = await db.listings.update_many(
        {
            "category": {
                "$regex": r"^(vehicles?|cars?|motorcycles?|trucks?|boats?|rvs?|trailers?|vehicle\s*parts)$",
                "$options": "i",
            },
            "$or": [
                {"listing_type": {"$nin": list(VEHICLE_TYPES)}},
                {"listing_type": {"$exists": False}},
                {"listing_type": None},
            ],
        },
        {"$set": {"listing_type": CANONICAL_TYPE["vehicle"], "section": "vehicles"}},
    )
    counts["vehicles"] = int(r.modified_count or 0)

    # 3) Multi-quantity → lots (only when listing_type missing — never
    #    overwrite an explicit categorization).
    r = await db.listings.update_many(
        {
            "quantity": {"$gt": 1},
            "$or": [
                {"listing_type": {"$exists": False}},
                {"listing_type": None},
            ],
        },
        {"$set": {"listing_type": CANONICAL_TYPE["lots"], "section": "lots"}},
    )
    counts["lots"] = int(r.modified_count or 0)

    # 4) Stamp `section` on every doc that still lacks it. We don't touch
    #    listing_type here — only the section field that powers cross-feed
    #    badges + section filters when listing_type is heterogeneous.
    r = await db.listings.update_many(
        {
            "listing_type": {"$in": list(STORAGE_TYPES)},
            "$or": [{"section": {"$exists": False}}, {"section": None}],
        },
        {"$set": {"section": "storage"}},
    )
    r = await db.listings.update_many(
        {
            "listing_type": {"$in": list(VEHICLE_TYPES)},
            "$or": [{"section": {"$exists": False}}, {"section": None}],
        },
        {"$set": {"section": "vehicles"}},
    )
    r = await db.listings.update_many(
        {
            "listing_type": {"$in": list(LOT_TYPES)},
            "$or": [{"section": {"$exists": False}}, {"section": None}],
        },
        {"$set": {"section": "lots"}},
    )

    # 5) Everything still without a section gets `marketplace`.
    r = await db.listings.update_many(
        {"$or": [{"section": {"$exists": False}}, {"section": None}]},
        {"$set": {"section": "marketplace"}},
    )
    counts["marketplace"] = int(r.modified_count or 0)
    return counts


__all__ = [
    "STORAGE_TYPES", "VEHICLE_TYPES", "LOT_TYPES",
    "STORAGE_CATEGORIES", "VEHICLE_CATEGORIES", "CANONICAL_TYPE",
    "infer_section", "infer_seller_context",
    "section_query_filter", "backfill_listing_sections",
]
