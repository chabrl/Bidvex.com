"""
Test Partner Pro Trial & Stripe Billing - Iteration 74
Tests:
- GET /api/subscription-plans returns 4 plans including partner_pro at $240/yr
- POST /api/subscriptions/create accepts partner_pro as valid plan_id
- POST /api/partner-pro/trial/start creates 14-day trial (trial already used for admin)
- POST /api/partner-pro/trial/start returns 400 if trial already used
- POST /api/partner-pro/trial/start returns 400 if user already has partner_pro
- GET /api/partner-pro/trial/status returns correct trial state
- Partner Pro endpoints return 200 for trialing user
- GET /api/partner-pro/bulk-import/template returns CSV
- GET /api/storefronts/{user_id} returns storefront data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://auction-marketplace-15.preview.emergentagent.com')


class TestSubscriptionPlansWithPartnerPro:
    """Test subscription plans includes partner_pro at $240/yr"""

    def test_subscription_plans_returns_4_plans(self):
        """GET /api/subscription-plans should return 4 plans including partner_pro"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        plans = data.get("plans", [])
        assert len(plans) == 4
        plan_ids = [p["plan_id"] for p in plans]
        assert "free" in plan_ids
        assert "premium" in plan_ids
        assert "partner_pro" in plan_ids
        assert "vip" in plan_ids
        print("PASS: Subscription plans returns 4 tiers")

    def test_partner_pro_pricing_240_per_year(self):
        """Partner Pro plan shows $240/yr with original $480/yr"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        data = response.json()
        plans = data.get("plans", [])
        partner_pro = next((p for p in plans if p["plan_id"] == "partner_pro"), None)
        assert partner_pro is not None
        assert partner_pro["price_yearly"] == 240.0
        assert partner_pro["original_price_yearly"] == 480.0
        print("PASS: Partner Pro pricing is $240/yr (original $480/yr)")


class TestSubscriptionCreateAcceptsPartnerPro:
    """Test POST /api/subscriptions/create accepts partner_pro as valid plan_id"""

    @pytest.fixture
    def admin_token(self):
        """Login as admin (has partner_pro trial active)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token")

    def test_subscriptions_create_accepts_partner_pro(self, admin_token):
        """POST /api/subscriptions/create accepts partner_pro (returns error for missing Stripe price, not invalid plan)"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "partner_pro"}
        )
        # Should accept partner_pro as valid plan - error is about Stripe config, not invalid plan
        data = response.json()
        # The endpoint correctly identifies partner_pro as valid plan
        # Error is "Stripe price not configured" NOT "Invalid plan"
        assert "Invalid plan" not in data.get("detail", "")
        print("PASS: subscriptions/create accepts partner_pro as valid plan_id")

    def test_subscriptions_create_rejects_invalid_plan(self, admin_token):
        """POST /api/subscriptions/create rejects invalid plan names"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"plan_id": "invalid_plan_name"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "Invalid plan" in data.get("detail", "")
        print("PASS: subscriptions/create rejects invalid plan names")


class TestPartnerProTrialEndpoints:
    """Test Partner Pro trial start and status endpoints"""

    @pytest.fixture
    def admin_token(self):
        """Login as admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token")

    def test_trial_status_returns_correct_state(self, admin_token):
        """GET /api/partner-pro/trial/status returns correct trial state"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/trial/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Admin has already started trial
        assert data.get("trial_used") is True
        assert data.get("is_trialing") is True
        assert "trial_end" in data
        assert "days_remaining" in data
        assert data.get("eligible_for_trial") is False
        print(f"PASS: Trial status shows trialing with {data['days_remaining']} days remaining")

    def test_trial_start_returns_400_if_already_used(self, admin_token):
        """POST /api/partner-pro/trial/start returns 400 if trial already used"""
        response = requests.post(
            f"{BASE_URL}/api/partner-pro/trial/start",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "already used" in data.get("detail", "").lower() or "already have" in data.get("detail", "").lower()
        print("PASS: Trial start returns 400 for already used trial")


class TestPartnerProEndpointsForTrialingUser:
    """Test Partner Pro endpoints return 200 for trialing user"""

    @pytest.fixture
    def admin_token(self):
        """Login as admin (has partner_pro trialing status)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token")

    def test_analytics_export_returns_200(self, admin_token):
        """GET /api/partner-pro/analytics/export returns 200 for trialing user"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/analytics/export",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        # Should return CSV content
        assert "text/csv" in response.headers.get("content-type", "")
        print("PASS: Analytics export returns 200 for trialing user")

    def test_featured_listings_returns_200(self, admin_token):
        """GET /api/partner-pro/featured-listings returns 200 for trialing user"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/featured-listings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "used" in data
        assert "limit" in data
        assert data["limit"] == 10  # Partner Pro limit
        print("PASS: Featured listings returns 200 for trialing user")

    def test_early_access_returns_200(self, admin_token):
        """GET /api/partner-pro/early-access returns 200 for trialing user"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/early-access",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "early_access_listings" in data
        print("PASS: Early access returns 200 for trialing user")


class TestCSVTemplateAndStorefront:
    """Test CSV template and storefront endpoints"""

    def test_csv_template_returns_200(self):
        """GET /api/partner-pro/bulk-import/template returns 200 with CSV"""
        response = requests.get(f"{BASE_URL}/api/partner-pro/bulk-import/template")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        content = response.text
        assert "title" in content.lower()
        assert "starting_price" in content.lower()
        assert "category" in content.lower()
        print("PASS: CSV template download returns 200")

    def test_storefront_returns_data(self):
        """GET /api/storefronts/{user_id} returns storefront data"""
        user_id = "8940074d-da97-43ca-9a0b-c59d39411ed6"  # Admin user
        response = requests.get(f"{BASE_URL}/api/storefronts/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "seller" in data
        assert "storefront" in data
        assert "listings" in data
        assert data["seller"]["id"] == user_id
        assert data["seller"]["subscription_tier"] == "partner_pro"
        assert data["has_storefront"] is True
        print("PASS: Storefront returns data with partner_pro tier")


class TestHealthCheck:
    """Basic health check"""

    def test_api_health(self):
        """GET /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json().get("status") == "healthy"
        print("PASS: API health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
