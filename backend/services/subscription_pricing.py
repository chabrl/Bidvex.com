"""
BidVex Subscription Pricing & Coupon Management Service
Handles dynamic pricing, coupon codes, and Stripe synchronization
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, field_validator, ValidationInfo
import stripe
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe_api_key = os.environ.get('STRIPE_API_KEY', '')
try:
    if stripe_api_key and stripe_api_key != "your-stripe-api-key-here":
        stripe.api_key = stripe_api_key
        logger.info("Stripe initialized in subscription_pricing")
    else:
        logger.info("Stripe disabled in subscription_pricing — valid API key not yet provided")
except Exception as e:
    logger.warning(f"Stripe unavailable in subscription_pricing: {e}")


# ========== PYDANTIC MODELS ==========

class PlanPricing(BaseModel):
    """Subscription plan pricing model"""
    plan_id: str = Field(..., description="Plan identifier: free, premium, vip")
    name: str = Field(..., description="Display name")
    price_monthly: float = Field(0.0, ge=0, description="Monthly price in CAD")
    price_yearly: float = Field(0.0, ge=0, description="Yearly price in CAD")
    original_price_monthly: float = Field(0.0, ge=0, description="Original monthly price for promotional display")
    original_price_yearly: float = Field(0.0, ge=0, description="Original yearly price for promotional display")
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_yearly: Optional[str] = None
    stripe_product_id: Optional[str] = None
    features: List[str] = []
    buyer_premium_discount: float = Field(0.0, ge=0, le=100, description="Discount percentage")
    seller_commission_discount: float = Field(0.0, ge=0, le=100, description="Discount percentage")
    monthly_listing_limit: int = Field(10, ge=0)
    is_active: bool = True
    
    @field_validator('price_monthly', 'price_yearly', 'original_price_monthly', 'original_price_yearly', mode='before')
    @classmethod
    def validate_price(cls, v):
        if v is None:
            return 0.0
        if isinstance(v, (int, float)) and v < 0:
            raise ValueError('Price must be non-negative')
        return float(v)


class CouponCode(BaseModel):
    """Coupon code model"""
    id: Optional[str] = None
    code: str = Field(..., min_length=3, max_length=20, description="Unique coupon code")
    discount_type: str = Field(..., description="percentage or fixed")
    value: float = Field(..., gt=0, description="Discount value")
    expiry_date: Optional[str] = None
    usage_limit: int = Field(0, ge=0, description="0 = unlimited")
    usage_count: int = Field(0, ge=0)
    min_purchase_amount: float = Field(0.0, ge=0)
    applicable_plans: List[str] = Field(default_factory=lambda: ["premium", "vip"])
    stripe_coupon_id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    
    @field_validator('code', mode='before')
    @classmethod
    def uppercase_code(cls, v):
        return v.upper().strip() if v else v

    @field_validator('discount_type', mode='before')
    @classmethod
    def validate_discount_type(cls, v):
        if v not in ['percentage', 'fixed']:
            raise ValueError('discount_type must be "percentage" or "fixed"')
        return v

    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v, info: ValidationInfo):
        if v <= 0:
            raise ValueError('Discount value must be positive')
        if info.data.get('discount_type') == 'percentage' and v > 100:
            raise ValueError('Percentage discount cannot exceed 100%')
        return float(v)


class CouponValidationResult(BaseModel):
    """Result of coupon validation"""
    valid: bool
    code: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[float] = None
    discount_amount: Optional[float] = None
    new_total: Optional[float] = None
    original_total: Optional[float] = None
    message: str = ""
    stripe_coupon_id: Optional[str] = None


class PricingChangeLog(BaseModel):
    """Log entry for pricing changes"""
    id: str
    plan_id: str
    field_changed: str
    old_value: Any
    new_value: Any
    changed_by: str
    changed_at: str
    reason: Optional[str] = None


# ========== DEFAULT PLANS ==========

DEFAULT_PLANS = {
    "free": {
        "plan_id": "free",
        "name": "Free",
        "price_monthly": 0.0,
        "price_yearly": 0.0,
        "original_price_monthly": 0.0,  # For promotional display
        "original_price_yearly": 0.0,
        "features": [
            "Basic marketplace access",
            "Up to 5 listings per month",
            "Standard buyer premium (5%)",
            "Standard seller commission (4%)"
        ],
        "buyer_premium_discount": 0.0,
        "seller_commission_discount": 0.0,
        "monthly_listing_limit": 5,
        "is_active": True
    },
    "premium": {
        "plan_id": "premium",
        "name": "Premium",
        "price_monthly": 29.99,
        "price_yearly": 299.99,
        "original_price_monthly": 59.99,  # For promotional display (shows as "was $59.99")
        "original_price_yearly": 599.99,
        "features": [
            "Unlimited listings",
            "Reduced buyer premium (3.5%)",
            "Reduced seller commission (2.5%)",
            "Priority customer support",
            "Advanced analytics dashboard",
            "Featured seller badge"
        ],
        "buyer_premium_discount": 30.0,  # 30% discount on 5% = 3.5%
        "seller_commission_discount": 37.5,  # 37.5% discount on 4% = 2.5%
        "monthly_listing_limit": -1,  # Unlimited
        "is_active": True
    },
    "vip": {
        "plan_id": "vip",
        "name": "VIP",
        "price_monthly": 99.99,
        "price_yearly": 999.99,
        "original_price_monthly": 199.99,  # For promotional display
        "original_price_yearly": 1999.99,
        "features": [
            "All Premium benefits",
            "Lowest buyer premium (3%)",
            "Lowest seller commission (2%)",
            "Dedicated account manager",
            "VIP badge with animation",
            "Auto-promotion on listings",
            "Early access to new features",
            "Exclusive VIP events",
            "Compare up to 6 listings"
        ],
        "buyer_premium_discount": 40.0,  # 40% discount on 5% = 3%
        "seller_commission_discount": 50.0,  # 50% discount on 4% = 2%
        "monthly_listing_limit": -1,  # Unlimited
        "is_active": True
    },
    "partner_pro": {
        "plan_id": "partner_pro",
        "name": "Partner Pro",
        "price_monthly": 0.0,
        "price_yearly": 100.00,
        "original_price_monthly": 0.0,
        "original_price_yearly": 200.00,
        "features": [
            "All Premium benefits",
            "25% buyer premium discount",
            "25% seller commission discount",
            "10 featured listings per month",
            "Branded storefront page",
            "CSV bulk listing import",
            "Early auction access (2h head start)",
            "Priority chat + email support",
            "Full analytics dashboard + export",
            "Compare up to 4 listings"
        ],
        "buyer_premium_discount": 25.0,
        "seller_commission_discount": 25.0,
        "monthly_listing_limit": -1,
        "featured_listings_per_month": 10,
        "early_access_hours": 2,
        "has_storefront": True,
        "has_bulk_import": True,
        "has_analytics_export": True,
        "support_level": "priority_chat_email",
        "is_active": True
    },
    # iter326 — Partner tier added to canonical DEFAULT_PLANS as the legacy
    # pricing_config.SUBSCRIPTION_TIERS["partner"] is now derived from here.
    # Annual-only billing — no monthly equivalent.
    "partner": {
        "plan_id": "partner",
        "name": "Partner",
        "price_monthly": 0.0,
        "price_yearly": 100.00,
        "original_price_monthly": 0.0,
        "original_price_yearly": 100.00,
        "features": [
            "Standard marketplace access",
            "Unlimited listings",
            "Standard buyer premium (5%)",
            "Standard seller commission (4%)",
            "Annual billing only"
        ],
        "buyer_premium_discount": 0.0,
        "seller_commission_discount": 0.0,
        "monthly_listing_limit": -1,
        "is_active": True
    }
}


class SubscriptionPricingService:
    """
    Service for managing subscription pricing and coupon codes.
    Syncs with Stripe for payment processing.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.plans_collection = db.subscription_plans
        self.coupons_collection = db.coupon_codes
        self.changelog_collection = db.pricing_changelog
        self._plans_cache = None      # in-memory cache
        self._plans_cache_ts = 0      # epoch when cached
        self._plans_cache_ttl = 3600  # 1 hour
        self._initialized = False
    
    # ========== PRICING MANAGEMENT ==========
    
    async def initialize_plans(self):
        """Initialize default plans if not present in database, migrate existing plans with new fields"""
        if self._initialized:
            return
        for plan_id, plan_data in DEFAULT_PLANS.items():
            existing = await self.plans_collection.find_one({"plan_id": plan_id})
            if not existing:
                plan_data["created_at"] = datetime.now(timezone.utc).isoformat()
                plan_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                await self.plans_collection.insert_one(plan_data)
                logger.info(f"Initialized plan: {plan_id}")
            else:
                # Migration: Add original_price fields if missing
                updates = {}
                if "original_price_monthly" not in existing:
                    updates["original_price_monthly"] = plan_data.get("original_price_monthly", 0.0)
                if "original_price_yearly" not in existing:
                    updates["original_price_yearly"] = plan_data.get("original_price_yearly", 0.0)
                if updates:
                    await self.plans_collection.update_one(
                        {"plan_id": plan_id},
                        {"$set": updates}
                    )
                    logger.info(f"Migrated plan {plan_id} with original price fields")
        self._initialized = True
    
    async def get_all_plans(self) -> List[Dict[str, Any]]:
        """Get all subscription plans — cached in memory for 1 hour."""
        import time as _t
        now = _t.time()
        if self._plans_cache and now < self._plans_cache_ts + self._plans_cache_ttl:
            return self._plans_cache

        await self.initialize_plans()
        plans = await self.plans_collection.find({}, {"_id": 0}).to_list(10)
        for plan in plans:
            if "original_price_monthly" not in plan:
                plan["original_price_monthly"] = 0.0
            if "original_price_yearly" not in plan:
                plan["original_price_yearly"] = 0.0
        self._plans_cache = plans
        self._plans_cache_ts = now
        return plans
    
    async def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific plan by ID"""
        plan = await self.plans_collection.find_one({"plan_id": plan_id}, {"_id": 0})
        return plan
    
    async def update_plan_pricing(
        self,
        plan_id: str,
        updates: Dict[str, Any],
        admin_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update plan pricing with validation and changelog.
        Syncs to Stripe if price changes.
        """
        # Validate plan exists
        existing = await self.plans_collection.find_one({"plan_id": plan_id})
        if not existing:
            raise ValueError(f"Plan {plan_id} not found")
        
        # Validate numeric fields
        numeric_fields = ['price_monthly', 'price_yearly', 'buyer_premium_discount', 
                         'seller_commission_discount', 'monthly_listing_limit']
        
        for field in numeric_fields:
            if field in updates:
                value = updates[field]
                if not isinstance(value, (int, float)) or value < 0:
                    raise ValueError(f"{field} must be a non-negative number")
                if 'discount' in field and value > 100:
                    raise ValueError(f"{field} cannot exceed 100%")
        
        # Log changes
        for field, new_value in updates.items():
            if field in existing and existing[field] != new_value:
                changelog = {
                    "id": f"log-{datetime.now().timestamp()}",
                    "plan_id": plan_id,
                    "field_changed": field,
                    "old_value": existing[field],
                    "new_value": new_value,
                    "changed_by": admin_id,
                    "changed_at": datetime.now(timezone.utc).isoformat(),
                    "reason": reason
                }
                await self.changelog_collection.insert_one(changelog)
        
        # Check if price changed - sync to Stripe
        price_changed = False
        if 'price_monthly' in updates and updates['price_monthly'] != existing.get('price_monthly'):
            price_changed = True
        if 'price_yearly' in updates and updates['price_yearly'] != existing.get('price_yearly'):
            price_changed = True
        
        if price_changed and stripe_api_key and plan_id != 'free':
            try:
                await self._sync_plan_to_stripe(plan_id, {**existing, **updates})
            except Exception as e:
                logger.error(f"Failed to sync plan {plan_id} to Stripe: {e}")
        
        # Update in database
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self.plans_collection.update_one(
            {"plan_id": plan_id},
            {"$set": updates}
        )
        
        return await self.get_plan(plan_id)
    
    async def get_pricing_changelog(
        self, 
        plan_id: Optional[str] = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get pricing change history"""
        query = {}
        if plan_id:
            query["plan_id"] = plan_id
        
        logs = await self.changelog_collection.find(
            query, 
            {"_id": 0}
        ).sort("changed_at", -1).limit(limit).to_list(limit)
        
        return logs
    
    async def _sync_plan_to_stripe(self, plan_id: str, plan_data: Dict[str, Any]):
        """Sync plan pricing to Stripe"""
        if not stripe_api_key:
            logger.warning("Stripe API key not configured")
            return
        
        try:
            # Get or create Stripe product
            product_id = plan_data.get('stripe_product_id')
            if not product_id:
                product = stripe.Product.create(
                    name=f"BidVex {plan_data['name']} Subscription",
                    description=f"BidVex {plan_data['name']} membership with premium benefits",
                    metadata={"bidvex_plan_id": plan_id}
                )
                product_id = product.id
                await self.plans_collection.update_one(
                    {"plan_id": plan_id},
                    {"$set": {"stripe_product_id": product_id}}
                )
            
            # Create/update monthly price
            if plan_data.get('price_monthly', 0) > 0:
                price = stripe.Price.create(
                    product=product_id,
                    unit_amount=int(plan_data['price_monthly'] * 100),  # Convert to cents
                    currency="cad",
                    recurring={"interval": "month"},
                    metadata={"bidvex_plan_id": plan_id, "billing_period": "monthly"}
                )
                await self.plans_collection.update_one(
                    {"plan_id": plan_id},
                    {"$set": {"stripe_price_id_monthly": price.id}}
                )
                logger.info(f"Created Stripe monthly price for {plan_id}: {price.id}")
            
            # Create/update yearly price
            if plan_data.get('price_yearly', 0) > 0:
                price = stripe.Price.create(
                    product=product_id,
                    unit_amount=int(plan_data['price_yearly'] * 100),  # Convert to cents
                    currency="cad",
                    recurring={"interval": "year"},
                    metadata={"bidvex_plan_id": plan_id, "billing_period": "yearly"}
                )
                await self.plans_collection.update_one(
                    {"plan_id": plan_id},
                    {"$set": {"stripe_price_id_yearly": price.id}}
                )
                logger.info(f"Created Stripe yearly price for {plan_id}: {price.id}")
                
        except stripe.StripeError as e:
            logger.error(f"Stripe error syncing plan {plan_id}: {e}")
            raise
    
    # ========== COUPON MANAGEMENT ==========
    
    async def create_coupon(
        self,
        coupon_data: CouponCode,
        admin_id: str
    ) -> Dict[str, Any]:
        """Create a new coupon code"""
        # Check for duplicate code
        existing = await self.coupons_collection.find_one({"code": coupon_data.code})
        if existing:
            raise ValueError(f"Coupon code {coupon_data.code} already exists")
        
        # Generate ID
        coupon_dict = coupon_data.model_dump()
        coupon_dict["id"] = f"coupon-{datetime.now().timestamp()}"
        coupon_dict["created_at"] = datetime.now(timezone.utc).isoformat()
        coupon_dict["created_by"] = admin_id
        coupon_dict["usage_count"] = 0
        
        # Create in Stripe
        if stripe_api_key:
            try:
                stripe_coupon = await self._create_stripe_coupon(coupon_data)
                coupon_dict["stripe_coupon_id"] = stripe_coupon.id
            except Exception as e:
                logger.error(f"Failed to create Stripe coupon: {e}")
        
        await self.coupons_collection.insert_one(coupon_dict)
        
        # Remove MongoDB _id before returning
        coupon_dict.pop("_id", None)
        return coupon_dict
    
    async def get_all_coupons(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all coupon codes"""
        query = {} if include_inactive else {"is_active": True}
        coupons = await self.coupons_collection.find(query, {"_id": 0}).to_list(100)
        return coupons
    
    async def get_coupon(self, coupon_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific coupon by ID"""
        coupon = await self.coupons_collection.find_one({"id": coupon_id}, {"_id": 0})
        return coupon
    
    async def update_coupon(
        self,
        coupon_id: str,
        updates: Dict[str, Any],
        admin_id: str
    ) -> Dict[str, Any]:
        """Update a coupon code"""
        existing = await self.coupons_collection.find_one({"id": coupon_id})
        if not existing:
            raise ValueError(f"Coupon {coupon_id} not found")
        
        # Validate updates
        if 'discount_type' in updates:
            if updates['discount_type'] not in ['percentage', 'fixed']:
                raise ValueError('discount_type must be "percentage" or "fixed"')
        
        if 'value' in updates:
            if updates['value'] <= 0:
                raise ValueError('Discount value must be positive')
            if updates.get('discount_type', existing.get('discount_type')) == 'percentage':
                if updates['value'] > 100:
                    raise ValueError('Percentage discount cannot exceed 100%')
        
        if 'code' in updates:
            updates['code'] = updates['code'].upper().strip()
            # Check for duplicate
            dup = await self.coupons_collection.find_one({
                "code": updates['code'], 
                "id": {"$ne": coupon_id}
            })
            if dup:
                raise ValueError(f"Coupon code {updates['code']} already exists")
        
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["updated_by"] = admin_id
        
        await self.coupons_collection.update_one(
            {"id": coupon_id},
            {"$set": updates}
        )
        
        return await self.get_coupon(coupon_id)
    
    async def delete_coupon(self, coupon_id: str) -> bool:
        """Soft delete a coupon (set inactive)"""
        result = await self.coupons_collection.update_one(
            {"id": coupon_id},
            {"$set": {"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat()}}
        )
        return result.modified_count > 0
    
    async def validate_coupon(
        self,
        code: str,
        plan_id: str,
        billing_period: str = "yearly"  # monthly or yearly
    ) -> CouponValidationResult:
        """
        Validate a coupon code and calculate discount.
        Returns validation result with discount details.
        """
        code = code.upper().strip()
        
        # Find coupon
        coupon = await self.coupons_collection.find_one({"code": code, "is_active": True})
        
        if not coupon:
            return CouponValidationResult(
                valid=False,
                message="Invalid coupon code"
            )
        
        # Check expiry
        if coupon.get("expiry_date"):
            try:
                expiry = datetime.fromisoformat(coupon["expiry_date"].replace("Z", "+00:00"))
                if expiry < datetime.now(timezone.utc):
                    return CouponValidationResult(
                        valid=False,
                        code=code,
                        message="This coupon has expired"
                    )
            except Exception:
                pass
        
        # Check usage limit
        if coupon.get("usage_limit", 0) > 0:
            if coupon.get("usage_count", 0) >= coupon["usage_limit"]:
                return CouponValidationResult(
                    valid=False,
                    code=code,
                    message="This coupon has reached its usage limit"
                )
        
        # Check applicable plans
        applicable_plans = coupon.get("applicable_plans", ["premium", "vip"])
        if plan_id not in applicable_plans:
            return CouponValidationResult(
                valid=False,
                code=code,
                message=f"This coupon is not valid for the {plan_id} plan"
            )
        
        # Get plan pricing
        plan = await self.get_plan(plan_id)
        if not plan:
            return CouponValidationResult(
                valid=False,
                message="Invalid plan selected"
            )
        
        # Calculate original total
        if billing_period == "monthly":
            original_total = plan.get("price_monthly", 0)
        else:
            original_total = plan.get("price_yearly", 0)
        
        # Check minimum purchase
        min_amount = coupon.get("min_purchase_amount", 0)
        if original_total < min_amount:
            return CouponValidationResult(
                valid=False,
                code=code,
                message=f"Minimum purchase amount of ${min_amount:.2f} required"
            )
        
        # Calculate discount
        discount_type = coupon.get("discount_type", "percentage")
        value = coupon.get("value", 0)
        
        if discount_type == "percentage":
            discount_amount = original_total * (value / 100)
        else:  # fixed
            discount_amount = min(value, original_total)  # Can't exceed total
        
        new_total = max(0, original_total - discount_amount)
        
        return CouponValidationResult(
            valid=True,
            code=code,
            discount_type=discount_type,
            discount_value=value,
            discount_amount=round(discount_amount, 2),
            new_total=round(new_total, 2),
            original_total=round(original_total, 2),
            message=f"Coupon applied! You save ${discount_amount:.2f}",
            stripe_coupon_id=coupon.get("stripe_coupon_id")
        )
    
    async def increment_coupon_usage(self, code: str) -> bool:
        """Increment usage count when coupon is successfully used"""
        code = code.upper().strip()
        result = await self.coupons_collection.update_one(
            {"code": code},
            {"$inc": {"usage_count": 1}}
        )
        return result.modified_count > 0
    
    async def _create_stripe_coupon(self, coupon_data: CouponCode) -> stripe.Coupon:
        """Create coupon in Stripe"""
        params = {
            "id": coupon_data.code.lower().replace(" ", "-"),
            "name": coupon_data.code,
            "metadata": {"bidvex_code": coupon_data.code}
        }
        
        if coupon_data.discount_type == "percentage":
            params["percent_off"] = coupon_data.value
        else:
            params["amount_off"] = int(coupon_data.value * 100)  # Convert to cents
            params["currency"] = "cad"
        
        if coupon_data.usage_limit and coupon_data.usage_limit > 0:
            params["max_redemptions"] = coupon_data.usage_limit
        
        if coupon_data.expiry_date:
            try:
                expiry = datetime.fromisoformat(coupon_data.expiry_date.replace("Z", "+00:00"))
                params["redeem_by"] = int(expiry.timestamp())
            except Exception:
                pass
        
        return stripe.Coupon.create(**params)


# Singleton instance
_pricing_service = None

def get_pricing_service(db: AsyncIOMotorDatabase) -> SubscriptionPricingService:
    """Get or create the pricing service instance"""
    global _pricing_service
    if _pricing_service is None:
        _pricing_service = SubscriptionPricingService(db)
    return _pricing_service
