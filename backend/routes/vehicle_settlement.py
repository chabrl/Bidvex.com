"""
BidVex — Vehicle Settlement Routes
Handles fee calculation, seller-contact gating, and settlement status.
"""

from fastapi import APIRouter, HTTPException, Depends
from deps import get_db, get_current_user, User
from services.vehicle_fee_service import calculate_vehicle_fee
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

vehicle_settlement_router = APIRouter(tags=["Vehicle Settlement"])


@vehicle_settlement_router.get("/vehicle-settlement/fee-preview/{hammer_price}")
async def preview_vehicle_fee(hammer_price: float):
    """
    Public endpoint: calculate the platform fee breakdown for a given hammer price.
    Used by frontend to show the bilingual fee breakdown on bidding screens.
    """
    if hammer_price <= 0:
        raise HTTPException(status_code=400, detail="Hammer price must be positive")
    fees = calculate_vehicle_fee(hammer_price)
    return {
        "hammer_price": fees["hammer_price"],
        "platform_fee": fees["net_commission"],
        "processing_fee": fees["stripe_processing_fee"],
        "total_charge_to_buyer": fees["total_charge"],
        "fee_rate_percent": fees["fee_rate"] * 100,
        "currency": "CAD",
        "breakdown_en": f"Platform Fee: ${fees['net_commission']:.2f} + Processing: ${fees['stripe_processing_fee']:.2f}",
        "breakdown_fr": f"Frais de plateforme : {fees['net_commission']:.2f} $ + Traitement : {fees['stripe_processing_fee']:.2f} $",
    }


@vehicle_settlement_router.get("/auctions/{auction_id}/seller-contact")
async def get_seller_contact(auction_id: str, current_user: User = Depends(get_current_user)):
    """
    Gated endpoint: returns seller contact info ONLY after platform fee is paid.
    Returns 402 Payment Required if contact_revealed is false.
    """
    db = get_db()

    # Check settlement record
    settlement = await db.vehicle_settlements.find_one(
        {"auction_id": auction_id, "buyer_id": current_user.id},
        {"_id": 0}
    )

    if not settlement:
        raise HTTPException(
            status_code=402,
            detail={
                "message_en": "Platform fee payment required to view seller contact information.",
                "message_fr": "Le paiement des frais de plateforme est requis pour voir les coordonnées du vendeur.",
                "settlement_status": "PENDING_CLOSE",
            }
        )

    if not settlement.get("contact_revealed", False):
        raise HTTPException(
            status_code=402,
            detail={
                "message_en": "Platform fee payment is being processed. Seller contact will be revealed once payment succeeds.",
                "message_fr": "Le paiement des frais de plateforme est en cours de traitement. Les coordonnées du vendeur seront révélées une fois le paiement réussi.",
                "settlement_status": settlement.get("settlement_status", "FEE_PROCESSING"),
            }
        )

    # Fee paid — reveal seller contact
    listing = await db.vehicle_listings.find_one({"id": auction_id}, {"_id": 0})
    if not listing:
        listing = await db.listings.find_one({"id": auction_id}, {"_id": 0})

    seller_id = (listing or {}).get("seller_user_id") or (listing or {}).get("seller_id")
    if not seller_id:
        raise HTTPException(status_code=404, detail="Seller not found for this auction")

    seller = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "name": 1, "email": 1, "phone": 1, "company_name": 1, "address": 1}
    )
    if not seller:
        raise HTTPException(status_code=404, detail="Seller account not found")

    return {
        "contact_revealed": True,
        "settlement_status": "FEE_PAID",
        "seller": {
            "name": seller.get("company_name") or seller.get("name", ""),
            "email": seller.get("email", ""),
            "phone": seller.get("phone", ""),
            "address": seller.get("address", ""),
        },
        "auction_id": auction_id,
        "hammer_price": settlement.get("hammer_price"),
        "fee_paid": settlement.get("net_commission_amount"),
    }


@vehicle_settlement_router.get("/vehicle-settlement/{auction_id}/status")
async def get_settlement_status(auction_id: str, current_user: User = Depends(get_current_user)):
    """Check settlement status for an auction the user won."""
    db = get_db()
    settlement = await db.vehicle_settlements.find_one(
        {"auction_id": auction_id, "buyer_id": current_user.id},
        {"_id": 0, "settlement_status": 1, "contact_revealed": 1, "hammer_price": 1,
         "net_commission_amount": 1, "total_processed_amount": 1, "fee_paid_at": 1}
    )
    if not settlement:
        return {"settlement_status": "PENDING_CLOSE", "contact_revealed": False}
    return settlement



@vehicle_settlement_router.post("/vehicle-settlement/verify-card")
async def verify_card_for_bidding(current_user: User = Depends(get_current_user)):
    """
    Pre-bid safety gate: Create a Stripe SetupIntent to verify the buyer's card
    supports 3D Secure before allowing bids on vehicle auctions.
    Returns the client_secret for the frontend to confirm.
    """
    import os
    import stripe
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
    db = get_db()

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "stripe_customer_id": 1})
    if not user_doc or not user_doc.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No payment method on file. Please add a card first.")

    # Check if already verified recently
    existing = await db.card_verifications.find_one({
        "user_id": current_user.id,
        "status": "succeeded",
    })
    if existing:
        return {"verified": True, "message": "Card already verified."}

    try:
        si = stripe.SetupIntent.create(
            customer=user_doc["stripe_customer_id"],
            usage="off_session",
            metadata={
                "user_id": current_user.id,
                "purpose": "vehicle_bid_verification",
            },
        )

        await db.card_verifications.insert_one({
            "user_id": current_user.id,
            "setup_intent_id": si.id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "verified": False,
            "client_secret": si.client_secret,
            "setup_intent_id": si.id,
            "message_en": "To ensure auction integrity, please verify your card. This is a temporary authorization only.",
            "message_fr": "Pour garantir l'intégrité de l'enchère, veuillez vérifier votre carte. Il s'agit d'une autorisation temporaire uniquement.",
        }
    except Exception as e:
        logger.error(f"SetupIntent creation failed: {e}")
        raise HTTPException(status_code=500, detail="Card verification failed. Please try again.")


@vehicle_settlement_router.post("/vehicle-settlement/confirm-card-verification")
async def confirm_card_verification(current_user: User = Depends(get_current_user)):
    """Mark card as verified after frontend confirms the SetupIntent."""
    db = get_db()
    await db.card_verifications.update_one(
        {"user_id": current_user.id, "status": "pending"},
        {"$set": {"status": "succeeded", "verified_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"verified": True, "message": "Card verified successfully."}


# ============================================================================
# SETTLEMENT CONFIRMATION WORKFLOW (iteration 167)
# ----------------------------------------------------------------------------
# After the buyer pays the 2.5% BidVex fee, the vehicle enters the
# "AWAITING_DEALER_CONFIRMATION" state. The dealer must then attest that the
# vehicle has been paid for in full AND delivered. This creates an on-platform
# LEGACY: opc_permit → migrated to dealer_license_* (iter201) — do not expose to users.
# audit trail for provincial-dealer compliance — even though BidVex never custodied the
# vehicle price itself.
#
# State transitions:
#   FEE_PAID → AWAITING_DEALER_CONFIRMATION → DEALER_CONFIRMED
#           → FULLY_SETTLED (after optional buyer ack)
#           → DISPUTED (buyer escalates) → ADMIN_RESOLVED
#
# Endpoints:
#   GET  /api/vehicles/dealer/pending-settlements        (dealer queue)
#   POST /api/vehicles/{vehicle_id}/dealer-confirm       (dealer attests)
#   POST /api/vehicles/{vehicle_id}/proof-upload         (optional PDF/image)
#   GET  /api/vehicles/settlement/{vehicle_id}/proof     (download proof)
#   GET  /api/vehicles/buyer/settlements                 (buyer's settlements)
#   POST /api/vehicles/{vehicle_id}/buyer-acknowledge    (buyer confirms)
#   POST /api/vehicles/{vehicle_id}/buyer-dispute        (buyer escalates)
#   GET  /api/admin/vehicles/disputed-settlements        (admin queue)
#   POST /api/admin/vehicles/{vehicle_id}/resolve        (admin resolve)
# ============================================================================

from fastapi import BackgroundTasks, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import io

ALLOWED_SETTLEMENT_METHODS = {
    "bank_wire", "cheque", "cash", "certified_draft", "financing", "other"
}
ALLOWED_PROOF_MIME = {
    "application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"
}
MAX_PROOF_BYTES = 10 * 1024 * 1024  # 10 MB


class DealerConfirmPayload(BaseModel):
    dealer_attestation: bool = Field(..., description="Must be true — dealer legally attests vehicle is paid + delivered")
    dealer_amount_received: float = Field(..., ge=0, description="Amount dealer received (defaults to hammer)")
    dealer_settlement_method: str = Field(..., description=f"One of {sorted(ALLOWED_SETTLEMENT_METHODS)}")
    dealer_notes: Optional[str] = None


class BuyerDisputePayload(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


class AdminResolvePayload(BaseModel):
    resolution: str = Field(..., description="'settle_in_favor_of_dealer' | 'settle_in_favor_of_buyer' | 'refund_platform_fee'")
    admin_notes: str = Field(..., min_length=10)


async def _require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def _load_settlement_or_404(db, vehicle_id: str):
    s = await db.vehicle_settlements.find_one({"auction_id": vehicle_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Settlement not found for this vehicle")
    return s


# ── DEALER SIDE ─────────────────────────────────────────────────────────────

@vehicle_settlement_router.get("/vehicles/dealer/pending-settlements")
async def dealer_pending_settlements(current_user: User = Depends(get_current_user)):
    """Return the list of settlements where THIS dealer must confirm."""
    db = get_db()
    cursor = db.vehicle_settlements.find(
        {
            "seller_id": current_user.id,
            "settlement_status": {"$in": ["AWAITING_DEALER_CONFIRMATION", "DEALER_CONFIRMED", "FULLY_SETTLED", "DISPUTED"]},
        },
        {"_id": 0},
    ).sort("fee_paid_at", -1).limit(100)
    settlements = await cursor.to_list(100)

    # Enrich with vehicle title + buyer info
    vehicle_ids = list({s["auction_id"] for s in settlements})
    buyer_ids = list({s["buyer_id"] for s in settlements})

    vehicles: dict = {}
    async for v in db.vehicle_listings.find({"id": {"$in": vehicle_ids}}, {"_id": 0, "id": 1, "title": 1, "make": 1, "model": 1, "year": 1, "vin": 1}):
        vehicles[v["id"]] = v

    buyers: dict = {}
    async for u in db.users.find({"id": {"$in": buyer_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1, "company_name": 1}):
        buyers[u["id"]] = u

    for s in settlements:
        s["vehicle"] = vehicles.get(s["auction_id"], {})
        s["buyer"] = buyers.get(s["buyer_id"], {})

    return {"total": len(settlements), "settlements": settlements}


@vehicle_settlement_router.post("/vehicles/{vehicle_id}/dealer-confirm")
async def dealer_confirm_settlement(
    vehicle_id: str,
    payload: DealerConfirmPayload,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Dealer attests that the vehicle has been paid for in full AND delivered.
    Attestation is REQUIRED (legal basis for the audit trail).
    Proof upload is OPTIONAL — handled via the separate /proof-upload endpoint.
    """
    db = get_db()
    settlement = await _load_settlement_or_404(db, vehicle_id)

    if settlement.get("seller_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="You are not the dealer for this vehicle")

    if settlement.get("settlement_status") not in {"AWAITING_DEALER_CONFIRMATION", "DISPUTED"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm — current status: {settlement.get('settlement_status')}"
        )

    if not payload.dealer_attestation:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "attestation_required",
                "message_en": "You must legally attest that the vehicle has been paid for in full and delivered.",
                "message_fr": "Vous devez attester légalement que le véhicule a été payé en totalité et livré.",
            },
        )

    if payload.dealer_settlement_method not in ALLOWED_SETTLEMENT_METHODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid settlement method. Must be one of: {sorted(ALLOWED_SETTLEMENT_METHODS)}"
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.vehicle_settlements.update_one(
        {"auction_id": vehicle_id},
        {"$set": {
            "settlement_status": "DEALER_CONFIRMED",
            "dealer_confirmed_at": now,
            "dealer_attestation": True,
            "dealer_attestation_at": now,
            "dealer_attestation_ip": None,  # could be wired if needed
            "dealer_amount_received": payload.dealer_amount_received,
            "dealer_settlement_method": payload.dealer_settlement_method,
            "dealer_notes": payload.dealer_notes,
            "updated_at": now,
        }},
    )

    # Audit log
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "vehicle_settlement_dealer_confirmed",
        "target_type": "vehicle_settlement",
        "target_id": vehicle_id,
        "actor_id": current_user.id,
        "actor_email": current_user.email,
        "timestamp": now,
        "amount_received": payload.dealer_amount_received,
        "method": payload.dealer_settlement_method,
    })

    # Email both parties (non-blocking)
    try:
        buyer = await db.users.find_one({"id": settlement["buyer_id"]}, {"_id": 0})
        if buyer:
            background_tasks.add_task(
                _notify_buyer_of_dealer_confirmation,
                buyer, vehicle_id, settlement, payload
            )
    except Exception as e:
        logger.error(f"[SETTLEMENT] Notify buyer failed for {vehicle_id}: {e}")

    logger.info(f"[SETTLEMENT] Vehicle {vehicle_id} DEALER_CONFIRMED by {current_user.email} "
                f"amount=${payload.dealer_amount_received} method={payload.dealer_settlement_method}")

    return {"success": True, "settlement_status": "DEALER_CONFIRMED", "vehicle_id": vehicle_id}


async def _notify_buyer_of_dealer_confirmation(buyer: dict, vehicle_id: str, settlement: dict, payload: DealerConfirmPayload):
    """Bilingual email — dealer has confirmed receipt; buyer can optionally acknowledge."""
    try:
        from services.emails._email_core import send_email
        email = (buyer or {}).get("email")
        if not email:
            return
        method_labels_en = {
            "bank_wire": "Bank wire", "cheque": "Cheque", "cash": "Cash",
            "certified_draft": "Certified bank draft", "financing": "Financing", "other": "Other",
        }
        method_labels_fr = {
            "bank_wire": "Virement bancaire", "cheque": "Chèque", "cash": "Comptant",
            "certified_draft": "Traite bancaire", "financing": "Financement", "other": "Autre",
        }
        method_en = method_labels_en.get(payload.dealer_settlement_method, payload.dealer_settlement_method)
        method_fr = method_labels_fr.get(payload.dealer_settlement_method, payload.dealer_settlement_method)

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
          <h2 style="color:#2186C6;">Dealer Confirmed Settlement / Le concessionnaire a confirmé le règlement</h2>
          <hr style="border:none;border-top:1px solid #eee;"/>
          <p><strong>EN:</strong></p>
          <p>The dealer for vehicle <strong>#{vehicle_id[:8]}</strong> has confirmed that they received full payment (<strong>${payload.dealer_amount_received:,.2f} CAD</strong> via {method_en}) and delivered the vehicle to you.</p>
          <p>If this matches your records, no further action is required. If there is a discrepancy, please <a href="https://www.bidvex.com/buyer-dashboard?tab=vehicle-purchases" style="color:#2186C6;">open a dispute within 48 hours</a>.</p>
          <p style="font-size:12px;color:#666;">Dealer's note: {payload.dealer_notes or '—'}</p>
          <hr style="border:none;border-top:1px solid #eee;"/>
          <p><strong>FR:</strong></p>
          <p>Le concessionnaire du véhicule <strong>#{vehicle_id[:8]}</strong> a confirmé avoir reçu le paiement complet (<strong>{payload.dealer_amount_received:,.2f} $ CAD</strong> par {method_fr}) et vous avoir livré le véhicule.</p>
          <p>Si cela correspond à vos informations, aucune action n'est requise. En cas de divergence, <a href="https://www.bidvex.com/buyer-dashboard?tab=vehicle-purchases" style="color:#2186C6;">ouvrez un litige dans les 48 heures</a>.</p>
          <p style="font-size:12px;color:#666;">Note du concessionnaire : {payload.dealer_notes or '—'}</p>
        </div>
        """
        await send_email(
            to_email=email,
            subject=f"Dealer confirmed settlement — Vehicle #{vehicle_id[:8]}",
            html_content=html,
        )
    except Exception as e:
        logger.error(f"[SETTLEMENT] buyer email failed: {e}")


# ── PROOF UPLOAD (optional) ─────────────────────────────────────────────────

@vehicle_settlement_router.post("/vehicles/{vehicle_id}/proof-upload")
async def upload_settlement_proof(
    vehicle_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Optional — dealer uploads a Bill of Sale PDF, wire-receipt, or cheque scan.
    Stored in MongoDB GridFS. Max 10 MB. PDF/PNG/JPEG/WebP only.
    """
    import gridfs
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket

    db = get_db()
    settlement = await _load_settlement_or_404(db, vehicle_id)
    if settlement.get("seller_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="You are not the dealer for this vehicle")

    if file.content_type not in ALLOWED_PROOF_MIME:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed: PDF, PNG, JPEG, WebP"
        )

    payload = await file.read()
    if len(payload) > MAX_PROOF_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")

    bucket = AsyncIOMotorGridFSBucket(db, bucket_name="settlement_proofs")
    file_id = await bucket.upload_from_stream(
        f"{vehicle_id}_{file.filename}",
        io.BytesIO(payload),
        metadata={
            "vehicle_id": vehicle_id,
            "dealer_id": current_user.id,
            "mime": file.content_type,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    await db.vehicle_settlements.update_one(
        {"auction_id": vehicle_id},
        {"$set": {
            "dealer_proof_file_id": str(file_id),
            "dealer_proof_filename": file.filename,
            "dealer_proof_mime": file.content_type,
            "dealer_proof_uploaded_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    logger.info(f"[SETTLEMENT] proof uploaded for {vehicle_id} file_id={file_id} size={len(payload)}")
    return {
        "success": True,
        "file_id": str(file_id),
        "filename": file.filename,
        "size_bytes": len(payload),
    }


@vehicle_settlement_router.get("/vehicles/settlement/{vehicle_id}/proof")
async def download_settlement_proof(vehicle_id: str, current_user: User = Depends(get_current_user)):
    """Download the settlement proof (only dealer, buyer, or admin can access)."""
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    from bson import ObjectId
    db = get_db()

    settlement = await _load_settlement_or_404(db, vehicle_id)
    file_id = settlement.get("dealer_proof_file_id")
    if not file_id:
        raise HTTPException(status_code=404, detail="No proof uploaded for this settlement")

    # Authorization: dealer, buyer, or admin
    authorized = (
        current_user.id == settlement.get("seller_id")
        or current_user.id == settlement.get("buyer_id")
        or current_user.role in ("admin", "super_admin")
    )
    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized to view this proof")

    bucket = AsyncIOMotorGridFSBucket(db, bucket_name="settlement_proofs")
    try:
        stream = await bucket.open_download_stream(ObjectId(file_id))
        data = await stream.read()
    except Exception as e:
        logger.error(f"[SETTLEMENT] proof read failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve proof file")

    return Response(
        content=data,
        media_type=settlement.get("dealer_proof_mime", "application/octet-stream"),
        headers={"Content-Disposition": f"inline; filename=\"{settlement.get('dealer_proof_filename', 'proof')}\""},
    )


# ── BUYER SIDE ──────────────────────────────────────────────────────────────

@vehicle_settlement_router.get("/vehicles/buyer/settlements")
async def buyer_settlements(current_user: User = Depends(get_current_user)):
    """Return all vehicle settlements where THIS user is the winning buyer."""
    db = get_db()
    cursor = db.vehicle_settlements.find(
        {"buyer_id": current_user.id},
        {"_id": 0},
    ).sort("fee_paid_at", -1).limit(100)
    settlements = await cursor.to_list(100)
    vehicle_ids = list({s["auction_id"] for s in settlements})
    vehicles: dict = {}
    async for v in db.vehicle_listings.find({"id": {"$in": vehicle_ids}}, {"_id": 0}):
        vehicles[v["id"]] = v
    for s in settlements:
        s["vehicle"] = vehicles.get(s["auction_id"], {})
    return {"total": len(settlements), "settlements": settlements}


@vehicle_settlement_router.post("/vehicles/{vehicle_id}/buyer-acknowledge")
async def buyer_acknowledge_settlement(
    vehicle_id: str,
    current_user: User = Depends(get_current_user),
):
    """Buyer confirms receipt — transitions DEALER_CONFIRMED → FULLY_SETTLED."""
    db = get_db()
    settlement = await _load_settlement_or_404(db, vehicle_id)
    if settlement.get("buyer_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="You are not the buyer for this vehicle")
    if settlement.get("settlement_status") != "DEALER_CONFIRMED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot acknowledge — current status: {settlement.get('settlement_status')}"
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.vehicle_settlements.update_one(
        {"auction_id": vehicle_id},
        {"$set": {
            "settlement_status": "FULLY_SETTLED",
            "buyer_acknowledged_at": now,
            "updated_at": now,
        }},
    )
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "vehicle_settlement_buyer_acknowledged",
        "target_type": "vehicle_settlement",
        "target_id": vehicle_id,
        "actor_id": current_user.id,
        "actor_email": current_user.email,
        "timestamp": now,
    })
    logger.info(f"[SETTLEMENT] Vehicle {vehicle_id} FULLY_SETTLED (buyer ack)")
    return {"success": True, "settlement_status": "FULLY_SETTLED"}


@vehicle_settlement_router.post("/vehicles/{vehicle_id}/buyer-dispute")
async def buyer_dispute_settlement(
    vehicle_id: str,
    payload: BuyerDisputePayload,
    current_user: User = Depends(get_current_user),
):
    """Buyer disputes the dealer's confirmation. Escalates to admin queue."""
    db = get_db()
    settlement = await _load_settlement_or_404(db, vehicle_id)
    if settlement.get("buyer_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="You are not the buyer for this vehicle")
    if settlement.get("settlement_status") not in {"AWAITING_DEALER_CONFIRMATION", "DEALER_CONFIRMED"}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot dispute — current status: {settlement.get('settlement_status')}"
        )
    now = datetime.now(timezone.utc).isoformat()
    await db.vehicle_settlements.update_one(
        {"auction_id": vehicle_id},
        {"$set": {
            "settlement_status": "DISPUTED",
            "buyer_dispute_reason": payload.reason,
            "buyer_dispute_at": now,
            "updated_at": now,
        }},
    )
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "vehicle_settlement_buyer_disputed",
        "target_type": "vehicle_settlement",
        "target_id": vehicle_id,
        "actor_id": current_user.id,
        "actor_email": current_user.email,
        "timestamp": now,
        "reason": payload.reason,
    })
    logger.info(f"[SETTLEMENT] Vehicle {vehicle_id} DISPUTED by {current_user.email}")
    return {"success": True, "settlement_status": "DISPUTED"}


# ── ADMIN SIDE ──────────────────────────────────────────────────────────────

@vehicle_settlement_router.get("/admin/vehicles/disputed-settlements")
async def admin_disputed_settlements(current_user: User = Depends(_require_admin)):
    """Admin queue: all DISPUTED settlements pending resolution."""
    db = get_db()
    cursor = db.vehicle_settlements.find(
        {"settlement_status": "DISPUTED"},
        {"_id": 0},
    ).sort("buyer_dispute_at", 1).limit(200)
    disputes = await cursor.to_list(200)

    vehicle_ids = list({s["auction_id"] for s in disputes})
    user_ids = set()
    for s in disputes:
        if s.get("buyer_id"):
            user_ids.add(s["buyer_id"])
        if s.get("seller_id"):
            user_ids.add(s["seller_id"])

    vehicles: dict = {}
    async for v in db.vehicle_listings.find({"id": {"$in": vehicle_ids}}, {"_id": 0}):
        vehicles[v["id"]] = v

    users: dict = {}
    async for u in db.users.find({"id": {"$in": list(user_ids)}}, {"_id": 0, "id": 1, "name": 1, "email": 1, "company_name": 1}):
        users[u["id"]] = u

    for s in disputes:
        s["vehicle"] = vehicles.get(s["auction_id"], {})
        s["buyer"] = users.get(s.get("buyer_id"), {})
        s["seller"] = users.get(s.get("seller_id"), {})

    return {"total": len(disputes), "disputes": disputes}


@vehicle_settlement_router.get("/admin/vehicles/disputed-settlements/count")
async def admin_disputed_settlements_count(current_user: User = Depends(_require_admin)):
    """iter197 — Lightweight counter for the Admin Home triage card."""
    db = get_db()
    total = await db.vehicle_settlements.count_documents({"settlement_status": "DISPUTED"})
    return {"total": total}


@vehicle_settlement_router.post("/admin/vehicles/{vehicle_id}/resolve")
async def admin_resolve_settlement(
    vehicle_id: str,
    payload: AdminResolvePayload,
    current_user: User = Depends(_require_admin),
):
    """Admin closes a DISPUTED settlement with a written resolution."""
    if payload.resolution not in {"settle_in_favor_of_dealer", "settle_in_favor_of_buyer", "refund_platform_fee"}:
        raise HTTPException(status_code=400, detail="Invalid resolution")

    db = get_db()
    settlement = await _load_settlement_or_404(db, vehicle_id)
    if settlement.get("settlement_status") != "DISPUTED":
        raise HTTPException(status_code=400, detail="Only DISPUTED settlements can be admin-resolved")

    now = datetime.now(timezone.utc).isoformat()
    await db.vehicle_settlements.update_one(
        {"auction_id": vehicle_id},
        {"$set": {
            "settlement_status": "ADMIN_RESOLVED",
            "admin_resolution": payload.resolution,
            "admin_notes": payload.admin_notes,
            "admin_resolved_at": now,
            "admin_resolved_by": current_user.id,
            "updated_at": now,
        }},
    )
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "vehicle_settlement_admin_resolved",
        "target_type": "vehicle_settlement",
        "target_id": vehicle_id,
        "actor_id": current_user.id,
        "actor_email": current_user.email,
        "timestamp": now,
        "resolution": payload.resolution,
        "notes": payload.admin_notes,
    })
    logger.info(f"[SETTLEMENT] Vehicle {vehicle_id} ADMIN_RESOLVED by {current_user.email} → {payload.resolution}")
    return {"success": True, "settlement_status": "ADMIN_RESOLVED", "resolution": payload.resolution}
