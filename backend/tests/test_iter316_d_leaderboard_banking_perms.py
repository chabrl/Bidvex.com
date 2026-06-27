"""
iter316-D — backend tests for Leaderboard + Banking validation + Permissions.

Covers:
  • GET   /api/twilio/admin/contractors/leaderboard
  • GET   /api/twilio/contractor/payout-readiness  (admin & self)
  • PATCH /api/twilio/admin/contractors/{id}/permissions
  • GET   /api/twilio/admin/contractors/{id}/permissions
  • GET   /api/twilio/contractor/permissions/me
  • POST  /api/twilio/contractor/clients (permission-gated)
"""
from __future__ import annotations

import os
import sys
import httpx
import pytest

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
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def buyer_token() -> str:
    r = httpx.post(f"{API_BASE}/api/auth/login", json={
        "email": BUYER_EMAIL, "password": BUYER_PASSWORD,
    }, timeout=30.0)
    if r.status_code != 200:
        pytest.skip(f"buyer login failed: {r.status_code}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def fresh_contractor(admin_token: str):
    """Spin up a fresh contractor for the permission tests so we don't
    interfere with shared test_contractor-1 state."""
    email = f"itd-perm-{os.urandom(4).hex()}@bidvex.test"
    r = httpx.post(f"{API_BASE}/api/twilio/admin/contractors",
                   headers={"Authorization": f"Bearer {admin_token}"},
                   json={"email": email, "name": "iter316-D perm test"},
                   timeout=30.0)
    assert r.status_code == 200, r.text
    cid = r.json()["contractor_id"]
    yield {"id": cid, "email": email}
    # cleanup
    httpx.post(
        f"{API_BASE}/api/twilio/admin/users/{cid}/demote-from-contractor",
        headers={"Authorization": f"Bearer {admin_token}"}, timeout=15.0,
    )


@pytest.fixture(scope="module")
def fresh_contractor_token(fresh_contractor, admin_token):
    """Build a JWT for the fresh contractor by minting via direct DB
    password reset. The simplest approach: log in as admin and reuse
    the admin token in role-isolation tests; for the actual "self"
    flow, the existing testbuyer is sufficient. So return None and
    skip self-flow tests when not feasible."""
    return None


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ─── Leaderboard ──────────────────────────────────────────────────────

def test_leaderboard_returns_ranked_rows(admin_token):
    r = httpx.get(f"{API_BASE}/api/twilio/admin/contractors/leaderboard",
                  headers=_h(admin_token), timeout=30.0)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "period" in data
    assert data["period"] == "lifetime"
    if data["items"]:
        for i, row in enumerate(data["items"]):
            assert row["rank"] == i + 1
            assert "earnings" in row and "call_volume" in row
            assert "referred_count" in row and "conversion_rate" in row
            assert 0.0 <= row["conversion_rate"] <= 1.0


def test_leaderboard_supports_period_filters(admin_token):
    for period in ("month", "week", "lifetime"):
        r = httpx.get(
            f"{API_BASE}/api/twilio/admin/contractors/leaderboard?period={period}",
            headers=_h(admin_token), timeout=30.0,
        )
        assert r.status_code == 200, f"period={period} failed"
        assert r.json()["period"] == period


def test_leaderboard_blocks_non_admin(buyer_token):
    r = httpx.get(f"{API_BASE}/api/twilio/admin/contractors/leaderboard",
                  headers=_h(buyer_token), timeout=30.0)
    assert r.status_code == 403


# ─── Payout readiness ─────────────────────────────────────────────────

def test_payout_readiness_admin_self_returns_not_a_contractor(admin_token):
    r = httpx.get(f"{API_BASE}/api/twilio/contractor/payout-readiness",
                  headers=_h(admin_token), timeout=30.0)
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is False
    assert "not_a_contractor" in body["blocked_reasons"]
    assert "accrued_total" in body
    assert "next_payout_at" in body


def test_payout_readiness_admin_override_other_id(admin_token, fresh_contractor):
    r = httpx.get(
        f"{API_BASE}/api/twilio/contractor/payout-readiness",
        params={"contractor_id": fresh_contractor["id"]},
        headers=_h(admin_token), timeout=30.0,
    )
    assert r.status_code == 200
    body = r.json()
    # Fresh contractor has no Stripe Connect yet → must NOT be ready.
    assert body["ready"] is False
    assert "no_stripe_account" in body["blocked_reasons"]
    assert "payouts_disabled" in body["blocked_reasons"]


def test_payout_readiness_blocks_buyer_querying_other(buyer_token):
    r = httpx.get(
        f"{API_BASE}/api/twilio/contractor/payout-readiness",
        params={"contractor_id": "anything-else"},
        headers=_h(buyer_token), timeout=30.0,
    )
    assert r.status_code == 403


# ─── Permissions ──────────────────────────────────────────────────────

def test_admin_can_get_and_set_permissions(admin_token, fresh_contractor):
    cid = fresh_contractor["id"]
    # Initial state: empty.
    r = httpx.get(
        f"{API_BASE}/api/twilio/admin/contractors/{cid}/permissions",
        headers=_h(admin_token), timeout=30.0,
    )
    assert r.status_code == 200
    assert r.json()["permissions"] == []
    allowed = r.json()["allowed_options"]
    assert "add_users" in allowed
    assert "manage_subscriptions" in allowed

    # Set 2 valid + 1 unknown → unknown stripped.
    r = httpx.patch(
        f"{API_BASE}/api/twilio/admin/contractors/{cid}/permissions",
        json={"permissions": ["add_users", "manage_subscriptions", "nonexistent_perm"]},
        headers=_h(admin_token), timeout=30.0,
    )
    assert r.status_code == 200
    saved = r.json()["permissions"]
    assert "add_users" in saved
    assert "manage_subscriptions" in saved
    assert "nonexistent_perm" not in saved

    # Round-trip GET.
    r = httpx.get(
        f"{API_BASE}/api/twilio/admin/contractors/{cid}/permissions",
        headers=_h(admin_token), timeout=30.0,
    )
    assert r.status_code == 200
    assert set(r.json()["permissions"]) == {"add_users", "manage_subscriptions"}


def test_permissions_me_returns_own(admin_token):
    """Admin user calls /me — they aren't a contractor but should still
    get a {permissions: [], is_contractor: False} contract back."""
    r = httpx.get(f"{API_BASE}/api/twilio/contractor/permissions/me",
                  headers=_h(admin_token), timeout=30.0)
    assert r.status_code == 200
    body = r.json()
    assert body["is_contractor"] is False
    assert isinstance(body["permissions"], list)


def test_non_admin_cannot_set_permissions(buyer_token, fresh_contractor):
    r = httpx.patch(
        f"{API_BASE}/api/twilio/admin/contractors/{fresh_contractor['id']}/permissions",
        json={"permissions": ["add_users"]},
        headers=_h(buyer_token), timeout=30.0,
    )
    assert r.status_code == 403


# ─── Contractor add-client (permission-gated) ─────────────────────────

def test_buyer_cannot_create_referred_client(buyer_token):
    """Buyer (role != dialer_contractor && != admin) → 403 contractor only."""
    r = httpx.post(f"{API_BASE}/api/twilio/contractor/clients",
                   json={"email": "x@x.test"},
                   headers=_h(buyer_token), timeout=30.0)
    assert r.status_code == 403


def test_admin_can_create_client_directly(admin_token):
    """Admin bypasses the permission check."""
    email = f"itd-client-{os.urandom(4).hex()}@bidvex.test"
    r = httpx.post(f"{API_BASE}/api/twilio/contractor/clients",
                   json={"email": email, "name": "admin-created client",
                          "account_type": "individual_seller"},
                   headers=_h(admin_token), timeout=30.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "client_id" in body
    assert "invite_token" in body


def test_duplicate_email_blocked(admin_token):
    email = f"itd-dup-{os.urandom(4).hex()}@bidvex.test"
    r1 = httpx.post(f"{API_BASE}/api/twilio/contractor/clients",
                     json={"email": email, "name": "first"},
                     headers=_h(admin_token), timeout=30.0)
    assert r1.status_code == 200
    r2 = httpx.post(f"{API_BASE}/api/twilio/contractor/clients",
                     json={"email": email, "name": "dup"},
                     headers=_h(admin_token), timeout=30.0)
    assert r2.status_code == 409
    d = r2.json()["detail"]
    assert isinstance(d, dict)
    assert d["error"] == "email_exists"
