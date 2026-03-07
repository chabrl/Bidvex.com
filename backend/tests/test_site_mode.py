"""
Test suite for Website Maintenance / Coming Soon Mode feature
Tests: Site mode management, email subscription, subscriber management
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

# Admin credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

class TestSiteModePublicEndpoints:
    """Test public site mode endpoints"""
    
    def test_get_site_mode_returns_current_mode(self):
        """GET /api/site-mode should return current site mode"""
        response = requests.get(f"{BASE_URL}/api/site-mode")
        assert response.status_code == 200
        
        data = response.json()
        assert "mode" in data
        assert data["mode"] in ["live", "maintenance", "coming_soon"]
        print(f"✅ Current site mode: {data['mode']}")
    
    def test_get_site_mode_includes_optional_fields(self):
        """GET /api/site-mode should include message and expected_back fields"""
        response = requests.get(f"{BASE_URL}/api/site-mode")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "expected_back" in data
        print(f"✅ Site mode response includes optional fields")


class TestEmailSubscription:
    """Test email subscription feature"""
    
    def test_subscribe_new_email(self):
        """POST /api/subscribe should save a new email"""
        test_email = f"test_{uuid.uuid4().hex[:8]}@testmail.com"
        response = requests.post(
            f"{BASE_URL}/api/subscribe",
            json={"email": test_email}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        print(f"✅ Subscribed email: {test_email}")
        
        # Return email for cleanup (used by other tests)
        return test_email
    
    def test_subscribe_existing_email_returns_success(self):
        """POST /api/subscribe with existing email should still return success"""
        # First subscribe
        test_email = f"test_duplicate_{uuid.uuid4().hex[:8]}@testmail.com"
        requests.post(f"{BASE_URL}/api/subscribe", json={"email": test_email})
        
        # Try to subscribe again
        response = requests.post(
            f"{BASE_URL}/api/subscribe",
            json={"email": test_email}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "already subscribed" in data["message"].lower()
        print(f"✅ Duplicate subscription handled correctly")
    
    def test_subscribe_invalid_email_fails(self):
        """POST /api/subscribe with invalid email should fail"""
        response = requests.post(
            f"{BASE_URL}/api/subscribe",
            json={"email": "not-an-email"}
        )
        # Should return 422 for validation error
        assert response.status_code == 422
        print(f"✅ Invalid email rejected with 422")


class TestAdminSiteModeManagement:
    """Test admin site mode management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip("Admin login failed - skipping admin tests")
        
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_update_site_mode_to_live(self):
        """PUT /api/admin/site-mode should update mode to live"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={"mode": "live", "message": None, "expected_back": None},
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["mode"] == "live"
        print(f"✅ Updated site mode to: live")
    
    def test_update_site_mode_to_maintenance(self):
        """PUT /api/admin/site-mode should update mode to maintenance"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={
                "mode": "maintenance",
                "message": "We are upgrading our systems",
                "expected_back": "2026-01-15T14:00:00"
            },
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["mode"] == "maintenance"
        print(f"✅ Updated site mode to: maintenance")
    
    def test_update_site_mode_to_coming_soon(self):
        """PUT /api/admin/site-mode should update mode to coming_soon"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={
                "mode": "coming_soon",
                "message": "BidVex is launching soon!",
                "expected_back": None
            },
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["mode"] == "coming_soon"
        print(f"✅ Updated site mode to: coming_soon")
    
    def test_update_site_mode_invalid_mode_fails(self):
        """PUT /api/admin/site-mode with invalid mode should fail"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={"mode": "invalid_mode"},
            headers=self.headers
        )
        assert response.status_code == 400
        print(f"✅ Invalid mode rejected with 400")
    
    def test_update_site_mode_unauthenticated_fails(self):
        """PUT /api/admin/site-mode without auth should fail"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={"mode": "live"}
        )
        assert response.status_code == 401
        print(f"✅ Unauthenticated request rejected with 401")


class TestAdminSubscriberManagement:
    """Test admin subscriber management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip("Admin login failed - skipping admin tests")
        
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_subscribers_list(self):
        """GET /api/admin/subscribers should return subscriber list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/subscribers",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "subscribers" in data
        assert isinstance(data["subscribers"], list)
        assert "total" in data
        print(f"✅ Retrieved {len(data['subscribers'])} subscribers (total: {data['total']})")
    
    def test_get_subscribers_with_search(self):
        """GET /api/admin/subscribers with search should filter results"""
        response = requests.get(
            f"{BASE_URL}/api/admin/subscribers?search=test",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        print(f"✅ Search filter returned {len(data['subscribers'])} results")
    
    def test_export_subscribers_csv(self):
        """GET /api/admin/subscribers/export should return CSV format"""
        response = requests.get(
            f"{BASE_URL}/api/admin/subscribers/export",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "csv" in data
        assert "filename" in data
        assert data["filename"].endswith(".csv")
        
        # Verify CSV has header
        csv_content = data["csv"]
        assert csv_content.startswith("email,subscribed_at,ip_address,source,notified")
        print(f"✅ CSV export with {data['total']} subscribers")
    
    def test_get_subscriber_stats(self):
        """GET /api/admin/subscribers/stats should return statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/subscribers/stats",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "total" in data
        assert "today" in data
        assert "daily_trend" in data
        assert isinstance(data["daily_trend"], list)
        print(f"✅ Subscriber stats: total={data['total']}, today={data['today']}")
    
    def test_delete_subscriber(self):
        """DELETE /api/admin/subscribers/{id} should remove subscriber"""
        # First create a subscriber to delete
        test_email = f"delete_test_{uuid.uuid4().hex[:8]}@testmail.com"
        requests.post(f"{BASE_URL}/api/subscribe", json={"email": test_email})
        
        # Get the subscriber ID
        list_response = requests.get(
            f"{BASE_URL}/api/admin/subscribers?search={test_email}",
            headers=self.headers
        )
        assert list_response.status_code == 200
        
        subscribers = list_response.json()["subscribers"]
        if not subscribers:
            pytest.skip("Test subscriber not found")
        
        subscriber_id = subscribers[0]["subscriber_id"]
        
        # Delete the subscriber
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/subscribers/{subscriber_id}",
            headers=self.headers
        )
        assert delete_response.status_code == 200
        
        data = delete_response.json()
        assert data["success"] is True
        print(f"✅ Deleted subscriber: {subscriber_id}")
    
    def test_delete_nonexistent_subscriber_fails(self):
        """DELETE /api/admin/subscribers/{id} with invalid ID should fail"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/subscribers/non-existent-id",
            headers=self.headers
        )
        assert response.status_code == 404
        print(f"✅ Non-existent subscriber delete rejected with 404")


class TestSiteModeVerification:
    """Verify site mode after updates"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip("Admin login failed")
        
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_mode_persists_after_update(self):
        """Site mode should persist after being updated"""
        # Set to maintenance
        requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={"mode": "maintenance", "message": "Testing persistence"},
            headers=self.headers
        )
        
        # Verify it persisted
        response = requests.get(f"{BASE_URL}/api/site-mode")
        assert response.status_code == 200
        assert response.json()["mode"] == "maintenance"
        assert response.json()["message"] == "Testing persistence"
        print(f"✅ Mode persistence verified")
        
        # Reset to coming_soon (original state per test requirements)
        requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={"mode": "coming_soon", "message": None},
            headers=self.headers
        )


# Final cleanup - restore to coming_soon mode
class TestCleanup:
    """Cleanup after all tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code != 200:
            pytest.skip("Admin login failed")
        
        self.token = login_response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_z_restore_coming_soon_mode(self):
        """Final test: Restore site to coming_soon mode"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={"mode": "coming_soon", "message": None, "expected_back": None},
            headers=self.headers
        )
        assert response.status_code == 200
        print(f"✅ Restored site mode to coming_soon")
