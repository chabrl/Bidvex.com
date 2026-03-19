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
