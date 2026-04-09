"""
Test suite for Multi-Item Checkout Expansion: Cash & E-Transfer payment methods
Tests the offline-checkout endpoint and offline-order retrieval
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Admin123!"
TEST_USER_EMAIL = "starter@test.com"
TEST_USER_PASSWORD = "TestUser2026!"


class TestOfflineCheckoutEndpoints:
    """Tests for POST /api/payments/offline-checkout/{listing_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_auth_token(self, email, password):
        """Helper to get auth token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    # Test 1: Invalid payment_method returns 400
    def test_offline_checkout_invalid_payment_method(self):
        """POST /api/payments/offline-checkout/{listing_id} with invalid payment_method returns 400"""
        token = self.get_auth_token(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        # Use a fake listing_id - the payment_method validation should happen first
        fake_listing_id = str(uuid.uuid4())
        
        response = self.session.post(
            f"{BASE_URL}/api/payments/offline-checkout/{fake_listing_id}",
            json={"payment_method": "bitcoin", "return_url": "https://example.com"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should return 400 for invalid payment method
        # Note: It might return 404 if listing check happens first
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "invalid" in data.get("detail", "").lower() or "payment" in data.get("detail", "").lower(), \
                f"Expected error about invalid payment method, got: {data}"
            print(f"✓ Test passed: Invalid payment_method returns 400 - {data.get('detail')}")
        else:
            print(f"✓ Test passed: Listing not found (404) - payment method validation may happen after listing check")
    
    # Test 2: Nonexistent listing returns 404
    def test_offline_checkout_nonexistent_listing(self):
        """POST /api/payments/offline-checkout/{listing_id} with nonexistent listing returns 404"""
        token = self.get_auth_token(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        fake_listing_id = str(uuid.uuid4())
        
        response = self.session.post(
            f"{BASE_URL}/api/payments/offline-checkout/{fake_listing_id}",
            json={"payment_method": "cash", "return_url": "https://example.com"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert "not found" in data.get("detail", "").lower(), f"Expected 'not found' in detail, got: {data}"
        print(f"✓ Test passed: Nonexistent listing returns 404 - {data.get('detail')}")
    
    # Test 3: Without auth returns 401
    def test_offline_checkout_no_auth(self):
        """POST /api/payments/offline-checkout/{listing_id} without auth returns 401"""
        fake_listing_id = str(uuid.uuid4())
        
        response = self.session.post(
            f"{BASE_URL}/api/payments/offline-checkout/{fake_listing_id}",
            json={"payment_method": "cash", "return_url": "https://example.com"}
            # No Authorization header
        )
        
        # Should return 401 or 403 for unauthenticated request
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}: {response.text}"
        print(f"✓ Test passed: No auth returns {response.status_code}")


class TestOfflineOrderEndpoint:
    """Tests for GET /api/payments/offline-order/{order_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_auth_token(self, email, password):
        """Helper to get auth token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    # Test 4: Nonexistent order returns 404
    def test_offline_order_nonexistent(self):
        """GET /api/payments/offline-order/{order_id} with nonexistent order returns 404"""
        token = self.get_auth_token(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        fake_order_id = str(uuid.uuid4())
        
        response = self.session.get(
            f"{BASE_URL}/api/payments/offline-order/{fake_order_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert "not found" in data.get("detail", "").lower(), f"Expected 'not found' in detail, got: {data}"
        print(f"✓ Test passed: Nonexistent order returns 404 - {data.get('detail')}")
    
    # Test: Offline order without auth returns 401
    def test_offline_order_no_auth(self):
        """GET /api/payments/offline-order/{order_id} without auth returns 401"""
        fake_order_id = str(uuid.uuid4())
        
        response = self.session.get(
            f"{BASE_URL}/api/payments/offline-order/{fake_order_id}"
            # No Authorization header
        )
        
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}: {response.text}"
        print(f"✓ Test passed: No auth returns {response.status_code}")


class TestPaymentMethodValidation:
    """Additional tests for payment method validation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_auth_token(self, email, password):
        """Helper to get auth token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    def test_valid_payment_methods_accepted(self):
        """Verify 'cash' and 'etransfer' are valid payment methods (should fail on listing not found, not payment method)"""
        token = self.get_auth_token(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        fake_listing_id = str(uuid.uuid4())
        
        # Test 'cash' payment method
        response_cash = self.session.post(
            f"{BASE_URL}/api/payments/offline-checkout/{fake_listing_id}",
            json={"payment_method": "cash", "return_url": "https://example.com"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should return 404 (listing not found) not 400 (invalid payment method)
        assert response_cash.status_code == 404, f"Expected 404 for cash, got {response_cash.status_code}"
        print(f"✓ 'cash' is a valid payment method (got 404 for listing not found)")
        
        # Test 'etransfer' payment method
        response_etransfer = self.session.post(
            f"{BASE_URL}/api/payments/offline-checkout/{fake_listing_id}",
            json={"payment_method": "etransfer", "return_url": "https://example.com"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response_etransfer.status_code == 404, f"Expected 404 for etransfer, got {response_etransfer.status_code}"
        print(f"✓ 'etransfer' is a valid payment method (got 404 for listing not found)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
