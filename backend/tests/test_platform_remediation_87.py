"""
Platform Remediation Tests - Iteration 87
Tests for admin panel, buyer payment flow, email marketing, and platform health.

Key fixes verified:
1. JWT_SECRET consistency across route files
2. FLAG_TYPES import in trust_safety.py
3. calculate_trust_score function implementation
4. MongoDB connection tuning
5. site-config fallback on DB timeout
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-fix-critical.preview.emergentagent.com')

# Admin credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestAdminAuth:
    """Test admin authentication and token validity"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token for all tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_admin_login(self, admin_token):
        """TASK 1 - Admin Auth: Login as admin and verify token works"""
        assert admin_token is not None
        assert len(admin_token) > 50  # JWT tokens are long
        print(f"✓ Admin login successful, token length: {len(admin_token)}")


class TestAdminEndpoints:
    """Test all admin endpoints with valid admin token"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    # TASK 1 - Admin Users
    def test_admin_users(self, admin_headers):
        """GET /api/admin/users returns user list with valid admin token"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "users" in data or isinstance(data, list), "Response should contain users"
        print(f"✓ Admin users endpoint: {response.status_code}")
    
    # TASK 1 - Admin Analytics
    def test_admin_analytics(self, admin_headers):
        """GET /api/admin/analytics returns stats data"""
        # Try /api/admin/analytics/users first (more specific)
        response = requests.get(f"{BASE_URL}/api/admin/analytics/users", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin analytics/users endpoint: {response.status_code}")
    
    # TASK 1 - Admin Analytics Revenue
    def test_admin_analytics_revenue(self, admin_headers):
        """GET /api/admin/analytics/revenue returns revenue data"""
        response = requests.get(f"{BASE_URL}/api/admin/analytics/revenue", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin analytics/revenue endpoint: {response.status_code}")
    
    # TASK 1 - Admin Listings
    def test_admin_listings(self, admin_headers):
        """GET /api/admin/listings/all returns listings"""
        response = requests.get(f"{BASE_URL}/api/admin/listings/all", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "listings" in data or isinstance(data, list), "Response should contain listings"
        print(f"✓ Admin listings/all endpoint: {response.status_code}")
    
    # TASK 1 - Admin Marketplace Settings
    def test_admin_marketplace_settings(self, admin_headers):
        """GET /api/admin/marketplace-settings returns settings"""
        response = requests.get(f"{BASE_URL}/api/admin/marketplace-settings", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin marketplace-settings endpoint: {response.status_code}")
    
    # TASK 1 - Admin Partners
    def test_admin_partners(self, admin_headers):
        """GET /api/admin/partners returns partner list"""
        response = requests.get(f"{BASE_URL}/api/admin/partners", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin partners endpoint: {response.status_code}")
    
    # TASK 1 - Admin Finance
    def test_admin_finance_revenue_summary(self, admin_headers):
        """GET /api/admin/finance/revenue-summary returns financial data"""
        response = requests.get(f"{BASE_URL}/api/admin/finance/revenue-summary", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin finance/revenue-summary endpoint: {response.status_code}")
    
    # TASK 1 - Admin Logs
    def test_admin_logs(self, admin_headers):
        """GET /api/admin/logs returns activity logs"""
        response = requests.get(f"{BASE_URL}/api/admin/logs", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin logs endpoint: {response.status_code}")
    
    # TASK 1 - Admin Promotions
    def test_admin_promotions(self, admin_headers):
        """GET /api/admin/promotions returns promotions list"""
        response = requests.get(f"{BASE_URL}/api/admin/promotions", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin promotions endpoint: {response.status_code}")
    
    # TASK 1 - Admin Affiliates
    def test_admin_affiliates(self, admin_headers):
        """GET /api/admin/affiliates returns affiliate data"""
        response = requests.get(f"{BASE_URL}/api/admin/affiliates", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin affiliates endpoint: {response.status_code}")
    
    # TASK 1 - Admin Trust Safety Scores (was 500, now fixed)
    def test_admin_trust_safety_scores(self, admin_headers):
        """GET /api/admin/trust-safety/scores returns trust scores"""
        response = requests.get(f"{BASE_URL}/api/admin/trust-safety/scores", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list of trust scores"
        print(f"✓ Admin trust-safety/scores endpoint: {response.status_code} - {len(data)} scores")
    
    # TASK 1 - Admin AI Guard Stats (was 500, now fixed)
    def test_admin_ai_guard_stats(self, admin_headers):
        """GET /api/admin/ai-guard/stats returns fraud stats"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-guard/stats", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "stats" in data or "success" in data, "Response should contain stats"
        print(f"✓ Admin ai-guard/stats endpoint: {response.status_code}")
    
    # TASK 1 - Admin Marketing
    def test_admin_marketing_campaigns(self, admin_headers):
        """GET /api/admin/marketing/campaigns returns campaign list"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing/campaigns", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin marketing/campaigns endpoint: {response.status_code}")
    
    # TASK 1 - Admin Subscriptions
    def test_admin_subscription_plans(self, admin_headers):
        """GET /api/admin/subscription-plans returns plans"""
        response = requests.get(f"{BASE_URL}/api/admin/subscription-plans", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin subscription-plans endpoint: {response.status_code}")
    
    # TASK 1 - Admin Categories
    def test_categories(self, admin_headers):
        """GET /api/categories returns category list"""
        response = requests.get(f"{BASE_URL}/api/categories", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert isinstance(data, list) or "categories" in data, "Response should contain categories"
        print(f"✓ Categories endpoint: {response.status_code}")
    
    # TASK 1 - Admin Coupons
    def test_admin_coupons(self, admin_headers):
        """GET /api/admin/coupons returns coupon list"""
        response = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin coupons endpoint: {response.status_code}")
    
    # TASK 1 - Admin Tax
    def test_admin_tax_pending(self, admin_headers):
        """GET /api/admin/tax/pending returns pending tax reviews"""
        response = requests.get(f"{BASE_URL}/api/admin/tax/pending", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin tax/pending endpoint: {response.status_code}")
    
    # TASK 1 - Admin Site Config (was 500 timeout, now has fallback)
    def test_admin_site_config(self, admin_headers):
        """GET /api/admin/site-config returns config"""
        response = requests.get(f"{BASE_URL}/api/admin/site-config", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "branding" in data or "homepage_layout" in data, "Response should contain config"
        print(f"✓ Admin site-config endpoint: {response.status_code}")


class TestPaymentFlow:
    """Test buyer payment flow endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    # TASK 2 - Checkout endpoint
    def test_checkout_endpoint_exists(self, admin_headers):
        """POST /api/checkout with listing_id - verify endpoint exists"""
        # This will fail without a valid listing_id, but we verify the endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            headers=admin_headers,
            json={"listing_id": "test-listing-id"}
        )
        # 404 means listing not found (endpoint works), 401/403 means auth issue
        assert response.status_code in [200, 400, 404, 422], f"Unexpected: {response.status_code} - {response.text}"
        print(f"✓ Checkout endpoint exists: {response.status_code}")
    
    # TASK 2 - Payment status
    def test_payment_status_endpoint(self, admin_headers):
        """GET /api/status/{session_id} returns checkout status"""
        # Test with a dummy session ID - should return 400 (invalid) not 404 (not found)
        response = requests.get(f"{BASE_URL}/api/payments/status/test_session_id", headers=admin_headers)
        # 400 means invalid session (endpoint works), 404 means endpoint not found
        assert response.status_code in [200, 400], f"Unexpected: {response.status_code} - {response.text}"
        print(f"✓ Payment status endpoint exists: {response.status_code}")
    
    # TASK 2 - Hammer price calculation
    def test_calculate_buyer_total(self, admin_headers):
        """Verify /api/payments/calculate-buyer-total or similar endpoint"""
        # Try the fee calculation endpoint
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/calculate-buyer-cost?price=1000&tier=free",
            headers=admin_headers
        )
        if response.status_code == 200:
            data = response.json()
            assert "total_cost" in data or "buyer_premium" in data, "Should return fee breakdown"
            print(f"✓ Fee calculation endpoint: {response.status_code}")
        else:
            # Try alternative endpoint
            response2 = requests.post(
                f"{BASE_URL}/api/payments/fees/calculate",
                headers=admin_headers,
                json={"hammer_price": 1000, "category": "general"}
            )
            assert response2.status_code in [200, 422], f"Fee calc failed: {response2.status_code}"
            print(f"✓ Fee calculation endpoint (POST): {response2.status_code}")


class TestEmailMarketing:
    """Test email marketing endpoints for sellers"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    # TASK 3 - Email marketing campaigns
    def test_marketing_campaigns(self, admin_headers):
        """GET /api/admin/marketing/campaigns returns campaign data"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing/campaigns", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Marketing campaigns endpoint: {response.status_code}")
    
    # TASK 3 - Email settings
    def test_email_settings(self, admin_headers):
        """GET /api/admin/email-settings returns settings"""
        response = requests.get(f"{BASE_URL}/api/admin/email-settings", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "configured" in data or "source" in data, "Should return email config status"
        print(f"✓ Email settings endpoint: {response.status_code}")
    
    # TASK 3 - Email templates
    def test_email_templates(self, admin_headers):
        """GET /api/admin/email-templates returns templates"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Email templates endpoint: {response.status_code}")


class TestPlatformHealth:
    """Test platform health and public endpoints"""
    
    # TASK 4 - Health check
    def test_health_check(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected status: {data}"
        print(f"✓ Health check: {response.status_code} - {data}")
    
    # TASK 4 - Public site-config
    def test_public_site_config(self):
        """GET /api/site-config returns branding data without auth"""
        response = requests.get(f"{BASE_URL}/api/site-config")
        assert response.status_code == 200, f"Site config failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "branding" in data, "Response should contain branding"
        print(f"✓ Public site-config: {response.status_code}")
    
    # TASK 4 - JWT consistency verification
    def test_jwt_consistency(self):
        """Verify all route files use same JWT_SECRET default"""
        # This is a code review check - we verify by testing that admin token works on all endpoints
        # If JWT secrets were mismatched, some endpoints would return 401
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test token on multiple endpoints that use different route files
        endpoints = [
            "/api/admin/users",  # admin.py
            "/api/auth/me",  # auth.py
            "/api/admin/trust-safety/scores",  # trust_safety.py
            "/api/admin/site-config",  # site_config.py
        ]
        
        for endpoint in endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            assert resp.status_code == 200, f"JWT mismatch on {endpoint}: {resp.status_code}"
        
        print(f"✓ JWT consistency verified across {len(endpoints)} endpoints")


class TestAdminTransactions:
    """Test admin transaction endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_admin_transactions(self, admin_headers):
        """GET /api/admin/transactions returns transaction data"""
        response = requests.get(f"{BASE_URL}/api/admin/transactions", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        print(f"✓ Admin transactions endpoint: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
