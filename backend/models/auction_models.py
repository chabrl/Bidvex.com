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
    agreement_accepted: bool = False
    agreement_metadata: Optional[Dict[str, Any]] = None
    # Listing-level buyer's premium (rate, e.g. 0.15 for 15%). None = use org/tier default
    buyers_premium_rate: Optional[float] = None
    # Seller payment method preference: "stripe", "cash", "e-transfer"
    payment_method: Optional[str] = None
    currency: Optional[str] = None  # CAD or USD; auto-detected from location if omitted
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
    custom_buyer_premium_rate: Optional[float] = None
    is_partner_listing: bool = False
    is_opc_certified: bool = False
    buyers_premium_percent: Optional[float] = None
    payment_method: Optional[str] = None  # "stripe", "cash", "e-transfer"
    currency: str = "CAD"
    # i18n bilingual fields
    title_en: Optional[str] = None
    title_fr: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    # Multi-lot fields (populated when listing is a lot within a multi-item auction)
    listing_type: Optional[str] = None
    parent_auction_id: Optional[str] = None
    parent_auction_title: Optional[str] = None
    lot_number: Optional[int] = None
    total_lots: Optional[int] = None
    badge_en: Optional[str] = None
    badge_fr: Optional[str] = None
    bids: Optional[int] = None


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
    documents: Optional[Dict[str, Any]] = None
    shipping_info: Optional[Dict[str, Any]] = None
    visit_availability: Optional[Dict[str, Any]] = None
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
    payment_method: Optional[str] = None
    payment_proof_url: Optional[str] = None
    auction_terms_en: Optional[str] = None
    auction_terms_fr: Optional[str] = None
    seller_obligations: Optional[Dict[str, Any]] = None
    # i18n bilingual fields
    title_en: Optional[str] = None
    title_fr: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
