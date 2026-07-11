"""
iter341 P1 — Google Maps B2B Prospect Finder service.

Places API (New) Text Search — a single request with an Enterprise-tier
field mask returns name/address/phone/website/rating for up to 20 results,
so NO per-result Place Details calls are needed.

Billing model (surface this to admins): ~US$0.035 per UNCACHED query
(Text Search, Enterprise SKU ≈ $35/1000 requests, 20-result cap). Identical
{city+type+radius} queries are served from a 24-hour MongoDB cache at $0.

Feature flag: GOOGLE_MAPS_API_KEY must be set in the Emergent environment
configuration — endpoints return 503 with the prerequisite message until then.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.googleMapsUri",
])

# BidVex business types → Places text queries.
TYPE_QUERIES: Dict[str, str] = {
    "vehicle_dealer": "car dealer OR used car dealer",
    "liquidator": "liquidation store OR moving company",
    "auctioneer": "auction house",
    "storage_facility": "self storage facility",
    "industrial": "general contractor OR warehouse",
}

BILLING_NOTE = (
    "Google Places API cost: ~US$0.035 per uncached search "
    "(1 Text Search, Enterprise field mask, 20-result cap). "
    "Identical city+type searches are cached for 24 hours at no cost."
)

_LEGAL_SUFFIX_RE = re.compile(
    r"\b(inc|inc\.|ltd|ltd\.|ltée|ltee|llc|corp|corp\.|co|co\.|enr|enr\.|limited|incorporated)\b",
    re.IGNORECASE,
)


def maps_flag() -> Dict[str, Any]:
    missing = [] if os.environ.get("GOOGLE_MAPS_API_KEY", "").strip() else ["GOOGLE_MAPS_API_KEY"]
    return {
        "enabled": not missing,
        "missing": missing,
        "prerequisite": (
            "" if not missing else
            "Prospect Finder requires a Google Maps Places API key. Create one in "
            "Google Cloud Console (enable 'Places API (New)' + billing), then add "
            "GOOGLE_MAPS_API_KEY to the Emergent environment configuration."
        ),
    }


def normalize_phone(phone: Optional[str]) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_business_name(name: Optional[str]) -> str:
    s = _LEGAL_SUFFIX_RE.sub("", (name or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


async def search_places(city: str, biz_type: str, max_results: int = 20) -> List[Dict[str, Any]]:
    import httpx
    query = f"{TYPE_QUERIES[biz_type]} in {city}, Canada"
    body = {"textQuery": query, "pageSize": min(20, max_results), "languageCode": "en"}
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
        "X-Goog-FieldMask": FIELD_MASK,
    }
    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.post(PLACES_SEARCH_URL, json=body, headers=headers)
    resp.raise_for_status()
    out: List[Dict[str, Any]] = []
    for p in (resp.json().get("places") or [])[:max_results]:
        phone = p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber") or ""
        out.append({
            "name": (p.get("displayName") or {}).get("text") or "",
            "address": p.get("formattedAddress") or "",
            "phone": phone,
            "website": p.get("websiteUri") or "",
            "rating": p.get("rating"),
            "review_count": p.get("userRatingCount") or 0,
            "place_id": p.get("id") or "",
            "google_maps_url": p.get("googleMapsUri") or "",
        })
    return out


async def flag_already_in_bidvex(db, prospects: List[Dict[str, Any]]) -> None:
    """Data quality — mark prospects whose phone or business name fuzzy-matches
    an existing BidVex account so contractors don't cold-call customers."""
    for p in prospects:
        p["already_in_bidvex"] = False
        clauses = []
        digits = normalize_phone(p.get("phone"))
        if len(digits) == 10:
            clauses.append({"phone": {"$regex": f"{digits}$"}})
        core = normalize_business_name(p.get("name"))
        if len(core) >= 6:
            pattern = re.escape(core)
            clauses.append({"company_name": {"$regex": pattern, "$options": "i"}})
            clauses.append({"name": {"$regex": pattern, "$options": "i"}})
        if not clauses:
            continue
        try:
            hit = await db.users.find_one({"$or": clauses}, {"_id": 0, "id": 1})
            p["already_in_bidvex"] = bool(hit)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[prospect-finder] already_in_bidvex check failed: {e}")
