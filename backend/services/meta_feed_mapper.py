"""
Phase 5 — Meta Dynamic Local Ads infrastructure.

Public catalog feed mapper that converts BidVex active listings into
Meta's Product Catalog JSON schema. Schema reference:
https://developers.facebook.com/docs/marketing-api/catalog

Strict field-name compliance; Meta's catalog ingestion is case-sensitive
and rejects feeds with missing mandatory fields. Listings missing any
mandatory field are excluded.

This module is read-only; it never mutates listings or the fee engine.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from routes.marketplace import _normalize_region

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────
BIDVEX_BASE_URL = os.environ.get("BIDVEX_BASE_URL", "https://bidvex.com").rstrip("/")
FEED_REQUIRE_GEO = (os.environ.get("FEED_REQUIRE_GEO", "false").lower() == "true")

# Branded fallback used when a listing has images but none are valid https URLs
# (e.g. base64 data URLs uploaded before the S3/Cloudinary migration). Meta
# strictly rejects feeds with no `image_link`; this keeps the listing live in
# the catalog with a neutral branded image instead of silently dropping it.
BIDVEX_PLACEHOLDER_IMAGE = f"{BIDVEX_BASE_URL}/assets/placeholder-ad.jpg"


# ── Listing type → URL path prefix ────────────────────────────────────
LISTING_TYPE_TO_PATH = {
    "marketplace": "listings",
    "single":      "listings",
    "lots":        "lots",
    "multi_lot":   "lots",
    "vehicle":     "vehicle-auctions",
    "storage":     "storage-auctions",
}

# Source-collection → derived listing_type
COLLECTION_TO_TYPE = {
    "listings":            "marketplace",
    "multi_item_listings": "lots",
    "vehicles":            "vehicle",
    "storage_auctions":    "storage",
}

# Type prefix for the catalog `id` (must match the frontend pixel's content_ids)
TYPE_PREFIX = {
    "marketplace": "MKT",
    "lots":        "LOT",
    "vehicle":     "VEH",
    "storage":     "STO",
}


# ── Google Product Taxonomy short numeric mapping ─────────────────────
# Meta accepts Google's product taxonomy IDs.
_GOOGLE_CATEGORY_BY_KEYWORD = [
    ("vehicle",      "916"),
    ("car",          "916"),
    ("auto",         "916"),
    ("furniture",    "436"),
    ("meuble",       "436"),
    ("electronic",   "222"),
    ("ordinateur",   "222"),
    ("informatique", "222"),
    ("clothing",     "166"),
    ("mode",         "166"),
    ("vetement",     "166"),
    ("v\u00eatement",     "166"),
    ("tool",         "632"),
    ("outil",        "632"),
    ("sport",        "990"),
    ("collect",      "216"),
    ("art",          "216"),
]


def _google_product_category(category: Optional[str]) -> str:
    if not category:
        return "632"
    c = str(category).lower()
    for keyword, code in _GOOGLE_CATEGORY_BY_KEYWORD:
        if keyword in c:
            return code
    return "632"


# ── Condition mapping ────────────────────────────────────────────────
_CONDITION_MAP = {
    "new":          "new",
    "like_new":     "refurbished",
    "like new":     "refurbished",
    "excellent":    "refurbished",
    "good":         "used",
    "fair":         "used",
    "used":         "used",
    "salvage":      "used",
    "as is":        "used",
    "as_is":        "used",
}


def _map_condition(value: Optional[str]) -> str:
    if not value:
        return "used"
    return _CONDITION_MAP.get(str(value).strip().lower(), "used")


# ── HTML & whitespace cleanup ────────────────────────────────────────
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: Optional[str], max_len: int) -> str:
    if not s:
        return ""
    cleaned = _HTML_TAG_RE.sub("", str(s)).strip()
    return cleaned[:max_len]


# ── Image URL filter — Meta requires absolute https:// JPEG/PNG ──────
# iter213 — Reject the legacy Facebook redirect / CDN URLs that previously
# leaked into the catalog. They render as expired placeholders in Meta
# Commerce Manager because Facebook strips their session-bound query
# parameters before the crawler can hydrate them.
_BANNED_HOST_FRAGMENTS = (
    "l.facebook.com/l.php",  # Facebook click-tracking redirect
    "fbcdn.net",             # Bare Facebook CDN domain (session-bound)
)


def _is_valid_image_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    u = url.strip()
    if not u.startswith("https://"):
        return False
    lower = u.lower()
    for frag in _BANNED_HOST_FRAGMENTS:
        if frag in lower:
            return False
    # Also reject Facebook scontent CDN (subdomain-encoded session tokens
    # expire within hours of generation; Meta's crawler returns 404 once
    # the token is invalidated).
    if "scontent" in lower and ".facebook" in lower:
        return False
    # Meta auto-detects content-type, so we don't enforce extension.
    return True


def _first_valid_image(images: Optional[List[Any]], lots: Optional[List[Dict]]) -> Tuple[Optional[str], List[str]]:
    """Returns (primary_image_link, list_of_extra_image_links).

    For multi-item listings, walks lot images if top-level images is empty.
    """
    primary: Optional[str] = None
    extras: List[str] = []

    def _consume(url_list: Optional[List[Any]]) -> None:
        nonlocal primary
        if not url_list:
            return
        for u in url_list:
            if not _is_valid_image_url(u):
                continue
            if primary is None:
                primary = u
            elif u != primary and len(extras) < 9:
                extras.append(u)

    _consume(images)
    if lots:
        for lot in lots:
            _consume(lot.get("images"))
            if primary and len(extras) >= 9:
                break

    return primary, extras


def _has_any_image(images: Optional[List[Any]], lots: Optional[List[Dict]]) -> bool:
    """Returns True if the listing has at least one image of any kind (even
    base64 / non-https). Used to decide between excluding the listing entirely
    (no_images) versus serving a branded BidVex placeholder.
    """
    def _any(url_list: Optional[List[Any]]) -> bool:
        if not url_list:
            return False
        for u in url_list:
            if isinstance(u, str) and u.strip():
                return True
        return False

    if _any(images):
        return True
    if lots:
        for lot in lots:
            if _any(lot.get("images")):
                return True
    return False


# ── Province → ISO 3166-2:CA subdivision code (uppercase) ────────────
def _iso_region_code(province: Optional[str]) -> Optional[str]:
    if not province:
        return None
    normalized = _normalize_region(province)  # "qc", "on", etc.
    if not normalized or len(normalized) != 2:
        return None
    return normalized.upper()


# ── Coarse geocode fallback for major Canadian cities ────────────────
# Used only when the listing has no lat/lng. Centroid coordinates from
# Statistics Canada (public domain). Keys are lowercased + accent-stripped.
_CITY_GEOCODES: Dict[Tuple[str, str], Tuple[float, float]] = {
    ("montreal", "QC"):       (45.5019, -73.5674),
    ("quebec", "QC"):         (46.8139, -71.2080),
    ("laval", "QC"):          (45.5650, -73.7500),
    ("gatineau", "QC"):       (45.4765, -75.7013),
    ("longueuil", "QC"):      (45.5333, -73.5167),
    ("sherbrooke", "QC"):     (45.4001, -71.8825),
    ("saguenay", "QC"):       (48.4280, -71.0676),
    ("trois-rivieres", "QC"): (46.3432, -72.5432),
    ("levis", "QC"):          (46.7382, -71.2465),
    ("toronto", "ON"):        (43.6532, -79.3832),
    ("ottawa", "ON"):         (45.4215, -75.6972),
    ("mississauga", "ON"):    (43.5890, -79.6441),
    ("hamilton", "ON"):       (43.2557, -79.8711),
    ("london", "ON"):         (42.9849, -81.2453),
    ("brampton", "ON"):       (43.7315, -79.7624),
    ("vaughan", "ON"):        (43.8361, -79.4983),
    ("vancouver", "BC"):      (49.2827, -123.1207),
    ("victoria", "BC"):       (48.4284, -123.3656),
    ("surrey", "BC"):         (49.1913, -122.8490),
    ("burnaby", "BC"):        (49.2488, -122.9805),
    ("calgary", "AB"):        (51.0447, -114.0719),
    ("edmonton", "AB"):       (53.5461, -113.4938),
    ("winnipeg", "MB"):       (49.8951, -97.1384),
    ("regina", "SK"):         (50.4452, -104.6189),
    ("saskatoon", "SK"):      (52.1332, -106.6700),
    ("halifax", "NS"):        (44.6488, -63.5752),
    ("st johns", "NL"):       (47.5615, -52.7126),
    ("charlottetown", "PE"):  (46.2382, -63.1311),
    ("fredericton", "NB"):    (45.9636, -66.6431),
    ("moncton", "NB"):        (46.0878, -64.7782),
    ("whitehorse", "YT"):     (60.7212, -135.0568),
    ("yellowknife", "NT"):    (62.4540, -114.3718),
    ("iqaluit", "NU"):        (63.7467, -68.5170),
}


def _normalize_city_key(city: str) -> str:
    return (
        (city or "")
        .strip()
        .lower()
        .replace("\u00e9", "e").replace("\u00e8", "e").replace("\u00ea", "e")
        .replace("\u00e0", "a").replace("\u00ee", "i").replace("\u00f4", "o")
        .replace("'", "")
        .replace(".", "")
    )


def _geocode(city: Optional[str], region_iso: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Cheap city-centroid lookup. Returns (None, None) if no match."""
    if not city or not region_iso:
        return (None, None)
    return _CITY_GEOCODES.get((_normalize_city_key(city), region_iso), (None, None))


# ── Postal code normalization (uppercase, strip spaces/hyphens) ──────
def _normalize_postal(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return re.sub(r"\s|-", "", str(raw)).upper()


# ── Brand resolution by seller account type ──────────────────────────
def _brand(listing: Dict[str, Any]) -> str:
    acct = listing.get("seller_account_type")
    if acct == "partner":
        return (listing.get("seller_partner_company_name") or "BidVex Partner")[:100]
    if acct == "vehicle_dealer":
        return (listing.get("seller_company_name") or "BidVex Dealer")[:100]
    if acct == "storage_facility":
        return (listing.get("seller_company_name") or "BidVex Storage")[:100]
    return "BidVex Marketplace"


def _content_id(listing_type: str, listing_id: str) -> str:
    """iter224 hotfix — Meta catalog item ID + Pixel content_ids must be
    EXACTLY identical to `listing.id`. No prefix, no reformatting.

    Earlier iterations (iter218) used a `BIDVEX-{TYPE}-{id}` token to bake
    a type discriminator into the ID, but that breaks Google Merchant
    Center's `id ↔ link page id` validation and prevents the Pixel↔Catalog
    match-rate fix. Going forward the raw UUID is the canonical ID across
    Pixel, CAPI, Meta catalog, and Google Merchant Center.
    """
    return str(listing_id)


def _price_str_from_value(v: Any) -> str:
    """Helper: format a single price value as 'X.XX CAD' (no fallbacks)."""
    try:
        f = float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        f = 0.0
    return f"{f:.2f} CAD"


def _final_or_current_price(listing: Dict[str, Any], lots: Optional[List[Dict]]) -> Any:
    """iter224 hotfix — Return the single canonical price for catalog/feed.

    Auction price priority:
      1. status in ("ended","sold","closed") AND `final_hammer_price` → use it
      2. status in ("ended","sold","closed") AND `current_price/current_bid` → use it
      3. Live current_bid / current_price → use it
      4. Highest lot price (multi-lot) → use it
      5. starting_price / starting_bid → use it
      6. 1.00 (Meta refuses 0)
    `buy_now_price` is NEVER returned — auctions only expose live bid prices.
    """
    status = (listing.get("status") or "").lower()
    if status in ("ended", "sold", "closed", "completed"):
        for k in ("final_hammer_price", "winning_bid", "final_price", "current_bid", "current_price"):
            v = listing.get(k)
            if v is not None:
                try:
                    if float(v) > 0:
                        return v
                except (TypeError, ValueError):
                    continue

    current = listing.get("current_bid") or listing.get("current_price")
    if current and float(current) > 0:
        return current

    if lots:
        currents = [
            (lot.get("current_price") or lot.get("starting_price") or 0) for lot in lots
        ]
        currents = [c for c in currents if c]
        if currents:
            return max(currents)

    starting = listing.get("starting_bid") or listing.get("starting_price")
    if starting:
        try:
            if float(starting) > 0:
                return starting
        except (TypeError, ValueError):
            pass

    return 1.00


def _price_str(listing: Dict[str, Any], lots: Optional[List[Dict]]) -> str:
    """Returns 'X.XX CAD' using the canonical (NO buy_now) price."""
    return _price_str_from_value(_final_or_current_price(listing, lots))


def _availability(listing: Dict[str, Any]) -> str:
    """iter224 hotfix — Ended/sold listings remain in the catalog but flip
    to `out of stock` so Meta + Google retain match history instead of
    hard-deleting and breaking attribution."""
    status = (listing.get("status") or "").lower()
    if status in ("ended", "sold", "closed", "completed", "deleted", "archived"):
        return "out of stock"
    return "in stock"


def _build_link(listing_type: str, listing_id: str) -> str:
    path = LISTING_TYPE_TO_PATH.get(listing_type, "listings")
    return f"{BIDVEX_BASE_URL}/{path}/{listing_id}"


def _is_demo(seller: Dict[str, Any]) -> bool:
    return bool(
        seller.get("is_demo_account")
        or seller.get("is_demo")
        or seller.get("demo")
    )


def _auction_ends_within_24h(listing: Dict[str, Any]) -> bool:
    end = listing.get("auction_end_date")
    if not end:
        return False
    try:
        from datetime import datetime, timezone, timedelta
        if isinstance(end, str):
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return timedelta(0) < (end - now) < timedelta(hours=24)
    except Exception:
        return False


def map_listing_to_meta_item(
    listing: Dict[str, Any],
    listing_type: str,
    seller: Dict[str, Any],
    exclusion_counter: Dict[str, int],
) -> Optional[Dict[str, Any]]:
    """Returns a Meta-catalog-shaped dict or None if the listing must be excluded.

    `exclusion_counter` is mutated in-place with the reason key.
    """
    # ── Pre-flight exclusion checks ──
    status = listing.get("status")
    # iter224 hotfix — ended/sold/closed listings are NO LONGER excluded
    # from the catalog. Per Meta best practice we keep them indexed with
    # `availability: "out of stock"` so attribution + match history survive.
    # Only moderation-blocked listings are still dropped.
    if status in ("pending_review", "manual_review"):
        exclusion_counter["moderation_pending"] += 1
        return None
    if status not in ("active", "ended", "sold", "closed", "completed"):
        # Anything else (draft, deleted by user, archived without sale, etc.)
        return None

    if _is_demo(seller):
        exclusion_counter["demo_account"] += 1
        return None

    title = _strip_html(listing.get("title"), 150)
    if not title:
        exclusion_counter["no_title"] += 1
        return None

    primary_image, extra_images = _first_valid_image(
        listing.get("images"),
        listing.get("lots"),
    )
    if not primary_image:
        # Listing has SOME image data (base64 etc) but no valid https URL:
        # serve the branded BidVex placeholder so the listing still surfaces
        # in Meta's catalog. Listings with literally zero images of any kind
        # remain excluded — those are spammy/incomplete records.
        if _has_any_image(listing.get("images"), listing.get("lots")):
            primary_image = BIDVEX_PLACEHOLDER_IMAGE
            exclusion_counter["placeholder_used"] = exclusion_counter.get("placeholder_used", 0) + 1
        else:
            exclusion_counter["no_images"] += 1
            return None

    # Location — flat fields on the BidVex schema (no nested location object)
    city = (listing.get("city") or "").strip()
    region_iso = _iso_region_code(listing.get("region") or listing.get("province"))
    if not city or not region_iso:
        exclusion_counter["no_location"] += 1
        return None

    lat = listing.get("latitude")
    lng = listing.get("longitude")
    if not lat or not lng:
        # Geocoding fallback (city centroid) so Local Inventory Ads still work.
        lat, lng = _geocode(city, region_iso)

    if FEED_REQUIRE_GEO and (not lat or not lng):
        exclusion_counter["no_location"] += 1
        return None

    listing_id = listing.get("id")
    if not listing_id:
        exclusion_counter["no_title"] += 1
        return None

    description = _strip_html(listing.get("description"), 5000) or (
        f"{listing.get('category') or 'Auction item'} \u2014 "
        f"{listing.get('condition') or 'used'} \u2014 Listed on BidVex"
    )

    item: Dict[str, Any] = {
        # Mandatory
        "id":              _content_id(listing_type, listing_id),
        "title":           title,
        "description":     description,
        # iter224 hotfix — availability flips to "out of stock" for ended/sold
        # listings so Meta + Google keep match history instead of hard-delete.
        "availability":    _availability(listing),
        "condition":       _map_condition(listing.get("condition")),
        # iter224 hotfix — price is ALWAYS the live bid (or final hammer if
        # the auction has ended). buy_now_price is NEVER sent to external feeds.
        "price":           _price_str(listing, listing.get("lots")),
        "link":            _build_link(listing_type, listing_id),
        "image_link":      primary_image,
        "brand":           _brand(listing),
        # Location
        "city":            city,
        "region":          region_iso,
        "country":         "CA",
        "postal_code":     _normalize_postal(listing.get("postal_code")),
        "neighborhood":    city[:200],
        # Optional / recommended
        "google_product_category": _google_product_category(listing.get("category")),
        "custom_label_0":  listing_type,
        "custom_label_1":  listing.get("seller_account_type") or "individual",
        "custom_label_2":  region_iso,
        "custom_label_3":  "auction_ending_soon" if _auction_ends_within_24h(listing) else "auction_active",
    }

    # Geo coordinates (skip if still missing)
    if lat and lng:
        try:
            item["latitude"]  = float(lat)
            item["longitude"] = float(lng)
        except (TypeError, ValueError):
            pass

    # Multiple images — comma-separated list, max 9 extras
    if extra_images:
        item["additional_image_link"] = ",".join(extra_images)

    # iter224 hotfix — sale_price/buy_now removed from feed entirely.
    # BidVex is an auction platform; the only valid price is the live bid.
    # Google Merchant Center was rejecting listings with "Invalid sales
    # price — Prevents from showing in Canada" because the feed sale_price
    # didn't match the crawled-page current bid.

    return item


# ── Seed items — Meta Commerce Manager 5-product minimum ─────────────
# Meta refuses to ingest a catalog with fewer than 5 unique products. When
# the live catalog (or a province/category-filtered slice) returns less than
# 5 eligible items, we pad with neutral "test_seed" placeholders so the feed
# stays ingestible. Seeds are flagged via `custom_label_3="test_seed"` so they
# can be excluded server-side from real ads with one filter.
#
# Seeds rotate across QC and ON anchor cities so geographic ad delivery still
# has at least one valid (city, region) tuple per province. The seed pool is
# small and deterministic so the same set of seeds appears across rebuilds —
# Meta will treat them as stable catalog items rather than churn churn.
_SEED_TEMPLATES: List[Dict[str, Any]] = [
    {
        "suffix":      "001",
        "title":       "BidVex Sample Auction Lot A",
        "description": "Sample placeholder lot for catalog onboarding.",
        "city":        "Montreal",
        "region":      "QC",
        "postal_code": "H2X3L7",
        "latitude":    45.5019,
        "longitude":   -73.5674,
    },
    {
        "suffix":      "002",
        "title":       "BidVex Sample Auction Lot B",
        "description": "Sample placeholder lot for catalog onboarding.",
        "city":        "Toronto",
        "region":      "ON",
        "postal_code": "M5H2N2",
        "latitude":    43.6532,
        "longitude":   -79.3832,
    },
    {
        "suffix":      "003",
        "title":       "BidVex Sample Auction Lot C",
        "description": "Sample placeholder lot for catalog onboarding.",
        "city":        "Quebec",
        "region":      "QC",
        "postal_code": "G1R4P3",
        "latitude":    46.8139,
        "longitude":   -71.2080,
    },
    {
        "suffix":      "004",
        "title":       "BidVex Sample Auction Lot D",
        "description": "Sample placeholder lot for catalog onboarding.",
        "city":        "Ottawa",
        "region":      "ON",
        "postal_code": "K1A0A6",
        "latitude":    45.4215,
        "longitude":   -75.6972,
    },
    {
        "suffix":      "005",
        "title":       "BidVex Sample Auction Lot E",
        "description": "Sample placeholder lot for catalog onboarding.",
        "city":        "Laval",
        "region":      "QC",
        "postal_code": "H7V0A4",
        "latitude":    45.5650,
        "longitude":   -73.7500,
    },
]


def build_seed_items(needed: int) -> List[Dict[str, Any]]:
    """Returns up to `needed` seed items shaped exactly like real catalog items.

    Every seed item carries `custom_label_3="test_seed"` so production
    campaigns can exclude them via a single `custom_label_3 != test_seed`
    filter. Seeds satisfy all 14 Meta-mandatory fields.
    """
    if needed <= 0:
        return []

    out: List[Dict[str, Any]] = []
    for tpl in _SEED_TEMPLATES[:needed]:
        seed_id = f"BIDVEX-SEED-{tpl['suffix']}"
        out.append({
            # Mandatory
            "id":              seed_id,
            "title":           tpl["title"],
            "description":     tpl["description"],
            "availability":    "in stock",
            "condition":       "used",
            "price":           "1.00 CAD",
            "link":            BIDVEX_BASE_URL,
            "image_link":      BIDVEX_PLACEHOLDER_IMAGE,
            "brand":           "BidVex Marketplace",
            # Location
            "city":            tpl["city"],
            "region":          tpl["region"],
            "country":         "CA",
            "postal_code":     tpl["postal_code"],
            "neighborhood":    tpl["city"],
            # Optional / recommended
            "google_product_category": "632",
            "custom_label_0":  "lots",
            "custom_label_1":  "individual",
            "custom_label_2":  tpl["region"],
            "custom_label_3":  "test_seed",
            "latitude":        tpl["latitude"],
            "longitude":       tpl["longitude"],
        })
    return out


# Minimum number of items Meta Commerce Manager requires before it will
# ingest the catalog. Padded with seed items via `build_seed_items()`.
META_MIN_CATALOG_ITEMS = 5
