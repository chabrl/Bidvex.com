"""
iter306 — Backend tests for new endpoints:
  • CSV bulk-import into a multi-lot vehicle auction
  • Error logging (frontend POST + admin list endpoints)
"""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ───────────────── CSV BULK IMPORT ─────────────────
def test_bulk_import_404_unknown_event(admin_token):
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    r = requests.post(
        f"{API}/vehicle-multi-lot-auctions/no-such-event/bulk-import",
        headers=h,
        json={"lots": [{"vin": "X" * 17, "year": 2020, "make": "Ford", "model": "F-150",
                        "starting_price": 5000, "location_city": "Toronto",
                        "location_province": "ON", "title": "x"}]},
        timeout=10,
    )
    assert r.status_code == 404


def test_bulk_import_requires_auth():
    r = requests.post(
        f"{API}/vehicle-multi-lot-auctions/anything/bulk-import",
        json={"lots": []},
        timeout=10,
    )
    assert r.status_code in (401, 403)


def test_bulk_import_max_lots_enforced(admin_token):
    """Server rejects > 50 lots before checking event ownership."""
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    fake_lot = {"vin": "X" * 17, "year": 2020, "make": "Ford", "model": "F-150",
                "starting_price": 5000, "location_city": "Toronto",
                "location_province": "ON", "title": "x"}
    body = {"lots": [fake_lot] * 51}
    r = requests.post(
        f"{API}/vehicle-multi-lot-auctions/no-event/bulk-import",
        headers=h, json=body, timeout=10,
    )
    assert r.status_code == 400
    detail = r.json().get("detail") or {}
    assert detail.get("code") == "max_lots_exceeded"


def test_bulk_import_qc_requires_title_fr(admin_token):
    """A QC lot without title_fr must produce a validation error in the response."""
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    # First, create a draft event we own
    create = requests.post(
        f"{API}/vehicle-multi-lot-auctions",
        headers=h,
        json={
            "title": "pytest-iter306 csv event",
            "description": "", "timing_mode": "sequential",
            "start_time": "2030-01-01T12:00:00Z",
            "lot_duration_seconds": 120,
            "stagger_offset_seconds": 60,
            "submission_intent": "draft",
            "lots": [],
        },
        timeout=15,
    )
    assert create.status_code in (200, 201), create.text
    event_id = create.json()["id"]

    # Two lots — one bad (QC without title_fr), one good
    body = {"lots": [
        {"vin": "1HGBH41JXMN109186", "year": 2020, "make": "Toyota", "model": "Camry",
         "starting_price": 5000, "location_city": "Montréal",
         "location_province": "QC", "title": "QC lot without FR title"},
        {"vin": "1FTFW1ET9DFA12345", "year": 2019, "make": "Ford", "model": "F-150",
         "starting_price": 6000, "location_city": "Toronto",
         "location_province": "ON", "title": "ON lot OK"},
    ]}
    r = requests.post(f"{API}/vehicle-multi-lot-auctions/{event_id}/bulk-import",
                      headers=h, json=body, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] == 1  # only the ON lot
    assert len(data["errors"]) == 1
    err = data["errors"][0]
    assert err["row"] == 1
    assert "title_fr" in err["message_en"].lower() or "bill 96" in err["message_en"].lower()
    # FR message is also present
    assert any(s in err["message_fr"].lower() for s in ["loi 96", "titre"])


# ───────────────── ERROR LOGS ─────────────────
def test_log_frontend_error_anonymous_accepted():
    """Public endpoint — anonymous error logging is allowed."""
    r = requests.post(f"{API}/errors/frontend",
                      json={"error_message": "pytest test error", "url": "/test"},
                      timeout=10)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "id" in r.json()


def test_admin_errors_frontend_requires_admin():
    r = requests.get(f"{API}/admin/errors/frontend", timeout=10)
    assert r.status_code in (401, 403)


def test_admin_errors_frontend_list(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{API}/admin/errors/frontend?days=30&limit=10", headers=h, timeout=10)
    assert r.status_code == 200
    assert "items" in r.json()
    assert "total" in r.json()


def test_admin_errors_backend_list(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{API}/admin/errors/backend?days=30&limit=10", headers=h, timeout=10)
    assert r.status_code == 200
    assert "items" in r.json()
