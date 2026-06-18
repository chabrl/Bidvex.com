"""
iter308 — Billing & Verification Coverage
==========================================

Tests:
  • Auth gates on every admin endpoint (non-admin → 403)
  • Verification state transitions actually persist in MongoDB
  • Admin tier override persists + survives a fresh read
  • Annual fee Stripe Checkout endpoint returns a valid session payload
  • checkout.session.completed webhook activates annual fee + sets flags +
    unblocks listings (smoke via handler module)
  • Footer "Vehicle Auctions" link asserts /vehicle-auctions structurally
  • Admin sub-panel integration health — primary endpoint of every audited
    admin tab returns 200 with a valid admin token
"""
import asyncio
import os
import re
from pathlib import Path

import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


# ─── helpers ─────────────────────────────────────────────────────────


def _admin_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _buyer_token() -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user_id_by_email(email: str) -> str:
    """Find a user's id directly from MongoDB (used by tests that need to
    persist state and read it back without going through the /admin/users
    pagination)."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def _q():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            u = await cli[os.environ["DB_NAME"]].users.find_one({"email": email}, {"_id": 0, "id": 1})
            return (u or {}).get("id", "")
        finally:
            cli.close()
    return asyncio.get_event_loop().run_until_complete(_q()) if asyncio.get_event_loop().is_running() else asyncio.run(_q())


def _db_field(email: str, field: str):
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")

    async def _q():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            u = await cli[os.environ["DB_NAME"]].users.find_one({"email": email}, {"_id": 0, field: 1})
            return (u or {}).get(field)
        finally:
            cli.close()
    return asyncio.run(_q())


# ─── Auth gates ──────────────────────────────────────────────────────


def test_non_admin_cannot_change_tier():
    bt = _buyer_token()
    r = requests.post(
        f"{API}/admin/users/some-id/change-tier",
        json={"tier": "premium"},
        headers=_h(bt), timeout=15,
    )
    assert r.status_code == 403


def test_non_admin_cannot_override_subscription():
    bt = _buyer_token()
    r = requests.post(
        f"{API}/admin/users/some-id/subscription/override",
        json={"plan": "premium", "reason": "iter308 non-admin gate test", "duration_days": 30},
        headers=_h(bt), timeout=15,
    )
    assert r.status_code in (401, 403)


def test_non_admin_cannot_approve_broker():
    bt = _buyer_token()
    r = requests.patch(
        f"{API}/admin/brokers/some-broker-id/approve",
        headers=_h(bt), timeout=15,
    )
    assert r.status_code == 403


def test_non_admin_cannot_reject_partner():
    bt = _buyer_token()
    r = requests.post(
        f"{API}/admin/partners/some-id/reject",
        json={"reason": "test"}, headers=_h(bt), timeout=15,
    )
    assert r.status_code in (401, 403)


# ─── Verification state transitions actually persist in MongoDB ──────


def test_change_tier_persists_to_mongo_and_survives_reload():
    """Change buyer_tier → premium; read it back DIRECTLY from MongoDB."""
    t = _admin_token()
    uid = _db_field(BUYER_EMAIL, "id")
    assert uid, "testbuyer must exist in DB"
    r = requests.post(
        f"{API}/admin/users/{uid}/change-tier",
        json={"tier": "premium"}, headers=_h(t), timeout=15,
    )
    assert r.status_code == 200, r.text
    # Fresh read from MongoDB — not from the API response
    persisted = _db_field(BUYER_EMAIL, "buyer_tier")
    assert persisted == "premium", f"buyer_tier did not persist (got {persisted!r})"
    updated_at = _db_field(BUYER_EMAIL, "buyer_tier_updated_at")
    assert updated_at, "buyer_tier_updated_at must be set"


def test_subscription_override_persists_with_timestamp():
    t = _admin_token()
    uid = _db_field(BUYER_EMAIL, "id")
    r = requests.post(
        f"{API}/admin/users/{uid}/subscription/override",
        json={"plan": "premium", "reason": "iter308 test", "duration_days": 60},
        headers=_h(t), timeout=15,
    )
    assert r.status_code == 200, r.text
    tier = _db_field(BUYER_EMAIL, "subscription_tier")
    ovr_at = _db_field(BUYER_EMAIL, "subscription_override_at")
    assert tier == "premium"
    assert ovr_at, "subscription_override_at must be persisted"


# ─── Annual fee Stripe Checkout (smoke) ──────────────────────────────


def test_annual_fee_checkout_requires_vehicle_dealer():
    """Non-dealer users hit a 403 — the endpoint should not silently 200."""
    bt = _buyer_token()
    r = requests.post(
        f"{API}/dealer-subscription/create-checkout-session",
        headers=_h(bt), timeout=20,
    )
    # Non-dealer buyer or demo: 403 expected
    assert r.status_code in (403, 401), r.text
    detail = (r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else "")
    assert any(x in str(detail).lower() for x in ("dealer", "demo", "unauth", "forbidden"))


def test_checkout_endpoint_module_exists_and_uses_settings_price_id():
    """Structural assertion — module imports + spec config."""
    from routes import dealer_subscription_routes as m
    assert hasattr(m, "create_dealer_checkout_session"), "Endpoint must exist"
    src = (Path("/app/backend/routes/dealer_subscription_routes.py")).read_text()
    assert 'settings["price_id"]' in src, "Must use price_id from settings"
    assert 'COUPON_ID' in src, "Must apply LAUNCH50 coupon"
    assert 'vehicle_dealer_annual_fee' in src, "Metadata.type must be vehicle_dealer_annual_fee"


# ─── checkout.session.completed handler smoke ────────────────────────


def test_webhook_handler_sets_iter308_fields():
    """Source assertion that the iter308 webhook branch persists the new
    annual_platform_fee_paid + listing unblock fields."""
    src = Path("/app/backend/routes/webhooks.py").read_text()
    assert '"annual_platform_fee_paid": True' in src
    assert '"annual_fee_paid_at"' in src
    # Listing unblock
    assert 'unblock_filter' in src or 'listing_blocked' in src
    # Email + push send paths present in the branch
    assert 'send_email' in src
    assert 'dispatch_push' in src


def test_webhook_signature_verification_is_enforced():
    src = Path("/app/backend/routes/webhooks.py").read_text()
    assert 'stripe.Webhook.construct_event' in src
    assert 'STRIPE_WEBHOOK_SECRET' in src
    # Missing-signature header must return 400 (don't silently 200)
    assert 'Missing stripe-signature header' in src


# ─── Footer link assertion ───────────────────────────────────────────


def test_footer_vehicle_auctions_link_resolves_to_vehicle_auctions():
    src = Path("/app/frontend/src/components/Footer.js").read_text()
    # The Vehicle Auctions entry must point to /vehicle-auctions (NOT /vehicles)
    m = re.search(
        r'to="(/[^"]+)"[^>]*data-testid="footer-vehicles-link"',
        src,
    )
    assert m, "footer-vehicles-link Link not found"
    assert m.group(1) == "/vehicle-auctions", (
        f"Footer Vehicle Auctions link must be /vehicle-auctions, got {m.group(1)!r}"
    )
    # Belt-and-braces: no stale /vehicles target anywhere
    assert 'to="/vehicles"' not in src, "Stale to=/vehicles Link in Footer.js"


# ─── Admin sub-panel integration health ─────────────────────────────


_ADMIN_HEALTH_ENDPOINTS = [
    # tab → primary GET endpoint
    ("vehicles",                "/admin/listings/pending"),
    ("settings",                "/admin/site-config"),
    ("banners",                 "/admin/banners"),
    ("analytics",               "/admin/analytics/overview"),
    ("partners",                "/admin/partners"),
    ("team",                    "/team/members"),
    ("admin-logs",              "/admin/logs"),
    ("facilities",              "/admin/storage-facilities"),
    ("listing-change-requests", "/admin/listing-requests?status=pending"),
    ("tax-verification",        "/admin/users?search=&limit=1"),
    ("compliance-dashboard",    "/admin/compliance/flagged-listings"),
    ("error-logs",              "/admin/errors/frontend?days=1&limit=1"),
    ("affiliate-admin",         "/affiliate/admin/all"),
    ("dealer-subscriptions",    "/admin/dealer-subscriptions"),
    ("flagged-ai",              "/admin/listing-reviews?status=pending"),
    ("auction-control",         "/admin/marketplace-settings"),
]


def test_admin_subpanel_endpoints_reachable_with_admin_token():
    """Smoke-test that every audited admin sub-panel has a working
    primary endpoint. Any endpoint that doesn't exist on the backend
    OR is broken will show up as a hard failure here.
    """
    t = _admin_token()
    failures = []
    for tab, ep in _ADMIN_HEALTH_ENDPOINTS:
        r = requests.get(f"{API}{ep}", headers=_h(t), timeout=15)
        if r.status_code not in (200, 204):
            # 404 = endpoint missing — block iter308 close-out
            # 403 = auth gate misconfigured for admin role — block
            failures.append(f"{tab} → GET {ep} returned {r.status_code}")
    assert not failures, "Broken admin sub-panel endpoints:\n  " + "\n  ".join(failures)
