"""
BidVex Admin Escrow Endpoints Tests - Iteration 149
Tests for:
- GET /api/escrow/admin/escrow/transactions (admin auth required)
- GET /api/escrow/admin/escrow/penalties (admin auth required)
- GET /api/escrow/admin/escrow/disputes (admin auth required)
- Non-admin user gets 403 on admin escrow endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


class TestAdminEscrowEndpoints:
    """Tests for admin escrow management endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    # ============ ADMIN ESCROW TRANSACTIONS ============
    def test_admin_escrow_transactions_returns_array(self, admin_headers):
        """GET /api/escrow/admin/escrow/transactions returns array (empty is OK)"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/transactions", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Admin escrow transactions returned {len(data)} records")
    
    def test_admin_escrow_transactions_unauthenticated(self):
        """GET /api/escrow/admin/escrow/transactions without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/transactions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated request correctly rejected with 401")
    
    # ============ ADMIN ESCROW PENALTIES ============
    def test_admin_escrow_penalties_returns_array(self, admin_headers):
        """GET /api/escrow/admin/escrow/penalties returns array (empty is OK)"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/penalties", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Admin escrow penalties returned {len(data)} records")
    
    def test_admin_escrow_penalties_unauthenticated(self):
        """GET /api/escrow/admin/escrow/penalties without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/penalties")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated request correctly rejected with 401")
    
    # ============ ADMIN ESCROW DISPUTES ============
    def test_admin_escrow_disputes_returns_array(self, admin_headers):
        """GET /api/escrow/admin/escrow/disputes returns array (empty is OK)"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/disputes", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Admin escrow disputes returned {len(data)} records")
    
    def test_admin_escrow_disputes_unauthenticated(self):
        """GET /api/escrow/admin/escrow/disputes without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/disputes")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated request correctly rejected with 401")


class TestNonAdminAccessDenied:
    """Tests that non-admin users get 403 on admin escrow endpoints"""
    
    @pytest.fixture(scope="class")
    def non_admin_token(self):
        """Create a test user and get their token"""
        import uuid
        test_email = f"test_buyer_{uuid.uuid4().hex[:8]}@test.com"
        test_password = "TestPass123!"
        
        # Register a new user
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": test_password,
            "name": "Test Buyer",
            "account_type": "buyer"
        })
        
        if register_response.status_code not in [200, 201]:
            pytest.skip(f"Could not create test user: {register_response.status_code}")
        
        # Login to get token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": test_password
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Test user login failed: {login_response.status_code}")
    
    @pytest.fixture(scope="class")
    def non_admin_headers(self, non_admin_token):
        """Headers with non-admin auth"""
        return {"Authorization": f"Bearer {non_admin_token}"}
    
    def test_non_admin_escrow_transactions_forbidden(self, non_admin_headers):
        """Non-admin user gets 403 on /api/escrow/admin/escrow/transactions"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/transactions", headers=non_admin_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Non-admin correctly denied access to escrow transactions (403)")
    
    def test_non_admin_escrow_penalties_forbidden(self, non_admin_headers):
        """Non-admin user gets 403 on /api/escrow/admin/escrow/penalties"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/penalties", headers=non_admin_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Non-admin correctly denied access to escrow penalties (403)")
    
    def test_non_admin_escrow_disputes_forbidden(self, non_admin_headers):
        """Non-admin user gets 403 on /api/escrow/admin/escrow/disputes"""
        response = requests.get(f"{BASE_URL}/api/escrow/admin/escrow/disputes", headers=non_admin_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ Non-admin correctly denied access to escrow disputes (403)")


class TestBuyerSellerEscrowEndpoints:
    """Tests for buyer/seller escrow status endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip(f"Admin authentication failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Headers with auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_buyer_escrow_status_authenticated(self, auth_headers):
        """GET /api/escrow/buyer/status returns array when authenticated"""
        response = requests.get(f"{BASE_URL}/api/escrow/buyer/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Buyer escrow status returned {len(data)} records")
    
    def test_seller_escrow_status_authenticated(self, auth_headers):
        """GET /api/escrow/seller/status returns array when authenticated"""
        response = requests.get(f"{BASE_URL}/api/escrow/seller/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Seller escrow status returned {len(data)} records")
    
    def test_buyer_escrow_status_unauthenticated(self):
        """GET /api/escrow/buyer/status without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/escrow/buyer/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated buyer escrow request correctly rejected with 401")
    
    def test_seller_escrow_status_unauthenticated(self):
        """GET /api/escrow/seller/status without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/escrow/seller/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated seller escrow request correctly rejected with 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
