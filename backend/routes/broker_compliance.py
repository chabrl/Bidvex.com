"""
iter217 Phase 5 Hotfix v7 — Individual seller, dispute timeout & broker
ratings routes (legal compliance hardening).

Mounted at /api by server.py.

Endpoints:
    POST   /api/listings/individual               — non-vehicle listing by individual seller
    POST   /api/broker-invoices/{id}/non-responsive
    POST   /api/broker-invoices/{id}/admin-action
    POST   /api/broker-invoices/{id}/dispute      — open a dispute
    POST   /api/admin/broker-invoices/{id}/resolve-dispute
    POST   /api/broker-relationships/{id}/rate    — buyer rates broker
    GET    /api/brokers/{id}/ratings              — public list of broker ratings
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, User


def _utcnow():
    return datetime.now(timezone.utc)


broker_compliance_router = APIRouter(prefix="/api", tags=["broker-compliance"])


# ─────────────────────────────────────────────────────────────────────
# Task 5 — Individual seller listings (non-vehicle only)
# ─────────────────────────────────────────────────────────────────────
class _IndividualListingIn(BaseModel):
    title:           str
    description:     str
    category:        str
    starting_price:  float = Field(gt=0)
    images:          List[str] = []
    region:          Optional[str] = None
    city:            Optional[str] = None
    title_fr:        Optional[str] = None
    description_fr:  Optional[str] = None


@broker_compliance_router.post("/listings/individual")
async def create_individual_listing(
    payload:      _IndividualListingIn,
    current_user: User = Depends(get_current_user),
):
    """An individual (non-broker, non-dealer) lists a non-vehicle item.

    Business rules:
      • Vehicles category is REJECTED (legal requirement).
      • First 3 listings → admin manual review (status=pending_review).
      • After 3 approved listings → auto-approve (status=active).
      • Commission deducted at payout = 8% of hammer + GST (5%) + QST 9.975% if QC.
      • A `seller_account_type` of "individual" is stamped on the listing.
    """
    from services.category_rules import assert_seller_can_list

    db = get_db()

    # Legal: individuals cannot list vehicles
    ok, err = assert_seller_can_list(payload.category, current_user.account_type or "individual")
    if not ok:
        raise HTTPException(status_code=403, detail=err)

    # Approval-trust: count prior approved listings by this seller
    approved_count = await db.listings.count_documents({
        "seller_id":               current_user.id,
        "seller_account_type":     "individual",
        "status":                  {"$in": ["active", "ended", "sold"]},
    })
    auto_approved = approved_count >= 3
    listing_status = "active" if auto_approved else "pending_review"

    doc = {
        "id":                 str(uuid.uuid4()),
        "title":              payload.title.strip(),
        "title_fr":           payload.title_fr,
        "description":        payload.description,
        "description_fr":     payload.description_fr,
        "category":           payload.category,
        "starting_price":     float(payload.starting_price),
        "current_price":      float(payload.starting_price),
        "images":             list(payload.images or []),
        "region":             payload.region,
        "city":               payload.city,
        "seller_id":          current_user.id,
        "seller_account_type": "individual",
        "commission_rate":    0.08,
        "status":             listing_status,
        "review_state":       "pending_review" if not auto_approved else "auto_approved",
        "auto_approved":      auto_approved,
        "created_at":         _utcnow(),
    }
    await db.listings.insert_one(doc)

    # Strip Mongo ObjectId before returning
    doc.pop("_id", None)
    return {
        "success":            True,
        "listing_id":         doc["id"],
        "status":             listing_status,
        "auto_approved":      auto_approved,
        "prior_approved":     approved_count,
        "needs_admin_review": not auto_approved,
        "commission_rate":    0.08,
        "message_en": (
            "Listing auto-approved." if auto_approved
            else "Listing submitted for admin review (24-48 hours)."
        ),
        "message_fr": (
            "Annonce approuvée automatiquement." if auto_approved
            else "Annonce soumise à l'examen administratif (24-48 heures)."
        ),
    }


@broker_compliance_router.get("/individual-seller/payout-preview")
async def individual_payout_preview(
    hammer_price:   float,
    buyer_province: Optional[str] = None,
    current_user:   User = Depends(get_current_user),
):
    """Show the seller what they will net after BidVex's 8% commission +
    GST (5%) + QST (9.975%, Quebec only). Pure calculator — no DB writes.
    """
    h = max(0.0, float(hammer_price or 0))
    commission = round(h * 0.08, 2)
    gst        = round(commission * 0.05, 2)
    qst        = round(commission * 0.09975, 2) if (buyer_province or "").upper() == "QC" else 0.0
    net        = round(h - commission - gst - qst, 2)
    return {
        "hammer_price":    h,
        "commission_pct":  0.08,
        "commission_cad":  commission,
        "gst_cad":         gst,
        "qst_cad":         qst,
        "seller_net_cad":  net,
    }


# ─────────────────────────────────────────────────────────────────────
# Task 6 — Dispute & non-payment timeout flow
# ─────────────────────────────────────────────────────────────────────
class _NonResponsiveIn(BaseModel):
    reason: Optional[str] = None


@broker_compliance_router.post("/broker-invoices/{invoice_id}/non-responsive")
async def mark_buyer_non_responsive(
    invoice_id:   str,
    payload:      _NonResponsiveIn,
    current_user: User = Depends(get_current_user),
):
    """Broker (>=48h after invoice generated) marks the buyer as
    non-responsive. Notifies admin who can re-auction, forfeit deposit,
    or suspend the buyer (next endpoint).
    """
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    inv    = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not broker or not inv or inv["broker_id"] != broker["id"]:
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})

    elapsed = _utcnow() - (inv.get("created_at") or _utcnow())
    if elapsed < timedelta(hours=48):
        raise HTTPException(
            status_code=400,
            detail={"error": "too_early",
                    "message_en": "You can only flag a buyer as non-responsive 48 hours after the invoice is generated.",
                    "message_fr": "Vous ne pouvez signaler un acheteur comme non-réactif que 48 heures après la génération de la facture."},
        )
    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "non_responsive_flagged_at": _utcnow(),
            "non_responsive_reason":     payload.reason,
            "non_responsive_flagged_by": current_user.id,
        }},
    )
    return {"success": True, "message_en": "Buyer flagged as non-responsive. Admin notified."}


class _AdminInvoiceActionIn(BaseModel):
    action: Literal["re_auction", "deposit_forfeit", "suspend_buyer"]
    note:   Optional[str] = None


@broker_compliance_router.post("/admin/broker-invoices/{invoice_id}/admin-action")
async def admin_invoice_action(
    invoice_id:   str,
    payload:      _AdminInvoiceActionIn,
    current_user: User = Depends(get_current_user),
):
    """Admin resolution after 72h timeout or non-responsive flag.
    `re_auction` — relist the listing; `deposit_forfeit` — capture the
    $500 Stripe hold; `suspend_buyer` — mark buyer account suspended."""
    if (current_user.role or "") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail={"error": "admin_only"})
    db  = get_db()
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail={"error": "invoice_not_found"})

    now = _utcnow()
    audit = {
        "id":            str(uuid.uuid4()),
        "invoice_id":    invoice_id,
        "action":        payload.action,
        "actor_email":   current_user.email,
        "note":          payload.note,
        "at":            now,
    }
    update: Dict[str, Any] = {"admin_action": payload.action, "admin_action_at": now}
    if payload.action == "suspend_buyer":
        await db.users.update_one({"id": inv.get("buyer_user_id")}, {"$set": {"is_suspended": True, "suspended_at": now}})
    elif payload.action == "deposit_forfeit":
        update["deposit_forfeited"] = True
        update["deposit_forfeited_at"] = now
    elif payload.action == "re_auction":
        await db.listings.update_one({"id": inv.get("vehicle_listing_id")}, {"$set": {"status": "ready_for_relist"}})

    await db.broker_invoices.update_one({"id": invoice_id}, {"$set": update})
    await db.broker_invoice_audit.insert_one(audit)
    return {"success": True, "applied": payload.action}


class _OpenDisputeIn(BaseModel):
    reason: str = Field(min_length=10)
    side:   Literal["buyer", "broker"]


@broker_compliance_router.post("/broker-invoices/{invoice_id}/dispute")
async def open_dispute(
    invoice_id:   str,
    payload:      _OpenDisputeIn,
    current_user: User = Depends(get_current_user),
):
    """Open a dispute window. Only allowed within 7 days of vehicle release."""
    db  = get_db()
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail={"error": "invoice_not_found"})

    released = inv.get("released_at")
    if not released:
        raise HTTPException(status_code=400, detail={"error": "release_not_yet",
                                                     "message_en": "A dispute can only be opened after the vehicle has been released."})
    if isinstance(released, str):
        released = datetime.fromisoformat(released.replace("Z", "+00:00"))
    if released.tzinfo is None:
        released = released.replace(tzinfo=timezone.utc)
    if _utcnow() > released + timedelta(days=7):
        raise HTTPException(status_code=400, detail={"error": "dispute_window_closed",
                                                     "message_en": "The 7-day dispute window has expired."})

    # Authorization: only broker (owner) or buyer (winner) of the invoice
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1})
    is_owner_broker = broker and inv["broker_id"] == broker["id"] and payload.side == "broker"
    is_buyer        = inv.get("buyer_user_id") == current_user.id and payload.side == "buyer"
    if not (is_owner_broker or is_buyer):
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})

    now = _utcnow()
    await db.broker_invoices.update_one({"id": invoice_id}, {"$set": {
        "dispute_status":      "open",
        "dispute_opened_at":   now,
        "dispute_opened_by":   payload.side,
        "dispute_reason":      payload.reason,
        "dispute_deadline_at": released + timedelta(days=7),
    }})
    return {"success": True, "dispute_deadline_at": (released + timedelta(days=7)).isoformat()}


class _ResolveDisputeIn(BaseModel):
    award_to: Literal["buyer", "broker"]
    note:     Optional[str] = None


@broker_compliance_router.post("/admin/broker-invoices/{invoice_id}/resolve-dispute")
async def admin_resolve_dispute(
    invoice_id:   str,
    payload:      _ResolveDisputeIn,
    current_user: User = Depends(get_current_user),
):
    """Admin decides where the $500 deposit goes."""
    if (current_user.role or "") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail={"error": "admin_only"})
    db  = get_db()
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv or inv.get("dispute_status") != "open":
        raise HTTPException(status_code=400, detail={"error": "no_open_dispute"})

    now = _utcnow()
    await db.broker_invoices.update_one({"id": invoice_id}, {"$set": {
        "dispute_status":      "resolved",
        "dispute_resolved_at": now,
        "dispute_award_to":    payload.award_to,
        "dispute_admin_note":  payload.note,
        "deposit_released":    payload.award_to == "buyer",
        "deposit_forfeited":   payload.award_to == "broker",
    }})
    await db.broker_invoice_audit.insert_one({
        "id":          str(uuid.uuid4()),
        "invoice_id":  invoice_id,
        "action":      "resolve_dispute",
        "actor_email": current_user.email,
        "details":     payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
        "at":          now,
    })
    return {"success": True, "award_to": payload.award_to}


# ─────────────────────────────────────────────────────────────────────
# v8 — Vehicle Title Transfer Tracker (closes the compliance audit loop)
# ─────────────────────────────────────────────────────────────────────
class _TitleTransferIn(BaseModel):
    registry_tx_number: str = Field(min_length=3, max_length=100)
    province:           Literal["QC", "ON", "AB", "BC", "MB", "SK", "NS", "NB", "NL", "PE", "OTHER"]
    registry:           Optional[str] = None   # auto-fills if omitted
    transfer_date:      datetime
    receipt_url:        Optional[str] = None   # PDF/JPG/PNG URL (uploaded separately)


_REGISTRY_BY_PROVINCE = {
    "QC":    "SAAQ",
    "ON":    "ServiceOntario",
    "AB":    "AMVIC / Alberta Registries",
    "BC":    "ICBC",
    "MB":    "Manitoba Public Insurance",
    "SK":    "SGI",
    "NS":    "Service Nova Scotia",
    "NB":    "Service New Brunswick",
    "NL":    "Motor Registration Division",
    "PE":    "Access PEI",
    "OTHER": "Provincial Registry",
}


@broker_compliance_router.patch("/broker-invoices/{invoice_id}/log-title-transfer")
async def log_title_transfer(
    invoice_id:   str,
    payload:      _TitleTransferIn,
    current_user: User = Depends(get_current_user),
):
    """Broker logs the provincial title transfer reference number.

    Required within 14 days of vehicle release. Auth: broker only (owner
    of the invoice). All actions audited.
    """
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0, "id": 1, "legal_business_name": 1})
    inv    = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not broker or not inv or inv["broker_id"] != broker["id"]:
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})
    if not inv.get("released_at"):
        raise HTTPException(
            status_code=400,
            detail={"error": "release_required_first",
                    "message_en": "You can only log the title transfer after releasing the vehicle.",
                    "message_fr": "Vous ne pouvez consigner le transfert de propriété qu'après la remise du véhicule."},
        )
    if inv.get("title_transfer_logged_at"):
        raise HTTPException(status_code=400, detail={"error": "already_logged"})

    registry = payload.registry or _REGISTRY_BY_PROVINCE.get(payload.province, _REGISTRY_BY_PROVINCE["OTHER"])
    now = _utcnow()

    await db.broker_invoices.update_one(
        {"id": invoice_id},
        {"$set": {
            "title_transfer_logged_at":  now,
            "title_transfer_logged_by":  current_user.id,
            "title_transfer_registry":   registry,
            "title_transfer_province":   payload.province,
            "title_transfer_tx_number":  payload.registry_tx_number.strip(),
            "title_transfer_date":       payload.transfer_date,
            "title_transfer_receipt_url": payload.receipt_url,
        }},
    )
    # Audit trail
    try:
        await db.broker_invoice_audit.insert_one({
            "id":          str(uuid.uuid4()),
            "invoice_id":  invoice_id,
            "action":      "log_title_transfer",
            "actor_id":    current_user.id,
            "actor_email": current_user.email,
            "details":     payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
            "at":          now,
        })
    except Exception:
        pass   # non-fatal — audit failure must not break the user-facing call

    # Buyer email is dispatched out-of-band by a background worker
    # (not blocking the response). Mark a flag for the worker to pick up.
    await db.email_outbox.insert_one({
        "id":         str(uuid.uuid4()),
        "kind":       "title_transfer_filed",
        "to_user_id": inv.get("buyer_user_id"),
        "context":    {
            "invoice_id":         invoice_id,
            "registry":           registry,
            "registry_tx_number": payload.registry_tx_number.strip(),
            "transfer_date":      payload.transfer_date.isoformat(),
            "broker_name":        broker.get("legal_business_name"),
        },
        "queued_at":  now,
    })
    return {
        "success":         True,
        "registry":        registry,
        "registry_tx_number": payload.registry_tx_number.strip(),
        "logged_at":       now,
    }


@broker_compliance_router.get("/admin/broker-invoices/missing-title-transfer")
async def admin_missing_title_transfers(current_user: User = Depends(get_current_user)):
    """Invoices released > 14 days ago without a logged title transfer.
    Admin dashboard polls this for the "Broker has not filed title transfer"
    notification list.
    """
    if (current_user.role or "") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail={"error": "admin_only"})
    db = get_db()
    cutoff = _utcnow() - timedelta(days=14)
    rows: List[Dict[str, Any]] = []
    async for inv in db.broker_invoices.find({
        "released_at":              {"$ne": None, "$lt": cutoff},
        "title_transfer_logged_at": None,
    }, {"_id": 0}).limit(200):
        broker = await db.brokers.find_one({"id": inv["broker_id"]}, {"_id": 0, "legal_business_name": 1, "broker_license_number": 1})
        rel_days = None
        if inv.get("released_at"):
            rel = inv["released_at"]
            if isinstance(rel, str):
                from datetime import datetime as _dt
                rel = _dt.fromisoformat(rel.replace("Z", "+00:00"))
            if rel.tzinfo is None:
                rel = rel.replace(tzinfo=timezone.utc)
            rel_days = (_utcnow() - rel).days - 14
        rows.append({
            "invoice_id":     inv["id"],
            "invoice_number": inv.get("invoice_number"),
            "broker_id":      inv["broker_id"],
            "broker_name":    (broker or {}).get("legal_business_name"),
            "released_at":    inv.get("released_at"),
            "days_overdue":   rel_days,
        })
    return {"data": rows, "count": len(rows)}


# ─────────────────────────────────────────────────────────────────────
# Task 7 — Broker trust score (ratings & response time)
# ─────────────────────────────────────────────────────────────────────
class _RateBrokerIn(BaseModel):
    stars:   int = Field(ge=1, le=5)
    review:  Optional[str] = None


@broker_compliance_router.post("/broker-relationships/{rel_id}/rate")
async def rate_broker(
    rel_id:       str,
    payload:      _RateBrokerIn,
    current_user: User = Depends(get_current_user),
):
    """Only buyers who completed a transaction can rate. One rating per
    completed transaction. Broker never sees individual reviewer identity.
    """
    db  = get_db()
    rel = await db.broker_buyer_relationships.find_one({"id": rel_id}, {"_id": 0})
    if not rel or (rel.get("buyer_user_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail={"error": "not_authorized"})

    # Require a released invoice for this broker × buyer pair
    completed = await db.broker_invoices.count_documents({
        "broker_id":      rel["broker_id"],
        "buyer_user_id":  current_user.id,
        "released_at":    {"$ne": None},
    })
    if completed == 0:
        raise HTTPException(status_code=400, detail={"error": "no_completed_tx",
                                                     "message_en": "You can only rate a broker after completing a transaction."})

    # Prevent double-rating
    already = await db.broker_ratings.count_documents({
        "relationship_id": rel_id, "buyer_user_id": current_user.id,
    })
    if already > 0:
        raise HTTPException(status_code=400, detail={"error": "already_rated"})

    now = _utcnow()
    await db.broker_ratings.insert_one({
        "id":              str(uuid.uuid4()),
        "broker_id":       rel["broker_id"],
        "relationship_id": rel_id,
        "buyer_user_id":   current_user.id,
        "stars":           int(payload.stars),
        "review":          payload.review,
        "created_at":      now,
    })

    # Recompute aggregate on the broker doc
    pipeline = [
        {"$match": {"broker_id": rel["broker_id"]}},
        {"$group": {"_id": None, "avg": {"$avg": "$stars"}, "count": {"$sum": 1}}},
    ]
    agg = await db.broker_ratings.aggregate(pipeline).to_list(length=1)
    avg, count = (agg[0]["avg"], agg[0]["count"]) if agg else (None, 0)
    await db.brokers.update_one({"id": rel["broker_id"]}, {"$set": {
        "rating_avg":   round(float(avg or 0), 2),
        "rating_count": int(count),
    }})

    # Admin notification on low ratings
    if int(payload.stars) <= 2:
        await db.admin_notifications.insert_one({
            "id":         str(uuid.uuid4()),
            "type":       "low_broker_rating",
            "broker_id":  rel["broker_id"],
            "stars":      int(payload.stars),
            "review":     payload.review,
            "at":         now,
        })

    return {"success": True, "avg": round(float(avg or 0), 2), "count": int(count)}


@broker_compliance_router.get("/brokers/{broker_id}/ratings")
async def list_broker_ratings(broker_id: str, limit: int = 20):
    """Public ratings list — no PII. Buyer is anonymous."""
    db = get_db()
    rows: List[Dict[str, Any]] = []
    async for r in db.broker_ratings.find({"broker_id": broker_id}, {"_id": 0, "buyer_user_id": 0}).sort("created_at", -1).limit(limit):
        rows.append(r)
    return {"data": rows, "count": len(rows)}


@broker_compliance_router.get("/brokers/{broker_id}/trust-score")
async def broker_trust_score(broker_id: str):
    """Compute on-the-fly trust metrics for the public directory card."""
    db = get_db()
    broker = await db.brokers.find_one({"id": broker_id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=404, detail={"error": "broker_not_found"})

    completed_count = await db.broker_invoices.count_documents({
        "broker_id":   broker_id,
        "released_at": {"$ne": None},
    })

    # Median response time: relationship.created_at → approved_at
    pipeline = [
        {"$match": {"broker_id": broker_id, "approved_at": {"$ne": None}, "created_at": {"$ne": None}}},
        {"$project": {"hours": {"$divide": [{"$subtract": ["$approved_at", "$created_at"]}, 1000 * 60 * 60]}}},
        {"$group": {"_id": None, "avg": {"$avg": "$hours"}}},
    ]
    rt = await db.broker_buyer_relationships.aggregate(pipeline).to_list(length=1)
    response_hours = round(float(rt[0]["avg"]), 1) if rt else None

    return {
        "broker_id":           broker_id,
        "verified":            broker.get("verification_status") == "approved",
        "completed_transactions": completed_count,
        "avg_response_hours":  response_hours,
        "rating_avg":          float(broker.get("rating_avg") or 0),
        "rating_count":        int(broker.get("rating_count") or 0),
        "member_since":        broker.get("created_at"),
    }


@broker_compliance_router.get("/stripe/connect-onboarding-link")
async def broker_stripe_connect_onboarding(
    request:      Request,
    current_user: User = Depends(get_current_user),
):
    """v8.1 — Broker-specific Stripe Connect onboarding link.

    Creates (or reuses) a Stripe Express account for the current broker,
    then returns an `account_links` URL that bounces the broker back to
    /dashboard/revenue?status=success (or ?status=failed on refresh).
    """
    import os
    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=501, detail={"error": "stripe_sdk_unavailable"})

    stripe.api_key = (
        os.environ.get("STRIPE_SECRET_KEY")
        or os.environ.get("STRIPE_TEST_SECRET_KEY")
    )
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail={"error": "stripe_not_configured"})

    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=403, detail={"error": "not_a_broker"})

    connect_id = broker.get("stripe_connect_account_id")
    if not connect_id:
        try:
            account = stripe.Account.create(
                type="express",
                country="CA",
                email=current_user.email,
                capabilities={"card_payments": {"requested": True},
                              "transfers":     {"requested": True}},
                business_type="company",
                metadata={"user_id": current_user.id, "broker_id": broker["id"], "platform": "bidvex"},
            )
            connect_id = account.id
            await db.brokers.update_one(
                {"id": broker["id"]},
                {"$set": {
                    "stripe_connect_account_id":         connect_id,
                    "stripe_connect_onboarding_complete": False,
                    "stripe_connect_created_at":         _utcnow(),
                }},
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail={"error": "stripe_account_create_failed", "message_en": str(e)})

    base_url = os.environ.get("REACT_APP_BACKEND_URL", str(request.base_url).rstrip("/"))
    try:
        link = stripe.AccountLink.create(
            account=connect_id,
            refresh_url=f"{base_url}/broker/dashboard?revenue=refresh&status=failed",
            return_url=f"{base_url}/broker/dashboard?revenue=connected&status=success",
            type="account_onboarding",
            collection_options={"fields": "eventually_due"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": "stripe_link_create_failed", "message_en": str(e)})

    return {"connect_account_id": connect_id, "onboarding_url": link.url}


@broker_compliance_router.get("/stripe/broker-connect-status")
async def broker_stripe_connect_status(current_user: User = Depends(get_current_user)):
    """Return whether the broker's Stripe Connect account is onboarded + balance."""
    import os
    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=501, detail={"error": "stripe_sdk_unavailable"})
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_TEST_SECRET_KEY")
    db = get_db()
    broker = await db.brokers.find_one({"user_id": current_user.id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=403, detail={"error": "not_a_broker"})
    connect_id = broker.get("stripe_connect_account_id")
    if not connect_id:
        return {"onboarded": False, "connect_account_id": None}
    try:
        acct = stripe.Account.retrieve(connect_id)
        onboarded = bool(acct.charges_enabled and acct.payouts_enabled and acct.details_submitted)
        balance = None
        if onboarded:
            try:
                bal = stripe.Balance.retrieve(stripe_account=connect_id)
                balance = {
                    "available_cad": sum(b.amount for b in bal.available if b.currency == "cad") / 100.0,
                    "pending_cad":   sum(b.amount for b in bal.pending   if b.currency == "cad") / 100.0,
                }
            except Exception:
                balance = None
        if onboarded != bool(broker.get("stripe_connect_onboarding_complete")):
            await db.brokers.update_one({"id": broker["id"]},
                                         {"$set": {"stripe_connect_onboarding_complete": onboarded}})
        return {
            "onboarded":         onboarded,
            "connect_account_id": connect_id,
            "charges_enabled":   bool(acct.charges_enabled),
            "payouts_enabled":   bool(acct.payouts_enabled),
            "details_submitted": bool(acct.details_submitted),
            "balance":           balance,
        }
    except Exception as e:
        return {"onboarded": False, "connect_account_id": connect_id, "error": str(e)}



# Token-secured, no login required. The 12-char `receipt_token` is
# stored on the invoice and embedded in the buyer release email link.
# Returns 404 (NOT 403) on token mismatch to avoid leaking whether
# the invoice_id exists.
# ─────────────────────────────────────────────────────────────────────
def _mask_full_name(full_name: Optional[str]) -> str:
    """'John Doe' → 'John D.'  'Marie-Claire Dupont' → 'Marie-Claire D.'."""
    if not full_name or not full_name.strip():
        return "Anonymous"
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


@broker_compliance_router.get("/broker-invoices/{invoice_id}/receipt")
async def get_buyer_receipt(invoice_id: str, code: Optional[str] = None):
    """Public token-secured buyer transaction receipt."""
    db = get_db()
    inv = await db.broker_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv or not code or inv.get("receipt_token") != code:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    broker  = await db.brokers.find_one({"id": inv["broker_id"]}, {"_id": 0}) or {}
    buyer   = await db.users.find_one({"id": inv["buyer_user_id"]}, {"_id": 0, "full_name": 1, "name": 1}) or {}
    listing = (await db.listings.find_one({"id": inv["vehicle_listing_id"]}, {"_id": 0})
               or await db.vehicle_listings.find_one({"id": inv["vehicle_listing_id"]}, {"_id": 0})
               or {})

    lic = broker.get("broker_license_number") or ""
    masked_license = ("•" * max(0, len(lic) - 3)) + lic[-3:] if lic else ""
    fee_breakdown = inv.get("fee_breakdown") or {}

    return {
        "invoice_number":   inv.get("invoice_number"),
        "issued_at":        inv.get("created_at"),
        "vehicle": {
            "title":            listing.get("title"),
            "year":             listing.get("year"),
            "make":             listing.get("make"),
            "model":            listing.get("model"),
            "vin":              listing.get("vin"),
            "mileage":          listing.get("mileage") or listing.get("odometer"),
            "origin_province":  (listing.get("region") or listing.get("province") or inv.get("title_transfer_province")),
            "country":          listing.get("country") or "Canada",
        },
        "buyer":  {"display_name": _mask_full_name(buyer.get("full_name") or buyer.get("name"))},
        "broker": {
            "legal_business_name": broker.get("legal_business_name"),
            "license_masked":      masked_license,
            "regulatory_body":     broker.get("regulatory_body"),
            "operating_province":  broker.get("operating_province"),
        },
        "transaction": {
            "hammer_price_cad":              float(inv.get("hammer_price_cad", 0)),
            "hammer_settlement":             "direct",
            "hammer_settlement_note":        ("Settled directly between the buyer and the licensed broker outside of BidVex "
                                              "(bank wire, certified cheque, or broker trust account)."),
            "auction_closed_at":             inv.get("created_at"),
            "vehicle_released_at":           inv.get("released_at"),
            "title_transfer_logged_at":      inv.get("title_transfer_logged_at"),
            "title_transfer_registry":       inv.get("title_transfer_registry"),
            "title_transfer_tx_number":      inv.get("title_transfer_tx_number"),
            "title_transfer_date":           inv.get("title_transfer_date"),
            "pickup_code_used":              inv.get("pickup_code") if inv.get("released_at") else None,
        },
        "fees_via_stripe": {
            "platform_fee_cad":              float(inv.get("bidvex_platform_fee_cad", 0)),
            "broker_fee_cad":                float(inv.get("broker_fee_cad", 0)),
            "gst_cad":                       float(inv.get("gst_cad", 0)),
            "qst_cad":                       float(inv.get("qst_cad", 0)),
            "stripe_processing_fee_cad":     float(fee_breakdown.get("stripe_processing_fee", 0)),
            "total_via_stripe_cad":          float(inv.get("total_cad", 0)),
        },
        "platform_disclaimer": ("The vehicle hammer price was settled directly between the buyer and the licensed "
                                "broker outside of BidVex. BidVex is a marketplace platform and does not act as a "
                                "dealer or financial intermediary."),
        "platform_address":   "BidVex Inc. — Sherbrooke, QC, Canada",
        "gst_registration":   "GST# 00000 00000 RT0001",
        "qst_registration":   "QST# 0000000000 TQ0001",
    }


@broker_compliance_router.get("/broker-invoices/{invoice_id}/receipt/pdf")
async def get_buyer_receipt_pdf(invoice_id: str, code: Optional[str] = None, lang: str = "en"):
    """Single-page bilingual PDF version of the buyer receipt."""
    from fastapi.responses import StreamingResponse
    import io
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.colors import HexColor
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas as _pdf_canvas

    data = await get_buyer_receipt(invoice_id, code)
    fr = (lang == "fr")
    t = {
        "title":   "Reçu officiel de transaction BidVex"     if fr else "BidVex Official Transaction Receipt",
        "invoice": "Facture n°"                              if fr else "Invoice #",
        "vehicle": "Véhicule"                                if fr else "Vehicle",
        "buyer":   "Acheteur"                                 if fr else "Buyer",
        "broker":  "Courtier licencié"                       if fr else "Licensed Broker",
        "license": "Permis"                                  if fr else "License #",
        "registry":"Registre provincial"                     if fr else "Provincial Registry",
        "txn":     "Détails de la transaction"               if fr else "Transaction Details",
        "hammer":  "Prix marteau (réglé directement)"        if fr else "Hammer Price (settled directly)",
        "released":"Véhicule remis"                          if fr else "Vehicle Released",
        "tt":      "Transfert de propriété déposé"           if fr else "Title Transfer Filed",
        "tt_pending": "En attente"                            if fr else "Pending",
        "fees":    "Frais traités via BidVex (Stripe)"       if fr else "Fees Processed via BidVex (Stripe)",
        "pf":      "Frais de plateforme BidVex"              if fr else "BidVex Platform Fee",
        "bf":      "Frais de service du courtier"            if fr else "Broker Service Fee",
        "gst":     "TPS (5 %)"                                if fr else "GST (5%)",
        "qst":     "TVQ (9,975 %)"                            if fr else "QST (9.975%)",
        "spf":     "Frais de traitement Stripe"              if fr else "Stripe Processing Fee",
        "total_s": "TOTAL via Stripe"                         if fr else "TOTAL via Stripe",
        "warn":    ("⚠ Le prix marteau a été réglé directement entre l'acheteur et le courtier licencié "
                    "hors de BidVex. BidVex est une plateforme de marché et n'agit pas comme "
                    "concessionnaire ou intermédiaire financier.")
                   if fr else
                   ("⚠ The vehicle hammer price was settled directly between the buyer and the "
                    "licensed broker outside of BidVex. BidVex is a marketplace platform and does "
                    "not act as a dealer or financial intermediary."),
        "footer":  "Vérifié par BidVex Inc. — Sherbrooke, QC, Canada"
                   if fr else "Verified by BidVex Inc. — Sherbrooke, QC, Canada",
    }

    buf = io.BytesIO()
    c = _pdf_canvas.Canvas(buf, pagesize=LETTER)
    w, h = LETTER
    navy  = HexColor("#1E3A8A")
    grey  = HexColor("#6B7280")
    amber = HexColor("#92400E")
    y = h - 50

    c.setFillColor(navy); c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "🔒 " + t["title"]); y -= 22
    c.setFillColor(grey); c.setFont("Helvetica", 9)
    c.drawString(50, y, f"{t['invoice']}: {data.get('invoice_number','—')}  ·  {str(data.get('issued_at',''))[:10]}")
    y -= 8
    c.setStrokeColor(navy); c.setLineWidth(1.5); c.line(50, y, w - 50, y); y -= 18

    v   = data["vehicle"]; b = data["buyer"]; brk = data["broker"]
    tx  = data["transaction"]; fees = data["fees_via_stripe"]

    def hd(lbl):
        nonlocal y
        c.setFillColor(navy); c.setFont("Helvetica-Bold", 11); c.drawString(50, y, lbl); y -= 14

    def kv(k, val):
        nonlocal y
        c.setFillColor(HexColor("#1F2937")); c.setFont("Helvetica", 10)
        c.drawString(60, y, str(k)); c.drawRightString(w - 50, y, str(val)); y -= 12

    def amt(k, val):
        nonlocal y
        c.setFillColor(HexColor("#1F2937")); c.setFont("Helvetica", 10)
        c.drawString(60, y, str(k)); c.drawRightString(w - 50, y, f"${float(val or 0):,.2f} CAD"); y -= 12

    hd(t["vehicle"])
    kv("Title",            v.get("title") or "—")
    kv("Year/Make/Model",  " ".join(str(x) for x in [v.get("year"), v.get("make"), v.get("model")] if x) or "—")
    kv("VIN",              v.get("vin") or "—")
    kv("Mileage",          v.get("mileage") or "—")
    kv("Origin",           f'{v.get("origin_province") or "—"}, {v.get("country") or ""}')
    y -= 4
    hd(t["buyer"]);  kv("Display name", b.get("display_name"))
    hd(t["broker"]); kv("Business", brk.get("legal_business_name") or "—")
    kv(t["license"],  brk.get("license_masked") or "—")
    kv(t["registry"], f'{brk.get("regulatory_body") or "—"} ({brk.get("operating_province") or ""})')
    y -= 4

    hd(t["txn"])
    c.setFillColor(amber); c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y, t["hammer"]); c.drawRightString(w - 50, y, f"${float(tx.get('hammer_price_cad', 0)):,.2f} CAD")
    y -= 12
    kv(t["released"], str(tx.get("vehicle_released_at") or "—")[:10])
    if tx.get("title_transfer_logged_at"):
        kv(t["tt"], f"{tx.get('title_transfer_registry') or ''} {tx.get('title_transfer_tx_number') or ''}".strip())
        kv("Date", str(tx.get("title_transfer_date") or "—")[:10])
    else:
        c.setFillColor(amber); c.drawString(60, y, t["tt"]); c.drawRightString(w - 50, y, t["tt_pending"]); y -= 12
    y -= 4

    hd(t["fees"])
    amt(t["pf"],  fees.get("platform_fee_cad"))
    amt(t["bf"],  fees.get("broker_fee_cad"))
    amt(t["gst"], fees.get("gst_cad"))
    if float(fees.get("qst_cad", 0) or 0) > 0:
        amt(t["qst"], fees.get("qst_cad"))
    amt(t["spf"], fees.get("stripe_processing_fee_cad"))
    c.setStrokeColor(navy); c.setLineWidth(1); c.line(50, y + 4, w - 50, y + 4); y -= 2
    c.setFillColor(navy); c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, t["total_s"]); c.drawRightString(w - 50, y, f"${float(fees.get('total_via_stripe_cad', 0)):,.2f} CAD")
    y -= 18

    c.setFillColor(amber); c.setFont("Helvetica-Oblique", 9)
    for ln in simpleSplit(t["warn"], "Helvetica-Oblique", 9, w - 100):
        c.drawString(50, y, ln); y -= 11
    y -= 8
    c.setFillColor(grey); c.setFont("Helvetica", 8)
    c.drawString(50, y, t["footer"]); y -= 10
    c.drawString(50, y, f'{data.get("gst_registration","")}   ·   {data.get("qst_registration","")}')

    c.showPage(); c.save(); buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="bidvex-receipt-{data.get("invoice_number")}.pdf"',
    })
