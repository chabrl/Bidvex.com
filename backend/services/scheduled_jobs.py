"""
BidVex — Scheduled Background Jobs
Extracted from server.py (Phase 4 refactor).
All functions are registered by server.py via APScheduler.
"""

from datetime import datetime, timezone, timedelta
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)


# ─── Scheduler Health Tracking ────────────────────────────────────────────
# Updated by safe_run() — read by /api/admin/scheduler/status endpoint.
_JOB_STATUS = {}


def get_job_status_snapshot():
    """Return a copy of the latest job status dict (used by admin API)."""
    return dict(_JOB_STATUS)


async def safe_run(job_name: str, coro, timeout_seconds: float = 55.0):
    """Run a scheduler coroutine with timeout + per-job exception isolation.

    One failing job will never crash the scheduler or the API.
    Records last_run / last_status / last_duration_ms in _JOB_STATUS so
    the admin dashboard can surface job health.
    """
    started_at = datetime.now(timezone.utc)
    t0 = asyncio.get_event_loop().time()
    status = "success"
    error_msg = None
    try:
        await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        status = "timeout"
        error_msg = f"timed out after {timeout_seconds}s"
        logger.error(f"⏰ Scheduler job '{job_name}' {error_msg}")
    except Exception as e:
        status = "error"
        error_msg = str(e)[:500]
        logger.error(f"❌ Scheduler job '{job_name}' failed: {e}", exc_info=True)
    finally:
        duration_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
        _JOB_STATUS[job_name] = {
            "name": job_name,
            "last_run": started_at.isoformat(),
            "last_status": status,
            "last_duration_ms": duration_ms,
            "last_error": error_msg,
        }
        if status == "success":
            logger.info(f"✅ Scheduler job '{job_name}' completed in {duration_ms}ms")


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


_REMINDER_COLLECTIONS = [
    ("listings", "marketplace"),
    ("multi_item_listings", "lots"),
    ("storage_auctions", "storage"),
    ("vehicle_listings", "vehicles"),
]


async def send_auction_payment_reminders(db):
    """iter302 — T+24h and T+48h automated payment reminders.

    The 72h payment clock starts when the listing is stamped
    `payment_status=pending_payment` with a `payment_deadline` (deadline−72h
    = T0). Runs hourly across all 4 sections:
      • ≥24h elapsed → reminder #1 (flag payment_reminder_24_sent)
      • ≥48h elapsed → reminder #2 with escalation warning
        (flag payment_reminder_48_sent)
    """
    try:
        now = datetime.now(timezone.utc)
        from services.emails.email_system import send_payment_reminder_email

        for coll, _section in _REMINDER_COLLECTIONS:
            pending = await db[coll].find({
                "payment_status": "pending_payment",
                "payment_deadline": {"$exists": True, "$ne": None},
                "$or": [
                    {"payment_reminder_24_sent": {"$ne": True}},
                    {"payment_reminder_48_sent": {"$ne": True}},
                ],
            }, {"_id": 0}).to_list(200)

            for listing in pending:
                try:
                    winner_id = (listing.get("winner_id") or listing.get("winner_user_id")
                                 or listing.get("highest_bidder_id"))
                    if not winner_id:
                        continue
                    try:
                        deadline_dt = datetime.fromisoformat(
                            str(listing["payment_deadline"]).replace("Z", "+00:00"))
                        if deadline_dt.tzinfo is None:
                            deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        continue
                    t0 = deadline_dt - timedelta(hours=72)
                    elapsed_h = (now - t0).total_seconds() / 3600
                    if elapsed_h < 24:
                        continue

                    stage = None
                    if elapsed_h >= 48 and not listing.get("payment_reminder_48_sent"):
                        stage = "48"
                    elif elapsed_h >= 24 and not listing.get("payment_reminder_24_sent"):
                        stage = "24"
                    if not stage:
                        continue

                    winner = await db.users.find_one(
                        {"id": winner_id}, {"_id": 0, "email": 1, "name": 1})
                    hammer = float(listing.get("final_price") or listing.get("current_price")
                                   or listing.get("current_bid") or 0)
                    hours_remaining = max(0, (deadline_dt - now).total_seconds() / 3600)

                    if winner and winner.get("email"):
                        await send_payment_reminder_email(
                            winner_email=winner["email"],
                            winner_name=winner.get("name", "Winner"),
                            item_title=listing.get("title", "Item"),
                            final_price=hammer,
                            listing_id=listing["id"],
                            days_remaining=int(hours_remaining // 24),
                            payment_deadline=str(listing["payment_deadline"]),
                        )
                        # Escalation warning on the 48h reminder
                        if stage == "48":
                            try:
                                from services.emails._email_core import send_email, _base_template
                                await send_email(
                                    to_email=winner["email"],
                                    subject="Final notice before auto-charge / Dernier avis avant prélèvement automatique",
                                    html_content=_base_template(
                                        f"<h2 style='margin:0 0 16px 0;color:#b91c1c;'>Escalation Warning / Avertissement</h2>"
                                        f"<p>Payment for <strong>{listing.get('title','your item')}</strong> remains outstanding. "
                                        f"If unpaid by the deadline, BidVex will charge your saved payment method for the "
                                        f"full amount owing, as authorized when you placed your bid.</p>"
                                        f"<p style='color:#555;'>Le paiement pour <strong>{listing.get('title','votre article')}</strong> est "
                                        f"toujours impay&eacute;. S'il n'est pas r&eacute;gl&eacute; avant l'&eacute;ch&eacute;ance, BidVex pr&eacute;l&egrave;vera votre moyen de "
                                        f"paiement enregistr&eacute; pour le montant total d&ucirc;, tel qu'autoris&eacute; lors de votre mise.</p>",
                                        "Escalation Warning",
                                    ),
                                )
                            except Exception as esc_err:  # noqa: BLE001
                                logger.warning(f"[reminders] escalation email failed: {esc_err}")

                    # Bilingual bell notification
                    try:
                        from services.notifications_i18n import create_notification
                        await create_notification(
                            db, user_id=winner_id, kind="payment_reminder",
                            params={"title": listing.get("title", "your item"),
                                    "amount": f"{hammer:,.2f}"},
                            data={"listing_id": listing["id"], "stage": stage,
                                  "action_url": "/dashboard/buyer"},
                        )
                    except Exception:  # noqa: BLE001
                        pass

                    await db[coll].update_one(
                        {"id": listing["id"]},
                        {"$set": {f"payment_reminder_{stage}_sent": True,
                                  f"payment_reminder_{stage}_sent_at": now.isoformat()}},
                    )
                    logger.info(f"[reminders] T+{stage}h reminder sent for {listing['id']}")
                except Exception as e:
                    logger.error(f"Failed payment reminder for {listing.get('id')}: {e}")
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

                # iter296 P0 BUG 4 — bilingual
                from services.notifications_i18n import create_notification
                await create_notification(
                    db, user_id=winner_id, kind="winner_payment_due",
                    params={"title": listing.get("title", "your item"), "amount": penalty_amount, "days": 14},
                    data={"listing_id": listing_id, "checkout_url": f"/checkout/{listing_id}",
                          "penalty_amount": penalty_amount},
                )

                # iter306 — Web Push
                try:
                    from services.push_dispatcher import dispatch_push
                    from services.category_rules import is_vehicle_category
                    _cat = (listing.get("category") or "").lower()
                    _is_vehicle = is_vehicle_category(_cat)
                    await dispatch_push(
                        db, user_id=winner_id, kind="payment_due",
                        title_item=listing.get("title", "your item"),
                        amount=hammer_price, listing_id=listing_id,
                        is_vehicle=_is_vehicle,
                        url=f"/checkout/{listing_id}",
                    )
                except Exception:
                    pass

                winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "email": 1, "name": 1})
                if winner and winner.get("email"):
                    from services.emails.email_system import send_payment_overdue_email
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
                    from services.emails.email_system import send_review_request_email
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
#   1. If soft_close_enabled and a bid landed in last 2 min → extend end_time
#      by soft_close_extension_minutes (default 2) instead of closing.
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
                    soft_minutes = int(auction.get("soft_close_extension_minutes", 2) or 2)
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
                # iter296 P0 BUG 1 + 5 — propagate winner + sold marker
                # so seller dashboard counters reflect the close within
                # one tick.
                if new_status == "sold" and winner_id:
                    set_update["winner_user_id"] = winner_id
                    set_update["sold_at"] = now.isoformat()
                    set_update["final_price"] = current_bid
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

                # ── Create down payment ($50 flat for storage) ──
                if new_status == "sold" and winner_id:
                    try:
                        from services.down_payment_service import create_down_payment
                        await create_down_payment(
                            db,
                            auction_id=auction_id,
                            auction_type="storage",
                            buyer_id=winner_id,
                            seller_id=auction.get("facility_owner_id"),
                            winning_bid=current_bid,
                            listing_title=auction.get("title") or auction.get("unit_number") or "Storage Unit",
                        )
                    except Exception as e:
                        logger.error(f"[STORAGE_CLOSE] down payment create failed for {auction_id}: {e}")

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
                        from services.emails.email_marketplace import (
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

                # iter298 BUG 3/4 — Storage Stripe path: auto-charge the
                # winner (hammer + 5% fee + processing + tax − $50
                # deposit) at close, stamp the payment lifecycle, flag
                # payout_pending, and issue receipts/statements.
                if new_status == "sold" and winner_id and pricing and (auction.get("payment_method") or "stripe").lower() == "stripe":
                    try:
                        from services.payment_collection import (
                            settle_storage_stripe, finalize_auction_payment,
                        )
                        storage_settlement = await settle_storage_stripe(
                            db, auction=auction, pricing=pricing,
                        )
                        _facility_user_id = facility.get("user_id") or auction.get("facility_owner_id") or facility.get("id")
                        await finalize_auction_payment(
                            db,
                            listing={**auction, "winner_user_id": winner_id,
                                     "final_price": current_bid,
                                     "seller_id": _facility_user_id},
                            collection="storage_auctions",
                            settlement=storage_settlement,
                            section="storage",
                            listing_title=auction.get("title") or auction.get("unit_label") or auction.get("unit_number") or "Storage Unit",
                            hammer_override=current_bid,
                            winner_override=winner_id,
                        )
                    except Exception as e:
                        logger.error(f"[STORAGE_CLOSE] stripe auto-charge failed for {auction_id}: {e}")

                # iter298 BUG 2 — unsold storage auction → relist email +
                # bilingual notification to the facility owner.
                if new_status == "unsold":
                    try:
                        _fac_user_id = facility.get("user_id") or auction.get("facility_owner_id") or facility.get("id")
                        _fac_user = await db.users.find_one(
                            {"id": _fac_user_id}, {"_id": 0, "name": 1, "email": 1}) or {}
                        _st_title = auction.get("unit_label") or auction.get("title") or auction.get("unit_number") or "Storage Unit"
                        if _fac_user.get("email"):
                            from services.emails.email_vehicles import (
                                send_seller_auction_no_bids_email,
                            )
                            await send_seller_auction_no_bids_email(
                                seller_email=_fac_user["email"],
                                seller_name=_fac_user.get("name", "Seller"),
                                listing_title=_st_title,
                                listing_id=auction_id,
                                auction_type="storage",
                                auction_end_time=str(auction.get("end_time") or now.isoformat()),
                                bid_count=len(bids),
                            )
                    except Exception as e:
                        logger.warning(f"[STORAGE_CLOSE] unsold relist email failed for {auction_id}: {e}")

                # iter211 Task 2 — Hybrid commission routing for storage facilities.
                # If the facility opted into manual payouts AND this is a cash/etransfer
                # auction (the only case where BidVex needs to collect), enqueue the
                # commission instead of trying to auto-charge their card.
                if new_status == "sold" and auction.get("payment_method") in ("cash", "etransfer") and pricing:
                    try:
                        facility_user = await db.users.find_one(
                            {"id": facility.get("user_id") or facility.get("id")},
                            {"_id": 0, "commission_payout_method": 1, "email": 1},
                        ) or {}
                        if (facility_user.get("commission_payout_method") or "auto") == "manual":
                            from services.manual_settlement_service import enqueue_manual_commission
                            owed = float(pricing["facility_invoice"].get("facility_owes_bidvex", 0) or 0)
                            if owed > 0:
                                await enqueue_manual_commission(
                                    db,
                                    user_id=facility.get("user_id") or facility.get("id"),
                                    auction_id=auction_id,
                                    listing_id=auction_id,
                                    listing_title=auction.get("unit_label") or auction.get("title") or f"Storage auction {auction_id}",
                                    commission_amount_cad=owed,
                                )
                                logger.info(f"[STORAGE_CLOSE] manual commission enqueued for facility user={facility.get('user_id')} amount=${owed:.2f}")
                    except Exception as e:
                        logger.error(f"[STORAGE_CLOSE] manual commission enqueue failed for {auction_id}: {e}")

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

                # iter296 P0 BUG 4 — Bilingual platform notifications.
                try:
                    from services.notifications_i18n import create_notification
                    _storage_title = auction.get("unit_label") or auction.get("title") or auction.get("unit_number") or "Storage Unit"
                    if new_status == "sold" and winner_id:
                        await create_notification(
                            db, user_id=winner_id, kind="auction_won",
                            params={"title": _storage_title, "amount": current_bid},
                            data={"auction_id": auction_id, "amount": current_bid,
                                  "action_url": f"/storage-auctions/{auction_id}"},
                        )
                    facility_user_id = facility.get("user_id") or facility.get("id")
                    if facility_user_id:
                        await create_notification(
                            db, user_id=facility_user_id,
                            kind=("auction_ended" if new_status == "sold" else "auction_ended_no_winner"),
                            params={"title": _storage_title, "amount": current_bid},
                            data={"auction_id": auction_id, "amount": current_bid,
                                  "action_url": "/storage-facility-dashboard"},
                        )
                except Exception as e:
                    logger.warning(f"[STORAGE_CLOSE] bilingual notif failed for {auction_id}: {e}")

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
    """Downgrade listings whose promotion has expired.

    Handles BOTH schemas:
      - New: is_promoted + promotion_end  (from /payments/promote-listing)
      - Legacy: promoted_until + promotion_tier + is_featured
    Runs against listings, vehicle_listings and storage_auctions.
    """
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        stats = {}
        expired_listings = []
        for coll_name in ("listings", "vehicle_listings", "storage_auctions", "multi_item_listings"):
            coll = db[coll_name]
            # First capture ids + seller_id for expiry notification emails (iter189)
            docs_to_expire = await coll.find(
                {
                    "$or": [
                        {"promoted_until":  {"$lt": now_iso}, "promotion_tier": {"$nin": [None, ""]}},
                        {"promoted_until":  {"$lt": now_iso}, "is_featured": True},
                        {"promotion_end":   {"$lt": now_iso}, "is_promoted": True},
                    ]
                },
                {"_id": 0, "id": 1, "seller_id": 1, "title": 1, "promotion_tier": 1},
            ).to_list(200)
            for d in docs_to_expire:
                d["listing_type"] = {
                    "listings": "marketplace",
                    "vehicle_listings": "vehicle",
                    "storage_auctions": "storage",
                    "multi_item_listings": "lots",
                }.get(coll_name, "marketplace")
                expired_listings.append(d)
            result = await coll.update_many(
                {
                    "$or": [
                        {"promoted_until":  {"$lt": now_iso}, "promotion_tier": {"$nin": [None, ""]}},
                        {"promoted_until":  {"$lt": now_iso}, "is_featured": True},
                        {"promotion_end":   {"$lt": now_iso}, "is_promoted": True},
                    ]
                },
                {"$set": {
                    "is_promoted": False,
                    "is_featured": False,
                    "promotion_tier": None,
                    "promotion_tier_weight": 0,
                    "promotion_expired_at": now_iso,
                }},
            )
            stats[coll_name] = result.modified_count

        # Also mark matching promotion rows as expired for the admin panel
        try:
            await db.promotions.update_many(
                {"status": "active", "end_date": {"$lt": now_iso}},
                {"$set": {"status": "expired", "expired_at": now_iso}},
            )
        except Exception:
            pass

        # Send expiry notification emails (iter189 Feature 1 — fire-and-forget, batch)
        if expired_listings:
            try:
                from services.emails.email_system import send_promotion_expired_email
                for d in expired_listings[:50]:  # cap to avoid scheduler overruns
                    try:
                        seller = await db.users.find_one(
                            {"id": d.get("seller_id")}, {"_id": 0, "email": 1, "name": 1}
                        )
                        if seller and seller.get("email"):
                            await send_promotion_expired_email(
                                seller_email=seller["email"],
                                seller_name=seller.get("name", "Seller"),
                                listing_title=d.get("title", "Your listing"),
                                listing_id=d.get("id"),
                                listing_type=d.get("listing_type"),
                                tier=d.get("promotion_tier", "basic"),
                            )
                    except Exception as notify_err:
                        logger.warning(f"[PROMOTIONS] expiry email error: {notify_err}")
            except ImportError:
                logger.info("[PROMOTIONS] send_promotion_expired_email not available — skip notifications")

        total = sum(stats.values())
        if total:
            logger.info(f"[PROMOTIONS] downgraded {total} expired promotions: {stats}")
        return {"downgraded": total, "per_collection": stats}
    except Exception as e:
        logger.error(f"[PROMOTIONS] downgrade error: {e}")
        return {"error": str(e)}



# ============= DEALER LICENSE EXPIRY (iter195) =============

async def process_expired_dealer_licenses(db):
    """Mark approved dealer licenses as 'expired' once their expiry_date passes.

    Sends a transactional email to the user notifying them to renew. Runs daily.
    """
    try:
        now = datetime.now(timezone.utc)
        # Find approved licenses whose expiry has passed (handles both ISO string + datetime)
        candidates = await db.dealer_licenses.find(
            {"status": "approved"},
            {"_id": 0}
        ).to_list(length=1000)

        expired_ids = []
        for d in candidates:
            exp = d.get("expiry_date")
            if isinstance(exp, str):
                try:
                    exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                except Exception:
                    exp = None
            if exp and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp and exp < now:
                expired_ids.append(d)

        if not expired_ids:
            return {"expired": 0}

        ids_to_update = [d["id"] for d in expired_ids]
        result = await db.dealer_licenses.update_many(
            {"id": {"$in": ids_to_update}},
            {"$set": {"status": "expired", "expired_at": now}},
        )

        # Send notification emails
        try:
            from services.emails.email_vehicles import send_dealer_license_expired_email
            for lic in expired_ids:
                try:
                    target_user = await db.users.find_one(
                        {"id": lic["user_id"]},
                        {"_id": 0, "email": 1, "name": 1},
                    )
                    if target_user and target_user.get("email"):
                        await send_dealer_license_expired_email(target_user, lic)
                except Exception as notify_err:
                    logger.warning(f"[DEALER-LICENSE] expiry email error: {notify_err}")
        except ImportError:
            logger.info("[DEALER-LICENSE] expired-email helper not available — skip notifications")

        logger.info(f"[DEALER-LICENSE] expired {result.modified_count} licenses")
        return {"expired": result.modified_count}
    except Exception as e:
        logger.error(f"[DEALER-LICENSE] expiry error: {e}")
        return {"error": str(e)}
