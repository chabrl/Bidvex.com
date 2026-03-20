"""
BidVex - Shared configuration, models, and utilities.
Extracted from server.py to keep the entry point clean.
"""

from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import random
import string
import logging

logger = logging.getLogger(__name__)

# ─── Affiliate Constants ───
AFFILIATE_COMMISSION_RATE = 0.015

def generate_affiliate_code(user_id: str) -> str:
    prefix = user_id[:8].upper()
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BVX{prefix}{suffix}"

# ─── Email Template Defaults ───
DEFAULT_EMAIL_TEMPLATES = {
    "auth_password_reset_en": "d-dbfba723dd5e4895a579b462b19c56fb",
    "auth_password_reset_fr": "d-9084b4478e024056a9fa5207fdfc91e6",
    "auth_password_changed_en": "d-1e018cb66df54ee58616f9abd0720b0f",
    "auth_password_changed_fr": "d-16ad9371e1c54f2996f4ff453dfc2b82",
    "auth_email_verification_en": "d-79352dd5a50849c7bb4cbe93e726051f",
    "auth_email_verification_fr": "d-48d6d49961ab439f89d55b890bc84b8a",
    "auth_welcome_en": "d-db7d296ad54247138f3f210a1fb52e0a",
    "auth_welcome_fr": "d-256f3801670441808730c4cfb259d9a2",
    "auth_two_factor_en": "d-7fe6f17a934f491ca91aa36534be85e2",
    "auth_two_factor_fr": "d-ec1e531f92bc4d01bf24dc47620cabed",
    "auth_login_alert_en": "d-2cbb18036b9e44e4ba67ac3ee614e339",
    "auth_login_alert_fr": "d-2e3509d0a8c3480e83cd0d6b6ffc8c25",
    "admin_account_suspended_en": "d-cf2d8fb5bad74d4ab00b85236a93755d",
    "admin_account_suspended_fr": "d-89596fbe221f4740aa29cff3d09d6754",
    "admin_report_received_en": "d-539a4d89254f42baa38de4f139e7a36b",
    "admin_report_received_fr": "d-1e6b72f9301c49949b9a5cb21f0a39d5",
    "comm_announcement_en": "d-877f77c6623b4ed3879e4a7fcab2f8a5",
    "comm_announcement_fr": "d-b1fd6b2e096d47bb95c96fc9ca93af68",
    "comm_support_ack_en": "d-5a4bdee8c66041ba8d44ba0d7fc0244a",
    "comm_support_ack_fr": "d-7ecc0e3ab5c24c8283416a0e1ef4c9eb",
    "comm_platform_updates_en": "d-268de17d00514f3bb674e688d414b157",
    "comm_platform_updates_fr": "d-3dc15879450146dd9e1d48e59dc8cccc",
    "fin_invoice_issued_en": "d-d25445886edb4cc08cc8107b07cb343f",
    "fin_invoice_issued_fr": "d-780daa32909e438aad5ee459cb21703a",
    "fin_payment_receipt_en": "d-5f88411aa2584e63afccbbe6603b3b3a",
    "fin_payment_receipt_fr": "d-110c93dfaea74c439488cdbe89985bf3",
    "fin_payout_sent_en": "d-36b5f93ff1064b8c815253aa60c02829",
    "fin_payout_sent_fr": "d-73eae4ffc4e9404f9aa931493a4f2724",
    "seller_new_bid_en": "d-da5049e2aac143aa937c4dd113d9fb96",
    "seller_new_bid_fr": "d-5e45290634c648d5aa818a733a94f13d",
    "seller_listing_approved_en": "d-e65e2943cc6d4b0b968fb0f877357fc0",
    "seller_listing_approved_fr": "d-2d34d8977ef84acaad852ddf73cf8fb7",
    "seller_listing_rejected_en": "d-57976d80ab25467cad32db22cd11d06b",
    "seller_listing_rejected_fr": "d-168a20ae972845658e166bc442904136",
    "auction_announcement_en": "d-e525a2ab091a42049f75fb9d102b9cde",
    "auction_announcement_fr": "d-7a20775199774c5b84e0c3c12c1721a6",
    "auction_reminder_en": "d-7ae5b7a394494823b16e71a1029e1e6e",
    "auction_reminder_fr": "d-8c5efdf9cd2449a7b288bc8d3be54885",
    "auction_results_en": "d-4c519ffa806f41729c07b5c9feca09ab",
    "auction_results_fr": "d-284252b173364ddab13854da54c70a87",
    "bid_outbid_en": "d-89c95108533249aaa1659e258f11dd90",
    "bid_outbid_fr": "d-94110d612e1243a58fc28c99872cfce6",
    "bid_confirmed_en": "d-fde06627d9dc4b79a250123604efb39c",
    "bid_confirmed_fr": "d-e1fec1eab388405cb172f71c7b6e7879",
    "bid_winning_en": "d-27a3e1edafe24fa09437ab929eeab070",
    "bid_winning_fr": "d-a790684646d0430b91686923b46bf697",
    "affiliate_monthly_earnings_en": "d-bacce34b0273477f8e7e4df61b737512",
    "affiliate_monthly_earnings_fr": "d-7e4e67d882ad490fac384ab166e7f89b",
    "affiliate_commission_earned_en": "d-60618f4cb6d54a579fe4cc82052ea41d",
    "affiliate_commission_earned_fr": "d-df3d97fe87b34060b5b6dee14977efcd",
    "affiliate_referral_notification_en": "d-da95ceff24c54d39b15a29e56d804ee9",
    "affiliate_referral_notification_fr": "d-32a08f1a11a7441186944747602cfd53",
    "affiliate_program_summary_en": "d-ea4ab5b49ce9448fa552303fa5e9e2cd",
    "affiliate_program_summary_fr": "d-b7e970f39ce748c0bc3773a5a5606a91",
}

EMAIL_TEMPLATE_CATEGORIES = {
    "authentication": {
        "name": "Authentication",
        "description": "User authentication emails (login, password, verification)",
        "icon": "lock",
        "keys": ["auth_password_reset", "auth_password_changed", "auth_email_verification",
                 "auth_welcome", "auth_two_factor", "auth_login_alert"]
    },
    "financial": {
        "name": "Financial",
        "description": "Invoices, receipts, and payout notifications",
        "icon": "dollar",
        "keys": ["fin_invoice_issued", "fin_payment_receipt", "fin_payout_sent"]
    },
    "bidding": {
        "name": "Bidding & Auction",
        "description": "Bid confirmations, outbid alerts, and auction results",
        "icon": "gavel",
        "keys": ["bid_outbid", "bid_confirmed", "bid_winning", "auction_announcement",
                 "auction_reminder", "auction_results"]
    },
    "seller": {
        "name": "Seller Notifications",
        "description": "Seller-specific emails for bids and listing status",
        "icon": "store",
        "keys": ["seller_new_bid", "seller_listing_approved", "seller_listing_rejected"]
    },
    "communication": {
        "name": "Communication & Admin",
        "description": "Announcements, support acknowledgments, and admin alerts",
        "icon": "megaphone",
        "keys": ["comm_announcement", "comm_support_ack", "comm_platform_updates",
                 "admin_account_suspended", "admin_report_received"]
    },
    "affiliate": {
        "name": "Affiliate Program",
        "description": "Commission and referral notifications",
        "icon": "handshake",
        "keys": ["affiliate_monthly_earnings", "affiliate_commission_earned",
                 "affiliate_referral_notification"]
    }
}

# ─── Marketplace Settings Defaults ───
DEFAULT_MARKETPLACE_SETTINGS = {
    "id": "marketplace_settings",
    "allow_all_users_multi_lot": True,
    "require_approval_new_sellers": False,
    "max_active_auctions_per_user": 20,
    "max_lots_per_auction": 50,
    "minimum_bid_increment": 1.0,
    "enable_anti_sniping": True,
    "anti_sniping_window_minutes": 2,
    "enable_buy_now": True,
    "updated_at": None,
    "updated_by": None
}

# ─── Fee Constants ───
STANDARD_BUYER_PREMIUM_RATE = 0.05
STANDARD_SELLER_COMMISSION_RATE = 0.04
PARTNER_PLATFORM_FEE_RATE = 0.03
PARTNER_ANNUAL_ACCESS_FEE = 100.00
STRIPE_PERCENTAGE_FEE = 0.029
STRIPE_FIXED_FEE = 0.30

class FeeCalculation(BaseModel):
    base_amount: float
    fee_percentage: float
    fee_amount: float
    total_amount: float
    is_premium_member: bool
    discount_applied: float

def calculate_stripe_fee_recovery(desired_net: float) -> float:
    total_to_charge = (desired_net + STRIPE_FIXED_FEE) / (1 - STRIPE_PERCENTAGE_FEE)
    return round(total_to_charge - desired_net, 2)

def calculate_partner_checkout(hammer_price: float, custom_buyer_premium_rate: float = 0.0) -> dict:
    platform_fee = round(hammer_price * PARTNER_PLATFORM_FEE_RATE, 2)
    buyer_premium = round(hammer_price * custom_buyer_premium_rate, 2)
    stripe_base = hammer_price + buyer_premium
    stripe_fee = calculate_stripe_fee_recovery(stripe_base)
    total_buyer_pays = round(hammer_price + buyer_premium + stripe_fee, 2)
    return {
        "hammer_price": hammer_price,
        "buyer_premium_rate": custom_buyer_premium_rate,
        "buyer_premium": buyer_premium,
        "platform_fee_rate": PARTNER_PLATFORM_FEE_RATE,
        "platform_fee": platform_fee,
        "stripe_fee": stripe_fee,
        "total_buyer_pays": total_buyer_pays,
        "seller_receives": round(hammer_price - platform_fee, 2),
        "bidvex_revenue": platform_fee,
    }

def calculate_standard_checkout(hammer_price: float, buyer_subscription_tier: str = "free") -> dict:
    buyer_premium_rate = STANDARD_BUYER_PREMIUM_RATE
    discount = 0.0
    if buyer_subscription_tier == "premium":
        discount = 0.25
    elif buyer_subscription_tier == "vip":
        discount = 0.50
    effective_rate = buyer_premium_rate * (1 - discount)
    buyer_premium = round(hammer_price * effective_rate, 2)
    seller_commission = round(hammer_price * STANDARD_SELLER_COMMISSION_RATE, 2)
    stripe_base = hammer_price + buyer_premium
    stripe_fee = calculate_stripe_fee_recovery(stripe_base)
    total_buyer_pays = round(hammer_price + buyer_premium + stripe_fee, 2)
    return {
        "hammer_price": hammer_price,
        "buyer_premium_rate": effective_rate,
        "buyer_premium": buyer_premium,
        "seller_commission_rate": STANDARD_SELLER_COMMISSION_RATE,
        "seller_commission": seller_commission,
        "stripe_fee": stripe_fee,
        "total_buyer_pays": total_buyer_pays,
        "seller_receives": round(hammer_price - seller_commission, 2),
        "bidvex_revenue": round(buyer_premium + seller_commission, 2),
        "discount_applied": discount,
    }

def calculate_buyer_fees(hammer_price: float, subscription_tier: str = "free") -> FeeCalculation:
    base_rate = STANDARD_BUYER_PREMIUM_RATE
    discount = 0.0
    if subscription_tier == "premium":
        discount = 0.25
    elif subscription_tier == "vip":
        discount = 0.50
    effective_rate = base_rate * (1 - discount)
    fee = round(hammer_price * effective_rate, 2)
    return FeeCalculation(
        base_amount=hammer_price, fee_percentage=effective_rate,
        fee_amount=fee, total_amount=round(hammer_price + fee, 2),
        is_premium_member=subscription_tier != "free", discount_applied=discount,
    )

def calculate_seller_fees(hammer_price: float, subscription_tier: str = "free") -> FeeCalculation:
    base_rate = STANDARD_SELLER_COMMISSION_RATE
    discount = 0.0
    if subscription_tier == "premium":
        discount = 0.25
    elif subscription_tier == "vip":
        discount = 0.50
    effective_rate = base_rate * (1 - discount)
    fee = round(hammer_price * effective_rate, 2)
    return FeeCalculation(
        base_amount=hammer_price, fee_percentage=effective_rate,
        fee_amount=fee, total_amount=round(hammer_price - fee, 2),
        is_premium_member=subscription_tier != "free", discount_applied=discount,
    )

# ─── Timestamp Helper ───
def get_epoch_timestamp(dt) -> int:
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return 0
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    return 0

def get_server_timestamp() -> int:
    return int(datetime.now(timezone.utc).timestamp())

# ─── DB Helper Functions ───
async def get_email_templates(db):
    templates = await db.email_settings.find_one({"id": "email_templates"}, {"_id": 0})
    if not templates:
        templates = {
            "id": "email_templates",
            "templates": DEFAULT_EMAIL_TEMPLATES,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "system"
        }
        await db.email_settings.insert_one(templates)
    return templates

async def get_email_template_id(db, template_key: str, language: str = "en") -> str:
    templates = await get_email_templates(db)
    template_dict = templates.get("templates", {})
    lang_key = f"{template_key}_{language}"
    if lang_key in template_dict:
        return template_dict[lang_key]
    en_key = f"{template_key}_en"
    if en_key in template_dict:
        return template_dict[en_key]
    return "d-default-template-id"

async def get_marketplace_settings(db):
    settings = await db.settings.find_one({"id": "marketplace_settings"}, {"_id": 0})
    if not settings:
        settings = {**DEFAULT_MARKETPLACE_SETTINGS, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.settings.insert_one(settings)
    return settings

# ─── Extra Pydantic Models (not yet in models/ package) ───
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    account_type: str
    phone: str
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None
    terms_agreed: bool = False

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class Category(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    name_en: Optional[str] = None
    name_fr: Optional[str] = None
    icon: Optional[str] = None
    slug: Optional[str] = None
    parent_id: Optional[str] = None
    subcategories: List[str] = Field(default_factory=list)

class SessionCreate(BaseModel):
    participant_id: str
    listing_id: Optional[str] = None

class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    buyer_id: str
    seller_id: str
    listing_id: str
    amount: float
    status: str = "pending"
    stripe_payment_intent_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class PaddleNumber(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    auction_id: str
    paddle_number: int
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Invoice(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_number: str
    invoice_type: str
    auction_id: str
    user_id: str
    seller_id: Optional[str] = None
    items: List[Dict] = Field(default_factory=list)
    subtotal: float = 0.0
    gst_amount: float = 0.0
    qst_amount: float = 0.0
    total_amount: float = 0.0
    buyer_premium: float = 0.0
    seller_commission: float = 0.0
    platform_fee: float = 0.0
    currency: str = "CAD"
    status: str = "issued"
    pdf_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentMethodCreate(BaseModel):
    stripe_payment_method_id: str

class PaymentMethodResponse(BaseModel):
    id: str
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool = False

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Dict[str, str]] = None
    picture: Optional[str] = None

class LocationSearchParams(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 50.0
    category: Optional[str] = None
    limit: int = 50

# ─── Bid Increment Functions ───
def get_minimum_increment_tiered(current_bid: float) -> float:
    if current_bid < 50:
        return 1.0
    elif current_bid < 100:
        return 2.50
    elif current_bid < 250:
        return 5.0
    elif current_bid < 500:
        return 10.0
    elif current_bid < 1000:
        return 25.0
    elif current_bid < 2500:
        return 50.0
    elif current_bid < 5000:
        return 100.0
    elif current_bid < 10000:
        return 250.0
    elif current_bid < 25000:
        return 500.0
    elif current_bid < 50000:
        return 1000.0
    elif current_bid < 100000:
        return 2500.0
    else:
        return 5000.0

def get_minimum_increment_simplified(current_bid: float) -> float:
    if current_bid < 100:
        return 1.0
    elif current_bid < 1000:
        return 5.0
    elif current_bid < 10000:
        return 25.0
    else:
        return 100.0

def get_minimum_increment(auction: dict, current_bid: float) -> float:
    increment_type = auction.get("increment_type", "auto_tiered")
    if increment_type == "fixed":
        return auction.get("fixed_increment", 1.0)
    elif increment_type == "auto_simplified":
        return get_minimum_increment_simplified(current_bid)
    else:
        return get_minimum_increment_tiered(current_bid)

# ─── Additional Pydantic Models for extracted routes ───

class SiteModeUpdate(BaseModel):
    mode: str = Field(..., description="Site mode: live, maintenance, coming_soon")
    message: Optional[str] = None
    expected_back: Optional[str] = None
    social_links: Optional[dict] = None

class EmailSubscription(BaseModel):
    email: EmailStr

class BannerCreate(BaseModel):
    title: str
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    position: Optional[str] = "homepage"
    active: bool = True
    order: int = 0

class CurrencyAppeal(BaseModel):
    listing_id: str
    reason: str
    preferred_currency: str
    additional_info: Optional[str] = None

class AdvancedAudiencePreviewRequest(BaseModel):
    segment_type: Optional[str] = "all"
    filters: Optional[Dict] = None
    custom_query: Optional[Dict] = None

class CampaignCreateRequest(BaseModel):
    name: str
    subject: str
    content: Optional[str] = None
    template_id: Optional[str] = None
    segment_type: Optional[str] = "all"
    scheduled_at: Optional[str] = None

class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    template_id: Optional[str] = None
    segment_type: Optional[str] = None
    scheduled_at: Optional[str] = None
    status: Optional[str] = None

class UserContactCreateRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    tags: Optional[List[str]] = None

class UserContactBulkRequest(BaseModel):
    contacts: List[Dict]

class UserCampaignCreateRequest(BaseModel):
    name: str
    subject: str
    content: Optional[str] = None
    template_id: Optional[str] = None
    contact_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    scheduled_at: Optional[str] = None
