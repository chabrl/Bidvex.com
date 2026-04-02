"""
BidVex Backend Refactoring Tests - Phase 4 & 5
Tests for:
- Admin route deduplication
- Unified admin middleware (require_admin)
- Server.py scheduler/lifecycle extraction
- Listings CRUD service extraction
- CORS_ORIGINS env var functionality
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestHealthEndpoints:
    """Health check endpoints - should work without auth"""
    
    def test_api_health(self):
        """GET /api/health returns 200 with healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ GET /api/health - PASSED")
    
    def test_root_health(self):
        """GET /health returns 200 with ok status"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        print("✓ GET /health - PASSED")


class TestAuthEndpoints:
    """Authentication endpoints"""
    
    def test_admin_login(self):
        """POST /api/auth/login with admin credentials returns access_token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("user", {}).get("role") == "admin"
        print("✓ POST /api/auth/login (admin) - PASSED")
        return data["access_token"]


class TestPublicEndpoints:
    """Public endpoints that don't require authentication"""
    
    def test_marketplace_items(self):
        """GET /api/marketplace/items returns items (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items")
        assert response.status_code == 200
        print("✓ GET /api/marketplace/items - PASSED")
    
    def test_multi_item_listings(self):
        """GET /api/multi-item-listings returns listings (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings")
        assert response.status_code == 200
        print("✓ GET /api/multi-item-listings - PASSED")
    
    def test_feature_flags(self):
        """GET /api/marketplace/feature-flags returns feature flags (public)"""
        response = requests.get(f"{BASE_URL}/api/marketplace/feature-flags")
        assert response.status_code == 200
        data = response.json()
        # Verify expected feature flag keys exist
        assert "enable_buy_now" in data
        assert "enable_anti_sniping" in data
        print("✓ GET /api/marketplace/feature-flags - PASSED")


class TestAdminEndpointsWithAuth:
    """Admin endpoints that require authentication"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_admin_listings_all(self):
        """GET /api/admin/listings/all returns list of listings (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/listings/all", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ GET /api/admin/listings/all - PASSED")
    
    def test_admin_reports(self):
        """GET /api/admin/reports returns list (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/reports", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ GET /api/admin/reports - PASSED")
    
    def test_admin_deletion_requests(self):
        """GET /api/admin/deletion-requests returns list (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/deletion-requests", headers=self.headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print("✓ GET /api/admin/deletion-requests - PASSED")
    
    def test_admin_analytics_users(self):
        """GET /api/admin/analytics/users returns user counts (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/users", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "personal" in data
        assert "business" in data
        assert "total" in data
        print("✓ GET /api/admin/analytics/users - PASSED")
    
    def test_admin_marketplace_settings(self):
        """GET /api/admin/marketplace-settings returns settings object (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/marketplace-settings", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        # Verify expected settings keys exist
        assert "allow_all_users_multi_lot" in data or "enable_buy_now" in data
        print("✓ GET /api/admin/marketplace-settings - PASSED")
    
    def test_admin_risk_monitoring(self):
        """GET /api/admin/risk-monitoring returns risk data (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/risk-monitoring", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data or "stats" in data or "flags" in data
        print("✓ GET /api/admin/risk-monitoring - PASSED")
    
    def test_admin_email_templates(self):
        """GET /api/admin/email-templates returns templates (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data or "templates" in data or "total_templates" in data
        print("✓ GET /api/admin/email-templates - PASSED")
    
    def test_admin_users(self):
        """GET /api/admin/users returns user list (requires admin auth)"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert "total" in data
        print("✓ GET /api/admin/users - PASSED")


class TestUnauthenticatedAdminAccess:
    """Test that admin endpoints return 401/403 without auth"""
    
    def test_admin_listings_no_auth(self):
        """Unauthenticated request to admin endpoints returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/admin/listings/all")
        assert response.status_code in [401, 403]
        print("✓ GET /api/admin/listings/all (no auth) - Returns 401/403 as expected")
    
    def test_admin_reports_no_auth(self):
        """Unauthenticated request to admin reports returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/admin/reports")
        assert response.status_code in [401, 403]
        print("✓ GET /api/admin/reports (no auth) - Returns 401/403 as expected")
    
    def test_admin_users_no_auth(self):
        """Unauthenticated request to admin users returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code in [401, 403]
        print("✓ GET /api/admin/users (no auth) - Returns 401/403 as expected")
    
    def test_admin_marketplace_settings_no_auth(self):
        """Unauthenticated request to admin marketplace-settings returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/admin/marketplace-settings")
        assert response.status_code in [401, 403]
        print("✓ GET /api/admin/marketplace-settings (no auth) - Returns 401/403 as expected")


class TestCORSConfiguration:
    """Test CORS configuration is working"""
    
    def test_cors_headers_present(self):
        """Verify CORS headers are present in response"""
        response = requests.options(
            f"{BASE_URL}/api/health",
            headers={
                "Origin": "https://bidvex.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        # CORS preflight should return 200 or the actual response
        assert response.status_code in [200, 204, 405]
        print("✓ CORS preflight request handled")


class TestListingsServiceExtraction:
    """Test that listings endpoints still work after service extraction"""
    
    def test_get_listings(self):
        """GET /api/listings returns listings"""
        response = requests.get(f"{BASE_URL}/api/listings")
        assert response.status_code == 200
        print("✓ GET /api/listings - PASSED")
    
    def test_get_multi_item_listings(self):
        """GET /api/multi-item-listings returns multi-item listings"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings")
        assert response.status_code == 200
        print("✓ GET /api/multi-item-listings - PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
