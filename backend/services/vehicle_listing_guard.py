"""
iter203 P0 Compliance — Vehicle Listing Guard
===============================================
Centralised, non-AI detection of vehicle-shaped marketplace listings that
must be funnelled to the dealer-only Vehicle Auctions pipeline.

iter338 P0 fix — WORD-BOUNDARY matching + ambiguous-token handling.
The previous implementation used raw substring matching, so the Kia "rio"
model token matched inside "Ontario"/"interior", "x1" matched inside
"17x1..." dimensions and "sti" matched inside "listing". A legitimate
"Bicycles, Furniture & Extra Goods" multi-lot auction was blocked 4 times.
Fixes:
  1. Every token list is matched with word boundaries (services.word_match).
  2. Model names that are common English words ("rio", "fit", "golf",
     "ninja", "1500"…) only auto-flag when a vehicle BRAND is also present.
  3. Ambiguous brands ("ram", "lincoln", "international"…) only count when
     another vehicle signal (model/body/category) co-occurs.
  4. Non-vehicle brand contexts ("Honda generator", "Yamaha keyboard") are
     stripped before brand detection.
  5. Every gate block now dispatches an admin notification so false
     positives are reviewable (previously only a hidden audit log row).

Public API:
  • is_vehicle_listing(category, title, description) → (bool, signals, strength)
  • check_user_is_verified_dealer(db, user_id)        → (bool, user_doc)
  • enforce_vehicle_dealer_gate(db, user, ...)        → raises 403 on violation
  • should_pause_existing_listing(listing, user_doc)  → bool
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException

from services.word_match import first_word_match, has_word

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
# or a model token. Matched with word boundaries.
VEHICLE_BRAND_TOKENS: frozenset[str] = frozenset({
    "honda", "toyota", "ford", "chevrolet", "chevy", "gmc", "dodge",
    "jeep", "chrysler", "nissan", "hyundai", "kia", "mazda", "subaru",
    "volkswagen", "vw", "audi", "bmw", "mercedes", "mercedes-benz",
    "lexus", "acura", "infiniti", "porsche", "jaguar", "land rover",
    "range rover", "volvo", "mini cooper", "tesla", "cadillac",
    "buick", "mitsubishi", "fiat", "alfa romeo", "maserati", "bentley",
    "rolls-royce", "rolls royce", "ferrari", "lamborghini", "aston martin",
    "saturn", "scion", "saab",
    # Powersports / motorcycle
    "ducati", "harley", "harley-davidson", "yamaha", "kawasaki", "suzuki",
    "ktm", "indian motorcycle", "polaris", "ski-doo", "ski doo",
    "sea-doo", "sea doo", "can-am", "can am", "arctic cat",
    # Truck / commercial / heavy
    "freightliner", "peterbilt", "kenworth",
    "caterpillar", "komatsu", "john deere", "case ih", "kubota",
})

# iter338 — Brands that are ALSO common words or major non-vehicle brands
# (RAM memory, Lincoln welders, International shipping, smart TV, Sega
# Genesis, Triumph brand). These count as a brand signal ONLY when another
# vehicle signal (model / body / category) co-occurs.
AMBIGUOUS_BRAND_TOKENS: frozenset[str] = frozenset({
    "ram", "smart", "genesis", "international", "lincoln", "triumph",
})

# iter342 — Conservative vehicle-context nouns for FREE-TEXT co-signals.
# Deliberately excludes words with common non-vehicle meanings in listing
# copy ("pickup" = item collection, "van" = shelving, "boat" = shoes).
CONTENT_VEHICLE_CONTEXT_TOKENS: frozenset[str] = frozenset({
    "motorcycle", "motorcycles", "motorbike", "motorbikes", "moped",
    "scooter", "scooters", "snowmobile", "snowmobiles", "atv", "atvs",
    "suv", "suvs", "minivan", "minivans", "jetski", "watercraft",
    "powersport", "powersports", "moto", "motos", "motoneige",
    "motoneiges", "vtt",
})

# Body/style words that increase confidence.
VEHICLE_BODY_TOKENS: frozenset[str] = frozenset({
    "sedan", "coupe", "hatchback", "wagon", "convertible", "roadster",
    "berline", "berlinette", "cabriolet", "familiale",
})

# iter338 — Non-vehicle product contexts. When a vehicle brand is directly
# followed by one of these product nouns ("Honda generator", "Yamaha
# keyboard"), that occurrence is stripped before brand detection.
_NON_VEHICLE_BRAND_CONTEXT_RE = re.compile(
    r"(?<![a-z0-9])"
    r"(honda|yamaha|suzuki|kawasaki|subaru|kubota|toyota|bmw|ford|john deere)"
    r"\s+"
    r"(generator|generators|génératrice|generatrice|génératrices|"
    r"keyboard|keyboards|piano|pianos|clavier|claviers|"
    r"speaker|speakers|receiver|receivers|amplifier|amplifiers|amp|mixer|"
    r"guitar|guitars|drum|drums|violin|"
    r"lawn ?mower|lawnmower|mower|mowers|tondeuse|"
    r"pressure washer|water pump|pump|snowblower|snow blower|"
    r"sewing machine|forklift)"
    r"(?![a-z0-9])"
)

# iter205/iter338 — Specific model identifiers, split by ambiguity.
#
# UNAMBIGUOUS: names that essentially never appear in a non-vehicle context.
# ANY of these in the title or description auto-flags (+5) on its own.
UNAMBIGUOUS_MODEL_TOKENS: tuple[str, ...] = (
    # Ford
    "f-150", "f150", "f-250", "f250", "f-350", "f350", "f-450", "f450",
    "mustang", "bronco",
    # Chevrolet / GMC
    "silverado", "camaro", "corvette",
    # Ram
    "ram 1500", "ram 2500", "ram 3500", "ram1500", "ram2500", "ram3500",
    "ram-1500",
    # Jeep
    "grand cherokee",
    # Toyota
    "tacoma trd", "rav4", "rav 4", "4runner", "land cruiser", "corolla",
    "camry", "prius", "venza", "yaris",
    # Honda
    "cr-v", "crv", "hr-v", "hrv", "ridgeline",
    # Hyundai / Kia
    "elantra", "veloster", "sportage", "sorento",
    # Nissan / Infiniti
    "altima", "maxima", "sentra", "qashqai", "qx50", "qx60", "qx80",
    # Mazda / Subaru
    "mazda3", "mazda 3", "mazda6", "mazda 6", "cx-3", "cx-30", "cx-5",
    "cx-9", "cx-50", "miata", "mx-5",
    "impreza", "wrx", "eclipse cross",
    # Volkswagen
    "jetta", "passat", "tiguan", "id.4",
    # BMW / Mercedes
    "320i", "330i", "335i", "340i", "330e",
    "c-class", "e-class", "s-class",
    # Lexus
    "rx350", "rx 350", "nx300", "is300", "is350", "es350", "gs350",
    "gx460", "lx570",
    # Volvo / Tesla / Cadillac
    "xc40", "xc60", "xc90",
    "model 3", "model y", "model s", "model x", "cybertruck", "escalade",
    # Motorcycles / powersports
    "cbr", "yzf", "z900", "mt-07", "mt-09", "harley", "softail",
    "sportster", "road king", "street glide",
    "polaris rzr", "rzr", "ranger 1000", "ranger 570",
    "ski-doo", "sea-doo", "skandic",
)

# AMBIGUOUS: model names that double as common English/French words, place
# names, paper sizes, screw sizes, CPU names, kitchen/camera/PC brands…
# ("rio" → Ontario is NOT a match anymore thanks to word boundaries, but
# "Rio" alone can still legitimately appear — e.g. "Rio-themed decor").
# These auto-flag (+5) ONLY when a vehicle brand is also present.
AMBIGUOUS_MODEL_TOKENS: tuple[str, ...] = (
    # Ford
    "explorer", "escape", "edge", "expedition", "maverick", "transit",
    "ranger",
    # Chevrolet / GMC
    "sierra", "colorado", "canyon", "tahoe", "suburban", "yukon", "blazer",
    "equinox", "trailblazer", "malibu", "impala", "trax",
    # Dodge
    "charger", "challenger", "durango", "journey", "caravan",
    # Jeep
    "wrangler", "cherokee", "compass", "patriot", "renegade", "gladiator",
    # Toyota
    "tacoma", "tundra", "highlander", "sequoia", "avalon", "sienna",
    "matrix",
    # Honda
    "civic", "accord", "passport", "pilot", "odyssey", "fit", "insight",
    # Hyundai / Kia
    "sonata", "tucson", "santa fe", "santafe", "kona", "palisade",
    "rio", "forte", "soul", "carnival", "telluride", "stinger",
    # Nissan
    "versa", "leaf", "rogue", "murano", "pathfinder", "frontier", "titan",
    "armada", "kicks",
    # Subaru / Mitsubishi
    "outback", "forester", "legacy", "ascent", "sti", "lancer",
    "outlander", "rvr",
    # Volkswagen / Audi
    "golf", "atlas", "taos", "gli", "gti",
    "a3", "a4", "a5", "a6", "a7", "a8", "q3", "q5", "q7", "q8", "rs5", "rs7",
    # BMW (M3 screws, X1 dimensions, i7 CPUs)
    "m3", "m4", "m5", "x1", "x3", "x5", "x7", "i3", "i4", "i7",
    # Mercedes (C300 = Canon cinema camera)
    "c300", "c-300", "e350", "e-350", "glc", "gle", "glk", "gla", "amg",
    # Acura / Volvo codes
    "tlx", "rdx", "mdx", "ilx", "nsx",
    "s60", "s90", "v60", "v90",
    # Cadillac / Lincoln
    "cts", "ats", "xt4", "xt5", "xt6", "navigator", "aviator",
    "nautilus", "corsair",
    # Plain pickup numbers
    "1500", "2500", "3500",
    # Motorcycles / powersports (Ninja blenders, Canon Rebel, Vulcan ranges)
    "ninja", "r1", "r6", "fat boy", "vulcan", "shadow", "rebel",
    "summit", "rxt", "rxp", "gtx", "spark",
)

# Strong content tokens that on their own indicate a vehicle listing,
# regardless of category. Title or description match → flagged.
VEHICLE_STRONG_TOKENS: tuple[str, ...] = (
    "vin:", "vin#", "vin number", "vin no", "n.i.v", "niv:",
    "odometer", "odomètre", "kilometrage", "kilométrage", "mileage",
    "engine size", "engine number", "engine no.", "transmission:",
    "horsepower", "cylindrée",
    "fuel type", "type de carburant", "drivetrain",
    "registered with the saaq", "registered with omvic",
    "carfax", "carproof",
)

# Year regex — allow 1950 thru 2099 (covers historic and future model years)
_YEAR_RE = re.compile(r"\b(?:19[5-9]\d|20\d\d)\b")

# iter342 P0 — "cylinder" alone is NOT a vehicle signal (glass cylinder
# vases, hydraulic cylinders, propane cylinders blocked Alex's vase).
# Only numeric ENGINE phrasing counts: "4 cylinder", "6-cylinder", "8 cyl".
_ENGINE_CYL_RE = re.compile(
    r"\b(?:\d{1,2}|four|six|eight|ten|twelve|quatre|huit|douze)[\s-]?(?:cylinder|cylindre)s?\b"
)


def _normalise(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def is_vehicle_listing(
    category: Optional[str],
    title: Optional[str],
    description: Optional[str],
    *,
    threshold: int = 4,
) -> tuple[bool, list[str], int]:
    """
    Detect whether a listing is a road/marine/powersport vehicle.

    Detection rules (additive strength score, iter338 word-boundary rules):
      • Category token match              → +5  (auto-flag on its own)
      • Strong content token              → +5  (auto-flag — VIN / odometer / etc.)
      • Unambiguous model token           → +5  (auto-flag — "f-150", "silverado")
      • Ambiguous model + brand present   → +5  (auto-flag — "kia rio", "honda civic")
      • Ambiguous model alone             → +0  (weak signal, logged only)
      • Year + brand in TITLE             → +5  (auto-flag — "2018 Honda Civic")
      • Year + brand in description only  → +3
      • Brand in TITLE alone              → +3
      • Brand in description alone        → +2
      • Body type alone                   → +1

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

    # Category match — strongest signal; word-boundary token match
    cat_hit = first_word_match(cat_n, VEHICLE_CATEGORY_TOKENS)
    if cat_hit:
        signals.append(f"category:{cat_hit}")
        strength += 5

    # Strong content tokens (title + description)
    strong_hit = first_word_match(haystack, VEHICLE_STRONG_TOKENS)
    if strong_hit:
        signals.append(f"strong:{strong_hit.strip()}")
        strength += 5
    else:
        # iter342 — numeric engine-cylinder phrasing ("4-cylinder engine")
        cyl_hit = _ENGINE_CYL_RE.search(haystack)
        if cyl_hit:
            signals.append(f"strong:{cyl_hit.group().strip()}")
            strength += 5

    # Brand detection — strip non-vehicle contexts ("Honda generator") first
    brand_haystack = _NON_VEHICLE_BRAND_CONTEXT_RE.sub(" ", haystack)
    brand_title = _NON_VEHICLE_BRAND_CONTEXT_RE.sub(" ", title_n)
    brand_match = first_word_match(brand_haystack, VEHICLE_BRAND_TOKENS)

    # Unambiguous model identifiers — auto-flag alone
    model_hit = first_word_match(haystack, UNAMBIGUOUS_MODEL_TOKENS)
    if model_hit:
        signals.append(f"model:{model_hit.strip()}")
        strength += 5

    # iter342 — vehicle-category words in the CONTENT ("Ninja motorcycle",
    # "Vulcan scooter") count as vehicle context for ambiguous models, so
    # "Ninja motorcycle 2019" flags while "Ninja blender" never does.
    content_cat_hit = first_word_match(haystack, CONTENT_VEHICLE_CONTEXT_TOKENS)

    # Ambiguous model identifiers — only with a brand/vehicle-context co-signal
    amb_model_hit = first_word_match(haystack, AMBIGUOUS_MODEL_TOKENS)

    # Ambiguous brands ("ram", "lincoln"…) need an UNAMBIGUOUS co-signal
    # (unambiguous model / body / category). Ambiguous models must NOT
    # promote ambiguous brands — "Corsair RAM" + "i7" is a PC, not a truck.
    if not brand_match:
        amb_brand = first_word_match(brand_haystack, AMBIGUOUS_BRAND_TOKENS)
        if amb_brand and (
            model_hit or cat_hit
            or first_word_match(haystack, VEHICLE_BODY_TOKENS)
        ):
            brand_match = amb_brand

    if amb_model_hit:
        if brand_match or content_cat_hit:
            signals.append(f"model:{amb_model_hit.strip()}")
            strength += 5
        else:
            # Weak signal — logged for audit but contributes no strength.
            signals.append(f"model-weak:{amb_model_hit.strip()}")

    # Year + brand co-occurrence
    year_match = _YEAR_RE.search(haystack)
    if year_match and brand_match:
        if has_word(brand_title, brand_match):
            signals.append(f"year:{year_match.group()}+brand:{brand_match}")
            strength += 5
        else:
            # Year + brand only in the description ("purchased in 2021,
            # comes with Yamaha receiver") — suspicious but not conclusive.
            signals.append(f"year:{year_match.group()}+brand-in-desc:{brand_match}")
            strength += 3
    elif brand_match:
        # iter205 — brand-in-title is a stronger signal than brand-in-description.
        if has_word(brand_title, brand_match):
            signals.append(f"brand-in-title:{brand_match}")
            strength += 3
        else:
            signals.append(f"brand:{brand_match}")
            strength += 2

    # Body style alone
    body_hit = first_word_match(haystack, VEHICLE_BODY_TOKENS)
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
    compliance message. Always logs the attempt to `audit_logs` AND
    (iter338) dispatches an admin notification so false positives are
    reviewable by a human.

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

    # iter338 — Admin notification (in-app + deduped email) on EVERY block
    # so a human can review possible false positives. Best-effort.
    try:
        from services.compliance_notifier import notify_admins_of_violation
        await notify_admins_of_violation(
            db,
            kind="blocked_at_gate",
            listing={
                "id": None,
                "title": title,
                "category": category,
                "seller_id": user_id,
            },
            signals=signals,
            seller_email=user_doc.get("email"),
            extra={"surface": surface, "detection_strength": strength,
                   "gate": "vehicle_gate"},
        )
    except Exception as notify_exc:  # noqa: BLE001
        logger.warning("[vehicle_listing_guard] admin notify failed: %s", notify_exc)

    from services.block_messages import BLOCK_MESSAGES
    raise HTTPException(
        status_code=403,
        detail={
            "error": "vehicle_listing_dealer_required",
            "block_reason": "vehicle_dealer_required",
            "message": DEALER_ONLY_BILINGUAL_MESSAGE,
            "message_en": BLOCK_MESSAGES["vehicle_dealer_required"]["en"],
            "message_fr": BLOCK_MESSAGES["vehicle_dealer_required"]["fr"],
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
