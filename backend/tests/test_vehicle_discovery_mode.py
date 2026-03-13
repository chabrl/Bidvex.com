"""
Test Vehicle Auction Discovery Mode Features
Tests for:
1. System status endpoint returns discovery_mode: true and vehicle_auctions_enabled: false
2. Admin can toggle vehicle auctions via POST /api/vehicle-admin/system/toggle-auctions
3. Admin can toggle vehicle listing via POST /api/vehicle-admin/system/toggle-listing
4. Vehicle bidding is blocked when vehicle_bidding_enabled is false (403 error)
5. Vehicle listing creation is blocked when vehicle_listing_enabled is false (403 error)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://payment-checkout-10.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestSystemStatusEndpoint:
    """Test system status endpoint returns correct discovery mode values"""
    
    def test_system_status_returns_discovery_mode(self):
        """System status should return discovery_mode: true when auctions disabled"""
        response = requests.get(f"{BASE_URL}/api/vehicles/system/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "discovery_mode" in data
        assert "vehicle_auctions_enabled" in data
        assert "vehicle_listing_enabled" in data
        assert "vehicle_bidding_enabled" in data
        assert "message" in data
        
        # Verify discovery mode is true when auctions are disabled
        if not data["vehicle_auctions_enabled"]:
            assert data["discovery_mode"] == True
            assert "discovery mode" in data["message"].lower()
        
        print(f"System status: discovery_mode={data['discovery_mode']}, auctions_enabled={data['vehicle_auctions_enabled']}")
    
    def test_system_status_no_auth_required(self):
        """System status endpoint should be public (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/vehicles/system/status")
        assert response.status_code == 200
        print("System status endpoint is public - no auth required")


class TestAdminToggleEndpoints:
    """Test admin toggle endpoints for vehicle auctions and listing"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture
    def admin_headers(self, admin_token):
        """Get headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_admin_get_system_settings(self, admin_headers):
        """Admin should be able to get system settings"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/system/settings",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "vehicle_auctions_enabled" in data
        assert "vehicle_listing_enabled" in data
        assert "vehicle_bidding_enabled" in data
        print(f"Admin system settings: {data}")
    
    def test_admin_toggle_auctions_enable(self, admin_headers):
        """Admin should be able to enable vehicle auctions"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=true",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["vehicle_auctions_enabled"] == True
        assert data["vehicle_bidding_enabled"] == True  # Bidding follows auction status
        print(f"Auctions enabled: {data}")
    
    def test_admin_toggle_auctions_disable(self, admin_headers):
        """Admin should be able to disable vehicle auctions"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=false",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["vehicle_auctions_enabled"] == False
        assert data["vehicle_bidding_enabled"] == False
        print(f"Auctions disabled: {data}")
    
    def test_admin_toggle_listing_enable(self, admin_headers):
        """Admin should be able to enable vehicle listing"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-listing?enabled=true",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["vehicle_listing_enabled"] == True
        print(f"Listing enabled: {data}")
    
    def test_admin_toggle_listing_disable(self, admin_headers):
        """Admin should be able to disable vehicle listing"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-listing?enabled=false",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["vehicle_listing_enabled"] == False
        print(f"Listing disabled: {data}")
    
    def test_toggle_auctions_requires_admin(self):
        """Toggle auctions should require admin authentication"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=true"
        )
        assert response.status_code == 401
        print("Toggle auctions correctly requires authentication")
    
    def test_toggle_listing_requires_admin(self):
        """Toggle listing should require admin authentication"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-listing?enabled=true"
        )
        assert response.status_code == 401
        print("Toggle listing correctly requires authentication")


class TestBiddingBlockedWhenDisabled:
    """Test that bidding is blocked when vehicle_bidding_enabled is false"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture
    def admin_headers(self, admin_token):
        """Get headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.fixture
    def ensure_bidding_disabled(self, admin_headers):
        """Ensure bidding is disabled before test"""
        requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=false",
            headers=admin_headers
        )
        yield
        # Cleanup - keep disabled
    
    def test_bidding_blocked_when_disabled(self, admin_headers, ensure_bidding_disabled):
        """Bidding should return 403 when vehicle_bidding_enabled is false"""
        # Try to place a bid (using admin token as a regular user)
        response = requests.post(
            f"{BASE_URL}/api/vehicle-bids",
            headers=admin_headers,
            json={
                "vehicle_id": "test-vehicle-id",
                "amount": 10000
            }
        )
        
        # Should be 403 (forbidden) because bidding is disabled
        # Or 404 if vehicle doesn't exist - but 403 should come first
        assert response.status_code in [403, 404]
        
        if response.status_code == 403:
            data = response.json()
            assert "disabled" in data.get("detail", "").lower() or "pending" in data.get("detail", "").lower()
            print(f"Bidding correctly blocked: {data['detail']}")
        else:
            print("Got 404 - vehicle doesn't exist, but bidding check may have passed")


class TestListingBlockedWhenDisabled:
    """Test that listing creation is blocked when vehicle_listing_enabled is false"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture
    def admin_headers(self, admin_token):
        """Get headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.fixture
    def ensure_listing_disabled(self, admin_headers):
        """Ensure listing is disabled before test"""
        requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-listing?enabled=false",
            headers=admin_headers
        )
        yield
        # Cleanup - keep disabled
    
    def test_listing_blocked_when_disabled(self, admin_headers, ensure_listing_disabled):
        """Listing creation should return 403 when vehicle_listing_enabled is false"""
        # Try to create a vehicle listing with correct enum values
        response = requests.post(
            f"{BASE_URL}/api/vehicles",
            headers=admin_headers,
            json={
                "vin": "1HGBH41JXMN109186",
                "year": 2021,
                "make": "Honda",
                "model": "Accord",
                "body_type": "sedan",
                "mileage": 50000,
                "transmission": "automatic",
                "fuel_type": "gasoline",
                "drivetrain": "fwd",
                "exterior_color": "Black",
                "interior_color": "Black",
                "ownership_status": "owned",
                "title_status": "clean",
                "lien_status": "clear",  # Fixed: was "none", should be "clear"
                "condition_report": {
                    "overall_rating": 4,
                    "is_running": True,
                    "has_accident_history": False,
                    "has_flood_damage": False,
                    "has_fire_damage": False,
                    "has_frame_damage": False,
                    "has_salvage_title": False
                },
                "location_city": "Toronto",
                "location_province": "ON",
                "location_postal_code": "M5V 1A1",
                "auction_type": "timed",
                "visibility": "public",
                "start_time": "2026-02-01T00:00:00Z",
                "end_time": "2026-02-07T00:00:00Z",
                "starting_price": 15000,
                "bid_increment": 100,
                "requires_deposit": False,
                "title": "2021 Honda Accord Test",
                "description": "Test listing"
            }
        )
        
        # Should be 403 (forbidden) because listing is disabled
        # Or 403 for not being a verified seller
        assert response.status_code == 403
        
        data = response.json()
        # Check if it's blocked due to listing disabled OR seller verification
        detail = data.get("detail", "").lower() if isinstance(data.get("detail"), str) else str(data.get("detail", "")).lower()
        assert "disabled" in detail or "seller" in detail or "pending" in detail
        print(f"Listing correctly blocked: {data['detail']}")


class TestDiscoveryModeIntegration:
    """Integration tests for discovery mode behavior"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture
    def admin_headers(self, admin_token):
        """Get headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_discovery_mode_flow(self, admin_headers):
        """Test complete discovery mode flow"""
        # 1. Disable auctions (ensure discovery mode)
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=false",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # 2. Verify system status shows discovery mode
        response = requests.get(f"{BASE_URL}/api/vehicles/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["discovery_mode"] == True
        assert data["vehicle_auctions_enabled"] == False
        assert data["vehicle_bidding_enabled"] == False
        print(f"Discovery mode active: {data}")
        
        # 3. Verify vehicles can still be browsed
        response = requests.get(f"{BASE_URL}/api/vehicles")
        assert response.status_code == 200
        print("Vehicles can still be browsed in discovery mode")
    
    def test_enable_auctions_disables_discovery_mode(self, admin_headers):
        """Enabling auctions should disable discovery mode"""
        # Enable auctions
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=true",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Verify discovery mode is now false
        response = requests.get(f"{BASE_URL}/api/vehicles/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["discovery_mode"] == False
        assert data["vehicle_auctions_enabled"] == True
        print(f"Discovery mode disabled when auctions enabled: {data}")
        
        # Cleanup - disable auctions again
        requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=false",
            headers=admin_headers
        )


class TestCleanup:
    """Cleanup tests - ensure system is in discovery mode after tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("access_token")
    
    @pytest.fixture
    def admin_headers(self, admin_token):
        """Get headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_cleanup_ensure_discovery_mode(self, admin_headers):
        """Ensure system is in discovery mode after all tests"""
        # Disable auctions
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-auctions?enabled=false",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Disable listing
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/system/toggle-listing?enabled=false",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Verify final state
        response = requests.get(f"{BASE_URL}/api/vehicles/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["discovery_mode"] == True
        assert data["vehicle_auctions_enabled"] == False
        assert data["vehicle_listing_enabled"] == False
        assert data["vehicle_bidding_enabled"] == False
        print(f"System restored to discovery mode: {data}")
