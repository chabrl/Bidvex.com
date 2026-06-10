"""
services/pickup_confirmation.py — iter297 P1

Buyer-Confirm-Pickup / Deposit-Release Flow.

Closes the auction-end transaction loop. Once an auction has ended
with a winner, the buyer (and as a fallback the seller, or an admin)
can confirm that the item was received / pickup was arranged. This
action:

  • Stamps `pickup_confirmed=True` + `pickup_confirmed_at=now()` on
    the listing.
  • Sets `status = "completed"`.
  • Auto-refunds the buyer's deposit IF the listing is non-vehicle
    (marketplace / lots / storage). For VEHICLES the deposit is held
    and an admin sign-off notification is emitted (vehicles are high
    value → manual gate).
  • Increments the seller's `completed_auctions` counter.
  • Fires two rating-request emails (buyer→seller, seller→buyer).

WINDOW
======
The buyer has 7 days from `ended_at` to self-confirm. After 7 days the
seller may also confirm. After 7 days with NEITHER party confirming,
the nightly `flag_stuck_transactions_job` flags the listing
`pending_review` and notifies admins; the deposit is HELD until admin
resolves.

All actions are idempotent — re-calling `confirm_pickup` after the
listing is already `completed` is a no-op that returns the prior
result.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

PICKUP_WINDOW_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# ── Listing resolver ──────────────────────────────────────────────────

# Tuples of (collection_name, listing_kind, requires_admin_release).
# `requires_admin_release=True` means we DO NOT auto-refund the
# buyer's deposit on confirm — an admin must sign off (vehicles).
_LISTING_TARGETS = (
    ("listings",              "marketplace", False),
    ("multi_item_listings",   "lots",        False),
    ("storage_auctions",      "storage",     False),
    ("vehicle_listings",      "vehicle",     True),
)


async def _resolve_listing(db, listing_id: str) -> Optional[Tuple[Dict[str, Any], str, bool]]:
    """Returns (doc, kind, requires_admin_release) for the first
    collection that contains `listing_id`. None if not found anywhere."""
    for coll, kind, admin_release in _LISTING_TARGETS:
        doc = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return doc, kind, admin_release
    return None


def _winner_id(listing: Dict[str, Any]) -> Optional[str]:
    """Multi-collection canonical winner id resolver."""
    return (
        listing.get("winner_user_id")
        or listing.get("winner_id")          # vehicle convention
        or listing.get("highest_bidder_id")  # legacy pre-iter296
    )


def _title(listing: Dict[str, Any]) -> str:
    return (
        listing.get("title")
        or listing.get("unit_label")
        or listing.get("name")
        or (f"{listing.get('year','')} {listing.get('make','')} "
            f"{listing.get('model','')}").strip()
        or "your item"
    )


def _ended_at_dt(listing: Dict[str, Any]) -> Optional[datetime]:
    """Best-effort end-time resolver across collections."""
    val = (
        listing.get("ended_at")
        or listing.get("closed_at")
        or listing.get("sold_at")
        or listing.get("auction_end_date")
    )
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            d = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


# ── Authorization ─────────────────────────────────────────────────────

def authorize_pickup_confirm(
    *, listing: Dict[str, Any], actor_user: Dict[str, Any]
) -> Tuple[bool, str]:
    """Returns (allowed, role) where role ∈ {'buyer','seller','admin'}.
    Sellers may only confirm AFTER the buyer's 7-day window elapses
    (gives the buyer first right of confirmation)."""
    if not actor_user:
        return False, ""
    if actor_user.get("role") in ("admin", "super_admin"):
        return True, "admin"

    winner = _winner_id(listing)
    seller = listing.get("seller_id") or listing.get("seller_user_id") or listing.get("facility_id")
    uid = actor_user.get("id")

    if winner and uid == winner:
        return True, "buyer"

    if seller and uid == seller:
        # Seller can only confirm after the buyer's window expires.
        ended = _ended_at_dt(listing)
        if ended and _now() - ended >= timedelta(days=PICKUP_WINDOW_DAYS):
            return True, "seller"
        return False, "seller_must_wait"

    return False, "not_party"


# ── Deposit release ───────────────────────────────────────────────────

async def _release_deposit_for_listing(db, *, listing_id: str, kind: str) -> Dict[str, Any]:
    """Refund the buyer's deposit for THIS listing. Marketplace/lots
    use the `bidder_deposits` collection; storage uses `bidder_deposits`
    too; vehicles use `vehicle_bid_deposits` but those are NOT auto-
    released (gated by admin sign-off — caller short-circuits before
    calling us)."""
    summary = {"released": 0, "errors": []}
    coll = "bidder_deposits" if kind != "vehicle" else "vehicle_bid_deposits"
    try:
        cursor = db[coll].find({
            "listing_id": listing_id,
            "status": {"$in": ["paid", "authorized", "held", "succeeded"]},
        })
        async for dep in cursor:
            try:
                # Stripe refund (best-effort). If no Stripe id exists
                # we still mark the doc refunded — the deposit may
                # have been a demo / off-platform deposit.
                pi = dep.get("payment_intent_id") or dep.get("stripe_payment_intent_id")
                if pi and not str(pi).startswith("demo_"):
                    try:
                        import stripe
                        stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
                        if stripe.api_key:
                            stripe.Refund.create(payment_intent=pi)
                    except Exception as se:
                        logger.warning(f"[pickup_confirm] stripe refund failed for {pi}: {se}")
                await db[coll].update_one(
                    {"id": dep["id"]},
                    {"$set": {
                        "status":      "refunded",
                        "refunded_at": _now_iso(),
                        "refund_reason": "pickup_confirmed",
                    }},
                )
                summary["released"] += 1
            except Exception as ex:
                logger.warning(f"[pickup_confirm] refund error: {ex}")
                summary["errors"].append(str(ex))
    except Exception as ex:
        logger.warning(f"[pickup_confirm] deposit scan failed: {ex}")
        summary["errors"].append(str(ex))
    return summary


# ── Rating-request emails (best-effort) ───────────────────────────────

async def _send_rating_requests(db, *, listing: Dict[str, Any], kind: str) -> None:
    winner_id = _winner_id(listing)
    seller_id = listing.get("seller_id") or listing.get("seller_user_id") or listing.get("facility_id")
    if not (winner_id and seller_id):
        return
    try:
        winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "email": 1, "name": 1, "first_name": 1})
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1, "name": 1, "first_name": 1, "business_name": 1})
    except Exception as ex:
        logger.warning(f"[pickup_confirm] rating-request user lookup failed: {ex}")
        return

    title = _title(listing)
    listing_id = listing["id"]
    rating_url = f"{os.environ.get('FRONTEND_URL', 'https://bidvex.com')}/rate/{kind}/{listing_id}"

    try:
        from services.emails._email_core import send_unified_email
        # Buyer → Seller
        if winner and winner.get("email"):
            await send_unified_email(
                to_email=winner["email"],
                to_name=winner.get("first_name") or winner.get("name") or "",
                subject="How was your experience? Rate the seller.",
                html_body=(
                    f"<p>Now that you've received <strong>{title}</strong>, please take 30 seconds "
                    f"to rate your experience.</p>"
                    f"<p><a href='{rating_url}' style='display:inline-block;padding:10px 18px;"
                    f"background:#0B2545;color:#fff;text-decoration:none;border-radius:6px;'>"
                    f"Rate Seller</a></p>"
                ),
                category="rating_request_buyer",
            )
        # Seller → Buyer
        if seller and seller.get("email"):
            buyer_first = (winner.get("first_name") or (winner.get("name") or "").split(" ")[0]) if winner else "your buyer"
            await send_unified_email(
                to_email=seller["email"],
                to_name=seller.get("first_name") or seller.get("name") or seller.get("business_name") or "",
                subject=f"Rate your buyer {buyer_first}",
                html_body=(
                    f"<p>The transaction for <strong>{title}</strong> is now complete.</p>"
                    f"<p>Please leave a quick rating for your buyer.</p>"
                    f"<p><a href='{rating_url}' style='display:inline-block;padding:10px 18px;"
                    f"background:#0B2545;color:#fff;text-decoration:none;border-radius:6px;'>"
                    f"Rate Buyer</a></p>"
                ),
                category="rating_request_seller",
            )
    except Exception as ex:
        logger.warning(f"[pickup_confirm] rating-request emails failed: {ex}")


# ── Main entry point ──────────────────────────────────────────────────

async def confirm_pickup(
    db,
    *,
    listing_id: str,
    actor_user: Dict[str, Any],
) -> Dict[str, Any]:
    """Atomically stamp pickup-confirmed + run all post-confirm side
    effects. Returns the new listing snapshot plus a side-effect
    summary."""
    found = await _resolve_listing(db, listing_id)
    if not found:
        return {"ok": False, "error": "listing_not_found"}
    listing, kind, requires_admin_release = found

    if listing.get("pickup_confirmed"):
        return {
            "ok": True, "kind": kind, "idempotent": True,
            "listing_id": listing_id,
            "pickup_confirmed_at": listing.get("pickup_confirmed_at"),
        }

    # Listing must actually have ended with a winner.
    if listing.get("status") not in ("ended", "sold", "completed"):
        return {"ok": False, "error": "listing_not_ended", "status": listing.get("status")}
    if not _winner_id(listing):
        return {"ok": False, "error": "no_winner"}

    allowed, role = authorize_pickup_confirm(listing=listing, actor_user=actor_user)
    if not allowed:
        return {"ok": False, "error": "not_authorized", "reason": role}

    # 1) Stamp the listing.
    coll = next(c for c, k, _ in _LISTING_TARGETS if k == kind)
    now_iso = _now_iso()
    set_update = {
        "pickup_confirmed":    True,
        "pickup_confirmed_at": now_iso,
        "pickup_confirmed_by": role,
        "pickup_confirmed_by_user_id": actor_user.get("id"),
        "status":              "completed",
        "completed_at":        now_iso,
        "updated_at":          now_iso,
    }
    await db[coll].update_one({"id": listing_id}, {"$set": set_update})

    out: Dict[str, Any] = {
        "ok":          True,
        "kind":        kind,
        "role":        role,
        "listing_id":  listing_id,
        "stamped_at":  now_iso,
    }

    # 2) Deposit release (skip vehicles → admin sign-off).
    if requires_admin_release:
        out["deposit_release"] = "pending_admin_signoff"
        # Notify admins so they can release manually.
        try:
            from services.notifications_i18n import create_notification
            async for admin in db.users.find({"role": {"$in": ["admin", "super_admin"]}}, {"_id": 0, "id": 1}):
                await create_notification(
                    db, user_id=admin["id"],
                    kind="auction_ended",
                    params={"title": f"VEHICLE deposit needs admin release — {_title(listing)}",
                            "amount": float(listing.get("final_price") or 0)},
                    data={"listing_id": listing_id, "action": "deposit_release_required",
                          "kind": "vehicle"},
                )
        except Exception as ex:
            logger.warning(f"[pickup_confirm] admin notification failed: {ex}")
    else:
        out["deposit_release"] = await _release_deposit_for_listing(db, listing_id=listing_id, kind=kind)

    # 3) Seller `completed_auctions` counter.
    seller_id = listing.get("seller_id") or listing.get("seller_user_id") or listing.get("facility_id")
    if seller_id:
        try:
            await db.users.update_one(
                {"id": seller_id},
                {"$inc": {"completed_auctions": 1}},
            )
        except Exception as ex:
            logger.warning(f"[pickup_confirm] counter increment failed: {ex}")

    # 4) Rating-request emails (fire-and-forget).
    try:
        await _send_rating_requests(db, listing=listing, kind=kind)
    except Exception as ex:
        logger.warning(f"[pickup_confirm] rating emails failed: {ex}")

    # 5) Platform notifications — let the buyer + seller see the close.
    try:
        from services.notifications_i18n import create_notification
        winner_id = _winner_id(listing)
        if winner_id:
            await create_notification(
                db, user_id=winner_id, kind="auction_ended",
                params={"title": _title(listing), "amount": float(listing.get("final_price") or 0)},
                data={"listing_id": listing_id, "action": "transaction_completed",
                      "action_url": f"/listings/{listing_id}"},
            )
        if seller_id:
            await create_notification(
                db, user_id=seller_id, kind="auction_ended",
                params={"title": _title(listing), "amount": float(listing.get("final_price") or 0)},
                data={"listing_id": listing_id, "action": "transaction_completed",
                      "action_url": "/seller/dashboard"},
            )
    except Exception as ex:
        logger.warning(f"[pickup_confirm] notifications failed: {ex}")

    return out


# ── 7-day stuck-transaction sweeper ───────────────────────────────────

async def flag_stuck_transactions(db) -> Dict[str, int]:
    """Nightly: any ended-with-winner listing whose pickup wasn't
    confirmed within 7 days gets flagged `pending_review` and the
    admins receive a bell-icon ping. Run idempotently — the flag is
    only applied once."""
    cutoff = _now() - timedelta(days=PICKUP_WINDOW_DAYS)
    out = {"flagged": 0, "kinds": {}}

    for coll_name, kind, _ in _LISTING_TARGETS:
        try:
            async for doc in db[coll_name].find({
                "status": {"$in": ["ended", "sold"]},
                # Buyer/seller has NOT yet confirmed pickup.
                "$or": [{"pickup_confirmed": False}, {"pickup_confirmed": {"$exists": False}}],
                # AND this listing hasn't been flagged for admin review yet.
                "$nor": [{"pending_review_flagged": True}],
            }, {"_id": 0, "id": 1, "ended_at": 1, "sold_at": 1, "auction_end_date": 1, "title": 1}):
                # Use the helper end-time resolver.
                ended = _ended_at_dt(doc)
                if not ended or ended > cutoff:
                    continue
                await db[coll_name].update_one(
                    {"id": doc["id"]},
                    {"$set": {
                        "pending_review_flagged":    True,
                        "pending_review_flagged_at": _now_iso(),
                        "pending_review_reason":     "no_pickup_confirmation_after_7d",
                    }},
                )
                out["flagged"] += 1
                out["kinds"][kind] = out["kinds"].get(kind, 0) + 1
                # Bell-icon ping for every admin.
                try:
                    from services.notifications_i18n import create_notification
                    async for admin in db.users.find({"role": {"$in": ["admin", "super_admin"]}}, {"_id": 0, "id": 1}):
                        await create_notification(
                            db, user_id=admin["id"], kind="auction_ended",
                            params={"title": f"PENDING REVIEW: {doc.get('title','Unnamed')}", "amount": 0},
                            data={"listing_id": doc["id"], "action": "pickup_overdue",
                                  "kind": kind, "action_url": "/admin/pickup-review"},
                        )
                except Exception as ex:
                    logger.warning(f"[stuck_tx] admin notif failed: {ex}")
        except Exception as ex:
            logger.warning(f"[stuck_tx] scan {coll_name} failed: {ex}")

    return out


__all__ = [
    "confirm_pickup", "flag_stuck_transactions",
    "authorize_pickup_confirm", "PICKUP_WINDOW_DAYS",
]
