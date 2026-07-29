"""
iter408 — Unified coupon / promotion cross-collection resolver.

BidVex currently exposes THREE places where an admin can mint a code:

  1. `coupon_codes`         — Admin → Coupon Codes    (subscription discounts)
  2. `promotions`           — Admin → Promotions      (fee / listing discounts)
  3. `partner_trial_coupons`— Admin → Partner Trial   (30/60/45-day free trial)

Historically each entry point (subscription checkout, partner dashboard,
partner-trial preview) only queried ONE collection, so a code minted in
"Coupon Codes" was rejected at partner-dashboard checkout, and a
"Promotions" code was rejected at subscription checkout. This module
centralises the lookup + validation predicates so every entry point can
resolve a code created via ANY of the three admin surfaces.

The public API:

    from services.coupon_lookup import (
        find_in_coupon_codes,   # apply is_active + expiry + usage_limit + applicable_plans
        find_in_promotions,     # apply status + start_date + end_date + max_uses
        find_in_trial_coupons,  # apply status='issued' + not expired
    )

Each returns `(doc, reason)`:
  * `doc`     — the raw MongoDB document if a **valid** match exists.
  * `reason`  — one of `None | "not_found" | "expired" | "usage_limit"
                       | "plan_mismatch" | "status" | "date_window"
                       | "max_uses"`.

Callers stay responsible for shaping the result into their own response
envelope (CouponValidationResult, promotion-dict, or preview payload) —
this module is intentionally opinion-free about that so it can be reused
without ripple changes.

Contract note (does NOT change how codes are stored — task item #4):
  * The three collections keep their existing schemas.
  * Case normalisation: all callers should upper-case + trim the code
    before calling the helpers below (matches existing behaviour).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Re-export the return-shape as a plain tuple to keep the module dep-free.
LookupResult = Tuple[Optional[Dict[str, Any]], Optional[str]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    """Tolerate naive strings, `Z`-suffixed strings, and datetime objects.

    iter409 — Always returns a **timezone-aware** datetime (UTC when the
    source lacked tzinfo). This is critical because
    `datetime.now(timezone.utc)` is aware, and comparing an aware value
    to a naive one raises ``TypeError: can't compare offset-naive and
    offset-aware datetimes`` which used to bubble up as a 500 on
    ``coupon_lookup.find_in_*`` callers and crash the frontend.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def find_in_coupon_codes(
    db,
    code: str,
    *,
    plan_id: Optional[str] = None,
) -> LookupResult:
    """Mirror of `subscription_pricing.validate_coupon`'s predicates.

    Applies: `is_active=true` filter (baked into the query), expiry,
    usage_limit, and applicable_plans (when `plan_id` is provided).
    """
    if not code:
        return (None, "not_found")
    doc = await db.coupon_codes.find_one({"code": code.upper().strip(), "is_active": True})
    if not doc:
        return (None, "not_found")

    expiry_at = _parse_iso(doc.get("expiry_date"))
    if expiry_at and expiry_at < datetime.now(timezone.utc):
        return (None, "expired")

    usage_limit = doc.get("usage_limit", 0) or 0
    if usage_limit > 0 and (doc.get("usage_count", 0) or 0) >= usage_limit:
        return (None, "usage_limit")

    if plan_id is not None:
        applicable: List[str] = doc.get("applicable_plans") or ["premium", "vip"]
        if plan_id not in applicable:
            return (None, "plan_mismatch")

    return (doc, None)


async def find_in_promotions(
    db,
    code: str,
    *,
    plan_id: Optional[str] = None,
) -> LookupResult:
    """Mirror of `apply_active_promotions`'s predicates.

    Applies: `status='active'`, `start_date <= now <= end_date`, and
    `max_uses` (vs `current_uses`). When `plan_id` is provided we also
    honour `config.applicable_plans` if the campaign encodes one (some
    subscription-discount promos do).
    """
    if not code:
        return (None, "not_found")
    doc = await db.promotions.find_one({"coupon_code": code.upper().strip()}, {"_id": 0})
    if not doc:
        return (None, "not_found")

    if doc.get("status") != "active":
        return (None, "status")

    now = datetime.now(timezone.utc)
    start_at = _parse_iso(doc.get("start_date"))
    end_at   = _parse_iso(doc.get("end_date"))
    if start_at and start_at > now:
        return (None, "date_window")
    if end_at and end_at < now:
        return (None, "date_window")

    max_uses = doc.get("max_uses") or 0
    if max_uses > 0 and (doc.get("current_uses", 0) or 0) >= max_uses:
        return (None, "max_uses")

    if plan_id is not None:
        cfg = doc.get("config", {}) or {}
        applicable: Optional[List[str]] = cfg.get("applicable_plans")
        if applicable and plan_id not in applicable:
            return (None, "plan_mismatch")

    return (doc, None)


async def find_in_trial_coupons(db, code: str) -> LookupResult:
    """Mirror of `trial_coupons.preview_coupon` predicates.

    Applies: `status='issued'` and `expires_at > now`.
    """
    if not code:
        return (None, "not_found")
    doc = await db.partner_trial_coupons.find_one({"code": code.upper().strip()}, {"_id": 0})
    if not doc:
        return (None, "not_found")

    if doc.get("status") != "issued":
        return (None, "status")

    expires_at = _parse_iso(doc.get("expires_at"))
    if expires_at and expires_at < datetime.now(timezone.utc):
        return (None, "expired")

    return (doc, None)


# ─── Shape helpers ────────────────────────────────────────────────────
#
# Callers can convert a `coupon_codes` doc into a promotion-shaped dict
# (for the fee/checkout pipeline that only knows how to consume
# promotion dicts) using this synthesiser. It is intentionally
# conservative: unknown fields are set to sane defaults.


def synthesize_promotion_from_coupon_code(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a `coupon_codes` row into a promotion-shaped dict so the
    promotion-runtime pipeline can consume it without branching.

    We map the discount to `type='subscription_discount'` with
    `config.discount_percent` — matches the semantics of coupon_codes
    (which only target subscription plans, per its `applicable_plans`).
    The synthetic id is deterministic so `record_promotion_usage()` etc.
    can key off it without colliding with real promotion ids.
    """
    percent = 0.0
    dtype = (doc.get("discount_type") or "percentage").lower()
    if dtype == "percentage":
        try:
            percent = float(doc.get("value") or 0)
        except (TypeError, ValueError):
            percent = 0.0
    # Fixed-amount coupons cannot be expressed as a percentage without
    # knowing the base; the promotion pipeline is percentage-based, so
    # we fall through to 0% here — the subscription-checkout path (which
    # goes through `validate_coupon` directly) handles fixed correctly.

    return {
        "id":              f"synthetic_coupon::{doc.get('id') or doc.get('code')}",
        "coupon_code":     doc.get("code"),
        "type":            "subscription_discount",
        "status":          "active",
        "config":          {
            "discount_percent": percent,
            "scope":            ["all"],
            "applicable_plans": doc.get("applicable_plans") or ["premium", "vip"],
        },
        "max_uses":        doc.get("usage_limit") or 0,
        "current_uses":    doc.get("usage_count", 0) or 0,
        "source":          "coupon_codes",  # audit hint (never written back)
    }


__all__ = [
    "find_in_coupon_codes",
    "find_in_promotions",
    "find_in_trial_coupons",
    "synthesize_promotion_from_coupon_code",
]
