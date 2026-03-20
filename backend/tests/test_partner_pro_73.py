"""
Test Partner Pro Features - Iteration 73
Tests: subscription-plans (4 tiers), Partner Pro endpoints with permission checks,
       public storefront endpoint, CSV template download
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dashboard-localize.preview.emergentagent.com')


class TestSubscriptionPlans:
    """Test subscription plans endpoint returns 4 tiers including partner_pro"""

    def test_subscription_plans_returns_4_plans(self):
        """GET /api/subscription-plans should return 4 plans"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        plans = data.get("plans", [])
        assert len(plans) == 4
        plan_ids = [p["plan_id"] for p in plans]
        assert "free" in plan_ids
        assert "premium" in plan_ids
        assert "partner_pro" in plan_ids
        assert "vip" in plan_ids
        print("PASS: Subscription plans returns 4 tiers")

    def test_partner_pro_pricing(self):
        """Partner Pro plan shows $240/yr with original $480/yr"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        data = response.json()
        plans = data.get("plans", [])
        partner_pro = next((p for p in plans if p["plan_id"] == "partner_pro"), None)
        assert partner_pro is not None
        assert partner_pro["price_yearly"] == 240.0
        assert partner_pro["original_price_yearly"] == 480.0
        print("PASS: Partner Pro pricing is correct ($240/yr, original $480/yr)")


class TestCSVTemplate:
    """Test CSV template download endpoint"""

    def test_csv_template_download(self):
        """GET /api/partner-pro/bulk-import/template returns CSV file"""
        response = requests.get(f"{BASE_URL}/api/partner-pro/bulk-import/template")
        assert response.status_code == 200
        # Check content type is CSV
        assert "text/csv" in response.headers.get("content-type", "")
        # Check content has CSV headers
        content = response.text
        assert "title" in content.lower()
        assert "starting_price" in content.lower()
        assert "category" in content.lower()
        print("PASS: CSV template download works (200)")


class TestPartnerProPermissions:
    """Test Partner Pro endpoints require partner_pro or vip subscription"""

    @pytest.fixture
    def admin_token(self):
        """Login as admin (has premium tier, NOT partner_pro)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token")

    def test_bulk_import_requires_partner_pro(self, admin_token):
        """POST /api/partner-pro/bulk-import returns 403 for non-partner_pro"""
        response = requests.post(
            f"{BASE_URL}/api/partner-pro/bulk-import",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("test.csv", b"title,starting_price,category\n", "text/csv")}
        )
        assert response.status_code == 403
        assert "Partner Pro or VIP" in response.json().get("detail", "")
        print("PASS: Bulk import returns 403 for non-partner_pro user")

    def test_analytics_export_requires_partner_pro(self, admin_token):
        """GET /api/partner-pro/analytics/export returns 403 for non-partner_pro"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/analytics/export",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403
        assert "Partner Pro or VIP" in response.json().get("detail", "")
        print("PASS: Analytics export returns 403 for non-partner_pro user")

    def test_featured_listings_requires_partner_pro(self, admin_token):
        """GET /api/partner-pro/featured-listings returns 403 for non-partner_pro"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/featured-listings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403
        assert "Partner Pro or VIP" in response.json().get("detail", "")
        print("PASS: Featured listings returns 403 for non-partner_pro user")

    def test_early_access_requires_partner_pro(self, admin_token):
        """GET /api/partner-pro/early-access returns 403 for non-partner_pro"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/early-access",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403
        assert "Partner Pro or VIP" in response.json().get("detail", "")
        print("PASS: Early access returns 403 for non-partner_pro user")

    def test_storefront_update_requires_partner_pro(self, admin_token):
        """PUT /api/partner-pro/storefront returns 403 for non-partner_pro"""
        response = requests.put(
            f"{BASE_URL}/api/partner-pro/storefront",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tagline": "Test tagline"}
        )
        assert response.status_code == 403
        assert "Partner Pro or VIP" in response.json().get("detail", "")
        print("PASS: Storefront update returns 403 for non-partner_pro user")


class TestPublicStorefront:
    """Test public storefront endpoint"""

    def test_storefront_public_access(self):
        """GET /api/storefronts/{user_id} returns storefront data (public)"""
        # Use admin user ID
        user_id = "8940074d-da97-43ca-9a0b-c59d39411ed6"
        response = requests.get(f"{BASE_URL}/api/storefronts/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "seller" in data
        assert "storefront" in data
        assert "listings" in data
        assert data["seller"]["id"] == user_id
        print("PASS: Public storefront endpoint works")

    def test_storefront_404_for_invalid_user(self):
        """GET /api/storefronts/{invalid_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/storefronts/invalid-user-id-12345")
        assert response.status_code == 404
        print("PASS: Storefront returns 404 for invalid user")


class TestHealthCheck:
    """Smoke test - health endpoint"""

    def test_health(self):
        """GET /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json().get("status") == "healthy"
        print("PASS: Health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
