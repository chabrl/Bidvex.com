"""
iter372 — Contractor Email Hub Reply-To routing tests.

Coverage:
  • resolve_contractor_reply_to returns the contractor's personal_email
    when it's set and passes validation.
  • Falls back to support@bidvex.com when personal_email is missing.
  • Falls back to support@bidvex.com when personal_email is invalid
    (empty, malformed, too long).
  • Multiple contractors get their OWN Reply-To addresses — no cross-
    contamination.
  • send_contractor_email writes the resolved reply_to (and the
    reply_to_is_fallback flag) to the contractor_emails row.
  • Display name = "BidVex Contractor" (updated iter372 spec).
  • FROM email = "contractor@bidvex.com" (unchanged).
  • Fallback path emits a WARNING log so admins can chase down missing
    profile fields.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import sys
sys.path.insert(0, "/app/backend")

from services.contractor_email_hub import (  # noqa: E402
    CONTRACTOR_SENDER_EMAIL,
    CONTRACTOR_SENDER_NAME,
    FALLBACK_REPLY_TO,
    FALLBACK_REPLY_TO_NAME,
    _is_valid_email,
    resolve_contractor_reply_to,
    send_contractor_email,
)

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ─────────────────────────────────────────────────────────────────────────
#  Pure-function resolver tests
# ─────────────────────────────────────────────────────────────────────────

def test_sender_identity_is_bidvex_contractor():
    """iter372 spec — FROM address + display name are locked."""
    assert CONTRACTOR_SENDER_EMAIL == "contractor@bidvex.com"
    assert CONTRACTOR_SENDER_NAME == "BidVex Contractor"


def test_fallback_reply_to_is_support():
    assert FALLBACK_REPLY_TO == "support@bidvex.com"
    assert "BidVex" in FALLBACK_REPLY_TO_NAME


def test_resolver_uses_personal_email_when_valid():
    c = {
        "id": "c1",
        "name": "Sam North",
        "personal_email": "sam.north@gmail.com",
    }
    r = resolve_contractor_reply_to(c)
    assert r["email"] == "sam.north@gmail.com"
    assert r["name"] == "Sam North"
    assert r["is_fallback"] is False


def test_resolver_falls_back_when_personal_email_missing(caplog):
    """Missing field → support@bidvex.com + WARNING log."""
    with caplog.at_level(logging.WARNING, logger="services.contractor_email_hub"):
        r = resolve_contractor_reply_to({"id": "c2", "name": "No Email"})
    assert r["email"] == FALLBACK_REPLY_TO
    assert r["is_fallback"] is True
    # A fallback log line MUST be emitted so admins can chase it.
    assert any("reply-to fallback" in m and "c2" in m for m in caplog.messages)


def test_resolver_falls_back_when_personal_email_invalid(caplog):
    """Malformed field → support@bidvex.com + WARNING log."""
    with caplog.at_level(logging.WARNING, logger="services.contractor_email_hub"):
        r = resolve_contractor_reply_to({
            "id": "c3", "personal_email": "not-an-email",
        })
    assert r["email"] == FALLBACK_REPLY_TO
    assert r["is_fallback"] is True
    assert any("invalid_format" in m for m in caplog.messages)


def test_resolver_falls_back_on_blank_and_whitespace():
    for bad in ("", "   ", None):
        r = resolve_contractor_reply_to({"id": "c4", "personal_email": bad})
        assert r["email"] == FALLBACK_REPLY_TO
        assert r["is_fallback"] is True


def test_resolver_falls_back_on_none_contractor():
    r = resolve_contractor_reply_to(None)
    assert r["email"] == FALLBACK_REPLY_TO
    assert r["is_fallback"] is True


def test_multiple_contractors_get_distinct_reply_to():
    """iter372 spec — each contractor's outbound uses THEIR own email.

    Guarantees the resolver doesn't cross-contaminate: contractor A's
    Reply-To must never surface on contractor B's message.
    """
    a = {"id": "cA", "name": "Ava Adams", "personal_email": "ava@a.com"}
    b = {"id": "cB", "name": "Ben Bell", "personal_email": "ben@b.com"}
    c = {"id": "cC", "name": "Cam Cole", "personal_email": None}  # fallback
    ra = resolve_contractor_reply_to(a)
    rb = resolve_contractor_reply_to(b)
    rc = resolve_contractor_reply_to(c)
    assert ra["email"] == "ava@a.com"
    assert rb["email"] == "ben@b.com"
    assert rc["email"] == FALLBACK_REPLY_TO  # untouched fallback
    # Names propagate — never leaks another contractor's name.
    assert ra["name"] == "Ava Adams"
    assert rb["name"] == "Ben Bell"


def test_is_valid_email_boundary_cases():
    assert _is_valid_email("a@b.co") is True
    assert _is_valid_email("first.last+tag@sub.example.co.uk") is True
    assert _is_valid_email("") is False
    assert _is_valid_email(None) is False
    assert _is_valid_email("no-at-sign.com") is False
    assert _is_valid_email("two@@ats.com") is False
    assert _is_valid_email("a" * 260 + "@x.co") is False  # too long


# ─────────────────────────────────────────────────────────────────────────
#  send_contractor_email persists the resolved reply_to
# ─────────────────────────────────────────────────────────────────────────


def test_send_contractor_email_persists_personal_email_reply_to():
    """End-to-end: two contractors send an email each — the DB row for
    each must carry that contractor's own reply_to."""
    async def run():
        # Use motor for parity with the production path.
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        # Clear any previous test rows.
        await db.contractor_emails.delete_many({"contractor_id": {"$in": ["iter372-A", "iter372-B", "iter372-fallback"]}})

        contractor_a = {
            "id": "iter372-A",
            "name": "Ava Adams",
            "email": "ava.company@bidvex.com",
            "personal_email": "ava@personal.com",
        }
        contractor_b = {
            "id": "iter372-B",
            "name": "Ben Bell",
            "email": "ben.company@bidvex.com",
            "personal_email": "ben@personal.com",
        }
        contractor_missing = {
            "id": "iter372-fallback",
            "name": "Cam Cole",
            "email": "cam.company@bidvex.com",
            # personal_email deliberately omitted → fallback path
        }

        # In a test env SENDGRID_API_KEY is unset → the dispatcher returns
        # None (dry-run) but the DB row still records the resolved reply_to.
        prev_key = os.environ.pop("SENDGRID_API_KEY", None)
        try:
            for c, expected_reply, expect_fallback in [
                (contractor_a, "ava@personal.com", False),
                (contractor_b, "ben@personal.com", False),
                (contractor_missing, FALLBACK_REPLY_TO, True),
            ]:
                row = await send_contractor_email(
                    db,
                    contractor=c,
                    to_email="client@example.com",
                    subject="iter372 test",
                    body_html="<p>hi</p>",
                )
                assert row["from_email"] == CONTRACTOR_SENDER_EMAIL
                assert row["from_name"] == CONTRACTOR_SENDER_NAME
                assert row["reply_to"] == expected_reply, (c["id"], row)
                assert row["reply_to_is_fallback"] is expect_fallback
                assert row["contractor_id"] == c["id"]
        finally:
            if prev_key is not None:
                os.environ["SENDGRID_API_KEY"] = prev_key

        # Verify all three rows made it to Mongo with the right reply_to.
        docs = await db.contractor_emails.find(
            {"contractor_id": {"$in": ["iter372-A", "iter372-B", "iter372-fallback"]}},
            {"_id": 0, "contractor_id": 1, "reply_to": 1, "reply_to_is_fallback": 1},
        ).to_list(10)
        by_id = {d["contractor_id"]: d for d in docs}
        assert by_id["iter372-A"]["reply_to"] == "ava@personal.com"
        assert by_id["iter372-A"]["reply_to_is_fallback"] is False
        assert by_id["iter372-B"]["reply_to"] == "ben@personal.com"
        assert by_id["iter372-B"]["reply_to_is_fallback"] is False
        assert by_id["iter372-fallback"]["reply_to"] == FALLBACK_REPLY_TO
        assert by_id["iter372-fallback"]["reply_to_is_fallback"] is True

        # Cleanup
        await db.contractor_emails.delete_many(
            {"contractor_id": {"$in": ["iter372-A", "iter372-B", "iter372-fallback"]}},
        )
        client.close()

    asyncio.run(run())


# ─────────────────────────────────────────────────────────────────────────
#  Legacy build_contractor_reply_to still importable (rollout safety)
# ─────────────────────────────────────────────────────────────────────────


def test_legacy_build_contractor_reply_to_returns_fallback():
    """iter372 keeps the deprecated helper importable so old callers don't
    crash on rollout. New callers must use resolve_contractor_reply_to."""
    from services.contractor_email_hub import build_contractor_reply_to
    assert build_contractor_reply_to("abc") == FALLBACK_REPLY_TO
    assert build_contractor_reply_to(None) == FALLBACK_REPLY_TO


# ─────────────────────────────────────────────────────────────────────────
#  Contractor profile endpoint accepts personal_email
# ─────────────────────────────────────────────────────────────────────────


def test_update_profile_body_accepts_personal_email():
    """The PATCH endpoint's request schema must accept personal_email
    without breaking the existing personal_phone_number field."""
    from routes.contractor_profile_ext import UpdateProfileBody
    # Both fields optional (either can be omitted).
    b = UpdateProfileBody()
    assert b.personal_email is None
    assert b.personal_phone_number is None
    b = UpdateProfileBody(personal_email="jane@example.com")
    assert b.personal_email == "jane@example.com"
    b = UpdateProfileBody(personal_phone_number="+15551112222",
                          personal_email="jane@example.com")
    assert b.personal_email == "jane@example.com"
    assert b.personal_phone_number == "+15551112222"


# ─────────────────────────────────────────────────────────────────────────
#  Static invariants — the frontend editor exposes the new field
# ─────────────────────────────────────────────────────────────────────────


def test_contractor_profile_frontend_exposes_personal_email_field():
    """iter372 spec — the profile UI must let contractors store + edit
    their personal_email (the value that becomes their Reply-To)."""
    src = open(
        "/app/frontend/src/pages/contractor/ContractorIter323Panel.jsx",
        encoding="utf-8",
    ).read()
    assert "personal_email" in src
    assert 'data-testid="contractor-personal-email-input"' in src
    assert 'data-testid="contractor-personal-email-save-btn"' in src
    assert "savePersonalEmail" in src


def test_get_my_contractor_profile_returns_personal_email():
    src = open(
        "/app/backend/routes/contractor_profile_ext.py",
        encoding="utf-8",
    ).read()
    assert '"personal_email":       doc.get("personal_email"),' in src
