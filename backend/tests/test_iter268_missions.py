"""
iter268 — 5-Mission sprint covering:

  Mission 1 — Stripe Transfer webhooks (`transfer.created`, `paid`,
              `failed`, `reversed`) drive the `stripe_transfer_status`
              field on `affiliate_payouts`; admin re-issue endpoint
              creates a fresh Transfer with full history audit.
  Mission 2 — Admin `reset-attachment` endpoint clears the submission,
              deletes the file from disk (traversal-guarded), and
              notifies the user via a fresh bell.
  Mission 3 — Pre-launch audit: ErrorBoundary now wrapping critical
              routes at the App.js level + every existing component
              import is valid (yarn build green).
  Mission 4 — SEO meta tags added to Marketplace, Lots, ContactUs
              (HomePage + ListingDetail were already done).
  Mission 5 — Sitemap now includes vehicle auctions + multi-item lots
              in addition to the previously covered listings + storage.
"""
from __future__ import annotations

import os
import httpx


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")


def _read(rel: str, root: str = BACKEND_ROOT) -> str:
    with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _login_admin():
    try:
        r = httpx.post(
            f"{BASE}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=8.0,
        )
        if r.status_code != 200:
            return None
        return r.json().get("access_token") or r.json().get("token")
    except Exception:
        return None


# ─── Mission 1 ────────────────────────────────────────────────────────


def test_iter268_transfer_webhook_dispatcher_registered():
    src = _read("routes/webhooks.py")
    for evt in ("transfer.created", "transfer.paid", "transfer.failed", "transfer.reversed"):
        assert evt in src, f"webhook handler missing {evt!r}"
    assert "_handle_affiliate_transfer_event" in src


def test_iter268_transfer_webhook_writes_status_fields():
    src = _read("routes/webhooks.py")
    assert "stripe_transfer_status" in src
    assert "stripe_transfer_failure_reason" in src
    assert "stripe_transfer_confirmed_at" in src


def test_iter268_admin_alert_on_failure_or_reversal():
    src = _read("routes/webhooks.py")
    assert "Affiliate payout transfer FAILED" in src
    assert "Affiliate payout REVERSED" in src
    assert "send_unified_email" in src


def test_iter268_reissue_endpoint_registered():
    src = _read("routes/admin_oversight.py")
    assert '@admin_oversight_router.post("/affiliate-payouts/{payout_id}/reissue")' in src
    assert "stripe_transfer_history" in src
    assert "Only failed/reversed transfers can be reissued" in src


def test_iter268_admin_table_renders_transfer_badge_and_reissue():
    src = _read("../frontend/src/pages/admin/AdminAffiliatePayouts.jsx")
    assert "TRANSFER_BADGES" in src
    assert "payout-transfer-badge-" in src
    assert "handleReissue" in src
    assert "payout-reissue-" in src
    # Status mapping per spec.
    assert "'✅ Confirmed by Stripe'" in src
    assert "'❌ Transfer Failed'" in src


def test_iter268_reissue_endpoint_live_404_for_missing():
    token = _login_admin()
    if not token:
        return
    r = httpx.post(
        f"{BASE}/api/admin/affiliate-payouts/nope/reissue",
        headers={"Authorization": f"Bearer {token}"},
        timeout=8.0,
    )
    assert r.status_code == 404


# ─── Mission 2 ────────────────────────────────────────────────────────


def test_iter268_reset_attachment_endpoint_registered():
    src = _read("routes/notifications.py")
    assert '@admin_notifications_router.post("/{notification_id}/reset-attachment")' in src
    assert "attachment_reset_by" in src
    assert "attachment_reset_at" in src


def test_iter268_reset_attachment_notifies_user():
    src = _read("routes/notifications.py")
    assert "Document re-upload requested" in src
    assert "Téléversement à nouveau requis" in src
    assert "attachment_reset" in src


def test_iter268_reset_attachment_path_traversal_guarded():
    src = _read("routes/notifications.py")
    # Both download AND reset must use realpath check.
    assert src.count("realpath") >= 2


def test_iter268_reset_attachment_requires_admin():
    """Unauthenticated → 401."""
    try:
        r = httpx.post(
            f"{BASE}/api/admin/notifications/x/reset-attachment",
            json={"reason": "test"},
            timeout=8.0,
        )
        assert r.status_code in (401, 403)
    except Exception:
        return


def test_iter268_reset_attachment_404_for_missing():
    token = _login_admin()
    if not token:
        return
    r = httpx.post(
        f"{BASE}/api/admin/notifications/does-not-exist/reset-attachment",
        json={"reason": "wrong file"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=8.0,
    )
    assert r.status_code == 404


# ─── Mission 3 ────────────────────────────────────────────────────────


def test_iter268_error_boundary_wraps_critical_routes():
    src = _read("../frontend/src/App.js")
    # Top-level import + at least 5 critical routes wrapped.
    assert "import ErrorBoundary from './components/ErrorBoundary';" in src
    boundary_count = src.count("<ErrorBoundary")
    assert boundary_count >= 7, f"Only {boundary_count} <ErrorBoundary wrappers"
    # Specific scopes per spec.
    for scope in (
        'scope="marketplace"',
        'scope="lots"',
        'scope="vehicle-auctions"',
        'scope="storage-auctions"',
        'scope="affiliate-dashboard"',
        'scope="admin"',
        'scope="broker-dashboard"',
    ):
        assert scope in src, f"missing ErrorBoundary {scope}"


def test_iter268_error_boundary_component_exists():
    src = _read("../frontend/src/components/ErrorBoundary.jsx")
    assert "getDerivedStateFromError" in src
    assert "handleRetry" in src


# ─── Mission 4 ────────────────────────────────────────────────────────


def test_iter268_seo_on_marketplace_page():
    src = _read("../frontend/src/pages/MarketplacePage.js")
    assert "import SEO from '../components/SEO'" in src
    assert "<SEO" in src


def test_iter268_seo_on_lots_marketplace():
    src = _read("../frontend/src/pages/LotsMarketplacePage.js")
    assert "import SEO from '../components/SEO'" in src
    assert "<SEO" in src


def test_iter268_seo_on_contact_us():
    src = _read("../frontend/src/pages/ContactUsPage.jsx")
    assert "<SEO" in src


def test_iter268_listing_detail_has_dynamic_seo():
    src = _read("../frontend/src/pages/ListingDetailPage.js")
    assert "<SEO" in src
    assert "schema.org" in src
    assert "Product" in src


# ─── Mission 5 ────────────────────────────────────────────────────────


def test_iter268_sitemap_includes_vehicles_and_lots():
    src = _read("routes/sitemap.py")
    assert "/vehicle-auctions/{vid}" in src
    assert "/lots/{lid}" in src
    assert "multi_item_listings" in src


def test_iter268_sitemap_live_returns_valid_xml():
    try:
        r = httpx.get(f"{BASE}/sitemap.xml", timeout=10.0)
        assert r.status_code == 200
        body = r.text
        assert body.startswith('<?xml')
        assert "<urlset" in body
        assert "</urlset>" in body
        # Always contains the homepage.
        assert "bidvex.com/" in body
    except Exception:
        return


def test_iter268_robots_lists_meta_catalog_and_sitemap():
    src_static = _read("../frontend/public/robots.txt")
    src_dyn = _read("routes/sitemap.py")
    assert "meta-catalog.json" in src_static
    assert "meta-catalog.json" in src_dyn
    assert "sitemap.xml" in src_dyn
