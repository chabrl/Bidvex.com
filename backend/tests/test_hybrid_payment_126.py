"""
Test suite for Multi-Item Auction — Hybrid Payment Integration
Tests the buy-now endpoint with stripe, cash, and etransfer payment methods
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Admin123!"

# Test listing - active multi-item listing with buy_now enabled
TEST_LISTING_ID = "0e97aca1-86be-430c-860f-732c1f71164a"
TEST_LOT_NUMBER = 1  # Test Item with Buy Now


class TestBuyNowHybridPayment:
    """Tests for POST /api/buy-now with different payment methods"""
    
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
    
    # Test 1: Buy Now with stripe payment method (existing flow)
    def test_buy_now_stripe_payment_method(self):
        """POST /api/buy-now with payment_method='stripe' should work as before"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        # Get current lot info first
        listing_response = self.session.get(f"{BASE_URL}/api/multi-item-listings/{TEST_LISTING_ID}")
        assert listing_response.status_code == 200, f"Failed to get listing: {listing_response.text}"
        
        listing = listing_response.json()
        lot = next((l for l in listing.get("lots", []) if l["lot_number"] == TEST_LOT_NUMBER), None)
        
        if lot is None:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} not found in listing")
        
        if not lot.get("buy_now_enabled"):
            pytest.skip(f"Buy Now not enabled for lot {TEST_LOT_NUMBER}")
        
        available_qty = lot.get("available_quantity", lot.get("quantity", 0))
        if available_qty <= 0:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} is sold out")
        
        # Test stripe payment method
        response = self.session.post(
            f"{BASE_URL}/api/buy-now",
            json={
                "auction_id": TEST_LISTING_ID,
                "lot_number": TEST_LOT_NUMBER,
                "quantity": 1,
                "payment_method": "stripe"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should return 200 with pending payment status
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        assert "transaction_id" in data, f"Expected transaction_id in response, got: {data}"
        assert data.get("payment_method") == "stripe", f"Expected payment_method='stripe', got: {data.get('payment_method')}"
        assert data.get("payment_status") == "pending", f"Expected payment_status='pending' for stripe, got: {data.get('payment_status')}"
        
        print(f"✓ Test passed: Stripe payment method returns success with pending status")
        print(f"  Transaction ID: {data.get('transaction_id')}")
        print(f"  Payment Status: {data.get('payment_status')}")
    
    # Test 2: Buy Now with etransfer payment method
    def test_buy_now_etransfer_payment_method(self):
        """POST /api/buy-now with payment_method='etransfer' should return waiting_for_offline_confirmation"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        # Get current lot info first
        listing_response = self.session.get(f"{BASE_URL}/api/multi-item-listings/{TEST_LISTING_ID}")
        assert listing_response.status_code == 200, f"Failed to get listing: {listing_response.text}"
        
        listing = listing_response.json()
        lot = next((l for l in listing.get("lots", []) if l["lot_number"] == TEST_LOT_NUMBER), None)
        
        if lot is None:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} not found in listing")
        
        if not lot.get("buy_now_enabled"):
            pytest.skip(f"Buy Now not enabled for lot {TEST_LOT_NUMBER}")
        
        available_qty = lot.get("available_quantity", lot.get("quantity", 0))
        if available_qty <= 0:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} is sold out")
        
        # Test etransfer payment method
        response = self.session.post(
            f"{BASE_URL}/api/buy-now",
            json={
                "auction_id": TEST_LISTING_ID,
                "lot_number": TEST_LOT_NUMBER,
                "quantity": 1,
                "payment_method": "etransfer"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should return 200 with waiting_for_offline_confirmation status
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        assert "transaction_id" in data, f"Expected transaction_id in response, got: {data}"
        assert data.get("payment_method") == "etransfer", f"Expected payment_method='etransfer', got: {data.get('payment_method')}"
        assert data.get("payment_status") == "waiting_for_offline_confirmation", \
            f"Expected payment_status='waiting_for_offline_confirmation' for etransfer, got: {data.get('payment_status')}"
        
        print(f"✓ Test passed: E-Transfer payment method returns success with waiting_for_offline_confirmation")
        print(f"  Transaction ID: {data.get('transaction_id')}")
        print(f"  Payment Status: {data.get('payment_status')}")
        print(f"  Message: {data.get('message')}")
    
    # Test 3: Buy Now with cash payment method
    def test_buy_now_cash_payment_method(self):
        """POST /api/buy-now with payment_method='cash' should return waiting_for_offline_confirmation"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        # Get current lot info first
        listing_response = self.session.get(f"{BASE_URL}/api/multi-item-listings/{TEST_LISTING_ID}")
        assert listing_response.status_code == 200, f"Failed to get listing: {listing_response.text}"
        
        listing = listing_response.json()
        lot = next((l for l in listing.get("lots", []) if l["lot_number"] == TEST_LOT_NUMBER), None)
        
        if lot is None:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} not found in listing")
        
        if not lot.get("buy_now_enabled"):
            pytest.skip(f"Buy Now not enabled for lot {TEST_LOT_NUMBER}")
        
        available_qty = lot.get("available_quantity", lot.get("quantity", 0))
        if available_qty <= 0:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} is sold out")
        
        # Test cash payment method
        response = self.session.post(
            f"{BASE_URL}/api/buy-now",
            json={
                "auction_id": TEST_LISTING_ID,
                "lot_number": TEST_LOT_NUMBER,
                "quantity": 1,
                "payment_method": "cash"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should return 200 with waiting_for_offline_confirmation status
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        assert "transaction_id" in data, f"Expected transaction_id in response, got: {data}"
        assert data.get("payment_method") == "cash", f"Expected payment_method='cash', got: {data.get('payment_method')}"
        assert data.get("payment_status") == "waiting_for_offline_confirmation", \
            f"Expected payment_status='waiting_for_offline_confirmation' for cash, got: {data.get('payment_status')}"
        
        print(f"✓ Test passed: Cash payment method returns success with waiting_for_offline_confirmation")
        print(f"  Transaction ID: {data.get('transaction_id')}")
        print(f"  Payment Status: {data.get('payment_status')}")
        print(f"  Message: {data.get('message')}")
    
    # Test 4: Buy Now without auth returns 401
    def test_buy_now_no_auth(self):
        """POST /api/buy-now without auth returns 401"""
        response = self.session.post(
            f"{BASE_URL}/api/buy-now",
            json={
                "auction_id": TEST_LISTING_ID,
                "lot_number": TEST_LOT_NUMBER,
                "quantity": 1,
                "payment_method": "stripe"
            }
            # No Authorization header
        )
        
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}: {response.text}"
        print(f"✓ Test passed: No auth returns {response.status_code}")
    
    # Test 5: Buy Now with nonexistent listing returns 404
    def test_buy_now_nonexistent_listing(self):
        """POST /api/buy-now with nonexistent listing returns 404"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        fake_listing_id = str(uuid.uuid4())
        
        response = self.session.post(
            f"{BASE_URL}/api/buy-now",
            json={
                "auction_id": fake_listing_id,
                "lot_number": 1,
                "quantity": 1,
                "payment_method": "stripe"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✓ Test passed: Nonexistent listing returns 404")
    
    # Test 6: Buy Now with nonexistent lot returns 404
    def test_buy_now_nonexistent_lot(self):
        """POST /api/buy-now with nonexistent lot returns 404"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        response = self.session.post(
            f"{BASE_URL}/api/buy-now",
            json={
                "auction_id": TEST_LISTING_ID,
                "lot_number": 9999,  # Nonexistent lot
                "quantity": 1,
                "payment_method": "stripe"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✓ Test passed: Nonexistent lot returns 404")


class TestBuyNowTransactionRecords:
    """Tests for verifying transaction records are created correctly"""
    
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
    
    # Test 7: Verify listing endpoint returns lot info
    def test_listing_endpoint_returns_lot_info(self):
        """GET /api/multi-item-listings/{id} returns lot information"""
        response = self.session.get(f"{BASE_URL}/api/multi-item-listings/{TEST_LISTING_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "lots" in data, f"Expected 'lots' in response, got: {data.keys()}"
        assert len(data["lots"]) > 0, "Expected at least one lot"
        
        # Find our test lot
        lot = next((l for l in data["lots"] if l["lot_number"] == TEST_LOT_NUMBER), None)
        if lot:
            print(f"✓ Test passed: Listing endpoint returns lot info")
            print(f"  Lot {TEST_LOT_NUMBER}: {lot.get('title')}")
            print(f"  Buy Now Price: {lot.get('buy_now_price')}")
            print(f"  Buy Now Enabled: {lot.get('buy_now_enabled')}")
            print(f"  Available Quantity: {lot.get('available_quantity', lot.get('quantity'))}")
        else:
            print(f"⚠ Lot {TEST_LOT_NUMBER} not found in listing")


class TestPaymentMethodModel:
    """Tests for BuyNowPurchase model payment_method field"""
    
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
    
    # Test 8: Default payment method is stripe
    def test_default_payment_method_is_stripe(self):
        """POST /api/buy-now without payment_method defaults to stripe"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token is not None, "Failed to get auth token"
        
        # Get current lot info first
        listing_response = self.session.get(f"{BASE_URL}/api/multi-item-listings/{TEST_LISTING_ID}")
        assert listing_response.status_code == 200, f"Failed to get listing: {listing_response.text}"
        
        listing = listing_response.json()
        lot = next((l for l in listing.get("lots", []) if l["lot_number"] == TEST_LOT_NUMBER), None)
        
        if lot is None:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} not found in listing")
        
        if not lot.get("buy_now_enabled"):
            pytest.skip(f"Buy Now not enabled for lot {TEST_LOT_NUMBER}")
        
        available_qty = lot.get("available_quantity", lot.get("quantity", 0))
        if available_qty <= 0:
            pytest.skip(f"Lot {TEST_LOT_NUMBER} is sold out")
        
        # Test without payment_method (should default to stripe)
        response = self.session.post(
            f"{BASE_URL}/api/buy-now",
            json={
                "auction_id": TEST_LISTING_ID,
                "lot_number": TEST_LOT_NUMBER,
                "quantity": 1
                # No payment_method - should default to stripe
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("payment_method") == "stripe", f"Expected default payment_method='stripe', got: {data.get('payment_method')}"
        assert data.get("payment_status") == "pending", f"Expected payment_status='pending' for default stripe, got: {data.get('payment_status')}"
        
        print(f"✓ Test passed: Default payment method is stripe")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
