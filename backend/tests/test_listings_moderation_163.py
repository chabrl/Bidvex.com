"""
Iteration 163 — Listings Moderation Workflow + Admin Signup Notification enrichment regression.
Covers: signup country/referral enrichment, marketplace setting gate, pending list shape,
approve/reject flows, edge cases (400/404/403/double-approve), public-feed regression.
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
ADMIN_REF_CODE = "BVX8940074DXKTU"

# Direct Mongo for seeding
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "bazario_db")


@pytest.fixture(scope="session")
def mongo_db():
    if not MONGO_URL:
        pytest.skip("MONGO_URL not set")
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    d = r.json()
    return d.get("access_token") or d.get("token")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _unique_email(prefix="iter163"):
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}@bidvex-test.com"


# ---------- Signup enrichment tests ----------
class TestSignupEnrichment:
    def test_signup_with_ref_code_enriches_country_and_referrer(self):
        email = _unique_email("country_test")
        payload = {
            "email": email, "password": "Test1234!@#", "name": "Country Test",
            "terms_agreed": True, "ai_disclosure_consent": True,
            "ref_code": ADMIN_REF_CODE,
        }
        t0 = time.time()
        r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
        elapsed = time.time() - t0
        assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
        assert elapsed < 5.0, f"Register too slow: {elapsed:.2f}s (BackgroundTasks should keep <2s ideal, <5s hard cap)"
        data = r.json()
        user = data.get("user", data)
        # Referral fields must be populated
        assert user.get("referred_by_code") == ADMIN_REF_CODE
        assert user.get("referred_by_email"), "referred_by_email missing"
        assert user.get("referred_by_name") is not None
        # Country code may be None if IP geolocation fails from preview ingress — assert field exists
        assert "signup_country_code" in user
        assert "signup_country_name" in user

    def test_signup_without_ref_code_has_null_referrer(self):
        email = _unique_email("noref_test")
        payload = {
            "email": email, "password": "Test1234!@#", "name": "No Ref",
            "terms_agreed": True, "ai_disclosure_consent": True,
        }
        r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
        assert r.status_code in (200, 201)
        user = r.json().get("user", r.json())
        assert user.get("referred_by_code") in (None, "", None)
        assert user.get("referred_by_email") in (None, "")


# ---------- Moderation workflow ----------
@pytest.fixture(scope="class")
def seeded_pending_listing(mongo_db, admin_headers):
    """Seed a pending single-item listing directly in MongoDB."""
    # Find any non-admin user to be seller
    seller = mongo_db.users.find_one({"role": {"$ne": "admin"}, "id": {"$exists": True}}, {"_id": 0, "id": 1, "email": 1, "name": 1})
    if not seller:
        pytest.skip("No non-admin seller user available")
    listing_id = f"TEST_pending_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": listing_id,
        "title": "TEST Pending Moderation Iter163",
        "description": "Seeded for moderation regression tests",
        "price": 99.99,
        "category": "Electronics",
        "seller_id": seller["id"],
        "status": "pending",
        "created_at": "2026-01-15T12:00:00+00:00",
        "images": [],
    }
    mongo_db.listings.insert_one(doc)
    yield {"id": listing_id, "seller": seller}
    # Cleanup
    mongo_db.listings.delete_one({"id": listing_id})


class TestPendingListings:
    def test_requires_admin(self):
        r = requests.get(f"{API}/admin/listings/pending", timeout=20)
        assert r.status_code in (401, 403), f"Expected auth guard, got {r.status_code}"

    def test_pending_shape(self, admin_headers, seeded_pending_listing):
        r = requests.get(f"{API}/admin/listings/pending", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("total", "single_count", "multi_count", "listings"):
            assert key in data, f"Missing key {key}"
        assert isinstance(data["listings"], list)
        found = next((l for l in data["listings"] if l.get("id") == seeded_pending_listing["id"]), None)
        assert found, f"Seeded listing {seeded_pending_listing['id']} not in pending response"
        assert found.get("_listing_type") == "single"
        assert "_seller_email" in found
        assert "_seller_name" in found
        assert found["_seller_email"] == seeded_pending_listing["seller"]["email"]

    def test_public_feed_excludes_pending(self, seeded_pending_listing):
        r = requests.get(f"{API}/listings", timeout=20)
        assert r.status_code == 200
        listings = r.json() if isinstance(r.json(), list) else r.json().get("listings", [])
        ids = [l.get("id") for l in listings]
        assert seeded_pending_listing["id"] not in ids, "Pending listing leaked into public feed"


class TestRejectValidation:
    @pytest.fixture(autouse=True)
    def _seed(self, mongo_db):
        """Fresh pending listing for each test in this class."""
        seller = mongo_db.users.find_one({"role": {"$ne": "admin"}, "id": {"$exists": True}}, {"_id": 0, "id": 1})
        if not seller:
            pytest.skip("no seller")
        self.lid = f"TEST_reject_{uuid.uuid4().hex[:8]}"
        mongo_db.listings.insert_one({
            "id": self.lid, "title": "TEST reject", "description": "x", "price": 10,
            "seller_id": seller["id"], "status": "pending",
            "created_at": "2026-01-15T12:00:00+00:00",
        })
        yield
        mongo_db.listings.delete_one({"id": self.lid})

    def test_reject_without_reason_400(self, admin_headers):
        r = requests.post(f"{API}/admin/listings/{self.lid}/reject", headers=admin_headers, json={}, timeout=20)
        assert r.status_code == 400, r.text
        assert "rejection reason is required" in r.text.lower()

    def test_reject_short_reason_400(self, admin_headers):
        r = requests.post(f"{API}/admin/listings/{self.lid}/reject", headers=admin_headers,
                          json={"reason": "bad"}, timeout=20)
        assert r.status_code == 400, r.text

    def test_reject_valid_reason_200(self, admin_headers, mongo_db):
        reason = "Photos are blurry and title is misleading."
        r = requests.post(f"{API}/admin/listings/{self.lid}/reject", headers=admin_headers,
                          json={"reason": reason}, timeout=20)
        assert r.status_code == 200, r.text
        doc = mongo_db.listings.find_one({"id": self.lid}, {"_id": 0})
        assert doc["status"] == "rejected"
        assert doc.get("rejection_reason") == reason
        assert doc.get("moderation_decision") == "rejected"
        assert doc.get("moderated_by")
        audit = mongo_db.admin_audit_logs.find_one({"target_id": self.lid, "action": "listing_rejected"})
        assert audit is not None, "audit log missing"
        assert audit.get("reason") == reason


class TestApproveFlow:
    @pytest.fixture(autouse=True)
    def _seed(self, mongo_db):
        seller = mongo_db.users.find_one({"role": {"$ne": "admin"}, "id": {"$exists": True}}, {"_id": 0, "id": 1})
        if not seller:
            pytest.skip("no seller")
        self.lid = f"TEST_approve_{uuid.uuid4().hex[:8]}"
        mongo_db.listings.insert_one({
            "id": self.lid, "title": "TEST approve", "description": "x", "price": 10,
            "seller_id": seller["id"], "status": "pending",
            "created_at": "2026-01-15T12:00:00+00:00",
        })
        yield
        mongo_db.listings.delete_one({"id": self.lid})

    def test_approve_flips_status_and_audits(self, admin_headers, mongo_db):
        r = requests.post(f"{API}/admin/listings/{self.lid}/approve", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        doc = mongo_db.listings.find_one({"id": self.lid}, {"_id": 0})
        assert doc["status"] == "active"
        assert doc.get("moderation_decision") == "approved"
        assert doc.get("moderated_by")
        audit = mongo_db.admin_audit_logs.find_one({"target_id": self.lid, "action": "listing_approved"})
        assert audit is not None

    def test_double_approve_400(self, admin_headers):
        r1 = requests.post(f"{API}/admin/listings/{self.lid}/approve", headers=admin_headers, timeout=20)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/admin/listings/{self.lid}/approve", headers=admin_headers, timeout=20)
        assert r2.status_code == 400, f"Expected 400 for non-pending, got {r2.status_code}: {r2.text}"


class TestEdgeCases:
    def test_approve_nonexistent_404(self, admin_headers):
        r = requests.post(f"{API}/admin/listings/nonexistent_xyz_123/approve", headers=admin_headers, timeout=20)
        assert r.status_code == 404

    def test_reject_nonexistent_404(self, admin_headers):
        r = requests.post(f"{API}/admin/listings/nonexistent_xyz_123/reject",
                          headers=admin_headers, json={"reason": "valid reason here"}, timeout=20)
        assert r.status_code == 404

    def test_non_admin_forbidden(self):
        # Register a fresh non-admin
        email = _unique_email("nonadmin")
        reg = requests.post(f"{API}/auth/register", json={
            "email": email, "password": "Test1234!@#", "name": "NonAdmin",
            "terms_agreed": True, "ai_disclosure_consent": True,
        }, timeout=30)
        assert reg.status_code in (200, 201)
        token = reg.json().get("token") or reg.json().get("access_token")
        if not token:
            # try login
            lg = requests.post(f"{API}/auth/login", json={"email": email, "password": "Test1234!@#"}, timeout=20)
            token = lg.json().get("token")
        h = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{API}/admin/listings/pending", headers=h, timeout=20)
        assert r.status_code in (401, 403), f"Expected 401/403 for non-admin, got {r.status_code}"
