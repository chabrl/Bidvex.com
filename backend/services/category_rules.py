"""
iter217 Phase 5 Hotfix v7 — Category-based business rules.

Source of truth for which listing categories require a licensed broker
for individual buyers (legal constraint), and which commission rate
applies to direct-sale categories.

Per Senior Architect Directive — Task 4:

    Category                  requires_broker   Commission
    ─────────────────────────────────────────────────────
    Vehicles (all types)      TRUE              2.5%
    Restaurant Equipment      FALSE             5.0%
    Bankrupt Inventory        FALSE             4.0%
    General Lots              FALSE             5.0%
    Storage Auctions          FALSE             TBD
    Industrial Equipment      FALSE             4.5%
"""
from __future__ import annotations

from typing import Tuple, Dict

# Substrings that mark a listing as a road vehicle (broker required).
_VEHICLE_TOKENS = (
    "vehicle", "vehicles", "véhicule", "véhicules", "vehicule", "vehicules",
    "car", "cars", "auto", "automobile", "truck", "camion",
    "suv", "van", "motorcycle", "moto", "motorbike",
    "rv", "vr",
)

# Commission rates for non-broker direct categories
COMMISSION_RATES = {
    "vehicles":            0.025,
    "restaurant_equipment": 0.05,
    "bankrupt_inventory":   0.04,
    "general_lots":         0.05,
    "industrial_equipment": 0.045,
    "storage_auctions":     None,    # TBD — Phase 2
    "default":              0.05,
}


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def category_requires_broker(category: str) -> bool:
    """Return True if a listing in this category legally requires a
    licensed broker to mediate between an individual buyer and the
    seller (vehicle categories under OMVIC / SAAQ / AMVIC / VSA).
    """
    cat = _normalize(category)
    if not cat:
        return False
    return any(tok in cat for tok in _VEHICLE_TOKENS)


def commission_rate_for_category(category: str) -> float:
    """Return the BidVex platform commission rate (decimal) for a given
    category. Vehicles use the standard 2.5% (charged to the buyer via
    the broker); other categories use the listed direct-sale rate.
    """
    cat = _normalize(category)
    if category_requires_broker(cat):
        return COMMISSION_RATES["vehicles"]
    for k, v in COMMISSION_RATES.items():
        if v is None or k in ("vehicles", "default"):
            continue
        if k.replace("_", " ") in cat or k.replace("_", "") in cat:
            return v
    return COMMISSION_RATES["default"]


def assert_broker_eligible(category: str, bidder_account_type: str,
                            has_active_relationship: bool) -> Tuple[bool, Dict[str, str]]:
    """Decide if a bidder may place a direct bid on a vehicle category.

    Args:
        category:                listing.category (string)
        bidder_account_type:     "individual" | "broker" | "dealer" | "admin"
        has_active_relationship: True if bidder is binding via a broker

    Returns:
        (ok, error_dict).  If ok=False, error_dict has machine + bilingual
        explanations for the API caller.
    """
    if not category_requires_broker(category):
        return True, {}
    if bidder_account_type in ("broker", "dealer", "admin"):
        return True, {}
    if has_active_relationship:
        # The bid is going to be routed via /api/bid-via-broker; the
        # generic /api/bids endpoint should reject it so the buyer is
        # forced down the legal proxy-bid path.
        return False, {
            "error":      "broker_required_use_proxy",
            "message_en": "Vehicles require a licensed broker. Please use the proxy bid form via your active broker.",
            "message_fr": "Les véhicules nécessitent un courtier licencié. Veuillez utiliser le formulaire d'enchère par procuration via votre courtier actif.",
        }
    return False, {
        "error":      "broker_required",
        "message_en": "A licensed broker is required to bid on vehicles. Find a broker to represent you.",
        "message_fr": "Un courtier licencié est requis pour enchérir sur des véhicules. Trouvez un courtier pour vous représenter.",
        "action_url": "/brokers",
    }


def assert_seller_can_list(category: str, seller_account_type: str) -> Tuple[bool, Dict[str, str]]:
    """Individual (non-broker, non-dealer) sellers cannot list in the
    Vehicles category. They are restricted to non-vehicle categories.
    """
    if not category_requires_broker(category):
        return True, {}
    if seller_account_type in ("broker", "dealer", "admin"):
        return True, {}
    return False, {
        "error":      "individual_cannot_list_vehicles",
        "message_en": "Individual sellers cannot list vehicles. Only licensed dealers / brokers may list in this category.",
        "message_fr": "Les vendeurs particuliers ne peuvent pas inscrire de véhicules. Seuls les concessionnaires / courtiers licenciés peuvent publier dans cette catégorie.",
    }
