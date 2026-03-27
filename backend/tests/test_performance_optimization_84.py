"""
Performance Optimization Tests - Iteration 84
Tests for:
- Health endpoint response time
- Subscription plans caching (was 11s, now <1s)
- Marketplace items endpoint (was 502 timeout, now <2s)
- Multi-item listings endpoint
- Filter counts endpoint
- X-Response-Time header presence
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com')


class TestHealthEndpoint:
    """Health endpoint tests - should respond under 1s"""
    
    def test_health_returns_200(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health endpoint returned 200 with status: {data.get('status')}")
    
    def test_health_response_time_under_1s(self):
        """GET /api/health responds under 1 second"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"Health endpoint took {elapsed:.2f}s, expected <1s"
        print(f"✓ Health endpoint responded in {elapsed:.3f}s")
    
    def test_health_has_response_time_header(self):
        """GET /api/health has X-Response-Time header"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert response.status_code == 200
        assert "x-response-time" in response.headers, "Missing X-Response-Time header"
        print(f"✓ X-Response-Time header present: {response.headers.get('x-response-time')}")


class TestSubscriptionPlans:
    """Subscription plans tests - was 11s, now should be <1s from cache"""
    
    def test_subscription_plans_returns_200(self):
        """GET /api/subscription-plans returns 200"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "plans" in data
        print(f"✓ Subscription plans returned {len(data.get('plans', []))} plans")
    
    def test_subscription_plans_response_time_under_1s(self):
        """GET /api/subscription-plans responds under 1 second (was 11s)"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/subscription-plans", timeout=10)
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"Subscription plans took {elapsed:.2f}s, expected <1s (was 11s)"
        print(f"✓ Subscription plans responded in {elapsed:.3f}s (was 11s)")
    
    def test_subscription_plans_has_required_fields(self):
        """Subscription plans have required fields"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans", timeout=10)
        assert response.status_code == 200
        data = response.json()
        plans = data.get("plans", [])
        assert len(plans) >= 3, "Expected at least 3 plans (free, premium, vip)"
        
        for plan in plans:
            assert "plan_id" in plan
            assert "name" in plan
            assert "price_monthly" in plan
            assert "price_yearly" in plan
            assert "features" in plan
        print(f"✓ All {len(plans)} plans have required fields")


class TestMarketplaceItems:
    """Marketplace items tests - was 502 timeout, now should be <2s"""
    
    def test_marketplace_items_returns_200(self):
        """GET /api/marketplace/items returns 200"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=20", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✓ Marketplace items returned {len(data.get('items', []))} items, total: {data.get('total')}")
    
    def test_marketplace_items_response_time_under_2s(self):
        """GET /api/marketplace/items responds under 2 seconds (was 502 timeout)"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=20", timeout=15)
        elapsed = time.time() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"Marketplace items took {elapsed:.2f}s, expected <2s"
        print(f"✓ Marketplace items responded in {elapsed:.3f}s (was 502 timeout)")
    
    def test_marketplace_items_has_pagination(self):
        """Marketplace items response has pagination fields"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=20", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "has_more" in data
        print(f"✓ Pagination fields present: limit={data.get('limit')}, has_more={data.get('has_more')}")
    
    def test_marketplace_items_cache_warming_flag(self):
        """Marketplace items may return cache_warming flag on cold cache"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=1", timeout=15)
        assert response.status_code == 200
        data = response.json()
        # cache_warming is optional - only present on cold cache
        if data.get("cache_warming"):
            print(f"✓ Cache warming in progress")
        else:
            print(f"✓ Cache is warm, returned {len(data.get('items', []))} items")


class TestMultiItemListings:
    """Multi-item listings tests"""
    
    def test_multi_item_listings_returns_200(self):
        """GET /api/multi-item-listings returns 200"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=20", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Multi-item listings returned {len(data)} listings")
    
    def test_multi_item_listings_response_time(self):
        """GET /api/multi-item-listings responds in reasonable time"""
        # First call may be slow (cold cache), second should be fast
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=20", timeout=15)
        elapsed = time.time() - start
        assert response.status_code == 200
        print(f"✓ Multi-item listings responded in {elapsed:.3f}s")
        
        # Second call should be faster (from cache)
        start2 = time.time()
        response2 = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=20", timeout=15)
        elapsed2 = time.time() - start2
        assert response2.status_code == 200
        print(f"✓ Second call responded in {elapsed2:.3f}s (should be faster from cache)")


class TestFilterCounts:
    """Filter counts tests"""
    
    def test_filter_counts_returns_200(self):
        """GET /api/marketplace/filter-counts returns 200"""
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "auctioneers" in data
        assert "categories" in data
        assert "locations" in data
        assert "total_active_items" in data
        print(f"✓ Filter counts returned: {len(data.get('categories', []))} categories, {data.get('total_active_items')} active items")
    
    def test_filter_counts_response_time(self):
        """GET /api/marketplace/filter-counts responds quickly"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts", timeout=10)
        elapsed = time.time() - start
        assert response.status_code == 200
        print(f"✓ Filter counts responded in {elapsed:.3f}s")


class TestResponseTimeHeader:
    """X-Response-Time header tests"""
    
    def test_health_has_response_time_header(self):
        """Health endpoint has X-Response-Time header"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert "x-response-time" in response.headers
        print(f"✓ /api/health X-Response-Time: {response.headers.get('x-response-time')}")
    
    def test_subscription_plans_has_response_time_header(self):
        """Subscription plans endpoint has X-Response-Time header"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans", timeout=10)
        assert "x-response-time" in response.headers
        print(f"✓ /api/subscription-plans X-Response-Time: {response.headers.get('x-response-time')}")
    
    def test_marketplace_items_has_response_time_header(self):
        """Marketplace items endpoint has X-Response-Time header"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=1", timeout=15)
        assert "x-response-time" in response.headers
        print(f"✓ /api/marketplace/items X-Response-Time: {response.headers.get('x-response-time')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
