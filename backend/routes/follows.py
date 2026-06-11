"""
routes/follows.py — iter300 P2 "Follow Seller"

  POST   /api/sellers/{seller_id}/follow          (auth)   follow
  DELETE /api/sellers/{seller_id}/follow          (auth)   unfollow
  GET    /api/sellers/{seller_id}/follow-status   (opt.)   {following, followers_count}
  GET    /api/me/followed-sellers                 (auth)   enriched list for the buyer dashboard

Collection: `seller_follows` {id, seller_id, follower_id, created_at}
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import User, get_current_user, get_current_user_optional, get_db

logger = logging.getLogger(__name__)
follows_router = APIRouter(tags=["follows"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@follows_router.post("/sellers/{seller_id}/follow")
async def follow_seller(seller_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    if seller_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself")
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "id": 1})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    await db.seller_follows.update_one(
        {"seller_id": seller_id, "follower_id": current_user.id},
        {"$setOnInsert": {"id": str(uuid.uuid4()),
                          "seller_id": seller_id,
                          "follower_id": current_user.id,
                          "created_at": _now_iso()}},
        upsert=True,
    )
    count = await db.seller_follows.count_documents({"seller_id": seller_id})
    return {"success": True, "following": True, "followers_count": count}


@follows_router.delete("/sellers/{seller_id}/follow")
async def unfollow_seller(seller_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    await db.seller_follows.delete_one(
        {"seller_id": seller_id, "follower_id": current_user.id})
    count = await db.seller_follows.count_documents({"seller_id": seller_id})
    return {"success": True, "following": False, "followers_count": count}


@follows_router.get("/sellers/{seller_id}/follow-status")
async def follow_status(seller_id: str,
                        current_user: Optional[User] = Depends(get_current_user_optional)):
    db = get_db()
    count = await db.seller_follows.count_documents({"seller_id": seller_id})
    following = False
    if current_user:
        following = bool(await db.seller_follows.find_one(
            {"seller_id": seller_id, "follower_id": current_user.id}, {"_id": 1}))
    return {"following": following, "followers_count": count}


@follows_router.get("/me/followed-sellers")
async def my_followed_sellers(current_user: User = Depends(get_current_user)):
    db = get_db()
    follows = await db.seller_follows.find(
        {"follower_id": current_user.id}, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    seller_ids = [f["seller_id"] for f in follows]
    sellers = {}
    if seller_ids:
        async for u in db.users.find(
            {"id": {"$in": seller_ids}},
            {"_id": 0, "id": 1, "name": 1, "company_name": 1, "picture": 1,
             "is_top_seller": 1, "subscription_tier": 1},
        ):
            sellers[u["id"]] = u
    rows = []
    for f in follows:
        s = sellers.get(f["seller_id"]) or {}
        active = await db.listings.count_documents(
            {"seller_id": f["seller_id"], "status": "active"})
        rows.append({
            "seller_id": f["seller_id"],
            "followed_at": f.get("created_at"),
            "name": s.get("name") or s.get("company_name") or "Seller",
            "picture": s.get("picture"),
            "is_top_seller": bool(s.get("is_top_seller")),
            "active_listings": active,
        })
    return {"sellers": rows, "total": len(rows)}
