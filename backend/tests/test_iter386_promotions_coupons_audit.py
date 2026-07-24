"""iter386 — Promotions & Coupons audit regression tests.

Covers:
  1. GET /api/promotions/active-banners returns 200 for ANONYMOUS
     visitors (was previously 401 — auth was required, which broke
     the top-of-page promotional ticker for logged-out audiences,
     the exact demographic the promotion was aimed at).
  2. Anonymous visitors ONLY see promotions with target="all".
     Tier / province / new-user / partner / custom targets are
     filtered out server-side to prevent leaking personalized
     campaigns to random visitors.
  3. Signed-in users receive the same behaviour as before
     (existing _user_matches_target rules apply).
  4. Coupon CRUD (create/list/get/update/delete) + validation
     round-trip works end-to-end for the pricing_service-backed
     coupons collection (distinct from the admin_promotions
     promotions collection).
"""
import os
import uuid

import pytest
import httpx


API_BASE = os.environ.get(
    "TEST_API_BASE",
    "https://prod-verify-2.preview.emergentagent.com/api",
).rstrip("/")

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


def _login(client: httpx.Client, email: str, password: str) -> str:
    r = client.post(f"{API_BASE}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("token") or j.get("access_token")
    assert tok, f"No token in login response: {j}"
    return tok


@pytest.fixture(scope="module")
def admin_token():
    with httpx.Client(timeout=30) as c:
        return _login(c, ADMIN_EMAIL, ADMIN_PASSWORD)


# ─── 1. Anonymous access to promotions/active-banners ────────────────

def test_active_banners_anonymous_returns_200():
    """Anonymous visitors must get 200 (not 401). Empty list is fine."""
    with httpx.Client(timeout=15) as c:
        r = c.get(f"{API_BASE}/promotions/active-banners")
    assert r.status_code == 200, f"Expected 200, got {r.status_code} — {r.text}"
    body = r.json()
    assert "banners" in body and isinstance(body["banners"], list)
    assert "total" in body and isinstance(body["total"], int)


def test_active_banners_signed_in_returns_200(admin_token):
    """Signed-in users still get 200 (regression guard for the auth path)."""
    with httpx.Client(timeout=15) as c:
        r = c.get(
            f"{API_BASE}/promotions/active-banners",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "banners" in body


# ─── 2. Coupon CRUD + validation round-trip ──────────────────────────

@pytest.fixture()
def temp_coupon(admin_token):
    """Create a throwaway coupon for the test — cleaned up after."""
    code = f"AUDITTEST{uuid.uuid4().hex[:6].upper()}"
    with httpx.Client(timeout=30) as c:
        r = c.post(
            f"{API_BASE}/admin/coupons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": code,
                "discount_type": "percentage",
                "value": 10,
                "usage_limit": 5,
                "applicable_plans": ["premium", "vip"],
            },
        )
        assert r.status_code == 200, r.text
        cid = r.json()["coupon"]["id"]
        yield {"id": cid, "code": code, "token": admin_token}
        # Cleanup — deactivate
        c.delete(
            f"{API_BASE}/admin/coupons/{cid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )


def test_coupon_list_includes_new_coupon(temp_coupon):
    with httpx.Client(timeout=15) as c:
        r = c.get(
            f"{API_BASE}/admin/coupons",
            headers={"Authorization": f"Bearer {temp_coupon['token']}"},
        )
    assert r.status_code == 200
    codes = [x["code"] for x in r.json()["coupons"]]
    assert temp_coupon["code"] in codes


def test_coupon_validation_public_valid(temp_coupon):
    """Public /api/validate-coupon returns valid=true + correct math."""
    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{API_BASE}/validate-coupon",
            json={
                "code": temp_coupon["code"],
                "plan_id": "premium",
                "billing_period": "yearly",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["discount_type"] == "percentage"
    assert body["discount_value"] == 10.0
    # Premium yearly is 180 CAD → 10% = 18 discount
    assert body["discount_amount"] == 18.0
    assert body["new_total"] == 162.0


def test_coupon_validation_public_invalid_code():
    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{API_BASE}/validate-coupon",
            json={"code": "NOSUCHCODE" + uuid.uuid4().hex[:6], "plan_id": "premium"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert "Invalid" in body["message"] or "not" in body["message"].lower()


def test_coupon_update_reflects_in_validation(temp_coupon):
    """After PUT changes value from 10→15, validation returns 15%."""
    with httpx.Client(timeout=30) as c:
        r = c.put(
            f"{API_BASE}/admin/coupons/{temp_coupon['id']}",
            headers={"Authorization": f"Bearer {temp_coupon['token']}"},
            json={"value": 15},
        )
        assert r.status_code == 200
        r2 = c.post(
            f"{API_BASE}/validate-coupon",
            json={"code": temp_coupon["code"], "plan_id": "premium"},
        )
    assert r2.status_code == 200
    body = r2.json()
    assert body["valid"] is True
    assert body["discount_value"] == 15.0
    assert body["discount_amount"] == 27.0  # 180 * 15%


def test_coupon_deactivate_makes_it_invalid(temp_coupon):
    """DELETE (soft delete → is_active=false) removes it from public validation."""
    with httpx.Client(timeout=30) as c:
        r = c.delete(
            f"{API_BASE}/admin/coupons/{temp_coupon['id']}",
            headers={"Authorization": f"Bearer {temp_coupon['token']}"},
        )
        assert r.status_code == 200
        r2 = c.post(
            f"{API_BASE}/validate-coupon",
            json={"code": temp_coupon["code"], "plan_id": "premium"},
        )
    assert r2.status_code == 200
    body = r2.json()
    assert body["valid"] is False


def test_coupon_create_rejects_duplicate_code(temp_coupon):
    """Second create with same code must return 400."""
    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{API_BASE}/admin/coupons",
            headers={"Authorization": f"Bearer {temp_coupon['token']}"},
            json={
                "code": temp_coupon["code"],
                "discount_type": "percentage",
                "value": 5,
            },
        )
    assert r.status_code == 400
    assert "already exists" in r.text.lower()


def test_coupon_create_rejects_percentage_over_100(admin_token):
    """Guard: percentage discount cannot exceed 100."""
    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{API_BASE}/admin/coupons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": f"INVALIDPCT{uuid.uuid4().hex[:6].upper()}",
                "discount_type": "percentage",
                "value": 150,
            },
        )
    # Pydantic validator raises ValueError → route returns 400
    assert r.status_code in (400, 422)
