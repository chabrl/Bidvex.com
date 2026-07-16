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
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.seo_jsonld import (
    CANONICAL_HOST,
    breadcrumb_ld,
    event_ld,
    faqpage_ld,
    organization_ld,
    product_offer_ld,
    website_ld,
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

    jsonld_blocks = [
        _jsonld_script(organization_ld()),
        _jsonld_script(product_offer_ld(
            name=title,
            description=description or title,
            image_url=img,
            canonical_url=canonical,
            current_price=current_price,
            currency="CAD",
            seller_name=seller_name,
            availability=availability,
            category=category,
        )),
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
    """Central dispatch — returns a template-ready context dict."""
    if not path.startswith("/"):
        path = "/" + path
    # Normalize trailing slashes except for root
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

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

    return await _resolve_static_page(db, path, lang)


def render_html(context: Dict[str, Any]) -> str:
    """Render the Jinja2 template referenced in `context["template"]`."""
    tpl = _ENV.get_template(context["template"])
    return tpl.render(**context)
