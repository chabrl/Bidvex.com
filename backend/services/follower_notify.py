"""
services/follower_notify.py — iter300 P2 "Follow Seller"

Fan-out to a seller's followers when they post a NEW listing that is
publicly visible (status=active). Called from:
  • routes/listings.py        (single + multi create, when active)
  • routes/admin_moderation.py (approve: pending_review → active)

Each follower gets a bilingual platform notification + email:
  "[Seller] just listed [title] — bid now"
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

_MAX_FANOUT = 500  # safety cap per listing


def listing_public_url(section: str, listing_id: str) -> str:
    return {
        "marketplace": f"/listing/{listing_id}",
        "lots": f"/lots/{listing_id}",
        "vehicles": f"/vehicles/{listing_id}",
        "storage": f"/storage-auctions/{listing_id}",
    }.get(section, f"/listing/{listing_id}")


async def notify_followers(db, *, seller_id: str, listing_id: str,
                           listing_title: str, section: str = "marketplace") -> Dict[str, Any]:
    """Never raises — fan-out failures must not block listing creation."""
    out = {"followers": 0, "notified": 0, "emails": 0}
    try:
        seller = await db.users.find_one(
            {"id": seller_id}, {"_id": 0, "name": 1, "company_name": 1})
        seller_name = (seller or {}).get("name") or (seller or {}).get("company_name") or "A seller you follow"
        url_path = listing_public_url(section, listing_id)

        follows = await db.seller_follows.find(
            {"seller_id": seller_id}, {"_id": 0, "follower_id": 1},
        ).to_list(_MAX_FANOUT)
        out["followers"] = len(follows)
        if not follows:
            return out

        from services.notifications_i18n import create_notification
        for f in follows:
            fid = f.get("follower_id")
            if not fid or fid == seller_id:
                continue
            try:
                await create_notification(
                    db, user_id=fid, kind="followed_seller_new_listing",
                    params={"seller_name": seller_name, "title": listing_title},
                    data={"listing_id": listing_id, "section": section,
                          "action_url": url_path})
                out["notified"] += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[follow-notify] notif failed for {fid}: {e}")

            follower = await db.users.find_one(
                {"id": fid}, {"_id": 0, "email": 1, "name": 1})
            if follower and follower.get("email"):
                try:
                    from services.emails.email_engagement import (
                        send_followed_seller_new_listing_email,
                    )
                    await send_followed_seller_new_listing_email(
                        to_email=follower["email"],
                        to_name=follower.get("name") or "Bidder",
                        seller_name=seller_name,
                        listing_title=listing_title,
                        url_path=url_path)
                    out["emails"] += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[follow-notify] email failed for {fid}: {e}")
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[follow-notify] fan-out failed for {listing_id}: {e}")
        return out
