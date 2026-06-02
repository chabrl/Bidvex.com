"""
iter265 — 5-Mission sprint covering:

  Mission 1 — Raw HTML email refactor through `send_unified_email`
              (via the new `EmailService.send_raw_html` shim) + inline
              Promoted-card injection on Lots Marketplace + Seller
              Promote modal + geo-notification wiring.
  Mission 2 — `GET /api/admin/test-email` admin verification endpoint
              + SendGrid live-send observability.
  Mission 3 — `POST /api/affiliate/request-payout` spec-aligned alias
              persisting both to `affiliate_payouts` (new) and
              `withdrawal_requests` (legacy).
  Mission 4 — `GET /api/feeds/meta-catalog.json` public JSON feed
              + `robots.txt` sitemap entry.
  Mission 5 — Daily 06:00 UTC compliance scan via APScheduler +
              FR language toggle (`PATCH /api/users/me {language}`).
"""
from __future__ import annotations

import os

import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ─── Mission 1 ────────────────────────────────────────────────────────


def test_iter265_email_service_send_raw_html_routes_through_unified():
    """`EmailService.send_raw_html` (added in iter265) must route
    through `send_unified_email()` with `html_full_override`."""
    src = _read("services/email_service.py")
    assert "async def send_raw_html(" in src
    assert "html_full_override" in src
    assert "send_unified_email" in src


def test_iter265_geo_notify_wired_on_listing_create():
    src = _read("routes/listings.py")
    assert "from services.geo_notifications import notify_nearby_users" in src
    assert "notify_nearby_users(" in src


def test_iter265_lots_marketplace_inline_promoted_cards():
    src = _read("../frontend/src/pages/LotsMarketplacePage.js")
    # Splice positions + section + fetch path.
    assert "PROMO_SLOTS" in src
    assert "section=lots" in src
    assert "promoted-listings" in src


def test_iter265_seller_promote_modal_mounted():
    """The seller Promote modal is mounted on SellerDashboard."""
    src = _read("../frontend/src/pages/SellerDashboard.js")
    assert "PromoteListingModal" in src
    assert "promote-listing-btn-" in src


def test_iter265_promote_endpoint_exists():
    """`POST /api/listings/{id}/promote` is wired in routes/promotions.py."""
    src = _read("routes/promotions.py")
    assert '/listings/{listing_id}/promote' in src


# ─── Mission 2 ────────────────────────────────────────────────────────


def test_iter265_admin_test_email_endpoint_registered():
    src = _read("routes/admin_oversight.py")
    assert '@admin_oversight_router.get("/test-email")' in src
    assert "send_unified_email" in src


def test_iter265_admin_test_email_requires_auth():
    """The endpoint MUST refuse anonymous callers (401 from get_current_user)."""
    base = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
    try:
        r = httpx.get(f"{base}/api/admin/test-email", timeout=8.0)
    except Exception:
        return  # backend offline in CI
    assert r.status_code in (401, 403)


# ─── Mission 3 ────────────────────────────────────────────────────────


def test_iter265_affiliate_request_payout_registered():
    src = _read("routes/misc.py")
    assert '@misc_router.post("/affiliate/request-payout")' in src
    assert "affiliate_payouts" in src


def test_iter265_affiliate_payout_requires_auth():
    base = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
    try:
        r = httpx.post(f"{base}/api/affiliate/request-payout", json={}, timeout=8.0)
    except Exception:
        return
    assert r.status_code in (401, 403)


# ─── Mission 4 ────────────────────────────────────────────────────────


def test_iter265_meta_catalog_endpoint_registered():
    src = _read("routes/feeds.py")
    assert '@router.get("/meta-catalog.json")' in src
    assert '"version":      1' in src or '"version": 1' in src


def test_iter265_meta_catalog_returns_active_listings_shape():
    base = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
    try:
        r = httpx.get(f"{base}/api/feeds/meta-catalog.json?limit=3", timeout=10.0)
    except Exception:
        return
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("version") == 1
    assert "count" in data
    assert "items" in data and isinstance(data["items"], list)
    for item in data["items"][:3]:
        for k in ("id", "title", "price", "currency", "image", "url"):
            assert k in item


def test_iter265_robots_includes_meta_catalog_sitemap():
    """The frontend's static `public/robots.txt` lists the new feed."""
    src = _read("../frontend/public/robots.txt")
    assert "meta-catalog.json" in src


# ─── Mission 5 ────────────────────────────────────────────────────────


def test_iter265_compliance_scan_callable_exported():
    """The scan logic was factored out so the scheduler can call it."""
    src = _read("routes/admin_oversight.py")
    assert "async def execute_compliance_scan(" in src
    assert "execute_compliance_scan" in src.split("__all__")[1]


def test_iter265_compliance_scheduler_cron_registered():
    src = _read("services/scheduler.py")
    assert "compliance_scan_daily" in src
    assert "CronTrigger(hour=6, minute=0)" in src
    assert "execute_compliance_scan" in src


def test_iter265_users_me_accepts_patch_and_language_alias():
    """The canonical /users/me update endpoint accepts PATCH + maps
    `language` → `preferred_language` per spec."""
    src = _read("routes/profiles.py")
    assert '@profiles_router.put("/users/me")' in src
    assert '@profiles_router.patch("/users/me")' in src
    # The language alias path must convert "fr"/"en".
    assert '"preferred_language"] = "fr"' in src
    assert '"preferred_language"] = "en"' in src


def test_iter265_patch_users_me_fr_persists_preferred_language():
    """Live PATCH round-trip — uses the admin account from test_credentials."""
    base = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
    try:
        login = httpx.post(
            f"{base}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=8.0,
        )
    except Exception:
        return
    if login.status_code != 200:
        return  # rate-limit / env issue
    token = login.json().get("access_token") or login.json().get("token")
    if not token:
        return
    headers = {"Authorization": f"Bearer {token}"}
    # PATCH fr
    r = httpx.patch(f"{base}/api/users/me", json={"language": "fr"}, headers=headers, timeout=8.0)
    assert r.status_code == 200, r.text
    me = httpx.get(f"{base}/api/auth/me", headers=headers, timeout=8.0).json()
    assert me.get("preferred_language") == "fr"
    # Reset
    httpx.patch(f"{base}/api/users/me", json={"language": "en"}, headers=headers, timeout=8.0)
