"""
Password Management API Tests
Tests for change-password, forgot-password, and reset-password endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Admin123!"
TEST_USER_EMAIL = "starter@test.com"
TEST_USER_PASSWORD = "TestUser2026!"


class TestAuthEndpoints:
    """Test authentication and password management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_auth_token(self, email, password):
        """Helper to get auth token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    # ============= LOGIN TESTS =============
    
    def test_login_admin_success(self):
        """Test admin login returns JWT token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        print(f"Admin login response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Response should contain access_token"
        assert "user" in data, "Response should contain user object"
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"PASS: Admin login successful, token received")
    
    def test_login_invalid_credentials(self):
        """Test login with wrong password returns 401"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword123!"
        })
        print(f"Invalid login response: {response.status_code}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: Invalid credentials correctly rejected")
    
    # ============= CHANGE PASSWORD TESTS =============
    
    def test_change_password_no_auth(self):
        """Test change-password without auth returns 401"""
        response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": "test",
            "new_password": "NewPass123!"
        })
        print(f"Change password no auth response: {response.status_code}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"PASS: Unauthenticated request correctly rejected")
    
    def test_change_password_wrong_current(self):
        """Test change-password with wrong current password returns 400"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": "WrongCurrentPassword!",
            "new_password": "NewPass123!"
        })
        print(f"Wrong current password response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "incorrect" in data.get("detail", "").lower(), f"Expected 'incorrect' in error message, got: {data}"
        print(f"PASS: Wrong current password correctly rejected with message: {data.get('detail')}")
    
    def test_change_password_weak_new_password(self):
        """Test change-password with weak new password returns 400"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Test too short password
        response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "short"
        })
        print(f"Weak password (too short) response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: Short password rejected: {response.json().get('detail')}")
        
        # Test no uppercase
        response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "nouppercase123"
        })
        print(f"Weak password (no uppercase) response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: No uppercase password rejected: {response.json().get('detail')}")
        
        # Test no number
        response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "NoNumberHere"
        })
        print(f"Weak password (no number) response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: No number password rejected: {response.json().get('detail')}")
    
    def test_change_password_same_as_current(self):
        """Test change-password with same password returns 400"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": ADMIN_PASSWORD,
            "new_password": ADMIN_PASSWORD
        })
        print(f"Same password response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "different" in data.get("detail", "").lower(), f"Expected 'different' in error message, got: {data}"
        print(f"PASS: Same password correctly rejected: {data.get('detail')}")
    
    def test_change_password_success_and_revert(self):
        """Test change-password with valid data succeeds, then revert"""
        token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert token, "Failed to get auth token"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Change to new password
        new_password = "NewAdmin456!"
        response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": ADMIN_PASSWORD,
            "new_password": new_password
        })
        print(f"Change password success response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        print(f"PASS: Password changed successfully: {data.get('message')}")
        
        # Verify can login with new password
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": new_password
        })
        print(f"Login with new password response: {login_response.status_code}")
        assert login_response.status_code == 200, f"Expected 200, got {login_response.status_code}"
        print(f"PASS: Login with new password successful")
        
        # REVERT: Change back to original password
        new_token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {new_token}"})
        
        revert_response = self.session.post(f"{BASE_URL}/api/auth/change-password", json={
            "current_password": new_password,
            "new_password": ADMIN_PASSWORD
        })
        print(f"Revert password response: {revert_response.status_code}")
        assert revert_response.status_code == 200, f"Expected 200, got {revert_response.status_code}: {revert_response.text}"
        print(f"PASS: Password reverted to original")
        
        # Verify original password works
        final_login = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert final_login.status_code == 200, f"Failed to login with original password after revert"
        print(f"PASS: Original password verified working")
    
    # ============= FORGOT PASSWORD TESTS =============
    
    def test_forgot_password_success(self):
        """Test forgot-password returns success (prevents email enumeration)"""
        response = self.session.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": ADMIN_EMAIL
        })
        print(f"Forgot password response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got: {data}"
        assert "message" in data, "Response should contain message"
        print(f"PASS: Forgot password request successful: {data.get('message')}")
    
    def test_forgot_password_nonexistent_email(self):
        """Test forgot-password with non-existent email still returns success (security)"""
        response = self.session.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": "nonexistent@example.com"
        })
        print(f"Forgot password nonexistent email response: {response.status_code}")
        # Should still return 200 to prevent email enumeration
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True for security, got: {data}"
        print(f"PASS: Non-existent email correctly returns success (prevents enumeration)")
    
    # ============= VERIFY RESET TOKEN TESTS =============
    
    def test_verify_reset_token_invalid(self):
        """Test verify-reset-token with invalid token"""
        response = self.session.get(f"{BASE_URL}/api/auth/verify-reset-token/invalid-token-12345")
        print(f"Verify invalid token response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("valid") == False, f"Expected valid=False, got: {data}"
        print(f"PASS: Invalid token correctly identified: {data.get('message')}")
    
    # ============= RESET PASSWORD TESTS =============
    
    def test_reset_password_invalid_token(self):
        """Test reset-password with invalid token returns 400"""
        response = self.session.post(f"{BASE_URL}/api/auth/reset-password", json={
            "token": "invalid-token-12345",
            "new_password": "NewPass123!"
        })
        print(f"Reset password invalid token response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: Invalid reset token correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
