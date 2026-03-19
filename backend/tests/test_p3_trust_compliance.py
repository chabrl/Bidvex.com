"""
P3 Trust & Compliance Phase Backend Tests
Tests for:
1. Auth refactor - /api/auth/* endpoints
2. Verified Firm Badge - Admin toggle for is_verified_firm
3. Email templates verification - No linear-gradient, table-based layout
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://cookie-consent-i18n.preview.emergentagent.com')

# Admin credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

class TestAuthEndpoints:
    """Test refactored auth endpoints at /api/auth/*"""
    
    def test_login_admin_success(self):
        """Test admin login returns access_token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✅ Admin login successful, got access_token")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Invalid credentials correctly rejected with 401")
    
    def test_register_new_user(self):
        """Test registration with new user"""
        import uuid
        unique_email = f"test_{uuid.uuid4().hex[:8]}@bidvex-test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPassword123!",
            "name": "Test User P3",
            "account_type": "personal",
            "phone": "+15145551234",
            "terms_agreed": True
        })
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token after registration"
        assert "user" in data, "No user in response"
        assert data["user"]["email"] == unique_email
        print(f"✅ New user registered: {unique_email}")
    
    def test_auth_me_with_valid_token(self):
        """Test GET /api/auth/me with valid token"""
        # First login to get token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Now test /me endpoint
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"GET /me failed: {response.text}"
        data = response.json()
        assert "email" in data
        assert data["email"] == ADMIN_EMAIL
        print("✅ GET /api/auth/me returned user data")
    
    def test_auth_me_without_token(self):
        """Test GET /api/auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ GET /api/auth/me without token correctly returns 401")
    
    def test_forgot_password_accepts_email(self):
        """Test POST /api/auth/forgot-password accepts email"""
        response = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": ADMIN_EMAIL
        })
        assert response.status_code == 200, f"Forgot password failed: {response.text}"
        data = response.json()
        assert "success" in data or "message" in data
        print("✅ Forgot password endpoint accepts email")


class TestVerifiedFirmBadge:
    """Test admin toggle for Verified Auction Firm badge"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_verified_firm_toggle_without_auth(self):
        """Test toggle endpoint returns 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/fake-id/verified-firm",
            json={"is_verified_firm": True}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Verified firm toggle correctly requires auth (401)")
    
    def test_verified_firm_toggle_nonexistent_partner(self, admin_token):
        """Test toggle endpoint returns 404 for non-existent partner"""
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/nonexistent-partner-id-12345/verified-firm",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_verified_firm": True}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✅ Verified firm toggle correctly returns 404 for non-existent partner")
    
    def test_get_partners_list(self, admin_token):
        """Test admin can list partner applications"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partners",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Get partners failed: {response.text}"
        data = response.json()
        assert "applications" in data or "partners" in data or isinstance(data, list)
        print("✅ Admin can list partners")


class TestEmailTemplates:
    """Verify email templates have correct Outlook-compatible formatting"""
    
    def test_no_linear_gradient_in_email_templates(self):
        """Verify no linear-gradient remains in email_notifications.py"""
        email_file = "/app/backend/services/email_notifications.py"
        
        with open(email_file, 'r') as f:
            content = f.read()
        
        assert "linear-gradient" not in content, "linear-gradient found in email templates!"
        print("✅ No linear-gradient found in email templates")
    
    def test_no_div_elements_in_email_templates(self):
        """Verify all content uses table-based layout (no div elements)"""
        email_file = "/app/backend/services/email_notifications.py"
        
        with open(email_file, 'r') as f:
            content = f.read()
        
        # Check for <div in HTML content (excluding any code comments)
        # We need to check if <div> appears in HTML strings
        assert "<div" not in content, "<div> elements found in email templates!"
        print("✅ No <div> elements found in email templates (table-based layout)")
    
    def test_email_templates_use_tables(self):
        """Verify email templates use table elements"""
        email_file = "/app/backend/services/email_notifications.py"
        
        with open(email_file, 'r') as f:
            content = f.read()
        
        assert "<table" in content, "No <table> elements found in email templates!"
        assert "<tr>" in content, "No <tr> elements found in email templates!"
        assert "<td" in content, "No <td> elements found in email templates!"
        print("✅ Email templates use table-based layout")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
