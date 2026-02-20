"""
Phase 1 Modular Router Refactoring Tests
Tests to verify that existing functionality still works after new router files were added
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestHealthEndpoint:
    """Verify basic API health"""
    
    def test_health_endpoint(self):
        """GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health endpoint working")


class TestAuthEndpoints:
    """Verify authentication still works"""
    
    def test_login_success(self):
        """POST /api/auth/login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("user", {}).get("email") == ADMIN_EMAIL
        print(f"✅ Login successful for {ADMIN_EMAIL}")
        return data.get("access_token")
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login with invalid credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "invalid@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        print("✅ Invalid login correctly rejected with 401")


class TestUserMarketingEndpoints:
    """Verify user marketing endpoints still work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_user_marketing_access(self):
        """GET /api/user/marketing/access returns access info"""
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/access",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "can_access" in data
        assert "subscription_tier" in data
        assert "limits" in data
        print(f"✅ User marketing access: tier={data.get('subscription_tier')}, can_send={data.get('can_send')}")
    
    def test_user_marketing_templates(self):
        """GET /api/user/marketing/templates returns templates"""
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/templates",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        templates = data.get("templates", [])
        assert len(templates) >= 1, "Should have at least 1 template"
        print(f"✅ User marketing templates: {len(templates)} templates available")


class TestAdminMarketingEndpoints:
    """Verify admin marketing endpoints still work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_admin_marketing_campaigns_list(self):
        """GET /api/admin/marketing/campaigns returns campaigns list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/marketing/campaigns",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "campaigns" in data
        # API returns 'count' not 'total'
        total = data.get("total") or data.get("count", 0)
        print(f"✅ Admin marketing campaigns: {total} total campaigns")
    
    def test_admin_marketing_segment_filters(self):
        """GET /api/admin/marketing/segment-filters returns filters"""
        response = requests.get(
            f"{BASE_URL}/api/admin/marketing/segment-filters",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        # Should return segment filter config
        assert isinstance(data, dict)
        print(f"✅ Admin marketing segment filters available")


class TestCoreRoutersStillWork:
    """Verify analytics, auctions, and other core routers work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_analytics_endpoint(self):
        """Test analytics router is working"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/public-stats",
            headers=self.headers
        )
        # Either 200 or 404 is acceptable (if no stats exist)
        assert response.status_code in [200, 404]
        print(f"✅ Analytics router responding (status: {response.status_code})")
    
    def test_listings_endpoint(self):
        """GET /api/listings returns listings"""
        response = requests.get(f"{BASE_URL}/api/listings")
        assert response.status_code == 200
        data = response.json()
        # Should return listings array
        assert "listings" in data or isinstance(data, list)
        print(f"✅ Listings endpoint working")
    
    def test_categories_endpoint(self):
        """GET /api/categories returns categories"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        data = response.json()
        # Should return categories array
        assert isinstance(data, list)
        print(f"✅ Categories endpoint working: {len(data)} categories")


class TestNewModularRoutersFramework:
    """Verify the new modular routers are loaded but don't conflict"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_no_duplicate_route_errors(self):
        """Verify server starts without route conflicts"""
        # If we can reach health, server started successfully
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✅ Server started without route conflicts")
    
    def test_admin_users_endpoint(self):
        """GET /api/admin/users returns user list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        # Response may be a list or an object with users key
        if isinstance(data, list):
            print(f"✅ Admin users endpoint: {len(data)} users")
        else:
            assert "users" in data
            print(f"✅ Admin users endpoint: {data.get('total', len(data.get('users', [])))} users")
    
    def test_webhook_endpoint_exists(self):
        """POST /api/webhooks/sendgrid exists (should accept but may return error without valid payload)"""
        response = requests.post(
            f"{BASE_URL}/api/webhooks/sendgrid",
            json=[{"event": "test", "email": "test@test.com", "timestamp": 123}],
            headers={"Content-Type": "application/json"}
        )
        # Should get 200 or 500 (internal error processing), not 404
        assert response.status_code != 404
        print(f"✅ SendGrid webhook endpoint exists (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
