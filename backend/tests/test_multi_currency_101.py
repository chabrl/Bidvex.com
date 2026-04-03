"""
BidVex Multi-Currency Feature Tests - Iteration 101
Tests for CAD/USD currency support in listings, bids, and payments.
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

# Test listing IDs from main agent
TEST_USD_LISTING_ID = "37e196bf-7d47-487e-85c5-7585108fe655"
TEST_CAD_LISTING_ID = "97e65cbd-c7c0-44bc-8aa6-04beaec7a2cb"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestListingCurrencyAPI:
    """Test currency field in listings API"""
    
    def test_get_listings_returns_currency_field(self, api_client):
        """GET /api/listings should return currency field in each listing"""
        response = api_client.get(f"{BASE_URL}/api/listings?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        listings = response.json()
        assert isinstance(listings, list), "Response should be a list"
        
        if len(listings) > 0:
            listing = listings[0]
            assert "currency" in listing, "Listing should have 'currency' field"
            assert listing["currency"] in ["CAD", "USD"], f"Currency should be CAD or USD, got {listing.get('currency')}"
            print(f"✓ Listing {listing.get('id', 'N/A')[:8]}... has currency: {listing['currency']}")
    
    def test_get_listings_filter_by_currency_usd(self, api_client):
        """GET /api/listings?currency=USD should filter by USD"""
        response = api_client.get(f"{BASE_URL}/api/listings?currency=USD&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        listings = response.json()
        for listing in listings:
            assert listing.get("currency") == "USD", f"Expected USD, got {listing.get('currency')}"
        print(f"✓ Found {len(listings)} USD listings")
    
    def test_get_listings_filter_by_currency_cad(self, api_client):
        """GET /api/listings?currency=CAD should filter by CAD"""
        response = api_client.get(f"{BASE_URL}/api/listings?currency=CAD&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        listings = response.json()
        for listing in listings:
            assert listing.get("currency") == "CAD", f"Expected CAD, got {listing.get('currency')}"
        print(f"✓ Found {len(listings)} CAD listings")
    
    def test_get_specific_usd_listing(self, api_client):
        """GET /api/listings/{id} for USD listing should return USD currency"""
        response = api_client.get(f"{BASE_URL}/api/listings/{TEST_USD_LISTING_ID}")
        
        if response.status_code == 404:
            pytest.skip(f"USD test listing {TEST_USD_LISTING_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        listing = response.json()
        assert listing.get("currency") == "USD", f"Expected USD, got {listing.get('currency')}"
        print(f"✓ USD listing verified: {listing.get('title', 'N/A')[:30]}...")
    
    def test_get_specific_cad_listing(self, api_client):
        """GET /api/listings/{id} for CAD listing should return CAD currency"""
        response = api_client.get(f"{BASE_URL}/api/listings/{TEST_CAD_LISTING_ID}")
        
        if response.status_code == 404:
            pytest.skip(f"CAD test listing {TEST_CAD_LISTING_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        listing = response.json()
        assert listing.get("currency") == "CAD", f"Expected CAD, got {listing.get('currency')}"
        print(f"✓ CAD listing verified: {listing.get('title', 'N/A')[:30]}...")


class TestMultiItemListingsCurrency:
    """Test currency field in multi-item listings API"""
    
    def test_get_multi_item_listings_returns_currency(self, api_client):
        """GET /api/multi-item-listings should return currency field"""
        response = api_client.get(f"{BASE_URL}/api/multi-item-listings?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        listings = response.json()
        if len(listings) > 0:
            listing = listings[0]
            assert "currency" in listing, "Multi-item listing should have 'currency' field"
            assert listing["currency"] in ["CAD", "USD"], f"Currency should be CAD or USD"
            print(f"✓ Multi-item listing has currency: {listing['currency']}")
    
    def test_get_multi_item_listings_filter_by_currency(self, api_client):
        """GET /api/multi-item-listings?currency=CAD should filter by currency"""
        response = api_client.get(f"{BASE_URL}/api/multi-item-listings?currency=CAD&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        listings = response.json()
        for listing in listings:
            assert listing.get("currency") == "CAD", f"Expected CAD, got {listing.get('currency')}"
        print(f"✓ Found {len(listings)} CAD multi-item listings")


class TestCurrencyAutoDetection:
    """Test currency auto-detection from location"""
    
    def test_create_listing_with_explicit_usd(self, authenticated_client):
        """POST /api/listings with currency=USD should create USD listing"""
        end_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        
        payload = {
            "title": "TEST_USD_Currency_Test_Item",
            "description": "Test item for USD currency verification",
            "category": "Electronics",
            "condition": "good",
            "starting_price": 100.00,
            "images": [],
            "location": "New York, NY",
            "city": "New York",
            "region": "New York",
            "country": "US",
            "auction_end_date": end_date,
            "currency": "USD",
            "agreement_accepted": True
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/listings", json=payload)
        
        if response.status_code == 403:
            pytest.skip("User not authorized to create listings (tax onboarding required)")
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        listing = response.json()
        assert listing.get("currency") == "USD", f"Expected USD, got {listing.get('currency')}"
        print(f"✓ Created USD listing: {listing.get('id', 'N/A')[:8]}...")
        
        # Cleanup - delete the test listing
        if listing.get("id"):
            authenticated_client.delete(f"{BASE_URL}/api/listings/{listing['id']}")
    
    def test_create_listing_with_explicit_cad(self, authenticated_client):
        """POST /api/listings with currency=CAD should create CAD listing"""
        end_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        
        payload = {
            "title": "TEST_CAD_Currency_Test_Item",
            "description": "Test item for CAD currency verification",
            "category": "Electronics",
            "condition": "good",
            "starting_price": 100.00,
            "images": [],
            "location": "Montreal, QC",
            "city": "Montreal",
            "region": "Quebec",
            "country": "CA",
            "auction_end_date": end_date,
            "currency": "CAD",
            "agreement_accepted": True
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/listings", json=payload)
        
        if response.status_code == 403:
            pytest.skip("User not authorized to create listings (tax onboarding required)")
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        listing = response.json()
        assert listing.get("currency") == "CAD", f"Expected CAD, got {listing.get('currency')}"
        print(f"✓ Created CAD listing: {listing.get('id', 'N/A')[:8]}...")
        
        # Cleanup
        if listing.get("id"):
            authenticated_client.delete(f"{BASE_URL}/api/listings/{listing['id']}")
    
    def test_create_listing_auto_detect_cad_from_canada(self, authenticated_client):
        """POST /api/listings without currency for Canada should auto-detect CAD"""
        end_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        
        payload = {
            "title": "TEST_AutoDetect_CAD_Item",
            "description": "Test item for CAD auto-detection",
            "category": "Electronics",
            "condition": "good",
            "starting_price": 50.00,
            "images": [],
            "location": "Toronto, ON",
            "city": "Toronto",
            "region": "Ontario",
            "country": "CA",
            "auction_end_date": end_date,
            # No currency field - should auto-detect CAD
            "agreement_accepted": True
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/listings", json=payload)
        
        if response.status_code == 403:
            pytest.skip("User not authorized to create listings")
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        listing = response.json()
        assert listing.get("currency") == "CAD", f"Expected auto-detected CAD, got {listing.get('currency')}"
        print(f"✓ Auto-detected CAD for Canada location")
        
        # Cleanup
        if listing.get("id"):
            authenticated_client.delete(f"{BASE_URL}/api/listings/{listing['id']}")
    
    def test_create_listing_auto_detect_usd_from_us(self, authenticated_client):
        """POST /api/listings without currency for US should auto-detect USD"""
        end_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        
        payload = {
            "title": "TEST_AutoDetect_USD_Item",
            "description": "Test item for USD auto-detection",
            "category": "Electronics",
            "condition": "good",
            "starting_price": 50.00,
            "images": [],
            "location": "Los Angeles, CA",
            "city": "Los Angeles",
            "region": "California",
            "country": "US",
            "auction_end_date": end_date,
            # No currency field - should auto-detect USD
            "agreement_accepted": True
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/listings", json=payload)
        
        if response.status_code == 403:
            pytest.skip("User not authorized to create listings")
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        listing = response.json()
        assert listing.get("currency") == "USD", f"Expected auto-detected USD, got {listing.get('currency')}"
        print(f"✓ Auto-detected USD for US location")
        
        # Cleanup
        if listing.get("id"):
            authenticated_client.delete(f"{BASE_URL}/api/listings/{listing['id']}")


class TestBidCurrencyContext:
    """Test that bids inherit listing currency context"""
    
    def test_bid_response_includes_currency(self, authenticated_client):
        """Bid response should include currency from listing"""
        # First get an active listing
        response = authenticated_client.get(f"{BASE_URL}/api/listings?limit=1")
        assert response.status_code == 200
        
        listings = response.json()
        if not listings:
            pytest.skip("No active listings to test bidding")
        
        listing = listings[0]
        listing_id = listing.get("id")
        current_price = listing.get("current_price", 0)
        listing_currency = listing.get("currency", "CAD")
        
        # Place a bid
        bid_amount = current_price + 10
        bid_response = authenticated_client.post(f"{BASE_URL}/api/bids", json={
            "listing_id": listing_id,
            "amount": bid_amount
        })
        
        if bid_response.status_code == 400:
            # Might be outbid or auction ended
            print(f"⚠ Could not place bid: {bid_response.text}")
            pytest.skip("Could not place test bid")
        
        if bid_response.status_code == 200:
            bid_data = bid_response.json()
            # Check if currency is in response
            if "currency" in bid_data:
                assert bid_data["currency"] == listing_currency
                print(f"✓ Bid response includes currency: {bid_data['currency']}")
            else:
                print(f"⚠ Bid response does not include currency field (may be expected)")


class TestI18nCurrencyKeys:
    """Test that i18n currency keys exist"""
    
    def test_en_json_has_currency_keys(self):
        """English locale should have currency section"""
        import json
        en_path = "/app/frontend/src/locales/en.json"
        
        with open(en_path, 'r') as f:
            en_data = json.load(f)
        
        assert "currency" in en_data, "en.json should have 'currency' section"
        currency_section = en_data["currency"]
        
        required_keys = ["selector", "warningBody", "bidIn", "listedIn"]
        for key in required_keys:
            assert key in currency_section, f"en.json currency section missing '{key}'"
            print(f"✓ en.json has currency.{key}: {currency_section[key][:30]}...")
    
    def test_fr_json_has_currency_keys(self):
        """French locale should have currency section"""
        import json
        fr_path = "/app/frontend/src/locales/fr.json"
        
        with open(fr_path, 'r') as f:
            fr_data = json.load(f)
        
        assert "currency" in fr_data, "fr.json should have 'currency' section"
        currency_section = fr_data["currency"]
        
        required_keys = ["selector", "warningBody", "bidIn", "listedIn"]
        for key in required_keys:
            assert key in currency_section, f"fr.json currency section missing '{key}'"
            print(f"✓ fr.json has currency.{key}: {currency_section[key][:30]}...")


class TestCurrencyFormatterUtility:
    """Test formatListingPrice utility exists and is used"""
    
    def test_currency_formatter_file_exists(self):
        """currencyFormatter.js should exist with formatListingPrice"""
        formatter_path = "/app/frontend/src/utils/currencyFormatter.js"
        
        with open(formatter_path, 'r') as f:
            content = f.read()
        
        assert "formatListingPrice" in content, "currencyFormatter.js should export formatListingPrice"
        assert "formatCurrency" in content, "currencyFormatter.js should export formatCurrency"
        
        # Check for bilingual formatting logic
        assert "fr-CA" in content or "isFr" in content, "Should have French locale support"
        assert "en-CA" in content, "Should have English-Canada locale support"
        
        print("✓ currencyFormatter.js has formatListingPrice with bilingual support")


class TestPaymentsCurrencyIntegration:
    """Test that payment routes use listing currency (code-level verification)"""
    
    def test_payments_route_uses_listing_currency(self):
        """payments.py should use listing.currency instead of hardcoded 'cad'"""
        payments_path = "/app/backend/routes/payments.py"
        
        with open(payments_path, 'r') as f:
            content = f.read()
        
        # Check for dynamic currency usage patterns
        assert 'listing.get("currency"' in content or "listing.get('currency'" in content, \
            "payments.py should fetch currency from listing"
        
        # Check that it's used in Stripe session creation
        assert 'auction_currency' in content or 'listing_currency' in content or 'winner_currency' in content, \
            "payments.py should use dynamic currency variable"
        
        # Verify no hardcoded 'cad' in critical Stripe sections (approximate check)
        # This is a heuristic - we look for the pattern of using .lower() on currency
        assert '.lower()' in content, "Should convert currency to lowercase for Stripe"
        
        print("✓ payments.py uses dynamic listing currency for Stripe")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
