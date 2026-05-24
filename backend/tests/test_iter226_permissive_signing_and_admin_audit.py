"""iter226 — Permissive Sign-Liability + Admin Audit Endpoints tests.

Covers:
  Task 1: POST /brokers/sign-liability now works for ANY authenticated user
          (not just approved brokers). Audit row + pending-signature stamp.
  Task 2: GET /admin/brokers/{id}/relationships
          GET /admin/brokers/{id}/activity-log
          - require admin auth
          - 404 for unknown broker
          - return expected shape
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


# ── Task 1 — Permissive sign-liability ─────────────────────────────────
def test_sign_liability_works_for_non_broker_authenticated_user():
    """A regular buyer (NOT a broker) should be able to sign during the
    onboarding wizard without hitting `not_a_broker`."""
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("test buyer not available on preview")

    payload = {
        "signature_full_name": "Iter226 Test Signer",
        "accepted_section_1":  True,
        "accepted_section_2":  True,
        "accepted_section_3":  True,
        "scrolled_to_bottom":  True,
        "locale":              "en",
    }
    r = requests.post(
        f"{API}/brokers/sign-liability", json=payload,
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code} body={r.text[:300]}"
    body = r.json()
    assert body["success"] is True
    assert body["stage"] in ("pending_applicant", "approved_broker")
    assert body.get("signed_at")


def test_sign_liability_still_rejects_unscrolled():
    """Even for pending users, scroll gate still applies."""
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("test buyer not available on preview")
    payload = {
        "signature_full_name": "Test",
        "accepted_section_1":  True,
        "accepted_section_2":  True,
        "accepted_section_3":  True,
        "scrolled_to_bottom":  False,
        "locale":              "en",
    }
    r = requests.post(
        f"{API}/brokers/sign-liability", json=payload,
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "scroll_required"


def test_sign_liability_still_rejects_partial_acceptance():
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("test buyer not available on preview")
    payload = {
        "signature_full_name": "Test",
        "accepted_section_1":  True,
        "accepted_section_2":  False,
        "accepted_section_3":  True,
        "scrolled_to_bottom":  True,
        "locale":              "en",
    }
    r = requests.post(
        f"{API}/brokers/sign-liability", json=payload,
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "all_three_sections_required"


def test_sign_liability_requires_auth():
    payload = {
        "signature_full_name": "Anonymous",
        "accepted_section_1":  True,
        "accepted_section_2":  True,
        "accepted_section_3":  True,
        "scrolled_to_bottom":  True,
        "locale":              "en",
    }
    r = requests.post(f"{API}/brokers/sign-liability", json=payload, timeout=15)
    assert r.status_code in (401, 403)


# ── Task 2 — Admin Audit Endpoints ─────────────────────────────────────
def test_admin_broker_relationships_requires_admin():
    """Non-admin token should get 403."""
    token = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    if not token:
        pytest.skip("test buyer not available on preview")
    fake_id = str(uuid.uuid4())
    r = requests.get(
        f"{API}/admin/brokers/{fake_id}/relationships",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 403


def test_admin_broker_relationships_404_unknown_id():
    token = _login("charbel911@gmail.com", "Anderosli123!@#")
    if not token:
        pytest.skip("admin login unavailable on preview")
    fake_id = str(uuid.uuid4())
    r = requests.get(
        f"{API}/admin/brokers/{fake_id}/relationships",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 404


def test_admin_broker_activity_log_404_unknown_id():
    token = _login("charbel911@gmail.com", "Anderosli123!@#")
    if not token:
        pytest.skip("admin login unavailable on preview")
    fake_id = str(uuid.uuid4())
    r = requests.get(
        f"{API}/admin/brokers/{fake_id}/activity-log",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 404


def test_admin_broker_activity_log_returns_event_list_for_known_broker():
    """Pick the first approved broker (if any) and validate shape."""
    token = _login("charbel911@gmail.com", "Anderosli123!@#")
    if not token:
        pytest.skip("admin login unavailable on preview")

    listing = requests.get(
        f"{API}/admin/brokers?status=approved",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    if listing.status_code != 200:
        pytest.skip("admin brokers list unavailable")
    rows = listing.json().get("data") or []
    if not rows:
        pytest.skip("no approved brokers on preview")

    broker_id = rows[0]["id"]
    r = requests.get(
        f"{API}/admin/brokers/{broker_id}/activity-log",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert "broker" in body and body["broker"]["id"] == broker_id
    assert isinstance(body["events"], list)
    assert "count" in body and body["count"] == len(body["events"])
    # If there are events, each must have kind / at / message
    for e in body["events"][:5]:
        assert "kind" in e and "at" in e


def test_admin_broker_relationships_returns_shape_for_known_broker():
    token = _login("charbel911@gmail.com", "Anderosli123!@#")
    if not token:
        pytest.skip("admin login unavailable on preview")

    listing = requests.get(
        f"{API}/admin/brokers?status=approved",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    if listing.status_code != 200:
        pytest.skip("admin brokers list unavailable")
    rows = listing.json().get("data") or []
    if not rows:
        pytest.skip("no approved brokers on preview")

    broker_id = rows[0]["id"]
    r = requests.get(
        f"{API}/admin/brokers/{broker_id}/relationships",
        headers={"Authorization": f"Bearer {token}"}, timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert "broker" in body
    assert "relationships" in body and isinstance(body["relationships"], list)
    assert "counts" in body
    expected_keys = {"total", "active", "pending", "terminated", "rejected", "suspended",
                     "deposits_held", "deposits_refunded", "deposits_released"}
    assert expected_keys.issubset(set(body["counts"].keys()))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
