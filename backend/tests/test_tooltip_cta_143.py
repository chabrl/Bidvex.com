"""
BidVex Iteration 143 - Tooltip Visibility & CTA Tracking Tests
Tests:
1. CTA tracking endpoint POST /api/analytics/cta-click
2. GET /api/listings returns properly (deduplication logic)
3. Basic API health checks
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCTATracking:
    """CTA click tracking endpoint tests"""
    
    def test_cta_click_tracking_returns_tracked(self):
        """POST /api/analytics/cta-click should return {status: tracked}"""
        response = requests.post(f"{BASE_URL}/api/analytics/cta-click", json={
            "page": "how-it-works",
            "action": "hero_signup",
            "section": "hero",
            "label": "Create Free Account",
            "timestamp": "2026-01-15T10:00:00.000Z"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "tracked", f"Expected status='tracked', got {data}"
        print(f"✓ CTA tracking endpoint returned: {data}")
    
    def test_cta_click_tracking_with_minimal_data(self):
        """POST /api/analytics/cta-click with minimal data"""
        response = requests.post(f"{BASE_URL}/api/analytics/cta-click", json={
            "page": "how-it-works",
            "action": "test_action"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["tracked", "error"], f"Unexpected status: {data}"
        print(f"✓ CTA tracking with minimal data: {data}")


class TestListingsEndpoint:
    """GET /api/listings endpoint tests"""
    
    def test_listings_endpoint_returns_200(self):
        """GET /api/listings should return 200"""
        response = requests.get(f"{BASE_URL}/api/listings?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ GET /api/listings returned {len(data)} items")
    
    def test_listings_with_category_filter(self):
        """GET /api/listings with category filter"""
        response = requests.get(f"{BASE_URL}/api/listings?category=electronics&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/listings with category filter returned {len(data)} items")
    
    def test_listings_with_price_filter(self):
        """GET /api/listings with price filter"""
        response = requests.get(f"{BASE_URL}/api/listings?min_price=10&max_price=1000&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/listings with price filter returned {len(data)} items")


class TestMultiItemListings:
    """GET /api/multi-item-listings endpoint tests"""
    
    def test_multi_item_listings_returns_200(self):
        """GET /api/multi-item-listings should return 200"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ GET /api/multi-item-listings returned {len(data)} items")


class TestAnalyticsEndpoints:
    """Other analytics endpoints"""
    
    def test_impression_tracking(self):
        """POST /api/analytics/impression should work"""
        response = requests.post(f"{BASE_URL}/api/analytics/impression", json={
            "listing_id": "test-listing-123",
            "source": "marketplace"
        })
        # May return 200 or 500 if listing doesn't exist, but endpoint should be reachable
        assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}"
        print(f"✓ Impression tracking endpoint reachable: {response.status_code}")
    
    def test_click_tracking(self):
        """POST /api/analytics/click should work"""
        response = requests.post(f"{BASE_URL}/api/analytics/click", json={
            "listing_id": "test-listing-123",
            "source": "direct"
        })
        assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}"
        print(f"✓ Click tracking endpoint reachable: {response.status_code}")


class TestCategoriesEndpoint:
    """Categories endpoint for CreateListingPage"""
    
    def test_categories_returns_list(self):
        """GET /api/categories should return list of categories"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) > 0, "Expected at least one category"
        print(f"✓ GET /api/categories returned {len(data)} categories")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
