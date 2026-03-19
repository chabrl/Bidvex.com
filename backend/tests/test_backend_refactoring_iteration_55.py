"""
BidVex Backend Refactoring Tests - Iteration 55
Tests for routes extracted from server.py into:
- routes/listings.py (listings CRUD, multi-item listings)
- routes/auctions.py (bids, auto-bid, bid history, buy now)

These tests verify the refactoring didn't break existing functionality.
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestAdminAuth:
    """Get admin token for authenticated endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Login as admin and get access token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        # Token field is 'access_token' not 'token'
        token = data.get("access_token")
        assert token, f"No access_token in response: {data}"
        print(f"✅ Admin authenticated successfully")
        return token


class TestListingsEndpoints(TestAdminAuth):
    """Test listings CRUD endpoints extracted to routes/listings.py"""
    
    # ========== GET /api/listings ==========
    def test_get_listings_returns_200(self):
        """GET /api/listings returns 200 and list of listings"""
        response = requests.get(f"{BASE_URL}/api/listings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Response should be a list
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"
        print(f"✅ GET /api/listings returns 200 with {len(data)} listings")
    
    def test_get_listings_with_filters(self):
        """GET /api/listings with query params works"""
        response = requests.get(f"{BASE_URL}/api/listings?limit=5&skip=0")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ GET /api/listings with filters works, got {len(data)} items")
    
    # ========== GET /api/listings/{listing_id} ==========
    def test_get_listing_not_found(self):
        """GET /api/listings/{listing_id} returns 404 for non-existent listing"""
        fake_id = "non-existent-listing-id-12345"
        response = requests.get(f"{BASE_URL}/api/listings/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✅ GET /api/listings/{fake_id} returns 404 for non-existent listing")
    
    def test_get_listing_detail_if_exists(self):
        """GET /api/listings/{listing_id} returns listing detail"""
        # First get a listing ID
        response = requests.get(f"{BASE_URL}/api/listings?limit=1")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                listing_id = data[0].get("id")
                # Get the specific listing
                detail_response = requests.get(f"{BASE_URL}/api/listings/{listing_id}")
                assert detail_response.status_code == 200, f"Expected 200, got {detail_response.status_code}"
                listing = detail_response.json()
                assert listing.get("id") == listing_id, "Listing ID mismatch"
                print(f"✅ GET /api/listings/{listing_id} returns listing detail")
            else:
                print("⚠️ No listings available to test detail endpoint")
        else:
            print("⚠️ Could not fetch listings to test detail endpoint")
    
    # ========== POST /api/listings (agreement_accepted validation) ==========
    def test_create_listing_without_agreement_returns_422(self, admin_token):
        """POST /api/listings with agreement_accepted=false returns 422 with agreement_required"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        listing_data = {
            "title": "Test Listing",
            "description": "Test description",
            "category": "Electronics",
            "condition": "New",
            "starting_price": 100.0,
            "images": [],
            "location": "Montreal, QC",
            "city": "Montreal",
            "region": "Quebec",
            "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "agreement_accepted": False  # Should trigger 422
        }
        response = requests.post(f"{BASE_URL}/api/listings", json=listing_data, headers=headers)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        data = response.json()
        # Check for agreement_required error type
        detail = data.get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("type") == "agreement_required", f"Expected agreement_required, got: {detail}"
        print(f"✅ POST /api/listings with agreement_accepted=false returns 422 with agreement_required")
    
    def test_create_listing_with_agreement_admin_bypass(self, admin_token):
        """POST /api/listings with agreement_accepted=true creates listing (admin bypasses phone/payment checks)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        unique_title = f"Test Listing {datetime.now().timestamp()}"
        listing_data = {
            "title": unique_title,
            "description": "Test description for admin bypass",
            "category": "Electronics",
            "condition": "New",
            "starting_price": 50.0,
            "images": ["https://example.com/image.jpg"],
            "location": "Montreal, QC",
            "city": "Montreal",
            "region": "Quebec",
            "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "agreement_accepted": True  # Should pass
        }
        response = requests.post(f"{BASE_URL}/api/listings", json=listing_data, headers=headers)
        # Admin can bypass phone_verified and payment_method checks
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("title") == unique_title, f"Title mismatch: {data}"
        print(f"✅ POST /api/listings with agreement_accepted=true creates listing (admin bypass works)")
        
        # Cleanup: delete the created listing
        listing_id = data.get("id")
        if listing_id:
            requests.delete(f"{BASE_URL}/api/listings/{listing_id}", headers=headers)


class TestMultiItemListingsEndpoints(TestAdminAuth):
    """Test multi-item listings endpoints extracted to routes/listings.py"""
    
    # ========== GET /api/multi-item-listings ==========
    def test_get_multi_item_listings_returns_200(self):
        """GET /api/multi-item-listings returns 200"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Response should be a list
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"
        print(f"✅ GET /api/multi-item-listings returns 200 with {len(data)} auctions")
    
    def test_get_multi_item_listings_with_filters(self):
        """GET /api/multi-item-listings with query params works"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=5&status=active")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ GET /api/multi-item-listings with filters works, got {len(data)} items")
    
    # ========== GET /api/multi-item-listings/{id} ==========
    def test_get_multi_item_listing_not_found(self):
        """GET /api/multi-item-listings/{id} returns 404 for non-existent listing"""
        fake_id = "non-existent-multi-listing-12345"
        response = requests.get(f"{BASE_URL}/api/multi-item-listings/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✅ GET /api/multi-item-listings/{fake_id} returns 404 for non-existent listing")
    
    def test_get_multi_item_listing_detail_if_exists(self):
        """GET /api/multi-item-listings/{id} returns detail"""
        # First get a multi-item listing ID
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=1")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                listing_id = data[0].get("id")
                # Get the specific listing
                detail_response = requests.get(f"{BASE_URL}/api/multi-item-listings/{listing_id}")
                assert detail_response.status_code == 200, f"Expected 200, got {detail_response.status_code}"
                listing = detail_response.json()
                assert listing.get("id") == listing_id, "Listing ID mismatch"
                print(f"✅ GET /api/multi-item-listings/{listing_id} returns detail")
            else:
                print("⚠️ No multi-item listings available to test detail endpoint")
        else:
            print("⚠️ Could not fetch multi-item listings to test detail endpoint")
    
    # ========== POST /api/multi-item-listings (agreement validation) ==========
    def test_create_multi_item_listing_without_agreement_returns_422(self, admin_token):
        """POST /api/multi-item-listings with agreement_accepted=false returns 422"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        listing_data = {
            "title": "Test Multi-Item Auction",
            "description": "Test description",
            "category": "Estate Sale",
            "location": "Montreal, QC",
            "city": "Montreal",
            "region": "Quebec",
            "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "lots": [
                {
                    "lot_number": 1,
                    "title": "Test Lot 1",
                    "description": "Test lot description",
                    "quantity": 1,
                    "starting_price": 10.0,
                    "current_price": 10.0,
                    "condition": "Good"
                }
            ],
            "agreement_accepted": False  # Should trigger 422
        }
        response = requests.post(f"{BASE_URL}/api/multi-item-listings", json=listing_data, headers=headers)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        data = response.json()
        detail = data.get("detail", {})
        if isinstance(detail, dict):
            assert detail.get("type") == "agreement_required", f"Expected agreement_required, got: {detail}"
        print(f"✅ POST /api/multi-item-listings with agreement_accepted=false returns 422")


class TestBidsEndpoints(TestAdminAuth):
    """Test bid endpoints extracted to routes/auctions.py (bids_router)"""
    
    # ========== GET /api/bids/listing/{listing_id} ==========
    def test_get_listing_bids_returns_200(self):
        """GET /api/bids/listing/{listing_id} returns 200 with array"""
        # Use a random listing ID - should return empty array if no bids
        test_listing_id = "some-listing-id-12345"
        response = requests.get(f"{BASE_URL}/api/bids/listing/{test_listing_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list/array, got {type(data)}: {data}"
        print(f"✅ GET /api/bids/listing/{test_listing_id} returns 200 with array ({len(data)} bids)")
    
    def test_get_listing_bids_with_existing_listing(self):
        """GET /api/bids/listing/{listing_id} returns bids for existing listing"""
        # First get a listing ID
        response = requests.get(f"{BASE_URL}/api/listings?limit=1")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                listing_id = data[0].get("id")
                bids_response = requests.get(f"{BASE_URL}/api/bids/listing/{listing_id}")
                assert bids_response.status_code == 200, f"Expected 200, got {bids_response.status_code}"
                bids = bids_response.json()
                assert isinstance(bids, list), "Bids should be a list"
                print(f"✅ GET /api/bids/listing/{listing_id} returns {len(bids)} bids")
            else:
                print("⚠️ No listings available to test bids endpoint")
        else:
            print("⚠️ Could not fetch listings to test bids endpoint")
    
    # ========== POST /api/bids (requires auth) ==========
    def test_place_bid_without_auth_returns_401(self):
        """POST /api/bids without auth returns 401"""
        bid_data = {
            "listing_id": "some-listing-id",
            "amount": 100.0
        }
        response = requests.post(f"{BASE_URL}/api/bids", json=bid_data)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print(f"✅ POST /api/bids without auth returns 401")
    
    def test_place_bid_for_nonexistent_listing_returns_404(self, admin_token):
        """POST /api/bids returns 404 for listing not found"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        bid_data = {
            "listing_id": "non-existent-listing-uuid-123",
            "amount": 100.0
        }
        response = requests.post(f"{BASE_URL}/api/bids", json=bid_data, headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✅ POST /api/bids returns 404 for listing not found")
    
    # ========== GET /api/bids/auto-bid (requires auth) ==========
    def test_get_auto_bids_requires_auth(self):
        """GET /api/bids/auto-bid without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/bids/auto-bid")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✅ GET /api/bids/auto-bid requires auth (401)")
    
    def test_get_auto_bids_with_auth_returns_200(self, admin_token):
        """GET /api/bids/auto-bid with auth returns 200"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/bids/auto-bid", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have auto_bids array
        assert "auto_bids" in data, f"Expected auto_bids key, got: {data}"
        print(f"✅ GET /api/bids/auto-bid returns 200 with {len(data.get('auto_bids', []))} auto-bids")


class TestSellerListingsEndpoints(TestAdminAuth):
    """Test seller listings endpoint extracted to routes/listings.py"""
    
    # ========== GET /api/sellers/{seller_id}/listings ==========
    def test_get_seller_listings_returns_200(self):
        """GET /api/sellers/{seller_id}/listings returns 200 with single_listings and multi_listings"""
        # Use a fake seller ID - should return empty arrays
        fake_seller_id = "fake-seller-id-12345"
        response = requests.get(f"{BASE_URL}/api/sellers/{fake_seller_id}/listings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have single_listings and multi_listings arrays
        assert "single_listings" in data, f"Expected single_listings key, got: {data}"
        assert "multi_listings" in data, f"Expected multi_listings key, got: {data}"
        assert "total" in data, f"Expected total key, got: {data}"
        print(f"✅ GET /api/sellers/{fake_seller_id}/listings returns 200 with single_listings and multi_listings")
    
    def test_get_seller_listings_with_real_seller(self, admin_token):
        """GET /api/sellers/{seller_id}/listings with real seller ID"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Get current user to get their ID
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        if me_response.status_code == 200:
            user = me_response.json()
            seller_id = user.get("id")
            response = requests.get(f"{BASE_URL}/api/sellers/{seller_id}/listings")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "single_listings" in data
            assert "multi_listings" in data
            print(f"✅ GET /api/sellers/{seller_id}/listings returns {data['total']} total listings")
        else:
            print("⚠️ Could not get user ID to test seller listings")


class TestRegressionEndpoints(TestAdminAuth):
    """Regression tests for endpoints that stayed in server.py"""
    
    # ========== GET /api/categories ==========
    def test_get_categories_returns_200(self):
        """GET /api/categories returns 200 (stays in server.py)"""
        response = requests.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✅ GET /api/categories returns 200 (regression check)")
    
    # ========== GET /api/fee-calculator ==========
    def test_fee_calculator_returns_200(self):
        """GET /api/fee-calculator?hammer_price=100 returns 200 (stays in server.py)"""
        response = requests.get(f"{BASE_URL}/api/fee-calculator?hammer_price=100")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should contain fee calculation fields
        assert "hammer_price" in data and "buyers_premium_amount" in data, f"Expected fee calculation, got: {data}"
        print(f"✅ GET /api/fee-calculator?hammer_price=100 returns 200 (regression check)")
    
    # ========== GET /api/marketplace/feature-flags ==========
    def test_feature_flags_returns_200(self):
        """GET /api/marketplace/feature-flags returns 200 (stays in server.py)"""
        response = requests.get(f"{BASE_URL}/api/marketplace/feature-flags")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should be a dict with feature flags
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        print(f"✅ GET /api/marketplace/feature-flags returns 200 (regression check)")
    
    # ========== GET /api/admin/users (admin auth) ==========
    def test_admin_users_returns_200(self, admin_token):
        """GET /api/admin/users?page=1 returns 200 with admin auth (admin.py regression check)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users?page=1", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have users array
        assert "users" in data or isinstance(data, list), f"Expected users data, got: {data}"
        print(f"✅ GET /api/admin/users?page=1 returns 200 (regression check)")
    
    # ========== GET /api/admin/marketplace-settings (admin auth) ==========
    def test_admin_marketplace_settings_returns_200(self, admin_token):
        """GET /api/admin/marketplace-settings returns 200 with admin auth (regression check)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/marketplace-settings", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have marketplace settings
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        print(f"✅ GET /api/admin/marketplace-settings returns 200 (regression check)")


class TestAuctionsRouterEndpoints(TestAdminAuth):
    """Test auction lifecycle endpoints in routes/auctions.py (auctions_router with /auctions prefix)"""
    
    # ========== GET /api/auctions/end-status/{auction_id} ==========
    def test_auction_end_status_not_found(self):
        """GET /api/auctions/end-status/{auction_id} returns 404 for non-existent auction"""
        fake_id = "non-existent-auction-12345"
        response = requests.get(f"{BASE_URL}/api/auctions/end-status/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✅ GET /api/auctions/end-status/{fake_id} returns 404 for non-existent auction")
    
    def test_auction_end_status_with_existing_listing(self):
        """GET /api/auctions/end-status/{auction_id} returns status for existing listing"""
        # Get a listing ID
        response = requests.get(f"{BASE_URL}/api/listings?limit=1")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                listing_id = data[0].get("id")
                status_response = requests.get(f"{BASE_URL}/api/auctions/end-status/{listing_id}")
                assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"
                status = status_response.json()
                assert "status" in status, f"Expected status field, got: {status}"
                print(f"✅ GET /api/auctions/end-status/{listing_id} returns status: {status.get('status')}")
            else:
                print("⚠️ No listings available to test auction end status")
        else:
            print("⚠️ Could not fetch listings to test auction end status")


# Run all tests when called directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
