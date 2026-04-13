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
