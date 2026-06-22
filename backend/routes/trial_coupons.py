"""
iter274 — Partner Trial Coupons.

A coupon represents a *pre-issued* free trial that an unregistered
auctioneer / dealer / broker / storage operator can redeem at signup
without ever paying the partner annual fee. Coupons are minted by
BidVex staff (one-off via the Admin Promotions Engine) or in bulk
attached to an external acquisition campaign.

Schema (`partner_trial_coupons` collection):

    {
      "id":               uuid,
      "code":             "BVX-TRIAL-XXXXXXXX",  # uppercase A-Z 0-9
      "partner_type":     "dealer" | "broker" | "storage",
      "duration_days":    30 | 60 | 45,
      "status":           "issued" | "redeemed" | "expired" | "revoked",
      "created_by":       admin user id,
      "created_at":       ISO,
      "expires_at":       ISO,  # default +90d from issue
      "redeemed_by_user_id": null | uuid,
      "redeemed_at":      null | ISO,
      "source":           "manual" | "external_campaign",
      "campaign_id":      None | uuid,
      "recipient_email":  optional — locks the coupon to one email,
      "recipient_name":   optional — pre-fills the partner profile,
      "company_name":     optional — pre-filled on profile registration,
    }

Routes:
    POST  /api/admin/promotions/activate-trial         — mint one
    POST  /api/admin/promotions/coupons/bulk           — mint N
    GET   /api/admin/promotions/coupons                — list (admin)
    DELETE /api/admin/promotions/coupons/{code}        — revoke (admin)
    GET   /api/promotions/coupons/{code}               — public preview
"""
from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, EmailStr

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

# Trial duration mirrors `partner_trial._TRIAL_DURATIONS` so the two
# minting paths converge on the same business rule.
#
# iter309 D3 — Added the generic `partner` (30-day) tier so admins can
# attach a "Partner Account Free Trial" coupon to external campaigns
# without committing recipients to a specific dealer/broker/storage role.
TRIAL_DURATIONS = {
    "dealer":  30,
    "broker":  60,
    "storage": 45,
    "partner": 30,
}

# Public base URL used to build the redemption signup link. Read from
# env so non-prod environments shorten correctly without code changes.
import os
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://bidvex.com").rstrip("/")

# Default coupon validity window for issued (but unredeemed) coupons.
DEFAULT_COUPON_VALID_DAYS = 90

# Canonical regex for the coupon-code wire format. Used by both the
# admin generator and the consumer-side redemption check.
COUPON_CODE_RE = re.compile(r"^BVX-TRIAL-[A-Z0-9]{8}$")


def _require_admin(user: User) -> None:
    if getattr(user, "role", None) != "admin" and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")


def generate_coupon_code() -> str:
    """`BVX-TRIAL-XXXXXXXX` where XXXXXXXX is 8 cryptographically
    random uppercase hex chars. Collision odds at 1 M codes ~ 0.0%."""
    suffix = secrets.token_hex(4).upper()  # 8 hex chars
    return f"BVX-TRIAL-{suffix}"


def build_signup_url(
    code: str,
    *,
    campaign_slug: Optional[str] = None,
    utm_source: str = "external_marketing",
) -> str:
    """Per-recipient registration URL with the promo, UTM source and
    optional campaign slug pre-baked. Always points to /register so the
    AuthPage can parse the query string and short-circuit the annual
    fee gate.
    """
    slug = campaign_slug or "auctioneer_invite"
    return (
        f"{PUBLIC_BASE_URL}/register?promo={code}"
        f"&utm_source={utm_source}&utm_campaign={slug}"
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


async def _ensure_unique_code(db) -> str:
    """Spin until we land on a code that doesn't exist yet — usually
    one attempt at our address space."""
    for _ in range(8):
        code = generate_coupon_code()
        if not await db.partner_trial_coupons.find_one({"code": code}, {"_id": 0, "id": 1}):
            return code
    raise HTTPException(status_code=500, detail="coupon code generation collision storm")


def _serialize_coupon(c: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo internals and add the convenience `signup_url`."""
    c = {k: v for k, v in c.items() if k != "_id"}
    c["signup_url"] = build_signup_url(
        c["code"],
        campaign_slug=(c.get("campaign_slug") or c.get("utm_campaign")),
    )
    return c


# ─── Schemas ──────────────────────────────────────────────────────────


class ActivateTrialBody(BaseModel):
    partner_type: str = Field(..., pattern="^(dealer|broker|storage|partner)$")
    recipient_email: Optional[EmailStr] = None
    recipient_name: Optional[str] = Field(default=None, max_length=200)
    company_name: Optional[str] = Field(default=None, max_length=200)
    send_invite_email: bool = False
    note: Optional[str] = Field(default=None, max_length=500)


class BulkCouponsBody(BaseModel):
    partner_type: str = Field(..., pattern="^(dealer|broker|storage|partner)$")
    count: int = Field(..., ge=1, le=2000)
    campaign_id: Optional[str] = None
    campaign_slug: Optional[str] = Field(default=None, max_length=120)


# ─── Routers ──────────────────────────────────────────────────────────


admin_coupons_router = APIRouter(
    prefix="/admin/promotions",
    tags=["Admin Promotions — Trial Coupons"],
)
public_coupons_router = APIRouter(
    prefix="/promotions/coupons",
    tags=["Promotions — Trial Coupons (public)"],
)


# ─── Admin endpoints ──────────────────────────────────────────────────


@admin_coupons_router.post("/activate-trial")
async def activate_trial(
    body: ActivateTrialBody,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mint a single tracking-friendly trial coupon. If
    `send_invite_email=True` AND a `recipient_email` was supplied, also
    fire an external acquisition email with the per-recipient signup
    link so the admin doesn't have to copy-paste the URL into anything.

    Idempotent on `(recipient_email, partner_type)` — if a non-redeemed
    coupon already exists for that pair, it is returned as-is instead
    of double-minting."""
    _require_admin(current_user)
    db = get_db()

    duration = TRIAL_DURATIONS[body.partner_type]
    now = _now()

    # Re-use any existing live coupon for the same recipient + type so
    # admins clicking "Activate" twice don't flood the table.
    if body.recipient_email:
        existing = await db.partner_trial_coupons.find_one(
            {
                "recipient_email": body.recipient_email.lower(),
                "partner_type":    body.partner_type,
                "status":          "issued",
            },
            {"_id": 0},
        )
        if existing:
            return {
                "success":       True,
                "deduped":       True,
                "coupon":        _serialize_coupon(existing),
            }

    code = await _ensure_unique_code(db)
    doc = {
        "id":              str(uuid.uuid4()),
        "code":            code,
        "partner_type":    body.partner_type,
        "duration_days":   duration,
        "status":          "issued",
        "created_by":      current_user.id,
        "created_at":      _now_iso(),
        "expires_at":      (now + timedelta(days=DEFAULT_COUPON_VALID_DAYS)).isoformat(),
        "redeemed_by_user_id": None,
        "redeemed_at":     None,
        "source":          "manual",
        "campaign_id":     None,
        "campaign_slug":   None,
        "recipient_email": (body.recipient_email or "").lower() or None,
        "recipient_name":  (body.recipient_name or "").strip() or None,
        "company_name":    (body.company_name or "").strip() or None,
        "note":            (body.note or "").strip() or None,
    }
    await db.partner_trial_coupons.insert_one(doc)

    email_sent = False
    if body.send_invite_email and body.recipient_email:
        try:
            from services.external_email import send_external_campaign_email
            signup_url = build_signup_url(code)
            # A minimal bilingual invite — full design lives in the
            # external-campaign body template, but we still ship a
            # CASL-compliant single-shot when the admin checks the
            # "Email recipient now" box.
            html = (
                f"<p>Hello {body.recipient_name or ''},</p>"
                f"<p>You've been invited to BidVex with a complimentary "
                f"<strong>{duration}-day {body.partner_type} trial</strong>.</p>"
                f"<p><a href='{signup_url}'>Activate your account</a></p>"
                f"<p style='font-size:12px;color:#666'>"
                f"This invite was sent on behalf of BidVex marketing. "
                f"Click <a href='{{unsubscribe_url}}'>here</a> to unsubscribe."
                f"</p>"
            )
            result = await send_external_campaign_email(
                to_email=body.recipient_email,
                to_name=body.recipient_name or "",
                subject=f"You're invited to BidVex — {duration}-day {body.partner_type} trial",
                body_html=html,
                campaign_id=doc["id"],
                utm_campaign="manual_trial_invite",
            )
            email_sent = result.get("status") in ("sent", "logged")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter274 trial-coupon] invite email failed: {exc}")

    return {
        "success":    True,
        "deduped":    False,
        "email_sent": email_sent,
        "coupon":     _serialize_coupon(doc),
    }


@admin_coupons_router.post("/coupons/bulk")
async def bulk_mint_coupons(
    body: BulkCouponsBody,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mint N coupons in a single round trip — used by the external
    campaign send-now flow to pre-allocate one code per recipient."""
    _require_admin(current_user)
    db = get_db()

    duration = TRIAL_DURATIONS[body.partner_type]
    now = _now()
    expires = (now + timedelta(days=DEFAULT_COUPON_VALID_DAYS)).isoformat()

    docs = []
    for _ in range(body.count):
        code = await _ensure_unique_code(db)
        docs.append({
            "id":              str(uuid.uuid4()),
            "code":            code,
            "partner_type":    body.partner_type,
            "duration_days":   duration,
            "status":          "issued",
            "created_by":      current_user.id,
            "created_at":      _now_iso(),
            "expires_at":      expires,
            "redeemed_by_user_id": None,
            "redeemed_at":     None,
            "source":          "external_campaign",
            "campaign_id":     body.campaign_id,
            "campaign_slug":   body.campaign_slug,
            "recipient_email": None,
            "recipient_name":  None,
            "company_name":    None,
            "note":            None,
        })
    if docs:
        await db.partner_trial_coupons.insert_many(docs)

    return {
        "success": True,
        "minted":  len(docs),
        "codes":   [d["code"] for d in docs],
    }


@admin_coupons_router.get("/coupons")
async def list_coupons(
    status: Optional[str] = None,
    partner_type: Optional[str] = None,
    campaign_id: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if partner_type:
        q["partner_type"] = partner_type
    if campaign_id:
        q["campaign_id"] = campaign_id
    cursor = (
        db.partner_trial_coupons.find(q, {"_id": 0})
        .sort("created_at", -1).limit(max(1, min(500, int(limit or 100))))
    )
    items = await cursor.to_list(length=500)
    total = await db.partner_trial_coupons.count_documents(q)
    return {
        "items": [_serialize_coupon(i) for i in items],
        "total": total,
    }


@admin_coupons_router.delete("/coupons/{code}")
async def revoke_coupon(code: str, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    res = await db.partner_trial_coupons.update_one(
        {"code": code.upper(), "status": "issued"},
        {"$set": {"status": "revoked", "revoked_at": _now_iso()}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="coupon not found or not in issued status")
    return {"success": True, "code": code.upper(), "status": "revoked"}


# ─── Public preview endpoint ──────────────────────────────────────────


@public_coupons_router.get("/{code}")
async def preview_coupon(code: str) -> Dict[str, Any]:
    """Used by the AuthPage to show the "FREE TRIAL UNLOCKED" banner
    before the user finishes signup. Returns ONLY non-sensitive fields."""
    code = code.upper().strip()
    if not COUPON_CODE_RE.match(code):
        raise HTTPException(status_code=400, detail={
            "error_code": "invalid_coupon_format",
            "message_en": "Coupon code format is invalid.",
            "message_fr": "Le format du code de coupon est invalide.",
        })
    db = get_db()
    c = await db.partner_trial_coupons.find_one({"code": code}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail={
            "error_code": "coupon_not_found",
            "message_en": "Coupon not found.",
            "message_fr": "Coupon introuvable.",
        })
    now = _now()
    expired = False
    try:
        expired = datetime.fromisoformat(c["expires_at"]) < now
    except Exception:
        pass
    return {
        "code":           c["code"],
        "partner_type":   c["partner_type"],
        "duration_days":  c["duration_days"],
        "status":         c["status"],
        "expired":        expired,
        "valid":          c["status"] == "issued" and not expired,
        "pre_filled": {
            "recipient_email": c.get("recipient_email"),
            "recipient_name":  c.get("recipient_name"),
            "company_name":    c.get("company_name"),
        },
    }


# ─── Server-side coupon consumption (called from auth.register) ───────


async def redeem_coupon_for_user(
    code: str,
    *,
    user_id: str,
    user_email: str,
    company_name_hint: Optional[str] = None,
    phone_hint: Optional[str] = None,
    province_hint: Optional[str] = "QC",
) -> Optional[Dict[str, Any]]:
    """Atomically claim the coupon and provision the corresponding
    `partner_trials` row + user flags so the new account skips the
    annual-fee gate.

    Returns the claimed coupon doc on success, None on any failure
    (invalid code, expired, already redeemed, etc.) — never raises so
    the register flow keeps shipping the user response even when the
    promo turned out to be stale.
    """
    if not code:
        return None
    code = code.upper().strip()
    if not COUPON_CODE_RE.match(code):
        return None

    db = get_db()
    now = _now()

    # Atomic claim — only flip status if still `issued` and not expired.
    res = await db.partner_trial_coupons.find_one_and_update(
        {
            "code":   code,
            "status": "issued",
            "expires_at": {"$gte": now.isoformat()},
        },
        {"$set": {
            "status":              "redeemed",
            "redeemed_by_user_id": user_id,
            "redeemed_by_email":   user_email.lower(),
            "redeemed_at":         _now_iso(),
        }},
        return_document=True,  # post-update doc
        projection={"_id": 0},
    )
    if not res:
        return None

    partner_type = res["partner_type"]
    duration = res["duration_days"]
    trial_expiry = now + timedelta(days=duration)

    # Provision the partner_trials row so the existing trial machinery
    # (extend / revoke / featured listing quota) keeps working.
    # iter309 D3 — Added `partner` to the featured-listings table so the
    # generic Partner Account tier doesn't KeyError on lookup.
    featured_quota_map = {"dealer": 3, "broker": 99, "storage": 5, "partner": 5}
    trial_doc = {
        "id":                          str(uuid.uuid4()),
        "user_id":                     user_id,
        "partner_type":                partner_type,
        "company_name":                (res.get("company_name") or company_name_hint or "Auctioneer Partner").strip()[:200],
        "licence_number":              None,
        "province":                    (province_hint or "QC").upper(),
        "phone":                       phone_hint or "",
        "status":                      "active",
        "trial_expires_at":            trial_expiry.isoformat(),
        "featured_listings_remaining": featured_quota_map.get(partner_type, 5),
        "created_at":                  _now_iso(),
        "activated_via_coupon":        code,
        "campaign_id":                 res.get("campaign_id"),
    }
    await db.partner_trials.insert_one(trial_doc)

    user_updates = {
        "partner_type":                partner_type,
        "partner_trial_active":        True,
        "partner_trial_expires_at":    trial_expiry.isoformat(),
        # iter309 D3 — Canonical `trial_active` flag + `account_tier` so the
        # rest of the platform (gated dashboards, partner badges, fee rules)
        # consistently identifies trial members without inferring from
        # partner_type alone.
        "trial_active":                True,
        "trial_expires_at":            trial_expiry.isoformat(),
        "account_tier":                "partner",
        # iter274 — Annual-fee gate is short-circuited: partner is
        # treated as paid for the duration of the trial so the dashboard
        # doesn't show the "pay $99 to continue" overlay.
        "platform_fee_paid":           True,
        "partner_subscription_active": True,
        "partner_fee_paid_via_coupon": code,
        "partner_fee_paid_at":         _now_iso(),
    }
    if partner_type == "broker":
        user_updates["is_broker_partner"] = True
    await db.users.update_one({"id": user_id}, {"$set": user_updates})

    return res


__all__ = [
    "TRIAL_DURATIONS",
    "COUPON_CODE_RE",
    "generate_coupon_code",
    "build_signup_url",
    "redeem_coupon_for_user",
    "admin_coupons_router",
    "public_coupons_router",
]
