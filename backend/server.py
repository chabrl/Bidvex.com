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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Database (connection pooling) ───
try:
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
    logger.info("MongoDB client initialized successfully")
except Exception as e:
    logger.error(f"MongoDB client initialization failed: {e}")
    raise  # DB is a hard dependency — fail fast

try:
    import stripe
    if stripe_api_key and stripe_api_key != "your-stripe-api-key-here":
        stripe.api_key = stripe_api_key
        logger.info("Stripe initialized successfully")
    else:
        logger.info("Stripe disabled — valid API key not yet provided")
except Exception as e:
    logger.warning(f"Stripe unavailable at startup: {e}")

# ─── App ───
app = FastAPI()
api_router = APIRouter(prefix="/api")

# ─── Root Health Check (MUST be first — before all middleware) ───
@app.get("/health")
@app.head("/health")
async def root_health():
    return {"status": "ok"}

@app.get("/api/health")
@app.head("/api/health")
async def api_health():
    return {"status": "healthy"}

# Trust proxy headers from Cloudflare/Railway
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

app.add_middleware(GZipMiddleware, minimum_size=500)
_cors_origins_env = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] if _cors_origins_env else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if _cors_origins != ["*"] else False,
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
    # Cloudflare CDN-specific headers for high-res image delivery
    if path.startswith("/static/") or any(path.endswith(ext) for ext in (".js", ".css", ".woff2", ".woff")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["CDN-Cache-Control"] = "public, max-age=31536000"
    elif any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".gif", ".avif")):
        response.headers["Cache-Control"] = "public, max-age=31536000"
        response.headers["CDN-Cache-Control"] = "public, max-age=31536000"
        response.headers["Vary"] = "Accept-Encoding"
    elif path.endswith(".html") or path == "/":
        response.headers["Cache-Control"] = "no-cache"
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["CDN-Cache-Control"] = "no-store"
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

# ─── 500 Error & Webhook Failure Tracking Middleware ───
@app.middleware("http")
async def error_tracking_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        if response.status_code >= 500:
            import asyncio
            from routes.monitoring import log_error_event
            asyncio.ensure_future(log_error_event(
                event_type="http_500",
                message=f"{request.method} {request.url.path} returned {response.status_code}",
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "query": str(request.query_params),
                },
                severity="error",
            ))
        return response
    except Exception as exc:
        import asyncio
        from routes.monitoring import log_error_event
        asyncio.ensure_future(log_error_event(
            event_type="unhandled_exception",
            message=f"Unhandled exception on {request.method} {request.url.path}: {str(exc)[:200]}",
            details={
                "method": request.method,
                "path": request.url.path,
                "error": str(exc)[:500],
            },
            severity="critical",
        ))
        raise

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

from services.scheduled_jobs import (
    transition_upcoming_auctions,
    expire_partner_pro_trials,
    send_trial_reminder_emails,
    send_auction_payment_reminders,
    process_overdue_auction_payments,
    send_review_request_emails,
    keepalive_ping,
)

async def run_process_ended_auctions():
    from routes.auctions import process_ended_auctions
    await process_ended_auctions()

scheduler.add_job(lambda: transition_upcoming_auctions(db), trigger=IntervalTrigger(minutes=5),
                  id='transition_upcoming_auctions', replace_existing=True)
scheduler.add_job(run_process_ended_auctions, trigger=IntervalTrigger(minutes=1),
                  id='process_ended_auctions', replace_existing=True)
scheduler.add_job(lambda: expire_partner_pro_trials(db), trigger=IntervalTrigger(hours=1),
                  id='expire_trials', replace_existing=True)
scheduler.add_job(lambda: send_trial_reminder_emails(db), trigger=IntervalTrigger(hours=1),
                  id='trial_reminders', replace_existing=True)
scheduler.add_job(lambda: send_auction_payment_reminders(db), trigger=IntervalTrigger(hours=6),
                  id='payment_reminders', replace_existing=True)
scheduler.add_job(lambda: process_overdue_auction_payments(db), trigger=IntervalTrigger(hours=6),
                  id='overdue_payments', replace_existing=True)
scheduler.add_job(lambda: send_review_request_emails(db), trigger=IntervalTrigger(hours=1),
                  id='review_requests', replace_existing=True)
scheduler.add_job(keepalive_ping, trigger=IntervalTrigger(minutes=4),
                  id='keepalive_ping', replace_existing=True)

# ─── Health Endpoints ───
@api_router.get("/")
async def root():
    return {"message": "Bazario API v1.0"}

@api_router.get("/cache-stats")
async def get_cache_statistics():
    from services.api_cache import get_cache_stats
    return await get_cache_stats()

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
    from routes.deposits import deposits_router, set_deposits_db, set_deposits_auth
    from routes.user_insights import insights_router, set_insights_db, set_insights_auth
    from services.email_service import get_email_service
    from services.email_marketing import get_marketing_service, SEGMENT_FILTERS, CAMPAIGN_STATUS
    from services.user_email_marketing import get_user_marketing_service, SUBSCRIPTION_LIMITS

    # Inject DB into all core routers
    for setter in [set_analytics_db, set_auctions_db, set_sms_db, set_users_db,
                   set_marketing_db, set_admin_db, set_webhooks_db, set_payments_db,
                   set_marketplace_db, set_listings_db, set_auth_db, set_dashboard_db, set_profiles_db,
                   set_deposits_db, set_insights_db]:
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
                   set_payments_auth, set_dashboard_auth, set_profiles_auth,
                   set_deposits_auth, set_insights_auth]:
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
                   marketplace_router, admin_router, dashboard_router, profiles_router,
                   deposits_router, insights_router]:
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
        ("routes.monitoring", "monitoring_router", None, False),
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
    from routes.vehicles_admin import vehicle_admin_router, _init_vehicle_admin
    from services.scheduler import init_scheduler as init_vehicle_scheduler, start_scheduler as start_vehicle_scheduler
    set_vehicle_db(db)
    _init_vehicle_admin(db)
    init_vehicle_scheduler(db)
    app.include_router(vehicle_router)
    app.include_router(vehicle_admin_router)

    @app.on_event("startup")
    async def start_vehicle_auction_scheduler():
        try:
            start_vehicle_scheduler()
        except Exception as e:
            logger.error(f"Failed to start vehicle scheduler: {e}")
except ImportError:
    pass

# ─── WebSocket Handlers ───
try:
    from ws_handlers import register_ws_handlers
    register_ws_handlers(app, db, manager, message_manager)
    logger.info("WebSocket handlers registered successfully")
except Exception as e:
    logger.warning(f"WebSocket handlers unavailable at startup: {e}")

# ─── Mount API Router ───
app.include_router(api_router)

@app.get("/")
async def serve_spa_root():
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

# ─── Lifecycle Events ───
from lifecycle import (
    log_db_status, prewarm_caches, init_cloud_storage,
    seed_categories, create_database_indexes,
)

@app.on_event("startup")
async def on_startup():
    try:
        scheduler.start()
        logger.info("APScheduler started")
    except Exception as e:
        logger.warning(f"APScheduler unavailable at startup: {e}")
    await log_db_status(db)
    await prewarm_caches(db)
    await init_cloud_storage()
    await seed_categories(db)
    await create_database_indexes(db)

@app.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown()
    client.close()


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
