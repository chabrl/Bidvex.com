"""
iter488 — Scoped MCP Token System.

Additive endpoints for user-managed MCP tokens. These tokens are an
authentication alternative to normal session JWTs when connecting Claude
Desktop (or any MCP client) to BidVex — the user never has to expose
their session JWT.

Security model:
  * Raw token is generated with `secrets.token_urlsafe(32)` (≥ 256 bits of
    entropy) and returned to the caller EXACTLY ONCE at creation time.
  * Only the bcrypt hash of the raw secret is persisted.
  * `token_id` is a non-secret short hex identifier used purely to
    locate the token record (bcrypt hashes are salted so we cannot query
    by hash).
  * `scopes` are validated against an allowlist. Users can never
    self-grant `admin` — admin privileges continue to flow from the
    existing role-based gates in the MCP server.
  * Token permissions are the INTERSECTION of the requested scopes and
    what the user's existing BidVex authorization allows. A token can
    restrict access, never elevate it.
  * Revocation is immediate; `revoked=True` is checked on every use.
  * Expiration is enforced on every use.
  * Existing session-JWT auth remains completely unaffected.

Endpoints:
  * POST   /api/mcp/token              — generate a new scoped MCP token
  * GET    /api/mcp/tokens             — list caller's tokens (metadata only)
  * DELETE /api/mcp/token/{token_id}   — revoke a token
"""
from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from deps import User, get_current_user, get_db

logger = logging.getLogger("bidvex.mcp_tokens")

# Router is mounted UNDER /api/mcp/* via server.py's api_router
# (same prefix as the MCP server, but a separate module).
mcp_tokens_router = APIRouter(prefix="/mcp", tags=["MCP Tokens"])

MCP_TOKENS_COLLECTION = "mcp_tokens"

# Non-secret prefix on the raw token surface. Lets the resolver in
# `mcp_server.py` decide whether an `Authorization: Bearer …` header is
# an MCP token or a JWT by simple string match. No bearing on security.
RAW_TOKEN_PREFIX = "bvx_mcp_"

# Allowlist of user-grantable scopes. Kept intentionally coarse so
# Claude prompts stay readable and permission modelling matches the
# capability areas users think in. Admin capability is deliberately
# absent — it comes exclusively from the existing role-based gates.
ALLOWED_SCOPES: List[str] = ["read", "bid", "list", "promote", "analytics", "matchmaker"]

# Expiration guardrails
MIN_EXPIRATION_DAYS = 1
MAX_EXPIRATION_DAYS = 365
DEFAULT_EXPIRATION_DAYS = 90

# Bcrypt work factor. Keep low enough for interactive latency, high
# enough that offline brute-force on a leaked hash is impractical.
_BCRYPT_ROUNDS = 12

_LABEL_RE = re.compile(r"^[A-Za-z0-9 _.\-]{1,64}$")
_TOKEN_ID_RE = re.compile(r"^[a-f0-9]{16}$")  # 8-byte hex identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mint_raw_token(token_id: str) -> tuple[str, bytes, str]:
    """Return `(raw_token, bcrypt_hash, secret_only)`.

    The raw token surfaced to the user is `{PREFIX}{token_id}_{secret}`.
    We bcrypt the `secret` part; the `token_id` is non-secret and used
    solely to locate the record.
    """
    secret = secrets.token_urlsafe(32)  # ≥ 256 bits of entropy
    raw = f"{RAW_TOKEN_PREFIX}{token_id}_{secret}"
    bh = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return raw, bh, secret


def parse_raw_token(raw: str) -> Optional[tuple[str, str]]:
    """Parse a raw MCP token into `(token_id, secret)`.

    Returns None if the format doesn't look like an MCP token — callers
    should fall back to normal JWT auth in that case.
    """
    if not raw or not isinstance(raw, str) or not raw.startswith(RAW_TOKEN_PREFIX):
        return None
    remainder = raw[len(RAW_TOKEN_PREFIX):]
    parts = remainder.split("_", 1)
    if len(parts) != 2:
        return None
    token_id, secret = parts
    if not _TOKEN_ID_RE.match(token_id) or not secret:
        return None
    return token_id, secret


def looks_like_mcp_token(raw: str) -> bool:
    """Fast prefix check used by the mcp_server auth resolver."""
    return isinstance(raw, str) and raw.startswith(RAW_TOKEN_PREFIX)


async def verify_and_touch_token(
    db, raw_token: str,
) -> Optional[tuple[Dict[str, Any], List[str]]]:
    """Verify a raw MCP token against the database.

    On success: returns `(user_doc, effective_scopes)`, updates
    `last_used_at`.
    On any failure (bad format, unknown token_id, mismatched secret,
    revoked, expired): returns None.

    Raw tokens are NEVER written to logs.
    """
    parsed = parse_raw_token(raw_token)
    if not parsed:
        return None
    token_id, secret = parsed

    doc = await db[MCP_TOKENS_COLLECTION].find_one(
        {"token_id": token_id}, {"_id": 0},
    )
    if not doc:
        return None
    if doc.get("revoked") is True:
        return None
    exp = doc.get("expires_at")
    if isinstance(exp, str):
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if exp_dt < datetime.now(timezone.utc):
                return None
        except Exception:  # noqa: BLE001
            return None

    stored_hash = doc.get("token_hash")
    if not stored_hash:
        return None
    try:
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode("utf-8")
        if not bcrypt.checkpw(secret.encode("utf-8"), stored_hash):
            return None
    except Exception:  # noqa: BLE001
        return None

    user_doc = await db.users.find_one({"id": doc["user_id"]}, {"_id": 0, "password": 0})
    if not user_doc:
        return None

    scopes = [s for s in (doc.get("scopes") or []) if s in ALLOWED_SCOPES]

    # Fire-and-forget last_used_at update. Failure must not affect
    # authentication.
    try:
        await db[MCP_TOKENS_COLLECTION].update_one(
            {"token_id": token_id},
            {"$set": {"last_used_at": _now_iso()}},
        )
    except Exception:  # noqa: BLE001
        pass

    return user_doc, scopes


# ─── Subscription gate (mirrors mcp_server._require_mcp_access) ────
_ALLOWED_TIERS = {"premium", "vip", "partner_pro"}
_ADMIN_ROLES = {"admin", "super_admin"}


def _subscription_active(user_doc: Dict[str, Any]) -> bool:
    tier = (user_doc.get("subscription_tier") or "").lower()
    status = (user_doc.get("subscription_status") or "").lower()
    account_type = (user_doc.get("account_type") or "").lower()

    if tier in _ALLOWED_TIERS and status == "active":
        return True
    if user_doc.get("is_vehicle_dealer") is True:
        dealer_status = (user_doc.get("dealer_subscription_status") or "").lower()
        dealer_active = bool(user_doc.get("dealer_subscription_active"))
        if dealer_status == "active" and dealer_active:
            return True
    if account_type == "broker" and status == "active":
        return True
    if account_type == "storage_facility":
        if user_doc.get("facility_verified") is True and status == "active":
            return True
    if (user_doc.get("role") or "").lower() in _ADMIN_ROLES:
        return True
    return False


async def _require_mcp_subscription(db, user: User) -> Dict[str, Any]:
    user_doc = await db.users.find_one({"id": user.id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail={"error": "USER_NOT_FOUND"})
    if not _subscription_active(user_doc):
        raise HTTPException(status_code=402, detail={
            "error":      "SUBSCRIPTION_REQUIRED",
            "message_en": "MCP tokens require an active BidVex Premium, VIP, Partner Pro, Vehicle Dealer, Broker, or verified Storage Facility subscription.",
            "message_fr": "Les jetons MCP nécessitent un abonnement BidVex Premium, VIP, Partner Pro, concessionnaire, courtier ou établissement d'entreposage vérifié.",
            "upgrade_url": "/pricing",
        })
    return user_doc


# ─── Request / response models ─────────────────────────────────────
class CreateTokenRequest(BaseModel):
    label: str = Field(..., description="Human-readable label (max 64 chars).")
    scopes: List[str] = Field(default_factory=lambda: ["read"])
    expires_in_days: Optional[int] = Field(default=DEFAULT_EXPIRATION_DAYS)

    @field_validator("label")
    @classmethod
    def _label_valid(cls, v: str) -> str:
        v = (v or "").strip()
        if not _LABEL_RE.match(v):
            raise ValueError("label must be 1-64 chars, alphanumeric + spaces + . _ -")
        return v

    @field_validator("scopes")
    @classmethod
    def _scopes_valid(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list) or not v:
            raise ValueError("scopes must be a non-empty list")
        cleaned: List[str] = []
        for s in v:
            s = (s or "").strip().lower()
            if s in ALLOWED_SCOPES and s not in cleaned:
                cleaned.append(s)
        if not cleaned:
            raise ValueError(f"scopes must contain at least one of: {ALLOWED_SCOPES}")
        return cleaned

    @field_validator("expires_in_days")
    @classmethod
    def _exp_valid(cls, v: Optional[int]) -> int:
        if v is None:
            return DEFAULT_EXPIRATION_DAYS
        if not isinstance(v, int):
            raise ValueError("expires_in_days must be an integer")
        if v < MIN_EXPIRATION_DAYS or v > MAX_EXPIRATION_DAYS:
            raise ValueError(f"expires_in_days must be {MIN_EXPIRATION_DAYS}-{MAX_EXPIRATION_DAYS}")
        return v


class TokenPublicView(BaseModel):
    token_id: str
    label: str
    scopes: List[str]
    created_at: str
    expires_at: str
    last_used_at: Optional[str] = None
    revoked: bool = False
    status: str


def _to_public(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitise a token record for API return — NEVER includes the raw
    token or the bcrypt hash."""
    exp = doc.get("expires_at") or ""
    now = datetime.now(timezone.utc)
    status = "revoked" if doc.get("revoked") else "active"
    if status == "active" and exp:
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if exp_dt < now:
                status = "expired"
        except Exception:  # noqa: BLE001
            pass
    return {
        "token_id":     doc.get("token_id"),
        "label":        doc.get("label"),
        "scopes":       [s for s in (doc.get("scopes") or []) if s in ALLOWED_SCOPES],
        "created_at":   doc.get("created_at"),
        "expires_at":   exp,
        "last_used_at": doc.get("last_used_at"),
        "revoked":      bool(doc.get("revoked")),
        "status":       status,
    }


# ─── Endpoints ─────────────────────────────────────────────────────
@mcp_tokens_router.post("/token")
async def create_mcp_token(
    body: CreateTokenRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a scoped MCP token for the authenticated user.

    Returns the raw token EXACTLY ONCE. It is never retrievable again.
    """
    db = get_db()
    await _require_mcp_subscription(db, current_user)

    # Deliberate: we do NOT accept admin scopes. Even if the caller is
    # an admin, tokens carry only the coarse capability scopes; admin
    # privileges continue to flow from the user's role at execution
    # time (via the existing `_require_admin_role` gate).
    scopes = body.scopes

    token_id = uuid.uuid4().hex[:16]  # 8-byte hex, non-secret
    raw_token, bh, _ = _mint_raw_token(token_id)

    now_dt = datetime.now(timezone.utc)
    expires_at = now_dt + timedelta(days=int(body.expires_in_days or DEFAULT_EXPIRATION_DAYS))

    doc: Dict[str, Any] = {
        "id":           str(uuid.uuid4()),
        "token_id":     token_id,
        "user_id":      current_user.id,
        "token_hash":   bh.decode("utf-8"),
        "label":        body.label,
        "scopes":       scopes,
        "created_at":   now_dt.isoformat(),
        "expires_at":   expires_at.isoformat(),
        "last_used_at": None,
        "revoked":      False,
    }
    await db[MCP_TOKENS_COLLECTION].insert_one(doc)

    # Explicit — the ONLY response ever to contain `token`.
    logger.info(
        "[mcp_tokens] created token_id=%s user_id=%s scopes=%s",
        token_id, current_user.id, scopes,
    )
    return {
        "token":     raw_token,
        "token_id":  token_id,
        "label":     body.label,
        "scopes":    scopes,
        "expires_at": doc["expires_at"],
        "warning_en": "This token is shown only once. Store it securely — BidVex cannot display it again.",
        "warning_fr": "Ce jeton n'est affiché qu'une seule fois. Stockez-le en lieu sûr — BidVex ne peut pas le réafficher.",
    }


@mcp_tokens_router.get("/tokens")
async def list_mcp_tokens(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the caller's MCP tokens (metadata only — never the raw
    token or hash)."""
    db = get_db()
    rows = await db[MCP_TOKENS_COLLECTION].find(
        {"user_id": current_user.id}, {"_id": 0, "token_hash": 0},
    ).sort("created_at", -1).to_list(200)
    return {"tokens": [_to_public(r) for r in rows]}


@mcp_tokens_router.delete("/token/{token_id}")
async def revoke_mcp_token(
    token_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Revoke a token. Only the token owner or an admin may revoke."""
    db = get_db()
    if not _TOKEN_ID_RE.match(token_id or ""):
        raise HTTPException(status_code=400, detail={"error": "INVALID_TOKEN_ID"})

    doc = await db[MCP_TOKENS_COLLECTION].find_one(
        {"token_id": token_id}, {"_id": 0, "token_hash": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "TOKEN_NOT_FOUND"})

    is_owner = doc.get("user_id") == current_user.id
    is_admin = (getattr(current_user, "role", "") or "").lower() in _ADMIN_ROLES
    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail={"error": "NOT_TOKEN_OWNER"})

    await db[MCP_TOKENS_COLLECTION].update_one(
        {"token_id": token_id},
        {"$set": {"revoked": True, "revoked_at": _now_iso()}},
    )
    logger.info(
        "[mcp_tokens] revoked token_id=%s revoked_by=%s owner=%s admin=%s",
        token_id, current_user.id, is_owner, is_admin,
    )
    return {"token_id": token_id, "revoked": True}


__all__ = [
    "mcp_tokens_router",
    "MCP_TOKENS_COLLECTION",
    "ALLOWED_SCOPES",
    "RAW_TOKEN_PREFIX",
    "verify_and_touch_token",
    "looks_like_mcp_token",
    "parse_raw_token",
]
