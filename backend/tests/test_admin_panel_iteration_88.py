"""
Test Admin Panel Endpoints - Iteration 88
Tests all admin panel sections and buyer payment flow
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminAuth:
    """Admin authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        # API returns access_token, not token
        token = data.get("access_token") or data.get("token")
        assert token, f"No token in response: {data.keys()}"
        return token
    
    def test_admin_login(self, admin_token):
        """Test admin can login"""
        assert admin_token is not None
        assert len(admin_token) > 0
        print("✓ Admin login successful")


class TestAdminPanelEndpoints:
    """Test all admin panel endpoints that frontend pages depend on"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        data = response.json()
        token = data.get("access_token") or data.get("token")
        return {"Authorization": f"Bearer {token}"}
    
    # ManageAllAuctions page endpoints
    def test_admin_listings_all(self, admin_headers):
        """ManageAllAuctions: GET /api/admin/listings/all"""
        response = requests.get(f"{BASE_URL}/api/admin/listings/all", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should return array or object with listings key
        assert isinstance(data, (list, dict)), "Response should be list or dict"
        print(f"✓ /api/admin/listings/all - {response.status_code}")
    
    def test_admin_multi_item_listings_all(self, admin_headers):
        """ManageAllAuctions: GET /api/admin/multi-item-listings/all"""
        response = requests.get(f"{BASE_URL}/api/admin/multi-item-listings/all", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/multi-item-listings/all - {response.status_code}")
    
    # AnalyticsDashboard page endpoints
    def test_admin_analytics_revenue(self, admin_headers):
        """AnalyticsDashboard: GET /api/admin/analytics/revenue"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/revenue", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/analytics/revenue - {response.status_code}")
    
    def test_admin_analytics_listings(self, admin_headers):
        """AnalyticsDashboard: GET /api/admin/analytics/listings"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/listings", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should have active/sold/pending counts
        print(f"✓ /api/admin/analytics/listings - {response.status_code} - data: {data}")
    
    # AdminLogs page endpoint
    def test_admin_logs(self, admin_headers):
        """AdminLogs: GET /api/admin/logs"""
        response = requests.get(f"{BASE_URL}/api/admin/logs", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should return array or object with logs key
        assert isinstance(data, (list, dict)), "Response should be list or dict"
        print(f"✓ /api/admin/logs - {response.status_code}")
    
    # MessagingOversight page endpoint
    def test_admin_messages_flagged(self, admin_headers):
        """MessagingOversight: GET /api/admin/messages/flagged"""
        response = requests.get(f"{BASE_URL}/api/admin/messages/flagged", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/messages/flagged - {response.status_code}")
    
    # ReportManager page endpoint
    def test_admin_reports(self, admin_headers):
        """ReportManager: GET /api/admin/reports"""
        response = requests.get(f"{BASE_URL}/api/admin/reports", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/reports - {response.status_code}")
    
    # DeletionRequestsManager page endpoint
    def test_admin_deletion_requests(self, admin_headers):
        """DeletionRequestsManager: GET /api/admin/deletion-requests"""
        response = requests.get(f"{BASE_URL}/api/admin/deletion-requests", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/deletion-requests - {response.status_code}")
    
    # SubscriptionManager page endpoint
    def test_admin_users(self, admin_headers):
        """SubscriptionManager: GET /api/admin/users"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should return array or object with users key
        assert isinstance(data, (list, dict)), "Response should be list or dict"
        print(f"✓ /api/admin/users - {response.status_code}")
    
    # EmailTemplates page endpoint
    def test_admin_email_templates(self, admin_headers):
        """EmailTemplates: GET /api/admin/email-templates"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/email-templates - {response.status_code}")


class TestBuyerPaymentFlow:
    """Test buyer payment flow endpoints"""
    
    @pytest.fixture(scope="class")
    def user_headers(self):
        """Get regular user auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        data = response.json()
        token = data.get("access_token") or data.get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_fee_calculation_endpoint(self, user_headers):
        """GET /api/payments/fees/calculate-buyer-cost"""
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/calculate-buyer-cost",
            params={"price": 1000},  # Fixed: use 'price' not 'hammer_price'
            headers=user_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        print(f"✓ /api/payments/fees/calculate-buyer-cost - {response.status_code} - {data}")
    
    def test_checkout_auction_endpoint_exists(self, user_headers):
        """POST /api/payments/checkout/auction - endpoint exists"""
        # This will fail without valid listing_id but should return 4xx not 5xx
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout/auction",
            json={"listing_id": "nonexistent-id", "return_url": "http://test.com"},
            headers=user_headers
        )
        # Should be 404 (listing not found) or 400 (bad request), not 500
        assert response.status_code in [400, 404, 422], f"Unexpected status: {response.status_code} - {response.text}"
        print(f"✓ /api/payments/checkout/auction endpoint exists - {response.status_code}")


class TestEmailMarketing:
    """Test email marketing endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        data = response.json()
        token = data.get("access_token") or data.get("token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_marketing_campaigns(self, admin_headers):
        """GET /api/admin/marketing/campaigns"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing/campaigns", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/marketing/campaigns - {response.status_code}")
    
    def test_email_settings(self, admin_headers):
        """GET /api/admin/email-settings"""
        response = requests.get(f"{BASE_URL}/api/admin/email-settings", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/admin/email-settings - {response.status_code}")


class TestPlatformHealth:
    """Test platform health endpoints"""
    
    def test_health_check(self):
        """GET /api/health"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unhealthy: {data}"
        print(f"✓ /api/health - {response.status_code}")
    
    def test_site_config(self):
        """GET /api/site-config (public)"""
        response = requests.get(f"{BASE_URL}/api/site-config")
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ /api/site-config - {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
