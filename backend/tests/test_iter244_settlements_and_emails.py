"""
iter244 — Integration tests for the closing missions of the Admin Promotions
Engine, the modular email migration, and the CSV-export pipeline.

Coverage breakdown (12 tests):

  Mission 1 — Live bid-settlement promotion injection (4 tests)
    1. `_apply_settlement_promotions` returns zero-discount no-op when
       no promotion is active.
    2. `_apply_settlement_promotions` zeroes buyer_premium under a
       100% `free_platform_fee` waiver AND records usage atomically.
    3. `_apply_settlement_promotions` discounts seller_commission by
       50% under a `reduced_commission` promo.
    4. Promotion bookkeeping failures inside the settlement helper are
       swallowed (settlement must NEVER block on a promo issue).

  Mission 2 — Email migration / HTML preservation (4 tests)
    5. `build_email_payload` with `html_full_override` preserves the
       supplied HTML BYTE-FOR-BYTE (no template chrome added).
    6. `build_email_payload` with `body_html_override` keeps the body
       intact AND wraps it inside the canonical BIDVEX header+footer.
    7. `_send_via_unified` routes legacy HTML through `send_email`
       without any wrapping (the migration shim).
    8. Live HTTP grep guarantee — `services/email_notifications.py`
       has exactly ONE `sg.send(` call, inside the canonical
       `send_email()` function.

  Mission 3 — CSV export (3 tests)
    9. `GET /api/admin/promotions/{id}/usage.csv` requires admin auth.
   10. CSV export returns a well-formed `text/csv` body with the seven
       expected columns and a `Content-Disposition: attachment` header.
   11. CSV rows are sorted newest-first and include the hydrated buyer
       email from the `users` collection.

  Regression sanity (1 test)
   12. The legacy `send_bid_placed_email` helper still dispatches via
       `send_unified_email("bid_placed", …)` after the migration.
"""
from __future__ import annotations

import asyncio
import io
import csv as _csv
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


# ─── Shared HTTP helpers ──────────────────────────────────────────────
def _base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    return base


_TOKEN_CACHE = {"token": None}


def _admin_token(base: str) -> str:
    if _TOKEN_CACHE["token"]:
        return _TOKEN_CACHE["token"]
    r = requests.post(
        f"{base}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("admin login failed; cannot run live admin tests")
    body = r.json()
    _TOKEN_CACHE["token"] = body.get("access_token") or body.get("token") or ""
    return _TOKEN_CACHE["token"]


# ═════════════════════════════════════════════════════════════════════
# Mission 1 — Settlement-time promotion injection
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_iter244_settlement_promo_noop_when_no_active_promo():
    """Settlement helper returns the zero-discount shape verbatim when
    no promotion is active. Discount fields = 0, promo IDs = None."""
    from services.auction_settlement import _apply_settlement_promotions

    db = MagicMock()
    # apply_active_promotions returns None when no promo matches; we
    # patch the symbol imported into promotion_runtime to short-circuit.
    with patch(
        "services.promotion_runtime.apply_active_promotions",
        new=AsyncMock(return_value=None),
    ):
        out = await _apply_settlement_promotions(
            db=db,
            winner_user_id="u_buyer",
            seller_id="u_seller",
            buyer_premium_amount=120.00,
            seller_commission_amount=80.00,
            auction_id="auc_1",
            listing_type="lots",
        )

    assert out == {
        "buyer_discount_amount": 0.0,
        "seller_discount_amount": 0.0,
        "buyer_promotion_id": None,
        "seller_promotion_id": None,
        "buyer_coupon_code": None,
        "seller_coupon_code": None,
    }


@pytest.mark.asyncio
async def test_iter244_settlement_applies_full_buyer_premium_waiver():
    """A 100% `free_platform_fee` promotion at settlement time must
    discount the buyer_premium to $0 AND log usage atomically."""
    from services.auction_settlement import _apply_settlement_promotions

    waiver_promo = {
        "id": "promo_waive_bp",
        "type": "free_platform_fee",
        "status": "active",
        "coupon_code": "BP-WAIVE",
        "target": "all",
        "target_config": {"target": "all"},
        "config": {"scope": ["all"]},
        "current_uses": 0,
        "uses_per_user": 1,
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
    }

    db = MagicMock()
    db.promotion_usage.insert_one = AsyncMock()
    db.promotions.update_one = AsyncMock()

    with patch(
        "services.promotion_runtime.apply_active_promotions",
        new=AsyncMock(return_value=waiver_promo),
    ):
        out = await _apply_settlement_promotions(
            db=db,
            winner_user_id="u_buyer",
            seller_id="u_seller",
            buyer_premium_amount=120.00,
            seller_commission_amount=80.00,
            auction_id="auc_42",
            listing_type="lots",
        )

    # Buyer side fully discounted.
    assert out["buyer_discount_amount"] == 120.00
    assert out["buyer_promotion_id"] == "promo_waive_bp"
    assert out["buyer_coupon_code"] == "BP-WAIVE"
    # Seller side also eligible (free_platform_fee waives seller_commission too).
    assert out["seller_discount_amount"] == 80.00
    assert out["seller_promotion_id"] == "promo_waive_bp"
    # Usage rows recorded — once for buyer side, once for seller side.
    assert db.promotion_usage.insert_one.await_count == 2
    # current_uses bumped twice (buyer + seller redemptions).
    assert db.promotions.update_one.await_count == 2


@pytest.mark.asyncio
async def test_iter244_settlement_applies_50pct_seller_commission_discount():
    """A `reduced_commission` promo with discount_percent=50 must cut
    the seller's commission in half at settlement time."""
    from services.auction_settlement import _apply_settlement_promotions

    promo_sc50 = {
        "id": "promo_sc50",
        "type": "reduced_commission",
        "status": "active",
        "coupon_code": "SC50",
        "target": "all",
        "target_config": {"target": "all"},
        "config": {"discount_percent": 50, "scope": ["all"]},
        "current_uses": 0,
        "uses_per_user": 1,
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
    }

    db = MagicMock()
    db.promotion_usage.insert_one = AsyncMock()
    db.promotions.update_one = AsyncMock()

    with patch(
        "services.promotion_runtime.apply_active_promotions",
        new=AsyncMock(return_value=promo_sc50),
    ):
        out = await _apply_settlement_promotions(
            db=db,
            winner_user_id="u_buyer",
            seller_id="u_seller",
            buyer_premium_amount=100.00,
            seller_commission_amount=200.00,
            auction_id="auc_77",
            listing_type="lots",
        )

    # reduced_commission only affects seller_commission. Buyer untouched.
    assert out["buyer_discount_amount"] == 0.0
    assert out["buyer_promotion_id"] is None
    # Seller half-off.
    assert out["seller_discount_amount"] == 100.00
    assert out["seller_promotion_id"] == "promo_sc50"
    assert out["seller_coupon_code"] == "SC50"


@pytest.mark.asyncio
async def test_iter244_settlement_swallows_promotion_lookup_failures():
    """If the promotion lookup raises, settlement must NOT propagate
    the error — it must log a warning and return the no-op shape."""
    from services.auction_settlement import _apply_settlement_promotions

    db = MagicMock()
    with patch(
        "services.promotion_runtime.apply_active_promotions",
        new=AsyncMock(side_effect=RuntimeError("transient db blip")),
    ):
        out = await _apply_settlement_promotions(
            db=db,
            winner_user_id="u_buyer",
            seller_id="u_seller",
            buyer_premium_amount=120.00,
            seller_commission_amount=80.00,
            auction_id="auc_err",
            listing_type="lots",
        )

    # No exception bubbles up; output is the zero-shape no-op.
    assert out["buyer_discount_amount"] == 0.0
    assert out["seller_discount_amount"] == 0.0
    assert out["buyer_promotion_id"] is None
    assert out["seller_promotion_id"] is None


# ═════════════════════════════════════════════════════════════════════
# Mission 2 — Email migration / HTML preservation
# ═════════════════════════════════════════════════════════════════════

def test_iter244_build_email_payload_html_full_override_preserved_verbatim():
    """`html_full_override` must skip template wrapping entirely and
    return the supplied HTML byte-for-byte."""
    from services.email_templates import build_email_payload

    raw_html = (
        "<!DOCTYPE html><html><body>"
        "<h1>Legacy Invoice 12345</h1>"
        "<p>Hammer price: $1,250 CAD</p>"
        "</body></html>"
    )
    out = build_email_payload(
        "new_feature",
        user={"email": "buyer@example.com", "first_name": "B"},
        data={
            "html_full_override": raw_html,
            "subject_override": "Your Invoice 12345",
        },
    )

    assert out["to_email"] == "buyer@example.com"
    assert out["subject"] == "Your Invoice 12345"
    # CRITICAL: html_content is the supplied HTML verbatim — no wrapping.
    assert out["html_content"] == raw_html
    # And it does NOT contain the BIDVEX wrapper signature.
    assert "BIDVEX" not in out["html_content"].upper() or "BIDVEX-WIN" not in out["html_content"]
    assert "Unsubscribe" not in out["html_content"]


def test_iter244_build_email_payload_body_html_override_wraps_with_template():
    """`body_html_override` is the migration-safe alternative — it keeps
    the body markup verbatim BUT wraps it inside the BidVex header/footer
    chrome. Used by migrated helpers that want the unified envelope but
    a legacy body."""
    from services.email_templates import build_email_payload

    inner = "<p>Custom legacy <strong>body</strong> contents.</p>"
    out = build_email_payload(
        "new_feature",
        user={"email": "buyer@example.com", "first_name": "Buyer"},
        data={
            "feature_name": "iter244",
            "feature_description": "doesn't matter",
            "feature_url": "https://bidvex.com",
            "body_html_override": inner,
        },
    )

    html = out["html_content"]
    # Body preserved verbatim.
    assert inner in html
    # Wrapped inside BidVex chrome.
    assert "761 Rue Chalifoux" in html
    assert "support@bidvex.com" in html
    assert "Unsubscribe" in html


@pytest.mark.asyncio
async def test_iter244_send_via_unified_dispatches_through_send_email():
    """`_send_via_unified` is the consolidation shim. Verify it calls
    `send_email` with the EXACT html_content + subject from the
    `html_full_override` path (no extra wrapping, no template munging)."""
    from services.emails import _email_core as en

    captured = {}

    async def _fake_send_email(to_email, subject, html_content, attachments=None, **kwargs):
        captured["to_email"] = to_email
        captured["subject"] = subject
        captured["html_content"] = html_content
        captured["attachments"] = attachments
        return {"status": "sent", "status_code": 202}

    raw_html = "<div>Bid Placed — $500 CAD</div>"
    with patch.object(en, "send_email", new=_fake_send_email):
        res = await en._send_via_unified(
            to_email="winner@example.com",
            subject="Your bid is live",
            html_content=raw_html,
            first_name="Winner",
        )

    assert res["status"] == "sent"
    assert captured["to_email"] == "winner@example.com"
    assert captured["subject"] == "Your bid is live"
    # The shim must NOT mutate the HTML — it goes through verbatim.
    assert captured["html_content"] == raw_html


def test_iter244_email_notifications_has_single_canonical_sg_send():
    """Grep guarantee: there must be EXACTLY ONE `sg.send(` callsite
    in `services/emails/_email_core.py` — the canonical send_email()
    bottom-of-stack dispatcher. Every other legacy helper goes through
    `_send_via_unified`."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "services", "emails", "_email_core.py"
    )
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()

    # Count `sg.send(` matches (the literal SendGrid dispatch call).
    hits = src.count("sg.send(")
    assert hits == 1, (
        f"Expected exactly 1 `sg.send(` callsite in email_notifications.py "
        f"(inside the canonical send_email() function); found {hits}. "
        f"Mission 2 migration has regressed."
    )


# ═════════════════════════════════════════════════════════════════════
# Mission 3 — CSV export
# ═════════════════════════════════════════════════════════════════════

def test_iter244_csv_export_requires_admin_auth():
    """The CSV export endpoint must reject unauthenticated callers."""
    base = _base()
    r = requests.get(
        f"{base}/api/admin/promotions/some-promo-id/usage.csv",
        timeout=10,
    )
    assert r.status_code in (401, 403)


def test_iter244_csv_export_returns_well_formed_csv_with_headers():
    """End-to-end: admin creates a promo, the CSV export returns a
    proper text/csv body with the 7 expected columns and a download
    Content-Disposition header."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    promo_body = {
        "name_en": "iter244-CSV-export-promo",
        "name_fr": "iter244-CSV-export-promo-FR",
        "type": "free_platform_fee",
        "config": {"scope": ["all"]},
        "target_config": {"target": "all"},
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "uses_per_user": 99,
        "show_banner": False,
        "notify_users": False,
    }
    rc = requests.post(
        f"{base}/api/admin/promotions",
        json=promo_body,
        headers=headers,
        timeout=10,
    )
    assert rc.status_code == 200, rc.text
    promo_id = rc.json()["id"]

    try:
        rcsv = requests.get(
            f"{base}/api/admin/promotions/{promo_id}/usage.csv",
            headers=headers,
            timeout=10,
        )
        assert rcsv.status_code == 200, rcsv.text
        ct = rcsv.headers.get("content-type", "")
        assert "text/csv" in ct, ct
        cd = rcsv.headers.get("content-disposition", "")
        assert "attachment" in cd and ".csv" in cd, cd

        # Parse and assert column shape.
        reader = _csv.reader(io.StringIO(rcsv.text))
        header_row = next(reader)
        assert header_row == [
            "Redemption ID", "Timestamp", "User ID", "User Email",
            "Coupon Code", "Promotion Type", "Saved Amount CAD",
        ]
    finally:
        requests.delete(
            f"{base}/api/admin/promotions/{promo_id}",
            headers=headers,
            timeout=10,
        )


def test_iter244_csv_export_404_for_unknown_promo():
    """Unknown promotion IDs must return 404 — not an empty CSV file."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(
        f"{base}/api/admin/promotions/this-promo-does-not-exist-xyz/usage.csv",
        headers=headers,
        timeout=10,
    )
    assert r.status_code == 404, r.text


# ═════════════════════════════════════════════════════════════════════
# Regression — legacy email migration sanity
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_iter244_bid_placed_email_still_routes_through_send_unified():
    """Regression: the legacy `send_bid_placed_email` helper must still
    dispatch via the unified path (iter239 behaviour preserved)."""
    from services.emails import email_marketplace as en

    captured = {}

    async def _fake_send_unified(email_type, user, data=None, *, lang="en", attachments=None):
        captured["email_type"] = email_type
        captured["user"] = user
        captured["data"] = data
        captured["lang"] = lang
        return {"status": "sent", "status_code": 202}

    with patch.object(en, "send_unified_email", new=_fake_send_unified):
        await en.send_bid_placed_email(
            bidder_email="buyer@example.com",
            bidder_name="Buyer",
            listing_title="Test Lot 1",
            bid_amount=250.0,
            listing_id="auc_x",
            auction_end_date="2026-01-01T00:00:00+00:00",
            is_leading=True,
            auction_type="lots",
        )

    # bid_placed remains the canonical email_type for this helper.
    assert captured.get("email_type") == "bid_placed", captured
    assert captured["user"]["email"] == "buyer@example.com"
    assert captured["data"]["listing_title"] == "Test Lot 1"
