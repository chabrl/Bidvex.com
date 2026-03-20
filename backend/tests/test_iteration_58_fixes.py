"""
BidVex Iteration 58 Testing - Template ID Fix & Outlook Email Verification

Tests:
1. Backend health endpoint
2. Auth login, register, me, forgot-password
3. Admin verified-firm toggle (401 without auth, 404 for non-existent)
4. Email template config verification (no invalid IDs)
5. Email template Outlook compatibility (no linear-gradient, no <div>)
"""

import pytest
import requests
import os
import re

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://dashboard-localize.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestBackendHealth:
    """Test backend health and basic connectivity"""
    
    def test_health_endpoint(self):
        """GET /api/health should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected status: {data}"
        print("✓ Health endpoint working correctly")


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_login_success(self):
        """POST /api/auth/login with admin credentials should return access_token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("token_type") == "bearer", "Token type should be bearer"
        assert "user" in data, "No user data in response"
        print(f"✓ Admin login successful, got token: {data['access_token'][:20]}...")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login with wrong credentials should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid login correctly returns 401")
    
    def test_me_with_valid_token(self):
        """GET /api/auth/me with valid token should return user data"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        token = login_response.json()["access_token"]
        
        # Then get /me
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Failed to get /me: {response.status_code}"
        data = response.json()
        assert data.get("email") == ADMIN_EMAIL, f"Wrong email in response: {data.get('email')}"
        print(f"✓ /me endpoint returns correct user: {data.get('email')}")
    
    def test_me_without_token(self):
        """GET /api/auth/me without token should return 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /me without token correctly returns 401")
    
    def test_register_new_user(self):
        """POST /api/auth/register should accept new user registration"""
        import uuid
        unique_email = f"test_{uuid.uuid4().hex[:8]}@bidvex-test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "name": "Test User",
                "account_type": "personal",
                "terms_agreed": True
            }
        )
        assert response.status_code == 200, f"Registration failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in registration response"
        assert data.get("user", {}).get("email") == unique_email, "Email mismatch"
        print(f"✓ Registration successful for {unique_email}")
    
    def test_forgot_password(self):
        """POST /api/auth/forgot-password should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": ADMIN_EMAIL}
        )
        assert response.status_code == 200, f"Forgot password failed: {response.status_code}"
        data = response.json()
        assert data.get("success") == True, "forgot-password should return success"
        print("✓ Forgot password endpoint working correctly")


class TestAdminVerifiedFirm:
    """Test admin verified-firm toggle endpoint"""
    
    def test_verified_firm_without_auth(self):
        """POST /api/admin/partners/{id}/verified-firm should return 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/nonexistent-id/verified-firm",
            json={"is_verified_firm": True}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Verified-firm toggle returns 401 without auth")
    
    def test_verified_firm_nonexistent_partner(self):
        """POST /api/admin/partners/{id}/verified-firm with non-existent partner should return 404"""
        # Login first
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        token = login_response.json()["access_token"]
        
        # Try to toggle non-existent partner
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/nonexistent-partner-id-12345/verified-firm",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_verified_firm": True}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Verified-firm toggle returns 404 for non-existent partner")


class TestEmailTemplateConfig:
    """Test email template configuration"""
    
    def test_no_invalid_template_id_in_config(self):
        """Verify config/email_templates.py has NO references to d-e0ee403fbd8646db8011339cf2eeac30"""
        config_path = "/app/backend/config/email_templates.py"
        invalid_id = "d-e0ee403fbd8646db8011339cf2eeac30"
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        assert invalid_id not in content, f"Invalid template ID {invalid_id} found in email_templates.py!"
        print("✓ No invalid template ID in config/email_templates.py")
    
    def test_password_reset_template_ids(self):
        """Verify EmailTemplates.get_id() returns correct EN and FR IDs for PASSWORD_RESET"""
        import sys
        sys.path.insert(0, '/app/backend')
        from config.email_templates import EmailTemplates
        
        en_id = EmailTemplates.get_id(EmailTemplates.PASSWORD_RESET, 'en')
        fr_id = EmailTemplates.get_id(EmailTemplates.PASSWORD_RESET, 'fr')
        
        expected_en = "d-dbfba723dd5e4895a579b462b19c56fb"
        expected_fr = "d-9084b4478e024056a9fa5207fdfc91e6"
        
        assert en_id == expected_en, f"Wrong EN template ID: {en_id} (expected {expected_en})"
        assert fr_id == expected_fr, f"Wrong FR template ID: {fr_id} (expected {expected_fr})"
        print(f"✓ PASSWORD_RESET EN: {en_id}")
        print(f"✓ PASSWORD_RESET FR: {fr_id}")
    
    def test_all_templates_have_valid_format(self):
        """Verify all template IDs have the correct d-* format"""
        import sys
        sys.path.insert(0, '/app/backend')
        from config.email_templates import EmailTemplates
        
        template_pattern = re.compile(r'^d-[a-f0-9]{32}$')
        
        templates = [
            EmailTemplates.WELCOME, EmailTemplates.EMAIL_VERIFICATION,
            EmailTemplates.PASSWORD_RESET, EmailTemplates.PASSWORD_CHANGED,
            EmailTemplates.TWO_FACTOR, EmailTemplates.LOGIN_ALERT,
            EmailTemplates.BID_PLACED, EmailTemplates.BID_OUTBID, EmailTemplates.BID_WON,
            EmailTemplates.AUCTION_STARTED, EmailTemplates.AUCTION_ENDING_SOON, EmailTemplates.AUCTION_RESULTS,
            EmailTemplates.NEW_BID_RECEIVED, EmailTemplates.LISTING_APPROVED, EmailTemplates.LISTING_REJECTED,
            EmailTemplates.INVOICE, EmailTemplates.PAYMENT_RECEIVED, EmailTemplates.PAYOUT_SENT,
            EmailTemplates.ANNOUNCEMENT, EmailTemplates.SUPPORT_ACK, EmailTemplates.PLATFORM_UPDATES,
            EmailTemplates.REPORT_RECEIVED, EmailTemplates.ACCOUNT_SUSPENDED,
            EmailTemplates.AFFILIATE_COMMISSION, EmailTemplates.AFFILIATE_REFERRAL,
            EmailTemplates.AFFILIATE_EARNINGS, EmailTemplates.AFFILIATE_SUMMARY
        ]
        
        for template in templates:
            assert "en" in template, f"Template missing 'en' key: {template}"
            assert "fr" in template, f"Template missing 'fr' key: {template}"
            assert template_pattern.match(template["en"]), f"Invalid EN template format: {template['en']}"
            assert template_pattern.match(template["fr"]), f"Invalid FR template format: {template['fr']}"
        
        print(f"✓ All {len(templates)} template pairs have valid d-* format")


class TestEmailNotificationsOutlook:
    """Test email_notifications.py for Outlook compatibility"""
    
    def test_no_linear_gradient(self):
        """Verify email_notifications.py has zero linear-gradient occurrences"""
        filepath = "/app/backend/services/email_notifications.py"
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        count = content.lower().count('linear-gradient')
        assert count == 0, f"Found {count} linear-gradient occurrences in email_notifications.py"
        print("✓ No linear-gradient in email_notifications.py (Outlook-safe)")
    
    def test_no_div_elements(self):
        """Verify email_notifications.py has zero <div> elements"""
        filepath = "/app/backend/services/email_notifications.py"
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Count <div occurrences (case-insensitive)
        count = len(re.findall(r'<div', content, re.IGNORECASE))
        assert count == 0, f"Found {count} <div> elements in email_notifications.py"
        print("✓ No <div> elements in email_notifications.py (Outlook-safe, uses tables)")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
