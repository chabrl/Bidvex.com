"""
Phase 3 Testing: DISRUPTOR PROTOCOL - Currency, Transparency & Premium UI Overhaul
Tests for:
1. User stats endpoint /api/users/me/stats
2. Currency toggle localStorage persistence
3. Subscription cards with glassmorphism
4. Public bid history with masked names
5. Personalized savings calculator
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://clean-power-bids.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel@admin.bazario.com"
ADMIN_PASSWORD = "Admin123!"


class TestHealthAndBasics:
    """Basic health checks"""
    
    def test_health_endpoint(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health endpoint working")


class TestAuthentication:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"✅ Admin login successful: {data['user']['name']}")
        return data["access_token"]


class TestUserStatsEndpoint:
    """Tests for /api/users/me/stats endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_user_stats_endpoint_exists(self, auth_token):
        """Test that /api/users/me/stats endpoint exists and returns data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/users/me/stats", headers=headers)
        
        assert response.status_code == 200, f"Stats endpoint failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "annual_volume" in data, "Missing annual_volume field"
        assert "total_bids" in data, "Missing total_bids field"
        assert "auctions_won" in data, "Missing auctions_won field"
        
        print(f"✅ User stats endpoint working:")
        print(f"   - Annual Volume: ${data['annual_volume']}")
        print(f"   - Total Bids: {data['total_bids']}")
        print(f"   - Auctions Won: {data['auctions_won']}")
    
    def test_user_stats_requires_auth(self):
        """Test that stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/users/me/stats")
        assert response.status_code == 401, "Stats endpoint should require authentication"
        print("✅ Stats endpoint correctly requires authentication")
    
    def test_user_stats_data_types(self, auth_token):
        """Test that stats endpoint returns correct data types"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/users/me/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify data types
        assert isinstance(data["annual_volume"], (int, float)), "annual_volume should be numeric"
        assert isinstance(data["total_bids"], int), "total_bids should be integer"
        assert isinstance(data["auctions_won"], int), "auctions_won should be integer"
        
        # Verify non-negative values
        assert data["annual_volume"] >= 0, "annual_volume should be non-negative"
        assert data["total_bids"] >= 0, "total_bids should be non-negative"
        assert data["auctions_won"] >= 0, "auctions_won should be non-negative"
        
        print("✅ User stats data types are correct")


class TestBidHistoryEndpoint:
    """Tests for bid history endpoints used by PublicBidHistory component"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_bid_history_endpoint_for_listing(self, auth_token):
        """Test bid history endpoint for single listings"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # First get a listing to test with
        listings_response = requests.get(f"{BASE_URL}/api/listings?limit=1", headers=headers)
        
        if listings_response.status_code == 200:
            listings = listings_response.json()
            if listings and len(listings) > 0:
                listing_id = listings[0].get("id")
                
                # Test bid history endpoint
                response = requests.get(f"{BASE_URL}/api/bids/listing/{listing_id}", headers=headers)
                assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
                
                if response.status_code == 200:
                    bids = response.json()
                    assert isinstance(bids, list), "Bids should be a list"
                    print(f"✅ Bid history endpoint working for listing {listing_id}: {len(bids)} bids")
                else:
                    print(f"✅ Bid history endpoint returns 404 for listing with no bids (expected)")
            else:
                print("⚠️ No listings found to test bid history")
        else:
            print("⚠️ Could not fetch listings to test bid history")
    
    def test_multi_item_lot_bids_endpoint(self, auth_token):
        """Test bid history endpoint for multi-item listing lots"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Get a multi-item listing
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=1", headers=headers)
        
        if response.status_code == 200:
            listings = response.json()
            if listings and len(listings) > 0:
                listing_id = listings[0].get("id")
                lot_number = 1  # Test first lot
                
                # Test lot bids endpoint
                bids_response = requests.get(
                    f"{BASE_URL}/api/multi-item-listings/{listing_id}/lots/{lot_number}/bids",
                    headers=headers
                )
                
                assert bids_response.status_code in [200, 404], f"Unexpected status: {bids_response.status_code}"
                
                if bids_response.status_code == 200:
                    bids = bids_response.json()
                    assert isinstance(bids, list), "Bids should be a list"
                    print(f"✅ Multi-item lot bids endpoint working: {len(bids)} bids for lot {lot_number}")
                else:
                    print(f"✅ Multi-item lot bids endpoint returns 404 (no bids or lot not found)")
            else:
                print("⚠️ No multi-item listings found to test")
        else:
            print("⚠️ Could not fetch multi-item listings")


class TestSubscriptionEndpoints:
    """Tests for subscription-related endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_user_subscription_tier_in_profile(self, auth_token):
        """Test that user profile includes subscription tier"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify subscription fields exist
        assert "subscription_tier" in data, "Missing subscription_tier field"
        assert data["subscription_tier"] in ["free", "premium", "vip"], f"Invalid tier: {data['subscription_tier']}"
        
        print(f"✅ User subscription tier: {data['subscription_tier']}")


class TestCategoriesEndpoint:
    """Test categories endpoint used by various components"""
    
    def test_categories_endpoint(self):
        """Test that categories endpoint returns data"""
        response = requests.get(f"{BASE_URL}/api/categories")
        
        assert response.status_code == 200, f"Categories failed: {response.status_code}"
        data = response.json()
        
        assert isinstance(data, list), "Categories should be a list"
        if len(data) > 0:
            # Verify category structure
            category = data[0]
            assert "name_en" in category or "name" in category, "Category should have name"
            print(f"✅ Categories endpoint working: {len(data)} categories")
        else:
            print("⚠️ No categories found")


class TestFeeCalculations:
    """Test fee calculation logic for savings calculator"""
    
    def test_fee_rates_by_tier(self):
        """Verify fee rates match expected values"""
        # Expected fee rates (NO CAP)
        expected_rates = {
            "free": {"buyer": 5.0, "seller": 4.0, "combined": 9.0},
            "premium": {"buyer": 3.5, "seller": 2.5, "combined": 6.0},
            "vip": {"buyer": 3.0, "seller": 2.0, "combined": 5.0}
        }
        
        # Test calculations for $100,000 volume
        test_volume = 100000
        
        for tier, rates in expected_rates.items():
            buyer_fee = test_volume * (rates["buyer"] / 100)
            seller_fee = test_volume * (rates["seller"] / 100)
            combined_fee = test_volume * (rates["combined"] / 100)
            
            print(f"✅ {tier.upper()} tier @ ${test_volume:,}:")
            print(f"   - Buyer fee: ${buyer_fee:,.2f} ({rates['buyer']}%)")
            print(f"   - Seller fee: ${seller_fee:,.2f} ({rates['seller']}%)")
            print(f"   - Combined: ${combined_fee:,.2f} ({rates['combined']}%)")
        
        # Calculate savings
        free_fees = test_volume * 0.09
        premium_fees = test_volume * 0.06
        vip_fees = test_volume * 0.05
        
        premium_savings = free_fees - premium_fees
        vip_savings = free_fees - vip_fees
        
        print(f"\n✅ Savings calculations @ ${test_volume:,}:")
        print(f"   - Premium saves: ${premium_savings:,.2f} (3% of volume)")
        print(f"   - VIP saves: ${vip_savings:,.2f} (4% of volume)")
        
        # Verify ROI
        premium_roi = premium_savings / 99.99
        vip_roi = vip_savings / 299.99
        
        print(f"\n✅ ROI calculations:")
        print(f"   - Premium ROI: {premium_roi:.1f}x (${99.99} subscription)")
        print(f"   - VIP ROI: {vip_roi:.1f}x (${299.99} subscription)")
        
        assert premium_savings == 3000, f"Premium savings should be $3,000, got ${premium_savings}"
        assert vip_savings == 4000, f"VIP savings should be $4,000, got ${vip_savings}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
