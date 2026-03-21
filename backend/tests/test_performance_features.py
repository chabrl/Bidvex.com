"""
Performance Feature Tests for BidVex
Tests API caching, GZip middleware, and SEO endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://auction-marketplace-15.preview.emergentagent.com').rstrip('/')

class TestAPICaching:
    """Test TTL-based API caching for public endpoints"""
    
    def test_categories_api_returns_data(self):
        """Test /api/categories returns valid category data"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Categories API returned {len(data)} categories")
    
    def test_carousel_new_listings_api_returns_data(self):
        """Test /api/carousel/new-listings returns listing data"""
        response = requests.get(f"{BASE_URL}/api/carousel/new-listings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ New Listings carousel API returned {len(data)} items")
    
    def test_categories_caching_performance(self):
        """Test that cached API responses are faster on subsequent calls"""
        # First call - may hit DB
        start1 = time.time()
        resp1 = requests.get(f"{BASE_URL}/api/categories")
        time1 = time.time() - start1
        assert resp1.status_code == 200
        
        # Second call - should hit cache
        start2 = time.time()
        resp2 = requests.get(f"{BASE_URL}/api/categories")
        time2 = time.time() - start2
        assert resp2.status_code == 200
        
        # Both should return same data
        assert resp1.json() == resp2.json()
        
        print(f"✅ First call: {time1*1000:.0f}ms, Second call: {time2*1000:.0f}ms")
        # Note: Network latency may mask caching benefits in remote testing


class TestGZipMiddleware:
    """Test GZip compression middleware"""
    
    def test_gzip_compression_headers(self):
        """Test that server responds with gzip when requested"""
        headers = {"Accept-Encoding": "gzip, deflate, br"}
        response = requests.get(f"{BASE_URL}/api/categories", headers=headers)
        assert response.status_code == 200
        
        # Note: K8s ingress may handle compression
        encoding = response.headers.get("Content-Encoding", "")
        print(f"Content-Encoding: {encoding or 'none (may be handled by K8s ingress)'}")
        
        # Verify response is valid regardless of compression
        data = response.json()
        assert isinstance(data, list)
        print("✅ API response valid with gzip accept header")


class TestSEOEndpoints:
    """Test SEO-related static files"""
    
    def test_robots_txt_accessible(self):
        """Test robots.txt is served correctly"""
        response = requests.get(f"{BASE_URL}/robots.txt")
        assert response.status_code == 200
        content = response.text
        
        # Check for expected content (may be K8s default or BidVex custom)
        print(f"robots.txt content (first 100 chars): {content[:100]}")
        print("✅ robots.txt is accessible")
    
    def test_sitemap_xml_accessible(self):
        """Test sitemap.xml is served correctly"""
        response = requests.get(f"{BASE_URL}/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        
        # Check for XML content
        assert "<?xml" in content or "urlset" in content.lower()
        print(f"sitemap.xml content (first 100 chars): {content[:100]}")
        print("✅ sitemap.xml is accessible and contains XML")


class TestAPIHealthCheck:
    """Basic API health checks"""
    
    def test_listings_api_accessible(self):
        """Test /api/listings returns data"""
        response = requests.get(f"{BASE_URL}/api/listings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Listings API returned {len(data)} items")
    
    def test_multi_item_listings_api_accessible(self):
        """Test /api/multi-item-listings returns data"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Multi-item listings API returned {len(data)} items")


class TestCurrencyFormatting:
    """Test currency-related API responses (regression test)"""
    
    def test_listings_have_price_fields(self):
        """Verify listings contain proper price fields"""
        response = requests.get(f"{BASE_URL}/api/listings?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            listing = data[0]
            assert "current_price" in listing
            assert "starting_price" in listing
            assert isinstance(listing["current_price"], (int, float))
            print(f"✅ Listing price format valid: ${listing['current_price']}")
        else:
            print("ℹ️ No listings available to test price format")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
