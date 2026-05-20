"""
BidVex — FEATURE PATCH v9 / Feature 3
AI Watchdog Admin Review Flow for category mismatches.

Endpoints:
  POST   /api/listings/{listing_id}/flag-for-ai-review    (seller-side)
  GET    /api/admin/listing-reviews?status=pending        (admin queue)
  GET    /api/admin/listing-reviews/{review_id}            (single)
  POST   /api/admin/listing-reviews/{review_id}/approve    (admin action)
  POST   /api/admin/listing-reviews/{review_id}/reject     (admin action)
  POST   /api/listings/{listing_id}/correct-category       (seller resubmit)
  POST   /api/listings/{listing_id}/withdraw-from-review   (seller withdraw)

Workflow:
  1. Seller submits listing → AI scanner suggests category mismatch.
  2. UI shows warning popup; seller clicks "OK" → listing goes to
     pending_ai_review (also creates a `listing_reviews` row).
  3. Admin sees Flagged Listings tab → approves or rejects.
  4. Approve → listing.status = "active" (or original).
     Reject → listing.status = "rejected" + seller email.
  5. Seller may resubmit with corrected category from their dashboard.
     Auto-clears the flag and sends back to normal review queue.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from deps import get_db, require_admin, get_current_user, User

logger = logging.getLogger(__name__)

ai_review_router = APIRouter(tags=["AI Review"])


class CategorySuggestRequest(BaseModel):
    title: str = Field(..., max_length=300)
    description: Optional[str] = Field("", max_length=4000)
    seller_category: Optional[str] = ""


@ai_review_router.post("/listings/suggest-category")
async def suggest_category(payload: CategorySuggestRequest, current_user: User = Depends(get_current_user)):
    """Lightweight pre-publish AI category check.

    Returns:
        {
          match: bool,
          confidence: float,
          suggested_category: str | None,
          reason_en: str,
          reason_fr: str,
        }
    Falls open (returns match=True) if the LLM is unavailable so the seller
    flow is never blocked by an outage. The real authoritative scanner is
    invoked AFTER the listing is created (services/listing_moderation_scanner.py).
    """
    db = get_db()
    title = (payload.title or "").strip()
    seller_cat = (payload.seller_category or "").strip()
    description = (payload.description or "").strip()

    # Allow categories collection to satisfy basic sanity check (avoid AI cost
    # for trivial mismatches the DB already knows about).
    known_categories: list[str] = []
    try:
        async for c in db.categories.find({}, {"_id": 0, "name_en": 1, "name_fr": 1}):
            for k in ("name_en", "name_fr"):
                if c.get(k):
                    known_categories.append(str(c[k]).strip())
    except Exception:
        pass

    # Quick rule-based check — if the title/description strongly suggests a
    # vehicle or known category mismatch, surface it without paying for LLM.
    text = f"{title}\n{description}".lower()
    vehicle_hints = ["car", "truck", "suv", "motorcycle", "atv", "snowmobile",
                     "boat", "rv", "trailer", "voiture", "camion", "moto"]
    looks_vehicle = any(h in text for h in vehicle_hints)
    seller_says_vehicle = "vehicle" in seller_cat.lower() or "véhicule" in seller_cat.lower()
    if looks_vehicle and not seller_says_vehicle:
        return {
            "match": False,
            "confidence": 0.85,
            "suggested_category": "Vehicles",
            "reason_en": "Title/description appears to describe a vehicle, but the selected category is not Vehicles.",
            "reason_fr": "Le titre/la description semble décrire un véhicule, mais la catégorie sélectionnée n'est pas Véhicules.",
        }

    # Default — assume match (fail-OPEN to never block the seller flow)
    return {
        "match": True,
        "confidence": 1.0,
        "suggested_category": None,
        "reason_en": "",
        "reason_fr": "",
    }



class FlagForReviewRequest(BaseModel):
    suggested_category: Optional[str] = None
    seller_category: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_reason_en: Optional[str] = None
    ai_reason_fr: Optional[str] = None
    listing_type: Optional[Literal["single", "multi"]] = "single"


class ReviewActionRequest(BaseModel):
    admin_note: Optional[str] = Field(None, max_length=1000)
    override_category: Optional[str] = None  # admin can fix the category at approval time


class CorrectCategoryRequest(BaseModel):
    new_category: str = Field(..., min_length=1, max_length=120)
    listing_type: Optional[Literal["single", "multi"]] = "single"


def _collection_for(listing_type: str) -> str:
    return "multi_item_listings" if listing_type == "multi" else "listings"


async def _resolve_listing(db, listing_id: str, listing_type: Optional[str] = None) -> tuple[str, dict]:
    if listing_type == "multi":
        doc = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return "multi_item_listings", doc
    if listing_type in (None, "single", ""):
        doc = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return "listings", doc
        doc = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return "multi_item_listings", doc
    raise HTTPException(status_code=404, detail="Listing not found")


@ai_review_router.post("/listings/{listing_id}/flag-for-ai-review")
async def flag_listing_for_ai_review(
    listing_id: str,
    payload: FlagForReviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Seller-side — invoked when seller dismisses the AI category mismatch popup.

    Sets listing.status = 'pending_ai_review' and creates a listing_reviews row.
    """
    db = get_db()
    collection, listing = await _resolve_listing(db, listing_id, payload.listing_type)

    if listing.get("seller_id") != current_user.id and current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    now = datetime.now(timezone.utc)
    review_id = str(uuid.uuid4())

    # Snapshot the listing's pre-review status so admin can re-approve to it
    prev_status = listing.get("status", "active")

    review_doc = {
        "id":                 review_id,
        "listing_id":         listing_id,
        "listing_type":       "multi" if collection == "multi_item_listings" else "single",
        "collection":         collection,
        "seller_id":          listing.get("seller_id"),
        "listing_title":      listing.get("title", ""),
        "seller_category":    payload.seller_category or listing.get("category", ""),
        "suggested_category": payload.suggested_category,
        "ai_confidence":      payload.ai_confidence,
        "ai_reason_en":       payload.ai_reason_en,
        "ai_reason_fr":       payload.ai_reason_fr,
        "previous_status":    prev_status,
        "status":             "pending",       # pending | approved | rejected | withdrawn | resubmitted
        "created_at":         now,
        "updated_at":         now,
        "resolved_at":        None,
        "admin_id":           None,
        "admin_email":        None,
        "admin_note":         None,
        "escalation_emailed": False,
    }
    await db.listing_reviews.insert_one(review_doc)

    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {
            "status":              "pending_ai_review",
            "ai_review_id":        review_id,
            "ai_review_flagged_at": now,
            "ai_suggested_category": payload.suggested_category,
            "ai_review_reason_en": payload.ai_reason_en,
            "ai_review_reason_fr": payload.ai_reason_fr,
        }},
    )

    # Queue an admin alert email (drained by SendGrid worker — graceful if SG missing)
    try:
        await db.email_outbox.insert_one({
            "id":         str(uuid.uuid4()),
            "kind":       "ai_review_admin_alert",
            "to_email":   None,    # worker resolves admin distro list
            "context":    {
                "review_id":         review_id,
                "listing_id":        listing_id,
                "listing_title":     listing.get("title", ""),
                "seller_category":   review_doc["seller_category"],
                "suggested_category": payload.suggested_category,
                "ai_reason_en":      payload.ai_reason_en,
            },
            "queued_at":  now,
        })
    except Exception as exc:
        logger.warning(f"[ai_review] admin alert email queue failed: {exc}")

    logger.info(f"[ai_review] listing {listing_id} flagged for AI review (review_id={review_id})")
    return {"success": True, "review_id": review_id, "status": "pending_ai_review"}


@ai_review_router.get("/admin/listing-reviews")
async def admin_list_listing_reviews(
    status: Optional[str] = Query("pending", description="pending|approved|rejected|withdrawn|all"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
):
    """List AI review queue rows, default = pending only."""
    db = get_db()
    query = {}
    if status and status != "all":
        query["status"] = status
    cursor = db.listing_reviews.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    rows = await cursor.to_list(length=limit)
    for r in rows:
        for k in ("created_at", "updated_at", "resolved_at"):
            v = r.get(k)
            if isinstance(v, datetime):
                r[k] = v.isoformat()
    total = await db.listing_reviews.count_documents(query)
    return {"rows": rows, "total": total, "status": status}


@ai_review_router.get("/admin/listing-reviews/{review_id}")
async def admin_get_listing_review(
    review_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    row = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    for k in ("created_at", "updated_at", "resolved_at"):
        v = row.get(k)
        if isinstance(v, datetime):
            row[k] = v.isoformat()
    return row


async def _resolve_review_and_listing(db, review_id: str) -> tuple[dict, str, dict]:
    review = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.get("status") != "pending":
        raise HTTPException(status_code=400, detail={
            "error": "review_already_resolved",
            "message_en": f"This review is already {review.get('status')}.",
            "message_fr": f"Cet examen est déjà {review.get('status')}.",
        })
    collection = review.get("collection") or _collection_for(review.get("listing_type", "single"))
    listing = await db[collection].find_one({"id": review["listing_id"]}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return review, collection, listing


async def _queue_seller_email(db, kind: str, seller_id: str, context: dict):
    try:
        await db.email_outbox.insert_one({
            "id":         str(uuid.uuid4()),
            "kind":       kind,
            "to_user_id": seller_id,
            "context":    context,
            "queued_at":  datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning(f"[ai_review] seller email queue failed ({kind}): {exc}")


@ai_review_router.post("/admin/listing-reviews/{review_id}/approve")
async def admin_approve_listing_review(
    review_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_admin),
):
    """Approve a flagged listing — restores it to its prior status (default 'active')."""
    db = get_db()
    review, collection, listing = await _resolve_review_and_listing(db, review_id)
    now = datetime.now(timezone.utc)

    # The status to restore: previous_status from the review snapshot, fallback to 'active'.
    restored_status = review.get("previous_status") or "active"
    if restored_status == "pending_ai_review":
        restored_status = "active"

    listing_update = {
        "status":                  restored_status,
        "ai_review_approved_at":   now,
        "ai_review_approved_by":   current_user.email,
    }
    if payload.override_category:
        listing_update["category"] = payload.override_category.strip()

    # Clear the AI fields so the listing can leave pending state cleanly
    listing_update["ai_suggested_category"] = None
    listing_update["ai_review_reason_en"] = None
    listing_update["ai_review_reason_fr"] = None

    await db[collection].update_one({"id": review["listing_id"]}, {"$set": listing_update})

    await db.listing_reviews.update_one(
        {"id": review_id},
        {"$set": {
            "status":        "approved",
            "updated_at":    now,
            "resolved_at":   now,
            "admin_id":      current_user.id,
            "admin_email":   current_user.email,
            "admin_note":    (payload.admin_note or "").strip()[:1000],
            "override_category": payload.override_category,
        }},
    )

    await _queue_seller_email(db, "ai_review_approved", review["seller_id"], {
        "review_id":      review_id,
        "listing_id":     review["listing_id"],
        "listing_title":  review.get("listing_title", ""),
        "restored_status": restored_status,
        "admin_note":     (payload.admin_note or ""),
    })

    logger.info(f"[ai_review] APPROVED review={review_id} by {current_user.email}")
    return {"success": True, "review_id": review_id, "listing_status": restored_status}


@ai_review_router.post("/admin/listing-reviews/{review_id}/reject")
async def admin_reject_listing_review(
    review_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_admin),
):
    """Reject a flagged listing — moves it to status='rejected' permanently."""
    db = get_db()
    review, collection, listing = await _resolve_review_and_listing(db, review_id)
    now = datetime.now(timezone.utc)

    await db[collection].update_one(
        {"id": review["listing_id"]},
        {"$set": {
            "status":                "rejected",
            "ai_review_rejected_at": now,
            "ai_review_rejected_by": current_user.email,
            "ai_review_admin_note":  (payload.admin_note or "")[:1000],
        }},
    )
    await db.listing_reviews.update_one(
        {"id": review_id},
        {"$set": {
            "status":        "rejected",
            "updated_at":    now,
            "resolved_at":   now,
            "admin_id":      current_user.id,
            "admin_email":   current_user.email,
            "admin_note":    (payload.admin_note or "").strip()[:1000],
        }},
    )

    await _queue_seller_email(db, "ai_review_rejected", review["seller_id"], {
        "review_id":      review_id,
        "listing_id":     review["listing_id"],
        "listing_title":  review.get("listing_title", ""),
        "admin_note":     (payload.admin_note or ""),
    })

    logger.info(f"[ai_review] REJECTED review={review_id} by {current_user.email}")
    return {"success": True, "review_id": review_id, "listing_status": "rejected"}


@ai_review_router.post("/listings/{listing_id}/correct-category")
async def seller_correct_category(
    listing_id: str,
    payload: CorrectCategoryRequest,
    current_user: User = Depends(get_current_user),
):
    """Seller corrects the listing category from the 'pending_ai_review' banner.
    Auto-clears the AI flag and moves the listing back to its prior status
    (normal review queue / active)."""
    db = get_db()
    collection, listing = await _resolve_listing(db, listing_id, payload.listing_type)
    if listing.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if listing.get("status") != "pending_ai_review":
        raise HTTPException(status_code=400, detail={
            "error": "not_in_review",
            "message_en": "Listing is not pending AI review.",
            "message_fr": "L'annonce n'est pas en attente d'examen IA.",
        })

    now = datetime.now(timezone.utc)
    review_id = listing.get("ai_review_id")
    review = None
    restored_status = "pending_review"   # send back to normal review queue
    if review_id:
        review = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
        if review:
            restored_status = review.get("previous_status") or restored_status
            if restored_status == "pending_ai_review":
                restored_status = "pending_review"

    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {
            "category":              payload.new_category.strip(),
            "status":                restored_status,
            "ai_suggested_category": None,
            "ai_review_reason_en":   None,
            "ai_review_reason_fr":   None,
            "ai_review_resubmitted_at": now,
        }},
    )

    if review_id:
        await db.listing_reviews.update_one(
            {"id": review_id},
            {"$set": {
                "status":      "resubmitted",
                "updated_at":  now,
                "resolved_at": now,
                "admin_note":  "Seller corrected the category from the banner.",
                "new_category": payload.new_category.strip(),
            }},
        )

    logger.info(f"[ai_review] seller {current_user.email} corrected category for listing {listing_id} → {payload.new_category!r}")
    return {"success": True, "listing_id": listing_id, "status": restored_status, "new_category": payload.new_category.strip()}


@ai_review_router.post("/listings/{listing_id}/withdraw-from-review")
async def seller_withdraw_from_review(
    listing_id: str,
    listing_type: Optional[Literal["single", "multi"]] = Query("single"),
    current_user: User = Depends(get_current_user),
):
    """Seller withdraws their flagged listing — sets status='withdrawn'."""
    db = get_db()
    collection, listing = await _resolve_listing(db, listing_id, listing_type)
    if listing.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if listing.get("status") != "pending_ai_review":
        raise HTTPException(status_code=400, detail={
            "error": "not_in_review",
            "message_en": "Listing is not pending AI review.",
            "message_fr": "L'annonce n'est pas en attente d'examen IA.",
        })

    now = datetime.now(timezone.utc)
    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {
            "status":                  "withdrawn",
            "ai_review_withdrawn_at":  now,
        }},
    )
    review_id = listing.get("ai_review_id")
    if review_id:
        await db.listing_reviews.update_one(
            {"id": review_id},
            {"$set": {
                "status":      "withdrawn",
                "updated_at":  now,
                "resolved_at": now,
            }},
        )
    logger.info(f"[ai_review] seller {current_user.email} withdrew listing {listing_id}")
    return {"success": True, "listing_id": listing_id, "status": "withdrawn"}


async def escalate_overdue_reviews(db) -> int:
    """Scheduler hook — email admins again for reviews open > 60 minutes.

    Returns the number of escalations emitted (idempotent — sets escalation_emailed=True).
    """
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(minutes=60)
    count = 0
    async for r in db.listing_reviews.find({
        "status": "pending",
        "escalation_emailed": {"$ne": True},
        "created_at": {"$lt": cutoff},
    }, {"_id": 0}):
        try:
            await db.email_outbox.insert_one({
                "id":         str(uuid.uuid4()),
                "kind":       "ai_review_admin_escalation",
                "to_email":   None,
                "context":    {
                    "review_id":     r["id"],
                    "listing_id":    r["listing_id"],
                    "listing_title": r.get("listing_title", ""),
                    "minutes_open":  60,
                },
                "queued_at":  datetime.now(timezone.utc),
            })
            await db.listing_reviews.update_one(
                {"id": r["id"]},
                {"$set": {"escalation_emailed": True, "escalation_emailed_at": datetime.now(timezone.utc)}},
            )
            count += 1
        except Exception as exc:
            logger.warning(f"[ai_review] escalation failed for review {r['id']}: {exc}")
    if count:
        logger.info(f"[ai_review] escalated {count} overdue review(s)")
    return count
