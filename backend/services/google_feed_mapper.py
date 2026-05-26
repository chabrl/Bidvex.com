"""iter231 — Google Merchant Center XML feed for BidVex auction listings.

Endpoint:  GET /api/feeds/google
Output:    RSS 2.0 XML with `xmlns:g="http://base.google.com/ns/1.0"`

Strategy (Three-Surface Mirroring):
  • <g:price>            = live current_bid (or final hammer price if ended).
                           NEVER buy_now_price. NEVER sale_price.
  • <g:price_type>       = "auction" (custom attribute declared in Merchant
                           Center → Custom attributes). Tells Google this is
                           a dynamic-price item and tolerates the bid range.
  • <g:availability>     = "in_stock" while status=active, "out_of_stock"
                           once ended/sold/closed (preserves ad attribution).
  • <g:id>               = canonical listing.id UUID (matches pixel content_ids
                           1:1 → catalog match rate → audience builders).
  • <g:identifier_exists>= "no" — auction lots don't have GTIN/MPN.
  • <g:condition>        = used / new / refurbished per listing.

This module is read-only; it reuses meta_feed_mapper.map_listing_to_meta_item
so price/availability/exclusion logic stays a single source of truth.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List
from xml.sax.saxutils import escape as _xml_escape

logger = logging.getLogger(__name__)

BIDVEX_BASE_URL = os.environ.get("BIDVEX_BASE_URL", "https://bidvex.com").rstrip("/")


def _g(text: Any) -> str:
    """XML-escape any value and coerce to string. None → empty string."""
    if text is None:
        return ""
    return _xml_escape(str(text), {'"': "&quot;", "'": "&apos;"})


def _to_google_availability(meta_value: str) -> str:
    """Translate Meta's 'in stock' / 'out of stock' to Google's underscored form."""
    if not meta_value:
        return "in_stock"
    v = meta_value.lower().strip()
    if v in ("in stock", "in_stock"):
        return "in_stock"
    if v in ("out of stock", "out_of_stock", "available_for_order"):
        return "out_of_stock"
    return "in_stock"


def _to_google_condition(meta_value: str) -> str:
    """Translate Meta's condition to Google's exact whitelist."""
    if not meta_value:
        return "used"
    v = meta_value.lower().strip()
    if v in ("new", "refurbished", "used"):
        return v
    return "used"


def _split_meta_price(meta_price: str) -> str:
    """Meta produces 'NNNN.NN CAD'; Google wants the exact same format."""
    if not meta_price:
        return "0.00 CAD"
    parts = str(meta_price).strip().split()
    if len(parts) == 2:
        return meta_price
    return f"{meta_price} CAD"


def meta_item_to_google_xml(item: Dict[str, Any]) -> str:
    """Render a single Meta-shaped item dict as a Google Merchant <item> block.

    Reuses Meta's price + availability + content_id values verbatim so the
    two catalogs stay byte-for-byte aligned on every comparable field.
    """
    listing_id     = item.get("id") or ""
    title          = item.get("title") or ""
    description    = item.get("description") or ""
    link           = item.get("link") or f"{BIDVEX_BASE_URL}"
    image_link     = item.get("image_link") or ""
    price          = _split_meta_price(item.get("price") or "")
    availability   = _to_google_availability(item.get("availability"))
    condition      = _to_google_condition(item.get("condition"))
    brand          = item.get("brand") or "BidVex"
    city           = item.get("city") or ""
    region         = item.get("region") or ""
    country        = item.get("country") or "CA"
    postal         = item.get("postal_code") or ""
    google_cat     = item.get("google_product_category") or ""
    custom_0       = item.get("custom_label_0") or ""
    custom_1       = item.get("custom_label_1") or ""
    custom_2       = item.get("custom_label_2") or ""
    custom_3       = item.get("custom_label_3") or ""
    extra_images   = item.get("additional_image_link") or ""

    # Build the XML — RSS 2.0 dialect with g: namespace
    parts: List[str] = []
    parts.append("<item>")
    parts.append(f"<g:id>{_g(listing_id)}</g:id>")
    parts.append(f"<g:title>{_g(title)}</g:title>")
    parts.append(f"<g:description>{_g(description)}</g:description>")
    parts.append(f"<g:link>{_g(link)}</g:link>")
    parts.append(f"<g:image_link>{_g(image_link)}</g:image_link>")
    if extra_images:
        # Google accepts up to 10 additional_image_link entries; Meta packs them
        # comma-separated in a single string — split + emit one tag each.
        for extra in str(extra_images).split(",")[:10]:
            extra = extra.strip()
            if extra:
                parts.append(f"<g:additional_image_link>{_g(extra)}</g:additional_image_link>")
    parts.append(f"<g:availability>{_g(availability)}</g:availability>")
    parts.append(f"<g:condition>{_g(condition)}</g:condition>")
    parts.append(f"<g:price>{_g(price)}</g:price>")
    # iter231 — auction price-type marker. Declare this in Merchant Center
    # → Attributes → Custom attribute, type=text. Google then knows this
    # item's price is dynamic and tolerates the bid range.
    parts.append("<g:price_type>auction</g:price_type>")
    parts.append(f"<g:brand>{_g(brand)}</g:brand>")
    # No GTIN / MPN for auction lots — explicit identifier_exists=no
    parts.append("<g:identifier_exists>no</g:identifier_exists>")
    if google_cat:
        parts.append(f"<g:google_product_category>{_g(google_cat)}</g:google_product_category>")
    if city or region:
        parts.append(f"<g:shipping><g:country>{_g(country)}</g:country><g:region>{_g(region)}</g:region><g:price>0.00 CAD</g:price></g:shipping>")
    if postal:
        parts.append(f"<g:product_highlight>{_g(f'Located in {city}, {region} {postal}')}</g:product_highlight>")
    # Custom labels — same scheme as Meta so reporting comparisons line up
    if custom_0: parts.append(f"<g:custom_label_0>{_g(custom_0)}</g:custom_label_0>")
    if custom_1: parts.append(f"<g:custom_label_1>{_g(custom_1)}</g:custom_label_1>")
    if custom_2: parts.append(f"<g:custom_label_2>{_g(custom_2)}</g:custom_label_2>")
    if custom_3: parts.append(f"<g:custom_label_3>{_g(custom_3)}</g:custom_label_3>")
    # Adult flag — auctions are general audience
    parts.append("<g:adult>no</g:adult>")
    parts.append("</item>")
    return "".join(parts)


def build_google_feed_xml(items: List[Dict[str, Any]]) -> str:
    """Wrap a list of Meta-shaped items in the Google RSS 2.0 envelope.

    The envelope is the only place Google strictly requires:
      - rss[version=2.0] root element
      - xmlns:g="http://base.google.com/ns/1.0" namespace declaration
      - <channel><title><link><description> mandatory metadata
    """
    item_blocks = "\n".join(meta_item_to_google_xml(item) for item in items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
        '<channel>\n'
        f'<title>{_g("BidVex — Live Auction Catalog")}</title>\n'
        f'<link>{_g(BIDVEX_BASE_URL)}</link>\n'
        f'<description>{_g("Live Canadian auction marketplace — vehicles, storage, multi-lot liquidations. All sales final, as-is, where-is. Prices reflect the current high bid; auctions close per the listing schedule.")}</description>\n'
        f'<language>en-CA</language>\n'
        f'{item_blocks}\n'
        '</channel>\n'
        '</rss>\n'
    )
