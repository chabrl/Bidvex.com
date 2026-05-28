"""
BidVex Shared Utility Functions
Pure helper functions used across multiple route files.
"""

from datetime import datetime, timezone
from typing import Dict


# ========== MARKETPLACE SETTINGS ==========

DEFAULT_MARKETPLACE_SETTINGS = {
    "id": "marketplace_settings",
    "allow_all_users_multi_lot": True,
    "require_approval_new_sellers": False,
    "max_active_auctions_per_user": 20,
    "max_lots_per_auction": 50,
    "minimum_bid_increment": 1.0,
    "enable_anti_sniping": True,
    "anti_sniping_window_minutes": 2,
    "enable_buy_now": True,
    "updated_at": None,
    "updated_by": None
}


async def get_marketplace_settings(db):
    """Fetch marketplace settings from database, or return defaults."""
    settings = await db.settings.find_one({"id": "marketplace_settings"}, {"_id": 0})
    if not settings:
        settings = {**DEFAULT_MARKETPLACE_SETTINGS, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.settings.insert_one(settings)
    return settings


# ========== TIMEZONE HELPERS ==========

def get_epoch_timestamp(dt) -> int:
    """Convert datetime to Unix epoch timestamp (seconds since 1970-01-01 UTC)."""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def get_server_timestamp() -> int:
    """Get current server time as Unix epoch timestamp."""
    return int(datetime.now(timezone.utc).timestamp())


# ========== BID INCREMENT LOGIC ==========

def get_minimum_increment_tiered(current_bid: float) -> float:
    """Tiered increment schedule (Option A)."""
    if current_bid < 100:
        return 5
    elif current_bid < 500:
        return 10
    elif current_bid < 1000:
        return 25
    elif current_bid < 5000:
        return 50
    elif current_bid < 10000:
        return 100
    elif current_bid < 50000:
        return 250
    elif current_bid < 100000:
        return 500
    else:
        return 1000


def get_minimum_increment_simplified(current_bid: float) -> float:
    """Simplified increment schedule (Option B)."""
    if current_bid <= 100:
        return 1
    elif current_bid <= 1000:
        return 5
    elif current_bid <= 10000:
        return 25
    else:
        return 100


def get_minimum_increment(auction: dict, current_bid: float) -> float:
    """Get minimum increment based on auction's increment_option."""
    increment_option = auction.get("increment_option", "tiered")
    if increment_option == "simplified":
        return get_minimum_increment_simplified(current_bid)
    else:
        return get_minimum_increment_tiered(current_bid)


# ========== CURRENCY / TAX HELPERS ==========

def detect_currency_from_location(city: str = None, region: str = None, country: str = None) -> str:
    """Detect currency based on user location. Returns 'CAD' or 'USD'."""
    if country:
        country_lower = country.lower()
        if 'united states' in country_lower or 'usa' in country_lower or 'us' == country_lower:
            return 'USD'
        if 'canada' in country_lower:
            return 'CAD'

    canadian_provinces = [
        'alberta', 'british columbia', 'manitoba', 'new brunswick',
        'newfoundland', 'labrador', 'northwest territories', 'nova scotia',
        'nunavut', 'ontario', 'prince edward island', 'quebec', 'saskatchewan', 'yukon',
        'ab', 'bc', 'mb', 'nb', 'nl', 'nt', 'ns', 'nu', 'on', 'pe', 'qc', 'sk', 'yt'
    ]

    us_states = [
        'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
        'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
        'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
        'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota', 'mississippi',
        'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire', 'new jersey',
        'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio', 'oklahoma',
        'oregon', 'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
        'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
        'west virginia', 'wisconsin', 'wyoming'
    ]

    if region:
        region_lower = region.lower()
        if any(province in region_lower for province in canadian_provinces):
            return 'CAD'
        if any(state in region_lower for state in us_states):
            return 'USD'

    return 'CAD'


def get_tax_rates_for_currency(currency: str) -> Dict[str, float]:
    """Get applicable tax rates based on currency."""
    if currency == 'CAD':
        return {"tax_rate_gst": 5.0, "tax_rate_qst": 9.975}
    else:
        return {"tax_rate_gst": 0.0, "tax_rate_qst": 0.0}

from typing import Dict, Optional


# Locked iter237 city → {lat, lng} table. Lowercase, accent-stripped keys.
CITY_COORDS: Dict[str, Dict[str, float]] = {
    "sherbrooke":     {"lat": 45.4042, "lng": -71.8929},
    "montreal":       {"lat": 45.5017, "lng": -73.5673},
    "quebec city":    {"lat": 46.8139, "lng": -71.2080},
    "quebec":         {"lat": 46.8139, "lng": -71.2080},   # alias
    "laval":          {"lat": 45.6066, "lng": -73.7124},
    "gatineau":       {"lat": 45.4765, "lng": -75.7013},
    "longueuil":      {"lat": 45.5315, "lng": -73.5185},
    "saguenay":       {"lat": 48.4284, "lng": -71.0537},
    "levis":          {"lat": 46.8032, "lng": -71.1756},
    "trois-rivieres": {"lat": 46.3432, "lng": -72.5428},
    "trois rivieres": {"lat": 46.3432, "lng": -72.5428},   # alias (no hyphen)
    "drummondville":  {"lat": 45.8833, "lng": -72.4833},
    "saint-jerome":   {"lat": 45.7749, "lng": -74.0001},
    "saint jerome":   {"lat": 45.7749, "lng": -74.0001},   # alias
    "granby":         {"lat": 45.4001, "lng": -72.7335},
    "sorel-tracy":    {"lat": 46.0334, "lng": -73.1168},
    "sorel tracy":    {"lat": 46.0334, "lng": -73.1168},   # alias
    "toronto":        {"lat": 43.6532, "lng": -79.3832},
    "ottawa":         {"lat": 45.4215, "lng": -75.6919},
    "vancouver":      {"lat": 49.2827, "lng": -123.1207},
    "calgary":        {"lat": 51.0447, "lng": -114.0719},
    "edmonton":       {"lat": 53.5461, "lng": -113.4938},
}


def _normalise(city: Optional[str]) -> str:
    if not city:
        return ""
    return (
        city.strip()
            .lower()
            .replace("é", "e").replace("è", "e").replace("ê", "e")
            .replace("à", "a").replace("â", "a")
            .replace("ô", "o").replace("ï", "i").replace("î", "i")
            .replace("ç", "c")
    )


def resolve_city_coords(city: Optional[str]) -> Optional[Dict[str, float]]:
    """Return {'lat': float, 'lng': float} or None."""
    key = _normalise(city)
    return CITY_COORDS.get(key)


def build_geo_point(
    city: Optional[str],
    *,
    province: Optional[str] = None,
) -> Optional[Dict]:
    """Build a GeoJSON Point payload for the `geo` top-level field.

    Returns:
      {
        "type": "Point",
        "coordinates": [lng, lat],
        "city": "<original city>",
        "province": "<original province>" | "",
      }
    or None when the city is not in the lookup table — caller should
    decide whether to write a sentinel `{type: None, coordinates: None}`
    or skip the field entirely.

    NOTE: iter237 — A separate top-level `geo` field is used (instead of
    rewriting the existing `location: str` field) so the human-readable
    address displays elsewhere in the UI remain untouched. The 2dsphere
    index is on `geo` and all $geoWithin queries target `geo`.
    """
    resolved = resolve_city_coords(city)
    if not resolved:
        return None
    return {
        "type": "Point",
        "coordinates": [resolved["lng"], resolved["lat"]],
        "city": (city or "").strip(),
        "province": (province or "").strip(),
    }


__all__ = ["CITY_COORDS", "resolve_city_coords", "build_geo_point"]
