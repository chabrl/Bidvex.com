"""
iter201 — Phase 2 — Vehicle category taxonomy.

Authoritative source of truth for the BidVex 15 vehicle categories per CEO spec.
Used by:
  • Backend: validation in `routes/vehicles.py` create-listing
  • Frontend: `VehicleCategoryGrid.js` icon picker
  • Admin: filtering / reporting

Per CEO constraint #3: "Vehicle Parts & Accessories" is the ONLY category that
does NOT require a dealer licence. Individual sellers may list parts freely.
"""
from typing import Dict, List, Optional


# Each category has:
#   id (stable string id, machine-only),
#   icon (emoji or icon name),
#   label_en, label_fr,
#   subcategories (list of {id, label_en, label_fr}),
#   requires_dealer_license (bool),
#   description_en (short helper text), description_fr.
VEHICLE_CATEGORIES: List[Dict] = [
    {
        "id": "cars_sedans",
        "icon": "🚗",
        "label_en": "Cars & Sedans",
        "label_fr": "Voitures et berlines",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "sedan", "label_en": "Sedan", "label_fr": "Berline"},
            {"id": "coupe", "label_en": "Coupe", "label_fr": "Coupé"},
            {"id": "hatchback", "label_en": "Hatchback", "label_fr": "À hayon"},
            {"id": "convertible", "label_en": "Convertible", "label_fr": "Cabriolet"},
            {"id": "wagon", "label_en": "Station Wagon", "label_fr": "Familiale"},
        ],
    },
    {
        "id": "suvs_crossovers",
        "icon": "🚙",
        "label_en": "SUVs & Crossovers",
        "label_fr": "VUS et multisegments",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "compact_suv", "label_en": "Compact SUV", "label_fr": "VUS compact"},
            {"id": "midsize_suv", "label_en": "Mid-Size SUV", "label_fr": "VUS intermédiaire"},
            {"id": "fullsize_suv", "label_en": "Full-Size SUV", "label_fr": "VUS pleine grandeur"},
            {"id": "luxury_suv", "label_en": "Luxury SUV", "label_fr": "VUS de luxe"},
            {"id": "crossover", "label_en": "Crossover", "label_fr": "Multisegment"},
        ],
    },
    {
        "id": "trucks_pickups",
        "icon": "🛻",
        "label_en": "Trucks & Pickups",
        "label_fr": "Camionnettes et pickups",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "half_ton", "label_en": "Half-Ton Pickup", "label_fr": "Camionnette demi-tonne"},
            {"id": "three_quarter_ton", "label_en": "Three-Quarter Ton", "label_fr": "Trois-quarts de tonne"},
            {"id": "one_ton", "label_en": "One-Ton", "label_fr": "Une tonne"},
            {"id": "work_truck", "label_en": "Work Truck", "label_fr": "Camionnette de travail"},
            {"id": "sport_truck", "label_en": "Sport Truck", "label_fr": "Camionnette sport"},
        ],
    },
    {
        "id": "vans_minivans",
        "icon": "🚐",
        "label_en": "Vans & Minivans",
        "label_fr": "Fourgonnettes et minifourgonnettes",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "cargo_van", "label_en": "Cargo Van", "label_fr": "Fourgonnette utilitaire"},
            {"id": "passenger_van", "label_en": "Passenger Van", "label_fr": "Fourgonnette de passagers"},
            {"id": "minivan", "label_en": "Minivan", "label_fr": "Mini-fourgonnette"},
            {"id": "fullsize_van", "label_en": "Full-Size Van", "label_fr": "Fourgonnette pleine grandeur"},
        ],
    },
    {
        "id": "motorcycles_scooters",
        "icon": "🏍️",
        "label_en": "Motorcycles & Scooters",
        "label_fr": "Motos et scooters",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "sport_bike", "label_en": "Sport Bike", "label_fr": "Moto sportive"},
            {"id": "cruiser", "label_en": "Cruiser", "label_fr": "Custom"},
            {"id": "touring", "label_en": "Touring", "label_fr": "Tourisme"},
            {"id": "dual_sport", "label_en": "Dual-Sport", "label_fr": "Double usage"},
            {"id": "dirt_bike", "label_en": "Dirt Bike", "label_fr": "Moto tout-terrain"},
            {"id": "scooter", "label_en": "Scooter", "label_fr": "Scooter"},
            {"id": "moped", "label_en": "Moped", "label_fr": "Cyclomoteur"},
        ],
    },
    {
        "id": "luxury_exotic",
        "icon": "🏎️",
        "label_en": "Luxury & Exotic",
        "label_fr": "Luxe et exotiques",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "luxury_sedan", "label_en": "Luxury Sedan", "label_fr": "Berline de luxe"},
            {"id": "exotic_sports", "label_en": "Exotic Sports Car", "label_fr": "Voiture sport exotique"},
            {"id": "prestige_suv", "label_en": "Prestige SUV", "label_fr": "VUS de prestige"},
            {"id": "collector", "label_en": "Collector Vehicle", "label_fr": "Véhicule de collection"},
        ],
    },
    {
        "id": "commercial",
        "icon": "🚛",
        "label_en": "Commercial Vehicles",
        "label_fr": "Véhicules commerciaux",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "box_truck", "label_en": "Box Truck", "label_fr": "Camion porteur"},
            {"id": "flatbed", "label_en": "Flatbed", "label_fr": "Plateau"},
            {"id": "tractor_unit", "label_en": "Tractor Unit", "label_fr": "Tracteur routier"},
            {"id": "dump_truck", "label_en": "Dump Truck", "label_fr": "Camion à benne"},
            {"id": "semi_truck", "label_en": "Semi-Truck", "label_fr": "Semi-remorque"},
            {"id": "cube_van", "label_en": "Cube Van", "label_fr": "Camion cube"},
        ],
    },
    {
        "id": "heavy_equipment",
        "icon": "🚜",
        "label_en": "Heavy Equipment & Farm",
        "label_fr": "Équipement lourd et agricole",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "excavator", "label_en": "Excavator", "label_fr": "Excavatrice"},
            {"id": "bulldozer", "label_en": "Bulldozer", "label_fr": "Bulldozer"},
            {"id": "loader", "label_en": "Loader", "label_fr": "Chargeuse"},
            {"id": "backhoe", "label_en": "Backhoe", "label_fr": "Rétrocaveuse"},
            {"id": "forklift", "label_en": "Forklift", "label_fr": "Chariot élévateur"},
            {"id": "tractor", "label_en": "Tractor", "label_fr": "Tracteur"},
            {"id": "farm_equipment", "label_en": "Farm Equipment", "label_fr": "Équipement agricole"},
            {"id": "skid_steer", "label_en": "Skid Steer", "label_fr": "Chargeuse compacte"},
            {"id": "crane", "label_en": "Crane", "label_fr": "Grue"},
        ],
    },
    {
        "id": "boats_watercraft",
        "icon": "🛥️",
        "label_en": "Boats & Watercraft",
        "label_fr": "Bateaux et embarcations",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "motorboat", "label_en": "Motorboat", "label_fr": "Bateau à moteur"},
            {"id": "sailboat", "label_en": "Sailboat", "label_fr": "Voilier"},
            {"id": "pontoon", "label_en": "Pontoon", "label_fr": "Ponton"},
            {"id": "jet_ski", "label_en": "Jet Ski / PWC", "label_fr": "Motomarine"},
            {"id": "fishing_boat", "label_en": "Fishing Boat", "label_fr": "Bateau de pêche"},
            {"id": "yacht", "label_en": "Yacht", "label_fr": "Yacht"},
            {"id": "zodiac", "label_en": "Zodiac", "label_fr": "Zodiac"},
        ],
    },
    {
        "id": "rvs_motorhomes",
        "icon": "🏕️",
        "label_en": "RVs & Motorhomes",
        "label_fr": "VR et autocaravanes",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "class_a", "label_en": "Class A", "label_fr": "Classe A"},
            {"id": "class_b", "label_en": "Class B", "label_fr": "Classe B"},
            {"id": "class_c", "label_en": "Class C", "label_fr": "Classe C"},
            {"id": "travel_trailer", "label_en": "Travel Trailer", "label_fr": "Caravane de voyage"},
            {"id": "fifth_wheel", "label_en": "Fifth Wheel", "label_fr": "Sellette"},
            {"id": "tent_trailer", "label_en": "Tent Trailer", "label_fr": "Tente-roulotte"},
            {"id": "park_model", "label_en": "Park Model", "label_fr": "Modèle de parc"},
        ],
    },
    {
        "id": "trailers",
        "icon": "🚚",
        "label_en": "Trailers",
        "label_fr": "Remorques",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "cargo_trailer", "label_en": "Cargo Trailer", "label_fr": "Remorque utilitaire"},
            {"id": "car_hauler", "label_en": "Car Hauler", "label_fr": "Remorque porte-voitures"},
            {"id": "flatbed_trailer", "label_en": "Flatbed Trailer", "label_fr": "Remorque à plateau"},
            {"id": "horse_trailer", "label_en": "Horse Trailer", "label_fr": "Remorque à chevaux"},
            {"id": "utility_trailer", "label_en": "Utility Trailer", "label_fr": "Remorque utilitaire"},
            {"id": "boat_trailer", "label_en": "Boat Trailer", "label_fr": "Remorque pour bateau"},
        ],
    },
    {
        "id": "atvs_offroad",
        "icon": "🏁",
        "label_en": "ATVs, UTVs & Off-Road",
        "label_fr": "VTT, côtés-côtés et hors-route",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "atv_quad", "label_en": "ATV / Quad", "label_fr": "VTT / Quad"},
            {"id": "utv_sxs", "label_en": "UTV / Side-by-Side", "label_fr": "Côtés-côtés"},
            {"id": "snowmobile", "label_en": "Snowmobile", "label_fr": "Motoneige"},
            {"id": "dirt_bike_off", "label_en": "Off-Road Dirt Bike", "label_fr": "Moto tout-terrain"},
        ],
    },
    {
        "id": "buses_passenger",
        "icon": "🚌",
        "label_en": "Buses & Passenger Transport",
        "label_fr": "Autobus et transport de passagers",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "school_bus", "label_en": "School Bus", "label_fr": "Autobus scolaire"},
            {"id": "coach_bus", "label_en": "Coach Bus", "label_fr": "Autocar"},
            {"id": "minibus", "label_en": "Minibus", "label_fr": "Minibus"},
            {"id": "shuttle_van", "label_en": "Shuttle Van", "label_fr": "Navette"},
            {"id": "transit_bus", "label_en": "Transit Bus", "label_fr": "Autobus urbain"},
        ],
    },
    {
        "id": "electric_hybrid",
        "icon": "⚡",
        "label_en": "Electric & Hybrid",
        "label_fr": "Électrique et hybride",
        "requires_dealer_license": True,
        "subcategories": [
            {"id": "electric_car", "label_en": "Electric Car", "label_fr": "Voiture électrique"},
            {"id": "hybrid", "label_en": "Hybrid", "label_fr": "Hybride"},
            {"id": "plugin_hybrid", "label_en": "Plug-in Hybrid", "label_fr": "Hybride rechargeable"},
            {"id": "electric_truck", "label_en": "Electric Truck", "label_fr": "Camion électrique"},
            {"id": "electric_van", "label_en": "Electric Van", "label_fr": "Fourgon électrique"},
        ],
    },
    # CEO constraint #3 — only category that does NOT require dealer licence.
    {
        "id": "parts_accessories",
        "icon": "🔧",
        "label_en": "Vehicle Parts & Accessories",
        "label_fr": "Pièces et accessoires de véhicules",
        "requires_dealer_license": False,
        "description_en": "Parts do NOT require a dealer licence — individual sellers may list parts freely.",
        "description_fr": "Les pièces ne nécessitent PAS de licence de concessionnaire — les vendeurs individuels peuvent les lister librement.",
        "subcategories": [
            {"id": "engines", "label_en": "Engines", "label_fr": "Moteurs"},
            {"id": "transmissions", "label_en": "Transmissions", "label_fr": "Transmissions"},
            {"id": "body_parts", "label_en": "Body Parts", "label_fr": "Pièces de carrosserie"},
            {"id": "wheels_tires", "label_en": "Wheels & Tires", "label_fr": "Roues et pneus"},
            {"id": "audio", "label_en": "Audio", "label_fr": "Audio"},
            {"id": "performance", "label_en": "Performance Parts", "label_fr": "Pièces de performance"},
        ],
    },
]


def get_category(category_id: str) -> Optional[Dict]:
    for c in VEHICLE_CATEGORIES:
        if c["id"] == category_id:
            return c
    return None


def get_subcategory(category_id: str, subcategory_id: str) -> Optional[Dict]:
    cat = get_category(category_id)
    if not cat:
        return None
    for s in cat.get("subcategories", []):
        if s["id"] == subcategory_id:
            return s
    return None


def category_requires_dealer_license(category_id: str) -> bool:
    """CEO constraint #3 — only `parts_accessories` does NOT require dealer licence.

    Unknown / missing category IDs default to True (safe — block by default).
    """
    cat = get_category(category_id)
    if cat is None:
        return True
    return bool(cat.get("requires_dealer_license", True))
