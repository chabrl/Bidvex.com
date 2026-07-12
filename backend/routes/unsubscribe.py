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
from typing import Dict, Optional
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
    """Helper used by the email-send pipeline to inject EN + FR links.

    iter309 D4 — Canonical URL format:
        https://bidvex.com/unsubscribe?token=<signed>&lang=<en|fr>
    Both EN and FR resolve to the same `/unsubscribe` SPA route; the
    `lang` query param drives the bilingual rendering. Legacy `/desabonnement`
    route remains alive via a frontend alias for older campaign emails
    already in inboxes.
    """
    token = generate_unsubscribe_token(email)
    return {
        "en": f"{FRONTEND_URL}/unsubscribe?token={token}&lang=en",
        "fr": f"{FRONTEND_URL}/unsubscribe?token={token}&lang=fr",
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
    # iter310 — optional bilingual hint for the Unsubscribe Audit Trail. Falls
    # back to `en` (or whatever the JWT payload carries for external tokens).
    lang: Optional[str] = None


# iter346 P0 — Admin unsubscribe guard. Administrative accounts
# (role=admin | super_admin) must never be able to unsubscribe from
# platform notifications — a stale unsubscribe click on 2026-07-02
# for charbel911@gmail.com silently blocked ALL admin alerts platform-wide
# for a week. Prevention: refuse the token, log with a red flag, and
# return a bilingual explanatory error.
async def _is_admin_email(db, email: str) -> bool:
    """Return True if `email` belongs to a user with role admin/super_admin."""
    if not email:
        return False
    user = await db.users.find_one(
        {"email": email.strip().lower()}, {"_id": 0, "role": 1},
    )
    return bool(user and user.get("role") in ("admin", "super_admin"))


ADMIN_UNSUBSCRIBE_REFUSAL = {
    "error":      "admin_unsubscribe_blocked",
    "message_en": ("Administrative accounts cannot be unsubscribed from "
                   "platform notifications. Contact IT if you believe this "
                   "is an error."),
    "message_fr": ("Les comptes administratifs ne peuvent pas être désabonnés "
                   "des notifications de la plateforme. Contactez le service "
                   "informatique si vous croyez qu'il s'agit d'une erreur."),
}


@unsubscribe_router.post("/confirm")
async def confirm_unsubscribe(payload: ConfirmRequest, request: Request):
    """Mark the recipient as unsubscribed in MongoDB + SendGrid global suppressions."""
    email = _decode_unsubscribe_token(payload.token)
    db = get_db()
    now = datetime.now(timezone.utc)

    # iter346 P0 — hard-block admin unsubscribe attempts.
    if await _is_admin_email(db, email):
        logger.warning(
            f"[UNSUBSCRIBE] BLOCKED admin unsubscribe attempt for {email} "
            f"from ip={request.client.host if request.client else 'n/a'}"
        )
        # Best-effort audit row so ops can see the attempts.
        try:
            await db.unsubscribe_events.insert_one({
                "id":              str(uuid.uuid4()),
                "email":           email,
                "event":           "blocked_admin_attempt",
                "source":          "platform",
                "token_type":      "itsdangerous",
                "unsubscribed_at": now,
                "ip":              (request.client.host if request.client else None),
                "user_agent":      (request.headers.get("user-agent") if hasattr(request, "headers") else None),
            })
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=403, detail=ADMIN_UNSUBSCRIBE_REFUSAL)

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


# ── Resubscribe (re-opt-in) ────────────────────────────────────
# Uses the SAME signed token as unsubscribe — links from emails or success
# pages are reusable for either direction since they only encode the email.
@unsubscribe_router.get("/resubscribe-verify")
async def verify_resubscribe_token(token: str = ""):
    """Decode + return masked email and current subscription status."""
    if not token:
        raise HTTPException(status_code=400, detail="token_missing")
    email = _decode_unsubscribe_token(token)
    db = get_db()
    user = await db.users.find_one({"email": email}, {"_id": 0, "marketing_unsubscribed": 1})
    suppressed = await db.email_suppressions.find_one({"email": email}, {"_id": 0, "email": 1})
    is_suppressed = bool((user and user.get("marketing_unsubscribed")) or suppressed)
    return {
        "email_masked": _mask_email(email),
        "is_subscribed": not is_suppressed,
    }


@unsubscribe_router.post("/resubscribe-confirm")
async def confirm_resubscribe(payload: ConfirmRequest, request: Request):
    """Re-opt-in: clear DB suppression + remove from SendGrid global list."""
    email = _decode_unsubscribe_token(payload.token)
    db = get_db()
    now = datetime.now(timezone.utc)

    # Already subscribed?
    suppressed = await db.email_suppressions.find_one({"email": email}, {"_id": 0, "email": 1})
    user_flag = await db.users.find_one({"email": email}, {"_id": 0, "marketing_unsubscribed": 1})
    if not suppressed and not (user_flag and user_flag.get("marketing_unsubscribed")):
        return {"status": "already_subscribed", "email_masked": _mask_email(email)}

    # 1. Clear the dedicated suppression list (fast-path source of truth)
    await db.email_suppressions.delete_one({"email": email})

    # 2. Flip the user-doc flag (don't upsert — only update if user exists)
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "marketing_unsubscribed": False,
                "marketing_resubscribed_at": now,
                "marketing_resubscribed_source": "link",
                "marketing_resubscribed_ip": (request.client.host if request.client else None),
            },
            "$unset": {
                "marketing_unsubscribed_at": "",
                "marketing_unsubscribed_source": "",
                "marketing_unsubscribed_group_id": "",
            },
        },
    )

    # 3. Propagate to SendGrid — remove from global suppressions
    if SENDGRID_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.delete(
                    f"{SENDGRID_SUPPRESSIONS_URL}/{email}",
                    headers={"Authorization": f"Bearer {SENDGRID_API_KEY}"},
                )
                # 204 = removed, 404 = wasn't in list (still success), anything else = warn
                if r.status_code not in (200, 204, 404):
                    logger.warning(
                        f"[RESUBSCRIBE] SendGrid DELETE returned {r.status_code}: {r.text[:200]}"
                    )
        except Exception as e:
            # DB is source of truth — never fail the user flow on a SG hiccup.
            logger.error(f"[RESUBSCRIBE] SendGrid API call failed: {type(e).__name__}: {e}")

    return {"status": "success", "email_masked": _mask_email(email)}


# ── iter309 D4 — Unified auto-verify / auto-confirm ────────────
# Standardized unsubscribe handler that decodes EITHER:
#   • platform itsdangerous tokens (issued by build_unsubscribe_urls)
#   • external campaign JWT tokens (issued by external_email.make_unsubscribe_token)
# so a single canonical /unsubscribe?token=...&lang=... URL works across
# every marketing/campaign email type. Sets `email_unsubscribed=true` on
# the user document + writes to the suppression collections.

def _decode_any_unsubscribe_token(token: str) -> Dict[str, str]:
    """Try platform itsdangerous decoder first, fall back to external JWT.

    Returns a dict: {email, campaign_id?, source: "platform"|"external"}.
    Raises HTTPException(400) on any failure.
    """
    # 1. Platform itsdangerous attempt.
    try:
        email = _decode_unsubscribe_token(token)
        return {"email": email, "campaign_id": None, "source": "platform"}
    except HTTPException:
        pass

    # 2. External JWT attempt.
    try:
        from services.external_email import decode_unsubscribe_token as decode_jwt
        payload = decode_jwt(token)
        if not isinstance(payload, dict) or payload.get("type") != "external_unsub":
            raise ValueError("invalid_token_type")
        email = (payload.get("email") or "").strip().lower()
        if not email:
            raise ValueError("no_email_in_token")
        return {
            "email":       email,
            "campaign_id": payload.get("campaign_id"),
            "source":      "external",
        }
    except Exception as exc:
        logger.warning(f"[UNSUBSCRIBE auto] JWT decode failed: {exc}")
        raise HTTPException(status_code=400, detail="token_invalid")


@unsubscribe_router.get("/auto-verify")
async def auto_verify_unsubscribe_token(token: str = ""):
    """Decode any platform / external token + return masked email + status."""
    if not token:
        raise HTTPException(status_code=400, detail="token_missing")
    decoded = _decode_any_unsubscribe_token(token)
    email = decoded["email"]
    db = get_db()
    user = await db.users.find_one(
        {"email": email},
        {"_id": 0, "marketing_unsubscribed": 1, "email_unsubscribed": 1},
    )
    suppressed_platform = bool(user and (user.get("marketing_unsubscribed") or user.get("email_unsubscribed")))
    suppressed_external = await db.external_email_suppressions.find_one(
        {"email": email}, {"_id": 0, "email": 1},
    )
    return {
        "email_masked":         _mask_email(email),
        "already_unsubscribed": bool(suppressed_platform or suppressed_external),
        "source":               decoded["source"],
    }


@unsubscribe_router.post("/auto-confirm")
async def auto_confirm_unsubscribe(payload: ConfirmRequest, request: Request):
    """Standardize unsubscribe across platform + external campaign tokens.

    iter309 D4:
      • Sets `email_unsubscribed=true` (canonical) + `marketing_unsubscribed=true`
        (legacy compat) on the user document (upserts a contact-only row if no
        user exists).
      • Writes to `email_suppressions` (platform) + `external_email_suppressions`
        (campaigns) so every send-time guard agrees.
      • Increments `analytics.unsubscribed` on the source campaign when the token
        is an external JWT carrying a `campaign_id`.
      • Pushes the suppression to the SendGrid global list (best-effort).
    """
    decoded = _decode_any_unsubscribe_token(payload.token)
    email = decoded["email"]
    campaign_id = decoded.get("campaign_id")
    source = decoded["source"]
    db = get_db()
    now = datetime.now(timezone.utc)

    # iter346 P0 — hard-block admin unsubscribe attempts (see /confirm).
    if await _is_admin_email(db, email):
        logger.warning(
            f"[UNSUBSCRIBE auto] BLOCKED admin unsubscribe attempt for {email} "
            f"(source={source}, campaign_id={campaign_id}) "
            f"from ip={request.client.host if request.client else 'n/a'}"
        )
        try:
            await db.unsubscribe_events.insert_one({
                "id":              str(uuid.uuid4()),
                "email":           email,
                "campaign_id":     campaign_id,
                "event":           "blocked_admin_attempt",
                "source":          source,
                "token_type":      "itsdangerous" if source == "platform" else "jwt",
                "unsubscribed_at": now,
                "ip":              (request.client.host if request.client else None),
                "user_agent":      (request.headers.get("user-agent") if hasattr(request, "headers") else None),
            })
        except Exception:  # noqa: BLE001
            pass
        raise HTTPException(status_code=403, detail=ADMIN_UNSUBSCRIBE_REFUSAL)

    # Short-circuit if already unsubscribed.
    user = await db.users.find_one(
        {"email": email},
        {"_id": 0, "marketing_unsubscribed": 1, "email_unsubscribed": 1},
    )
    already = bool(user and (user.get("marketing_unsubscribed") or user.get("email_unsubscribed")))

    if not already:
        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "email_unsubscribed":          True,
                    "email_unsubscribed_at":       now,
                    "email_unsubscribed_source":   source,
                    "marketing_unsubscribed":      True,
                    "marketing_unsubscribed_at":   now,
                    "marketing_unsubscribed_source": "link",
                    "marketing_unsubscribed_ip": (request.client.host if request.client else None),
                },
                "$setOnInsert": {
                    "id":               str(uuid.uuid4()),
                    "email":            email,
                    "created_at":       now,
                    "is_contact_only":  True,
                },
            },
            upsert=True,
        )

    # iter310 — Unsubscribe Audit Trail. Write one row per *successful*
    # unsubscribe attempt so admins can audit deliverability spikes per
    # campaign / source / token-type. Even already-unsubscribed re-clicks
    # are logged (as `repeat_click`) so we can see suppression-list drift.
    user_doc = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    audit_row = {
        "id":              str(uuid.uuid4()),
        "user_id":         (user_doc or {}).get("id"),
        "email":           email,
        "campaign_id":     campaign_id,
        "source":          "platform" if source == "platform" else "external_campaign",
        "unsubscribed_at": now,
        "token_type":      "itsdangerous" if source == "platform" else "jwt",
        "lang":            ((payload.lang if hasattr(payload, "lang") and payload.lang else None) or "en").lower(),
        "event":           "repeat_click" if already else "unsubscribed",
        "ip":              (request.client.host if request.client else None),
        "user_agent":      (request.headers.get("user-agent") if hasattr(request, "headers") else None),
    }
    try:
        await db.unsubscribe_events.insert_one(audit_row)
    except Exception as audit_err:
        logger.warning(f"[UNSUBSCRIBE audit] insert failed (non-fatal): {audit_err}")

    # Platform suppression list (fast lookup for send-time guard).
    await db.email_suppressions.update_one(
        {"email": email},
        {
            "$set": {
                "email":           email,
                "unsubscribed_at": now,
                "source":          source,
            }
        },
        upsert=True,
    )

    # External campaign suppression list — keeps external sender in sync.
    await db.external_email_suppressions.update_one(
        {"email": email},
        {
            "$setOnInsert": {
                "email":          email,
                "reason":         "unsubscribe",
                "campaign_id":    campaign_id,
                "suppressed_at":  now.isoformat(),
                "source":         source,
            }
        },
        upsert=True,
    )

    # Campaign analytics tick (external campaigns).
    if campaign_id:
        try:
            await db.external_email_campaigns.update_one(
                {"id": campaign_id},
                {
                    "$inc": {"analytics.unsubscribed": 1},
                    "$set": {"analytics.last_updated_at": now.isoformat()},
                },
            )
        except Exception as exc:
            logger.warning(f"[UNSUBSCRIBE auto] campaign analytics update failed: {exc}")

    # Propagate to SendGrid global suppressions (best effort).
    if SENDGRID_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    SENDGRID_SUPPRESSIONS_URL,
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type":  "application/json",
                    },
                    json={"recipient_emails": [email]},
                )
                if r.status_code not in (200, 201):
                    logger.warning(
                        f"[UNSUBSCRIBE auto] SendGrid suppression returned "
                        f"{r.status_code}: {r.text[:200]}"
                    )
        except Exception as exc:
            logger.error(f"[UNSUBSCRIBE auto] SendGrid API call failed: {exc}")

    return {
        "status":       "already_done" if already else "success",
        "email_masked": _mask_email(email),
        "source":       source,
    }


# ── Admin-only debug helper ────────────────────────────────────
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
