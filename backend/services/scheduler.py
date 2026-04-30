"""
BidVex Vehicle Auction - Background Scheduler Service
Handles automated auction processing, penalty application, and cleanup
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError, ConfigurationError

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None
db_instance = None

# Custom exception for database authentication errors
class DatabaseAuthenticationError(Exception):
    """Raised when database authentication fails"""
    pass


async def check_db_connection():
    """Verify database connection and permissions before running jobs"""
    global db_instance
    
    if db_instance is None:
        raise DatabaseAuthenticationError("Database not initialized")
    
    try:
        # Test basic read permission by running a simple command
        await db_instance.command('ping')
        return True
    except OperationFailure as e:
        error_code = e.details.get('code', 0)
        if error_code == 13:  # Unauthorized
            raise DatabaseAuthenticationError(
                f"Database authentication failed (Error 13): {e}. "
                "Please verify: 1) MONGO_URL has correct credentials, "
                "2) User has readWrite permission on the database, "
                "3) authSource is set correctly (e.g., ?authSource=admin)"
            )
        raise
    except ServerSelectionTimeoutError as e:
        raise DatabaseAuthenticationError(
            f"Could not connect to MongoDB server: {e}. "
            "Please verify: 1) MongoDB server is running, "
            "2) Network access is configured (IP whitelist for Atlas)"
        )
    except ConfigurationError as e:
        raise DatabaseAuthenticationError(
            f"MongoDB configuration error: {e}. "
            "Please verify MONGO_URL format is correct."
        )


async def safe_db_operation(operation_name: str, operation_func):
    """Wrapper to handle database operations with proper error handling"""
    try:
        return await operation_func()
    except OperationFailure as e:
        error_code = e.details.get('code', 0)
        if error_code == 13:  # Unauthorized
            logger.error(
                f"🔐 DATABASE AUTH FAILURE in {operation_name}: "
                f"Not authorized to execute command. Error: {e}"
            )
            logger.error(
                "🔧 FIX: Grant readWrite permissions to your MongoDB user. "
                "Run in MongoDB shell:\n"
                "  use admin\n"
                "  db.grantRolesToUser('your_username', [{role: 'readWrite', db: 'bazario_db'}])"
            )
            return {"error": "database_auth_failure", "details": str(e)}
        raise
    except ServerSelectionTimeoutError as e:
        logger.error(f"🔌 DATABASE CONNECTION TIMEOUT in {operation_name}: {e}")
        return {"error": "connection_timeout", "details": str(e)}
    except Exception as e:
        logger.exception(f"❌ UNEXPECTED ERROR in {operation_name}: {e}")
        return {"error": "unexpected_error", "details": str(e)}


async def process_ended_auctions_job():
    """Job: Process all ended vehicle auctions"""
    from services.vehicle_auction_handler import process_all_ended_auctions
    
    if db_instance is None:
        logger.warning("Database not initialized, skipping auction processing")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Running ended auctions job...")
        results = await process_all_ended_auctions(db_instance)
        sold_count = sum(1 for r in results if r.status == "sold")
        logger.info(f"Processed {len(results)} auctions: {sold_count} sold")
        return {
            "processed": len(results),
            "sold": sold_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    return await safe_db_operation("process_ended_auctions", _run)


async def activate_scheduled_auctions_job():
    """Job: Activate auctions that have reached their start time"""
    from services.vehicle_auction_handler import activate_scheduled_auctions
    
    if db_instance is None:
        logger.warning("Database not initialized, skipping auction activation")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Running auction activation job...")
        count = await activate_scheduled_auctions(db_instance)
        if count > 0:
            logger.info(f"Activated {count} scheduled auctions")
        return {
            "activated": count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    return await safe_db_operation("activate_scheduled_auctions", _run)


async def apply_late_penalties_job():
    """Job: Apply late payment penalties to overdue invoices"""
    from services.vehicle_invoice import check_and_apply_late_penalties
    
    if db_instance is None:
        logger.warning("Database not initialized, skipping penalty application")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Running late penalties job...")
        penalties = await check_and_apply_late_penalties(db_instance)
        if penalties:
            logger.warning(f"Applied penalties to {len(penalties)} overdue invoices")
        return {
            "penalties_applied": len(penalties),
            "invoices": [p["invoice_number"] for p in penalties],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    return await safe_db_operation("apply_late_penalties", _run)


async def cleanup_expired_deposits_job():
    """Job: Clean up expired pending deposits"""
    if db_instance is None:
        logger.warning("Database not initialized, skipping deposit cleanup")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Running deposit cleanup job...")
        now = datetime.now(timezone.utc)
        
        # Find deposits that have been pending for more than 24 hours
        from datetime import timedelta
        cutoff = now - timedelta(hours=24)
        
        result = await db_instance.vehicle_bid_deposits.update_many(
            {
                "status": "pending",
                "created_at": {"$lt": cutoff}
            },
            {
                "$set": {
                    "status": "expired",
                    "expired_at": now
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Expired {result.modified_count} stale pending deposits")
        
        return {
            "expired_deposits": result.modified_count,
            "timestamp": now.isoformat()
        }
    
    return await safe_db_operation("cleanup_expired_deposits", _run)


async def cleanup_expired_sessions_job():
    """Job: Clean up expired payment sessions"""
    if db_instance is None:
        logger.warning("Database not initialized, skipping session cleanup")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Running payment session cleanup job...")
        now = datetime.now(timezone.utc)
        
        from datetime import timedelta
        cutoff = now - timedelta(hours=24)
        
        result = await db_instance.payment_transactions.update_many(
            {
                "payment_status": "initiated",
                "created_at": {"$lt": cutoff}
            },
            {
                "$set": {
                    "payment_status": "expired",
                    "expired_at": now
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Expired {result.modified_count} stale payment sessions")
        
        return {
            "expired_sessions": result.modified_count,
            "timestamp": now.isoformat()
        }
    
    return await safe_db_operation("cleanup_expired_sessions", _run)


async def daily_summary_job():
    """Job: Generate daily auction summary (for logging/monitoring)"""
    if db_instance is None:
        logger.warning("Database not initialized, skipping daily summary")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Generating daily summary...")
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count today's activities
        new_listings = await db_instance.vehicle_listings.count_documents({
            "created_at": {"$gte": start_of_day}
        })
        
        completed_auctions = await db_instance.vehicle_listings.count_documents({
            "status": "sold",
            "sold_at": {"$gte": start_of_day}
        })
        
        new_sellers = await db_instance.vehicle_sellers.count_documents({
            "created_at": {"$gte": start_of_day}
        })
        
        new_bids = await db_instance.vehicle_bids.count_documents({
            "created_at": {"$gte": start_of_day}
        })
        
        summary = {
            "date": start_of_day.date().isoformat(),
            "new_listings": new_listings,
            "completed_auctions": completed_auctions,
            "new_sellers": new_sellers,
            "new_bids": new_bids,
            "generated_at": now.isoformat()
        }
        
        logger.info(f"Daily summary: {summary}")
        
        # Store summary
        await db_instance.scheduler_logs.insert_one({
            "job": "daily_summary",
            **summary
        })
        
        return summary
    
    return await safe_db_operation("daily_summary", _run)


async def check_subscription_expirations_job():
    """
    Job: Check for expired manual subscriptions and downgrade to Free
    
    Runs daily at 00:30 UTC
    - Finds all manual subscriptions where end_date < now
    - Downgrades to Free plan
    - Sends expiration email
    - Logs all changes
    """
    if db_instance is None:
        logger.warning("Database not initialized, skipping subscription check")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Checking for expired subscriptions...")
        now = datetime.now(timezone.utc)
        
        # Find expired manual subscriptions
        expired_users = await db_instance.users.find({
            "subscription_source": "manual",
            "subscription_status": "active",
            "subscription_tier": {"$ne": "free"},
            "subscription_end_date": {"$lt": now.isoformat()}
        }).to_list(None)
        
        expired_count = 0
        for user in expired_users:
            try:
                previous_plan = user.get("subscription_tier")
                
                # Downgrade to free
                await db_instance.users.update_one(
                    {"id": user["id"]},
                    {
                        "$set": {
                            "subscription_tier": "free",
                            "subscription_status": "expired",
                            "subscription_expired_at": now.isoformat(),
                            "updated_at": now.isoformat()
                        }
                    }
                )
                
                # Log to audit
                await db_instance.subscription_audit_logs.insert_one({
                    "id": str(uuid.uuid4()),
                    "action": "subscription_auto_expired",
                    "user_id": user["id"],
                    "user_email": user.get("email"),
                    "admin_id": "system",
                    "admin_email": "system@bidvex.com",
                    "previous_values": {"plan": previous_plan},
                    "new_values": {"plan": "free", "status": "expired"},
                    "reason": "Automatic expiration - subscription end date reached",
                    "timestamp": now.isoformat()
                })
                
                # Send expiration email
                try:
                    from services.email_notifications import send_subscription_expired_email
                    await send_subscription_expired_email(
                        user_email=user.get("email"),
                        user_name=user.get("name", user.get("email")),
                        previous_plan=previous_plan
                    )
                except Exception as email_error:
                    logger.error(f"Failed to send expiration email to {user.get('email')}: {email_error}")
                
                expired_count += 1
                logger.info(f"Expired subscription for {user.get('email')}: {previous_plan} -> free")
                
            except Exception as user_error:
                logger.error(f"Error expiring subscription for user {user.get('id')}: {user_error}")
        
        logger.info(f"Subscription expiration job completed: {expired_count} subscriptions expired")
        
        return {
            "expired_count": expired_count,
            "timestamp": now.isoformat()
        }
    
    return await safe_db_operation("check_subscription_expirations", _run)


async def send_subscription_reminders_job():
    """
    Job: Send reminder emails for subscriptions expiring in 3 days
    
    Runs daily at 01:00 UTC
    """
    if db_instance is None:
        logger.warning("Database not initialized, skipping subscription reminders")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Checking for subscription expiration reminders...")
        now = datetime.now(timezone.utc)
        
        from datetime import timedelta
        
        # Find subscriptions expiring in exactly 3 days
        reminder_date_start = now + timedelta(days=2, hours=23)  # ~3 days from now
        reminder_date_end = now + timedelta(days=3, hours=1)      # Window of 2 hours
        
        expiring_users = await db_instance.users.find({
            "subscription_source": "manual",
            "subscription_status": "active",
            "subscription_tier": {"$ne": "free"},
            "subscription_end_date": {
                "$gte": reminder_date_start.isoformat(),
                "$lt": reminder_date_end.isoformat()
            },
            # Don't send reminder if already sent
            "subscription_reminder_sent": {"$ne": True}
        }).to_list(None)
        
        reminder_count = 0
        for user in expiring_users:
            try:
                end_date = user.get("subscription_end_date")
                if isinstance(end_date, str):
                    end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                days_left = (end_date - now).days
                
                # Send reminder email
                try:
                    from services.email_notifications import send_subscription_reminder_email
                    await send_subscription_reminder_email(
                        user_email=user.get("email"),
                        user_name=user.get("name", user.get("email")),
                        plan=user.get("subscription_tier"),
                        days_remaining=days_left,
                        end_date=end_date.strftime("%B %d, %Y")
                    )
                    
                    # Mark reminder as sent
                    await db_instance.users.update_one(
                        {"id": user["id"]},
                        {"$set": {"subscription_reminder_sent": True}}
                    )
                    
                    reminder_count += 1
                    logger.info(f"Sent subscription reminder to {user.get('email')} - expires in {days_left} days")
                    
                except Exception as email_error:
                    logger.error(f"Failed to send reminder email to {user.get('email')}: {email_error}")
                
            except Exception as user_error:
                logger.error(f"Error sending reminder to user {user.get('id')}: {user_error}")
        
        logger.info(f"Subscription reminder job completed: {reminder_count} reminders sent")
        
        return {
            "reminders_sent": reminder_count,
            "timestamp": now.isoformat()
        }
    
    return await safe_db_operation("send_subscription_reminders", _run)


async def process_scheduled_campaigns_job():
    """
    Job: Process scheduled email campaigns
    
    Runs every 5 minutes
    - Finds scheduled campaigns where scheduled_at <= now
    - Sends each campaign
    """
    if db_instance is None:
        logger.warning("Database not initialized, skipping scheduled campaigns")
        return {"error": "db_not_initialized"}
    
    async def _run():
        logger.info("Checking for scheduled email campaigns...")
        now = datetime.now(timezone.utc)
        
        # Find campaigns ready to send
        ready_campaigns = await db_instance.email_campaigns.find({
            "status": "scheduled",
            "scheduled_at": {"$lte": now.isoformat()}
        }).to_list(None)
        
        if not ready_campaigns:
            return {"processed": 0}
        
        from services.email_marketing import get_marketing_service
        marketing = get_marketing_service(db_instance)
        
        processed_count = 0
        for campaign in ready_campaigns:
            try:
                logger.info(f"Processing scheduled campaign: {campaign['id']} - {campaign['name']}")
                
                # Update status to sending
                await db_instance.email_campaigns.update_one(
                    {"id": campaign["id"]},
                    {"$set": {
                        "status": "sending",
                        "sent_at": now.isoformat(),
                        "updated_at": now.isoformat()
                    }}
                )
                
                # Execute send
                result = await marketing._execute_campaign_send(campaign["id"])
                processed_count += 1
                
                logger.info(f"Campaign {campaign['id']} sent: {result}")
                
            except Exception as campaign_error:
                logger.error(f"Error sending campaign {campaign['id']}: {campaign_error}")
                
                # Mark as failed
                await db_instance.email_campaigns.update_one(
                    {"id": campaign["id"]},
                    {"$set": {
                        "status": "failed",
                        "error": str(campaign_error),
                        "updated_at": now.isoformat()
                    }}
                )
        
        logger.info(f"Processed {processed_count} scheduled campaigns")
        
        return {
            "processed": processed_count,
            "timestamp": now.isoformat()
        }
    
    return await safe_db_operation("process_scheduled_campaigns", _run)


# ─────────────────────────────────────────────────────────────
# VEHICLE SETTLEMENT CONFIRMATION REMINDERS (iteration 167)
# ─────────────────────────────────────────────────────────────
# D+7 post fee payment → reminder email to dealer.
# D+14 post fee payment → admin alert + nudge email to buyer.

async def _send_settlement_reminder_emails():
    """Send D+7 dealer reminders and D+14 admin/buyer alerts."""
    db = db_instance
    if db is None:
        return
    from services.email_notifications import send_email
    from datetime import timedelta
    import os as _os
    now = datetime.now(timezone.utc)
    day7 = (now - timedelta(days=7)).isoformat()
    day8 = (now - timedelta(days=8)).isoformat()
    day14 = (now - timedelta(days=14)).isoformat()
    day15 = (now - timedelta(days=15)).isoformat()

    # ── D+7 dealer reminder (only if not already sent) ──
    cursor = db.vehicle_settlements.find({
        "settlement_status": "AWAITING_DEALER_CONFIRMATION",
        "fee_paid_at": {"$gte": day8, "$lte": day7},
        "dealer_reminder_d7_sent_at": {"$exists": False},
    })
    async for s in cursor:
        seller_id = s.get("seller_id")
        if not seller_id:
            continue
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1, "name": 1})
        if not seller or not seller.get("email"):
            continue
        vehicle_id = s["auction_id"]
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
          <h2 style="color:#F59E0B;">Action needed — Confirm Vehicle Settlement</h2>
          <p>The buyer paid the BidVex platform fee 7 days ago for vehicle <strong>#{vehicle_id[:8]}</strong>.</p>
          <p>Please visit your <a href="https://www.bidvex.com/seller-dashboard?tab=vehicle-settlements" style="color:#2186C6;">Vehicle Settlements dashboard</a> and confirm the transaction is complete — this keeps our audit trail intact for the OPC.</p>
          <hr style="border:none;border-top:1px solid #eee;"/>
          <p><strong>FR :</strong> L'acheteur a payé les frais de plateforme BidVex il y a 7 jours pour le véhicule <strong>#{vehicle_id[:8]}</strong>. Veuillez confirmer la transaction dans votre <a href="https://www.bidvex.com/seller-dashboard?tab=vehicle-settlements" style="color:#2186C6;">tableau de bord</a>.</p>
        </div>
        """
        try:
            await send_email(seller["email"], "Reminder — Confirm Vehicle Settlement", html)
            await db.vehicle_settlements.update_one(
                {"auction_id": vehicle_id},
                {"$set": {"dealer_reminder_d7_sent_at": now.isoformat()}},
            )
        except Exception as e:
            logger.error(f"[SETTLEMENT_REMINDER] D+7 email failed for {vehicle_id}: {e}")

    # ── D+14 admin alert + buyer nudge ──
    admin_email = (
        _os.environ.get("ADMIN_NOTIFICATION_EMAIL")
        or _os.environ.get("ADMIN_EMAIL")
        or "info@bidvex.com"
    )
    cursor = db.vehicle_settlements.find({
        "settlement_status": "AWAITING_DEALER_CONFIRMATION",
        "fee_paid_at": {"$gte": day15, "$lte": day14},
        "admin_alert_d14_sent_at": {"$exists": False},
    })
    async for s in cursor:
        vehicle_id = s["auction_id"]
        html_admin = f"""
        <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
          <h2 style="color:#DC2626;">⚠️ Dealer hasn't confirmed settlement — 14 days</h2>
          <p>Vehicle <strong>#{vehicle_id[:8]}</strong> has been waiting for dealer confirmation for 14 days.</p>
          <p>Dealer: {s.get('seller_id','')}<br/>Buyer: {s.get('buyer_id','')}<br/>Hammer: ${s.get('hammer_price',0):,.2f} CAD</p>
          <p><a href="https://www.bidvex.com/admin" style="color:#2186C6;">Open admin queue</a></p>
        </div>
        """
        try:
            await send_email(admin_email, f"[Settlement D+14] Vehicle #{vehicle_id[:8]} unconfirmed", html_admin)
            buyer = await db.users.find_one({"id": s.get("buyer_id")}, {"_id": 0, "email": 1})
            if buyer and buyer.get("email"):
                html_buyer = f"""
                <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
                  <h2 style="color:#F59E0B;">Settlement still pending — 14 days</h2>
                  <p>The dealer hasn't yet confirmed the settlement for vehicle <strong>#{vehicle_id[:8]}</strong>.</p>
                  <p>If the vehicle has already been paid for and delivered, no action is needed. If there's an issue, you can <a href="https://www.bidvex.com/buyer-dashboard" style="color:#2186C6;">open a dispute</a>.</p>
                </div>
                """
                await send_email(buyer["email"], f"Vehicle #{vehicle_id[:8]} — Settlement update", html_buyer)
            await db.vehicle_settlements.update_one(
                {"auction_id": vehicle_id},
                {"$set": {"admin_alert_d14_sent_at": now.isoformat()}},
            )
        except Exception as e:
            logger.error(f"[SETTLEMENT_REMINDER] D+14 email failed for {vehicle_id}: {e}")


async def settlement_reminders_job():
    """Daily: send D+7 dealer reminders and D+14 admin/buyer alerts."""
    async def _run():
        await _send_settlement_reminder_emails()
        return 0
    return await safe_db_operation("settlement_reminders", _run)



def init_scheduler(database):
    """Initialize the background scheduler with all jobs"""
    global scheduler, db_instance
    
    db_instance = database
    scheduler = AsyncIOScheduler()
    
    # Job 1: Process ended auctions - every minute
    scheduler.add_job(
        process_ended_auctions_job,
        IntervalTrigger(minutes=1),
        id="process_ended_auctions",
        name="Process Ended Auctions",
        replace_existing=True
    )
    
    # Job 2: Activate scheduled auctions - every minute
    scheduler.add_job(
        activate_scheduled_auctions_job,
        IntervalTrigger(minutes=1),
        id="activate_scheduled_auctions",
        name="Activate Scheduled Auctions",
        replace_existing=True
    )
    
    # Job 3: Apply late penalties - daily at midnight
    scheduler.add_job(
        apply_late_penalties_job,
        CronTrigger(hour=0, minute=5),
        id="apply_late_penalties",
        name="Apply Late Payment Penalties",
        replace_existing=True
    )
    
    # Job 4: Cleanup expired deposits - every hour
    scheduler.add_job(
        cleanup_expired_deposits_job,
        IntervalTrigger(hours=1),
        id="cleanup_expired_deposits",
        name="Cleanup Expired Deposits",
        replace_existing=True
    )
    
    # Job 5: Cleanup expired payment sessions - every hour
    scheduler.add_job(
        cleanup_expired_sessions_job,
        IntervalTrigger(hours=1),
        id="cleanup_expired_sessions",
        name="Cleanup Expired Sessions",
        replace_existing=True
    )
    
    # Job 6: Daily summary - every day at 11:55 PM
    scheduler.add_job(
        daily_summary_job,
        CronTrigger(hour=23, minute=55),
        id="daily_summary",
        name="Daily Summary",
        replace_existing=True
    )

    # Job 6b: Vehicle settlement confirmation reminders - daily at 9:00 AM UTC
    scheduler.add_job(
        settlement_reminders_job,
        CronTrigger(hour=9, minute=0),
        id="settlement_reminders",
        name="Vehicle Settlement Confirmation Reminders",
        replace_existing=True,
    )
    
    # Job 7: Check subscription expirations - daily at 00:30 UTC
    scheduler.add_job(
        check_subscription_expirations_job,
        CronTrigger(hour=0, minute=30),
        id="check_subscription_expirations",
        name="Check Subscription Expirations",
        replace_existing=True
    )
    
    # Job 8: Auction ending soon notifications - every 5 minutes
    async def ending_soon_job():
        if db_instance is None:
            return
        from services.scheduled_jobs import send_auction_ending_soon_notifications
        await send_auction_ending_soon_notifications(db_instance)
    
    scheduler.add_job(
        ending_soon_job,
        IntervalTrigger(minutes=5),
        id="auction_ending_soon_notifications",
        name="Auction Ending Soon Notifications",
        replace_existing=True
    )
    
    # Job 8: Send subscription reminders - daily at 01:00 UTC
    scheduler.add_job(
        send_subscription_reminders_job,
        CronTrigger(hour=1, minute=0),
        id="send_subscription_reminders",
        name="Send Subscription Reminders",
        replace_existing=True
    )
    
    # Job 9: Process scheduled email campaigns - every 5 minutes
    scheduler.add_job(
        process_scheduled_campaigns_job,
        IntervalTrigger(minutes=5),
        id="process_scheduled_campaigns",
        name="Process Scheduled Email Campaigns",
        replace_existing=True
    )
    
    logger.info("Scheduler initialized with 9 jobs")
    return scheduler


def start_scheduler():
    """Start the scheduler"""
    global scheduler
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")


def get_scheduler_status() -> dict:
    """Get current scheduler status and job info"""
    global scheduler
    
    if scheduler is None:
        return {"status": "not_initialized"}
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    
    return {
        "status": "running" if scheduler.running else "stopped",
        "jobs": jobs
    }


async def run_job_manually(job_id: str) -> dict:
    """Manually trigger a specific job"""
    global scheduler
    
    if scheduler is None:
        return {"error": "Scheduler not initialized"}
    
    job = scheduler.get_job(job_id)
    if not job:
        return {"error": f"Job '{job_id}' not found"}
    
    # Run the job function directly
    job_funcs = {
        "process_ended_auctions": process_ended_auctions_job,
        "activate_scheduled_auctions": activate_scheduled_auctions_job,
        "apply_late_penalties": apply_late_penalties_job,
        "cleanup_expired_deposits": cleanup_expired_deposits_job,
        "cleanup_expired_sessions": cleanup_expired_sessions_job,
        "daily_summary": daily_summary_job
    }
    
    func = job_funcs.get(job_id)
    if func:
        result = await func()
        return {
            "job_id": job_id,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "result": result
        }
    
    return {"error": f"Job function not found for '{job_id}'"}
