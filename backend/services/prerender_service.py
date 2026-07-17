"""
iter354 — Prerender service (SSR-for-crawlers).

Called by GET /api/prerender/{path} and by the ingress-override middleware
when a bot User-Agent hits a public route. Returns fully-rendered HTML with
per-route <title>, meta description, canonical, hreflang, Open Graph +
Twitter card tags, and Schema.org JSON-LD.

Real users bypass this — they still hit the SPA build served by the frontend
container. This module ONLY exists to give crawlers a payload that isn't
`<div id="root"></div>`.
"""
from __future__ import annotations

import html as _html
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.seo_jsonld import (
    CANONICAL_HOST,
    breadcrumb_ld,
    event_ld,
    faqpage_ld,
    local_business_ld,
    organization_ld,
    product_offer_ld,
    vehicle_ld,
    website_ld,
)
from services.qc_city_pages import (
    build_qc_vehicle_city_entries,
    build_qc_storage_city_entries,
    qc_province_city_grid_for,
)
from services.platform_stats import get_platform_stats
from services.press_release import (
    build_press_release_entries,
    news_article_ld_for,
    press_release_paths,
    PRESS_RELEASE_PDF_URL,
)

logger = logging.getLogger(__name__)

# Jinja2 env — templates live under backend/templates/prerender/
_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "prerender")
_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def _canonical(path: str, lang: str = "en") -> str:
    """Full canonical URL for `path`, with optional `?lang=` for hreflang alternate.
    Path MUST start with '/'."""
    if not path.startswith("/"):
        path = "/" + path
    if lang == "default":
        return f"{CANONICAL_HOST}{path}"
    return f"{CANONICAL_HOST}{path}?lang={lang}" if lang in ("en", "fr") else f"{CANONICAL_HOST}{path}"


def _hreflang_alternates(path: str) -> Dict[str, str]:
    """Every public prerender emits en-CA, fr-CA, x-default. Tier 3 M-3 will
    upgrade this to subdirectory routing (/en /fr). For now query-string
    variants are Google-accepted."""
    return {
        "en-CA":     _canonical(path, "en"),
        "fr-CA":     _canonical(path, "fr"),
        "x-default": _canonical(path, "default"),
    }


def _jsonld_script(payload: Any) -> str:
    """Render a JSON-LD block. Uses HTML-escape on the JSON body to prevent
    </script>-injection."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("</script>", "<\\/script>")
    return f'<script type="application/ld+json">{body}</script>'


# ─── Route resolvers ───────────────────────────────────────────────────

async def _resolve_homepage(db, lang: str) -> Dict[str, Any]:
    title = (
        "BidVex | Canada's Bilingual Auction Marketplace" if lang == "en"
        else "BidVex | La marketplace d'enchères bilingue du Canada"
    )
    description = (
        "Bid on vehicles, storage lockers, industrial equipment and lots. "
        "Verified sellers, secure Stripe escrow, bilingual EN/FR platform. "
        "Sherbrooke, Quebec."
        if lang == "en" else
        "Enchérissez sur des véhicules, casiers de stockage, équipement industriel "
        "et lots. Vendeurs vérifiés, séquestre Stripe sécurisé, plateforme bilingue "
        "EN/FR. Sherbrooke, Québec."
    )
    canonical = _canonical("/", lang)
    return {
        "template": "homepage.html",
        "title": title,
        "description": description,
        "canonical": canonical,
        "og_type": "website",
        "og_image": f"{CANONICAL_HOST}/bidvex-icon.png",
        "hreflang": _hreflang_alternates("/"),
        "jsonld_blocks": [
            _jsonld_script(organization_ld()),
            _jsonld_script(website_ld()),
            # iter357 — LocalBusiness on the homepage so Google links
            # BidVex Inc. to the physical Sherbrooke address in the
            # local-pack + Knowledge Graph.
            _jsonld_script(local_business_ld(lang=lang)),
        ],
        "lang": lang,
        "hero_headline": title,
        "hero_subtitle": description,
        "canonical_host": CANONICAL_HOST,
    }


async def _resolve_static_page(db, path: str, lang: str) -> Dict[str, Any]:
    """Terms / FAQ / How it works / About / Contact / Privacy / Refund.
    Each has a hard-coded copy stanza; the real page content is behind the
    React SPA — this is a crawler-only summary."""
    stanzas = {
        "/terms": {
            "en": ("BidVex Terms of Service",
                   "The complete BidVex Terms of Service covering account rules, bidding, "
                   "escrow, dispute resolution, fee schedule (§5B and §8 include the "
                   "vehicle vs non-vehicle escrow flows), and privacy."),
            "fr": ("Conditions d'utilisation BidVex",
                   "Les conditions d'utilisation complètes de BidVex couvrant règles de "
                   "compte, enchères, séquestre, litiges, barème de frais (§5B et §8 "
                   "décrivent les modèles véhicules vs non-véhicules) et confidentialité."),
        },
        "/legal/terms": {
            "en": ("BidVex Terms of Service",
                   "Complete legal terms — updated for the two-flow escrow model."),
            "fr": ("Conditions d'utilisation BidVex",
                   "Termes légaux complets — mis à jour pour le modèle à deux flux de séquestre."),
        },
        "/faq": {
            "en": ("BidVex FAQ — Auction Marketplace",
                   "Frequently asked questions on bidding, seller verification, escrow flows, "
                   "vehicle broker payments, buyer premium, taxes, and refunds."),
            "fr": ("FAQ BidVex — Enchères en ligne",
                   "Questions fréquentes sur les enchères, vérification des vendeurs, "
                   "flux de séquestre, paiements courtier de véhicule, prime d'acheteur, "
                   "taxes et remboursements."),
        },
        "/how-it-works": {
            "en": ("How BidVex Works — Auctions, Escrow, Vehicles",
                   "Learn how to buy and sell on BidVex — from account creation to auction "
                   "close, pickup codes for non-vehicle escrow, and the broker-direct payment "
                   "model for vehicles."),
            "fr": ("Comment fonctionne BidVex — Enchères, séquestre, véhicules",
                   "Apprenez à acheter et vendre sur BidVex — de la création du compte à la "
                   "clôture, codes de retrait pour le séquestre non-véhicule et modèle de "
                   "paiement direct courtier pour véhicules."),
        },
        "/about": {
            "en": ("About BidVex — Canada's Auction Marketplace",
                   "BidVex is a Canadian-owned bilingual auction platform headquartered in "
                   "Sherbrooke, Quebec. Not affiliated with any cryptocurrency platform."),
            "fr": ("À propos de BidVex — La marketplace d'enchères canadienne",
                   "BidVex est une plateforme d'enchères bilingue à propriété canadienne, "
                   "basée à Sherbrooke, Québec. Sans affiliation avec aucune plateforme cryptomonnaie."),
        },
        "/about-us": {
            "en": ("About BidVex", "About the BidVex team and mission."),
            "fr": ("À propos de BidVex", "Équipe et mission de BidVex."),
        },
        "/contact": {
            "en": ("Contact BidVex — Sherbrooke, QC",
                   "Get in touch with BidVex support. Phone: +1 (450) 634-3099. Bilingual EN/FR."),
            "fr": ("Contacter BidVex — Sherbrooke, QC",
                   "Contactez le support BidVex. Téléphone : +1 (450) 634-3099. Bilingue EN/FR."),
        },
        "/legal/privacy": {
            "en": ("BidVex Privacy Policy",
                   "How BidVex collects, processes, and protects your personal data (Law 25 compliant)."),
            "fr": ("Politique de confidentialité BidVex",
                   "Comment BidVex collecte, traite et protège vos données (conforme Loi 25)."),
        },
        "/privacy-policy": {
            "en": ("BidVex Privacy Policy", "How BidVex handles your data."),
            "fr": ("Politique de confidentialité BidVex", "Comment BidVex gère vos données."),
        },
        "/legal/refunds": {
            "en": ("BidVex Refund Policy", "Refund rules for auctions, subscriptions, and disputes."),
            "fr": ("Politique de remboursement BidVex", "Règles de remboursement pour enchères, abonnements et litiges."),
        },
    }
    key = path.rstrip("/") or "/"
    stanza = stanzas.get(key) or stanzas.get(path)
    if not stanza:
        # Unknown static path — fall back to homepage.
        return await _resolve_homepage(db, lang)
    title, description = stanza[lang if lang in stanza else "en"]

    jsonld_blocks = [
        _jsonld_script(organization_ld()),
        _jsonld_script(breadcrumb_ld([
            {"name": "Home",  "url": CANONICAL_HOST + "/"},
            {"name": title,   "url": _canonical(path, lang)},
        ])),
    ]
    # /faq gets an additional FAQPage block
    if path in ("/faq", "/how-it-works"):
        qas_en = [
            {"q": "Is BidVex safe?",
             "a": "Yes. All payments are processed via Stripe with SSL encryption. Sellers are verified and we use AI-powered fraud detection."},
            {"q": "What are the fees?",
             "a": "Non-vehicle buyers pay a 5% premium. Non-vehicle sellers pay a 4% commission. Vehicles: BidVex charges 2.5% platform fee + buyer's premium + GST/QST — the hammer price is settled directly with the licensed broker off-platform."},
            {"q": "How does the escrow work?",
             "a": "For non-vehicle items, funds are held in BidVex escrow (Stripe manual capture) until the buyer confirms pickup with their 6-character code. For vehicles, BidVex holds only the platform fee + buyer's premium; the hammer price is paid broker↔buyer off-platform."},
            {"q": "Can I sell vehicles?",
             "a": "Only province-licensed vehicle dealers (OMVIC, AMVIC, VSA, SAAQ, etc.) can list vehicles."},
        ]
        qas_fr = [
            {"q": "BidVex est-il sécuritaire?",
             "a": "Oui. Tous les paiements sont traités par Stripe avec chiffrement SSL. Les vendeurs sont vérifiés et nous utilisons la détection de fraude par IA."},
            {"q": "Quels sont les frais?",
             "a": "Acheteurs non-véhicules : prime de 5%. Vendeurs non-véhicules : commission de 4%. Véhicules : BidVex prélève 2,5% de frais + prime + TPS/TVQ — le prix marteau est réglé directement avec le courtier licencié hors plateforme."},
            {"q": "Comment fonctionne le séquestre?",
             "a": "Pour les articles non-véhicules, les fonds sont détenus en séquestre BidVex (Stripe capture manuelle) jusqu'à ce que l'acheteur confirme le retrait avec son code de 6 caractères. Pour les véhicules, BidVex détient uniquement les frais de plateforme + prime d'acheteur; le prix marteau est payé directement acheteur↔courtier hors plateforme."},
            {"q": "Puis-je vendre des véhicules?",
             "a": "Seuls les concessionnaires de véhicules licenciés par leur province (OMVIC, AMVIC, VSA, SAAQ, etc.) peuvent publier des véhicules."},
        ]
        jsonld_blocks.append(_jsonld_script(faqpage_ld(qas_fr if lang == "fr" else qas_en)))

    return {
        "template": "static_page.html",
        "title": title,
        "description": description,
        "canonical": _canonical(path, lang),
        "og_type": "article",
        "og_image": f"{CANONICAL_HOST}/bidvex-icon.png",
        "hreflang": _hreflang_alternates(path),
        "jsonld_blocks": jsonld_blocks,
        "lang": lang,
        "hero_headline": title,
        "hero_subtitle": description,
        "canonical_host": CANONICAL_HOST,
    }


async def _resolve_auction(db, listing_id: str, path: str, lang: str, kind: str) -> Dict[str, Any]:
    """Auction detail page — kind ∈ {'listing','multi_item','vehicle','storage'}."""
    coll_map = {
        "listing":      "listings",
        "multi_item":   "multi_item_listings",
        "vehicle":      "vehicle_multi_lot_auctions",
        "storage":      "storage_auctions",
    }
    coll = coll_map.get(kind, "listings")
    doc = await db[coll].find_one({"id": listing_id}, {"_id": 0}) or {}
    title = doc.get("title") or doc.get("title_en") or doc.get("name") or "Auction Listing"
    if lang == "fr":
        title = doc.get("title_fr") or title
    description = (doc.get("description") or doc.get("description_en") or "")[:220]
    if lang == "fr":
        description = (doc.get("description_fr") or description)[:220]

    # Image
    img = None
    imgs = doc.get("images") or doc.get("photos") or []
    if imgs and isinstance(imgs[0], str) and imgs[0].startswith("http"):
        img = imgs[0]
    if not img and doc.get("lots"):
        # Nested lots (multi_item / vehicle multi-lot)
        for lot in doc["lots"]:
            l_imgs = lot.get("images") or lot.get("photos") or []
            for cand in l_imgs:
                if isinstance(cand, str) and cand.startswith("http"):
                    img = cand
                    break
            if img:
                break
    img = img or f"{CANONICAL_HOST}/placeholder-ad.jpg"

    # Price + timing
    current_price = float(doc.get("current_bid") or doc.get("starting_bid") or doc.get("reserve_price") or 0)
    starts_at = doc.get("starts_at") or doc.get("start_time") or doc.get("created_at") or datetime.now(timezone.utc).isoformat()
    ends_at   = doc.get("ends_at") or doc.get("end_time") or doc.get("closes_at") or starts_at
    seller_name = doc.get("seller_name") or doc.get("dealer_name") or doc.get("facility_name") or "Verified Seller"
    category = doc.get("category") or kind

    # Determine availability
    now = datetime.now(timezone.utc)
    try:
        ends_dt = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
        availability = "InStock" if ends_dt > now else "SoldOut"
    except Exception:
        availability = "InStock"

    canonical = _canonical(path, lang)

    # iter356 — Emit Vehicle schema (Product+Vehicle dual-type) for vehicle
    # auctions so Google unlocks the vehicle-listing rich result. Non-vehicle
    # auctions keep the classic Product/AggregateOffer path.
    if kind in ("vehicle",):
        primary_schema = vehicle_ld(
            name=title,
            description=description or title,
            canonical_url=canonical,
            image_url=img,
            current_price=current_price,
            currency="CAD",
            seller_name=seller_name,
            availability=availability,
            condition=doc.get("condition") or "UsedCondition",
            vin=doc.get("vin"),
            make=doc.get("make") or doc.get("brand"),
            model=doc.get("model"),
            year=int(doc["year"]) if str(doc.get("year") or "").isdigit() else None,
            mileage_km=(float(doc["mileage"]) if str(doc.get("mileage") or "").replace(".", "").isdigit() else None),
            body_type=doc.get("body_type") or doc.get("bodyStyle"),
            transmission=doc.get("transmission"),
            fuel_type=doc.get("fuel_type"),
        )
    else:
        primary_schema = product_offer_ld(
            name=title,
            description=description or title,
            image_url=img,
            canonical_url=canonical,
            current_price=current_price,
            currency="CAD",
            seller_name=seller_name,
            availability=availability,
            category=category,
        )

    jsonld_blocks = [
        _jsonld_script(organization_ld()),
        _jsonld_script(primary_schema),
        _jsonld_script(event_ld(
            name=title,
            description=description or title,
            canonical_url=canonical,
            starts_at_iso=str(starts_at),
            ends_at_iso=str(ends_at),
            image_url=img,
            current_price=current_price,
        )),
        _jsonld_script(breadcrumb_ld([
            {"name": "Home",     "url": CANONICAL_HOST + "/"},
            {"name": "Auctions", "url": CANONICAL_HOST + "/marketplace"},
            {"name": title,      "url": canonical},
        ])),
    ]

    return {
        "template": "auction_detail.html",
        "title": f"{title} | BidVex Auction",
        "description": description or f"Bid on {title} on BidVex — Canada's auction marketplace.",
        "canonical": canonical,
        "og_type": "product",
        "og_image": img,
        "hreflang": _hreflang_alternates(path),
        "jsonld_blocks": jsonld_blocks,
        "lang": lang,
        "hero_headline": title,
        "hero_subtitle": description,
        "hero_image": img,
        "current_price": current_price,
        "currency": "CAD",
        "seller_name": seller_name,
        "ends_at": ends_at,
        "availability": availability,
        "category": category,
        "canonical_host": CANONICAL_HOST,
    }


async def resolve_route(db, path: str, lang: str = "en") -> Dict[str, Any]:
    """Central dispatch — returns a template-ready context dict.

    iter357 subpath handling:
      • `/en/<path>` and `/fr/<path>` are stripped to `/<path>` before dispatch
      • `lang` is inferred from the prefix (overrides caller-provided lang)
      • The stripped result is what we resolve — old URLs and new URLs
        share the same content pipeline
    """
    if not path.startswith("/"):
        path = "/" + path
    # Normalize trailing slashes except for root
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # iter357 — Language subpath handling (backend acceptance only; SPA
    # frontend refactor lands in iter358).
    if path.startswith("/en/"):
        lang = "en"
        path = path[3:] or "/"
    elif path.startswith("/fr/"):
        lang = "fr"
        path = path[3:] or "/"
    elif path in ("/en", "/fr"):
        lang = path[1:]
        path = "/"

    # iter358 — FR-slug → EN-slug backend normalization so /fr/marche resolves
    # to the marketplace page's SSR context (with FR title). The frontend
    # canonical URL keeps the FR slug via hreflang alternates.
    _FR_TO_EN_SLUGS = {
        "/marche":                      "/marketplace",
        "/encheres-vehicules":          "/vehicle-auctions",
        "/encheres-entreposage":        "/storage-auctions",
        "/comment-ca-marche":           "/how-it-works",
        "/comment-fonctionnent-les-courtiers": "/how-brokers-work",
        "/a-propos":                    "/about",
        "/tarifs":                      "/pricing",
        "/conditions-utilisation":      "/terms-of-service",
        "/politique-confidentialite":   "/privacy-policy",
        "/politique-remboursement":     "/refund-policy",
        "/carrieres":                   "/careers",
        "/communaute":                  "/community",
        "/blogues":                     "/blogs",
        "/annuaire-courtiers":          "/broker-directory",
        "/courtiers":                   "/broker-directory",
        "/devenir-courtier":            "/become-a-broker",
        "/devenir-partenaire":          "/become-a-partner",
        "/articles-interdits":          "/prohibited-items",
    }
    if lang == "fr" and path in _FR_TO_EN_SLUGS:
        path = _FR_TO_EN_SLUGS[path]

    if path in ("/", ""):
        return await _resolve_homepage(db, lang)

    # Auction detail routes
    parts = path.split("/")
    if len(parts) >= 3:
        head, ident = parts[1], parts[2]
        if head == "auctions" and ident:
            return await _resolve_auction(db, ident, path, lang, kind="listing")
        if head == "multi-item-auctions" and ident:
            return await _resolve_auction(db, ident, path, lang, kind="multi_item")
        if head in ("vehicles", "vehicle-auctions") and ident:
            return await _resolve_auction(db, ident, path, lang, kind="vehicle")
        if head in ("storage", "storage-auctions") and ident:
            return await _resolve_auction(db, ident, path, lang, kind="storage")

    # Public list routes (marketplace / vehicle-auctions / storage-auctions root)
    static_list_labels = {
        "/marketplace":       ("BidVex Marketplace — All Auctions",
                               "Marketplace BidVex — Toutes les enchères"),
        "/lots-marketplace":  ("BidVex Lots Marketplace",
                               "Marketplace des lots BidVex"),
        "/vehicle-auctions":  ("Vehicle Auctions Canada — BidVex",
                               "Enchères de véhicules Canada — BidVex"),
        "/storage-auctions":  ("Storage Locker Auctions Canada — BidVex",
                               "Enchères de casiers de stockage Canada — BidVex"),
        "/broker-directory":  ("Licensed Vehicle Brokers — BidVex Canada",
                               "Courtiers de véhicules licenciés — BidVex Canada"),
    }
    if path in static_list_labels:
        en, fr = static_list_labels[path]
        title = fr if lang == "fr" else en
        desc = title
        return {
            "template": "static_page.html",
            "title": title,
            "description": desc,
            "canonical": _canonical(path, lang),
            "og_type": "website",
            "og_image": f"{CANONICAL_HOST}/bidvex-icon.png",
            "hreflang": _hreflang_alternates(path),
            "jsonld_blocks": [
                _jsonld_script(organization_ld()),
                _jsonld_script(breadcrumb_ld([
                    {"name": "Home",  "url": CANONICAL_HOST + "/"},
                    {"name": title,   "url": _canonical(path, lang)},
                ])),
            ],
            "lang": lang,
            "hero_headline": title,
            "hero_subtitle": desc,
            "canonical_host": CANONICAL_HOST,
        }

    # iter356 — Regional SEO landing pages (P1 fix H3).
    # 10 EN + 2 FR Quebec pages + iter357 24 QC city pages + iter358 press-release pages.
    regional = _resolve_regional_landing(path, lang)
    if regional:
        # iter357 — Attach social-proof widget stats (5-min cached).
        # Skip for press-release pages (they have their own layout).
        if not regional.get("is_press_release"):
            await attach_social_proof(regional, db)
        return regional

    return await _resolve_static_page(db, path, lang)


# ─── iter356 · Regional SEO landing pages ─────────────────────────────

def _regional_pair(en_path: str, fr_path: str) -> Dict[str, str]:
    """Return hreflang alternates pointing at the EN + FR twin pages."""
    return {
        "en-CA":     f"{CANONICAL_HOST}{en_path}",
        "fr-CA":     f"{CANONICAL_HOST}{fr_path}",
        "x-default": f"{CANONICAL_HOST}{en_path}",
    }


# Definition table: EN slug → {title, description, hero_h1, keywords,
# canonical province code, marketplace filter URL, twin FR slug (or None)}.
_REGIONAL_LANDINGS: Dict[str, Dict[str, Any]] = {
    # ── Broad Canada-wide ────────────────────────────────────────
    "/car-auctions-canada": {
        "title_en": "Car Auctions Canada — Bid Online on Vehicles | BidVex",
        "desc_en":  "Browse and bid on Canadian car auctions online. Verified dealers, "
                    "transparent bidding, bilingual EN/FR platform. Live vehicle "
                    "auctions from Quebec, Ontario, Alberta, and British Columbia.",
        "h1_en":    "Online Car Auctions Across Canada",
        "cta_target": "/vehicle-auctions",
        "twin_fr": None,
    },
    "/vehicle-auctions-canada": {
        "title_en": "Vehicle Auctions Canada — Cars, Trucks, SUVs | BidVex",
        "desc_en":  "Bid on Canadian vehicle auctions online. Cars, pickup trucks, "
                    "SUVs, motorcycles from licensed dealers nationwide.",
        "h1_en":    "Vehicle Auctions — Canada-Wide",
        "cta_target": "/vehicle-auctions",
        "twin_fr": None,
    },
    "/equipment-auctions-canada": {
        "title_en": "Industrial Equipment Auctions Canada | BidVex",
        "desc_en":  "Bid online on Canadian industrial equipment auctions. "
                    "Heavy machinery, tools, restaurant equipment, IT gear.",
        "h1_en":    "Industrial Equipment Auctions — Canada",
        "cta_target": "/marketplace?category=equipment",
        "twin_fr": None,
    },
    # ── Provincial ───────────────────────────────────────────────
    "/vehicle-auctions-quebec": {
        "title_en": "Vehicle Auctions Quebec — Cars & Trucks Online | BidVex",
        "desc_en":  "Bid online on Quebec vehicle auctions. Cars, trucks, and SUVs "
                    "from SAAQ-licensed dealers across Montreal, Quebec City, "
                    "Sherbrooke, Laval, and Gatineau. Bilingual EN/FR platform.",
        "h1_en":    "Online Vehicle Auctions in Quebec",
        "cta_target": "/vehicle-auctions?province=QC",
        "twin_fr": "/encheres-vehicules-quebec",
    },
    "/vehicle-auctions-ontario": {
        "title_en": "Vehicle Auctions Ontario — Toronto, Ottawa, Hamilton | BidVex",
        "desc_en":  "Ontario online vehicle auctions from OMVIC-licensed dealers. "
                    "Cars, trucks, and SUVs shipped or picked up in Toronto, "
                    "Ottawa, Mississauga, Hamilton, and London.",
        "h1_en":    "Online Vehicle Auctions in Ontario",
        "cta_target": "/vehicle-auctions?province=ON",
        "twin_fr": None,
    },
    "/vehicle-auctions-british-columbia": {
        "title_en": "Vehicle Auctions British Columbia — Vancouver, Victoria | BidVex",
        "desc_en":  "British Columbia online vehicle auctions from VSA-licensed dealers. "
                    "Cars, trucks, and SUVs from Vancouver, Victoria, Surrey, and Kelowna.",
        "h1_en":    "Online Vehicle Auctions in British Columbia",
        "cta_target": "/vehicle-auctions?province=BC",
        "twin_fr": None,
    },
    "/vehicle-auctions-alberta": {
        "title_en": "Vehicle Auctions Alberta — Calgary, Edmonton | BidVex",
        "desc_en":  "Alberta online vehicle auctions from AMVIC-licensed dealers. "
                    "Cars, trucks, SUVs from Calgary, Edmonton, Red Deer, Lethbridge.",
        "h1_en":    "Online Vehicle Auctions in Alberta",
        "cta_target": "/vehicle-auctions?province=AB",
        "twin_fr": None,
    },
    "/storage-auctions-ontario": {
        "title_en": "Storage Unit Auctions Ontario — Online Bidding | BidVex",
        "desc_en":  "Bid online on abandoned storage unit auctions in Ontario. "
                    "Verified facilities in Toronto, Mississauga, Ottawa, Hamilton.",
        "h1_en":    "Storage Unit Auctions in Ontario",
        "cta_target": "/storage-auctions?province=ON",
        "twin_fr": None,
    },
    "/storage-auctions-quebec": {
        "title_en": "Storage Unit Auctions Quebec — Locker Bidding | BidVex",
        "desc_en":  "Bid online on abandoned storage unit auctions in Quebec. "
                    "Verified facilities in Montreal, Quebec City, Sherbrooke, and Laval. "
                    "Bilingual EN/FR platform.",
        "h1_en":    "Storage Unit Auctions in Quebec",
        "cta_target": "/storage-auctions?province=QC",
        "twin_fr": "/encheres-entreposage-quebec",
    },
    "/storage-auctions-british-columbia": {
        "title_en": "Storage Unit Auctions British Columbia | BidVex",
        "desc_en":  "British Columbia storage unit auctions online — Vancouver, "
                    "Victoria, Surrey. Bid on abandoned lockers from verified facilities.",
        "h1_en":    "Storage Unit Auctions in British Columbia",
        "cta_target": "/storage-auctions?province=BC",
        "twin_fr": None,
    },
    # ── FR-only Quebec twins ─────────────────────────────────────
    "/encheres-vehicules-quebec": {
        "title_fr": "Enchères de véhicules au Québec — Voitures et camions | BidVex",
        "desc_fr":  "Enchérissez en ligne sur des véhicules du Québec. Voitures, "
                    "camions et VUS de concessionnaires licenciés SAAQ à Montréal, "
                    "Québec, Sherbrooke, Laval et Gatineau. Plateforme bilingue EN/FR.",
        "h1_fr":    "Enchères de véhicules en ligne au Québec",
        "cta_target": "/vehicle-auctions?province=QC",
        "twin_en": "/vehicle-auctions-quebec",
        "lang_only": "fr",
        "province_page": True,
        "province_kind": "vehicle",
    },
    "/encheres-entreposage-quebec": {
        "title_fr": "Enchères d'entreposage au Québec — Casiers en ligne | BidVex",
        "desc_fr":  "Enchérissez en ligne sur des casiers d'entreposage abandonnés "
                    "au Québec. Installations vérifiées à Montréal, Québec, "
                    "Sherbrooke et Laval. Plateforme bilingue EN/FR.",
        "h1_fr":    "Enchères de casiers d'entreposage au Québec",
        "cta_target": "/storage-auctions?province=QC",
        "twin_en": "/storage-auctions-quebec",
        "lang_only": "fr",
        "province_page": True,
        "province_kind": "storage",
    },
}


# iter357 — Merge in the 24 QC city landing pages (12 cities × 2 langs).
# QC vehicle cities are also linked from `/encheres-vehicules-quebec` via
# the Adwords city-grid section rendered by regional_landing.html.
_REGIONAL_LANDINGS.update(build_qc_vehicle_city_entries())
_REGIONAL_LANDINGS.update(build_qc_storage_city_entries())

# iter358 — Press release pages (EN + FR) merged into the same regional-landing
# dispatch table so they benefit from the existing hreflang/breadcrumb/social
# proof plumbing. Distinguished by `kind == "press_release"` for template routing
# + NewsArticle JSON-LD injection.
_REGIONAL_LANDINGS.update(build_press_release_entries())


# ─── Also mark the QC province pages as province-level for the Adwords
#     city grid; we already labelled them with `province_page: True` above.
_REGIONAL_LANDINGS["/vehicle-auctions-quebec"]["province_page"] = True
_REGIONAL_LANDINGS["/vehicle-auctions-quebec"]["province_kind"] = "vehicle"
_REGIONAL_LANDINGS["/storage-auctions-quebec"]["province_page"] = True
_REGIONAL_LANDINGS["/storage-auctions-quebec"]["province_kind"] = "storage"


def _resolve_regional_landing(path: str, lang: str) -> Optional[Dict[str, Any]]:
    """Build a prerender context for a regional SEO landing page, or None
    if `path` isn't one of the known regional slugs. Bilingual pairs get
    correct hreflang cross-references.

    iter357 additions:
      • QC city + province pages get a LocalBusiness JSON-LD block
      • QC province pages render a city-grid Adwords copy section
      • City pages render the city-specific body blurb (`body_fr`/`body_en`)
    """
    entry = _REGIONAL_LANDINGS.get(path)
    if not entry:
        return None

    # FR-only page → force lang=fr, twin points to EN counterpart.
    lang_only = entry.get("lang_only")
    if lang_only == "fr":
        title = entry["title_fr"]
        desc  = entry["desc_fr"]
        h1    = entry["h1_fr"]
        body  = entry.get("body_fr", "")
        hreflang = _regional_pair(entry["twin_en"], path)
        page_lang = "fr"
        canonical = f"{CANONICAL_HOST}{path}"
    elif lang == "fr" and entry.get("title_fr"):
        title = entry["title_fr"]
        desc  = entry["desc_fr"]
        h1    = entry["h1_fr"]
        body  = entry.get("body_fr", "")
        twin_fr = entry.get("twin_fr")
        hreflang = _regional_pair(path, twin_fr) if twin_fr else _hreflang_alternates(path)
        page_lang = "fr"
        canonical = f"{CANONICAL_HOST}{path}?lang=fr"
    else:
        title = entry["title_en"]
        desc  = entry["desc_en"]
        h1    = entry["h1_en"]
        body  = entry.get("body_en", "")
        twin_fr = entry.get("twin_fr")
        hreflang = _regional_pair(path, twin_fr) if twin_fr else _hreflang_alternates(path)
        page_lang = "en"
        canonical = f"{CANONICAL_HOST}{path}"

    # Breadcrumb ancestry: Home → (Province page) → Current
    breadcrumb_items = [
        {"name": "BidVex" if page_lang == "en" else "Accueil",
         "url":  CANONICAL_HOST + "/"},
    ]
    if entry.get("kind") in ("qc_city_vehicle", "qc_city_storage"):
        breadcrumb_items.append({
            "name": entry.get("province_page_name", "Québec"),
            "url":  CANONICAL_HOST + entry.get("province_page", "/"),
        })
    else:
        breadcrumb_items.append({
            "name": ("Vehicle Auctions" if "vehicle" in path or "encheres-veh" in path
                     else "Storage Auctions" if "storage" in path or "entreposage" in path
                     else "Auctions"),
            "url":  CANONICAL_HOST + entry["cta_target"],
        })
    breadcrumb_items.append({"name": title, "url": canonical})

    jsonld_blocks = [
        _jsonld_script(organization_ld()),
        _jsonld_script(breadcrumb_ld(breadcrumb_items)),
    ]

    # QC city / province page → emit LocalBusiness with the city in the name.
    is_qc_city = entry.get("kind") in ("qc_city_vehicle", "qc_city_storage")
    is_qc_province = entry.get("province_page", False)
    is_press_release = entry.get("kind") == "press_release"
    if is_qc_city or is_qc_province:
        city_name = None
        if is_qc_city:
            city_name = entry.get("city_fr" if page_lang == "fr" else "city_en")
        jsonld_blocks.append(_jsonld_script(local_business_ld(
            city_name=city_name, lang=page_lang,
        )))

    # iter358 — Press release pages get a NewsArticle JSON-LD block.
    if is_press_release:
        news_ld = news_article_ld_for(page_lang)
        # Strip null translationOfWork field for EN version (Google is strict).
        news_ld = {k: v for k, v in news_ld.items() if v is not None}
        jsonld_blocks.append(_jsonld_script(news_ld))

    # Adwords city grid for QC province pages.
    city_grid: List[Dict[str, str]] = []
    if is_qc_province and entry.get("province_kind"):
        city_grid = qc_province_city_grid_for(
            kind=entry["province_kind"], lang=page_lang,
        )

    return {
        "template": "press_release.html" if is_press_release else "regional_landing.html",
        "title": title,
        "description": desc,
        "canonical": canonical,
        "og_type": "article" if is_press_release else "website",
        "og_image": f"{CANONICAL_HOST}/bidvex-icon.png",
        "hreflang": hreflang,
        "jsonld_blocks": jsonld_blocks,
        "lang": page_lang,
        "hero_headline": h1,
        "hero_subtitle": desc,
        "body_copy": body,
        "cta_target": entry["cta_target"],
        "city_grid": city_grid,
        "is_qc_province": bool(is_qc_province),
        "is_qc_city": bool(is_qc_city),
        "is_press_release": bool(is_press_release),
        "press_pdf_url": PRESS_RELEASE_PDF_URL,
        "canonical_host": CANONICAL_HOST,
        # `social_proof` gets attached later, once the resolver caller
        # (which has the db handle) awaits `attach_social_proof(ctx, db)`.
        "social_proof": None,
    }


async def attach_social_proof(ctx: Dict[str, Any], db) -> Dict[str, Any]:
    """Enrich a regional-landing context with the social-proof widget stats."""
    try:
        ctx["social_proof"] = await get_platform_stats(db)
    except Exception:
        ctx["social_proof"] = None
    return ctx


def render_html(context: Dict[str, Any]) -> str:
    """Render the Jinja2 template referenced in `context["template"]`."""
    tpl = _ENV.get_template(context["template"])
    return tpl.render(**context)
