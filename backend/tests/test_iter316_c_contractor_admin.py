"""
iter316-C — backend tests for Admin Contractor onboarding & oversight.

Covers:
  • POST /api/twilio/admin/contractors — new + promote-existing
  • POST /api/twilio/admin/users/{id}/promote-to-contractor
  • POST /api/twilio/admin/users/{id}/demote-from-contractor
  • GET  /api/twilio/admin/contractors/{id}/profile
  • GET  /api/twilio/calls?agent_user_id={id} (admin drill-in filter)
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import pytest
import httpx

sys.path.insert(0, "/app/backend")

API_BASE = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://prod-verify-2.preview.emergentagent.com")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = httpx.post(f"{API_BASE}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=30.0)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def buyer_token() -> str:
    r = httpx.post(f"{API_BASE}/api/auth/login", json={
        "email": BUYER_EMAIL, "password": BUYER_PASSWORD,
    }, timeout=30.0)
    if r.status_code != 200:
        pytest.skip(f"buyer login failed: {r.status_code}")
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _delete_contractor(token: str, contractor_id: str) -> None:
    """Best-effort cleanup — no public endpoint, so we use the
    demote-from-contractor route. The test user row remains in DB but
    no longer claims the contractor role."""
    httpx.post(
        f"{API_BASE}/api/twilio/admin/users/{contractor_id}/demote-from-contractor",
        headers=_h(token), timeout=15.0,
    )


# ─── Create new contractor ─────────────────────────────────────────────

def test_admin_create_new_contractor_then_get_profile(admin_token):
    email = f"itctest-{os.urandom(4).hex()}@bidvex.test"
    r = httpx.post(f"{API_BASE}/api/twilio/admin/contractors",
                   headers=_h(admin_token),
                   json={
                       "email": email,
                       "name": "iter316-C Test Contractor",
                       "phone": "+14155550199",
                       "province": "QC",
                       "initial_default_rate": 0.18,
                   }, timeout=30.0)
    assert r.status_code == 200, r.text
    out = r.json()
    cid = out["contractor_id"]
    assert out["promoted"] is False, "fresh email should NOT be a promotion"
    assert len(out["invite_token"]) >= 16

    # Profile is now reachable + returns the right shape.
    p = httpx.get(f"{API_BASE}/api/twilio/admin/contractors/{cid}/profile",
                  headers=_h(admin_token), timeout=30.0)
    assert p.status_code == 200, p.text
    body = p.json()
    assert body["contractor"]["email"] == email
    assert body["contractor"]["role"] == "dialer_contractor"
    assert body["referred_count"] == 0
    assert body["calls_total"] == 0
    assert body["stripe"]["connected"] is False
    assert body["ai_summary"]["sentiment"] == {
        "positive": 0, "neutral": 0, "negative": 0,
    }
    _delete_contractor(admin_token, cid)


def test_admin_create_existing_email_promotes_instead(admin_token):
    # The platform buyer already exists; the same endpoint must promote
    # them instead of duplicating, then demote at the end.
    r = httpx.post(f"{API_BASE}/api/twilio/admin/contractors",
                   headers=_h(admin_token),
                   json={"email": BUYER_EMAIL, "name": "test buyer promoted"},
                   timeout=30.0)
    assert r.status_code in (200, 409), r.text
    if r.status_code == 409:
        pytest.skip("already-promoted from a previous test run")
    out = r.json()
    assert out["promoted"] is True
    cid = out["contractor_id"]
    # cleanup
    _delete_contractor(admin_token, cid)


# ─── Promote / demote ────────────────────────────────────────────────

def test_admin_promote_then_demote_flow(admin_token):
    # Step 1: create a fresh user via admin-contractors (start in promoted
    # role), demote, re-promote, re-demote.
    email = f"itc-promote-{os.urandom(4).hex()}@bidvex.test"
    create = httpx.post(f"{API_BASE}/api/twilio/admin/contractors",
                         headers=_h(admin_token),
                         json={"email": email, "name": "promo test"},
                         timeout=30.0)
    assert create.status_code == 200, create.text
    cid = create.json()["contractor_id"]

    # Demote → reverts to "user" (the role assigned on create flow when no
    # previous_role exists).
    d1 = httpx.post(
        f"{API_BASE}/api/twilio/admin/users/{cid}/demote-from-contractor",
        headers=_h(admin_token), timeout=30.0,
    )
    assert d1.status_code == 200
    assert d1.json()["status"] == "demoted"
    assert d1.json()["reverted_to_role"] in ("user", "individual_seller")

    # Demote again — should 409 (already not a contractor).
    d2 = httpx.post(
        f"{API_BASE}/api/twilio/admin/users/{cid}/demote-from-contractor",
        headers=_h(admin_token), timeout=30.0,
    )
    assert d2.status_code == 409
    detail = d2.json()["detail"]
    assert isinstance(detail, dict)
    assert "n'est pas" in detail["message_fr"] or "not_a_contractor" == detail["error"]

    # Promote again.
    p = httpx.post(
        f"{API_BASE}/api/twilio/admin/users/{cid}/promote-to-contractor",
        headers=_h(admin_token), json={"initial_default_rate": 0.25},
        timeout=30.0,
    )
    assert p.status_code == 200
    assert p.json()["status"] == "promoted"

    # Idempotency: promoting an already-contractor returns 409.
    p2 = httpx.post(
        f"{API_BASE}/api/twilio/admin/users/{cid}/promote-to-contractor",
        headers=_h(admin_token), json={}, timeout=30.0,
    )
    assert p2.status_code == 409

    # cleanup
    _delete_contractor(admin_token, cid)


# ─── Admin drill-in calls filter (agent_user_id) ──────────────────────

def test_admin_calls_filter_by_agent_user_id(admin_token):
    # Just verify the API contract — empty list is fine.
    r = httpx.get(f"{API_BASE}/api/twilio/calls",
                  params={"agent_user_id": "non-existent-id"},
                  headers=_h(admin_token), timeout=30.0)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and body["items"] == []


def test_admin_calls_filter_rejects_non_admin(buyer_token):
    r = httpx.get(f"{API_BASE}/api/twilio/calls",
                  params={"agent_user_id": "anything"},
                  headers=_h(buyer_token), timeout=30.0)
    # Either 403 from the role gate or 403 from the agent_user_id
    # admin-only check — either path is acceptable.
    assert r.status_code == 403


# ─── 403 / 401 negative paths ────────────────────────────────────────

def test_non_admin_cannot_create_contractor(buyer_token):
    r = httpx.post(f"{API_BASE}/api/twilio/admin/contractors",
                   headers=_h(buyer_token),
                   json={"email": "x@x.test"}, timeout=30.0)
    assert r.status_code == 403


def test_non_admin_cannot_view_contractor_profile(buyer_token):
    r = httpx.get(f"{API_BASE}/api/twilio/admin/contractors/anything/profile",
                  headers=_h(buyer_token), timeout=30.0)
    assert r.status_code == 403


def test_anonymous_blocked(admin_token):  # pylint: disable=unused-argument
    r = httpx.post(f"{API_BASE}/api/twilio/admin/contractors",
                   json={"email": "anon@x.test"}, timeout=30.0)
    assert r.status_code in (401, 403)
