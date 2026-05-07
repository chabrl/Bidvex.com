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
# override=False so Kubernetes container env vars (set by Emergent at deploy
# time) take precedence over the local .env file. The .env file is still used
# as a fallback for any keys not set in the container env.
load_dotenv(ROOT_DIR / '.env', override=False)

# Safety net: if STRIPE_API_KEY is the literal Emergent placeholder or
# missing/expired-looking, fall back to STRIPE_TEST_SECRET_KEY (a real
# Stripe test account provisioned for this project).
_stripe_key = os.environ.get('STRIPE_API_KEY', '').strip()
if not _stripe_key or _stripe_key == 'sk_test_emergent' or not _stripe_key.startswith(('sk_live_', 'sk_test_', 'rk_')):
    _fallback = os.environ.get('STRIPE_TEST_SECRET_KEY', '').strip()
    if _fallback.startswith('sk_test_'):
        os.environ['STRIPE_API_KEY'] = _fallback
        logging.getLogger(__name__).warning(
            "[STRIPE] STRIPE_API_KEY missing/placeholder — using STRIPE_TEST_SECRET_KEY fallback"
        )

mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'bazario_db')
stripe_api_key = os.environ.get('STRIPE_API_KEY', '')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Sentry (optional) ───
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    _sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
    if _sentry_dsn:
        sentry_sdk.init(
            dsn=_sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.environ.get("SENTRY_ENVIRONMENT", os.environ.get("ENVIRONMENT", "production")),
            send_default_pii=False,
        )
        logger.info(f"Sentry initialized (env={os.environ.get('ENVIRONMENT', 'production')})")
    else:
        logger.info("Sentry disabled — SENTRY_DSN not set")
except Exception as _se:  # pragma: no cover
    logger.warning(f"Sentry init failed (non-fatal): {_se}")

# ─── Database (connection pooling — production tuned) ───
try:
    from pymongo import ReadPreference
    client = AsyncIOMotorClient(
        mongo_url,
        maxPoolSize=50,                 # Max 50 concurrent connections
        minPoolSize=5,                  # Keep 5 connections warm
        maxIdleTimeMS=30000,            # Close idle connections after 30s
        connectTimeoutMS=5000,          # Fail fast (5s) if can't connect
        serverSelectionTimeoutMS=5000,  # Don't wait forever for MongoDB
        socketTimeoutMS=20000,
        retryReads=True,
        retryWrites=True,               # Auto-retry on transient write errors
        w="majority",                   # Confirmed by majority of replicas
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
    # ── Security Headers (Cloudflare CDN-safe) ──
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

    # ── Cache-Control Strategy ──
    # Tier 1: Static hashed assets (JS/CSS chunks) — immutable, cache forever
    if path.startswith("/static/") or any(path.endswith(ext) for ext in (".js", ".css", ".woff2", ".woff")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["CDN-Cache-Control"] = "public, max-age=31536000"
    # Tier 2: Images, fonts, icons — cache 1 year
    elif any(path.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".gif", ".avif")):
        response.headers["Cache-Control"] = "public, max-age=31536000"
        response.headers["CDN-Cache-Control"] = "public, max-age=31536000"
        response.headers["Vary"] = "Accept-Encoding"
    # Tier 3: HTML entry point — must revalidate every time
    elif path.endswith(".html") or path == "/":
        response.headers["Cache-Control"] = "no-cache"
    # Tier 4: Public API routes — short CDN cache (5 min edge, 60s browser)
    elif path.startswith("/api/") and _is_public_cacheable_api(path, request.method):
        response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"
        response.headers["CDN-Cache-Control"] = "public, max-age=300"
        response.headers["Vary"] = "Accept-Encoding"
    # Tier 5: All other API routes (user-specific, real-time) — never cache
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
        response.headers["CDN-Cache-Control"] = "no-store"

    # CSP
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://assets.emergent.sh https://unpkg.com https://d2adkz2s9zrlge.cloudfront.net https://cdn.tailwindcss.com https://us-assets.i.posthog.com https://js.stripe.com https://connect.facebook.net https://www.googletagmanager.com https://www.google-analytics.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https: http:; "
        "connect-src 'self' https: wss:; "
        "frame-src 'self' https://js.stripe.com https://www.facebook.com; "
        "object-src 'none'; "
        "base-uri 'self'"
    )
    return response


# Public API routes safe for CDN edge caching (GET only, non-personalized)
_PUBLIC_CACHEABLE_PREFIXES = (
    "/api/marketplace/items",
    "/api/marketplace/filter-counts",
    "/api/site-config",
    "/api/categories",
    "/api/listings/featured",
    "/api/listings/active",
    "/api/community/questions",
    "/api/health",
)


def _is_public_cacheable_api(path: str, method: str) -> bool:
    """Returns True for GET requests on public, non-personalized endpoints."""
    if method != "GET":
        return False
    return any(path.startswith(prefix) for prefix in _PUBLIC_CACHEABLE_PREFIXES)

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

# ─── Rate Limiting (bilingual 429 handler) ───
from rate_limit import limiter
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter


async def _bilingual_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Bilingual EN/FR rate limit error response."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message_en": "Too many requests. Please wait before trying again.",
            "message_fr": "Trop de requêtes. Veuillez patienter avant de réessayer.",
            "retry_after_seconds": 60,
        },
        headers={"Retry-After": "60"},
    )


app.add_exception_handler(RateLimitExceeded, _bilingual_rate_limit_handler)

# ─── WebSocket Managers ───
from ws_managers import ConnectionManager, MessageConnectionManager, MarketplaceConnectionManager

manager = ConnectionManager()
message_manager = MessageConnectionManager()
marketplace_ws = MarketplaceConnectionManager()

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
    safe_run,
)

async def run_process_ended_auctions():
    from routes.auctions import process_ended_auctions
    await process_ended_auctions()

scheduler.add_job(
    lambda: safe_run("transition_upcoming_auctions", transition_upcoming_auctions(db)),
    trigger=IntervalTrigger(minutes=5), id='transition_upcoming_auctions', replace_existing=True)
scheduler.add_job(
    lambda: safe_run("process_ended_auctions", run_process_ended_auctions()),
    trigger=IntervalTrigger(minutes=1), id='process_ended_auctions', replace_existing=True)
scheduler.add_job(
    lambda: safe_run("expire_partner_pro_trials", expire_partner_pro_trials(db)),
    trigger=IntervalTrigger(hours=1), id='expire_trials', replace_existing=True)
scheduler.add_job(
    lambda: safe_run("send_trial_reminder_emails", send_trial_reminder_emails(db)),
    trigger=IntervalTrigger(hours=1), id='trial_reminders', replace_existing=True)
scheduler.add_job(
    lambda: safe_run("send_auction_payment_reminders", send_auction_payment_reminders(db)),
    trigger=IntervalTrigger(hours=6), id='payment_reminders', replace_existing=True)
scheduler.add_job(
    lambda: safe_run("process_overdue_auction_payments", process_overdue_auction_payments(db)),
    trigger=IntervalTrigger(hours=6), id='overdue_payments', replace_existing=True)
scheduler.add_job(
    lambda: safe_run("send_review_request_emails", send_review_request_emails(db)),
    trigger=IntervalTrigger(hours=1), id='review_requests', replace_existing=True)
scheduler.add_job(
    lambda: safe_run("keepalive_ping", keepalive_ping()),
    trigger=IntervalTrigger(minutes=4), id='keepalive_ping', replace_existing=True)

# Watchlist expiry push alerts — check every 2 minutes for items ending within 5 min
async def run_watchlist_expiry_alerts():
    from routes.push_notifications import send_push_to_user
    try:
        now = datetime.now(timezone.utc)
        five_min = now + timedelta(minutes=5)
        six_min = now + timedelta(minutes=6)
        # Find listings ending in 5-6 min window (to only alert once per window)
        expiring = await db.listings.find(
            {"status": "active", "auction_end_date": {"$gte": five_min.isoformat(), "$lt": six_min.isoformat()}},
            {"_id": 0, "id": 1, "title": 1, "category": 1}
        ).to_list(50)
        for listing in expiring:
            lid = listing["id"]
            cat = (listing.get("category") or "").lower()
            is_vehicle = any(v in cat for v in ("vehicle", "car", "auto"))
            url = f"/vehicle-auctions/{lid}" if is_vehicle else f"/listing/{lid}"
            # Find users who have this in their watchlist
            watchers = await db.watchlist.find({"listing_id": lid}, {"_id": 0, "user_id": 1}).to_list(200)
            for w in watchers:
                await send_push_to_user(db, w["user_id"], {
                    "title": "Auction ending soon!",
                    "body": f"'{listing.get('title', 'Item')}' ends in 5 minutes!",
                    "type": "watchlist_expiry",
                    "url": url,
                    "listing_id": lid,
                    "category": listing.get("category", ""),
                })
    except Exception as e:
        logger.warning(f"Watchlist expiry alerts failed: {e}")

scheduler.add_job(
    lambda: safe_run("watchlist_expiry_alerts", run_watchlist_expiry_alerts()),
    trigger=IntervalTrigger(minutes=2), id='watchlist_expiry_alerts', replace_existing=True)

# ─── Deposit refund queue worker (60s SLA — Spec Feature 2) ───
async def run_deposit_refund_queue():
    from services.deposit_refund_queue import process_deposit_refund_queue
    await process_deposit_refund_queue(db)

async def _deposit_refund_queue_tick():
    """AsyncIOScheduler-friendly wrapper: must be a coroutine, not a sync lambda
    returning a coroutine, otherwise apscheduler's default executor never awaits it."""
    await safe_run("deposit_refund_queue", run_deposit_refund_queue())

scheduler.add_job(
    _deposit_refund_queue_tick,
    trigger=IntervalTrigger(seconds=10), id='deposit_refund_queue', replace_existing=True)

# ─── Promotion email blast worker (iter189 Feature 1 — T+24h premium blasts) ───
async def _promotion_email_blast_tick():
    from services.promotion_email_blast import process_promotion_email_blast_queue
    await safe_run("promotion_email_blast", process_promotion_email_blast_queue(db))

scheduler.add_job(
    _promotion_email_blast_tick,
    trigger=IntervalTrigger(minutes=5), id='promotion_email_blast', replace_existing=True)

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
    from routes.auctions import auctions_router, bids_router, set_db as set_auctions_db, set_notification_manager, set_ws_manager, set_sms_service_getter, set_marketplace_ws
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
    from routes.community import community_router, set_db as set_community_db
    from routes.escrow import escrow_router
    from services.email_service import get_email_service
    from services.email_marketing import get_marketing_service, SEGMENT_FILTERS, CAMPAIGN_STATUS
    from services.user_email_marketing import get_user_marketing_service, SUBSCRIPTION_LIMITS

    # Inject DB into all core routers
    for setter in [set_analytics_db, set_auctions_db, set_sms_db, set_users_db,
                   set_marketing_db, set_admin_db, set_webhooks_db, set_payments_db,
                   set_marketplace_db, set_listings_db, set_auth_db, set_dashboard_db, set_profiles_db,
                   set_deposits_db, set_insights_db, set_community_db]:
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
    set_marketplace_ws(marketplace_ws)
    try:
        from services.sms_notifications import get_sms_notification_service
        set_sms_service_getter(get_sms_notification_service)
    except ImportError:
        pass

    # Include core routers
    for router in [analytics_router, auctions_router, bids_router, listings_router,
                   auth_router, sms_router, payments_router, webhooks_router,
                   marketplace_router, admin_router, dashboard_router, profiles_router,
                   deposits_router, insights_router, community_router, escrow_router]:
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
        ("routes.push_notifications", "push_router", "set_push_db", False),
        ("routes.sendgrid_webhook", "sendgrid_webhook_router", None, False),
        ("routes.unsubscribe", "unsubscribe_router", None, False),
        ("routes.email_preferences", "email_preferences_router", None, False),
        ("routes.feature_flags", "admin_feature_flags_router", None, False),
        ("routes.feature_flags", "public_feature_flags_router", None, False),
        ("routes.feature_flags", "waitlist_router", None, False),
        ("routes.feature_flags", "admin_waitlist_router", None, False),
        ("routes.admin_deposits", "admin_deposits_router", None, False),
        ("routes.admin_bulk", "admin_bulk_router", None, False),
        ("routes.admin_listing_edit", "admin_listing_edit_router", None, False),
        ("routes.down_payments", "down_payments_router", None, False),
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

    # ─── Marketing Router (separate import) ───
    try:
        api_router.include_router(marketing_router)
        logger.info("Marketing router registered")
    except Exception as e:
        logger.error(f"Failed to register marketing router: {e}")

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

    # Vehicle Settlement routes (fee-to-unlock, seller contact gate)
    from routes.vehicle_settlement import vehicle_settlement_router
    api_router.include_router(vehicle_settlement_router)

    from routes.storage_auctions import storage_router
    api_router.include_router(storage_router)

    # Admin Payment Charges (strict payment system observability)
    from routes.admin_charges import admin_charges_router
    api_router.include_router(admin_charges_router)

    # Strict bidder deposits (Spec Feature 1 — partner-defined deposits)
    from routes.bidder_deposits import bidder_deposits_router
    api_router.include_router(bidder_deposits_router)

    # SEO: Dynamic sitemap.xml + robots.txt (app-level, not /api)
    from routes.sitemap import sitemap_router
    app.include_router(sitemap_router, tags=["SEO"])

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
    register_ws_handlers(app, db, manager, message_manager, marketplace_ws)
    logger.info("WebSocket handlers registered successfully")
except Exception as e:
    logger.warning(f"WebSocket handlers unavailable at startup: {e}")

# ─── Mount API Router ───
app.include_router(api_router)

@app.get("/")
async def serve_spa_root():
    """Serve React SPA index.html at root"""
    import os
    index_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "build", "index.html")
    if not os.path.isfile(index_path):
        # Try absolute path
        index_path = "/app/frontend/build/index.html"
    if os.path.isfile(index_path):
        from starlette.responses import FileResponse
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"status": "healthy", "service": "BidVex API", "message": "Frontend build not found. Deploy frontend first."})

@app.get("/api/status")
async def api_status():
    """API status endpoint (moved from root to avoid conflicting with SPA)"""
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
    check_redis_connection,
)

@app.on_event("startup")
async def on_startup():
    try:
        scheduler.start()
        logger.info("APScheduler started")
    except Exception as e:
        logger.warning(f"APScheduler unavailable at startup: {e}")
    
    # Register lifecycle & geo email automation jobs
    try:
        from services.email_automation import register_lifecycle_jobs
        from services.geo_email_service import register_geo_jobs
        register_lifecycle_jobs(scheduler, db)
        register_geo_jobs(scheduler, db)
    except Exception as e:
        logger.warning(f"Email automation registration failed (non-fatal): {e}")
    
    await check_redis_connection()
    await log_db_status(db)
    await prewarm_caches(db)
    await init_cloud_storage()
    await seed_categories(db)
    await create_database_indexes(db)
    await create_critical_indexes(db)

    # ── New strict-payment-system indexes (Spec global rules 3 + 4) ──
    try:
        from services.payment_idempotency import ensure_payment_charges_indexes
        from services.deposit_refund_queue import ensure_refund_queue_indexes
        from services.promotion_email_blast import ensure_email_blast_queue_indexes
        await ensure_payment_charges_indexes(db)
        await ensure_refund_queue_indexes(db)
        await ensure_email_blast_queue_indexes(db)
    except Exception as e:
        logger.warning(f"Strict payment indexes registration failed (non-fatal): {e}")


async def create_critical_indexes(database):
    """Run on every startup — idempotent, safe to re-run.
    Only the most critical indexes for fast cold-start verification.
    Each index is wrapped independently so one collision doesn't stop the rest.
    """
    critical = [
        ("listings", [("status", 1), ("end_time", 1)], {"background": True}),
        ("storage_auctions", [("status", 1), ("end_time", 1)], {"background": True}),
        ("users", [("email", 1)], {"unique": True, "background": True}),
        ("deposits", [("auction_id", 1), ("status", 1)], {"background": True}),
        # TTL — auto-deletes expired refresh tokens
        ("refresh_tokens", [("expires_at", 1)], {"expireAfterSeconds": 0, "background": True}),
    ]
    ok = 0
    for coll, keys, opts in critical:
        try:
            await database[coll].create_index(keys, **opts)
            ok += 1
        except Exception as e:
            logger.warning(f"[critical-index] {coll} {keys}: {e}")
    logger.info(f"✅ Critical database indexes verified ({ok}/{len(critical)} ok)")

@app.on_event("shutdown")
async def on_shutdown():
    scheduler.shutdown()
    client.close()


# ─── Static Frontend & SPA Catch-All (MUST be last) ───
import os

# Resolve frontend build directory — works on both local and Railway
_server_dir = os.path.dirname(os.path.abspath(__file__))
_possible_build_dirs = [
    os.path.join(_server_dir, "..", "frontend", "build"),   # /app/backend/../frontend/build
    os.path.join(_server_dir, "..", "frontend", "dist"),    # Vite fallback
    os.path.join(_server_dir, "static"),                    # Copied into backend/static
    "/app/frontend/build",                                  # Absolute fallback
]
_frontend_build = None
for _d in _possible_build_dirs:
    _resolved = os.path.abspath(_d)
    if os.path.isdir(_resolved) and os.path.isfile(os.path.join(_resolved, "index.html")):
        _frontend_build = _resolved
        logger.info(f"[SPA] Frontend build found at: {_frontend_build}")
        break

if not _frontend_build:
    logger.warning(f"[SPA] No frontend build directory found. Checked: {[os.path.abspath(d) for d in _possible_build_dirs]}")

if _frontend_build:
    from starlette.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    _static_dir = os.path.join(_frontend_build, "static")
    if os.path.isdir(_static_dir):
        app.mount("/static", StaticFiles(directory=_static_dir), name="static-assets")

    # Serve public assets from build root (manifest.json, ads.txt, etc.)
    _public_exts = {".xml", ".txt", ".ico", ".png", ".json", ".webmanifest"}

    # Note: /sitemap.xml and /robots.txt are served by routes/sitemap.py (dynamic)

    @app.api_route("/{path:path}", methods=["GET"], include_in_schema=False)
    async def spa_catch_all(path: str):
        """Serve static files from build root, or fall back to index.html for SPA routing."""
        # 1. Try exact file match in build directory
        file_path = os.path.join(_frontend_build, path)
        if os.path.isfile(file_path) and not path.startswith("api/"):
            return FileResponse(file_path)
        # 2. SPA fallback — serve index.html for all client-side routes
        index_file = os.path.join(_frontend_build, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file, media_type="text/html")
        return JSONResponse({"status": "healthy", "detail": "SPA build not found"}, status_code=200)
else:
    # No build directory — serve a helpful message
    @app.api_route("/{path:path}", methods=["GET"], include_in_schema=False)
    async def no_frontend(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return JSONResponse({
            "status": "healthy",
            "service": "BidVex API",
            "message": "Frontend build not found. Run 'cd frontend && yarn build' first.",
        })
