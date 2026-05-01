"""
BidVex — Scheduled Background Jobs
Extracted from server.py (Phase 4 refactor).
All functions are registered by server.py via APScheduler.
"""

from datetime import datetime, timezone, timedelta
import logging
import httpx

logger = logging.getLogger(__name__)


async def transition_upcoming_auctions(db):
    """Move auctions from 'upcoming' → 'active' when start date arrives."""
    try:
        now = datetime.now(timezone.utc)
        upcoming = await db.multi_item_listings.find({
            "status": "upcoming",
            "auction_start_date": {"$lte": now.isoformat()}
        }).to_list(100)
        for auction in upcoming:
            await db.multi_item_listings.update_one(
                {"id": auction["id"]}, {"$set": {"status": "active"}}
            )
        if upcoming:
            logger.info(f"Transitioned {len(upcoming)} upcoming auction(s) to active")
    except Exception as e:
        logger.error(f"Error in transition_upcoming_auctions: {e}")


async def expire_partner_pro_trials(db):
    """Revert expired Partner Pro trials to free tier."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        expired = await db.users.find({
            "subscription_status": "trialing",
            "subscription_source": "trial",
            "partner_pro_trial_end": {"$lte": now},
        }).to_list(100)
        for user in expired:
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {
                    "subscription_tier": "free",
                    "subscription_status": "expired",
                    "updated_at": now,
                }}
            )
            logger.info(f"Trial expired for user {user['id']}")
            try:
                from services.email_service import get_email_service
                from services.partner_pro_emails import trial_expired
                svc = get_email_service()
                if svc and svc.is_configured() and user.get("email"):
                    tmpl = trial_expired(user.get("name", "there"))
                    await svc.send_raw_html(user["email"], tmpl["subject"], tmpl["html"])
            except Exception as em:
                logger.warning(f"Trial expired email failed for {user.get('email')}: {em}")
    except Exception as e:
        logger.error(f"Error in expire_partner_pro_trials: {e}")


async def send_trial_reminder_emails(db):
    """Send reminder emails for trials expiring in 3 days via SendGrid."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        pending = await db.scheduled_emails.find({
            "type": "trial_expiry_reminder",
            "sent": False,
            "scheduled_for": {"$lte": now},
        }).to_list(50)
        for item in pending:
            try:
                from services.email_service import get_email_service
                from services.partner_pro_emails import trial_reminder
                svc = get_email_service()
                if svc and svc.is_configured():
                    user = await db.users.find_one({"id": item["user_id"]}, {"_id": 0})
                    tmpl = trial_reminder(user.get("name", "there") if user else "there", 3)
                    await svc.send_raw_html(item["email"], tmpl["subject"], tmpl["html"])
                await db.scheduled_emails.update_one(
                    {"id": item["id"]}, {"$set": {"sent": True, "sent_at": now}}
                )
                logger.info(f"Trial reminder sent to {item['email']}")
            except Exception as em:
                logger.error(f"Failed to send trial reminder to {item.get('email')}: {em}")
    except Exception as e:
        logger.error(f"Error in send_trial_reminder_emails: {e}")


async def send_auction_payment_reminders(db):
    """Send payment reminders for auctions where deadline is in ~4 days (day 10 of 14)."""
    try:
        now = datetime.now(timezone.utc)
        reminder_window_start = (now + timedelta(days=3)).isoformat()
        reminder_window_end = (now + timedelta(days=5)).isoformat()

        pending_listings = await db.listings.find({
            "payment_status": "pending_payment",
            "payment_deadline": {"$gte": reminder_window_start, "$lte": reminder_window_end},
            "reminder_sent": {"$ne": True},
        }, {"_id": 0}).to_list(100)

        for listing in pending_listings:
            try:
                winner_id = listing.get("winner_id")
                if not winner_id:
                    continue
                winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "email": 1, "name": 1})
                if not winner or not winner.get("email"):
                    continue

                deadline_dt = datetime.fromisoformat(listing["payment_deadline"])
                days_remaining = max(0, (deadline_dt - now).days)

                from services.email_notifications import send_payment_reminder_email
                await send_payment_reminder_email(
                    winner_email=winner["email"],
                    winner_name=winner.get("name", "Winner"),
                    item_title=listing.get("title", "Item"),
                    final_price=listing.get("final_price", 0),
                    listing_id=listing["id"],
                    days_remaining=days_remaining,
                    payment_deadline=listing["payment_deadline"],
                )

                await db.listings.update_one(
                    {"id": listing["id"]},
                    {"$set": {"reminder_sent": True}},
                )
                logger.info(f"Payment reminder sent for listing {listing['id']} to {winner['email']}")
            except Exception as e:
                logger.error(f"Failed to send payment reminder for listing {listing.get('id')}: {e}")
    except Exception as e:
        logger.error(f"Error in send_auction_payment_reminders: {e}")


async def process_overdue_auction_payments(db):
    """Mark overdue payments (day 14+) and apply 2%/month penalty."""
    try:
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        import uuid

        overdue_listings = await db.listings.find({
            "payment_status": "pending_payment",
            "payment_deadline": {"$lte": now_str},
            "overdue_notified": {"$ne": True},
        }, {"_id": 0}).to_list(100)

        for listing in overdue_listings:
            try:
                listing_id = listing["id"]
                winner_id = listing.get("winner_id")
                hammer_price = listing.get("final_price", 0)

                if not winner_id:
                    continue

                deadline_dt = datetime.fromisoformat(listing["payment_deadline"])
                days_late = max(0, (now - deadline_dt).days)
                months_late = max(1, (days_late + 29) // 30)
                penalty_rate = 0.02 * months_late
                penalty_amount = round(hammer_price * penalty_rate, 2)

                await db.listings.update_one(
                    {"id": listing_id},
                    {"$set": {
                        "payment_status": "overdue",
                        "overdue_notified": True,
                        "late_penalty_rate": penalty_rate,
                        "late_penalty_amount": penalty_amount,
                        "overdue_at": now_str,
                    }},
                )

                await db.notifications.insert_one({
                    "id": str(uuid.uuid4()),
                    "user_id": winner_id,
                    "type": "payment_overdue",
                    "title": "Payment Overdue",
                    "message": f"Your payment for {listing.get('title')} is overdue. A late penalty of ${penalty_amount:.2f} has been applied.",
                    "listing_id": listing_id,
                    "data": {
                        "checkout_url": f"/checkout/{listing_id}",
                        "penalty_amount": penalty_amount,
                    },
                    "read": False,
                    "created_at": now_str,
                })

                winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "email": 1, "name": 1})
                if winner and winner.get("email"):
                    from services.email_notifications import send_payment_overdue_email
                    await send_payment_overdue_email(
                        winner_email=winner["email"],
                        winner_name=winner.get("name", "Winner"),
                        item_title=listing.get("title", "Item"),
                        final_price=hammer_price,
                        listing_id=listing_id,
                        penalty_amount=penalty_amount,
                        total_with_penalty=hammer_price + penalty_amount,
                    )

                logger.info(f"Overdue processed for listing {listing_id}: penalty=${penalty_amount:.2f}")
            except Exception as e:
                logger.error(f"Failed to process overdue for listing {listing.get('id')}: {e}")
    except Exception as e:
        logger.error(f"Error in process_overdue_auction_payments: {e}")


async def send_review_request_emails(db):
    """Send 'How was your purchase?' emails 24h after payment confirmation."""
    try:
        now_str = datetime.now(timezone.utc).isoformat()

        pending_requests = await db.review_requests.find({
            "send_at": {"$lte": now_str},
            "sent": False,
        }, {"_id": 0}).to_list(50)

        for req in pending_requests:
            try:
                buyer = await db.users.find_one({"id": req["buyer_id"]}, {"_id": 0})
                if buyer and buyer.get("email"):
                    from services.email_notifications import send_review_request_email
                    await send_review_request_email(
                        buyer_email=buyer["email"],
                        buyer_name=buyer.get("name", "Buyer"),
                        item_title=req.get("item_title", "Item"),
                        transaction_id=req["transaction_id"],
                        seller_name=req.get("seller_name", "Seller"),
                    )
                await db.review_requests.update_one(
                    {"transaction_id": req["transaction_id"]},
                    {"$set": {"sent": True, "sent_at": now_str}},
                )
                logger.info(f"Review request email sent for txn {req['transaction_id']}")
            except Exception as e:
                logger.error(f"Failed to send review request: {e}")
    except Exception as e:
        logger.error(f"Error in send_review_request_emails: {e}")


async def keepalive_ping():
    """Ping own endpoints every 4 min to prevent cold starts."""
    endpoints = ["/api/health", "/api/marketplace/items?limit=1", "/api/multi-item-listings?limit=1"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=10) as c:
        for ep in endpoints:
            try:
                r = await c.get(ep)
                logger.debug(f"[keepalive] GET {ep} -> {r.status_code} ({r.elapsed.total_seconds():.2f}s)")
            except Exception as e:
                logger.debug(f"[keepalive] GET {ep} -> error: {e}")



async def send_auction_ending_soon_notifications(db):
    """
    Trigger: Runs every 5 minutes.
    Sends 'Ending Soon' emails to all bidders + watchers for auctions ending within 1 hour.
    Deduplicates via ending_soon_email_log collection.
    """
    try:
        now = datetime.now(timezone.utc)
        one_hour = (now + timedelta(hours=1)).isoformat()
        now_str = now.isoformat()

        # Find active auctions ending within 1 hour (both vehicle and regular)
        ending_auctions = []
        for coll_name in ["vehicle_listings", "listings"]:
            coll = db[coll_name]
            auctions = await coll.find({
                "status": "active",
                "end_time": {"$lte": one_hour, "$gte": now_str},
            }, {"_id": 0, "id": 1, "title": 1, "current_price": 1, "end_time": 1}).to_list(100)
            ending_auctions.extend(auctions)

        if not ending_auctions:
            return

        from services.email_service import send_auction_ending_soon_email

        sent_count = 0
        for auction in ending_auctions:
            auction_id = auction["id"]

            # Calculate time remaining
            try:
                end_dt = datetime.fromisoformat(auction["end_time"].replace("Z", "+00:00"))
                mins_left = max(1, int((end_dt - now).total_seconds() / 60))
                time_remaining = f"{mins_left} min" if mins_left < 60 else f"{mins_left // 60}h {mins_left % 60}m"
            except Exception:
                time_remaining = "< 1 hour"

            current_highest = auction.get("current_price", 0)

            # Get all bidders for this auction
            bids = await db.bids.find(
                {"listing_id": auction_id},
                {"_id": 0, "user_id": 1, "amount": 1}
            ).to_list(500)
            # Also get watchers
            watchers = await db.watchlists.find(
                {"listing_id": auction_id},
                {"_id": 0, "user_id": 1}
            ).to_list(500)

            # Merge unique user IDs
            user_bids = {}
            for b in bids:
                uid = b.get("user_id")
                if uid:
                    user_bids[uid] = max(user_bids.get(uid, 0), b.get("amount", 0))
            watcher_ids = {w.get("user_id") for w in watchers if w.get("user_id")}
            all_user_ids = set(user_bids.keys()) | watcher_ids

            for uid in all_user_ids:
                # Deduplicate: don't send twice for same auction
                already_sent = await db.ending_soon_email_log.find_one({
                    "user_id": uid, "auction_id": auction_id
                })
                if already_sent:
                    continue

                user = await db.users.find_one(
                    {"id": uid},
                    {"_id": 0, "email": 1, "name": 1, "preferred_language": 1, "language_preference": 1}
                )
                if not user or not user.get("email"):
                    continue

                user_last_bid = user_bids.get(uid, 0)

                try:
                    success = await send_auction_ending_soon_email(
                        user=user,
                        auction_id=auction_id,
                        item_name=auction.get("title", "Item"),
                        current_highest_bid=current_highest,
                        user_last_bid=user_last_bid,
                        time_remaining=time_remaining,
                    )
                    if success:
                        await db.ending_soon_email_log.insert_one({
                            "user_id": uid,
                            "auction_id": auction_id,
                            "sent_at": now_str,
                        })
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Failed ending-soon email to {user.get('email')}: {e}")

        if sent_count > 0:
            logger.info(f"[ENDING_SOON] Sent {sent_count} ending-soon notifications for {len(ending_auctions)} auctions")
    except Exception as e:
        logger.error(f"Error in send_auction_ending_soon_notifications: {e}")



# ─────────────────────────────────────────────────────────────────────────────
# Storage Auctions — auto-close processor (iter171)
# Runs every 5 minutes via scheduler.py. For each ACTIVE storage auction whose
# end_time has passed:
#   1. If soft_close_enabled and a bid landed in last 10 min → extend end_time
#      by soft_close_extension_minutes (default 10) instead of closing.
#   2. Otherwise:
#      a. Flip status → "sold" if there is a winning bidder, else "unsold"
#      b. Release held deposits (winner→applied, losers→refunded) via
#         services.storage_deposit_service.release_deposits_on_close
#      c. Email winner (per-payment-method bilingual) + email facility
#      d. Queue seller commission invoice (5% + Stripe + tax) email
#      e. Log the close event in storage_close_logs
# iter172: winner auctions also get a generated pickup_code (BV-XXXX-XXXX).
# ─────────────────────────────────────────────────────────────────────────────


def generate_pickup_code() -> str:
    """BidVex digital pickup code: BV-XXXX-XXXX (alphanumeric, uppercase)."""
    import secrets
    import string
    chars = string.ascii_uppercase + string.digits
    p1 = "".join(secrets.choice(chars) for _ in range(4))
    p2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"BV-{p1}-{p2}"


async def process_ended_storage_auctions(db):
    """Auto-close ended storage auctions with soft-close awareness."""
    try:
        now = datetime.now(timezone.utc)
        active_ended = await db.storage_auctions.find(
            {"status": "active", "end_time": {"$lte": now.isoformat()}},
            {"_id": 0},
        ).to_list(500)

        if not active_ended:
            return {"processed": 0, "closed": 0, "extended": 0}

        closed = 0
        extended = 0
        errors = []

        for auction in active_ended:
            try:
                auction_id = auction["id"]
                bids = auction.get("bids", [])

                # ── Soft-close guard ──
                if auction.get("soft_close_enabled", True) and bids:
                    soft_minutes = int(auction.get("soft_close_extension_minutes", 10) or 10)
                    # Find the most recent bid's placed_at
                    last_bid_time = None
                    for b in bids:
                        pa = b.get("placed_at")
                        if pa:
                            try:
                                dt = datetime.fromisoformat(str(pa).replace("Z", "+00:00"))
                                if not last_bid_time or dt > last_bid_time:
                                    last_bid_time = dt
                            except Exception:
                                pass

                    if last_bid_time:
                        end_time_dt = datetime.fromisoformat(str(auction["end_time"]).replace("Z", "+00:00"))
                        window_start = end_time_dt - timedelta(minutes=soft_minutes)
                        if last_bid_time >= window_start:
                            # Extend end_time by soft_minutes
                            new_end = end_time_dt + timedelta(minutes=soft_minutes)
                            await db.storage_auctions.update_one(
                                {"id": auction_id},
                                {"$set": {"end_time": new_end.isoformat(), "updated_at": now.isoformat()}},
                            )
                            extended += 1
                            logger.info(f"[STORAGE_CLOSE] soft-extended {auction_id} by {soft_minutes}m")
                            continue

                # ── Actually close ──
                winner_id = auction.get("winning_bidder_id")
                current_bid = float(auction.get("current_bid", 0) or 0)
                new_status = "sold" if winner_id and bids else "unsold"

                # Generate pickup code for winning auctions (iter172)
                pickup_code = None
                if new_status == "sold":
                    pickup_code = generate_pickup_code()

                set_update = {
                    "status": new_status,
                    "winning_bid": current_bid if new_status == "sold" else None,
                    "closed_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                if pickup_code:
                    set_update["pickup_code"] = pickup_code
                    set_update["pickup_code_used"] = False
                    set_update["pickup_code_used_at"] = None

                await db.storage_auctions.update_one(
                    {"id": auction_id},
                    {"$set": set_update},
                )
                # Refresh auction dict with the new fields so the email sees them
                if pickup_code:
                    auction["pickup_code"] = pickup_code

                # ── Release deposits (best-effort) ──
                try:
                    from services.storage_deposit_service import release_deposits_on_close
                    await release_deposits_on_close(db, auction_id, winner_id)
                except Exception as e:
                    logger.error(f"[STORAGE_CLOSE] deposit release failed for {auction_id}: {e}")

                # ── Fetch facility + buyer ──
                facility = await db.storage_facilities.find_one(
                    {"id": auction["facility_id"]}, {"_id": 0}
                ) or {}
                buyer = {}
                if winner_id:
                    buyer = await db.users.find_one({"id": winner_id}, {"_id": 0}) or {}

                # ── Compute pricing for emails ──
                pricing = None
                try:
                    from services.storage_pricing import calculate_storage_pricing
                    pricing = calculate_storage_pricing(
                        current_bid,
                        facility.get("province", ""),
                        auction.get("payment_method", "stripe"),
                        deposit_amount=auction.get("deposit_amount") or 0,
                    )
                except Exception as e:
                    logger.error(f"[STORAGE_CLOSE] pricing calc failed for {auction_id}: {e}")

                # ── Emails (non-blocking in practice; awaited for reliability here) ──
                if new_status == "sold":
                    try:
                        from services.email_notifications import (
                            send_storage_auction_won_email,
                            send_storage_auction_sold_email,
                            send_storage_seller_commission_invoice,
                        )
                        await send_storage_auction_won_email(buyer, auction, facility, pricing)
                        await send_storage_auction_sold_email(facility, auction, buyer)
                        if pricing:
                            # Reuse existing commission invoice helper (it accepts "seller_invoice" shape)
                            seller_invoice_compat = {
                                "seller_invoice": {
                                    "commission": pricing["facility_invoice"].get("bidvex_platform_fee", 0) if auction.get("payment_method") != "stripe" else pricing["buyer_invoice"].get("platform_fee", 0),
                                    "stripe_recovery": pricing["facility_invoice"].get("stripe_recovery", 0) if auction.get("payment_method") != "stripe" else pricing["buyer_invoice"].get("stripe_recovery", 0),
                                    "tax": pricing["facility_invoice"].get("tax", 0) if auction.get("payment_method") != "stripe" else pricing["buyer_invoice"].get("tax", 0),
                                    "tax_label": pricing.get("tax_label", ""),
                                    "total": pricing["facility_invoice"].get("facility_owes_bidvex", 0) if auction.get("payment_method") != "stripe" else (float(pricing["buyer_invoice"].get("platform_fee", 0)) + float(pricing["buyer_invoice"].get("stripe_recovery", 0)) + float(pricing["buyer_invoice"].get("tax", 0))),
                                }
                            }
                            # Only send a separate invoice for cash/etransfer (Stripe path = fee already charged to buyer)
                            if auction.get("payment_method") in ("cash", "etransfer"):
                                await send_storage_seller_commission_invoice(facility, auction, seller_invoice_compat)
                    except Exception as e:
                        logger.error(f"[STORAGE_CLOSE] email dispatch failed for {auction_id}: {e}")

                # ── Log ──
                await db.storage_close_logs.insert_one({
                    "auction_id": auction_id,
                    "facility_id": auction.get("facility_id"),
                    "winning_bid": current_bid,
                    "winner_id": winner_id,
                    "final_status": new_status,
                    "payment_method": auction.get("payment_method"),
                    "bids_count": len(bids),
                    "closed_at": now.isoformat(),
                })

                closed += 1
            except Exception as e:
                logger.error(f"[STORAGE_CLOSE] failed to close {auction.get('id')}: {e}")
                errors.append({"id": auction.get("id"), "error": str(e)})

        if closed or extended:
            logger.info(f"[STORAGE_CLOSE] closed={closed} extended={extended} errors={len(errors)}")
        return {"processed": len(active_ended), "closed": closed, "extended": extended, "errors": errors}
    except Exception as e:
        logger.error(f"[STORAGE_CLOSE] top-level error: {e}")
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────
# Expired promotions auto-downgrade (iter172)
# Runs every hour — finds any listing where promoted_until < now and resets
# promotion_tier and is_featured. Covers marketplace listings, vehicles, and
# storage auctions.
# ─────────────────────────────────────────────────────────────

async def process_expired_promotions(db):
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        stats = {}
        for coll_name in ("listings", "vehicle_listings", "storage_auctions"):
            coll = db[coll_name]
            result = await coll.update_many(
                {
                    "$or": [
                        {"promoted_until": {"$lt": now_iso}, "promotion_tier": {"$nin": [None, ""]}},
                        {"promoted_until": {"$lt": now_iso}, "is_featured": True},
                    ]
                },
                {"$set": {
                    "promotion_tier": None,
                    "is_featured": False,
                    "promotion_expired_at": now_iso,
                }},
            )
            stats[coll_name] = result.modified_count
        total = sum(stats.values())
        if total:
            logger.info(f"[PROMOTIONS] downgraded {total} expired promotions: {stats}")
        return {"downgraded": total, "per_collection": stats}
    except Exception as e:
        logger.error(f"[PROMOTIONS] downgrade error: {e}")
        return {"error": str(e)}
