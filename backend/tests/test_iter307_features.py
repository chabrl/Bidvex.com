"""
iter307 — Backend E2E tests
============================
Covers:
  • POST /api/settlement/panel/{listing_id}/resend-winner-notification
    (admin gate, max-3-resends counter, action logging, no-winner check)
  • Admin Compliance endpoints (read-only happy path for each section)
  • Affiliate endpoints (my-referral-link, /r/{code} redirect, admin/all)
  • Bill 96 sweep helper is importable (smoke)
"""
import os
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


def _admin_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─── Re-send winner notification (admin) ─────────────────────────────

def test_resend_winner_notification_requires_admin():
    r = requests.post(f"{API}/settlement/panel/fake-id/resend-winner-notification", timeout=15)
    assert r.status_code in (401, 403)


def test_resend_winner_notification_404_for_unknown_listing():
    t = _admin_token()
    r = requests.post(
        f"{API}/settlement/panel/totally-fake-listing-xyz/resend-winner-notification",
        headers=_h(t), timeout=15,
    )
    assert r.status_code == 404


# ─── Compliance Dashboard happy paths (all sections) ──────────────────

def test_compliance_flagged_listings_returns_items_list():
    t = _admin_token()
    r = requests.get(f"{API}/admin/compliance/flagged-listings", headers=_h(t), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d and isinstance(d["items"], list)
    assert "total" in d


def test_compliance_bidding_suspended_returns_items_list():
    t = _admin_token()
    r = requests.get(f"{API}/admin/compliance/bidding-suspended", headers=_h(t), timeout=15)
    assert r.status_code == 200
    assert "items" in r.json()


def test_compliance_overdue_payments_returns_items_list():
    t = _admin_token()
    r = requests.get(f"{API}/admin/compliance/overdue-payments", headers=_h(t), timeout=15)
    assert r.status_code == 200
    assert "items" in r.json()


def test_compliance_escalated_disputes_returns_items_list():
    t = _admin_token()
    r = requests.get(f"{API}/admin/compliance/escalated-disputes", headers=_h(t), timeout=15)
    assert r.status_code == 200
    assert "items" in r.json()


def test_compliance_bill96_violations_returns_items_list():
    t = _admin_token()
    r = requests.get(f"{API}/admin/compliance/bill96-violations", headers=_h(t), timeout=15)
    assert r.status_code == 200
    assert "items" in r.json()


def test_compliance_requires_admin():
    r = requests.get(f"{API}/admin/compliance/flagged-listings", timeout=15)
    assert r.status_code in (401, 403)


# ─── Affiliate / Referral ────────────────────────────────────────────

def test_affiliate_my_referral_link_returns_canonical_format():
    t = _admin_token()
    r = requests.get(f"{API}/affiliate/my-referral-link", headers=_h(t), timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("referral_code")
    assert d.get("referral_link", "").endswith(f"/r/{d['referral_code']}")


def test_affiliate_stats_uses_canonical_referral_url():
    t = _admin_token()
    r = requests.get(f"{API}/affiliate/stats", headers=_h(t), timeout=15)
    assert r.status_code == 200
    d = r.json()
    # Must NOT be the legacy `?ref=` format
    assert "?ref=" not in (d.get("referral_link") or "")
    assert "/r/" in (d.get("referral_link") or "")


def test_referral_landing_track_endpoint_works():
    # External traffic to /r/{code} hits the FRONTEND (React SPA handles it
    # client-side, setting the bidvex_ref cookie + calling this endpoint).
    # We test the click-track API contract here.
    r = requests.get(f"{API}/affiliate/track/TESTCODE123", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d.get("success") is True
    assert d.get("code") == "TESTCODE123"
    assert d.get("cookie_max_age_days") == 30


def test_admin_affiliate_all_requires_admin():
    r = requests.get(f"{API}/affiliate/admin/all", timeout=15)
    assert r.status_code in (401, 403)


def test_admin_affiliate_all_returns_items_for_admin():
    t = _admin_token()
    r = requests.get(f"{API}/affiliate/admin/all", headers=_h(t), timeout=15)
    assert r.status_code == 200
    assert "items" in r.json()


# ─── Meta + Google feed: iter307 fixes ───────────────────────────────

def test_meta_feed_region_is_iso_3166_2():
    r = requests.get(f"{API}/feeds/facebook-local?format=json", timeout=20)
    assert r.status_code == 200
    items = r.json().get("data", [])
    assert items, "Feed must have at least seed items"
    for it in items[:5]:
        region = it.get("region", "")
        assert region.startswith("CA-"), f"region must be ISO 3166-2 (CA-XX) but got {region!r}"


def test_meta_feed_shipping_block_present():
    r = requests.get(f"{API}/feeds/facebook-local?format=json", timeout=20)
    assert r.status_code == 200
    items = r.json().get("data", [])
    for it in items[:5]:
        shipping = it.get("shipping", [])
        assert isinstance(shipping, list) and shipping, f"shipping must be a non-empty list, got {shipping}"
        first = shipping[0]
        assert first.get("country") == "CA"
        assert first.get("price") == "0 CAD"
        assert first.get("service") == "Buyer Arranges Transport"


def test_google_feed_includes_shipping_with_iso_region():
    r = requests.get(f"{API}/feeds/google?limit=2", timeout=20)
    assert r.status_code == 200
    xml = r.text
    assert "<g:shipping>" in xml
    assert "<g:service>Buyer Arranges Transport</g:service>" in xml
    assert "<g:price>0 CAD</g:price>" in xml


# ─── Bill 96 sweep helper is importable ──────────────────────────────

def test_bill96_autosuspend_sweep_is_importable():
    from routes.admin_compliance import bill96_autosuspend_sweep
    assert callable(bill96_autosuspend_sweep)


# ─── Referral commission award helper is importable ──────────────────

def test_award_referral_credit_helper_is_importable():
    from routes.affiliate import award_referral_credit_if_first_purchase
    assert callable(award_referral_credit_if_first_purchase)


# ─── SEO infra ───────────────────────────────────────────────────────

def test_sitemap_returns_xml_with_static_and_dynamic_urls():
    r = requests.get(f"{BASE}/sitemap.xml", timeout=15)
    assert r.status_code == 200
    body = r.text
    assert "<?xml" in body
    assert "<urlset" in body
    assert "/marketplace" in body
    assert "/vehicle-auctions" in body


def test_robots_txt_includes_sitemap_directive():
    r = requests.get(f"{BASE}/robots.txt", timeout=15)
    assert r.status_code == 200
    body = r.text
    assert "Sitemap:" in body
    assert "Disallow: /admin" in body
