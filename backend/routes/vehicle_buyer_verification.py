"""
iter201 — Phase 3 / 3A — Vehicle Buyer Verification (province-aware).

Endpoints:
  • POST /api/vehicles/buyer-verification/submit
        Restricted-province buyers (ON/NB/NS/PE/NL) submit dealer-license
        OR dealer-rep credentials before they can bid. Status: pending_review.
  • POST /api/vehicles/buyer-verification/qc-ack
        Quebec buyers acknowledge LPC disclosure. One-time per listing.
  • GET  /api/vehicles/buyer-verification/me
        Returns the buyer's current verification status + a "what's blocking
        me" reason code for the frontend gate modal.
  • POST /api/vehicles/buyer-province
        Set the buyer's province (separate from free-text address).

Persistence model on `users.vehicle_buyer_verification`:
{
  "province": "ON",
  "type": "dealer" | "dealer_representative" | "individual" | "blocked",
  "license_number": "...",
  "dealer_business_name": "...",        # only for dealer_representative
  "document_path": "...",
  "verified": false,
  "verified_at": null,
  "verified_by": null,
  "submitted_at": "...",
  "rejection_reason": null,
  "qc_lpc_ack": { "<listing_id>": "<isoformat>" }   # per-listing LPC ack
}
"""
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from deps import get_current_user

buyer_verification_router = APIRouter(prefix="/api", tags=["vehicle-buyer-verification"])

# iter295 P0 — Consolidated into services/province_compliance.py.
# These re-exports keep every existing import (`from routes.vehicle_buyer_verification import RESTRICTED_PROVINCES`)
# working unchanged; new code should import from `services.province_compliance` directly.
from services.province_compliance import (  # noqa: F401
    RESTRICTED_PROVINCES,
    OPEN_PROVINCES,
    QC_DISCLOSURE_PROVINCE,
    TERRITORY_PROVINCES,
)


_db_ref: Optional[AsyncIOMotorDatabase] = None


def set_buyer_verification_db(db: AsyncIOMotorDatabase):
    global _db_ref
    _db_ref = db


def _db() -> AsyncIOMotorDatabase:
    if _db_ref is None:
        raise RuntimeError("buyer_verification db not initialised")
    return _db_ref


def _get_buyer_province(user_doc: dict) -> Optional[str]:
    """Read the buyer's province preference. Prefer the structured `province`
    field; fall back to a parsed two-letter code in `address` if present."""
    p = (user_doc.get("province") or "").strip().upper()
    if p in OPEN_PROVINCES | RESTRICTED_PROVINCES | TERRITORY_PROVINCES | {QC_DISCLOSURE_PROVINCE}:
        return p
    return None


# ─────────────────── REQUEST MODELS ───────────────────

class BuyerProvinceUpdate(BaseModel):
    province: str = Field(..., min_length=2, max_length=2)


class BuyerVerificationSubmit(BaseModel):
    type: Literal["dealer", "dealer_representative"]
    license_number: str = Field(..., min_length=2, max_length=64)
    dealer_business_name: Optional[str] = None  # required for dealer_representative


class QCDisclosureAck(BaseModel):
    listing_id: str = Field(..., min_length=4, max_length=128)


# ─────────────────── ENDPOINTS ───────────────────

@buyer_verification_router.post("/vehicles/buyer-province")
async def set_buyer_province(payload: BuyerProvinceUpdate, current_user: dict = Depends(get_current_user)):
    """Set the buyer's province (ISO-3166-2 CA-* two-letter code)."""
    code = payload.province.strip().upper()
    valid = OPEN_PROVINCES | RESTRICTED_PROVINCES | TERRITORY_PROVINCES | {QC_DISCLOSURE_PROVINCE}
    if code not in valid:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_province",
            "message_en": f"Unknown province code: {code}",
            "message_fr": f"Code de province inconnu : {code}",
        })

    user_id = current_user["id"] if isinstance(current_user, dict) else current_user.id
    res = await _db().users.update_one(
        {"id": user_id},
        {"$set": {"province": code, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "province": code}


@buyer_verification_router.post("/vehicles/buyer-verification/submit")
async def submit_buyer_verification(
    type: Literal["dealer", "dealer_representative"] = Form(...),
    license_number: str = Form(...),
    dealer_business_name: Optional[str] = Form(None),
    document: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    """Restricted-province buyer submits dealer credentials. Goes to admin queue."""
    user_id = current_user["id"] if isinstance(current_user, dict) else current_user.id
    user_doc = await _db().users.find_one({"id": user_id}, {"_id": 0, "email": 1, "province": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    province = _get_buyer_province(user_doc)
    if province not in RESTRICTED_PROVINCES:
        raise HTTPException(status_code=400, detail={
            "code": "verification_not_required",
            "message_en": f"Buyer verification is not required for {province or 'your province'}.",
            "message_fr": "La vérification d'acheteur n'est pas requise pour votre province.",
        })

    if type == "dealer_representative" and not (dealer_business_name or "").strip():
        raise HTTPException(status_code=400, detail={
            "code": "business_name_required",
            "message_en": "Dealer business name is required for representative submissions.",
            "message_fr": "Le nom de l'entreprise du concessionnaire est requis.",
        })

    # Save the document if provided (in /uploads/buyer_verifications/)
    document_path = None
    if document is not None:
        import os
        upload_dir = "/app/backend/uploads/buyer_verifications"
        os.makedirs(upload_dir, exist_ok=True)
        # Sanitize filename
        ext = (document.filename or "").rsplit(".", 1)[-1].lower() if "." in (document.filename or "") else "bin"
        if ext not in ("pdf", "jpg", "jpeg", "png"):
            raise HTTPException(status_code=400, detail="Document must be PDF, JPG, or PNG")
        # Read with size cap (10 MB)
        body = await document.read()
        if len(body) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Document exceeds 10 MB limit")
        filename = f"{user_id}_{int(datetime.now(timezone.utc).timestamp())}.{ext}"
        with open(os.path.join(upload_dir, filename), "wb") as f:
            f.write(body)
        document_path = f"buyer_verifications/{filename}"

    submission = {
        "province": province,
        "type": type,
        "license_number": license_number.strip()[:64],
        "dealer_business_name": (dealer_business_name or "").strip()[:128] or None,
        "document_path": document_path,
        "verified": False,
        "verified_at": None,
        "verified_by": None,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "rejection_reason": None,
        "status": "pending_review",
        "qc_lpc_ack": {},
    }

    await _db().users.update_one(
        {"id": user_id},
        {"$set": {"vehicle_buyer_verification": submission, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    await _db().audit_logs.insert_one({
        "action": "buyer_verification_submitted",
        "user_id": user_id,
        "email": user_doc.get("email"),
        "province": province,
        "type": type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {"success": True, "status": "pending_review"}


@buyer_verification_router.post("/vehicles/buyer-verification/qc-ack")
async def acknowledge_qc_lpc_disclosure(payload: QCDisclosureAck, current_user: dict = Depends(get_current_user)):
    """Quebec buyer acknowledges LPC disclosure for a specific listing.
    Per CEO Q1=(c): show only ONCE per user per listing."""
    user_id = current_user["id"] if isinstance(current_user, dict) else current_user.id
    user_doc = await _db().users.find_one({"id": user_id}, {"_id": 0, "vehicle_buyer_verification": 1, "province": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    province = _get_buyer_province(user_doc)
    if province != QC_DISCLOSURE_PROVINCE:
        raise HTTPException(status_code=400, detail={
            "code": "qc_only",
            "message_en": "LPC acknowledgement is only required for Quebec buyers.",
            "message_fr": "L'accusé LPC n'est requis que pour les acheteurs québécois.",
        })

    bv = user_doc.get("vehicle_buyer_verification") or {}
    qc_acks = bv.get("qc_lpc_ack") or {}
    qc_acks[payload.listing_id] = datetime.now(timezone.utc).isoformat()
    bv["qc_lpc_ack"] = qc_acks
    bv.setdefault("province", "QC")
    bv.setdefault("type", "individual")
    bv.setdefault("verified", True)  # QC individuals self-verify by ack

    await _db().users.update_one(
        {"id": user_id},
        {"$set": {"vehicle_buyer_verification": bv, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True, "listing_id": payload.listing_id, "acknowledged_at": qc_acks[payload.listing_id]}


@buyer_verification_router.get("/vehicles/buyer-verification/me")
async def my_buyer_verification(listing_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """
    Returns the buyer's current province + verification state and tells the
    frontend exactly what to show.
    """
    user_id = current_user["id"] if isinstance(current_user, dict) else current_user.id
    user_doc = await _db().users.find_one(
        {"id": user_id},
        {"_id": 0, "id": 1, "province": 1, "vehicle_buyer_verification": 1},
    )
    if user_doc is None:
        raise HTTPException(status_code=404, detail="User not found")

    province = _get_buyer_province(user_doc)
    bv = user_doc.get("vehicle_buyer_verification") or {}

    if not province:
        return {"province": None, "gate_state": "province_required", "verified": False}

    if province in OPEN_PROVINCES:
        return {"province": province, "gate_state": "open", "verified": True}

    if province in TERRITORY_PROVINCES:
        return {"province": province, "gate_state": "territory_advisory", "verified": True}

    if province == QC_DISCLOSURE_PROVINCE:
        listing_acked = bool(listing_id) and (bv.get("qc_lpc_ack") or {}).get(listing_id) is not None
        return {
            "province": province,
            "gate_state": "qc_disclosure" if not listing_acked else "qc_disclosure_acked",
            "verified": True,
            "qc_lpc_ack_for_listing": listing_acked,
        }

    # Restricted provinces — depends on submission status
    if province in RESTRICTED_PROVINCES:
        # iter201 — Verification only counts if it was issued for the CURRENT province.
        bv_province = (bv.get("province") or "").upper()
        is_verified = bool(bv.get("verified")) and bv_province == province
        status = (bv or {}).get("status") or "not_submitted"
        if is_verified:
            return {"province": province, "gate_state": "verified", "verified": True, "type": bv.get("type")}
        if status == "pending_review" and bv_province == province:
            return {"province": province, "gate_state": "pending_review", "verified": False, "submitted_at": bv.get("submitted_at")}
        if status == "rejected" and bv_province == province:
            return {"province": province, "gate_state": "rejected", "verified": False, "rejection_reason": bv.get("rejection_reason")}
        return {"province": province, "gate_state": "restricted_gate", "verified": False}

    return {"province": province, "gate_state": "open", "verified": True}
