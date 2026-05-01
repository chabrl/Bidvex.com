"""
BidVex Storage Unit Auction Models — iteration 169
==================================================
Two MongoDB collections:
  • storage_facilities  — verified Canadian self-storage operators
  • storage_auctions    — individual unit auctions (lien or non-lien)

Pricing rules (single source of truth):
  • Seller (facility): 5% flat commission + Stripe recovery + provincial tax
  • Buyer: ZERO BidVex fees. Pays facility directly.
    - Stripe payment → +Stripe fees passed through (facility nets full bid)
    - Cash / E-Transfer → exact winning bid only

Tax always applies to BidVex's 5% commission for ALL provinces. Provincial
sales tax on the winning bid is the FACILITY's responsibility, not BidVex's
(matches the vehicle module's intermediary posture).
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


CANADIAN_PROVINCES = ["AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK", "NT", "NU", "YT"]
UNIT_SIZES = ["5x5", "5x10", "10x10", "10x15", "10x20", "10x30+"]
UNIT_TYPES = ["indoor", "outdoor", "climate_controlled", "drive_up"]
PAYMENT_METHODS = ["stripe", "cash", "etransfer"]
AUCTION_STATUSES = ["upcoming", "active", "ended", "sold", "cancelled"]


class StorageFacilityRegister(BaseModel):
    """Public registration form payload."""
    company_name: str = Field(..., min_length=2, max_length=200)
    company_name_fr: Optional[str] = None
    contact_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    phone: str = Field(..., min_length=7)
    address: str = Field(..., min_length=5)
    city: str = Field(..., min_length=2)
    province: str
    postal_code: str
    units_available: int = Field(default=0, ge=0)
    referral_source: Optional[str] = None
    accepted_terms: bool


class StorageAuctionCreate(BaseModel):
    """Facility creating a new auction listing."""
    unit_number: str
    unit_size: str
    unit_type: str
    is_lien_unit: bool = False
    past_due_balance: Optional[float] = None
    description_en: str = Field(..., min_length=10)
    description_fr: Optional[str] = None
    photos: List[str] = []
    video_url: Optional[str] = None
    starting_price: float = Field(..., ge=0)
    reserve_price: Optional[float] = None
    bid_increment: float = Field(default=10.0, ge=1.0)
    start_time: datetime
    end_time: datetime
    soft_close_enabled: bool = True
    soft_close_extension_minutes: int = Field(default=10, ge=1, le=60)
    cleanup_deadline_hours: int = Field(default=72, ge=24, le=168)
    cleanup_deposit: float = Field(default=0.0, ge=0)
    payment_methods_accepted: List[str] = Field(default_factory=lambda: ["stripe", "cash", "etransfer"])


class StorageBidPayload(BaseModel):
    """A user placing a bid (with proxy max)."""
    max_bid: float = Field(..., ge=1)
