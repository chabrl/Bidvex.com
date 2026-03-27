"""
BidVex Auction Marketplace — Server Entry Point
All business logic lives in /routes/* modules.
This file: app creation, middleware, DB setup, router registration, startup events.
"""

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime, timezone, timedelta
import os
import logging
import uuid
import time as _time
import httpx

# ─── Environment ───
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=False)

mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'bazario_db')
stripe_api_key = os.environ.get('STRIPE_API_KEY', '')

# ─── Database (connection pooling) ───
from pymongo import ReadPreference
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=5000,
    maxPoolSize=50,
    minPoolSize=2,
    connectTimeoutMS=10000,
    socketTimeoutMS=20000,
    retryReads=True,
    retryWrites=True,
    w="majority",
)
db = client[db_name]
# Use secondary-preferred reads so queries don't wait for a failing primary
db_read = client.get_database(db_name, read_preference=ReadPreference.SECONDARY_PREFERRED)

import stripe
if stripe_api_key:
    stripe.api_key = stripe_api_key

# ─── App ───
app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Trust proxy headers from Cloudflare/Railway
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── WWW → non-WWW Redirect Middleware ───
from starlette.responses import RedirectResponse
@app.middleware("http")
async def www_redirect(request: Request, call_next):
    host = request.headers.get("host", "")
    if host.startswith("www."):
        non_www_host = host[4:]
        url = str(request.url).replace(f"://{host}", f"://{non_www_host}", 1)
        return RedirectResponse(url=url, status_code=301)
    return await call_next(request)

# ─── Response Time Logging Middleware ───
@app.middleware("http")
async def response_time_middleware(request: Request, call_next):
    start = _time.monotonic()
    response = await call_next(request)
    elapsed = round((_time.monotonic() - start) * 1000)
    path = request.url.path
    if not path.startswith("/health") and elapsed > 500:
        logger.warning(f"SLOW {request.method} {path} — {elapsed}ms")
    response.headers["X-Response-Time"] = f"{elapsed}ms"
    # FIX 5: Cache-Control — static assets get 1yr, HTML must revalidate
    if path.startswith("/static/") or any(path.endswith(ext) for ext in (".js", ".css", ".woff2", ".woff")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".gif")):
        response.headers["Cache-Control"] = "public, max-age=31536000"
    elif path.endswith(".html") or path == "/":
        response.headers["Cache-Control"] = "no-cache"
    # FIX 8: Security headers
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://assets.emergent.sh https://unpkg.com https://d2adkz2s9zrlge.cloudfront.net https://cdn.tailwindcss.com https://us-assets.i.posthog.com https://js.stripe.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https: http:; "
        "connect-src 'self' https: wss:; "
        "frame-src 'self' https://js.stripe.com; "
        "object-src 'none'; "
        "base-uri 'self'"
    )
    return response

# ─── Rate Limiting ───
from rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── WebSocket Managers ───
from ws_managers import ConnectionManager, MessageConnectionManager

manager = ConnectionManager()
message_manager = MessageConnectionManager()

# ─── Auth (shared by router injection) ───
from deps import set_db as set_deps_db, get_current_user
set_deps_db(db)

# ─── Scheduler ───
scheduler = AsyncIOScheduler()

async def transition_upcoming_auctions():
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

async def run_process_ended_auctions():
    from routes.auctions import process_ended_auctions
    await process_ended_auctions()

scheduler.add_job(transition_upcoming_auctions, trigger=IntervalTrigger(minutes=5),
                  id='transition_upcoming_auctions', replace_existing=True)
scheduler.add_job(run_process_ended_auctions, trigger=IntervalTrigger(minutes=1),
                  id='process_ended_auctions', replace_existing=True)


async def expire_partner_pro_trials():
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
            # Send trial-expired email
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


async def send_trial_reminder_emails():
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


scheduler.add_job(expire_partner_pro_trials, trigger=IntervalTrigger(hours=1),
                  id='expire_partner_pro_trials', replace_existing=True)
scheduler.add_job(send_trial_reminder_emails, trigger=IntervalTrigger(hours=1),
                  id='send_trial_reminder_emails', replace_existing=True)


async def send_auction_payment_reminders():
    """Send payment reminders for auctions where deadline is in ~4 days (day 10 of 14)."""
    try:
        now = datetime.now(timezone.utc)
        # Find listings with payment due in 3-5 days that haven't had a reminder sent
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


async def process_overdue_auction_payments():
    """Mark overdue payments (day 14+) and apply 2%/month penalty."""
    try:
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

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

                # Calculate penalty (2% per month, minimum 1 month)
                deadline_dt = datetime.fromisoformat(listing["payment_deadline"])
                days_late = max(0, (now - deadline_dt).days)
                months_late = max(1, (days_late + 29) // 30)
                penalty_rate = 0.02 * months_late
                penalty_amount = round(hammer_price * penalty_rate, 2)
                total_with_penalty = hammer_price + penalty_amount

                # Update listing
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

                # Create overdue notification
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

                # Send overdue email
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
                        total_with_penalty=total_with_penalty,
                    )

                logger.info(f"Overdue processed for listing {listing_id}: penalty=${penalty_amount:.2f}")
            except Exception as e:
                logger.error(f"Failed to process overdue for listing {listing.get('id')}: {e}")
    except Exception as e:
        logger.error(f"Error in process_overdue_auction_payments: {e}")


scheduler.add_job(send_auction_payment_reminders, trigger=IntervalTrigger(hours=6),
                  id='send_auction_payment_reminders', replace_existing=True)
scheduler.add_job(process_overdue_auction_payments, trigger=IntervalTrigger(hours=6),
                  id='process_overdue_auction_payments', replace_existing=True)


async def send_review_request_emails():
    """Send 'How was your purchase?' emails 24h after payment confirmation."""
    try:
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

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


scheduler.add_job(send_review_request_emails, trigger=IntervalTrigger(hours=1),
                  id='send_review_request_emails', replace_existing=True)

# ─── Keep-Alive Self-Ping (prevents backend sleep) ───
async def keepalive_ping():
    """Ping own endpoints every 4 min to prevent cold starts."""
    endpoints = ["/api/health", "/api/marketplace/items?limit=1", "/api/multi-item-listings?limit=1"]
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=10) as c:
        for ep in endpoints:
            try:
                r = await c.get(ep)
                logger.debug(f"[keepalive] GET {ep} → {r.status_code} ({r.elapsed.total_seconds():.2f}s)")
            except Exception as e:
                logger.debug(f"[keepalive] GET {ep} → error: {e}")

scheduler.add_job(keepalive_ping, trigger=IntervalTrigger(minutes=4),
                  id='keepalive_ping', replace_existing=True)

# ─── Health Endpoints ───
@api_router.get("/")
async def root():
    return {"message": "Bazario API v1.0"}

@api_router.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "healthy"}

# ─── Register All Routers ───
try:
    # Core routers (with dependency injection)
    from routes.analytics import analytics_router, set_db as set_analytics_db
    from routes.auctions import auctions_router, bids_router, set_db as set_auctions_db, set_notification_manager, set_ws_manager, set_sms_service_getter
    from routes.sms_verification import sms_router, set_db as set_sms_db
    from routes.users import users_router, set_users_db, set_users_auth
    from routes.marketing import marketing_router, set_marketing_db, set_marketing_auth, set_marketing_services
    from routes.admin import admin_router, set_admin_db, set_admin_auth, set_admin_email_service
    from routes.webhooks import webhooks_router, set_webhooks_db, set_webhooks_marketing_service
    from routes.payments import payments_router, set_payments_db, set_payments_auth
    from routes.marketplace import marketplace_router, set_marketplace_db
    from routes.listings import listings_router, set_listings_db
    from routes.auth import auth_router, set_auth_db
    from routes.dashboard import dashboard_router, set_dashboard_db, set_dashboard_auth
    from routes.profiles import profiles_router, set_profiles_db, set_profiles_auth
    from services.email_service import get_email_service
    from services.email_marketing import get_marketing_service, SEGMENT_FILTERS, CAMPAIGN_STATUS
    from services.user_email_marketing import get_user_marketing_service, SUBSCRIPTION_LIMITS

    # Inject DB into all core routers
    for setter in [set_analytics_db, set_auctions_db, set_sms_db, set_users_db,
                   set_marketing_db, set_admin_db, set_webhooks_db, set_payments_db,
                   set_marketplace_db, set_listings_db, set_auth_db, set_dashboard_db, set_profiles_db]:
        setter(db)

    # Inject fast-read DB (secondary-preferred) for read-heavy modules
    from routes.listings import set_listings_read_db
    from routes.marketplace import set_marketplace_read_db
    from routes.dashboard import set_dashboard_read_db
    for setter in [set_listings_read_db, set_marketplace_read_db, set_dashboard_read_db]:
        try:
            setter(db_read)
        except Exception:
            pass

    # Inject auth
    for setter in [set_users_auth, set_marketing_auth, set_admin_auth,
                   set_payments_auth, set_dashboard_auth, set_profiles_auth]:
        setter(get_current_user)

    # Inject services
    set_marketing_services(get_marketing_service, get_user_marketing_service, SEGMENT_FILTERS, CAMPAIGN_STATUS, SUBSCRIPTION_LIMITS)
    set_webhooks_marketing_service(get_marketing_service)
    set_admin_email_service(get_email_service())
    set_notification_manager(message_manager)
    set_ws_manager(manager)
    try:
        from services.sms_notifications import get_sms_notification_service
        set_sms_service_getter(get_sms_notification_service)
    except ImportError:
        pass

    # Include core routers
    for router in [analytics_router, auctions_router, bids_router, listings_router,
                   auth_router, sms_router, payments_router, webhooks_router,
                   marketplace_router, admin_router, dashboard_router, profiles_router]:
        api_router.include_router(router)

    # Self-contained routers (import from deps directly)
    SELF_CONTAINED_ROUTERS = [
        ("routes.team", "team_router", "set_team_db", True),  # True = app-level
        ("routes.ai_chat", "ai_chat_router", "set_ai_chat_db", False),
        ("routes.fees", "fees_router", None, False),
        ("routes.notifications", "notifications_router", None, False),
        ("routes.watchlist", "watchlist_router", None, False),
        ("routes.tax", "tax_calc_router", None, False),
        ("routes.messages", "messages_router", "set_messages_db", False),
        ("routes.tax_reports", "tax_router", "set_tax_db", False),
        ("routes.tax_dashboard", "tax_dashboard_router", "set_tax_dashboard_db", False),
        ("routes.carousel", "carousel_router", "set_carousel_db", False),
        ("routes.site_config", "site_config_router", "set_site_config_db", False),
        ("routes.subscriptions", "subscriptions_router", None, False),
        ("routes.invoices", "invoices_router", None, False),
        ("routes.partners", "partners_router", None, False),
        ("routes.admin_config", "admin_config_router", None, False),
        ("routes.admin_ops", "admin_ops_router", None, False),
        ("routes.trust_safety", "trust_safety_router", None, False),
        ("routes.email_marketing_ext", "email_marketing_ext_router", None, False),
        ("routes.legal", "legal_router", None, False),
        ("routes.site_mode", "site_mode_router", None, False),
        ("routes.misc", "misc_router", None, False),
        ("routes.partner_pro", "partner_pro_router", "set_partner_pro_db", False),
        ("routes.reviews", "reviews_router", "set_reviews_db", False),
    ]

    for module_path, router_name, db_setter_name, app_level in SELF_CONTAINED_ROUTERS:
        try:
            mod = __import__(module_path, fromlist=[router_name])
            router_obj = getattr(mod, router_name)
            if db_setter_name:
                db_setter = getattr(mod, db_setter_name)
                db_setter(db)
            # Special: messages router needs managers
            if module_path == "routes.messages":
                mod.set_message_managers(message_manager, manager)
            if app_level:
                app.include_router(router_obj)
            else:
                api_router.include_router(router_obj)
        except Exception as e:
            import traceback
            logger.error(f"FAILED to load {module_path}: {e}\n{traceback.format_exc()}")

    logger.info("All routers registered")

except Exception as e:
    logger.error(f"CRITICAL: Could not load modular routers: {e}")
    import traceback
    traceback.print_exc()

# ─── Vehicle Module (standalone) ───
try:
    from routes.vehicles import vehicle_router, set_vehicle_db
    from services.scheduler import init_scheduler as init_vehicle_scheduler, start_scheduler as start_vehicle_scheduler
    set_vehicle_db(db)
    init_vehicle_scheduler(db)
    app.include_router(vehicle_router)

    @app.on_event("startup")
    async def start_vehicle_auction_scheduler():
        try:
            start_vehicle_scheduler()
        except Exception as e:
            logger.error(f"Failed to start vehicle scheduler: {e}")
except ImportError:
    pass

# ─── WebSocket Handlers ───
from ws_handlers import register_ws_handlers
register_ws_handlers(app, db, manager, message_manager)

# ─── Mount API Router ───
app.include_router(api_router)

@app.get("/")
async def root():
    """Serve React SPA index.html or return healthy JSON"""
    import os
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "build", "index.html")
    if os.path.isfile(index_path):
        from starlette.responses import FileResponse
        return FileResponse(index_path, media_type="text/html")
    return {"status": "healthy", "service": "BidVex API", "version": "1.0"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    import os
    fav_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "build", "favicon.ico")
    if os.path.exists(fav_path):
        from starlette.responses import FileResponse
        return FileResponse(fav_path)
    return {"status": "no favicon"}

@app.api_route("/health", methods=["GET", "HEAD"])
async def root_health():
    return {"status": "healthy"}

# ─── Lifecycle Events ───
@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
    logger.info("APScheduler started")

@app.on_event("startup")
async def log_db_status():
    import asyncio
    async def _check():
        try:
            count = await db.categories.count_documents({})
            logger.info(f"DB connected — categories found: {count}")
            users = await db.users.count_documents({})
            logger.info(f"DB connected — users found: {users}")
        except Exception as e:
            logger.warning(f"DB status check failed (non-fatal): {e}")
    asyncio.ensure_future(_check())

@app.on_event("startup")
async def prewarm_caches():
    """Pre-warm frequently-accessed data so first user never waits."""
    import asyncio
    async def _warm():
        try:
            # 1. Subscription plans
            from services.subscription_pricing import get_pricing_service
            ps = get_pricing_service(db)
            await ps.get_all_plans()
            logger.info("[prewarm] Subscription plans cached")
        except Exception as e:
            logger.warning(f"[prewarm] subscription plans: {e}")
        try:
            # 2. Categories
            cats = await db.categories.find({}, {"_id": 0}).to_list(100)
            logger.info(f"[prewarm] {len(cats)} categories loaded")
        except Exception as e:
            logger.warning(f"[prewarm] categories: {e}")
        try:
            # 3. Active listing count
            count = await db.listings.count_documents({"status": "active"})
            logger.info(f"[prewarm] {count} active listings counted")
        except Exception as e:
            logger.warning(f"[prewarm] listing count: {e}")
        try:
            # 4. Marketplace items (warm the cache via HTTP self-call)
            # Wait for server to be ready
            await asyncio.sleep(2)
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as c:
                r = await c.get("/api/marketplace/items?limit=1")
                logger.info(f"[prewarm] Marketplace items → {r.status_code} ({r.elapsed.total_seconds():.2f}s)")
                r2 = await c.get("/api/multi-item-listings?limit=1")
                logger.info(f"[prewarm] Multi-item listings → {r2.status_code} ({r2.elapsed.total_seconds():.2f}s)")
        except Exception as e:
            logger.warning(f"[prewarm] marketplace: {e}")
    asyncio.ensure_future(_warm())

@app.on_event("startup")
async def init_cloud_storage():
    import asyncio
    async def _init():
        try:
            from services.cloud_storage import _get_s3
            _get_s3()
        except Exception as e:
            logger.error(f"Cloud storage init failed (non-fatal): {e}")
    asyncio.ensure_future(_init())

@app.on_event("shutdown")
async def shutdown_scheduler():
    scheduler.shutdown()

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

@app.on_event("startup")
async def seed_categories():
    import asyncio
    async def _seed():
        try:
            if await db.categories.count_documents({}) == 0:
                categories = [
                    {"id": str(uuid.uuid4()), "name_en": "Electronics", "name_fr": "Électronique", "icon": "laptop"},
                    {"id": str(uuid.uuid4()), "name_en": "Fashion", "name_fr": "Mode", "icon": "shirt"},
                    {"id": str(uuid.uuid4()), "name_en": "Home & Garden", "name_fr": "Maison & Jardin", "icon": "home"},
                    {"id": str(uuid.uuid4()), "name_en": "Sports", "name_fr": "Sports", "icon": "dumbbell"},
                    {"id": str(uuid.uuid4()), "name_en": "Vehicles", "name_fr": "Véhicules", "icon": "car"},
                    {"id": str(uuid.uuid4()), "name_en": "Art & Collectibles", "name_fr": "Art & Objets de collection", "icon": "palette"},
                    {"id": str(uuid.uuid4()), "name_en": "Books & Media", "name_fr": "Livres & Médias", "icon": "book"},
                    {"id": str(uuid.uuid4()), "name_en": "Toys & Games", "name_fr": "Jouets & Jeux", "icon": "gamepad-2"},
                ]
                await db.categories.insert_many(categories)
                logger.info("Categories seeded")
        except Exception as e:
            logger.error(f"Startup error: {e}")
    asyncio.ensure_future(_seed())

@app.on_event("startup")
async def create_database_indexes():
    import asyncio
    async def _create():
        try:
            from pymongo import ASCENDING
            from db.indexes import create_all_indexes
            indexes = [
                ("bids", [("listing_id", ASCENDING)], "idx_bids_listing_id", False),
                ("lot_bids", [("listing_id", ASCENDING), ("lot_number", ASCENDING)], "idx_lot_bids_listing_lot", False),
                ("auto_bids", [("user_id", ASCENDING), ("listing_id", ASCENDING), ("is_active", ASCENDING)], "idx_auto_bids_user_listing", False),
                ("invoices", [("user_id", ASCENDING)], "idx_invoices_user_id", False),
                ("subscription_invoices", [("user_id", ASCENDING)], "idx_sub_invoices_user_id", False),
                ("listings", [("status", ASCENDING), ("created_at", ASCENDING)], "idx_listings_status_created", False),
                ("listings", [("status", ASCENDING), ("category", ASCENDING)], "idx_listings_status_category", False),
                ("listings", [("status", ASCENDING), ("auction_end_date", ASCENDING)], "idx_listings_status_enddate", False),
                ("listings", [("seller_id", ASCENDING), ("status", ASCENDING)], "idx_listings_seller_status", False),
                ("listings", [("id", ASCENDING)], "idx_listings_id_unique", True),
                ("users", [("email", ASCENDING)], "idx_users_email_unique", True),
                ("users", [("role", ASCENDING)], "idx_users_role", False),
                ("users", [("id", ASCENDING)], "idx_users_id_unique", True),
                ("transactions", [("status", ASCENDING), ("created_at", ASCENDING)], "idx_transactions_status_created", False),
                ("transactions", [("buyer_id", ASCENDING)], "idx_transactions_buyer", False),
                ("transactions", [("seller_id", ASCENDING)], "idx_transactions_seller", False),
                ("notifications", [("user_id", ASCENDING), ("is_read", ASCENDING), ("created_at", ASCENDING)], "idx_notifications_user_read_date", False),
                ("messages", [("conversation_id", ASCENDING), ("created_at", ASCENDING)], "idx_messages_conversation_date", False),
                ("multi_item_listings", [("status", ASCENDING), ("created_at", ASCENDING)], "idx_multi_listings_status_created", False),
                ("multi_item_listings", [("id", ASCENDING)], "idx_multi_listings_id_unique", True),
            ]
            for coll, keys, name, unique in indexes:
                await db[coll].create_index(keys, background=True, unique=unique, name=name)
            logger.info("Database indexes created")
            await create_all_indexes(db)
        except Exception as e:
            logger.warning(f"Index creation note (non-fatal): {e}")
    asyncio.ensure_future(_create())


# ─── Static Frontend & SPA Catch-All (MUST be last) ───
import os
_frontend_build = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")
if os.path.isdir(_frontend_build):
    from starlette.staticfiles import StaticFiles
    from starlette.responses import FileResponse
    app.mount("/static", StaticFiles(directory=os.path.join(_frontend_build, "static")), name="static-assets")

    @app.api_route("/{path:path}", methods=["GET"], include_in_schema=False)
    async def spa_catch_all(path: str):
        """Serve React SPA for all non-API routes"""
        file_path = os.path.join(_frontend_build, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(_frontend_build, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file, media_type="text/html")
        return JSONResponse({"status": "healthy", "detail": "SPA build not found"}, status_code=200)
