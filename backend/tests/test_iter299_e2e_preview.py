"""
iter299 — E2E interactive validation on PREVIEW environment.

Focus: live HTTP flows that pytest unit tests (test_iter299_postlaunch.py)
do not cover — specifically moderation approve/reject E2E with DB state
verification, notifications bilingual fallback, analytics overview shape,
ending_soon filter, no-phone register.

Single admin login -> token reused across all tests (rate-limit safe).
"""
import os
import time
import uuid

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "iter225buyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer225!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def buyer_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD},
                      timeout=30)
    if r.status_code != 200:
        pytest.skip(f"buyer login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


def _ah(tok):
    return {"Authorization": f"Bearer {tok}"}


# ───────────────── Analytics ─────────────────
def test_analytics_overview(admin_token):
    r = requests.get(f"{BASE}/api/admin/analytics/overview", headers=_ah(admin_token), timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d.get("gmv"), dict)
    assert "all_time" in d["gmv"] and "last_30d" in d["gmv"]
    assert "platform_revenue" in d
    assert "auctions_by_section" in d
    assert "users_by_role" in d
    assert "top_sellers" in d
    assert "top_listings" in d
    assert "conversion_rate_pct" in d
    assert isinstance(d.get("signups_per_day"), list) and len(d["signups_per_day"]) == 30
    assert isinstance(d.get("revenue_per_day"), list) and len(d["revenue_per_day"]) == 30


def test_analytics_advanced_merged(admin_token):
    r = requests.get(f"{BASE}/api/admin/analytics/advanced",
                     headers=_ah(admin_token), timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    # gmv + revenue merged into legacy
    assert isinstance(d.get("gmv"), dict) and "all_time" in d["gmv"]
    assert "platform_revenue" in d
    # legacy fields preserved
    assert "top_sellers" in d or "conversion" in d


def test_analytics_advanced_no_auth():
    r = requests.get(f"{BASE}/api/admin/analytics/advanced", timeout=30)
    assert r.status_code in (401, 403)


# ───────────────── Moderation ─────────────────
def test_moderation_count(admin_token):
    r = requests.get(f"{BASE}/api/admin/moderation/count", headers=_ah(admin_token), timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json().get("pending_review"), int)


def test_moderation_pending_enrichment(admin_token):
    r = requests.get(f"{BASE}/api/admin/moderation/pending", headers=_ah(admin_token), timeout=30)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "listings" in d and "total" in d
    if not d["listings"]:
        pytest.skip("no pending listings to verify enrichment")
    row = d["listings"][0]
    assert row.get("section") in ("marketplace", "lots")
    assert "seller_email" in row
    # title_fr / seller_name / seller_province may be None for legacy rows
    # but the keys must exist
    for k in ("title_fr", "seller_name", "seller_province"):
        assert k in row, f"missing enrichment key: {k}"


def test_moderation_requires_admin():
    r = requests.get(f"{BASE}/api/admin/moderation/pending", timeout=30)
    assert r.status_code in (401, 403)


def test_moderation_reject_empty_reason_422(admin_token):
    # Use a random uuid (no need to be real — 422 happens at validation layer)
    r = requests.post(f"{BASE}/api/admin/moderation/{uuid.uuid4()}/reject",
                      json={"reason": ""}, headers=_ah(admin_token), timeout=30)
    assert r.status_code == 422, f"got {r.status_code}: {r.text[:200]}"


def test_moderation_approve_unknown_id_404(admin_token):
    r = requests.post(f"{BASE}/api/admin/moderation/{uuid.uuid4()}/approve",
                      headers=_ah(admin_token), timeout=30)
    assert r.status_code == 404


def _get_pending_ids(admin_token, limit=2):
    r = requests.get(f"{BASE}/api/admin/moderation/pending", headers=_ah(admin_token), timeout=30)
    assert r.status_code == 200
    listings = r.json().get("listings", [])
    return [(it["id"], it.get("section", "marketplace")) for it in listings[:limit]]


def test_moderation_approve_e2e(admin_token):
    """Approve ONE pending listing, verify status flips + 409 on re-approve."""
    pending = _get_pending_ids(admin_token, limit=2)
    if not pending:
        pytest.skip("no pending listings to approve")
    listing_id, section = pending[0]

    r = requests.post(f"{BASE}/api/admin/moderation/{listing_id}/approve",
                      headers=_ah(admin_token), timeout=30)
    assert r.status_code == 200, f"approve failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    # response shape sanity
    assert body.get("ok") is True or "status" in body or "listing" in body

    # Re-approving the same id should now be 409
    r2 = requests.post(f"{BASE}/api/admin/moderation/{listing_id}/approve",
                       headers=_ah(admin_token), timeout=30)
    assert r2.status_code in (409, 400), f"expected 409 on re-approve, got {r2.status_code}"

    # Listing should no longer be in pending
    r3 = requests.get(f"{BASE}/api/admin/moderation/pending", headers=_ah(admin_token), timeout=30)
    pending_ids = [x["id"] for x in r3.json().get("listings", [])]
    assert listing_id not in pending_ids, "approved listing still appears in pending queue"


def test_moderation_reject_e2e(admin_token):
    """Reject ONE different pending listing with a reason."""
    pending = _get_pending_ids(admin_token, limit=5)
    if not pending:
        pytest.skip("no pending listings to reject")
    listing_id, _ = pending[0]
    reason = "iter299 E2E test rejection — non-compliant title"

    r = requests.post(f"{BASE}/api/admin/moderation/{listing_id}/reject",
                      json={"reason": reason}, headers=_ah(admin_token), timeout=30)
    assert r.status_code == 200, f"reject failed: {r.status_code} {r.text[:300]}"

    # No longer in pending
    r2 = requests.get(f"{BASE}/api/admin/moderation/pending", headers=_ah(admin_token), timeout=30)
    pending_ids = [x["id"] for x in r2.json().get("listings", [])]
    assert listing_id not in pending_ids


# ───────────────── Notifications bilingual fallback ─────────────────
def test_notifications_bilingual_non_empty(buyer_token):
    r = requests.get(f"{BASE}/api/notifications", headers=_ah(buyer_token), timeout=30)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    rows = data if isinstance(data, list) else data.get("notifications") or data.get("items") or []
    if not rows:
        pytest.skip("no notifications for buyer account")
    missing = []
    for n in rows[:25]:
        for k in ("title_en", "message_en", "title_fr", "message_fr"):
            if not (n.get(k) or "").strip():
                missing.append((n.get("id") or n.get("_id"), k))
    assert not missing, f"notifications with empty bilingual fields: {missing[:5]}"


# ───────────────── Register without phone ─────────────────
def test_register_without_phone():
    ts = int(time.time())
    payload = {
        "email": f"ta299+{ts}@example.com",
        "password": "TestBuyer123!",
        "name": "iter299 test",
        "terms_agreed": True,
        "ai_disclosure_consent": True,
    }
    r = requests.post(f"{BASE}/api/auth/register", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"register w/o phone failed: {r.status_code} {r.text[:300]}"


# ───────────────── Ending soon filter ─────────────────
def test_marketplace_ending_soon():
    r = requests.get(f"{BASE}/api/marketplace/items", params={"ending_soon": "true"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("results") or []
    now = time.time()
    # 24h window — be permissive (some seeds may slip a bit), use 25h cap
    for it in items:
        end = it.get("auction_end_time") or it.get("ends_at") or it.get("end_time")
        if not end:
            continue
        # parse iso
        from datetime import datetime
        try:
            t = datetime.fromisoformat(str(end).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        assert t - now <= 25 * 3600, f"item {it.get('id')} ends in >24h"
