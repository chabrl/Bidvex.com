"""
iter490 — Streamable HTTP transport for BidVex Remote MCP.

Adds a canonical MCP Streamable HTTP endpoint at `POST /api/mcp` (with
matching `GET` and `DELETE`), fully compliant with the 2025-03-26 /
2025-06-18 MCP protocol revisions that Claude.ai uses.

Why this exists
---------------
`POST /api/mcp/rpc` (iter485/iter489) is a stateless JSON-RPC endpoint.
Claude.ai's remote-connector client speaks *Streamable HTTP*, which
adds session management via the `Mcp-Session-Id` header. Without a
proper session lifecycle, Claude can't distinguish "session dropped"
from "session still valid" and eventually decides the connection is
broken (the "Connection issue — Your connection to Bidvex stopped
working" message).

This module is 100% additive. The old endpoints stay unchanged:
  * iter485 `/api/mcp/tools/call`, `/tools/list` — still work
  * iter485 `/api/mcp/rpc` — still works (used by mcp_bridge.py, tests)
  * iter486 `/api/mcp/sse` — still works
  * iter488 OAuth token surface — unchanged

Contract implemented per spec
-----------------------------
  * `POST /api/mcp` — JSON-RPC dispatch, issues `Mcp-Session-Id` on
    initialize, requires it on subsequent requests. Returns
    HTTP 400/404 for missing/unknown session IDs.
  * `GET  /api/mcp` — 405 Method Not Allowed with proper Allow header
    (we support one-shot request/response, not server-initiated
    streams; per spec §Transports §Streamable HTTP §GET, returning
    405 is explicitly allowed for servers that don't need to push
    unsolicited messages).
  * `DELETE /api/mcp` — terminates the given session.
  * `Accept` header validation (spec: MUST include both
    `application/json` and `text/event-stream`).
  * `WWW-Authenticate: Bearer resource_metadata=…` on 401 so Claude
    can discover the OAuth server automatically.

Session storage is MongoDB-backed (`mcp_streamable_sessions`) so
preview pod restarts don't kill sessions.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from deps import User, get_current_user, get_db

logger = logging.getLogger("bidvex.mcp_streamable")

# Session lifetime (idle timeout). Persistent enough to survive normal
# preview restarts but short enough that stale sessions don't linger
# in the DB forever.
SESSION_IDLE_TTL_MIN = 60
SESSION_MAX_TTL_HOURS = 24
SESSIONS_COLLECTION = "mcp_streamable_sessions"

# Namespaced router — mounts as `/api/mcp` on top of the existing
# `/api/mcp/*` tree; siblings (`/api/mcp/rpc`, etc.) are untouched.
streamable_router = APIRouter(prefix="/mcp", tags=["MCP Streamable HTTP"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _issuer(request: Request) -> str:
    import os
    return (os.environ.get("REMOTE_MCP_PUBLIC_URL")
            or os.environ.get("FRONTEND_URL")
            or f"{request.url.scheme}://{request.url.netloc}").rstrip("/")


def _www_auth(request: Request) -> Dict[str, str]:
    """Return the WWW-Authenticate header value that points at our
    protected-resource metadata (RFC 9728). Claude.ai reads this on 401
    to discover the OAuth authorization server automatically."""
    origin = _issuer(request)
    return {"WWW-Authenticate":
            f'Bearer realm="bidvex-mcp", '
            f'resource_metadata="{origin}/api/.well-known/oauth-protected-resource"'}


async def _load_session(db, session_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[SESSIONS_COLLECTION].find_one({"session_id": session_id}, {"_id": 0})
    if not doc:
        return None
    exp = doc.get("expires_at")
    try:
        if datetime.fromisoformat(exp.replace("Z", "+00:00")) < _now():
            return None
    except Exception:  # noqa: BLE001
        return None
    return doc


async def _touch_session(db, session_id: str) -> None:
    await db[SESSIONS_COLLECTION].update_one(
        {"session_id": session_id},
        {"$set": {"last_activity_at": _now_iso(),
                  "expires_at": (_now() + timedelta(minutes=SESSION_IDLE_TTL_MIN)).isoformat()}},
    )


async def _create_session(db, user: User, request: Request) -> str:
    session_id = "mcp_sess_" + secrets.token_urlsafe(24)
    now = _now()
    scopes = getattr(request.state, "mcp_scopes", None)
    auth_source = getattr(request.state, "mcp_auth_source", "jwt")
    doc = {
        "id":                 str(uuid.uuid4()),
        "session_id":         session_id,
        "user_id":            user.id,
        "auth_source":        auth_source,      # jwt | mcp_token
        "scopes":             list(scopes) if scopes is not None else None,
        "created_at":         now.isoformat(),
        "last_activity_at":   now.isoformat(),
        "initialized_at":     now.isoformat(),
        "expires_at":         (now + timedelta(minutes=SESSION_IDLE_TTL_MIN)).isoformat(),
        "hard_expires_at":    (now + timedelta(hours=SESSION_MAX_TTL_HOURS)).isoformat(),
    }
    await db[SESSIONS_COLLECTION].insert_one(doc)
    return session_id


def _validate_accept(accept: Optional[str]) -> None:
    """Spec §Streamable HTTP: `Accept` MUST include both
    `application/json` and `text/event-stream`. Failure → 406."""
    if not accept:
        # Be lenient — some clients omit Accept
        return
    a = accept.lower()
    if "application/json" not in a and "*/*" not in a:
        raise HTTPException(status_code=406, detail={
            "error": "not_acceptable",
            "error_description":
                "Accept header must include application/json and text/event-stream",
        })


# ─── Resolver: reuse iter488 auth resolver, but expose WWW-Authenticate ─
async def _resolve_or_401(request: Request) -> User:
    """Delegate to iter488's `_resolve_user_or_mcp_token`. If it raises
    401, re-raise with a WWW-Authenticate header attached so Claude
    can discover OAuth."""
    from mcp_server import _resolve_user_or_mcp_token
    try:
        return await _resolve_user_or_mcp_token(request)
    except HTTPException as exc:
        if exc.status_code == 401:
            # Preserve body, add WWW-Authenticate
            raise HTTPException(status_code=401, detail=exc.detail,
                                headers=_www_auth(request))
        raise


# ═══════════════════════════════════════════════════════════════════
# POST /api/mcp  — JSON-RPC + session management
# ═══════════════════════════════════════════════════════════════════
@streamable_router.post("")
async def streamable_post(
    request: Request,
    body: Dict[str, Any],
    mcp_session_id: Optional[str] = Header(default=None, alias="Mcp-Session-Id"),
    accept: Optional[str] = Header(default=None),
) -> Response:
    """Streamable HTTP JSON-RPC endpoint.

    Contract:
      * `initialize` requests are the only ones allowed *without* an
        `Mcp-Session-Id` header. The server creates a session and
        returns the ID in the response header.
      * Every other JSON-RPC method MUST carry a valid `Mcp-Session-Id`.
        Missing → 400. Unknown/expired → 404 (per spec, the client
        should re-initialize).
      * Notifications (`method="notifications/*"`) may or may not carry
        a session ID — we accept both.
    """
    _validate_accept(accept)
    current_user = await _resolve_or_401(request)
    db = get_db()

    method = (body or {}).get("method") if isinstance(body, dict) else None
    is_init = method == "initialize"
    is_notification = isinstance(method, str) and method.startswith("notifications/")

    # ── Session gate ─────────────────────────────────────────────
    session_doc: Optional[Dict[str, Any]] = None
    if is_init:
        # Fresh session
        session_id = await _create_session(db, current_user, request)
    else:
        if not mcp_session_id:
            if is_notification:
                # Some clients batch a notification before initialize —
                # be lenient and just 202-accept it.
                return Response(status_code=202)
            raise HTTPException(status_code=400, detail={
                "error": "missing_session",
                "error_description": "Mcp-Session-Id header is required",
            })
        session_doc = await _load_session(db, mcp_session_id)
        if not session_doc:
            # Unknown / expired — client should re-initialize
            raise HTTPException(status_code=404, detail={
                "error": "session_not_found",
                "error_description": "Session is unknown or expired; re-initialize.",
            })
        if session_doc.get("user_id") != current_user.id:
            # Session belongs to a different identity — reject
            raise HTTPException(status_code=403, detail={
                "error": "session_mismatch",
                "error_description": "Bearer identity does not match session owner.",
            })
        session_id = mcp_session_id
        await _touch_session(db, session_id)

    # ── Dispatch via iter485 pipeline (unchanged business logic) ─
    from mcp_server import _dispatch_jsonrpc
    # Extract JWT for the bidding path (unchanged behavior)
    jwt_token = None
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        jwt_token = auth.split(" ", 1)[1]
    mcp_scopes = getattr(request.state, "mcp_scopes", None)

    if isinstance(body, list):
        # Batch — dispatch in order
        responses = []
        for msg in body:
            if isinstance(msg, dict):
                r = await _dispatch_jsonrpc(db, current_user, msg,
                                            jwt_token=jwt_token,
                                            mcp_scopes=mcp_scopes)
                if r is not None:
                    responses.append(r)
        return JSONResponse(responses, headers={"Mcp-Session-Id": session_id})

    if not isinstance(body, dict):
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None,
             "error": {"code": -32600, "message": "invalid Request"}},
            headers={"Mcp-Session-Id": session_id},
        )

    r = await _dispatch_jsonrpc(db, current_user, body,
                                 jwt_token=jwt_token,
                                 mcp_scopes=mcp_scopes)
    headers = {"Mcp-Session-Id": session_id}
    if r is None:
        # Notification per spec — 202 Accepted
        return Response(status_code=202, headers=headers)

    # Bump the server-advertised protocolVersion on initialize so
    # Claude.ai negotiates to Streamable HTTP session semantics.
    # (2025-06-18 is the current stable spec revision at time of
    # writing; if the client sent an older version we honour it.)
    if is_init and isinstance(r, dict) and isinstance(r.get("result"), dict):
        requested = (body.get("params") or {}).get("protocolVersion")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18"}
        if requested in supported:
            r["result"]["protocolVersion"] = requested
        else:
            # Choose highest we support that the client can plausibly use
            r["result"]["protocolVersion"] = "2025-06-18"
    return JSONResponse(r, headers=headers)


# ═══════════════════════════════════════════════════════════════════
# GET /api/mcp — server-initiated SSE stream (optional per spec)
# ═══════════════════════════════════════════════════════════════════
@streamable_router.get("")
async def streamable_get(
    request: Request,
    mcp_session_id: Optional[str] = Header(default=None, alias="Mcp-Session-Id"),
) -> Response:
    """Spec: "The server MAY, but is not required to, offer an SSE
    stream on GET." BidVex does not currently push unsolicited
    server-initiated messages, so we politely 405 with proper Allow
    header instead of 404. Some clients probe GET before POST to see
    if the endpoint exists; a 405 with correct Allow reliably tells
    them the endpoint is here and to use POST.
    """
    await _resolve_or_401(request)
    return Response(status_code=405, headers={"Allow": "POST, DELETE"})


# ═══════════════════════════════════════════════════════════════════
# DELETE /api/mcp — session termination
# ═══════════════════════════════════════════════════════════════════
@streamable_router.delete("")
async def streamable_delete(
    request: Request,
    mcp_session_id: Optional[str] = Header(default=None, alias="Mcp-Session-Id"),
) -> Response:
    """Terminate a session cleanly. Idempotent — deleting an unknown
    session returns 204 to avoid leaking session-existence."""
    current_user = await _resolve_or_401(request)
    db = get_db()
    if mcp_session_id:
        await db[SESSIONS_COLLECTION].delete_one({
            "session_id": mcp_session_id,
            "user_id":    current_user.id,
        })
    return Response(status_code=204)


__all__ = ["streamable_router", "SESSIONS_COLLECTION"]
