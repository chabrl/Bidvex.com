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

from fastapi import APIRouter, Depends, HTTPException
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
    if (current_user.role or "") not in ("admin", "superadmin"):
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
    if (current_user.role or "") not in ("admin", "superadmin"):
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
    if not rel or rel.get("buyer_user_id") != current_user.id:
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
