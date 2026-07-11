"""
iter320 — Live Support Escalation Protocol.
iter321 — Real-time SSE notifier for admin (+ in-memory pub/sub).

Backed by the canonical AI Core system prompt section 8: the assistant
runs a 2-question gate, then emits a `[[BIDVEX_ESCALATION]]…[[/BIDVEX_ESCALATION]]`
marker. The frontend parses that marker out of the assistant's reply
and POSTs the JSON payload + recent transcript to this endpoint.

Endpoints
─────────
POST /api/support/escalate
    JWT-protected. Persists into `support_escalations`, emails admin,
    returns a confirmation envelope including the ticket id so the
    widget can display "Ticket #XYZ created".

GET  /api/admin/support/escalations
    Admin-only list view (filters: status, search, date range).

PATCH /api/admin/support/escalations/{id}/status
    Admin updates {open|acknowledged|resolved|dismissed}.

GET  /api/admin/support/escalations/stream  (iter321)
    Admin-only Server-Sent Events stream. Pushes `new_ticket`
    events whenever a ticket is created, plus periodic `ping`
    keepalives. The frontend `EscalationAlertProvider` subscribes
    here to play the 2-tone chime + desktop notification + flash
    the tab title in real time.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Support — Escalation"])

ADMIN_ROLES = {"admin", "super_admin"}
ESCALATION_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}
MAX_TRANSCRIPT_MESSAGES = 20
MAX_PROBLEM_CHARS = 1500
MAX_DETAILS_CHARS = 2500
MAX_TRANSCRIPT_CONTENT_CHARS = 2000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _role(user: User) -> str:
    return getattr(user, "role", None) or "user"


def require_admin(user: User = Depends(get_current_user)) -> User:
    if _role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "admin only")
    return user


# ─── iter321 — In-memory pub/sub broker for admin SSE ────────────────────
#
# Single-pod deployment friendly. Each admin SSE connection registers
# an asyncio.Queue; whenever a ticket is created we fan-out the event
# to every queue. This avoids MongoDB change-streams (which require a
# replica set) and works with the standalone Mongo used in dev.
#
# For multi-pod production, swap this for Redis pub/sub — the public
# `publish()` API stays the same.
class _EscalationBroker:
    def __init__(self) -> None:
        # Admin-fanout subscribers — every connected admin tab receives
        # every new_ticket / ticket_updated event.
        self._subscribers: List[asyncio.Queue] = []
        # iter322 — User-targeted subscribers. Keyed by user_id so an
        # admin reply to ticket X owned by user U only reaches U's tabs
        # (not every random user). Each user can have multiple open
        # tabs/devices, hence a list per user_id.
        self._user_subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    async def subscribe_user(self, user_id: str) -> asyncio.Queue:
        """iter322 — Subscribe a user-side SSE consumer so they receive
        admin replies to their own tickets in real time."""
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        async with self._lock:
            self._user_subscribers.setdefault(user_id, []).append(q)
        return q

    async def unsubscribe_user(self, user_id: str, q: asyncio.Queue) -> None:
        async with self._lock:
            lst = self._user_subscribers.get(user_id) or []
            try:
                lst.remove(q)
            except ValueError:
                pass
            if not lst:
                self._user_subscribers.pop(user_id, None)

    async def publish(self, event: str, data: Dict[str, Any]) -> None:
        """Fan-out to every ADMIN subscriber. Never raises — a slow consumer
        whose queue is full is silently dropped from this event (will
        get the next one + auto-reconnect on the next ping)."""
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                logger.warning("[escalation broker] dropped event for slow consumer")

    async def publish_to_user(self, user_id: str, event: str, data: Dict[str, Any]) -> None:
        """iter322 — Fan-out an event to one specific user's open tabs only."""
        async with self._lock:
            subs = list(self._user_subscribers.get(user_id, []))
        for q in subs:
            try:
                q.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                logger.warning("[escalation broker] dropped user event for slow consumer")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def user_subscriber_count(self) -> int:
        return sum(len(v) for v in self._user_subscribers.values())


broker = _EscalationBroker()


# ─── Models ─────────────────────────────────────────────────────────────

class TranscriptMessage(BaseModel):
    role:    str
    content: str
    ts:      Optional[str] = None


class EscalationCreateBody(BaseModel):
    problem:    str = Field(..., min_length=1, max_length=MAX_PROBLEM_CHARS)
    details:    str = Field(default="", max_length=MAX_DETAILS_CHARS)
    language:   str = Field(default="en", max_length=4)
    transcript: List[TranscriptMessage] = Field(default_factory=list, max_length=MAX_TRANSCRIPT_MESSAGES)
    session_id: Optional[str] = Field(default=None, max_length=200)
    page_url:   Optional[str] = Field(default=None, max_length=500)


class EscalationStatusBody(BaseModel):
    status: str
    admin_notes: Optional[str] = None


# ─── Email payload (Context Packet) ─────────────────────────────────────

def _render_context_packet_html(row: Dict[str, Any]) -> str:
    """Server-rendered Context Packet — the admin sees the full user
    problem statement, details, AND the recent transcript so the
    handoff is informed before the agent enters the chat."""
    transcript_html_rows = []
    for m in (row.get("transcript") or [])[-MAX_TRANSCRIPT_MESSAGES:]:
        role = (m.get("role") or "").lower()
        bg, label = {
            "user":      ("#EFF6FF", "USER"),
            "assistant": ("#F8FAFC", "AI"),
            "system":    ("#FEF3C7", "SYS"),
        }.get(role, ("#F1F5F9", role.upper()[:5]))
        content = (m.get("content") or "")[:MAX_TRANSCRIPT_CONTENT_CHARS]
        # Strip any leftover escalation marker so the email doesn't show it.
        content = re.sub(
            r"\[\[BIDVEX_ESCALATION\]\][\s\S]*?\[\[/BIDVEX_ESCALATION\]\]",
            "",
            content,
        ).strip()
        if not content:
            continue
        transcript_html_rows.append(
            f'<tr><td style="padding:6px 12px 6px 0;color:#475569;font-size:11px;'
            f'font-weight:700;vertical-align:top;white-space:nowrap;">{label}</td>'
            f'<td style="padding:6px 0;background:{bg};border-radius:6px;padding:8px 12px;'
            f'font-size:12px;line-height:1.5;color:#0F172A;">{_escape_html(content)}</td></tr>'
        )
    transcript_table = (
        f'<table style="border-collapse:separate;border-spacing:0 4px;width:100%;">'
        f'{"".join(transcript_html_rows)}</table>'
        if transcript_html_rows
        else '<p style="color:#94A3B8;font-size:12px;">No transcript captured.</p>'
    )

    rows_html = "".join([
        _kv_row("Ticket ID",          row["id"]),
        _kv_row("Created",            row["created_at"]),
        _kv_row("Language",           row.get("language", "en").upper()),
        _kv_row("User",               row.get("user_email") or row.get("user_id") or "anonymous"),
        _kv_row("Page",               row.get("page_url") or "—"),
        _kv_row("Session",            row.get("session_id") or "—"),
    ])
    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#F0F4F8;font-family:sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px;">
<table width="640" style="background:#fff;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
<tr><td style="background:#0B2545;padding:20px 24px;border-radius:10px 10px 0 0;">
<h2 style="color:#fff;margin:0;font-size:18px;">🆘 BidVex Admin — Live Support Escalation</h2>
<p style="color:#cbd5e1;margin:6px 0 0;font-size:12px;">A user has requested human assistance via the AI Core widget.</p></td></tr>
<tr><td style="padding:16px 24px;background:#F8FAFC;">
<table width="100%">{rows_html}</table>
</td></tr>
<tr><td style="padding:16px 24px;">
<h3 style="margin:0 0 6px;color:#0B2545;font-size:14px;">Problem (Q1)</h3>
<p style="background:#FEF2F2;border-left:4px solid #DC2626;padding:10px 14px;font-size:13px;
color:#7F1D1D;border-radius:4px;line-height:1.55;margin:0;">{_escape_html(row.get('problem',''))}</p>
<h3 style="margin:16px 0 6px;color:#0B2545;font-size:14px;">Details (Q2)</h3>
<p style="background:#EFF6FF;border-left:4px solid #2563EB;padding:10px 14px;font-size:13px;
color:#1E3A8A;border-radius:4px;line-height:1.55;margin:0;">{_escape_html(row.get('details') or '(none provided)')}</p>
<h3 style="margin:16px 0 6px;color:#0B2545;font-size:14px;">Conversation Transcript</h3>
{transcript_table}
</td></tr>
<tr><td style="background:#F8FAFC;padding:12px 24px;border-radius:0 0 10px 10px;text-align:center;color:#94A3B8;font-size:11px;">
BidVex Canada — Live Support Escalation</td></tr>
</table></td></tr></table></body></html>"""


def _escape_html(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _kv_row(k: str, v: Any) -> str:
    return (
        f'<tr><td style="padding:4px 12px 4px 0;color:#64748B;font-size:12px;font-weight:600;">{k}:</td>'
        f'<td style="padding:4px 0;color:#0F172A;font-size:12px;">{_escape_html(str(v))}</td></tr>'
    )


async def _email_admin(row: Dict[str, Any]) -> None:
    try:
        from services.admin_notifications import _send_admin_raw
        subject = (
            f"🆘 BidVex Live Support: "
            f"{(row.get('user_email') or row.get('user_id') or 'anonymous')[:48]}"
            f" — {(row.get('problem') or '')[:80]}"
        )
        await _send_admin_raw(subject, _render_context_packet_html(row))
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[escalation] admin email failed: {e}")


# ─── Endpoints ──────────────────────────────────────────────────────────

@router.post("/support/escalate")
async def create_escalation(
    body: EscalationCreateBody,
    request: Request,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Persist a Live Support Escalation ticket and email the admin
    team the full Context Packet (problem + details + recent transcript).

    Called by the AICoreSupportWidget when it detects a
    `[[BIDVEX_ESCALATION]]` marker in the assistant's reply.
    """
    db = get_db()

    # Strip the escalation marker out of any transcript content just in
    # case the frontend included it inside a message — defence in depth.
    transcript_clean: List[Dict[str, Any]] = []
    for m in body.transcript[-MAX_TRANSCRIPT_MESSAGES:]:
        content = re.sub(
            r"\[\[BIDVEX_ESCALATION\]\][\s\S]*?\[\[/BIDVEX_ESCALATION\]\]",
            "",
            m.content or "",
        ).strip()
        if not content:
            continue
        transcript_clean.append({
            "role":    (m.role or "").lower()[:20],
            "content": content[:MAX_TRANSCRIPT_CONTENT_CHARS],
            "ts":      m.ts,
        })

    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
        or ""
    )
    user_agent = request.headers.get("user-agent", "")[:500]

    row = {
        "id":           str(uuid.uuid4()),
        "user_id":      user.id,
        "user_email":   getattr(user, "email", None),
        "user_name":    getattr(user, "name", None) or getattr(user, "first_name", None),
        "user_role":    _role(user),
        "session_id":   body.session_id,
        "page_url":     body.page_url,
        "language":     "fr" if (body.language or "en").lower().startswith("fr") else "en",
        "problem":      body.problem.strip()[:MAX_PROBLEM_CHARS],
        "details":      body.details.strip()[:MAX_DETAILS_CHARS] if body.details else "",
        "transcript":   transcript_clean,
        "status":       "open",
        "admin_notes":  None,
        "created_at":   _now_iso(),
        "ip_address":   client_ip,
        "user_agent":   user_agent,
    }

    await db.support_escalations.insert_one(row)
    # iter321 — Broadcast to every admin SSE subscriber FIRST so the
    # in-app alert (2-tone chime + desktop notification + tab flash)
    # fires within ~50ms of the ticket landing.
    try:
        await broker.publish("new_ticket", {
            "id":          row["id"],
            "user_email":  row.get("user_email"),
            "user_id":     row.get("user_id"),
            "problem":     row["problem"][:160],
            "language":    row["language"],
            "created_at":  row["created_at"],
            "status":      row["status"],
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[escalation] broker publish failed: {e}")

    # Fire-and-forget email so a SendGrid hiccup never breaks the widget UX.
    try:
        await _email_admin(row)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[escalation] email-admin best-effort failed: {e}")

    row.pop("_id", None)
    return {
        "ticket_id":  row["id"],
        "status":     "open",
        "message_en": "Your ticket is open. An agent will reach out shortly.",
        "message_fr": "Votre demande est ouverte. Un agent vous contactera sous peu.",
    }


@router.get("/admin/support/escalations")
async def admin_list_escalations(
    user: User = Depends(require_admin),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    db = get_db()
    q: Dict[str, Any] = {}
    if status and status in ESCALATION_STATUSES:
        q["status"] = status
    if search:
        q["$or"] = [
            {"user_email": {"$regex": re.escape(search), "$options": "i"}},
            {"problem":    {"$regex": re.escape(search), "$options": "i"}},
            {"details":    {"$regex": re.escape(search), "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await db.support_escalations.count_documents(q)
    rows = await db.support_escalations.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return {"items": rows, "count": total, "page": page, "limit": limit}


@router.get("/admin/support/escalations/{ticket_id}")
async def admin_get_escalation(ticket_id: str,
                                 user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    row = await db.support_escalations.find_one({"id": ticket_id}, {"_id": 0})
    if not row:
        raise HTTPException(404, "ticket not found")
    return row


@router.patch("/admin/support/escalations/{ticket_id}/status")
async def admin_update_escalation_status(
    ticket_id: str,
    body: EscalationStatusBody,
    user: User = Depends(require_admin),
) -> Dict[str, Any]:
    if body.status not in ESCALATION_STATUSES:
        raise HTTPException(422, {
            "error":      "invalid_status",
            "allowed":    sorted(ESCALATION_STATUSES),
            "message_en": "Invalid status value.",
            "message_fr": "Valeur de statut invalide.",
        })
    db = get_db()
    existing = await db.support_escalations.find_one({"id": ticket_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "ticket not found")
    patch: Dict[str, Any] = {
        "status":             body.status,
        "status_updated_at":  _now_iso(),
        "status_updated_by":  getattr(user, "email", None),
    }
    if body.admin_notes is not None:
        patch["admin_notes"] = body.admin_notes
    await db.support_escalations.update_one(
        {"id": ticket_id}, {"$set": patch},
    )
    return {**existing, **patch}


@router.get("/admin/support/escalations/pending/count")
async def admin_pending_count(user: User = Depends(require_admin)) -> Dict[str, Any]:
    """Cheap badge counter — surfaces in the admin sidebar as a red
    notification dot when > 0."""
    db = get_db()
    n = await db.support_escalations.count_documents({"status": "open"})
    return {"open_count": int(n)}


# ─── iter321 — Real-time SSE stream for admin alerts ────────────────────

async def _resolve_admin_from_query_or_header(
    request: Request, token_qp: Optional[str],
) -> User:
    """EventSource cannot send Authorization headers, so we accept the
    JWT via either (a) the Authorization header (standard), (b) the
    session_token cookie (browser SSO), or (c) `?token=<jwt>` query
    string (EventSource fallback). All three resolve to the same User
    object. Raises 401/403 with the same envelope as REST endpoints."""
    import os as _os
    from jose import jwt as _jwt, JWTError as _JWTError
    from deps import db as _db, jwt_secret as _jwt_secret

    token: Optional[str] = None
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    elif request.headers.get("authorization", "").lower().startswith("bearer "):
        token = request.headers["authorization"].split(None, 1)[1].strip()
    elif token_qp:
        token = token_qp.strip()

    if not token:
        raise HTTPException(401, "auth required")

    jwt_secret = _jwt_secret
    try:
        payload = _jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except _JWTError:
        raise HTTPException(401, "invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "invalid token")
    user_doc = await _db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(401, "user not found")
    u = User(**user_doc)
    if _role(u) not in ADMIN_ROLES:
        raise HTTPException(403, "admin only")
    return u


@router.get("/admin/support/escalations/realtime/stream")
async def admin_escalations_stream(
    request: Request,
    token: Optional[str] = Query(None),
) -> StreamingResponse:
    """Server-Sent Events stream pushing `new_ticket` events to admins
    in real time. The first event is always `ready` so the client
    knows the connection is live; thereafter `new_ticket` lands as
    soon as a ticket is created; `: keepalive` comments fire every
    25s so proxies don't time out idle connections.

    Token query-param fallback is supported because EventSource cannot
    set Authorization headers — the frontend can send `?token=<jwt>`.
    """
    await _resolve_admin_from_query_or_header(request, token)

    queue = await broker.subscribe()

    async def event_iter():
        # Initial open-count snapshot so the client can immediately
        # reconcile state (in case it missed events while disconnected).
        try:
            db = get_db()
            open_count = await db.support_escalations.count_documents({"status": "open"})
        except Exception:  # noqa: BLE001
            open_count = 0
        yield (
            "event: ready\n"
            f"data: {json.dumps({'open_count': int(open_count), 'subscribers': broker.subscriber_count})}\n\n"
        )

        keepalive_seconds = 25
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=keepalive_seconds)
                    yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive comment so proxies don't kill the conn.
                    yield f": keepalive {_now_iso()}\n\n"
        finally:
            await broker.unsubscribe(queue)

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ─── iter322 — Interactive 2-way chat (admin reply + user reply) ─────────


class ReplyRequest(BaseModel):
    """Either an admin replying to a user OR a user adding context to their
    own ticket. The reply is appended to the ticket's transcript and broadcast
    via SSE to the other party in real time."""
    message: str = Field(..., min_length=1, max_length=2500)


@router.post("/admin/support/escalations/{ticket_id}/reply")
async def admin_reply_to_escalation(
    ticket_id: str,
    body: ReplyRequest,
    request: Request,
    user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Admin posts a reply on a Live Support ticket. Appends to transcript,
    broadcasts SSE to the user's open tabs + every admin's escalations console
    (so multi-admin scenarios stay in sync), and fires a best-effort SendGrid
    email with `Reply-To: service@bidvex.com`. Status is auto-set to
    `acknowledged` if it was still `open`."""
    db = get_db()
    ticket = await db.support_escalations.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(404, "ticket not found")
    if ticket.get("status") == "dismissed":
        raise HTTPException(409, "cannot reply to a dismissed ticket")

    reply_msg = {
        "role":        "admin",
        "content":     body.message.strip()[:2500],
        "ts":          _now_iso(),
        "admin_id":    user.id,
        "admin_email": getattr(user, "email", None),
    }
    new_status = ticket.get("status") or "open"
    if new_status == "open":
        new_status = "acknowledged"

    update = {
        "$push": {"transcript": reply_msg},
        "$set": {
            "status":             new_status,
            "status_updated_at":  reply_msg["ts"],
            "last_admin_reply_at": reply_msg["ts"],
            "has_unread_admin_reply": True,
        },
    }
    await db.support_escalations.update_one({"id": ticket_id}, update)
    refreshed = await db.support_escalations.find_one({"id": ticket_id}, {"_id": 0})

    # Broadcast to all admin tabs (so concurrent admins see the same convo).
    try:
        await broker.publish("ticket_updated", {
            "id":             ticket_id,
            "status":         new_status,
            "last_message":   reply_msg["content"][:160],
            "last_role":      "admin",
            "last_ts":        reply_msg["ts"],
        })
    except Exception:  # noqa: BLE001
        pass

    # Notify the user's open tabs (AIAssistant subscribes to this stream).
    try:
        target_user_id = ticket.get("user_id")
        if target_user_id:
            await broker.publish_to_user(target_user_id, "admin_reply", {
                "ticket_id":   ticket_id,
                "message":     reply_msg["content"],
                "ts":          reply_msg["ts"],
                "admin_email": "service@bidvex.com",
                "status":      new_status,
            })
    except Exception:  # noqa: BLE001
        pass

    # Best-effort email — never blocks the API. Uses Reply-To: service@bidvex.com
    # so the user can hit reply and land back in the support inbox.
    try:
        await _email_user_admin_reply(ticket, reply_msg["content"])
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[escalation reply] user email best-effort failed: {e}")

    return {
        "ok":      True,
        "ticket":  refreshed,
        "reply":   reply_msg,
    }


@router.post("/support/escalations/{ticket_id}/reply")
async def user_reply_to_escalation(
    ticket_id: str,
    body: ReplyRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """User adds a follow-up message on their own ticket — appended to the
    transcript and broadcast to admin tabs as ticket_updated."""
    db = get_db()
    ticket = await db.support_escalations.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(404, "ticket not found")
    if str(ticket.get("user_id")) != str(getattr(user, "id", "")):
        raise HTTPException(403, "this ticket does not belong to you")
    if ticket.get("status") in ("resolved", "dismissed"):
        raise HTTPException(409, "ticket already closed")

    reply_msg = {
        "role":    "user",
        "content": body.message.strip()[:2500],
        "ts":      _now_iso(),
        "user_id": user.id,
    }
    await db.support_escalations.update_one(
        {"id": ticket_id},
        {
            "$push": {"transcript": reply_msg},
            "$set":  {"last_user_reply_at": reply_msg["ts"], "has_unread_user_reply": True},
        },
    )
    refreshed = await db.support_escalations.find_one({"id": ticket_id}, {"_id": 0})
    try:
        await broker.publish("ticket_updated", {
            "id":           ticket_id,
            "status":       refreshed.get("status"),
            "last_message": reply_msg["content"][:160],
            "last_role":    "user",
            "last_ts":      reply_msg["ts"],
        })
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "ticket": refreshed, "reply": reply_msg}


async def _resolve_user_from_query_or_header(
    request: Request, token_qp: Optional[str],
) -> User:
    """Same dual-auth pattern as the admin SSE resolver but for normal users.
    Required because EventSource cannot send Authorization headers."""
    import os as _os
    from jose import jwt as _jwt, JWTError as _JWTError
    from deps import db as _db, jwt_secret as _jwt_secret

    token: Optional[str] = None
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    elif request.headers.get("authorization", "").lower().startswith("bearer "):
        token = request.headers["authorization"].split(None, 1)[1].strip()
    elif token_qp:
        token = token_qp.strip()
    if not token:
        raise HTTPException(401, "auth required")
    try:
        payload = _jwt.decode(token, _jwt_secret, algorithms=["HS256"])
    except _JWTError:
        raise HTTPException(401, "invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "invalid token")
    user_doc = await _db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(401, "user not found")
    return User(**user_doc)


@router.get("/support/escalations/user/stream")
async def user_escalations_stream(
    request: Request,
    token: Optional[str] = Query(None),
) -> StreamingResponse:
    """User-side SSE stream — pushes `admin_reply` events whenever an
    admin replies to one of THIS user's tickets. Used by AIAssistant
    to surface inline support replies as new chat bubbles."""
    user = await _resolve_user_from_query_or_header(request, token)
    queue = await broker.subscribe_user(user.id)

    async def event_iter():
        # Initial ready snapshot — also reports how many open tickets
        # this user has so the client can render a "1 ticket in progress"
        # pill if needed.
        try:
            db = get_db()
            open_count = await db.support_escalations.count_documents(
                {"user_id": user.id, "status": {"$in": ["open", "acknowledged"]}}
            )
        except Exception:  # noqa: BLE001
            open_count = 0
        yield (
            "event: ready\n"
            f"data: {json.dumps({'open_count': int(open_count)})}\n\n"
        )
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive {_now_iso()}\n\n"
        finally:
            await broker.unsubscribe_user(user.id, queue)

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ─── iter322 — Best-effort email when admin replies in-app ────────────────


async def _email_user_admin_reply(ticket: Dict[str, Any], admin_message: str) -> None:
    """Fire a 'we replied' email to the ticket's owner with Reply-To set to
    service@bidvex.com so a forward-email chain doesn't break the loop."""
    try:
        from services.email_service import get_email_service
        email_service = get_email_service()
        if not email_service.is_configured():
            return
        recipient = ticket.get("user_email")
        if not recipient:
            return
        ticket_id_short = (ticket.get("id") or "")[:8]
        problem_preview = (ticket.get("problem") or "")[:200]
        admin_preview = (admin_message or "")[:1500]
        is_fr = (ticket.get("language") or "en").startswith("fr")
        if is_fr:
            subject = f"BidVex Support — Réponse sur votre demande #{ticket_id_short}"
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
  <tr><td style="background:#1e3a8a;padding:24px 32px;text-align:center;">
    <h1 style="color:#ffffff;margin:0;font-size:24px;">BidVex Support</h1>
  </td></tr>
  <tr><td style="padding:32px;">
    <h2 style="color:#1e3a8a;margin:0 0 16px;">Réponse sur votre demande #{ticket_id_short}</h2>
    <p style="color:#374151;font-size:14px;line-height:1.6;background:#f9fafb;padding:10px 14px;border-left:3px solid #d1d5db;border-radius:0 6px 6px 0;">
      <strong>Votre problème :</strong> {problem_preview}
    </p>
    <p style="color:#374151;font-size:16px;line-height:1.6;"><strong>Notre réponse :</strong></p>
    <p style="color:#374151;font-size:15px;line-height:1.7;background:#fff7ed;padding:14px 18px;border-left:3px solid #f59e0b;border-radius:0 6px 6px 0;white-space:pre-wrap;">{admin_preview}</p>
    <p style="color:#6b7280;font-size:13px;line-height:1.5;">Pour répondre, ouvrez l'application BidVex et continuez la conversation dans votre fenêtre de chat — ou répondez à ce courriel.</p>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:16px 32px;text-align:center;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">&copy; BidVex — service@bidvex.com</p>
  </td></tr>
</table></td></tr></table></body></html>"""
        else:
            subject = f"BidVex Support — Reply on your ticket #{ticket_id_short}"
            html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
  <tr><td style="background:#1e3a8a;padding:24px 32px;text-align:center;">
    <h1 style="color:#ffffff;margin:0;font-size:24px;">BidVex Support</h1>
  </td></tr>
  <tr><td style="padding:32px;">
    <h2 style="color:#1e3a8a;margin:0 0 16px;">Reply on your ticket #{ticket_id_short}</h2>
    <p style="color:#374151;font-size:14px;line-height:1.6;background:#f9fafb;padding:10px 14px;border-left:3px solid #d1d5db;border-radius:0 6px 6px 0;">
      <strong>Your problem:</strong> {problem_preview}
    </p>
    <p style="color:#374151;font-size:16px;line-height:1.6;"><strong>Our reply:</strong></p>
    <p style="color:#374151;font-size:15px;line-height:1.7;background:#fff7ed;padding:14px 18px;border-left:3px solid #f59e0b;border-radius:0 6px 6px 0;white-space:pre-wrap;">{admin_preview}</p>
    <p style="color:#6b7280;font-size:13px;line-height:1.5;">To respond, open BidVex and continue the conversation in your chat panel — or simply reply to this email.</p>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:16px 32px;text-align:center;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">&copy; BidVex — service@bidvex.com</p>
  </td></tr>
</table></td></tr></table></body></html>"""
        # Send via the existing send_raw_html method. The underlying
        # email_service already sets `Reply-To: service@bidvex.com` by
        # default (see email_service.py lines 135 + 241).
        await email_service.send_raw_html(
            to=recipient, subject=subject, html_content=html, disable_tracking=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[escalation reply email] failed: {e}")


__all__ = ["router"]
