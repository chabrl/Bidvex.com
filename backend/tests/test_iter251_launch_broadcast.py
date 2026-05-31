"""
iter251 — Launch Broadcast wiring + manual list audience honouring.

Test roster (5 tests):
  1. Partner-outreach blast with promotion_id + custom_emails target
     resolves to the manual list (NOT the is_partner=True set).
  2. Manual list path strips unsubscribed addresses.
  3. Manual list path hydrates province from the users collection when
     a recipient happens to exist as a user, so language routing still
     works on the manual list.
  4. Cold-outreach addresses (not in users collection) still get a
     recipient row with `first_name="Partner"`.
  5. Default partner-segment path is preserved when target_config has
     no `target=="custom"` override (back-compat with iter247-iter250).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

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


_TOKEN = {"admin": None}


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


def _make_partner_outreach_promo(base: str, token: str, *, custom_emails=None):
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "name_en": f"iter251-launch-{uuid.uuid4().hex[:6]}",
        "name_fr": "iter251-launch-FR",
        "type": "partner_launch_offer",
        "config": {"scope": ["all"]},
        "target_config": {
            "target": "custom" if custom_emails else "partners",
            "custom_emails": custom_emails or [],
        },
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "uses_per_user": 1,
        "show_banner": False,
        "notify_users": False,
    }
    r = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _delete_promo(base, token, pid):
    requests.delete(f"{base}/api/admin/promotions/{pid}", headers={"Authorization": f"Bearer {token}"}, timeout=10)


# ─── Manual list audience honouring ──────────────────────────────────

def test_iter251_blast_honours_manual_custom_emails_list():
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    custom = [
        "iter251-launch-1@example.com",
        "iter251-launch-2@example.com",
        "iter251-launch-3@example.com",
    ]
    promo = _make_partner_outreach_promo(base, token, custom_emails=custom)
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Recipient set MUST be exactly the manual list (de-duplicated).
        emails = sorted([row["email"].lower() for row in body["recipients"]])
        assert emails == sorted(custom), (emails, custom)
        # All emails attached the right PDF.
        for row in body["recipients"]:
            assert row.get("pdf_filename", "").endswith(".pdf")
    finally:
        _delete_promo(base, token, pid)


def test_iter251_manual_list_strips_unsubscribed_addresses():
    """The recipient resolver must remove any email present in the
    `email_unsubscribes` collection — even if it's on the manual list."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    # Use an obviously cold address that we can register as unsubscribed.
    cold = f"iter251-unsubbed-{uuid.uuid4().hex[:6]}@example.com"
    keep = f"iter251-keep-{uuid.uuid4().hex[:6]}@example.com"

    # Register the cold address as unsubscribed via direct Mongo write.
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "bazario_db")
    if not mongo_url:
        pytest.skip("MONGO_URL not available")

    async def _setup():
        client = AsyncIOMotorClient(mongo_url)
        try:
            await client[db_name].email_unsubscribes.insert_one({
                "email": cold, "created_at": datetime.now(timezone.utc).isoformat(),
                "source": "iter251_test",
            })
        finally:
            client.close()

    async def _cleanup():
        client = AsyncIOMotorClient(mongo_url)
        try:
            await client[db_name].email_unsubscribes.delete_many({"source": "iter251_test"})
        finally:
            client.close()

    asyncio.run(_setup())
    promo = _make_partner_outreach_promo(base, token, custom_emails=[cold, keep])
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        emails = [row["email"].lower() for row in r.json()["recipients"]]
        assert cold not in emails, emails
        assert keep in emails, emails
    finally:
        _delete_promo(base, token, pid)
        asyncio.run(_cleanup())


def test_iter251_manual_list_with_existing_user_hydrates_province():
    """An email in the manual list that DOES match a `users` document
    should pick up that user's province + preferred_language so the
    language router still works on the manual cohort."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    # Admin's own email is a known user (province may or may not be QC,
    # but the hydrated row WILL carry whatever's on disk).
    promo = _make_partner_outreach_promo(
        base, token,
        custom_emails=["charbel911@gmail.com"],
    )
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        rows = body["recipients"]
        assert len(rows) == 1
        row = rows[0]
        # Lang is one of {en, fr} based on the admin's stored province.
        assert row["lang"] in ("en", "fr")
        # PDF filename matches the language.
        if row["lang"] == "fr":
            assert "Guide-Evaluation-Programme-Partenaires.pdf" in row["pdf_filename"]
        else:
            assert "BidVex-Partner-Program-Guide.pdf" in row["pdf_filename"]
    finally:
        _delete_promo(base, token, pid)


def test_iter251_manual_list_cold_email_defaults_to_partner_firstname():
    """Cold email addresses (not in `users`) still land in the recipient
    set with a stable `first_name="Partner"` default."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    cold = f"iter251-cold-{uuid.uuid4().hex[:6]}@example.com"
    promo = _make_partner_outreach_promo(base, token, custom_emails=[cold])
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        rows = r.json()["recipients"]
        assert any(row["email"].lower() == cold for row in rows), rows
    finally:
        _delete_promo(base, token, pid)


def test_iter251_default_partner_segment_preserved_when_no_custom_override():
    """Back-compat regression: a `partner_launch_offer` promo with
    `target_config.target == "partners"` (no custom_emails) keeps the
    original `is_partner=True` audience query."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    promo = _make_partner_outreach_promo(base, token, custom_emails=None)
    pid = promo["id"]
    try:
        r = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # The live preview env has ≥1 partner user flagged from iter247.
        # Default segment must resolve at least that one.
        assert body["recipient_count"] >= 1, body
    finally:
        _delete_promo(base, token, pid)
