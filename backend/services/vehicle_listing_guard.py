"""
iter203 P0 Compliance — Vehicle Listing Guard
===============================================
Centralised, non-AI detection of vehicle-shaped marketplace listings that
must be funnelled to the dealer-only Vehicle Auctions pipeline.

The previous narrow whitelist (`category in ["vehicle", "vehicles", ...]`)
let listings slip through when the seller picked "Cars", "Auto", "Truck",
or any other variant. This module is the **hard-coded gate** that runs at
the API layer (sprint requirement #2) — independent of the AI scanner —
so a single seller can never list a vehicle from a non-dealer account
again.

Public API:
  • is_vehicle_listing(category, title, description) → (bool, signals, strength)
  • check_user_is_verified_dealer(db, user_id)        → (bool, user_doc)
  • enforce_vehicle_dealer_gate(db, user, ...)        → raises 403 on violation
  • should_pause_existing_listing(listing, user_doc)  → bool

The same detection logic feeds the AI scanner prompt, the safety watchdog
cron job, and the one-shot cleanup script.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detection vocabularies
# ---------------------------------------------------------------------------
# Words that on their own (in the category) are enough to flag the listing.
# These cover EN + FR variants and common subcategory codes.
VEHICLE_CATEGORY_TOKENS: frozenset[str] = frozenset({
    # English singular / plural
    "vehicle", "vehicles", "car", "cars", "auto", "autos", "automotive",
    "automobile", "automobiles", "truck", "trucks", "pickup", "pickups",
    "motorcycle", "motorcycles", "motorbike", "motorbikes", "moped",
    "scooter", "scooters",
    "suv", "suvs", "crossover", "crossovers", "van", "vans", "minivan",
    "minivans", "rv", "rvs", "camper", "trailer",
    "boat", "boats", "watercraft", "marine", "yacht", "jetski",
    "powersport", "powersports", "atv", "atvs", "snowmobile", "snowmobiles",
    "off-road", "off_road", "offroad",
    "road_vehicles", "vehicle parts", "vehicle_parts", "auto parts",
    "auto_parts", "automotive parts",
    "bus", "buses",
    # French
    "véhicule", "vehicule", "véhicules", "vehicules", "voiture", "voitures",
    "camion", "camions", "moto", "motos", "fourgonnette", "fourgonnettes",
    "utilitaire", "utilitaires", "vtt", "motoneige", "motoneiges",
    "remorque", "embarcation", "embarcations",
})

# Brand names that typically indicate a vehicle when paired with a year
# or other vehicle-shaped fields.
VEHICLE_BRAND_TOKENS: frozenset[str] = frozenset({
    "honda", "toyota", "ford", "chevrolet", "chevy", "gmc", "dodge", "ram",
    "jeep", "chrysler", "nissan", "hyundai", "kia", "mazda", "subaru",
    "volkswagen", "vw", "audi", "bmw", "mercedes", "mercedes-benz",
    "lexus", "acura", "infiniti", "porsche", "jaguar", "land rover",
    "range rover", "volvo", "mini cooper", "tesla", "cadillac", "lincoln",
    "buick", "mitsubishi", "fiat", "alfa romeo", "maserati", "bentley",
    "rolls-royce", "rolls royce", "ferrari", "lamborghini", "aston martin",
    "genesis", "smart", "saturn", "scion", "saab",
    # Powersports / motorcycle
    "ducati", "harley", "harley-davidson", "yamaha", "kawasaki", "suzuki",
    "ktm", "triumph", "indian motorcycle", "polaris", "ski-doo", "ski doo",
    "sea-doo", "sea doo", "can-am", "can am", "arctic cat",
    # Truck / commercial / heavy
    "freightliner", "peterbilt", "kenworth", "international",
    "caterpillar", "komatsu", "john deere", "case ih", "kubota",
})

# Body/style words that increase confidence.
VEHICLE_BODY_TOKENS: frozenset[str] = frozenset({
    "sedan", "coupe", "hatchback", "wagon", "convertible", "roadster",
    "berline", "berlinette", "cabriolet", "familiale",
})

# Strong content tokens that on their own indicate a vehicle listing,
# regardless of category. Title or description match → flagged.
VEHICLE_STRONG_TOKENS: tuple[str, ...] = (
    "vin:", "vin#", "vin number", "vin no", "n.i.v", "niv:",
    "odometer", "odomètre", "kilometrage", "kilométrage", "mileage",
    "engine size", "engine number", "engine no.", "transmission:",
    "horsepower", "cylinder", "cylinders", "cylindrée",
    "fuel type", "type de carburant", "drivetrain",
    "registered with the saaq", "registered with omvic",
    "carfax", "carproof",
)

# Year regex — allow 1950 thru 2099 (covers historic and future model years)
_YEAR_RE = re.compile(r"\b(?:19[5-9]\d|20\d\d)\b")
# "2018 Honda Civic" / "Honda Civic 2018" pattern
_YEAR_BRAND_NEAR_RE = None  # built dynamically


def _normalise(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _haystack_contains(haystack: str, tokens: Iterable[str]) -> Optional[str]:
    for tok in tokens:
        if tok in haystack:
            return tok
    return None


def is_vehicle_listing(
    category: Optional[str],
    title: Optional[str],
    description: Optional[str],
    *,
    threshold: int = 4,
) -> tuple[bool, list[str], int]:
    """
    Detect whether a listing is a road/marine/powersport vehicle.

    Detection rules (additive strength score):
      • Category match               → +5  (auto-flag on its own)
      • Strong content token         → +5  (auto-flag)
      • Year + brand combined        → +5  (auto-flag)
      • Brand alone                  → +2
      • Body type alone              → +1

    A listing is flagged when total strength ≥ `threshold` (default 4).

    Returns (is_vehicle, signals, strength). `signals` is a list of human-
    readable strings used in audit logs and admin moderation UI.
    """
    cat_n = _normalise(category)
    title_n = _normalise(title)
    desc_n = _normalise(description)
    haystack = f" {title_n}  {desc_n} "

    signals: list[str] = []
    strength = 0

    # Category match — strongest signal; substring + token match
    cat_hit = None
    for token in VEHICLE_CATEGORY_TOKENS:
        # Allow either exact category equality or token-presence in compound categories
        # like "vehicles & motors" or "auto parts & accessories"
        if token == cat_n or f" {token} " in f" {cat_n} " or token in cat_n.replace("&", " ").replace("/", " ").split():
            cat_hit = token
            break
    if cat_hit:
        signals.append(f"category:{cat_hit}")
        strength += 5

    # Strong content tokens (title + description)
    strong_hit = _haystack_contains(haystack, VEHICLE_STRONG_TOKENS)
    if strong_hit:
        signals.append(f"strong:{strong_hit.strip()}")
        strength += 5

    # Year + brand co-occurrence in title/description
    year_match = _YEAR_RE.search(haystack)
    brand_match = _haystack_contains(haystack, VEHICLE_BRAND_TOKENS)
    if year_match and brand_match:
        signals.append(f"year:{year_match.group()}+brand:{brand_match}")
        strength += 5
    elif brand_match:
        signals.append(f"brand:{brand_match}")
        strength += 2

    # Body style alone
    body_hit = _haystack_contains(haystack, VEHICLE_BODY_TOKENS)
    if body_hit:
        signals.append(f"body:{body_hit}")
        strength += 1

    return strength >= threshold, signals, strength


# ---------------------------------------------------------------------------
# Dealer-status check
# ---------------------------------------------------------------------------
async def check_user_is_verified_dealer(db, user_id: Optional[str]) -> tuple[bool, dict]:
    """Return (is_verified_dealer, user_projection).

    A user qualifies if any of the following are true:
      • dealer_license_verified == True            (iter201 canonical)
      • opc_permit_verified     == True            (legacy, kept for back-compat)
      • role in {admin, super_admin}                (admins bypass)
    """
    if not user_id:
        return False, {}
    user_doc = await db.users.find_one(
        {"id": user_id},
        {
            "_id": 0,
            "id": 1,
            "seller_type": 1,
            "dealer_license_verified": 1,
            "dealer_license_province": 1,
            "opc_permit_verified": 1,
            "role": 1,
            "email": 1,
        },
    ) or {}
    is_dealer = bool(
        user_doc.get("dealer_license_verified")
        or user_doc.get("opc_permit_verified")
        or (user_doc.get("role") in ("admin", "super_admin"))
    )
    return is_dealer, user_doc


# ---------------------------------------------------------------------------
# Hard 403 enforcer (call from POST /api/listings + /api/multi-item-listings)
# ---------------------------------------------------------------------------
DEALER_ONLY_BILINGUAL_MESSAGE = (
    "Vehicle listings are restricted to licensed dealers only. "
    "Please upgrade your account to a verified provincial dealer account "
    "(OMVIC in ON, AMVIC in AB, VSA in BC, SAAQ in QC, FCAA in SK, etc.). "
    "/ Les annonces de véhicules sont réservées aux concessionnaires licenciés. "
    "Veuillez mettre à niveau votre compte vers un compte de concessionnaire "
    "vérifié (OMVIC en ON, AMVIC en AB, VSA en C.-B., SAAQ au QC, FCAA en SK, etc.)."
)


async def enforce_vehicle_dealer_gate(
    db,
    current_user,
    *,
    category: Optional[str],
    title: Optional[str],
    description: Optional[str],
    surface: str = "single_listing",
) -> Optional[dict]:
    """
    Hard-coded gate. If the listing looks like a vehicle AND the user is
    not a verified dealer, raise HTTPException(403) with the bilingual
    compliance message. Always logs the attempt to `audit_logs`.

    Args:
      • db, current_user — injected by the route
      • category/title/description — listing payload fields
      • surface — "single_listing" | "multi_item_listing" | "multi_item_lot"
                  used purely for audit log filtering.

    Returns:
      • None when not a vehicle (no-op)
      • dict with detection metadata when it IS a vehicle and the user IS
        a verified dealer (caller may attach this to the listing for audit)
    """
    is_vehicle, signals, strength = is_vehicle_listing(category, title, description)
    if not is_vehicle:
        return None

    user_id = getattr(current_user, "id", None)
    is_dealer, user_doc = await check_user_is_verified_dealer(db, user_id)

    audit_base = {
        "user_id": user_id,
        "user_email": user_doc.get("email"),
        "category": category,
        "title": (title or "")[:160],
        "detection_signals": signals,
        "detection_strength": strength,
        "surface": surface,
        "seller_type": user_doc.get("seller_type"),
        "dealer_license_verified": bool(user_doc.get("dealer_license_verified")),
        "opc_permit_verified": bool(user_doc.get("opc_permit_verified")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if is_dealer:
        await db.audit_logs.insert_one({
            **audit_base,
            "action": "vehicle_listing_allowed_dealer",
        })
        return {
            "is_vehicle": True,
            "signals": signals,
            "strength": strength,
            "verified_dealer": True,
        }

    # Block — non-dealer attempting a vehicle listing
    await db.audit_logs.insert_one({
        **audit_base,
        "action": "vehicle_listing_blocked",
    })
    logger.warning(
        "[vehicle_listing_guard] BLOCKED user=%s surface=%s category=%r signals=%s",
        user_id, surface, category, signals,
    )
    raise HTTPException(
        status_code=403,
        detail={
            "error": "vehicle_listing_dealer_required",
            "message": DEALER_ONLY_BILINGUAL_MESSAGE,
            "signals": signals,
        },
    )


# ---------------------------------------------------------------------------
# Existing-listing scan helper (used by watchdog + cleanup script)
# ---------------------------------------------------------------------------
def should_pause_existing_listing(
    listing: dict,
    is_dealer: bool,
) -> tuple[bool, list[str], int]:
    """Return (should_pause, signals, strength) for an already-persisted listing.

    A listing is paused when it looks like a vehicle AND the seller is
    not a verified dealer.
    """
    is_vehicle, signals, strength = is_vehicle_listing(
        listing.get("category"),
        listing.get("title"),
        listing.get("description"),
    )
    if not is_vehicle:
        return False, signals, strength
    if is_dealer:
        return False, signals, strength
    return True, signals, strength
