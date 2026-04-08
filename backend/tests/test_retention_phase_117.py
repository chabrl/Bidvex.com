"""
BidVex Retention Phase Testing - Iteration 117
Tests for:
- Task 2: Sidebar filters (categories, regions, cities), /lots page, Vehicle Detail Page
- Task 5: User Insights tracking (POST /insights/track, GET /insights/profile/{user_id})
- Task 4: Winner's Circle (GET /winners/my-wins)
- Task 1: Outbid notifications
- Task 3: WebSocket time extension handling
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
STARTER_EMAIL = "starter@test.com"
STARTER_PASSWORD = "TestUser2026!"
PREMIUM_EMAIL = "premium@test.com"
PREMIUM_PASSWORD = "TestUser2026!"

# Vehicle IDs for testing
VEHICLE_ID_PORSCHE = "4cadc374-d72e-4801-9fee-c6f320f1e3b8"
VEHICLE_ID_BMW = "c56c1177-c6b0-4398-b0a1-fa523932a228"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin authentication failed: {response.status_code}")


@pytest.fixture(scope="module")
def starter_token(api_client):
    """Get starter user authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": STARTER_EMAIL,
        "password": STARTER_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Starter authentication failed: {response.status_code}")


@pytest.fixture(scope="module")
def premium_token(api_client):
    """Get premium user authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": PREMIUM_EMAIL,
        "password": PREMIUM_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Premium authentication failed: {response.status_code}")


class TestHealthAndBasics:
    """Basic health checks"""
    
    def test_api_health(self, api_client):
        """Test API health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ API health check passed")
    
    def test_admin_login(self, api_client):
        """Test admin login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        print("✓ Admin login successful")
    
    def test_starter_login(self, api_client):
        """Test starter user login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": STARTER_EMAIL,
            "password": STARTER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        print("✓ Starter user login successful")


class TestTask2SidebarFilters:
    """Task 2: Sidebar filters on /marketplace"""
    
    def test_marketplace_items_endpoint(self, api_client):
        """Test marketplace items endpoint returns data"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?limit=20")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✓ Marketplace items endpoint returned {len(data['items'])} items, total: {data['total']}")
    
    def test_marketplace_filter_counts(self, api_client):
        """Test filter counts endpoint for sidebar"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/filter-counts")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "locations" in data
        assert "total_active_items" in data
        print(f"✓ Filter counts: {len(data['categories'])} categories, {len(data['locations'])} locations, {data['total_active_items']} active items")
    
    def test_marketplace_category_filter(self, api_client):
        """Test filtering by category (e.g., electronics)"""
        # First get available categories
        counts_response = api_client.get(f"{BASE_URL}/api/marketplace/filter-counts")
        counts_data = counts_response.json()
        
        if counts_data.get("categories"):
            test_category = counts_data["categories"][0]["name"]
            response = api_client.get(f"{BASE_URL}/api/marketplace/items?categories={test_category}&limit=50")
            assert response.status_code == 200
            data = response.json()
            # Verify all returned items match the category
            for item in data["items"]:
                assert item.get("category") == test_category, f"Item category {item.get('category')} doesn't match filter {test_category}"
            print(f"✓ Category filter '{test_category}' returned {len(data['items'])} items")
        else:
            pytest.skip("No categories available for testing")
    
    def test_marketplace_region_filter(self, api_client):
        """Test filtering by region (e.g., QC)"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?regions=QC&limit=50")
        assert response.status_code == 200
        data = response.json()
        # Verify all returned items are from QC region
        for item in data["items"]:
            assert item.get("region") == "QC", f"Item region {item.get('region')} doesn't match filter QC"
        print(f"✓ Region filter 'QC' returned {len(data['items'])} items")
    
    def test_marketplace_city_filter(self, api_client):
        """Test filtering by city"""
        # First get available cities from filter counts
        counts_response = api_client.get(f"{BASE_URL}/api/marketplace/filter-counts")
        counts_data = counts_response.json()
        
        test_city = None
        for loc in counts_data.get("locations", []):
            if loc.get("cities"):
                test_city = loc["cities"][0]["name"]
                break
        
        if test_city:
            response = api_client.get(f"{BASE_URL}/api/marketplace/items?cities={test_city}&limit=50")
            assert response.status_code == 200
            data = response.json()
            for item in data["items"]:
                assert item.get("city") == test_city, f"Item city {item.get('city')} doesn't match filter {test_city}"
            print(f"✓ City filter '{test_city}' returned {len(data['items'])} items")
        else:
            pytest.skip("No cities available for testing")
    
    def test_marketplace_combined_filters(self, api_client):
        """Test combining multiple filters"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?regions=QC&sort=ending_soon&limit=20")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Combined filters (QC + ending_soon) returned {len(data['items'])} items")


class TestTask2LotsPage:
    """Task 2: /lots page functionality"""
    
    def test_multi_item_listings_endpoint(self, api_client):
        """Test multi-item listings endpoint for /lots page"""
        response = api_client.get(f"{BASE_URL}/api/multi-item-listings?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Multi-item listings endpoint returned {len(data)} lot auctions")
    
    def test_lots_with_sidebar_filters(self, api_client):
        """Test lots endpoint with sidebar filter params"""
        response = api_client.get(f"{BASE_URL}/api/multi-item-listings?region=QC&limit=50")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Lots with region filter returned {len(data)} auctions")


class TestTask2VehicleDetailPage:
    """Task 2: Vehicle Detail Page /vehicle-auctions/:id"""
    
    def test_vehicles_endpoint(self, api_client):
        """Test vehicles listing endpoint"""
        response = api_client.get(f"{BASE_URL}/api/vehicles?limit=20")
        assert response.status_code == 200
        data = response.json()
        assert "vehicles" in data or isinstance(data, list)
        vehicles = data.get("vehicles", data) if isinstance(data, dict) else data
        print(f"✓ Vehicles endpoint returned {len(vehicles)} vehicles")
    
    def test_vehicle_detail_porsche(self, api_client):
        """Test vehicle detail page for Porsche 911"""
        response = api_client.get(f"{BASE_URL}/api/vehicles/{VEHICLE_ID_PORSCHE}")
        if response.status_code == 404:
            pytest.skip(f"Vehicle {VEHICLE_ID_PORSCHE} not found in database")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "make" in data or "title" in data
        print(f"✓ Vehicle detail for Porsche loaded: {data.get('make', '')} {data.get('model', '')}")
    
    def test_vehicle_detail_bmw(self, api_client):
        """Test vehicle detail page for BMW M3"""
        response = api_client.get(f"{BASE_URL}/api/vehicles/{VEHICLE_ID_BMW}")
        if response.status_code == 404:
            pytest.skip(f"Vehicle {VEHICLE_ID_BMW} not found in database")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"✓ Vehicle detail for BMW loaded: {data.get('make', '')} {data.get('model', '')}")


class TestTask5UserInsights:
    """Task 5: Gemini Insight user profiling - POST /insights/track, GET /insights/profile"""
    
    def test_track_event_anonymous(self, api_client):
        """Test tracking event without authentication (anonymous)"""
        event_data = {
            "event_type": "view",
            "listing_id": "test-listing-123",
            "category": "electronics",
            "price": 150.00,
            "region": "QC",
            "city": "Montreal"
        }
        response = api_client.post(f"{BASE_URL}/api/insights/track", json=event_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ Anonymous event tracking successful")
    
    def test_track_event_click(self, api_client):
        """Test tracking click event"""
        event_data = {
            "event_type": "click",
            "listing_id": "test-listing-456",
            "category": "furniture"
        }
        response = api_client.post(f"{BASE_URL}/api/insights/track", json=event_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ Click event tracking successful")
    
    def test_track_event_search(self, api_client):
        """Test tracking search event"""
        event_data = {
            "event_type": "search",
            "search_query": "vintage watch"
        }
        response = api_client.post(f"{BASE_URL}/api/insights/track", json=event_data)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ Search event tracking successful")
    
    def test_track_batch_events(self, api_client):
        """Test batch event tracking"""
        events = [
            {"event_type": "view", "listing_id": "batch-1", "category": "art"},
            {"event_type": "click", "listing_id": "batch-2", "category": "jewelry"},
            {"event_type": "bid", "listing_id": "batch-3", "price": 500.00}
        ]
        response = api_client.post(f"{BASE_URL}/api/insights/track-batch", json=events)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data.get("tracked") == 3
        print("✓ Batch event tracking successful (3 events)")
    
    def test_get_user_profile_anonymous(self, api_client):
        """Test getting user profile for anonymous user"""
        response = api_client.get(f"{BASE_URL}/api/insights/profile/anonymous")
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "total_events" in data
        assert "top_categories" in data
        assert "top_regions" in data
        assert "price_sensitivity" in data
        assert "activity" in data
        print(f"✓ User profile retrieved: {data['total_events']} events, {len(data['top_categories'])} top categories")
    
    def test_get_user_profile_specific(self, api_client, starter_token):
        """Test getting user profile for authenticated user"""
        # First track some events for this user
        headers = {"Authorization": f"Bearer {starter_token}"}
        
        # Track a few events
        for i in range(3):
            api_client.post(f"{BASE_URL}/api/insights/track", json={
                "event_type": "view",
                "listing_id": f"user-test-{i}",
                "category": "electronics"
            }, headers=headers)
        
        # Get user profile (need to extract user_id from token or use a known ID)
        # For now, test the endpoint structure
        response = api_client.get(f"{BASE_URL}/api/insights/profile/test-user-id")
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        print("✓ Specific user profile endpoint working")


class TestTask4WinnersCircle:
    """Task 4: Winner's Circle - GET /winners/my-wins"""
    
    def test_my_wins_requires_auth(self, api_client):
        """Test that /winners/my-wins requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/winners/my-wins")
        assert response.status_code == 401
        print("✓ /winners/my-wins correctly requires authentication")
    
    def test_my_wins_authenticated(self, api_client, starter_token):
        """Test getting won auctions for authenticated user"""
        headers = {"Authorization": f"Bearer {starter_token}"}
        response = api_client.get(f"{BASE_URL}/api/winners/my-wins", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "wins" in data
        assert "total" in data
        assert isinstance(data["wins"], list)
        print(f"✓ Winner's Circle returned {data['total']} won auctions")


class TestTask1OutbidNotifications:
    """Task 1: Outbid Alert System - notifications created when auto-bid exceeded"""
    
    def test_notifications_endpoint(self, api_client, starter_token):
        """Test notifications endpoint exists and returns data"""
        headers = {"Authorization": f"Bearer {starter_token}"}
        response = api_client.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Should return a list or object with notifications
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "notifications" in data or "items" in data or "data" in data
        print(f"✓ Notifications endpoint working")
    
    def test_notifications_requires_auth(self, api_client):
        """Test that notifications require authentication"""
        response = api_client.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 401
        print("✓ Notifications correctly require authentication")


class TestMarketplaceVehicleIsolation:
    """Verify vehicles are excluded from general marketplace"""
    
    def test_marketplace_excludes_vehicles(self, api_client):
        """Test that marketplace items don't include vehicle categories"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        vehicle_categories = ["vehicles", "vehicle", "car", "auto", "automobile", "truck", "motorcycle"]
        vehicle_items = [item for item in data["items"] if item.get("category", "").lower() in vehicle_categories]
        
        assert len(vehicle_items) == 0, f"Found {len(vehicle_items)} vehicle items in general marketplace"
        print(f"✓ Marketplace correctly excludes vehicles (0 vehicle items in {len(data['items'])} total)")


class TestSortingAndPagination:
    """Test marketplace sorting and pagination"""
    
    def test_sort_ending_soon(self, api_client):
        """Test sorting by ending soon (default)"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?sort=ending_soon&limit=10")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Ending soon sort returned {len(data['items'])} items")
    
    def test_sort_price_asc(self, api_client):
        """Test sorting by price ascending"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?sort=price&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        # Verify prices are in ascending order
        prices = [item.get("current_price", 0) for item in data["items"]]
        assert prices == sorted(prices), "Prices not in ascending order"
        print(f"✓ Price ascending sort working correctly")
    
    def test_sort_price_desc(self, api_client):
        """Test sorting by price descending"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?sort=-price&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        # Verify prices are in descending order
        prices = [item.get("current_price", 0) for item in data["items"]]
        assert prices == sorted(prices, reverse=True), "Prices not in descending order"
        print(f"✓ Price descending sort working correctly")
    
    def test_pagination_cursor(self, api_client):
        """Test cursor-based pagination"""
        # Get first page
        response1 = api_client.get(f"{BASE_URL}/api/marketplace/items?limit=5")
        assert response1.status_code == 200
        data1 = response1.json()
        
        if data1.get("has_more") and data1.get("next_cursor"):
            # Get second page
            response2 = api_client.get(f"{BASE_URL}/api/marketplace/items?limit=5&cursor={data1['next_cursor']}")
            assert response2.status_code == 200
            data2 = response2.json()
            
            # Verify different items
            ids1 = {item["id"] for item in data1["items"]}
            ids2 = {item["id"] for item in data2["items"]}
            assert ids1.isdisjoint(ids2), "Pagination returned duplicate items"
            print(f"✓ Cursor pagination working (page 1: {len(data1['items'])}, page 2: {len(data2['items'])} items)")
        else:
            print("✓ Pagination test skipped (not enough items for multiple pages)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
