"""
BidVex User Schema Extension
Defines Pydantic models for user tax and business information

New fields for marketplace engine finalization:
- is_business: Boolean - Whether user operates as a business
- is_tax_registered: Boolean - Whether user has valid tax registration
- tax_id: String - GST/QST or business number
- stripe_connect_account_id: String - Stripe Connect account for payouts
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AccountType(str, Enum):
    """User account type"""
    PERSONAL = "personal"
    BUSINESS = "business"


# ── Seller Type ─────────────────────────────────────────────────
# The canonical 3-state value used by the pricing engine.
# Drives BP/SC routing, tax behavior, and listing badges.
SELLER_TYPE_INDIVIDUAL = "individual"
SELLER_TYPE_PARTNER = "partner"
SELLER_TYPE_ENTERPRISE = "enterprise"
ALLOWED_SELLER_TYPES = {
    SELLER_TYPE_INDIVIDUAL,
    SELLER_TYPE_PARTNER,
    SELLER_TYPE_ENTERPRISE,
}


def resolve_seller_type(user: dict) -> str:
    """
    Canonical resolver for a user's seller_type.

    Order of precedence:
      1. Explicit `seller_type` field if already set and valid.
      2. `is_partner=True` → "partner"
      3. `account_type="business"` (or `is_business=True`) → "enterprise"
      4. Default → "individual"
    """
    if not user:
        return SELLER_TYPE_INDIVIDUAL
    explicit = (user.get("seller_type") or "").lower().strip()
    if explicit in ALLOWED_SELLER_TYPES:
        return explicit
    if user.get("is_partner") is True:
        return SELLER_TYPE_PARTNER
    if (user.get("account_type") or "").lower() == "business" or user.get("is_business") is True:
        return SELLER_TYPE_ENTERPRISE
    return SELLER_TYPE_INDIVIDUAL


class UserTaxInfo(BaseModel):
    """User tax and business registration information"""
    is_business: bool = Field(default=False, description="Whether user operates as a registered business")
    is_tax_registered: bool = Field(default=False, description="Whether user has valid tax registration (GST/QST)")
    tax_id: Optional[str] = Field(default=None, description="Business tax registration number (GST/QST)")
    business_name: Optional[str] = Field(default=None, description="Registered business name")
    business_address: Optional[str] = Field(default=None, description="Business address")


class UserStripeInfo(BaseModel):
    """User Stripe integration information"""
    stripe_customer_id: Optional[str] = Field(default=None, description="Stripe customer ID for payments")
    stripe_connect_account_id: Optional[str] = Field(default=None, description="Stripe Connect account ID for payouts")
    stripe_connect_onboarding_complete: bool = Field(default=False, description="Whether Stripe Connect onboarding is complete")
    stripe_subscription_id: Optional[str] = Field(default=None, description="Active subscription ID")


class UpdateUserTaxInfo(BaseModel):
    """Request model for updating user tax information"""
    is_business: Optional[bool] = None
    is_tax_registered: Optional[bool] = None
    tax_id: Optional[str] = None
    business_name: Optional[str] = None
    business_address: Optional[str] = None


class UserSellerProfile(BaseModel):
    """Complete seller profile with tax and payout info"""
    id: str
    name: str
    email: str
    account_type: AccountType = AccountType.PERSONAL
    
    # Tax info
    is_business: bool = False
    is_tax_registered: bool = False
    tax_id: Optional[str] = None
    business_name: Optional[str] = None
    
    # Stripe Connect
    stripe_connect_account_id: Optional[str] = None
    stripe_connect_onboarding_complete: bool = False
    
    # Subscription
    subscription_tier: str = "basic"
    
    # Verification
    admin_verified: bool = False
    email_verified: bool = False
    phone_verified: bool = False


# Default fields to add to new users
DEFAULT_USER_TAX_FIELDS = {
    "is_business": False,
    "is_tax_registered": False,
    "tax_id": None,
    "business_name": None,
    "business_address": None,
    "stripe_connect_account_id": None,
    "stripe_connect_onboarding_complete": False
}
