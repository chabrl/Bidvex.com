"""
iter217 Phase 5 Hotfix v5b — Broker Ecosystem API.

Three groups of endpoints:

  1. Broker self-service:
     - POST /api/brokers/apply           (logged-in user applies)
     - GET  /api/brokers                 (public directory of approved brokers)
     - GET  /api/brokers/me              (broker dashboard data)
     - GET  /api/brokers/{id}            (public profile)
     - PATCH /api/brokers/settings       (update fee structure / settings)

  2. Buyer ↔ broker relationships:
     - POST /api/broker-relationships/request           (buyer)
     - GET  /api/broker-relationships/my-broker         (buyer)
     - GET  /api/broker-relationships/my-buyers         (broker)
     - POST /api/broker-relationships/{id}/approve      (broker)
     - POST /api/broker-relationships/{id}/reject       (broker)
     - PATCH /api/broker-relationships/{id}/bid-limit   (broker)
     - POST /api/broker-relationships/{id}/release-deposit (broker)
     - POST /api/broker-relationships/{id}/capture-deposit (broker+admin)
     - POST /api/broker-relationships/{id}/terminate    (broker)
     - POST /api/broker-relationships/{id}/suspend      (broker)

  3. Broker bidding:
     - POST /api/vehicle-auctions/{id}/bid-via-broker   (buyer)
     - GET  /api/broker-bids/audit                      (admin)

  4. Admin:
     - GET   /api/admin/brokers
     - PATCH /api/admin/brokers/{id}/approve
     - PATCH /api/admin/brokers/{id}/reject
     - PATCH /api/admin/brokers/{id}/suspend
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, require_admin, User
from models.broker_models import (
    BrokerCreate, BrokerFeeStructure, RelationshipRequest,
    make_broker_doc, make_relationship_doc, make_broker_bid_doc,
)
from services.broker_conflict_guard import check_intra_broker_conflict
from services.broker_fee_engine import calculate_broker_transaction

logger = logging.getLogger("broker_routes")

brokers_router = APIRouter(prefix="/api", tags=["brokers"])

DEFAULT_DEPOSIT_CAD = 500.0

# iter217 Phase 5 Hotfix v6 — Broker subscription model.
# Brokers pay a yearly platform fee. Default is $200/year; the launch
# promotion applies a 50% discount until admin clears it. Per-broker
# overrides are stored on the broker doc and take precedence.
BROKER_SUBSCRIPTION_BASE_CAD     = 200.0
BROKER_SUBSCRIPTION_DISCOUNT_PCT = 50.0   # 0..100, applied to base
BROKER_SUBSCRIPTION_PERIOD_DAYS  = 365


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _exclude_id(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if d is None:
        return None
    d.pop("_id", None)
    return d


# ── 1. Broker self-service ─────────────────────────────────────────────
@brokers_router.post("/brokers/apply")
async def apply_to_become_broker(payload: BrokerCreate, current_user: User = Depends(get_current_user)):
    db = get_db()
    # User can have at most one broker record
    existing = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1, "verification_status": 1})
    if existing:
        raise HTTPException(status_code=400, detail={
            "error": "broker_application_exists",
            "message_en": "You already have a broker application on file.",
            "message_fr": "Vous avez déjà une demande de courtier au dossier.",
            "broker_id": existing["id"],
            "verification_status": existing["verification_status"],
        })
    # Cannot be a partner and a broker simultaneously
    if (current_user.account_type or "").lower() in ("partner", "vehicle_dealer", "storage_facility"):
        raise HTTPException(status_code=400, detail={
            "error": "incompatible_account_type",
            "message_en": "Partner accounts cannot also be brokers. Please contact support to convert your account.",
            "message_fr": "Les comptes partenaires ne peuvent pas être courtiers. Veuillez contacter le support.",
        })

    doc = make_broker_doc(user_id=current_user.id, payload=payload)
    await db.brokers.insert_one(doc)

    # Bind broker_id on the user record
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"broker_id": doc["id"], "account_type": "broker"}},
    )

    # Admin notification (best-effort)
    try:
        await db.admin_notifications.insert_one({
            "id":         doc["id"] + ":apply",
            "type":       "broker_application",
            "title":      f"New broker application — {doc['legal_business_name']}",
            "broker_id":  doc["id"],
            "user_id":    current_user.id,
            "created_at": _utcnow(),
            "read":       False,
        })
    except Exception as e:
        logger.warning("admin_notifications insert failed: %s", e)

    return {"success": True, "broker_id": doc["id"], "verification_status": doc["verification_status"]}


# ── 1b. Broker document upload (multipart, partner-style) ──────────────
@brokers_router.post("/brokers/upload-documents")
async def upload_broker_documents(
    license_document: Optional[UploadFile] = File(None),
    registration_document: Optional[UploadFile] = File(None),
    additional_documents: List[UploadFile] = File(default_factory=list),
    current_user: User = Depends(get_current_user),
):
    """Upload broker registration documents to S3 and return their URLs.

    The broker apply form calls this first to materialize URLs, then
    submits the apply payload with those URLs. Mirrors the partner
    upload UX (NEQ + certification files).
    """
    from services.s3_service import upload_broker_document

    out: Dict[str, Any] = {"license_document_url": None, "registration_document_url": None, "additional_documents": []}
    try:
        if license_document:
            out["license_document_url"] = await upload_broker_document(
                license_document, current_user.id, "license"
            )
        if registration_document:
            out["registration_document_url"] = await upload_broker_document(
                registration_document, current_user.id, "registration"
            )
        for i, f in enumerate(additional_documents or []):
            url = await upload_broker_document(f, current_user.id, f"extra-{i}")
            out["additional_documents"].append(url)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"error": "upload_failed", "message": str(ve)})
    except Exception as e:
        logger.error("broker upload failed: %s", e)
        raise HTTPException(status_code=502, detail={"error": "s3_upload_failed"})

    # Persist on broker doc if one exists (post-apply re-upload supported)
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if broker:
        update: Dict[str, Any] = {"updated_at": _utcnow()}
        if out["license_document_url"]:      update["license_document_url"]      = out["license_document_url"]
        if out["registration_document_url"]: update["registration_document_url"] = out["registration_document_url"]
        if out["additional_documents"]:
            await db.brokers.update_one(
                {"id": broker["id"]},
                {"$push": {"additional_documents": {"$each": out["additional_documents"]}}, "$set": update},
            )
        else:
            await db.brokers.update_one({"id": broker["id"]}, {"$set": update})
    return out


# ── 1c. Broker subscription (yearly platform fee) ──────────────────────
def _resolve_subscription_pricing(broker_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the broker's effective subscription price + currency."""
    base     = float(broker_doc.get("subscription_base_cad", BROKER_SUBSCRIPTION_BASE_CAD))
    pct      = broker_doc.get("subscription_discount_pct")
    pct_val  = float(pct) if pct is not None else BROKER_SUBSCRIPTION_DISCOUNT_PCT
    pct_val  = max(0.0, min(100.0, pct_val))
    final    = round(base * (1.0 - pct_val / 100.0), 2)
    return {
        "base_cad":       round(base, 2),
        "discount_pct":   round(pct_val, 2),
        "final_cad":      final,
        "currency":       "CAD",
        "period_days":    BROKER_SUBSCRIPTION_PERIOD_DAYS,
        "status":         broker_doc.get("subscription_status") or "unpaid",
        "expires_at":     broker_doc.get("subscription_expires_at"),
        "promotion_note": "Launch promotion — 50% off. Admin can adjust per broker.",
    }


_GLOBAL_SETTINGS_DOC_ID = "broker_subscription_global"


async def _get_global_subscription_settings(db) -> Dict[str, Any]:
    """Effective global broker subscription settings (with built-in defaults)."""
    doc = await db.platform_settings.find_one({"id": _GLOBAL_SETTINGS_DOC_ID}, {"_id": 0})
    if not doc:
        doc = {}
    return {
        "id":                  _GLOBAL_SETTINGS_DOC_ID,
        "plan_name":           doc.get("plan_name", "BidVex Broker Annual Plan"),
        "base_cad":            float(doc.get("base_cad", BROKER_SUBSCRIPTION_BASE_CAD)),
        "currency":            doc.get("currency", "CAD"),
        "discount_active":     bool(doc.get("discount_active", True)),
        "discount_type":       doc.get("discount_type", "percentage"),         # percentage | fixed
        "discount_value":      float(doc.get("discount_value", BROKER_SUBSCRIPTION_DISCOUNT_PCT)),
        "discount_label":      doc.get("discount_label", "Launch Offer — 50% OFF"),
        "discount_starts_at":  doc.get("discount_starts_at"),
        "discount_ends_at":    doc.get("discount_ends_at"),
        "period_days":         int(doc.get("period_days", BROKER_SUBSCRIPTION_PERIOD_DAYS)),
        "auto_renew":          bool(doc.get("auto_renew", True)),
        "updated_at":          doc.get("updated_at"),
        "updated_by":          doc.get("updated_by"),
    }


def _compute_effective_price(base: float, discount_type: str, discount_value: float, discount_active: bool) -> Dict[str, float]:
    """Apply a global discount (percentage or fixed) to a base price."""
    base = max(0.0, float(base or 0.0))
    if not discount_active:
        return {"final_cad": round(base, 2), "discount_amount_cad": 0.0}
    val = max(0.0, float(discount_value or 0.0))
    if discount_type == "fixed":
        final = max(0.0, base - val)
        return {"final_cad": round(final, 2), "discount_amount_cad": round(min(base, val), 2)}
    # percentage (default)
    pct = max(0.0, min(100.0, val))
    final = round(base * (1.0 - pct / 100.0), 2)
    return {"final_cad": final, "discount_amount_cad": round(base - final, 2)}


@brokers_router.get("/brokers/me/subscription")
async def get_my_subscription(current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    # Merge per-broker overrides with global settings
    settings = await _get_global_subscription_settings(db)
    pricing  = _resolve_subscription_pricing(broker)
    pricing["plan_name"]      = settings["plan_name"]
    pricing["discount_label"] = settings["discount_label"]
    pricing["auto_renew"]     = bool(broker.get("subscription_auto_renew", settings["auto_renew"]))
    return pricing


class _SubscriptionOverrideIn(BaseModel):
    base_cad:        Optional[float] = None    # Override the $200 base
    discount_pct:    Optional[float] = None    # 0..100; 100 = free
    discount_fixed_cad: Optional[float] = None # Alt. discount type: fixed $ amount
    status:          Optional[Literal["unpaid", "active", "expired", "comp", "suspended", "free"]] = None
    expires_at:      Optional[datetime] = None
    extend_days:     Optional[int] = None      # Push expires_at forward N days from now
    note:            Optional[str] = None
    free_access:     Optional[bool] = None     # Shortcut: 100% discount + status="free"


@brokers_router.patch("/admin/brokers/{broker_id}/subscription")
async def admin_set_broker_subscription(
    broker_id: str,
    payload:   _SubscriptionOverrideIn,
    current_user: User = Depends(require_admin),
):
    """Admin per-broker subscription override.

    Use cases:
      • Promo accounts: discount_pct=100 → effective free
      • Custom enterprise pricing: base_cad=500
      • Comp / free access: free_access=true → 100% discount + status="free"
      • Suspend: status="suspended" (revokes access)
      • Reactivate: status="active"
      • Extend N days: extend_days=30 → push expires_at forward
      • Manual activation after wire transfer: status="active", expires_at=now+365d
    """
    db = get_db()
    if payload.base_cad is not None and payload.base_cad < 0:
        raise HTTPException(status_code=422, detail={"error": "negative_base"})
    if payload.discount_pct is not None and not (0.0 <= payload.discount_pct <= 100.0):
        raise HTTPException(status_code=422, detail={"error": "discount_pct_out_of_range_0_100"})
    if payload.discount_fixed_cad is not None and payload.discount_fixed_cad < 0:
        raise HTTPException(status_code=422, detail={"error": "negative_discount_fixed"})
    if payload.free_access and not (payload.note and payload.note.strip()):
        raise HTTPException(status_code=422, detail={"error": "admin_note_required_for_free_access"})

    update: Dict[str, Any] = {"updated_at": _utcnow()}
    if payload.base_cad           is not None: update["subscription_base_cad"]        = float(payload.base_cad)
    if payload.discount_pct       is not None: update["subscription_discount_pct"]    = float(payload.discount_pct)
    if payload.discount_fixed_cad is not None: update["subscription_discount_fixed_cad"] = float(payload.discount_fixed_cad)
    if payload.status             is not None: update["subscription_status"]          = payload.status
    if payload.expires_at         is not None: update["subscription_expires_at"]      = payload.expires_at
    if payload.note               is not None: update["subscription_note"]            = payload.note
    if payload.free_access is True:
        update["subscription_discount_pct"] = 100.0
        update["subscription_status"]       = "free"

    if payload.extend_days and payload.extend_days > 0:
        existing = await db.brokers.find_one({"id": broker_id}, {"_id": 0, "subscription_expires_at": 1})
        cur = (existing or {}).get("subscription_expires_at") or _utcnow()
        if isinstance(cur, str):
            try:
                cur = datetime.fromisoformat(cur.replace("Z", "+00:00"))
            except Exception:
                cur = _utcnow()
        from datetime import timedelta
        update["subscription_expires_at"] = cur + timedelta(days=int(payload.extend_days))

    update["subscription_updated_by"] = current_user.email
    update["subscription_updated_at"] = _utcnow()

    res = await db.brokers.update_one({"id": broker_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})

    # Audit log
    try:
        await db.broker_subscription_audit.insert_one({
            "id":           str(__import__("uuid").uuid4()),
            "broker_id":    broker_id,
            "admin_email":  current_user.email,
            "changes":      {k: v for k, v in update.items() if not k.startswith("subscription_updated")},
            "note":         payload.note,
            "at":           _utcnow(),
        })
    except Exception as e:
        logger.warning("broker_subscription_audit insert failed: %s", e)

    fresh = await db.brokers.find_one({"id": broker_id}, {"_id": 0})
    return {"success": True, "pricing": _resolve_subscription_pricing(fresh)}


@brokers_router.get("/brokers")
async def list_brokers_public(province: Optional[str] = None, limit: int = 50):
    """Public directory — approved brokers only."""
    db = get_db()
    query: Dict[str, Any] = {"verification_status": "approved"}
    if province:
        query["operating_province"] = province.strip().upper()
    rows: List[Dict[str, Any]] = []
    async for d in db.brokers.find(query, {"_id": 0}).limit(limit):
        # Mask the broker license number (last 4 visible)
        lic = d.get("broker_license_number") or ""
        d["broker_license_number_masked"] = ("•" * max(0, len(lic) - 4)) + lic[-4:] if lic else ""
        d.pop("broker_license_number", None)
        d.pop("license_document_url", None)
        d.pop("registration_document_url", None)
        d.pop("additional_documents", None)
        d.pop("verification_notes", None)
        rows.append(d)
    return {"data": rows, "count": len(rows)}


@brokers_router.get("/brokers/me")
async def get_my_broker(current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    return broker


@brokers_router.get("/brokers/{broker_id}")
async def get_broker_public(broker_id: str):
    db = get_db()
    d = await db.brokers.find_one({"id": broker_id, "verification_status": "approved"}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    lic = d.get("broker_license_number") or ""
    d["broker_license_number_masked"] = ("•" * max(0, len(lic) - 4)) + lic[-4:] if lic else ""
    d.pop("broker_license_number", None)
    return d


class _SettingsUpdate(BaseModel):
    fee_structure: Optional[BrokerFeeStructure] = None
    default_deposit_amount_cad: Optional[float] = None


@brokers_router.patch("/brokers/settings")
async def update_broker_settings(payload: _SettingsUpdate, current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1, "verification_status": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    update: Dict[str, Any] = {"updated_at": _utcnow()}
    if payload.fee_structure is not None:
        update["fee_structure"] = payload.fee_structure.dict()
    if payload.default_deposit_amount_cad is not None:
        if payload.default_deposit_amount_cad < 100:
            raise HTTPException(status_code=422, detail={"error": "deposit_min_100_cad"})
        update["default_deposit_amount_cad"] = float(payload.default_deposit_amount_cad)
    await db.brokers.update_one({"id": broker["id"]}, {"$set": update})
    return {"success": True}


# ── 2. Buyer ↔ broker relationships ────────────────────────────────────
@brokers_router.post("/broker-relationships/request")
async def request_broker_partnership(
    request: Request,
    payload: RelationshipRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db()

    # Broker must exist and be approved
    broker = await db.brokers.find_one({"id": payload.broker_id, "verification_status": "approved"}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found_or_not_approved"})

    # Buyer cannot bind to multiple brokers at once
    existing = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": {"$in": ["pending", "approved", "active"]}},
        {"_id": 0, "id": 1, "broker_id": 1, "status": 1},
    )
    if existing:
        raise HTTPException(status_code=400, detail={
            "error": "already_bound",
            "current_broker_id": existing["broker_id"],
            "current_status": existing["status"],
        })

    deposit_amount = float(broker.get("default_deposit_amount_cad") or DEFAULT_DEPOSIT_CAD)
    rel = make_relationship_doc(
        broker_id          = payload.broker_id,
        buyer_user_id      = current_user.id,
        deposit_amount_cad = deposit_amount,
    )
    await db.broker_buyer_relationships.insert_one(rel)

    # Authorize Stripe deposit hold (best-effort — if stripe fails we
    # leave deposit_status="pending" and the broker can retry).
    pi_data = None
    try:
        from services.broker_deposit_service import authorize_deposit
        pi_data = authorize_deposit(
            amount_cad        = deposit_amount,
            customer_email    = current_user.email,
            payment_method_id = payload.payment_method_id,
            relationship_id   = rel["id"],
            broker_id         = payload.broker_id,
            buyer_user_id     = current_user.id,
        )
        await db.broker_buyer_relationships.update_one(
            {"id": rel["id"]},
            {"$set": {
                "deposit_stripe_payment_intent_id": pi_data["payment_intent_id"],
                "deposit_status":                  "held" if pi_data["status"] in ("requires_capture", "succeeded") else "pending",
                "deposit_held_at":                 _utcnow() if pi_data["status"] == "requires_capture" else None,
                "updated_at":                      _utcnow(),
            }},
        )
    except Exception as e:
        logger.warning("stripe deposit authorize failed for rel=%s: %s", rel["id"], e)

    return {
        "success":         True,
        "relationship_id": rel["id"],
        "deposit": (
            {
                "amount_cad":        deposit_amount,
                "payment_intent_id": pi_data["payment_intent_id"] if pi_data else None,
                "client_secret":     pi_data["client_secret"] if pi_data else None,
                "status":            pi_data["status"] if pi_data else "pending",
            }
        ),
    }


@brokers_router.get("/broker-relationships/my-broker")
async def get_my_broker_binding(current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": {"$in": ["pending", "approved", "active"]}},
        {"_id": 0},
    )
    if not rel:
        return {"data": None}
    broker = await db.brokers.find_one({"id": rel["broker_id"]}, {"_id": 0})
    return {"data": {"relationship": rel, "broker": _exclude_id(broker)}}


@brokers_router.get("/broker-relationships/my-buyers")
async def get_my_buyers(current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    rows: List[Dict[str, Any]] = []
    async for d in db.broker_buyer_relationships.find({"broker_id": broker["id"]}, {"_id": 0}):
        # Hydrate buyer email
        u = await db.users.find_one({"id": d["buyer_user_id"]}, {"_id": 0, "email": 1, "name": 1, "full_name": 1})
        d["buyer_email"]     = (u or {}).get("email")
        d["buyer_full_name"] = (u or {}).get("full_name") or (u or {}).get("name")
        rows.append(d)
    return {"data": rows, "count": len(rows)}


async def _require_broker_owns_relationship(db, rel_id: str, user_id: str) -> Dict[str, Any]:
    rel = await db.broker_buyer_relationships.find_one({"id": rel_id}, {"_id": 0})
    if not rel:
        raise HTTPException(status_code=404, detail={"error": "relationship_not_found"})
    broker = await db.brokers.find_one({"id": rel["broker_id"]}, {"_id": 0, "id": 1, "user_id": 1})
    if not broker or broker["user_id"] != user_id:
        raise HTTPException(status_code=403, detail={"error": "not_your_relationship"})
    return rel


@brokers_router.post("/broker-relationships/{rel_id}/approve")
async def approve_buyer(rel_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    if rel["status"] not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail={"error": "invalid_state", "current_status": rel["status"]})
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"status": "active", "can_bid": True, "updated_at": _utcnow()}},
    )
    await db.users.update_one(
        {"id": rel["buyer_user_id"]},
        {"$set": {"bound_broker_id": rel["broker_id"], "broker_binding_status": "active", "can_bid_on_vehicles": True}},
    )
    await db.brokers.update_one({"id": rel["broker_id"]}, {"$inc": {"total_buyers_managed": 1}})
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/reject")
async def reject_buyer(rel_id: str, reason: str = Body("", embed=True), current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    # Release the deposit hold
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    if pi_id:
        try:
            from services.broker_deposit_service import release_deposit
            release_deposit(pi_id)
        except Exception as e:
            logger.warning("release_deposit on reject failed: %s", e)
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {
            "status":              "rejected",
            "deposit_status":      "released",
            "deposit_released_at": _utcnow(),
            "updated_at":          _utcnow(),
            "rejection_reason":    reason,
        }},
    )
    return {"success": True}


@brokers_router.patch("/broker-relationships/{rel_id}/bid-limit")
async def set_bid_limit(rel_id: str, max_bid_amount_cad: float = Body(..., embed=True), current_user: User = Depends(get_current_user)):
    db = get_db()
    await _require_broker_owns_relationship(db, rel_id, current_user.id)
    if max_bid_amount_cad < 0:
        raise HTTPException(status_code=422, detail={"error": "negative_limit"})
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"max_bid_amount_cad": float(max_bid_amount_cad), "updated_at": _utcnow()}},
    )
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/release-deposit")
async def release_deposit_endpoint(rel_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    if not pi_id:
        raise HTTPException(status_code=400, detail={"error": "no_deposit_on_file"})
    try:
        from services.broker_deposit_service import release_deposit
        release_deposit(pi_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": "stripe_release_failed", "message": str(e)})
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"deposit_status": "released", "deposit_released_at": _utcnow(), "updated_at": _utcnow()}},
    )
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/terminate")
async def terminate_relationship(rel_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    rel = await _require_broker_owns_relationship(db, rel_id, current_user.id)
    # Release the deposit if still held
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    if pi_id and rel.get("deposit_status") == "held":
        try:
            from services.broker_deposit_service import release_deposit
            release_deposit(pi_id)
        except Exception as e:
            logger.warning("release on terminate failed: %s", e)
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"status": "terminated", "can_bid": False, "deposit_status": "released",
                  "deposit_released_at": _utcnow(), "updated_at": _utcnow()}},
    )
    await db.users.update_one(
        {"id": rel["buyer_user_id"]},
        {"$set": {"bound_broker_id": None, "broker_binding_status": "none", "can_bid_on_vehicles": False}},
    )
    return {"success": True}


@brokers_router.post("/broker-relationships/{rel_id}/suspend")
async def suspend_relationship(rel_id: str, reason: str = Body("", embed=True), current_user: User = Depends(get_current_user)):
    db = get_db()
    await _require_broker_owns_relationship(db, rel_id, current_user.id)
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"status": "suspended", "can_bid": False, "suspended_reason": reason, "updated_at": _utcnow()}},
    )
    return {"success": True}


# ── 3. Broker bidding ──────────────────────────────────────────────────
class _BrokerBidIn(BaseModel):
    bid_amount_cad: float = Field(..., gt=0)
    broker_confirmation: bool = False


@brokers_router.post("/vehicle-auctions/{listing_id}/bid-via-broker")
async def place_bid_via_broker(
    listing_id: str,
    request: Request,
    payload: _BrokerBidIn,
    current_user: User = Depends(get_current_user),
):
    db = get_db()

    # 1. Buyer must have an active broker relationship
    rel = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": "active", "can_bid": True},
        {"_id": 0},
    )
    if not rel:
        raise HTTPException(status_code=403, detail={
            "error": "no_active_broker",
            "message_en": "You must be connected to an approved broker to bid on vehicles in your province.",
            "message_fr": "Vous devez être connecté à un courtier approuvé pour enchérir sur des véhicules.",
        })

    # 2. Broker still approved?
    broker = await db.brokers.find_one(
        {"id": rel["broker_id"], "verification_status": "approved"},
        {"_id": 0},
    )
    if not broker:
        raise HTTPException(status_code=403, detail={
            "error": "broker_not_active",
            "message_en": "Your broker is no longer authorized to place bids on your behalf.",
            "message_fr": "Votre courtier n'est plus autorisé à enchérir en votre nom.",
        })

    # 3. Bid limit check
    if rel.get("max_bid_amount_cad") is not None:
        if payload.bid_amount_cad > rel["max_bid_amount_cad"]:
            raise HTTPException(status_code=400, detail={
                "error": "bid_exceeds_broker_limit",
                "max_bid_amount_cad": rel["max_bid_amount_cad"],
            })

    # 4. Intra-broker conflict
    conflict = await check_intra_broker_conflict(
        db,
        vehicle_listing_id = listing_id,
        broker_id          = rel["broker_id"],
        new_buyer_id       = current_user.id,
    )
    if conflict.conflict:
        raise HTTPException(status_code=409, detail={
            "error":            "intra_broker_conflict",
            "message_en":       conflict.message_en,
            "message_fr":       conflict.message_fr,
            "blocking_buyer_id": conflict.blocking_buyer_id,
        })

    # 5. Snapshot the auction state
    snapshot: Dict[str, Any] = {}
    try:
        listing = await db.vehicle_listings.find_one({"id": listing_id}, {"_id": 0, "current_bid": 1, "highest_bidder_id": 1, "bid_count": 1})
        if listing:
            snapshot = {
                "current_bid":       listing.get("current_bid"),
                "highest_bidder_id": listing.get("highest_bidder_id"),
                "bid_count":         listing.get("bid_count"),
            }
    except Exception:
        pass

    # 6. Write immutable audit row
    bid_doc = make_broker_bid_doc(
        vehicle_listing_id          = listing_id,
        broker_id                   = rel["broker_id"],
        broker_license_number       = broker["broker_license_number"],
        broker_legal_business_name  = broker["legal_business_name"],
        buyer_user_id               = current_user.id,
        bid_amount_cad              = payload.bid_amount_cad,
        ip_address                  = request.client.host if request.client else None,
        user_agent                  = request.headers.get("user-agent"),
        session_id                  = request.headers.get("x-session-id"),
        auction_state_snapshot      = snapshot,
    )
    await db.broker_bids.insert_one(bid_doc)

    # 7. Outbid any previous broker bids on this listing
    await db.broker_bids.update_many(
        {"vehicle_listing_id": listing_id, "id": {"$ne": bid_doc["id"]}, "status": "placed"},
        {"$set": {"status": "outbid", "outbid_at": _utcnow()}},
    )

    # 8. Mirror into the standard vehicle bid stream (best-effort)
    try:
        await db.vehicle_listings.update_one(
            {"id": listing_id},
            {
                "$push": {"bids_via_broker": bid_doc["id"]},
                "$set": {
                    "current_bid":               payload.bid_amount_cad,
                    "highest_bidder_id":         current_user.id,
                    "highest_bidder_display":    broker["legal_business_name"],
                    "highest_bidder_via_broker": rel["broker_id"],
                    "updated_at":                _utcnow(),
                },
                "$inc": {"bid_count": 1},
            },
        )
    except Exception as e:
        logger.warning("vehicle_listings mirror failed for %s: %s", listing_id, e)

    return {
        "success":               True,
        "bid_id":                bid_doc["id"],
        "broker_display_name":   broker["legal_business_name"],
        "broker_license_number": broker["broker_license_number"],
    }


@brokers_router.get("/broker-bids/audit")
async def audit_broker_bids(
    broker_id:    Optional[str] = None,
    buyer_id:     Optional[str] = None,
    listing_id:   Optional[str] = None,
    limit:        int = 200,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    q: Dict[str, Any] = {}
    if broker_id:  q["broker_id"]         = broker_id
    if buyer_id:   q["buyer_user_id"]     = buyer_id
    if listing_id: q["vehicle_listing_id"] = listing_id
    rows = []
    async for d in db.broker_bids.find(q, {"_id": 0}).sort("placed_at", -1).limit(limit):
        rows.append(d)
    return {"data": rows, "count": len(rows)}


# ── 4. Admin ───────────────────────────────────────────────────────────
@brokers_router.get("/admin/brokers")
async def admin_list_brokers(
    status: Optional[str] = None,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    q: Dict[str, Any] = {}
    if status: q["verification_status"] = status
    rows = []
    async for d in db.brokers.find(q, {"_id": 0}).sort("created_at", -1):
        u = await db.users.find_one({"id": d["user_id"]}, {"_id": 0, "email": 1, "full_name": 1, "name": 1})
        d["user_email"] = (u or {}).get("email")
        d["user_name"]  = (u or {}).get("full_name") or (u or {}).get("name")
        rows.append(d)
    return {"data": rows, "count": len(rows)}


@brokers_router.patch("/admin/brokers/{broker_id}/approve")
async def admin_approve_broker(broker_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    res = await db.brokers.update_one(
        {"id": broker_id},
        {"$set": {
            "verification_status": "approved",
            "verified_at":         _utcnow(),
            "verified_by":         current_user.email,
            "updated_at":          _utcnow(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    return {"success": True}


@brokers_router.patch("/admin/brokers/{broker_id}/reject")
async def admin_reject_broker(broker_id: str, reason: str = Body("", embed=True), current_user: User = Depends(require_admin)):
    db = get_db()
    res = await db.brokers.update_one(
        {"id": broker_id},
        {"$set": {
            "verification_status": "rejected",
            "rejection_reason":    reason,
            "verified_by":         current_user.email,
            "updated_at":          _utcnow(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    return {"success": True}


@brokers_router.patch("/admin/brokers/{broker_id}/suspend")
async def admin_suspend_broker(broker_id: str, reason: str = Body("", embed=True), current_user: User = Depends(require_admin)):
    db = get_db()
    res = await db.brokers.update_one(
        {"id": broker_id},
        {"$set": {
            "verification_status": "suspended",
            "suspended_at":        _utcnow(),
            "suspended_reason":    reason,
            "updated_at":          _utcnow(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    return {"success": True}


# ── 5. Fee preview endpoint (public, no auth) ──────────────────────────
@brokers_router.post("/brokers/{broker_id}/fee-preview")
async def fee_preview(broker_id: str, hammer_price: float = Body(..., embed=True), buyer_province: Optional[str] = Body(None, embed=True)):
    db = get_db()
    broker = await db.brokers.find_one({"id": broker_id, "verification_status": "approved"}, {"_id": 0, "fee_structure": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    bd = calculate_broker_transaction(
        hammer_price         = hammer_price,
        broker_fee_structure = broker["fee_structure"],
        buyer_province       = buyer_province,
    )
    return bd.as_dict()


# ── 6. Hotfix v6: Active Deals (live bid stream) ──────────────────────
@brokers_router.get("/broker-relationships/active-deals")
async def get_active_deals(current_user: User = Depends(get_current_user)):
    """Returns vehicle auctions every buyer-bound-to-this-broker is touching.
    Powers the broker dashboard "Active Deals" Kanban view.
    """
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    rows: List[Dict[str, Any]] = []
    async for bid in db.broker_bids.find({"broker_id": broker["id"]}, {"_id": 0}).sort("placed_at", -1).limit(200):
        listing = await db.vehicle_listings.find_one(
            {"id": bid["vehicle_listing_id"]},
            {"_id": 0, "id": 1, "make": 1, "model": 1, "year": 1, "title": 1,
             "current_bid": 1, "highest_bidder_id": 1, "auction_end_date": 1, "photos": 1, "status": 1},
        )
        buyer = await db.users.find_one({"id": bid["buyer_user_id"]}, {"_id": 0, "email": 1, "full_name": 1, "name": 1})
        if listing:
            # Determine column: winning|outbid|bidding|watching
            our_top = bid.get("status") == "placed" and listing.get("highest_bidder_id") == bid["buyer_user_id"]
            ended   = listing.get("status") in ("ended", "completed", "won", "sold")
            column = "won" if ended and our_top else (
                "winning" if our_top else
                "outbid"  if bid.get("status") == "outbid" else
                "bidding"
            )
            rows.append({
                "bid_id":              bid["id"],
                "vehicle_id":          listing["id"],
                "vehicle_label":       f"{listing.get('year','')} {listing.get('make','')} {listing.get('model','')}".strip() or listing.get("title", "Vehicle"),
                "photo":               (listing.get("photos") or [{}])[0].get("url") if listing.get("photos") else None,
                "buyer_email":         (buyer or {}).get("email"),
                "buyer_name":          (buyer or {}).get("full_name") or (buyer or {}).get("name"),
                "buyer_user_id":       bid["buyer_user_id"],
                "our_bid_amount_cad":  bid["bid_amount_cad"],
                "current_bid_cad":     listing.get("current_bid"),
                "auction_end_date":    listing.get("auction_end_date"),
                "status":              bid.get("status"),
                "column":              column,
            })
    return {"data": rows, "count": len(rows)}


# ── 7. Hotfix v6: Post-auction pipeline (invoices) ────────────────────
class _InvoiceCreateIn(BaseModel):
    vehicle_listing_id: str
    buyer_user_id:      str
    dealer_user_id:     str
    hammer_price_cad:   float
    buyer_province:     Optional[str] = "ON"


@brokers_router.post("/broker-invoices/generate")
async def generate_broker_invoice(payload: _InvoiceCreateIn, current_user: User = Depends(get_current_user)):
    from models.broker_models import make_invoice_doc
    import secrets

    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    # Idempotency: one invoice per (broker, vehicle, buyer)
    existing = await db.broker_invoices.find_one(
        {"broker_id": broker["id"], "vehicle_listing_id": payload.vehicle_listing_id, "buyer_user_id": payload.buyer_user_id},
        {"_id": 0},
    )
    if existing:
        return existing

    bd = calculate_broker_transaction(
        hammer_price         = payload.hammer_price_cad,
        broker_fee_structure = broker["fee_structure"],
        buyer_province       = payload.buyer_province,
    )
    pickup = secrets.token_hex(4).upper()
    doc = make_invoice_doc(
        vehicle_listing_id      = payload.vehicle_listing_id,
        broker_id               = broker["id"],
        buyer_user_id           = payload.buyer_user_id,
        dealer_user_id          = payload.dealer_user_id,
        hammer_price_cad        = bd.hammer_price_cad,
        bidvex_platform_fee_cad = bd.bidvex_platform_fee_cad,
        broker_fee_cad          = bd.broker_fee_cad,
        gst_cad                 = bd.gst_cad,
        qst_cad                 = bd.qst_cad,
        total_cad               = bd.total_cad,
        pickup_code             = pickup,
    )
    await db.broker_invoices.insert_one(doc)
    doc.pop("_id", None)
    return doc


@brokers_router.get("/broker-invoices")
async def list_broker_invoices(current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    rows = []
    async for d in db.broker_invoices.find({"broker_id": broker["id"]}, {"_id": 0}).sort("created_at", -1):
        rows.append(d)
    return {"data": rows, "count": len(rows)}


@brokers_router.patch("/broker-invoices/{invoice_id}/mark-paid")
async def mark_invoice_paid(invoice_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0, "broker_id": 1})
    if not inv or not broker or inv["broker_id"] != broker["id"]:
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"buyer_payment_status": "paid", "buyer_paid_at": _utcnow(), "vehicle_release_status": "ready"}},
    )
    return {"success": True}


@brokers_router.post("/broker-invoices/{invoice_id}/release-vehicle")
async def release_vehicle(invoice_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0, "broker_id": 1})
    if not inv or not broker or inv["broker_id"] != broker["id"]:
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"vehicle_release_status": "released", "released_at": _utcnow()}},
    )
    return {"success": True}


# ── 8. Hotfix v6: PDF invoice generator ───────────────────────────────
@brokers_router.get("/broker-invoices/{invoice_id}/pdf")
async def get_invoice_pdf(invoice_id: str, current_user: User = Depends(get_current_user)):
    from fastapi.responses import StreamingResponse
    import io
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    db = get_db()
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail={"error": "invoice_not_found"})
    broker = await db.brokers.find_one({"id": inv["broker_id"]}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    # Authorization: broker owner OR buyer themselves OR admin
    is_owner = broker.get("user_id") == current_user.id
    is_buyer = inv.get("buyer_user_id") == current_user.id
    is_admin = (current_user.role or "") in ("admin", "superadmin")
    if not (is_owner or is_buyer or is_admin):
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    w, h = LETTER

    y = h - 50
    c.setFont("Helvetica-Bold", 22); c.drawString(50, y, "BidVex × Broker Invoice")
    y -= 24
    c.setFont("Helvetica", 10);     c.drawString(50, y, f"Invoice #: {inv.get('invoice_number')}")
    y -= 14;                         c.drawString(50, y, f"Issued: {inv.get('created_at')}")
    y -= 28
    c.setFont("Helvetica-Bold", 12); c.drawString(50, y, "Broker")
    y -= 14
    c.setFont("Helvetica", 10);     c.drawString(50, y, broker.get("legal_business_name", ""))
    y -= 12;                         c.drawString(50, y, f"{broker.get('operating_province','')} · {broker.get('regulatory_body','')}")
    y -= 12;                         c.drawString(50, y, f"License: {broker.get('broker_license_number','')}")
    y -= 28
    c.setFont("Helvetica-Bold", 12); c.drawString(50, y, "Vehicle")
    y -= 14
    c.setFont("Helvetica", 10);     c.drawString(50, y, f"Listing ID: {inv.get('vehicle_listing_id')}")
    y -= 12;                         c.drawString(50, y, f"Pickup Code: {inv.get('pickup_code')}")
    y -= 28
    c.setFont("Helvetica-Bold", 12); c.drawString(50, y, "Price Breakdown")
    y -= 18

    def line(label, amount):
        nonlocal y
        c.setFont("Helvetica", 10)
        c.drawString(50, y, label)
        c.drawRightString(w - 50, y, f"${float(amount):,.2f} CAD")
        y -= 14

    line("Hammer Price",                inv.get("hammer_price_cad", 0))
    line("BidVex Platform Fee (2.5%)",  inv.get("bidvex_platform_fee_cad", 0))
    line("Broker Fee",                  inv.get("broker_fee_cad", 0))
    line("GST (5%)",                    inv.get("gst_cad", 0))
    if (inv.get("qst_cad") or 0) > 0:
        line("QST (9.975%)", inv.get("qst_cad", 0))
    y -= 6
    c.line(50, y, w - 50, y); y -= 14
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "TOTAL DUE")
    c.drawRightString(w - 50, y, f"${float(inv.get('total_cad', 0)):,.2f} CAD")

    y -= 40
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, y, f"This invoice is issued under {broker.get('regulatory_body','')} licensed broker permit.")
    c.drawString(50, y - 10, "Records retained for 7 years per Canadian business record law.")

    c.showPage()
    c.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="invoice-{inv.get("invoice_number")}.pdf"',
    })


# ── 9. Hotfix v6: Buyer invitation flow ───────────────────────────────
class _InviteBuyerIn(BaseModel):
    email: str


@brokers_router.post("/broker-relationships/invite")
async def invite_buyer(payload: _InviteBuyerIn, current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id, "verification_status": "approved"}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=403, detail={"error": "not_an_approved_broker"})
    invite_id = str(__import__("uuid").uuid4())
    doc = {
        "id":            invite_id,
        "broker_id":     broker["id"],
        "buyer_email":   payload.email.lower().strip(),
        "status":        "sent",
        "created_at":    _utcnow(),
        "accepted_at":   None,
    }
    await db.broker_invitations.insert_one(doc)
    # Email sending is best-effort: log it; queue actual email send for v6.5
    logger.info("BROKER_INVITE issued broker=%s email=%s id=%s", broker["id"], payload.email, invite_id)
    return {"success": True, "invite_id": invite_id, "join_url": f"/brokers/join?broker_id={broker['id']}&invite={invite_id}"}


# ── 10. Hotfix v6: Admin Buyer Deposits + Conflict Alerts + Audit ─────
@brokers_router.get("/admin/broker-deposits")
async def admin_list_broker_deposits(current_user: User = Depends(require_admin)):
    db = get_db()
    rows = []
    async for r in db.broker_buyer_relationships.find(
        {"deposit_status": {"$in": ["held", "captured"]}},
        {"_id": 0},
    ).sort("created_at", -1).limit(200):
        broker = await db.brokers.find_one({"id": r["broker_id"]}, {"_id": 0, "legal_business_name": 1})
        buyer  = await db.users.find_one({"id": r["buyer_user_id"]}, {"_id": 0, "email": 1, "full_name": 1})
        r["broker_name"] = (broker or {}).get("legal_business_name")
        r["buyer_email"] = (buyer or {}).get("email")
        rows.append(r)
    return {"data": rows, "count": len(rows)}


@brokers_router.get("/admin/broker-conflicts")
async def admin_list_broker_conflicts(current_user: User = Depends(require_admin), limit: int = 100):
    """All intra-broker conflict events surfaced as audit rows where a
    bid was attempted but blocked. We approximate via repeated-listing,
    same-broker, multiple-distinct-buyer entries.
    """
    db = get_db()
    pipeline = [
        {"$group": {
            "_id": {"listing": "$vehicle_listing_id", "broker": "$broker_id"},
            "buyer_ids": {"$addToSet": "$buyer_user_id"},
            "bid_count": {"$sum": 1},
        }},
        {"$match": {"$expr": {"$gt": [{"$size": "$buyer_ids"}, 1]}}},
        {"$limit": limit},
    ]
    rows = []
    async for row in db.broker_bids.aggregate(pipeline):
        rows.append({
            "vehicle_listing_id": row["_id"]["listing"],
            "broker_id":          row["_id"]["broker"],
            "distinct_buyers":    len(row["buyer_ids"]),
            "total_bids":         row["bid_count"],
            "buyer_ids":          row["buyer_ids"],
        })
    return {"data": rows, "count": len(rows)}


@brokers_router.get("/admin/broker-revenue")
async def admin_broker_revenue(current_user: User = Depends(require_admin)):
    """Sum platform fees collected from broker-mediated transactions."""
    db = get_db()
    pipeline = [
        {"$group": {
            "_id":               None,
            "total_platform":    {"$sum": "$bidvex_platform_fee_cad"},
            "total_broker_fees": {"$sum": "$broker_fee_cad"},
            "total_hammer":      {"$sum": "$hammer_price_cad"},
            "deal_count":        {"$sum": 1},
        }},
    ]
    agg = None
    async for row in db.broker_invoices.aggregate(pipeline):
        agg = row
    if not agg:
        return {"deal_count": 0, "total_platform_fee_cad": 0, "total_broker_fees_cad": 0, "total_hammer_cad": 0}
    return {
        "deal_count":             agg.get("deal_count", 0),
        "total_platform_fee_cad": round(agg.get("total_platform", 0), 2),
        "total_broker_fees_cad":  round(agg.get("total_broker_fees", 0), 2),
        "total_hammer_cad":       round(agg.get("total_hammer", 0), 2),
    }


# ── 11. Subscription Management (Admin Panel /admin/subscriptions) ────
@brokers_router.get("/admin/subscriptions/settings")
async def admin_get_subscription_settings(current_user: User = Depends(require_admin)):
    """Effective global broker subscription settings."""
    db = get_db()
    return await _get_global_subscription_settings(db)


class _GlobalSettingsIn(BaseModel):
    plan_name:           Optional[str]   = None
    base_cad:            Optional[float] = None
    currency:            Optional[str]   = None
    discount_active:     Optional[bool]  = None
    discount_type:       Optional[Literal["percentage", "fixed"]] = None
    discount_value:      Optional[float] = None
    discount_label:      Optional[str]   = None
    discount_starts_at:  Optional[datetime] = None
    discount_ends_at:    Optional[datetime] = None
    period_days:         Optional[int]   = None
    auto_renew:          Optional[bool]  = None


@brokers_router.patch("/admin/subscriptions/settings")
async def admin_update_subscription_settings(
    payload: _GlobalSettingsIn,
    current_user: User = Depends(require_admin),
):
    """Update global broker subscription settings (idempotent upsert)."""
    db = get_db()
    if payload.base_cad is not None and payload.base_cad < 0:
        raise HTTPException(status_code=422, detail={"error": "negative_base"})
    if payload.discount_value is not None and payload.discount_value < 0:
        raise HTTPException(status_code=422, detail={"error": "negative_discount"})
    if payload.discount_type == "percentage" and payload.discount_value is not None and payload.discount_value > 100:
        raise HTTPException(status_code=422, detail={"error": "percentage_above_100"})
    if payload.period_days is not None and payload.period_days < 1:
        raise HTTPException(status_code=422, detail={"error": "period_days_must_be_positive"})

    update: Dict[str, Any] = {
        "id":         _GLOBAL_SETTINGS_DOC_ID,
        "updated_at": _utcnow(),
        "updated_by": current_user.email,
    }
    for k in ("plan_name", "base_cad", "currency", "discount_active",
              "discount_type", "discount_value", "discount_label",
              "discount_starts_at", "discount_ends_at", "period_days", "auto_renew"):
        v = getattr(payload, k)
        if v is not None:
            update[k] = v

    await db.platform_settings.update_one(
        {"id": _GLOBAL_SETTINGS_DOC_ID},
        {"$set": update},
        upsert=True,
    )
    return await _get_global_subscription_settings(db)


@brokers_router.get("/admin/subscriptions/list")
async def admin_list_subscriptions(
    status_filter: Optional[Literal["active", "expired", "free", "suspended", "unpaid", "comp"]] = Query(None, alias="status"),
    search: Optional[str] = None,
    limit:  int = 200,
    current_user: User = Depends(require_admin),
):
    """All broker subscriptions with hydrated user info.

    Filter by `status` (active|expired|free|suspended|unpaid|comp).
    Search by broker name or user email.
    """
    db = get_db()
    settings = await _get_global_subscription_settings(db)
    q: Dict[str, Any] = {}
    if status_filter:
        q["subscription_status"] = status_filter

    rows: List[Dict[str, Any]] = []
    async for b in db.brokers.find(q, {"_id": 0}).sort("created_at", -1).limit(limit):
        u = await db.users.find_one({"id": b["user_id"]}, {"_id": 0, "email": 1, "full_name": 1, "name": 1})
        email     = (u or {}).get("email") or ""
        full_name = (u or {}).get("full_name") or (u or {}).get("name") or ""

        # Search filter (case-insensitive substring on email + business name)
        if search:
            needle = search.lower()
            if needle not in email.lower() and needle not in (b.get("legal_business_name") or "").lower():
                continue

        pricing = _resolve_subscription_pricing(b)
        rows.append({
            "broker_id":             b["id"],
            "user_id":                b.get("user_id"),
            "user_email":            email,
            "user_name":             full_name,
            "legal_business_name":   b.get("legal_business_name"),
            "operating_province":    b.get("operating_province"),
            "plan_name":             settings["plan_name"],
            "subscription_status":   b.get("subscription_status") or "unpaid",
            "base_cad":              pricing["base_cad"],
            "discount_pct":          pricing["discount_pct"],
            "final_cad":             pricing["final_cad"],
            "subscription_started_at": b.get("subscription_started_at"),
            "subscription_expires_at": b.get("subscription_expires_at"),
            "subscription_note":     b.get("subscription_note"),
            "created_at":            b.get("created_at"),
        })
    return {"data": rows, "count": len(rows)}


@brokers_router.get("/admin/subscriptions/revenue")
async def admin_subscription_revenue(current_user: User = Depends(require_admin)):
    """Subscription revenue summary: MRR, ARR, active counts, lost-to-discount."""
    db = get_db()
    settings = await _get_global_subscription_settings(db)

    totals = {
        "total_brokers":        0,
        "active":               0,
        "expired":              0,
        "free":                 0,
        "suspended":            0,
        "unpaid":               0,
        "comp":                 0,
        "full_price_count":     0,
        "discounted_count":     0,
        "arr_cad":              0.0,   # Sum of final_cad over active subscribers
        "potential_arr_cad":    0.0,   # Sum of base_cad if no discounts existed
        "revenue_lost_cad":     0.0,   # potential - actual
    }
    async for b in db.brokers.find({}, {"_id": 0}):
        totals["total_brokers"] += 1
        status = (b.get("subscription_status") or "unpaid")
        if status in totals:
            totals[status] += 1
        pricing = _resolve_subscription_pricing(b)
        if status in ("active", "comp", "free"):
            totals["arr_cad"]           += pricing["final_cad"]
            totals["potential_arr_cad"] += pricing["base_cad"]
            if pricing["discount_pct"] > 0 or pricing["final_cad"] < pricing["base_cad"]:
                totals["discounted_count"] += 1
            else:
                totals["full_price_count"] += 1

    totals["arr_cad"]           = round(totals["arr_cad"], 2)
    totals["potential_arr_cad"] = round(totals["potential_arr_cad"], 2)
    totals["revenue_lost_cad"]  = round(totals["potential_arr_cad"] - totals["arr_cad"], 2)
    totals["mrr_cad"]           = round(totals["arr_cad"] / 12.0, 2)
    totals["currency"]          = settings["currency"]
    return totals


@brokers_router.get("/admin/subscriptions/audit/{broker_id}")
async def admin_get_subscription_audit(broker_id: str, current_user: User = Depends(require_admin)):
    """Audit log of admin overrides applied to a specific broker subscription."""
    db = get_db()
    rows: List[Dict[str, Any]] = []
    async for r in db.broker_subscription_audit.find({"broker_id": broker_id}, {"_id": 0}).sort("at", -1).limit(100):
        rows.append(r)
    return {"data": rows, "count": len(rows)}
