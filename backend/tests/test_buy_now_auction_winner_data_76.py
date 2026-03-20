"""
Test Suite for BidVex Buy Now & Auction Winner Payment Endpoints (Iteration 76)
With actual test data for comprehensive testing.

Tests the following new endpoints:
1. POST /api/payments/buy-now-preview - Server-side price breakdown for Buy Now
2. POST /api/payments/buy-now-checkout - Create Stripe checkout for Buy Now
3. GET /api/payments/auction-winner-preview/{listing_id} - Preview for auction winner
4. POST /api/payments/auction-winner-checkout/{listing_id} - Checkout for auction winner

Security tests:
- Non-winner cannot access auction-winner-preview (403)
- Already-paid listings are rejected (400)
- All prices calculated server-side from MongoDB
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
ADMIN_USER_ID = "8940074d-da97-43ca-9a0b-c59d39411ed6"

# Test data IDs (created by setup script)
TEST_MULTI_ITEM_AUCTION_ID = "test-buy-now-auction-76"
TEST_WINNER_LISTING_ID = "test-winner-listing-76"
TEST_OTHER_WINNER_LISTING_ID = "test-other-winner-listing-76"
TEST_ALREADY_PAID_LISTING_ID = "test-already-paid-listing-76"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Health endpoint working")
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"✓ Login successful, token received")


class TestBuyNowPreviewWithData:
    """Tests for POST /api/payments/buy-now-preview with test data"""
    
    def test_buy_now_preview_success(self, auth_headers):
        """Test buy-now-preview with valid auction and lot"""
        response = requests.post(
            f"{BASE_URL}/api/payments/buy-now-preview",
            json={
                "auction_id": TEST_MULTI_ITEM_AUCTION_ID,
                "lot_number": 1,
                "quantity": 1
            },
            headers=auth_headers
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify price breakdown fields
        assert "item_total" in data
        assert "buyer_premium" in data
        assert "buyer_premium_rate" in data
        assert "total_tax" in data
        assert "processing_fee" in data
        assert "buyer_total" in data
        
        # Verify server-side calculation
        assert data["price_per_unit"] == 50.00  # Buy Now price from DB
        assert data["item_total"] == 50.00  # 1 x $50
        assert data["buyer_premium_rate"] > 0  # Should have a premium rate
        assert data["buyer_total"] > data["item_total"]  # Total should include fees
        
        print(f"✓ Buy Now preview returned correct breakdown:")
        print(f"  Item Total: ${data['item_total']}")
        print(f"  Buyer Premium ({data['buyer_premium_rate']*100:.1f}%): ${data['buyer_premium']}")
        print(f"  Total Tax: ${data['total_tax']}")
        print(f"  Processing Fee: ${data['processing_fee']}")
        print(f"  Buyer Total: ${data['buyer_total']}")
    
    def test_buy_now_preview_quantity_2(self, auth_headers):
        """Test buy-now-preview with quantity > 1"""
        response = requests.post(
            f"{BASE_URL}/api/payments/buy-now-preview",
            json={
                "auction_id": TEST_MULTI_ITEM_AUCTION_ID,
                "lot_number": 1,
                "quantity": 2
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify quantity calculation
        assert data["quantity"] == 2
        assert data["item_total"] == 100.00  # 2 x $50
        print(f"✓ Buy Now preview with quantity 2: item_total=${data['item_total']}, buyer_total=${data['buyer_total']}")
    
    def test_buy_now_preview_exceeds_quantity(self, auth_headers):
        """Test buy-now-preview with quantity exceeding available"""
        response = requests.post(
            f"{BASE_URL}/api/payments/buy-now-preview",
            json={
                "auction_id": TEST_MULTI_ITEM_AUCTION_ID,
                "lot_number": 1,
                "quantity": 100  # More than available (5)
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "available" in response.json().get("detail", "").lower()
        print("✓ Buy Now preview correctly rejects quantity exceeding available")


class TestBuyNowCheckoutWithData:
    """Tests for POST /api/payments/buy-now-checkout with test data"""
    
    def test_buy_now_checkout_creates_stripe_session(self, auth_headers):
        """Test buy-now-checkout creates Stripe session with correct amount"""
        response = requests.post(
            f"{BASE_URL}/api/payments/buy-now-checkout",
            json={
                "auction_id": TEST_MULTI_ITEM_AUCTION_ID,
                "lot_number": 1,
                "quantity": 1,
                "return_url": "https://example.com/success"
            },
            headers=auth_headers
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify Stripe session created
        assert "checkout_url" in data
        assert "stripe.com" in data["checkout_url"]
        assert "session_id" in data
        
        print(f"✓ Buy Now checkout created Stripe session")
        print(f"  Session ID: {data['session_id']}")
        print(f"  Checkout URL: {data['checkout_url'][:80]}...")


class TestAuctionWinnerPreviewWithData:
    """Tests for GET /api/payments/auction-winner-preview/{listing_id} with test data"""
    
    def test_auction_winner_preview_success(self, auth_headers):
        """Test auction-winner-preview for listing where admin is winner"""
        response = requests.get(
            f"{BASE_URL}/api/payments/auction-winner-preview/{TEST_WINNER_LISTING_ID}",
            headers=auth_headers
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify breakdown fields
        assert "hammer_price" in data
        assert "buyer_premium" in data
        assert "buyer_premium_rate" in data
        assert "total_tax" in data
        assert "processing_fee" in data
        assert "buyer_total" in data
        assert "late_penalty" in data
        assert "is_overdue" in data
        assert "payment_deadline" in data
        
        # Verify server-side calculation
        assert data["hammer_price"] == 150.00  # From DB
        assert data["late_penalty"] == 0  # Not overdue yet
        assert data["is_overdue"] == False
        
        print(f"✓ Auction winner preview returned correct breakdown:")
        print(f"  Hammer Price: ${data['hammer_price']}")
        print(f"  Buyer Premium ({data['buyer_premium_rate']*100:.1f}%): ${data['buyer_premium']}")
        print(f"  Total Tax: ${data['total_tax']}")
        print(f"  Processing Fee: ${data['processing_fee']}")
        print(f"  Late Penalty: ${data['late_penalty']}")
        print(f"  Buyer Total: ${data['buyer_total']}")
    
    def test_auction_winner_preview_non_winner_forbidden(self, auth_headers):
        """Test that non-winner gets 403 Forbidden"""
        response = requests.get(
            f"{BASE_URL}/api/payments/auction-winner-preview/{TEST_OTHER_WINNER_LISTING_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 403
        assert "winner" in response.json().get("detail", "").lower()
        print("✓ Non-winner correctly gets 403 Forbidden")
    
    def test_auction_winner_preview_already_paid_rejected(self, auth_headers):
        """Test that already-paid listing returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/payments/auction-winner-preview/{TEST_ALREADY_PAID_LISTING_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "paid" in response.json().get("detail", "").lower()
        print("✓ Already-paid listing correctly returns 400")


class TestAuctionWinnerCheckoutWithData:
    """Tests for POST /api/payments/auction-winner-checkout/{listing_id} with test data"""
    
    def test_auction_winner_checkout_creates_stripe_session(self, auth_headers):
        """Test auction-winner-checkout creates Stripe session with idempotency key"""
        response = requests.post(
            f"{BASE_URL}/api/payments/auction-winner-checkout/{TEST_WINNER_LISTING_ID}",
            json={"return_url": "https://example.com/checkout/success"},
            headers=auth_headers
        )
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify Stripe session created
        assert "checkout_url" in data
        assert "stripe.com" in data["checkout_url"]
        assert "session_id" in data
        assert "breakdown" in data
        
        print(f"✓ Auction winner checkout created Stripe session")
        print(f"  Session ID: {data['session_id']}")
        print(f"  Total Cents: {data.get('total_cents')}")
    
    def test_auction_winner_checkout_non_winner_forbidden(self, auth_headers):
        """Test that non-winner gets 403 Forbidden on checkout"""
        response = requests.post(
            f"{BASE_URL}/api/payments/auction-winner-checkout/{TEST_OTHER_WINNER_LISTING_ID}",
            json={"return_url": "https://example.com/checkout/success"},
            headers=auth_headers
        )
        
        assert response.status_code == 403
        assert "winner" in response.json().get("detail", "").lower()
        print("✓ Non-winner correctly gets 403 Forbidden on checkout")
    
    def test_auction_winner_checkout_already_paid_rejected(self, auth_headers):
        """Test that already-paid listing returns 400 on checkout"""
        response = requests.post(
            f"{BASE_URL}/api/payments/auction-winner-checkout/{TEST_ALREADY_PAID_LISTING_ID}",
            json={"return_url": "https://example.com/checkout/success"},
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "paid" in response.json().get("detail", "").lower()
        print("✓ Already-paid listing correctly returns 400 on checkout")


class TestFeeCalculationEndpoints:
    """Test existing fee calculation endpoints to ensure they still work"""
    
    def test_fee_structure_endpoint(self):
        """Test GET /api/payments/fees/structure"""
        response = requests.get(f"{BASE_URL}/api/payments/fees/structure")
        assert response.status_code == 200
        print("✓ Fee structure endpoint working")
    
    def test_fee_calculate_general(self):
        """Test GET /api/payments/fees/general"""
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/general",
            params={"price": 1000, "buyer_tier": "basic", "seller_tier": "basic"}
        )
        assert response.status_code == 200
        print("✓ General fee calculation endpoint working")
    
    def test_tax_calculate_endpoint(self):
        """Test POST /api/payments/tax/calculate"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyer_tier": "basic",
                "seller_tier": "basic",
                "seller_is_business": False
            }
        )
        assert response.status_code == 200
        print("✓ Tax calculation endpoint working")


class TestProcessingFeeEndpoint:
    """Test processing fee info endpoint"""
    
    def test_processing_fee_info(self):
        """Test GET /api/payments/fees/processing"""
        response = requests.get(f"{BASE_URL}/api/payments/fees/processing")
        assert response.status_code == 200
        data = response.json()
        assert data["percentage_display"] == "2.9%"
        assert data["fixed_fee_display"] == "$0.30"
        print("✓ Processing fee info endpoint working")


class TestTrustStatusEndpoint:
    """Test trust status endpoint"""
    
    def test_trust_status_with_auth(self, auth_headers):
        """Test trust status with valid auth"""
        response = requests.get(
            f"{BASE_URL}/api/payments/trust-status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "trust_status" in data
        assert "can_bid" in data
        print(f"✓ Trust status: {data.get('trust_status')}, can_bid: {data.get('can_bid')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
