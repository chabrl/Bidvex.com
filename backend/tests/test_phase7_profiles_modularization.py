"""
BidVex Phase 7: Profile Modularization Tests
Tests for 20 profile endpoints extracted from server.py to routes/profiles.py

Endpoints tested:
- User lookup: GET /api/users/{user_id}
- Profile summary: GET /api/users/{user_id}/profile-summary
- Profile update: PUT /api/users/me (name, phone, preferred_language)
- User stats: GET /api/users/me/stats
- Seller trust score: GET /api/sellers/{seller_id}/trust-score
- Tax info: GET /api/users/me/tax-info, PUT /api/users/me/tax-info
- GDPR: GET /api/user/data-deletion-status, GET /api/user/export-data
- Dashboard endpoints (regression): GET /api/dashboard/seller, GET /api/dashboard/buyer
- Admin endpoints (regression): GET /api/admin/email-preview

Critical: preferred_language update (en/fr) for bilingual SendGrid templates
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealth:
    """Health check - run first"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✅ PASS: GET /api/health returns healthy")


class TestAuthLogin:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Login with admin credentials and return token for subsequent tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        print("✅ PASS: POST /api/auth/login returns access_token")
        return data["access_token"], data["user"]


class TestProfileEndpoints:
    """Profile GET/PUT endpoints from routes/profiles.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def user_id(self):
        """Get user ID from login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["user"]["id"]
    
    def test_get_auth_me(self, auth_token):
        """GET /api/auth/me - Get current user profile"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "email" in data
        assert "preferred_language" in data
        print(f"✅ PASS: GET /api/auth/me returns user data with name='{data.get('name')}' and preferred_language='{data.get('preferred_language')}'")
    
    def test_update_profile_name_and_language_to_french(self, auth_token):
        """PUT /api/users/me - Update name and preferred_language to fr"""
        response = requests.put(
            f"{BASE_URL}/api/users/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "name": "Test Name Phase7",
                "preferred_language": "fr"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("message") == "Profile updated successfully"
        print("✅ PASS: PUT /api/users/me with name and preferred_language=fr returns success")
    
    def test_verify_profile_update_persisted(self, auth_token):
        """GET /api/auth/me - Verify name and language=fr persisted"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == "Test Name Phase7"
        assert data.get("preferred_language") == "fr"
        print(f"✅ PASS: Profile update persisted - name='{data.get('name')}', preferred_language='{data.get('preferred_language')}'")
    
    def test_restore_profile_to_original(self, auth_token):
        """PUT /api/users/me - Restore original name and language=en"""
        response = requests.put(
            f"{BASE_URL}/api/users/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "name": "Charbel Admin",
                "preferred_language": "en"
            }
        )
        assert response.status_code == 200
        print("✅ PASS: PUT /api/users/me restored to original name='Charbel Admin' and preferred_language='en'")
    
    def test_verify_restore_persisted(self, auth_token):
        """GET /api/auth/me - Verify restore was persisted"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == "Charbel Admin"
        assert data.get("preferred_language") == "en"
        print(f"✅ PASS: Profile restored - name='{data.get('name')}', preferred_language='{data.get('preferred_language')}'")
    
    def test_profile_language_validation_invalid(self, auth_token):
        """PUT /api/users/me - Invalid language should return 400"""
        response = requests.put(
            f"{BASE_URL}/api/users/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "preferred_language": "invalid"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "en" in str(data).lower() or "fr" in str(data).lower()
        print("✅ PASS: PUT /api/users/me with preferred_language='invalid' returns 400")


class TestProfileSummaryAndTrustScore:
    """Profile summary and seller trust score endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def user_id(self):
        """Get user ID"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["user"]["id"]
    
    def test_get_profile_summary(self, user_id):
        """GET /api/users/{user_id}/profile-summary - Get profile stats"""
        response = requests.get(f"{BASE_URL}/api/users/{user_id}/profile-summary")
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "name" in data
        assert "stats" in data
        assert "total_auctions" in data["stats"]
        print(f"✅ PASS: GET /api/users/{user_id}/profile-summary returns stats object with total_auctions={data['stats']['total_auctions']}")
    
    def test_get_seller_trust_score(self, user_id):
        """GET /api/sellers/{seller_id}/trust-score - Get trust metrics"""
        response = requests.get(f"{BASE_URL}/api/sellers/{user_id}/trust-score")
        assert response.status_code == 200
        data = response.json()
        assert "seller_id" in data
        assert "overall_score" in data
        assert "metrics" in data
        assert "total_ratings" in data
        print(f"✅ PASS: GET /api/sellers/{user_id}/trust-score returns overall_score={data['overall_score']} and metrics")


class TestUserStats:
    """User stats endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    def test_get_user_stats(self, auth_token):
        """GET /api/users/me/stats - Get user's transaction statistics"""
        response = requests.get(
            f"{BASE_URL}/api/users/me/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "annual_volume" in data
        assert "total_bids" in data
        assert "auctions_won" in data
        assert "period" in data
        print(f"✅ PASS: GET /api/users/me/stats returns annual_volume={data['annual_volume']} and total_bids={data['total_bids']}")


class TestTaxInfo:
    """Tax info GET/PUT endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    def test_get_tax_info(self, auth_token):
        """GET /api/users/me/tax-info - Get tax information"""
        response = requests.get(
            f"{BASE_URL}/api/users/me/tax-info",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "is_business" in data
        assert "account_type" in data
        print(f"✅ PASS: GET /api/users/me/tax-info returns is_business={data['is_business']} and account_type='{data['account_type']}'")
    
    def test_update_tax_info(self, auth_token):
        """PUT /api/users/me/tax-info - Update to business"""
        response = requests.put(
            f"{BASE_URL}/api/users/me/tax-info",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "is_business": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_business") == True
        assert data.get("account_type") == "business"
        print("✅ PASS: PUT /api/users/me/tax-info with is_business=true updates correctly")
    
    def test_restore_tax_info(self, auth_token):
        """PUT /api/users/me/tax-info - Restore to personal"""
        response = requests.put(
            f"{BASE_URL}/api/users/me/tax-info",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "is_business": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_business") == False
        assert data.get("account_type") == "personal"
        print("✅ PASS: PUT /api/users/me/tax-info restored to is_business=false, account_type=personal")


class TestGDPR:
    """GDPR data management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    def test_gdpr_deletion_status(self, auth_token):
        """GET /api/user/data-deletion-status - Check for pending deletion requests"""
        response = requests.get(
            f"{BASE_URL}/api/user/data-deletion-status",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "has_pending_request" in data
        print(f"✅ PASS: GET /api/user/data-deletion-status returns has_pending_request={data['has_pending_request']}")
    
    def test_gdpr_export_data(self, auth_token):
        """GET /api/user/export-data - Export all user data"""
        response = requests.get(
            f"{BASE_URL}/api/user/export-data",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "personal_information" in data
        assert "user_id" in data
        assert "export_date" in data
        assert "data_categories" in data
        print(f"✅ PASS: GET /api/user/export-data returns user data with personal_information")


class TestDashboardRegression:
    """Regression tests for dashboard endpoints after modularization"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    def test_dashboard_seller(self, auth_token):
        """GET /api/dashboard/seller - Verify still works after extraction"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/seller",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "active_listings" in data or "total_sales" in data or "sold_listings" in data
        print(f"✅ PASS: GET /api/dashboard/seller still works after extraction")
    
    def test_dashboard_buyer(self, auth_token):
        """GET /api/dashboard/buyer - Verify still works"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/buyer",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_bids" in data or "active_bids" in data or "won_items" in data
        print(f"✅ PASS: GET /api/dashboard/buyer still works")


class TestAdminRegression:
    """Regression tests for admin endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "charbeladmin@bidvex.com",
                "password": "Admin123!"
            }
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    def test_admin_email_preview(self, auth_token):
        """GET /api/admin/email-preview/WELCOME - Still works after profile extraction"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-preview/WELCOME?language=en",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "template_id" in data
        print(f"✅ PASS: GET /api/admin/email-preview/WELCOME still works")


class TestAuthenticationRequired:
    """Test endpoints require authentication"""
    
    def test_profile_update_no_auth(self):
        """PUT /api/users/me without auth should return 401"""
        response = requests.put(
            f"{BASE_URL}/api/users/me",
            json={"name": "Unauthorized"}
        )
        assert response.status_code == 401
        print("✅ PASS: PUT /api/users/me without auth returns 401")
    
    def test_user_stats_no_auth(self):
        """GET /api/users/me/stats without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/users/me/stats")
        assert response.status_code == 401
        print("✅ PASS: GET /api/users/me/stats without auth returns 401")
    
    def test_tax_info_no_auth(self):
        """GET /api/users/me/tax-info without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/users/me/tax-info")
        assert response.status_code == 401
        print("✅ PASS: GET /api/users/me/tax-info without auth returns 401")
    
    def test_gdpr_status_no_auth(self):
        """GET /api/user/data-deletion-status without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/user/data-deletion-status")
        assert response.status_code == 401
        print("✅ PASS: GET /api/user/data-deletion-status without auth returns 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
