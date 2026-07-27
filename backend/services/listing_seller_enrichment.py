"""
iter217 — Listing seller enrichment

Surfaces the seller's account_type onto every listing GET response so the
frontend can:
  - Render the correct seller-type badge (Partner Auction / Vehicle Dealer
    Auction / Storage Auction / Private Sale).
  - Read the canonical buyer's premium rate from `buyer_premium_rate`
    (fraction, 0.15 = 15%) regardless of which field the listing stored
    historically (`premium_percentage`, `custom_buyer_premium_rate`,
    `buyers_premium_percent`, `partner_bp_rate`).

The fee math itself is NOT touched here. This is purely a display-layer
enrichment so the buyer UI stops misrepresenting partner auctions as
private sales.
"""
from typing import Any, Dict, Optional


def _coerce_rate_to_fraction(value: Any) -> Optional[float]:
    """Convert a stored BP value to a 0-1 fraction.

    - 5.0   -> 0.05  (stored as percent)
    - 0.05  -> 0.05  (already a fraction)
    - 15    -> 0.15
    - None  -> None
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    if v > 1.0:
        v = v / 100.0
    return round(v, 6)


def resolve_seller_account_type(
    seller: Dict[str, Any],
    listing_context: str = "general",
) -> str:
    """Deterministic single-value classification scoped to listing context.

    Context-aware priority:
      - "vehicle"  -> vehicle_dealer > partner > individual
      - "storage"  -> storage_facility > partner > individual
      - everything else (lots / marketplace / "general"):
          partner > vehicle_dealer > storage_facility > individual
        (a verified partner posting a regular auction is a PARTNER AUCTION;
         vehicle_dealer/storage_facility flags only dominate inside their
         own dedicated listing surfaces.)
    """
    if not seller:
        return "individual"

    is_partner = bool(
        seller.get("is_partner")
        and seller.get("partner_verification_status") in ("verified", "approved")
    )
    is_dealer = bool(seller.get("is_vehicle_dealer"))
    is_facility = bool(
        seller.get("is_storage_facility")
        or seller.get("account_type") == "storage_facility"
    )

    if listing_context == "vehicle":
        if is_dealer:
            return "vehicle_dealer"
        if is_partner:
            return "partner"
        return "individual"

    if listing_context == "storage":
        if is_facility:
            return "storage_facility"
        if is_partner:
            return "partner"
        return "individual"

    # General / marketplace / lots auctions —
    #
    # iter292 — A vehicle dealer or storage facility selling a non-vehicle /
    # non-storage item (e.g. a dealer listing a table on the Marketplace, or
    # a storage facility running a Lots auction) is just a regular seller.
    # The "Vehicle Dealer Auction — Full taxes on hammer price" badge and
    # the vehicle fee block must NOT bleed into marketplace / lots
    # listings. Dealer / facility flags only dominate inside their own
    # dedicated listing surfaces (handled by the explicit `vehicle` /
    # `storage` context branches above).
    if is_partner:
        return "partner"
    return "individual"


def enrich_listing_with_seller(
    listing: Dict[str, Any],
    seller: Optional[Dict[str, Any]],
    listing_context: str = "general",
) -> Dict[str, Any]:
    """Mutates and returns the listing dict with seller_* enrichment fields."""
    if listing is None:
        return listing
    seller = seller or {}
    account_type = resolve_seller_account_type(seller, listing_context)

    listing["seller_account_type"] = account_type
    listing["seller_is_partner"] = account_type == "partner"
    listing["seller_is_vehicle_dealer"] = account_type == "vehicle_dealer"
    listing["seller_is_storage_facility"] = account_type == "storage_facility"
    listing["seller_is_business"] = bool(
        seller.get("is_tax_registered")
        or account_type in ("partner", "vehicle_dealer", "storage_facility")
    )
    listing["seller_partner_company_name"] = (
        seller.get("partner_company_name") if account_type == "partner" else None
    )
    # iter300 — merit-based Top Seller badge (nightly GMV ranking).
    listing["seller_is_top_seller"] = bool(seller.get("is_top_seller"))
    # iter283 — Public seller-info fields surfaced on the listing detail
    # "Seller Information" card. None when missing so the FE can hide the
    # row cleanly. Only forwarded for non-individual sellers to avoid
    # leaking a private seller's home address-derived city/province.
    if account_type in ("partner", "vehicle_dealer", "storage_facility"):
        listing["seller_website"] = (seller.get("website") or None)
        listing["seller_company_name"] = (
            seller.get("partner_company_name")
            or seller.get("company_name")
            or None
        )
        listing["seller_province"] = seller.get("province") or listing.get("seller_province")
        listing["seller_city"] = seller.get("city") or listing.get("seller_city")
    else:
        listing.setdefault("seller_website", None)
        listing.setdefault("seller_company_name", None)

    # Canonical buyer's premium rate (fraction). Prefer explicit per-listing
    # fields; fall back to the partner's account-level BP.
    rate = (
        _coerce_rate_to_fraction(listing.get("buyer_premium_rate"))
        or _coerce_rate_to_fraction(listing.get("custom_buyer_premium_rate"))
        or _coerce_rate_to_fraction(listing.get("premium_percentage"))
        or _coerce_rate_to_fraction(listing.get("buyers_premium_percent"))
        or _coerce_rate_to_fraction(listing.get("partner_bp_rate"))
    )
    if rate is None and account_type == "partner":
        rate = _coerce_rate_to_fraction(seller.get("partner_buyer_premium_pct"))
    listing["buyer_premium_rate"] = rate
    return listing


async def enrich_listings_bulk_async(
    db,
    listings,
    listing_context: str = "general",
):
    """iter217 — Bulk enrich a list of listing dicts in ONE round-trip to MongoDB.

    Walks all unique seller_ids, batch-loads their User docs, then applies
    `enrich_listing_with_seller` to each listing. Same field shape as the
    single-doc helper.
    """
    if not listings:
        return listings
    seller_ids = {l.get("seller_id") for l in listings if l and l.get("seller_id")}
    sellers_by_id = {}
    if seller_ids:
        cursor = db.users.find(
            {"id": {"$in": list(seller_ids)}},
            {
                "_id": 0,
                "id": 1,
                "is_partner": 1,
                "partner_verification_status": 1,
                "partner_company_name": 1,
                "partner_buyer_premium_pct": 1,
                "is_vehicle_dealer": 1,
                "is_storage_facility": 1,
                "is_tax_registered": 1,
                "account_type": 1,
                "subscription_tier": 1,
                "platform_fee_paid": 1,
                "partner_subscription_active": 1,
                "is_top_seller": 1,
                # iter283 — Public seller-info fields (website + company)
                # used by the listing detail "Seller Information" card.
                "website": 1,
                "company_name": 1,
                "province": 1,
                "city": 1,
            },
        )
        async for s in cursor:
            sellers_by_id[s["id"]] = s
    for listing in listings:
        seller = sellers_by_id.get(listing.get("seller_id"), {})
        # iter283 — When `listing_context` is "auto" (or None), infer the
        # context per-listing so a multi-flagged seller's storage row
        # shows a storage badge while their vehicle row shows a vehicle
        # badge. Callers can still pin a single context (e.g. "vehicle"
        # for the vehicle auctions page) by passing it explicitly.
        ctx = listing_context
        if not ctx or ctx == "auto":
            try:
                from services.listing_sections import infer_seller_context
                ctx = infer_seller_context(listing)
            except Exception:  # noqa: BLE001
                ctx = "general"
        enrich_listing_with_seller(listing, seller, ctx)
    return listings



async def enrich_listing_async(
    db,
    listing: Dict[str, Any],
    listing_context: str = "general",
) -> Dict[str, Any]:
    """Convenience wrapper: fetch the seller doc from MongoDB and enrich one listing."""
    if not listing:
        return listing
    seller_id = listing.get("seller_id")
    if not seller_id:
        return enrich_listing_with_seller(listing, {}, listing_context)
    seller = await db.users.find_one(
        {"id": seller_id},
        {
            "_id": 0,
            "is_partner": 1,
            "partner_verification_status": 1,
            "partner_company_name": 1,
            "partner_buyer_premium_pct": 1,
            "is_vehicle_dealer": 1,
            "is_storage_facility": 1,
            "is_tax_registered": 1,
            "account_type": 1,
            "subscription_tier": 1,
            "platform_fee_paid": 1,
            "partner_subscription_active": 1,
            "is_top_seller": 1,
            # iter283 — Public seller-info fields.
            "website": 1,
            "company_name": 1,
            "province": 1,
            "city": 1,
        },
    )
    return enrich_listing_with_seller(listing, seller, listing_context)



# ── iter394 · Fan-out helper ────────────────────────────────────────
async def refresh_seller_type_across_listings(db, user_id: str) -> Dict[str, int]:
    """Recompute `seller_account_type` (+ sibling booleans) on every open
    listing owned by `user_id` across `listings`, `multi_item_listings`,
    and `vehicle_listings`.

    Call this from any endpoint that promotes/demotes a user's seller flags
    (partner grant/revoke, vehicle-dealer approval, storage-facility grant,
    account-type change). This closes the persistence-drift class of bugs
    that iter392 diagnosed — the moment a user upgrades to partner, every
    one of their listings sees the correct `partner` badge, tax rate, and
    fee schedule without waiting for the nightly sweep to catch it.

    Returns `{"listings": N, "multi_item_listings": M, "vehicle_listings": K}` —
    the number of docs updated per collection.
    """
    if not user_id:
        return {"listings": 0, "multi_item_listings": 0, "vehicle_listings": 0}

    seller = await db.users.find_one(
        {"id": user_id},
        {
            "_id": 0, "is_partner": 1, "partner_verification_status": 1,
            "partner_company_name": 1, "partner_buyer_premium_pct": 1,
            "is_vehicle_dealer": 1, "is_storage_facility": 1,
            "is_tax_registered": 1, "account_type": 1,
            "subscription_tier": 1, "platform_fee_paid": 1,
            "partner_subscription_active": 1, "is_top_seller": 1,
            "website": 1, "company_name": 1, "province": 1, "city": 1,
        },
    )
    seller = seller or {}

    result: Dict[str, int] = {}
    # Only recompute on the seller's OPEN listings so we don't churn every
    # closed/sold/completed doc unnecessarily. Closed listings keep their
    # historical badge, which is intentional for audit-trail integrity.
    open_status_filter = {"status": {"$nin": ["completed", "sold", "cancelled", "expired"]}}

    for coll_name, context in (
        ("listings",            "general"),
        ("multi_item_listings", "lots"),
        ("vehicle_listings",    "vehicle"),
    ):
        new_type = (resolve_seller_account_type(seller, context) or "individual").lower()
        update_fields = {
            "seller_account_type":         new_type,
            "seller_is_partner":           new_type == "partner",
            "seller_is_vehicle_dealer":    new_type == "vehicle_dealer",
            "seller_is_storage_facility":  new_type == "storage_facility",
        }
        try:
            res = await db[coll_name].update_many(
                {"seller_id": user_id, **open_status_filter},
                {"$set": update_fields},
            )
            result[coll_name] = res.modified_count
        except Exception:  # noqa: BLE001 — never let one collection block the others
            result[coll_name] = -1

    return result
