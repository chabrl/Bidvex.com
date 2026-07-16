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
    """Event schema — auctions are online time-bounded events per schema.org.
    Unlocks the SERP Events carousel."""
    return {
        "@context": "https://schema.org",
        "@type":    "Event",
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
        },
    }


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
    "breadcrumb_ld",
    "faqpage_ld",
]
