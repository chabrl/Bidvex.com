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


CANONICAL_HOST = "https://www.bidvex.com"


def organization_ld() -> Dict[str, Any]:
    """Emit BidVex Organization schema — homepage + any generic prerender page."""
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "BidVex",
        "alternateName": ["BidVex Canada", "BidVex Auctions"],
        "url": CANONICAL_HOST,
        "logo": f"{CANONICAL_HOST}/bidvex-icon.png",
        "description": (
            "BidVex — Canada's bilingual online auction marketplace. "
            "Vehicles, storage lockers, industrial equipment, and lots. "
            "Sherbrooke, Quebec."
        ),
        "foundingLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": "Sherbrooke",
                "addressRegion": "QC",
                "addressCountry": "CA",
            },
        },
        "address": {
            "@type": "PostalAddress",
            "addressLocality": "Sherbrooke",
            "addressRegion": "QC",
            "addressCountry": "CA",
        },
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "telephone": "+1-450-634-3099",
                "contactType": "Customer Service",
                "areaServed": "CA",
                "availableLanguage": ["English", "French"],
            }
        ],
        "sameAs": [
            "https://www.facebook.com/bidvex",
            "https://www.linkedin.com/company/bidvex",
            "https://x.com/bidvex",
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
    """items: [{"name": "Home", "url": "https://www.bidvex.com/"}, ...]"""
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


__all__ = [
    "CANONICAL_HOST",
    "organization_ld",
    "website_ld",
    "product_offer_ld",
    "event_ld",
    "auction_sale_event_ld",
    "vehicle_ld",
    "breadcrumb_ld",
    "faqpage_ld",
]
