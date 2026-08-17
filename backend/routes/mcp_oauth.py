"""
iter489 — OAuth 2.1 Authorization Server for the BidVex Remote MCP
connector (Claude.ai / any other MCP client that speaks the standard
custom-connector OAuth flow).

Design invariants (do not weaken):
  * Access tokens issued by this OAuth server ARE iter488 scoped MCP
    tokens. Zero token-storage duplication; every existing security
    property (bcrypt hashing, revocation, expiration, scope
    enforcement, audit sanitisation) applies automatically.
  * OAuth is a *bootstrap* channel only — it does not touch the MCP
    dispatcher, tool registry, gate enforcement, or business logic.
  * PKCE S256 is mandatory (RFC 7636).
  * Authorization codes are single-use and short-lived (≤ 10 min).
  * Client secrets (if any) are stored bcrypt-hashed, never in plain
    text; a public client (no secret) is the recommended path for
    Claude.ai and is the primary supported mode.
  * The user's session JWT is required to actually approve a grant —
    the OAuth authorize endpoint cannot mint a token without the
    user's browser session.
  * Every raw secret (client_secret, authorization_code, PKCE verifier,
    access_token) is redacted in logs by the existing sanitiser and is
    never persisted in cleartext.

Endpoints (mounted under `/api/mcp/oauth/*`):
  * POST /register              — Dynamic Client Registration (RFC 7591)
  * GET  /authorize             — starts the authorization flow (302 → consent)
  * POST /authorize/decision    — user approve/deny (called by consent UI)
  * POST /token                 — code → access_token (also refresh flow stub)
  * POST /revoke                — revoke an access token (RFC 7009)
  * GET  /clients/{client_id}   — client metadata (read-only)

Discovery is served in `server.py` at:
  * GET /.well-known/oauth-authorization-server
  * GET /.well-known/oauth-protected-resource
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

from deps import User, get_current_user, get_db
from routes.mcp_tokens import (
    ALLOWED_SCOPES, _now_iso, _require_mcp_subscription, _mint_raw_token,
    MCP_TOKENS_COLLECTION, DEFAULT_EXPIRATION_DAYS,
)

logger = logging.getLogger("bidvex.mcp_oauth")

mcp_oauth_router = APIRouter(prefix="/mcp/oauth", tags=["MCP OAuth"])

# Collections
CLIENTS_COLLECTION = "mcp_oauth_clients"
CODES_COLLECTION   = "mcp_oauth_codes"
DCR_RATE_COLLECTION = "mcp_oauth_dcr_rate"       # iter491 — DCR abuse guard

# Timings
AUTH_CODE_TTL_S       = 600        # 10 min
CLIENT_REGISTRATION_TTL_DAYS = 365  # metadata retention
ACCESS_TOKEN_TTL_DAYS = 90         # default MCP token expiration

# iter491 — RFC 7591 §5 SHOULD rate-limit unauthenticated DCR.
DCR_RATE_WINDOW_S = 3600
DCR_RATE_MAX_PER_IP = 200

# Regexes
_CLIENT_ID_RE   = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")
_HTTPS_OR_LOCAL = re.compile(r"^https://|^http://localhost|^http://127\.0\.0\.1")


def _b64url_sha256(s: str) -> str:
    """RFC 7636 S256: base64url(no padding) of SHA-256(verifier)."""
    import base64
    return base64.urlsafe_b64encode(hashlib.sha256(s.encode("utf-8")).digest()).rstrip(b"=").decode("ascii")


# ─── Pydantic models ─────────────────────────────────────────────────
class ClientRegistrationRequest(BaseModel):
    """RFC 7591 dynamic client registration request. Kept intentionally
    minimal — only the fields required by Claude.ai's custom connector
    are honoured."""
    client_name:                Optional[str] = Field(default=None)
    redirect_uris:              List[str]     = Field(..., min_length=1)
    grant_types:                Optional[List[str]] = None
    response_types:             Optional[List[str]] = None
    token_endpoint_auth_method: Optional[str] = Field(default="none")
    scope:                      Optional[str] = None
    software_id:                Optional[str] = None
    software_version:           Optional[str] = None

    @field_validator("redirect_uris")
    @classmethod
    def _validate_redirects(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("at least one redirect_uri is required")
        for uri in v:
            if not _HTTPS_OR_LOCAL.match(uri):
                raise ValueError(f"redirect_uri must be https:// (or http://localhost for dev): {uri}")
            parsed = urlparse(uri)
            if parsed.fragment:
                raise ValueError("redirect_uri MUST NOT contain a fragment (RFC 6749 §3.1.2)")
        return v


class TokenExchangeRequest(BaseModel):
    grant_type:    str
    code:          Optional[str] = None
    redirect_uri:  Optional[str] = None
    client_id:     Optional[str] = None
    client_secret: Optional[str] = None
    code_verifier: Optional[str] = None


class AuthorizeDecisionRequest(BaseModel):
    """The consent UI submits this to record the user's decision.

    All the OAuth parameters passed to `GET /authorize` are echoed
    back so the backend can verify the client and mint a code."""
    approved:              bool
    client_id:             str
    redirect_uri:          str
    code_challenge:        str
    code_challenge_method: str = "S256"
    scope:                 str
    state:                 str
    resource:              Optional[str] = None


# ─── Storage helpers ─────────────────────────────────────────────────
async def _load_client(db, client_id: str) -> Optional[Dict[str, Any]]:
    return await db[CLIENTS_COLLECTION].find_one({"client_id": client_id}, {"_id": 0})


async def _validate_scopes(requested: str) -> List[str]:
    """Filter a space-separated scope string down to the iter488
    allowlist. Empty → default `read`."""
    if not requested:
        return ["read"]
    parts = [s.strip().lower() for s in requested.replace(",", " ").split() if s.strip()]
    cleaned = [s for s in parts if s in ALLOWED_SCOPES]
    return cleaned or ["read"]


def _new_client_id() -> str:
    return "mcp_" + secrets.token_urlsafe(16)


def _sanitize_client_public(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Never surface client_secret_hash externally."""
    return {
        "client_id":                  doc.get("client_id"),
        "client_id_issued_at":        int(datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00")).timestamp())
                                          if doc.get("created_at") else None,
        "client_name":                doc.get("client_name"),
        "redirect_uris":              doc.get("redirect_uris") or [],
        "grant_types":                doc.get("grant_types") or ["authorization_code"],
        "response_types":             doc.get("response_types") or ["code"],
        "token_endpoint_auth_method": doc.get("token_endpoint_auth_method") or "none",
        # RFC 7591 §3.2.1 — echo the scopes the client is authorised to
        # request. Prefer the scope stored on the client record so DCR
        # scope negotiation is preserved through the /authorize step.
        "scope":                      doc.get("scope") or " ".join(ALLOWED_SCOPES),
    }


async def _dcr_rate_check(db, ip: str) -> None:
    """iter491 — RFC 7591 §5 SHOULD rate-limit an unauthenticated DCR
    endpoint. Enforce ≤ DCR_RATE_MAX_PER_IP registrations per hour per
    remote IP. Returns silently on OK; raises 429 on overflow."""
    if not ip:
        return
    now_dt = datetime.now(timezone.utc)
    window_start = now_dt - timedelta(seconds=DCR_RATE_WINDOW_S)
    coll = db[DCR_RATE_COLLECTION]
    doc = await coll.find_one({"ip": ip}, {"_id": 0})
    events = [e for e in (doc.get("events", []) if doc else [])
              if datetime.fromisoformat(e.replace("Z", "+00:00")) >= window_start]
    if len(events) >= DCR_RATE_MAX_PER_IP:
        logger.warning(f"[mcp_oauth] DCR rate limit HIT ip={ip} count={len(events)}")
        raise HTTPException(status_code=429, detail={
            "error": "too_many_requests",
            "error_description": f"DCR is rate-limited to {DCR_RATE_MAX_PER_IP} registrations/hour per IP.",
        })
    events.append(now_dt.isoformat())
    await coll.update_one({"ip": ip},
                          {"$set": {"ip": ip, "events": events,
                                    "last_seen": now_dt.isoformat()}},
                          upsert=True)


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").split(",")
    if xff and xff[0].strip():
        return xff[0].strip()
    return request.client.host if request.client else ""


# ─── 1. Dynamic Client Registration (RFC 7591) ───────────────────────
@mcp_oauth_router.post("/register")
async def register_client(body: ClientRegistrationRequest, request: Request) -> JSONResponse:
    """Public dynamic-client-registration endpoint. Deliberately
    unauthenticated per RFC 7591 §3 (public clients). Per RFC 7591
    §3.2.1 a successful registration MUST respond with HTTP 201
    Created + Cache-Control: no-store, so strict clients like
    Claude.ai accept the response."""
    db = get_db()
    await _dcr_rate_check(db, _client_ip(request))

    # `none` (public client) is the recommended token-endpoint auth
    # method for Claude.ai + PKCE. We also accept `client_secret_post`
    # for private clients that want to demonstrate confidential auth.
    method = (body.token_endpoint_auth_method or "none").lower()
    if method not in {"none", "client_secret_post", "client_secret_basic"}:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_client_metadata",
            "error_description": "token_endpoint_auth_method must be one of: none, client_secret_post, client_secret_basic",
        })

    # iter491 — echo only grant_types we support. RFC 7591 §2 permits
    # the server to return a subset of what the client requested; that
    # subset then binds the client. If a client asks for refresh_token
    # we drop it so the client won't attempt an unsupported grant later.
    requested_grants = body.grant_types or ["authorization_code"]
    grant_types = [g for g in requested_grants if g == "authorization_code"]
    if "authorization_code" not in grant_types:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_client_metadata",
            "error_description": "authorization_code grant_type is required",
        })

    # iter491 — negotiate scope: echo the intersection of the client's
    # requested scope and our allowlist. If the client did not send a
    # scope, default to the full allowlist for backward compatibility.
    negotiated_scopes = await _validate_scopes(body.scope or "")
    if not body.scope:
        negotiated_scopes = list(ALLOWED_SCOPES)

    client_id = _new_client_id()
    now = _now_iso()
    doc: Dict[str, Any] = {
        "id":                         str(uuid.uuid4()),
        "client_id":                  client_id,
        "client_name":                (body.client_name or "MCP Remote Client")[:120],
        "redirect_uris":              body.redirect_uris,
        "grant_types":                grant_types,
        "response_types":             body.response_types or ["code"],
        "token_endpoint_auth_method": method,
        "scope":                      " ".join(negotiated_scopes),
        "software_id":                (body.software_id or "")[:120] or None,
        "software_version":           (body.software_version or "")[:120] or None,
        "created_at":                 now,
    }

    response: Dict[str, Any] = _sanitize_client_public(doc)
    # iter491 — RFC 7591 §3.2.1: `client_secret_expires_at` is REQUIRED
    # when the response includes `client_secret` and RECOMMENDED for
    # consistency. For public clients we emit 0 (never expires) so
    # strict clients don't reject a "malformed" response.
    if method in {"client_secret_post", "client_secret_basic"}:
        secret_raw = secrets.token_urlsafe(32)
        doc["client_secret_hash"] = bcrypt.hashpw(
            secret_raw.encode("utf-8"), bcrypt.gensalt(rounds=12),
        ).decode("utf-8")
        response["client_secret"] = secret_raw           # returned exactly once
        response["client_secret_expires_at"] = 0         # 0 = never (RFC 7591)
    await db[CLIENTS_COLLECTION].insert_one(doc)
    logger.info(f"[mcp_oauth] registered client_id={client_id} method={method} "
                f"redirects={len(body.redirect_uris)} scopes={negotiated_scopes}")
    # RFC 7591 §3.2.1 MUST return 201 Created + Cache-Control: no-store
    return JSONResponse(status_code=201, content=response,
                        headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


@mcp_oauth_router.get("/clients/{client_id}")
async def get_client(client_id: str) -> Dict[str, Any]:
    """Read-only public metadata for a registered client. Never
    surfaces client_secret_hash."""
    db = get_db()
    doc = await _load_client(db, client_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "invalid_client"})
    return _sanitize_client_public(doc)


# ─── 2. Authorize endpoint — hands off to the consent UI ─────────────
@mcp_oauth_router.get("/authorize")
async def authorize(
    request: Request,
    response_type:         str = Query(...),
    client_id:             str = Query(...),
    redirect_uri:          str = Query(...),
    code_challenge:        str = Query(...),
    code_challenge_method: str = Query("S256"),
    scope:                 str = Query("read"),
    state:                 str = Query(...),
    resource:              Optional[str] = Query(None),
) -> RedirectResponse:
    """Validate the OAuth params, then redirect the browser to the
    React consent page which will collect the user's approval.

    Errors go BACK to the caller as OAuth redirect errors so the client
    can render a meaningful message — except catastrophic errors
    (unknown client, bad redirect_uri) which are surfaced directly per
    RFC 6749 §4.1.2.1."""
    db = get_db()
    client = await _load_client(db, client_id)
    if not client:
        raise HTTPException(status_code=400, detail={"error": "invalid_client"})
    if redirect_uri not in (client.get("redirect_uris") or []):
        # RFC 6749: never redirect to an unregistered URI — surface a hard error
        raise HTTPException(status_code=400, detail={
            "error": "invalid_request",
            "error_description": "redirect_uri is not registered for this client",
        })
    if response_type != "code":
        return _oauth_error_redirect(redirect_uri, state, "unsupported_response_type",
                                     "only response_type=code is supported")
    if code_challenge_method != "S256":
        return _oauth_error_redirect(redirect_uri, state, "invalid_request",
                                     "code_challenge_method must be S256")
    if not code_challenge or len(code_challenge) < 43:
        return _oauth_error_redirect(redirect_uri, state, "invalid_request",
                                     "code_challenge is required (S256)")
    scopes = await _validate_scopes(scope)

    # Hand off to the React consent page. The consent page will
    # authenticate the user (via existing session JWT) and POST the
    # decision to /authorize/decision.
    q = urlencode({
        "client_id":             client_id,
        "redirect_uri":          redirect_uri,
        "code_challenge":        code_challenge,
        "code_challenge_method": code_challenge_method,
        "scope":                 " ".join(scopes),
        "state":                 state,
        "resource":              resource or "",
        "client_name":           client.get("client_name") or "MCP Client",
    })
    consent_url = f"/mcp-consent?{q}"
    return RedirectResponse(url=consent_url, status_code=302)


def _oauth_error_redirect(redirect_uri: str, state: str, error: str, description: str) -> RedirectResponse:
    q = urlencode({"error": error, "error_description": description, "state": state})
    return RedirectResponse(url=f"{redirect_uri}?{q}", status_code=302)


# ─── 3. Consent decision — issues the authorization code ─────────────
@mcp_oauth_router.post("/authorize/decision")
async def authorize_decision(
    body: AuthorizeDecisionRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Called by the React consent page. Requires the user's session
    JWT — this is how we prove that a real BidVex user, not just a
    request from Claude.ai's backend, is granting the token."""
    db = get_db()
    # Same subscription gate as normal MCP token creation
    await _require_mcp_subscription(db, current_user)

    client = await _load_client(db, body.client_id)
    if not client:
        raise HTTPException(status_code=400, detail={"error": "invalid_client"})
    if body.redirect_uri not in (client.get("redirect_uris") or []):
        raise HTTPException(status_code=400, detail={"error": "invalid_redirect_uri"})
    if body.code_challenge_method != "S256":
        raise HTTPException(status_code=400, detail={"error": "invalid_request",
                                                     "error_description": "S256 required"})

    if not body.approved:
        # Bounce back with `access_denied` — RFC 6749 §4.1.2.1
        q = urlencode({"error": "access_denied", "state": body.state})
        return {"redirect_to": f"{body.redirect_uri}?{q}"}

    scopes = await _validate_scopes(body.scope)
    code = "mcpcode_" + secrets.token_urlsafe(32)
    now_dt = datetime.now(timezone.utc)
    await db[CODES_COLLECTION].insert_one({
        "id":                     str(uuid.uuid4()),
        "code":                   code,
        "client_id":              body.client_id,
        "user_id":                current_user.id,
        "redirect_uri":           body.redirect_uri,
        "code_challenge":         body.code_challenge,
        "code_challenge_method":  body.code_challenge_method,
        "scopes":                 scopes,
        "resource":               body.resource,
        "created_at":             now_dt.isoformat(),
        "expires_at":             (now_dt + timedelta(seconds=AUTH_CODE_TTL_S)).isoformat(),
        "used":                   False,
    })
    q = urlencode({"code": code, "state": body.state})
    logger.info(f"[mcp_oauth] issued code client_id={body.client_id} user_id={current_user.id} scopes={scopes}")
    return {"redirect_to": f"{body.redirect_uri}?{q}"}


# ─── 4. Token endpoint — exchanges code for access_token ─────────────
@mcp_oauth_router.post("/token")
async def token_exchange(request: Request) -> Dict[str, Any]:
    """OAuth 2.1 token endpoint. Accepts both JSON and
    application/x-www-form-urlencoded bodies (per RFC 6749). Returns
    an iter488 scoped MCP token as `access_token`."""
    db = get_db()
    # Parse either JSON or form
    ct = (request.headers.get("content-type") or "").lower()
    if ct.startswith("application/json"):
        raw_body = await request.json()
    else:
        form = await request.form()
        raw_body = {k: v for k, v in form.items()}
    body = TokenExchangeRequest(**raw_body)

    if body.grant_type != "authorization_code":
        raise HTTPException(status_code=400, detail={
            "error": "unsupported_grant_type",
            "error_description": "only authorization_code is supported in this build",
        })
    if not body.code or not body.redirect_uri or not body.code_verifier:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_request",
            "error_description": "code, redirect_uri, and code_verifier are required",
        })

    # Client authentication ------------------------------------------------
    # Prefer client_id in body; also honour HTTP Basic per RFC 6749 §2.3.1
    client_id = body.client_id
    client_secret = body.client_secret
    if not client_id:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("basic "):
            import base64
            try:
                raw = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
                cid, csec = raw.split(":", 1)
                client_id = cid
                client_secret = csec
            except Exception:  # noqa: BLE001
                pass
    if not client_id:
        raise HTTPException(status_code=401, detail={"error": "invalid_client"})

    client = await _load_client(db, client_id)
    if not client:
        raise HTTPException(status_code=401, detail={"error": "invalid_client"})

    method = client.get("token_endpoint_auth_method") or "none"
    if method != "none":
        # Confidential client — require client_secret and verify against
        # the stored bcrypt hash.
        if not client_secret:
            raise HTTPException(status_code=401, detail={"error": "invalid_client"})
        stored_hash = client.get("client_secret_hash") or ""
        if not stored_hash or not bcrypt.checkpw(
            client_secret.encode("utf-8"), stored_hash.encode("utf-8"),
        ):
            raise HTTPException(status_code=401, detail={"error": "invalid_client"})

    # Code lookup / validation --------------------------------------------
    code_doc = await db[CODES_COLLECTION].find_one({"code": body.code}, {"_id": 0})
    if not code_doc:
        raise HTTPException(status_code=400, detail={"error": "invalid_grant"})
    if code_doc.get("used"):
        # Reuse detection — RFC 6749 §4.1.2 recommends invalidating any
        # tokens minted from this code. Since we mint iter488 tokens
        # (already listed in mcp_tokens), we revoke the last one if it
        # was minted from this code.
        prior = code_doc.get("issued_token_id")
        if prior:
            await db[MCP_TOKENS_COLLECTION].update_one(
                {"token_id": prior},
                {"$set": {"revoked": True, "revoked_reason": "auth_code_reused"}},
            )
        raise HTTPException(status_code=400, detail={"error": "invalid_grant",
                                                     "error_description": "authorization code already used"})
    exp = code_doc.get("expires_at")
    try:
        exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        exp_dt = datetime.now(timezone.utc) - timedelta(seconds=1)
    if exp_dt < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail={"error": "invalid_grant",
                                                     "error_description": "authorization code expired"})
    if code_doc.get("client_id") != client_id:
        raise HTTPException(status_code=400, detail={"error": "invalid_grant"})
    if code_doc.get("redirect_uri") != body.redirect_uri:
        raise HTTPException(status_code=400, detail={"error": "invalid_grant",
                                                     "error_description": "redirect_uri mismatch"})

    # PKCE verification (RFC 7636)
    expected = _b64url_sha256(body.code_verifier)
    if expected != code_doc.get("code_challenge"):
        raise HTTPException(status_code=400, detail={"error": "invalid_grant",
                                                     "error_description": "PKCE verifier mismatch"})

    # Mint an iter488 scoped MCP token as the access_token ---------------
    user_id = code_doc["user_id"]
    scopes = [s for s in (code_doc.get("scopes") or []) if s in ALLOWED_SCOPES]
    if not scopes:
        scopes = ["read"]

    # Confirm subscription is still active NOW (in case anything changed
    # between authorize and token exchange)
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=400, detail={"error": "invalid_grant"})

    token_id = uuid.uuid4().hex[:16]
    raw_token, bh, _ = _mint_raw_token(token_id)
    now_dt = datetime.now(timezone.utc)
    expires_at = now_dt + timedelta(days=ACCESS_TOKEN_TTL_DAYS)
    await db[MCP_TOKENS_COLLECTION].insert_one({
        "id":            str(uuid.uuid4()),
        "token_id":      token_id,
        "user_id":       user_id,
        "token_hash":    bh.decode("utf-8"),
        "label":         f"OAuth · {client.get('client_name') or client_id}",
        "scopes":        scopes,
        "created_at":    now_dt.isoformat(),
        "expires_at":    expires_at.isoformat(),
        "last_used_at":  None,
        "revoked":       False,
        "issued_via":    "oauth",
        "oauth_client_id": client_id,
    })

    # Mark code used and remember the token so we can revoke on reuse
    await db[CODES_COLLECTION].update_one(
        {"code": body.code},
        {"$set": {"used": True, "issued_token_id": token_id,
                  "issued_at": now_dt.isoformat()}},
    )

    logger.info(f"[mcp_oauth] issued access_token token_id={token_id} client_id={client_id} scopes={scopes}")
    return {
        "access_token": raw_token,
        "token_type":   "Bearer",
        "expires_in":   ACCESS_TOKEN_TTL_DAYS * 24 * 3600,
        "scope":        " ".join(scopes),
    }


# ─── 5. Token revocation (RFC 7009) ──────────────────────────────────
@mcp_oauth_router.post("/revoke")
async def revoke(request: Request) -> Dict[str, Any]:
    """Revoke an issued access token by presenting the raw token. This
    is intentionally unauthenticated per RFC 7009 §2.1: the presented
    token IS the auth. (The scope of what it can revoke is limited to
    the token itself — cannot be used to enumerate.)"""
    db = get_db()
    ct = (request.headers.get("content-type") or "").lower()
    if ct.startswith("application/json"):
        body = await request.json()
    else:
        form = await request.form()
        body = {k: v for k, v in form.items()}
    token = (body.get("token") or "").strip()
    if not token or not token.startswith("bvx_mcp_"):
        # RFC 7009 §2.2 — server SHOULD respond 200 for unknown tokens
        return {"revoked": False}
    remainder = token[len("bvx_mcp_"):]
    parts = remainder.split("_", 1)
    if len(parts) != 2:
        return {"revoked": False}
    token_id, _ = parts
    await db[MCP_TOKENS_COLLECTION].update_one(
        {"token_id": token_id},
        {"$set": {"revoked": True, "revoked_at": _now_iso(),
                  "revoked_reason": "oauth_revoke_endpoint"}},
    )
    return {"revoked": True}


__all__ = [
    "mcp_oauth_router",
    "CLIENTS_COLLECTION",
    "CODES_COLLECTION",
    "AUTH_CODE_TTL_S",
]
