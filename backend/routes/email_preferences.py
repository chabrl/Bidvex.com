"""
Email Preferences (CASL Compliance) — iter175
==============================================
Category-level email opt-in/out so users can keep critical *transactional*
mail (which Canadian Anti-Spam Law makes mandatory anyway) while opting out
of *marketing* and/or *bidding alerts*.

Token model: same self-contained `URLSafeTimedSerializer` as unsubscribe.py
(scoped by EMAIL_PREF_SALT so the same email can't have its preference
token reused for unsubscribe and vice versa).

Categories
----------
  • marketing       — newsletters, promotions, partner emails (CASL-protected)
  • bidding_alerts  — outbid emails, ending-soon, new bids on watchlist
  • transactional   — winner emails, payment receipts, invoices (MANDATORY,
                       always sent regardless of preference)

The user document gets a single `email_preferences` dict:
    { marketing: bool, bidding_alerts: bool }
Transactional is implicit and never persisted.

Endpoints (all under /api/email-preferences)
--------------------------------------------
  POST /generate-token            — admin-only — mint a 30-day token for any email
  GET  /verify?token=...          — return masked email + current preferences
  POST /update                    — { token, preferences: {...} } persist user choice
"""
from datetime import datetime, timezone
from typing import Dict, Optional
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Request, Depends
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel, Field

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

# Re-use UNSUBSCRIBE_SECRET so we don't add another env-var; different salt
# means the tokens are NOT interchangeable with the unsubscribe ones.
EMAIL_PREF_SECRET = os.environ.get("UNSUBSCRIBE_SECRET", "")
EMAIL_PREF_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
EMAIL_PREF_SALT = "bidvex-email-preferences-v1"
FRONTEND_URL = (os.environ.get("FRONTEND_URL") or "https://bidvex.com").rstrip("/")

# Valid categories users can toggle. `transactional` is always-on.
TOGGLEABLE_CATEGORIES = {"marketing", "bidding_alerts"}
DEFAULT_PREFERENCES = {"marketing": True, "bidding_alerts": True}


def _serializer() -> URLSafeTimedSerializer:
    if not EMAIL_PREF_SECRET:
        raise RuntimeError(
            "UNSUBSCRIBE_SECRET env var is not set — refusing to generate or verify email-pref tokens."
        )
    return URLSafeTimedSerializer(EMAIL_PREF_SECRET, salt=EMAIL_PREF_SALT)


def generate_email_pref_token(email: str) -> str:
    """Mint a 30-day signed token tied to `email`."""
    normalized = (email or "").strip().lower()
    if not normalized:
        raise ValueError("email is required")
    return _serializer().dumps({"email": normalized, "ts": datetime.now(timezone.utc).isoformat()})


def _decode_email_pref_token(token: str) -> str:
    """Decode + validate. Raises HTTPException on failure."""
    try:
        payload = _serializer().loads(token, max_age=EMAIL_PREF_TOKEN_TTL_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="token_expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="token_invalid")
    except Exception as e:
        logger.error(f"[EMAIL_PREF] decode error: {e}")
        raise HTTPException(status_code=400, detail="token_invalid")

    if not isinstance(payload, dict) or not payload.get("email"):
        raise HTTPException(status_code=400, detail="token_invalid")
    return payload["email"].strip().lower()


def _mask_email(email: str) -> str:
    if "@" not in email:
        return (email or "")[:1] + "***"
    local, domain = email.split("@", 1)
    if not local:
        return "***@" + domain
    return local[:1] + "***@" + domain


def build_email_preferences_url(email: str) -> str:
    """Helper used by email-send pipeline to inject a one-link 'Manage preferences' URL."""
    token = generate_email_pref_token(email)
    return f"{FRONTEND_URL}/email-preferences?token={token}"


# ── Send-time guard ────────────────────────────────────────────
async def get_user_email_preferences(email: str) -> Dict[str, bool]:
    """Return the user's per-category preferences, defaulted to all-on for new users."""
    if not email:
        return DEFAULT_PREFERENCES.copy()
    db = get_db()
    user = await db.users.find_one(
        {"email": email.strip().lower()},
        {"_id": 0, "email_preferences": 1, "marketing_unsubscribed": 1},
    )
    prefs = DEFAULT_PREFERENCES.copy()
    if user and isinstance(user.get("email_preferences"), dict):
        for k in TOGGLEABLE_CATEGORIES:
            v = user["email_preferences"].get(k)
            if v is not None:
                prefs[k] = bool(v)
    # Honor legacy `marketing_unsubscribed=True` even if email_preferences is missing
    if user and user.get("marketing_unsubscribed"):
        prefs["marketing"] = False
    return prefs


async def is_category_suppressed(email: str, category: str) -> bool:
    """
    True if BidVex must NOT send this category to this email.
    `transactional` is NEVER suppressed (CASL-allowed).
    """
    if not email:
        return True
    if category == "transactional":
        return False
    if category not in TOGGLEABLE_CATEGORIES:
        # Unknown category — fail open for safety (treat as marketing-equivalent)
        category = "marketing"
    prefs = await get_user_email_preferences(email)
    return not prefs.get(category, True)


# ── Router ─────────────────────────────────────────────────────
email_preferences_router = APIRouter(prefix="/email-preferences", tags=["Email Preferences"])


class EmailPreferencesUpdate(BaseModel):
    token: str
    preferences: Dict[str, bool] = Field(default_factory=dict)


@email_preferences_router.get("/verify")
async def verify_email_preferences_token(token: str = ""):
    """Decode token + return masked email and current per-category preferences."""
    if not token:
        raise HTTPException(status_code=400, detail="token_missing")
    email = _decode_email_pref_token(token)
    prefs = await get_user_email_preferences(email)
    return {
        "email_masked": _mask_email(email),
        "preferences": prefs,
        "categories": [
            {
                "key": "marketing",
                "label_en": "Marketing & Promotions",
                "label_fr": "Marketing et promotions",
                "description_en": "Newsletters, partner offers, new feature announcements.",
                "description_fr": "Infolettres, offres partenaires, annonces de nouveautés.",
                "toggleable": True,
            },
            {
                "key": "bidding_alerts",
                "label_en": "Bidding Alerts",
                "label_fr": "Alertes d'enchères",
                "description_en": "Outbid notices, ending-soon reminders, watchlist updates.",
                "description_fr": "Avis de surenchère, rappels de fin imminente, mises à jour de la liste de surveillance.",
                "toggleable": True,
            },
            {
                "key": "transactional",
                "label_en": "Transactional (Required)",
                "label_fr": "Transactionnel (Requis)",
                "description_en": "Winner emails, payment receipts, invoices, account security. Required by Canadian law (CASL §6(6)).",
                "description_fr": "Courriels de gagnant, reçus de paiement, factures, sécurité du compte. Requis par la Loi canadienne anti-pourriel (LCAP §6(6)).",
                "toggleable": False,
            },
        ],
    }


@email_preferences_router.post("/update")
async def update_email_preferences(payload: EmailPreferencesUpdate, request: Request):
    """Persist the user's per-category email preferences."""
    email = _decode_email_pref_token(payload.token)
    db = get_db()
    now = datetime.now(timezone.utc)

    # Sanitize: only honor toggleable categories from the payload
    incoming = payload.preferences or {}
    sanitized: Dict[str, bool] = {}
    for k in TOGGLEABLE_CATEGORIES:
        if k in incoming:
            sanitized[k] = bool(incoming[k])

    # Merge with existing prefs so partial updates work
    existing = await get_user_email_preferences(email)
    merged = {**existing, **sanitized}

    update_doc = {
        "$set": {
            "email_preferences": merged,
            "email_preferences_updated_at": now,
            "email_preferences_updated_ip": (request.client.host if request.client else None),
        },
        "$setOnInsert": {
            "id": str(uuid.uuid4()),
            "email": email,
            "created_at": now,
            "is_contact_only": True,
        },
    }

    # If marketing was toggled OFF, also flip the legacy flag + write to suppressions
    if merged.get("marketing") is False:
        update_doc["$set"]["marketing_unsubscribed"] = True
        update_doc["$set"]["marketing_unsubscribed_at"] = now
        update_doc["$set"]["marketing_unsubscribed_source"] = "preferences-page"
        await db.email_suppressions.update_one(
            {"email": email},
            {"$set": {"email": email, "unsubscribed_at": now, "source": "preferences-page"}},
            upsert=True,
        )
    elif merged.get("marketing") is True:
        # Re-opt-in: clear suppression so user receives marketing again
        update_doc["$set"]["marketing_unsubscribed"] = False
        update_doc.setdefault("$unset", {})
        update_doc["$unset"]["marketing_unsubscribed_at"] = ""
        update_doc["$unset"]["marketing_unsubscribed_source"] = ""
        await db.email_suppressions.delete_one({"email": email})

    await db.users.update_one({"email": email}, update_doc, upsert=True)

    return {
        "status": "success",
        "email_masked": _mask_email(email),
        "preferences": merged,
    }


# ── Admin-only debug helper ────────────────────────────────────
@email_preferences_router.get("/generate-token")
async def admin_generate_email_pref_token(email: str, _: User = Depends(require_admin)):
    """Admin-only: mint a 30-day token for any email (QA convenience)."""
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="invalid_email")
    url = build_email_preferences_url(normalized)
    return {
        "email": normalized,
        "url": url,
        "expires_in_days": EMAIL_PREF_TOKEN_TTL_SECONDS // 86400,
    }
