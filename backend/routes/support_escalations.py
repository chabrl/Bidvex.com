"""
iter320 — Live Support Escalation Protocol.

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
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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


__all__ = ["router"]
