"""
BidVex — Geo-Sort Helper
Adjacency map for Canadian provinces/territories used to sort listings
"nearby first" based on the buyer's province vs the seller's province.

Priority: same province → adjacent → other.
"""

ADJACENT_PROVINCES = {
    "QC": ["ON", "NB", "NL"],
    "ON": ["QC", "MB"],
    "MB": ["ON", "SK"],
    "SK": ["MB", "AB"],
    "AB": ["SK", "BC"],
    "BC": ["AB"],
    "NB": ["QC", "NS", "PEI", "PE"],
    "NS": ["NB", "PEI", "PE"],
    "PEI": ["NS", "NB"],
    "PE": ["NS", "NB"],
    "NL": ["QC"],
    "YT": ["BC"],
    "NT": ["AB", "BC", "SK"],
    "NU": ["NT", "MB"],
}


def get_adjacent_provinces(province: str) -> list:
    """Return list of provinces adjacent to `province`. Empty if unknown."""
    if not province:
        return []
    return ADJACENT_PROVINCES.get(province.upper(), [])


def geo_priority_pipeline_stage(buyer_province: str) -> dict:
    """
    Returns a Mongo `$addFields` stage that tags every listing with a
    `geo_priority` integer:
        0 = same province as buyer
        1 = adjacent province
        2 = anywhere else
    Use it before `$sort` to bubble nearby listings to the top.
    """
    bp = (buyer_province or "").upper()
    return {
        "$addFields": {
            "geo_priority": {
                "$switch": {
                    "branches": [
                        {"case": {"$eq": ["$seller_province", bp]}, "then": 0},
                        {"case": {"$in": ["$seller_province", get_adjacent_provinces(bp)]}, "then": 1},
                    ],
                    "default": 2,
                }
            }
        }
    }


def geo_priority_value(seller_province: str, buyer_province: str) -> int:
    """In-Python equivalent for sorting in-memory dicts (post-aggregation merges)."""
    sp = (seller_province or "").upper()
    bp = (buyer_province or "").upper()
    if not sp or not bp:
        return 2
    if sp == bp:
        return 0
    if sp in get_adjacent_provinces(bp):
        return 1
    return 2
