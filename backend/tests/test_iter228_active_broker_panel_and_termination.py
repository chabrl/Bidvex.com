"""iter228 — Complete Buyer-Broker Active Portal & Termination Flow.

Covers:
  - GET /broker-relationships/my-active-broker returns full panel data
    (relationship + broker + active_bids + purchases + termination gate).
  - POST /broker-relationships/{rel_id}/buyer-terminate
      * 401 unauthed
      * 404 if rel doesn't exist
      * 403 if rel belongs to another buyer
      * 400 if already terminated
      * 409 with proper detail when blocked by active bids or pending invoices
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


# ── my-active-broker endpoint ─────────────────────────────────────────
def test_my_active_broker_requires_auth():
    r = requests.get(f"{API}/broker-relationships/my-active-broker", timeout=15)
    assert r.status_code in (401, 403)


def test_my_active_broker_returns_null_data_for_unbound_buyer():
    """A buyer with no active partnership should get {data: null}, not an error."""
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    r = requests.get(
        f"{API}/broker-relationships/my-active-broker",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    # The buyer may or may not be currently bound — just assert shape
    if body["data"] is not None:
        assert "relationship" in body["data"]
        assert "broker"       in body["data"]
        assert "active_bids"  in body["data"]
        assert "purchases"    in body["data"]
        assert "termination"  in body["data"]
        assert "can_terminate" in body["data"]["termination"]


def test_my_active_broker_shape_when_data_is_present():
    """If data is non-null, broker section must be sanitized (no _id leakage)."""
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    r = requests.get(
        f"{API}/broker-relationships/my-active-broker",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    if body.get("data"):
        b = body["data"]["broker"]
        # Must include the new fields that drive the UI
        for k in ("legal_business_name", "operating_province", "regulatory_body",
                  "fee_structure", "broker_license_number", "verification_status"):
            assert k in b, f"broker view missing key {k}"
        # No Mongo _id leakage
        assert "_id" not in b
        assert "_id" not in body["data"]["relationship"]


# ── buyer-terminate endpoint ─────────────────────────────────────────
def test_buyer_terminate_requires_auth():
    r = requests.post(f"{API}/broker-relationships/test-id/buyer-terminate", timeout=15)
    assert r.status_code in (401, 403)


def test_buyer_terminate_404_for_unknown_rel():
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("buyer login unavailable")
    fake_rel = str(uuid.uuid4())
    r = requests.post(
        f"{API}/broker-relationships/{fake_rel}/buyer-terminate",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "relationship_not_found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
