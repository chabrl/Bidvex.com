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

# ─── iter264 Mission 1 — Required ENV validation ─────────────────────
# Soft validation only: log a WARNING for each missing var so degraded
# functionality is discoverable in the logs, but never crash the boot.
_REQUIRED_ENV_VARS = (
    ("STRIPE_API_KEY", "Stripe payment links + checkout sessions"),
    ("STRIPE_WEBHOOK_SECRET", "Stripe webhook signature verification"),
    ("SENDGRID_API_KEY", "Outbound transactional emails"),
    ("EMERGENT_LLM_KEY", "AI assistant + chat completions"),
    ("MONGO_URL", "Database connectivity"),
)
for _var, _purpose in _REQUIRED_ENV_VARS:
    if not os.environ.get(_var):
        logger.warning(
            f"⚠️  ENV VAR MISSING: {_var} — {_purpose} will be degraded."
        )

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
# iter213 — Modern FastAPI lifespan handler (replaces deprecated on_event hooks).
# Centralises all startup + shutdown work in one context manager.
from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(app):
    # ── STARTUP ──
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

    # iter234 — Daily Watchdog: pull 24h MongoDB logs → Gemini 2.5 Flash analysis
    # → SendGrid email to charbel911@gmail.com. Runs at 00:00 UTC every day.
    try:
        from apscheduler.triggers.cron import CronTrigger
        from services.genai_watchdog import run_daily_watchdog_cycle

        scheduler.add_job(
            run_daily_watchdog_cycle,
            CronTrigger(hour=0, minute=0, timezone="UTC"),
            kwargs={"db": db},
            id="genai_daily_watchdog",
            replace_existing=True,
            misfire_grace_time=3600,  # tolerate up to 1h scheduler downtime
        )
        logger.info("iter234 — Daily GenAI Watchdog cron registered (00:00 UTC)")
    except Exception as e:
        logger.warning(f"GenAI Watchdog cron registration failed (non-fatal): {e}")

    # iter316 Mission 4 — Monthly contractor commission payout (1st of each month, 02:00 UTC)
    try:
        from apscheduler.triggers.cron import CronTrigger
        from services.contractor_commission import run_monthly_contractor_payouts

        async def _monthly_contractor_payout_job():
            try:
                report = await run_monthly_contractor_payouts(db)
                logger.info(f"[contractor_payout] monthly run: "
                            f"paid_count={report.get('paid_count')} "
                            f"batch_total={report.get('batch_total')} "
                            f"skipped_no_connect={len(report.get('skipped_no_connect') or [])} "
                            f"errors={len(report.get('errors') or [])}")
            except Exception as je:  # noqa: BLE001
                logger.warning(f"[contractor_payout] monthly job failed: {je}")

        scheduler.add_job(
            _monthly_contractor_payout_job,
            CronTrigger(day=1, hour=2, minute=0, timezone="UTC"),
            id="contractor_commission_monthly_payout",
            replace_existing=True,
            misfire_grace_time=86400,
        )
        logger.info("iter316 — Monthly contractor commission payout cron registered (1st @ 02:00 UTC)")
    except Exception as e:
        logger.warning(f"Contractor payout cron registration failed (non-fatal): {e}")

    # iter317 Directive 1 — Weekly leaderboard commission overlay
    # Mondays @ 08:00 America/Toronto (EST/EDT auto-handled by ZoneInfo).
    try:
        from apscheduler.triggers.cron import CronTrigger
        from services.leaderboard_overlay import (
            run_weekly_leaderboard_overlay,
            LEADERBOARD_CRON_TZ,
            LEADERBOARD_CRON_HOUR,
            LEADERBOARD_CRON_DAY_OF_WEEK,
        )

        async def _weekly_leaderboard_job():
            try:
                report = await run_weekly_leaderboard_overlay(db)
                logger.info(
                    f"[leaderboard_overlay] weekly run: iso_week={report.get('iso_week')} "
                    f"evaluated={report.get('contractors_evaluated')} "
                    f"top5={report.get('top_5_ids')} "
                    f"entered={report.get('entered_top_5')} "
                    f"dropped={report.get('dropped_top_5')}"
                )
            except Exception as je:  # noqa: BLE001
                logger.warning(f"[leaderboard_overlay] weekly job failed: {je}")

        scheduler.add_job(
            _weekly_leaderboard_job,
            CronTrigger(
                day_of_week=LEADERBOARD_CRON_DAY_OF_WEEK,
                hour=LEADERBOARD_CRON_HOUR,
                minute=0,
                timezone=LEADERBOARD_CRON_TZ,
            ),
            id="leaderboard_overlay_weekly",
            replace_existing=True,
            misfire_grace_time=21600,  # 6h tolerance for cluster restarts
        )
        logger.info(
            f"iter317 — Weekly leaderboard overlay cron registered "
            f"(Mon @ 08:00 {LEADERBOARD_CRON_TZ})"
        )
    except Exception as e:
        logger.warning(f"Leaderboard overlay cron registration failed (non-fatal): {e}")

    # iter391 — Nightly base64 sweep alert. Runs the migration script in
    # DRY-RUN mode at 04:00 UTC. NEVER migrates. If ANY base64 entry is
    # still hiding in listings / multi_item_listings / vehicle_listings /
    # storage_auctions, sends an HTML admin email with per-collection
    # counts + the manual `python -m scripts.migrate_...` command.
    try:
        from apscheduler.triggers.cron import CronTrigger
        from services.base64_sweep_alert import run_nightly_base64_sweep_alert

        async def _nightly_base64_sweep_job():
            try:
                report = await run_nightly_base64_sweep_alert(db)
                logger.info(
                    "[base64_sweep_alert] nightly run complete: "
                    f"total_found={report.get('totals',{}).get('found',0)} "
                    f"alert_triggered={report.get('alert_triggered')} "
                    f"email_sent={report.get('email_sent')} "
                    f"recipient={report.get('recipient')}"
                )
            except Exception as je:  # noqa: BLE001
                logger.warning(f"[base64_sweep_alert] nightly job failed: {je}")

        scheduler.add_job(
            _nightly_base64_sweep_job,
            CronTrigger(hour=4, minute=0, timezone="UTC"),
            id="base64_sweep_alert_nightly",
            replace_existing=True,
            misfire_grace_time=3600,  # 1h scheduler-downtime tolerance
        )
        logger.info("iter391 — Nightly base64 sweep alert cron registered (04:00 UTC)")
    except Exception as e:
        logger.warning(f"Base64 sweep alert cron registration failed (non-fatal): {e}")

    # iter316 Mission 1 — Twilio dialer configuration check (non-fatal).
    try:
        from services.twilio_service import verify_twilio_config, verify_twilio_auth
        s = verify_twilio_config()
        if s["configured"]:
            logger.info("iter316 — Twilio dialer fully configured.")
        else:
            logger.warning(f"iter316 — Twilio dialer partial config. Missing: {s['missing']}. "
                           f"can_mint_tokens={s['can_mint_tokens']}, can_place_calls={s['can_place_calls']}.")
        # iter342 — live auth-token validation (background, logs VALID/INVALID)
        import asyncio as _aio
        _aio.get_event_loop().create_task(verify_twilio_auth(force=True))
    except Exception as e:
        logger.warning(f"Twilio config check failed (non-fatal): {e}")

    try:
        from lifecycle import (
            log_db_status, prewarm_caches, init_cloud_storage,
            seed_categories, create_database_indexes,
            check_redis_connection,
        )
        await check_redis_connection()
        await log_db_status(db)
        await prewarm_caches(db)
        await init_cloud_storage()
        await seed_categories(db)
        await create_database_indexes(db)
        await create_critical_indexes(db)
    except Exception as e:
        logger.warning(f"Core startup helpers failed (non-fatal): {e}")

    # ── New strict-payment-system indexes (Spec global rules 3 + 4) ──
    try:
        from services.payment_idempotency import ensure_payment_charges_indexes
        from services.deposit_refund_queue import ensure_refund_queue_indexes
        from services.promotion_email_blast import ensure_email_blast_queue_indexes
        await ensure_payment_charges_indexes(db)
        await ensure_refund_queue_indexes(db)
        await ensure_email_blast_queue_indexes(db)
        # iter350 — Bootstrap the CRA-compliant tax_rate_config collection
        # (idempotent). Rates are then hot-reloadable via
        # /api/admin/pricing/tax-rates without a redeploy.
        try:
            from services.tax_rate_config import seed_bootstrap_rates, refresh_cache_from_db
            await seed_bootstrap_rates(db)
            await refresh_cache_from_db(db)
        except Exception as _te:
            logger.warning(f"[iter350] tax_rate_config bootstrap failed (non-fatal): {_te}")

        # iter353 P2 — Prospect Finder DB indexes + phone_last10 backfill.
        # Idempotent — safe to run on every boot. Turns the batched
        # already_in_bidvex query into an index-covered lookup so it
        # stays under 50ms even at prod scale.
        try:
            from services.prospect_finder_indexes import (
                ensure_prospect_finder_indexes, backfill_phone_last10,
            )
            await ensure_prospect_finder_indexes(db)
            result = await backfill_phone_last10(db)
            logger.info(f"[iter353 P2] prospect finder indexes + backfill: {result}")
        except Exception as _pfe:
            logger.warning(f"[iter353 P2] prospect finder index setup failed (non-fatal): {_pfe}")
        # iter236 Mission 2 — 2dsphere index on listings.location.coordinates
        from routes.geo_search import ensure_2dsphere_index
        await ensure_2dsphere_index()
        # iter373 — Landing Page Builder indexes (slug-unique, status filter,
        # audit-log page lookup, per-view row lookup).
        try:
            await db.landing_pages.create_index(
                "slug", unique=True, name="idx_landing_pages_slug_unique",
            )
            await db.landing_pages.create_index(
                "status", name="idx_landing_pages_status",
            )
            await db.landing_page_audit_log.create_index(
                [("page_id", 1), ("created_at", -1)],
                name="idx_lp_audit_page_created",
            )
            await db.landing_page_views.create_index(
                [("page_id", 1), ("created_at", -1)],
                name="idx_lp_views_page_created",
            )
        except Exception as _lpi:  # noqa: BLE001
            logger.warning(f"[iter373] landing_pages index setup skipped: {_lpi}")
        # iter265 Mission 1.4 — 2dsphere on users.location.coordinates so
        # per-listing nearby fan-out can $geoWithin/$centerSphere. The
        # `sparse=True` flag lets users without coordinates remain
        # untouched. Also TTL-style cleanup on recent_nearby_notifs so
        # dedup rows don't grow unbounded.
        try:
            await db.users.create_index(
                [("location.coordinates", "2dsphere")],
                sparse=True,
                name="users_location_2dsphere_iter265",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter265] users 2dsphere index skipped: {exc}")
        try:
            await db.recent_nearby_notifs.create_index(
                "sent_at",
                expireAfterSeconds=60 * 60 * 24 * 2,  # 48h TTL
                name="recent_nearby_notifs_ttl_iter265",
            )
        except Exception as exc:  # noqa: BLE001
            logger.info(f"[iter265] recent_nearby_notifs TTL index skipped: {exc}")
    except Exception as e:
        logger.warning(f"Strict payment indexes registration failed (non-fatal): {e}")

    # iter296 P0 BUG 5 — One-shot backfill of `winner_user_id` /
    # `sold_at` / `final_price` for marketplace + multi-item listings
    # that ended before the iter296 fix shipped. Idempotent — second
    # run is a no-op.
    try:
        from services.iter296_data_repair import run_iter296_listing_repair
        repair = await run_iter296_listing_repair(db)
        logger.info(f"[iter296_repair] {repair}")
    except Exception as e:
        logger.warning(f"[iter296_repair] failed (non-fatal): {e}")

    # iter283 — Idempotent listing-section backfill. Tags every active
    # listing with `section` + canonical `listing_type` so the storage,
    # vehicle, and lots section pages see EVERY listing they should.
    # Safe to run every boot — only updates docs that don't already
    # match the canonical set.
    try:
        from services.listing_sections import backfill_listing_sections
        sec_counts = await backfill_listing_sections(db)
        logger.info(f"[iter283] section backfill counts: {sec_counts}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter283] section backfill skipped: {exc}")

    # iter283-hotfix-2 — Vehicle fast-track for trusted sellers
    # (admins / verified partners / vehicle dealers / storage facilities)
    # and a sane default for the `vehicle_auctions_enabled` toggle.
    # Without this, vehicle listings stay invisible behind the
    # admin-approval workflow even when the seller is a trusted account.
    try:
        from services.vehicle_fast_track import (
            fast_track_trusted_drafts,
            ensure_vehicle_auctions_toggle_default,
        )
        vfast = await fast_track_trusted_drafts(db)
        vtog = await ensure_vehicle_auctions_toggle_default(db)
        logger.info(f"[iter283-hotfix-2] vehicle fast-track: {vfast} toggle_default_written={vtog}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter283-hotfix-2] vehicle fast-track skipped: {exc}")

    # iter283-payments-audit Mission 4B — Webhook idempotency.
    # Adds a unique index on `stripe_events.id`. Combined with the
    # webhook handler's check-and-insert flow, this guarantees every
    # Stripe event is processed AT MOST ONCE even under retry storms.
    # We first purge legacy docs with a NULL/missing `id` field, then
    # dedupe by `id` (keeping the oldest doc per event) — these were
    # written by a pre-iter283-payments-audit handler that didn't
    # enforce uniqueness.
    try:
        await db.stripe_events.delete_many(
            {"$or": [{"id": {"$exists": False}}, {"id": None}, {"id": ""}]}
        )
        # Dedupe: aggregate-then-delete keeping `_id` of the oldest
        # doc per event id. Idempotent — repeat runs find 0 dupes.
        pipeline = [
            {"$match": {"id": {"$type": "string"}}},
            {"$sort": {"created_at": 1, "_id": 1}},
            {"$group": {
                "_id": "$id",
                "keep": {"$first": "$_id"},
                "all": {"$push": "$_id"},
            }},
            {"$project": {
                "to_delete": {
                    "$filter": {
                        "input": "$all",
                        "as": "oid",
                        "cond": {"$ne": ["$$oid", "$keep"]},
                    }
                }
            }},
        ]
        oids_to_delete = []
        async for row in db.stripe_events.aggregate(pipeline):
            oids_to_delete.extend(row.get("to_delete") or [])
        if oids_to_delete:
            await db.stripe_events.delete_many({"_id": {"$in": oids_to_delete}})
            logger.info(
                f"[iter283-payments-audit] purged {len(oids_to_delete)} "
                "duplicate stripe_events before index build"
            )
        await db.stripe_events.create_index(
            "id", unique=True, name="id_unique",
            partialFilterExpression={"id": {"$type": "string"}},
        )
        logger.info("[iter283-payments-audit] stripe_events.id unique index ensured")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter283-payments-audit] stripe_events index skipped: {exc}")

    # iter283-payments-audit Mission 1B — Backfill Stripe Customers
    # for users missing `stripe_customer_id`. Idempotent — only acts
    # on users without an existing customer record.
    try:
        from services.stripe_customer_backfill import backfill_stripe_customers
        bf = await backfill_stripe_customers(db)
        logger.info(f"[iter283-payments-audit] stripe customer backfill: {bf}")
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[iter283-payments-audit] customer backfill skipped: {exc}")

    # ── iter212 — Grandfather existing storage facilities ──
    try:
        res = await db.storage_facilities.update_many(
            {"company_registration_verified": {"$exists": False}},
            {"$set": {"company_registration_verified": True, "company_registration_grandfathered": True}},
        )
        if res.modified_count:
            logger.info(
                f"[iter212] Grandfathered {res.modified_count} existing storage facilities."
            )
        owner_ids = await db.storage_facilities.distinct("owner_user_id")
        if owner_ids:
            await db.users.update_many(
                {"id": {"$in": owner_ids}, "is_storage_facility": {"$ne": True}},
                {"$set": {"is_storage_facility": True, "account_type": "storage_facility"}},
            )
    except Exception as e:
        logger.warning(f"[iter212] storage-facility grandfather pass failed (non-fatal): {e}")

    # ── HOTFIX (AI Watchdog Infinite Re-flag Loop) / FIX 3 ──
    # One-shot backfill: stamp `watchdog_exempt=True` on every listing the
    # admin already approved through the listing_reviews queue, and bounce
    # any paused-by-watchdog rows back to active. Idempotent — re-runs are
    # no-ops once every row already carries the passport.
    try:
        from services.watchdog_exempt_backfill import backfill_watchdog_exempt
        result = await backfill_watchdog_exempt(db)
        if result["listings_modified"] or result["restored_to_active"]:
            logger.info(
                "[watchdog-exempt-backfill] approved=%s listings_modified=%s "
                "multi_modified=%s restored=%s",
                result["approved_count"], result["listings_modified"],
                result["multi_modified"], result["restored_to_active"],
            )
    except Exception as e:
        logger.warning(f"[watchdog-exempt-backfill] non-fatal failure: {e}")

    # ── iter216 — Sync legacy/new subscription fields so dashboards never
    # disagree with admin manual-settle. For every partner / dealer / facility
    # who has the modern `*_subscription_active=True` flag but is MISSING
    # the legacy alias, set the legacy alias too. Idempotent.
    try:
        res_p = await db.users.update_many(
            {"partner_subscription_active": True, "platform_fee_paid": {"$ne": True}},
            {"$set": {"platform_fee_paid": True, "iter216_sync_applied": True}},
        )
        if res_p.modified_count:
            logger.info(f"[iter216] synced platform_fee_paid on {res_p.modified_count} partner accounts (incl. Alex Boulanger)")
        # Also handle the reverse — someone paid via Stripe (legacy) but never
        # got the modern active flag flipped (so subscription panels look stale).
        res_p2 = await db.users.update_many(
            {"platform_fee_paid": True, "partner_subscription_active": {"$ne": True}},
            {"$set": {"partner_subscription_active": True, "iter216_sync_applied": True}},
        )
        if res_p2.modified_count:
            logger.info(f"[iter216] synced partner_subscription_active on {res_p2.modified_count} stripe-paid partners")
    except Exception as e:
        logger.warning(f"[iter216] partner-fee sync failed (non-fatal): {e}")

    # ── iter398 — Rebuild PRICE_ID_TO_TIER reverse map on boot ──
    # After a restart the in-memory reverse map only contains the 3
    # hardcoded pins from `services.subscription_service`. Read every
    # `subscription_plans.stripe_price_id_{yearly,monthly}` and register
    # them so webhook `_handle_subscription_created` can resolve any
    # admin-created price → correct tier immediately.
    try:
        from services.subscription_service import rebuild_price_id_map
        added = await rebuild_price_id_map(db)
        if added:
            logger.info(f"[iter398] PRICE_ID_TO_TIER hydrated with {added} Stripe price IDs from subscription_plans")
    except Exception as e:
        logger.warning(f"[iter398] rebuild_price_id_map failed (non-fatal): {e}")

    # ── iter194 — Vehicle dealer license / unlock-fee backfill ──
    try:
        from routes.vehicle_dealer_extras import migrate_existing_vehicle_listings
        modified = await migrate_existing_vehicle_listings()
        if modified:
            logger.info(f"[iter194] backfilled auction_access/run_status on {modified} vehicle listings")
    except Exception as e:
        logger.warning(f"[iter194] migration failed: {e}")

    # ── Vehicle auction scheduler ──
    try:
        from services.scheduler import start_scheduler as _start_vehicle_scheduler
        _start_vehicle_scheduler()
    except Exception as e:
        logger.warning(f"Failed to start vehicle scheduler (non-fatal): {e}")

    # iter270 — Email config validation + SendGrid DNS authentication probe.
    try:
        from services.email_deliverability import (
            validate_email_config, verify_sendgrid_domain,
        )
        validate_email_config()
        await verify_sendgrid_domain()
    except Exception as e:
        logger.warning(f"[iter270] Email deliverability check failed (non-fatal): {e}")

    # Hand control to the app
    yield

    # ── SHUTDOWN ──
    try:
        scheduler.shutdown()
    except Exception as e:
        logger.warning(f"scheduler shutdown failed: {e}")
    try:
        client.close()
    except Exception as e:
        logger.warning(f"Mongo client close failed: {e}")


app = FastAPI(lifespan=lifespan)
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

# iter234 — GZip must NOT consume StreamingResponse generators end-to-end
# (it would buffer the full Gemini stream before flushing, killing chunked UX).
# Subclass to opt-out streaming paths.
class _ScopedGZipMiddleware(GZipMiddleware):
    _STREAM_PATH_PREFIXES = ("/api/chat/stream",)

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if any(path.startswith(p) for p in self._STREAM_PATH_PREFIXES):
                # Skip compression for streaming routes — preserves chunked transfer.
                await self.app(scope, receive, send)
                return
        await super().__call__(scope, receive, send)

app.add_middleware(_ScopedGZipMiddleware, minimum_size=500)
_cors_origins_env = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] if _cors_origins_env else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if _cors_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── iter354 www_canonical_redirect REMOVED (ticket 209107) — was redirecting
# bidvex.com -> www.bidvex.com with a 301, stripping CORS headers since
# www.bidvex.com is an unverified custom domain. bidvex.com is the verified
# apex; it must be served directly, not redirected. ───

# ─── iter354 — Bot-UA prerender middleware (preview validation layer) ───
# In preview, this intercepts crawler traffic and serves the SSR HTML instead
# of the SPA. In production, the Cloudflare Worker does the same at the edge
# and this middleware is a no-op (bot traffic hits `/api/prerender/...`
# directly and the middleware sees `X-Prerender-Version` header, skipping).
try:
    from routes.prerender import BotPrerenderMiddleware as _BotPrerenderMiddleware
    _prerender_enabled = os.environ.get("PRERENDER_MIDDLEWARE_ENABLED", "1") == "1"
    app.add_middleware(_BotPrerenderMiddleware, enabled=_prerender_enabled)
    logger.info(f"[iter354] BotPrerenderMiddleware enabled={_prerender_enabled}")

    # iter361 — Cache-Control layer. Sets immutable cache on static assets
    # (JS/CSS/PNG/WOFF, 1-year TTL) and forces bots to receive no-store
    # responses (defensive hedge against the crawler-cache layer sitting
    # in front of production).
    from routes.seo_admin import CacheHeadersMiddleware as _CacheHeadersMiddleware
    app.add_middleware(_CacheHeadersMiddleware)
    logger.info("[iter361] CacheHeadersMiddleware enabled")
except Exception as _pmw_exc:
    logger.warning(f"[iter354] BotPrerenderMiddleware failed to register: {_pmw_exc}")

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
    # iter375 — public landing-page render endpoint needs SAMEORIGIN so
    # the admin editor's preview iframe can display the published page.
    # Cross-origin framing is still blocked.
    if path.startswith("/api/lp/") and path.endswith("/render"):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    else:
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
    elif path.startswith("/api/feeds/facebook-local"):
        # iter217 Phase 5 — Meta product feed: 15 min cache for Meta's crawler.
        response.headers["Cache-Control"] = "public, max-age=900"
        response.headers["CDN-Cache-Control"] = "public, max-age=900"
        response.headers["Access-Control-Allow-Origin"] = "*"
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
    # iter217 Phase 5 — Meta product feed (must be public-cacheable for Meta's crawler)
    "/api/feeds/facebook-local",
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


# ─── iter309 — Bilingual validation error handler ──────────────────
# Converts FastAPI's default 422 validation envelope into a clean 400
# with EN/FR field-by-field error messages. This is what the frontend
# binds to inline form errors (instead of the generic 500 popup).
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse as _JSONResponse


# Reusable field-name → bilingual label lookup. Listing routes were the
# P0 hot path for iter309; add entries as new forms emerge.
_FIELD_LABELS_BILINGUAL = {
    "title": ("Title", "Titre"),
    "title_fr": ("French title", "Titre en français"),
    "description": ("Description", "Description"),
    "description_fr": ("French description", "Description en français"),
    "category": ("Category", "Catégorie"),
    "condition": ("Condition", "État"),
    "starting_price": ("Starting price", "Prix de départ"),
    "starting_bid": ("Starting bid", "Mise de départ"),
    "buy_now_price": ("Buy-now price", "Prix achat immédiat"),
    "reserve_price": ("Reserve price", "Prix de réserve"),
    "location": ("Location", "Emplacement"),
    "city": ("City", "Ville"),
    "region": ("Province / Region", "Province / Région"),
    "country": ("Country", "Pays"),
    "auction_end_date": ("Auction end date", "Date de fin de l'enchère"),
    "auction_start_date": ("Auction start date", "Date de début de l'enchère"),
    "duration_days": ("Duration (days)", "Durée (jours)"),
    "images": ("Photos", "Photos"),
    "payment_method": ("Payment method", "Méthode de paiement"),
    "lots": ("Lots", "Lots"),
    "vin": ("VIN", "NIV"),
    "make": ("Make", "Marque"),
    "model": ("Model", "Modèle"),
    "year": ("Year", "Année"),
    "mileage": ("Mileage", "Kilométrage"),
}


def _label_for(field_name: str) -> tuple[str, str]:
    label = _FIELD_LABELS_BILINGUAL.get(field_name)
    if label:
        return label
    # Fallback: prettify the field name itself in both languages
    pretty = field_name.replace("_", " ").strip().capitalize()
    return (pretty, pretty)


@app.exception_handler(RequestValidationError)
async def _bilingual_validation_handler(request: Request, exc: RequestValidationError):
    """Convert Pydantic validation errors → 400 with bilingual messages."""
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if str(p) != "body"]
        field_name = loc[-1] if loc else "body"
        en_label, fr_label = _label_for(field_name)
        etype = err.get("type", "")
        if etype == "missing" or etype.endswith("_required"):
            msg_en = f"Missing field: {en_label}"
            msg_fr = f"Champ manquant : {fr_label}"
        elif etype.startswith("string_too_short"):
            msg_en = f"{en_label} is too short"
            msg_fr = f"{fr_label} est trop court"
        elif etype.startswith("greater_than") or etype.startswith("less_than"):
            msg_en = f"{en_label} value out of range"
            msg_fr = f"Valeur de « {fr_label} » hors limites"
        elif etype.startswith("type_error") or etype.startswith("value_error"):
            msg_en = f"{en_label} format is invalid"
            msg_fr = f"Format de « {fr_label} » invalide"
        else:
            base = err.get("msg") or "Invalid value"
            msg_en = f"{en_label}: {base}"
            msg_fr = f"{fr_label} : valeur invalide"
        fields.append({
            "field": ".".join(loc) if loc else "body",
            "message_en": msg_en,
            "message_fr": msg_fr,
            "code": etype or "invalid",
        })
    return _JSONResponse(
        status_code=400,
        content={
            "detail": {
                "code": "validation_error",
                "message_en": "Some required fields are missing or invalid.",
                "message_fr": "Certains champs requis sont manquants ou invalides.",
                "fields": fields,
            }
        },
    )



# ─── iter306 — Global Backend Exception Handler ───
# Captures all unhandled exceptions and writes them to the `backend_errors`
# collection so production issues surface in the admin Error Logs tab.
# Returns a generic 500 with a bilingual error envelope; never leaks stack traces.
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    """Log + return generic 500 for any unhandled exception."""
    from fastapi.responses import JSONResponse
    import traceback as _tb
    try:
        user_id = None
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            try:
                import base64, json as _json
                token = auth.split(" ", 1)[1]
                payload_b64 = token.split(".")[1] + "=="
                payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
                user_id = payload.get("sub") or payload.get("user_id")
            except Exception:
                pass
        await db.backend_errors.insert_one({
            "id": str(uuid.uuid4()),
            "endpoint": str(request.url.path),
            "method": request.method,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:2000],
            "stack_trace": "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))[:5000],
            "user_id": user_id,
            "ip": request.client.host if request.client else "",
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as log_err:
        logger.error(f"[global-exception-handler] Failed to log exception: {log_err}")
    logger.error(f"[unhandled] {request.method} {request.url.path} -> {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "internal_server_error",
                "message_en": "An unexpected error occurred. Our team has been notified.",
                "message_fr": "Une erreur inattendue est survenue. Notre équipe a été notifiée.",
            }
        },
    )

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


# iter296 P0 — FIX BUG 1: Sync lambdas returning coroutines were never
# awaited by APScheduler's AsyncIOExecutor → the marketplace
# `process_ended_auctions` job (and 6 others) were dead since
# registration. Each job below is now an `async def` wrapper that
# APScheduler awaits correctly.

async def _job_transition_upcoming_auctions():
    await safe_run("transition_upcoming_auctions", transition_upcoming_auctions(db))


async def _job_process_ended_auctions():
    await safe_run("process_ended_auctions", run_process_ended_auctions())


async def _job_expire_partner_pro_trials():
    await safe_run("expire_partner_pro_trials", expire_partner_pro_trials(db))


async def _job_send_trial_reminder_emails():
    await safe_run("send_trial_reminder_emails", send_trial_reminder_emails(db))


async def _job_send_auction_payment_reminders():
    await safe_run("send_auction_payment_reminders", send_auction_payment_reminders(db))


async def _job_process_overdue_auction_payments():
    await safe_run("process_overdue_auction_payments", process_overdue_auction_payments(db))


async def _job_send_review_request_emails():
    await safe_run("send_review_request_emails", send_review_request_emails(db))


async def _job_keepalive_ping():
    await safe_run("keepalive_ping", keepalive_ping())


# iter297 P1 — Nightly sweep for ended-with-winner listings whose
# pickup wasn't confirmed within 7 days → flag pending_review + ping
# admins.
async def _job_flag_stuck_transactions():
    from services.pickup_confirmation import flag_stuck_transactions
    await safe_run("flag_stuck_transactions", flag_stuck_transactions(db))


# iter297 P1 — Nightly Pillow placeholder regeneration for the
# Meta/Google feeds. Pre-bakes a branded JPEG for every active/upcoming
# listing missing a valid image URL.
async def _job_regenerate_feed_placeholders():
    from services.feed_placeholder_image import regenerate_missing_feed_placeholders
    await safe_run("regenerate_feed_placeholders",
                   regenerate_missing_feed_placeholders(db))


scheduler.add_job(
    _job_transition_upcoming_auctions,
    trigger=IntervalTrigger(minutes=5), id='transition_upcoming_auctions', replace_existing=True)
scheduler.add_job(
    _job_process_ended_auctions,
    trigger=IntervalTrigger(minutes=1), id='process_ended_auctions', replace_existing=True)
scheduler.add_job(
    _job_expire_partner_pro_trials,
    trigger=IntervalTrigger(hours=1), id='expire_trials', replace_existing=True)
scheduler.add_job(
    _job_send_trial_reminder_emails,
    trigger=IntervalTrigger(hours=1), id='trial_reminders', replace_existing=True)

# ── iter399 — Subscription trial-conversion reminder (T-3 days) ──
# Sends a bilingual EN+FR email to every user whose 30-day trial converts
# to paid billing in exactly 3 days. Daily at 09:00 UTC (5am ET, well
# before most Canadian users open their inbox mid-morning).
from apscheduler.triggers.cron import CronTrigger as _CronTrigger_iter399
from services.trial_conversion_reminder import send_trial_conversion_reminders
async def _job_send_trial_conversion_reminders():
    await safe_run("trial_conversion_reminder", send_trial_conversion_reminders(db))
scheduler.add_job(
    _job_send_trial_conversion_reminders,
    trigger=_CronTrigger_iter399(hour=9, minute=0, timezone="UTC"),
    id='trial_conversion_reminders_iter399',
    replace_existing=True,
)
scheduler.add_job(
    _job_send_auction_payment_reminders,
    trigger=IntervalTrigger(hours=1), id='payment_reminders', replace_existing=True)
scheduler.add_job(
    _job_process_overdue_auction_payments,
    trigger=IntervalTrigger(hours=6), id='overdue_payments', replace_existing=True)
scheduler.add_job(
    _job_send_review_request_emails,
    trigger=IntervalTrigger(hours=1), id='review_requests', replace_existing=True)
scheduler.add_job(
    _job_keepalive_ping,
    trigger=IntervalTrigger(minutes=4), id='keepalive_ping', replace_existing=True)
# iter297 P1 — nightly sweep at 3:00 UTC.
from apscheduler.triggers.cron import CronTrigger
scheduler.add_job(
    _job_flag_stuck_transactions,
    trigger=CronTrigger(hour=3, minute=0),
    id='flag_stuck_transactions', replace_existing=True)
# iter297 P1 — nightly Pillow placeholder regeneration at 3:30 UTC.
scheduler.add_job(
    _job_regenerate_feed_placeholders,
    trigger=CronTrigger(hour=3, minute=30),
    id='regenerate_feed_placeholders', replace_existing=True)

# ── iter401 — Seller Action Marketing Emails (Flow 2) ──
# Three triggers, all cron-driven:
#   A) Draft ≥24h — hourly at :15
#   B) Auction starts in 90–150 min — hourly at :35 (matches lower/upper bound)
#   C) Ended ≥24h with unapproved winners — hourly at :45
from services.marketing_flows import (
    run_seller_draft_reminders,
    run_seller_auction_starting_reminders,
    run_seller_winner_approval_reminders,
)
async def _job_seller_draft_reminders():
    await safe_run("seller_draft_reminders", run_seller_draft_reminders(db))
async def _job_seller_starting_reminders():
    await safe_run("seller_starting_reminders", run_seller_auction_starting_reminders(db))
async def _job_seller_winner_reminders():
    await safe_run("seller_winner_reminders", run_seller_winner_approval_reminders(db))
scheduler.add_job(_job_seller_draft_reminders,   trigger=CronTrigger(minute=15), id='iter401_draft',    replace_existing=True)
scheduler.add_job(_job_seller_starting_reminders, trigger=CronTrigger(minute=35), id='iter401_starting', replace_existing=True)
scheduler.add_job(_job_seller_winner_reminders,   trigger=CronTrigger(minute=45), id='iter401_winners',  replace_existing=True)

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

async def _watchlist_expiry_alerts_tick():
    """AsyncIOScheduler wrapper — must be a coroutine function so the executor awaits it."""
    await safe_run("watchlist_expiry_alerts", run_watchlist_expiry_alerts())

scheduler.add_job(
    _watchlist_expiry_alerts_tick,
    trigger=IntervalTrigger(minutes=2), id='watchlist_expiry_alerts', replace_existing=True)


# iter306 — 1-hour pre-end nudge (push notification only — emails handled elsewhere)
async def run_watchlist_1h_nudge():
    try:
        now = datetime.now(timezone.utc)
        # 60-65 minute window so each item is only nudged once per scheduler tick (runs every 5 min)
        in_60_min = now + timedelta(minutes=60)
        in_65_min = now + timedelta(minutes=65)
        expiring = await db.listings.find(
            {"status": "active", "auction_end_date": {"$gte": in_60_min.isoformat(), "$lt": in_65_min.isoformat()}},
            {"_id": 0, "id": 1, "title": 1, "category": 1}
        ).to_list(100)
        from services.push_dispatcher import dispatch_push
        for listing in expiring:
            lid = listing["id"]
            cat = (listing.get("category") or "").lower()
            is_vehicle = any(v in cat for v in ("vehicle", "car", "auto"))
            watchers = await db.watchlist.find({"listing_id": lid}, {"_id": 0, "user_id": 1}).to_list(200)
            for w in watchers:
                await dispatch_push(
                    db, user_id=w["user_id"], kind="ending_soon_1h",
                    title_item=listing.get("title", "Item"),
                    listing_id=lid, is_vehicle=is_vehicle,
                )
    except Exception as e:
        logger.warning(f"Watchlist 1h nudge failed: {e}")


async def _watchlist_1h_nudge_tick():
    """iter377 — AsyncIOScheduler wrapper. The previous `lambda: safe_run(...)`
    returned a coroutine that the executor never awaited, so this job silently
    stopped running (and emitted a `coroutine … was never awaited` warning on
    every tick)."""
    await safe_run("watchlist_1h_nudge", run_watchlist_1h_nudge())

scheduler.add_job(
    _watchlist_1h_nudge_tick,
    trigger=IntervalTrigger(minutes=5), id='watchlist_1h_nudge', replace_existing=True)


# iter307 — Bill 96 auto-suspend sweep (every 30 min)
async def run_bill96_autosuspend():
    try:
        from routes.admin_compliance import bill96_autosuspend_sweep
        count = await bill96_autosuspend_sweep(db)
        if count:
            logger.info(f"[iter307] Bill 96 auto-suspended {count} QC listing(s) past 48h notice")
    except Exception as e:
        logger.warning(f"Bill 96 sweep failed: {e}")


async def _bill96_autosuspend_tick():
    await safe_run("bill96_autosuspend", run_bill96_autosuspend())

scheduler.add_job(
    _bill96_autosuspend_tick,
    trigger=IntervalTrigger(minutes=30), id='bill96_autosuspend', replace_existing=True)


# iter307 — Nightly sitemap + robots regeneration (2am ET = 06:00 UTC)
async def run_sitemap_regen():
    try:
        from services.sitemap_regen import regenerate_sitemap_and_robots
        counts = await regenerate_sitemap_and_robots(db)
        logger.info(f"[iter307] Sitemap regenerated: {counts}")
    except Exception as e:
        logger.warning(f"Sitemap regen failed: {e}")


async def _sitemap_regen_tick():
    await safe_run("sitemap_regen", run_sitemap_regen())

scheduler.add_job(
    _sitemap_regen_tick,
    trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
    id='sitemap_regen', replace_existing=True,
)


# iter307 — Run once at startup so a freshly-deployed environment has a
# valid sitemap before the first cron tick fires.
async def _initial_sitemap_regen():
    try:
        from services.sitemap_regen import regenerate_sitemap_and_robots
        await regenerate_sitemap_and_robots(db)
    except Exception as e:
        logger.warning(f"[iter307] startup sitemap regen failed: {e}")


@app.on_event("startup")
async def _iter307_startup_sitemap():
    await _initial_sitemap_regen()


# iter341 — Summer Grand Opening OG card: generated once at startup and
# served statically from frontend/public (public, no auth — social crawlers).
@app.on_event("startup")
async def _iter341_startup_og_card():
    try:
        import asyncio as _aio
        from services.og_card import ensure_summer_og_card
        await _aio.to_thread(ensure_summer_og_card)
    except Exception as e:
        logger.warning(f"[iter341] OG card generation failed: {e}")

# iter241 Mission 1 — Sweep expired listing promotions every hour.
async def run_promotion_expiry_sweep():
    try:
        from services.promotion_expiry import expire_listing_promotions
        stats = await expire_listing_promotions(db)
        if stats.get("expired_count", 0) > 0:
            logger.info(f"[promo-expiry] hourly sweep: {stats}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Promotion expiry sweep failed: {e}")

async def _promotion_expiry_sweep_tick():
    await safe_run("promotion_expiry_sweep", run_promotion_expiry_sweep())

scheduler.add_job(
    _promotion_expiry_sweep_tick,
    trigger=IntervalTrigger(hours=1), id='promotion_expiry_sweep', replace_existing=True)

# ─── iter378 — Weekly marketing digest (Mon 08:00 UTC) ────────────
from apscheduler.triggers.cron import CronTrigger as _WeeklyCronTrigger

async def run_weekly_marketing_digest():
    """Send each opted-in user a personalised weekly digest email —
    followed sellers' new listings, watchlist updates, interest matches.
    Bilingual EN/FR; unsubscribe honoured via send_email(is_marketing=True).
    Transactional bid emails are NOT touched by this job."""
    from services.weekly_digest import run_weekly_digest_batch
    return await run_weekly_digest_batch(db)

async def _weekly_marketing_digest_tick():
    """AsyncIOScheduler wrapper — must be a coroutine function so the
    executor awaits it (iter377 pattern)."""
    await safe_run("weekly_marketing_digest", run_weekly_marketing_digest(),
                   timeout_seconds=1500)  # allow up to 25 min for large sends

scheduler.add_job(
    _weekly_marketing_digest_tick,
    trigger=_WeeklyCronTrigger(day_of_week='mon', hour=8, minute=0, timezone="UTC"),
    id='weekly_marketing_digest', replace_existing=True,
)

# ─── iter379 — Partner-trial expiry sweep (every 6 h) ─────────────
async def run_partner_trial_expiry_job():
    """Expire admin-granted partner trials whose date has passed.
    iter378 audit surfaced that the existing `expire_partner_pro_trials`
    job only touches subscription-trial fields; admin-granted partner
    trials (partner_trial_active + trial_expires_at) never expired.
    """
    from services.partner_trial_expiry import run_partner_trial_expiry
    return await run_partner_trial_expiry(db)

async def _partner_trial_expiry_tick():
    """AsyncIOScheduler wrapper — coroutine function so the executor
    awaits it (iter377 pattern)."""
    await safe_run("partner_trial_expiry", run_partner_trial_expiry_job())

scheduler.add_job(
    _partner_trial_expiry_tick,
    trigger=IntervalTrigger(hours=6),
    id='partner_trial_expiry', replace_existing=True,
)

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

# ─── Dealer License Expiry sweep (iter195 — daily) ───
async def _dealer_license_expiry_tick():
    from services.scheduled_jobs import process_expired_dealer_licenses
    await safe_run("dealer_license_expiry", process_expired_dealer_licenses(db))

scheduler.add_job(
    _dealer_license_expiry_tick,
    trigger=IntervalTrigger(hours=6), id='dealer_license_expiry', replace_existing=True)

# ─── iter299 P1 — "Last Chance" 1-hour nudge (every 10 min) ───
async def _last_chance_tick():
    from services.last_chance import process_last_chance_nudges
    await safe_run("last_chance_nudges", process_last_chance_nudges(db))

scheduler.add_job(
    _last_chance_tick,
    trigger=IntervalTrigger(minutes=10), id='last_chance_nudges', replace_existing=True)

# ─── iter300 P1 — Nightly Top Seller badge recalculation (04:15 UTC) ───
async def _top_seller_recalc_tick():
    from services.top_sellers import recalculate_top_sellers
    await safe_run("top_seller_recalc", recalculate_top_sellers(db))

from apscheduler.triggers.cron import CronTrigger as _CronTrigger
scheduler.add_job(
    _top_seller_recalc_tick,
    trigger=_CronTrigger(hour=4, minute=15, timezone="UTC"),
    id='top_seller_recalc', replace_existing=True)

# ─── iter300 P1 — Hourly overdue-payment auto-capture ───
async def _overdue_autocapture_tick():
    from services.overdue_autocapture import process_overdue_autocapture
    await safe_run("overdue_autocapture", process_overdue_autocapture(db))

scheduler.add_job(
    _overdue_autocapture_tick,
    trigger=IntervalTrigger(hours=1), id='overdue_autocapture', replace_existing=True)

# ─── Phase 5 — Meta product feed cache warming (every 10 min) ───
async def _fb_feed_cache_warm_tick():
    """Pre-builds the unfiltered feed so Meta's crawler always hits warm cache.
    The 30s crawler timeout makes cold MongoDB reads risky on a busy catalog."""
    import time as _t
    started = _t.time()
    from routes.feeds import _build_feed_items, FEED_MAX_ITEMS_PER_REQUEST
    from services.feed_cache import cache_set, make_cache_key, invalidate_feed_cache

    invalidate_feed_cache()
    items, exclusions = await _build_feed_items(None, None, None, FEED_MAX_ITEMS_PER_REQUEST, 0)
    cache_set(make_cache_key(None, None, None, FEED_MAX_ITEMS_PER_REQUEST, 0), items, exclusions)
    logger.info(
        "FB feed cache warmed: %d items, took %.2fs",
        len(items), _t.time() - started,
    )

async def _fb_feed_cache_warm_scheduler_tick():
    await safe_run("fb_feed_cache_warm", _fb_feed_cache_warm_tick())

scheduler.add_job(
    _fb_feed_cache_warm_scheduler_tick,
    trigger=IntervalTrigger(minutes=10), id='fb_feed_cache_warm', replace_existing=True)

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
    # iter297 cleanup #1 — users_router was imported at line 814 but
    # never registered. Routes like /api/users/me/stats were only being
    # served by profiles.py's catch-all because users_router was dead.
    # Registering it makes /api/users/* endpoints (sold-counter union,
    # profile-summary, /me PATCH, etc.) actually reachable.
    for router in [analytics_router, auctions_router, bids_router, listings_router,
                   auth_router, sms_router, payments_router, webhooks_router,
                   marketplace_router, admin_router, dashboard_router, profiles_router,
                   users_router,
                   deposits_router, insights_router, community_router, escrow_router]:
        api_router.include_router(router)

    # Self-contained routers (import from deps directly)
    SELF_CONTAINED_ROUTERS = [
        ("routes.team", "team_router", "set_team_db", True),  # True = app-level
        # iter354 — SEO prerender endpoint (crawler-only HTML rendering)
        ("routes.prerender", "router", None, False),
        # iter355 — H-1 Bidder Identity (Stripe Identity KYC soft-gate)
        ("routes.identity", "identity_router", "set_identity_db", False),
        # iter357 — Public platform stats (no auth) — social proof widget
        ("routes.public_stats", "public_stats_router", None, False),
        # iter373 — Admin Landing Page Builder (backend foundation)
        ("routes.landing_pages", "router", "set_db", False),
        ("routes.ai_chat", "ai_chat_router", "set_ai_chat_db", False),
        # iter234 — Direct google-genai (Gemini 2.5 Flash) streaming chat + watchdog
        ("routes.genai_chat", "genai_chat_router", "set_genai_chat_db", False),
        # iter236 Mission 2 — Geo-aware listings search (lat/lng/radius + city).
        ("routes.geo_search", "geo_router", "set_geo_db", False),
        # iter238 Mission 1 — Onboarding endpoint (post-Google-signin wizard).
        ("routes.onboarding", "onboarding_router", "set_onboarding_db", False),
        # iter238 Mission 4 — AI chat history + proactive notifications.
        ("routes.chat_history", "chat_history_router", "set_chat_history_db", False),
        # iter238 Mission 5 — Promoted/featured listings + admin backfill.
        ("routes.promotions", "promotions_router", "set_promotions_db", False),
        # iter274 — Trial-coupon routers MUST be mounted before
        # admin_promotions_router because that router declares
        # `/admin/promotions/{promo_id}` which would otherwise greedy-
        # match our `/admin/promotions/coupons` listing endpoint.
        ("routes.trial_coupons", "admin_coupons_router", None, False),
        ("routes.trial_coupons", "public_coupons_router", None, False),
        # iter241 Mission 7 — Admin Promotions & Offers Engine.
        ("routes.admin_promotions", "admin_promotions_router", None, False),
        # iter258 Mission 1 — Admin Request Payment + Stripe Payment Links.
        ("routes.admin_payment_requests", "admin_payment_requests_router", None, False),
        # iter261 Mission 1 — Public pay endpoints + BidVex-hosted pay page.
        ("routes.public_payments", "public_payments_router", None, False),
        # iter264 Mission 4 — Generic admin oversight (disputes, compliance, auctions).
        ("routes.admin_oversight", "admin_oversight_router", None, False),
        ("routes.admin_oversight", "public_disputes_router", None, False),
        # iter264 Mission 6 — User-controlled notification preferences.
        ("routes.notification_prefs", "notification_prefs_router", None, False),
        # iter258 Mission 4 — Partner trial activation (dealer/broker/storage).
        ("routes.partner_trial", "partner_trial_router", None, False),
        # iter259 — Admin management of partner trials (list/extend/revoke).
        ("routes.partner_trial", "admin_partner_trials_router", None, False),
        # iter276 — BidVex AI Core Platform Assistant (Gemini-backed,
        # via the Emergent Universal LLM Key). Exposes /api/support/chat
        # + /api/support/health.
        ("routes.support", "router", None, False),
        # iter241 Mission 1 — Stripe checkout for promoted listings + email credits.
        ("routes.payments_promotions", "promotions_sub_router", None, False),
        ("routes.fees", "fees_router", None, False),
        ("routes.notifications", "notifications_router", None, False),
        # iter267 Mission 2 — Admin notification attachment download.
        ("routes.notifications", "admin_notifications_router", None, False),
        # iter271 — External campaign manager (acquisition emails).
        ("routes.external_campaigns", "router", None, False),
        ("routes.external_campaigns", "public_router", None, False),
        ("routes.external_campaigns", "suppression_router", None, False),
        ("routes.watchlist", "watchlist_router", None, False),
        ("routes.tax", "tax_calc_router", None, False),
        ("routes.messages", "messages_router", "set_messages_db", False),
        ("routes.vehicle_buyer_verification", "buyer_verification_router", "set_buyer_verification_db", True),
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
        ("routes.admin_unsubscribe_audit", "admin_unsubscribe_audit_router", None, False),
        ("routes.admin_offline_transactions", "admin_offline_tx_router", None, False),
        ("routes.public_recently_sold", "public_recently_sold_router", None, False),
        ("routes.drafts", "drafts_router", None, False),
        # iter316 — Twilio Dialer + Contractor Commission Engine
        ("routes.twilio", "router", None, False),
        ("routes.admin_bulk", "admin_bulk_router", None, False),
        ("routes.admin_listing_edit", "admin_listing_edit_router", None, False),
        ("routes.admin_end_time", "admin_end_time_router", None, False),
        ("routes.admin_ai_review", "ai_review_router", None, False),
        ("routes.admin_conversion_funnel", "conversion_funnel_router", None, False),
        ("routes.storage_cleanout", "storage_cleanout_router", None, False),
        ("routes.admin_maintenance", "admin_maintenance_router", None, False),
        ("routes.down_payments", "down_payments_router", None, False),
        ("routes.partner_card", "partner_card_router", None, False),
        ("routes.dealer_subscription_routes", "dealer_subscription_router", None, False),
        ("routes.broker_subscription_routes", "broker_subscription_router", None, False),
        ("routes.manual_settlement", "manual_settlement_router", None, False),
        ("routes.pricing_engine_routes", "pricing_engine_router", None, False),
        ("routes.demo_account_routes", "demo_accounts_router", None, False),
        # Phase 6.2 Task 6 — Storage Facility Manager Dashboard
        ("routes.facility_dashboard", "facility_router", None, True),
        ("routes.facility_dashboard", "public_facility_router", None, True),
        # iter217 Phase 5 — public Meta product catalog feed
        ("routes.feeds", "router", None, False),
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

    # ─── iter217 Phase 5 Hotfix v5b — Broker Ecosystem ───
    try:
        from routes.brokers import brokers_router
        app.include_router(brokers_router)
        # iter217 Phase 5 Hotfix v7 — Individual seller, dispute, ratings
        from routes.broker_compliance import broker_compliance_router
        app.include_router(broker_compliance_router)
        logger.info("Broker ecosystem router registered")
    except Exception as e:
        logger.error(f"Failed to register broker router: {e}")
        import traceback
        traceback.print_exc()

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

    # iter194 — Vehicle dealer license + 2.5% unlock fee
    # iter213: migration is invoked from the `lifespan` handler at the top
    # of this module; we only mount the router here.
    from routes.vehicle_dealer_extras import router as vehicle_dealer_router
    api_router.include_router(vehicle_dealer_router)

    from routes.storage_auctions import storage_router
    api_router.include_router(storage_router)

    # Admin Payment Charges (strict payment system observability)
    from routes.admin_charges import admin_charges_router
    api_router.include_router(admin_charges_router)

    # Strict bidder deposits (Spec Feature 1 — partner-defined deposits)
    from routes.bidder_deposits import bidder_deposits_router
    api_router.include_router(bidder_deposits_router)

    # iter214 P2 — Admin user-action endpoints (send notification, request docs)
    from routes.admin_user_actions import router as admin_user_actions_router
    api_router.include_router(admin_user_actions_router)

    # iter311 — Unified server-aggregated admin listing view across the
    # 4 listing collections (replaces 4 client-side fetches with 1).
    from routes.admin_listings_aggregated import router as admin_listings_aggregated_router
    api_router.include_router(admin_listings_aggregated_router)

    # iter214 P1 — Individual-seller pickup-code system
    from routes.transaction_pickup_code import router as pickup_code_router
    api_router.include_router(pickup_code_router)

    # iter288 — Listing change-request pipeline (user self-service + admin triage)
    from routes.listing_requests import router as listing_requests_router
    # iter297 P1 — Pickup-confirmation router (closes auction-end
    # transaction loop with deposit release + rating-request emails).
    try:
        from routes.pickup_confirm import (
            pickup_confirm_router,
            set_pickup_confirm_db,
            set_pickup_confirm_auth_and_bind,
        )
        set_pickup_confirm_db(db)
        set_pickup_confirm_auth_and_bind(get_current_user)
        api_router.include_router(pickup_confirm_router)
        logger.info("✅ Pickup-confirmation routes mounted")
    except Exception as e:
        logger.error(f"Pickup-confirmation router mount failed: {e}")

    api_router.include_router(listing_requests_router)

    # iter298 BUG 2 — Relist flow for zero-bid ended auctions.
    from routes.relist import relist_router
    api_router.include_router(relist_router)

    # iter299 P1 — Marketplace listings moderation (approve / reject).
    from routes.admin_moderation import moderation_router
    api_router.include_router(moderation_router)

    # iter299 P2 — Admin advanced analytics.
    from routes.admin_analytics import analytics_router
    api_router.include_router(analytics_router)

    # iter300 P2 — Follow Seller.
    from routes.follows import follows_router
    api_router.include_router(follows_router)

    # iter300 P1 — Dispute resolution (file + admin tooling).
    from routes.disputes import disputes_router
    api_router.include_router(disputes_router)

    # iter302 — Winner & Settlement panel + buyer Settle Payment flow.
    from routes.settlement import settlement_router
    api_router.include_router(settlement_router)

    # iter307 — Admin Compliance Dashboard (5 sections)
    from routes.admin_compliance import compliance_router
    api_router.include_router(compliance_router)

    # iter307 — Affiliate / Referral program
    from routes.affiliate import affiliate_router, referral_redirect_router
    api_router.include_router(affiliate_router)
    # Public landing /r/{code} must be at the app root, not behind /api,
    # since the link is the user-facing URL bidvex.com/r/CODE.
    app.include_router(referral_redirect_router)

    # iter304 — Lot Templates for multi-lot vehicle auction wizard
    from routes.lot_templates import router as lot_templates_router
    api_router.include_router(lot_templates_router)

    # iter304 — "Verified Auction Firm" badge admin endpoints
    from routes.verified_firm import router as verified_firm_router
    api_router.include_router(verified_firm_router)

    # iter304 — "Email to Friend" share endpoint for vehicle listings
    from routes.email_to_friend import router as email_to_friend_router
    api_router.include_router(email_to_friend_router)

    # iter306 — CSV bulk import of lots into a multi-lot vehicle auction event
    from routes.multi_lot_bulk_import import router as multi_lot_bulk_import_router
    api_router.include_router(multi_lot_bulk_import_router)

    # iter306 — Error logging (frontend + backend) and admin Error Logs tab
    from routes.error_logs import router as error_logs_router
    api_router.include_router(error_logs_router)


    # iter298 BUG 4 — Buyer receipts + seller statements.
    from routes.receipts import receipts_router
    api_router.include_router(receipts_router)

    # iter293 — Multi-Lot Vehicle Auction (Copart-style sequential events)
    from routes.vehicle_multi_lot import vehicle_multi_lot_router, set_vehicle_multi_lot_db
    set_vehicle_multi_lot_db(db)
    app.include_router(vehicle_multi_lot_router)

    # iter293 — Multi-Lot Vehicle Auction scheduler tick (every 15s)
    from services.vehicle_multi_lot_scheduler import tick_once as _ml_tick
    async def _ml_scheduler_tick():
        try:
            await _ml_tick(db)
        except Exception as _e:
            logger.warning(f"vehicle_multi_lot_scheduler tick error: {_e}")
    scheduler.add_job(_ml_scheduler_tick, "interval", seconds=15,
                      id="vehicle_multi_lot_progress",
                      replace_existing=True, max_instances=1)

    # iter293 — Upcoming-notify: "Notify me when live" email triggers
    from routes.upcoming_notify import (
        upcoming_notify_router, set_upcoming_notify_db,
        fire_live_transitions_once as _notif_tick,
    )
    set_upcoming_notify_db(db)
    app.include_router(upcoming_notify_router)
    async def _notif_scheduler_tick():
        try:
            await _notif_tick(db)
        except Exception as _e:
            logger.warning(f"upcoming_notify tick error: {_e}")
    scheduler.add_job(_notif_scheduler_tick, "interval", seconds=30,
                      id="upcoming_notify_fire",
                      replace_existing=True, max_instances=1)

    # SEO: Dynamic sitemap.xml + robots.txt (app-level, not /api)
    from routes.sitemap import sitemap_router
    app.include_router(sitemap_router, tags=["SEO"])

    # iter361 — Admin SEO probe (sitemap health, robots.txt reachability).
    from routes.seo_admin import seo_router as _seo_admin_router
    app.include_router(_seo_admin_router)
    logger.info("[iter361] seo_admin router mounted at /api/admin/seo/*")

    # iter363 — Public contact form endpoint (routes to team inbox via SendGrid).
    from routes.contact import contact_router as _contact_router
    app.include_router(_contact_router)
    logger.info("[iter363] contact router mounted at /api/contact/submit")

    # iter364 — Admin notification-bell aggregate counters.
    from routes.admin_notifications import admin_notifications_router as _adm_notif_router
    app.include_router(_adm_notif_router)
    logger.info("[iter364] admin notifications router mounted at /api/admin/notifications/summary")

    # iter318 BidVex Careers module — public + admin job/applicant API
    try:
        from routes.careers import router as careers_router
        api_router.include_router(careers_router)
        logger.info("iter318 — Careers module mounted under /api/careers and /api/admin/careers")
    except Exception as ce:  # noqa: BLE001
        logger.warning(f"Careers router registration failed (non-fatal): {ce}")

    # iter320 — Live Support Escalation Protocol (AI Core handoff to admin)
    try:
        from routes.support_escalations import router as escalations_router
        api_router.include_router(escalations_router)
        logger.info("iter320 — Support escalation routes mounted at /api/support/escalate + /api/admin/support/escalations")
    except Exception as ce:  # noqa: BLE001
        logger.warning(f"Support escalation router registration failed (non-fatal): {ce}")

    # iter323 — Contractor profile (extension + photo), leaderboard, IVR + SendGrid inbound parse
    try:
        from routes.contractor_profile_ext import router as contractor_profile_ext_router
        from routes.contractor_ivr_inbound import router as contractor_ivr_inbound_router
        from routes.promo import router as promo_router  # iter330 — Summer 2026 promo API
        api_router.include_router(contractor_profile_ext_router)
        api_router.include_router(contractor_ivr_inbound_router)
        api_router.include_router(promo_router)
        logger.info("iter323 — Contractor profile/leaderboard + IVR + SendGrid inbound parse mounted")
    except Exception as ce:  # noqa: BLE001
        logger.warning(f"iter323 router registration failed (non-fatal): {ce}")

    # iter331 — Press/Blogs CRUD + Contractor Aid AI hub (Gemini)
    try:
        from routes.blogs import router as blogs_router
        from routes.contractor_aid import router as contractor_aid_router
        from routes.ai_voice import router as ai_voice_router  # iter334 — AI Voice Assistant (Gemini Live)
        from routes.ai_coach import router as ai_coach_router  # iter335 — Silent AI Coach (outbound)
        from routes.ad_campaigns import router as ad_campaigns_router  # iter337 — Ad Campaigns admin + Gemini copy
        from routes.contractor_prospects import router as contractor_prospects_router  # iter341 — Prospect Finder
        api_router.include_router(blogs_router)
        api_router.include_router(contractor_aid_router)
        api_router.include_router(ai_voice_router)
        api_router.include_router(ai_coach_router)
        api_router.include_router(ad_campaigns_router)
        api_router.include_router(contractor_prospects_router)
        logger.info("iter331 — Blogs CRUD + Contractor Aid AI mounted")
        logger.info("iter334 — AI Voice Assistant (Gemini Live + Twilio Media Streams) mounted")
        logger.info("iter335 — Silent AI Coach (outbound Gemini eavesdrop) mounted")
        logger.info("iter337 — Ad Campaigns admin panel + Gemini copy generator mounted")

        # Idempotent seed of the 6 default press articles (only inserts
        # rows whose slug is missing). Safe to re-run on every boot.
        try:
            from services.blogs_seed import seed_press_articles
            import asyncio as _asyncio
            _asyncio.create_task(seed_press_articles(db))
        except Exception as se:  # noqa: BLE001
            logger.warning(f"iter331 — press_articles seed scheduling failed: {se}")
    except Exception as ce:  # noqa: BLE001
        logger.warning(f"iter331 router registration failed (non-fatal): {ce}")

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
# iter213: startup/shutdown work is now in the `lifespan` context manager
# at the top of this module. The handler imports its helpers from `lifecycle`
# (log_db_status, prewarm_caches, init_cloud_storage, etc.).

async def create_critical_indexes(database):
    """Run on every startup — idempotent, safe to re-run.
    Only the most critical indexes for fast cold-start verification.
    Each index is wrapped independently so one collision doesn't stop the rest.
    """
    critical = [
        ("listings", [("status", 1), ("end_time", 1)], {"background": True}),
        ("storage_auctions", [("status", 1), ("end_time", 1)], {"background": True}),
        ("users", [("email", 1)], {"unique": True, "background": True}),
        # Phase 6.0 / Task 2 + iter298 — Unique-when-set mobile number.
        # PARTIAL (not sparse): sparse unique indexes treat explicit
        # `null` values as duplicate keys, which 500'd every phone-less
        # registration after the first. The partial filter only indexes
        # real string values.
        ("users", [("mobile_number_normalized", 1)],
         {"unique": True, "background": True,
          "partialFilterExpression": {"mobile_number_normalized": {"$type": "string"}}}),
        ("deposits", [("auction_id", 1), ("status", 1)], {"background": True}),
        # TTL — auto-deletes expired refresh tokens
        ("refresh_tokens", [("expires_at", 1)], {"expireAfterSeconds": 0, "background": True}),
        # iter240 — Hot collections that had ZERO indexes before today.
        # `ai_chat_sessions` is queried by (user_id, updated_at) on every
        # history fetch and by (user_id, session_id) on every persist.
        # `notifications` is sorted by (user_id, created_at DESC) on every
        # navbar fetch. Adding these avoids COLLSCAN as both collections grow.
        ("ai_chat_sessions", [("user_id", 1), ("updated_at", -1)], {"background": True}),
        ("ai_chat_sessions", [("user_id", 1), ("session_id", 1)], {"unique": True, "background": True}),
        ("notifications", [("user_id", 1), ("created_at", -1)], {"background": True}),
        # iter301 P2 — high-frequency query fields across the 4 listing
        # collections + bids + messaging + reviews + follows.
        ("listings", [("seller_id", 1)], {"background": True}),
        ("listings", [("winner_id", 1)], {"background": True}),
        ("listings", [("winner_user_id", 1)], {"background": True}),
        ("multi_item_listings", [("status", 1), ("end_time", 1)], {"background": True}),
        ("multi_item_listings", [("seller_id", 1)], {"background": True}),
        ("vehicle_listings", [("status", 1), ("end_time", 1)], {"background": True}),
        ("vehicle_listings", [("seller_id", 1)], {"background": True}),
        ("vehicle_listings", [("winner_id", 1)], {"background": True}),
        ("storage_auctions", [("seller_id", 1)], {"background": True}),
        ("storage_auctions", [("facility_id", 1)], {"background": True}),
        ("bids", [("user_id", 1)], {"background": True}),
        ("bids", [("listing_id", 1), ("created_at", -1)], {"background": True}),
        ("lot_bids", [("user_id", 1)], {"background": True}),
        # iter304 P1 — auction_id-style compound indexes for fast bid history
        ("lot_bids", [("listing_id", 1), ("created_at", -1)], {"background": True}),
        ("vehicle_bids", [("user_id", 1)], {"background": True}),
        ("vehicle_bids", [("vehicle_id", 1), ("created_at", -1)], {"background": True}),
        ("bidding_deposits", [("auction_id", 1), ("created_at", -1)], {"background": True}),
        # iter304 — Lot templates (per-dealer lookup)
        ("lot_templates", [("dealer_id", 1), ("created_at", -1)], {"background": True}),
        # iter304 — Email to friend rate limit log
        ("email_to_friend_log", [("sender_id", 1), ("sent_at", -1)], {"background": True}),
        ("messages", [("conversation_id", 1), ("created_at", -1)], {"background": True}),
        ("messages", [("receiver_id", 1), ("is_read", 1)], {"background": True}),
        ("conversations", [("participants", 1)], {"background": True}),
        ("reviews", [("seller_id", 1), ("status", 1)], {"background": True}),
        ("reviews", [("listing_id", 1)], {"background": True}),
        ("reviews", [("reviewee_id", 1), ("role", 1)], {"background": True}),
        ("follows", [("seller_id", 1)], {"background": True}),
        ("follows", [("follower_id", 1)], {"background": True}),
    ]
    ok = 0
    for coll, keys, opts in critical:
        try:
            await database[coll].create_index(keys, **opts)
            ok += 1
        except Exception as e:
            # iter298 — self-heal the mobile_number_normalized index: the
            # legacy sparse-unique version conflicts with the new partial
            # spec. Drop the stale index once and recreate.
            if coll == "users" and "mobile_number_normalized" in str(keys) and (
                "IndexOptionsConflict" in str(e) or "already exists with different options" in str(e)
            ):
                try:
                    await database.users.drop_index("mobile_number_normalized_1")
                    await database[coll].create_index(keys, **opts)
                    ok += 1
                    logger.info("[critical-index] migrated mobile_number_normalized_1 to partial-unique")
                    continue
                except Exception as e2:
                    logger.warning(f"[critical-index] mobile index migration failed: {e2}")
            logger.warning(f"[critical-index] {coll} {keys}: {e}")
    logger.info(f"✅ Critical database indexes verified ({ok}/{len(critical)} ok)")
    # iter344 — canonical role normalization: "superadmin" → "super_admin"
    try:
        res = await database.users.update_many({"role": "superadmin"}, {"$set": {"role": "super_admin"}})
        if res.modified_count:
            logger.info(f"[role-normalize] migrated {res.modified_count} user(s) superadmin → super_admin")
    except Exception as e:
        logger.warning(f"[role-normalize] failed: {e}")

    # iter346 P0 — Admin unsubscribe self-heal. If any user with role
    # admin/super_admin is currently in a suppressed state, revert it +
    # delete from local suppression collections. This runs on every boot
    # so a stale unsubscribe click on production is auto-repaired before
    # the first email of the day gets silently dropped.
    #
    # ⚠️ SendGrid-side global suppressions must be removed manually via
    # the Dashboard (or via the DELETE API we now trigger below best-effort)
    # because SendGrid is the ultimate silent dropper regardless of DB state.
    try:
        admin_emails = [u["email"] async for u in database.users.find(
            {"role": {"$in": ["admin", "super_admin"]},
             "$or": [
                 {"marketing_unsubscribed": True},
                 {"email_unsubscribed": True},
             ]},
            {"_id": 0, "email": 1},
        )]
        if not admin_emails:
            # Also check dedicated suppression collections for admin emails.
            admin_only = [u["email"] async for u in database.users.find(
                {"role": {"$in": ["admin", "super_admin"]}}, {"_id": 0, "email": 1},
            )]
            admin_emails = admin_only

        if admin_emails:
            # Flip user-doc flags back.
            await database.users.update_many(
                {"email": {"$in": admin_emails}},
                {"$set": {
                    "marketing_unsubscribed": False,
                    "email_unsubscribed": False,
                    "marketing_resubscribed_at": datetime.now(timezone.utc),
                    "marketing_resubscribed_source": "iter346_admin_selfheal",
                }},
            )
            # Remove from local suppression collections.
            r1 = await database.email_suppressions.delete_many({"email": {"$in": admin_emails}})
            r2 = await database.external_email_suppressions.delete_many({"email": {"$in": admin_emails}})
            if r1.deleted_count or r2.deleted_count:
                logger.warning(
                    f"[iter346-admin-unsuppress] cleared local suppressions for "
                    f"admin/super_admin: {admin_emails} "
                    f"(email_suppressions={r1.deleted_count}, "
                    f"external={r2.deleted_count}) — reminder: also clear "
                    f"SendGrid Dashboard suppressions"
                )

            # Best-effort DELETE from SendGrid global suppressions.
            sg_key = os.environ.get("SENDGRID_API_KEY", "")
            if sg_key:
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=10) as _http:
                    for _em in admin_emails:
                        try:
                            _r = await _http.delete(
                                f"https://api.sendgrid.com/v3/asm/suppressions/global/{_em}",
                                headers={"Authorization": f"Bearer {sg_key}"},
                            )
                            if _r.status_code in (204, 200, 404):
                                logger.info(f"[iter346-admin-unsuppress] SendGrid DELETE {_em} → {_r.status_code}")
                            else:
                                logger.warning(
                                    f"[iter346-admin-unsuppress] SendGrid DELETE {_em} → "
                                    f"{_r.status_code} {_r.text[:200]}"
                                )
                        except Exception as _e:  # noqa: BLE001
                            logger.warning(f"[iter346-admin-unsuppress] SendGrid API call failed for {_em}: {_e}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter346-admin-unsuppress] failed: {e}")


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

    # iter267 Mission 3 — Public `/uploads/...` for notification attachments
    # + other persistent files. Path-traversal-protected by StaticFiles
    # which only serves files under the configured directory.
    _uploads_dir = "/app/uploads"
    try:
        os.makedirs(os.path.join(_uploads_dir, "notification_attachments"), exist_ok=True)
        app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")
        logger.info(f"[uploads] Mounted /uploads at {_uploads_dir}")
    except Exception as _exc:  # noqa: BLE001
        logger.warning(f"[uploads] Mount failed: {_exc}")

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
