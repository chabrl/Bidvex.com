"""
Vehicle Auction Module - Pydantic Models
Standalone, enterprise-grade vehicle auction data models
Completely separate from general marketplace
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timezone
from enum import Enum
import re


# ============= ENUMS =============

class VehicleBodyType(str, Enum):
    SEDAN = "sedan"
    COUPE = "coupe"
    HATCHBACK = "hatchback"
    SUV = "suv"
    CROSSOVER = "crossover"
    TRUCK = "truck"
    VAN = "van"
    MINIVAN = "minivan"
    WAGON = "wagon"
    CONVERTIBLE = "convertible"
    MOTORCYCLE = "motorcycle"
    RV = "rv"
    TRAILER = "trailer"
    BOAT = "boat"
    OTHER = "other"


class TransmissionType(str, Enum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    CVT = "cvt"
    DCT = "dct"
    OTHER = "other"


class FuelType(str, Enum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"
    PLUGIN_HYBRID = "plugin_hybrid"
    HYDROGEN = "hydrogen"
    PROPANE = "propane"
    FLEX_FUEL = "flex_fuel"
    OTHER = "other"


class DrivetrainType(str, Enum):
    FWD = "fwd"
    RWD = "rwd"
    AWD = "awd"
    FOUR_WD = "4wd"
    OTHER = "other"


class TitleStatus(str, Enum):
    CLEAN = "clean"
    SALVAGE = "salvage"
    REBUILT = "rebuilt"
    FLOOD = "flood"
    LEMON = "lemon"
    BONDED = "bonded"
    EXPORT = "export"
    UNKNOWN = "unknown"


class OwnershipStatus(str, Enum):
    OWNED = "owned"
    FINANCED = "financed"
    LEASED = "leased"
    CONSIGNMENT = "consignment"


class LienStatus(str, Enum):
    CLEAR = "clear"
    LIEN_EXISTS = "lien_exists"
    PENDING_RELEASE = "pending_release"
    UNKNOWN = "unknown"


class SellerType(str, Enum):
    PRIVATE = "private"
    DEALER = "dealer"
    AUCTIONEER = "auctioneer"


class SellerVerificationStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class VehicleListingStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    ENDED = "ended"
    SOLD = "sold"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class VehicleAuctionType(str, Enum):
    TIMED = "timed"
    LIVE = "live"
    BUY_NOW = "buy_now"
    TIMED_WITH_BUY_NOW = "timed_with_buy_now"


class VehicleAuctionVisibility(str, Enum):
    PUBLIC = "public"
    DEALER_ONLY = "dealer_only"
    AUCTIONEER_ONLY = "auctioneer_only"


class AuctionAccessType(str, Enum):
    """iter194 — Dealer-controlled bidder access."""
    PUBLIC_INDIVIDUAL = "public_individual"  # Open to all verified buyers
    LICENSED_ONLY = "licensed_only"          # Restricted to licensed_dealer-verified buyers


class VehicleRunStatus(str, Enum):
    """iter194 — Mechanical operational state (Copart-style)."""
    RUN_AND_DRIVE = "run_and_drive"      # Starts, shifts, drives
    STARTS_ONLY = "starts_only"          # Engine starts but does not drive
    NON_OPERATIONAL = "non_operational"  # Does not start / major mechanical failure


class DealerLicenseVerificationStatus(str, Enum):
    """iter194 — Buyer dealer-license verification workflow."""
    NONE = "none"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BidStatus(str, Enum):
    ACTIVE = "active"
    OUTBID = "outbid"
    WINNING = "winning"
    WON = "won"
    CANCELLED = "cancelled"
    RETRACTED = "retracted"


# ============= VIN VALIDATION =============

def validate_vin(vin: str) -> bool:
    """Validate VIN format (17 characters, no I, O, Q)"""
    if not vin or len(vin) != 17:
        return False
    # VIN cannot contain I, O, Q
    if any(c in vin.upper() for c in ['I', 'O', 'Q']):
        return False
    # Must be alphanumeric
    if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', vin.upper()):
        return False
    return True


# ============= VEHICLE SELLER MODELS =============

class VehicleSellerDocument(BaseModel):
    """Document uploaded for seller verification"""
    document_type: Literal["drivers_license", "business_license", "dealer_license", "auctioneer_license", "proof_of_address", "tax_certificate", "other"]
    file_url: str
    file_name: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now())
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    notes: Optional[str] = None


class VehicleSellerCreate(BaseModel):
    """Request model to register as a vehicle seller"""
    seller_type: SellerType
    business_name: Optional[str] = None
    business_address: Optional[str] = None
    business_phone: Optional[str] = None
    license_number: Optional[str] = None
    license_province: Optional[str] = None
    license_expiry: Optional[datetime] = None
    tax_id: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    
    @field_validator('business_name')
    @classmethod
    def business_name_required_for_dealers(cls, v, info):
        if info.data.get('seller_type') in [SellerType.DEALER, SellerType.AUCTIONEER] and not v:
            raise ValueError('Business name required for dealers and auctioneers')
        return v


class VehicleSeller(BaseModel):
    """Complete vehicle seller profile"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    user_id: str
    seller_type: SellerType
    verification_status: SellerVerificationStatus = SellerVerificationStatus.PENDING
    
    # Business Info
    business_name: Optional[str] = None
    business_address: Optional[str] = None
    business_phone: Optional[str] = None
    
    # Licensing
    license_number: Optional[str] = None
    license_province: Optional[str] = None
    license_expiry: Optional[datetime] = None
    tax_id: Optional[str] = None
    
    # Profile
    website: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    
    # Documents
    documents: List[VehicleSellerDocument] = []
    
    # Stats
    total_listings: int = 0
    total_sold: int = 0
    total_revenue: float = 0.0
    average_rating: float = 0.0
    review_count: int = 0
    
    # Limits (enforced at backend)
    monthly_listing_count: int = 0
    monthly_listing_limit: int = 1  # Default for private, 500 for business
    current_month: str = ""  # Format: "2025-01"
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None


# ============= VEHICLE CONDITION MODELS =============

class VehicleConditionReport(BaseModel):
    """Structured condition report for a vehicle"""
    # Running Status
    is_running: bool
    starts_normally: Optional[bool] = None
    engine_runs_smooth: Optional[bool] = None
    
    # Mechanical
    engine_condition: Literal["excellent", "good", "fair", "poor", "non_functional", "unknown"] = "unknown"
    transmission_condition: Literal["excellent", "good", "fair", "poor", "non_functional", "unknown"] = "unknown"
    brakes_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    suspension_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    exhaust_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    
    # Exterior
    body_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    paint_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    glass_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    lights_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    tires_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    
    # Interior
    interior_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    seats_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    dashboard_condition: Literal["excellent", "good", "fair", "poor", "unknown"] = "unknown"
    ac_heating_works: Optional[bool] = None
    electronics_work: Optional[bool] = None
    
    # Damage History
    has_accident_history: Optional[bool] = None
    accident_description: Optional[str] = None
    has_flood_damage: bool = False
    has_fire_damage: bool = False
    has_frame_damage: bool = False
    has_rust_damage: bool = False
    
    # Notes
    mechanical_notes: Optional[str] = None
    cosmetic_notes: Optional[str] = None
    additional_notes: Optional[str] = None


class VehicleMedia(BaseModel):
    """Media item for vehicle listing"""
    id: str
    type: Literal["photo", "video"]
    url: str
    thumbnail_url: Optional[str] = None
    category: Literal["front", "rear", "driver_side", "passenger_side", "interior_front", "interior_rear", "dashboard", "engine", "trunk", "vin_plate", "damage", "document", "other"]
    caption: Optional[str] = None
    order: int = 0
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now())


# ============= VEHICLE LISTING MODELS =============

class VehicleListingCreate(BaseModel):
    """Request model to create a vehicle listing"""
    # VIN (mandatory)
    vin: str
    
    # Basic Info (can be auto-filled from VIN decode)
    year: int
    make: str
    model: str
    trim: Optional[str] = None
    body_type: VehicleBodyType
    
    # Specs
    mileage: int
    transmission: TransmissionType
    fuel_type: FuelType
    drivetrain: DrivetrainType
    engine_size: Optional[str] = None
    cylinders: Optional[int] = None
    horsepower: Optional[int] = None
    
    # Colors
    exterior_color: str
    interior_color: str
    
    # Documentation
    ownership_status: OwnershipStatus
    title_status: TitleStatus
    lien_status: LienStatus
    
    # Condition
    condition_report: VehicleConditionReport
    
    # Location
    location_city: str
    location_province: str
    location_postal_code: str
    
    # Auction Settings
    auction_type: VehicleAuctionType
    visibility: VehicleAuctionVisibility = VehicleAuctionVisibility.PUBLIC
    # iter194 — Dealer access controls (mandatory for dealer listings)
    auction_access: AuctionAccessType = AuctionAccessType.PUBLIC_INDIVIDUAL
    run_status: VehicleRunStatus = VehicleRunStatus.RUN_AND_DRIVE
    start_time: datetime
    end_time: datetime
    starting_price: float
    reserve_price: Optional[float] = None
    buy_now_price: Optional[float] = None
    bid_increment: float = 100.0
    
    # Deposit
    requires_deposit: bool = True
    deposit_amount: float = 500.0
    
    # Description
    title: str
    description: str
    features: List[str] = []

    # iter198 — Pilot conversion attribution (e.g. "pilot-welcome-banner")
    utm_source: Optional[str] = None

    # iter201 — Phase 2 — Vehicle category taxonomy (CEO 15-category spec)
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None

    # iter201 — Phase 2 — Quebec bilingual fields (FR mandatory when location_province=QC)
    title_fr: Optional[str] = None
    description_fr: Optional[str] = None

    # iter285 — Bug 4 — Provincial registration eligibility. Either ['ALL'] or
    # an explicit list of 2-letter Canadian province codes (QC, ON, BC, …).
    # Optional on existing listings — absence renders the "Eligibility TBD"
    # warning on the buyer side, never blocks rendering.
    eligible_provinces: Optional[List[str]] = None
    inspection_status: Optional[str] = None  # safety_certified | e_tested | mvi_passed | as_is

    # iter286 — Bug 5 — Carfax / vehicle-history references.
    # `carfax_url` is the official Carfax CA shareable link. `carfax_file`
    # is an uploaded PDF (S3 URL). `inspection_file` is an optional
    # safety/MVI PDF. Documents are gated to broker-partner accounts on
    # the buyer side; sellers can attach them during listing creation.
    carfax_url: Optional[str] = None
    carfax_file: Optional[str] = None
    inspection_file: Optional[str] = None

    # iter292 — Directive 3: Dealer-controlled lifecycle intent at submit time.
    # `submission_intent` drives the post-create status:
    #   - "draft"    → status=DRAFT, hidden from public listings until edited
    #                  forward; bypasses the trusted-seller auto-promote.
    #   - "schedule" → status=ACTIVE with the supplied future start_time;
    #                  visible publicly as Upcoming, bidding gated until
    #                  start_time.
    #   - "live"     → status=ACTIVE with start_time=now(); bidding opens
    #                  immediately. Default — preserves existing behaviour.
    submission_intent: Optional[str] = "live"

    @field_validator('vin')
    @classmethod
    def validate_vin_format(cls, v):
        if not validate_vin(v):
            raise ValueError('Invalid VIN format. Must be 17 characters, alphanumeric, no I/O/Q')
        return v.upper()
    
    @field_validator('year')
    @classmethod
    def validate_year(cls, v):
        current_year = datetime.now().year
        if v < 1900 or v > current_year + 1:
            raise ValueError(f'Year must be between 1900 and {current_year + 1}')
        return v
    
    @field_validator('mileage')
    @classmethod
    def validate_mileage(cls, v):
        if v < 0:
            raise ValueError('Mileage cannot be negative')
        return v
    
    @field_validator('starting_price', 'reserve_price', 'buy_now_price', 'deposit_amount')
    @classmethod
    def validate_prices(cls, v):
        if v is not None and v < 0:
            raise ValueError('Price cannot be negative')
        return v


class VehicleListing(BaseModel):
    """Complete vehicle listing"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    seller_id: str
    seller_user_id: str
    
    # VIN
    vin: str
    vin_decoded: bool = False
    vin_data: Optional[Dict[str, Any]] = None
    
    # Basic Info
    year: int
    make: str
    model: str
    trim: Optional[str] = None
    body_type: VehicleBodyType
    
    # Specs
    mileage: int
    transmission: TransmissionType
    fuel_type: FuelType
    drivetrain: DrivetrainType
    engine_size: Optional[str] = None
    cylinders: Optional[int] = None
    horsepower: Optional[int] = None
    
    # Colors
    exterior_color: str
    interior_color: str
    
    # Documentation
    ownership_status: OwnershipStatus
    title_status: TitleStatus
    lien_status: LienStatus
    inspection_report_url: Optional[str] = None
    title_document_url: Optional[str] = None
    
    # Condition
    condition_report: VehicleConditionReport
    
    # Location
    location_city: str
    location_province: str
    location_postal_code: str
    
    # Auction Settings
    auction_type: VehicleAuctionType
    visibility: VehicleAuctionVisibility
    # iter194 — Dealer access controls
    auction_access: AuctionAccessType = AuctionAccessType.PUBLIC_INDIVIDUAL
    run_status: VehicleRunStatus = VehicleRunStatus.RUN_AND_DRIVE
    start_time: datetime
    end_time: datetime
    original_end_time: datetime  # For tracking extensions
    starting_price: float
    reserve_price: Optional[float] = None
    reserve_met: bool = False
    buy_now_price: Optional[float] = None
    bid_increment: float
    
    # Deposit
    requires_deposit: bool
    deposit_amount: float
    
    # Description
    title: str
    description: str
    features: List[str] = []
    
    # Media (minimum 10 photos required)
    media: List[VehicleMedia] = []
    
    # Status
    status: VehicleListingStatus = VehicleListingStatus.DRAFT
    rejection_reason: Optional[str] = None
    
    # Bidding Stats
    current_bid: float = 0.0
    bid_count: int = 0
    highest_bidder_id: Optional[str] = None
    watchers_count: int = 0
    views_count: int = 0
    
    # Winner
    winner_id: Optional[str] = None
    final_price: Optional[float] = None
    sold_at: Optional[datetime] = None

    # iter194 — Buyer Unlock Flow (dealer contact gating)
    unlock_required: bool = True
    unlock_paid_at: Optional[datetime] = None
    unlock_payment_intent_id: Optional[str] = None
    unlock_amount_charged: Optional[float] = None    # Total charged to buyer (gross)
    unlock_platform_net: Optional[float] = None      # 2.5% net to BidVex (excludes Stripe fees)

    # Fees
    buyer_premium_percent: float = 5.0  # 5% buyer premium
    platform_fee_percent: float = 2.5   # 2.5% platform fee
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None


# ============= BIDDING MODELS =============

class VehicleBidCreate(BaseModel):
    """Request model to place a bid"""
    vehicle_id: str
    amount: float
    max_bid: Optional[float] = None  # For proxy bidding
    
    @field_validator('amount', 'max_bid')
    @classmethod
    def validate_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Bid amount must be positive')
        return v


class VehicleBid(BaseModel):
    """Complete bid record"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    vehicle_id: str
    bidder_id: str
    bidder_name: str  # Anonymized display name
    
    amount: float
    max_bid: Optional[float] = None
    status: BidStatus = BidStatus.ACTIVE
    
    # Deposit
    deposit_paid: bool = False
    deposit_transaction_id: Optional[str] = None
    deposit_refunded: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    retracted_at: Optional[datetime] = None
    retraction_reason: Optional[str] = None


class VehicleBidDeposit(BaseModel):
    """Bid deposit record"""
    id: str
    vehicle_id: str
    bidder_id: str
    amount: float
    
    status: Literal["pending", "paid", "refunded", "forfeited"]
    payment_intent_id: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    paid_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None


# ============= INVOICE MODELS =============

class VehicleInvoiceLineItem(BaseModel):
    """Invoice line item"""
    description: str
    amount: float


class VehicleInvoice(BaseModel):
    """Invoice for won vehicle"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: str
    invoice_number: str
    vehicle_id: str
    vehicle_title: str
    vehicle_vin: str
    
    seller_id: str
    buyer_id: str
    
    # Amounts
    hammer_price: float
    buyer_premium: float
    platform_fee: float
    taxes_gst: float = 0.0
    taxes_qst: float = 0.0
    taxes_pst: float = 0.0
    taxes_hst: float = 0.0
    total_amount: float
    
    # Line Items
    line_items: List[VehicleInvoiceLineItem] = []
    
    # Payment
    payment_status: Literal["pending", "partial", "paid", "overdue", "refunded"]
    payment_deadline: datetime
    payment_method: Optional[str] = None
    paid_at: Optional[datetime] = None
    
    # Deposit Credit
    deposit_credited: float = 0.0
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    sent_at: Optional[datetime] = None


# ============= LEGAL ACCEPTANCE =============

class LegalAcceptance(BaseModel):
    """Record of legal terms acceptance"""
    id: str
    user_id: str
    vehicle_id: Optional[str] = None
    
    acceptance_type: Literal["seller_terms", "buyer_terms", "bid_terms", "as_is_where_is"]
    accepted: bool = True
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now())


# ============= ADMIN AUDIT LOG =============

class VehicleAuditLog(BaseModel):
    """Audit log for vehicle module actions"""
    id: str
    entity_type: Literal["vehicle", "seller", "bid", "invoice"]
    entity_id: str
    action: str
    
    performed_by: str
    performed_by_role: Literal["admin", "seller", "buyer", "system"]
    
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now())



# ============= DEALER LICENSE VERIFICATION (iter194) =============

class DealerLicenseSubmit(BaseModel):
    """Buyer submits proof of dealer license to access licensed-only auctions."""
    license_number: str = Field(..., min_length=2, max_length=64)
    jurisdiction: str = Field(..., min_length=2, max_length=64)  # e.g. "QC", "ON", "BC"
    expiry_date: datetime
    document_url: str  # uploaded file path (use existing media upload endpoint)


class DealerLicense(BaseModel):
    """Dealer license verification record (one per user)."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str
    license_number: str
    jurisdiction: str
    expiry_date: datetime
    document_url: str
    status: DealerLicenseVerificationStatus = DealerLicenseVerificationStatus.PENDING
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DealerLicenseAdminAction(BaseModel):
    """Admin approve/reject decision."""
    decision: str  # "approve" | "reject"
    rejection_reason: Optional[str] = None


# ============= UNLOCK FEE (iter194) =============

class UnlockFeeQuote(BaseModel):
    """Returned by GET /api/vehicles/{id}/unlock-quote — buyer sees full breakdown."""
    listing_id: str
    winning_bid: float
    platform_fee_percent: float = 2.5
    platform_fee_net: float          # 2.5% of winning bid (BidVex's net revenue)
    stripe_processing_fee: float     # Stripe's cut (so BidVex gets full 2.5% net)
    total_charge_to_buyer: float     # platform_fee_net + stripe_processing_fee
    currency: str = "CAD"


class UnlockFeeIntent(BaseModel):
    """Returned by POST /api/vehicles/{id}/unlock-fee/checkout."""
    listing_id: str
    payment_intent_id: str
    client_secret: str
    publishable_key: str
    quote: UnlockFeeQuote


class DealerContactReveal(BaseModel):
    """Post-unlock dealer contact details (only returned after unlock_paid_at is set)."""
    seller_name: str
    seller_phone: Optional[str] = None
    seller_email: Optional[str] = None
    seller_business_name: Optional[str] = None
    pickup_address: str
    pickup_city: str
    pickup_province: str
    pickup_postal_code: str
    additional_notes: Optional[str] = None
