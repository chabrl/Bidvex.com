"""
Test LocationSelector Feature - Unified Location Architecture
Tests for location fields (country, region, city, postal_code) in listing APIs
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin login failed: {response.status_code}")


@pytest.fixture
def auth_headers(admin_token):
    """Authorization headers"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestListingLocationFields:
    """Test location fields in single-item listing API"""
    
    def test_create_listing_with_full_location(self, auth_headers):
        """Test creating a listing with all location fields (country, region, city, postal_code)"""
        end_date = (datetime.now() + timedelta(days=7)).isoformat()
        
        payload = {
            "title": "TEST_LocationSelector Test Item",
            "description": "Testing location fields",
            "category": "general",
            "condition": "good",
            "starting_price": 100.0,
            "images": [],
            "location": "Montreal, QC, H1H 1H1",
            "country": "CA",
            "region": "QC",
            "city": "Montreal",
            "postal_code": "H1H 1H1",
            "auction_end_date": end_date,
            "agreement_accepted": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/listings",
            json=payload,
            headers=auth_headers
        )
        
        print(f"Create listing response: {response.status_code}")
        if response.status_code >= 400:
            print(f"Error: {response.text[:500]}")
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        data = response.json()
        # Verify location fields are returned
        assert data.get("country") == "CA", "Country should be CA"
        assert data.get("region") == "QC", "Region should be QC"
        assert data.get("city") == "Montreal", "City should be Montreal"
        
        # Store listing ID for cleanup
        return data.get("id")
    
    def test_create_listing_with_us_location(self, auth_headers):
        """Test creating a listing with US location"""
        end_date = (datetime.now() + timedelta(days=7)).isoformat()
        
        payload = {
            "title": "TEST_US Location Test Item",
            "description": "Testing US location fields",
            "category": "general",
            "condition": "good",
            "starting_price": 50.0,
            "images": [],
            "location": "New York, NY, 10001",
            "country": "US",
            "region": "NY",
            "city": "New York City",
            "postal_code": "10001",
            "auction_end_date": end_date,
            "agreement_accepted": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/listings",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        data = response.json()
        assert data.get("country") == "US", "Country should be US"
        assert data.get("region") == "NY", "Region should be NY"
    
    def test_create_listing_default_country(self, auth_headers):
        """Test that country defaults to CA if not provided"""
        end_date = (datetime.now() + timedelta(days=7)).isoformat()
        
        payload = {
            "title": "TEST_Default Country Test Item",
            "description": "Testing default country",
            "category": "general",
            "condition": "good",
            "starting_price": 25.0,
            "images": [],
            "location": "Toronto, ON",
            "region": "ON",
            "city": "Toronto",
            # No country field provided
            "auction_end_date": end_date,
            "agreement_accepted": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/listings",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        data = response.json()
        # Country should default to CA
        assert data.get("country") == "CA", "Country should default to CA"


class TestMultiItemListingLocationFields:
    """Test location fields in multi-item listing API"""
    
    def test_create_multi_item_with_location(self, auth_headers):
        """Test creating multi-item listing with full location"""
        end_date = (datetime.now() + timedelta(days=7)).isoformat()
        
        payload = {
            "title": "TEST_Multi-Item Location Test",
            "description": "Testing multi-item location fields",
            "category": "general",
            "location": "Quebec City, QC, G1A 1A1",
            "country": "CA",
            "region": "QC",
            "city": "Quebec City",
            "postal_code": "G1A 1A1",
            "auction_end_date": end_date,
            "agreement_accepted": True,
            "lots": [
                {
                    "lot_number": 1,
                    "title": "Test Lot 1",
                    "description": "First test lot",
                    "quantity": 1,
                    "starting_price": 10.0,
                    "current_price": 10.0,
                    "condition": "good",
                    "images": []
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/multi-item-listings",
            json=payload,
            headers=auth_headers
        )
        
        print(f"Multi-item listing response: {response.status_code}")
        if response.status_code >= 400:
            print(f"Error: {response.text[:500]}")
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}"
        
        data = response.json()
        assert data.get("country") == "CA", "Country should be CA"
        assert data.get("region") == "QC", "Region should be QC"
        assert data.get("postal_code") == "G1A 1A1", "Postal code should be G1A 1A1"


class TestExistingListingsHaveISOCodes:
    """Verify migration script normalized existing data to ISO codes"""
    
    def test_listings_have_iso_region_codes(self, auth_headers):
        """Test that fetched listings have ISO codes for regions (not full names)"""
        response = requests.get(
            f"{BASE_URL}/api/listings",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        listings = data if isinstance(data, list) else data.get("listings", data.get("items", []))
        
        if len(listings) > 0:
            # Check that regions are ISO codes (2-letter) not full names
            for listing in listings[:5]:  # Check first 5
                region = listing.get("region", "")
                if region:
                    # ISO codes are typically 2 characters
                    assert len(region) <= 3 or region.upper() == region, \
                        f"Region '{region}' should be an ISO code, not a full name"
                    print(f"Listing '{listing.get('title', 'N/A')[:30]}...' has region: {region}")
            
            print(f"Verified {min(5, len(listings))} listings have ISO region codes")
        else:
            print("No listings found to verify")


class TestLocationFilterInMarketplace:
    """Test that location filtering works with ISO codes"""
    
    def test_filter_by_region(self, auth_headers):
        """Test filtering listings by region"""
        response = requests.get(
            f"{BASE_URL}/api/listings?region=QC",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        listings = data if isinstance(data, list) else data.get("listings", data.get("items", []))
        
        # All returned listings should have QC region
        for listing in listings:
            region = listing.get("region", "")
            if region:  # Some may not have region
                assert region.upper() == "QC", f"Expected region QC, got {region}"
        
        print(f"Found {len(listings)} listings in QC")


# Cleanup test data
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_listings(admin_token):
    """Cleanup TEST_ prefixed listings after tests"""
    yield
    
    if admin_token:
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get listings to find test items
        response = requests.get(f"{BASE_URL}/api/listings", headers=headers)
        if response.status_code == 200:
            data = response.json()
            listings = data if isinstance(data, list) else data.get("listings", data.get("items", []))
            
            for listing in listings:
                if listing.get("title", "").startswith("TEST_"):
                    listing_id = listing.get("id")
                    if listing_id:
                        requests.delete(
                            f"{BASE_URL}/api/listings/{listing_id}",
                            headers=headers
                        )
                        print(f"Cleaned up test listing: {listing_id}")
