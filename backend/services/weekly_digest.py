"""
iter378 — Weekly Marketing Email Digest.

Every Monday morning we ship each user a personalised summary containing:

  1. New listings from sellers they follow (last 7 days).
  2. Watchlist updates — new bid, ends soon, price change.
  3. New listings matching their inferred interests (top categories from
     `user_interests` and watchlisted-item categories in the last 60 days).

Bilingual EN / FR based on `preferred_language` (falls back to
`language_preference`, then EN).

Unsubscribe is handled centrally by `send_email(is_marketing=True)`
which:
  • honours `email_suppressions` global opt-out,
  • honours `email_preferences.marketing == False`,
  • honours legacy `marketing_unsubscribed == True`,
  • injects the List-Unsubscribe headers + CASL footer + manage-
    preferences URL automatically.

Nothing in this module touches SendGrid config, DNS, or existing
transactional templates.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Config knobs (all overridable via env for staging tests).
_LOOKBACK_NEW_LISTINGS_DAYS = int(os.environ.get("WEEKLY_DIGEST_NEW_DAYS", "7"))
_LOOKBACK_INTERESTS_DAYS = int(os.environ.get("WEEKLY_DIGEST_INTEREST_DAYS", "60"))
_MAX_SELLERS_LISTINGS = 5
_MAX_WATCHLIST_ITEMS = 5
_MAX_INTEREST_LISTINGS = 6
_MAX_CATEGORIES = 5
_BATCH_USER_LIMIT = 5000  # safety cap per run
_SEND_CONCURRENCY = 6      # dispatch a few in parallel


FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "https://www.bidvex.com").rstrip("/")


# ────────────────────────────────────────────────────────────────────
#  Data gathering helpers (pure functions on `db`)
# ────────────────────────────────────────────────────────────────────

async def _resolve_user_language(user: Dict[str, Any]) -> str:
    lang = (user.get("preferred_language")
            or user.get("language_preference")
            or "en")
    lang = str(lang).lower().strip()
    return "fr" if lang.startswith("fr") else "en"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_days_ago(days: int) -> str:
    return (_now_utc() - timedelta(days=days)).isoformat()


async def _followed_seller_ids(db, user_id: str) -> List[str]:
    follows = await db.seller_follows.find(
        {"follower_id": user_id}, {"_id": 0, "seller_id": 1},
    ).limit(200).to_list(200)
    return [f["seller_id"] for f in follows if f.get("seller_id")]


async def _new_listings_from_sellers(db, seller_ids: List[str]) -> List[Dict[str, Any]]:
    if not seller_ids:
        return []
    since = _iso_days_ago(_LOOKBACK_NEW_LISTINGS_DAYS)
    rows = await db.listings.find(
        {
            "seller_id": {"$in": seller_ids},
            "status": "active",
            "created_at": {"$gte": since},
        },
        {"_id": 0, "id": 1, "title": 1, "seller_id": 1, "price": 1, "current_bid": 1,
         "starting_price": 1, "image_url": 1, "images": 1, "category": 1,
         "auction_end_time": 1, "created_at": 1},
    ).sort("created_at", -1).limit(_MAX_SELLERS_LISTINGS).to_list(_MAX_SELLERS_LISTINGS)

    # attach seller name for the section headline
    seller_map: Dict[str, str] = {}
    if rows:
        active_seller_ids = list({r["seller_id"] for r in rows if r.get("seller_id")})
        async for u in db.users.find(
            {"id": {"$in": active_seller_ids}},
            {"_id": 0, "id": 1, "name": 1, "company_name": 1},
        ):
            seller_map[u["id"]] = u.get("company_name") or u.get("name") or "Seller"
    for r in rows:
        r["seller_name"] = seller_map.get(r.get("seller_id"), "Seller")
    return rows


async def _watchlist_updates(db, user_id: str) -> List[Dict[str, Any]]:
    """Return the buyer's watchlisted lots that are still active, enriched
    with the latest price + a 'time_remaining' hint for the digest card.
    """
    watch_rows = await db.watchlist.find(
        {"user_id": user_id}, {"_id": 0, "listing_id": 1, "created_at": 1},
    ).sort("created_at", -1).limit(_MAX_WATCHLIST_ITEMS * 3).to_list(_MAX_WATCHLIST_ITEMS * 3)
    if not watch_rows:
        return []
    listing_ids = [w["listing_id"] for w in watch_rows if w.get("listing_id")]
    if not listing_ids:
        return []
    active = await db.listings.find(
        {"id": {"$in": listing_ids}, "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "current_bid": 1, "starting_price": 1,
         "auction_end_time": 1, "image_url": 1, "images": 1, "category": 1,
         "bid_count": 1},
    ).to_list(len(listing_ids))
    by_id = {a["id"]: a for a in active}
    # Preserve watchlist ordering, keep only active ones, cap the count.
    ordered: List[Dict[str, Any]] = []
    now = _now_utc()
    for w in watch_rows:
        item = by_id.get(w.get("listing_id"))
        if not item:
            continue
        # Compute a friendly `time_remaining` for the template.
        try:
            end = item.get("auction_end_time")
            if isinstance(end, str):
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            elif isinstance(end, datetime):
                end_dt = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
            else:
                end_dt = None
        except Exception:
            end_dt = None
        secs = int((end_dt - now).total_seconds()) if end_dt else 0
        item["ends_in_seconds"] = max(0, secs)
        ordered.append(item)
        if len(ordered) >= _MAX_WATCHLIST_ITEMS:
            break
    return ordered


async def _top_interest_categories(db, user_id: str) -> List[str]:
    """Return up to _MAX_CATEGORIES categories the user has shown interest
    in — derived from `user_interests` events + their watchlist items."""
    pipeline = [
        {"$match": {
            "user_id": user_id,
            "created_at": {"$gte": _iso_days_ago(_LOOKBACK_INTERESTS_DAYS)},
            "category": {"$exists": True, "$ne": None},
        }},
        {"$group": {"_id": "$category", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": _MAX_CATEGORIES},
    ]
    cats: List[str] = []
    try:
        async for r in db.user_interests.aggregate(pipeline):
            if r.get("_id"):
                cats.append(str(r["_id"]))
    except Exception as e:
        logger.warning(f"weekly_digest: user_interests aggregation failed: {e}")

    if len(cats) < _MAX_CATEGORIES:
        # Fallback / augment via watchlist item categories.
        watch = await db.watchlist.find(
            {"user_id": user_id}, {"_id": 0, "listing_id": 1},
        ).limit(50).to_list(50)
        wl_ids = [w["listing_id"] for w in watch if w.get("listing_id")]
        if wl_ids:
            async for l in db.listings.find(
                {"id": {"$in": wl_ids}}, {"_id": 0, "category": 1},
            ):
                c = l.get("category")
                if c and c not in cats:
                    cats.append(str(c))
                    if len(cats) >= _MAX_CATEGORIES:
                        break
    return cats


async def _interest_matched_listings(
    db, user_id: str, categories: List[str], exclude_ids: List[str],
) -> List[Dict[str, Any]]:
    if not categories:
        return []
    since = _iso_days_ago(_LOOKBACK_NEW_LISTINGS_DAYS)
    query = {
        "category": {"$in": categories},
        "status": "active",
        "created_at": {"$gte": since},
        "seller_id": {"$ne": user_id},  # never show your own listings
    }
    if exclude_ids:
        query["id"] = {"$nin": exclude_ids}
    return await db.listings.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "current_bid": 1, "starting_price": 1,
         "image_url": 1, "images": 1, "category": 1, "auction_end_time": 1,
         "created_at": 1, "price": 1},
    ).sort("created_at", -1).limit(_MAX_INTEREST_LISTINGS).to_list(_MAX_INTEREST_LISTINGS)


# ────────────────────────────────────────────────────────────────────
#  Payload builder
# ────────────────────────────────────────────────────────────────────

async def build_user_digest(db, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Assemble the per-user digest payload. Returns None when there's
    absolutely nothing useful to send — the scheduler then skips the
    dispatch entirely so we never send an empty marketing email."""
    if not user or not user.get("id") or not user.get("email"):
        return None

    seller_ids = await _followed_seller_ids(db, user["id"])
    seller_listings = await _new_listings_from_sellers(db, seller_ids)
    watchlist_updates = await _watchlist_updates(db, user["id"])

    exclude_ids: List[str] = [l["id"] for l in seller_listings] + \
                             [w["id"] for w in watchlist_updates]
    categories = await _top_interest_categories(db, user["id"])
    interest_listings = await _interest_matched_listings(
        db, user["id"], categories, exclude_ids,
    )

    if not seller_listings and not watchlist_updates and not interest_listings:
        # Nothing personal to say → skip send.
        return None

    lang = await _resolve_user_language(user)
    return {
        "user_id": user["id"],
        "email": user["email"],
        "name": user.get("first_name") or user.get("name") or "",
        "lang": lang,
        "seller_listings": seller_listings,
        "watchlist_updates": watchlist_updates,
        "interest_listings": interest_listings,
        "categories": categories,
        "sent_at": _now_utc().isoformat(),
    }


# ────────────────────────────────────────────────────────────────────
#  Per-user dispatch
# ────────────────────────────────────────────────────────────────────

async def send_weekly_digest_to_user(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Build + send. Returns a status envelope for the caller/audit log."""
    payload = await build_user_digest(db, user)
    if payload is None:
        return {"status": "skipped", "reason": "no_content", "user_id": user.get("id")}

    from services.templates.weekly_digest_template import (
        render_weekly_digest_html, render_weekly_digest_subject,
    )
    html = render_weekly_digest_html(payload)
    subject = render_weekly_digest_subject(payload)

    # send_email(is_marketing=True) will short-circuit if the user is
    # suppressed globally or has toggled marketing off — no need to
    # re-check here.
    from services.emails._email_core import send_email
    result = await send_email(
        to_email=payload["email"],
        subject=subject,
        html_content=html,
        is_marketing=True,
        categories=["weekly-digest", f"weekly-digest-{payload['lang']}"],
        custom_args={
            "user_id": payload["user_id"],
            "kind": "weekly_digest",
            "lang": payload["lang"],
        },
    )

    # Audit trail
    try:
        await db.weekly_digest_sends.insert_one({
            "user_id": payload["user_id"],
            "email": payload["email"],
            "lang": payload["lang"],
            "sent_at": _now_utc().isoformat(),
            "status": result.get("status", "unknown"),
            "reason": result.get("reason"),
            "counts": {
                "seller_listings": len(payload["seller_listings"]),
                "watchlist_updates": len(payload["watchlist_updates"]),
                "interest_listings": len(payload["interest_listings"]),
            },
        })
    except Exception as e:
        logger.warning(f"weekly_digest audit insert failed: {e}")

    return {"status": result.get("status", "sent"),
            "user_id": payload["user_id"],
            "lang": payload["lang"]}


# ────────────────────────────────────────────────────────────────────
#  Batch runner (called by APScheduler)
# ────────────────────────────────────────────────────────────────────

async def run_weekly_digest_batch(db=None, limit: int = _BATCH_USER_LIMIT) -> Dict[str, Any]:
    """Iterate all opted-in users and send. Concurrency-limited so we don't
    hammer SendGrid or the DB."""
    if db is None:
        from deps import get_db
        db = get_db()

    # Only send to users with a real login (skip contact-only rows created
    # by unsubscribes / marketing lists).
    query = {
        "email": {"$exists": True, "$ne": None},
        "is_contact_only": {"$ne": True},
        "role": {"$ne": "dialer_contractor"},  # contractors aren't the audience
    }
    projection = {
        "_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1,
        "preferred_language": 1, "language_preference": 1,
    }

    sem = asyncio.Semaphore(_SEND_CONCURRENCY)
    stats = {"attempted": 0, "sent": 0, "skipped": 0, "errors": 0}

    async def _one(u: Dict[str, Any]):
        async with sem:
            stats["attempted"] += 1
            try:
                out = await send_weekly_digest_to_user(db, u)
                if out.get("status") == "sent":
                    stats["sent"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.warning(
                    f"weekly_digest send failed for {u.get('id')}: {e}"
                )

    tasks: List[asyncio.Task] = []
    async for user in db.users.find(query, projection).limit(limit):
        tasks.append(asyncio.create_task(_one(user)))
        # keep the task list small to bound memory
        if len(tasks) >= _SEND_CONCURRENCY * 4:
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = []
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"weekly_digest batch complete: {stats}")
    return stats


__all__ = [
    "build_user_digest",
    "send_weekly_digest_to_user",
    "run_weekly_digest_batch",
]
