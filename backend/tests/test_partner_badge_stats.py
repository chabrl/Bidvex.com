"""
Partner Badge & Stats API Tests - Iteration 97
Tests for:
- GET /api/partner/badge/{user_id} - returns badge_type, is_verified_firm, partner_tier
- GET /api/partner/stats - returns partner stats (requires auth)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestPartnerBadgeAPI:
    """Tests for GET /api/partner/badge/{user_id}"""
    
    @pytest.fixture(scope="class")
    def admin_user_id(self):
        """Get admin user ID by logging in"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return data.get("user", {}).get("id")
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("token")
    
    def test_badge_endpoint_returns_200_for_valid_user(self, admin_user_id):
        """GET /api/partner/badge/{user_id} returns 200 for valid user"""
        response = requests.get(f"{BASE_URL}/api/partner/badge/{admin_user_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "user_id" in data, "Response should contain user_id"
        assert "badge_type" in data, "Response should contain badge_type"
        assert "is_verified_firm" in data, "Response should contain is_verified_firm"
        assert "partner_tier" in data, "Response should contain partner_tier"
        
        # Verify user_id matches
        assert data["user_id"] == admin_user_id
        
        # Verify data types
        assert isinstance(data["is_verified_firm"], bool), "is_verified_firm should be boolean"
        assert data["partner_tier"] in ["free", "pro", "vip", None], f"Unexpected partner_tier: {data['partner_tier']}"
        
        print(f"Badge data for admin: badge_type={data['badge_type']}, is_verified_firm={data['is_verified_firm']}, partner_tier={data['partner_tier']}")
    
    def test_badge_endpoint_returns_404_for_invalid_user(self):
        """GET /api/partner/badge/invalid-id returns 404"""
        response = requests.get(f"{BASE_URL}/api/partner/badge/invalid-user-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "404 response should contain detail message"
        print(f"404 response detail: {data['detail']}")
    
    def test_badge_endpoint_returns_404_for_nonexistent_uuid(self):
        """GET /api/partner/badge/{nonexistent_uuid} returns 404"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{BASE_URL}/api/partner/badge/{fake_uuid}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


class TestPartnerStatsAPI:
    """Tests for GET /api/partner/stats"""
    
    def get_auth_token(self):
        """Get fresh auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    def test_stats_endpoint_returns_403_without_auth(self):
        """GET /api/partner/stats returns 403 for unauthenticated requests"""
        response = requests.get(f"{BASE_URL}/api/partner/stats")
        # Should return 401 or 403 for unauthenticated
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated stats request returned: {response.status_code}")
    
    def test_stats_endpoint_returns_data_for_admin(self):
        """GET /api/partner/stats returns stats for admin user"""
        auth_token = self.get_auth_token()
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/partner/stats", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields for partner's own stats
        assert "my_active_listings" in data, "Response should contain my_active_listings"
        assert "my_total_listings" in data, "Response should contain my_total_listings"
        assert "my_total_bids_received" in data, "Response should contain my_total_bids_received"
        assert "my_projected_revenue" in data, "Response should contain my_projected_revenue"
        
        # Verify data types
        assert isinstance(data["my_active_listings"], int), "my_active_listings should be int"
        assert isinstance(data["my_total_listings"], int), "my_total_listings should be int"
        assert isinstance(data["my_total_bids_received"], int), "my_total_bids_received should be int"
        assert isinstance(data["my_projected_revenue"], (int, float)), "my_projected_revenue should be numeric"
        
        print(f"Partner stats: active={data['my_active_listings']}, total={data['my_total_listings']}, bids={data['my_total_bids_received']}, revenue={data['my_projected_revenue']}")
    
    def test_stats_endpoint_returns_platform_stats_for_admin(self):
        """GET /api/partner/stats also returns platform-wide stats for admin"""
        auth_token = self.get_auth_token()
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/partner/stats", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Platform-wide stats (from get_partner_stats)
        platform_fields = [
            "total_partners", "verified_partners", "pending_applications",
            "fee_paid_partners", "pro_subscribers", "trialing",
            "active_partner_listings", "total_partner_listings"
        ]
        
        for field in platform_fields:
            assert field in data, f"Response should contain platform stat: {field}"
            print(f"Platform stat {field}: {data[field]}")


class TestPartnerDashboardAPI:
    """Tests for GET /api/partner/dashboard"""
    
    def get_auth_token(self):
        """Get fresh auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    def test_dashboard_endpoint_requires_auth(self):
        """GET /api/partner/dashboard returns 401/403 without auth"""
        response = requests.get(f"{BASE_URL}/api/partner/dashboard")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_dashboard_endpoint_returns_data_for_partner(self):
        """GET /api/partner/dashboard returns dashboard data for partner/admin"""
        auth_token = self.get_auth_token()
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/partner/dashboard", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure
        assert "partner" in data, "Response should contain partner info"
        assert "stats" in data, "Response should contain stats"
        
        # Verify partner info
        partner = data["partner"]
        assert "platform_fee_paid" in partner, "Partner info should contain platform_fee_paid"
        
        # Verify stats
        stats = data["stats"]
        assert "active_listings" in stats, "Stats should contain active_listings"
        assert "total_listings" in stats, "Stats should contain total_listings"
        assert "total_bids_received" in stats, "Stats should contain total_bids_received"
        
        print(f"Dashboard partner: {partner}")
        print(f"Dashboard stats: {stats}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
