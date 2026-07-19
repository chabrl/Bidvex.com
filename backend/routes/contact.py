"""
iter363 — Contact form submission endpoint.

`POST /api/contact/submit` accepts a bilingual contact-form payload and
routes the message to the correct team inbox via SendGrid. Client no
longer needs a working mail client (mailto: fallback still available in
`ContactUsPage.jsx` for offline resilience).

Rate-limit friendly: no authentication required so the public contact
form works for unauthenticated visitors, but every submission is logged
to `contact_submissions` for audit + spam analysis.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator

logger = logging.getLogger(__name__)

contact_router = APIRouter(prefix="/api/contact", tags=["contact"])


# ─── Subject → team email map ──────────────────────────────────────────
# Mirrors `ContactUsPage.jsx.COPY.en.teams` — keep in sync.
TEAM_EMAIL_MAP: Dict[str, str] = {
    "office":      "office@bidvex.com",
    "support":     "service@bidvex.com",
    "vehicles":    "vehicles@bidvex.com",
    "brokers":     "broker@bidvex.com",
    "resolutions": "dispute@bidvex.com",
    "payment":     "payment@bidvex.com",
    "privacy":     "privacy@bidvex.com",
    "marketing":   "marketing@bidvex.com",
    "careers":     "careers@bidvex.com",
    "contractors": "contractor@bidvex.com",  # iter362 addition
}
DEFAULT_FALLBACK_EMAIL = "office@bidvex.com"


class ContactSubmission(BaseModel):
    name:     str = Field(..., min_length=1, max_length=120)
    email:    EmailStr
    team_id:  str = Field(..., min_length=1, max_length=32)
    message:  str = Field(..., min_length=10, max_length=5000)
    lang:     str = Field(default="en", pattern="^(en|fr)$")

    @field_validator("team_id")
    @classmethod
    def team_id_must_be_known(cls, v: str) -> str:
        if v not in TEAM_EMAIL_MAP:
            raise ValueError(f"Unknown team_id: {v!r} — expected one of {list(TEAM_EMAIL_MAP)}")
        return v

    @field_validator("message")
    @classmethod
    def message_no_url_spam(cls, v: str) -> str:
        # Simple spam heuristic: >4 URLs = probably automated form-fill.
        url_count = len(re.findall(r"https?://", v, flags=re.IGNORECASE))
        if url_count > 4:
            raise ValueError("Message contains too many URLs")
        return v


@contact_router.post("/submit")
async def submit_contact_form(
    payload: ContactSubmission,
    request: Request,
):
    """Route the contact form to the correct team email via SendGrid.

    Response schema:
      { ok: true, team: <team_id>, routed_to: <email>, submission_id: <uuid> }
    """
    target_email = TEAM_EMAIL_MAP.get(payload.team_id, DEFAULT_FALLBACK_EMAIL)
    now = datetime.now(timezone.utc)

    # Compose email envelope
    subject_prefix = "[BidVex Contact]" if payload.lang == "en" else "[Contact BidVex]"
    email_subject = f"{subject_prefix} {payload.team_id.title()} — {payload.name}"
    email_body_lines = [
        f"From:    {payload.name} <{payload.email}>",
        f"Team:    {payload.team_id} ({target_email})",
        f"Lang:    {payload.lang}",
        f"Time:    {now.isoformat()}",
        f"IP:      {(request.client.host if request.client else '?')}",
        f"UA:      {(request.headers.get('user-agent') or '')[:200]}",
        "",
        "─── MESSAGE " + "─" * 65,
        payload.message,
        "─" * 76,
        "",
        "— Sent via bidvex.com contact form (iter363)",
    ]
    email_body = "\n".join(email_body_lines)

    # Persist to DB for audit + spam analysis
    import uuid
    submission_id = str(uuid.uuid4())
    try:
        from deps import get_db
        db = get_db()
        await db.contact_submissions.insert_one({
            "_id":          submission_id,
            "name":         payload.name,
            "email":        payload.email,
            "team_id":      payload.team_id,
            "routed_to":    target_email,
            "message":      payload.message,
            "lang":         payload.lang,
            "ip":           request.client.host if request.client else None,
            "user_agent":   (request.headers.get("user-agent") or "")[:500],
            "created_at":   now.isoformat(),
            "delivery_status": "queued",
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[contact/submit] db persist failed (non-fatal): {exc}")

    # Send via SendGrid
    delivered = False
    delivery_error: Optional[str] = None
    api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com").strip()

    if not api_key:
        delivery_error = "SENDGRID_API_KEY not configured — logged only"
        logger.warning(f"[contact/submit] {delivery_error}")
    else:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, ReplyTo

            mail = Mail(
                from_email=from_email,
                to_emails=target_email,
                subject=email_subject,
                plain_text_content=email_body,
            )
            # Reply-To goes to the submitter's real address so the recipient
            # can hit reply and land in the customer's inbox directly.
            mail.reply_to = ReplyTo(payload.email, payload.name)
            sg = SendGridAPIClient(api_key)
            r = sg.send(mail)
            if 200 <= r.status_code < 300:
                delivered = True
            else:
                delivery_error = f"SendGrid returned {r.status_code}"
                logger.error(f"[contact/submit] {delivery_error}: {r.body}")
        except Exception as exc:  # noqa: BLE001
            delivery_error = str(exc)[:200]
            logger.error(f"[contact/submit] SendGrid send failed: {exc}")

    # Update DB with delivery status
    try:
        from deps import get_db
        db = get_db()
        await db.contact_submissions.update_one(
            {"_id": submission_id},
            {"$set": {"delivery_status": "delivered" if delivered else "failed",
                      "delivery_error": delivery_error}},
        )
    except Exception:
        pass

    if not delivered and delivery_error and "not configured" not in delivery_error:
        # Genuine send failure — surface to client so they can fall back
        # to the mailto: link inside the ContactUsPage.jsx form.
        raise HTTPException(status_code=502, detail={
            "ok":       False,
            "error":    "email_delivery_failed",
            "detail":   delivery_error,
        })

    logger.info(f"[contact/submit] {payload.team_id} → {target_email} "
                f"delivered={delivered} id={submission_id}")
    return {
        "ok":            True,
        "team":          payload.team_id,
        "routed_to":     target_email,
        "submission_id": submission_id,
        "delivered":     delivered,
    }


__all__ = ["contact_router", "TEAM_EMAIL_MAP"]
