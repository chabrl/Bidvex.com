"""
BidVex Subscription Service
Handles subscription tier management, Stripe price mappings, and tier-based fee calculations

Stripe Price IDs:
- Free: price_1T5V79Bd6Wtvh7hsnp69zu1F
- Premium ($180.00 CAD/year): price_1T5V5xBd6Wtvh7hscWcNnk34
- VIP ($300.00 CAD/year): price_1T5V2bBd6Wtvh7hsqLLmAZSH
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

# ============= STRIPE PRICE ID MAPPINGS =============

class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"  # Alias for free
    PREMIUM = "premium"
    VIP = "vip"


# Stripe Price IDs (Production)
STRIPE_PRICE_IDS = {
    "free": "price_1T5V79Bd6Wtvh7hsnp69zu1F",
    "basic": "price_1T5V79Bd6Wtvh7hsnp69zu1F",  # Same as free
    "premium": "price_1T5V5xBd6Wtvh7hscWcNnk34",
    "vip": "price_1T5V2bBd6Wtvh7hsqLLmAZSH",
}

# Reverse mapping: Price ID -> Tier
PRICE_ID_TO_TIER = {
    "price_1T5V79Bd6Wtvh7hsnp69zu1F": "free",
    "price_1T5V5xBd6Wtvh7hscWcNnk34": "premium",
    "price_1T5V2bBd6Wtvh7hsqLLmAZSH": "vip",
}

# Subscription prices (for display)
SUBSCRIPTION_PRICES = {
    "free": {"amount": 0, "currency": "CAD", "interval": "year", "display": "Free"},
    "basic": {"amount": 0, "currency": "CAD", "interval": "year", "display": "Free"},
    "premium": {"amount": 18000, "currency": "CAD", "interval": "year", "display": "$180.00 CAD/year + taxes"},
    "vip": {"amount": 30000, "currency": "CAD", "interval": "year", "display": "$300.00 CAD/year + taxes"},
}

# Fee rates by tier (synchronized with tax_engine.py)
BUYER_PREMIUM_RATES = {
    "free": 0.05,      # 5.0%
    "basic": 0.05,     # 5.0%
    "premium": 0.035,  # 3.5%
    "vip": 0.03,       # 3.0%
}

SELLER_COMMISSION_RATES = {
    "free": 0.04,      # 4.0%
    "basic": 0.04,     # 4.0%
    "premium": 0.025,  # 2.5%
    "vip": 0.02,       # 2.0%
}

# Tier benefits
TIER_BENEFITS = {
    "free": {
        "name": "Free",
        "buyer_premium": "5.0%",
        "seller_commission": "4.0%",
        "features": [
            "Access to all auctions",
            "Basic bidding features",
            "Email notifications"
        ]
    },
    "basic": {
        "name": "Basic",
        "buyer_premium": "5.0%",
        "seller_commission": "4.0%",
        "features": [
            "Access to all auctions",
            "Basic bidding features",
            "Email notifications"
        ]
    },
    "premium": {
        "name": "Premium",
        "buyer_premium": "3.5%",
        "seller_commission": "2.5%",
        "price": "$180 CAD/year + taxes",
        "features": [
            "Reduced buyer premium (3.5%)",
            "Reduced seller commission (2.5%)",
            "Priority customer support",
            "Early access to new features",
            "Advanced analytics dashboard"
        ],
        "savings_example": "Save $15 per $1,000 vs Basic"
    },
    "vip": {
        "name": "VIP Elite",
        "buyer_premium": "3.0%",
        "seller_commission": "2.0%",
        "price": "$300 CAD/year + taxes",
        "features": [
            "Lowest buyer premium (3.0%)",
            "Lowest seller commission (2.0%)",
            "Dedicated account manager",
            "VIP-only auctions access",
            "Free shipping on select items",
            "Extended payment terms",
            "Premium analytics & reports"
        ],
        "savings_example": "Save $20 per $1,000 vs Basic"
    }
}


def get_tier_from_price_id(price_id: str) -> str:
    """Get subscription tier from Stripe price ID"""
    return PRICE_ID_TO_TIER.get(price_id, "free")


def get_price_id_for_tier(tier: str) -> str:
    """Get Stripe price ID for a subscription tier"""
    normalized = tier.lower().strip()
    return STRIPE_PRICE_IDS.get(normalized, STRIPE_PRICE_IDS["free"])


def get_buyer_premium_rate(tier: str) -> float:
    """Get buyer premium rate for a tier"""
    normalized = tier.lower().strip()
    return BUYER_PREMIUM_RATES.get(normalized, 0.05)


def get_seller_commission_rate(tier: str) -> float:
    """Get seller commission rate for a tier"""
    normalized = tier.lower().strip()
    return SELLER_COMMISSION_RATES.get(normalized, 0.04)


def get_tier_benefits(tier: str) -> Dict[str, Any]:
    """Get benefits information for a tier"""
    normalized = tier.lower().strip()
    return TIER_BENEFITS.get(normalized, TIER_BENEFITS["free"])


def get_all_tiers() -> Dict[str, Any]:
    """Get all subscription tiers with their details"""
    return {
        "tiers": [
            {
                "id": "free",
                "name": "Free",
                "price": 0,
                "price_display": "Free",
                "stripe_price_id": STRIPE_PRICE_IDS["free"],
                **TIER_BENEFITS["free"]
            },
            {
                "id": "premium",
                "name": "Premium",
                "price": 18000,
                "price_display": "$180 CAD/year + taxes",
                "stripe_price_id": STRIPE_PRICE_IDS["premium"],
                **TIER_BENEFITS["premium"]
            },
            {
                "id": "vip",
                "name": "VIP Elite",
                "price": 30000,
                "price_display": "$300 CAD/year + taxes",
                "stripe_price_id": STRIPE_PRICE_IDS["vip"],
                **TIER_BENEFITS["vip"]
            }
        ],
        "fee_comparison": {
            "columns": ["Tier", "Buyer Premium", "Seller Commission", "Savings per $1,000"],
            "rows": [
                ["Free/Basic", "5.0%", "4.0%", "-"],
                ["Premium", "3.5%", "2.5%", "$15"],
                ["VIP Elite", "3.0%", "2.0%", "$20"]
            ]
        }
    }


async def create_subscription_checkout(
    db,
    user_id: str,
    tier: str,
    return_url: str
) -> Dict[str, Any]:
    """
    Create Stripe Checkout session for subscription upgrade
    
    Args:
        db: Database connection
        user_id: User's ID
        tier: Target subscription tier
        return_url: URL to redirect after checkout
    
    Returns:
        Checkout session details
    """
    import stripe
    
    # Get user
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise ValueError("User not found")
    
    price_id = get_price_id_for_tier(tier)
    
    # Get or create Stripe customer
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.get("email"),
            name=user.get("name"),
            metadata={"user_id": user_id, "platform": "bidvex"}
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"stripe_customer_id": customer_id}}
        )
    
    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price": price_id,
            "quantity": 1
        }],
        success_url=f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
        cancel_url=f"{return_url}?status=cancelled",
        metadata={
            "user_id": user_id,
            "tier": tier,
            "type": "subscription_upgrade"
        },
        subscription_data={
            "metadata": {
                "user_id": user_id,
                "tier": tier
            }
        }
    )
    
    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "tier": tier,
        "price_display": SUBSCRIPTION_PRICES[tier]["display"]
    }


async def handle_subscription_event(
    db,
    event_type: str,
    subscription_data: Dict[str, Any]
) -> bool:
    """
    Handle Stripe subscription webhook events
    
    Events handled:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.paid
    
    Returns:
        True if handled successfully
    """
    subscription_id = subscription_data.get("id")
    customer_id = subscription_data.get("customer")
    
    # Get user by Stripe customer ID
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        logger.warning(f"No user found for Stripe customer {customer_id}")
        return False
    
    user_id = user.get("id")
    
    if event_type in ["customer.subscription.created", "customer.subscription.updated"]:
        # Get tier from price ID
        items = subscription_data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            tier = get_tier_from_price_id(price_id)
        else:
            tier = subscription_data.get("metadata", {}).get("tier", "free")
        
        status = subscription_data.get("status")
        
        # Update user subscription
        update_data = {
            "subscription_tier": tier,
            "stripe_subscription_id": subscription_id,
            "subscription_status": status,
            "subscription_updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if status == "active":
            update_data["subscription_active"] = True
            update_data["subscription_period_end"] = datetime.fromtimestamp(
                subscription_data.get("current_period_end", 0),
                tz=timezone.utc
            ).isoformat()
        
        await db.users.update_one(
            {"id": user_id},
            {"$set": update_data}
        )
        
        logger.info(f"Updated subscription for user {user_id}: tier={tier}, status={status}")
        return True
    
    elif event_type == "customer.subscription.deleted":
        # Downgrade to free tier
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "subscription_tier": "free",
                "subscription_status": "cancelled",
                "subscription_active": False,
                "subscription_updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        logger.info(f"Subscription cancelled for user {user_id}, downgraded to free")
        return True
    
    elif event_type == "invoice.paid":
        # Subscription payment successful
        subscription_id = subscription_data.get("subscription")
        
        if subscription_id:
            # Update last payment date
            await db.users.update_one(
                {"stripe_subscription_id": subscription_id},
                {"$set": {
                    "subscription_last_payment": datetime.now(timezone.utc).isoformat(),
                    "subscription_status": "active",
                    "subscription_active": True
                }}
            )
        
        return True
    
    return False


async def get_user_subscription_status(db, user_id: str) -> Dict[str, Any]:
    """Get user's current subscription status and benefits"""
    user = await db.users.find_one({"id": user_id})
    
    if not user:
        return {"error": "User not found"}
    
    tier = user.get("subscription_tier", "free")
    
    return {
        "user_id": user_id,
        "tier": tier,
        "tier_name": TIER_BENEFITS.get(tier, TIER_BENEFITS["free"])["name"],
        "status": user.get("subscription_status", "active" if tier == "free" else "none"),
        "is_active": user.get("subscription_active", tier == "free"),
        "stripe_subscription_id": user.get("stripe_subscription_id"),
        "period_end": user.get("subscription_period_end"),
        "benefits": get_tier_benefits(tier),
        "fee_rates": {
            "buyer_premium": get_buyer_premium_rate(tier),
            "seller_commission": get_seller_commission_rate(tier)
        },
        "can_upgrade": tier != "vip",
        "upgrade_options": [
            t for t in ["premium", "vip"] 
            if t != tier and (tier == "free" or tier == "basic" or (tier == "premium" and t == "vip"))
        ]
    }


# Exports
__all__ = [
    "SubscriptionTier",
    "STRIPE_PRICE_IDS",
    "PRICE_ID_TO_TIER",
    "SUBSCRIPTION_PRICES",
    "BUYER_PREMIUM_RATES",
    "SELLER_COMMISSION_RATES",
    "TIER_BENEFITS",
    "get_tier_from_price_id",
    "get_price_id_for_tier",
    "get_buyer_premium_rate",
    "get_seller_commission_rate",
    "get_tier_benefits",
    "get_all_tiers",
    "create_subscription_checkout",
    "handle_subscription_event",
    "get_user_subscription_status",
]
