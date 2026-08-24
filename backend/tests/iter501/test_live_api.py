"""iter501 live-API integration tests against the running preview backend."""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def db():
    # Load env from backend/.env
    from pathlib import Path
    env_file = Path("/app/backend/.env")
    mongo_url = MONGO_URL
    db_name = DB_NAME
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("MONGO_URL="):
                mongo_url = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("DB_NAME="):
                db_name = line.split("=", 1)[1].strip().strip('"')
    client = MongoClient(mongo_url)
    yield client[db_name]
    client.close()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture()
def seed_user(db):
    """Create a fresh test user with an affiliate_code."""
    uid = str(uuid.uuid4())
    doc = {
        "id": uid,
        "email": f"TEST_iter501_{uid[:8]}@example.com",
        "name": "Iter501 Test",
        "affiliate_code": f"IT501{uid[:6].upper()}",
        "affiliate_status": "none",
        "commission_rate": None,
        "created_at": "2026-01-01T00:00:00Z",
    }
    db.users.insert_one(doc)
    yield doc
    db.users.delete_one({"id": uid})
    db.admin_action_logs.delete_many({"target_user_id": uid})


# --- Tests ---

def test_admin_get_all_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/affiliate/admin/all", timeout=20)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("default_rate") == 0.03
    assert body.get("max_rate") == 0.20
    items = body.get("items") or body.get("affiliates") or []
    assert isinstance(items, list)
    if items:
        row = items[0]
        for field in ["id", "email", "affiliate_code", "affiliate_status", "commission_rate", "effective_rate", "referred_count", "total_credits_earned"]:
            assert field in row, f"missing {field} in {row}"


def test_set_status_active_with_rate(admin_session, seed_user, db):
    uid = seed_user["id"]
    r = admin_session.post(f"{BASE_URL}/api/affiliate/admin/set-status",
                           json={"user_id": uid, "status": "active", "commission_rate": 0.05}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    u = db.users.find_one({"id": uid})
    assert u["affiliate_status"] == "active"
    assert abs(u["commission_rate"] - 0.05) < 1e-9
    log = db.admin_action_logs.find_one({"target_user_id": uid}, sort=[("_id", -1)])
    assert log is not None
    before = log.get("before") or {}
    after = log.get("after") or {}
    b_status = before.get("status") or before.get("affiliate_status")
    a_status = after.get("status") or after.get("affiliate_status")
    a_rate = after.get("rate") if after.get("rate") is not None else after.get("commission_rate")
    assert b_status in ("none", None)
    assert a_status == "active"
    assert abs((a_rate or 0) - 0.05) < 1e-9


def test_set_rate_out_of_range(admin_session, seed_user, db):
    uid = seed_user["id"]
    # first set a known rate
    admin_session.post(f"{BASE_URL}/api/affiliate/admin/set-status",
                       json={"user_id": uid, "status": "active", "commission_rate": 0.05}, timeout=20)
    r = admin_session.post(f"{BASE_URL}/api/affiliate/admin/set-rate",
                           json={"user_id": uid, "commission_rate": 0.50}, timeout=20)
    assert r.status_code == 400
    body = r.json()
    err = body.get("error") or body.get("detail")
    assert err and "out_of_range" in str(err), body
    u = db.users.find_one({"id": uid})
    assert abs(u["commission_rate"] - 0.05) < 1e-9  # unchanged


def test_set_rate_null_clears(admin_session, seed_user, db):
    uid = seed_user["id"]
    admin_session.post(f"{BASE_URL}/api/affiliate/admin/set-status",
                       json={"user_id": uid, "status": "active", "commission_rate": 0.07}, timeout=20)
    r = admin_session.post(f"{BASE_URL}/api/affiliate/admin/set-rate",
                           json={"user_id": uid, "commission_rate": None}, timeout=20)
    assert r.status_code == 200, r.text[:300]
    u = db.users.find_one({"id": uid})
    assert u.get("commission_rate") in (None,)
    # effective rate via admin/all
    r2 = admin_session.get(f"{BASE_URL}/api/affiliate/admin/all", timeout=20)
    row = next((x for x in r2.json().get("items", []) if x["id"] == uid), None)
    assert row is not None
    assert abs(row["effective_rate"] - 0.03) < 1e-9


def test_set_status_idempotent(admin_session, seed_user, db):
    uid = seed_user["id"]
    r1 = admin_session.post(f"{BASE_URL}/api/affiliate/admin/set-status",
                            json={"user_id": uid, "status": "active", "commission_rate": 0.08}, timeout=20)
    assert r1.status_code == 200
    logs_before = db.admin_action_logs.count_documents({"target_user_id": uid})
    r2 = admin_session.post(f"{BASE_URL}/api/affiliate/admin/set-status",
                            json={"user_id": uid, "status": "active", "commission_rate": 0.08}, timeout=20)
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("changed") is False
    logs_after = db.admin_action_logs.count_documents({"target_user_id": uid})
    assert logs_after == logs_before, f"expected no new log row, got {logs_after - logs_before}"


def test_non_admin_denied(seed_user):
    # anonymous request
    r = requests.post(f"{BASE_URL}/api/affiliate/admin/set-status",
                      json={"user_id": seed_user["id"], "status": "active"}, timeout=20)
    assert r.status_code in (401, 403)
    r2 = requests.post(f"{BASE_URL}/api/affiliate/admin/set-rate",
                       json={"user_id": seed_user["id"], "commission_rate": 0.05}, timeout=20)
    assert r2.status_code in (401, 403)


def test_backfill_idempotent(admin_session):
    r1 = admin_session.post(f"{BASE_URL}/api/affiliate/admin/backfill-active", json={}, timeout=30)
    assert r1.status_code == 200, r1.text[:300]
    r2 = admin_session.post(f"{BASE_URL}/api/affiliate/admin/backfill-active", json={}, timeout=30)
    assert r2.status_code == 200
    body2 = r2.json()
    promoted = body2.get("promoted", body2.get("promoted_count", 0))
    assert promoted == 0, f"second run should promote 0, got {body2}"


def test_legacy_shim_sets_active_no_affiliates_row(admin_session, seed_user, db):
    uid = seed_user["id"]
    r = admin_session.put(f"{BASE_URL}/api/admin/users/{uid}/affiliate",
                          json={"is_affiliate": True}, timeout=20)
    assert r.status_code in (200, 201), r.text[:300]
    u = db.users.find_one({"id": uid})
    assert u["affiliate_status"] == "active"
    # NO row in db.affiliates
    aff_row = db.affiliates.find_one({"user_id": uid}) if "affiliates" in db.list_collection_names() else None
    assert aff_row is None
    # flip false → revoked
    r2 = admin_session.put(f"{BASE_URL}/api/admin/users/{uid}/affiliate",
                           json={"is_affiliate": False}, timeout=20)
    assert r2.status_code in (200, 201)
    u2 = db.users.find_one({"id": uid})
    assert u2["affiliate_status"] == "revoked"


def test_earnings_summary_returns_rate_as_float(admin_session):
    # admin is also a user; check the shape
    r = admin_session.get(f"{BASE_URL}/api/affiliate/earnings-summary", timeout=20)
    assert r.status_code in (200, 403, 404), r.text[:300]
    if r.status_code == 200:
        body = r.json()
        assert "commission_rate" in body
        assert isinstance(body["commission_rate"], (int, float))
        assert "default_commission_rate" in body
        assert body["default_commission_rate"] == 0.03
        assert "affiliate_status" in body


def test_affiliate_stats_shape(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/affiliate/stats", timeout=20)
    assert r.status_code in (200, 403, 404)
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body.get("commission_rate"), (int, float))
        assert "commission_rate_display" in body
        assert "%" in body["commission_rate_display"]
        assert body.get("default_commission_rate") == 0.03
        assert "affiliate_status" in body
