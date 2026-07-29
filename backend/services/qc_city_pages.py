"""
iter357 — Quebec city landing page catalog.

12 cities × 2 languages = 24 new SEO landing pages targeting long-tail
Quebec queries like "encan de voitures Montréal", "encan Sherbrooke",
"storage auction Longueuil".

Each city entry has:
    • Unique 130-180 word local-context blurb (EN and FR)
    • H1, meta description, breadcrumb, canonical
    • Bilingual twin cross-reference
    • LocalBusiness NAP (BidVex Inc., Sherbrooke HQ) — same address
      across all pages for GMB verification consistency
    • Referenced from the QC province page's city grid (Adwords copy block)
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


# BidVex NAP — canonical constant. NEVER modify without updating every
# occurrence across sitemap, footer, contact page, and LocalBusiness
# schemas. Google penalizes NAP inconsistency for local-business ranking.
BIDVEX_NAP = {
    "name":     "BidVex Inc.",
    "street":   "761 Rue Chalifoux",
    "city":     "Sherbrooke",
    "region":   "QC",
    "region_full": "Québec",
    "postal":   "J1G 0A8",
    "country":  "CA",
    "phone":    "+14506343099",
    "phone_pretty": "+1 (450) 634-3099",
    "email":    "support@bidvex.com",
    "lat":      45.4041,
    "lng":      -71.9047,
}

# Social profiles for Organization.sameAs (per iter357 spec).
BIDVEX_SAMEAS: List[str] = [
    "https://www.facebook.com/profile.php?id=61583211430354",
    "https://www.linkedin.com/company/bidvex",
    "https://twitter.com/bidvex",
    "https://www.instagram.com/bidvex",
]


# ─── City catalog ──────────────────────────────────────────────────────
# Each entry: (fr_slug, en_slug, fr_name, en_name, province_slug_full)

_QC_VEHICLE_CITIES: List[Tuple[str, str, str, str]] = [
    ("montreal",       "montreal",        "Montréal",       "Montreal"),
    ("quebec-ville",   "quebec-city",     "Québec",         "Quebec City"),
    ("sherbrooke",     "sherbrooke",      "Sherbrooke",     "Sherbrooke"),
    ("laval",          "laval",           "Laval",          "Laval"),
    ("gatineau",       "gatineau",        "Gatineau",       "Gatineau"),
    ("saguenay",       "saguenay",        "Saguenay",       "Saguenay"),
    ("trois-rivieres", "trois-rivieres",  "Trois-Rivières", "Trois-Rivières"),
    ("longueuil",      "longueuil",       "Longueuil",      "Longueuil"),
]

_QC_STORAGE_CITIES: List[Tuple[str, str, str, str]] = [
    ("montreal",     "montreal",     "Montréal",  "Montreal"),
    ("quebec-ville", "quebec-city",  "Québec",    "Quebec City"),
    ("sherbrooke",   "sherbrooke",   "Sherbrooke", "Sherbrooke"),
    ("laval",        "laval",        "Laval",     "Laval"),
]


# ─── City-specific unique copy (French) ────────────────────────────────
# 130-180 words per city referencing genuine local context (dealer scenes,
# regional demographics, cross-border dynamics). Do NOT template these —
# each blurb must be substantively unique or Google flags as thin content.
_FR_CITY_COPY: Dict[str, str] = {
    "montreal": (
        "Le marché de l'enchère automobile en ligne à Montréal est le plus dynamique du "
        "Québec. La métropole compte plus de 300 concessionnaires licenciés SAAQ, "
        "de Saint-Léonard à Verdun en passant par Rosemont, offrant tous les segments : "
        "berlines, VUS familiaux, camions Ford et Ram populaires en région, et modèles "
        "de luxe européens. BidVex vous connecte directement avec ces vendeurs sans les "
        "commissions traditionnelles. Grâce à notre plateforme bilingue, vous pouvez "
        "enchérir de la Rive-Sud ou de Laval sur des véhicules situés au centre-ville, "
        "avec livraison ou retrait organisé en région. Notre système anti-snipe garantit "
        "que les enchères de dernière minute ne vous privent pas d'une bonne affaire. "
        "Que vous cherchiez votre première voiture pour naviguer les rues du Plateau ou "
        "un camion pour un projet de rénovation à Ahuntsic, BidVex Montréal offre les "
        "prix les plus compétitifs au Canada."
    ),
    "quebec-ville": (
        "La capitale nationale et sa région comptent un marché automobile solide, "
        "structuré autour des concessionnaires de Sainte-Foy, Charlesbourg et Beauport. "
        "Les acheteurs de Québec ville privilégient traditionnellement les VUS et les "
        "4×4 pour affronter les hivers rigoureux et les routes de la Côte-Nord. BidVex "
        "s'adapte à ce marché en offrant des filtres détaillés par transmission "
        "intégrale, capacité de remorquage et équipement d'hiver. Nos enchères en ligne "
        "vous permettent d'accéder aussi bien à des véhicules de la Rive-Sud (Lévis, "
        "Saint-Nicolas) qu'à ceux de la région de Portneuf. Le processus 100 % en ligne "
        "élimine les déplacements chez multiple concessionnaires : vous comparez, "
        "enchérissez et concluez depuis votre domicile. Toutes les transactions sont "
        "sécurisées par notre modèle de séquestre Stripe et notre équipe support "
        "bilingue est disponible pour vous accompagner."
    ),
    "sherbrooke": (
        "Sherbrooke, cœur de l'Estrie et région universitaire majeure, présente un "
        "marché automobile particulier : forte demande pour des véhicules d'entrée "
        "de gamme fiables (Honda Civic, Toyota Corolla, Mazda3) portée par la clientèle "
        "étudiante et jeune professionnelle. BidVex, dont le siège social se trouve à "
        "Sherbrooke même, comprend intimement ce marché. Nous mettons en relation des "
        "concessionnaires locaux du secteur King Ouest, Rock Forest et Fleurimont avec "
        "des acheteurs de toute l'Estrie, de Magog à Coaticook. Nos enchères en ligne "
        "sont particulièrement adaptées aux budgets étudiants avec des véhicules à "
        "partir de 3 000 $. La plateforme bilingue reflète parfaitement la réalité "
        "sherbrookoise. Retrait organisé à quelques minutes de l'Université de "
        "Sherbrooke ou de l'Université Bishop's."
    ),
    "laval": (
        "Laval, ville-île au nord de Montréal, est un marché automobile familial dominé "
        "par les VUS 7 places, les minivans (Toyota Sienna, Honda Odyssey) et les "
        "berlines confortables. Avec ses grandes artères comme le boulevard Le "
        "Corbusier et le boulevard des Laurentides, Laval concentre plusieurs "
        "concessionnaires majeurs qui proposent régulièrement leurs surplus d'inventaire "
        "sur BidVex. Notre plateforme est idéale pour les familles lavalloises : "
        "sélection large, filtres par nombre de sièges, historique d'entretien vérifié. "
        "Grâce à la proximité avec Montréal et la Rive-Nord, la logistique de retrait "
        "est simple. BidVex économise aux familles de Chomedey, Sainte-Rose et "
        "Duvernay des milliers de dollars comparativement aux prix concessionnaires "
        "traditionnels."
    ),
    "gatineau": (
        "Gatineau présente une réalité automobile unique au Québec : ville frontalière "
        "avec Ottawa, elle voit une circulation quotidienne intense de fonctionnaires "
        "fédéraux et de travailleurs bi-provinciaux. Le marché favorise les voitures "
        "hybrides et compactes économiques (Toyota Prius, Honda Insight) pour la "
        "traversée quotidienne des ponts. BidVex facilite l'accès aux inventaires "
        "gatinois du secteur Aylmer, Hull et Buckingham. Nos concessionnaires "
        "partenaires acceptent également des transactions transfrontalières avec Ottawa, "
        "sujet à immatriculation SAAQ. La plateforme entièrement bilingue reflète le "
        "caractère unique de l'Outaouais. Support téléphonique bilingue et paiement "
        "sécurisé Stripe conforme aux normes canadiennes."
    ),
    "saguenay": (
        "La région du Saguenay–Lac-Saint-Jean impose des exigences automobiles "
        "particulières : hivers longs, routes montagneuses, distances importantes "
        "entre Chicoutimi, Jonquière, Alma et Roberval. Le marché privilégie les VUS "
        "à traction intégrale, les camions pick-up robustes (Ford F-150, Chevrolet "
        "Silverado) et les voitures avec 4 roues motrices. BidVex ouvre ce marché "
        "régional à toute la province avec livraison organisée depuis les grands "
        "centres. Nos partenaires concessionnaires de Chicoutimi et Alma proposent "
        "régulièrement des véhicules bien entretenus, souvent en excellente condition "
        "malgré leur kilométrage — les Saguenéens prennent soin de leur mécanique. "
        "Enchères 100 % en ligne, retrait ou livraison à convenir."
    ),
    "trois-rivieres": (
        "Trois-Rivières, capitale de la Mauricie, occupe une position stratégique à "
        "mi-chemin entre Montréal et Québec. Le marché automobile local sert autant "
        "les résidents de Cap-de-la-Madeleine et Shawinigan que les acheteurs de "
        "passage. BidVex Trois-Rivières offre une sélection variée : voitures "
        "compactes urbaines, VUS familiaux, camions de travail pour les nombreux "
        "entrepreneurs de la région. Notre système d'enchère anti-snipe et notre "
        "vérification d'identité KYC pour les gagnants sécurisent chaque transaction. "
        "La proximité de l'autoroute 40 rend la logistique de retrait très simple, "
        "que vous veniez de Batiscan, de Bécancour ou du secteur Pointe-du-Lac. "
        "Enchères bilingues, support téléphonique en français et en anglais."
    ),
    "longueuil": (
        "Longueuil, plus grande ville de la Rive-Sud, dessert un marché automobile "
        "de banlieue dense couvrant les arrondissements du Vieux-Longueuil, Saint-Hubert "
        "et Greenfield Park. Les acheteurs longueuillois recherchent principalement des "
        "berlines économiques et des VUS compacts pour naviguer les ponts vers "
        "Montréal (Jacques-Cartier, Champlain, tunnel Louis-H.-La Fontaine). BidVex "
        "réduit dramatiquement le coût d'acquisition en éliminant les marges des "
        "intermédiaires. Nos concessionnaires partenaires de Boucherville, Brossard "
        "et Saint-Lambert affichent régulièrement leur inventaire sur la plateforme. "
        "Retrait organisé à proximité du Métro Longueuil–Université-de-Sherbrooke ou "
        "livraison à domicile disponible."
    ),
}


# ─── City-specific unique copy (English) ───────────────────────────────
_EN_CITY_COPY: Dict[str, str] = {
    "montreal": (
        "Montreal's online vehicle auction market is the most active in Quebec, with "
        "over 300 SAAQ-licensed dealers spread across Saint-Léonard, Verdun, Rosemont, "
        "and downtown Montreal. Every segment is represented: sedans, family SUVs, "
        "popular Ford and Ram pickup trucks, and European luxury models. BidVex "
        "connects buyers directly with these dealers without traditional dealership "
        "markups. Our bilingual platform means South Shore or Laval buyers can bid "
        "on downtown vehicles with organized delivery or pickup arranged. Our "
        "anti-snipe extension prevents last-second bidding wars from locking you out "
        "of a good deal. Whether you're shopping for your first car for Plateau streets "
        "or a work truck for an Ahuntsic renovation, BidVex Montreal offers the most "
        "competitive prices in Canada."
    ),
    "quebec-city": (
        "The national capital region has a strong automotive market centered around "
        "dealerships in Sainte-Foy, Charlesbourg, and Beauport. Quebec City buyers "
        "traditionally prefer SUVs and 4×4s to handle harsh winters and North Shore "
        "road conditions. BidVex adapts to this market with detailed filters by "
        "all-wheel drive, towing capacity, and winter equipment. Our online auctions "
        "give access to both South Shore vehicles (Lévis, Saint-Nicolas) and cars from "
        "the Portneuf region. The 100% online process eliminates trips to multiple "
        "dealers: you compare, bid, and close from home. All transactions are secured "
        "through our Stripe escrow model, with bilingual support available."
    ),
    "sherbrooke": (
        "Sherbrooke, the heart of the Eastern Townships and a major university city, "
        "has a unique automotive market: high demand for reliable entry-level vehicles "
        "(Honda Civic, Toyota Corolla, Mazda3) driven by student and young professional "
        "clientele. BidVex, headquartered in Sherbrooke itself, understands this "
        "market intimately. We connect local dealers from King West, Rock Forest, "
        "and Fleurimont with buyers across the Eastern Townships, from Magog to "
        "Coaticook. Our online auctions are particularly well-suited to student "
        "budgets with vehicles starting at $3,000. The bilingual platform perfectly "
        "reflects Sherbrooke's reality. Pickup organized just minutes from Université "
        "de Sherbrooke or Bishop's University."
    ),
    "laval": (
        "Laval, the island city north of Montreal, is a family-oriented automotive "
        "market dominated by 7-passenger SUVs, minivans (Toyota Sienna, Honda Odyssey), "
        "and comfortable sedans. With major arteries like Le Corbusier Boulevard and "
        "des Laurentides Boulevard, Laval hosts several large dealerships that "
        "regularly list surplus inventory on BidVex. Our platform is ideal for Laval "
        "families: wide selection, seat-count filters, verified maintenance history. "
        "Thanks to the proximity to Montreal and the North Shore, pickup logistics "
        "are simple. BidVex saves families in Chomedey, Sainte-Rose, and Duvernay "
        "thousands compared to traditional dealer prices."
    ),
    "gatineau": (
        "Gatineau has a unique automotive reality in Quebec: as a border city with "
        "Ottawa, it sees daily heavy traffic of federal workers and bi-provincial "
        "commuters. The market favors hybrid and compact economy cars (Toyota Prius, "
        "Honda Insight) for daily bridge crossings. BidVex facilitates access to "
        "Gatineau inventory in the Aylmer, Hull, and Buckingham sectors. Our dealer "
        "partners also accept cross-border transactions with Ottawa, subject to SAAQ "
        "registration. The fully bilingual platform reflects the unique character of "
        "the Outaouais region."
    ),
    "saguenay": (
        "The Saguenay–Lac-Saint-Jean region has specific automotive requirements: "
        "long winters, mountainous roads, significant distances between Chicoutimi, "
        "Jonquière, Alma, and Roberval. The market favors all-wheel-drive SUVs, "
        "robust pickup trucks (Ford F-150, Chevrolet Silverado), and 4WD-equipped "
        "cars. BidVex opens this regional market to the entire province with organized "
        "delivery from major hubs. Our Chicoutimi and Alma dealer partners regularly "
        "list well-maintained vehicles, often in excellent condition despite mileage — "
        "Saguenéens take care of their mechanics. 100% online auctions with pickup or "
        "delivery to be arranged."
    ),
    "trois-rivieres": (
        "Trois-Rivières, capital of the Mauricie region, occupies a strategic position "
        "midway between Montreal and Quebec City. The local automotive market serves "
        "residents of Cap-de-la-Madeleine and Shawinigan as well as pass-through buyers. "
        "BidVex Trois-Rivières offers a varied selection: urban compacts, family "
        "SUVs, work trucks for the region's many contractors. Our anti-snipe auction "
        "system and KYC identity verification for winners secure every transaction. "
        "Proximity to Highway 40 makes pickup logistics very simple whether you're "
        "coming from Batiscan, Bécancour, or the Pointe-du-Lac sector. Bilingual "
        "auctions, phone support in French and English."
    ),
    "longueuil": (
        "Longueuil, the largest South Shore city, serves a dense suburban automotive "
        "market covering the Vieux-Longueuil, Saint-Hubert, and Greenfield Park "
        "boroughs. Longueuil buyers primarily seek economy sedans and compact SUVs to "
        "navigate the bridges to Montreal (Jacques-Cartier, Champlain, Louis-H.-La "
        "Fontaine tunnel). BidVex dramatically reduces acquisition costs by eliminating "
        "middleman margins. Our dealer partners in Boucherville, Brossard, and "
        "Saint-Lambert regularly post inventory on the platform. Pickup organized near "
        "Longueuil–Université-de-Sherbrooke metro station or home delivery available."
    ),
}


def build_qc_vehicle_city_entries() -> Dict[str, Dict[str, Any]]:
    """Return a `_REGIONAL_LANDINGS`-compatible dict for all QC vehicle cities.

    Each city appears TWICE — once with FR slug (`/encheres-vehicules-<slug>`)
    and once with EN slug (`/vehicle-auctions-<slug>`) — with reciprocal
    hreflang cross-references between the two.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for fr_slug, en_slug, fr_name, en_name in _QC_VEHICLE_CITIES:
        fr_path = f"/encheres-vehicules-{fr_slug}"
        en_path = f"/vehicle-auctions-{en_slug}"

        fr_copy = _FR_CITY_COPY.get(fr_slug, "")
        en_copy = _EN_CITY_COPY.get(en_slug, "")

        # FR page
        out[fr_path] = {
            "kind": "qc_city_vehicle",
            "city_fr": fr_name,
            "city_en": en_name,
            "title_fr": f"Enchères de véhicules à {fr_name} | BidVex Québec",
            "desc_fr":  (
                f"Enchérissez sur des véhicules à {fr_name} — voitures, camions et "
                f"VUS de concessionnaires licenciés SAAQ. Plateforme 100 % en ligne, "
                f"bilingue, avec dépôts sécurisés et retrait organisé dans la région "
                f"de {fr_name}."
            ),
            "h1_fr": f"Enchères de véhicules à {fr_name}",
            "body_fr": fr_copy,
            "cta_target": f"/vehicle-auctions?province=QC&city={fr_slug}",
            "twin_en": en_path,
            "lang_only": "fr",
            "province_page": "/encheres-vehicules-quebec",
            "province_page_name": "Enchères de véhicules Québec",
        }
        # EN twin
        out[en_path] = {
            "kind": "qc_city_vehicle",
            "city_fr": fr_name,
            "city_en": en_name,
            "title_en": f"Vehicle Auctions in {en_name}, Quebec | BidVex",
            "desc_en":  (
                f"Bid online on vehicles in {en_name}, Quebec — cars, trucks, "
                f"and SUVs from SAAQ-licensed dealers. Fully online, bilingual "
                f"platform with secure deposits and pickup arranged in the "
                f"{en_name} region."
            ),
            "h1_en": f"Vehicle Auctions in {en_name}, Quebec",
            "body_en": en_copy,
            "cta_target": f"/vehicle-auctions?province=QC&city={fr_slug}",
            "twin_fr": fr_path,
            "province_page": "/vehicle-auctions-quebec",
            "province_page_name": "Vehicle Auctions Quebec",
        }
    return out


def build_qc_storage_city_entries() -> Dict[str, Dict[str, Any]]:
    """Same as `build_qc_vehicle_city_entries` but for storage auctions (4 cities)."""
    out: Dict[str, Dict[str, Any]] = {}
    for fr_slug, en_slug, fr_name, en_name in _QC_STORAGE_CITIES:
        fr_path = f"/encheres-entreposage-{fr_slug}"
        en_path = f"/storage-auctions-{en_slug}"

        out[fr_path] = {
            "kind": "qc_city_storage",
            "city_fr": fr_name,
            "city_en": en_name,
            "title_fr": f"Enchères d'entreposage à {fr_name} | BidVex Québec",
            "desc_fr":  (
                f"Enchérissez sur des casiers d'entreposage abandonnés à {fr_name}. "
                f"Installations vérifiées, enchères 100 % en ligne, retrait organisé "
                f"dans la région de {fr_name}. Plateforme bilingue EN/FR."
            ),
            "h1_fr": f"Enchères de casiers d'entreposage à {fr_name}",
            "body_fr": (
                f"Le marché de l'enchère d'entreposage à {fr_name} offre des "
                f"opportunités uniques aux revendeurs, collectionneurs et amateurs. "
                f"BidVex vous connecte avec les principales installations d'entreposage "
                f"de la région, dont Public Storage, U-Haul et opérateurs locaux "
                f"indépendants. Chaque casier abandonné représente un potentiel "
                f"significatif : meubles, appareils électroniques, articles de "
                f"collection, outillage. Nos enchères 100 % en ligne éliminent la "
                f"nécessité de vous déplacer physiquement. Le retrait s'effectue sur "
                f"place à l'installation dans les 48 heures suivant la fin de l'enchère. "
                f"Consultez les photos préalablement à l'enchère pour évaluer le "
                f"contenu du casier. Support bilingue disponible en français et anglais."
            ),
            "cta_target": f"/storage-auctions?province=QC&city={fr_slug}",
            "twin_en": en_path,
            "lang_only": "fr",
            "province_page": "/encheres-entreposage-quebec",
            "province_page_name": "Enchères d'entreposage Québec",
        }
        out[en_path] = {
            "kind": "qc_city_storage",
            "city_fr": fr_name,
            "city_en": en_name,
            "title_en": f"Storage Auctions in {en_name}, Quebec | BidVex",
            "desc_en":  (
                f"Bid online on abandoned storage lockers in {en_name}, Quebec. "
                f"Verified facilities, 100% online auctions, pickup arranged in "
                f"the {en_name} region. Bilingual EN/FR platform."
            ),
            "h1_en": f"Storage Auctions in {en_name}, Quebec",
            "body_en": (
                f"The storage auction market in {en_name} offers unique opportunities "
                f"for resellers, collectors, and enthusiasts. BidVex connects you with "
                f"major storage facilities in the region, including Public Storage, "
                f"U-Haul, and independent local operators. Each abandoned locker "
                f"represents significant potential: furniture, electronics, "
                f"collectibles, tools. Our 100% online auctions eliminate the need "
                f"to travel physically. Pickup is on-site at the facility within "
                f"48 hours after auction close. Review photos before bidding to "
                f"assess locker contents. Bilingual support available in English "
                f"and French."
            ),
            "cta_target": f"/storage-auctions?province=QC&city={fr_slug}",
            "twin_fr": fr_path,
            "province_page": "/storage-auctions-quebec",
            "province_page_name": "Storage Auctions Quebec",
        }
    return out


def all_qc_city_paths() -> List[str]:
    """Return every QC city landing page path — for sitemap + prerender wiring."""
    paths = list(build_qc_vehicle_city_entries().keys())
    paths.extend(build_qc_storage_city_entries().keys())
    return paths


def qc_province_city_grid_for(kind: str, lang: str) -> List[Dict[str, str]]:
    """Return the anchor-link data structure for the city grid on the
    province page (Adwords copy block). `kind` is "vehicle" or "storage",
    `lang` is "en" or "fr"."""
    if kind == "vehicle":
        cities = _QC_VEHICLE_CITIES
        prefix_fr, prefix_en = "/encheres-vehicules-", "/vehicle-auctions-"
        label_prefix_fr = "Encan de voitures"
        label_prefix_en = "Vehicle Auctions"
    else:
        cities = _QC_STORAGE_CITIES
        prefix_fr, prefix_en = "/encheres-entreposage-", "/storage-auctions-"
        label_prefix_fr = "Enchères d'entreposage"
        label_prefix_en = "Storage Auctions"

    grid = []
    for fr_slug, en_slug, fr_name, en_name in cities:
        if lang == "fr":
            grid.append({
                "href":  f"{prefix_fr}{fr_slug}",
                "label": f"{label_prefix_fr} {fr_name}",
            })
        else:
            grid.append({
                "href":  f"{prefix_en}{en_slug}",
                "label": f"{label_prefix_en} — {en_name}",
            })
    return grid


__all__ = [
    "BIDVEX_NAP",
    "BIDVEX_SAMEAS",
    "build_qc_vehicle_city_entries",
    "build_qc_storage_city_entries",
    "all_qc_city_paths",
    "qc_province_city_grid_for",
]
