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
    # iter353 — Cloudflare origin timeout is ~30s. Bound Places to 12s connect
    # / 15s read so a slow response can never push the outer request past 30s.
    tmo = httpx.Timeout(connect=12.0, read=15.0, write=15.0, pool=15.0)
    async with httpx.AsyncClient(timeout=tmo) as client:
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
    an existing BidVex account so contractors don't cold-call customers.

    iter353 — Batched single-query rewrite. Previously fired N × 3 regex
    scans in a tight loop with no timeout guard — up to 60 unindexed
    scans that could blow past Cloudflare's 30s origin ceiling. Now: one
    `$or` query with .max_time_ms(3000) hard ceiling. Regex on `name`/
    `company_name` is skipped when the normalized business name is too
    short (<6 chars) because it produces too many false positives AND is
    the slowest kind of scan.
    """
    # Default every prospect to false; we'll flip matched ones below.
    for p in prospects:
        p["already_in_bidvex"] = False

    # Build a batched $or with a bounded number of clauses. Cap at 60
    # clauses total (20 prospects × 3 clauses) — Mongo handles this in
    # a single scan and 60 is well below the 100-clause soft limit.
    clauses: list = []
    # Track which prospect each clause maps back to.
    phone_index: Dict[str, int] = {}
    name_index: Dict[str, int] = {}

    for i, p in enumerate(prospects):
        digits = normalize_phone(p.get("phone"))
        if len(digits) == 10:
            phone_index[digits] = i
            clauses.append({"phone": {"$regex": f"{re.escape(digits)}$"}})
        core = normalize_business_name(p.get("name"))
        if len(core) >= 6:
            name_index[core] = i
            pattern = re.escape(core)
            clauses.append({"company_name": {"$regex": pattern, "$options": "i"}})
            clauses.append({"name":         {"$regex": pattern, "$options": "i"}})

    if not clauses:
        return

    try:
        # `max_time_ms` — hard ceiling of 3 s regardless of how slow the
        # scan turns out. Returns whatever partial matches were found so
        # far; on true timeout Mongo raises ExecutionTimeout which we
        # swallow and just leave `already_in_bidvex=False` for everyone.
        cursor = db.users.find(
            {"$or": clauses},
            {"_id": 0, "phone": 1, "company_name": 1, "name": 1, "email": 1},
        ).max_time_ms(3000).limit(200)

        hits = await cursor.to_list(length=200)
        for hit in hits:
            hit_phone = normalize_phone(hit.get("phone"))
            hit_name  = normalize_business_name(hit.get("company_name") or hit.get("name"))
            if hit_phone and hit_phone in phone_index:
                prospects[phone_index[hit_phone]]["already_in_bidvex"] = True
            for core, idx in name_index.items():
                if core and (core in hit_name or hit_name in core):
                    prospects[idx]["already_in_bidvex"] = True
    except Exception as e:  # noqa: BLE001
        # Non-fatal — surface the exception in logs and let every
        # prospect stay flagged False (safe default: contractor may
        # accidentally re-contact an existing customer, but the search
        # ITSELF completes and Cloudflare stays happy).
        logger.warning(f"[prospect-finder] flag_already_in_bidvex bailed: {e}")
