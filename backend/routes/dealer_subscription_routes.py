"""
iter209 Step 6 — Vehicle Dealer Annual Subscription HTTP endpoints.

Mounted under `partners_router` style — no /api prefix here, the router will be
mounted under api_router which provides the /api prefix.
"""
from fastapi import APIRouter, Depends, HTTPException, Body

from deps import get_current_user, get_db, User

dealer_subscription_router = APIRouter(tags=["Dealer Subscription"])


@dealer_subscription_router.post("/admin/dealer-subscription/bootstrap")
async def admin_bootstrap_dealer_subscription(current_user: User = Depends(get_current_user)):
    """Admin-only: ensure Stripe Product/Price/Coupon exist. Idempotent."""
    db = get_db()
    admin = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1})
    if not admin or admin.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")
    from services.dealer_subscription_service import bootstrap_dealer_subscription_objects
    return await bootstrap_dealer_subscription_objects(db)


@dealer_subscription_router.post("/dealer-subscription/start")
async def start_dealer_subscription(
    payment_method_id: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
):
    """Called by the dealer's frontend AFTER they've collected a card via SetupIntent.

    Body: { "payment_method_id": "pm_xxx" }

    Charges $100/year (50% LAUNCH discount applied automatically) and persists
    the subscription on the user record.
    """
    db = get_db()
    from services.dealer_subscription_service import create_dealer_subscription
    result = await create_dealer_subscription(
        db,
        user_id=current_user.id,
        user_email=current_user.email,
        payment_method_id=payment_method_id,
    )
    return result


@dealer_subscription_router.get("/dealer-subscription/status")
async def my_dealer_subscription_status(current_user: User = Depends(get_current_user)):
    db = get_db()
    from services.dealer_subscription_service import get_dealer_subscription_status
    return await get_dealer_subscription_status(db, current_user.id)


@dealer_subscription_router.get("/admin/dealer-subscription/{user_id}/status")
async def admin_view_dealer_subscription(user_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    admin = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1})
    if not admin or admin.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")
    from services.dealer_subscription_service import get_dealer_subscription_status
    return await get_dealer_subscription_status(db, user_id)


# ── iter211 P3: hosted Stripe Checkout for dealer annual fee ─────────────
@dealer_subscription_router.post("/dealer-subscription/create-checkout-session")
async def create_dealer_checkout_session(current_user: User = Depends(get_current_user)):
    """Generate a hosted Stripe Checkout Session for the dealer's $100/yr
    subscription (uses the LAUNCH50 coupon → effective $100). Returns
    `{checkout_url}` for the frontend to redirect to. Idempotent: if the
    dealer already has an active subscription, returns `{already_active: true}`.
    Demo accounts are blocked (iter211 P4 isolation rule)."""
    import os
    import stripe
    from fastapi import HTTPException

    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0}) or {}

    # iter211 P4 — Demo accounts cannot trigger any real Stripe flow
    if user_doc.get("is_demo_account") is True:
        raise HTTPException(status_code=403, detail="demo_mode_payments_disabled")

    # Must be an approved vehicle dealer
    if not user_doc.get("is_vehicle_dealer"):
        raise HTTPException(status_code=403, detail="not_a_vehicle_dealer")

    # Idempotency: if already active, surface that
    if user_doc.get("dealer_subscription_active") is True:
        return {"already_active": True, "renewal_date": user_doc.get("dealer_subscription_renewal")}

    from services.dealer_subscription_service import _get_or_create_settings, COUPON_ID
    settings = await _get_or_create_settings(db)

    stripe.api_key = os.environ.get("STRIPE_API_KEY")
    frontend_url = os.environ.get("FRONTEND_URL", "https://bidvex.com")

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=current_user.email,
        line_items=[{"price": settings["price_id"], "quantity": 1}],
        discounts=[{"coupon": COUPON_ID}],
        success_url=f"{frontend_url}/seller-dashboard?dealer_fee=success",
        cancel_url=f"{frontend_url}/seller-dashboard?dealer_fee=cancelled",
        metadata={
            "user_id": current_user.id,
            "type": "vehicle_dealer_annual_fee",
        },
        subscription_data={
            "metadata": {
                "user_id": current_user.id,
                "type": "vehicle_dealer_annual_fee",
            }
        },
        allow_promotion_codes=False,
    )
    return {"checkout_url": session.url, "session_id": session.id}

