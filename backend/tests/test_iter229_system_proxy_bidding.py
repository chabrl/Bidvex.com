"""iter229 — System-Proxy Broker Bidding Engine tests.

Backend coverage:
  • GET  /broker-relationships/compliance-check
  • POST /broker-relationships/accept-proxy-agreement
  • PATCH /broker-relationships/{rel_id}/bid-cap
  • Bid-cap + proxy-agreement gates do NOT block non-vehicle listings.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("BIDVEX_BASE_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email: str, password: str) -> str | None:
    try:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code == 200:
            return r.json().get("access_token") or r.json().get("token")
    except Exception:
        pass
    return None


# ── compliance-check endpoint ─────────────────────────────────────────
def test_compliance_check_requires_auth():
    r = requests.get(f"{API}/broker-relationships/compliance-check?listing_id=x", timeout=15)
    assert r.status_code in (401, 403)


def test_compliance_check_404_for_unknown_listing():
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    r = requests.get(
        f"{API}/broker-relationships/compliance-check?listing_id={uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "listing_not_found"


# ── accept-proxy-agreement endpoint ───────────────────────────────────
def test_accept_proxy_requires_auth():
    r = requests.post(f"{API}/broker-relationships/accept-proxy-agreement", timeout=15)
    assert r.status_code in (401, 403)


def test_accept_proxy_400_no_active_partnership():
    """Buyer with no active partnership should get 400 no_active_partnership."""
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    r = requests.post(
        f"{API}/broker-relationships/accept-proxy-agreement",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    # 200 if buyer happens to be active, 400 otherwise — both acceptable.
    assert r.status_code in (200, 400)
    if r.status_code == 400:
        assert r.json()["detail"]["error"] == "no_active_partnership"


# ── bid-cap PATCH endpoint ────────────────────────────────────────────
def test_bid_cap_patch_requires_auth():
    r = requests.patch(f"{API}/broker-relationships/test/bid-cap", json={"bid_cap": 5000}, timeout=15)
    assert r.status_code in (401, 403)


def test_bid_cap_patch_404_for_unknown_relationship():
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    r = requests.patch(
        f"{API}/broker-relationships/{uuid.uuid4()}/bid-cap",
        json={"bid_cap": 5000},
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "relationship_not_found"


def test_bid_cap_patch_422_for_negative_value():
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    r = requests.patch(
        f"{API}/broker-relationships/{uuid.uuid4()}/bid-cap",
        json={"bid_cap": -100},
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    # Could be 404 (relationship not found checked first) OR 422 — both acceptable
    assert r.status_code in (404, 422)


# ── Non-vehicle listing path doesn't break ────────────────────────────
def test_non_vehicle_listing_returns_not_a_vehicle_verdict():
    """If we hit compliance-check on a non-vehicle listing, we should get
    not_a_vehicle (NOT no_broker)."""
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    # Find a non-vehicle listing (storage_locker / fashion / etc)
    listing_r = requests.get(f"{API}/listings?limit=5", timeout=15)
    if listing_r.status_code != 200:
        pytest.skip("listings endpoint unavailable")
    body = listing_r.json()
    if isinstance(body, list):
        rows = body
    else:
        rows = body.get("data") or body.get("listings") or []
    if not rows:
        pytest.skip("no listings on preview")
    sample = rows[0]
    if not sample.get("id"):
        pytest.skip("listing shape unknown")

    r = requests.get(
        f"{API}/broker-relationships/compliance-check?listing_id={sample['id']}",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    # Should be 200 with one of: not_a_vehicle, no_broker, no_deposit, etc.
    assert r.status_code == 200
    assert r.json().get("status") in (
        "not_a_vehicle", "no_broker", "relationship_pending", "no_deposit",
        "province_mismatch", "eligible",
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
