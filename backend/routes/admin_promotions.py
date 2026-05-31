"""
BidVex — Admin Promotions & Offers Engine (iter241 Mission 7).

Provides admins with platform-wide promotional offers that automatically
apply discounts (or zero-fee waivers, free boost credits, etc.) at
checkout. Promotions are stored in MongoDB and evaluated by
`apply_active_promotions()` whenever a financial event occurs.

This module owns ONLY the CRUD + eligibility logic. The checkout
integration hook is exported as `apply_active_promotions()` for the
existing fee-calculator paths to call into.
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone, timedelta as _td
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

admin_promotions_router = APIRouter(tags=["Admin Promotions"])

PROMOTION_TYPES = {
    "free_platform_fee",
    "free_first_listing",
    "reduced_commission",
    "free_promotion_boost",
    "subscription_discount",
    "partner_launch_offer",
}

PROMOTION_STATUSES = {"draft", "scheduled", "active", "paused", "expired", "exhausted"}


# ─── Pydantic ────────────────────────────────────────────────────────────
class PromotionTargetConfig(BaseModel):
    target: str = Field(..., description="all|tier|province|new_users|custom")
    target_tier: Optional[str] = None
    target_province: Optional[str] = None
    new_user_days: Optional[int] = None
    custom_user_ids: Optional[List[str]] = None
    custom_emails: Optional[List[str]] = None


class PromotionCreate(BaseModel):
    name_en: str
    name_fr: Optional[str] = None
    type: str
    config: Dict[str, Any] = Field(default_factory=dict)
    target_config: PromotionTargetConfig
    start_date: str  # ISO
    end_date: str  # ISO
    max_uses: Optional[int] = None
    uses_per_user: int = 1
    coupon_code: Optional[str] = None
    notify_users: bool = False
    show_banner: bool = False


class PromotionUpdate(BaseModel):
    name_en: Optional[str] = None
    name_fr: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    target_config: Optional[PromotionTargetConfig] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    max_uses: Optional[int] = None
    uses_per_user: Optional[int] = None
    status: Optional[str] = None
    notify_users: Optional[bool] = None
    show_banner: Optional[bool] = None



class PromotionValidateRequest(BaseModel):
    """iter253 — Inbound payload for `POST /api/promotions/validate`.

    Used by the Partner Dashboard coupon input + the listing-checkout
    coupon entry box. Returns the structured discount math so the
    frontend can pre-render a $0.00 CAD ledger BEFORE the user clicks
    "Proceed to Stripe Checkout".
    """
    coupon_code: str = Field(..., min_length=1, max_length=64)
    transaction_type: str = Field(
        "listing_fee",
        description="One of: listing_fee, listing_promotion, buyer_premium, "
                    "seller_commission, subscription_upgrade",
    )
    base_amount_cad: float = Field(0.0, ge=0)
    listing_type: Optional[str] = "vehicles"


class CouponActivationRequest(BaseModel):
    """iter254 Mission 1 — Inbound payload for the B2B account-level
    coupon activation (`POST /api/promotions/activate-to-account`)."""
    coupon_code: str = Field(..., min_length=1, max_length=64)



def _generate_coupon_code(prefix: str = "BIDVEX") -> str:
    """Generate a human-readable coupon: BIDVEX-<6 random alphanum>"""
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"{prefix}-{suffix}"


def _require_admin(user: User) -> None:
    if user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


async def _audience_preview(db, target_config: PromotionTargetConfig) -> Dict[str, Any]:
    """Count eligible users for a target config + sample 10 emails."""
    q: Dict[str, Any] = {}
    target = (target_config.target or "all").lower()
    if target == "all":
        pass
    elif target == "partners":
        # iter247 — Partners segment (Auctioneers + Liquidators).
        # Matches users flagged via `is_partner=True` OR the legacy
        # `account_type="partner"` field used by older partner-onboarding
        # flows. `partner_verification_status="verified"` is implicit when
        # `is_partner=True` is set by the verification webhook.
        q["$or"] = [
            {"is_partner": True},
            {"account_type": "partner"},
        ]
    elif target == "tier" and target_config.target_tier:
        q["subscription_tier"] = target_config.target_tier
    elif target == "province" and target_config.target_province:
        q["province"] = target_config.target_province
    elif target == "new_users" and target_config.new_user_days:
        from datetime import timedelta as _td
        cutoff = (datetime.now(timezone.utc) - _td(days=target_config.new_user_days)).isoformat()
        q["created_at"] = {"$gte": cutoff}
    elif target == "custom":
        ids = target_config.custom_user_ids or []
        emails = [e.lower() for e in (target_config.custom_emails or [])]
        if ids or emails:
            or_clauses: List[Dict[str, Any]] = []
            if ids:
                or_clauses.append({"id": {"$in": ids}})
            if emails:
                or_clauses.append({"email": {"$in": emails}})
            q["$or"] = or_clauses
        else:
            return {"count": 0, "sample": []}
    else:
        return {"count": 0, "sample": []}

    count = await db.users.count_documents(q)
    sample = await db.users.find(q, {"_id": 0, "email": 1, "id": 1}).limit(10).to_list(10)
    return {"count": count, "sample": [s.get("email") for s in sample if s.get("email")]}


# ─── CRUD endpoints ──────────────────────────────────────────────────────
@admin_promotions_router.post("/admin/promotions")
async def create_promotion(
    data: PromotionCreate,
    current_user: User = Depends(get_current_user),
):
    """Create a new admin promotion. Coupon auto-generated if absent."""
    _require_admin(current_user)
    if data.type not in PROMOTION_TYPES:
        raise HTTPException(400, f"type must be one of {sorted(PROMOTION_TYPES)}")

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    coupon = data.coupon_code or _generate_coupon_code()

    # Enforce coupon uniqueness.
    existing = await db.promotions.find_one({"coupon_code": coupon}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(400, f"Coupon code {coupon!r} already exists")

    # Status derivation from dates.
    start_dt = datetime.fromisoformat(data.start_date.replace("Z", "+00:00"))
    now_dt = datetime.now(timezone.utc)
    status = "scheduled" if start_dt > now_dt else "active"

    import uuid as _uuid
    # iter250 — Sanitize broker-supplied HTML/text fields on promotion creation.
    from services.html_sanitizer import sanitize_user_html, sanitize_inline
    promotion = {
        "id": str(_uuid.uuid4()),
        "name_en": sanitize_inline(data.name_en),
        "name_fr": sanitize_inline(data.name_fr or data.name_en),
        "type": data.type,
        "config": data.config,
        "target": data.target_config.target,
        "target_config": data.target_config.dict(),
        "coupon_code": coupon,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "max_uses": data.max_uses,
        "uses_per_user": data.uses_per_user,
        "current_uses": 0,
        "status": status,
        "notify_users": data.notify_users,
        "show_banner": data.show_banner,
        "created_by": current_user.id,
        "created_at": now,
        "updated_at": now,
    }
    # Banner HTML (if the admin supplied any) goes through the full HTML
    # sanitizer to preserve formatting tags while stripping XSS vectors.
    _banner_html = getattr(data, "banner_html_en", None) or getattr(data, "banner_html", None)
    if _banner_html:
        promotion["banner_html_en"] = sanitize_user_html(_banner_html)
    _banner_html_fr = getattr(data, "banner_html_fr", None)
    if _banner_html_fr:
        promotion["banner_html_fr"] = sanitize_user_html(_banner_html_fr)
    # Long-form description fields (when present on the model).
    for _f in ("description_en", "description_fr"):
        _val = getattr(data, _f, None)
        if _val:
            promotion[_f] = sanitize_user_html(_val)
    await db.promotions.insert_one(promotion)
    promotion.pop("_id", None)
    return promotion


@admin_promotions_router.get("/admin/promotions")
async def list_promotions(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    cur = db.promotions.find(q, {"_id": 0}).sort("created_at", -1)
    items = await cur.to_list(length=200)
    return {"items": items, "total": len(items)}


@admin_promotions_router.get("/admin/promotions/{promo_id}")
async def get_promotion(
    promo_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    doc = await db.promotions.find_one({"id": promo_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Promotion not found")
    # Attach a fresh audience preview.
    tc = PromotionTargetConfig(**doc.get("target_config", {"target": "all"}))
    doc["audience"] = await _audience_preview(db, tc)
    # Usage rollup.
    doc["usage_count"] = await db.promotion_usage.count_documents({"promotion_id": promo_id})
    return doc


@admin_promotions_router.patch("/admin/promotions/{promo_id}")
async def update_promotion(
    promo_id: str,
    data: PromotionUpdate,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    update: Dict[str, Any] = {k: v for k, v in data.dict(exclude_unset=True).items() if v is not None}
    if data.target_config is not None:
        update["target_config"] = data.target_config.dict()
        update["target"] = data.target_config.target
    if "status" in update and update["status"] not in PROMOTION_STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(PROMOTION_STATUSES)}")
    # iter250 — Sanitize broker-supplied HTML/text fields on update path too.
    from services.html_sanitizer import sanitize_user_html, sanitize_inline
    for _f in ("name_en", "name_fr"):
        if update.get(_f):
            update[_f] = sanitize_inline(update[_f])
    for _f in ("description_en", "description_fr", "banner_html_en", "banner_html_fr", "banner_html"):
        if update.get(_f):
            update[_f] = sanitize_user_html(update[_f])
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    r = await db.promotions.update_one({"id": promo_id}, {"$set": update})
    if r.matched_count == 0:
        raise HTTPException(404, "Promotion not found")
    doc = await db.promotions.find_one({"id": promo_id}, {"_id": 0})
    return doc


@admin_promotions_router.delete("/admin/promotions/{promo_id}")
async def delete_promotion(
    promo_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    r = await db.promotions.delete_one({"id": promo_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Promotion not found")
    return {"deleted": True}


@admin_promotions_router.post("/admin/promotions/{promo_id}/pause")
async def pause_promotion(
    promo_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return await update_promotion(promo_id, PromotionUpdate(status="paused"), current_user)


@admin_promotions_router.post("/admin/promotions/{promo_id}/activate")
async def activate_promotion(
    promo_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """iter243 Mission 2 — Activate + (optionally) broadcast.

    Sets status to `active` then fires a background email broadcast when
    the promotion has `notify_users=True`. The broadcast is idempotent —
    re-activating a promotion that's already been broadcast will not
    re-send.
    """
    _require_admin(current_user)
    activated = await update_promotion(promo_id, PromotionUpdate(status="active"), current_user)
    if activated and activated.get("notify_users"):
        # Schedule the broadcast so the API returns immediately.
        from services.promotion_broadcast import broadcast_promotion_activation
        db = get_db()
        background_tasks.add_task(broadcast_promotion_activation, db, promo_id)
        # Surface to the admin caller that a broadcast was scheduled.
        activated["broadcast_scheduled"] = True
    return activated


@admin_promotions_router.post("/admin/promotions/{promo_id}/duplicate")
async def duplicate_promotion(
    promo_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    doc = await db.promotions.find_one({"id": promo_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Promotion not found")
    import uuid as _uuid
    doc["id"] = str(_uuid.uuid4())
    doc["coupon_code"] = _generate_coupon_code()
    doc["current_uses"] = 0
    doc["status"] = "draft"
    doc["name_en"] = doc.get("name_en", "") + " (copy)"
    doc["name_fr"] = doc.get("name_fr", "") + " (copie)"
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_at"] = doc["created_at"]
    doc["created_by"] = current_user.id
    await db.promotions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@admin_promotions_router.post("/admin/promotions/{promo_id}/re-trigger")
async def re_trigger_promotion(
    promo_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """iter246 Mission 2 — One-click re-launch of a high-performing promotion.

    Clones the source promotion's full config, target_config, and
    pricing fields under a NEW unique coupon code prefixed `BIDVEX-RE-`.
    The new promotion is created `status="active"` with `current_uses=0`
    and a duration matching the source's original span (re-anchored to
    `now()`). If the source had `notify_users=True`, the broadcast is
    scheduled on the background task pipeline so admins get an immediate
    HTTP response.
    """
    _require_admin(current_user)
    db = get_db()

    source = await db.promotions.find_one({"id": promo_id}, {"_id": 0})
    if not source:
        raise HTTPException(404, "Promotion not found")

    # Compute the source's original duration and re-anchor to now().
    try:
        s_dt = datetime.fromisoformat((source.get("start_date") or "").replace("Z", "+00:00"))
        e_dt = datetime.fromisoformat((source.get("end_date") or "").replace("Z", "+00:00"))
        duration = e_dt - s_dt
        if duration.total_seconds() <= 0:
            duration = _td(days=30)
    except Exception:
        duration = _td(days=30)

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    new_end = (now_dt + duration).isoformat()

    # Generate a fresh BIDVEX-RE- coupon and guarantee uniqueness.
    import uuid as _uuid
    new_coupon = _generate_coupon_code(prefix="BIDVEX-RE")
    while await db.promotions.find_one({"coupon_code": new_coupon}, {"_id": 0, "id": 1}):
        new_coupon = _generate_coupon_code(prefix="BIDVEX-RE")

    clone: Dict[str, Any] = {
        "id": str(_uuid.uuid4()),
        "name_en": (source.get("name_en") or "Untitled Promotion") + " (re-trigger)",
        "name_fr": (source.get("name_fr") or source.get("name_en") or "Promotion") + " (re-déclenchement)",
        "type": source.get("type"),
        "config": dict(source.get("config") or {}),
        "target": source.get("target") or (source.get("target_config") or {}).get("target", "all"),
        "target_config": dict(source.get("target_config") or {"target": "all"}),
        "coupon_code": new_coupon,
        "start_date": now_iso,
        "end_date": new_end,
        "max_uses": source.get("max_uses"),
        "uses_per_user": source.get("uses_per_user") or 1,
        "current_uses": 0,
        "status": "active",
        "notify_users": bool(source.get("notify_users")),
        "show_banner": bool(source.get("show_banner")),
        "created_by": current_user.id,
        "created_at": now_iso,
        "updated_at": now_iso,
        "re_triggered_from": promo_id,
    }
    await db.promotions.insert_one(clone)
    clone.pop("_id", None)

    # Fire-and-forget broadcast if the source opted in.
    if clone["notify_users"]:
        try:
            from services.promotion_broadcast import broadcast_promotion_activation
            background_tasks.add_task(broadcast_promotion_activation, db, clone["id"])
            clone["broadcast_scheduled"] = True
        except Exception:
            clone["broadcast_scheduled"] = False

    return clone


class PartnerOutreachPayload(BaseModel):
    promotion_id: Optional[str] = Field(None, description="Promotion to anchor the coupon code on")
    coupon_code: Optional[str] = Field(None, description="Override coupon code (defaults to promo.coupon_code)")
    recipient_emails: Optional[List[str]] = Field(None, description="If set, ONLY blast to these emails (smoke testing)")
    dry_run: bool = Field(False, description="When True, do not actually call SendGrid")
    # iter254 Mission 3 — Forced language override. When set to "en" or
    # "fr", every recipient gets that variant regardless of their
    # `province` or `preferred_language`. None means auto-detect (default).
    forced_lang: Optional[str] = Field(
        None,
        description="Optional language override: 'en' or 'fr'. None = auto-detect.",
    )


@admin_promotions_router.post("/admin/promotions/partner-outreach/send")
async def send_partner_outreach_blast(
    payload: PartnerOutreachPayload,
    current_user: User = Depends(get_current_user),
):
    """iter247 — One-shot blast for the Partner Program Outreach campaign.

    Sends the locked English subject + body + PDF attachment to every
    flagged partner user. Recipient set:
      • Default: `users` collection where `is_partner=True` OR
        `account_type=="partner"`.
      • Override via `recipient_emails`.

    For each recipient, the email is dispatched via
    `send_unified_email("new_feature", data={html_full_override: ...})`
    with the rendered PDF attached. Returns counters + per-recipient
    delivery statuses.
    """
    _require_admin(current_user)
    db = get_db()

    from services.partner_outreach import (
        PARTNER_OUTREACH_EMAIL_SUBJECT,
        PARTNER_OUTREACH_EMAIL_SUBJECT_FR,
        partner_outreach_email_html,
        partner_outreach_email_html_fr,
        build_partner_outreach_pdf,
        build_partner_outreach_pdf_fr,
        detect_partner_language,
    )
    from services.email_notifications import send_unified_email
    import base64 as _b64

    coupon_code = payload.coupon_code
    promo_doc = None
    if payload.promotion_id:
        promo_doc = await db.promotions.find_one(
            {"id": payload.promotion_id}, {"_id": 0}
        )
        if promo_doc and not coupon_code:
            coupon_code = promo_doc.get("coupon_code")

    # Resolve recipients.
    # iter248 Mission 2 — When `recipient_emails` is supplied, we honour
    # it verbatim (admin "Send Preview to Myself"). The recipient's
    # province is still looked up in the users collection so the
    # preview matches what a real partner in QC would receive.
    if payload.recipient_emails:
        recipients = []
        for em in payload.recipient_emails:
            em_norm = (em or "").strip()
            if not em_norm:
                continue
            user_doc = await db.users.find_one(
                {"email": em_norm},
                {"_id": 0, "id": 1, "email": 1, "first_name": 1,
                 "name": 1, "company_name": 1, "province": 1,
                 "preferred_language": 1, "language": 1},
            )
            user_doc = user_doc or {}
            recipients.append({
                "email": em_norm,
                "first_name": user_doc.get("first_name") or user_doc.get("company_name") or user_doc.get("name") or "Partner",
                "id": user_doc.get("id"),
                "province": user_doc.get("province"),
                "preferred_language": user_doc.get("preferred_language") or user_doc.get("language"),
            })
    else:
        # iter251 — Audience resolution now honours the promotion's own
        # `target_config` when no explicit `recipient_emails` override is
        # supplied. This is what makes the [🚀 Launch Broadcast] CTA
        # actually fire to the manual list the admin typed into the
        # Edit dialog.
        target_cfg = (promo_doc or {}).get("target_config") or {}
        target_type = (target_cfg.get("target") or "partners").lower()

        if target_type == "custom" and (
            target_cfg.get("custom_emails") or target_cfg.get("custom_user_ids")
        ):
            # Manual list path. Honors both custom_emails and custom_user_ids.
            ids = target_cfg.get("custom_user_ids") or []
            emails = [(e or "").strip().lower() for e in (target_cfg.get("custom_emails") or [])]
            user_q: Dict[str, Any] = {}
            clauses: List[Dict[str, Any]] = []
            if ids:
                clauses.append({"id": {"$in": ids}})
            if emails:
                clauses.append({"email": {"$in": emails}})
            if clauses:
                user_q["$or"] = clauses
            users = await db.users.find(
                user_q,
                {"_id": 0, "id": 1, "email": 1, "first_name": 1, "name": 1,
                 "company_name": 1, "province": 1, "preferred_language": 1,
                 "language": 1},
            ).to_list(length=10000)
            # Hydrate any pure-email addresses that don't yet have a user record
            # (cold outreach is the WHOLE POINT of the manual list).
            known_emails = {(u.get("email") or "").lower() for u in users}
            for em in emails:
                if em and em not in known_emails:
                    users.append({
                        "id": None, "email": em, "first_name": "Partner",
                        "name": "", "province": None, "preferred_language": None,
                    })
        else:
            # Default: query all flagged partner users (original iter247 path).
            users = await db.users.find(
                {"$or": [{"is_partner": True}, {"account_type": "partner"}]},
                {"_id": 0, "id": 1, "email": 1, "first_name": 1, "name": 1,
                 "company_name": 1, "province": 1, "preferred_language": 1, "language": 1},
            ).to_list(length=5000)
        # Strip duplicates + unsubscribed.
        unsubs_cur = db.email_unsubscribes.find({}, {"_id": 0, "email": 1})
        unsub_set = {u["email"].lower() for u in await unsubs_cur.to_list(length=10000) if u.get("email")}
        seen = set()
        recipients = []
        for u in users:
            em = (u.get("email") or "").strip().lower()
            if not em or em in seen or em in unsub_set:
                continue
            seen.add(em)
            recipients.append({
                "email": u.get("email"),
                "first_name": u.get("first_name") or u.get("company_name") or u.get("name") or "Partner",
                "id": u.get("id"),
                "province": u.get("province"),
                "preferred_language": u.get("preferred_language") or u.get("language"),
            })

    # iter255 Mission 2 — Immediate dispatch contract is the ONLY mode.
    # Surfaced in EVERY response payload (including the early no-match
    # short-circuit) so admins get atomic dispatch-confirmation.
    _DISPATCH_MODE = "immediate"
    _DISPATCHED_AT = datetime.now(timezone.utc).isoformat()

    if not recipients:
        return {
            "sent": 0,
            "failed": 0,
            "recipients": [],
            "promotion_id": payload.promotion_id,
            "coupon_code": coupon_code,
            "subject": PARTNER_OUTREACH_EMAIL_SUBJECT,
            "dry_run": payload.dry_run,
            "dispatch_mode": _DISPATCH_MODE,
            "dispatched_at": _DISPATCHED_AT,
            "warning": "no_partner_users_matched",
        }

    # iter248 Mission 1 — Pre-render BOTH language variants once so the
    # per-recipient loop just picks the right cached pair.
    pdf_en = build_partner_outreach_pdf(coupon_code=coupon_code)
    pdf_fr = build_partner_outreach_pdf_fr(coupon_code=coupon_code)
    pdf_en_b64 = _b64.b64encode(pdf_en).decode("ascii")
    pdf_fr_b64 = _b64.b64encode(pdf_fr).decode("ascii")
    html_en = partner_outreach_email_html(coupon_code=coupon_code)
    html_fr = partner_outreach_email_html_fr(coupon_code=coupon_code)

    sent = 0
    failed = 0
    fr_count = 0
    en_count = 0
    # iter254 Mission 3 — Normalize the forced-language override once.
    _forced = (payload.forced_lang or "").lower().strip() if payload.forced_lang else ""
    forced_lang_norm = "fr" if _forced.startswith("fr") else ("en" if _forced.startswith("en") else None)
    results: List[Dict[str, Any]] = []
    for r in recipients:
        # iter254 Mission 3 — Forced override wins over geo-detection.
        lang = forced_lang_norm or detect_partner_language(r)
        if lang == "fr":
            fr_count += 1
            html_body = html_fr
            pdf_b64 = pdf_fr_b64
            subject = PARTNER_OUTREACH_EMAIL_SUBJECT_FR
            pdf_filename = "Guide-Evaluation-Programme-Partenaires.pdf"
        else:
            en_count += 1
            html_body = html_en
            pdf_b64 = pdf_en_b64
            subject = PARTNER_OUTREACH_EMAIL_SUBJECT
            pdf_filename = "BidVex-Partner-Program-Guide.pdf"

        if payload.dry_run:
            results.append({
                "email": r["email"], "lang": lang, "subject": subject,
                "pdf_filename": pdf_filename, "status": "skipped_dry_run",
            })
            continue
        try:
            # iter254 Mission 4 — Partner-program campaigns ship under
            # the partners@bidvex.ca branded sender.
            from services.email_notifications import (
                B2B_PARTNER_FROM_EMAIL as _B2B_FROM,
                B2B_PARTNER_FROM_NAME as _B2B_FROM_NAME,
            )
            res = await send_unified_email(
                "new_feature",
                user={"email": r["email"], "first_name": r["first_name"]},
                data={
                    "html_full_override": html_body,
                    "subject_override": subject,
                },
                attachments=[{
                    "content": pdf_b64,
                    "filename": pdf_filename,
                    "type": "application/pdf",
                }],
                from_email=_B2B_FROM,
                from_name=_B2B_FROM_NAME,
                reply_to=_B2B_FROM,
            )
            if res and res.get("status") in ("sent", "logged"):
                sent += 1
                results.append({"email": r["email"], "lang": lang, "status": res.get("status")})
            else:
                failed += 1
                results.append({"email": r["email"], "status": "error", "detail": str(res)[:200]})
        except Exception as exc:  # noqa: BLE001
            failed += 1
            results.append({"email": r["email"], "status": "error", "detail": str(exc)[:200]})

    # Audit row.
    await db.partner_outreach_runs.insert_one({
        "id": str(__import__("uuid").uuid4()),
        "promotion_id": payload.promotion_id,
        "coupon_code": coupon_code,
        "recipient_count": len(recipients),
        "sent": sent,
        "failed": failed,
        "lang_en": en_count,
        "lang_fr": fr_count,
        "dry_run": payload.dry_run,
        "triggered_by": current_user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "subject": PARTNER_OUTREACH_EMAIL_SUBJECT,
        "subject_fr": PARTNER_OUTREACH_EMAIL_SUBJECT_FR,
        "promotion_id": payload.promotion_id,
        "coupon_code": coupon_code,
        "recipient_count": len(recipients),
        "lang_breakdown": {"en": en_count, "fr": fr_count},
        "forced_lang": forced_lang_norm,
        "sent": sent,
        "failed": failed,
        "dry_run": payload.dry_run,
        "is_preview": bool(payload.recipient_emails),
        "dispatch_mode": _DISPATCH_MODE,
        "dispatched_at": _DISPATCHED_AT,
        "recipients": results,
    }


@admin_promotions_router.get("/admin/promotions/partner-outreach/pdf")
async def download_partner_outreach_pdf(
    coupon_code: Optional[str] = None,
    lang: str = "en",
    current_user: User = Depends(get_current_user),
):
    """iter247 — Download the locked Partner Program Evaluation Guide PDF.

    iter248 — Pass `?lang=fr` to render the French Quebec guide
    (`Guide-Evaluation-Programme-Partenaires.pdf`).
    """
    _require_admin(current_user)
    from fastapi.responses import StreamingResponse
    from services.partner_outreach import (
        build_partner_outreach_pdf, build_partner_outreach_pdf_fr,
    )

    if (lang or "").lower().startswith("fr"):
        pdf_bytes = build_partner_outreach_pdf_fr(coupon_code=coupon_code)
        filename = "Guide-Evaluation-Programme-Partenaires.pdf"
    else:
        pdf_bytes = build_partner_outreach_pdf(coupon_code=coupon_code)
        filename = "BidVex-Partner-Program-Guide.pdf"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )





@admin_promotions_router.get("/admin/promotions/{promo_id}/usage")
async def usage_report(
    promo_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    rows = await db.promotion_usage.find(
        {"promotion_id": promo_id}, {"_id": 0}
    ).sort("used_at", -1).limit(200).to_list(200)
    return {"items": rows, "total": len(rows)}


@admin_promotions_router.get("/admin/promotions/{promo_id}/usage.csv")
async def usage_report_csv(
    promo_id: str,
    current_user: User = Depends(get_current_user),
):
    """iter244 Mission 3 — Stream promotion-usage as a CSV download.

    Columns (one row per redemption):
        Redemption ID, Timestamp (ISO), User ID, User Email, Coupon Code,
        Promotion Type, Saved Amount CAD
    """
    _require_admin(current_user)
    import csv as _csv
    import io as _io
    from fastapi.responses import StreamingResponse

    db = get_db()
    promo = await db.promotions.find_one({"id": promo_id}, {"_id": 0})
    if not promo:
        raise HTTPException(404, "Promotion not found")

    rows = await db.promotion_usage.find(
        {"promotion_id": promo_id}, {"_id": 0}
    ).sort("used_at", -1).to_list(length=10_000)

    # Hydrate user emails in one batch.
    user_ids = list({r.get("user_id") for r in rows if r.get("user_id")})
    users = await db.users.find(
        {"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "email": 1}
    ).to_list(length=len(user_ids) or 1)
    email_map = {u["id"]: u.get("email", "") for u in users}

    buf = _io.StringIO()
    writer = _csv.writer(buf, quoting=_csv.QUOTE_MINIMAL)
    writer.writerow([
        "Redemption ID", "Timestamp", "User ID", "User Email",
        "Coupon Code", "Promotion Type", "Saved Amount CAD",
    ])
    coupon = promo.get("coupon_code", "")
    ptype = promo.get("type", "")
    for r in rows:
        writer.writerow([
            r.get("id", ""),
            r.get("used_at", ""),
            r.get("user_id", ""),
            email_map.get(r.get("user_id"), ""),
            coupon,
            ptype,
            f"{float(r.get('saved_amount') or 0):.2f}",
        ])
    buf.seek(0)
    filename = f"promotion-{(promo.get('coupon_code') or promo_id)}-usage.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@admin_promotions_router.get("/admin/promotions/analytics/dashboard")
async def promotions_analytics_dashboard(
    current_user: User = Depends(get_current_user),
    window_days: int = 30,
):
    """iter245 Mission 1 — Composite analytics for the Admin Promotion
    Performance Dashboard.

    Returns three blocks in a single round-trip:

      gross_metrics: {
        total_gmv_saved_cad: float       — Sum of saved_amount across
                                           buyer_premium, seller_commission,
                                           listing_fee, listing_promotion,
                                           and subscription_upgrade events
                                           in the last `window_days` days.
        total_active_redemptions: int    — Count of promotion_usage rows.
        unique_user_redeemers_count: int — Distinct user_id count.
      }
      top_campaigns: [
        {coupon_code, promotion_type, name_en, redemption_count,
         saved_amount_cad, percent_of_total}, ...  (top 5 by saved_amount)
      ]
      velocity_timeline: [
        {date: "YYYY-MM-DD", uses: int, amount: float}, ...
      ]  — One row per calendar day across the `window_days` window
           (zero-filled for days with no redemptions).
    """
    _require_admin(current_user)
    db = get_db()
    window_days = max(1, min(int(window_days) if window_days is not None else 30, 365))
    cutoff_dt = datetime.now(timezone.utc) - _td(days=window_days)
    cutoff_iso = cutoff_dt.isoformat()

    # ── Gross metrics — single aggregation, three counters. ──────────
    gross_pipeline = [
        {"$match": {"used_at": {"$gte": cutoff_iso}}},
        {"$group": {
            "_id": None,
            "total_gmv_saved_cad": {
                "$sum": {"$ifNull": ["$saved_amount", 0]}
            },
            "total_active_redemptions": {"$sum": 1},
            "unique_user_ids": {"$addToSet": "$user_id"},
        }},
        {"$project": {
            "_id": 0,
            "total_gmv_saved_cad": 1,
            "total_active_redemptions": 1,
            "unique_user_redeemers_count": {"$size": "$unique_user_ids"},
        }},
    ]
    gross_rows = await db.promotion_usage.aggregate(gross_pipeline).to_list(length=1)
    if gross_rows:
        gross = gross_rows[0]
        gross["total_gmv_saved_cad"] = round(float(gross.get("total_gmv_saved_cad", 0)), 2)
    else:
        gross = {
            "total_gmv_saved_cad": 0.0,
            "total_active_redemptions": 0,
            "unique_user_redeemers_count": 0,
        }

    # ── Top campaigns — group by promotion_id, sort by total saved. ──
    top_pipeline = [
        {"$match": {"used_at": {"$gte": cutoff_iso}}},
        {"$group": {
            "_id": "$promotion_id",
            "saved_amount_cad": {"$sum": {"$ifNull": ["$saved_amount", 0]}},
            "redemption_count": {"$sum": 1},
        }},
        {"$sort": {"saved_amount_cad": -1}},
        {"$limit": 5},
    ]
    top_rows = await db.promotion_usage.aggregate(top_pipeline).to_list(length=5)

    # Hydrate promotion metadata (coupon_code, type, name_en) for the top 5.
    promo_ids = [r["_id"] for r in top_rows if r.get("_id")]
    promos = await db.promotions.find(
        {"id": {"$in": promo_ids}},
        {"_id": 0, "id": 1, "coupon_code": 1, "type": 1, "name_en": 1},
    ).to_list(length=len(promo_ids) or 1)
    promo_map = {p["id"]: p for p in promos}

    total_saved_for_pct = gross["total_gmv_saved_cad"] or 1.0
    top_campaigns = []
    for r in top_rows:
        pid = r.get("_id")
        meta = promo_map.get(pid, {})
        saved = round(float(r.get("saved_amount_cad", 0)), 2)
        top_campaigns.append({
            "promotion_id": pid,
            "coupon_code": meta.get("coupon_code") or "—",
            "promotion_type": meta.get("type") or "unknown",
            "name_en": meta.get("name_en") or "Untitled Promotion",
            "redemption_count": int(r.get("redemption_count", 0)),
            "saved_amount_cad": saved,
            "percent_of_total": round(
                (saved / total_saved_for_pct) * 100.0, 2
            ) if total_saved_for_pct else 0.0,
        })

    # ── Velocity timeline — daily roll-up over the window. ───────────
    # Mongo can $substr the ISO string to slice off "YYYY-MM-DD" (positions 0..10).
    timeline_pipeline = [
        {"$match": {"used_at": {"$gte": cutoff_iso}}},
        {"$group": {
            "_id": {"$substr": ["$used_at", 0, 10]},
            "uses": {"$sum": 1},
            "amount": {"$sum": {"$ifNull": ["$saved_amount", 0]}},
        }},
    ]
    raw_timeline = await db.promotion_usage.aggregate(timeline_pipeline).to_list(length=window_days * 2)
    timeline_map: Dict[str, Dict[str, Any]] = {
        row["_id"]: {
            "uses": int(row.get("uses", 0)),
            "amount": round(float(row.get("amount", 0)), 2),
        }
        for row in raw_timeline
    }

    # Zero-fill every day in the window so the chart axis is dense.
    velocity_timeline: List[Dict[str, Any]] = []
    now_date = datetime.now(timezone.utc).date()
    for offset in range(window_days - 1, -1, -1):
        day = now_date - _td(days=offset)
        key = day.isoformat()
        bucket = timeline_map.get(key, {"uses": 0, "amount": 0.0})
        velocity_timeline.append({
            "date": key,
            "uses": bucket["uses"],
            "amount": bucket["amount"],
        })

    # ── iter249 Mission 2 — B2B Partner Acquisition ROI block ────────
    # Computes telemetry specific to the BIDVEX-PARTNERS campaign:
    #   • total_registered_partners — distinct users flagged as partner.
    #   • partners_redeemed         — distinct partner users with ≥1
    #     promotion_usage row carrying coupon BIDVEX-PARTNERS.
    #   • partner_conversion_rate_pct — 100 * partners_redeemed /
    #     total_registered_partners (0.0 when no partners exist).
    #   • projected_gmv_lift_cad — sum of 90-day `transactions.amount`
    #     for the redeemed partner cohort. Falls back to the saved
    #     promotion_usage amounts when no transactions collection rows
    #     match.
    partner_roi: Dict[str, Any] = {
        "campaign_code": "BIDVEX-PARTNERS",
        "total_registered_partners": 0,
        "partners_redeemed": 0,
        "partner_conversion_rate_pct": 0.0,
        "projected_gmv_lift_cad": 0.0,
        "window_days": 90,
    }
    try:
        partner_filter = {"$or": [{"is_partner": True}, {"account_type": "partner"}]}
        total_partners = await db.users.count_documents(partner_filter)
        partner_roi["total_registered_partners"] = int(total_partners)

        if total_partners > 0:
            # Redeemed partner cohort.
            redeemed_rows = await db.promotion_usage.aggregate([
                {"$match": {"coupon_code": "BIDVEX-PARTNERS"}},
                {"$group": {
                    "_id": "$user_id",
                    "saved_amount": {"$sum": {"$ifNull": ["$saved_amount", 0]}},
                }},
            ]).to_list(length=10000)
            redeemer_ids = [r["_id"] for r in redeemed_rows if r.get("_id")]

            # Filter down to those redeemer_ids that are actual partners.
            partner_redeemer_ids: List[str] = []
            if redeemer_ids:
                async for u in db.users.find(
                    {"$and": [partner_filter, {"id": {"$in": redeemer_ids}}]},
                    {"_id": 0, "id": 1},
                ):
                    partner_redeemer_ids.append(u["id"])

            partner_roi["partners_redeemed"] = len(partner_redeemer_ids)
            partner_roi["partner_conversion_rate_pct"] = round(
                100.0 * len(partner_redeemer_ids) / total_partners, 2,
            )

            # 90-day GMV lift — sum the transactions collection for the
            # redeemed-partner cohort. Falls back to summing the
            # promotion_usage saved_amount values if no `transactions`
            # collection rows match.
            gmv_lift = 0.0
            if partner_redeemer_ids:
                cutoff_90 = (datetime.now(timezone.utc) - _td(days=90)).isoformat()
                try:
                    txn_rows = await db.transactions.aggregate([
                        {"$match": {
                            "user_id": {"$in": partner_redeemer_ids},
                            "created_at": {"$gte": cutoff_90},
                        }},
                        {"$group": {
                            "_id": None,
                            "gmv": {"$sum": {"$ifNull": ["$amount", 0]}},
                        }},
                    ]).to_list(length=1)
                    if txn_rows:
                        gmv_lift = float(txn_rows[0].get("gmv", 0) or 0)
                except Exception:
                    gmv_lift = 0.0
                if gmv_lift <= 0.0:
                    # Fallback: sum the saved_amount entries for these partners.
                    for r in redeemed_rows:
                        if r.get("_id") in partner_redeemer_ids:
                            gmv_lift += float(r.get("saved_amount", 0) or 0)
            partner_roi["projected_gmv_lift_cad"] = round(gmv_lift, 2)
    except Exception as exc:  # noqa: BLE001 — defensive: never fail the dashboard
        partner_roi["error"] = str(exc)[:200]

    return {
        "window_days": window_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gross_metrics": gross,
        "top_campaigns": top_campaigns,
        "velocity_timeline": velocity_timeline,
        "partner_roi": partner_roi,
    }




@admin_promotions_router.post("/admin/promotions/preview-audience")
async def preview_audience(
    target_config: PromotionTargetConfig,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    return await _audience_preview(db, target_config)


@admin_promotions_router.get("/promotions/preview-discount")
async def preview_discount(
    transaction_type: str,
    base_amount_cad: float,
    listing_type: Optional[str] = None,
    coupon_code: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """iter242 Mission 2 — Public preview endpoint.

    Used by checkout pages to show "You'll pay $0.00 thanks to your
    Free Partner Promotion!" BEFORE the user clicks "Pay" so they're
    never surprised by a $0 transaction.

    Returns the PromotionDiscount block (see services/promotion_runtime.py).
    """
    from services.promotion_runtime import compute_promotion_discount
    db = get_db()
    discount = await compute_promotion_discount(
        db=db,
        user_id=current_user.id,
        transaction_type=transaction_type,
        listing_type=listing_type,
        base_amount_cad=base_amount_cad,
        coupon_code=coupon_code,
    )
    return discount.to_dict()



@admin_promotions_router.post("/promotions/validate")
async def validate_coupon_code(
    payload: PromotionValidateRequest,
    current_user: User = Depends(get_current_user),
):
    """iter253 — Validate a coupon code typed by a partner/broker on the
    listing-checkout or partner dashboard page.

    Returns the structured discount math + a human-readable message
    block so the frontend can pre-render the $0.00 CAD ledger and
    swap the CTA copy from "Proceed to Stripe Checkout" to
    "🚀 Launch Free Listing Live Now".
    """
    from services.promotion_runtime import compute_promotion_discount
    db = get_db()

    code = (payload.coupon_code or "").strip().upper()
    if not code:
        return {
            "applies": False,
            "is_full_waiver": False,
            "discount_percent": 0.0,
            "discount_amount": 0.0,
            "final_amount": payload.base_amount_cad,
            "promotion_id": None,
            "promotion_name": None,
            "coupon_code": payload.coupon_code,
            "message_en": "Please enter a coupon code.",
            "message_fr": "Veuillez saisir un code promo.",
        }

    discount = await compute_promotion_discount(
        db=db,
        user_id=current_user.id,
        transaction_type=payload.transaction_type,
        listing_type=payload.listing_type,
        base_amount_cad=payload.base_amount_cad,
        coupon_code=code,
    )
    body = discount.to_dict() if hasattr(discount, "to_dict") else dict(discount)

    # Hydrate the promotion name so the frontend can render "BIDVEX-PARTNERS — Partner Launch Offer"
    promo_name_en = None
    promo_name_fr = None
    if body.get("promotion_id"):
        p_doc = await db.promotions.find_one(
            {"id": body["promotion_id"]},
            {"_id": 0, "name_en": 1, "name_fr": 1, "coupon_code": 1, "type": 1},
        )
        if p_doc:
            promo_name_en = p_doc.get("name_en")
            promo_name_fr = p_doc.get("name_fr")
            body["promotion_name"] = promo_name_en
            body["promotion_type"] = p_doc.get("type")

    applies = bool(body.get("applies"))
    is_full = bool(body.get("is_full_waiver"))

    if not applies:
        msg_en = "Invalid or expired coupon code."
        msg_fr = "Code promo invalide ou expiré."
    elif is_full:
        msg_en = "Promo applied: 100% Free Listing Activated!"
        msg_fr = "Promo appliquée : annonce 100 % gratuite activée !"
    else:
        pct = body.get("discount_percent", 0)
        msg_en = f"Promo applied: {pct:.0f}% discount."
        msg_fr = f"Promo appliquée : remise de {pct:.0f} %."

    body["message_en"] = msg_en
    body["message_fr"] = msg_fr
    body["coupon_code"] = code
    return body



@admin_promotions_router.post("/promotions/activate-to-account")
async def activate_coupon_to_account(
    payload: CouponActivationRequest,
    current_user: User = Depends(get_current_user),
):
    """iter254 Mission 1 — Persist a B2B coupon activation on the user's
    account. After this call, every subsequent listing-creation /
    checkout flow will see `user.partner_offer_active=True` and the
    associated coupon code, so we can auto-apply the waiver on the next
    transaction without making the partner re-paste the code.

    Hard role-gate: regular buyers / `account_type="personal"` are
    rejected with 403. Only Partners, Brokers, Vehicle Dealers, and
    Storage Facilities can activate a coupon to their account.
    """
    db = get_db()
    user_doc = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "id": 1, "email": 1, "account_type": 1, "is_partner": 1,
         "is_storage_facility": 1, "role": 1, "province": 1, "preferred_language": 1},
    )
    if not user_doc:
        raise HTTPException(404, "User not found")

    # Role-gate: only B2B accounts.
    is_b2b = (
        user_doc.get("is_partner") is True
        or user_doc.get("is_storage_facility") is True
        or (user_doc.get("account_type") or "").lower() in {
            "partner", "broker", "vehicle_dealer", "storage_facility"
        }
        or (user_doc.get("role") or "") in ("admin", "super_admin")
    )
    if not is_b2b:
        raise HTTPException(
            403, "Partner coupons are reserved for professional B2B accounts.",
        )

    code = (payload.coupon_code or "").strip().upper()
    if not code:
        raise HTTPException(400, "Coupon code is required.")

    # Validate the coupon via the live runtime engine (same path used by
    # `/promotions/validate`). We compute against a $499 listing_fee
    # baseline so the math contract matches what the partner will see
    # at checkout.
    from services.promotion_runtime import compute_promotion_discount
    import os as _os_local
    base_fee = float(_os_local.environ.get("BIDVEX_PARTNER_ANNUAL_FEE_CAD", "499.0"))
    discount = await compute_promotion_discount(
        db=db,
        user_id=current_user.id,
        transaction_type="listing_fee",
        listing_type="vehicles",
        base_amount_cad=base_fee,
        coupon_code=code,
    )
    if not getattr(discount, "applies", False):
        return {
            "activated": False,
            "coupon_code": code,
            "message_en": "Invalid or expired coupon code.",
            "message_fr": "Code promo invalide ou expiré.",
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "partner_offer_active": True,
            "partner_offer_promotion_id": discount.promotion_id,
            "partner_offer_coupon_code": code,
            "partner_offer_activated_at": now_iso,
            "partner_offer_is_full_waiver": bool(getattr(discount, "is_full_waiver", False)),
            "partner_offer_discount_percent": float(getattr(discount, "discount_percent", 0)),
        }},
    )

    is_full = bool(getattr(discount, "is_full_waiver", False))
    if is_full:
        msg_en = "Verified Partner Offer: 100% Free Listing Credit Applied"
        msg_fr = "Offre partenaire vérifiée : crédit d'annonce gratuit à 100 % appliqué"
    else:
        pct = getattr(discount, "discount_percent", 0)
        msg_en = f"Verified Partner Offer: {pct:.0f}% credit applied"
        msg_fr = f"Offre partenaire vérifiée : crédit de {pct:.0f} % appliqué"

    return {
        "activated": True,
        "coupon_code": code,
        "promotion_id": discount.promotion_id,
        "is_full_waiver": is_full,
        "discount_percent": float(getattr(discount, "discount_percent", 0)),
        "message_en": msg_en,
        "message_fr": msg_fr,
        "activated_at": now_iso,
    }







@admin_promotions_router.get("/promotions/active-banners")
async def active_banners(
    current_user: User = Depends(get_current_user),
):
    """iter243 Mission 1 — Active promotional banners for the calling user.

    Filters promotions with `status=active`, `show_banner=true`, within
    the validity window, and matches the user's tier / province /
    target_config eligibility. Returns localized fields ready for the
    front-end banner component.
    """
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()

    base_query = {
        "status": "active",
        "show_banner": True,
        "start_date": {"$lte": now_iso},
        "end_date": {"$gte": now_iso},
    }
    cur = db.promotions.find(base_query, {"_id": 0}).sort("created_at", -1)
    candidates = await cur.to_list(length=50)

    # Hydrate user once for eligibility checks.
    user = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "id": 1, "email": 1, "subscription_tier": 1, "province": 1, "created_at": 1},
    )

    banners: List[Dict[str, Any]] = []
    for promo in candidates:
        # Max uses gate
        if promo.get("max_uses") and promo.get("current_uses", 0) >= promo["max_uses"]:
            continue
        if not await _user_matches_target(user, promo):
            continue
        banners.append({
            "id": promo["id"],
            "name_en": promo.get("name_en", ""),
            "name_fr": promo.get("name_fr", promo.get("name_en", "")),
            "type": promo.get("type"),
            "coupon_code": promo.get("coupon_code"),
            "end_date": promo.get("end_date"),
            "discount_percent": (promo.get("config") or {}).get("discount_percent"),
            "credit_tier": (promo.get("config") or {}).get("credit_tier"),
        })

    return {"banners": banners, "total": len(banners)}


# ─── Public lookup (coupon code) ──────────────────────────────────────
@admin_promotions_router.get("/promotions/lookup")
async def lookup_coupon(
    code: str,
    current_user: User = Depends(get_current_user),
):
    """Validate a coupon for the calling user. Returns the active promotion
    if the coupon exists AND the user is eligible AND it's not exhausted.
    Used by the checkout flow when a user types a coupon."""
    db = get_db()
    promo = await db.promotions.find_one({"coupon_code": code.upper().strip()}, {"_id": 0})
    if not promo:
        raise HTTPException(404, "Coupon not found")
    if promo.get("status") not in ("active",):
        raise HTTPException(400, "Coupon is not active")
    now_iso = datetime.now(timezone.utc).isoformat()
    if promo.get("end_date") and promo["end_date"] < now_iso:
        raise HTTPException(400, "Coupon has expired")
    if promo.get("max_uses") and promo.get("current_uses", 0) >= promo["max_uses"]:
        raise HTTPException(400, "Coupon usage limit reached")
    # Eligibility check.
    user = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    eligible = await _user_matches_target(user, promo)
    if not eligible:
        raise HTTPException(403, "You are not eligible for this coupon")
    # Per-user limit.
    used_by_user = await db.promotion_usage.count_documents({
        "promotion_id": promo["id"], "user_id": current_user.id,
    })
    if used_by_user >= (promo.get("uses_per_user", 1) or 1):
        raise HTTPException(400, "You have already used this coupon")
    return promo


# ─── Checkout integration ────────────────────────────────────────────
async def _user_matches_target(user: Dict[str, Any], promo: Dict[str, Any]) -> bool:
    if not user:
        return False
    tc = promo.get("target_config", {})
    target = (promo.get("target") or tc.get("target") or "all").lower()
    if target == "all":
        return True
    if target == "partners":
        return bool(user.get("is_partner")) or user.get("account_type") == "partner"
    if target == "tier":
        return user.get("subscription_tier") == tc.get("target_tier")
    if target == "province":
        return (user.get("province") or "").upper() == (tc.get("target_province") or "").upper()
    if target == "new_users":
        from datetime import timedelta as _td
        days = tc.get("new_user_days") or 30
        try:
            created = datetime.fromisoformat((user.get("created_at") or "").replace("Z", "+00:00"))
        except Exception:
            return False
        return (datetime.now(timezone.utc) - created) <= _td(days=days)
    if target == "custom":
        return (
            user.get("id") in (tc.get("custom_user_ids") or [])
            or (user.get("email") or "").lower() in [e.lower() for e in (tc.get("custom_emails") or [])]
        )
    return False


async def apply_active_promotions(
    db,
    user_id: str,
    transaction_type: str,
    listing_type: Optional[str] = None,
    coupon_code: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Find the best active promotion for a user/transaction.

    Returns the promotion doc + computed `applied_value` (None if no match).
    Never stacks: if multiple match, picks the one giving the biggest
    monetary benefit. The caller is responsible for recording usage via
    `record_promotion_usage()` once the underlying transaction completes.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    base_query = {
        "status": "active",
        "start_date": {"$lte": now_iso},
        "end_date": {"$gte": now_iso},
    }
    if coupon_code:
        base_query["coupon_code"] = coupon_code.upper().strip()

    cur = db.promotions.find(base_query, {"_id": 0})
    candidates = await cur.to_list(length=200)

    user = await db.users.find_one({"id": user_id}, {"_id": 0}) if user_id else None
    if user is None and not coupon_code:
        return None

    best = None
    best_value = -1.0
    for promo in candidates:
        # Max uses gate
        if promo.get("max_uses") and promo.get("current_uses", 0) >= promo["max_uses"]:
            continue
        # Per-user gate
        used = await db.promotion_usage.count_documents({
            "promotion_id": promo["id"], "user_id": user_id,
        })
        if used >= (promo.get("uses_per_user", 1) or 1):
            continue
        # Eligibility
        if user is not None and not await _user_matches_target(user, promo):
            continue
        # Scope match
        cfg = promo.get("config", {}) or {}
        scope = cfg.get("scope") or ["all"]
        if listing_type and "all" not in scope and listing_type not in scope:
            continue
        # Best-value scoring: higher discount_percent wins; "free" (100%) tops it.
        if promo["type"] in ("free_platform_fee", "free_first_listing", "partner_launch_offer"):
            value = 100.0
        elif promo["type"] == "reduced_commission":
            value = float(cfg.get("discount_percent", 0))
        elif promo["type"] == "subscription_discount":
            value = float(cfg.get("discount_percent", 0))
        elif promo["type"] == "free_promotion_boost":
            value = 50.0  # Mid-weight credit
        else:
            value = 25.0
        if value > best_value:
            best, best_value = promo, value

    if not best:
        return None
    return {**best, "applied_value": best_value}


async def record_promotion_usage(
    db,
    promotion_id: str,
    user_id: str,
    transaction_id: Optional[str] = None,
    saved_amount: Optional[float] = None,
    transaction_type: Optional[str] = None,
) -> None:
    """Log a promotion-redemption row and bump `current_uses` atomically."""
    import uuid as _uuid
    await db.promotion_usage.insert_one({
        "id": str(_uuid.uuid4()),
        "promotion_id": promotion_id,
        "user_id": user_id,
        "transaction_id": transaction_id,
        "transaction_type": transaction_type,
        "saved_amount": saved_amount,
        "used_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.promotions.update_one(
        {"id": promotion_id},
        {"$inc": {"current_uses": 1}},
    )


__all__ = [
    "admin_promotions_router",
    "apply_active_promotions",
    "record_promotion_usage",
    "PROMOTION_TYPES",
    "PROMOTION_STATUSES",
]
