"""
BidVex Shared Pydantic Models
All domain models used across multiple route files live here.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid


# ========== LISTINGS ==========

class ListingCreate(BaseModel):
    title: str
    description: str
    category: str
    condition: str
    starting_price: float
    buy_now_price: Optional[float] = None
    images: List[str] = []
    location: str
    city: str
    region: str
    country: Optional[str] = "CA"
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    auction_end_date: datetime
    shipping_info: Optional[Dict[str, Any]] = None
    visit_availability: Optional[Dict[str, Any]] = None
    # FEATURE PATCH v9 / Feature 4 — Quantity field for all listings
    quantity: int = 1
    multiply_hammer_by_quantity: bool = False
    # iter233 — Display-only "Lot price × Quantity" toggle (separate from
    # checkout-side multiply_hammer_by_quantity). When True AND quantity > 1,
    # marketplace cards and multi-lot rows render the *total* lot value while
    # bids continue to be placed at the per-unit price.
    price_multiplied_by_quantity: bool = False
    # Phase 6.0 / Task 3 — Storage Locker / Abandoned Unit
    listing_type: Optional[str] = None
    storage_metadata: Optional[Dict[str, Any]] = None
    # iter219 — Storage Locker bilingual content tags (optional).
    # Buyers can browse-filter on these. Allowed values (EN slugs):
    #   boxes, tools, furniture, electronics, sporting_goods, appliances, miscellaneous
    visible_content_tags: Optional[List[str]] = None
    agreement_accepted: bool = False
    agreement_metadata: Optional[Dict[str, Any]] = None
    # Listing-level buyer's premium (rate, e.g. 0.15 for 15%). None = use org/tier default
    buyers_premium_rate: Optional[float] = None
    # Seller payment method preference: "stripe", "cash", "e-transfer"
    payment_method: Optional[str] = None
    currency: Optional[str] = None  # CAD or USD; auto-detected from location if omitted
    # ── Deposit (a.k.a. "Down Payment") — single field, single flow per spec ──
    requires_deposit: bool = False
    deposit_amount: Optional[float] = None   # in auction currency
    deposit_type: Optional[str] = None       # "fixed" | "percentage"
    # i18n: manual overrides (auto-translated if omitted)
    title_en: Optional[str] = None
    title_fr: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    content_language: Optional[str] = "en"  # source language of title/description
    cfia_soil_declaration: Optional[bool] = None  # CFIA biosecurity: seller confirms equipment is soil-free


class Listing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    seller_id: str
    title: str
    description: str
    category: str
    condition: str
    starting_price: float
    current_price: float
    buy_now_price: Optional[float] = None
    images: List[str] = []
    location: str
    city: Optional[str] = ""
    region: Optional[str] = ""
    country: Optional[str] = "CA"
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    auction_end_date: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "active"
    bid_count: int = 0
    is_promoted: bool = False
    views: int = 0
    shipping_info: Optional[Dict[str, Any]] = None
    visit_availability: Optional[Dict[str, Any]] = None
    # FEATURE PATCH v9 / Feature 4 — Quantity field
    quantity: int = 1
    multiply_hammer_by_quantity: bool = False
    # iter233 — Display-only "Lot price × Quantity" toggle.
    price_multiplied_by_quantity: bool = False
    custom_buyer_premium_rate: Optional[float] = None
    is_partner_listing: bool = False
    # LEGACY: opc_permit → migrated to dealer_license_* (iter201).
    # Field name retained for backward compatibility with pre-iter201 listings.
    # New code should set is_dealer_certified instead and read both fields.
    is_opc_certified: bool = False
    is_dealer_certified: bool = False  # iter201 — replaces is_opc_certified going forward
    buyers_premium_percent: Optional[float] = None
    payment_method: Optional[str] = None  # "stripe", "cash", "e-transfer"
    currency: str = "CAD"
    # ── Deposit (Spec Feature 1) ──
    requires_deposit: bool = False
    deposit_amount: Optional[float] = None
    deposit_type: Optional[str] = None  # "fixed" | "percentage"
    # i18n bilingual fields
    title_en: Optional[str] = None
    title_fr: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    # Multi-lot fields (populated when listing is a lot within a multi-item auction)
    listing_type: Optional[str] = None
    # Phase 6.0 / Task 3 — Storage Locker / Abandoned Unit embedded metadata.
    # Populated only when listing_type == "storage_locker".
    storage_metadata: Optional[Dict[str, Any]] = None
    # iter219 — Bilingual content tags for storage-locker buyer keyword search.
    # Stored as English slugs (boxes, tools, furniture, electronics,
    # sporting_goods, appliances, miscellaneous). Empty = facility couldn't
    # see inside (closed boxes / lock-cut visibility only). Optional.
    visible_content_tags: List[str] = []
    parent_auction_id: Optional[str] = None
    # iter223 — Demo sandbox isolation flags. `is_demo_sandbox` is the
    # iter223-onwards public-exclusion field; `is_demo` is legacy and kept
    # for backwards-compat with older queries.
    is_demo_sandbox: bool = False
    is_demo: bool = False
    parent_auction_title: Optional[str] = None
    lot_number: Optional[int] = None
    total_lots: Optional[int] = None
    badge_en: Optional[str] = None
    badge_fr: Optional[str] = None
    bids: Optional[int] = None
    # ── Seller-type pricing/badge/geo-sort fields (copied at listing creation) ──
    seller_type: str = "individual"   # "individual" | "partner" | "enterprise"
    partner_bp_rate: Optional[float] = None  # only set for partner sellers
    seller_province: Optional[str] = None    # for geo-sort ("nearby first")
    seller_city: Optional[str] = None
    # iter217 — seller-account enrichment (computed at GET time, drives badges + tax label)
    seller_account_type: Optional[str] = None  # "partner" | "vehicle_dealer" | "storage_facility" | "individual"
    seller_is_partner: bool = False
    seller_is_vehicle_dealer: bool = False
    seller_is_storage_facility: bool = False
    seller_is_business: bool = False
    seller_partner_company_name: Optional[str] = None
    buyer_premium_rate: Optional[float] = None  # canonical, fraction (0.15 = 15%)


# ========== BIDS ==========

class BidCreate(BaseModel):
    listing_id: str
    amount: float
    cross_border_disclosure_accepted: Optional[bool] = None  # Required for US-origin listings


class Bid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    listing_id: str
    bidder_id: str
    amount: float
    bid_type: str = "normal"
    auto_bid_max: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutoBid(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    listing_id: str
    max_bid: float
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ========== BUY NOW ==========

class BuyNowPurchase(BaseModel):
    auction_id: str
    lot_number: int
    quantity: int = 1
    payment_method: str = "stripe"  # stripe, cash, etransfer


class BuyNowTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auction_id: str
    lot_number: int
    buyer_id: str
    quantity_purchased: int
    price_per_unit: float
    total_amount: float
    transaction_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payment_status: str = "pending"
    payment_method: Optional[str] = None
    bid_type: str = "normal"


# ========== MULTI-ITEM LISTINGS ==========

class Lot(BaseModel):
    lot_number: int
    title: str
    description: str
    quantity: int
    # FEATURE PATCH v9 / Feature 4 — lot-level "multiply hammer by quantity" opt-in
    multiply_hammer_by_quantity: bool = False
    # iter233 — Display-only "Lot price × Quantity" toggle (per lot).
    price_multiplied_by_quantity: bool = False
    starting_price: float
    current_price: float
    condition: str
    images: List[str] = []
    lot_end_time: Optional[datetime] = None
    pricing_mode: str = "multiplied"
    extension_count: int = 0
    buy_now_price: Optional[float] = None
    buy_now_enabled: bool = False
    available_quantity: Optional[int] = None
    sold_quantity: int = 0
    lot_status: str = "active"
    bid_count: int = 0
    highest_bidder_id: Optional[str] = None
    is_promoted: bool = False
    promotion_tier: Optional[str] = None
    impressions: int = 0
    clicks: int = 0
    # i18n bilingual fields
    title_en: Optional[str] = None
    title_fr: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    # ── Seller-type pricing/badge/geo-sort fields (copied at creation) ──
    seller_type: str = "individual"
    partner_bp_rate: Optional[float] = None
    seller_province: Optional[str] = None
    seller_city: Optional[str] = None
class MultiItemListingCreate(BaseModel):
    title: str
    description: str
    category: str
    location: str
    city: str
    region: str
    country: Optional[str] = "CA"
    postal_code: Optional[str] = None
    auction_end_date: datetime
    auction_start_date: Optional[datetime] = None
    lots: List[Lot]
    currency: Optional[str] = None
    payment_method: Optional[str] = None  # "stripe" | "cash" | "e-transfer"
    requires_deposit: bool = False
    deposit_amount: Optional[float] = None
    deposit_type: Optional[str] = None  # "fixed" | "percentage"
    documents: Optional[Dict[str, Any]] = None
    shipping_info: Optional[Dict[str, Any]] = None
    visit_availability: Optional[Dict[str, Any]] = None
    # FEATURE PATCH v9 / Feature 4 — Listing-level quantity (lots can override at lot level)
    quantity: int = 1
    multiply_hammer_by_quantity: bool = False
    # iter233 — Display-only "Lot price × Quantity" toggle.
    price_multiplied_by_quantity: bool = False
    auction_terms_en: Optional[str] = None
    auction_terms_fr: Optional[str] = None
    agreement_accepted: bool = False
    agreement_metadata: Optional[Dict[str, Any]] = None
    promotion_tier: Optional[str] = None
    is_promoted: bool = False
    # i18n: manual overrides (auto-translated if omitted)
    title_en: Optional[str] = None
    title_fr: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    content_language: Optional[str] = "en"  # source language of title/description


class MultiItemListing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    seller_id: str
    title: str
    description: str
    category: str
    location: str
    city: str
    region: str
    country: Optional[str] = "CA"
    postal_code: Optional[str] = None
    auction_end_date: datetime
    auction_start_date: Optional[datetime] = None
    lots: List[Lot]
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_lots: int = 0
    views: int = 0
    wishlist_count: int = 0
    currency: str = "CAD"
    increment_option: str = "tiered"
    is_featured: bool = False
    promotion_expiry: Optional[datetime] = None
    is_promoted: bool = False
    promotion_tier: Optional[str] = None
    promotion_start: Optional[datetime] = None
    promotion_end: Optional[datetime] = None
    total_impressions: int = 0
    total_clicks: int = 0
    premium_percentage: float = 5.0
    commission_rate: float = 4.0
    tax_rate_gst: float = 5.0
    tax_rate_qst: float = 9.975
    payment_deadline: Optional[datetime] = None
    pickup_locations: Optional[List[Dict[str, Any]]] = None
    payment_status: str = "pending"
    payment_date: Optional[datetime] = None
    documents: Optional[Dict[str, Any]] = None
    shipping_info: Optional[Dict[str, Any]] = None
    visit_availability: Optional[Dict[str, Any]] = None
    # FEATURE PATCH v9 / Feature 4
    quantity: int = 1
    multiply_hammer_by_quantity: bool = False
    # iter233 — Display-only "Lot price × Quantity" toggle.
    price_multiplied_by_quantity: bool = False
    payment_method: Optional[str] = None
    requires_deposit: bool = False
    deposit_amount: Optional[float] = None
    deposit_type: Optional[str] = None  # "fixed" | "percentage"
    payment_proof_url: Optional[str] = None
    auction_terms_en: Optional[str] = None
    auction_terms_fr: Optional[str] = None
    seller_obligations: Optional[Dict[str, Any]] = None
    # i18n bilingual fields
    title_en: Optional[str] = None
    title_fr: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    # iter217 — seller-account enrichment (computed at GET time, drives badges + tax label)
    seller_account_type: Optional[str] = None  # "partner" | "vehicle_dealer" | "storage_facility" | "individual"
    seller_is_partner: bool = False
    seller_is_vehicle_dealer: bool = False
    seller_is_storage_facility: bool = False
    seller_is_business: bool = False
    seller_partner_company_name: Optional[str] = None
    buyer_premium_rate: Optional[float] = None  # canonical, fraction (0.05 = 5%)
