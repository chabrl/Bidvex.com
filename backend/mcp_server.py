"""
BidVex — Model Context Protocol (MCP) Server (iter485 + iter486)
=================================================================

Additive layer exposing marketplace operations to Claude and other MCP
clients. **Does NOT** reimplement business logic — every tool wraps
existing internal service functions or HTTP endpoints so all snipe
protection, fee calculation, deposit rules, watchdog moderation, and
audit trails apply unchanged.

Transports offered
------------------
* **HTTP JSON-RPC** — `POST /api/mcp/rpc` (single endpoint, JSON-RPC 2.0)
  Used by the stdio bridge and by internal callers.
* **HTTP-SSE** — `GET /api/mcp/sse` + `POST /api/mcp/sse/messages?sid=<id>`
  Standard MCP HTTP-SSE transport (mcp-remote / Claude Web / other
  remote clients).
* **stdio** — via `backend/mcp_bridge.py` (a subprocess Claude Desktop
  launches natively).
* **Legacy REST** — `POST /api/mcp/tools/list` + `POST /api/mcp/tools/call`
  kept for iter485 backwards-compat (internal callers, existing tests).

Access model
------------
- **Auth**: every tool call validates the caller's JWT via the existing
  `deps.get_current_user` FastAPI dependency (same JWT users already
  have). No secrets or shared keys.
- **Subscription gate**: only users with an active paid subscription
  in one of these tiers may use the MCP server:
    * `subscription_tier` in {"premium", "vip", "partner_pro"} with
      `subscription_status="active"`
    * OR `is_vehicle_dealer=True` with an active dealer subscription
    * OR `account_type="broker"` with `subscription_status="active"`
    * OR `account_type="storage_facility"` with `facility_verified=True`
      and `subscription_status="active"`
  Free-tier users receive `SUBSCRIPTION_REQUIRED`.
- **Verification gate**: bid + listing-creation tools additionally
  require phone + payment-method verification (reused via
  `services.trust_gate.require_trust_verified`). Corporate/seller
  tools additionally require verified Seller Tax ID per vertical
  (`dealer_license_verified` / `facility_verified` / `admin_verified`).
- **Rate limit**: 30 tool-calls per minute per JWT subject. Redis-backed
  by default; falls back to in-process bucket if Redis is unreachable.
- **Audit**: every call (success/failure/rejected) is logged to the
  `mcp_audit_logs` collection with sanitized input params.

Registration
------------
This router is exported but **NOT registered by default in `server.py`**.
To enable in preview: `MCP_ENABLED=true` in `.env`.  This is the
"preview only" gate — do not enable in production without explicit
go-ahead.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
import json
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db

logger = logging.getLogger("bidvex.mcp")

mcp_router = APIRouter(prefix="/mcp", tags=["MCP"])

# ─── Constants ────────────────────────────────────────────────────────
MCP_AUDIT_COLLECTION = "mcp_audit_logs"
MCP_SOURCE_TAG = "mcp_claude"
ALLOWED_SUBSCRIPTION_TIERS: Set[str] = {"premium", "vip", "partner_pro"}
ADMIN_ROLES: Set[str] = {"admin", "super_admin"}
NOT_IMPLEMENTED_CODE = "NOT_IMPLEMENTED"

# MCP protocol version (matches the version Claude Desktop and mcp-remote speak).
MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_INFO = {"name": "bidvex-mcp", "version": "1.0.0"}

# Loopback base URL — MCP tools that wrap complex REST handlers call
# them over HTTP so all middleware (rate limiting, watchdog, snipe
# protection) runs unchanged.
_LOOPBACK_BASE = os.environ.get("MCP_LOOPBACK_BASE_URL") or "http://localhost:8001"

# ─── Redis-backed rate limiter with in-process fallback ───────────────
_RATE_WINDOW_S = 60
_RATE_LIMIT_PER_MIN = int(os.environ.get("MCP_RATE_LIMIT_PER_MIN", "30"))
_rate_buckets: Dict[str, List[float]] = defaultdict(list)  # fallback / test control
_redis_client = None
_redis_ready: Optional[bool] = None


async def _get_redis():
    """Lazy-init a Redis client with health probe.

    Returns None when Redis is unreachable — caller must fall back to
    the in-process bucket. Result is cached until the next successful
    ping restores the client.
    """
    global _redis_client, _redis_ready
    url = os.environ.get("REDIS_URL") or ""
    if not url:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        from redis.asyncio import Redis  # local import — optional dep
        client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
        await client.ping()
        _redis_client = client
        _redis_ready = True
        logger.info("[mcp] Redis rate limiter connected")
        return client
    except Exception as exc:  # noqa: BLE001
        _redis_ready = False
        logger.warning(f"[mcp] Redis unavailable, falling back to in-process bucket: {type(exc).__name__}: {exc}")
        return None


async def _rate_limit_check(user_id: str) -> Tuple[bool, int, str]:
    """Sliding-window rate limit.

    Returns `(allowed, remaining, backend)` where `backend ∈ {"redis","memory"}`.
    Falls open on any exception in either backend so a limiter bug can
    never wedge a legitimate user.
    """
    now = time.time()
    # Try Redis first
    client = await _get_redis()
    if client is not None:
        try:
            key = f"mcp:rl:{user_id}"
            # ZSET-based sliding window: score = timestamp
            cutoff = now - _RATE_WINDOW_S
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zcard(key)
            _, count = await pipe.execute()
            if int(count) >= _RATE_LIMIT_PER_MIN:
                return False, 0, "redis"
            member = f"{now}:{uuid.uuid4().hex[:8]}"
            pipe = client.pipeline()
            pipe.zadd(key, {member: now})
            pipe.expire(key, _RATE_WINDOW_S + 5)
            await pipe.execute()
            return True, max(0, _RATE_LIMIT_PER_MIN - int(count) - 1), "redis"
        except Exception as exc:  # noqa: BLE001
            # Reset the cached client so the next call re-probes.
            logger.warning(f"[mcp] Redis rate-limit path failed, falling back to memory: {type(exc).__name__}")
            global _redis_client, _redis_ready
            _redis_client = None
            _redis_ready = False
            # Fall through to in-process bucket below.

    # In-process fallback
    try:
        bucket = _rate_buckets[user_id]
        cutoff = now - _RATE_WINDOW_S
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= _RATE_LIMIT_PER_MIN:
            return False, 0, "memory"
        bucket.append(now)
        return True, max(0, _RATE_LIMIT_PER_MIN - len(bucket)), "memory"
    except Exception:  # noqa: BLE001
        return True, _RATE_LIMIT_PER_MIN, "memory"


# ─── Secret sanitizer for audit-log input params ──────────────────────
# Any dict key matching one of these terms is dropped from the audit
# entry. Value-level patterns catch known secret shapes even when the
# key is innocuous.
_SENSITIVE_KEY_RE = re.compile(
    r"(password|secret|token|api[_-]?key|access[_-]?key|refresh|"
    r"card_?number|cvv|cvc|pan|iban|routing|authorization|cookie|jwt)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"^(sk_(live|test)_|rk_(live|test)_|whsec_|pk_live_|pk_test_|"
    r"AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-]+)",
)


def _sanitize(value: Any, depth: int = 0) -> Any:
    """Recursively strip secrets from any log-bound structure."""
    if depth > 6:
        return "<truncated:depth>"
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if _SENSITIVE_KEY_RE.search(str(k)):
                out[k] = "<redacted:key>"
                continue
            out[k] = _sanitize(v, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_sanitize(v, depth + 1) for v in value][:50]
    if isinstance(value, str):
        if _SENSITIVE_VALUE_RE.match(value):
            return "<redacted:value>"
        if len(value) > 1000:
            return value[:1000] + "…<truncated>"
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    # Anything else (datetime, ObjectId, custom) → string
    return _sanitize(str(value), depth + 1)


async def _write_audit(
    db,
    *,
    user_id: str,
    tool_name: str,
    input_params: Dict[str, Any],
    result_status: str,
    error_code: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> None:
    """Insert an entry into mcp_audit_logs. Never raises — audit failure
    must not affect the user's flow."""
    try:
        doc = {
            "id":              str(uuid.uuid4()),
            "source":          MCP_SOURCE_TAG,
            "user_id":         user_id,
            "tool_name":       tool_name,
            "input_params":    _sanitize(input_params or {}),
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "result_status":   result_status,
            "error_code":      error_code,
            "latency_ms":      latency_ms,
        }
        await db[MCP_AUDIT_COLLECTION].insert_one(doc)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[mcp-audit] insert failed: {exc}")


# ─── Access gates ─────────────────────────────────────────────────────
def _subscription_active(user_doc: Dict[str, Any]) -> bool:
    """True iff the user has an active MCP-eligible subscription.

    Field names verified against the live users collection:
      - subscription_tier ∈ {"free","premium","vip","partner_pro"}
      - subscription_status ∈ {"active", ...}
      - is_vehicle_dealer + dealer_subscription_status + dealer_subscription_active
      - account_type ∈ {"broker","storage_facility","business","personal"}
      - facility_verified (bool)
    """
    tier = (user_doc.get("subscription_tier") or "").lower()
    status = (user_doc.get("subscription_status") or "").lower()
    account_type = (user_doc.get("account_type") or "").lower()

    # (1) Premium / VIP / Partner Pro with active subscription
    if tier in ALLOWED_SUBSCRIPTION_TIERS and status == "active":
        return True

    # (2) Active vehicle dealer subscription
    if user_doc.get("is_vehicle_dealer") is True:
        dealer_status = (user_doc.get("dealer_subscription_status") or "").lower()
        dealer_active = bool(user_doc.get("dealer_subscription_active"))
        if dealer_status == "active" and dealer_active:
            return True

    # (3) Broker with active subscription
    if account_type == "broker" and status == "active":
        return True

    # (4) Verified storage facility with active subscription
    if account_type == "storage_facility":
        if user_doc.get("facility_verified") is True and status == "active":
            return True

    # (5) Admin escape (always allowed — for platform ops)
    if (user_doc.get("role") or "").lower() in ADMIN_ROLES:
        return True

    return False


async def _require_mcp_access(db, user: User) -> Dict[str, Any]:
    """Load the full user document and enforce the subscription gate.

    Raises 402 with a bilingual message when the user isn't eligible.
    Returns the raw user_doc for reuse by downstream verification checks.
    """
    user_doc = await db.users.find_one({"id": user.id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail={"error": "USER_NOT_FOUND"})
    if not _subscription_active(user_doc):
        raise HTTPException(status_code=402, detail={
            "error":      "SUBSCRIPTION_REQUIRED",
            "message_en": (
                "The BidVex MCP service is available only to Premium, VIP, "
                "Partner Pro, Vehicle Dealer, Broker, or verified Storage "
                "Facility accounts with an active annual subscription."
            ),
            "message_fr": (
                "Le service MCP BidVex est réservé aux comptes Premium, VIP, "
                "Partner Pro, Concessionnaire automobile, Courtier ou "
                "Établissement d'entreposage vérifié avec un abonnement "
                "annuel actif."
            ),
            "upgrade_url": "/pricing",
        })
    return user_doc


async def _require_verification(
    db,
    user: User,
    user_doc: Dict[str, Any],
    *,
    action: str = "bid",
    require_tax_id: bool = False,
) -> None:
    """Enforce the mandatory verification pillars.

    * Phone + payment method + T&C — reuses `trust_gate.require_trust_verified`
      so the exact same rules that gate the REST bid endpoint apply here.
    * `require_tax_id=True` additionally enforces the vertical-appropriate
      tax-verification signal per user's option-(b) policy:
        - Vehicle dealer  → dealer_license_verified=True
        - Storage facility → facility_verified=True
        - Broker / business → admin_verified=True
      plus `tax_id` field non-empty in all cases.
    """
    from services.trust_gate import require_trust_verified  # local import — matches existing pattern
    # Phone + payment method + T&C (raises 403 trust_required on failure)
    await require_trust_verified(db, user, action=action)

    if not require_tax_id:
        return

    tax_id = (user_doc.get("tax_id") or "").strip()
    if not tax_id:
        raise HTTPException(status_code=403, detail={
            "error":      "TAX_ID_REQUIRED",
            "message_en": (
                "This action requires a verified Seller Tax ID (GST/QST) on "
                "your BidVex account before it can be used."
            ),
            "message_fr": (
                "Cette action nécessite un numéro fiscal du vendeur "
                "(TPS/TVQ) vérifié sur votre compte BidVex."
            ),
        })

    # Vertical-specific verification signal
    account_type = (user_doc.get("account_type") or "").lower()
    if user_doc.get("is_vehicle_dealer") is True:
        if not user_doc.get("dealer_license_verified"):
            raise HTTPException(status_code=403, detail={
                "error":      "TAX_ID_REQUIRED",
                "detail":     "dealer_license_not_verified",
                "message_en": "Your dealer licence must be verified by an admin before this action is allowed.",
                "message_fr": "Votre licence de concessionnaire doit être vérifiée par un administrateur avant cette action.",
            })
        return
    if account_type == "storage_facility":
        if not user_doc.get("facility_verified"):
            raise HTTPException(status_code=403, detail={
                "error":      "TAX_ID_REQUIRED",
                "detail":     "facility_not_verified",
                "message_en": "Your storage facility must be verified before this action is allowed.",
                "message_fr": "Votre entrepôt doit être vérifié avant cette action.",
            })
        return
    if account_type in ("broker", "business"):
        if not user_doc.get("admin_verified"):
            raise HTTPException(status_code=403, detail={
                "error":      "TAX_ID_REQUIRED",
                "detail":     "corporate_not_verified",
                "message_en": "Your corporate account must be admin-verified before this action is allowed.",
                "message_fr": "Votre compte d'entreprise doit être vérifié par un administrateur avant cette action.",
            })
        return
    # For personal accounts, having a tax_id is sufficient (rare but valid)


async def _require_admin_role(user_doc: Dict[str, Any]) -> None:
    if (user_doc.get("role") or "").lower() not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={
            "error":      "ADMIN_ONLY",
            "message_en": "This tool is restricted to admin/super_admin roles.",
            "message_fr": "Cet outil est réservé aux rôles administrateur.",
        })


# ─── Tool implementations — each is a self-contained async function ──
# All tools receive: (db, user, user_doc, params_dict). They return a
# plain-JSON-serializable dict. Any raised HTTPException is caught by
# the dispatcher and rendered as a `rejected` audit entry.

async def tool_get_listing_details(db, user, user_doc, params) -> Dict[str, Any]:
    listing_id = params.get("listing_id")
    if not listing_id:
        raise HTTPException(status_code=400, detail={"error": "listing_id required"})
    # Try marketplace / lots / vehicles / storage in that order.
    for coll_name, doc_type in (
        ("listings", "marketplace"),
        ("multi_item_listings", "lots"),
        ("vehicles", "vehicle"),
        ("storage_units", "storage"),
    ):
        doc = await db[coll_name].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            # Public projection — drop obviously private fields
            public = {k: v for k, v in doc.items() if not k.startswith("_") and k not in {
                "seller_stripe_customer_id", "internal_notes", "admin_notes",
            }}
            return {"vertical": doc_type, "listing": public}
    raise HTTPException(status_code=404, detail={"error": "listing_not_found"})


async def tool_search_auctions(db, user, user_doc, params) -> Dict[str, Any]:
    """Search active auctions across all four BidVex verticals.

    Reuses the same query shape the REST `GET /api/listings` endpoint
    uses (title/description regex, category, price range, currency).
    Returns per-vertical result groups so callers can decide how to
    render them.
    """
    q_text     = (params.get("query") or "").strip()
    category   = params.get("category")
    vertical   = (params.get("vertical") or "any").lower()
    min_price  = params.get("min_price")
    max_price  = params.get("max_price")
    status     = (params.get("status") or "active").lower()
    limit      = int(params.get("limit") or 20)
    limit      = max(1, min(100, limit))

    if vertical not in {"any", "marketplace", "lots", "vehicle", "storage"}:
        raise HTTPException(status_code=400, detail={
            "error": "vertical must be any|marketplace|lots|vehicle|storage",
        })

    # Reuse the existing helpers so regex injection is caught centrally.
    from services.sanitizer import sanitize_string, safe_regex

    base_query: Dict[str, Any] = {}
    if status != "any":
        base_query["status"] = status
    if category:
        base_query["category"] = category
    price_field_by_vertical = {
        "marketplace":       "current_price",
        "lots":              "current_price",
        "vehicle":           "current_bid",
        "storage":           "current_bid",
    }
    if q_text:
        try:
            q_text = sanitize_string(q_text)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid query text"})
        _safe = safe_regex(q_text)
        base_query["$or"] = [
            {"title":       {"$regex": _safe, "$options": "i"}},
            {"description": {"$regex": _safe, "$options": "i"}},
        ]

    def _with_price(coll_query: Dict[str, Any], price_field: str) -> Dict[str, Any]:
        q = dict(coll_query)
        if min_price is not None or max_price is not None:
            price_q: Dict[str, Any] = {}
            if min_price is not None:
                price_q["$gte"] = float(min_price)
            if max_price is not None:
                price_q["$lte"] = float(max_price)
            q[price_field] = price_q
        return q

    verticals_to_search = (
        ["marketplace", "lots", "vehicle", "storage"] if vertical == "any" else [vertical]
    )
    collections = {
        "marketplace": "listings",
        "lots":        "multi_item_listings",
        "vehicle":     "vehicles",
        "storage":     "storage_units",
    }
    projection = {
        "_id": 0, "id": 1, "title": 1, "category": 1, "current_price": 1,
        "current_bid": 1, "starting_bid": 1, "starting_price": 1,
        "auction_end_date": 1, "lot_end_time": 1, "status": 1,
        "images": 1, "vertical": 1, "seller_id": 1,
    }

    groups: Dict[str, List[Dict[str, Any]]] = {}
    total = 0
    per_group_limit = max(1, limit // max(1, len(verticals_to_search)))
    for v in verticals_to_search:
        coll = collections[v]
        q = _with_price(base_query, price_field_by_vertical[v])
        try:
            rows = await db[coll].find(q, projection).sort("created_at", -1).limit(per_group_limit).to_list(per_group_limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[mcp] search_auctions on {coll} failed: {type(exc).__name__}")
            rows = []
        # Add vertical tag for callers
        for r in rows:
            r["_vertical"] = v
        groups[v] = rows
        total += len(rows)

    return {
        "query":    q_text,
        "vertical": vertical,
        "total":    total,
        "limit":    limit,
        "results":  groups,
    }


async def tool_place_bid(db, user, user_doc, params, *, jwt: str) -> Dict[str, Any]:
    listing_id = params.get("listing_id")
    bid_amount = params.get("bid_amount")
    user_max_ceiling = params.get("user_max_ceiling")
    if not listing_id or bid_amount is None:
        raise HTTPException(status_code=400, detail={"error": "listing_id and bid_amount required"})

    # 1) Trust gate (phone + payment method + T&C) — no bypass
    await _require_verification(db, user, user_doc, action="bid", require_tax_id=False)

    # 2) Clamp check — REJECT (do NOT silently cap)
    try:
        bid_amount = float(bid_amount)
        if user_max_ceiling is not None:
            user_max_ceiling = float(user_max_ceiling)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"error": "bid_amount and user_max_ceiling must be numeric"})
    if user_max_ceiling is not None and bid_amount > user_max_ceiling:
        raise HTTPException(status_code=400, detail={
            "error":      "BID_EXCEEDS_MAX_CEILING",
            "bid_amount": bid_amount,
            "ceiling":    user_max_ceiling,
            "message_en": (
                f"Requested bid ${bid_amount:.2f} exceeds your declared "
                f"ceiling of ${user_max_ceiling:.2f}. No bid was placed."
            ),
            "message_fr": (
                f"L'enchère demandée de {bid_amount:.2f} $ dépasse votre "
                f"plafond de {user_max_ceiling:.2f} $. Aucune enchère n'a été placée."
            ),
        })

    # 3) Route through the existing REST bid endpoint — HTTP loopback so
    # ALL business rules (snipe protection, minimum increment, deposit,
    # watchdog, notifications) run unchanged.
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{_LOOPBACK_BASE}/api/bids",
            headers={"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"},
            json={"listing_id": listing_id, "amount": bid_amount},
        )
    if r.status_code >= 400:
        # Bubble up the structured error from the underlying handler
        try:
            detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text
        except Exception:  # noqa: BLE001
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)

    result = r.json()
    return {"bid_status": "placed", "result": result}


async def tool_create_auction_draft(db, user, user_doc, params) -> Dict[str, Any]:
    """Create a draft listing in the requested vertical.

    This tool only creates a persistent `status="draft"` row — publishing
    remains an explicit action gated by the existing publish endpoints
    (which run watchdog moderation, fee calculation, and validation).
    """
    vertical = (params.get("vertical") or "").lower()
    raw = params.get("raw_input") or {}
    if vertical not in {"marketplace", "lots", "vehicle", "storage"}:
        raise HTTPException(status_code=400, detail={
            "error": "vertical must be one of: marketplace, lots, vehicle, storage",
        })
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail={"error": "raw_input must be an object"})

    # Corporate/seller tax-id verification required for listing actions.
    await _require_verification(db, user, user_doc, action="list", require_tax_id=True)

    now = datetime.now(timezone.utc).isoformat()
    listing_id = str(uuid.uuid4())
    common = {
        "id":          listing_id,
        "seller_id":   user.id,
        "status":      "draft",
        "created_at":  now,
        "updated_at":  now,
        "created_via": MCP_SOURCE_TAG,
    }
    # Merge caller-provided raw payload but never let the caller override
    # ownership / status / id.
    safe_raw = {k: v for k, v in raw.items() if k not in {"id", "seller_id", "status", "created_at", "created_via"}}
    doc = {**safe_raw, **common}
    if vertical == "marketplace":
        await db.listings.insert_one(doc)
    elif vertical == "lots":
        await db.multi_item_listings.insert_one(doc)
    elif vertical == "vehicle":
        await db.vehicles.insert_one(doc)
    elif vertical == "storage":
        await db.storage_units.insert_one(doc)
    return {"draft_id": listing_id, "vertical": vertical, "status": "draft"}


async def tool_bulk_create_listings(db, user, user_doc, params) -> Dict[str, Any]:
    """Create multiple drafts in one call. Each item may target a
    different vertical. Reuses the same single-draft creation path so
    ownership/audit invariants hold."""
    items = params.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail={"error": "items must be a non-empty list"})
    if len(items) > 500:
        raise HTTPException(status_code=400, detail={"error": "at most 500 items per call"})

    # Verify once, up front (avoids partial writes if the user isn't tax-verified).
    await _require_verification(db, user, user_doc, action="list", require_tax_id=True)

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        try:
            r = await tool_create_auction_draft(db, user, user_doc, item)
            results.append({"index": idx, "ok": True, "draft_id": r["draft_id"], "vertical": r["vertical"]})
        except HTTPException as e:
            results.append({"index": idx, "ok": False, "error": e.detail})
    return {"total": len(items), "created": sum(1 for r in results if r["ok"]), "results": results}


async def tool_check_bid_status(db, user, user_doc, params) -> Dict[str, Any]:
    listing_id = params.get("listing_id")
    target_user_id = params.get("user_id") or user.id
    if not listing_id:
        raise HTTPException(status_code=400, detail={"error": "listing_id required"})
    # Non-admin can only query their own bid standing
    if target_user_id != user.id and (user_doc.get("role") or "").lower() not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"error": "cannot query other user's bids"})

    # Try both single-listing and multi-lot collections
    all_bids = await db.bids.find(
        {"listing_id": listing_id}, {"_id": 0},
    ).sort("amount", -1).to_list(500)
    if not all_bids:
        # Try lot_bids for multi-item lots — caller may or may not have specified lot_number
        lot_no = params.get("lot_number")
        query: Dict[str, Any] = {"listing_id": listing_id}
        if lot_no is not None:
            query["lot_number"] = lot_no
        all_bids = await db.lot_bids.find(query, {"_id": 0}).sort("amount", -1).to_list(500)

    if not all_bids:
        return {"listing_id": listing_id, "status": "no_bids", "user_position": None}

    # Determine listing status (active vs ended) — cheap best-effort
    listing = (
        await db.listings.find_one({"id": listing_id}, {"_id": 0, "status": 1}) or
        await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0, "status": 1}) or
        {}
    )
    listing_status = (listing.get("status") or "unknown").lower()

    top_bidder = all_bids[0].get("bidder_id")
    user_bids = [b for b in all_bids if b.get("bidder_id") == target_user_id]
    if not user_bids:
        my_status = "not_participating"
        position: Optional[int] = None
    else:
        my_top = user_bids[0].get("amount")
        # Rank: 1-based index of this user's top bid among sorted amounts
        sorted_amounts = sorted({b.get("amount") for b in all_bids}, reverse=True)
        position = sorted_amounts.index(my_top) + 1 if my_top in sorted_amounts else None
        if listing_status in {"ended", "sold", "closed", "completed"}:
            my_status = "won" if top_bidder == target_user_id else "ended_outbid"
        else:
            my_status = "winning" if top_bidder == target_user_id else "outbid"

    return {
        "listing_id":     listing_id,
        "listing_status": listing_status,
        "total_bids":     len(all_bids),
        "user_position":  position,
        "status":         my_status,
    }


async def tool_publish_meta_ad_promotion(db, user, user_doc, params) -> Dict[str, Any]:
    listing_id = params.get("listing_id")
    budget_cap_cents = params.get("budget_cap_cents")
    duration_days = params.get("duration_days")
    if not listing_id or budget_cap_cents is None or duration_days is None:
        raise HTTPException(status_code=400, detail={
            "error": "listing_id, budget_cap_cents, and duration_days are required",
        })
    try:
        budget_cap_cents = int(budget_cap_cents)
        duration_days = int(duration_days)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"error": "budget_cap_cents and duration_days must be integers"})
    if budget_cap_cents <= 0 or budget_cap_cents > 100_000_00:  # hard $100k lifetime ceiling
        raise HTTPException(status_code=400, detail={"error": "budget_cap_cents out of range (1..10000000)"})
    if duration_days < 1 or duration_days > 30:
        raise HTTPException(status_code=400, detail={"error": "duration_days out of range (1..30)"})

    # Load the listing for the ad creative
    listing = (
        await db.listings.find_one({"id": listing_id}, {"_id": 0}) or
        await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    )
    if not listing:
        raise HTTPException(status_code=404, detail={"error": "listing_not_found"})
    if listing.get("seller_id") != user.id and (user_doc.get("role") or "").lower() not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"error": "not_your_listing"})

    # Meta Ads publishing is env-gated. Do NOT touch new billing accounts.
    from services.ads_publisher import meta_flag, publish_to_meta_sync
    flag = meta_flag()
    if not flag.get("enabled"):
        return {
            "status":       NOT_IMPLEMENTED_CODE,
            "reason":       "meta_ads_not_provisioned",
            "prerequisite": flag.get("prerequisite"),
            "missing_env":  flag.get("missing", []),
        }

    # Enforce the caller-supplied budget cap EXPLICITLY. Never inject a
    # daily budget derived from anywhere else. If Meta enforces per-day
    # min, we split the cap across the duration.
    daily_cents = max(100, budget_cap_cents // max(1, duration_days))
    campaign_doc = {
        "listing_id": listing_id,
        "image_url":  (listing.get("images") or [None])[0],
        "title":      listing.get("title") or listing.get("title_en"),
        "budget_cap_cents":     budget_cap_cents,
        "daily_budget_cents":   daily_cents,
        "duration_days":        duration_days,
        "created_by":           user.id,
        "created_via":          MCP_SOURCE_TAG,
    }
    try:
        # publish_to_meta_sync is sync (Facebook Business SDK). Run in a threadpool.
        import asyncio
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, publish_to_meta_sync, campaign_doc)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — surface without leaking internals
        logger.warning(f"[mcp] meta ads publish failed: {type(exc).__name__}")
        raise HTTPException(status_code=502, detail={"error": "meta_publish_failed"})

    return {
        "status":            "published",
        "campaign_id":       result.get("campaign_id") or result.get("meta_campaign_id"),
        "ad_id":             result.get("ad_id"),
        "budget_cap_cents":  budget_cap_cents,
        "duration_days":     duration_days,
    }


async def tool_generate_listing_video(db, user, user_doc, params) -> Dict[str, Any]:
    """STUB — Higgsfield integration is not provisioned in this codebase.

    Per iter485 instructions: return NOT_IMPLEMENTED and warn. Do NOT
    fabricate an integration, create new billing allocations, or spend
    beyond what's already provisioned.
    """
    listing_id = params.get("listing_id")
    logger.warning(f"[mcp] generate_listing_video called but Higgsfield integration is NOT provisioned (listing_id={listing_id})")
    return {
        "status":         NOT_IMPLEMENTED_CODE,
        "reason":         "higgsfield_not_provisioned",
        "message_en":     "Short-form video generation via Higgsfield is not currently provisioned on this BidVex environment. Contact platform ops to enable.",
        "message_fr":     "La génération de vidéos courtes via Higgsfield n'est pas configurée sur cet environnement BidVex. Contactez l'exploitation.",
        "listing_id":     listing_id,
    }


async def tool_get_bidding_advice(db, user, user_doc, params) -> Dict[str, Any]:
    listing_id = params.get("listing_id")
    if not listing_id:
        raise HTTPException(status_code=400, detail={"error": "listing_id required"})
    listing = (
        await db.listings.find_one({"id": listing_id}, {"_id": 0}) or
        await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    )
    if not listing:
        raise HTTPException(status_code=404, detail={"error": "listing_not_found"})

    from services.chat_listing_context import fetch_market_comparables
    comparables = await fetch_market_comparables(db, listing, limit=5)
    return {
        "listing_id":  listing_id,
        "listing_summary": {
            "title":         listing.get("title") or listing.get("title_en"),
            "category":      listing.get("category"),
            "current_bid":   listing.get("current_bid") or listing.get("current_price"),
            "status":        listing.get("status"),
        },
        "comparables": comparables,  # data only, no advice generated
        "note":        "This tool returns market data only. Advice generation is the caller's responsibility.",
    }


async def tool_analyze_seller_inventory(db, user, user_doc, params) -> Dict[str, Any]:
    seller_id = params.get("seller_id") or user.id
    if seller_id != user.id and (user_doc.get("role") or "").lower() not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"error": "cannot inspect other seller's inventory"})

    active: List[Dict[str, Any]] = []
    ended: List[Dict[str, Any]] = []
    for coll in ("listings", "multi_item_listings", "vehicles", "storage_units"):
        try:
            docs = await db[coll].find(
                {"seller_id": seller_id},
                {"_id": 0, "id": 1, "title": 1, "status": 1, "views": 1,
                 "impressions": 1, "current_bid": 1, "current_price": 1,
                 "hammer_price": 1, "final_price": 1, "created_at": 1,
                 "updated_at": 1, "closed_at": 1, "category": 1},
            ).to_list(2000)
        except Exception:  # noqa: BLE001
            docs = []
        for d in docs:
            s = (d.get("status") or "").lower()
            if s in {"ended", "sold", "closed", "completed"}:
                ended.append(d)
            elif s == "active":
                active.append(d)
    total_gmv = sum(
        float(d.get("hammer_price") or d.get("final_price") or 0.0)
        for d in ended
    )
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    stale = [
        d for d in active
        if (isinstance(d.get("created_at"), str) and d["created_at"] < stale_cutoff.isoformat())
        and float(d.get("current_bid") or d.get("current_price") or 0) == 0
    ]
    return {
        "seller_id":       seller_id,
        "active_count":    len(active),
        "ended_count":     len(ended),
        "total_gmv":       round(total_gmv, 2),
        "stale_active":    [{"id": d.get("id"), "title": d.get("title")} for d in stale[:20]],
        "categories":      sorted({(d.get("category") or "uncategorized") for d in active + ended})[:30],
    }


async def tool_detect_performance_bottlenecks(db, user, user_doc, params) -> Dict[str, Any]:
    """Read-only flag pass on the caller's listings.

    A listing is "under-performing" when it's active, older than 7 days,
    and has fewer views than 25% of the same-category median.
    """
    seller_id = params.get("seller_id") or user.id
    listing_id = params.get("listing_id")
    if seller_id and seller_id != user.id and (user_doc.get("role") or "").lower() not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"error": "cannot inspect other seller's listings"})

    query: Dict[str, Any] = {"status": "active"}
    if listing_id:
        query["id"] = listing_id
    elif seller_id:
        query["seller_id"] = seller_id
    active = await db.listings.find(query, {
        "_id": 0, "id": 1, "title": 1, "category": 1, "views": 1,
        "current_bid": 1, "current_price": 1, "created_at": 1,
    }).to_list(500)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    flagged: List[Dict[str, Any]] = []
    for l in active:
        cat = l.get("category")
        peers = await db.listings.find(
            {"category": cat, "status": "active", "id": {"$ne": l["id"]}},
            {"_id": 0, "views": 1},
        ).to_list(500) if cat else []
        views = int(l.get("views") or 0)
        peer_views = sorted([int(p.get("views") or 0) for p in peers])
        median = peer_views[len(peer_views) // 2] if peer_views else 0
        if isinstance(l.get("created_at"), str) and l["created_at"] < cutoff and views < max(1, median // 4):
            flagged.append({
                "id":       l["id"],
                "title":    l.get("title"),
                "views":    views,
                "peer_median_views": median,
                "reason":   "low_views_vs_peers",
            })
    return {"scanned": len(active), "flagged_count": len(flagged), "flagged": flagged[:50]}


async def tool_identify_top_sellers(db, user, user_doc, params) -> Dict[str, Any]:
    await _require_admin_role(user_doc)  # admin-only per spec
    # Vertical / timeframe accepted but ignored for now — the existing
    # helper is all-time cross-vertical; we surface it as-is.
    limit = int(params.get("limit") or 5)
    from services.top_sellers import compute_top_sellers
    ranked = await compute_top_sellers(db, limit=min(50, max(1, limit)))
    return {"top_sellers": [{"seller_id": sid, "gmv": gmv} for sid, gmv in ranked]}


async def tool_b2b_syndication_matchmaker(db, user, user_doc, params) -> Dict[str, Any]:
    """
    /*
    TARGET INTENT (Phase 2 Build):
    Proactive B2B matchmaking workflow that ingests raw/chaotic seller
    inventory manifests or bulk items, parses and clusters the inventory,
    matches items against registered buyer preferences (vehicle dealers,
    brokers, storage facilities, corporate liquidators), and automatically
    generates targeted, bilingual (EN/FR) syndication campaigns to bridge
    buyers and sellers.
    */

    STUB — deliberately not implemented in this pass. Returns
    NOT_IMPLEMENTED per iter485 instructions; no fabricated integration.
    """
    seller_id = params.get("seller_id")
    logger.warning(f"[mcp] B2B_syndication_matchmaker called (seller_id={seller_id}) — stub returning NOT_IMPLEMENTED")
    return {
        "status":       NOT_IMPLEMENTED_CODE,
        "reason":       "b2b_matchmaker_phase_2",
        "message_en":   "The B2B syndication matchmaker is planned for a Phase 2 build and is not available yet.",
        "message_fr":   "Le service de mise en relation B2B est prévu pour la phase 2 et n'est pas encore disponible.",
        "seller_id":    seller_id,
    }


# ─── Tool registry + input schemas ───────────────────────────────────
class ToolSpec(BaseModel):
    name: str
    description_en: str
    description_fr: str
    input_schema: Dict[str, Any]
    admin_only: bool = False
    requires_tax_id: bool = False


TOOL_REGISTRY: Dict[str, ToolSpec] = {
    "get_listing_details": ToolSpec(
        name="get_listing_details",
        description_en="Return the full public listing document across all four verticals (marketplace, lots, vehicle, storage).",
        description_fr="Retourne le document public complet d'une annonce dans les quatre verticales.",
        input_schema={"type": "object", "properties": {"listing_id": {"type": "string"}}, "required": ["listing_id"]},
    ),
    "search_auctions": ToolSpec(
        name="search_auctions",
        description_en="Search active BidVex auctions across all four verticals (marketplace, lots, vehicles, storage). Use `vertical` to scope the search; omit or pass 'any' to search all verticals.",
        description_fr="Rechercher des enchères actives BidVex dans les quatre verticales (marché, lots, véhicules, entreposage).",
        input_schema={
            "type": "object",
            "properties": {
                "query":     {"type": "string",  "description": "Free-text search on title/description (regex-escaped server-side)."},
                "vertical":  {"type": "string",  "enum": ["any", "marketplace", "lots", "vehicle", "storage"], "default": "any"},
                "category":  {"type": "string"},
                "min_price": {"type": "number"},
                "max_price": {"type": "number"},
                "status":    {"type": "string",  "enum": ["active", "ended", "any"], "default": "active"},
                "limit":     {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
    ),
    "place_bid": ToolSpec(
        name="place_bid",
        description_en="Place a bid on a listing after clamp+ceiling checks; routes through the existing bid handler (snipe protection, minimum increment, deposit rules unchanged).",
        description_fr="Placer une enchère après vérification du plafond; passe par le gestionnaire d'enchères existant sans modifier les règles.",
        input_schema={
            "type": "object",
            "properties": {
                "listing_id":       {"type": "string"},
                "bid_amount":       {"type": "number"},
                "user_max_ceiling": {"type": "number", "description": "Hard ceiling; the tool REJECTS if bid_amount > ceiling."},
            },
            "required": ["listing_id", "bid_amount"],
        },
    ),
    "create_auction_draft": ToolSpec(
        name="create_auction_draft",
        description_en="Create a draft listing (status='draft') in the requested vertical. Publishing remains an explicit separate action.",
        description_fr="Créer un brouillon d'annonce (status='draft') dans la verticale demandée. La publication reste une action distincte.",
        input_schema={
            "type": "object",
            "properties": {
                "vertical":  {"type": "string", "enum": ["marketplace", "lots", "vehicle", "storage"]},
                "raw_input": {"type": "object"},
            },
            "required": ["vertical", "raw_input"],
        },
        requires_tax_id=True,
    ),
    "bulk_create_listings": ToolSpec(
        name="bulk_create_listings",
        description_en="Create up to 500 drafts in a single call. Each item must include `vertical` and `raw_input`.",
        description_fr="Créer jusqu'à 500 brouillons en un seul appel.",
        input_schema={
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"type": "object"}}},
            "required": ["items"],
        },
        requires_tax_id=True,
    ),
    "check_bid_status": ToolSpec(
        name="check_bid_status",
        description_en="Return the caller's bid standing on a listing (winning/outbid/won/ended/no_bids + position).",
        description_fr="Retourne la position du demandeur pour une annonce.",
        input_schema={
            "type": "object",
            "properties": {"listing_id": {"type": "string"}, "user_id": {"type": "string"}, "lot_number": {"type": "integer"}},
            "required": ["listing_id"],
        },
    ),
    "publish_meta_ad_promotion": ToolSpec(
        name="publish_meta_ad_promotion",
        description_en="Promote a listing on Meta Ads with a hard budget cap. Returns NOT_IMPLEMENTED when Meta Ads env is not provisioned.",
        description_fr="Promouvoir une annonce sur Meta Ads avec un plafond budgétaire strict.",
        input_schema={
            "type": "object",
            "properties": {
                "listing_id":       {"type": "string"},
                "budget_cap_cents": {"type": "integer", "minimum": 1, "maximum": 10_000_000},
                "duration_days":    {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "required": ["listing_id", "budget_cap_cents", "duration_days"],
        },
    ),
    "generate_listing_video": ToolSpec(
        name="generate_listing_video",
        description_en="Trigger short-form video generation for a listing via Higgsfield. STUB — returns NOT_IMPLEMENTED (Higgsfield not provisioned).",
        description_fr="Générer une vidéo courte via Higgsfield. STUB — retourne NOT_IMPLEMENTED.",
        input_schema={"type": "object", "properties": {"listing_id": {"type": "string"}}, "required": ["listing_id"]},
    ),
    "get_bidding_advice": ToolSpec(
        name="get_bidding_advice",
        description_en="Return comparable/market data (same-category recent sold + active listings). Data only — no LLM advice.",
        description_fr="Retourne des données comparables (annonces similaires récemment vendues et actives). Données seulement.",
        input_schema={"type": "object", "properties": {"listing_id": {"type": "string"}}, "required": ["listing_id"]},
    ),
    "analyze_seller_inventory": ToolSpec(
        name="analyze_seller_inventory",
        description_en="Aggregate a seller's active/ended listings: GMV, categories, stale actives. Caller must be the seller or an admin.",
        description_fr="Agrège les annonces actives/terminées d'un vendeur.",
        input_schema={"type": "object", "properties": {"seller_id": {"type": "string"}}},
    ),
    "detect_performance_bottlenecks": ToolSpec(
        name="detect_performance_bottlenecks",
        description_en="Flag active listings under-performing vs same-category median views. Read-only.",
        description_fr="Signale les annonces sous-performantes par rapport à la médiane de leur catégorie.",
        input_schema={"type": "object", "properties": {"seller_id": {"type": "string"}, "listing_id": {"type": "string"}}},
    ),
    "identify_top_sellers": ToolSpec(
        name="identify_top_sellers",
        description_en="Top sellers by all-time GMV (excludes demo data). Admin-only.",
        description_fr="Top vendeurs par PMV cumulé (données de démo exclues). Admin seulement.",
        input_schema={"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}},
        admin_only=True,
    ),
    "B2B_syndication_matchmaker": ToolSpec(
        name="B2B_syndication_matchmaker",
        description_en="Proactive B2B matchmaking. STUB — returns NOT_IMPLEMENTED; see Phase 2 intent comment in code.",
        description_fr="Mise en relation B2B proactive. STUB — retourne NOT_IMPLEMENTED.",
        input_schema={
            "type": "object",
            "properties": {"seller_id": {"type": "string"}, "manifest_raw_data": {"type": "object"}},
            "required": ["seller_id"],
        },
    ),
}


# Handler dispatch table
_HANDLERS: Dict[str, Callable[..., Any]] = {
    "get_listing_details":            tool_get_listing_details,
    "search_auctions":                tool_search_auctions,
    "place_bid":                      tool_place_bid,
    "create_auction_draft":           tool_create_auction_draft,
    "bulk_create_listings":           tool_bulk_create_listings,
    "check_bid_status":               tool_check_bid_status,
    "publish_meta_ad_promotion":      tool_publish_meta_ad_promotion,
    "generate_listing_video":         tool_generate_listing_video,
    "get_bidding_advice":             tool_get_bidding_advice,
    "analyze_seller_inventory":       tool_analyze_seller_inventory,
    "detect_performance_bottlenecks": tool_detect_performance_bottlenecks,
    "identify_top_sellers":           tool_identify_top_sellers,
    "B2B_syndication_matchmaker":     tool_b2b_syndication_matchmaker,
}


# ─── HTTP endpoints ──────────────────────────────────────────────────
class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


@mcp_router.get("/health")
async def mcp_health() -> Dict[str, Any]:
    """Public health probe — does NOT reveal internal config."""
    return {"status": "ok", "protocol": "mcp-http", "tool_count": len(TOOL_REGISTRY)}


@mcp_router.post("/tools/list")
async def mcp_tools_list(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the tool catalogue. Requires auth + active subscription."""
    db = get_db()
    user_doc = await _require_mcp_access(db, current_user)
    is_admin = (user_doc.get("role") or "").lower() in ADMIN_ROLES
    tools = []
    for spec in TOOL_REGISTRY.values():
        if spec.admin_only and not is_admin:
            continue
        tools.append(spec.dict())
    return {"tools": tools, "user_id": current_user.id}


@mcp_router.post("/tools/call")
async def mcp_tools_call(
    request: Request,
    body: ToolCallRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Dispatch a single tool call. Enforces:
      1. Subscription gate (SUBSCRIPTION_REQUIRED)
      2. Per-user rate limit (429)
      3. Admin-only tools (ADMIN_ONLY)
      4. Verification gate (delegated to each tool)
      5. Audit logging on every branch (success/failure/rejected)
    """
    started_ms = time.time()
    db = get_db()
    tool_name = body.name
    args = body.arguments or {}

    # 1) Subscription gate FIRST — cheapest audit-worthy path.
    try:
        user_doc = await _require_mcp_access(db, current_user)
    except HTTPException as e:
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="rejected",
                           error_code=str((e.detail or {}).get("error") if isinstance(e.detail, dict) else "SUBSCRIPTION_REQUIRED"),
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise

    # 2) Rate limit — per JWT subject
    allowed, remaining, rl_backend = await _rate_limit_check(current_user.id)
    if not allowed:
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="rejected",
                           error_code="RATE_LIMIT_EXCEEDED",
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise HTTPException(status_code=429, detail={
            "error":            "RATE_LIMIT_EXCEEDED",
            "limit_per_minute": _RATE_LIMIT_PER_MIN,
            "retry_after_s":    _RATE_WINDOW_S,
            "backend":          rl_backend,
            "message_en":       "Too many MCP tool calls. Please slow down.",
            "message_fr":       "Trop d'appels d'outils MCP. Veuillez ralentir.",
        })

    # 3) Tool exists?
    spec = TOOL_REGISTRY.get(tool_name)
    handler = _HANDLERS.get(tool_name)
    if not spec or not handler:
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="rejected",
                           error_code="UNKNOWN_TOOL",
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise HTTPException(status_code=404, detail={"error": "UNKNOWN_TOOL", "tool": tool_name})

    # 4) Admin-only enforcement
    if spec.admin_only:
        try:
            await _require_admin_role(user_doc)
        except HTTPException as e:
            await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                               input_params=args, result_status="rejected",
                               error_code="ADMIN_ONLY",
                               latency_ms=int((time.time() - started_ms) * 1000))
            raise

    # 5) Dispatch — forward JWT for tools that need HTTP loopback.
    jwt_token: Optional[str] = None
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        jwt_token = auth_header.split(" ", 1)[1]
    elif "session_token" in request.cookies:
        jwt_token = request.cookies["session_token"]

    try:
        sig = inspect.signature(handler)
        kwargs = {}
        if "jwt" in sig.parameters:
            if not jwt_token:
                raise HTTPException(status_code=401, detail={"error": "MISSING_JWT"})
            kwargs["jwt"] = jwt_token
        result = await handler(db, current_user, user_doc, args, **kwargs)
        latency_ms = int((time.time() - started_ms) * 1000)
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="success",
                           latency_ms=latency_ms)
        return {
            "tool":              tool_name,
            "result":            result,
            "rate_limit_remaining": remaining,
        }
    except HTTPException as e:
        # Structured audit — do not include the raw exception message,
        # only its short error_code so secrets never leak into logs.
        code = "HTTP_ERROR"
        if isinstance(e.detail, dict):
            code = str(e.detail.get("error") or code)
        elif isinstance(e.detail, str):
            code = e.detail[:80]
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args,
                           result_status="failure" if e.status_code >= 500 else "rejected",
                           error_code=code,
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise
    except Exception as exc:  # noqa: BLE001 — no unstructured leakage
        # Deliberately do NOT include str(exc) in the client response.
        logger.exception(f"[mcp] unhandled error in tool={tool_name} for user={current_user.id}")
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="failure",
                           error_code=type(exc).__name__,
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR"})


__all__ = ["mcp_router", "TOOL_REGISTRY", "MCP_AUDIT_COLLECTION"]


# ══════════════════════════════════════════════════════════════════════
# JSON-RPC 2.0 dispatch (Claude Desktop / mcp-remote / stdio bridge)
# ══════════════════════════════════════════════════════════════════════
#
# Every non-legacy transport funnels through `_dispatch_jsonrpc` which
# implements the MCP methods Claude Desktop actually calls:
#
#   • initialize                — handshake, returns serverInfo+capabilities
#   • notifications/initialized — client-side ack; response must be omitted
#   • ping                      — keep-alive
#   • tools/list                — returns TOOL_REGISTRY as MCP tool schemas
#   • tools/call                — dispatches into _HANDLERS with all gates
#
# The dispatch function does NOT create a FastAPI Response — callers
# decide how to write the reply (HTTP response body / SSE frame / stdout
# line).
#

class _JSONRPCError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def _rpc_ok(rpc_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _rpc_err(rpc_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": err}


def _tool_registry_as_mcp(is_admin: bool) -> List[Dict[str, Any]]:
    """Render TOOL_REGISTRY in the exact shape MCP clients expect
    (`inputSchema`, not `input_schema`; single English `description`)."""
    out = []
    for spec in TOOL_REGISTRY.values():
        if spec.admin_only and not is_admin:
            continue
        out.append({
            "name":        spec.name,
            "description": spec.description_en,
            "inputSchema": spec.input_schema,
        })
    return out


async def _rpc_run_tool(
    db, current_user: User, tool_name: str, args: Dict[str, Any], jwt_token: Optional[str],
) -> Dict[str, Any]:
    """Reimplements the exact same gate order as the legacy REST
    `tools/call` endpoint, but returns raw handler output (or raises
    HTTPException) instead of assembling a Response.

    Keeps the audit + gate order identical so callers get the same
    security surface regardless of transport.
    """
    started_ms = time.time()
    args = args or {}

    # (1) Subscription gate
    try:
        user_doc = await _require_mcp_access(db, current_user)
    except HTTPException as e:
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="rejected",
                           error_code=(e.detail or {}).get("error") if isinstance(e.detail, dict) else "SUBSCRIPTION_REQUIRED",
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise

    # (2) Rate limit
    allowed, remaining, rl_backend = await _rate_limit_check(current_user.id)
    if not allowed:
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="rejected",
                           error_code="RATE_LIMIT_EXCEEDED",
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise HTTPException(status_code=429, detail={
            "error":            "RATE_LIMIT_EXCEEDED",
            "limit_per_minute": _RATE_LIMIT_PER_MIN,
            "retry_after_s":    _RATE_WINDOW_S,
            "backend":          rl_backend,
        })

    # (3) Tool exists?
    spec = TOOL_REGISTRY.get(tool_name)
    handler = _HANDLERS.get(tool_name)
    if not spec or not handler:
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="rejected",
                           error_code="UNKNOWN_TOOL",
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise HTTPException(status_code=404, detail={"error": "UNKNOWN_TOOL", "tool": tool_name})

    # (4) Admin-only
    if spec.admin_only:
        try:
            await _require_admin_role(user_doc)
        except HTTPException as e:
            await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                               input_params=args, result_status="rejected",
                               error_code="ADMIN_ONLY",
                               latency_ms=int((time.time() - started_ms) * 1000))
            raise

    # (5) Dispatch
    try:
        sig = inspect.signature(handler)
        kwargs = {}
        if "jwt" in sig.parameters:
            if not jwt_token:
                raise HTTPException(status_code=401, detail={"error": "MISSING_JWT"})
            kwargs["jwt"] = jwt_token
        result = await handler(db, current_user, user_doc, args, **kwargs)
        latency_ms = int((time.time() - started_ms) * 1000)
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args, result_status="success",
                           latency_ms=latency_ms)
        return {"result": result, "rate_limit_remaining": remaining}
    except HTTPException as e:
        code = "HTTP_ERROR"
        if isinstance(e.detail, dict):
            code = str(e.detail.get("error") or code)
        elif isinstance(e.detail, str):
            code = e.detail[:80]
        await _write_audit(db, user_id=current_user.id, tool_name=tool_name,
                           input_params=args,
                           result_status="failure" if e.status_code >= 500 else "rejected",
                           error_code=code,
                           latency_ms=int((time.time() - started_ms) * 1000))
        raise


async def _dispatch_jsonrpc(
    db, current_user: User, msg: Dict[str, Any], *, jwt_token: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Dispatch a single JSON-RPC 2.0 message. Returns None for
    notifications (per spec — notifications get no response)."""
    method = msg.get("method")
    rpc_id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return _rpc_ok(rpc_id, {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities":    {"tools": {"listChanged": False}, "logging": {}},
            "serverInfo":      MCP_SERVER_INFO,
            "instructions":    (
                "BidVex MCP server. Auth: pass the caller's BidVex JWT via the "
                "Authorization header on the transport (already handled by the "
                "bridge). All tool calls are subject to subscription gate, "
                "trust gate, per-user rate limit, and audit logging."
            ),
        })
    if method == "notifications/initialized":
        return None  # spec: server MUST NOT respond
    if method == "ping":
        return _rpc_ok(rpc_id, {})
    if method == "tools/list":
        # Subscription gate check — same as the REST endpoint
        try:
            user_doc = await _require_mcp_access(db, current_user)
        except HTTPException as e:
            code = -32001
            detail = e.detail if isinstance(e.detail, dict) else {"error": str(e.detail)}
            return _rpc_err(rpc_id, code, "SUBSCRIPTION_REQUIRED", detail)
        is_admin = (user_doc.get("role") or "").lower() in ADMIN_ROLES
        return _rpc_ok(rpc_id, {"tools": _tool_registry_as_mcp(is_admin)})
    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments") or {}
        if not tool_name:
            return _rpc_err(rpc_id, -32602, "missing tool name")
        try:
            out = await _rpc_run_tool(db, current_user, tool_name, args, jwt_token)
            # MCP tools/call result shape: {"content":[{"type":"text","text":...}], "isError": false}
            payload_text = json.dumps(out["result"], default=str)
            return _rpc_ok(rpc_id, {
                "content":  [{"type": "text", "text": payload_text}],
                "isError":  False,
                "structuredContent": out["result"],
                "_meta":    {"rate_limit_remaining": out["rate_limit_remaining"]},
            })
        except HTTPException as e:
            # Map to MCP tool-call error shape: isError=true + content
            err_text = json.dumps(e.detail if isinstance(e.detail, dict) else {"error": str(e.detail)}, default=str)
            return _rpc_ok(rpc_id, {
                "content": [{"type": "text", "text": err_text}],
                "isError": True,
                "_meta":   {"http_status": e.status_code},
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[mcp] tools/call unhandled: {tool_name}")
            return _rpc_err(rpc_id, -32603, "INTERNAL_ERROR", {"type": type(exc).__name__})
    # Unknown method
    return _rpc_err(rpc_id, -32601, f"method not found: {method}")


@mcp_router.post("/rpc")
async def mcp_jsonrpc(
    request: Request,
    body: Dict[str, Any],
    current_user: User = Depends(get_current_user),
) -> Any:
    """MCP JSON-RPC 2.0 dispatch endpoint. Accepts a single message or a
    batch (array); returns matching response (or nothing for pure-
    notification batches)."""
    db = get_db()
    jwt_token = None
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        jwt_token = auth.split(" ", 1)[1]

    if isinstance(body, list):
        # Batch — dispatch in-order, drop notification (None) responses
        responses = []
        for msg in body:
            if not isinstance(msg, dict):
                responses.append(_rpc_err(None, -32600, "invalid Request"))
                continue
            r = await _dispatch_jsonrpc(db, current_user, msg, jwt_token=jwt_token)
            if r is not None:
                responses.append(r)
        return responses
    if not isinstance(body, dict):
        return _rpc_err(None, -32600, "invalid Request")

    r = await _dispatch_jsonrpc(db, current_user, body, jwt_token=jwt_token)
    if r is None:
        # Notification — return HTTP 202 with empty body per spec
        from fastapi.responses import Response as _Resp
        return _Resp(status_code=202)
    return r


# ══════════════════════════════════════════════════════════════════════
# HTTP-SSE transport (Claude Web / mcp-remote / other remote clients)
# ══════════════════════════════════════════════════════════════════════
# Session lifecycle:
#   1. Client opens `GET /api/mcp/sse` (with auth header).
#   2. Server allocates a session, sends `event: endpoint\ndata: <post-url>`
#      containing `POST /api/mcp/sse/messages?sid=<id>`.
#   3. Client POSTs JSON-RPC messages to that URL.
#   4. Server writes JSON-RPC responses back onto the SSE stream as
#      `event: message\ndata: <json>` frames.
#   5. Client disconnects → server tears down the session.
_SSE_SESSIONS: Dict[str, Dict[str, Any]] = {}
_SSE_SESSION_TTL_S = 60 * 30  # 30 minutes


async def _sse_session_gc():
    """Sweep expired sessions once per minute."""
    now = time.time()
    stale = [sid for sid, s in _SSE_SESSIONS.items() if s["expires_at"] < now]
    for sid in stale:
        try:
            _SSE_SESSIONS.pop(sid, None)
        except Exception:  # noqa: BLE001
            pass


@mcp_router.get("/sse")
async def mcp_sse_stream(
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> StreamingResponse:
    """Open an SSE stream. First event announces the message-post URL."""
    db = get_db()
    # Enforce subscription gate before opening the stream
    await _require_mcp_access(db, current_user)

    await _sse_session_gc()
    sid = uuid.uuid4().hex
    q: asyncio.Queue[str] = asyncio.Queue()
    jwt_token: Optional[str] = None
    if request is not None:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            jwt_token = auth.split(" ", 1)[1]
    _SSE_SESSIONS[sid] = {
        "user_id":    current_user.id,
        "queue":      q,
        "jwt":        jwt_token,
        "expires_at": time.time() + _SSE_SESSION_TTL_S,
    }
    logger.info(f"[mcp] SSE session opened sid={sid} user={current_user.id}")

    async def _stream() -> AsyncIterator[bytes]:
        # First event — advertise the POST endpoint (per MCP HTTP-SSE spec)
        post_url = f"/api/mcp/sse/messages?sid={sid}"
        yield f"event: endpoint\ndata: {post_url}\n\n".encode()
        try:
            while True:
                # Heartbeat every 15s to keep intermediaries alive
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield b": keep-alive\n\n"
                    continue
                if item == "__CLOSE__":
                    break
                yield f"event: message\ndata: {item}\n\n".encode()
        finally:
            _SSE_SESSIONS.pop(sid, None)
            logger.info(f"[mcp] SSE session closed sid={sid}")

    return StreamingResponse(_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-store",
        "Connection":    "keep-alive",
        "X-Accel-Buffering": "no",
    })


@mcp_router.post("/sse/messages")
async def mcp_sse_message(
    request: Request,
    body: Dict[str, Any],
    sid: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Client → server JSON-RPC message. Response is queued onto the
    matching SSE stream. HTTP body is 202 (message accepted)."""
    session = _SSE_SESSIONS.get(sid)
    if not session or session["user_id"] != current_user.id:
        raise HTTPException(status_code=404, detail={"error": "SSE_SESSION_NOT_FOUND"})
    session["expires_at"] = time.time() + _SSE_SESSION_TTL_S

    db = get_db()
    jwt_token = session.get("jwt")
    r = await _dispatch_jsonrpc(db, current_user, body, jwt_token=jwt_token)
    if r is not None:
        await session["queue"].put(json.dumps(r, default=str))
    from fastapi.responses import Response as _Resp
    return _Resp(status_code=202)
