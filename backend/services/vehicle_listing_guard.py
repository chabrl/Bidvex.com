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

# iter205 P0 — Specific model identifiers. ANY of these in the title or
# description IS sufficient on its own to flag the listing — these are
# unambiguous vehicle model names that don't appear in any non-vehicle
# context. This closes the "ford f150" / "honda civic" gap where the user
# omitted the model year.
VEHICLE_MODEL_TOKENS: tuple[str, ...] = (
    # Ford
    "f-150", "f150", "f-250", "f250", "f-350", "f350", "f-450", "f450",
    "mustang", "ranger", "explorer", "escape", "edge", "expedition",
    "bronco", "maverick", "transit",
    # Chevrolet / GMC
    "silverado", "sierra", "colorado", "canyon", "camaro", "corvette",
    "tahoe", "suburban", "yukon", "blazer", "equinox", "trailblazer",
    "malibu", "impala", "trax",
    # Ram / Dodge
    "ram 1500", "ram 2500", "ram 3500", "ram1500", "ram2500", "ram3500",
    "ram-1500", "charger", "challenger", "durango", "journey", "caravan",
    # Jeep
    "wrangler", "grand cherokee", "cherokee", "compass", "patriot",
    "renegade", "gladiator",
    # Toyota
    "tacoma", "tundra", "tacoma trd", "rav4", "rav 4", "highlander",
    "4runner", "land cruiser", "sequoia", "corolla", "camry", "avalon",
    "prius", "sienna", "venza", "matrix", "yaris",
    # Honda
    "civic", "accord", "cr-v", "crv", "cr v", "hr-v", "hrv", "passport",
    "pilot", "ridgeline", "odyssey", "fit", "insight",
    # Hyundai / Kia
    "elantra", "sonata", "tucson", "santa fe", "santafe", "kona",
    "palisade", "veloster",
    "rio", "forte", "soul", "sportage", "sorento", "telluride", "stinger",
    "carnival",
    # Nissan / Infiniti
    "altima", "maxima", "sentra", "versa", "leaf", "rogue", "murano",
    "pathfinder", "frontier", "titan", "armada", "kicks", "qashqai",
    "qx50", "qx60", "qx80",
    # Mazda / Subaru / Mitsubishi
    "mazda3", "mazda 3", "mazda6", "mazda 6", "cx-3", "cx-30", "cx-5",
    "cx-9", "cx-50", "miata", "mx-5",
    "outback", "forester", "impreza", "legacy", "ascent", "wrx", "sti",
    "lancer", "outlander", "eclipse cross", "rvr",
    # Volkswagen / Audi / BMW / Mercedes
    "jetta", "passat", "golf", "tiguan", "atlas", "taos", "id.4", "gli",
    "gti",
    "a3", "a4", "a5", "a6", "a7", "a8", "q3", "q5", "q7", "q8", "rs5", "rs7",
    "320i", "330i", "335i", "340i", "m3", "m4", "m5", "x1", "x3", "x5",
    "x7", "330e", "i3", "i4", "i7",
    "c-class", "c300", "c-300", "e-class", "e350", "e-350", "s-class",
    "glc", "gle", "glk", "gla", "amg",
    # Lexus / Acura / Volvo / Tesla / Cadillac / Lincoln
    "rx350", "rx 350", "nx300", "is300", "is350", "es350", "gs350",
    "gx460", "lx570",
    "tlx", "rdx", "mdx", "ilx", "nsx",
    "xc40", "xc60", "xc90", "s60", "s90", "v60", "v90",
    "model 3", "model y", "model s", "model x", "cybertruck",
    "escalade", "cts", "ats", "xt4", "xt5", "xt6",
    "navigator", "aviator", "nautilus", "corsair",
    # Pickup truck quick patterns (super common in marketplace abuse)
    "1500", "2500", "3500",  # paired with brand → strong
    # Powersports / motorcycles common models
    "ninja", "cbr", "yzf", "r1", "r6", "z900", "mt-07", "mt-09",
    "harley", "softail", "sportster", "fat boy", "road king", "street glide",
    "vulcan", "shadow", "rebel",
    "polaris rzr", "rzr", "ranger 1000", "ranger 570",
    "ski-doo", "renegade", "summit", "skandic",
    "sea-doo", "rxt", "rxp", "gtx", "spark",
)

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
      • Strong content token         → +5  (auto-flag — VIN / odometer / etc.)
      • Year + brand combined        → +5  (auto-flag — "2018 Honda Civic")
      • Brand + model token combined → +5  (auto-flag — "ford f150" with no year)
      • Specific model token alone   → +5  (auto-flag — VIN-like uniqueness)
      • Brand in TITLE alone         → +3  (raised in iter205 from +2)
      • Brand in description alone   → +2
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

    # iter205 P0 — Specific model identifiers (closes the "ford f150" gap).
    # Match in TITLE or DESCRIPTION. A model identifier is unambiguous —
    # nobody titles a non-vehicle "f-150" or "silverado".
    model_hit = _haystack_contains(haystack, VEHICLE_MODEL_TOKENS)
    if model_hit:
        signals.append(f"model:{model_hit.strip()}")
        strength += 5

    # Year + brand co-occurrence in title/description
    year_match = _YEAR_RE.search(haystack)
    brand_match = _haystack_contains(haystack, VEHICLE_BRAND_TOKENS)
    if year_match and brand_match:
        signals.append(f"year:{year_match.group()}+brand:{brand_match}")
        strength += 5
    elif brand_match:
        # iter205 — brand-in-title is a stronger signal than brand-in-description.
        # "ford" or "honda" appearing in the TITLE almost always means a vehicle;
        # whereas in description it could be incidental ("comes with Honda generator").
        if brand_match in title_n:
            signals.append(f"brand-in-title:{brand_match}")
            strength += 3
        else:
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

    iter205 P0 — STRICT compliance policy: a user qualifies as a verified
    dealer ONLY if they hold a verified provincial dealer licence. Admin
    role does NOT bypass this check — staff who want to list vehicles must
    verify a real dealer licence through the same pipeline as everyone
    else. Closes the loophole the user reported (their own admin account
    bypassing the gate).
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
