"""
BidVex Payments — Promotions & Email Credits Sub-Router
Extracted from payments.py for modularity.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging
import uuid
import stripe

from routes.payments_shared import get_db, get_current_user_wrapper, security

logger = logging.getLogger(__name__)

promotions_sub_router = APIRouter()


def _get_current_user():
    return get_current_user_wrapper()


# ========== PROMOTIONS ==========

# Feature packs per tier per listing_type (used by UI + confirmation emails)
PROMOTION_FEATURES = {
    "marketplace": {
        "basic":    ["Homepage highlight", "Search priority"],
        "standard": ["Homepage highlight", "Search priority", "Category banner"],
        "premium":  ["Homepage highlight", "Search priority", "Category banner", "Email blast", "Social share"],
    },
    "lots": {
        "basic":    ["Search priority", "Homepage placement"],
        "standard": ["Search priority", "Homepage placement", "Category banner", "Featured badge"],
        "premium":  ["Search priority", "Homepage placement", "Category banner", "Featured badge",
                     "Email blast", "Social share", "Featured Partner badge"],
    },
    "storage": {
        "basic":    ["Homepage highlight", "Search priority"],
        "standard": ["Homepage highlight", "Search priority", "Category banner on Storage page"],
        "premium":  ["Homepage highlight", "Search priority", "Category banner on Storage page",
                     "Email blast to storage waitlist", "Social share"],
    },
    "partner": {
        "basic":    ["Search priority", "Homepage placement"],
        "standard": ["Search priority", "Homepage placement", "Category banner", "Featured badge"],
        "premium":  ["Search priority", "Homepage placement", "Category banner", "Featured badge",
                     "Email blast", "Social share", "Featured Partner badge"],
    },
    "vehicle": {
        "basic":    ["Vehicle search priority", "Homepage placement"],
        "standard": ["Vehicle search priority", "Homepage placement", "Vehicle category banner", "Featured badge"],
        "premium":  ["Vehicle search priority", "Homepage placement", "Vehicle category banner", "Featured badge",
                     "Email blast to vehicle waitlist", "Social share"],
    },
}


def _listing_collection(db, listing_type: str):
    """Map listing_type → the right MongoDB collection (iter189: all 4 types)."""
    lt = (listing_type or "marketplace").lower()
    if lt == "storage":
        return db.storage_auctions, "storage"
    if lt == "vehicle":
        return db.vehicle_listings, "vehicle"
    if lt in ("lots", "multi_item", "partner"):
        return db.multi_item_listings, lt
    # marketplace default
    return db.listings, lt


@promotions_sub_router.post("/promote-listing")
async def promote_listing(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Purchase a promotion/boost for a listing (marketplace / lots / storage / partner).

    Uses the shared gross-up Stripe fee formula so the buyer pays the exact
    Stripe cost and BidVex receives the full subtotal.

    Request body:
        {
          "listing_id":    str,
          "boost_tier":    "basic" | "standard" | "premium",
          "listing_type":  "marketplace" | "lots" | "storage" | "partner",
          "return_url":    str (optional, defaults to bidvex.com)
        }
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    listing_id = data.get("listing_id")
    # Accept either `boost_tier` (new canonical) or legacy `tier`
    tier = (data.get("boost_tier") or data.get("tier") or "basic").lower()
    listing_type = (data.get("listing_type") or "marketplace").lower()
    return_url = data.get("return_url") or data.get("origin_url") or "https://bidvex.com"

    if tier not in ("basic", "standard", "premium"):
        raise HTTPException(status_code=400, detail="Invalid boost_tier")
    if listing_type not in ("marketplace", "lots", "storage", "partner", "vehicle", "multi_item"):
        raise HTTPException(status_code=400, detail="Invalid listing_type")

    # Lookup listing in the correct collection
    coll, _lt_norm = _listing_collection(db, listing_type)
    listing = await coll.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Authorisation — seller/facility_owner only
    _owner_id = listing.get("seller_id") or listing.get("facility_owner_id") or listing.get("owner_id")
    if _owner_id != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized to promote this listing")

    from services.pricing_config import PROMOTION_TIERS
    promo_config = PROMOTION_TIERS[tier]
    base_price_cad = round(promo_config["price_cents"] / 100, 2)   # e.g. $9.99
    boost_days = promo_config["duration_days"]

    # Full Canadian fee stack — GST + QST on base, then Stripe gross-up
    from decimal import Decimal as _D
    from services.pricing_manager import gross_up_stripe_fee
    base = _D(str(base_price_cad))
    gst = (base * _D("0.05")).quantize(_D("0.01"))
    qst = (base * _D("0.09975")).quantize(_D("0.01"))
    subtotal = (base + gst + qst).quantize(_D("0.01"))
    stripe_fee = gross_up_stripe_fee(subtotal, card_type="domestic")
    grand_total = (subtotal + stripe_fee).quantize(_D("0.01"))
    grand_total_cents = int(grand_total * 100)

    # Get/create Stripe customer
    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id") if user else None
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email, metadata={"user_id": current_user.id})
        customer_id = customer.id
        await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})

    # Create Stripe Checkout Session (non-Connect — promotion revenue goes to BidVex)
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "product_data": {
                        "name": f"BidVex {tier.title()} Boost ({boost_days} days)",
                        "description": f"Promotion for listing: {listing.get('title','Listing')[:80]}",
                    },
                    "unit_amount": grand_total_cents,
                },
                "quantity": 1,
            }],
            success_url=f"{return_url}?promo_success=1&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=return_url,
            metadata={
                "transaction_type": "listing_promotion",
                "type": "listing_promotion",
                "seller_id": current_user.id,
                "listing_id": listing_id,
                "listing_type": listing_type,
                "boost_tier": tier,
                "boost_days": str(boost_days),
                "base_price": f"{base_price_cad:.2f}",
                "gst":        f"{float(gst):.2f}",
                "qst":        f"{float(qst):.2f}",
                "subtotal":   f"{float(subtotal):.2f}",
                "stripe_fee_estimate": f"{float(stripe_fee):.2f}",
                "stripe_fee": f"{float(stripe_fee):.2f}",
                "grand_total": f"{float(grand_total):.2f}",
            },
        )
    except Exception as e:
        logger.error(f"[promote-listing] Stripe session create failed: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe checkout init failed: {e}")

    now = datetime.now(timezone.utc)
    promotion = {
        "id": str(uuid.uuid4()),
        "session_id": session.id,
        "listing_id": listing_id,
        "listing_type": listing_type,
        "seller_id": current_user.id,
        "user_id": current_user.id,
        "tier": tier,
        "boost_tier": tier,
        "duration_days": boost_days,
        "features": PROMOTION_FEATURES.get(listing_type, PROMOTION_FEATURES["marketplace"]).get(tier, []),
        "base_price": base_price_cad,
        "gst": float(gst),
        "qst": float(qst),
        "stripe_fee": float(stripe_fee),
        "grand_total": float(grand_total),
        "price_cents": grand_total_cents,
        "start_date": None,
        "end_date": None,
        "status": "pending_payment",
        "created_at": now.isoformat(),
    }
    await db.promotions.insert_one(promotion)

    return {
        "promotion_id": promotion["id"],
        "checkout_url": session.url,
        "session_id":   session.id,
        "tier":         tier,
        "listing_type": listing_type,
        "base_price":   base_price_cad,
        "gst":          float(gst),
        "qst":          float(qst),
        "subtotal":     float(subtotal),
        "stripe_fee":   float(stripe_fee),
        "grand_total":  float(grand_total),
    }


@promotions_sub_router.post("/promote")
async def create_promotion(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Create a listing promotion with Stripe Checkout."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    listing_id = data.get("listing_id")
    tier = data.get("tier", "basic")
    origin_url = data.get("origin_url", "https://bidvex.com")

    listing = await db.listings.find_one({"id": listing_id, "seller_id": current_user.id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or not owned by you")

    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id") if user else None
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email, metadata={"user_id": current_user.id})
        customer_id = customer.id
        await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})

    from services.connect_payment_engine import create_promotion_checkout

    # Get buyer's province for jurisdiction-aware tax
    buyer_province = user.get("province", "QC") if user else "QC"

    result = create_promotion_checkout(
        customer_id=customer_id,
        listing_id=listing_id,
        user_id=current_user.id,
        tier=tier,
        success_url=f"{origin_url}/payment/success?type=promotion&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin_url}/listing/{listing_id}",
        buyer_province=buyer_province,
    )

    from services.pricing_config import PROMOTION_TIERS

    promo_config = PROMOTION_TIERS.get(tier, PROMOTION_TIERS["basic"])
    now = datetime.now(timezone.utc)

    promotion = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "user_id": current_user.id,
        "tier": tier,
        "session_id": result["session_id"],
        "duration_days": promo_config["duration_days"],
        "features": promo_config["features"],
        "price_cents": promo_config["price_cents"],
        "start_date": None,
        "end_date": None,
        "status": "pending_payment",
        "created_at": now.isoformat(),
    }
    await db.promotions.insert_one(promotion)

    return {
        "promotion_id": promotion["id"],
        "checkout_url": result["checkout_url"],
        "session_id": result["session_id"],
        "tier": tier,
        "price": result["price"],
    }


@promotions_sub_router.get("/promotions/my")
async def get_my_promotions(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get user's active promotions."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    promotions = await db.promotions.find({"user_id": current_user.id}, {"_id": 0}).to_list(100)
    return {"promotions": promotions}


# ========== EMAIL MARKETING CREDITS ==========

class EmailCreditsRequest(BaseModel):
    quantity: int = Field(..., ge=100, le=100000, description="Number of email credits to purchase")
    origin_url: Optional[str] = "https://bidvex.com"


@promotions_sub_router.post("/email-credits/purchase")
async def purchase_email_credits(
    data: EmailCreditsRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Purchase email marketing credits (pay-as-you-go)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id") if user else None
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email, metadata={"user_id": current_user.id})
        customer_id = customer.id
        await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})

    from services.connect_payment_engine import create_email_credits_checkout

    # Get buyer's province for jurisdiction-aware tax
    buyer_province = user.get("province", "QC") if user else "QC"

    result = create_email_credits_checkout(
        customer_id=customer_id,
        user_id=current_user.id,
        quantity=data.quantity,
        success_url=f"{data.origin_url}/payment/success?type=email_credits&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{data.origin_url}/email-marketing",
        buyer_province=buyer_province,
    )

    return {
        "checkout_url": result["checkout_url"],
        "session_id": result["session_id"],
        "quantity": result["quantity"],
        "total_amount": result["total_cents"] / 100,
        "per_email": round(result["total_cents"] / result["quantity"] / 100, 4),
    }


@promotions_sub_router.get("/email-credits/balance")
async def get_email_credit_balance(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get the current user's email credit balance."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    user = await db.users.find_one({"id": current_user.id}, {"_id": 0, "email_credits": 1})
    return {"credits": user.get("email_credits", 0) if user else 0}


@promotions_sub_router.get("/pricing-config")
async def get_pricing_config():
    """Public endpoint returning current platform pricing for UI display."""
    from services.pricing_config import (
        BUYER_PREMIUM_RATES,
        SELLER_COMMISSION_RATES,
        SUBSCRIPTION_TIERS,
        PROMOTION_TIERS,
        EMAIL_CREDIT_TIERS,
        DEPOSIT_THRESHOLD_CAD,
        DEPOSIT_AMOUNT_DOLLARS,
        PLATFORM_FEE_GENERAL,
        PLATFORM_FEE_VEHICLE,
    )

    return {
        "commissions": {"general": float(PLATFORM_FEE_GENERAL), "vehicle": float(PLATFORM_FEE_VEHICLE)},
        "buyer_premiums": {k: float(v) for k, v in BUYER_PREMIUM_RATES.items()},
        "seller_commissions": {k: float(v) for k, v in SELLER_COMMISSION_RATES.items()},
        "subscriptions": SUBSCRIPTION_TIERS,
        "promotions": PROMOTION_TIERS,
        "email_credits": EMAIL_CREDIT_TIERS,
        "deposit": {"threshold_cad": DEPOSIT_THRESHOLD_CAD, "amount_dollars": DEPOSIT_AMOUNT_DOLLARS},
    }
