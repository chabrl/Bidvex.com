"""
BidVex Storage Unit Auction Models — iteration 170
==================================================
Two MongoDB collections:
  • storage_facilities  — verified Canadian self-storage operators
  • storage_auctions    — individual unit auctions (lien or non-lien)

NEW in iter170:
  • Single `payment_method` per auction (stripe | cash | etransfer)
  • Optional participation `deposit_required` + `deposit_amount`
  • storage_deposits collection (escrow holds via Stripe PI)

Pricing rules (single source of truth — see services/storage_pricing.py):
  • Stripe path → BidVex collects 5% + Stripe + tax from BUYER (facility nets full hammer)
  • Cash/E-Transfer path → buyer pays facility off-platform (hammer only)
       BidVex invoices FACILITY 5% + Stripe + tax
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator


CANADIAN_PROVINCES = ["AB", "BC", "MB", "NB", "NL", "NS", "ON", "PE", "QC", "SK", "NT", "NU", "YT"]
UNIT_SIZES = ["5x5", "5x10", "10x10", "10x15", "10x20", "10x30+"]
UNIT_TYPES = ["indoor", "outdoor", "climate_controlled", "drive_up"]
PAYMENT_METHODS = ["stripe", "cash", "etransfer"]
AUCTION_STATUSES = ["upcoming", "active", "ended", "sold", "cancelled"]

# iter212 — Allowed registration types per Canadian jurisdiction.
# Federal (CRA BN) is universally available as an alternative for every province.
REGISTRATION_TYPES = [
    "federal_bn",         # CRA Business Number (9 digit + RC0001)
    "qc_neq",             # Quebec — Numéro d'entreprise du Québec (10 digits)
    "on_ocn",             # Ontario Corporation Number (8-10 digits)
    "bc_registry",        # BC Registry number (7+ digits)
    "ab_corporate",       # Alberta Corporate Access Number (10 digits)
    "provincial_other",   # SK / MB / NS / NB / NL / PE — free text
    "territorial_other",  # NT / NU / YT — free text
]


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
    business_registration_number: Optional[str] = None
    opc_permit_number: Optional[str] = None
    accepted_terms: bool
    # iter212 — Provincial Business Registration (REQUIRED for new facilities)
    company_registration_type: Optional[str] = None          # one of REGISTRATION_TYPES
    company_registration_number: Optional[str] = None        # the actual ID typed by the user
    company_registration_document_url: Optional[str] = None  # /api/uploads/storage_facilities/{id}/{filename}


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
    soft_close_extension_minutes: int = Field(default=2, ge=1, le=60)
    cleanup_deadline_hours: int = Field(default=72, ge=24, le=168)

    # ── PAYMENT METHOD (single) ──
    payment_method: str = Field(default="stripe")  # stripe | cash | etransfer

    # ── PARTICIPATION DEPOSIT (optional) ──
    deposit_required: bool = False
    deposit_amount: Optional[float] = Field(default=None, ge=0)
    deposit_type: Optional[str] = Field(default="fixed")  # "fixed" | "percentage" (Spec Feature 1)
    deposit_description_en: Optional[str] = None
    deposit_description_fr: Optional[str] = None

    # ── CURRENCY (Spec Global Rule 1) ──
    currency: str = Field(default="CAD")  # "CAD" | "USD"

    @field_validator("payment_method")
    @classmethod
    def _vm(cls, v):
        v = (v or "").lower()
        if v not in PAYMENT_METHODS:
            raise ValueError(f"payment_method must be one of {PAYMENT_METHODS}")
        return v

    @model_validator(mode="after")
    def _vd(self):
        if self.deposit_required and (self.deposit_amount is None or self.deposit_amount <= 0):
            raise ValueError(
                "deposit_amount must be > 0 when deposit_required is true. "
                "Le montant du dépôt doit être supérieur à 0 si un dépôt est requis."
            )
        return self


class StorageBidPayload(BaseModel):
    """A user placing a bid (with proxy max)."""
    max_bid: float = Field(..., ge=1)


class StorageDepositRequest(BaseModel):
    """Buyer pays the participation deposit before placing first bid."""
    payment_method_id: str  # Stripe payment_method id (pm_xxx) from frontend Elements
