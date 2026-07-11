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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

AFFILIATE_PROFIT_SHARE_RATE = 0.03  # iter338 — 3% of BidVex's platform profit
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
    # Affiliates = anyone with a referral_code AND at least one referred user.
    pipeline = [
        {"$match": {"referred_by_code": {"$ne": None, "$exists": True}}},
        {"$group": {"_id": "$referred_by_code", "referred_count": {"$sum": 1}}},
    ]
    referred_counts: Dict[str, int] = {}
    async for row in db.users.aggregate(pipeline):
        referred_counts[row["_id"]] = row["referred_count"]

    items: List[Dict[str, Any]] = []
    if referred_counts:
        async for u in db.users.find(
            {"affiliate_code": {"$in": list(referred_counts.keys())}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "affiliate_code": 1, "created_at": 1},
        ):
            code = u["affiliate_code"]
            credits_total = 0.0
            async for c in db.platform_credits.find(
                {"user_id": u["id"], "source": "referral"},
                {"_id": 0, "amount": 1},
            ):
                credits_total += float(c.get("amount") or 0)
            items.append({
                **u,
                "referred_count": referred_counts.get(code, 0),
                "total_credits_earned": round(credits_total, 2),
            })
    return {"items": sorted(items, key=lambda x: -x["referred_count"]), "total": len(items)}


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
        {"_id": 0, "id": 1, "name": 1, "preferred_language": 1},
    )
    if not referrer:
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

    amount = round(float(platform_revenue) * AFFILIATE_PROFIT_SHARE_RATE, 2)
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
        "commission_rate": AFFILIATE_PROFIT_SHARE_RATE,
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
        await dispatch_push(
            db, user_id=referrer["id"], kind="new_message",  # reuse a generic kind
            sender_name="BidVex Rewards",
            preview=(f"Vous avez gagné {amount:.2f} $ CAD — commission de 3 % sur une transaction de {first_name} !"
                     if fr else
                     f"You earned ${amount:.2f} CAD — 3% commission on {first_name}'s transaction!"),
            url="/dashboard/affiliate",
        )
    except Exception:
        pass

    logger.info(
        f"[iter338] Affiliate commission ${amount:.2f} (3% of ${float(platform_revenue):.2f}) "
        f"awarded: referrer={referrer['id']} payer={payer_id} source={source} ref={reference_id}"
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
        "commission_rate": AFFILIATE_PROFIT_SHARE_RATE,
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
