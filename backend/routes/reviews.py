"""
BidVex Post-Purchase Review System
Handles review creation, seller reputation, and admin moderation.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
import logging
import re
import uuid
import jwt
import os

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
reviews_router = APIRouter(prefix="/reviews", tags=["Reviews"])

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
_db = None


def set_reviews_db(db_instance):
    global _db
    _db = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


async def _get_current_user(credentials):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        db = get_db()
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _sanitize_text(text: str) -> str:
    clean = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', clean).strip()


def _make_display_name(name: str) -> str:
    if not name:
        return "Anonymous"
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


async def recalculate_seller_reputation(db, seller_id: str):
    """Recalculate and cache seller reputation from all active reviews."""
    pipeline = [
        {"$match": {"seller_id": seller_id, "status": "active"}},
        {"$group": {
            "_id": None,
            "avg_rating": {"$avg": "$rating"},
            "total": {"$sum": 1},
            "avg_item_accuracy": {"$avg": "$item_accuracy"},
            "avg_communication": {"$avg": "$communication"},
            "avg_shipping_speed": {"$avg": "$shipping_speed"},
            "star_1": {"$sum": {"$cond": [{"$eq": ["$rating", 1]}, 1, 0]}},
            "star_2": {"$sum": {"$cond": [{"$eq": ["$rating", 2]}, 1, 0]}},
            "star_3": {"$sum": {"$cond": [{"$eq": ["$rating", 3]}, 1, 0]}},
            "star_4": {"$sum": {"$cond": [{"$eq": ["$rating", 4]}, 1, 0]}},
            "star_5": {"$sum": {"$cond": [{"$eq": ["$rating", 5]}, 1, 0]}},
        }}
    ]

    result = await db.reviews.aggregate(pipeline).to_list(1)

    if not result:
        rep = {
            "seller_id": seller_id,
            "average_rating": 0,
            "total_reviews": 0,
            "rating_breakdown": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
            "category_averages": {},
            "badge": "new_seller",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    else:
        r = result[0]
        total = r["total"]
        avg = round(r["avg_rating"], 2)

        if avg >= 4.7 and total >= 25:
            badge = "top_rated"
        elif avg >= 4.0 and total >= 10:
            badge = "trusted_seller"
        else:
            badge = "new_seller"

        cat_avgs = {}
        if r["avg_item_accuracy"] is not None:
            cat_avgs["item_accuracy"] = round(r["avg_item_accuracy"], 2)
        if r["avg_communication"] is not None:
            cat_avgs["communication"] = round(r["avg_communication"], 2)
        if r["avg_shipping_speed"] is not None:
            cat_avgs["shipping_speed"] = round(r["avg_shipping_speed"], 2)

        rep = {
            "seller_id": seller_id,
            "average_rating": avg,
            "total_reviews": total,
            "rating_breakdown": {
                "1": r["star_1"], "2": r["star_2"], "3": r["star_3"],
                "4": r["star_4"], "5": r["star_5"],
            },
            "category_averages": cat_avgs,
            "badge": badge,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    await db.seller_reputation.update_one(
        {"seller_id": seller_id}, {"$set": rep}, upsert=True
    )
    return rep


# ===== Request Models =====

class CreateReviewRequest(BaseModel):
    transaction_id: str
    rating: int = Field(..., ge=1, le=5)
    item_accuracy: Optional[int] = Field(None, ge=1, le=5)
    communication: Optional[int] = Field(None, ge=1, le=5)
    shipping_speed: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, min_length=20, max_length=500)


class UpdateReviewRequest(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    item_accuracy: Optional[int] = Field(None, ge=1, le=5)
    communication: Optional[int] = Field(None, ge=1, le=5)
    shipping_speed: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, min_length=20, max_length=500)


# ===== Endpoints =====

@reviews_router.get("/details/{transaction_id}")
async def get_review_details(
    transaction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get transaction details for the review form, plus existing review if any."""
    user = await _get_current_user(credentials)
    db = get_db()

    item_title = ""
    item_image = ""
    seller_name = ""
    seller_id = ""
    purchase_date = ""
    amount = 0

    # Search all transaction types
    # 1. Buy Now transactions
    bn = await db.buy_now_transactions.find_one(
        {"id": transaction_id, "buyer_id": user["id"]}, {"_id": 0}
    )
    if bn:
        auction = await db.multi_item_listings.find_one({"id": bn["auction_id"]}, {"_id": 0})
        if auction:
            lot = next((l for l in auction.get("lots", []) if l["lot_number"] == bn.get("lot_number")), None)
            item_title = lot.get("title", auction.get("title", "Item")) if lot else auction.get("title", "Item")
            item_image = (lot.get("images", []) or auction.get("images", []) or [""])[0] if lot else (auction.get("images", []) or [""])[0]
            seller = await db.users.find_one({"id": auction["seller_id"]}, {"_id": 0})
            seller_name = seller.get("name", "") if seller else ""
            seller_id = auction["seller_id"]
        purchase_date = bn.get("transaction_date", "")
        amount = bn.get("buyer_total", bn.get("total_amount", 0))
        if bn.get("payment_status") != "paid":
            raise HTTPException(status_code=400, detail="Payment must be confirmed before reviewing")

    # 2. Auction winner (listings with winner_id)
    if not bn:
        listing = await db.listings.find_one(
            {"id": transaction_id, "winner_id": user["id"], "payment_status": "paid"}, {"_id": 0}
        )
        if listing:
            item_title = listing.get("title", "Item")
            item_image = (listing.get("images", []) or [""])[0]
            seller = await db.users.find_one({"id": listing["seller_id"]}, {"_id": 0})
            seller_name = seller.get("name", "") if seller else ""
            seller_id = listing["seller_id"]
            purchase_date = listing.get("paid_at", listing.get("ended_at", ""))
            amount = listing.get("final_price", 0)

    if not item_title and not bn:
        raise HTTPException(status_code=404, detail="Transaction not found or you are not the buyer")

    existing_review = await db.reviews.find_one(
        {"transaction_id": transaction_id, "buyer_id": user["id"]}, {"_id": 0}
    )

    return {
        "item_title": item_title,
        "item_image": item_image,
        "seller_name": seller_name,
        "seller_id": seller_id,
        "purchase_date": purchase_date,
        "amount": amount,
        "existing_review": existing_review,
    }


@reviews_router.post("/create")
async def create_review(
    data: CreateReviewRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a review for a completed paid transaction."""
    user = await _get_current_user(credentials)
    db = get_db()

    # Rate limit: 10 reviews per user per hour
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    recent_count = await db.reviews.count_documents({
        "buyer_id": user["id"], "created_at": {"$gte": one_hour_ago}
    })
    if recent_count >= 10:
        raise HTTPException(status_code=429, detail="Rate limit: max 10 reviews per hour")

    # Find the transaction and verify ownership + paid status
    seller_id = None
    listing_id = None

    # Check buy_now_transactions
    bn = await db.buy_now_transactions.find_one(
        {"id": data.transaction_id, "payment_status": "paid"}, {"_id": 0}
    )
    if bn:
        if bn["buyer_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="You can only review your own purchases")
        auction = await db.multi_item_listings.find_one({"id": bn["auction_id"]}, {"_id": 0})
        if auction:
            seller_id = auction["seller_id"]
            listing_id = bn["auction_id"]

    # Check auction winner (listings)
    if not seller_id:
        listing = await db.listings.find_one(
            {"id": data.transaction_id, "winner_id": user["id"], "payment_status": "paid"}, {"_id": 0}
        )
        if listing:
            seller_id = listing["seller_id"]
            listing_id = listing["id"]

    if not seller_id:
        raise HTTPException(status_code=404, detail="No completed paid transaction found with this ID")

    if seller_id == user["id"]:
        raise HTTPException(status_code=400, detail="You cannot review yourself")

    # Check for duplicate
    existing = await db.reviews.find_one(
        {"transaction_id": data.transaction_id, "buyer_id": user["id"]}, {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this transaction")

    comment = _sanitize_text(data.comment) if data.comment else None
    now = datetime.now(timezone.utc)

    review = {
        "id": str(uuid.uuid4()),
        "transaction_id": data.transaction_id,
        "listing_id": listing_id,
        "buyer_id": user["id"],
        "seller_id": seller_id,
        "rating": data.rating,
        "item_accuracy": data.item_accuracy,
        "communication": data.communication,
        "shipping_speed": data.shipping_speed,
        "comment": comment,
        "buyer_display_name": _make_display_name(user.get("name", "")),
        "buyer_avatar": user.get("avatar_url"),
        "status": "active",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "editable_until": (now + timedelta(hours=48)).isoformat(),
    }

    await db.reviews.insert_one(review)

    # Recalculate reputation
    reputation = await recalculate_seller_reputation(db, seller_id)

    # Notify seller (in-app + email)
    try:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": seller_id,
            "type": "new_review",
            "title": "New Review Received",
            "message": f"{review['buyer_display_name']} left a {data.rating}-star review",
            "data": {"review_id": review["id"], "rating": data.rating},
            "read": False,
            "created_at": now.isoformat(),
        })
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0})
        if seller and seller.get("email"):
            from services.email_notifications import send_email, _base_template
            stars = "&#9733;" * data.rating + "&#9734;" * (5 - data.rating)
            html = f"""
            <h2 style="margin: 0 0 20px 0; color: #1e3a8a;">New Review Received</h2>
            <p>Hi {seller.get('name', 'Seller')},</p>
            <p>{review['buyer_display_name']} left you a review:</p>
            <div style="background: #fef3c7; padding: 16px; border-radius: 8px; text-align: center; margin: 20px 0;">
                <p style="font-size: 28px; margin: 0;">{stars}</p>
                <p style="font-size: 18px; font-weight: bold; margin: 8px 0;">{data.rating}/5 Stars</p>
            </div>
            """
            if comment:
                html += f'<blockquote style="border-left: 3px solid #ddd; padding-left: 16px; color: #555;">&ldquo;{comment}&rdquo;</blockquote>'
            await send_email(
                to_email=seller["email"],
                subject=f"New {data.rating}-Star Review from {review['buyer_display_name']}",
                html_content=_base_template(html, "New Review"),
            )
    except Exception as e:
        logger.warning(f"Failed to notify seller about review: {e}")

    review.pop("_id", None)
    return {"success": True, "review": review, "reputation": reputation}


@reviews_router.put("/{review_id}")
async def update_review(
    review_id: str,
    data: UpdateReviewRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a review within the 48h edit window."""
    user = await _get_current_user(credentials)
    db = get_db()

    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review["buyer_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You can only edit your own reviews")

    editable_until = datetime.fromisoformat(review["editable_until"])
    if datetime.now(timezone.utc) > editable_until:
        raise HTTPException(status_code=400, detail="Review can no longer be edited (48h window expired)")

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.rating is not None:
        update_fields["rating"] = data.rating
    if data.item_accuracy is not None:
        update_fields["item_accuracy"] = data.item_accuracy
    if data.communication is not None:
        update_fields["communication"] = data.communication
    if data.shipping_speed is not None:
        update_fields["shipping_speed"] = data.shipping_speed
    if data.comment is not None:
        update_fields["comment"] = _sanitize_text(data.comment)

    await db.reviews.update_one({"id": review_id}, {"$set": update_fields})
    await recalculate_seller_reputation(db, review["seller_id"])

    updated = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    return {"success": True, "review": updated}


@reviews_router.get("/seller/{seller_id}")
async def get_seller_reviews(
    seller_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    """Get paginated reviews for a seller (public)."""
    db = get_db()
    skip = (page - 1) * limit

    reviews = await db.reviews.find(
        {"seller_id": seller_id, "status": "active"}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    total = await db.reviews.count_documents({"seller_id": seller_id, "status": "active"})

    return {
        "reviews": reviews,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total + limit - 1) // limit),
    }


@reviews_router.get("/transaction/{transaction_id}")
async def get_transaction_review(transaction_id: str):
    """Get review for a specific transaction (public)."""
    db = get_db()
    review = await db.reviews.find_one(
        {"transaction_id": transaction_id, "status": {"$ne": "removed"}}, {"_id": 0}
    )
    return {"review": review}


@reviews_router.get("/reputation/{seller_id}")
async def get_seller_reputation(seller_id: str):
    """Get seller reputation score and badge (public)."""
    db = get_db()
    rep = await db.seller_reputation.find_one({"seller_id": seller_id}, {"_id": 0})
    if not rep:
        rep = await recalculate_seller_reputation(db, seller_id)

    # Hide exact score if fewer than 3 reviews
    if rep["total_reviews"] < 3:
        rep["average_rating_display"] = None
        rep["badge"] = "new_seller"
    else:
        rep["average_rating_display"] = rep["average_rating"]

    return rep


@reviews_router.post("/reputation/batch")
async def get_batch_reputations(data: Dict):
    """Get reputations for multiple sellers at once (for listing cards)."""
    db = get_db()
    seller_ids = data.get("seller_ids", [])
    if not seller_ids or len(seller_ids) > 50:
        raise HTTPException(status_code=400, detail="Provide 1-50 seller IDs")

    reps = await db.seller_reputation.find(
        {"seller_id": {"$in": seller_ids}}, {"_id": 0}
    ).to_list(50)

    result = {}
    found_ids = set()
    for rep in reps:
        sid = rep["seller_id"]
        found_ids.add(sid)
        if rep["total_reviews"] < 3:
            rep["average_rating_display"] = None
            rep["badge"] = "new_seller"
        else:
            rep["average_rating_display"] = rep["average_rating"]
        result[sid] = rep

    # Fill missing with defaults
    for sid in seller_ids:
        if sid not in found_ids:
            result[sid] = {
                "seller_id": sid,
                "average_rating": 0,
                "average_rating_display": None,
                "total_reviews": 0,
                "badge": "new_seller",
            }

    return {"reputations": result}


# ===== Admin Moderation =====

@reviews_router.delete("/{review_id}")
async def admin_remove_review(
    review_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Permanently remove a review."""
    user = await _get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await db.reviews.update_one(
        {"id": review_id},
        {"$set": {
            "status": "removed",
            "removed_at": datetime.now(timezone.utc).isoformat(),
            "removed_by": user["id"],
        }}
    )
    await recalculate_seller_reputation(db, review["seller_id"])
    return {"success": True, "message": "Review removed"}


@reviews_router.post("/{review_id}/flag")
async def admin_flag_review(
    review_id: str,
    data: Dict,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Flag a review (hidden pending decision)."""
    user = await _get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await db.reviews.update_one(
        {"id": review_id},
        {"$set": {
            "status": "flagged",
            "flagged_reason": data.get("reason", "No reason provided"),
            "flagged_at": datetime.now(timezone.utc).isoformat(),
            "flagged_by": user["id"],
        }}
    )
    await recalculate_seller_reputation(db, review["seller_id"])
    return {"success": True, "message": "Review flagged"}


@reviews_router.post("/{review_id}/unflag")
async def admin_unflag_review(
    review_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Restore a flagged review."""
    user = await _get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await db.reviews.update_one(
        {"id": review_id},
        {"$set": {"status": "active"},
         "$unset": {"flagged_reason": "", "flagged_at": "", "flagged_by": ""}}
    )
    await recalculate_seller_reputation(db, review["seller_id"])
    return {"success": True, "message": "Review restored"}


@reviews_router.get("/moderation/pending")
async def get_flagged_reviews(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
):
    """Admin: List all flagged reviews for moderation."""
    user = await _get_current_user(credentials)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    skip = (page - 1) * limit

    reviews = await db.reviews.find(
        {"status": "flagged"}, {"_id": 0}
    ).sort("flagged_at", -1).skip(skip).limit(limit).to_list(limit)

    total = await db.reviews.count_documents({"status": "flagged"})
    return {"reviews": reviews, "total": total, "page": page}
