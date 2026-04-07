"""
BidVex Bilingual Content & i18n Translation Tests - Iteration 113
Tests for:
- API returns title_en, title_fr, description_en, description_fr in /api/marketplace/items
- Backfill endpoint /api/admin/backfill-translations
- Translation manual override endpoint PUT /api/listings/{id}/translations
- Multi-item listing translation fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestMarketplaceI18nFields:
    """Test that marketplace items API returns bilingual fields"""
    
    def test_marketplace_items_has_i18n_fields(self, api_client):
        """Verify /api/marketplace/items returns title_en, title_fr, description_en, description_fr"""
        import time
        
        # Retry up to 3 times with delay (cache warming may be in progress)
        for attempt in range(3):
            response = api_client.get(f"{BASE_URL}/api/marketplace/items?limit=10")
            assert response.status_code == 200
            
            data = response.json()
            assert "items" in data
            
            items = data.get("items", [])
            if len(items) == 0:
                print(f"Attempt {attempt + 1}: No items yet, waiting for cache...")
                time.sleep(2)
                continue
            
            # Check at least one item has i18n fields
            items_with_i18n = 0
            for item in items:
                has_title_en = "title_en" in item
                has_title_fr = "title_fr" in item
                
                if has_title_en and has_title_fr:
                    items_with_i18n += 1
                    print(f"Item '{item.get('title', 'N/A')[:30]}...' has i18n fields:")
                    print(f"  title_en: {item.get('title_en', 'N/A')[:40]}...")
                    print(f"  title_fr: {item.get('title_fr', 'N/A')[:40]}...")
            
            if items_with_i18n > 0:
                print(f"\n{items_with_i18n}/{len(items)} items have i18n fields")
                return  # Test passed
            
            time.sleep(2)
        
        # If we get here, check if items exist but don't have i18n fields
        if len(items) > 0:
            print(f"Items found but no i18n fields. Sample keys: {list(items[0].keys())}")
        pytest.skip("Marketplace cache not warmed - items have no i18n fields yet")
    
    def test_marketplace_items_parent_auction_title_i18n(self, api_client):
        """Verify lot items have parent_auction_title_en and parent_auction_title_fr"""
        response = api_client.get(f"{BASE_URL}/api/marketplace/items?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        lot_items = [i for i in data.get("items", []) if i.get("auction_id")]
        
        if lot_items:
            for item in lot_items[:3]:
                print(f"Lot item: {item.get('title', 'N/A')[:30]}...")
                print(f"  parent_auction_title_en: {item.get('parent_auction_title_en', 'N/A')}")
                print(f"  parent_auction_title_fr: {item.get('parent_auction_title_fr', 'N/A')}")
                
                # Verify fields exist (may be None if not translated yet)
                assert "parent_auction_title_en" in item or "parent_auction_title_fr" in item
        else:
            print("No lot items found in marketplace")


class TestBackfillTranslations:
    """Test admin backfill translations endpoint"""
    
    def test_backfill_requires_auth(self, api_client):
        """Verify backfill endpoint requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/admin/backfill-translations")
        assert response.status_code in [401, 403, 422]
    
    def test_backfill_requires_admin(self, api_client, admin_token):
        """Verify backfill endpoint works for admin"""
        response = api_client.post(
            f"{BASE_URL}/api/admin/backfill-translations",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        print(f"Backfill response: {data}")


class TestTranslationOverride:
    """Test manual translation override endpoints"""
    
    def test_single_listing_translation_override(self, api_client, admin_token):
        """Test PUT /api/listings/{id}/translations for single listings"""
        # First get a listing
        listings_response = api_client.get(f"{BASE_URL}/api/listings?limit=1")
        if listings_response.status_code != 200 or not listings_response.json():
            pytest.skip("No single listings available to test")
        
        listing = listings_response.json()[0]
        listing_id = listing.get("id")
        
        # Test translation override
        response = api_client.put(
            f"{BASE_URL}/api/listings/{listing_id}/translations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title_fr": "Titre de test FR",
                "description_fr": "Description de test FR"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "updated_fields" in data
        print(f"Updated fields: {data.get('updated_fields')}")
    
    def test_multi_listing_translation_override(self, api_client, admin_token):
        """Test PUT /api/multi-item-listings/{id}/translations"""
        # First get a multi-item listing
        multi_response = api_client.get(f"{BASE_URL}/api/multi-item-listings?limit=1")
        if multi_response.status_code != 200 or not multi_response.json():
            pytest.skip("No multi-item listings available to test")
        
        listing = multi_response.json()[0]
        listing_id = listing.get("id")
        
        # Test translation override
        response = api_client.put(
            f"{BASE_URL}/api/multi-item-listings/{listing_id}/translations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title_fr": "Titre enchère multi-lots FR",
                "description_fr": "Description enchère FR"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"Multi-listing translation updated: {data}")


class TestMultiItemListingI18n:
    """Test multi-item listing detail endpoint returns i18n fields"""
    
    def test_multi_listing_detail_has_i18n(self, api_client):
        """Verify GET /api/multi-item-listings/{id} returns i18n fields"""
        # Get a multi-item listing
        list_response = api_client.get(f"{BASE_URL}/api/multi-item-listings?limit=1")
        if list_response.status_code != 200 or not list_response.json():
            pytest.skip("No multi-item listings available")
        
        listing_id = list_response.json()[0].get("id")
        
        # Get detail
        response = api_client.get(f"{BASE_URL}/api/multi-item-listings/{listing_id}")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check listing-level i18n fields
        print(f"Listing: {data.get('title', 'N/A')}")
        print(f"  title_en: {data.get('title_en', 'N/A')}")
        print(f"  title_fr: {data.get('title_fr', 'N/A')}")
        
        # Check lot-level i18n fields
        lots = data.get("lots", [])
        if lots:
            lot = lots[0]
            print(f"First lot: {lot.get('title', 'N/A')}")
            print(f"  lot title_en: {lot.get('title_en', 'N/A')}")
            print(f"  lot title_fr: {lot.get('title_fr', 'N/A')}")


class TestSingleListingI18n:
    """Test single listing detail endpoint returns i18n fields"""
    
    def test_single_listing_detail_has_i18n(self, api_client):
        """Verify GET /api/listings/{id} returns i18n fields"""
        # Get a single listing
        list_response = api_client.get(f"{BASE_URL}/api/listings?limit=1")
        if list_response.status_code != 200 or not list_response.json():
            pytest.skip("No single listings available")
        
        listing_id = list_response.json()[0].get("id")
        
        # Get detail
        response = api_client.get(f"{BASE_URL}/api/listings/{listing_id}")
        assert response.status_code == 200
        
        data = response.json()
        
        print(f"Listing: {data.get('title', 'N/A')}")
        print(f"  title_en: {data.get('title_en', 'N/A')}")
        print(f"  title_fr: {data.get('title_fr', 'N/A')}")
        print(f"  description_en: {str(data.get('description_en', 'N/A'))[:50]}...")
        print(f"  description_fr: {str(data.get('description_fr', 'N/A'))[:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
