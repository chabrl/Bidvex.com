"""
iter194 — Vehicle Dealer License Verification + Unlock Fee Flow

Two related route groups:
1. Dealer License Verification — buyers prove they are licensed dealers to bid on
   `auction_access=licensed_only` listings
2. Unlock Fee — winners pay a 2.5% net platform fee (Stripe processing on top) to
   unlock dealer contact details for off-platform settlement.
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
import os
import uuid

from models.vehicle_models import (
    VehicleListingStatus,
    DealerLicenseSubmit, DealerLicense, DealerLicenseAdminAction,
    DealerLicenseVerificationStatus,
    UnlockFeeQuote, UnlockFeeIntent, DealerContactReveal,
)

router = APIRouter()

# Lazy stripe + db imports (matches existing convention in this codebase)
def _get_db():
    from server import db
    return db


def _get_stripe():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    return stripe


# Reuse get_current_user from vehicles routes
from routes.vehicles import get_current_user


# =============================================================================
#  DEALER LICENSE VERIFICATION
# =============================================================================

@router.get("/dealer-licenses/me")
async def get_my_dealer_license(user: dict = Depends(get_current_user)):
    """Buyer fetches their current verification record (or none)."""
    db = _get_db()
    doc = await db.dealer_licenses.find_one({"user_id": user["id"]}, {"_id": 0})
    if not doc:
        return {"status": DealerLicenseVerificationStatus.NONE.value, "license": None}
    return {"status": doc.get("status"), "license": doc}


@router.post("/dealer-licenses")
async def submit_dealer_license(
    payload: DealerLicenseSubmit,
    user: dict = Depends(get_current_user),
):
    """Buyer submits dealer-license proof for admin review."""
    db = _get_db()

    if payload.expiry_date <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "license_already_expired",
                "message_en": "License is already expired. Please submit an active license.",
                "message_fr": "Le permis est déjà expiré. Veuillez soumettre un permis valide.",
            },
        )

    existing = await db.dealer_licenses.find_one({"user_id": user["id"]}, {"_id": 0})
    record = {
        "id": existing["id"] if existing else str(uuid.uuid4()),
        "user_id": user["id"],
        "license_number": payload.license_number,
        "jurisdiction": payload.jurisdiction.upper(),
        "expiry_date": payload.expiry_date,
        "document_url": payload.document_url,
        "status": DealerLicenseVerificationStatus.PENDING.value,
        "rejection_reason": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "submitted_at": datetime.now(timezone.utc),
    }
    if existing:
        await db.dealer_licenses.update_one({"id": existing["id"]}, {"$set": record})
    else:
        await db.dealer_licenses.insert_one(record)

    record.pop("_id", None)
    return {"success": True, "license": record}


@router.get("/admin/dealer-licenses")
async def admin_list_dealer_licenses(
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Admin: list all license submissions (optionally filtered by status)."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = _get_db()
    query = {}
    if status:
        query["status"] = status
    items = await db.dealer_licenses.find(query, {"_id": 0}).sort("submitted_at", -1).to_list(length=500)
    return {"items": items, "total": len(items)}


# iter198 — Pilot conversion attribution counter
@router.get("/admin/pilot-conversions")
async def admin_pilot_conversions(
    utm_source: str = "pilot-welcome-banner",
    user: dict = Depends(get_current_user),
):
    """
    Admin: count vehicle listings sourced from a specific utm_source (default = pilot welcome banner).
    Returns total and a sample of the most recent 25 listings (id, title, seller_id, created_at).
    """
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = _get_db()
    query = {"utm_source": utm_source}
    total = await db.vehicle_listings.count_documents(query)
    sample = await db.vehicle_listings.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "seller_id": 1, "seller_user_id": 1, "created_at": 1, "status": 1},
    ).sort("created_at", -1).limit(25).to_list(25)
    return {"utm_source": utm_source, "total": total, "sample": sample}


@router.post("/admin/dealer-licenses/{license_id}/decision")
async def admin_decide_dealer_license(
    license_id: str,
    decision: DealerLicenseAdminAction,
    user: dict = Depends(get_current_user),
):
    """Admin approves or rejects a license. Sends bilingual email to user on status change."""
    if user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    db = _get_db()

    doc = await db.dealer_licenses.find_one({"id": license_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="License not found")

    if decision.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    new_status = (
        DealerLicenseVerificationStatus.APPROVED.value if decision.decision == "approve"
        else DealerLicenseVerificationStatus.REJECTED.value
    )

    await db.dealer_licenses.update_one(
        {"id": license_id},
        {"$set": {
            "status": new_status,
            "rejection_reason": decision.rejection_reason if decision.decision == "reject" else None,
            "reviewed_by": user["id"],
            "reviewed_at": datetime.now(timezone.utc),
        }}
    )

    # iter198 — Auto-create draft vehicle_sellers record on approval (pre-fills license fields).
    # This skips the registration form and lets the dealer go straight from approval → listing.
    if decision.decision == "approve":
        try:
            existing_seller = await db.vehicle_sellers.find_one({"user_id": doc["user_id"]})
            if not existing_seller:
                seller_doc = {
                    "id": str(uuid.uuid4()),
                    "user_id": doc["user_id"],
                    "seller_type": "dealer",
                    "verification_status": "approved",  # license already verified
                    # Business info — empty; dealer can fill in later if needed
                    "business_name": None,
                    "business_address": None,
                    "business_phone": None,
                    # Licensing — pre-filled from the dealer license
                    "license_number": doc.get("license_number"),
                    "license_province": doc.get("jurisdiction"),
                    "license_expiry": doc.get("expiry_date"),
                    "tax_id": None,
                    # Profile
                    "website": None,
                    "description": None,
                    "logo_url": None,
                    # Documents
                    "documents": [],
                    # Stats
                    "total_listings": 0,
                    "total_sold": 0,
                    "total_revenue": 0.0,
                    "average_rating": 0.0,
                    "review_count": 0,
                    # Limits — full dealer monthly limit
                    "monthly_listing_count": 0,
                    "monthly_listing_limit": 500,
                    "current_month": datetime.now(timezone.utc).strftime("%Y-%m"),
                    # Timestamps
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": None,
                    "approved_at": datetime.now(timezone.utc),
                    "approved_by": user["id"],
                    "rejection_reason": None,
                    "auto_created_from_license": True,  # audit flag
                }
                await db.vehicle_sellers.insert_one(seller_doc)

            # iter211-fix — propagate to user document so the dealer dashboard
            # banner (DealerAnnualFeeBanner) and gating logic can see the flag.
            await db.users.update_one(
                {"id": doc["user_id"]},
                {"$set": {
                    "is_vehicle_dealer": True,
                    "vehicle_dealer_approved_at": datetime.now(timezone.utc).isoformat(),
                    "vehicle_dealer_approved_by": user["id"],
                }},
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"[iter198] auto-create vehicle_seller failed: {exc}")

    # iter195 + iter208 — Send transactional email + write admin_notifications + seller_notifications
    try:
        target_user = await db.users.find_one({"id": doc["user_id"]}, {"_id": 0})
        if target_user:
            from services.verification_service import notify_dealer_license_decision
            updated_doc = {**doc, "status": new_status, "rejection_reason": decision.rejection_reason}
            await notify_dealer_license_decision(
                db,
                user=target_user,
                license_doc=updated_doc,
                decision=decision.decision,
                admin_id=user["id"],
                rejection_reason=decision.rejection_reason or "",
            )
    except Exception as exc:
        # Notification failure must not break the decision endpoint
        import logging
        logging.getLogger(__name__).warning(f"[iter208] dealer-license decision notifier failed: {exc}")

    return {"success": True, "status": new_status}


# =============================================================================
#  UNLOCK FEE — Buyer pays 2.5% NET (Stripe fees grossed up) to reveal dealer contact
# =============================================================================

# Stripe Canada rate: 2.9% + $0.30 per transaction.
STRIPE_RATE_PERCENT = 2.9
STRIPE_FIXED_FEE = 0.30
PLATFORM_FEE_PERCENT = 2.5


def _gross_up_for_stripe(net: float) -> dict:
    """
    Solve: total_charged = net + (total_charged * 2.9% + 0.30)
    => total_charged = (net + 0.30) / (1 - 0.029)
    Returns dict with stripe_fee + total_charge.
    """
    total = (net + STRIPE_FIXED_FEE) / (1 - STRIPE_RATE_PERCENT / 100.0)
    stripe_fee = total - net
    return {
        "total_charge": round(total, 2),
        "stripe_fee": round(stripe_fee, 2),
    }


@router.get("/vehicles/{listing_id}/unlock-quote")
async def get_unlock_fee_quote(listing_id: str, user: dict = Depends(get_current_user)):
    """Winner sees the fee breakdown before paying."""
    db = _get_db()
    listing = await db.vehicle_listings.find_one(
        {"id": listing_id},
        {"_id": 0, "winner_id": 1, "final_price": 1, "status": 1, "unlock_paid_at": 1}
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("winner_id") != user["id"] and user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the winning bidder can pay the unlock fee")
    if listing.get("unlock_paid_at"):
        raise HTTPException(status_code=400, detail="Unlock fee already paid")

    winning_bid = float(listing.get("final_price") or 0)
    if winning_bid <= 0:
        raise HTTPException(status_code=400, detail="Auction has no winning bid")

    net = round(winning_bid * PLATFORM_FEE_PERCENT / 100.0, 2)
    grossed = _gross_up_for_stripe(net)

    return UnlockFeeQuote(
        listing_id=listing_id,
        winning_bid=winning_bid,
        platform_fee_percent=PLATFORM_FEE_PERCENT,
        platform_fee_net=net,
        stripe_processing_fee=grossed["stripe_fee"],
        total_charge_to_buyer=grossed["total_charge"],
        currency="CAD",
    )


@router.post("/vehicles/{listing_id}/unlock-fee/checkout")
async def create_unlock_fee_checkout(
    listing_id: str,
    user: dict = Depends(get_current_user),
):
    """Create a Stripe PaymentIntent for the unlock fee."""
    db = _get_db()
    stripe = _get_stripe()

    listing = await db.vehicle_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("winner_id") != user["id"] and user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the winning bidder can pay the unlock fee")
    if listing.get("unlock_paid_at"):
        raise HTTPException(status_code=400, detail="Unlock fee already paid")

    winning_bid = float(listing.get("final_price") or 0)
    net = round(winning_bid * PLATFORM_FEE_PERCENT / 100.0, 2)
    grossed = _gross_up_for_stripe(net)

    intent = stripe.PaymentIntent.create(
        amount=int(round(grossed["total_charge"] * 100)),  # cents
        currency="cad",
        metadata={
            "kind": "vehicle_unlock_fee",
            "listing_id": listing_id,
            "buyer_id": user["id"],
            "winning_bid": str(winning_bid),
            "platform_net": str(net),
            "stripe_fee_estimate": str(grossed["stripe_fee"]),
        },
        description=f"BidVex platform fee — vehicle {listing_id[:8]}",
    )

    await db.vehicle_listings.update_one(
        {"id": listing_id},
        {"$set": {
            "unlock_payment_intent_id": intent.id,
            "unlock_amount_charged": grossed["total_charge"],
            "unlock_platform_net": net,
        }}
    )

    publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    return UnlockFeeIntent(
        listing_id=listing_id,
        payment_intent_id=intent.id,
        client_secret=intent.client_secret,
        publishable_key=publishable_key,
        quote=UnlockFeeQuote(
            listing_id=listing_id,
            winning_bid=winning_bid,
            platform_fee_percent=PLATFORM_FEE_PERCENT,
            platform_fee_net=net,
            stripe_processing_fee=grossed["stripe_fee"],
            total_charge_to_buyer=grossed["total_charge"],
            currency="CAD",
        ),
    )


@router.post("/vehicles/{listing_id}/unlock-fee/confirm")
async def confirm_unlock_fee(
    listing_id: str,
    payload: dict,
    user: dict = Depends(get_current_user),
):
    """
    Confirm a successful PI. Verifies status with Stripe before flipping unlock state.
    Stripe webhook (vehicle.unlock_fee.paid) is idempotent; this endpoint is the
    primary buyer-side confirmation path.
    """
    db = _get_db()
    stripe = _get_stripe()

    listing = await db.vehicle_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("winner_id") != user["id"] and user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the winning bidder")
    if listing.get("unlock_paid_at"):
        return {"success": True, "already_unlocked": True}

    pi_id = payload.get("payment_intent_id") or listing.get("unlock_payment_intent_id")
    if not pi_id:
        raise HTTPException(status_code=400, detail="No payment intent reference")

    intent = stripe.PaymentIntent.retrieve(pi_id)
    if intent.status != "succeeded":
        raise HTTPException(status_code=400, detail=f"Payment not succeeded (status={intent.status})")

    await db.vehicle_listings.update_one(
        {"id": listing_id},
        {"$set": {
            "unlock_paid_at": datetime.now(timezone.utc),
            "unlock_amount_charged": intent.amount / 100.0,
        }}
    )
    return {"success": True}


@router.get("/vehicles/{listing_id}/dealer-contact")
async def get_dealer_contact_after_unlock(
    listing_id: str,
    user: dict = Depends(get_current_user),
):
    """Returns full dealer contact details — gated by `unlock_paid_at`."""
    db = _get_db()
    listing = await db.vehicle_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("winner_id") != user["id"] and user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the winning bidder can view dealer contact")
    if not listing.get("unlock_paid_at"):
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "code": "unlock_fee_unpaid",
                "message_en": "Pay the platform unlock fee to reveal dealer contact details.",
                "message_fr": "Payez les frais de plateforme pour révéler les coordonnées du concessionnaire.",
            }
        )

    seller = await db.vehicle_sellers.find_one({"id": listing["seller_id"]}, {"_id": 0})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller record missing")
    seller_user = await db.users.find_one({"id": seller["user_id"]}, {"_id": 0})

    return DealerContactReveal(
        seller_name=(seller.get("contact_name") or seller_user.get("name", "")),
        seller_phone=seller.get("contact_phone") or seller_user.get("phone"),
        seller_email=seller.get("contact_email") or seller_user.get("email"),
        seller_business_name=seller.get("business_name"),
        pickup_address=listing.get("location_address") or listing.get("location_city", ""),
        pickup_city=listing.get("location_city", ""),
        pickup_province=listing.get("location_province", ""),
        pickup_postal_code=listing.get("location_postal_code", ""),
        additional_notes=listing.get("pickup_notes"),
    )


# =============================================================================
#  Background migration — fill iter194 fields on existing listings
# =============================================================================

async def migrate_existing_vehicle_listings():
    """One-shot: backfill auction_access + run_status on listings that don't have them."""
    db = _get_db()
    res = await db.vehicle_listings.update_many(
        {"$or": [
            {"auction_access": {"$exists": False}},
            {"run_status": {"$exists": False}},
        ]},
        {"$set": {
            "auction_access": "public_individual",
            "run_status": "run_and_drive",
        }}
    )
    return res.modified_count
