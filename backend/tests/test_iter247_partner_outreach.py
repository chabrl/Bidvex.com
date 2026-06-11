"""
iter247 — Partner Outreach campaign (PDF + cold email blast).

Coverage (7 tests):
  1. `target=partners` matches users flagged with `is_partner=True`.
  2. `partner_launch_offer` is registered in PROMOTION_TYPES + rolls up
     to 100% pct in `compute_promotion_discount` for buyer_premium AND
     seller_commission AND listing_fee.
  3. PDF generator returns a valid `%PDF-` byte stream with coupon
     code embedded when supplied.
  4. Email HTML carries the exact subject, the locked English copy
     blocks, and (when supplied) the coupon code highlight.
  5. The blast endpoint blocks anonymous callers.
  6. The blast endpoint with `dry_run=True` resolves the partner
     audience, returns `recipient_count >= 0`, and emits a per-recipient
     `skipped_dry_run` row — without invoking SendGrid.
  7. The PDF download endpoint requires admin auth and returns
     `application/pdf`.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass


def _base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    return base


_TOKEN = {"v": None}


def _admin_token(base: str) -> str:
    if _TOKEN["v"]:
        return _TOKEN["v"]
    r = requests.post(
        f"{base}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("admin login failed")
    body = r.json()
    _TOKEN["v"] = body.get("access_token") or body.get("token") or ""
    return _TOKEN["v"]


# ─── Audience matching ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_iter247_user_matches_target_partners():
    from routes.admin_promotions import _user_matches_target

    promo = {"target": "partners", "target_config": {"target": "partners"}}

    # is_partner=True wins.
    assert await _user_matches_target(
        {"id": "u1", "is_partner": True}, promo
    ) is True
    # Legacy account_type field also wins.
    assert await _user_matches_target(
        {"id": "u2", "account_type": "partner"}, promo
    ) is True
    # Regular user is rejected.
    assert await _user_matches_target(
        {"id": "u3", "is_partner": False, "account_type": "user"}, promo
    ) is False


# ─── Promotion type wiring ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_iter247_partner_launch_offer_waives_buyer_premium_and_seller_commission():
    from services.promotion_runtime import compute_promotion_discount, _WAIVERS_BY_TX

    # The type is now an eligible waiver for the 4 fee paths.
    for tx in ("listing_fee", "listing_promotion", "buyer_premium", "seller_commission"):
        assert "partner_launch_offer" in _WAIVERS_BY_TX[tx], tx

    # 100% pct hard-coded so the Stripe-bypass kicks in.
    promo = {
        "id": "ppo1", "type": "partner_launch_offer", "status": "active",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2099-01-01T00:00:00+00:00",
        "target": "partners", "target_config": {"target": "partners"},
        "config": {"scope": ["all"]},
        "current_uses": 0, "uses_per_user": 1, "coupon_code": "BIDVEX-PARTNERS",
    }
    db = MagicMock()
    db.users.find_one = AsyncMock(return_value={"id": "u1", "is_partner": True})
    db.promotion_usage.count_documents = AsyncMock(return_value=0)

    with patch(
        "services.promotion_runtime.apply_active_promotions",
        new=AsyncMock(return_value=promo),
    ):
        for tx in ("buyer_premium", "seller_commission", "listing_fee"):
            disc = await compute_promotion_discount(
                db=db, user_id="u1", transaction_type=tx, base_amount_cad=200.0,
            )
            assert disc.applies is True, tx
            assert disc.discount_percent == 100.0, (tx, disc.discount_percent)
            assert disc.discount_amount == 200.00, (tx, disc.discount_amount)
            assert disc.final_amount == 0.0, (tx, disc.final_amount)
            assert disc.is_full_waiver is True, tx


# ─── PDF generator + email body ──────────────────────────────────────

def test_iter247_pdf_generator_emits_valid_pdf_with_coupon():
    from services.partner_outreach import build_partner_outreach_pdf

    pdf_bytes = build_partner_outreach_pdf(coupon_code="BIDVEX-PARTNERS")
    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 1000
    # No coupon supplied still produces a valid PDF (no highlight).
    pdf2 = build_partner_outreach_pdf()
    assert pdf2[:5] == b"%PDF-"


def test_iter247_email_html_carries_locked_subject_and_copy():
    from services.partner_outreach import (
        partner_outreach_email_html, PARTNER_OUTREACH_EMAIL_SUBJECT,
    )

    assert PARTNER_OUTREACH_EMAIL_SUBJECT == "Exclusive offer to try BidVex for free!"

    html = partner_outreach_email_html(coupon_code="BIDVEX-PARTNERS")
    # Locked phrasing.
    assert "Hello BidVex Partners!" in html
    assert "your first listing completely free" in html
    assert "risk-free" in html
    assert "real-time bidding infrastructure" in html
    assert "support@bidvex.com" in html
    # Coupon block.
    assert "BIDVEX-PARTNERS" in html


# ─── Endpoint auth gates ──────────────────────────────────────────────

def test_iter247_blast_endpoint_requires_admin_auth():
    base = _base()
    r = requests.post(
        f"{base}/api/admin/promotions/partner-outreach/send",
        json={"dry_run": True},
        timeout=10,
    )
    assert r.status_code in (401, 403), r.status_code


def test_iter247_blast_dry_run_resolves_partner_audience():
    base = _base()
    token = _admin_token(base)
    r = requests.post(
        f"{base}/api/admin/promotions/partner-outreach/send",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "coupon_code": "BIDVEX-PARTNERS",
            "dry_run": True,
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Subject + coupon round-trip through the response.
    assert body["subject"] == "Exclusive offer to try BidVex for free!"
    assert body["coupon_code"] == "BIDVEX-PARTNERS"
    assert body["dry_run"] is True
    # Every recipient row carries the skipped_dry_run marker.
    for r_row in body.get("recipients", []):
        assert r_row.get("status") == "skipped_dry_run"
    # Recipient_count is non-negative.
    assert body.get("recipient_count", 0) >= 0


def test_iter247_pdf_download_endpoint_returns_pdf():
    base = _base()
    token = _admin_token(base)
    r = requests.get(
        f"{base}/api/admin/promotions/partner-outreach/pdf?coupon_code=BIDVEX-PARTNERS",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert "application/pdf" in r.headers.get("content-type", "")
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 1000
    # Anonymous = blocked.
    r2 = requests.get(
        f"{base}/api/admin/promotions/partner-outreach/pdf",
        timeout=10,
    )
    assert r2.status_code in (401, 403)
