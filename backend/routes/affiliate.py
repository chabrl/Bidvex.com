"""
iter307 — Affiliate / Referral routes.

Endpoints (all under /api/affiliate unless noted):
  GET  /my-referral-link        Returns the caller's referral link + code.
  GET  /stats                   Full dashboard data (used by /dashboard/affiliate).
  POST /admin/credit            Admin manual credit adjust (positive or negative).
  GET  /admin/all               Admin view of every affiliate's activity.

App-level public route (mounted at app-root, NOT /api):
  GET  /r/{code}                Landing redirect — sets `bidvex_ref` cookie
                                (30-day) then 302 → / .

Commission contract (iter338 — replaces the iter307 flat $10 model):
  **3% of BidVex's net platform revenue** (buyer premium, seller commission,
  subscription payments — pre-tax, excluding Stripe pass-through fees) on
  EVERY transaction paid by a referred user, for life. Accrues as
  `platform_credits` rows (status="pending") that an admin approves before
  payout. Idempotent per (referrer, revenue_source, reference_id, payer).

Public helper (called from anywhere platform revenue is collected):
  await award_affiliate_commission(db, payer_id=..., platform_revenue=...,
                                   source=..., reference_id=...)
"""
from __future__ import annotations

import logging
import os
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

AFFILIATE_PROFIT_SHARE_RATE = 0.03  # iter338 — 3% default for general affiliates
# iter502 — Max per-rate ceiling raised to 75% (env-tunable). Kept as a
# fat-finger safeguard, not a business-logic block. Applied to every
# admin-supplied rate (flat commission_rate, tier_1_rate, tier_2_rate).
MAX_AFFILIATE_COMMISSION_RATE = float(
    os.environ.get("MAX_AFFILIATE_COMMISSION_RATE", "0.75")
)
# iter501 — Affiliate lifecycle statuses persisted on the user document
AFFILIATE_STATUSES = ("none", "pending", "active", "revoked")

# iter502 — Influencer Partner Program defaults. Applied only when the
# user's `partner_program == True`. General affiliates are untouched.
PARTNER_PROGRAM_TIER1_RATE_DEFAULT = float(
    os.environ.get("PARTNER_PROGRAM_TIER1_RATE", "0.50")
)  # 50 % for the promotional tier-1 window
PARTNER_PROGRAM_TIER1_DURATION_MONTHS_DEFAULT = int(
    os.environ.get("PARTNER_PROGRAM_TIER1_DURATION_MONTHS", "6")
)
PARTNER_PROGRAM_TIER2_RATE_DEFAULT = float(
    os.environ.get("PARTNER_PROGRAM_TIER2_RATE", "0.05")
)  # 5 % steady-state rate after the tier-1 window elapses

REFERRAL_COOKIE = "bidvex_ref"
COOKIE_MAX_AGE_DAYS = 30
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "https://bidvex.com").rstrip("/")

affiliate_router = APIRouter(prefix="/affiliate", tags=["affiliate"])

# Top-level router for the `/r/{code}` landing path (no /api prefix).
referral_redirect_router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_code(n: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # Avoid easily-confused chars
    alphabet = alphabet.translate(str.maketrans("", "", "0OIL1"))
    return "".join(secrets.choice(alphabet) for _ in range(n))


async def _ensure_referral_code(db, user_id: str) -> str:
    """Ensures the user has an `affiliate_code` field (which is the canonical
    field used by `/api/auth/register` to attribute referrals). Returns the
    code, creating a new unique one if needed.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "affiliate_code": 1})
    code = (user or {}).get("affiliate_code")
    if code:
        return code
    # Generate a unique code (3 tries — uniqueness pretty much guaranteed at n=8)
    for _ in range(3):
        candidate = _generate_code(8)
        existing = await db.users.find_one({"affiliate_code": candidate}, {"_id": 1})
        if not existing:
            await db.users.update_one({"id": user_id}, {"$set": {"affiliate_code": candidate}})
            return candidate
    raise HTTPException(status_code=500, detail="Could not generate referral code")


def _public_referral_link(code: str) -> str:
    return f"{PUBLIC_HOST}/r/{code}"


# ─── iter501 — Per-affiliate status + custom rate helpers ─────────────

def _partner_tier1_end(user_doc: Dict[str, Any]) -> Optional[datetime]:
    """Return the UTC datetime at which the tier-1 rate window expires
    for a partner, or None if the record is missing required data."""
    start = user_doc.get("partnership_start_date")
    if not start:
        return None
    if isinstance(start, str):
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(start, datetime):
        start_dt = start
    else:
        return None
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    months = user_doc.get("tier_1_duration_months")
    try:
        months = int(months) if months is not None else PARTNER_PROGRAM_TIER1_DURATION_MONTHS_DEFAULT
    except (TypeError, ValueError):
        months = PARTNER_PROGRAM_TIER1_DURATION_MONTHS_DEFAULT
    # month arithmetic: use 30.4375-day average.  Prevents relativedelta
    # dependency and keeps the boundary deterministic at the second level.
    return start_dt + timedelta(days=months * 30.4375)


def _clamp(rate: float) -> float:
    """Clamp a rate to [0, MAX_AFFILIATE_COMMISSION_RATE] — read-side
    defensive guard, used by ``_resolve_effective_rate`` so a stale
    out-of-range value in the DB never blocks a legitimate award."""
    if rate < 0:
        return 0.0
    if rate > MAX_AFFILIATE_COMMISSION_RATE:
        return MAX_AFFILIATE_COMMISSION_RATE
    return rate


def _resolve_effective_rate(
    user_doc: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> float:
    """Return the commission rate to apply for this user *right now*.

    Precedence (iter502):
      1. Explicit flat ``commission_rate`` override — an admin escape
         hatch that wins over everything else.  Setting it to ``None``
         re-enables the automatic path.
      2. Influencer Partner Program tier schedule — if
         ``partner_program`` is True, compute live:
             now < partnership_start_date + tier_1_duration_months
                 → tier_1_rate  (default 50 %)
             otherwise
                 → tier_2_rate  (default  5 %)
      3. Global default ``AFFILIATE_PROFIT_SHARE_RATE`` (3 %).

    ``now`` is injectable for tests; production omits it and gets UTC now.
    Never raises — falls back to the global default on any malformed data.
    """
    if not user_doc:
        return AFFILIATE_PROFIT_SHARE_RATE

    # 1) Explicit flat override wins — but a zero rate has no business
    #    meaning (use "revoked" status to stop accrual instead), so we
    #    treat 0.0 as "no override" and fall through to the tier
    #    schedule / global default.  This also protects partners whose
    #    commission_rate got accidentally cleared to 0 by a bad UI save.
    raw = user_doc.get("commission_rate")
    if raw is not None:
        try:
            rate = float(raw)
            if 0 < rate <= MAX_AFFILIATE_COMMISSION_RATE:
                return rate
        except (TypeError, ValueError):
            pass

    # 2) Partner Program tier schedule.
    if user_doc.get("partner_program") is True:
        tier1_end = _partner_tier1_end(user_doc)
        # If no start date recorded, we still honour the tier config using
        # the tier_1_rate (opening period) rather than the global 3 %.
        if tier1_end is None:
            try:
                r1 = float(user_doc.get("tier_1_rate", PARTNER_PROGRAM_TIER1_RATE_DEFAULT))
            except (TypeError, ValueError):
                r1 = PARTNER_PROGRAM_TIER1_RATE_DEFAULT
            return _clamp(r1)

        current = (now or datetime.now(timezone.utc))
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)

        if current < tier1_end:
            try:
                r1 = float(user_doc.get("tier_1_rate", PARTNER_PROGRAM_TIER1_RATE_DEFAULT))
            except (TypeError, ValueError):
                r1 = PARTNER_PROGRAM_TIER1_RATE_DEFAULT
            return _clamp(r1)
        try:
            r2 = float(user_doc.get("tier_2_rate", PARTNER_PROGRAM_TIER2_RATE_DEFAULT))
        except (TypeError, ValueError):
            r2 = PARTNER_PROGRAM_TIER2_RATE_DEFAULT
        return _clamp(r2)

    # 3) Global default.
    return AFFILIATE_PROFIT_SHARE_RATE


def _has_custom_rate(user_doc: Optional[Dict[str, Any]]) -> bool:
    """True iff the user has an *intentional* non-null non-zero flat
    ``commission_rate`` override.  Distinct from ``_resolve_effective_rate``
    which returns the applied number: this returns whether that number
    came from an explicit escape-hatch override or from the tier /
    default path.  Used by the affiliate dashboard to decide whether to
    show the ``(custom rate)`` tag."""
    if not user_doc:
        return False
    raw = user_doc.get("commission_rate")
    if raw is None:
        return False
    try:
        return float(raw) > 0
    except (TypeError, ValueError):
        return False


def _partner_tier_snapshot(
    user_doc: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """iter503 — Public serialization of the partner-program state used
    by the affiliate dashboard.  Returns the fields the UI needs to
    render the correct copy without duplicating rate-resolution logic
    on the client:
        partner_program      : bool
        partner_tier         : "tier_1" | "tier_2" | None
        tier_1_rate          : float | None
        tier_2_rate          : float | None
        tier_1_duration_months: int | None
        partnership_start_date: ISO string | None
        tier_ends_at         : ISO string | None (only while in tier 1)
        has_custom_rate      : bool  (see _has_custom_rate)
    """
    partner_program = bool((user_doc or {}).get("partner_program"))
    has_custom = _has_custom_rate(user_doc)
    partner_tier = None
    tier_ends_at = None
    if partner_program and not has_custom:
        end_dt = _partner_tier1_end(user_doc or {})
        if end_dt is None:
            partner_tier = "tier_1"
        else:
            cur = now or datetime.now(timezone.utc)
            if cur.tzinfo is None:
                cur = cur.replace(tzinfo=timezone.utc)
            partner_tier = "tier_1" if cur < end_dt else "tier_2"
            if partner_tier == "tier_1":
                tier_ends_at = end_dt.isoformat()
    return {
        "partner_program": partner_program,
        "partner_tier": partner_tier,
        "tier_1_rate": (user_doc or {}).get("tier_1_rate"),
        "tier_2_rate": (user_doc or {}).get("tier_2_rate"),
        "tier_1_duration_months": (user_doc or {}).get("tier_1_duration_months"),
        "partnership_start_date": (user_doc or {}).get("partnership_start_date"),
        "tier_ends_at": tier_ends_at,
        "has_custom_rate": has_custom,
    }


def _validate_rate(value: Any) -> Optional[float]:
    """Validate an admin-supplied commission rate.

    Returns the coerced float on success, raises HTTPException(400) with
    a clear bilingual message on any failure.  A `None` input is
    returned as `None` (means: clear the override and fall back to the
    global default).
    """
    if value is None:
        return None
    try:
        rate = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={
            "error": "invalid_commission_rate",
            "message_en": "commission_rate must be a number between 0 and "
                          f"{MAX_AFFILIATE_COMMISSION_RATE:.2f} (or null).",
            "message_fr": "Le taux de commission doit être un nombre entre 0 et "
                          f"{MAX_AFFILIATE_COMMISSION_RATE:.2f} (ou nul).",
        })
    if rate < 0 or rate > MAX_AFFILIATE_COMMISSION_RATE:
        raise HTTPException(status_code=400, detail={
            "error": "commission_rate_out_of_range",
            "message_en": (
                f"commission_rate must be between 0 and "
                f"{MAX_AFFILIATE_COMMISSION_RATE:.2f} "
                f"(got {rate:.4f})."
            ),
            "message_fr": (
                f"Le taux de commission doit être entre 0 et "
                f"{MAX_AFFILIATE_COMMISSION_RATE:.2f} "
                f"(reçu {rate:.4f})."
            ),
            "min": 0.0,
            "max": MAX_AFFILIATE_COMMISSION_RATE,
        })
    return rate


async def _write_affiliate_admin_log(
    db,
    *,
    admin: User,
    target_user_id: str,
    action: str,
    before: Dict[str, Any],
    after: Dict[str, Any],
    note: str = "",
) -> None:
    """Reuses the same admin_action_logs shape as admin_credit_affiliate."""
    await db.admin_action_logs.insert_one({
        "ts": _now().isoformat(),
        "admin_id": admin.id,
        "admin_email": getattr(admin, "email", "") or "",
        "action": action,
        "target_user_id": target_user_id,
        "before": before,
        "after": after,
        "note": (note or "")[:500],
    })


# ─── /api/affiliate/my-referral-link ─────────────────────────────────

@affiliate_router.get("/my-referral-link")
async def get_my_referral_link(current_user: User = Depends(get_current_user)):
    db = get_db()
    code = await _ensure_referral_code(db, current_user.id)
    return {"referral_code": code, "referral_link": _public_referral_link(code)}


# ─── /api/affiliate/stats lives in misc.py (iter307-extended) ─────────
# Kept as a single source of truth — see `misc.py::get_affiliate_stats`.


# ─── /api/affiliate/admin/all ────────────────────────────────────────

@affiliate_router.get("/admin/all")
async def admin_list_affiliates(current_user: User = Depends(get_current_user)):
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    # iter501 — Roster of everyone the admin might want to manage:
    #   • Users with any `affiliate_status` explicitly set (pending, active, revoked)
    #   • Users who already have at least one referred signup (referred_count > 0)
    # This ensures newly-pending users show up even before their first referral.

    # 1) Aggregate referred_count per referral code.
    pipeline = [
        {"$match": {"referred_by_code": {"$ne": None, "$exists": True}}},
        {"$group": {"_id": "$referred_by_code", "referred_count": {"$sum": 1}}},
    ]
    referred_counts: Dict[str, int] = {}
    async for row in db.users.aggregate(pipeline):
        referred_counts[row["_id"]] = row["referred_count"]

    # 2) Anyone with an explicit affiliate_status OR at least one referred user.
    or_clauses: List[Dict[str, Any]] = [
        {"affiliate_status": {"$in": ["pending", "active", "revoked"]}},
    ]
    if referred_counts:
        or_clauses.append({"affiliate_code": {"$in": list(referred_counts.keys())}})

    items: List[Dict[str, Any]] = []
    async for u in db.users.find(
        {"$or": or_clauses},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "affiliate_code": 1,
         "affiliate_status": 1, "commission_rate": 1, "created_at": 1,
         # iter502 — Influencer Partner Program fields.
         "partner_program": 1, "partnership_start_date": 1,
         "tier_1_rate": 1, "tier_1_duration_months": 1, "tier_2_rate": 1},
    ):
        code = u.get("affiliate_code") or ""
        credits_total = 0.0
        async for c in db.platform_credits.find(
            {"user_id": u["id"], "source": "referral"},
            {"_id": 0, "amount": 1},
        ):
            credits_total += float(c.get("amount") or 0)
        effective_rate = _resolve_effective_rate(u)
        items.append({
            **u,
            "affiliate_status": (u.get("affiliate_status") or "none"),
            "commission_rate": u.get("commission_rate"),
            "effective_rate": effective_rate,
            "referred_count": referred_counts.get(code, 0),
            "total_credits_earned": round(credits_total, 2),
            # iter502 — normalized partner-program snapshot for the UI.
            "partner_program": bool(u.get("partner_program")),
            "partnership_start_date": u.get("partnership_start_date"),
            "tier_1_rate": u.get("tier_1_rate"),
            "tier_1_duration_months": u.get("tier_1_duration_months"),
            "tier_2_rate": u.get("tier_2_rate"),
        })
    items.sort(key=lambda x: (-x["referred_count"], x.get("email") or ""))
    return {
        "items": items,
        "total": len(items),
        "default_rate": AFFILIATE_PROFIT_SHARE_RATE,
        "max_rate": MAX_AFFILIATE_COMMISSION_RATE,
        # iter502 — expose the partner-program defaults so the UI can
        # pre-fill the form when an admin enables the program for a
        # user who has never had these fields set.
        "partner_program_defaults": {
            "tier_1_rate": PARTNER_PROGRAM_TIER1_RATE_DEFAULT,
            "tier_1_duration_months": PARTNER_PROGRAM_TIER1_DURATION_MONTHS_DEFAULT,
            "tier_2_rate": PARTNER_PROGRAM_TIER2_RATE_DEFAULT,
        },
    }


# ─── /api/affiliate/admin/set-status ─────────────────────────────────
# iter501 — Approve / revoke an affiliate.  Optional commission_rate
# override applied in the same call.
# iter502 — Also accepts Influencer Partner Program fields:
#     partner_program, tier_1_rate, tier_1_duration_months, tier_2_rate,
#     partnership_start_date

# Fields written to the user document for partner-program members.
_PARTNER_PROJECTION = {
    "_id": 0, "id": 1, "email": 1, "affiliate_status": 1,
    "commission_rate": 1, "affiliate_code": 1,
    "partner_program": 1, "partnership_start_date": 1,
    "tier_1_rate": 1, "tier_1_duration_months": 1, "tier_2_rate": 1,
}


def _validate_partner_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """iter502 — Coerce & validate Influencer-Partner-Program overrides.

    Returns a dict of ONLY the fields the caller provided (empty dict if
    none were provided).  Rate fields are clamped by ``_validate_rate``
    so out-of-range values raise HTTPException(400).
    """
    out: Dict[str, Any] = {}
    if "partner_program" in payload:
        out["partner_program"] = bool(payload.get("partner_program"))
    if "tier_1_rate" in payload:
        out["tier_1_rate"] = _validate_rate(payload.get("tier_1_rate"))
    if "tier_2_rate" in payload:
        out["tier_2_rate"] = _validate_rate(payload.get("tier_2_rate"))
    if "tier_1_duration_months" in payload:
        raw = payload.get("tier_1_duration_months")
        if raw is None:
            out["tier_1_duration_months"] = None
        else:
            try:
                months = int(raw)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail={
                    "error": "invalid_tier_1_duration_months",
                    "message_en": "tier_1_duration_months must be a positive integer.",
                    "message_fr": "tier_1_duration_months doit être un entier positif.",
                })
            if months <= 0 or months > 120:
                raise HTTPException(status_code=400, detail={
                    "error": "tier_1_duration_out_of_range",
                    "message_en": "tier_1_duration_months must be between 1 and 120.",
                    "message_fr": "tier_1_duration_months doit être entre 1 et 120.",
                })
            out["tier_1_duration_months"] = months
    if "partnership_start_date" in payload:
        raw = payload.get("partnership_start_date")
        if raw is None or raw == "":
            out["partnership_start_date"] = None
        elif isinstance(raw, str):
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(status_code=400, detail={
                    "error": "invalid_partnership_start_date",
                    "message_en": "partnership_start_date must be an ISO 8601 string.",
                    "message_fr": "partnership_start_date doit être une chaîne ISO 8601.",
                })
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            out["partnership_start_date"] = parsed.isoformat()
        else:
            raise HTTPException(status_code=400, detail={
                "error": "invalid_partnership_start_date",
                "message_en": "partnership_start_date must be a string or null.",
                "message_fr": "partnership_start_date doit être une chaîne ou null.",
            })
    return out


@affiliate_router.post("/admin/set-status")
async def admin_set_affiliate_status(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    user_id = (payload.get("user_id") or "").strip()
    status = (payload.get("status") or "").strip().lower()
    note = (payload.get("note") or "")[:500]

    if not user_id:
        raise HTTPException(status_code=400, detail={
            "error": "missing_user_id",
            "message_en": "user_id is required.",
            "message_fr": "user_id est requis.",
        })
    if status not in ("active", "revoked"):
        raise HTTPException(status_code=400, detail={
            "error": "invalid_status",
            "message_en": 'status must be "active" or "revoked".',
            "message_fr": 'status doit être « active » ou « revoked ».',
        })

    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, _PARTNER_PROJECTION)
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    before_status = (user_doc.get("affiliate_status") or "none").lower()
    before_rate = user_doc.get("commission_rate")
    before_partner_snapshot = {
        "partner_program": user_doc.get("partner_program"),
        "partnership_start_date": user_doc.get("partnership_start_date"),
        "tier_1_rate": user_doc.get("tier_1_rate"),
        "tier_1_duration_months": user_doc.get("tier_1_duration_months"),
        "tier_2_rate": user_doc.get("tier_2_rate"),
    }

    # Optional rate override — None means "clear override".
    new_rate: Optional[float] = None
    rate_provided = "commission_rate" in payload
    if rate_provided:
        new_rate = _validate_rate(payload.get("commission_rate"))

    # iter502 — Partner Program field overrides.
    partner_updates = _validate_partner_fields(payload)

    # Make sure they have a referral code once they become active.
    if status == "active" and not user_doc.get("affiliate_code"):
        await _ensure_referral_code(db, user_id)

    updates: Dict[str, Any] = {"affiliate_status": status}
    if rate_provided:
        updates["commission_rate"] = new_rate
    updates.update(partner_updates)

    # iter502 — When flipping a user into the partner program AND we don't
    # already have a start date on file (either persisted or supplied in
    # this same payload), stamp `partnership_start_date` = activation time
    # so the tier-1 window begins immediately.
    if (
        updates.get("partner_program") is True
        and "partnership_start_date" not in payload
        and not user_doc.get("partnership_start_date")
    ):
        updates["partnership_start_date"] = _now().isoformat()

    # Idempotency — noop if nothing actually changes.  Include partner
    # fields in the equality check so re-submitting an identical payload
    # (same status + same tier config) skips both the DB write and audit.
    partner_unchanged = all(
        before_partner_snapshot.get(k) == v
        for k, v in partner_updates.items()
    )
    unchanged = (
        before_status == status
        and (not rate_provided or before_rate == new_rate)
        and partner_unchanged
        and "partnership_start_date" not in updates  # auto-stamp is a change
    )
    if not unchanged:
        await db.users.update_one({"id": user_id}, {"$set": updates})
        after_partner_snapshot = {
            **before_partner_snapshot,
            **{k: v for k, v in updates.items()
               if k in before_partner_snapshot},
        }
        await _write_affiliate_admin_log(
            db,
            admin=current_user,
            target_user_id=user_id,
            action="affiliate_status_change",
            before={"affiliate_status": before_status,
                    "commission_rate": before_rate,
                    **before_partner_snapshot},
            after={"affiliate_status": status,
                   "commission_rate": new_rate if rate_provided else before_rate,
                   **after_partner_snapshot},
            note=note,
        )

    # Reload for the response.
    fresh = await db.users.find_one({"id": user_id}, _PARTNER_PROJECTION) or {}
    return {
        "success": True,
        "changed": not unchanged,
        "user_id": user_id,
        "affiliate_status": fresh.get("affiliate_status") or "none",
        "commission_rate": fresh.get("commission_rate"),
        "effective_rate": _resolve_effective_rate(fresh),
        "default_rate": AFFILIATE_PROFIT_SHARE_RATE,
        "affiliate_code": fresh.get("affiliate_code"),
        # iter502 — surface the current partner-program snapshot
        "partner_program": bool(fresh.get("partner_program")),
        "partnership_start_date": fresh.get("partnership_start_date"),
        "tier_1_rate": fresh.get("tier_1_rate"),
        "tier_1_duration_months": fresh.get("tier_1_duration_months"),
        "tier_2_rate": fresh.get("tier_2_rate"),
    }


# ─── /api/affiliate/admin/set-rate ───────────────────────────────────
# iter501 — Adjust an affiliate's rate WITHOUT touching their status.

@affiliate_router.post("/admin/set-rate")
async def admin_set_affiliate_rate(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """iter501/iter502 — Adjust an affiliate's rate WITHOUT touching status.

    Accepts either:
      • ``commission_rate`` — the classic flat override (iter501)
      • Any subset of ``partner_program``, ``tier_1_rate``,
        ``tier_1_duration_months``, ``tier_2_rate``,
        ``partnership_start_date`` — the Influencer Partner tier schedule
        (iter502).  Enrolling in ``partner_program=True`` auto-stamps
        ``partnership_start_date=now`` if none is already set.

    At least one of the above must be provided in the body.
    """
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    user_id = (payload.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail={
            "error": "missing_user_id",
            "message_en": "user_id is required.",
            "message_fr": "user_id est requis.",
        })

    rate_provided = "commission_rate" in payload
    partner_updates = _validate_partner_fields(payload)
    if not rate_provided and not partner_updates:
        raise HTTPException(status_code=400, detail={
            "error": "missing_rate",
            "message_en": (
                "Provide at least one of: commission_rate, partner_program, "
                "tier_1_rate, tier_1_duration_months, tier_2_rate, "
                "partnership_start_date."
            ),
            "message_fr": (
                "Fournir au moins un de : commission_rate, partner_program, "
                "tier_1_rate, tier_1_duration_months, tier_2_rate, "
                "partnership_start_date."
            ),
        })

    new_rate = _validate_rate(payload.get("commission_rate")) if rate_provided else None
    note = (payload.get("note") or "")[:500]

    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, _PARTNER_PROJECTION)
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    before_rate = user_doc.get("commission_rate")
    before_partner_snapshot = {
        "partner_program": user_doc.get("partner_program"),
        "partnership_start_date": user_doc.get("partnership_start_date"),
        "tier_1_rate": user_doc.get("tier_1_rate"),
        "tier_1_duration_months": user_doc.get("tier_1_duration_months"),
        "tier_2_rate": user_doc.get("tier_2_rate"),
    }

    updates: Dict[str, Any] = {}
    if rate_provided:
        updates["commission_rate"] = new_rate
    updates.update(partner_updates)

    # Auto-stamp partnership_start_date if the caller just enabled the
    # partner program and neither the payload nor DB has a start date.
    if (
        updates.get("partner_program") is True
        and "partnership_start_date" not in payload
        and not user_doc.get("partnership_start_date")
    ):
        updates["partnership_start_date"] = _now().isoformat()

    partner_unchanged = all(
        before_partner_snapshot.get(k) == v
        for k, v in partner_updates.items()
    )
    unchanged = (
        (not rate_provided or before_rate == new_rate)
        and partner_unchanged
        and "partnership_start_date" not in updates
    )

    if not unchanged:
        await db.users.update_one({"id": user_id}, {"$set": updates})
        after_partner_snapshot = {
            **before_partner_snapshot,
            **{k: v for k, v in updates.items()
               if k in before_partner_snapshot},
        }
        await _write_affiliate_admin_log(
            db,
            admin=current_user,
            target_user_id=user_id,
            action="affiliate_rate_change",
            before={"commission_rate": before_rate,
                    "affiliate_status": (user_doc.get("affiliate_status") or "none"),
                    **before_partner_snapshot},
            after={"commission_rate": new_rate if rate_provided else before_rate,
                   "affiliate_status": (user_doc.get("affiliate_status") or "none"),
                   **after_partner_snapshot},
            note=note,
        )

    fresh = await db.users.find_one({"id": user_id}, _PARTNER_PROJECTION) or {}
    return {
        "success": True,
        "changed": not unchanged,
        "user_id": user_id,
        "affiliate_status": fresh.get("affiliate_status") or "none",
        "commission_rate": fresh.get("commission_rate"),
        "effective_rate": _resolve_effective_rate(fresh),
        "default_rate": AFFILIATE_PROFIT_SHARE_RATE,
        # iter502 — surface the current partner-program snapshot
        "partner_program": bool(fresh.get("partner_program")),
        "partnership_start_date": fresh.get("partnership_start_date"),
        "tier_1_rate": fresh.get("tier_1_rate"),
        "tier_1_duration_months": fresh.get("tier_1_duration_months"),
        "tier_2_rate": fresh.get("tier_2_rate"),
    }


# ─── /api/affiliate/admin/backfill-active ─────────────────────────────
# iter501 — Idempotent migration. Sets `affiliate_status="active"` for any
# user who was already earning under the pre-iter501 no-gate model:
#   • has at least one platform_credits row with source="referral", OR
#   • has referred_count > 0 (some user has `referred_by_code` == their code)
# Runs automatically on backend startup once, and is also exposed here so
# ops can re-run it after a DB restore / migration.  Never revokes;
# never overrides commission_rate; existing values win.

async def _backfill_active_affiliates(db) -> Dict[str, int]:
    """Returns {"promoted": int, "skipped_already_set": int}."""
    seen_ids: set[str] = set()

    # 1) Anyone with a referral platform_credit row.
    async for c in db.platform_credits.find(
        {"source": "referral"}, {"_id": 0, "user_id": 1},
    ):
        uid = c.get("user_id")
        if uid:
            seen_ids.add(uid)

    # 2) Anyone whose affiliate_code has been used by another user
    #    (referred_by_code matches).  Aggregate → set of codes with count > 0.
    used_codes: set[str] = set()
    async for row in db.users.aggregate([
        {"$match": {"referred_by_code": {"$ne": None, "$exists": True}}},
        {"$group": {"_id": "$referred_by_code"}},
    ]):
        code = row.get("_id")
        if code:
            used_codes.add(code)
    if used_codes:
        async for u in db.users.find(
            {"affiliate_code": {"$in": list(used_codes)}},
            {"_id": 0, "id": 1},
        ):
            if u.get("id"):
                seen_ids.add(u["id"])

    if not seen_ids:
        return {"promoted": 0, "skipped_already_set": 0}

    # Only touch users whose affiliate_status is missing OR "none".  Any
    # explicit prior status (pending/active/revoked) wins.
    result = await db.users.update_many(
        {"id": {"$in": list(seen_ids)},
         "$or": [{"affiliate_status": {"$exists": False}},
                 {"affiliate_status": None},
                 {"affiliate_status": "none"}]},
        {"$set": {"affiliate_status": "active"}},
    )
    promoted = int(getattr(result, "modified_count", 0) or 0)
    return {
        "promoted": promoted,
        "skipped_already_set": len(seen_ids) - promoted,
        "candidates": len(seen_ids),
    }


@affiliate_router.post("/admin/backfill-active")
async def admin_backfill_active_affiliates(current_user: User = Depends(get_current_user)):
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    result = await _backfill_active_affiliates(db)
    logger.info(f"[iter501 backfill] {result}")
    return {"success": True, **result}


@affiliate_router.post("/admin/credit")
async def admin_credit_affiliate(payload: Dict[str, Any],
                                   current_user: User = Depends(get_current_user)):
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    user_id = payload.get("user_id")
    amount = float(payload.get("amount") or 0)
    if not user_id or amount == 0:
        raise HTTPException(status_code=400, detail="user_id and non-zero amount required")
    note = payload.get("note") or ""
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.platform_credits.insert_one({
        "id": f"ADM-{_now().timestamp():.0f}-{secrets.token_hex(3)}",
        "user_id": user_id,
        "amount": amount,
        "currency": "CAD",
        "source": "admin_adjust",
        "status": "paid" if amount > 0 else "reversed",
        "admin_id": current_user.id,
        "note": note[:500],
        "created_at": _now().isoformat(),
    })
    await db.admin_action_logs.insert_one({
        "ts": _now().isoformat(),
        "admin_id": current_user.id,
        "admin_email": getattr(current_user, "email", "") or "",
        "action": "affiliate_credit_adjust",
        "target_user_id": user_id,
        "amount": amount,
        "note": note[:500],
    })
    return {"success": True}


@affiliate_router.get("/track/{code}")
async def track_referral_click(code: str, request: Request):
    """Lightweight click logger called by the React `/r/{code}` route.

    The actual 30-day cookie is set client-side (the React route does
    `document.cookie = 'bidvex_ref=...'`) because external traffic on
    /r/{code} hits the frontend SPA, not the backend.
    """
    try:
        db = get_db()
        await db.referral_clicks.insert_one({
            "code": code,
            "ts": _now().isoformat(),
            "ip": (request.client.host if request.client else "anon")[:64],
            "ua": (request.headers.get("user-agent") or "")[:200],
        })
    except Exception:
        pass
    return {"success": True, "code": code, "cookie_max_age_days": COOKIE_MAX_AGE_DAYS}


# ─── Public landing: /r/{code} ───────────────────────────────────────
# NOTE: External traffic to /r/{code} is routed to the FRONTEND (port 3000)
# by the kubernetes ingress because it doesn't carry the /api prefix.
# The React app handles it client-side (see `src/pages/ReferralLanding.jsx`)
# which sets the cookie + calls /api/affiliate/track/{code} then redirects.
# This backend route remains for direct curl/test access.

@referral_redirect_router.get("/r/{code}")
async def referral_landing(code: str, request: Request, response: Response):
    """Public 302 redirect that drops a 30-day `bidvex_ref` cookie.

    Idempotent. Does not require the code to match an existing affiliate
    (we attribute on register; invalid codes simply never convert).
    """
    # Build absolute redirect target — keep query params except `r`.
    target = f"{PUBLIC_HOST}/"
    qp = dict(request.query_params)
    qp.pop("r", None)
    if qp:
        from urllib.parse import urlencode
        target += "?" + urlencode(qp)
    resp = RedirectResponse(url=target, status_code=302)
    resp.set_cookie(
        REFERRAL_COOKIE,
        value=code,
        max_age=COOKIE_MAX_AGE_DAYS * 24 * 3600,
        httponly=False,  # readable by frontend so /register can attach it
        samesite="lax",
        secure=PUBLIC_HOST.startswith("https"),
        path="/",
    )
    # Best-effort click log (non-blocking)
    try:
        db = get_db()
        await db.referral_clicks.insert_one({
            "code": code,
            "ts": _now().isoformat(),
            "ip": (request.client.host if request.client else "anon")[:64],
            "ua": (request.headers.get("user-agent") or "")[:200],
        })
    except Exception:
        pass
    return resp


# ─── Commission engine — 3% of platform profit (iter338) ─────────────

async def award_affiliate_commission(
    db,
    *,
    payer_id: str,
    platform_revenue: float,
    source: str,                      # "auction_buyer_fee" | "auction_seller_fee" | "subscription"
    reference_id: str,
    description: str = "",
) -> Optional[Dict[str, Any]]:
    """Award the payer's referrer 3% of the net platform revenue BidVex
    earned on this transaction.

    Rules:
       • the payer must have been attributed at registration (`referred_by_code`),
       • lifetime — fires on EVERY qualifying payment, no cap,
       • `platform_revenue` is BidVex's pocketed fee (pre-tax, excluding
         Stripe pass-through), NOT the transaction value,
       • idempotent per (referrer, source, reference_id, payer),
       • accrues as a pending `platform_credits` row for admin approval.
    """
    if not payer_id or not platform_revenue or float(platform_revenue) <= 0:
        return None
    payer = await db.users.find_one(
        {"id": payer_id},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "referred_by_code": 1, "first_paid_at": 1},
    )
    if not payer:
        return None
    # Track conversion (referral dashboards mark "converted" off this stamp)
    if not payer.get("first_paid_at"):
        await db.users.update_one({"id": payer_id}, {"$set": {"first_paid_at": _now().isoformat()}})
    code = payer.get("referred_by_code")
    if not code:
        return None
    referrer = await db.users.find_one(
        {"affiliate_code": code, "id": {"$ne": payer_id}},
        {"_id": 0, "id": 1, "name": 1, "preferred_language": 1,
         # iter502 — pull the partner-program fields so
         # _resolve_effective_rate can compute the tier live.
         "affiliate_status": 1, "commission_rate": 1,
         "partner_program": 1, "partnership_start_date": 1,
         "tier_1_rate": 1, "tier_1_duration_months": 1, "tier_2_rate": 1},
    )
    if not referrer:
        return None

    # iter501 — Approval gate. Referral clicks / attribution are unchanged;
    # only commission ACCRUAL is gated on `affiliate_status == "active"`.
    status = (referrer.get("affiliate_status") or "none").lower()
    if status != "active":
        logger.debug(
            "[iter501] Skipping affiliate commission for referrer=%s status=%s "
            "payer=%s source=%s ref=%s",
            referrer["id"], status, payer_id, source, reference_id,
        )
        return None

    # Idempotency guard — one credit per (referrer, source, reference, payer)
    existing = await db.platform_credits.find_one(
        {"user_id": referrer["id"], "source": "referral",
         "revenue_source": source, "reference_id": reference_id,
         "referred_user_id": payer_id},
        {"_id": 1},
    )
    if existing:
        return None

    # iter501 — Resolve effective rate (custom override or global default).
    # The rate that fires TODAY is snapshotted onto the credit row so the
    # historical ledger never retroactively changes if an admin adjusts
    # the affiliate's rate later.
    effective_rate = _resolve_effective_rate(referrer)
    amount = round(float(platform_revenue) * effective_rate, 2)
    if amount < 0.01:
        return None

    credit_doc = {
        "id": f"REF-{_now().timestamp():.0f}-{secrets.token_hex(3)}",
        "user_id": referrer["id"],
        "amount": amount,
        "currency": "CAD",
        "source": "referral",
        "status": "pending",  # admin approves → "paid"
        "commission_base": round(float(platform_revenue), 2),
        "commission_rate": effective_rate,
        "revenue_source": source,
        "reference_id": reference_id,
        "description": (description or "")[:200],
        "referred_user_id": payer_id,
        "referred_user_name": payer.get("name") or "",
        "created_at": _now().isoformat(),
    }
    await db.platform_credits.insert_one(credit_doc)

    # Notify referrer (bell + push, both best-effort)
    try:
        from services.notifications_i18n import create_notification
        await create_notification(
            db, user_id=referrer["id"], kind="referral_credit_earned",
            params={"amount": amount, "referred_name": (payer.get("name") or "").split(" ")[0]},
            data={"action_url": "/dashboard/affiliate"},
        )
    except Exception:
        pass
    try:
        from services.push_dispatcher import dispatch_push
        fr = (referrer.get("preferred_language") or "").startswith("fr")
        first_name = (payer.get("name") or "Someone").split(" ")[0]
        rate_pct = effective_rate * 100
        await dispatch_push(
            db, user_id=referrer["id"], kind="new_message",  # reuse a generic kind
            sender_name="BidVex Rewards",
            preview=(
                f"Vous avez gagné {amount:.2f} $ CAD — commission de "
                f"{rate_pct:g} % sur une transaction de {first_name} !"
                if fr else
                f"You earned ${amount:.2f} CAD — {rate_pct:g}% commission "
                f"on {first_name}'s transaction!"
            ),
            url="/dashboard/affiliate",
        )
    except Exception:
        pass

    logger.info(
        f"[iter501] Affiliate commission ${amount:.2f} ({effective_rate*100:g}% of "
        f"${float(platform_revenue):.2f}) awarded: referrer={referrer['id']} "
        f"payer={payer_id} source={source} ref={reference_id}"
    )
    return credit_doc


# ─── iter339 — Earnings summary + commission-events feed ─────────────

def mask_referred_name(full_name: str) -> str:
    """Privacy — 'Alex Brown' → 'Alex B.'; never expose full names/emails."""
    parts = [p for p in (full_name or "").strip().split() if p]
    if not parts:
        return "User"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[1][0].upper()}."


def _parse_dt(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _shift_month(year: int, month: int, delta: int) -> tuple:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def compute_projection(monthly: Dict[tuple, float], now: datetime) -> tuple:
    """projected_next_month = avg of the last 3 COMPLETED calendar months.
    If activity started this month, use the current month (basis 1).
    Returns (projection, basis_months)."""
    if not monthly:
        return 0.0, 0
    earliest = min(monthly.keys())
    this_key = (now.year, now.month)
    candidates = [_shift_month(now.year, now.month, -d) for d in (1, 2, 3)]
    considered = [k for k in candidates if k >= earliest]
    if not considered:
        considered = [this_key]
    basis = len(considered)
    projection = round(sum(monthly.get(k, 0.0) for k in considered) / basis, 2)
    return projection, basis


async def _load_commission_rows(db, user_id: str) -> List[Dict[str, Any]]:
    """Merged ledger: iter338 platform_credits (referral) + legacy affiliate_earnings."""
    rows: List[Dict[str, Any]] = []
    async for c in db.platform_credits.find(
        {"user_id": user_id, "source": "referral"},
        {"_id": 0, "amount": 1, "commission_base": 1, "created_at": 1,
         "status": 1, "referred_user_id": 1},
    ):
        rows.append({
            "amount": float(c.get("amount") or 0),
            "base": float(c.get("commission_base") or 0),
            "created_at": _parse_dt(c.get("created_at")),
            "status": c.get("status") or "pending",
            "referred_user_id": c.get("referred_user_id"),
        })
    async for e in db.affiliate_earnings.find(
        {"affiliate_id": user_id},
        {"_id": 0, "commission_amount": 1, "created_at": 1, "status": 1,
         "referred_user_id": 1},
    ):
        rows.append({
            "amount": float(e.get("commission_amount") or 0),
            "base": 0.0,
            "created_at": _parse_dt(e.get("created_at")),
            "status": e.get("status") or "pending",
            "referred_user_id": e.get("referred_user_id"),
        })
    return rows


@affiliate_router.get("/earnings-summary")
async def get_earnings_summary(current_user: User = Depends(get_current_user)):
    """iter339 — Lifetime / monthly earnings + transparent 3-month projection."""
    db = get_db()
    rows = await _load_commission_rows(db, current_user.id)
    now = _now()
    this_key = (now.year, now.month)
    last_key = _shift_month(now.year, now.month, -1)

    monthly: Dict[tuple, float] = {}
    this_month = {"earned": 0.0, "transaction_count": 0, "platform_fees_generated": 0.0}
    last_month = {"earned": 0.0, "transaction_count": 0}
    lifetime = {"earned": 0.0, "transaction_count": 0}
    pending_approval = 0.0
    active_payers_this_month = set()

    for r in rows:
        lifetime["earned"] += r["amount"]
        lifetime["transaction_count"] += 1
        if r["status"] == "pending":
            pending_approval += r["amount"]
        dt = r["created_at"]
        if not dt:
            continue
        key = (dt.year, dt.month)
        monthly[key] = monthly.get(key, 0.0) + r["amount"]
        if key == this_key:
            this_month["earned"] += r["amount"]
            this_month["transaction_count"] += 1
            this_month["platform_fees_generated"] += r["base"]
            if r.get("referred_user_id"):
                active_payers_this_month.add(r["referred_user_id"])
        elif key == last_key:
            last_month["earned"] += r["amount"]
            last_month["transaction_count"] += 1

    projection, basis = compute_projection(monthly, now)

    referred_total = 0
    code = getattr(current_user, "affiliate_code", None)
    if not code:
        u = await db.users.find_one({"id": current_user.id}, {"_id": 0, "affiliate_code": 1})
        code = (u or {}).get("affiliate_code")
    if code:
        referred_total = await db.users.count_documents({"referred_by_code": code})

    # iter501 — Resolve the affiliate's effective rate (custom override or
    # global default) so their dashboard shows the real number they earn.
    # iter502 — Also surface partner-program metadata so the UI can render
    # a tier badge / countdown when applicable.
    _user_doc = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "affiliate_status": 1, "commission_rate": 1,
         "partner_program": 1, "partnership_start_date": 1,
         "tier_1_rate": 1, "tier_1_duration_months": 1, "tier_2_rate": 1},
    ) or {}
    effective_rate = _resolve_effective_rate(_user_doc)

    # iter503 — Consolidated partner-tier snapshot for the UI (also
    # includes has_custom_rate so the dashboard can show the "(custom rate)"
    # tag only when there's an actual intentional flat override).
    tier_snapshot = _partner_tier_snapshot(_user_doc)

    return {
        "this_month": {
            "earned": round(this_month["earned"], 2),
            "transaction_count": this_month["transaction_count"],
            "platform_fees_generated": round(this_month["platform_fees_generated"], 2),
        },
        "last_month": {
            "earned": round(last_month["earned"], 2),
            "transaction_count": last_month["transaction_count"],
        },
        "lifetime": {
            "earned": round(lifetime["earned"], 2),
            "transaction_count": lifetime["transaction_count"],
        },
        "projected_next_month": projection,
        "projection_basis_months": basis,
        "referred_users": {
            "total": referred_total,
            "active_this_month": len(active_payers_this_month),
        },
        "pending_approval": round(pending_approval, 2),
        "commission_rate": effective_rate,
        "default_commission_rate": AFFILIATE_PROFIT_SHARE_RATE,
        "affiliate_status": (_user_doc.get("affiliate_status") or "none"),
        # iter502/503 — Partner Program tier snapshot for the dashboard.
        **tier_snapshot,
    }


@affiliate_router.get("/commission-events")
async def get_commission_events(
    page: int = 1,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
):
    """iter339 — Paginated activity feed of commission events with
    privacy-masked referred-user names (first name + last initial)."""
    db = get_db()
    page = max(1, int(page))
    limit = max(1, min(50, int(limit)))
    q = {"user_id": current_user.id, "source": "referral"}
    total = await db.platform_credits.count_documents(q)
    cursor = (db.platform_credits.find(q, {"_id": 0})
              .sort("created_at", -1)
              .skip((page - 1) * limit).limit(limit))
    items: List[Dict[str, Any]] = []
    async for c in cursor:
        name = c.get("referred_user_name") or ""
        if not name and c.get("referred_user_id"):
            u = await db.users.find_one({"id": c["referred_user_id"]}, {"_id": 0, "name": 1})
            name = (u or {}).get("name") or ""
        items.append({
            "id": c.get("id"),
            "date": c.get("created_at"),
            "referred_user": mask_referred_name(name),
            "revenue_source": c.get("revenue_source") or "transaction",
            "platform_fee": round(float(c.get("commission_base") or 0), 2),
            "commission": round(float(c.get("amount") or 0), 2),
            "rate": float(c.get("commission_rate") or AFFILIATE_PROFIT_SHARE_RATE),
            "status": c.get("status") or "pending",
            "description": c.get("description") or "",
        })
    return {"items": items, "total": total, "page": page, "limit": limit,
            "has_more": page * limit < total}


# ─── iter340 P1 — "Share My Projection" social card ───────────────────

SHARE_CARD_DAILY_LIMIT = 10


@affiliate_router.get("/share-card")
async def get_share_card(lang: str = "en",
                         current_user: User = Depends(get_current_user)):
    """On-demand 600×315 PNG share card (Pillow + QR). Never stored in S3.
    Rate-limited to 10 generations per affiliate per day."""
    import asyncio
    from pymongo import ReturnDocument
    from services.share_card import build_share_card_png

    db = get_db()
    lang = "fr" if str(lang or "").lower().startswith("fr") else "en"

    today = _now().date().isoformat()
    counter = await db.share_card_generations.find_one_and_update(
        {"user_id": current_user.id, "date": today},
        {"$inc": {"count": 1},
         "$setOnInsert": {"user_id": current_user.id, "date": today}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    if (counter or {}).get("count", 1) > SHARE_CARD_DAILY_LIMIT:
        raise HTTPException(429, "Daily share-card limit reached (10/day). Try again tomorrow.")

    code = await _ensure_referral_code(db, current_user.id)
    rows = await _load_commission_rows(db, current_user.id)
    now = _now()
    monthly: Dict[tuple, float] = {}
    for r in rows:
        dt = r["created_at"]
        if dt:
            key = (dt.year, dt.month)
            monthly[key] = monthly.get(key, 0.0) + r["amount"]
    projection, _basis = compute_projection(monthly, now)

    png = await asyncio.to_thread(
        build_share_card_png, projection, _public_referral_link(code), lang)
    return Response(
        content=png, media_type="image/png",
        headers={
            "Content-Disposition": 'inline; filename="bidvex-earnings-projection.png"',
            "Cache-Control": "no-store",
        },
    )
