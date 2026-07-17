"""
iter330 — Summer 2026 promo API.

Exposes:
    GET  /api/promo/state                 → current user's promo state.
    POST /api/promo/trial/activate        → mark trial as redeemed for a tier.
    POST /api/promo/first-listing-free/consume
                                          → idempotent consume of the waiver flag,
                                            called by the listing-promotion path.

The trial-activation endpoint is a server-of-record. It does NOT create new
Stripe Subscriptions — that's still owned by routes/subscriptions.py and
services/dealer_subscription_service.py, which consult
services.trial_promo.is_trial_eligible() before calling
stripe.Subscription.create() with trial_period_days=TRIAL_DAYS.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Body

from routes.auth import get_current_user_from_token
from services.trial_promo import (
    TRIAL_ELIGIBLE_TIERS,
    TRIAL_DAYS,
    is_trial_eligible,
    mark_trial_redeemed,
    try_consume_first_listing_free,
    get_promo_state,
)

logger = logging.getLogger("promo")

router = APIRouter()


def _get_db():
    from server import db as _db  # late import — DB is bound on app startup
    return _db


@router.get("/promo/share/summer-launch")
async def summer_launch_share_page():
    """iter341 — Crawler-friendly share URL. Social crawlers (Facebook, X,
    LinkedIn) don't execute JS, so the SPA's Helmet tags are invisible to
    them; this endpoint serves the OG tags in raw HTML and meta-redirects
    humans to the real landing page.

    iter356 — Aligned all URLs to canonical `https://www.bidvex.com` (was
    apex `https://bidvex.com`, which the apex→www 308 rule immediately
    redirected — a wasted round trip and a duplicate-content signal)."""
    from fastapi.responses import HTMLResponse
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>BidVex Grand Opening — First Month FREE</title>'
        '<meta property="og:title" content="BidVex Grand Opening — First Month FREE">'
        '<meta property="og:description" content="Canada\'s new bilingual auction marketplace is live. '
        'List free, bid free, sell smarter. Vehicles, Marketplace, Lots &amp; Storage.">'
        '<meta property="og:image" content="https://www.bidvex.com/static/og/summer-launch-promo.png">'
        '<meta property="og:image:width" content="1200">'
        '<meta property="og:image:height" content="628">'
        '<meta property="og:url" content="https://www.bidvex.com/promo/summer-launch">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<meta name="twitter:image" content="https://www.bidvex.com/static/og/summer-launch-promo.png">'
        '<link rel="canonical" href="https://www.bidvex.com/promo/summer-launch">'
        '<meta http-equiv="refresh" content="0;url=https://www.bidvex.com/promo/summer-launch">'
        '</head><body>Redirecting to <a href="https://www.bidvex.com/promo/summer-launch">'
        'www.bidvex.com/promo/summer-launch</a>…</body></html>'
    )
    return HTMLResponse(content=html)


@router.get("/promo/state")
async def get_my_promo_state(current_user=Depends(get_current_user_from_token)):
    """Returns the calling user's trial + first-listing-free state."""
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_user")
    db = _get_db()
    state = await get_promo_state(db, user_id)
    state["trial_days"] = TRIAL_DAYS
    state["eligible_tiers"] = list(TRIAL_ELIGIBLE_TIERS)
    return state


@router.post("/promo/trial/activate")
async def activate_trial(
    payload: dict = Body(...),
    current_user=Depends(get_current_user_from_token),
):
    """Mark the trial as redeemed for `tier`.

    Body: {"tier": "premium" | "vip" | "partner" | "partner_pro" | "vehicle_dealer" | "storage_facility"}
    """
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_user")
    tier_raw = (payload or {}).get("tier")
    if not tier_raw:
        raise HTTPException(status_code=400, detail="tier_required")
    tier = str(tier_raw).lower()
    if tier not in TRIAL_ELIGIBLE_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"tier_not_trial_eligible (must be one of {list(TRIAL_ELIGIBLE_TIERS)})",
        )

    db = _get_db()
    if not await is_trial_eligible(db, user_id, tier=tier):
        raise HTTPException(status_code=409, detail="trial_already_redeemed")

    ok = await mark_trial_redeemed(db, user_id, tier)
    if not ok:
        raise HTTPException(status_code=409, detail="trial_already_redeemed")

    state = await get_promo_state(db, user_id)
    state["trial_days"] = TRIAL_DAYS
    return {"success": True, **state}


@router.post("/promo/first-listing-free/consume")
async def consume_first_listing_free(current_user=Depends(get_current_user_from_token)):
    """Idempotently consume the first-listing-free waiver.

    Returns:
        {"consumed": True}  if the waiver was just now used (caller should waive
                            the next listing/promotion fee)
        {"consumed": False} if the user had already used the waiver previously
    """
    user_id = current_user.get("id") if isinstance(current_user, dict) else getattr(current_user, "id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_user")
    db = _get_db()
    consumed = await try_consume_first_listing_free(db, user_id)
    return {"consumed": consumed}


__all__ = ["router"]
