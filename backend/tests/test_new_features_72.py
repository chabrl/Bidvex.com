"""
BidVex New Features Test - Iteration 72
Tests for:
1. Mobile Swipeable Carousels (frontend-only, tested via API endpoints for data)
2. Cloud PDF Invoice Storage (Emergent Object Storage)
3. Premium Comparison View (/api/listings/{id} for compare page)
"""

import pytest
import requests
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://dashboard-localize.preview.emergentagent.com"


class TestHealthAndBasicAPIs:
    """Basic health and API tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health endpoint: {data}")
    
    def test_root_health(self):
        """Test /health root endpoint"""
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200
        print("✓ Root health endpoint working")


class TestCarouselEndpoints:
    """Test carousel/homepage data endpoints that power SwipeableCardRow"""
    
    def test_ending_soon_carousel(self):
        """Test /api/carousel/ending-soon for Ending Soon section"""
        response = requests.get(f"{BASE_URL}/api/carousel/ending-soon?limit=12", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Ending soon carousel: {len(data)} items")
    
    def test_hot_items(self):
        """Test /api/stats/hot-items for Hot Items section"""
        response = requests.get(f"{BASE_URL}/api/stats/hot-items?limit=6", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Hot items: {len(data)} items")
    
    def test_featured_carousel(self):
        """Test /api/carousel/featured for Featured Auctions section"""
        response = requests.get(f"{BASE_URL}/api/carousel/featured?limit=12", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Featured carousel: {len(data)} items")
    
    def test_new_listings_carousel(self):
        """Test /api/carousel/new-listings for Just Listed section"""
        response = requests.get(f"{BASE_URL}/api/carousel/new-listings?limit=12", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ New listings carousel: {len(data)} items")
    
    def test_top_sellers(self):
        """Test /api/stats/top-sellers for Top Sellers section"""
        response = requests.get(f"{BASE_URL}/api/stats/top-sellers?limit=8", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Top sellers: {len(data)} sellers")
    
    def test_recently_sold_carousel(self):
        """Test /api/carousel/recently-sold endpoint"""
        response = requests.get(f"{BASE_URL}/api/carousel/recently-sold?limit=12", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Recently sold carousel: {len(data)} items")


class TestCompareViewAPIs:
    """Test APIs used by the Premium Comparison View feature"""
    
    def test_marketplace_items_for_compare(self):
        """Test /api/marketplace/items returns items with IDs for comparison"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=5", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        items = data["items"]
        assert isinstance(items, list)
        
        if len(items) > 0:
            item = items[0]
            # Items should have IDs for compare feature
            assert "id" in item, "Item should have ID for comparison"
            # Items should have basic data needed for comparison
            assert "title" in item or "current_price" in item
        print(f"✓ Marketplace items: {len(items)} items with IDs for compare")
    
    def test_individual_listing_for_compare(self):
        """Test /api/listings/{id} returns full listing data for compare page"""
        # First get a listing ID
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=1", timeout=10)
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        # Find a standalone listing (not a lot)
        listing_id = None
        for item in items:
            if "_lot" not in item.get("id", ""):
                listing_id = item["id"]
                break
        
        if not listing_id:
            # Try to get from listings endpoint
            resp = requests.get(f"{BASE_URL}/api/listings?limit=5", timeout=10)
            if resp.status_code == 200:
                listings = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
                for l in listings:
                    if "_lot" not in l.get("id", ""):
                        listing_id = l["id"]
                        break
        
        if listing_id:
            response = requests.get(f"{BASE_URL}/api/listings/{listing_id}", timeout=10)
            assert response.status_code == 200
            listing = response.json()
            
            # Verify listing has data needed for comparison
            assert "id" in listing
            assert "title" in listing
            
            # shipping_info can be string or object - compare page handles both
            if "shipping_info" in listing:
                # Can be string, dict, or None
                assert listing["shipping_info"] is None or isinstance(listing["shipping_info"], (str, dict))
            
            print(f"✓ Individual listing API works: {listing.get('title', 'N/A')[:30]}...")
        else:
            pytest.skip("No standalone listings found to test")
    
    def test_listing_search_for_compare(self):
        """Test /api/listings search endpoint used by compare search modal"""
        response = requests.get(f"{BASE_URL}/api/listings?search=test&limit=8", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Response can be list or dict with items
        if isinstance(data, list):
            items = data
        else:
            items = data.get("items", data.get("listings", []))
        
        print(f"✓ Listing search for compare: {len(items)} results for 'test'")


class TestCloudStorageIntegration:
    """Test Cloud PDF Invoice Storage with Emergent Object Storage"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "charbeladmin@bidvex.com", "password": "Admin123!"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token") or data.get("token")
        pytest.skip("Authentication failed")
    
    def test_invoices_endpoint_requires_auth(self):
        """Test /api/invoices requires authentication"""
        response = requests.get(f"{BASE_URL}/api/invoices", timeout=10)
        assert response.status_code == 401
        print("✓ Invoices endpoint requires auth")
    
    def test_invoices_endpoint_with_auth(self, auth_token):
        """Test /api/invoices returns invoices with signed download URLs"""
        response = requests.get(
            f"{BASE_URL}/api/invoices",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert "invoices" in data
        invoices = data["invoices"]
        
        if len(invoices) > 0:
            invoice = invoices[0]
            # Each invoice should have a signed download_url
            assert "download_url" in invoice, "Invoice should have download_url"
            download_url = invoice["download_url"]
            # URL should contain signature params
            assert "expires=" in download_url or "sig=" in download_url, "URL should be signed"
            print(f"✓ Invoice with signed URL: {invoice.get('invoice_number', 'N/A')}")
        else:
            print("✓ Invoices endpoint works (0 invoices for this user)")
    
    def test_signed_download_requires_valid_signature(self):
        """Test /api/invoices/download/{id} rejects invalid signatures"""
        # Try with invalid signature
        response = requests.get(
            f"{BASE_URL}/api/invoices/download/fake-id?expires=0&sig=invalid",
            timeout=10
        )
        assert response.status_code == 403
        print("✓ Signed download rejects invalid signature")


class TestMarketplaceCompareIntegration:
    """Test marketplace items have compare toggle data"""
    
    def test_marketplace_items_have_ids(self):
        """Test marketplace items have IDs for compare toggle"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10", timeout=10)
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        for item in items:
            assert "id" in item, f"Item missing ID: {item.get('title', 'Unknown')}"
        
        print(f"✓ All {len(items)} marketplace items have IDs for compare")
    
    def test_categories_for_compare_filter(self):
        """Test /api/categories returns categories for filter in compare"""
        response = requests.get(f"{BASE_URL}/api/categories", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            cat = data[0]
            assert "name_en" in cat or "name" in cat
        
        print(f"✓ Categories available: {len(data)} categories")


# Run if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
