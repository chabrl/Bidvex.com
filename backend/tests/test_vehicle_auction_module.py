"""
Vehicle Auction Module - Backend API Tests
Tests for VIN decoder, seller registration, vehicle listings, and admin operations
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

# Test VINs (real VINs for NHTSA API testing)
TEST_VIN_TESLA = "5YJ3E1EA1JF000001"  # Tesla Model 3
TEST_VIN_FORD = "1FAHP3F29CL000001"  # Ford Focus
TEST_VIN_INVALID = "INVALID12345678"


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")


class TestAuthentication:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful: {data['user']['email']}")
        return data["access_token"]


class TestVINDecoder:
    """VIN Decoder API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_decode_valid_vin(self, auth_token):
        """Test VIN decode with valid VIN"""
        response = requests.get(
            f"{BASE_URL}/api/vehicles/decode-vin/{TEST_VIN_TESLA}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # VIN decoder should return vehicle info
        assert "make" in data or "year" in data
        print(f"✓ VIN decode successful: {data.get('make', 'N/A')} {data.get('model', 'N/A')}")
    
    def test_decode_invalid_vin_format(self, auth_token):
        """Test VIN decode with invalid VIN format"""
        response = requests.get(
            f"{BASE_URL}/api/vehicles/decode-vin/SHORTVIN",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400
        print("✓ Invalid VIN format correctly rejected")
    
    def test_decode_vin_requires_auth(self):
        """Test VIN decode requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicles/decode-vin/{TEST_VIN_TESLA}")
        assert response.status_code == 401
        print("✓ VIN decode correctly requires authentication")


class TestVehicleSellerRegistration:
    """Vehicle Seller Registration API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_seller_profile(self, auth_token):
        """Test getting seller profile"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-sellers/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Either 200 (has profile) or 404 (not registered)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "seller_type" in data
            assert "verification_status" in data
            print(f"✓ Seller profile found: {data.get('seller_type')} - {data.get('verification_status')}")
        else:
            print("✓ No seller profile (expected for new users)")
    
    def test_seller_registration_requires_auth(self):
        """Test seller registration requires authentication"""
        response = requests.post(f"{BASE_URL}/api/vehicle-sellers/register", json={
            "seller_type": "private"
        })
        assert response.status_code == 401
        print("✓ Seller registration correctly requires authentication")
    
    def test_register_private_seller(self, auth_token):
        """Test registering as private seller"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-sellers/register",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "seller_type": "private",
                "business_name": None,
                "business_address": None,
                "business_phone": None,
                "license_number": None,
                "license_province": None,
                "tax_id": None,
                "website": None,
                "description": "Test private seller"
            }
        )
        # Either 200 (success) or 400 (already registered)
        assert response.status_code in [200, 201, 400]
        if response.status_code in [200, 201]:
            data = response.json()
            assert data.get("seller_type") == "private"
            assert data.get("monthly_listing_limit") == 1  # Private sellers limited to 1/month
            print(f"✓ Private seller registered: limit={data.get('monthly_listing_limit')}/month")
        else:
            print("✓ Already registered as seller (expected)")


class TestVehicleListings:
    """Vehicle Listings API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_list_public_vehicles(self):
        """Test listing public vehicles (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
        data = response.json()
        assert "vehicles" in data
        assert "total" in data
        assert "page" in data
        print(f"✓ Public vehicle listing: {data.get('total')} vehicles found")
    
    def test_list_vehicles_with_filters(self):
        """Test listing vehicles with filters"""
        response = requests.get(f"{BASE_URL}/api/vehicles", params={
            "make": "Tesla",
            "year_min": 2020,
            "price_max": 100000,
            "page": 1,
            "limit": 10
        })
        assert response.status_code == 200
        data = response.json()
        assert "vehicles" in data
        print(f"✓ Filtered vehicle listing: {data.get('total')} vehicles match filters")
    
    def test_get_my_listings_requires_seller(self, auth_token):
        """Test getting my listings requires seller account"""
        response = requests.get(
            f"{BASE_URL}/api/vehicles/my/listings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Either 200 (has seller account) or 403 (not a seller)
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert "listings" in data
            print(f"✓ My listings: {len(data.get('listings', []))} listings found")
        else:
            print("✓ Correctly requires verified seller account")


class TestAdminOperations:
    """Admin Operations API tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_get_pending_sellers(self, admin_token):
        """Test getting pending sellers (admin only)"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/pending-sellers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "sellers" in data
        print(f"✓ Pending sellers: {len(data.get('sellers', []))} awaiting approval")
    
    def test_get_pending_vehicles(self, admin_token):
        """Test getting pending vehicles (admin only)"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/pending-vehicles",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "vehicles" in data
        print(f"✓ Pending vehicles: {len(data.get('vehicles', []))} awaiting approval")
    
    def test_get_audit_logs(self, admin_token):
        """Test getting audit logs (admin only)"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/audit-logs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        print(f"✓ Audit logs: {len(data.get('logs', []))} entries")
    
    def test_admin_endpoints_require_admin_role(self):
        """Test admin endpoints require admin role"""
        response = requests.get(f"{BASE_URL}/api/vehicle-admin/pending-sellers")
        assert response.status_code == 401
        print("✓ Admin endpoints correctly require authentication")


class TestSellerLimits:
    """Seller Limits Enforcement tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_seller_monthly_limit_info(self, auth_token):
        """Test seller profile includes monthly limit info"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-sellers/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            data = response.json()
            assert "monthly_listing_limit" in data
            assert "monthly_listing_count" in data
            
            # Verify limits based on seller type
            seller_type = data.get("seller_type")
            limit = data.get("monthly_listing_limit")
            
            if seller_type == "private":
                assert limit == 1, "Private sellers should have 1 vehicle/month limit"
            else:
                assert limit == 500, "Business sellers should have 500 vehicles/month limit"
            
            print(f"✓ Seller limits: {data.get('monthly_listing_count')}/{limit} ({seller_type})")
        else:
            print("✓ No seller profile to check limits")


class TestBiddingEndpoints:
    """Bidding API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_my_bids(self, auth_token):
        """Test getting user's bid history"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-bids/my",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "bids" in data
        print(f"✓ My bids: {len(data.get('bids', []))} bids found")
    
    def test_place_bid_requires_auth(self):
        """Test placing bid requires authentication"""
        response = requests.post(f"{BASE_URL}/api/vehicle-bids", json={
            "vehicle_id": "test-id",
            "amount": 10000
        })
        assert response.status_code == 401
        print("✓ Bidding correctly requires authentication")


class TestVehicleDetailEndpoint:
    """Vehicle Detail API tests"""
    
    def test_get_nonexistent_vehicle(self):
        """Test getting non-existent vehicle returns 404"""
        response = requests.get(f"{BASE_URL}/api/vehicles/nonexistent-id-12345")
        assert response.status_code == 404
        print("✓ Non-existent vehicle correctly returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
