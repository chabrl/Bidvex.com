"""
iter184 P0 regression tests — GET /api/payments/status/{session_id}

Verifies the fix for iter183 critical bug where get_checkout_status()
referenced an undefined `db` (NameError silently swallowed). The fix
introduces `_db = get_db()` inside the try-block + an Optional auth +
a PII gate (buyer / seller / admin only see seller_contact).

Tests:
  HTTP-1: invalid session  → 400 (NOT 500 — proves no NameError crash)
  HTTP-2: anonymous + invalid → still 400 (no auth required)
  HTTP-3: random session that doesn't exist → 400 from Stripe
  FN-1:   anonymous on paid session → no seller_contact (PII gate)
  FN-2:   buyer  → seller_contact returned
  FN-3:   seller → seller_contact returned
  FN-4:   admin  → seller_contact returned
  FN-5:   stranger → no seller_contact
  FN-6:   paid session, no txn row → no crash, no seller_contact
  FN-7:   paid session, txn but no seller user → no crash, no seller_contact
"""

import os
import sys
import asyncio
import uuid
import pytest
import pytest_asyncio
import requests
from unittest.mock import patch, MagicMock
from dotenv import dotenv_values

# Ensure backend modules are importable
sys.path.insert(0, "/app/backend")

# Load env from backend/.env (NOT shell/test env which may have stale stripe key)
_cfg = dotenv_values("/app/backend/.env")
for k, v in _cfg.items():
    os.environ.setdefault(k, v) if v else None

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or \
           dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = BASE_URL.rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS  = "Anderosli123!@#"
BUYER_EMAIL = "p0bugtest@example.com"
BUYER_PASS  = "TestBuyer123!"


# ---------- HTTP fixtures ----------
@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(http, email, password):
    r = http.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        return None
    return r.json().get("access_token") or r.json().get("token")


# =========================================================
# HTTP regression — function must not crash with NameError
# =========================================================
class TestHTTPNoCrash:
    def test_invalid_session_returns_400_not_500(self, http):
        """PRIMARY iter184 regression: pre-fix this 500'd with NameError 'db'."""
        r = http.get(f"{BASE_URL}/api/payments/status/cs_invalid_xyz_123", timeout=15)
        assert r.status_code != 500, f"Got 500 (likely NameError regression): {r.text[:300]}"
        assert r.status_code == 400, f"Expected 400 from Stripe rejecting bad session, got {r.status_code}: {r.text[:200]}"

    def test_invalid_session_anonymous_no_500(self, http):
        """No Authorization header — function must still not crash."""
        bare = requests.Session()
        r = bare.get(f"{BASE_URL}/api/payments/status/totally_fake_session", timeout=15)
        assert r.status_code != 500, f"Anonymous call crashed: {r.text[:300]}"
        assert r.status_code == 400

    def test_invalid_session_with_bad_token_no_500(self, http):
        """Optional auth path: bad token should fall back to anonymous, not crash."""
        h = requests.Session()
        h.headers.update({"Authorization": "Bearer not_a_real_token", "Content-Type": "application/json"})
        r = h.get(f"{BASE_URL}/api/payments/status/another_bogus_session", timeout=15)
        assert r.status_code != 500
        assert r.status_code == 400

    def test_admin_login_works(self, http):
        """Sanity — credentials still valid (used by next-gen tests if they expand)."""
        tok = _login(http, ADMIN_EMAIL, ADMIN_PASS)
        assert tok, "Admin login failed — check /app/memory/test_credentials.md"

    def test_buyer_login_works(self, http):
        tok = _login(http, BUYER_EMAIL, BUYER_PASS)
        assert tok, "Buyer login failed — check /app/memory/test_credentials.md"


# =========================================================
# Function-level — mocked Stripe + seeded txn row
# Verifies the PII matrix end-to-end (buyer/seller/admin/stranger/anon).
# =========================================================
class _U:
    """Lightweight current_user mock."""
    def __init__(self, uid, role="user", email="x@y.z"):
        self.id = uid
        self.role = role
        self.email = email


def _mock_paid_session():
    sess = MagicMock()
    sess.status = "complete"
    sess.payment_status = "paid"
    sess.customer = "cus_x"
    sess.subscription = None
    sess.amount_total = 12345
    return sess


@pytest_asyncio.fixture
async def seeded_db():
    """Seed a payment_transactions row + seller user, yield identifiers, cleanup."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from routes import payments_shared
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    payments_shared.set_payments_db(db)  # wire DI for this loop

    sid     = f"TEST_sess_{uuid.uuid4().hex[:12]}"
    buyer   = f"TEST_buyer_{uuid.uuid4().hex[:8]}"
    seller  = f"TEST_seller_{uuid.uuid4().hex[:8]}"
    listing = f"TEST_listing_{uuid.uuid4().hex[:8]}"

    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": sid,
        "user_id": buyer,
        "seller_id": seller,
        "listing_id": listing,
        "payment_status": "paid",
    })
    await db.users.insert_one({
        "id": seller,
        "email": "TEST_seller@example.com",
        "name": "Test Seller",
        "phone": "+15145550199",
    })

    yield {"sid": sid, "buyer": buyer, "seller": seller, "listing": listing, "db": db}

    # cleanup
    await db.payment_transactions.delete_many({"session_id": sid})
    await db.users.delete_many({"id": seller})
    cli.close()


def _ensure_payments_db():
    """payments_shared.set_payments_db is normally called by server startup;
    in this test process we wire it directly. Each test that uses this without
    seeded_db must create its own client tied to the running event loop."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from routes import payments_shared
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    payments_shared.set_payments_db(cli[os.environ["DB_NAME"]])
    return cli


@pytest.mark.asyncio
class TestPIIMatrix:
    async def test_anonymous_no_seller_contact(self, seeded_db):
        # seeded_db fixture already wired payments_shared
        from routes.payments import get_checkout_status
        with patch("stripe.checkout.Session.retrieve", return_value=_mock_paid_session()):
            out = await get_checkout_status(seeded_db["sid"], credentials=None)
        assert out["payment_status"] == "paid"
        assert "seller_contact" not in out, "PII leaked to anonymous caller!"
        # listing_id is best-effort; surface it for the success page UI even when no PII.
        assert out.get("listing_id") == seeded_db["listing"]

    async def test_buyer_gets_seller_contact(self, seeded_db):
        # seeded_db fixture already wired payments_shared
        from routes.payments import get_checkout_status
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
        buyer_user = _U(seeded_db["buyer"], role="user")
        with patch("stripe.checkout.Session.retrieve", return_value=_mock_paid_session()), \
             patch("routes.payments._auth", return_value=buyer_user):
            out = await get_checkout_status(seeded_db["sid"], credentials=creds)
        assert "seller_contact" in out, f"Buyer denied PII: {out}"
        assert out["seller_contact"]["email"] == "TEST_seller@example.com"
        assert out["seller_contact"]["phone"] == "+15145550199"
        assert out["seller_contact"]["name"]  == "Test Seller"

    async def test_seller_gets_seller_contact(self, seeded_db):
        # seeded_db fixture already wired payments_shared
        from routes.payments import get_checkout_status
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
        seller_user = _U(seeded_db["seller"], role="user")
        with patch("stripe.checkout.Session.retrieve", return_value=_mock_paid_session()), \
             patch("routes.payments._auth", return_value=seller_user):
            out = await get_checkout_status(seeded_db["sid"], credentials=creds)
        assert "seller_contact" in out

    async def test_admin_gets_seller_contact(self, seeded_db):
        # seeded_db fixture already wired payments_shared
        from routes.payments import get_checkout_status
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
        admin_user = _U("some_admin_id", role="admin")
        with patch("stripe.checkout.Session.retrieve", return_value=_mock_paid_session()), \
             patch("routes.payments._auth", return_value=admin_user):
            out = await get_checkout_status(seeded_db["sid"], credentials=creds)
        assert "seller_contact" in out

    async def test_stranger_blocked(self, seeded_db):
        # seeded_db fixture already wired payments_shared
        from routes.payments import get_checkout_status
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
        stranger = _U("totally_unrelated_user", role="user")
        with patch("stripe.checkout.Session.retrieve", return_value=_mock_paid_session()), \
             patch("routes.payments._auth", return_value=stranger):
            out = await get_checkout_status(seeded_db["sid"], credentials=creds)
        assert "seller_contact" not in out, "PII leaked to unauthorized stranger!"
        assert out["payment_status"] == "paid"

    async def test_paid_session_no_txn_row_no_crash(self):
        """Best-effort enrichment: no matching txn → returns status fields, no crash."""
        cli = _ensure_payments_db()
        try:
            from routes.payments import get_checkout_status
            with patch("stripe.checkout.Session.retrieve", return_value=_mock_paid_session()):
                out = await get_checkout_status("TEST_orphan_session_xyz", credentials=None)
            assert out["payment_status"] == "paid"
            assert "seller_contact" not in out
            assert "listing_id" not in out
        finally:
            cli.close()

    async def test_paid_session_txn_but_seller_missing(self):
        """Txn row exists but no users record for seller_id → no crash, no PII."""
        cli = _ensure_payments_db()
        db = cli[os.environ["DB_NAME"]]
        sid = f"TEST_sess_orphan_{uuid.uuid4().hex[:8]}"
        seller_id = f"TEST_ghost_seller_{uuid.uuid4().hex[:8]}"
        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": sid,
            "user_id": "buyer_x",
            "seller_id": seller_id,
            "listing_id": "listing_x",
            "payment_status": "paid",
        })
        try:
            from routes.payments import get_checkout_status
            from fastapi.security import HTTPAuthorizationCredentials
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
            buyer_user = _U("buyer_x", role="user")
            with patch("stripe.checkout.Session.retrieve", return_value=_mock_paid_session()), \
                 patch("routes.payments._auth", return_value=buyer_user):
                out = await get_checkout_status(sid, credentials=creds)
            assert out["payment_status"] == "paid"
            assert "seller_contact" not in out  # seller user doesn't exist
            assert out.get("listing_id") == "listing_x"
        finally:
            await db.payment_transactions.delete_many({"session_id": sid})
            cli.close()
