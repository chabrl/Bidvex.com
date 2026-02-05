"""
BidVex Vehicle Auction - Background Scheduler Service
Handles automated auction processing, penalty application, and cleanup
"""

import asyncio
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None
db_instance = None


async def process_ended_auctions_job():
    """Job: Process all ended vehicle auctions"""
    from services.vehicle_auction_handler import process_all_ended_auctions
    
    if not db_instance:
        logger.warning("Database not initialized, skipping auction processing")
        return
    
    try:
        logger.info("Running ended auctions job...")
        results = await process_all_ended_auctions(db_instance)
        
        sold_count = sum(1 for r in results if r.status == "sold")
        logger.info(f"Processed {len(results)} auctions: {sold_count} sold")
        
        return {
            "processed": len(results),
            "sold": sold_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.exception(f"Error in ended auctions job: {e}")
        return {"error": str(e)}


async def activate_scheduled_auctions_job():
    """Job: Activate auctions that have reached their start time"""
    from services.vehicle_auction_handler import activate_scheduled_auctions
    
    if not db_instance:
        logger.warning("Database not initialized, skipping auction activation")
        return
    
    try:
        logger.info("Running auction activation job...")
        count = await activate_scheduled_auctions(db_instance)
        
        if count > 0:
            logger.info(f"Activated {count} scheduled auctions")
        
        return {
            "activated": count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.exception(f"Error in auction activation job: {e}")
        return {"error": str(e)}


async def apply_late_penalties_job():
    """Job: Apply late payment penalties to overdue invoices"""
    from services.vehicle_invoice import check_and_apply_late_penalties
    
    if not db_instance:
        logger.warning("Database not initialized, skipping penalty application")
        return
    
    try:
        logger.info("Running late penalties job...")
        penalties = await check_and_apply_late_penalties(db_instance)
        
        if penalties:
            logger.warning(f"Applied penalties to {len(penalties)} overdue invoices")
        
        return {
            "penalties_applied": len(penalties),
            "invoices": [p["invoice_number"] for p in penalties],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.exception(f"Error in late penalties job: {e}")
        return {"error": str(e)}


async def cleanup_expired_deposits_job():
    """Job: Clean up expired pending deposits"""
    if not db_instance:
        return
    
    try:
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
    except Exception as e:
        logger.exception(f"Error in deposit cleanup job: {e}")
        return {"error": str(e)}


async def cleanup_expired_sessions_job():
    """Job: Clean up expired payment sessions"""
    if not db_instance:
        return
    
    try:
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
    except Exception as e:
        logger.exception(f"Error in session cleanup job: {e}")
        return {"error": str(e)}


async def daily_summary_job():
    """Job: Generate daily auction summary (for logging/monitoring)"""
    if not db_instance:
        return
    
    try:
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
    except Exception as e:
        logger.exception(f"Error in daily summary job: {e}")
        return {"error": str(e)}


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
    
    logger.info("Scheduler initialized with 6 jobs")
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
    
    if not scheduler:
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
    
    if not scheduler:
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
