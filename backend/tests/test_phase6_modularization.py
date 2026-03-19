"""
Phase 6 Modularization Tests
Tests for:
1. Dashboard extraction: /api/dashboard/seller and /api/dashboard/buyer
2. Payment endpoint deduplication: /api/payments/checkout, /api/payments/payment-methods
3. Webhook consolidation (verified via code review)
4. Admin email preview: /api/admin/email-preview/{template_key}
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Admin credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestPhase6Modularization:
    """Phase 6 modularization tests for dashboard, payments, webhooks, and email preview"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in login response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get auth headers for authenticated requests"""
        return {"Authorization": f"Bearer {admin_token}"}

    # ============ HEALTH CHECK ============
    
    def test_health_endpoint(self):
        """Test GET /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"
        print("✅ GET /api/health returns healthy")

    # ============ AUTH LOGIN ============
    
    def test_auth_login_returns_access_token(self):
        """Test POST /api/auth/login with admin credentials returns access_token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        print(f"✅ POST /api/auth/login returns access_token ({len(data['access_token'])} chars)")

    # ============ DASHBOARD ENDPOINTS ============
    
    def test_dashboard_seller_with_token(self, auth_headers):
        """Test GET /api/dashboard/seller with token returns required fields"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/seller",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Dashboard seller failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        required_fields = ["active_listings", "sold_listings", "draft_listings", "total_sales"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✅ GET /api/dashboard/seller returns: active={data['active_listings']}, sold={data['sold_listings']}, draft={data['draft_listings']}, total_sales={data['total_sales']}")
    
    def test_dashboard_buyer_with_token(self, auth_headers):
        """Test GET /api/dashboard/buyer with token returns required fields"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/buyer",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Dashboard buyer failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        required_fields = ["total_bids", "active_bids", "won_items", "watchlist"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✅ GET /api/dashboard/buyer returns: total_bids={data['total_bids']}, active_bids={data['active_bids']}, won_items={data['won_items']}, watchlist_count={len(data.get('watchlist', []))}")
    
    def test_dashboard_seller_without_token_returns_401(self):
        """Test GET /api/dashboard/seller WITHOUT token returns 401"""
        response = requests.get(f"{BASE_URL}/api/dashboard/seller")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ GET /api/dashboard/seller without token returns 401")
    
    def test_dashboard_buyer_without_token_returns_401(self):
        """Test GET /api/dashboard/buyer WITHOUT token returns 401"""
        response = requests.get(f"{BASE_URL}/api/dashboard/buyer")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ GET /api/dashboard/buyer without token returns 401")

    # ============ PAYMENT METHODS ENDPOINT ============
    
    def test_payment_methods_get_with_token(self, auth_headers):
        """Test GET /api/payments/payment-methods with token returns array"""
        response = requests.get(
            f"{BASE_URL}/api/payments/payment-methods",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Payment methods GET failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected array, got {type(data)}"
        print(f"✅ GET /api/payments/payment-methods returns array with {len(data)} method(s)")
    
    def test_payment_methods_without_token_returns_401(self):
        """Test GET /api/payments/payment-methods without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/payments/payment-methods")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ GET /api/payments/payment-methods without token returns 401")

    # ============ CHECKOUT ENDPOINT ============
    
    def test_checkout_with_listing_id_attempts_creation(self, auth_headers):
        """Test POST /api/payments/checkout with listing_id payload attempts checkout creation"""
        # Use a fake listing_id - should return 404 since listing doesn't exist
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={"listing_id": "test-nonexistent-listing-123"}
        )
        # Either 404 (listing not found) or some error - not 500
        assert response.status_code in [400, 404], f"Unexpected status {response.status_code}: {response.text}"
        print(f"✅ POST /api/payments/checkout with listing_id returns {response.status_code} (listing not found as expected)")
    
    def test_checkout_without_token_returns_401(self):
        """Test POST /api/payments/checkout without token returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json={"listing_id": "test-listing"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ POST /api/payments/checkout without token returns 401")

    # ============ ADMIN EMAIL PREVIEW ENDPOINTS ============
    
    def test_email_preview_password_reset_en(self, auth_headers):
        """Test GET /api/admin/email-preview/PASSWORD_RESET?language=en returns correct template_id"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-preview/PASSWORD_RESET",
            params={"language": "en"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Email preview failed: {response.text}"
        data = response.json()
        
        # Check that it returns the correct template_id for PASSWORD_RESET EN
        expected_template_id = "d-dbfba723dd5e4895a579b462b19c56fb"
        assert data.get("template_id") == expected_template_id, f"Expected template_id {expected_template_id}, got {data.get('template_id')}"
        assert data.get("status") in ["sent", "preview_only"], f"Unexpected status: {data.get('status')}"
        print(f"✅ GET /api/admin/email-preview/PASSWORD_RESET?language=en returns status={data.get('status')}, template_id={data.get('template_id')}")
    
    def test_email_preview_welcome_fr(self, auth_headers):
        """Test GET /api/admin/email-preview/WELCOME?language=fr returns correct FR template_id"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-preview/WELCOME",
            params={"language": "fr"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Email preview failed: {response.text}"
        data = response.json()
        
        # Check that it returns the correct template_id for WELCOME FR
        expected_template_id = "d-256f3801670441808730c4cfb259d9a2"
        assert data.get("template_id") == expected_template_id, f"Expected template_id {expected_template_id}, got {data.get('template_id')}"
        print(f"✅ GET /api/admin/email-preview/WELCOME?language=fr returns correct FR template_id={data.get('template_id')}")
    
    def test_email_preview_bad_key_returns_404(self, auth_headers):
        """Test GET /api/admin/email-preview/NONEXISTENT returns 404 with available templates"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-preview/NONEXISTENT",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Should contain available templates list
        detail = data.get("detail", "")
        assert "Available" in detail or "not found" in detail.lower(), f"Expected available templates in error: {detail}"
        print(f"✅ GET /api/admin/email-preview/NONEXISTENT returns 404 with template list")
    
    def test_email_preview_without_token_returns_401(self):
        """Test GET /api/admin/email-preview/WELCOME without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/admin/email-preview/WELCOME")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ GET /api/admin/email-preview/WELCOME without token returns 401")

    # ============ VERIFIED FIRM BADGE TOGGLE ============
    
    def test_verified_firm_toggle_without_auth_returns_401(self):
        """Test POST /api/admin/partners/{id}/verified-firm without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/fake-partner-id/verified-firm",
            json={"is_verified_firm": True}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ POST /api/admin/partners/{id}/verified-firm without auth returns 401")
    
    def test_verified_firm_toggle_nonexistent_returns_404(self, auth_headers):
        """Test POST /api/admin/partners/{id}/verified-firm with non-existent partner returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/nonexistent-partner-12345/verified-firm",
            headers=auth_headers,
            json={"is_verified_firm": True}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✅ POST /api/admin/partners/{id}/verified-firm with non-existent partner returns 404")


class TestDashboardRouterIntegration:
    """Additional integration tests for dashboard router"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.text}")
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_seller_dashboard_returns_listings_arrays(self, auth_headers):
        """Verify seller dashboard returns listings and multi_item_listings arrays"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/seller",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check for listing arrays
        assert "listings" in data, "Missing 'listings' array"
        assert "multi_item_listings" in data, "Missing 'multi_item_listings' array"
        assert "all_listings" in data, "Missing 'all_listings' array"
        assert isinstance(data["listings"], list), "listings should be a list"
        assert isinstance(data["multi_item_listings"], list), "multi_item_listings should be a list"
        print(f"✅ Seller dashboard returns listings arrays: {len(data['listings'])} single, {len(data['multi_item_listings'])} multi")
    
    def test_buyer_dashboard_returns_bids_and_listings(self, auth_headers):
        """Verify buyer dashboard returns bids and listings arrays"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/buyer",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check for bids and listings arrays
        assert "bids" in data, "Missing 'bids' array"
        assert "listings" in data, "Missing 'listings' array"
        assert isinstance(data["bids"], list), "bids should be a list"
        assert isinstance(data["listings"], list), "listings should be a list"
        print(f"✅ Buyer dashboard returns: {len(data['bids'])} bids, {len(data['listings'])} listings")


class TestPaymentRouterIntegration:
    """Additional integration tests for payment router"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.text}")
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_subscription_status_endpoint(self, auth_headers):
        """Test GET /api/payments/subscription/status returns subscription info"""
        response = requests.get(
            f"{BASE_URL}/api/payments/subscription/status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Subscription status failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "tier" in data, "Missing 'tier' in subscription status"
        assert "source" in data, "Missing 'source' in subscription status"
        assert "status" in data, "Missing 'status' in subscription status"
        print(f"✅ GET /api/payments/subscription/status returns: tier={data.get('tier')}, source={data.get('source')}, status={data.get('status')}")
    
    def test_trust_status_endpoint(self, auth_headers):
        """Test GET /api/payments/trust-status returns trust verification info"""
        response = requests.get(
            f"{BASE_URL}/api/payments/trust-status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Trust status failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "trust_status" in data, "Missing 'trust_status'"
        assert "is_verified" in data, "Missing 'is_verified'"
        assert "has_payment_method" in data, "Missing 'has_payment_method'"
        assert "can_bid" in data, "Missing 'can_bid'"
        print(f"✅ GET /api/payments/trust-status returns: trust_status={data.get('trust_status')}, can_bid={data.get('can_bid')}")
    
    def test_fee_structure_endpoint(self):
        """Test GET /api/payments/fees/structure returns fee structure documentation"""
        response = requests.get(f"{BASE_URL}/api/payments/fees/structure")
        assert response.status_code == 200, f"Fee structure failed: {response.text}"
        data = response.json()
        
        # Check that it returns fee structure info
        assert data, "Empty response from fee structure endpoint"
        print(f"✅ GET /api/payments/fees/structure returns fee documentation")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
