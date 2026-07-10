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
