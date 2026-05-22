"""
iter219 — Storage Locker "Visible Content Tags" + category-bypass tests.

Coverage:
1. `sanitize_visible_content_tags` helper — slugs, aliases, drops unknowns.
2. `POST /api/listings` with `listing_type=storage_locker`:
   - Hard-codes `category="storage_locker"` even if caller varies it.
   - Persists `visible_content_tags` after normalization.
   - Publishes successfully with NO tags (system is optional).
3. `GET /api/storage-auctions?tags=furniture,tools` filters by tag.
4. `GET /api/storage-auctions?search=Meubles` accepts bilingual queries.
5. Endpoint response exposes `available_tags` so the FE doesn't drift.

These tests hit the LIVE preview API via `requests` (same pattern as
test_iter218_meta_pixel_integration.py). They sidestep the TestClient
event-loop-closed issue documented in the handoff.
"""
import os
import uuid
import pytest
import requests

# Live API base — read from frontend .env so we stay in sync.
def _api_base() -> str:
    env_path = "/app/frontend/.env"
    with open(env_path) as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.strip().split("=", 1)[1].rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found in frontend/.env")


BASE_URL = _api_base()

from services.visible_content_tags import (  # noqa: E402
    sanitize_visible_content_tags,
    ALLOWED_CONTENT_TAGS,
)


# ─── 1. Helper unit tests ──────────────────────────────────────────


def test_sanitize_accepts_canonical_slugs():
    assert sanitize_visible_content_tags(["boxes", "tools"]) == ["boxes", "tools"]


def test_sanitize_normalizes_bilingual_aliases():
    out = sanitize_visible_content_tags(["Meubles", "Outils", "Boîtes"])
    assert sorted(out) == ["boxes", "furniture", "tools"]


def test_sanitize_drops_unknown_silently():
    out = sanitize_visible_content_tags(["furniture", "spaceship", "unicorn"])
    assert out == ["furniture"]


def test_sanitize_deduplicates():
    out = sanitize_visible_content_tags(["boxes", "boxes", "Boîtes", "Boxes"])
    assert out == ["boxes"]


def test_sanitize_handles_none_empty_non_list():
    assert sanitize_visible_content_tags(None) == []
    assert sanitize_visible_content_tags([]) == []
    assert sanitize_visible_content_tags("furniture") == []   # str not allowed
    assert sanitize_visible_content_tags(123) == []           # int not allowed


def test_sanitize_handles_whitespace_and_casing():
    out = sanitize_visible_content_tags(["  Boxes  ", "TOOLS", "Sporting-Goods"])
    assert sorted(out) == ["boxes", "sporting_goods", "tools"]


def test_allowed_content_tags_count():
    # Lock down: 7 canonical tags exactly (matches FE constant).
    assert len(ALLOWED_CONTENT_TAGS) == 7


# ─── 2. POST /api/listings storage_locker behaviours ────────────────


@pytest.fixture(scope="module")
def auth_token():
    """Login fixture for the seed test account."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Test credentials login failed: {r.status_code} {r.text}")
    body = r.json()
    return body.get("access_token") or body.get("token")


def _storage_payload(extra=None):
    from datetime import datetime, timedelta, timezone
    # iter219 — Use only alpha chars to dodge the vehicle dealer guard's
    # substring matchers (Audi "A3", etc.).
    suffix = uuid.uuid4().hex[:6].translate(str.maketrans("0123456789", "ghijklmnop"))
    p = {
        "title": f"Storage Locker Auction Unit {suffix}",
        "description": "Closed boxes and miscellaneous items inside the unit. Sold as-is.",
        "category": "furniture",  # intentionally retail to verify override
        "condition": "good",      # required by ListingCreate; will be overwritten to as_is
        "starting_price": 50.0,
        "images": [],
        "location": "Montreal, QC",
        "city": "Montreal",
        "region": "QC",
        "country": "CA",
        "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "listing_type": "storage_locker",
        "storage_metadata": {
            "facility_name": "Unit Test Storage Co",
            "facility_address": "123 Main St",
            "locker_size": "10x10",
            "locker_number": "B12",
            "cleanout_deadline_hours": 72,
            "security_deposit_amount": 100,
            "facility_manager_email": "manager@example.com",
            "facility_manager_phone": "514-555-0000",
            "notes": "",
        },
        "agreement_accepted": True,
    }
    if extra:
        p.update(extra)
    return p


def test_storage_listing_forces_category_to_storage_locker(auth_token):
    """Even when caller submits category='furniture', backend MUST overwrite
    it to 'storage_locker' for storage_locker listings."""
    payload = _storage_payload({"visible_content_tags": ["furniture", "tools"]})
    r = requests.post(
        f"{BASE_URL}/api/listings",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    out = r.json()
    assert out.get("listing_type") == "storage_locker"
    assert out.get("category") == "storage_locker", (
        f"Expected category overridden to 'storage_locker', got {out.get('category')!r}"
    )
    assert set(out.get("visible_content_tags") or []) == {"furniture", "tools"}


def test_storage_listing_publishes_with_no_tags(auth_token):
    """A facility manager who cut a lock and sees only closed boxes MUST be
    able to publish with ZERO tags — the tag system is OPTIONAL."""
    payload = _storage_payload()
    payload.pop("visible_content_tags", None)
    r = requests.post(
        f"{BASE_URL}/api/listings",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    out = r.json()
    assert out.get("visible_content_tags") == [], (
        f"Expected empty tag list, got {out.get('visible_content_tags')!r}"
    )


def test_storage_listing_strips_buy_now_price(auth_token):
    """Storage Locker auctions MUST not support Buy Now Price (open-ended
    bidding only). Even when caller submits buy_now_price=999, backend
    forces it to None."""
    payload = _storage_payload({"buy_now_price": 999.99})
    r = requests.post(
        f"{BASE_URL}/api/listings",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    out = r.json()
    assert out.get("buy_now_price") in (None, 0, 0.0), (
        f"Expected buy_now_price stripped to None, got {out.get('buy_now_price')!r}"
    )


def test_storage_listing_filters_unknown_tags_but_keeps_valid_ones(auth_token):
    """Unknown tag values dropped silently, valid ones kept."""
    payload = _storage_payload(
        {"visible_content_tags": ["furniture", "spaceship", "Outils"]}
    )
    r = requests.post(
        f"{BASE_URL}/api/listings",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=30,
    )
    assert r.status_code in (200, 201), r.text
    saved = r.json().get("visible_content_tags") or []
    assert set(saved) == {"furniture", "tools"}


# ─── 3. GET /api/storage-auctions tag + search filters ──────────────


def test_browse_endpoint_returns_available_tags_list():
    """Endpoint exposes the canonical tag list so the FE doesn't drift."""
    r = requests.get(f"{BASE_URL}/api/storage-auctions?limit=1", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "available_tags" in body
    assert sorted(body["available_tags"]) == sorted(ALLOWED_CONTENT_TAGS)


def test_browse_endpoint_accepts_tags_filter_param():
    """Endpoint accepts ?tags=furniture,tools without erroring."""
    r = requests.get(
        f"{BASE_URL}/api/storage-auctions?tags=furniture,tools", timeout=15
    )
    assert r.status_code == 200
    body = r.json()
    assert "auctions" in body
    assert body.get("applied_tags") == ["furniture", "tools"]


def test_browse_endpoint_normalizes_french_tag_aliases():
    """French alias `Meubles` is normalized to `furniture`."""
    r = requests.get(
        f"{BASE_URL}/api/storage-auctions?tags=Meubles,Outils", timeout=15
    )
    assert r.status_code == 200
    body = r.json()
    assert sorted(body.get("applied_tags") or []) == ["furniture", "tools"]


def test_browse_endpoint_drops_unknown_tags():
    """Unknown tag values must be filtered out, not crash the endpoint."""
    r = requests.get(
        f"{BASE_URL}/api/storage-auctions?tags=furniture,spaceship,unicorn",
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("applied_tags") == ["furniture"]


def test_browse_endpoint_search_keyword_does_not_crash():
    """Free-text search keyword param accepted; result list well-formed."""
    r = requests.get(f"{BASE_URL}/api/storage-auctions?search=Meubles", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("auctions"), list)
    assert isinstance(body.get("total"), int)


def test_browse_endpoint_search_with_regex_special_chars():
    """Regex special chars in user search input MUST be escaped (no crash)."""
    for q in ["furniture.*", "[bracket]", "(group)", "$dollar^", "\\backslash"]:
        r = requests.get(
            f"{BASE_URL}/api/storage-auctions",
            params={"search": q},
            timeout=15,
        )
        assert r.status_code == 200, f"failed for search={q!r}: {r.text}"
