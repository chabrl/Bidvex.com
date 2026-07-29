"""
iter354 — Schema.org JSON-LD builders for SSR/prerender output.

Every builder returns a JSON-serializable Python dict (the caller wraps it in
`<script type="application/ld+json">`). Kept dependency-free so it's cheap to
import from the prerender path.

References:
  - https://schema.org/Organization
  - https://schema.org/Product
  - https://schema.org/AggregateOffer  (auctions with min/max price)
  - https://schema.org/Event           (auctions ARE time-bounded events)
  - https://schema.org/BreadcrumbList
  - https://schema.org/FAQPage
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


CANONICAL_HOST = "https://bidvex.com"


def organization_ld() -> Dict[str, Any]:
    """Emit BidVex Organization schema — homepage + any generic prerender page.

    iter357 additions:
      • `sameAs` array with all 4 social profiles (per iter357 spec)
      • Full LocalBusiness NAP (matches BIDVEX_NAP constant, single source of truth)
      • `aggregateRating` intentionally OMITTED for now — TODO(iter358):
        populate from Trustpilot API integration once BidVex has reviews.
    """
    # Late import to avoid a circular dep between services.
    try:
        from services.qc_city_pages import BIDVEX_SAMEAS, BIDVEX_NAP
        sameas = list(BIDVEX_SAMEAS)
        street  = BIDVEX_NAP["street"]
        postal  = BIDVEX_NAP["postal"]
        phone_e164 = BIDVEX_NAP["phone"]
    except ImportError:
        sameas = []
        street = "761 Rue Chalifoux"
        postal = "J1G 0A8"
        phone_e164 = "+14506343099"

    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "BidVex",
        "legalName": "BidVex Inc.",
        "alternateName": ["BidVex Canada", "BidVex Auctions"],
        "url": CANONICAL_HOST,
        "logo": f"{CANONICAL_HOST}/bidvex-icon.png",
        "description": (
            "BidVex — Canada's bilingual online auction marketplace. "
            "Vehicles, storage lockers, industrial equipment, and lots. "
            "Sherbrooke, Quebec."
        ),
        "sameAs": sameas,
        # aggregateRating: TODO(iter358) — populate from Trustpilot integration.
        "foundingLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "streetAddress":   street,
                "addressLocality": "Sherbrooke",
                "addressRegion":   "QC",
                "postalCode":      postal,
                "addressCountry":  "CA",
            },
        },
        "address": {
            "@type":           "PostalAddress",
            "streetAddress":   street,
            "addressLocality": "Sherbrooke",
            "addressRegion":   "QC",
            "postalCode":      postal,
            "addressCountry":  "CA",
        },
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "telephone": phone_e164,
                "contactType": "Customer Service",
                "areaServed": "CA",
                "availableLanguage": ["English", "French"],
            }
        ],
    }


def product_offer_ld(
    *,
    name: str,
    description: str,
    image_url: str,
    canonical_url: str,
    current_price: float,
    currency: str = "CAD",
    seller_name: Optional[str] = None,
    availability: str = "InStock",  # InStock | SoldOut | PreOrder
    condition: str = "UsedCondition",  # NewCondition | UsedCondition
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Product + AggregateOffer schema for an auction listing.

    Using AggregateOffer over Offer intentionally — Google explicitly accepts
    it for auction/marketplace pages and it does NOT trigger Merchant Center
    review for BidVex (which isn't a Shopping-enrolled merchant).
    """
    availability_map = {
        "InStock":   "https://schema.org/InStock",
        "SoldOut":   "https://schema.org/SoldOut",
        "PreOrder":  "https://schema.org/PreOrder",
        "Discontinued": "https://schema.org/Discontinued",
    }
    condition_map = {
        "NewCondition":         "https://schema.org/NewCondition",
        "UsedCondition":        "https://schema.org/UsedCondition",
        "RefurbishedCondition": "https://schema.org/RefurbishedCondition",
        "DamagedCondition":     "https://schema.org/DamagedCondition",
    }
    payload: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type":    "Product",
        "name":     name,
        "description": description,
        "image":    [image_url] if image_url else [],
        "url":      canonical_url,
        "offers": {
            "@type": "AggregateOffer",
            "priceCurrency": currency,
            "lowPrice":  round(float(current_price), 2),
            "highPrice": round(float(current_price), 2),
            "offerCount": 1,
            "availability": availability_map.get(availability, availability_map["InStock"]),
            "itemCondition": condition_map.get(condition, condition_map["UsedCondition"]),
            "url": canonical_url,
        },
    }
    if seller_name:
        payload["offers"]["seller"] = {"@type": "Organization", "name": seller_name}
    if category:
        payload["category"] = category
    return payload


def event_ld(
    *,
    name: str,
    description: str,
    canonical_url: str,
    starts_at_iso: str,
    ends_at_iso: str,
    image_url: str,
    current_price: float,
    currency: str = "CAD",
    location_name: str = "BidVex Online Marketplace",
) -> Dict[str, Any]:
    """SaleEvent schema — an online, time-bounded auction is a SaleEvent
    per Google's rich-results spec (a Product-owning subclass of Event).
    Emits both the base Event fields AND the SaleEvent-specific fields
    so we're eligible for the Events carousel AND the Sale-price snippet
    in Google Shopping tabs. Renamed from `event_ld` in iter354 →
    `auction_sale_event_ld` alias below for backwards-compat callers."""
    return {
        "@context": "https://schema.org",
        "@type":    ["Event", "SaleEvent"],
        "name":     name,
        "description": description,
        "url":      canonical_url,
        "startDate":  starts_at_iso,
        "endDate":    ends_at_iso,
        "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
        "eventStatus":         "https://schema.org/EventScheduled",
        "location": {
            "@type": "VirtualLocation",
            "url":   canonical_url,
        },
        "image": [image_url] if image_url else [],
        "organizer": {
            "@type": "Organization",
            "name":  "BidVex",
            "url":   CANONICAL_HOST,
        },
        "offers": {
            "@type": "Offer",
            "price": round(float(current_price), 2),
            "priceCurrency": currency,
            "availability":  "https://schema.org/InStock",
            "url":           canonical_url,
            "validFrom":     starts_at_iso,
            "validThrough":  ends_at_iso,
        },
    }


# iter356 alias — semantic name matching Google's auction rich-results docs.
auction_sale_event_ld = event_ld


def vehicle_ld(
    *,
    name: str,
    description: str,
    canonical_url: str,
    image_url: str,
    current_price: float,
    currency: str = "CAD",
    vin: Optional[str] = None,
    make: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[int] = None,
    mileage_km: Optional[float] = None,
    body_type: Optional[str] = None,
    transmission: Optional[str] = None,
    fuel_type: Optional[str] = None,
    seller_name: Optional[str] = None,
    availability: str = "InStock",
    condition: str = "UsedCondition",
) -> Dict[str, Any]:
    """iter356 — Vehicle rich result schema (Google's vehicle-listing carousel).

    Emits `@type: [Product, Vehicle]` — dual-type so we retain generic
    Product eligibility AND unlock the Vehicle-specific rich result which
    surfaces make/model/year/mileage in the SERP tile.
    """
    availability_map = {
        "InStock":   "https://schema.org/InStock",
        "SoldOut":   "https://schema.org/SoldOut",
        "PreOrder":  "https://schema.org/PreOrder",
        "Discontinued": "https://schema.org/Discontinued",
    }
    condition_map = {
        "NewCondition":         "https://schema.org/NewCondition",
        "UsedCondition":        "https://schema.org/UsedCondition",
        "RefurbishedCondition": "https://schema.org/RefurbishedCondition",
        "DamagedCondition":     "https://schema.org/DamagedCondition",
    }
    payload: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type":    ["Product", "Vehicle"],
        "name":     name,
        "description": description,
        "url":      canonical_url,
        "image":    [image_url] if image_url else [],
        "offers": {
            "@type": "Offer",
            "price": round(float(current_price), 2),
            "priceCurrency": currency,
            "availability": availability_map.get(availability, availability_map["InStock"]),
            "itemCondition": condition_map.get(condition, condition_map["UsedCondition"]),
            "url": canonical_url,
        },
    }
    if seller_name:
        payload["offers"]["seller"] = {"@type": "Organization", "name": seller_name}
    if vin:
        payload["vehicleIdentificationNumber"] = vin
    if make:
        payload["brand"] = {"@type": "Brand", "name": make}
        payload["manufacturer"] = {"@type": "Organization", "name": make}
    if model:
        payload["model"] = model
    if year:
        payload["vehicleModelDate"] = str(year)
        payload["productionDate"] = f"{year}-01-01"
    if mileage_km is not None:
        payload["mileageFromOdometer"] = {
            "@type":    "QuantitativeValue",
            "value":    round(float(mileage_km), 1),
            "unitCode": "KMT",  # UN/CEFACT code for kilometres
        }
    if body_type:
        payload["bodyType"] = body_type
    if transmission:
        payload["vehicleTransmission"] = transmission
    if fuel_type:
        payload["fuelType"] = fuel_type
    return payload


def breadcrumb_ld(items: List[Dict[str, str]]) -> Dict[str, Any]:
    """items: [{"name": "Home", "url": "https://bidvex.com/"}, ...]"""
    return {
        "@context": "https://schema.org",
        "@type":    "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": item["name"],
                "item": item["url"],
            }
            for i, item in enumerate(items)
        ],
    }


def faqpage_ld(qas: List[Dict[str, str]]) -> Dict[str, Any]:
    """qas: [{"q": "Question?", "a": "Answer text"}, ...]"""
    return {
        "@context": "https://schema.org",
        "@type":    "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name":  qa["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text":  qa["a"],
                },
            }
            for qa in qas
        ],
    }


def website_ld() -> Dict[str, Any]:
    """WebSite schema with search action — enables SERP sitelinks search box."""
    return {
        "@context": "https://schema.org",
        "@type":    "WebSite",
        "name":     "BidVex",
        "url":      CANONICAL_HOST,
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{CANONICAL_HOST}/marketplace?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def news_article_ld(
    *,
    headline: str,
    description: str,
    date_published: str,
    canonical_url: str,
    lang: str = "en",
    author_name: str = "BidVex Editorial",
    author_role: Optional[str] = None,
    image_url: Optional[str] = None,
    date_modified: Optional[str] = None,
) -> Dict[str, Any]:
    """iter358 — NewsArticle rich-result schema.

    Used by press-release pages so Google eligibility for Top Stories +
    News tab is unlocked. The publisher block is BidVex Inc. with the
    canonical logo per Google's `NewsArticle.publisher.logo` spec.
    """
    payload: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type":    "NewsArticle",
        "headline": headline[:110],  # Google caps headline at 110 chars
        "description": description,
        "datePublished": date_published,
        "dateModified":  date_modified or date_published,
        "inLanguage":    "fr-CA" if lang == "fr" else "en-CA",
        "url":           canonical_url,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id":   canonical_url,
        },
        "author": {
            "@type": "Person",
            "name":  author_name,
        },
        "publisher": {
            "@type": "Organization",
            "name":  "BidVex Inc.",
            "url":   CANONICAL_HOST,
            "logo": {
                "@type": "ImageObject",
                "url":   f"{CANONICAL_HOST}/bidvex-icon.png",
                "width":  512,
                "height": 512,
            },
        },
    }
    if author_role:
        payload["author"]["jobTitle"] = author_role
    if image_url:
        payload["image"] = [image_url]
    return payload


__all__ = [
    "CANONICAL_HOST",
    "organization_ld",
    "local_business_ld",
    "website_ld",
    "product_offer_ld",
    "event_ld",
    "auction_sale_event_ld",
    "vehicle_ld",
    "breadcrumb_ld",
    "faqpage_ld",
    "news_article_ld",
]


def local_business_ld(
    *,
    city_name: Optional[str] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """iter357 — LocalBusiness schema for GMB verification + local-pack ranking.

    Emitted on the homepage AND on every QC city landing page (with
    `city_name` set). All fields draw from `BIDVEX_NAP` — the single
    source of truth for the NAP (Name, Address, Phone) consistency
    that Google requires for local-business ranking.
    """
    try:
        from services.qc_city_pages import BIDVEX_NAP, BIDVEX_SAMEAS
    except ImportError:
        return {}

    business_name = (
        f"BidVex — {city_name}, Québec" if (city_name and lang == "fr")
        else f"BidVex — {city_name}, Quebec" if city_name
        else "BidVex Inc."
    )
    return {
        "@context": "https://schema.org",
        "@type":    "LocalBusiness",
        "@id":      f"{CANONICAL_HOST}/#localbusiness",
        "name":     business_name,
        "legalName": BIDVEX_NAP["name"],
        "url":      CANONICAL_HOST,
        "image":    f"{CANONICAL_HOST}/bidvex-icon.png",
        "logo":     f"{CANONICAL_HOST}/bidvex-icon.png",
        "description": (
            "BidVex Inc. — Canada's bilingual online auction marketplace, "
            "headquartered in Sherbrooke, Québec. Vehicles, marketplace listings, "
            "multi-item lots, and storage auctions across Canada."
        ),
        "telephone":  BIDVEX_NAP["phone"],
        "email":      BIDVEX_NAP["email"],
        "priceRange": "$$",
        "address": {
            "@type":           "PostalAddress",
            "streetAddress":   BIDVEX_NAP["street"],
            "addressLocality": BIDVEX_NAP["city"],
            "addressRegion":   BIDVEX_NAP["region"],
            "postalCode":      BIDVEX_NAP["postal"],
            "addressCountry":  BIDVEX_NAP["country"],
        },
        "geo": {
            "@type":    "GeoCoordinates",
            "latitude":  BIDVEX_NAP["lat"],
            "longitude": BIDVEX_NAP["lng"],
        },
        "areaServed": [
            {"@type": "State",   "name": "Québec"},
            {"@type": "State",   "name": "Ontario"},
            {"@type": "State",   "name": "British Columbia"},
            {"@type": "State",   "name": "Alberta"},
            {"@type": "Country", "name": "Canada"},
        ],
        "openingHoursSpecification": [{
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday",
                          "Friday", "Saturday", "Sunday"],
            "opens":  "00:00",
            "closes": "23:59",
            "description": "Online auctions available 24/7",
        }],
        "sameAs":     list(BIDVEX_SAMEAS),
        # aggregateRating: TODO(iter358) — Trustpilot integration.
    }
