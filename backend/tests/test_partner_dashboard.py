"""
Test Partner Dashboard API Endpoints (Iteration 54)

Tests for:
1. GET /api/partner/dashboard - Partner dashboard data
2. POST /api/partner/manage-billing - Stripe billing portal
3. Regression tests for marketplace and admin endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPartnerDashboardAuth:
    """Authentication and access control tests for partner endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    
    def test_partner_dashboard_requires_auth(self):
        """GET /api/partner/dashboard returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/partner/dashboard")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Partner dashboard correctly requires authentication")
    
    def test_partner_dashboard_rejects_non_partner(self, admin_token):
        """GET /api/partner/dashboard returns 400 for non-partner users"""
        response = requests.get(
            f"{BASE_URL}/api/partner/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "partner" in data["detail"].lower()
        print(f"✅ Partner dashboard correctly rejects non-partner: {data['detail']}")
    
    def test_manage_billing_requires_auth(self):
        """POST /api/partner/manage-billing returns 401 without auth"""
        response = requests.post(f"{BASE_URL}/api/partner/manage-billing")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Manage billing correctly requires authentication")
    
    def test_manage_billing_rejects_non_partner(self, admin_token):
        """POST /api/partner/manage-billing returns 400 for non-partner users"""
        response = requests.post(
            f"{BASE_URL}/api/partner/manage-billing",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "partner" in data["detail"].lower()
        print(f"✅ Manage billing correctly rejects non-partner: {data['detail']}")


class TestRegressionEndpoints:
    """Regression tests for previously working endpoints after refactoring"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    
    def test_marketplace_items_still_works(self):
        """GET /api/marketplace/items returns 200 after refactoring"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data, "Response should contain 'items' key"
        assert "total" in data, "Response should contain 'total' key"
        print(f"✅ Marketplace items endpoint working: {data['total']} items found")
    
    def test_admin_partners_still_works(self, admin_token):
        """GET /api/admin/partners returns 200 with admin auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partners",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Response structure: {"applications": [...], "total": int}
        assert "applications" in data, "Response should contain 'applications' key"
        assert "total" in data, "Response should contain 'total' key"
        print(f"✅ Admin partners endpoint working: {data['total']} partners found")
    
    def test_admin_partners_requires_auth(self):
        """GET /api/admin/partners returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/partners")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ Admin partners endpoint correctly requires authentication")
    
    def test_admin_email_settings_still_works(self, admin_token):
        """GET /api/admin/email-settings returns 200 with admin auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Response contains 'configured' key (not 'is_configured')
        assert "configured" in data or "from_email" in data, "Response should contain email settings"
        print(f"✅ Admin email settings endpoint working: configured={data.get('configured')}")
    
    def test_filter_counts_endpoint(self):
        """GET /api/marketplace/filter-counts returns proper structure"""
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should have categories, locations, and possibly auctioneers
        assert "categories" in data or "locations" in data
        print(f"✅ Filter counts endpoint working")
    
    def test_promoted_listings_endpoint(self):
        """GET /api/promoted-listings returns 200"""
        response = requests.get(f"{BASE_URL}/api/promoted-listings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Response structure: {"listings": [...], "total": int}
        assert "listings" in data or isinstance(data, list), "Response should contain listings"
        total = data.get("total", len(data)) if isinstance(data, dict) else len(data)
        print(f"✅ Promoted listings endpoint working: {total} promoted listings")


class TestPartnerDashboardDataStructure:
    """Test the data structure of partner dashboard response"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_partner_dashboard_error_structure(self, admin_token):
        """Verify error response structure when user is not a partner"""
        response = requests.get(
            f"{BASE_URL}/api/partner/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Admin is not a partner, should get 400
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✅ Error structure correct: {data}")
    
    def test_manage_billing_error_without_stripe(self, admin_token):
        """POST /api/partner/manage-billing returns proper error for non-partner"""
        response = requests.post(
            f"{BASE_URL}/api/partner/manage-billing",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✅ Billing error structure correct: {data}")


class TestAPIHealth:
    """Basic health and availability tests"""
    
    def test_auth_endpoint_available(self):
        """POST /api/auth/login is available"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpass"
        })
        # Should be 401 (wrong creds) not 404 or 500
        assert response.status_code in [401, 400], f"Auth endpoint error: {response.status_code}"
        print("✅ Auth endpoint is available")
    
    def test_marketplace_endpoint_available(self):
        """GET /api/marketplace/items is available"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items")
        assert response.status_code == 200, f"Marketplace endpoint error: {response.status_code}"
        print("✅ Marketplace endpoint is available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
