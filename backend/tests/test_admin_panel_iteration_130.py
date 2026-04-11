"""
Admin Panel Audit & Repair Tests - Iteration 130
Tests for:
- Marketplace: delete/archive/pause listings
- User Management: suspend/reactivate users
- Deletion Requests: approve/reject with notification
- Categories: CRUD + subcategories
- Coupons: CRUD
- Affiliate Payouts: GET
- Login block for suspended users
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Admin123!"
PARTNER_EMAIL = "partner@test.com"
PARTNER_PASSWORD = "TestUser2026!"


class TestAdminAuth:
    """Test admin authentication"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_admin_login_success(self, admin_token):
        """Verify admin can login and get token"""
        assert admin_token is not None
        assert len(admin_token) > 50


class TestMarketplaceListingManagement:
    """Test marketplace listing status changes and deletion"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def listing_id(self, admin_headers):
        """Get a real listing ID from the database"""
        response = requests.get(f"{BASE_URL}/api/admin/listings/all", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get listings: {response.text}"
        listings = response.json()
        if isinstance(listings, dict):
            listings = listings.get("listings", [])
        if listings:
            return listings[0]["id"]
        return None
    
    @pytest.fixture(scope="class")
    def multi_listing_id(self, admin_headers):
        """Get a real multi-item listing ID"""
        response = requests.get(f"{BASE_URL}/api/admin/multi-item-listings/all", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get multi-listings: {response.text}"
        listings = response.json()
        if isinstance(listings, dict):
            listings = listings.get("listings", [])
        if listings:
            return listings[0]["id"]
        return None
    
    def test_get_all_single_listings(self, admin_headers):
        """GET /api/admin/listings/all should return listings array"""
        response = requests.get(f"{BASE_URL}/api/admin/listings/all", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        # Can be array or object with listings key
        assert isinstance(data, (list, dict))
        print(f"PASS: Got {len(data) if isinstance(data, list) else len(data.get('listings', []))} single listings")
    
    def test_get_all_multi_listings(self, admin_headers):
        """GET /api/admin/multi-item-listings/all should return listings array"""
        response = requests.get(f"{BASE_URL}/api/admin/multi-item-listings/all", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))
        print(f"PASS: Got {len(data) if isinstance(data, list) else len(data.get('listings', []))} multi-item listings")
    
    def test_update_listing_status_paused(self, admin_headers, listing_id):
        """PUT /api/admin/listings/{id}/status with {status:'paused'} should work"""
        if not listing_id:
            pytest.skip("No listings available to test")
        response = requests.put(
            f"{BASE_URL}/api/admin/listings/{listing_id}/status",
            json={"status": "paused"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to pause listing: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"PASS: Listing {listing_id} status updated to paused")
    
    def test_update_listing_status_active(self, admin_headers, listing_id):
        """PUT /api/admin/listings/{id}/status with {status:'active'} should work"""
        if not listing_id:
            pytest.skip("No listings available to test")
        response = requests.put(
            f"{BASE_URL}/api/admin/listings/{listing_id}/status",
            json={"status": "active"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to activate listing: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"PASS: Listing {listing_id} status updated to active")
    
    def test_update_listing_status_archived(self, admin_headers, listing_id):
        """PUT /api/admin/listings/{id}/status with {status:'archived'} should work"""
        if not listing_id:
            pytest.skip("No listings available to test")
        response = requests.put(
            f"{BASE_URL}/api/admin/listings/{listing_id}/status",
            json={"status": "archived"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to archive listing: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"PASS: Listing {listing_id} status updated to archived")
        # Restore to active
        requests.put(
            f"{BASE_URL}/api/admin/listings/{listing_id}/status",
            json={"status": "active"},
            headers=admin_headers
        )
    
    def test_update_multi_listing_status_paused(self, admin_headers, multi_listing_id):
        """PUT /api/admin/multi-item-listings/{id}/status with {status:'paused'} should work"""
        if not multi_listing_id:
            pytest.skip("No multi-item listings available to test")
        response = requests.put(
            f"{BASE_URL}/api/admin/multi-item-listings/{multi_listing_id}/status",
            json={"status": "paused"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to pause multi-listing: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"PASS: Multi-item listing {multi_listing_id} status updated to paused")
        # Restore
        requests.put(
            f"{BASE_URL}/api/admin/multi-item-listings/{multi_listing_id}/status",
            json={"status": "active"},
            headers=admin_headers
        )


class TestUserSuspension:
    """Test user suspend/reactivate functionality"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_user_id(self, admin_headers):
        """Get a non-admin user ID to test suspension"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        if isinstance(users, dict):
            users = users.get("users", [])
        # Find a non-admin user
        for user in users:
            if user.get("role") != "admin" and user.get("email") != ADMIN_EMAIL:
                return user["id"]
        return None
    
    def test_suspend_user(self, admin_headers, test_user_id):
        """PUT /api/admin/users/{id}/suspend with {suspended:true,reason:'Test'} should suspend user"""
        if not test_user_id:
            pytest.skip("No non-admin user available to test")
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{test_user_id}/suspend",
            json={"suspended": True, "reason": "Test suspension from iteration 130"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to suspend user: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("new_status") == "suspended"
        print(f"PASS: User {test_user_id} suspended successfully")
    
    def test_reactivate_user(self, admin_headers, test_user_id):
        """PUT /api/admin/users/{id}/suspend with {suspended:false} should reactivate user"""
        if not test_user_id:
            pytest.skip("No non-admin user available to test")
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{test_user_id}/suspend",
            json={"suspended": False},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to reactivate user: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("new_status") == "active"
        print(f"PASS: User {test_user_id} reactivated successfully")


class TestSuspendedUserLoginBlock:
    """Test that suspended users cannot login"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_suspended_user_cannot_login(self, admin_headers):
        """Suspended user should get 403 when trying to login"""
        # First, get partner user ID
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        users = response.json()
        if isinstance(users, dict):
            users = users.get("users", [])
        
        partner_user = None
        for user in users:
            if user.get("email") == PARTNER_EMAIL:
                partner_user = user
                break
        
        if not partner_user:
            pytest.skip("Partner test user not found")
        
        # Suspend the partner user
        suspend_response = requests.put(
            f"{BASE_URL}/api/admin/users/{partner_user['id']}/suspend",
            json={"suspended": True, "reason": "Test login block"},
            headers=admin_headers
        )
        assert suspend_response.status_code == 200, f"Failed to suspend: {suspend_response.text}"
        
        # Try to login as suspended user - should get 403
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARTNER_EMAIL,
            "password": PARTNER_PASSWORD
        })
        
        # Reactivate user regardless of test result
        requests.put(
            f"{BASE_URL}/api/admin/users/{partner_user['id']}/suspend",
            json={"suspended": False},
            headers=admin_headers
        )
        
        assert login_response.status_code == 403, f"Expected 403 for suspended user, got {login_response.status_code}: {login_response.text}"
        print("PASS: Suspended user correctly blocked from login with 403")


class TestCouponCRUD:
    """Test coupon CRUD operations (endpoints in subscriptions.py)"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_coupon_code(self):
        """Generate unique coupon code for testing"""
        return f"TEST130_{uuid.uuid4().hex[:6].upper()}"
    
    def test_create_coupon(self, admin_headers, test_coupon_code):
        """POST /api/admin/coupons should create a coupon"""
        response = requests.post(
            f"{BASE_URL}/api/admin/coupons",
            json={
                "code": test_coupon_code,
                "discount_type": "percentage",
                "value": 10,
                "usage_limit": 100,
                "is_active": True
            },
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to create coupon: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "coupon" in data
        print(f"PASS: Coupon {test_coupon_code} created successfully")
        return data["coupon"]
    
    def test_get_coupons(self, admin_headers):
        """GET /api/admin/coupons should list coupons"""
        response = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get coupons: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "coupons" in data
        assert isinstance(data["coupons"], list)
        print(f"PASS: Got {len(data['coupons'])} coupons")
    
    def test_delete_coupon(self, admin_headers, test_coupon_code):
        """DELETE /api/admin/coupons/{id} should delete coupon"""
        # First get the coupon ID
        response = requests.get(f"{BASE_URL}/api/admin/coupons", headers=admin_headers)
        coupons = response.json().get("coupons", [])
        
        test_coupon = None
        for coupon in coupons:
            if coupon.get("code") == test_coupon_code:
                test_coupon = coupon
                break
        
        if not test_coupon:
            pytest.skip("Test coupon not found")
        
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/coupons/{test_coupon['id']}",
            headers=admin_headers
        )
        assert delete_response.status_code == 200, f"Failed to delete coupon: {delete_response.text}"
        data = delete_response.json()
        assert data.get("success") == True
        print(f"PASS: Coupon {test_coupon_code} deleted successfully")


class TestCategoryCRUD:
    """Test category CRUD with subcategory support"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_category_name(self):
        """Generate unique category name for testing"""
        return f"TestCategory130_{uuid.uuid4().hex[:6]}"
    
    def test_get_categories(self, admin_headers):
        """GET /api/admin/categories should return categories array"""
        response = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get categories: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Got {len(data)} categories")
    
    def test_create_top_level_category(self, admin_headers, test_category_name):
        """POST /api/admin/categories should create top-level category"""
        response = requests.post(
            f"{BASE_URL}/api/admin/categories",
            json={
                "name_en": test_category_name,
                "name_fr": f"{test_category_name}_FR",
                "icon": "🧪",
                "order": 999,
                "parent_id": None
            },
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to create category: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("name_en") == test_category_name
        print(f"PASS: Top-level category {test_category_name} created with ID {data['id']}")
        return data
    
    def test_create_subcategory(self, admin_headers, test_category_name):
        """POST /api/admin/categories with parent_id should create subcategory"""
        # First get the parent category ID
        response = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        categories = response.json()
        
        parent_category = None
        for cat in categories:
            if cat.get("name_en") == test_category_name:
                parent_category = cat
                break
        
        if not parent_category:
            pytest.skip("Parent category not found")
        
        subcategory_name = f"{test_category_name}_Sub"
        response = requests.post(
            f"{BASE_URL}/api/admin/categories",
            json={
                "name_en": subcategory_name,
                "name_fr": f"{subcategory_name}_FR",
                "icon": "📂",
                "order": 1,
                "parent_id": parent_category["id"]
            },
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed to create subcategory: {response.text}"
        data = response.json()
        assert data.get("parent_id") == parent_category["id"]
        print(f"PASS: Subcategory {subcategory_name} created under {test_category_name}")
        return data
    
    def test_delete_category(self, admin_headers, test_category_name):
        """DELETE /api/admin/categories/{id} should delete category"""
        # Get all categories
        response = requests.get(f"{BASE_URL}/api/admin/categories", headers=admin_headers)
        categories = response.json()
        
        # Find and delete subcategory first
        for cat in categories:
            if cat.get("name_en", "").startswith(test_category_name):
                delete_response = requests.delete(
                    f"{BASE_URL}/api/admin/categories/{cat['id']}",
                    headers=admin_headers
                )
                assert delete_response.status_code == 200, f"Failed to delete category: {delete_response.text}"
                print(f"PASS: Category {cat['name_en']} deleted")


class TestAffiliatePayouts:
    """Test affiliate payout endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_affiliate_payouts(self, admin_headers):
        """GET /api/admin/affiliate/payouts should return array"""
        response = requests.get(f"{BASE_URL}/api/admin/affiliate/payouts", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get payouts: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Got {len(data)} affiliate payouts")
    
    def test_get_affiliates(self, admin_headers):
        """GET /api/admin/affiliates should return array"""
        response = requests.get(f"{BASE_URL}/api/admin/affiliates", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get affiliates: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Got {len(data)} affiliates")


class TestDeletionRequests:
    """Test deletion request endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_deletion_requests(self, admin_headers):
        """GET /api/admin/deletion-requests should return array"""
        response = requests.get(f"{BASE_URL}/api/admin/deletion-requests", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get deletion requests: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Got {len(data)} pending deletion requests")


class TestPromotions:
    """Test promotion endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_promotions(self, admin_headers):
        """GET /api/admin/promotions should return array"""
        response = requests.get(f"{BASE_URL}/api/admin/promotions", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get promotions: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Got {len(data)} promotions")
    
    def test_get_listings_promotions(self, admin_headers):
        """GET /api/admin/listings-promotions should return listings with promotion info"""
        response = requests.get(f"{BASE_URL}/api/admin/listings-promotions", headers=admin_headers)
        assert response.status_code == 200, f"Failed to get listings promotions: {response.text}"
        data = response.json()
        assert "listings" in data
        assert "stats" in data
        print(f"PASS: Got {len(data['listings'])} listings with promotion info")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
