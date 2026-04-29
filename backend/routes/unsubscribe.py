"""
Custom Unsubscribe Flow — Token utilities + Router

Endpoints:
  GET  /api/unsubscribe/verify?token=...   — decode + return masked email + status
  POST /api/unsubscribe/confirm            — one-click confirm → DB + SendGrid API

Tokens are self-contained (no DB row needed at generation time) via
itsdangerous.URLSafeTimedSerializer, scoped by UNSUBSCRIBE_SECRET.

SendGrid Dashboard Settings (manual, one-time):
  1. Mail Settings → Subscription Tracking → **OFF**
     (otherwise SendGrid rewrites our unsubscribe link to their CDN)
  2. Mail Settings → Event Webhook → POST URL: https://bidvex.com/api/sendgrid/event-webhook
     Events: unsubscribe, group_unsubscribe, spamreport, bounce, dropped
     Toggle Signed Event Webhook → ON (SENDGRID_EVENT_WEBHOOK_VERIFICATION_KEY stored in .env)
"""
from datetime import datetime, timezone
from typing import Dict
import logging
import os
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request, Depends
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────
UNSUBSCRIBE_SECRET = os.environ.get("UNSUBSCRIBE_SECRET", "")
UNSUBSCRIBE_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
UNSUBSCRIBE_SALT = "bidvex-unsubscribe-v1"
FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "https://bidvex.com").rstrip("/")

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDGRID_SUPPRESSIONS_URL = "https://api.sendgrid.com/v3/asm/suppressions/global"


def _serializer() -> URLSafeTimedSerializer:
    """Lazy serializer — safe to instantiate on every call (cheap)."""
    if not UNSUBSCRIBE_SECRET:
        raise RuntimeError(
            "UNSUBSCRIBE_SECRET env var is not set — refusing to generate or verify tokens."
        )
    return URLSafeTimedSerializer(UNSUBSCRIBE_SECRET, salt=UNSUBSCRIBE_SALT)


def generate_unsubscribe_token(email: str) -> str:
    """Create a self-contained 30-day token tied to `email`."""
    normalized = (email or "").strip().lower()
    if not normalized:
        raise ValueError("email is required")
    return _serializer().dumps({"email": normalized})


def _decode_unsubscribe_token(token: str) -> str:
    """Decode + validate. Raises HTTPException on failure."""
    try:
        payload = _serializer().loads(token, max_age=UNSUBSCRIBE_TOKEN_TTL_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="token_expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="token_invalid")
    except Exception as e:
        logger.error(f"[UNSUBSCRIBE] decode error: {e}")
        raise HTTPException(status_code=400, detail="token_invalid")

    if not isinstance(payload, dict) or not payload.get("email"):
        raise HTTPException(status_code=400, detail="token_invalid")
    return payload["email"].strip().lower()


def _mask_email(email: str) -> str:
    """`alice@example.com` → `a***@example.com` (preserve last chars at discretion)."""
    if "@" not in email:
        return email[:1] + "***"
    local, domain = email.split("@", 1)
    if not local:
        return "***@" + domain
    return local[:1] + "***@" + domain


def build_unsubscribe_urls(email: str) -> Dict[str, str]:
    """Helper used by the email-send pipeline to inject EN + FR links."""
    token = generate_unsubscribe_token(email)
    return {
        "en": f"{FRONTEND_URL}/unsubscribe?token={token}&lang=en",
        "fr": f"{FRONTEND_URL}/desabonnement?token={token}&lang=fr",
    }


# ── Router ─────────────────────────────────────────────────────
unsubscribe_router = APIRouter(prefix="/unsubscribe", tags=["Unsubscribe"])


@unsubscribe_router.get("/verify")
async def verify_unsubscribe_token(token: str = ""):
    """Decode + return masked email and current subscription status."""
    if not token:
        raise HTTPException(status_code=400, detail="token_missing")
    email = _decode_unsubscribe_token(token)
    db = get_db()
    user = await db.users.find_one({"email": email}, {"_id": 0, "marketing_unsubscribed": 1})
    return {
        "email_masked": _mask_email(email),
        "already_unsubscribed": bool(user and user.get("marketing_unsubscribed")),
    }


class ConfirmRequest(BaseModel):
    token: str


@unsubscribe_router.post("/confirm")
async def confirm_unsubscribe(payload: ConfirmRequest, request: Request):
    """Mark the recipient as unsubscribed in MongoDB + SendGrid global suppressions."""
    email = _decode_unsubscribe_token(payload.token)
    db = get_db()
    now = datetime.now(timezone.utc)

    # Check current state
    existing = await db.users.find_one({"email": email}, {"_id": 0, "marketing_unsubscribed": 1})
    if existing and existing.get("marketing_unsubscribed"):
        return {"status": "already_done", "email_masked": _mask_email(email)}

    # Upsert: users collection may not have the recipient if they're a
    # contact-only entry from an imported list.
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "marketing_unsubscribed": True,
                "marketing_unsubscribed_at": now,
                "marketing_unsubscribed_source": "link",
                "marketing_unsubscribed_ip": (request.client.host if request.client else None),
            },
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "email": email,
                "created_at": now,
                "is_contact_only": True,
            },
        },
        upsert=True,
    )

    # Also write to a dedicated suppression list — fast lookup for send-time guard
    await db.email_suppressions.update_one(
        {"email": email},
        {
            "$set": {
                "email": email,
                "unsubscribed_at": now,
                "source": "link",
            }
        },
        upsert=True,
    )

    # Propagate to SendGrid global unsubscribe list
    if SENDGRID_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    SENDGRID_SUPPRESSIONS_URL,
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"recipient_emails": [email]},
                )
                if r.status_code not in (200, 201):
                    logger.warning(
                        f"[UNSUBSCRIBE] SendGrid suppression returned {r.status_code}: {r.text[:200]}"
                    )
        except Exception as e:
            # Do NOT fail the user flow if SendGrid API is momentarily down —
            # DB state is the source of truth; a scheduled reconciliation job
            # can retry SendGrid.
            logger.error(f"[UNSUBSCRIBE] SendGrid API call failed: {type(e).__name__}: {e}")

    return {"status": "success", "email_masked": _mask_email(email)}


# ── Send-time guard ────────────────────────────────────────────
async def is_marketing_suppressed(email: str) -> bool:
    """Return True if the recipient should NOT receive marketing emails.
    Used by email-send helpers before calling SendGrid.
    """
    if not email:
        return True
    normalized = email.strip().lower()
    db = get_db()
    # Fast path — dedicated suppression table
    hit = await db.email_suppressions.find_one({"email": normalized}, {"_id": 0, "email": 1})
    if hit:
        return True
    # Fallback — user doc flag (webhook-set)
    user = await db.users.find_one({"email": normalized}, {"_id": 0, "marketing_unsubscribed": 1})
    return bool(user and user.get("marketing_unsubscribed"))



# ── Admin-only debug helper ────────────────────────────────────
# REMOVE BEFORE PRODUCTION GA (or leave — the `require_admin` gate makes it
# safe; only super_admin / admin role can hit it). Useful for QA testing the
# unsubscribe flow end-to-end without going through the email send pipeline.
@unsubscribe_router.get("/generate-test-link")
async def generate_test_link(email: str, _: User = Depends(require_admin)):
    """
    Admin-only: mint a 30-day signed unsubscribe token for any email.
    Returns the EN + FR URLs so you can paste them into a browser to test the
    full verify → confirm flow without needing SendGrid in the loop.

    Example:
      curl -H "Authorization: Bearer <admin-jwt>" \
        "https://bidvex.com/api/unsubscribe/generate-test-link?email=test@example.com"
    """
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="invalid_email")
    urls = build_unsubscribe_urls(normalized)
    return {
        "email": normalized,
        "url_en": urls["en"],
        "url_fr": urls["fr"],
        "expires_in_days": UNSUBSCRIBE_TOKEN_TTL_SECONDS // 86400,
    }
