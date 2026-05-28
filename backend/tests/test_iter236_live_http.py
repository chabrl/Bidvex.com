"""iter236 live HTTP probes against preview URL (REACT_APP_BACKEND_URL)."""
import os
import re

import pytest
import requests

BASE_URL = "https://prod-verify-2.preview.emergentagent.com".rstrip("/")


def _get(path, **kw):
    return requests.get(f"{BASE_URL}{path}", timeout=30, **kw)


def _post(path, **kw):
    return requests.post(f"{BASE_URL}{path}", timeout=60, **kw)


# ---------- Mission 2: geo endpoints ----------
def test_geo_no_params_returns_200_empty_items():
    r = _get("/api/marketplace/items/geo")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data and "total" in data and "filter" in data
    assert isinstance(data["items"], list)


def test_geo_with_lat_lng_returns_filter_echo():
    r = _get("/api/marketplace/items/geo", params={
        "lat": 45.5017, "lng": -73.5673, "radius_km": 100, "limit": 5,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["filter"]["radius_km"] == 100
    assert abs(data["filter"]["lat"] - 45.5017) < 0.0001
    assert abs(data["filter"]["lng"] - (-73.5673)) < 0.0001
    assert isinstance(data["items"], list)


def test_geo_city_fallback_returns_200():
    r = _get("/api/marketplace/items/geo", params={"city": "montreal"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["filter"]["city"] == "montreal"
    assert isinstance(data["items"], list)


def test_ensure_geo_index_idempotent():
    r1 = _post("/api/marketplace/items/ensure-geo-index")
    r2 = _post("/api/marketplace/items/ensure-geo-index")
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json().get("status") == "ok"
    assert r2.json().get("status") == "ok"


# ---------- Mission 3: chat stream listing_id integration ----------
def test_chat_stream_missing_listing_id_does_not_500():
    r = _post(
        "/api/chat/stream",
        json={"message": "hello", "listing_id": "nonexistent-id-xyz"},
        stream=True,
    )
    assert r.status_code == 200, r.text[:200]
    body = b"".join(r.iter_content(chunk_size=1024))
    assert len(body) > 0


def test_chat_stream_with_real_listing_id():
    # Find a real listing id
    lr = _get("/api/marketplace/items", params={"limit": 1})
    assert lr.status_code == 200
    items = lr.json() if isinstance(lr.json(), list) else lr.json().get("items", [])
    if not items:
        pytest.skip("no marketplace items available to test with")
    lid = items[0].get("id")
    assert lid
    r = _post(
        "/api/chat/stream",
        json={"message": "Should I bid on this?", "listing_id": lid},
        stream=True,
    )
    assert r.status_code == 200, r.text[:200]
    body = b"".join(r.iter_content(chunk_size=1024)).decode("utf-8", errors="ignore")
    assert len(body) > 0
    # iter235 anti-hallucination: must not invent platform fee numbers.
    lower = body.lower()
    assert "$100 fee" not in lower
    assert "100$ fee" not in lower
    assert "3% fee" not in lower
    assert "3 % fee" not in lower
