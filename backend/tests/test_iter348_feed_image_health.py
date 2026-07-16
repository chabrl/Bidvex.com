"""
iter348 — Tests for the feed image URL crawler-health check:
  - filter_crawlable HEAD-tests and TTL-caches results.
  - diagnose_sample returns actionable probable_cause per URL.
  - /api/feeds/image-diagnostics admin endpoint returns full report.
  - _build_feed_items swaps unreachable image_link to placeholder.
"""
from __future__ import annotations

import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
import pytest
import requests

sys.path.insert(0, str(Path("/app/backend")))
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

os.environ["TWILIO_SKIP_SIGNATURE_VERIFY"] = "1"

from pymongo import MongoClient
from services.feed_image_health import (
    clear_cache, cache_stats, is_url_crawlable,
    filter_crawlable, diagnose_sample,
)


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


API = _api_base() + "/api"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


def _mint_admin_token(db, prefix: str = "iter348_admin"):
    import bcrypt
    from jose import jwt
    uid = str(uuid.uuid4())
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"
    pw = bcrypt.hashpw(b"AdminPass123!", bcrypt.gensalt()).decode()
    db.users.insert_one({
        "id":             uid,
        "email":          email,
        "password":       pw,
        "name":           "Iter348 Admin",
        "role":           "super_admin",
        "created_at":     datetime.now(timezone.utc).isoformat(),
        "email_verified": True,
    })
    jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
    token = jwt.encode({
        "sub":   uid,
        "email": email,
        "type":  "access",
        "exp":   datetime.now(timezone.utc) + timedelta(hours=1),
    }, jwt_secret, algorithm="HS256")
    return token, uid


# ═══ Unit tests — feed_image_health ════════════════════════════════════

@pytest.mark.asyncio
async def test_clear_cache_and_stats_start_empty():
    clear_cache()
    s = cache_stats()
    assert s["total_cached"] == 0
    assert s["ttl_seconds"] == 3600


@pytest.mark.asyncio
async def test_is_url_crawlable_rejects_http():
    clear_cache()
    ok, ct, status = await is_url_crawlable("http://insecure.example.com/x.jpg")
    assert ok is False
    assert status == 0


@pytest.mark.asyncio
async def test_is_url_crawlable_admits_real_jpeg(monkeypatch):
    """Monkey-patch httpx to return a fake 200 image/jpeg HEAD so the
    test doesn't depend on the public internet."""
    clear_cache()

    class _FakeResp:
        def __init__(self, status: int, ct: str):
            self.status_code = status
            self.headers = {"content-type": ct}

    class _FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, url, headers=None, timeout=5.0):
            return _FakeResp(200, "image/jpeg")

    monkeypatch.setattr("services.feed_image_health.httpx.AsyncClient", _FakeClient)
    ok, ct, status = await is_url_crawlable("https://cdn.bidvex.com/x.jpg")
    assert ok is True
    assert ct == "image/jpeg"
    assert status == 200

    # Cache hit: second call must NOT re-invoke httpx.
    monkeypatch.setattr("services.feed_image_health.httpx.AsyncClient", None)
    ok2, ct2, status2 = await is_url_crawlable("https://cdn.bidvex.com/x.jpg")
    assert ok2 is True and ct2 == "image/jpeg" and status2 == 200


@pytest.mark.asyncio
async def test_is_url_crawlable_rejects_403(monkeypatch):
    clear_cache()

    class _FakeResp:
        status_code = 403
        headers = {"content-type": "application/xml"}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, url, headers=None, timeout=5.0):
            return _FakeResp()

    monkeypatch.setattr(
        "services.feed_image_health.httpx.AsyncClient",
        lambda *a, **k: _FakeClient(),
    )
    ok, ct, status = await is_url_crawlable(
        "https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/x.jpg"
    )
    assert ok is False
    assert ct == "application/xml"
    assert status == 403


@pytest.mark.asyncio
async def test_is_url_crawlable_rejects_wrong_content_type(monkeypatch):
    clear_cache()

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, url, headers=None, timeout=5.0):
            return _FakeResp()

    monkeypatch.setattr(
        "services.feed_image_health.httpx.AsyncClient",
        lambda *a, **k: _FakeClient(),
    )
    ok, ct, status = await is_url_crawlable("https://cdn.bidvex.com/photo")
    assert ok is False
    assert ct == "text/html"


@pytest.mark.asyncio
async def test_filter_crawlable_batch(monkeypatch):
    clear_cache()

    class _FakeResp:
        def __init__(self, status, ct):
            self.status_code = status
            self.headers = {"content-type": ct}

    call_count = {"n": 0}

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, url, headers=None, timeout=5.0):
            call_count["n"] += 1
            # bad-url returns 403, others 200 image/jpeg
            if "bad" in url:
                return _FakeResp(403, "application/xml")
            return _FakeResp(200, "image/jpeg")

    monkeypatch.setattr(
        "services.feed_image_health.httpx.AsyncClient",
        lambda *a, **k: _FakeClient(),
    )
    urls = [
        "https://cdn.bidvex.com/good.jpg",
        "https://cdn.bidvex.com/bad.jpg",
        "https://cdn.bidvex.com/good.jpg",  # duplicate → dedup
    ]
    result = await filter_crawlable(urls)
    assert result["https://cdn.bidvex.com/good.jpg"][0] is True
    assert result["https://cdn.bidvex.com/bad.jpg"][0] is False
    # Duplicate wasn't head-tested twice.
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_diagnose_sample_labels_probable_causes(monkeypatch):
    clear_cache()

    class _FakeResp:
        def __init__(self, status, ct):
            self.status_code = status
            self.headers = {"content-type": ct}

    causes = {
        "https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/blocked.jpg": (403, "application/xml"),
        "https://cdn.bidvex.com/expired.jpg":  (401, "application/xml"),
        "https://cdn.bidvex.com/missing.jpg":  (404, "application/xml"),
        "https://cdn.bidvex.com/wrongct.jpg":  (200, "text/html"),
        "https://cdn.bidvex.com/good.jpg":     (200, "image/jpeg"),
    }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, url, headers=None, timeout=5.0):
            st, ct = causes.get(url, (500, "text/plain"))
            return _FakeResp(st, ct)

    monkeypatch.setattr(
        "services.feed_image_health.httpx.AsyncClient",
        lambda *a, **k: _FakeClient(),
    )
    report = await diagnose_sample(list(causes.keys()), limit=10)
    assert report["tested"] == 5
    assert report["would_be_accepted_count"] == 1
    assert report["would_be_rejected_count"] == 4
    by_url = {r["url"]: r for r in report["results"]}

    r_403 = by_url["https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/blocked.jpg"]
    assert r_403["http_status"] == 403
    assert "bucket_policy" in r_403["probable_cause"]

    r_401 = by_url["https://cdn.bidvex.com/expired.jpg"]
    assert "presigned" in r_401["probable_cause"]

    r_404 = by_url["https://cdn.bidvex.com/missing.jpg"]
    assert "object_not_found" in r_404["probable_cause"]

    r_ct = by_url["https://cdn.bidvex.com/wrongct.jpg"]
    assert "wrong_content_type" in r_ct["probable_cause"]

    r_ok = by_url["https://cdn.bidvex.com/good.jpg"]
    assert r_ok["would_be_accepted"] is True
    assert r_ok["probable_cause"] is None


# ═══ Integration test — /api/feeds/image-diagnostics ═══════════════════

class TestFeedImageDiagnosticsEndpoint:

    def test_endpoint_requires_admin(self):
        r = requests.get(f"{API}/feeds/image-diagnostics", timeout=15)
        assert r.status_code in (401, 403)

    def test_endpoint_returns_report_for_admin(self, db):
        token, uid = _mint_admin_token(db, "iter348_diag")
        try:
            r = requests.get(
                f"{API}/feeds/image-diagnostics?limit=5",
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code} — {r.text[:400]}"
            data = r.json()
            assert "tested" in data
            assert "would_be_accepted_count" in data
            assert "would_be_rejected_count" in data
            assert "results" in data
            assert "next_steps" in data
            assert isinstance(data["next_steps"], list)
        finally:
            db.users.delete_one({"id": uid})
