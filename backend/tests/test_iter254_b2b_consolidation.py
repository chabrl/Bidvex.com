"""
iter254 — Consolidation sprint: role-gated B2B coupon activation,
forced-language broadcast override, and outbound email branding.

Test roster (10 tests):

  Mission 1 — Role-gated coupon activation:
    1. `POST /api/promotions/activate-to-account` requires authentication.
    2. Non-B2B account (account_type="personal", is_partner=False,
       is_storage_facility=False) → 403 with the locked rejection copy.
    3. Admin/B2B account with a valid coupon → `activated=True` + locked
       English/French success copy + `partner_offer_active` flipped on
       the user record.
    4. Invalid coupon → `activated=False` + locked error copy.

  Mission 2 — Inline checkout coupon: already covered by iter253
    test_iter253_partner_coupon_input.py; no new tests needed.

  Mission 3 — Forced-language override:
    5. `forced_lang="fr"` on the blast endpoint routes ALL recipients
       to the French variant regardless of their province.
    6. `forced_lang="en"` routes ALL recipients to English regardless
       of profile.
    7. `forced_lang=None` (default) falls back to per-recipient
       `detect_partner_language` (back-compat with iter247-iter253).
    8. Response surfaces the resolved `forced_lang` field for the UI
       toast subtitle.

  Mission 4 — Email branding constants:
    9. `B2B_PARTNER_FROM_EMAIL == "partners@bidvex.ca"` and
       `TRANSACTIONAL_FROM_EMAIL == "support@bidvex.com"`.
   10. `send_email()` accepts and propagates `from_email`/`from_name`/
       `reply_to` overrides to the SendGrid Mail message (verified via
       the logged-only fallback path).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

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


_TOKEN = {"admin": None, "buyer_jwt": None}


def _admin_token(base: str) -> str:
    if _TOKEN["admin"]:
        return _TOKEN["admin"]
    r = requests.post(
        f"{base}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("admin login failed")
    body = r.json()
    _TOKEN["admin"] = body.get("access_token") or body.get("token") or ""
    return _TOKEN["admin"]


def _forge_buyer_jwt() -> str:
    """Forge a non-admin JWT so the role-gate can be exercised even when
    real buyer logins are rate-limited."""
    if _TOKEN["buyer_jwt"]:
        return _TOKEN["buyer_jwt"]
    try:
        from jose import jwt as _jose_jwt
        # Use a real existing buyer user id from the DB so the gate hits.
        # We seed a minimal user record via Mongo first.
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio as _asyncio
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "bazario_db")
        if not mongo_url:
            pytest.skip("MONGO_URL required to seed buyer user")
        user_id = f"iter254-buyer-{uuid.uuid4().hex[:8]}"

        async def _seed():
            client = AsyncIOMotorClient(mongo_url)
            try:
                await client[db_name].users.insert_one({
                    "id": user_id,
                    "email": f"{user_id}@example.com",
                    "name": "iter254 Test Buyer",
                    "first_name": "Buyer",
                    "role": "user",
                    "account_type": "personal",
                    "status": "active",
                    "is_partner": False,
                    "is_storage_facility": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            finally:
                client.close()
        _asyncio.run(_seed())
        secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
        payload = {
            "sub": user_id, "email": f"{user_id}@example.com",
            "role": "user",
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=20)).timestamp()),
            "type": "access",
        }
        _TOKEN["buyer_jwt"] = _jose_jwt.encode(payload, secret, algorithm="HS256")
        return _TOKEN["buyer_jwt"]
    except Exception:
        pytest.skip("could not forge buyer JWT")
        return ""  # unreachable


# ─── Mission 1 — Role-gated coupon activation ────────────────────────

def test_iter254_activate_to_account_requires_authentication():
    base = _base()
    r = requests.post(
        f"{base}/api/promotions/activate-to-account",
        json={"coupon_code": "BIDVEX-PARTNERS"},
        timeout=10,
    )
    assert r.status_code in (401, 403)


def test_iter254_activate_to_account_blocks_non_b2b_accounts():
    """A personal/buyer account must be rejected with 403 + the locked
    'reserved for professional B2B accounts' message."""
    base = _base()
    buyer_token = _forge_buyer_jwt()
    r = requests.post(
        f"{base}/api/promotions/activate-to-account",
        json={"coupon_code": "BIDVEX-PARTNERS"},
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 403, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "b2b" in detail or "professional" in detail or "partner" in detail


def test_iter254_activate_to_account_persists_on_admin_b2b_account():
    """Admin counts as B2B (role==admin) — activate a fresh promo on
    their account and assert `partner_offer_active=True` lands."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    # Create a transient promo we know admin can activate.
    body = {
        "name_en": f"iter254-act-{uuid.uuid4().hex[:6]}",
        "name_fr": "iter254-activation-fr",
        "type": "partner_launch_offer",
        "config": {"scope": ["all"], "discount_percent": 100},
        "target_config": {"target": "all"},
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "uses_per_user": 5,
        "show_banner": False, "notify_users": False,
    }
    r = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    promo = r.json()
    pid = promo["id"]
    coupon = promo["coupon_code"]
    try:
        ra = requests.post(
            f"{base}/api/promotions/activate-to-account",
            json={"coupon_code": coupon},
            headers=headers, timeout=15,
        )
        assert ra.status_code == 200, ra.text
        out = ra.json()
        assert out["activated"] is True
        assert out["coupon_code"] == coupon.upper()
        assert out["is_full_waiver"] is True
        assert out["message_en"] == "Verified Partner Offer: 100% Free Listing Credit Applied"
        assert out["message_fr"] == "Offre partenaire vérifiée : crédit d'annonce gratuit à 100 % appliqué"

        # Verify the user record was mutated (via auth/me).
        rm = requests.get(
            f"{base}/api/auth/me",
            headers=headers, timeout=10,
        )
        if rm.status_code == 200:
            me = rm.json()
            assert me.get("partner_offer_active") is True
            assert me.get("partner_offer_coupon_code") == coupon.upper()
    finally:
        # Roll back the activation so other tests aren't tainted.
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio as _asyncio
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "bazario_db")

        async def _rollback():
            client = AsyncIOMotorClient(mongo_url)
            try:
                await client[db_name].users.update_one(
                    {"email": "charbel911@gmail.com"},
                    {"$unset": {
                        "partner_offer_active": "",
                        "partner_offer_promotion_id": "",
                        "partner_offer_coupon_code": "",
                        "partner_offer_activated_at": "",
                        "partner_offer_is_full_waiver": "",
                        "partner_offer_discount_percent": "",
                    }},
                )
            finally:
                client.close()
        if mongo_url:
            _asyncio.run(_rollback())
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)


def test_iter254_activate_to_account_rejects_invalid_coupon():
    base = _base()
    token = _admin_token(base)
    r = requests.post(
        f"{base}/api/promotions/activate-to-account",
        json={"coupon_code": f"FAKE-{uuid.uuid4().hex[:6]}"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["activated"] is False
    assert body["message_en"] == "Invalid or expired coupon code."
    assert body["message_fr"] == "Code promo invalide ou expiré."


# ─── Mission 3 — Forced-language override ────────────────────────────

def _make_partner_promo(base, token, custom_emails):
    body = {
        "name_en": f"iter254-lang-{uuid.uuid4().hex[:6]}",
        "name_fr": "iter254-lang-fr",
        "type": "partner_launch_offer",
        "config": {"scope": ["all"]},
        "target_config": {"target": "custom", "custom_emails": custom_emails},
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "uses_per_user": 1,
        "show_banner": False, "notify_users": False,
    }
    r = requests.post(
        f"{base}/api/admin/promotions",
        json=body, headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_iter254_forced_lang_fr_routes_all_recipients_to_french():
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}
    # Mix of EN-implied (ON province), unknown, and one that would
    # auto-detect to whatever the live DB has.
    custom = [
        "iter254-en-1@example.com",
        "iter254-en-2@example.com",
    ]
    promo = _make_partner_promo(base, token, custom)
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True, "forced_lang": "fr"},
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["forced_lang"] == "fr"
        assert body["lang_breakdown"]["fr"] == body["recipient_count"]
        assert body["lang_breakdown"]["en"] == 0
        for row in body["recipients"]:
            assert row["lang"] == "fr"
            assert row["pdf_filename"] == "Guide-Evaluation-Programme-Partenaires.pdf"
            assert "Offre exclusive" in row["subject"]
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)


def test_iter254_forced_lang_en_routes_all_recipients_to_english():
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}
    custom = [
        "iter254-fr-1@example.com",
        "iter254-fr-2@example.com",
    ]
    promo = _make_partner_promo(base, token, custom)
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True, "forced_lang": "en"},
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["forced_lang"] == "en"
        assert body["lang_breakdown"]["en"] == body["recipient_count"]
        assert body["lang_breakdown"]["fr"] == 0
        for row in body["recipients"]:
            assert row["lang"] == "en"
            assert row["pdf_filename"] == "BidVex-Partner-Program-Guide.pdf"
            assert "Exclusive offer" in row["subject"]
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)


def test_iter254_forced_lang_none_falls_back_to_auto_detection():
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}
    custom = ["iter254-auto-1@example.com"]
    promo = _make_partner_promo(base, token, custom)
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},  # no forced_lang
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # No override → forced_lang is None.
        assert body["forced_lang"] is None
        # Unknown email defaults to English under auto-detect.
        assert body["recipients"][0]["lang"] == "en"
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)


def test_iter254_blast_response_surfaces_forced_lang_for_ui_toast():
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}
    promo = _make_partner_promo(base, token, ["iter254-x@example.com"])
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True, "forced_lang": "fr"},
            headers=headers, timeout=20,
        )
        assert r.json()["forced_lang"] == "fr"
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)


# ─── Mission 4 — Email branding constants & override propagation ─────

def test_iter254_email_branding_constants_match_spec():
    from services.emails._email_core import (
        B2B_PARTNER_FROM_EMAIL,
        B2B_PARTNER_FROM_NAME,
        TRANSACTIONAL_FROM_EMAIL,
        TRANSACTIONAL_FROM_NAME,
    )
    # iter270 collapsed all outbound FROMs to noreply@bidvex.com (DKIM);
    # partners@bidvex.ca lives on as the Reply-To.
    assert B2B_PARTNER_FROM_EMAIL == "noreply@bidvex.com"
    assert TRANSACTIONAL_FROM_EMAIL == "noreply@bidvex.com"
    from services.emails._email_core import TRANSACTIONAL_REPLY_TO
    assert TRANSACTIONAL_REPLY_TO == "support@bidvex.com"
    assert B2B_PARTNER_FROM_NAME  # non-empty
    assert TRANSACTIONAL_FROM_NAME  # non-empty


@pytest.mark.asyncio
async def test_iter254_send_email_accepts_branding_overrides():
    """`send_email` propagates `from_email`/`from_name`/`reply_to` into
    the response envelope. In the SendGrid-unavailable test env, the
    logged-only fallback returns the resolved overrides for assertion."""
    from services.emails import _email_core as en
    res = await en.send_email(
        to_email="test@example.com",
        subject="iter254 branding test",
        html_content="<p>body</p>",
        from_email="partners@bidvex.ca",
        from_name="BidVex Partner Program",
        reply_to="partners@bidvex.ca",
    )
    assert res["status"] in ("logged", "sent")
    # When SendGrid is unavailable the envelope echoes the overrides.
    if res["status"] == "logged":
        assert res["from_email"] == "partners@bidvex.ca"
        assert res["from_name"] == "BidVex Partner Program"
        assert res["reply_to"] == "partners@bidvex.ca"
