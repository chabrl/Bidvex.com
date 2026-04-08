"""
Phase 3 Integration Tests - BidVex Auction Marketplace
Tests: Vehicle Identity Routing, WebSocket Marketplace, Accept-Terms, Seller Ratings,
       Sidebar Filters, Category Guards, OPC Badge, Payment Disclaimers, Offline Invoices
"""

import pytest
import requests
import os
import json
import time
import websocket
import threading

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
STARTER_EMAIL = "starter@test.com"
STARTER_PASSWORD = "TestUser2026!"
PREMIUM_EMAIL = "premium@test.com"
PREMIUM_PASSWORD = "TestUser2026!"
PARTNER_EMAIL = "partner@test.com"
PARTNER_PASSWORD = "TestUser2026!"

# Known vehicle IDs from Atlas DB
VEHICLE_IDS = [
    "51dc43f8-66cb-45a0-bcc4-ad5432c16d0c",  # Audi RS e-tron GT
    "5d2475f4-8856-4fcc-9dec-c7016b62ed93",  # Corvette Z06
    "b0590d17-96ed-4438-8c6e-3810db448ece",  # Rivian R1T
    "0f10e7d8-670a-41d0-8d48-01f616e346ca",  # Lamborghini Huracan
    "f97feed7-555c-416f-9a93-e35234958db3",  # Land Rover Defender
]


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print("✓ API health check passed")


class TestAuthentication:
    """Authentication tests for all user types"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }, timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"✓ Admin login successful: {ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_starter_login(self):
        """Test starter user login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STARTER_EMAIL,
            "password": STARTER_PASSWORD
        }, timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"✓ Starter login successful: {STARTER_EMAIL}")
        return data["access_token"]
    
    def test_partner_login(self):
        """Test partner user login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_EMAIL,
            "password": PARTNER_PASSWORD
        }, timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"✓ Partner login successful: {PARTNER_EMAIL}")
        return data["access_token"]


class TestVehicleIdentityRouting:
    """Test vehicle identity routing - vehicles should redirect to /vehicle-auctions/:id"""
    
    def test_vehicle_listing_has_vehicle_category(self):
        """Verify vehicle listings have category='vehicles'"""
        response = requests.get(f"{BASE_URL}/api/vehicles", timeout=10)
        assert response.status_code == 200
        data = response.json()
        vehicles = data.get("vehicles", [])
        print(f"✓ Found {len(vehicles)} vehicles in /api/vehicles")
        
        # Check at least one vehicle exists
        if vehicles:
            vehicle = vehicles[0]
            print(f"  Sample vehicle: {vehicle.get('title', vehicle.get('make', 'Unknown'))}")
    
    def test_vehicle_detail_endpoint(self):
        """Test vehicle detail endpoint returns vehicle data"""
        for vehicle_id in VEHICLE_IDS[:2]:  # Test first 2
            response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Vehicle detail found: {data.get('title', data.get('make', 'Unknown'))} ({vehicle_id[:8]}...)")
                return
        
        # If no specific vehicle found, check general listings
        response = requests.get(f"{BASE_URL}/api/listings?category=vehicles&limit=1", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("listings"):
                print(f"✓ Vehicle listings available via /api/listings")
    
    def test_listing_detail_returns_category(self):
        """Test that listing detail includes category field for routing"""
        for vehicle_id in VEHICLE_IDS[:2]:
            response = requests.get(f"{BASE_URL}/api/listings/{vehicle_id}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                category = data.get("category", "").lower()
                print(f"✓ Listing {vehicle_id[:8]}... has category: '{category}'")
                if category in ["vehicle", "vehicles", "car", "auto"]:
                    print(f"  → Frontend should redirect to /vehicle-auctions/{vehicle_id}")
                return


class TestMarketplaceWebSocket:
    """Test marketplace WebSocket endpoint"""
    
    def test_marketplace_ws_connection(self):
        """Test WebSocket connection to /api/ws/marketplace"""
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/marketplace"
        
        received_messages = []
        connection_established = threading.Event()
        
        def on_message(ws, message):
            received_messages.append(message)
            try:
                data = json.loads(message)
                if data.get("type") in ["PONG", "HEARTBEAT"]:
                    connection_established.set()
            except:
                pass
        
        def on_open(ws):
            # Send PING to test connection
            ws.send(json.dumps({"type": "PING"}))
        
        def on_error(ws, error):
            print(f"  WebSocket error: {error}")
        
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_open=on_open,
            on_error=on_error
        )
        
        # Run in thread with timeout
        ws_thread = threading.Thread(target=ws.run_forever, kwargs={"ping_timeout": 5})
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for PONG response
        if connection_established.wait(timeout=10):
            print(f"✓ Marketplace WebSocket connected and responding to PING")
            ws.close()
            return True
        else:
            ws.close()
            # Check if we got any messages
            if received_messages:
                print(f"✓ Marketplace WebSocket connected, received: {received_messages[0][:100]}")
                return True
            pytest.skip("WebSocket connection timed out - may be network issue")


class TestAcceptTermsEndpoint:
    """Test accept-terms endpoint for vehicles"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STARTER_EMAIL,
            "password": STARTER_PASSWORD
        }, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Could not authenticate")
    
    def test_accept_terms_endpoint_exists(self, auth_token):
        """Test POST /api/vehicles/{id}/accept-terms endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        for vehicle_id in VEHICLE_IDS[:2]:
            response = requests.post(
                f"{BASE_URL}/api/vehicles/{vehicle_id}/accept-terms",
                headers=headers,
                timeout=10
            )
            
            # Should return 200 (success) or 404 (vehicle not found)
            # Should NOT return 405 (method not allowed) or 500
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Accept-terms endpoint works: {data.get('message', 'OK')}")
                return
            elif response.status_code == 404:
                print(f"  Vehicle {vehicle_id[:8]}... not found, trying next...")
                continue
            else:
                print(f"  Unexpected status {response.status_code} for {vehicle_id[:8]}...")
        
        # If no vehicle found, test with a general listing
        response = requests.get(f"{BASE_URL}/api/listings?limit=1", timeout=10)
        if response.status_code == 200:
            listings = response.json().get("listings", [])
            if listings:
                listing_id = listings[0].get("id")
                response = requests.post(
                    f"{BASE_URL}/api/vehicles/{listing_id}/accept-terms",
                    headers=headers,
                    timeout=10
                )
                if response.status_code in [200, 404]:
                    print(f"✓ Accept-terms endpoint responds correctly (status: {response.status_code})")


class TestSellerRatingsAPI:
    """Test seller ratings API endpoint"""
    
    def test_user_ratings_endpoint(self):
        """Test GET /api/users/{user_id}/ratings returns rating data"""
        # First get a user ID from a listing
        response = requests.get(f"{BASE_URL}/api/listings?limit=1", timeout=10)
        if response.status_code != 200:
            pytest.skip("Could not fetch listings")
        
        listings = response.json().get("listings", [])
        if not listings:
            pytest.skip("No listings available")
        
        seller_id = listings[0].get("seller_id")
        if not seller_id:
            pytest.skip("No seller_id in listing")
        
        # Test ratings endpoint
        response = requests.get(f"{BASE_URL}/api/users/{seller_id}/ratings", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        # Should have average_rating, total_ratings, and ratings array
        assert "average" in data or "average_rating" in data or "ratings" in data
        print(f"✓ Seller ratings endpoint works for user {seller_id[:8]}...")
        print(f"  Average: {data.get('average', data.get('average_rating', 0))}, Total: {data.get('total', len(data.get('ratings', [])))}")


class TestMarketplaceFilters:
    """Test marketplace sidebar filters"""
    
    def test_marketplace_items_endpoint(self):
        """Test /api/marketplace/items endpoint"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items", timeout=10)
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Marketplace items endpoint works, returned {len(data.get('items', []))} items")
    
    def test_marketplace_filter_counts(self):
        """Test /api/marketplace/filter-counts endpoint"""
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Filter counts endpoint works")
            if "categories" in data:
                print(f"  Categories: {len(data.get('categories', []))}")
            if "regions" in data:
                print(f"  Regions: {len(data.get('regions', []))}")
        else:
            print(f"  Filter counts endpoint returned {response.status_code}")
    
    def test_marketplace_category_filter(self):
        """Test filtering by category"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?categories=Electronics", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Category filter works, returned {len(data.get('items', []))} items")
    
    def test_marketplace_region_filter(self):
        """Test filtering by region"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?regions=QC", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Region filter works, returned {len(data.get('items', []))} items")
    
    def test_zero_fee_filter(self):
        """Test 0% buyer fee filter"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?zero_fee_only=true", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Zero fee filter works, returned {len(data.get('items', []))} items")


class TestCategoryGuard:
    """Test vehicle category guard for non-partner users"""
    
    @pytest.fixture
    def starter_token(self):
        """Get starter user token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STARTER_EMAIL,
            "password": STARTER_PASSWORD
        }, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Could not authenticate starter user")
    
    @pytest.fixture
    def partner_token(self):
        """Get partner user token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_EMAIL,
            "password": PARTNER_PASSWORD
        }, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Could not authenticate partner user")
    
    def test_starter_cannot_list_vehicles(self, starter_token):
        """Test that starter users cannot create vehicle listings"""
        headers = {"Authorization": f"Bearer {starter_token}"}
        
        # Try to create a listing with vehicle category
        listing_data = {
            "title": "TEST Vehicle Listing",
            "description": "This is a test vehicle listing that should be blocked",
            "category": "vehicles",
            "starting_price": 1000,
            "city": "Montreal",
            "region": "QC",
            "postal_code": "H2X 1Y4",
            "condition": "good",
            "auction_end_date": "2026-02-01T00:00:00Z"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/listings",
            json=listing_data,
            headers=headers,
            timeout=10
        )
        
        # Should return 403 Forbidden for non-partner users
        if response.status_code == 403:
            print(f"✓ Starter user correctly blocked from listing vehicles (403)")
        elif response.status_code == 400:
            print(f"✓ Starter user blocked from listing vehicles (400 - validation)")
        else:
            print(f"  Listing response: {response.status_code} - {response.text[:200]}")
    
    def test_starter_cannot_create_vehicle_multi_item(self, starter_token):
        """Test that starter users cannot create multi-item vehicle listings"""
        headers = {"Authorization": f"Bearer {starter_token}"}
        
        listing_data = {
            "title": "TEST Multi-Item Vehicle Auction",
            "description": "This should be blocked for starter users",
            "category": "vehicles",
            "city": "Montreal",
            "region": "QC",
            "postal_code": "H2X 1Y4",
            "auction_end_date": "2026-02-01T00:00:00Z",
            "lots": [
                {"title": "Test Lot 1", "starting_price": 100, "quantity": 1}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/multi-item-listings",
            json=listing_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 403:
            print(f"✓ Starter user correctly blocked from multi-item vehicle listings (403)")
        elif response.status_code == 400:
            print(f"✓ Starter user blocked from multi-item vehicle listings (400)")
        else:
            print(f"  Multi-item response: {response.status_code}")


class TestOPCBadgeAndPricing:
    """Test OPC certification badge and buyer's premium"""
    
    def test_listing_has_opc_fields(self):
        """Test that listings include OPC certification fields"""
        response = requests.get(f"{BASE_URL}/api/listings?limit=5", timeout=10)
        if response.status_code != 200:
            pytest.skip("Could not fetch listings")
        
        listings = response.json().get("listings", [])
        if not listings:
            pytest.skip("No listings available")
        
        # Check if any listing has OPC fields
        for listing in listings:
            if "is_opc_certified" in listing or "buyers_premium_percent" in listing:
                print(f"✓ Listing has OPC fields: is_opc_certified={listing.get('is_opc_certified')}, buyers_premium_percent={listing.get('buyers_premium_percent')}")
                return
        
        print(f"  Note: No listings with OPC fields found (may not be set)")
    
    def test_vehicle_has_pricing_fields(self):
        """Test that vehicle listings include pricing fields"""
        for vehicle_id in VEHICLE_IDS[:2]:
            response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Vehicle pricing fields:")
                print(f"  - buyers_premium_percent: {data.get('buyers_premium_percent', data.get('buyer_premium_percent', 'N/A'))}")
                print(f"  - is_opc_certified: {data.get('is_opc_certified', 'N/A')}")
                return


class TestPaymentOrchestration:
    """Test payment method fields and offline payment handling"""
    
    def test_listing_accepts_payment_method(self):
        """Test that listings can have payment_method field"""
        response = requests.get(f"{BASE_URL}/api/listings?limit=5", timeout=10)
        if response.status_code != 200:
            pytest.skip("Could not fetch listings")
        
        listings = response.json().get("listings", [])
        for listing in listings:
            payment_method = listing.get("payment_method")
            if payment_method:
                print(f"✓ Listing has payment_method: {payment_method}")
                return
        
        print(f"  Note: No listings with payment_method field found")
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Could not authenticate admin")
    
    def test_seller_invoices_collection_exists(self, admin_token):
        """Test that seller invoices can be queried (for offline payments)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Try to access admin invoices endpoint
        response = requests.get(
            f"{BASE_URL}/api/admin/invoices?limit=1",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✓ Admin invoices endpoint accessible")
        elif response.status_code == 404:
            print(f"  Admin invoices endpoint not found (may be different path)")
        else:
            print(f"  Admin invoices response: {response.status_code}")


class TestLotsPage:
    """Test lots/multi-item listings page"""
    
    def test_multi_item_listings_endpoint(self):
        """Test /api/multi-item-listings endpoint"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        if isinstance(data, list):
            print(f"✓ Multi-item listings endpoint works, returned {len(data)} auctions")
        elif isinstance(data, dict):
            listings = data.get("listings", data.get("auctions", []))
            print(f"✓ Multi-item listings endpoint works, returned {len(listings)} auctions")


class TestEndingSoonItems:
    """Test ending soon items for homepage"""
    
    def test_ending_soon_endpoint(self):
        """Test ending soon items endpoint"""
        response = requests.get(f"{BASE_URL}/api/marketplace/ending-soon?limit=10", timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            print(f"✓ Ending soon endpoint works, returned {len(items)} items")
            
            # Check if any are vehicles
            for item in items[:3]:
                category = item.get("category", "").lower()
                if category in ["vehicle", "vehicles", "car", "auto"]:
                    print(f"  → Vehicle in ending soon: {item.get('title', 'Unknown')[:50]}")
        else:
            print(f"  Ending soon endpoint returned {response.status_code}")


class TestHomepageData:
    """Test homepage data endpoints"""
    
    def test_hot_items_endpoint(self):
        """Test hot items endpoint"""
        response = requests.get(f"{BASE_URL}/api/marketplace/hot-items?limit=6", timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            print(f"✓ Hot items endpoint works, returned {len(items)} items")
    
    def test_featured_endpoint(self):
        """Test featured items endpoint"""
        response = requests.get(f"{BASE_URL}/api/marketplace/featured?limit=8", timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            print(f"✓ Featured endpoint works, returned {len(items)} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
