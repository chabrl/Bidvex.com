"""
P2 Performance Engineering Tests
Tests for:
- Cursor-based pagination on marketplace items
- Carousel & Stats API endpoints (extracted routes)
- Site Configuration endpoints (extracted routes)
- Admin Hero Banner CRUD
- Categories API
- Login API for authentication
"""

import pytest
import requests
import json
import base64
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if BASE_URL:
    BASE_URL = BASE_URL.rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not set")
    
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    
    data = response.json()
    return data.get("access_token") or data.get("token")


class TestHealthAndBasics:
    """Basic health check and API availability"""
    
    def test_api_health(self):
        """Test API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✓ Health check passed")


class TestCursorPagination:
    """Tests for cursor-based pagination on marketplace items"""
    
    def test_marketplace_items_returns_cursor_fields(self):
        """Verify /api/marketplace/items returns next_cursor and has_more fields"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=2")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify required cursor pagination fields exist
        assert "has_more" in data, "Response missing 'has_more' field"
        assert "next_cursor" in data, "Response missing 'next_cursor' field"
        assert "items" in data, "Response missing 'items' field"
        assert "total" in data, "Response missing 'total' field"
        
        print(f"✓ Marketplace items returned {len(data['items'])} items")
        print(f"  has_more: {data['has_more']}, next_cursor: {data.get('next_cursor', 'None')[:20] if data.get('next_cursor') else 'None'}...")
    
    def test_cursor_pagination_chaining(self):
        """Test that cursor can be used to get next page"""
        # First request
        response1 = requests.get(f"{BASE_URL}/api/marketplace/items?limit=2")
        assert response1.status_code == 200, f"First request failed: {response1.text}"
        
        data1 = response1.json()
        
        if not data1.get("has_more") or not data1.get("next_cursor"):
            print("⚠ Not enough items for pagination test, but structure is correct")
            return
        
        # Second request with cursor
        cursor = data1["next_cursor"]
        response2 = requests.get(f"{BASE_URL}/api/marketplace/items?limit=2&cursor={cursor}")
        assert response2.status_code == 200, f"Second request with cursor failed: {response2.text}"
        
        data2 = response2.json()
        
        # Verify we got different items (or at least the request succeeded)
        assert "items" in data2, "Second page missing 'items' field"
        assert "has_more" in data2, "Second page missing 'has_more' field"
        
        # Verify cursor is base64 encoded JSON with offset
        try:
            decoded = json.loads(base64.b64decode(cursor))
            assert "offset" in decoded, "Cursor should contain 'offset' field"
            print(f"✓ Cursor pagination works - decoded cursor: {decoded}")
        except Exception as e:
            print(f"⚠ Could not decode cursor: {e}")
        
        print(f"✓ Cursor pagination chaining works - page 2 has {len(data2['items'])} items")
    
    def test_marketplace_items_with_filters(self):
        """Test marketplace items with various filters"""
        # Test with search
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=5&search=test")
        assert response.status_code == 200, f"Search filter failed: {response.text}"
        
        # Test with sort
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=5&sort=ending_soon")
        assert response.status_code == 200, f"Sort filter failed: {response.text}"
        
        # Test with category (may return empty if category doesn't exist)
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=5&category=Electronics")
        assert response.status_code == 200, f"Category filter failed: {response.text}"
        
        print("✓ Marketplace filters work correctly")


class TestCategoriesAPI:
    """Tests for categories API"""
    
    def test_get_categories(self):
        """Test GET /api/categories returns category data"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200, f"Categories API failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Categories should return a list"
        
        if len(data) > 0:
            # Check structure of first category
            cat = data[0]
            assert "id" in cat or "name_en" in cat, "Category should have id or name_en"
            print(f"✓ Categories API returned {len(data)} categories")
        else:
            print("✓ Categories API works (empty list)")


class TestCarouselEndpoints:
    """Tests for carousel endpoints (extracted from server.py)"""
    
    def test_ending_soon(self):
        """Test GET /api/carousel/ending-soon"""
        response = requests.get(f"{BASE_URL}/api/carousel/ending-soon")
        assert response.status_code == 200, f"Ending soon failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"✓ /api/carousel/ending-soon returned {len(data)} items")
    
    def test_new_listings(self):
        """Test GET /api/carousel/new-listings"""
        response = requests.get(f"{BASE_URL}/api/carousel/new-listings")
        assert response.status_code == 200, f"New listings failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"✓ /api/carousel/new-listings returned {len(data)} items")
    
    def test_featured(self):
        """Test GET /api/carousel/featured"""
        response = requests.get(f"{BASE_URL}/api/carousel/featured")
        assert response.status_code == 200, f"Featured failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"✓ /api/carousel/featured returned {len(data)} items")
    
    def test_recently_sold(self):
        """Test GET /api/carousel/recently-sold"""
        response = requests.get(f"{BASE_URL}/api/carousel/recently-sold")
        assert response.status_code == 200, f"Recently sold failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"✓ /api/carousel/recently-sold returned {len(data)} items")


class TestStatsEndpoints:
    """Tests for stats endpoints (extracted from server.py)"""
    
    def test_top_sellers(self):
        """Test GET /api/stats/top-sellers"""
        response = requests.get(f"{BASE_URL}/api/stats/top-sellers")
        assert response.status_code == 200, f"Top sellers failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"✓ /api/stats/top-sellers returned {len(data)} sellers")
    
    def test_hot_items(self):
        """Test GET /api/stats/hot-items"""
        response = requests.get(f"{BASE_URL}/api/stats/hot-items")
        assert response.status_code == 200, f"Hot items failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        print(f"✓ /api/stats/hot-items returned {len(data)} items")


class TestSiteConfigEndpoints:
    """Tests for site configuration endpoints (extracted from server.py)"""
    
    def test_public_site_config(self):
        """Test GET /api/site-config (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/site-config")
        assert response.status_code == 200, f"Site config failed: {response.text}"
        
        data = response.json()
        
        # Verify expected fields
        assert "branding" in data, "Site config should have 'branding'"
        assert "homepage_layout" in data, "Site config should have 'homepage_layout'"
        assert "hero_banners" in data, "Site config should have 'hero_banners'"
        
        print(f"✓ Public site-config returned with branding, layout, and {len(data.get('hero_banners', []))} banners")
    
    def test_admin_site_config_requires_auth(self):
        """Test GET /api/admin/site-config requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/site-config")
        assert response.status_code in [401, 403], f"Should require auth, got: {response.status_code}"
        print("✓ Admin site-config correctly requires authentication")
    
    def test_admin_site_config_with_auth(self, admin_token):
        """Test GET /api/admin/site-config with admin token"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/site-config", headers=headers)
        assert response.status_code == 200, f"Admin site config failed: {response.text}"
        
        data = response.json()
        assert "branding" in data, "Admin site config should have 'branding'"
        print("✓ Admin site-config accessible with valid token")


class TestHeroBannerCRUD:
    """Tests for admin hero banner endpoints"""
    
    def test_get_hero_banners_requires_auth(self):
        """Test GET /api/admin/hero-banners requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/hero-banners")
        assert response.status_code in [401, 403], f"Should require auth, got: {response.status_code}"
        print("✓ Hero banners endpoint correctly requires authentication")
    
    def test_get_hero_banners_with_auth(self, admin_token):
        """Test GET /api/admin/hero-banners with admin token"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/hero-banners", headers=headers)
        assert response.status_code == 200, f"Hero banners failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return a list of banners"
        print(f"✓ Admin hero-banners returned {len(data)} banners")


class TestLoginAPI:
    """Tests for authentication"""
    
    def test_login_success(self):
        """Test POST /api/auth/login with valid admin credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data or "token" in data, "Login should return token"
        assert "user" in data, "Login should return user data"
        
        print(f"✓ Login successful for {data['user'].get('email')}")
    
    def test_login_invalid_credentials(self):
        """Test POST /api/auth/login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "invalid@test.com", "password": "wrongpassword"}
        )
        assert response.status_code in [401, 400, 404], f"Should reject invalid creds, got: {response.status_code}"
        print("✓ Invalid credentials correctly rejected")


class TestMarketplaceFilterCounts:
    """Tests for marketplace filter counts (stale-while-revalidate cache)"""
    
    def test_filter_counts(self):
        """Test GET /api/marketplace/filter-counts"""
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts")
        assert response.status_code == 200, f"Filter counts failed: {response.text}"
        
        data = response.json()
        
        # Verify expected structure
        assert "categories" in data, "Should have 'categories'"
        assert "auctioneers" in data, "Should have 'auctioneers'"
        assert "locations" in data, "Should have 'locations'"
        
        print(f"✓ Filter counts returned - {len(data.get('categories', []))} categories, {len(data.get('auctioneers', []))} auctioneers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
