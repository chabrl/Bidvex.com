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
from datetime import datetime, timezone
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
    promotion = {
        "id": str(_uuid.uuid4()),
        "name_en": data.name_en,
        "name_fr": data.name_fr or data.name_en,
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
        if promo["type"] in ("free_platform_fee", "free_first_listing"):
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
