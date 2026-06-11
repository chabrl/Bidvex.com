"""
services/top_sellers.py — iter300 P1

Merit-based "Top Seller" badge. The top 5 sellers by ALL-TIME GMV
(same definition as routes/admin_analytics.py) earn `is_top_seller=True`
on their user document. Recalculated nightly by the scheduler — badges
are added/removed automatically as rankings change.

  • Gain  → congratulatory email + bilingual platform notification
  • Loss  → silent removal (no notification, per spec)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_COLLECTIONS = ["listings", "multi_item_listings", "vehicle_listings", "storage_auctions"]


def _is_sold(doc: Dict[str, Any]) -> bool:
    if doc.get("status") == "sold":
        return True
    return doc.get("status") in ("ended", "completed") and bool(
        doc.get("winner_user_id") or doc.get("winner_id") or doc.get("winning_bidder_id")
    )


def _hammer(doc: Dict[str, Any]) -> float:
    return float(doc.get("final_price") or doc.get("current_price")
                 or doc.get("current_bid") or 0)


async def compute_top_sellers(db, limit: int = 5) -> List[Tuple[str, float]]:
    """Return [(seller_id, gmv), …] for the top `limit` sellers by all-time
    GMV across all four sections. Demo data excluded; GMV must be > 0."""
    seller_gmv: Dict[str, float] = defaultdict(float)
    for coll in _COLLECTIONS:
        docs = await db[coll].find(
            {}, {"_id": 0, "status": 1, "final_price": 1, "current_price": 1,
                 "current_bid": 1, "winner_user_id": 1, "winner_id": 1,
                 "winning_bidder_id": 1, "seller_id": 1, "facility_owner_id": 1,
                 "is_demo": 1, "is_demo_sandbox": 1},
        ).to_list(50000)
        for d in docs:
            if d.get("is_demo") or d.get("is_demo_sandbox"):
                continue
            if _is_sold(d):
                seller = d.get("seller_id") or d.get("facility_owner_id")
                if seller:
                    seller_gmv[seller] += _hammer(d)
    ranked = sorted(seller_gmv.items(), key=lambda kv: kv[1], reverse=True)
    return [(sid, round(gmv, 2)) for sid, gmv in ranked if gmv > 0][:limit]


async def recalculate_top_sellers(db) -> Dict[str, Any]:
    """Nightly job: sync `is_top_seller` flags with the current top-5 GMV
    ranking. Notifies first-time/regained earners; silent on removal."""
    now_iso = datetime.now(timezone.utc).isoformat()
    top = await compute_top_sellers(db, limit=5)
    top_ids = {sid for sid, _ in top}

    currently_flagged = {
        u["id"]
        async for u in db.users.find({"is_top_seller": True}, {"_id": 0, "id": 1})
    }
    gained = top_ids - currently_flagged
    lost = currently_flagged - top_ids

    # ── Silent removal ──
    if lost:
        await db.users.update_many(
            {"id": {"$in": list(lost)}},
            {"$set": {"is_top_seller": False, "top_seller_removed_at": now_iso}})

    # ── Gains: flag + congratulate ──
    notified = 0
    for sid, gmv in top:
        if sid not in gained:
            # already flagged — just refresh the GMV stamp
            await db.users.update_one(
                {"id": sid}, {"$set": {"top_seller_gmv": gmv}})
            continue
        await db.users.update_one(
            {"id": sid},
            {"$set": {"is_top_seller": True, "top_seller_since": now_iso,
                      "top_seller_gmv": gmv}})
        user = await db.users.find_one(
            {"id": sid}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1})
        if not user:
            continue
        try:
            from services.notifications_i18n import create_notification
            await create_notification(
                db, user_id=sid, kind="top_seller_earned",
                params={"gmv": gmv},
                data={"action_url": f"/store/{sid}"})
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[top-sellers] notif failed for {sid}: {e}")
        if user.get("email"):
            try:
                from services.emails.email_engagement import send_top_seller_congrats_email
                await send_top_seller_congrats_email(
                    to_email=user["email"],
                    to_name=user.get("name") or "Seller",
                    lang=(user.get("preferred_language") or "en"),
                    store_url_path=f"/store/{sid}")
                notified += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[top-sellers] email failed for {sid}: {e}")

    stats = {"top": [{"seller_id": s, "gmv": g} for s, g in top],
             "gained": len(gained), "lost": len(lost), "emails_sent": notified,
             "ran_at": now_iso}
    logger.info(f"[top-sellers] recalc: {stats}")
    return stats
