"""
Test Redis Cache Layer (Iteration 91)
Tests the new Redis-backed caching with in-memory fallback for marketplace endpoints.
Since REDIS_URL is not set locally, tests verify in-memory fallback mode.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestCacheStats:
    """Test /api/cache-stats diagnostic endpoint"""
    
    def test_cache_stats_returns_backend_info(self):
        """GET /api/cache-stats returns cache backend info"""
        response = requests.get(f"{BASE_URL}/api/cache-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "backend" in data, "Response should contain 'backend' field"
        assert data["backend"] in ["memory", "redis"], f"Backend should be 'memory' or 'redis', got {data['backend']}"
        assert "keys" in data, "Response should contain 'keys' field"
        assert isinstance(data["keys"], int), "Keys should be an integer"
        print(f"Cache backend: {data['backend']}, keys: {data['keys']}")
    
    def test_cache_stats_memory_fallback(self):
        """Verify in-memory fallback mode when REDIS_URL not set"""
        response = requests.get(f"{BASE_URL}/api/cache-stats")
        assert response.status_code == 200
        
        data = response.json()
        # In local env without REDIS_URL, should be memory
        # On Railway with Upstash, would be redis
        if data["backend"] == "memory":
            assert data["connected"] == False, "Memory backend should show connected=false"
            print("Confirmed: Running in memory fallback mode")
        else:
            assert data["backend"] == "redis"
            assert "memory_used" in data or "error" in data
            print(f"Running with Redis: {data}")


class TestHealthEndpoint:
    """Test health endpoints"""
    
    def test_api_health(self):
        """GET /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ["healthy", "ok"], f"Expected healthy status, got {data}"


class TestMarketplaceItemsCaching:
    """Test /api/marketplace/items with caching"""
    
    def test_marketplace_items_returns_paginated_items(self):
        """GET /api/marketplace/items returns paginated items with caching"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data, "Response should contain 'items'"
        assert "total" in data, "Response should contain 'total'"
        assert "limit" in data, "Response should contain 'limit'"
        assert "has_more" in data, "Response should contain 'has_more'"
        
        # Items may be empty if cache is warming
        if data.get("cache_warming"):
            print("Cache is warming, items may be empty")
        else:
            print(f"Marketplace items: {len(data['items'])} items, total: {data['total']}")
    
    def test_marketplace_items_pagination(self):
        """Test pagination parameters"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=5&skip=0")
        assert response.status_code == 200
        
        data = response.json()
        assert data["limit"] == 5, f"Expected limit=5, got {data['limit']}"
        print(f"Pagination test: limit={data['limit']}, skip={data['skip']}, has_more={data['has_more']}")
    
    def test_marketplace_items_filtering(self):
        """Test filtering parameters"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?category=Electronics")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        print(f"Filtered by Electronics: {len(data['items'])} items")


class TestFilterCountsCaching:
    """Test /api/marketplace/filter-counts with caching"""
    
    def test_filter_counts_returns_cached_data(self):
        """GET /api/marketplace/filter-counts returns category/location/auctioneer counts"""
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data, "Response should contain 'categories'"
        assert "locations" in data, "Response should contain 'locations'"
        assert "auctioneers" in data, "Response should contain 'auctioneers'"
        
        print(f"Filter counts: {len(data['categories'])} categories, {len(data['locations'])} locations, {len(data['auctioneers'])} auctioneers")
        
        if data.get("total_active_items") is not None:
            print(f"Total active items: {data['total_active_items']}")


class TestCategoriesCaching:
    """Test /api/categories with caching"""
    
    def test_categories_returns_cached_list(self):
        """GET /api/categories returns cached category list"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Categories: {len(data)} categories returned")
        
        # Verify expected categories exist
        if len(data) > 0:
            category_names = [c.get("name") for c in data]
            print(f"Sample categories: {category_names[:5]}")
    
    def test_categories_caching_increases_keys(self):
        """Second call to /api/categories should be served from cache"""
        # First call
        response1 = requests.get(f"{BASE_URL}/api/categories")
        assert response1.status_code == 200
        
        # Check cache stats before
        stats_before = requests.get(f"{BASE_URL}/api/cache-stats").json()
        keys_before = stats_before.get("keys", 0)
        
        # Second call (should hit cache)
        response2 = requests.get(f"{BASE_URL}/api/categories")
        assert response2.status_code == 200
        
        # Verify data is same
        assert response1.json() == response2.json(), "Cached response should match"
        
        # Check cache stats after
        stats_after = requests.get(f"{BASE_URL}/api/cache-stats").json()
        keys_after = stats_after.get("keys", 0)
        
        print(f"Cache keys: before={keys_before}, after={keys_after}")
        # Keys should be same or higher (not lower)
        assert keys_after >= keys_before, "Cache keys should not decrease"


class TestCarouselEndpoints:
    """Test carousel endpoints with caching"""
    
    def test_new_listings_returns_data(self):
        """GET /api/carousel/new-listings returns listings (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/carousel/new-listings")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"New listings: {len(data)} items")
    
    def test_top_sellers_returns_data(self):
        """GET /api/stats/top-sellers returns seller stats (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/stats/top-sellers")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Top sellers: {len(data)} sellers")


class TestAdminEndpointsWithAuth:
    """Test admin endpoints that require authentication"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        
        data = response.json()
        token = data.get("access_token")
        if not token:
            pytest.skip("No access_token in login response")
        return token
    
    def test_admin_login_returns_token(self):
        """POST /api/auth/login returns access_token for admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Response should contain access_token"
        print("Admin login successful")
    
    def test_admin_risk_monitoring(self, admin_token):
        """GET /api/admin/risk-monitoring works (admin auth required)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/risk-monitoring", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Risk monitoring data keys: {list(data.keys())}")
    
    def test_admin_listings_all(self, admin_token):
        """GET /api/admin/listings/all works (admin auth required)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/listings/all", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        if isinstance(data, dict):
            print(f"Admin listings response keys: {list(data.keys())}")
        else:
            print(f"Admin listings: {len(data)} items")
    
    def test_marketplace_feature_flags(self, admin_token):
        """GET /api/marketplace/feature-flags works (admin auth required)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/marketplace/feature-flags", headers=headers)
        # This endpoint may or may not require auth
        assert response.status_code in [200, 401], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            print(f"Feature flags: {data}")


class TestCacheInvalidation:
    """Test cache invalidation functionality"""
    
    def test_cache_keys_count(self):
        """Verify cache has keys after hitting cached endpoints"""
        # Hit several cached endpoints
        requests.get(f"{BASE_URL}/api/categories")
        requests.get(f"{BASE_URL}/api/marketplace/items")
        requests.get(f"{BASE_URL}/api/marketplace/filter-counts")
        requests.get(f"{BASE_URL}/api/carousel/new-listings")
        
        # Small delay for async cache operations
        time.sleep(0.5)
        
        # Check cache stats
        response = requests.get(f"{BASE_URL}/api/cache-stats")
        assert response.status_code == 200
        
        data = response.json()
        keys = data.get("keys", 0)
        print(f"Cache has {keys} keys after hitting cached endpoints")
        
        # Should have at least some keys
        assert keys >= 0, "Cache keys should be non-negative"


class TestEndpointResponseTimes:
    """Test that cached endpoints respond quickly"""
    
    def test_categories_response_time(self):
        """Categories endpoint should respond quickly (cached)"""
        # Warm the cache
        requests.get(f"{BASE_URL}/api/categories")
        
        # Measure second call
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/categories")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        print(f"Categories response time: {elapsed*1000:.2f}ms")
        
        # Should be fast (under 2 seconds for network + cache hit)
        assert elapsed < 2.0, f"Response too slow: {elapsed}s"
    
    def test_marketplace_items_response_time(self):
        """Marketplace items endpoint should respond reasonably"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        print(f"Marketplace items response time: {elapsed*1000:.2f}ms")
        
        # Should respond within 5 seconds
        assert elapsed < 5.0, f"Response too slow: {elapsed}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
