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

    # iter226 Task 1 — Promote any pending liability signature parked on
    # the user record onto the new broker doc + retag audit row.
    db_user = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "pending_broker_liability_signature": 1, "pending_broker_liability_signed_at": 1},
    ) or {}
    pending_sig = db_user.get("pending_broker_liability_signature")
    if pending_sig:
        doc["liability_agreement"]            = pending_sig
        doc["liability_agreement_signed"]     = True
        doc["liability_agreement_signed_at"]  = db_user.get("pending_broker_liability_signed_at") or pending_sig.get("signed_at")

    await db.brokers.insert_one(doc)

    # Backfill broker_id on the audit row(s) we wrote during the wizard
    if pending_sig:
        try:
            await db.broker_legal_audit.update_many(
                {"user_id": current_user.id, "broker_id": None},
                {"$set": {"broker_id": doc["id"], "stage": "promoted_to_broker"}},
            )
            await db.users.update_one(
                {"id": current_user.id},
                {"$unset": {"pending_broker_liability_signature": "", "pending_broker_liability_signed_at": ""}},
            )
        except Exception as e:
            logger.warning("pending liability promotion failed: %s", e)

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
        # iter217 Phase 5 Hotfix v7 — Trust score on every public card
        d["rating_avg"]              = float(d.get("rating_avg") or 0)
        d["rating_count"]            = int(d.get("rating_count") or 0)
        d["completed_transactions"]  = await db.broker_invoices.count_documents({
            "broker_id": d["id"], "released_at": {"$ne": None},
        })
        rows.append(d)
    return {"data": rows, "count": len(rows)}


@brokers_router.get("/brokers/me")
async def get_my_broker(current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    return broker


# ── iter227 Fix #3 — Live Broker Analytics (computed, not stored) ───────
@brokers_router.get("/brokers/me/analytics")
async def get_my_broker_analytics(current_user: User = Depends(get_current_user)):
    """Return REAL-TIME analytics for the authenticated broker.

    Replaces the stale `broker.total_buyers_managed` / `total_revenue_cad` /
    `total_deals_completed` counters with live aggregates from the actual
    `broker_buyer_relationships`, `broker_bids`, and `broker_invoices`
    collections.
    """
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    base_q = {"broker_id": broker["id"]}

    total_buyers      = await db.broker_buyer_relationships.count_documents(base_q)
    active_buyers     = await db.broker_buyer_relationships.count_documents({**base_q, "status": "active"})
    pending_requests  = await db.broker_buyer_relationships.count_documents({**base_q, "status": "pending"})
    terminated        = await db.broker_buyer_relationships.count_documents({**base_q, "status": "terminated"})
    rejected          = await db.broker_buyer_relationships.count_documents({**base_q, "status": "rejected"})
    suspended         = await db.broker_buyer_relationships.count_documents({**base_q, "status": "suspended"})

    total_bids        = await db.broker_bids.count_documents(base_q)
    deals_won         = await db.broker_invoices.count_documents({"broker_id": broker["id"]})
    deals_settled     = await db.broker_invoices.count_documents({
        "broker_id": broker["id"], "released_at": {"$ne": None},
    })

    revenue_pipeline = [
        {"$match": {"broker_id": broker["id"]}},
        {"$group": {"_id": None,
                    "total_revenue_cad":   {"$sum": {"$ifNull": ["$broker_fee_cad", 0]}},
                    "total_hammer_cad":    {"$sum": {"$ifNull": ["$hammer_price_cad", 0]}},
                    "total_settled_cad":   {"$sum": {"$cond": [{"$ne": ["$released_at", None]},
                                                               {"$ifNull": ["$broker_fee_cad", 0]}, 0]}}}},
    ]
    revenue_doc = None
    async for d in db.broker_invoices.aggregate(revenue_pipeline):
        revenue_doc = d
        break
    total_revenue_cad   = float((revenue_doc or {}).get("total_revenue_cad", 0))
    total_hammer_cad    = float((revenue_doc or {}).get("total_hammer_cad", 0))
    settled_revenue_cad = float((revenue_doc or {}).get("total_settled_cad", 0))

    last_bid = None
    async for b in db.broker_bids.find(base_q, {"_id": 0, "placed_at": 1}).sort("placed_at", -1).limit(1):
        last_bid = b.get("placed_at")
    last_invoice = None
    async for inv in db.broker_invoices.find({"broker_id": broker["id"]}, {"_id": 0, "created_at": 1}).sort("created_at", -1).limit(1):
        last_invoice = inv.get("created_at")

    return {
        "broker_id":           broker["id"],
        "total_buyers":        total_buyers,
        "active_buyers":       active_buyers,
        "pending_requests":    pending_requests,
        "terminated_buyers":   terminated,
        "rejected_buyers":     rejected,
        "suspended_buyers":    suspended,
        "deals_won":           deals_won,
        "deals_settled":       deals_settled,
        "total_bids":          total_bids,
        "total_revenue_cad":   total_revenue_cad,
        "settled_revenue_cad": settled_revenue_cad,
        "total_hammer_cad":    total_hammer_cad,
        "last_bid_at":         last_bid,
        "last_invoice_at":     last_invoice,
        "computed_at":         _utcnow(),
    }



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


# ── iter228 — Full "My Active Broker" panel data ────────────────────────
@brokers_router.get("/broker-relationships/my-active-broker")
async def get_my_active_broker_full(current_user: User = Depends(get_current_user)):
    """Comprehensive buyer-side view of an active broker partnership.

    Returns everything the buyer-side `My Active Broker` panel needs in
    one round-trip: relationship + broker (jurisdiction, license, fee
    structure, signed terms snapshot) + live activity (active bids,
    upcoming lots, purchases) + termination eligibility gate.
    """
    db = get_db()
    rel = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": {"$in": ["pending", "approved", "active"]}},
        {"_id": 0},
    )
    if not rel:
        return {"data": None}

    broker = await db.brokers.find_one({"id": rel["broker_id"]}, {"_id": 0}) or {}
    # Mask + project safe broker fields for buyer consumption
    safe_broker = {
        "id":                      broker.get("id"),
        "legal_business_name":     broker.get("legal_business_name"),
        "operating_province":      broker.get("operating_province"),
        "regulatory_body":         broker.get("regulatory_body"),
        "broker_license_number":   broker.get("broker_license_number"),
        "corporate_registration_number": broker.get("corporate_registration_number"),
        "verification_status":     broker.get("verification_status"),
        "verified_at":             broker.get("verified_at"),
        "created_at":              broker.get("created_at"),
        "fee_structure":           broker.get("fee_structure"),
        "qc_anq_number":           broker.get("qc_anq_number"),
        "qc_opc_number":           broker.get("qc_opc_number"),
        "on_omvic_number":         broker.get("on_omvic_number"),
        "bc_vsa_number":           broker.get("bc_vsa_number"),
        "ab_amvic_number":         broker.get("ab_amvic_number"),
        "rating_avg":              float(broker.get("rating_avg") or 0),
        "rating_count":            int(broker.get("rating_count") or 0),
        "custom_terms_html":       broker.get("custom_terms_html") or "",
        "custom_terms_plain":      broker.get("custom_terms_plain") or "",
        "custom_terms_enabled":    bool(broker.get("custom_terms_enabled", False)),
        "custom_terms_updated_at": broker.get("custom_terms_updated_at"),
    }

    # Live active bids — broker_bids placed for THIS buyer that are still
    # winning/placed on listings not yet ended.
    active_bids: List[Dict[str, Any]] = []
    async for bid in db.broker_bids.find(
        {"broker_id": broker.get("id"), "buyer_user_id": current_user.id,
         "status": {"$in": ["placed", "winning", "won"]}},
        {"_id": 0},
    ).sort("placed_at", -1).limit(50):
        listing = await db.vehicle_listings.find_one(
            {"id": bid.get("vehicle_listing_id")},
            {"_id": 0, "id": 1, "title": 1, "make": 1, "model": 1, "year": 1,
             "current_bid": 1, "highest_bidder_id": 1, "ends_at": 1, "status": 1,
             "vin": 1, "images": 1},
        ) or {}
        if (listing.get("status") or "").lower() in ("ended", "completed", "won", "sold", "closed"):
            continue
        active_bids.append({
            "bid_id":            bid.get("id"),
            "vehicle_listing_id": bid.get("vehicle_listing_id"),
            "bid_amount_cad":    float(bid.get("bid_amount_cad") or 0),
            "placed_at":         bid.get("placed_at"),
            "status":            bid.get("status"),
            "listing": {
                "id":            listing.get("id"),
                "title":         listing.get("title") or f"{listing.get('year', '')} {listing.get('make', '')} {listing.get('model', '')}".strip(),
                "current_bid":   float(listing.get("current_bid") or 0),
                "ends_at":       listing.get("ends_at"),
                "image":         (listing.get("images") or [None])[0],
                "we_are_top":    listing.get("highest_bidder_id") == current_user.id,
            },
        })

    # Purchased inventory — broker_invoices for this buyer
    purchases: List[Dict[str, Any]] = []
    async for inv in db.broker_invoices.find(
        {"broker_id": broker.get("id"), "buyer_user_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1):
        listing = await db.vehicle_listings.find_one(
            {"id": inv.get("vehicle_listing_id")},
            {"_id": 0, "title": 1, "make": 1, "model": 1, "year": 1, "vin": 1, "images": 1},
        ) or {}
        purchases.append({
            "invoice_id":         inv.get("id"),
            "invoice_number":     inv.get("invoice_number"),
            "vehicle_listing_id": inv.get("vehicle_listing_id"),
            "vin":                listing.get("vin"),
            "vehicle_title":      listing.get("title") or f"{listing.get('year', '')} {listing.get('make', '')} {listing.get('model', '')}".strip(),
            "image":              (listing.get("images") or [None])[0],
            "hammer_price_cad":   float(inv.get("hammer_price_cad") or 0),
            "broker_fee_cad":     float(inv.get("broker_fee_cad") or 0),
            "total_cad":          float(inv.get("total_cad") or 0),
            "payment_status":     "paid" if inv.get("hammer_payment_confirmed_at") else "pending",
            "released":           bool(inv.get("released_at")),
            "released_at":        inv.get("released_at"),
            "created_at":         inv.get("created_at"),
        })

    # Termination eligibility gate
    blocking_bids   = sum(1 for b in active_bids)
    pending_invoices = await db.broker_invoices.count_documents({
        "broker_id":     broker.get("id"),
        "buyer_user_id": current_user.id,
        "hammer_payment_confirmed_at": None,
    })
    can_terminate = blocking_bids == 0 and pending_invoices == 0
    block_reasons = []
    if blocking_bids:
        block_reasons.append({"code": "active_bids",     "count": blocking_bids})
    if pending_invoices:
        block_reasons.append({"code": "pending_invoices", "count": pending_invoices})

    return {
        "data": {
            "relationship": rel,
            "broker":       safe_broker,
            "active_bids":  active_bids,
            "purchases":    purchases,
            "termination": {
                "can_terminate":   can_terminate,
                "block_reasons":   block_reasons,
                "active_bid_count": blocking_bids,
                "pending_invoice_count": pending_invoices,
            },
        }
    }


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


# ── iter225 Task 1 — Buyer Reconciliation Ledger ──────────────────────
@brokers_router.get("/broker-relationships/buyer-ledger")
async def broker_buyer_ledger(current_user: User = Depends(get_current_user)):
    """Per-buyer reconciliation matrix.

    For each managed buyer, returns Active / Won / Lost auction counts
    based on the broker_bids audit trail joined with vehicle_listings
    status. Drives the Reconciliation tab on the Broker Dashboard.
    """
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})

    # Hydrate the buyer roster from approved/active relationships first
    rels: List[Dict[str, Any]] = []
    async for r in db.broker_buyer_relationships.find(
        {"broker_id": broker["id"]},
        {"_id": 0, "id": 1, "buyer_user_id": 1, "status": 1, "deposit_status": 1,
         "created_at": 1, "max_bid_amount_cad": 1, "custom_terms_accepted_at": 1},
    ):
        rels.append(r)

    rows: List[Dict[str, Any]] = []
    for rel in rels:
        buyer_id = rel["buyer_user_id"]
        # Pull buyer profile
        u = await db.users.find_one(
            {"id": buyer_id},
            {"_id": 0, "email": 1, "full_name": 1, "name": 1, "province": 1},
        ) or {}

        # Walk every bid this buyer placed UNDER THIS BROKER
        active = won = lost = 0
        total_bid_amount = 0.0
        last_bid_at = None
        async for bid in db.broker_bids.find(
            {"broker_id": broker["id"], "buyer_user_id": buyer_id},
            {"_id": 0, "vehicle_listing_id": 1, "bid_amount_cad": 1, "status": 1, "placed_at": 1},
        ):
            total_bid_amount += float(bid.get("bid_amount_cad") or 0)
            if last_bid_at is None or (bid.get("placed_at") and bid["placed_at"] > last_bid_at):
                last_bid_at = bid.get("placed_at")
            listing = await db.vehicle_listings.find_one(
                {"id": bid["vehicle_listing_id"]},
                {"_id": 0, "status": 1, "highest_bidder_id": 1},
            ) or {}
            l_status = (listing.get("status") or "").lower()
            ended = l_status in ("ended", "completed", "won", "sold", "closed")
            our_top = listing.get("highest_bidder_id") == buyer_id and bid.get("status") in ("placed", "winning", "won")
            if not ended:
                active += 1
            else:
                if our_top:
                    won += 1
                else:
                    lost += 1

        rows.append({
            "relationship_id":         rel["id"],
            "buyer_user_id":           buyer_id,
            "buyer_email":             u.get("email"),
            "buyer_full_name":         u.get("full_name") or u.get("name"),
            "buyer_province":          u.get("province"),
            "status":                  rel.get("status"),
            "deposit_status":          rel.get("deposit_status"),
            "max_bid_amount_cad":      rel.get("max_bid_amount_cad"),
            "custom_terms_accepted_at": rel.get("custom_terms_accepted_at"),
            "since":                   rel.get("created_at"),
            "active_auctions":         active,
            "won_auctions":            won,
            "lost_auctions":           lost,
            "total_bid_count":         active + won + lost,
            "total_bid_amount_cad":    round(total_bid_amount, 2),
            "last_bid_at":             last_bid_at,
        })

    totals = {
        "buyers":        len(rows),
        "active":        sum(r["active_auctions"] for r in rows),
        "won":           sum(r["won_auctions"]    for r in rows),
        "lost":          sum(r["lost_auctions"]   for r in rows),
        "total_bid_cad": round(sum(r["total_bid_amount_cad"] for r in rows), 2),
    }
    return {"data": rows, "totals": totals, "count": len(rows)}


# ── iter229 — System-Proxy Bidding Compliance Gateway ──────────────────
@brokers_router.get("/broker-relationships/compliance-check")
async def broker_compliance_check(
    listing_id:   str,
    current_user: User = Depends(get_current_user),
):
    """Returns the proxy-bid eligibility verdict for a buyer × listing pair.

    Verdicts (status field):
      • eligible             — buyer can place a system-proxy bid right now
      • no_broker            — buyer is not bound to any broker
      • relationship_pending — broker hasn't approved the partnership yet
      • no_deposit           — $500 escrow not authorized
      • province_mismatch    — broker not licensed in the vehicle's province
      • not_a_vehicle        — listing doesn't require a broker (non-vehicle)
    """
    db = get_db()

    # iter286 — Bug 2 — Dual-collection lookup. Vehicle listings created
    # via the broker dealer wizard live in `db.vehicle_listings` (not in
    # `db.listings`). The single-collection query below previously 404'd
    # with `listing_not_found`, which rendered raw inside the bid panel.
    # Try the canonical marketplace collection first; if missing, fall
    # back to vehicle_listings and synthesize the minimum fields this
    # endpoint reads (`category`, `seller_province`, `requires_broker`).
    #
    # NOTE: explicit `is not None` check (NOT truthiness). When the doc
    # exists but none of the projected fields are set, the projection
    # returns an empty dict `{}` which is falsy — the previous truthiness
    # check silently fell through to the 404 branch.
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if listing is None:
        vlisting = await db.vehicle_listings.find_one(
            {"id": listing_id},
            {"_id": 0, "category_id": 1, "location_province": 1, "seller_province": 1},
        )
        if vlisting is not None:
            listing = {
                "category":         "vehicle",
                "requires_broker":  True,
                "seller_province":  (vlisting.get("location_province")
                                     or vlisting.get("seller_province")
                                     or ""),
                "province":         (vlisting.get("location_province") or ""),
            }
    if listing is None:
        raise HTTPException(status_code=404, detail={"error": "listing_not_found"})

    cat = (listing.get("category") or "").lower()
    vehicle_cats = ("vehicle", "car", "auto", "truck", "motorcycle", "suv", "van", "rv")
    is_vehicle = bool(listing.get("requires_broker")) or any(v in cat for v in vehicle_cats)
    if not is_vehicle:
        return {"status": "not_a_vehicle"}

    listing_province = (listing.get("seller_province") or listing.get("province") or "").upper() or None

    rel = await db.broker_buyer_relationships.find_one(
        {"buyer_user_id": current_user.id, "status": {"$in": ["pending", "approved", "active"]}},
        {"_id": 0},
    )
    if not rel:
        return {"status": "no_broker"}
    if rel.get("status") in ("pending", "approved"):
        return {"status": "relationship_pending"}

    # Active — keep going
    if (rel.get("deposit_status") or "").lower() not in ("held", "captured", "succeeded", "authorized"):
        return {"status": "no_deposit"}

    broker = await db.brokers.find_one(
        {"id": rel["broker_id"], "verification_status": "approved"},
        {"_id": 0},
    )
    if not broker:
        return {"status": "no_broker"}

    broker_province = (broker.get("operating_province") or "").upper() or None
    if listing_province and broker_province and listing_province != broker_province:
        return {
            "status":           "province_mismatch",
            "broker_name":      broker.get("legal_business_name"),
            "broker_province":  broker_province,
            "listing_province": listing_province,
        }

    return {
        "status":                       "eligible",
        "relationship_id":              rel["id"],
        "broker_id":                    broker["id"],
        "broker_name":                  broker.get("legal_business_name"),
        "broker_license":               broker.get("broker_license_number"),
        "broker_registry":              broker.get("regulatory_body"),
        "broker_province":              broker_province,
        "listing_province":             listing_province,
        "bid_cap":                      rel.get("bid_cap"),
        "bid_cap_currency":             rel.get("bid_cap_currency", "CAD"),
        "max_bid_amount_cad":           rel.get("max_bid_amount_cad"),
        "proxy_bid_agreement_accepted": bool(rel.get("proxy_bid_agreement_accepted", False)),
        "proxy_bid_agreement_accepted_at": rel.get("proxy_bid_agreement_accepted_at"),
    }


@brokers_router.post("/broker-relationships/accept-proxy-agreement")
async def accept_proxy_agreement(
    request:      Request,
    current_user: User = Depends(get_current_user),
):
    """Buyer accepts the proxy-bidding legal rider — one-time per partnership."""
    db = get_db()
    now = _utcnow()
    result = await db.broker_buyer_relationships.update_one(
        {"buyer_user_id": current_user.id, "status": "active"},
        {"$set": {
            "proxy_bid_agreement_accepted":     True,
            "proxy_bid_agreement_accepted_at":  now,
            "proxy_bid_agreement_accepted_ip":  request.client.host if request.client else None,
            "proxy_bid_agreement_accepted_ua":  request.headers.get("user-agent"),
            "updated_at":                       now,
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=400, detail={
            "error":      "no_active_partnership",
            "message_en": "No active broker configuration found to accept rider agreements.",
            "message_fr": "Aucune configuration de courtier active trouvée pour accepter l'accord de procuration.",
        })
    try:
        await db.broker_legal_audit.insert_one({
            "id":      str(__import__("uuid").uuid4()),
            "user_id": current_user.id,
            "kind":    "proxy_bid_agreement_accepted",
            "details": {"signed_ip": request.client.host if request.client else None,
                        "signed_user_agent": request.headers.get("user-agent")},
            "at":      now,
        })
    except Exception as e:
        logger.warning("proxy-agreement audit failed (non-fatal): %s", e)
    return {"success": True, "accepted_at": now, "message": "Legal proxy rider recorded successfully."}


class _BidCapIn(BaseModel):
    bid_cap: Optional[float] = None  # None / null → no cap


@brokers_router.patch("/broker-relationships/{rel_id}/bid-cap")
async def set_relationship_bid_cap(
    rel_id:       str,
    payload:      _BidCapIn,
    current_user: User = Depends(get_current_user),
):
    """Buyer sets/updates the maximum bid cap for an active or pending relationship."""
    db = get_db()
    rel = await db.broker_buyer_relationships.find_one({"id": rel_id}, {"_id": 0})
    if not rel:
        raise HTTPException(status_code=404, detail={"error": "relationship_not_found"})
    if rel["buyer_user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail={"error": "not_your_relationship"})

    if payload.bid_cap is not None and payload.bid_cap <= 0:
        raise HTTPException(status_code=422, detail={"error": "bid_cap_must_be_positive_or_null"})

    now = _utcnow()
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {
            "bid_cap":           payload.bid_cap,
            "bid_cap_currency":  "CAD",
            "bid_cap_set_at":    now,
            "bid_cap_set_by":    "buyer",
            "updated_at":        now,
        }},
    )
    return {"success": True, "bid_cap": payload.bid_cap, "bid_cap_set_at": now}


# ── iter225 Task 3 — Broker Liability Agreement (digital signature) ───
class _LiabilitySignIn(BaseModel):
    signature_full_name: str
    accepted_section_1:  bool   # Liability Acceptance
    accepted_section_2:  bool   # Platform Immunity
    accepted_section_3:  bool   # Data / Audit Consent
    scrolled_to_bottom:  bool
    locale:              Optional[str] = "en"


@brokers_router.post("/brokers/sign-liability")
async def sign_broker_liability_agreement(
    payload: _LiabilitySignIn,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Sign the broker liability agreement.

    iter226 Task 1 — PERMISSIVE: any authenticated user can sign during
    the onboarding wizard, even before a broker record exists. The
    signature is always logged to `broker_legal_audit` keyed by user_id;
    if a broker record exists for this user, the signature is ALSO stamped
    onto the broker doc so the apply flow can pick it up.
    """
    db = get_db()

    # Validate gates BEFORE any role check so the wizard surfaces the
    # right error message regardless of broker state.
    if not (payload.accepted_section_1 and payload.accepted_section_2 and payload.accepted_section_3):
        raise HTTPException(status_code=400, detail={
            "error":      "all_three_sections_required",
            "message_en": "You must accept all three sections of the liability agreement.",
            "message_fr": "Vous devez accepter les trois sections de l'accord de responsabilité.",
        })
    if not payload.scrolled_to_bottom:
        raise HTTPException(status_code=400, detail={
            "error":      "scroll_required",
            "message_en": "You must scroll through the entire agreement before signing.",
            "message_fr": "Vous devez faire défiler l'intégralité de l'accord avant de signer.",
        })
    if not payload.signature_full_name.strip():
        raise HTTPException(status_code=422, detail={"error": "signature_required"})

    # Permissive — broker record is OPTIONAL. Wizard applicants don't
    # have one yet; existing brokers do.
    broker = await db.brokers.find_one(
        {"user_id": current_user.id},
        {"_id": 0, "id": 1, "legal_business_name": 1},
    )

    signature_doc = {
        "signature_full_name":  payload.signature_full_name.strip(),
        "accepted_section_1":   True,
        "accepted_section_2":   True,
        "accepted_section_3":   True,
        "scrolled_to_bottom":   True,
        "signed_at":            _utcnow(),
        "signed_ip":            request.client.host if request.client else None,
        "signed_user_agent":    request.headers.get("user-agent"),
        "locale":               payload.locale,
        "user_id":              current_user.id,
        "user_email":           current_user.email,
        "agreement_version":    "v1-iter225",
    }

    # If broker record already exists, stamp it.
    if broker:
        await db.brokers.update_one(
            {"id": broker["id"]},
            {"$set": {
                "liability_agreement":          signature_doc,
                "liability_agreement_signed":   True,
                "liability_agreement_signed_at": signature_doc["signed_at"],
                "updated_at":                   _utcnow(),
            }},
        )
    else:
        # Pending applicant — park the signature on the user record so
        # apply_to_become_broker can promote it onto the broker doc.
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "pending_broker_liability_signature":  signature_doc,
                "pending_broker_liability_signed_at": signature_doc["signed_at"],
            }},
        )

    # Audit log — always written, keyed by user_id and broker_id (if any).
    try:
        await db.broker_legal_audit.insert_one({
            "id":        str(__import__("uuid").uuid4()),
            "broker_id": broker["id"] if broker else None,
            "user_id":   current_user.id,
            "kind":      "liability_agreement",
            "stage":     "approved_broker" if broker else "pending_applicant",
            "details":   signature_doc,
            "at":        signature_doc["signed_at"],
        })
    except Exception as e:
        logger.warning("broker_legal_audit insert failed: %s", e)

    return {
        "success":   True,
        "signed_at": signature_doc["signed_at"],
        "stage":     "approved_broker" if broker else "pending_applicant",
    }


# ── iter225 Task 4 — Custom Broker-Buyer Contract Terms ────────────────
class _CustomTermsIn(BaseModel):
    custom_terms_html:   Optional[str] = None
    custom_terms_plain:  Optional[str] = None
    enabled:             bool = True


@brokers_router.patch("/brokers/custom-terms")
async def update_broker_custom_terms(payload: _CustomTermsIn, current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "not_a_broker"})
    # Strip leading/trailing whitespace; very large terms are capped at 50,000 chars
    html  = (payload.custom_terms_html  or "").strip()
    plain = (payload.custom_terms_plain or "").strip()
    if len(html) > 50000 or len(plain) > 50000:
        raise HTTPException(status_code=413, detail={"error": "terms_too_long_max_50000_chars"})
    await db.brokers.update_one(
        {"id": broker["id"]},
        {"$set": {
            "custom_terms_html":        html,
            "custom_terms_plain":       plain,
            "custom_terms_enabled":     bool(payload.enabled),
            "custom_terms_updated_at":  _utcnow(),
            "updated_at":               _utcnow(),
        }},
    )
    return {"success": True}


@brokers_router.get("/brokers/{broker_id}/custom-terms")
async def get_broker_custom_terms(broker_id: str):
    """Public — buyers fetching the contract before linking. Returns the
    broker's html/plain terms or empty strings if not configured."""
    db = get_db()
    b = await db.brokers.find_one(
        {"id": broker_id, "verification_status": "approved"},
        {"_id": 0, "id": 1, "legal_business_name": 1, "custom_terms_html": 1,
         "custom_terms_plain": 1, "custom_terms_enabled": 1, "custom_terms_updated_at": 1},
    )
    if not b:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    return {
        "broker_id":               b["id"],
        "broker_name":             b.get("legal_business_name"),
        "custom_terms_html":       b.get("custom_terms_html") or "",
        "custom_terms_plain":      b.get("custom_terms_plain") or "",
        "enabled":                 bool(b.get("custom_terms_enabled", False)),
        "custom_terms_updated_at": b.get("custom_terms_updated_at"),
    }


class _AcceptCustomTermsIn(BaseModel):
    accepted:        bool
    signature_text:  Optional[str] = None
    locale:          Optional[str] = "en"


@brokers_router.post("/broker-relationships/{rel_id}/accept-custom-terms")
async def accept_custom_terms(
    rel_id:       str,
    payload:      _AcceptCustomTermsIn,
    request:      Request,
    current_user: User = Depends(get_current_user),
):
    """Buyer endpoint — stores the buyer's acceptance of a broker's
    custom contract on the relationship doc. Required before any bid
    can be placed if the broker has `custom_terms_enabled=True`.
    """
    if not payload.accepted:
        raise HTTPException(status_code=400, detail={
            "error":      "acceptance_required",
            "message_en": "You must accept the broker's custom contract to proceed.",
            "message_fr": "Vous devez accepter le contrat personnalisé du courtier pour continuer.",
        })

    db = get_db()
    rel = await db.broker_buyer_relationships.find_one({"id": rel_id}, {"_id": 0})
    if not rel:
        raise HTTPException(status_code=404, detail={"error": "relationship_not_found"})
    if rel["buyer_user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail={"error": "not_your_relationship"})

    now = _utcnow()
    acceptance = {
        "accepted_at":       now,
        "signature_text":    (payload.signature_text or "").strip() or None,
        "accepted_ip":       request.client.host if request.client else None,
        "accepted_user_agent": request.headers.get("user-agent"),
        "locale":            payload.locale,
    }
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {
            "custom_terms_accepted_at": now,
            "custom_terms_acceptance":  acceptance,
            "updated_at":               now,
        }},
    )
    return {"success": True, "accepted_at": now}




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
    # iter225 Task 5 — auto refund/release the $500 escrow deposit
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    refund_result: Dict[str, Any] = {"action": "noop"}
    if pi_id:
        try:
            from services.broker_deposit_service import refund_or_release_deposit
            refund_result = refund_or_release_deposit(pi_id)
        except Exception as e:
            logger.warning("refund_or_release on reject failed: %s", e)
            refund_result = {"action": "error", "error": str(e)}
    deposit_status = "refunded" if refund_result.get("action") == "refunded" else "released"
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {
            "status":               "rejected",
            "deposit_status":       deposit_status,
            "deposit_released_at":  _utcnow(),
            "deposit_refund_result": refund_result,
            "updated_at":           _utcnow(),
            "rejection_reason":     reason,
        }},
    )
    return {"success": True, "refund": refund_result}


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
    # iter225 Task 5 — auto refund (if captured) or release (if still held) the $500 escrow
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    refund_result: Dict[str, Any] = {"action": "noop"}
    if pi_id and rel.get("deposit_status") in ("held", "captured", "pending"):
        try:
            from services.broker_deposit_service import refund_or_release_deposit
            refund_result = refund_or_release_deposit(pi_id)
        except Exception as e:
            logger.warning("refund_or_release on terminate failed: %s", e)
            refund_result = {"action": "error", "error": str(e)}
    deposit_status = "refunded" if refund_result.get("action") == "refunded" else "released"
    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {"status": "terminated", "can_bid": False, "deposit_status": deposit_status,
                  "deposit_released_at": _utcnow(), "deposit_refund_result": refund_result,
                  "updated_at": _utcnow()}},
    )
    await db.users.update_one(
        {"id": rel["buyer_user_id"]},
        {"$set": {"bound_broker_id": None, "broker_binding_status": "none", "can_bid_on_vehicles": False}},
    )
    return {"success": True, "refund": refund_result}



# ── iter228 — Buyer-initiated partnership termination ──────────────────
@brokers_router.post("/broker-relationships/{rel_id}/buyer-terminate")
async def buyer_terminate_relationship(
    rel_id:       str,
    current_user: User = Depends(get_current_user),
):
    """Buyer resigns from the broker partnership.

    Gate: refuses if any outstanding active broker_bids OR unsettled
    broker_invoices. On success: status='terminated', un-bind buyer,
    refund/release the $500 Stripe escrow, dispatch SendGrid emails to
    BOTH parties.
    """
    db = get_db()
    rel = await db.broker_buyer_relationships.find_one({"id": rel_id}, {"_id": 0})
    if not rel:
        raise HTTPException(status_code=404, detail={"error": "relationship_not_found"})
    if rel["buyer_user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail={"error": "not_your_relationship"})
    if rel.get("status") in ("terminated", "rejected"):
        raise HTTPException(status_code=400, detail={
            "error": "already_terminated", "current_status": rel.get("status"),
        })

    broker_id = rel["broker_id"]

    active_bid_count = 0
    async for bid in db.broker_bids.find(
        {"broker_id": broker_id, "buyer_user_id": current_user.id,
         "status": {"$in": ["placed", "winning", "won"]}},
        {"_id": 0, "vehicle_listing_id": 1, "status": 1},
    ):
        listing = await db.vehicle_listings.find_one(
            {"id": bid.get("vehicle_listing_id")},
            {"_id": 0, "status": 1},
        ) or {}
        if (listing.get("status") or "").lower() not in ("ended", "completed", "won", "sold", "closed"):
            active_bid_count += 1

    pending_invoice_count = await db.broker_invoices.count_documents({
        "broker_id":     broker_id,
        "buyer_user_id": current_user.id,
        "hammer_payment_confirmed_at": None,
    })

    if active_bid_count > 0 or pending_invoice_count > 0:
        raise HTTPException(status_code=409, detail={
            "error":      "cannot_terminate_with_open_obligations",
            "message_en": "Cannot terminate partnership while bids are active or invoices are pending settlement.",
            "message_fr": "Impossible de mettre fin au partenariat tant que des enchères sont actives ou que des factures sont en attente de règlement.",
            "active_bid_count":     active_bid_count,
            "pending_invoice_count": pending_invoice_count,
        })

    refund_result: Dict[str, Any] = {"action": "noop"}
    pi_id = rel.get("deposit_stripe_payment_intent_id")
    if pi_id and rel.get("deposit_status") in ("held", "captured", "pending"):
        try:
            from services.broker_deposit_service import refund_or_release_deposit
            refund_result = refund_or_release_deposit(pi_id)
        except Exception as e:
            logger.warning("buyer-terminate refund failed: %s", e)
            refund_result = {"action": "error", "error": str(e)}
    deposit_status = "refunded" if refund_result.get("action") == "refunded" else "released"

    await db.broker_buyer_relationships.update_one(
        {"id": rel_id},
        {"$set": {
            "status":                "terminated",
            "can_bid":               False,
            "deposit_status":        deposit_status,
            "deposit_released_at":   _utcnow(),
            "deposit_refund_result": refund_result,
            "terminated_at":         _utcnow(),
            "terminated_by":         "buyer",
            "updated_at":            _utcnow(),
        }},
    )
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"bound_broker_id": None, "broker_binding_status": "none", "can_bid_on_vehicles": False}},
    )

    try:
        await db.broker_legal_audit.insert_one({
            "id":        str(__import__("uuid").uuid4()),
            "broker_id": broker_id,
            "user_id":   current_user.id,
            "kind":      "buyer_terminated_partnership",
            "details":   {"relationship_id": rel_id, "refund_result": refund_result},
            "at":        _utcnow(),
        })
    except Exception as e:
        logger.warning("buyer-terminate audit insert failed: %s", e)

    broker_doc = await db.brokers.find_one({"id": broker_id}, {"_id": 0, "legal_business_name": 1, "user_id": 1}) or {}
    broker_user = await db.users.find_one({"id": broker_doc.get("user_id")}, {"_id": 0, "email": 1, "full_name": 1, "name": 1}) or {}
    broker_email = broker_user.get("email")
    broker_name  = broker_doc.get("legal_business_name") or "your brokerage"
    buyer_email  = current_user.email
    buyer_name   = getattr(current_user, "full_name", None) or buyer_email

    try:
        from services.emails._email_core import send_email
        if buyer_email:
            await send_email(
                buyer_email,
                f"Partnership with {broker_name} ended — $500 deposit refund initiated",
                f"""
                <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;color:#1e293b">
                  <h2 style="color:#1E3A8A;margin:0 0 12px">Partnership Terminated</h2>
                  <p>Hello {buyer_name},</p>
                  <p>You've successfully ended your broker partnership with <strong>{broker_name}</strong> on BidVex.</p>
                  <ul>
                    <li>Your $500 refundable deposit is being <strong>{deposit_status}</strong> via Stripe.</li>
                    <li>You are no longer able to place bids under this broker's licence.</li>
                    <li>You're free to partner with another broker at any time from <a href="https://bidvex.com/brokers">bidvex.com/brokers</a>.</li>
                  </ul>
                  <p style="color:#64748b;font-size:12px;margin-top:24px">If you didn't initiate this action, contact support@bidvex.com immediately.</p>
                </div>
                """,
            )
        if broker_email:
            await send_email(
                broker_email,
                f"Buyer {buyer_email} has ended their partnership with you",
                f"""
                <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;color:#1e293b">
                  <h2 style="color:#1E3A8A;margin:0 0 12px">Buyer Partnership Ended</h2>
                  <p>Hello,</p>
                  <p>Buyer <strong>{buyer_name}</strong> (<a href="mailto:{buyer_email}">{buyer_email}</a>) has formally ended their partnership with <strong>{broker_name}</strong>.</p>
                  <ul>
                    <li>No active bids or pending invoices remained when termination was approved.</li>
                    <li>The buyer's $500 deposit is being <strong>{deposit_status}</strong> via Stripe.</li>
                    <li>The relationship is now status <code>terminated</code> in your dashboard ledger.</li>
                  </ul>
                  <p style="color:#64748b;font-size:12px;margin-top:24px">View the full audit trail at <a href="https://bidvex.com/broker/dashboard">bidvex.com/broker/dashboard</a>.</p>
                </div>
                """,
            )
    except Exception as e:
        logger.warning("buyer-terminate emails failed (non-fatal): %s", e)

    return {
        "success":        True,
        "refund":         refund_result,
        "deposit_status": deposit_status,
        "message_en":     "Partnership terminated. Your $500 deposit refund has been initiated.",
        "message_fr":     "Partenariat résilié. Le remboursement de votre dépôt de 500 $ a été initié.",
    }


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

    # 2b. iter225 Task 4 — If broker has custom contract enabled, buyer must have accepted it
    if broker.get("custom_terms_enabled") and not rel.get("custom_terms_accepted_at"):
        raise HTTPException(status_code=403, detail={
            "error": "custom_terms_acceptance_required",
            "message_en": "You must review and accept your broker's custom contract before bidding.",
            "message_fr": "Vous devez consulter et accepter le contrat personnalisé de votre courtier avant d'enchérir.",
            "broker_id": broker["id"],
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
    broker_doc = await db.brokers.find_one({"id": broker_id}, {"_id": 0})
    if not broker_doc:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
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
    # iter308 — full notification loop (admin audit + email + push)
    await _notify_broker_decision(db, broker_doc, decision="approve", current_user=current_user)
    return {"success": True}


@brokers_router.patch("/admin/brokers/{broker_id}/reject")
async def admin_reject_broker(broker_id: str, reason: str = Body("", embed=True), current_user: User = Depends(require_admin)):
    db = get_db()
    broker_doc = await db.brokers.find_one({"id": broker_id}, {"_id": 0})
    if not broker_doc:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
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
    await _notify_broker_decision(db, broker_doc, decision="reject", current_user=current_user, rejection_reason=reason)
    return {"success": True}


async def _notify_broker_decision(db, broker_doc, *, decision, current_user, rejection_reason: str = ""):
    """iter308 — Centralized broker verify/reject notifier.

    Records admin audit log + sends bilingual email + push to the broker's
    underlying user. All best-effort; never raises.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)
    user_id = broker_doc.get("user_id")
    try:
        await db.admin_logs.insert_one({
            "id": __import__("uuid").uuid4().hex,
            "action": f"broker_{decision}d",
            "admin_id": current_user.id,
            "admin_email": current_user.email,
            "target_user_id": user_id,
            "details": {"broker_id": broker_doc.get("id"),
                         "business_name": broker_doc.get("legal_business_name") or broker_doc.get("business_name"),
                         "reason": rejection_reason} if decision == "reject" else
                        {"broker_id": broker_doc.get("id"),
                         "business_name": broker_doc.get("legal_business_name") or broker_doc.get("business_name")},
            "timestamp": _utcnow().isoformat() if hasattr(_utcnow(), "isoformat") else str(_utcnow()),
        })
    except Exception as e:
        _log.warning(f"[iter308] broker admin_logs insert failed: {e}")
    if not user_id:
        return
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1})
    if not user:
        return
    # Email
    try:
        fr = (user.get("preferred_language") or "").startswith("fr")
        if decision == "approve":
            subject = "Your broker account has been verified / Votre compte courtier a été vérifié"
            body = (
                f"<p>Hello {user.get('name','')},</p>"
                f"<p>Your broker application has been approved. You can now post broker listings "
                f"and accept bids on behalf of clients.</p>"
                f"<p><a href=\"https://bidvex.com/broker/dashboard\">Open your broker dashboard</a></p>"
                f"<hr><p>Bonjour {user.get('name','')},</p>"
                f"<p>Votre demande de courtier a été approuvée. Vous pouvez maintenant publier des "
                f"annonces de courtier et accepter des offres pour le compte de clients.</p>"
                f"<p><a href=\"https://bidvex.com/broker/dashboard\">Ouvrir le tableau de bord courtier</a></p>"
            )
        else:
            subject = "Your verification was not approved / Votre vérification n'a pas été approuvée"
            body = (
                f"<p>Hello {user.get('name','')},</p>"
                f"<p>Your broker application was not approved.</p>"
                f"<p><b>Reason:</b> {rejection_reason or 'Please contact support'}</p>"
                f"<p>To appeal or resubmit: <a href=\"mailto:support@bidvex.com\">support@bidvex.com</a></p>"
                f"<hr><p>Bonjour {user.get('name','')},</p>"
                f"<p>Votre demande de courtier n'a pas été approuvée.</p>"
                f"<p><b>Raison :</b> {rejection_reason or 'Veuillez contacter le support'}</p>"
                f"<p>Pour faire appel ou soumettre à nouveau : <a href=\"mailto:support@bidvex.com\">support@bidvex.com</a></p>"
            )
        from services.emails._email_core import send_email
        await send_email(to_email=user["email"], subject=subject, html_content=body)
    except Exception as e:
        _log.warning(f"[iter308] broker email failed: {e}")
    # Push
    try:
        from services.push_dispatcher import dispatch_push
        fr = (user.get("preferred_language") or "").startswith("fr")
        if decision == "approve":
            preview = ("Votre compte courtier a été vérifié — vous pouvez maintenant lister."
                       if fr else "Your broker account has been verified — you can now list.")
        else:
            preview = (f"Votre vérification n'a pas été approuvée. {rejection_reason or 'Voir email'}"
                       if fr else f"Your verification was not approved. {rejection_reason or 'See email'}")
        await dispatch_push(
            db, user_id=user_id, kind="new_message",
            sender_name="BidVex", preview=preview, url="/broker/dashboard",
        )
    except Exception as e:
        _log.warning(f"[iter308] broker push failed: {e}")


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


# ── iter226 Task 2 — Admin Broker Audit & Activity Tracking ────────────
@brokers_router.get("/admin/brokers/{broker_id}/relationships")
async def admin_get_broker_relationships(broker_id: str, current_user: User = Depends(require_admin)):
    """Admin compliance view — every buyer link on this broker license.

    Returns relationships enriched with:
      * Stripe escrow status ($500 hold / captured / refunded with the
        most recent refund_result blob if available).
      * Custom-terms acceptance timestamp + the EXACT signed HTML version
        of the broker's contract at acceptance time (or current if no
        snapshot was stored).
      * Buyer profile basics + bid count on this broker license.
    """
    db = get_db()
    broker = await db.brokers.find_one(
        {"id": broker_id},
        {"_id": 0, "id": 1, "legal_business_name": 1, "operating_province": 1,
         "verification_status": 1, "broker_license_number": 1,
         "custom_terms_html": 1, "custom_terms_plain": 1, "custom_terms_enabled": 1,
         "custom_terms_updated_at": 1},
    )
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})

    rels: List[Dict[str, Any]] = []
    async for r in db.broker_buyer_relationships.find({"broker_id": broker_id}, {"_id": 0}):
        buyer = await db.users.find_one(
            {"id": r["buyer_user_id"]},
            {"_id": 0, "email": 1, "full_name": 1, "name": 1, "province": 1, "phone": 1},
        ) or {}
        bid_count = await db.broker_bids.count_documents({
            "broker_id":     broker_id,
            "buyer_user_id": r["buyer_user_id"],
        })
        # Most recent refund result (if stored on rel) — surfaces Stripe action history.
        escrow = {
            "deposit_amount_cad":              r.get("deposit_amount_cad"),
            "deposit_status":                  r.get("deposit_status"),
            "deposit_stripe_payment_intent_id": r.get("deposit_stripe_payment_intent_id"),
            "deposit_held_at":                 r.get("deposit_held_at"),
            "deposit_released_at":             r.get("deposit_released_at"),
            "deposit_refund_result":           r.get("deposit_refund_result"),
        }
        # Custom terms snapshot — we serve the broker's current HTML
        # (acceptance time is stamped on the relationship).
        custom_terms_view = {
            "broker_enabled":             bool(broker.get("custom_terms_enabled", False)),
            "broker_terms_updated_at":    broker.get("custom_terms_updated_at"),
            "broker_terms_html":          broker.get("custom_terms_html") or "",
            "broker_terms_plain":         broker.get("custom_terms_plain") or "",
            "accepted_at":                r.get("custom_terms_accepted_at"),
            "acceptance":                 r.get("custom_terms_acceptance"),
        }
        rels.append({
            "relationship_id":           r["id"],
            "status":                    r.get("status"),
            "can_bid":                   r.get("can_bid"),
            "max_bid_amount_cad":        r.get("max_bid_amount_cad"),
            "buyer_user_id":             r["buyer_user_id"],
            "buyer_email":               buyer.get("email"),
            "buyer_full_name":           buyer.get("full_name") or buyer.get("name"),
            "buyer_province":            buyer.get("province"),
            "buyer_phone":               buyer.get("phone"),
            "bid_count":                 bid_count,
            "rejection_reason":          r.get("rejection_reason"),
            "suspended_reason":          r.get("suspended_reason"),
            "created_at":                r.get("created_at"),
            "updated_at":                r.get("updated_at"),
            "escrow":                    escrow,
            "custom_terms":              custom_terms_view,
        })

    # Aggregate counters
    counts = {
        "total":      len(rels),
        "active":     sum(1 for r in rels if r["status"] == "active"),
        "pending":    sum(1 for r in rels if r["status"] == "pending"),
        "terminated": sum(1 for r in rels if r["status"] == "terminated"),
        "rejected":   sum(1 for r in rels if r["status"] == "rejected"),
        "suspended":  sum(1 for r in rels if r["status"] == "suspended"),
        "deposits_held":     sum(1 for r in rels if r["escrow"].get("deposit_status") == "held"),
        "deposits_refunded": sum(1 for r in rels if r["escrow"].get("deposit_status") == "refunded"),
        "deposits_released": sum(1 for r in rels if r["escrow"].get("deposit_status") == "released"),
    }
    return {
        "broker": {
            "id":                  broker["id"],
            "legal_business_name": broker.get("legal_business_name"),
            "operating_province":  broker.get("operating_province"),
            "verification_status": broker.get("verification_status"),
            "broker_license_number": broker.get("broker_license_number"),
        },
        "relationships": rels,
        "counts":        counts,
        "count":         len(rels),
    }


@brokers_router.get("/admin/brokers/{broker_id}/activity-log")
async def admin_get_broker_activity_log(
    broker_id: str,
    limit:     int = Query(500, ge=1, le=2000),
    current_user: User = Depends(require_admin),
):
    """Admin platform footprint telemetry for a single broker.

    Aggregates events from 6 collections into a single sorted timeline:
      * broker_legal_audit          → liability + contract signatures
      * broker_bids                 → every bid placed under their licence
      * broker_buyer_relationships  → buyer link create/approve/terminate
      * broker_invoices             → invoice generated / paid / released
      * broker_subscription_audit   → admin subscription overrides
      * brokers                     → license / settings modifications (synthetic events)
    """
    db = get_db()
    broker = await db.brokers.find_one(
        {"id": broker_id},
        {"_id": 0, "id": 1, "user_id": 1, "legal_business_name": 1,
         "verification_status": 1, "created_at": 1, "verified_at": 1,
         "suspended_at": 1, "liability_agreement_signed_at": 1,
         "custom_terms_updated_at": 1, "subscription_status": 1,
         "subscription_expires_at": 1, "subscription_updated_at": 1, "updated_at": 1},
    )
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})

    events: List[Dict[str, Any]] = []

    def push(kind: str, at, **kwargs):
        if not at:
            return
        events.append({"kind": kind, "at": at, **kwargs})

    # Account lifecycle synthetics
    push("broker_application_submitted", broker.get("created_at"), severity="info",
         message="Broker application submitted.")
    if broker.get("verified_at"):
        push("broker_approved", broker.get("verified_at"), severity="ok",
             message="Broker approved by admin.")
    if broker.get("suspended_at"):
        push("broker_suspended", broker.get("suspended_at"), severity="warn",
             message="Broker suspended.")
    if broker.get("liability_agreement_signed_at"):
        push("liability_signed", broker.get("liability_agreement_signed_at"), severity="ok",
             message="3-tier liability agreement digitally signed.")
    if broker.get("custom_terms_updated_at"):
        push("custom_terms_updated", broker.get("custom_terms_updated_at"), severity="info",
             message="Custom broker-buyer contract updated.")

    # Legal audit rows (signatures + contract acceptances) — include broker AND user-keyed rows
    async for row in db.broker_legal_audit.find(
        {"$or": [{"broker_id": broker_id}, {"user_id": broker.get("user_id")}]},
        {"_id": 0},
    ).sort("at", -1).limit(limit):
        push(f"legal:{row.get('kind', 'unknown')}", row.get("at"),
             severity="ok",
             details={
                 "stage":                row.get("stage"),
                 "signature_full_name":  (row.get("details") or {}).get("signature_full_name"),
                 "signed_ip":            (row.get("details") or {}).get("signed_ip"),
                 "signed_user_agent":    (row.get("details") or {}).get("signed_user_agent"),
                 "agreement_version":    (row.get("details") or {}).get("agreement_version"),
                 "locale":               (row.get("details") or {}).get("locale"),
             },
             message="Legal signature recorded.")

    # Bids placed
    async for bid in db.broker_bids.find({"broker_id": broker_id}, {"_id": 0}).sort("placed_at", -1).limit(limit):
        push("bid_placed", bid.get("placed_at"),
             severity="info",
             details={
                 "vehicle_listing_id": bid.get("vehicle_listing_id"),
                 "buyer_user_id":      bid.get("buyer_user_id"),
                 "bid_amount_cad":     bid.get("bid_amount_cad"),
                 "status":             bid.get("status"),
                 "ip_address":         bid.get("ip_address"),
                 "user_agent":         bid.get("user_agent"),
             },
             message=f"Bid ${float(bid.get('bid_amount_cad') or 0):.2f} on listing {bid.get('vehicle_listing_id')}.")

    # Relationships — events on create, status change, escrow change
    async for r in db.broker_buyer_relationships.find({"broker_id": broker_id}, {"_id": 0}):
        push("relationship_created", r.get("created_at"),
             severity="info",
             details={"buyer_user_id": r.get("buyer_user_id"), "status": r.get("status"), "deposit_status": r.get("deposit_status")},
             message=f"Buyer linkage created (buyer {r.get('buyer_user_id')}).")
        if r.get("deposit_held_at"):
            push("deposit_held", r.get("deposit_held_at"),
                 severity="info",
                 details={"buyer_user_id": r.get("buyer_user_id"), "pi_id": r.get("deposit_stripe_payment_intent_id"), "amount_cad": r.get("deposit_amount_cad")},
                 message=f"$500 escrow held (PI {r.get('deposit_stripe_payment_intent_id')}).")
        if r.get("deposit_released_at"):
            push("deposit_released_or_refunded", r.get("deposit_released_at"),
                 severity="ok" if r.get("deposit_status") in ("refunded", "released") else "info",
                 details={"buyer_user_id": r.get("buyer_user_id"), "deposit_status": r.get("deposit_status"), "refund_result": r.get("deposit_refund_result")},
                 message=f"Escrow {r.get('deposit_status')}.")
        if r.get("custom_terms_accepted_at"):
            push("custom_terms_accepted", r.get("custom_terms_accepted_at"),
                 severity="ok",
                 details={"buyer_user_id": r.get("buyer_user_id"), "acceptance": r.get("custom_terms_acceptance")},
                 message=f"Buyer accepted custom broker contract.")

    # Invoices
    async for inv in db.broker_invoices.find({"broker_id": broker_id}, {"_id": 0}).sort("created_at", -1).limit(limit):
        push("invoice_generated", inv.get("created_at"),
             severity="info",
             details={"invoice_id": inv.get("id"), "buyer_user_id": inv.get("buyer_user_id"),
                      "hammer_price_cad": inv.get("hammer_price_cad"), "total_cad": inv.get("total_cad")},
             message=f"Invoice {inv.get('invoice_number')} generated.")
        if inv.get("hammer_payment_confirmed_at"):
            push("invoice_marked_paid", inv.get("hammer_payment_confirmed_at"),
                 severity="ok",
                 details={"invoice_id": inv.get("id"), "method": inv.get("hammer_payment_method")},
                 message=f"Invoice {inv.get('invoice_number')} marked paid.")
        if inv.get("released_at"):
            push("invoice_vehicle_released", inv.get("released_at"),
                 severity="ok",
                 details={"invoice_id": inv.get("id"), "pickup_code": inv.get("pickup_code")},
                 message=f"Vehicle released — invoice {inv.get('invoice_number')}.")

    # Subscription overrides by admin
    async for s in db.broker_subscription_audit.find({"broker_id": broker_id}, {"_id": 0}).sort("at", -1).limit(limit):
        push("subscription_override", s.get("at"),
             severity="warn",
             details={"admin_email": s.get("admin_email"), "changes": s.get("changes"), "note": s.get("note")},
             message="Admin updated subscription.")

    # Sort newest first; serializable timestamps
    def _ts(x):
        v = x.get("at")
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v) if v is not None else ""
    events.sort(key=_ts, reverse=True)
    events = events[:limit]
    # Normalize datetimes for JSON
    for e in events:
        v = e.get("at")
        if hasattr(v, "isoformat"):
            e["at"] = v

    return {
        "broker": {
            "id":                  broker["id"],
            "legal_business_name": broker.get("legal_business_name"),
            "verification_status": broker.get("verification_status"),
        },
        "events":  events,
        "count":   len(events),
    }



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
    return bd


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
        hammer_price_cad        = bd["hammer_price"],
        bidvex_platform_fee_cad = bd["platform_fee"],
        broker_fee_cad          = bd["broker_fee"],
        gst_cad                 = bd["gst"],
        qst_cad                 = bd["qst"],
        total_cad               = bd["stripe_total_charged"],
        pickup_code             = pickup,
        fee_breakdown           = bd,
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


class _MarkPaidIn(BaseModel):
    """Broker manual confirmation that they've received the hammer price
    DIRECTLY from the buyer (wire / certified cheque / trust account).
    BidVex Stripe never sees this money."""
    hammer_received_confirmed: bool
    payment_method:            Literal["wire", "certified_cheque", "trust_account", "other"] = "wire"
    proof_url:                 Optional[str] = None       # URL of uploaded proof (PDF/JPG/PNG)
    note:                      Optional[str] = None


@brokers_router.patch("/broker-invoices/{invoice_id}/mark-paid")
async def mark_invoice_paid(
    invoice_id:   str,
    payload:      _MarkPaidIn,
    current_user: User = Depends(get_current_user),
):
    """Broker confirms they've received the direct hammer payment.

    Legal note: this endpoint does NOT charge anything via Stripe — the
    hammer is settled outside the platform. The Stripe service-fee charge
    is a separate event (created at invoice generation and auto-confirmed
    by the webhook from `payment_intent.succeeded`).
    """
    if not payload.hammer_received_confirmed:
        raise HTTPException(
            status_code=400,
            detail={"error": "hammer_confirmation_required",
                    "message_en": "You must confirm receipt of the hammer payment before marking the invoice paid.",
                    "message_fr": "Vous devez confirmer la réception du paiement avant de marquer la facture payée."},
        )

    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0, "broker_id": 1, "id": 1})
    if not inv or not broker or inv["broker_id"] != broker["id"]:
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})

    now = _utcnow()
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "hammer_payment_received":     True,
            "hammer_payment_method":       payload.payment_method,
            "hammer_payment_confirmed_at": now,
            "hammer_payment_confirmed_by": current_user.id,
            "hammer_payment_proof_url":    payload.proof_url,
            "hammer_payment_note":         payload.note,
            "buyer_payment_status":        "paid",
            "buyer_paid_at":               now,
            "vehicle_release_status":      "ready",
        }},
    )
    # Audit trail
    try:
        await db.broker_invoice_audit.insert_one({
            "id":         str(__import__("uuid").uuid4()),
            "invoice_id": invoice_id,
            "actor_id":   current_user.id,
            "actor_email": current_user.email,
            "action":     "mark_paid",
            "details":    payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
            "at":         now,
        })
    except Exception as e:
        logger.warning("broker_invoice_audit insert failed: %s", e)

    # iter218 — Meta CAPI Purchase event fires the moment the broker confirms
    # service fees have settled. LEGAL: value = platform fee + broker fee only;
    # the vehicle hammer NEVER touches Meta. content_ids now carry the
    # canonical BIDVEX-VEH-<vehicle_id> token for catalog match.
    try:
        inv  = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
        buyer = await db.users.find_one({"id": inv.get("buyer_user_id")}, {"_id": 0}) if inv else None
        if inv:
            # Look up vehicle to get title + category for richer event data.
            vehicle_doc = None
            vid = inv.get("vehicle_id") or inv.get("listing_id")
            if vid:
                vehicle_doc = await db.vehicles.find_one({"id": vid}, {"_id": 0, "title": 1, "make": 1, "model": 1, "year": 1, "category_id": 1, "category": 1}) or \
                              await db.listings.find_one({"id": vid}, {"_id": 0, "title": 1, "category": 1, "listing_type": 1})
            from services.analytics_tracker import track_broker_purchase
            await track_broker_purchase(
                db=db,
                invoice_id=invoice_id,
                platform_fee=float(inv.get("bidvex_platform_fee_cad", 0)),
                broker_fee=float(inv.get("broker_fee_cad", 0)),
                buyer_user=buyer,
                listing_id=vid,
                listing_type="vehicle",
                listing_title=(vehicle_doc or {}).get("title") or
                              " ".join(filter(None, [
                                  str((vehicle_doc or {}).get("year") or ""),
                                  (vehicle_doc or {}).get("make") or "",
                                  (vehicle_doc or {}).get("model") or "",
                              ])).strip() or None,
                listing_category=(vehicle_doc or {}).get("category") or
                                 (vehicle_doc or {}).get("category_id") or "vehicle",
            )
    except Exception as e:
        logger.warning("meta_capi mark_paid emit failed: %s", e)

    return {"success": True}


@brokers_router.post("/broker-invoices/{invoice_id}/release-vehicle")
async def release_vehicle(invoice_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv or not broker or inv["broker_id"] != broker["id"]:
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})

    now = _utcnow()
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"vehicle_release_status": "released", "released_at": now}},
    )

    # v8.1 — Backfill a receipt_token for invoices created before v8.1
    # and queue a "vehicle released" email with the public receipt link.
    receipt_token = inv.get("receipt_token")
    if not receipt_token:
        import secrets, string
        _alphabet = string.ascii_letters + string.digits
        receipt_token = "".join(secrets.choice(_alphabet) for _ in range(12))
        await db.broker_invoices.update_one({"id": invoice_id}, {"$set": {"receipt_token": receipt_token}})

    try:
        await db.email_outbox.insert_one({
            "id":           str(__import__("uuid").uuid4()),
            "kind":         "vehicle_released_with_receipt",
            "to_user_id":   inv.get("buyer_user_id"),
            "context": {
                "invoice_id":     invoice_id,
                "invoice_number": inv.get("invoice_number"),
                "pickup_code":    inv.get("pickup_code"),
                "receipt_url":    f"/my-receipt/{invoice_id}?code={receipt_token}",
            },
            "queued_at":    now,
        })
    except Exception as e:
        logger.warning("vehicle_released email queue failed: %s", e)

    return {"success": True, "receipt_url": f"/my-receipt/{invoice_id}?code={receipt_token}"}


# ── 8. Hotfix v7: PDF invoice generator (bilingual, two-section legal) ─
@brokers_router.get("/broker-invoices/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id:   str,
    lang:         Optional[str] = Query("en", pattern="^(en|fr)$"),
    current_user: User = Depends(get_current_user),
):
    from fastapi.responses import StreamingResponse
    import io
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas

    db = get_db()
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail={"error": "invoice_not_found"})
    broker = await db.brokers.find_one({"id": inv["broker_id"]}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})
    is_owner = broker.get("user_id") == current_user.id
    is_buyer = inv.get("buyer_user_id") == current_user.id
    is_admin = (current_user.role or "") in ("admin", "superadmin")
    if not (is_owner or is_buyer or is_admin):
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})

    fr = (lang == "fr")
    # i18n strings
    t = {
        "title":          "FACTURE BIDVEX × COURTIER"          if fr else "BIDVEX × BROKER INVOICE",
        "invoice_no":     "Facture n°"                          if fr else "Invoice #",
        "issued":         "Émise le"                            if fr else "Issued",
        "broker":         "Courtier"                            if fr else "Broker",
        "license":        "Permis"                              if fr else "License #",
        "vehicle":        "Véhicule"                            if fr else "Vehicle",
        "listing_id":     "Identifiant"                         if fr else "Listing ID",
        "pickup":         "Code de retrait"                     if fr else "Pickup Code",
        "section_a":      "SECTION A — RÈGLEMENT DU VÉHICULE (Paiement direct)" if fr else "SECTION A — VEHICLE SETTLEMENT (Direct Payment)",
        "section_b":      "SECTION B — SERVICES DE PLATEFORME BIDVEX (Stripe)" if fr else "SECTION B — BIDVEX PLATFORM SERVICES (Stripe)",
        "hammer_label":   "Prix marteau de l'enchère"           if fr else "Auction Hammer Price",
        "hammer_warn":    ("⚠ IMPORTANT : Ce montant est réglé DIRECTEMENT entre l'acheteur et le courtier par "
                          "virement bancaire, chèque certifié ou compte en fiducie du courtier. "
                          "BidVex ne traite pas ce paiement.")
                         if fr else
                         ("⚠ IMPORTANT: This amount is settled DIRECTLY between the buyer and the broker "
                          "via bank wire, certified cheque, or the broker's licensed trust account. "
                          "BidVex does not process this payment."),
        "title_transfer": ("Le transfert de propriété du véhicule est effectué auprès de la SAAQ ou du registre "
                          "provincial applicable par le courtier licencié.")
                         if fr else
                         ("Vehicle title transfer handled at SAAQ / provincial registry by the licensed broker."),
        "platform_fee":   "Frais de plateforme BidVex (2,5 %)"  if fr else "BidVex Platform Fee (2.5%)",
        "broker_fee":     "Frais de service du courtier"        if fr else "Broker Service Fee",
        "subtotal":       "Sous-total"                          if fr else "Subtotal",
        "gst":            "TPS (5 %)"                            if fr else "GST (5%)",
        "qst":            "TVQ (9,975 %) [Québec seulement]"   if fr else "QST (9.975%) [QC only]",
        "stripe_fee":     "Frais de traitement Stripe"         if fr else "Stripe Processing Fee",
        "stripe_total":   "TOTAL FACTURÉ VIA STRIPE"            if fr else "TOTAL CHARGED VIA STRIPE",
        "deposit":        "Caution de sécurité (détenue)"      if fr else "Security Deposit (held)",
        "deposit_note":   "Libérée à la remise du véhicule"    if fr else "Released upon vehicle handoff",
        "broker_payout":  "Versement au courtier"              if fr else "Broker's Stripe payout",
        "bidvex_payout":  "Versement à BidVex (+ taxes remises à l'ARC et RQ)" if fr else "BidVex payout (+ taxes remitted to CRA and RQ)",
        "gst_reg":        "TPS / GST# 00000 00000 RT0001",
        "qst_reg":        "TVQ / QST# 0000000000 TQ0001",
        "footer_legal":   ("BidVex Inc., Sherbrooke, Québec, Canada. "
                          "BidVex est une plateforme de marché. Elle n'agit pas comme concessionnaire, "
                          "courtier ou intermédiaire financier dans les transactions de véhicules. "
                          "Dossiers conservés 7 ans conformément à la législation canadienne.")
                         if fr else
                         ("BidVex Inc., Sherbrooke, Quebec, Canada. "
                          "BidVex is a marketplace platform. It does not act as a dealer, broker, or "
                          "financial intermediary for vehicle transactions. "
                          "Records retained 7 years per Canadian business record law."),
    }

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    w, h = LETTER
    navy = HexColor("#1E3A8A")
    grey = HexColor("#6B7280")

    y = h - 50

    # ── Header
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, t["title"])
    y -= 22
    c.setFillColor(grey)
    c.setFont("Helvetica", 9)
    c.drawString(50, y, f'{t["invoice_no"]}: {inv.get("invoice_number","—")}  ·  {t["issued"]}: {str(inv.get("created_at","")).split(".")[0]}')
    y -= 8
    c.setStrokeColor(navy)
    c.setLineWidth(1.5); c.line(50, y, w - 50, y); y -= 16

    # ── Broker + Vehicle block
    c.setFillColor(navy); c.setFont("Helvetica-Bold", 11); c.drawString(50, y, t["broker"]); y -= 14
    c.setFillColor(HexColor("#1F2937"))
    c.setFont("Helvetica", 10)
    c.drawString(50, y, broker.get("legal_business_name", "")); y -= 12
    c.drawString(50, y, f'{broker.get("operating_province","")} · {broker.get("regulatory_body","")}'); y -= 12
    # Mask license # to last 4
    lic = (broker.get("broker_license_number") or "")
    lic_mask = ("•" * max(0, len(lic) - 3)) + lic[-3:] if len(lic) > 3 else lic
    c.drawString(50, y, f'{t["license"]}: {lic_mask}'); y -= 18

    c.setFillColor(navy); c.setFont("Helvetica-Bold", 11); c.drawString(50, y, t["vehicle"]); y -= 14
    c.setFillColor(HexColor("#1F2937")); c.setFont("Helvetica", 10)
    c.drawString(50, y, f'{t["listing_id"]}: {inv.get("vehicle_listing_id","—")}'); y -= 12
    c.drawString(50, y, f'{t["pickup"]}: {inv.get("pickup_code","—")}'); y -= 22

    # Helper for amount lines
    def amount_line(label, amount, bold=False, size=10):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.setFillColor(HexColor("#1F2937"))
        c.drawString(50, y, label)
        c.drawRightString(w - 50, y, f"${float(amount):,.2f} CAD")
        y -= 14

    # ── SECTION A — Vehicle Settlement (Direct)
    c.setFillColor(HexColor("#FEF3C7"))
    c.rect(48, y - 6, w - 96, 16, fill=1, stroke=0)
    c.setFillColor(HexColor("#92400E"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, t["section_a"])
    y -= 18
    c.setFillColor(HexColor("#1F2937"))
    amount_line(t["hammer_label"], inv.get("hammer_price_cad", 0), bold=True, size=11)
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(HexColor("#92400E"))
    # Wrap hammer_warn
    from reportlab.lib.utils import simpleSplit
    for ln in simpleSplit(t["hammer_warn"], "Helvetica-Oblique", 9, w - 110):
        c.drawString(50, y, ln); y -= 11
    y -= 4
    c.setFillColor(grey); c.setFont("Helvetica", 8)
    for ln in simpleSplit(t["title_transfer"], "Helvetica", 8, w - 110):
        c.drawString(50, y, ln); y -= 10
    y -= 10

    # ── SECTION B — BidVex Platform Services (Stripe)
    c.setFillColor(HexColor("#DBEAFE"))
    c.rect(48, y - 6, w - 96, 16, fill=1, stroke=0)
    c.setFillColor(navy); c.setFont("Helvetica-Bold", 11)
    c.drawString(54, y, t["section_b"]); y -= 18

    amount_line(t["platform_fee"], inv.get("bidvex_platform_fee_cad", 0))
    amount_line(t["broker_fee"],    inv.get("broker_fee_cad", 0))
    c.setStrokeColor(grey); c.setLineWidth(0.4); c.line(50, y + 4, w - 50, y + 4)
    subtotal = float(inv.get("bidvex_platform_fee_cad", 0)) + float(inv.get("broker_fee_cad", 0))
    amount_line(t["subtotal"], subtotal)
    amount_line(t["gst"], inv.get("gst_cad", 0))
    if float(inv.get("qst_cad", 0) or 0) > 0:
        amount_line(t["qst"], inv.get("qst_cad", 0))
    stripe_fee = float((inv.get("fee_breakdown") or {}).get("stripe_processing_fee", 0))
    if stripe_fee > 0:
        amount_line(t["stripe_fee"], stripe_fee)
    c.setStrokeColor(navy); c.setLineWidth(1); c.line(50, y + 4, w - 50, y + 4); y -= 2
    c.setFillColor(navy)
    amount_line(t["stripe_total"], inv.get("total_cad", 0), bold=True, size=12)
    y -= 6

    # ── Deposit
    c.setFillColor(HexColor("#F3F4F6"))
    c.rect(48, y - 12, w - 96, 28, fill=1, stroke=0)
    c.setFillColor(HexColor("#1F2937"))
    deposit_amount = float((inv.get("fee_breakdown") or {}).get("deposit_held", 500))
    c.setFont("Helvetica-Bold", 10); c.drawString(54, y, f'{t["deposit"]}: ${deposit_amount:,.2f} CAD')
    c.setFont("Helvetica", 9);     c.drawString(54, y - 10, t["deposit_note"])
    y -= 30

    # ── Footer block
    c.setStrokeColor(grey); c.line(50, y, w - 50, y); y -= 14
    c.setFillColor(HexColor("#1F2937")); c.setFont("Helvetica", 8)
    c.drawString(50, y, f'{t["gst_reg"]}   ·   {t["qst_reg"]}'); y -= 12
    broker_payout = float(inv.get("broker_fee_cad", 0)) + float(inv.get("gst_cad", 0)) + float(inv.get("qst_cad", 0))
    bidvex_payout = float(inv.get("bidvex_platform_fee_cad", 0))
    c.drawString(50, y, f'{t["broker_payout"]}: ${broker_payout:,.2f} CAD'); y -= 11
    c.drawString(50, y, f'{t["bidvex_payout"]}: ${bidvex_payout:,.2f} CAD'); y -= 18

    c.setFillColor(grey); c.setFont("Helvetica-Oblique", 8)
    for ln in simpleSplit(t["footer_legal"], "Helvetica-Oblique", 8, w - 100):
        c.drawString(50, y, ln); y -= 10

    c.showPage(); c.save(); buf.seek(0)
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
