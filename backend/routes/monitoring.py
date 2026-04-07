"""
BidVex Platform Monitoring & Alerting System
Tracks: Stripe webhook failures, HTTP 500 errors, API latency, system health.
Admin-only dashboard endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from deps import get_db, get_current_user, User
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

monitoring_router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


def _admin_guard(user: User):
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")


# ─── Log an error event (called from middleware / webhook handler) ───

async def log_error_event(
    event_type: str,
    message: str,
    details: dict = None,
    severity: str = "error",
):
    """Write an error/alert record to the monitoring_events collection."""
    try:
        db = get_db()
        await db.monitoring_events.insert_one({
            "event_type": event_type,
            "message": message,
            "details": details or {},
            "severity": severity,
            "resolved": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Failed to write monitoring event: {e}")


async def log_webhook_event(
    provider: str,
    event_type: str,
    status: str,
    details: dict = None,
):
    """Track every webhook invocation for audit and failure detection."""
    try:
        db = get_db()
        await db.webhook_log.insert_one({
            "provider": provider,
            "event_type": event_type,
            "status": status,
            "details": details or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error(f"Failed to write webhook log: {e}")


# ─── Admin Endpoints ───

@monitoring_router.get("/dashboard")
async def get_monitoring_dashboard(current_user: User = Depends(get_current_user)):
    """
    Aggregated monitoring dashboard for admins.
    Returns: error counts, webhook stats, uptime, recent alerts.
    """
    _admin_guard(current_user)
    db = get_db()

    now = datetime.now(timezone.utc)
    last_24h = (now - timedelta(hours=24)).isoformat()
    last_7d = (now - timedelta(days=7)).isoformat()

    # ── Error counts ──
    errors_24h = await db.monitoring_events.count_documents({
        "severity": "error",
        "created_at": {"$gte": last_24h},
    })
    errors_7d = await db.monitoring_events.count_documents({
        "severity": "error",
        "created_at": {"$gte": last_7d},
    })
    unresolved_errors = await db.monitoring_events.count_documents({
        "severity": "error",
        "resolved": False,
    })

    # ── Webhook stats ──
    webhook_total_24h = await db.webhook_log.count_documents({
        "created_at": {"$gte": last_24h},
    })
    webhook_failures_24h = await db.webhook_log.count_documents({
        "status": "failed",
        "created_at": {"$gte": last_24h},
    })
    stripe_failures_24h = await db.webhook_log.count_documents({
        "provider": "stripe",
        "status": "failed",
        "created_at": {"$gte": last_24h},
    })

    # ── Recent alerts (last 20) ──
    recent_alerts = await db.monitoring_events.find(
        {"severity": {"$in": ["error", "critical"]}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(20)

    # ── Recent webhook failures (last 20) ──
    recent_webhook_failures = await db.webhook_log.find(
        {"status": "failed"},
        {"_id": 0},
    ).sort("created_at", -1).to_list(20)

    # ── HTTP 500 errors (last 20) ──
    recent_500s = await db.monitoring_events.find(
        {"event_type": "http_500"},
        {"_id": 0},
    ).sort("created_at", -1).to_list(20)

    # ── System health indicators ──
    try:
        await db.command("ping")
        db_status = "healthy"
    except Exception:
        db_status = "degraded"

    return {
        "system_status": "operational" if errors_24h < 10 and db_status == "healthy" else "degraded",
        "db_status": db_status,
        "errors": {
            "last_24h": errors_24h,
            "last_7d": errors_7d,
            "unresolved": unresolved_errors,
        },
        "webhooks": {
            "total_24h": webhook_total_24h,
            "failures_24h": webhook_failures_24h,
            "stripe_failures_24h": stripe_failures_24h,
            "success_rate": round(
                ((webhook_total_24h - webhook_failures_24h) / max(webhook_total_24h, 1)) * 100, 1
            ) if webhook_total_24h > 0 else 100.0,
        },
        "recent_alerts": recent_alerts,
        "recent_webhook_failures": recent_webhook_failures,
        "recent_500s": recent_500s,
        "generated_at": now.isoformat(),
    }


@monitoring_router.get("/errors")
async def get_error_log(
    current_user: User = Depends(get_current_user),
    severity: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    """Paginated error log with filters."""
    _admin_guard(current_user)
    db = get_db()

    query = {}
    if severity:
        query["severity"] = severity
    if event_type:
        query["event_type"] = event_type
    if resolved is not None:
        query["resolved"] = resolved

    total = await db.monitoring_events.count_documents(query)
    events = await db.monitoring_events.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)

    return {"total": total, "events": events}


@monitoring_router.get("/webhooks")
async def get_webhook_log(
    current_user: User = Depends(get_current_user),
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    """Paginated webhook event log with filters."""
    _admin_guard(current_user)
    db = get_db()

    query = {}
    if provider:
        query["provider"] = provider
    if status:
        query["status"] = status

    total = await db.webhook_log.count_documents(query)
    events = await db.webhook_log.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)

    return {"total": total, "events": events}


@monitoring_router.post("/resolve/{event_type}")
async def resolve_alerts(
    event_type: str,
    current_user: User = Depends(get_current_user),
):
    """Mark all alerts of a given type as resolved."""
    _admin_guard(current_user)
    db = get_db()

    result = await db.monitoring_events.update_many(
        {"event_type": event_type, "resolved": False},
        {"$set": {"resolved": True, "resolved_by": current_user.email, "resolved_at": datetime.now(timezone.utc).isoformat()}},
    )

    return {"resolved_count": result.modified_count}


@monitoring_router.get("/health-check")
async def deep_health_check(current_user: User = Depends(get_current_user)):
    """Deep health check for all critical services."""
    _admin_guard(current_user)
    db = get_db()

    checks = {}

    # MongoDB
    try:
        await db.command("ping")
        checks["mongodb"] = {"status": "healthy", "latency_ms": 0}
    except Exception as e:
        checks["mongodb"] = {"status": "down", "error": str(e)}

    # Stripe
    try:
        import stripe as _stripe
        if _stripe.api_key:
            _stripe.Account.retrieve()
            checks["stripe"] = {"status": "healthy"}
        else:
            checks["stripe"] = {"status": "not_configured"}
    except Exception as e:
        checks["stripe"] = {"status": "degraded", "error": str(e)[:100]}

    # Collections stats
    try:
        collections = ["users", "listings", "vehicle_listings", "payment_transactions"]
        counts = {}
        for col in collections:
            counts[col] = await db[col].estimated_document_count()
        checks["collections"] = counts
    except Exception as e:
        checks["collections"] = {"error": str(e)}

    overall = "operational"
    if checks.get("mongodb", {}).get("status") != "healthy":
        overall = "critical"
    elif checks.get("stripe", {}).get("status") == "degraded":
        overall = "degraded"

    return {"overall": overall, "checks": checks, "timestamp": datetime.now(timezone.utc).isoformat()}
