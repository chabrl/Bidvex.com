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

    # General / marketplace / lots auctions
    if is_partner:
        return "partner"
    if is_dealer:
        return "vehicle_dealer"
    if is_facility:
        return "storage_facility"
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


async def enrich_listing_async(
    db,
    listing: Dict[str, Any],
    listing_context: str = "general",
) -> Dict[str, Any]:
    """Convenience wrapper: fetch the seller doc from MongoDB and enrich."""
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
        },
    )
    return enrich_listing_with_seller(listing, seller, listing_context)
