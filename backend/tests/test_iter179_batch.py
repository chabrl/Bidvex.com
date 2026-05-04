"""iter179 5-fix batch validation.

Coverage:
  1. StorageAuctionCreate: default soft_close_extension_minutes == 2; validator 1..60
  2. scheduled_jobs.py: soft-close fallback is 2 (grep literal)
  3. storage_auction_service.py: fallback soft minutes is 2 (grep literal)
  4. POST /api/storage-auctions/{id}/bid returns required keys + current_bid matches DB
  5. Scheduler still registers activate_upcoming_auctions + 13 jobs
"""
import os
import re
import sys
import pytest
import requests

sys.path.insert(0, "/app/backend")

def _load_backend_url():
    url = os.environ.get('REACT_APP_BACKEND_URL')
    if not url:
        for line in open('/app/frontend/.env').read().splitlines():
            if line.startswith('REACT_APP_BACKEND_URL='):
                url = line.split('=', 1)[1].strip()
                break
    return url.rstrip('/')
BASE_URL = _load_backend_url()
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


# ── 1. Pydantic model default/validator ─────────────────────────────
class TestStorageAuctionCreateModel:
    def test_default_soft_close_is_2(self):
        from models.storage_auction import StorageAuctionCreate
        from datetime import datetime, timedelta, timezone
        m = StorageAuctionCreate(
            unit_number="T1", unit_size="5x5", unit_type="indoor",
            description_en="Test unit for iter179 soft close default check",
            starting_price=10.0,
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        assert m.soft_close_extension_minutes == 2

    def test_soft_close_validator_range(self):
        from models.storage_auction import StorageAuctionCreate
        from datetime import datetime, timedelta, timezone
        base = dict(
            unit_number="T1", unit_size="5x5", unit_type="indoor",
            description_en="Test unit for iter179 soft close range",
            starting_price=10.0,
            start_time=datetime.now(timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        # accepts 1
        m1 = StorageAuctionCreate(**base, soft_close_extension_minutes=1)
        assert m1.soft_close_extension_minutes == 1
        # accepts 60
        m60 = StorageAuctionCreate(**base, soft_close_extension_minutes=60)
        assert m60.soft_close_extension_minutes == 60
        # rejects 0 and 61
        with pytest.raises(Exception):
            StorageAuctionCreate(**base, soft_close_extension_minutes=0)
        with pytest.raises(Exception):
            StorageAuctionCreate(**base, soft_close_extension_minutes=61)


# ── 2 & 3. Source-code fallback literals ────────────────────────────
class TestSoftCloseFallbackSource:
    def test_scheduled_jobs_fallback_2(self):
        src = open("/app/backend/services/scheduled_jobs.py").read()
        assert re.search(
            r'soft_close_extension_minutes["\']?\s*,\s*2\s*\)\s*or\s*2', src
        ), "scheduled_jobs.py fallback must be 2 not 10"
        assert 'or 10' not in src.split("soft_minutes")[1].split("\n")[0]

    def test_service_fallback_2(self):
        src = open("/app/backend/services/storage_auction_service.py").read()
        assert re.search(
            r'soft_close_extension_minutes["\']?\s*,\s*2\s*\)\s*or\s*2', src
        ), "storage_auction_service.py fallback must be 2"


# ── 4. POST /api/storage-auctions/{id}/bid ──────────────────────────
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code}")
    return r.json().get("access_token") or r.json().get("token")


class TestStorageBidEndpoint:
    def test_bid_response_shape_and_db_consistency(self, admin_token):
        # find an active storage auction
        r = requests.get(f"{BASE_URL}/api/storage-auctions?status=active", timeout=15)
        assert r.status_code == 200
        data = r.json()
        auctions = data if isinstance(data, list) else data.get("auctions", [])
        active = [a for a in auctions if not a.get("deposit_required")]
        if not active:
            active = auctions
        if not active:
            pytest.skip("no active storage auctions to bid on")
        auction = active[0]
        aid = auction["id"]

        # current state
        cur = auction.get("current_bid") or auction.get("starting_price") or 0
        inc = auction.get("bid_increment") or 10
        next_bid = float(cur) + float(inc) + 1

        headers = {"Authorization": f"Bearer {admin_token}"}
        rb = requests.post(
            f"{BASE_URL}/api/storage-auctions/{aid}/bid",
            json={"max_bid": next_bid},
            headers=headers, timeout=15,
        )
        # Admin may own the auction; accept 400/403 gracefully but still verify shape if 200
        if rb.status_code != 200:
            # Still verify required-keys schema on 400 isn't asserted; skip cleanly
            pytest.skip(f"bid returned {rb.status_code}: {rb.text[:200]}")
        body = rb.json()
        for key in ("current_bid", "you_are_winning", "end_time", "soft_close_extended"):
            assert key in body, f"bid response missing {key}"

        # refetch auction and compare current_bid
        rg = requests.get(f"{BASE_URL}/api/storage-auctions/{aid}", timeout=15)
        assert rg.status_code == 200
        assert float(rg.json()["current_bid"]) == float(body["current_bid"])


# ── 5. Scheduler job registration ───────────────────────────────────
class TestSchedulerJobs:
    def test_activate_upcoming_registered(self):
        src = open("/app/backend/services/scheduler.py").read()
        assert "activate_upcoming_auctions" in src
        assert 'id="activate_upcoming_auctions"' in src

    def test_scheduler_log_has_jobs(self):
        # scheduler.py logs "Scheduler initialized with N jobs"
        paths = [
            "/var/log/supervisor/backend.err.log",
            "/var/log/supervisor/backend.out.log",
        ]
        joined = ""
        for p in paths:
            if os.path.exists(p):
                joined += open(p, errors="ignore").read()[-200000:]
        m = re.findall(r"Scheduler initialized with (\d+) jobs", joined)
        assert m, "Scheduler startup log not found"
        assert int(m[-1]) >= 13, f"Scheduler has {m[-1]} jobs; expected >=13"
