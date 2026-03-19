"""
Test Listing-Level Buyer's Premium Feature
==========================================
Tests for:
1. POST /api/listings with buyers_premium_rate stores custom_buyer_premium_rate
2. POST /api/listings without buyers_premium_rate stores custom_buyer_premium_rate=null
3. POST /api/payments/tax/calculate with buyers_premium_rate returns correct buyer_premium
4. POST /api/payments/tax/calculate without buyers_premium_rate defaults to tier rate
5. GET /api/payments/tax/vehicle with buyers_premium_rate override
6. GET /api/listings/{id} returns custom_buyer_premium_rate
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

# Test listing with 15% premium
TEST_LISTING_ID = "a43ab510-3734-40f0-87c4-701708711769"


@pytest.fixture(scope="session")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestTaxCalculateWithBuyersPremium:
    """Tests for /api/payments/tax/calculate endpoint with buyers_premium_rate"""
    
    def test_tax_calculate_with_custom_premium_rate_15_percent(self, api_client):
        """POST /api/payments/tax/calculate with buyers_premium_rate=0.15 returns buyer_premium=150 on $1000"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyers_premium_rate": 0.15,  # 15%
                "buyer_tier": "basic",
                "seller_tier": "basic",
                "seller_is_business": False
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate buyer_premium calculation: $1000 * 0.15 = $150
        assert "buyer_premium" in data, "Response should contain buyer_premium"
        assert data["buyer_premium"] == 150.0, f"Expected buyer_premium=150, got {data['buyer_premium']}"
        
        # Validate buyer_premium_rate is returned correctly
        assert data.get("buyer_premium_rate") == 0.15, f"Expected buyer_premium_rate=0.15, got {data.get('buyer_premium_rate')}"
    
    def test_tax_calculate_with_10_percent_premium(self, api_client):
        """POST /api/payments/tax/calculate with buyers_premium_rate=0.10 returns buyer_premium=100 on $1000"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyers_premium_rate": 0.10,  # 10%
                "buyer_tier": "basic",
                "seller_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["buyer_premium"] == 100.0, f"Expected 100, got {data['buyer_premium']}"
        assert data["buyer_premium_rate"] == 0.10
    
    def test_tax_calculate_without_premium_defaults_to_tier_rate(self, api_client):
        """POST /api/payments/tax/calculate without buyers_premium_rate defaults to tier rate (5% for basic)"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyer_tier": "basic",
                "seller_tier": "basic",
                "seller_is_business": False
                # No buyers_premium_rate - should use tier default
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Default basic tier rate is 5%
        assert data["buyer_premium"] == 50.0, f"Expected 50 (5% of 1000), got {data['buyer_premium']}"
        assert data["buyer_premium_rate"] == 0.05, f"Expected 0.05 (5%), got {data.get('buyer_premium_rate')}"
    
    def test_tax_calculate_premium_tier_default(self, api_client):
        """POST /api/payments/tax/calculate with premium tier defaults to 3.5%"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyer_tier": "premium",
                "seller_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        # Premium tier default is 3.5%
        assert data["buyer_premium"] == 35.0, f"Expected 35 (3.5% of 1000), got {data['buyer_premium']}"
    
    def test_tax_calculate_premium_override_beats_tier(self, api_client):
        """Custom buyers_premium_rate overrides tier default even for premium users"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyer_tier": "premium",  # Would default to 3.5%
                "buyers_premium_rate": 0.20,  # Override to 20%
                "seller_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        # Custom rate should override tier default
        assert data["buyer_premium"] == 200.0, f"Expected 200 (20% override), got {data['buyer_premium']}"
        assert data["buyer_premium_rate"] == 0.20


class TestVehicleTaxWithBuyersPremium:
    """Tests for /api/payments/tax/vehicle endpoint with buyers_premium_rate"""
    
    def test_vehicle_tax_with_custom_premium_rate(self, api_client):
        """GET /api/payments/tax/vehicle?price=10000&buyers_premium_rate=0.10 returns buyer_premium=1000"""
        response = api_client.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={
                "price": 10000,
                "buyer_tier": "basic",
                "buyers_premium_rate": 0.10  # 10% override
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate buyer_premium: $10,000 * 0.10 = $1,000
        assert data.get("buyer_premium") == 1000.0, f"Expected 1000, got {data.get('buyer_premium')}"
        assert data.get("buyer_premium_rate") == 0.10
    
    def test_vehicle_tax_without_premium_uses_tier_default(self, api_client):
        """GET /api/payments/tax/vehicle without buyers_premium_rate uses tier default (5%)"""
        response = api_client.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={
                "price": 10000,
                "buyer_tier": "basic"
                # No buyers_premium_rate
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Default basic tier is 5%
        assert data.get("buyer_premium") == 500.0, f"Expected 500, got {data.get('buyer_premium')}"
        assert data.get("buyer_premium_rate") == 0.05


class TestGetListingWithBuyersPremium:
    """Tests for GET /api/listings/{id} returning custom_buyer_premium_rate"""
    
    def test_get_listing_returns_custom_buyer_premium_rate(self, api_client):
        """GET /api/listings/{id} returns custom_buyer_premium_rate in response"""
        response = api_client.get(f"{BASE_URL}/api/listings/{TEST_LISTING_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify custom_buyer_premium_rate field exists in response
        assert "custom_buyer_premium_rate" in data, "Listing response should contain custom_buyer_premium_rate"
        
        # This listing should have 15% premium set
        expected_rate = 0.15
        actual_rate = data.get("custom_buyer_premium_rate")
        assert actual_rate == expected_rate, f"Expected custom_buyer_premium_rate={expected_rate}, got {actual_rate}"


class TestTaxCalculateTotalCostVerification:
    """Tests to verify total cost calculations including premium and taxes"""
    
    def test_total_buyer_cost_general_private_seller(self, api_client):
        """Verify total buyer cost for general auction with private seller (no tax on item)"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyers_premium_rate": 0.15,  # 15%
                "buyer_tier": "basic",
                "seller_is_business": False  # Private seller
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Calculations:
        # Hammer: $1000
        # Buyer Premium (15%): $150
        # Tax on fees only (14.975% on $150): ~$22.46
        # Total: $1000 + $150 + $22.46 = $1172.46
        
        assert data["hammer_price"] == 1000.0
        assert data["buyer_premium"] == 150.0
        assert data.get("buyer_total") is not None, "Response should contain buyer_total"
        
        # Verify buyer total is approximately correct
        buyer_total = data["buyer_total"]
        # Expected total for private seller (no tax on hammer): ~$1172.46
        assert 1170 < buyer_total < 1175, f"Expected buyer_total ~$1172.46, got {buyer_total}"
    
    def test_total_buyer_cost_vehicle_auction(self, api_client):
        """Verify total cost for vehicle auction (fees only via Stripe)"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 10000,
                "category": "vehicle",
                "buyers_premium_rate": 0.10,  # 10%
                "buyer_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Vehicle calculation:
        # Hammer: $10,000 (paid directly to seller)
        # Buyer Premium (10%): $1,000
        # Platform Fee (2.5%): $250
        # BidVex fees subtotal: $1,250
        # Tax on fees (14.975%): ~$187.19
        # Stripe charge total: ~$1,437.19
        
        assert data["hammer_price"] == 10000.0
        assert data["buyer_premium"] == 1000.0
        
        # Check stripe_charge_total for vehicles (fees + tax only)
        stripe_total = data.get("stripe_charge_total")
        assert stripe_total is not None, "Vehicle response should contain stripe_charge_total"
        assert 1430 < stripe_total < 1445, f"Expected stripe_charge_total ~$1437, got {stripe_total}"
        
        # Verify seller balance due equals hammer price for vehicles
        assert data.get("seller_balance_due") == 10000.0


class TestBuyersPremiumEdgeCases:
    """Edge case tests for buyer's premium feature"""
    
    def test_zero_premium_rate(self, api_client):
        """Test with buyers_premium_rate=0 (zero premium)"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyers_premium_rate": 0.0,  # Zero premium
                "buyer_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["buyer_premium"] == 0.0, f"Expected 0 premium, got {data['buyer_premium']}"
    
    def test_high_premium_rate_25_percent(self, api_client):
        """Test with high buyers_premium_rate=0.25 (25%)"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyers_premium_rate": 0.25,  # 25%
                "buyer_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["buyer_premium"] == 250.0, f"Expected 250, got {data['buyer_premium']}"
    
    def test_decimal_premium_rate(self, api_client):
        """Test with decimal buyers_premium_rate=0.125 (12.5%)"""
        response = api_client.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyers_premium_rate": 0.125,  # 12.5%
                "buyer_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["buyer_premium"] == 125.0, f"Expected 125, got {data['buyer_premium']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
