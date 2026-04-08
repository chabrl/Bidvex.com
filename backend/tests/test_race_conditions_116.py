"""
Test Suite for Iteration 116: Race Conditions & Logic Bugs
Tests:
1. Hard Stop - reject bids after auction ends with 403
2. WebSocket timer sync keys for anti-sniping extensions
3. Auto-Bid Bot for Premium/VIP/Partner users
4. Vehicle vs Marketplace category isolation
5. Verify bulk listings (10 vehicles + 10 general)
6. Login verification for test users
7. Quick Bid single-item detection
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com')

# Test credentials from test_credentials.md
TEST_USERS = {
    "admin": {"email": "charbeladmin@bidvex.com", "password": "Admin123!"},
    "starter": {"email": "starter@test.com", "password": "TestUser2026!"},
    "premium": {"email": "premium@test.com", "password": "TestUser2026!"},
    "partner": {"email": "partner@test.com", "password": "TestUser2026!"},
}


class TestAuthentication:
    """Test login for all test users"""
    
    def test_admin_login(self):
        """Admin login should succeed"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["admin"]["email"],
            "password": TEST_USERS["admin"]["password"]
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"✓ Admin login successful")
    
    def test_starter_login(self):
        """Starter (free tier) user login should succeed"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["starter"]["email"],
            "password": TEST_USERS["starter"]["password"]
        })
        assert response.status_code == 200, f"Starter login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"✓ Starter user login successful")
    
    def test_premium_login(self):
        """Premium tier user login should succeed"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["premium"]["email"],
            "password": TEST_USERS["premium"]["password"]
        })
        assert response.status_code == 200, f"Premium login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"✓ Premium user login successful")
    
    def test_partner_login(self):
        """Partner tier user login should succeed"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["partner"]["email"],
            "password": TEST_USERS["partner"]["password"]
        })
        assert response.status_code == 200, f"Partner login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"✓ Partner user login successful")


class TestHardStopBidRejection:
    """Task 1: POST /api/bids on ended listing should return 403"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["admin"]["email"],
            "password": TEST_USERS["admin"]["password"]
        })
        return response.json().get("access_token")
    
    @pytest.fixture
    def starter_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["starter"]["email"],
            "password": TEST_USERS["starter"]["password"]
        })
        return response.json().get("access_token")
    
    def test_bid_on_ended_auction_returns_403(self, admin_token, starter_token):
        """
        Create a listing with auction_end_date in the past but status='active',
        then attempt to bid - should get 403 'Auction has already ended'
        """
        # First, create a test listing with past end date
        past_date = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        listing_data = {
            "title": "TEST_HardStop_EndedAuction",
            "description": "Test listing for hard stop validation",
            "category": "electronics",
            "condition": "new",
            "starting_price": 10.0,
            "auction_end_date": past_date,
            "images": ["https://example.com/test.jpg"]
        }
        
        # Create listing as admin
        create_response = requests.post(
            f"{BASE_URL}/api/listings",
            json=listing_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if create_response.status_code != 200:
            # Try to find an existing ended listing
            marketplace_response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=50")
            items = marketplace_response.json().get("items", [])
            
            # Find any listing with past auction_end_date
            ended_listing = None
            now = datetime.now(timezone.utc)
            for item in items:
                end_date_str = item.get("auction_end_date")
                if end_date_str:
                    try:
                        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                        if end_date < now and item.get("lot_number") is None:
                            ended_listing = item
                            break
                    except:
                        pass
            
            if not ended_listing:
                pytest.skip("Could not create or find an ended listing for testing")
            
            listing_id = ended_listing["id"]
        else:
            listing_id = create_response.json().get("id")
        
        # Attempt to bid on the ended listing
        bid_response = requests.post(
            f"{BASE_URL}/api/bids",
            json={"listing_id": listing_id, "amount": 15.0},
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        
        # Should get 403 with "Auction has already ended"
        assert bid_response.status_code == 403, f"Expected 403, got {bid_response.status_code}: {bid_response.text}"
        detail = bid_response.json().get("detail", "")
        assert "ended" in detail.lower() or "auction" in detail.lower(), f"Expected 'ended' in error message, got: {detail}"
        print(f"✓ Hard Stop working: Bid on ended auction correctly rejected with 403")


class TestAutoBidBot:
    """Task 3: Auto-Bid Bot for Premium/VIP/Partner users"""
    
    @pytest.fixture
    def premium_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["premium"]["email"],
            "password": TEST_USERS["premium"]["password"]
        })
        return response.json().get("access_token")
    
    @pytest.fixture
    def starter_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["starter"]["email"],
            "password": TEST_USERS["starter"]["password"]
        })
        return response.json().get("access_token")
    
    @pytest.fixture
    def partner_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USERS["partner"]["email"],
            "password": TEST_USERS["partner"]["password"]
        })
        return response.json().get("access_token")
    
    def test_free_tier_cannot_setup_auto_bid(self, starter_token):
        """Task 3b: Free/Starter tier user should get 403 when trying to set up auto-bid"""
        # Get an active listing
        marketplace_response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        items = marketplace_response.json().get("items", [])
        
        # Find a single-item listing (not multi-item lot)
        single_item = None
        for item in items:
            if item.get("lot_number") is None and item.get("auction_id") is None:
                single_item = item
                break
        
        if not single_item:
            pytest.skip("No single-item listing found for auto-bid test")
        
        listing_id = single_item["id"]
        
        # Attempt to setup auto-bid as free tier user
        response = requests.post(
            f"{BASE_URL}/api/bids/auto-bid",
            params={"listing_id": listing_id, "max_bid": 200.0},
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        
        assert response.status_code == 403, f"Expected 403 for free tier, got {response.status_code}: {response.text}"
        detail = response.json().get("detail", "")
        assert "premium" in detail.lower() or "upgrade" in detail.lower(), f"Expected premium upgrade message, got: {detail}"
        print(f"✓ Free tier correctly blocked from auto-bid with 403")
    
    def test_premium_can_setup_auto_bid(self, premium_token):
        """Premium user should be able to setup auto-bid"""
        # Get an active listing
        marketplace_response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        items = marketplace_response.json().get("items", [])
        
        # Find a single-item listing
        single_item = None
        for item in items:
            if item.get("lot_number") is None and item.get("auction_id") is None:
                single_item = item
                break
        
        if not single_item:
            pytest.skip("No single-item listing found for auto-bid test")
        
        listing_id = single_item["id"]
        current_price = single_item.get("current_price", single_item.get("starting_price", 10))
        
        # Setup auto-bid as premium user
        response = requests.post(
            f"{BASE_URL}/api/bids/auto-bid",
            params={"listing_id": listing_id, "max_bid": current_price + 100},
            headers={"Authorization": f"Bearer {premium_token}"}
        )
        
        # Should succeed (200) or already have auto-bid
        assert response.status_code in [200, 201], f"Expected 200/201 for premium, got {response.status_code}: {response.text}"
        data = response.json()
        assert "auto_bid_id" in data or "message" in data, f"Expected auto_bid_id or message in response"
        print(f"✓ Premium user can setup auto-bid successfully")
    
    def test_partner_can_setup_auto_bid(self, partner_token):
        """Partner user should be able to setup auto-bid"""
        # Get an active listing
        marketplace_response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        items = marketplace_response.json().get("items", [])
        
        # Find a single-item listing
        single_item = None
        for item in items:
            if item.get("lot_number") is None and item.get("auction_id") is None:
                single_item = item
                break
        
        if not single_item:
            pytest.skip("No single-item listing found for auto-bid test")
        
        listing_id = single_item["id"]
        current_price = single_item.get("current_price", single_item.get("starting_price", 10))
        
        # Setup auto-bid as partner user
        response = requests.post(
            f"{BASE_URL}/api/bids/auto-bid",
            params={"listing_id": listing_id, "max_bid": current_price + 150},
            headers={"Authorization": f"Bearer {partner_token}"}
        )
        
        # Should succeed
        assert response.status_code in [200, 201], f"Expected 200/201 for partner, got {response.status_code}: {response.text}"
        print(f"✓ Partner user can setup auto-bid successfully")


class TestVehicleMarketplaceIsolation:
    """Task 4: Vehicle vs Marketplace category isolation"""
    
    def test_marketplace_excludes_vehicles(self):
        """Task 4: GET /api/marketplace/items should return ZERO items with category='vehicles'"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=100")
        assert response.status_code == 200, f"Marketplace request failed: {response.text}"
        
        data = response.json()
        items = data.get("items", [])
        
        # Check that no items have vehicle categories
        vehicle_categories = ["vehicles", "vehicle", "car", "auto", "automobile", "truck", "motorcycle"]
        vehicle_items = [item for item in items if item.get("category", "").lower() in vehicle_categories]
        
        assert len(vehicle_items) == 0, f"Found {len(vehicle_items)} vehicle items in marketplace: {[i.get('title') for i in vehicle_items]}"
        print(f"✓ Marketplace correctly excludes vehicles (0 vehicle items found in {len(items)} total items)")
    
    def test_vehicles_endpoint_returns_vehicles(self):
        """Task 4b: GET /api/vehicles should return vehicle-category items"""
        response = requests.get(f"{BASE_URL}/api/vehicles?page=1&limit=50")
        assert response.status_code == 200, f"Vehicles request failed: {response.text}"
        
        data = response.json()
        vehicles = data.get("vehicles", [])
        total = data.get("total", 0)
        
        print(f"✓ Vehicles endpoint returned {len(vehicles)} vehicles (total: {total})")
        
        # Verify at least some vehicles exist
        if total > 0:
            # Check that returned items are actually vehicles
            for v in vehicles[:5]:  # Check first 5
                category = v.get("category", "").lower()
                source = v.get("source", "vehicle_listings")
                # Either from vehicle_listings collection or has vehicle category
                assert source == "listings" or category in ["vehicles", "vehicle", "car", "auto", ""], \
                    f"Non-vehicle item in vehicles endpoint: {v.get('title')}"
        
        return total


class TestBulkListings:
    """Task 5: Verify at least 10 vehicle listings and 10 general listings exist"""
    
    def test_minimum_vehicle_listings(self):
        """Verify at least 10 vehicle listings exist and are active"""
        response = requests.get(f"{BASE_URL}/api/vehicles?page=1&limit=50")
        assert response.status_code == 200, f"Vehicles request failed: {response.text}"
        
        data = response.json()
        total = data.get("total", 0)
        
        assert total >= 10, f"Expected at least 10 vehicle listings, found {total}"
        print(f"✓ Found {total} vehicle listings (minimum 10 required)")
    
    def test_minimum_general_listings(self):
        """Verify at least 10 general (non-vehicle) listings exist and are active"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=50")
        assert response.status_code == 200, f"Marketplace request failed: {response.text}"
        
        data = response.json()
        total = data.get("total", 0)
        items = data.get("items", [])
        
        # Count non-vehicle items
        vehicle_categories = ["vehicles", "vehicle", "car", "auto", "automobile", "truck", "motorcycle"]
        general_items = [item for item in items if item.get("category", "").lower() not in vehicle_categories]
        
        assert len(general_items) >= 10, f"Expected at least 10 general listings, found {len(general_items)}"
        print(f"✓ Found {len(general_items)} general listings (minimum 10 required)")


class TestWebSocketBroadcastKeys:
    """Task 2: Verify WebSocket BID_UPDATE message contains anti-sniping extension keys"""
    
    def test_broadcast_data_structure_in_code(self):
        """
        Verify the broadcast_data structure in auctions_bids.py contains required keys.
        This is a code review test - actual WebSocket testing requires integration test.
        """
        # Read the auctions_bids.py file to verify the broadcast_data structure
        import os
        bids_file = "/app/backend/routes/auctions_bids.py"
        
        if os.path.exists(bids_file):
            with open(bids_file, 'r') as f:
                content = f.read()
            
            # Check for required keys in broadcast_data
            required_keys = [
                "time_extended",
                "new_auction_end",
                "new_auction_end_epoch",
                "server_time_epoch"
            ]
            
            for key in required_keys:
                assert f"'{key}'" in content or f'"{key}"' in content, \
                    f"Missing key '{key}' in broadcast_data structure"
            
            print(f"✓ All required WebSocket broadcast keys found in code: {required_keys}")
        else:
            pytest.skip("auctions_bids.py not found")
    
    def test_ws_manager_broadcast_structure(self):
        """Verify ws_managers.py includes anti-sniping fields in BID_UPDATE"""
        import os
        ws_file = "/app/backend/ws_managers.py"
        
        if os.path.exists(ws_file):
            with open(ws_file, 'r') as f:
                content = f.read()
            
            # Check for required keys in broadcast_bid_update
            required_keys = [
                "time_extended",
                "new_auction_end",
                "new_auction_end_epoch",
                "server_time_epoch"
            ]
            
            for key in required_keys:
                assert f"'{key}'" in content or f'"{key}"' in content, \
                    f"Missing key '{key}' in ws_managers broadcast"
            
            print(f"✓ All required WebSocket keys found in ws_managers.py")
        else:
            pytest.skip("ws_managers.py not found")


class TestQuickBidSingleItemDetection:
    """Test that Quick Bid correctly detects single vs multi-item listings"""
    
    def test_marketplace_items_have_correct_structure(self):
        """Verify marketplace items have auction_id and lot_number for detection"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=20")
        assert response.status_code == 200
        
        items = response.json().get("items", [])
        
        single_items = []
        multi_items = []
        
        for item in items:
            auction_id = item.get("auction_id")
            lot_number = item.get("lot_number")
            
            if auction_id and lot_number is not None:
                multi_items.append(item)
            else:
                single_items.append(item)
        
        print(f"✓ Found {len(single_items)} single-item listings and {len(multi_items)} multi-item lots")
        print(f"  Single items use /api/bids endpoint")
        print(f"  Multi-item lots use /api/multi-item-listings/{{auction_id}}/lots/{{lot_number}}/bid")
        
        # Verify structure is correct for detection
        if single_items:
            item = single_items[0]
            assert item.get("auction_id") is None or item.get("lot_number") is None, \
                "Single item should have null auction_id or lot_number"
        
        if multi_items:
            item = multi_items[0]
            assert item.get("auction_id") is not None and item.get("lot_number") is not None, \
                "Multi-item lot should have both auction_id and lot_number"


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_health_endpoint(self):
        """API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ API health check passed")
    
    def test_marketplace_endpoint(self):
        """Marketplace endpoint accessible"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=5")
        assert response.status_code == 200
        print("✓ Marketplace endpoint accessible")
    
    def test_vehicles_endpoint(self):
        """Vehicles endpoint accessible"""
        response = requests.get(f"{BASE_URL}/api/vehicles?page=1&limit=5")
        assert response.status_code == 200
        print("✓ Vehicles endpoint accessible")
    
    def test_bids_endpoint_requires_auth(self):
        """Bids endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/bids", json={"listing_id": "test", "amount": 10})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Bids endpoint correctly requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
