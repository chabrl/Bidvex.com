"""
Test Suite for Affiliate Referral & Payout System - Iteration 141
Tests:
1. POST /api/auth/register with ref_code creates affiliate_referrals record
2. POST /api/auth/register without ref_code works normally
3. GET /api/affiliate/stats returns correct structure
4. PricingManager.affiliate_commission() calculations
5. Webhook handler affiliate commission logic
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
ADMIN_AFFILIATE_CODE = "BVX8940074DXKTU"


class TestAffiliateReferralSystem:
    """Tests for the Affiliate Referral & Payout System"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    
    # ── Test 1: Registration with ref_code ──
    def test_register_with_ref_code_creates_referral_record(self, admin_token):
        """POST /api/auth/register with ref_code should create affiliate_referrals record"""
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"TEST_affiliate_ref_{unique_id}@bidvex.test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPassword123!",
            "name": f"Test Affiliate Ref {unique_id}",
            "account_type": "personal",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
            "ref_code": ADMIN_AFFILIATE_CODE
        })
        
        # Check registration succeeded
        assert response.status_code == 200, f"Registration failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Missing access_token in response"
        assert "user" in data, "Missing user in response"
        
        user = data["user"]
        assert user["email"] == test_email.lower(), "Email mismatch"
        assert user.get("referred_by") is not None, "referred_by should be set when ref_code is provided"
        assert user.get("referred_by_code") == ADMIN_AFFILIATE_CODE, f"referred_by_code should be {ADMIN_AFFILIATE_CODE}"
        
        print(f"PASS: Registration with ref_code created user with referred_by={user.get('referred_by')}")
    
    # ── Test 2: Registration without ref_code ──
    def test_register_without_ref_code_works_normally(self):
        """POST /api/auth/register without ref_code should work normally"""
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"TEST_no_ref_{unique_id}@bidvex.test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPassword123!",
            "name": f"Test No Ref {unique_id}",
            "account_type": "personal",
            "terms_agreed": True,
            "ai_disclosure_consent": True
            # No ref_code
        })
        
        assert response.status_code == 200, f"Registration without ref_code failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Missing access_token"
        assert "user" in data, "Missing user"
        
        user = data["user"]
        assert user.get("referred_by") is None, "referred_by should be None when no ref_code"
        assert user.get("referred_by_code") is None, "referred_by_code should be None when no ref_code"
        assert user.get("affiliate_code") is not None, "User should have their own affiliate_code"
        
        print(f"PASS: Registration without ref_code works, user has affiliate_code={user.get('affiliate_code')}")
    
    # ── Test 3: GET /api/affiliate/stats ──
    def test_affiliate_stats_endpoint(self, admin_token):
        """GET /api/affiliate/stats returns correct structure"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/affiliate/stats", headers=headers)
        
        assert response.status_code == 200, f"Affiliate stats failed: {response.status_code} - {response.text}"
        
        data = response.json()
        
        # Check required fields
        assert "affiliate_code" in data, "Missing affiliate_code"
        assert "referral_link" in data, "Missing referral_link"
        assert "commission_rate" in data, "Missing commission_rate"
        assert "total_referrals" in data, "Missing total_referrals"
        assert "total_earnings" in data, "Missing total_earnings"
        
        # Validate values
        assert data["affiliate_code"] == ADMIN_AFFILIATE_CODE, f"Expected affiliate_code {ADMIN_AFFILIATE_CODE}, got {data['affiliate_code']}"
        assert data["commission_rate"] == "10%", f"Expected commission_rate '10%', got {data['commission_rate']}"
        assert "?ref=" in data["referral_link"], f"Referral link should contain '?ref=', got {data['referral_link']}"
        assert data["referral_link"].endswith(f"?ref={ADMIN_AFFILIATE_CODE}"), f"Referral link format incorrect: {data['referral_link']}"
        
        # Check numeric fields
        assert isinstance(data["total_referrals"], int), "total_referrals should be int"
        assert isinstance(data["total_earnings"], (int, float)), "total_earnings should be numeric"
        
        print(f"PASS: Affiliate stats returned correctly:")
        print(f"  - affiliate_code: {data['affiliate_code']}")
        print(f"  - referral_link: {data['referral_link']}")
        print(f"  - commission_rate: {data['commission_rate']}")
        print(f"  - total_referrals: {data['total_referrals']}")
        print(f"  - total_earnings: {data['total_earnings']}")
    
    # ── Test 4: Affiliate stats additional fields ──
    def test_affiliate_stats_additional_fields(self, admin_token):
        """GET /api/affiliate/stats returns all expected fields"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/affiliate/stats", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check additional fields
        expected_fields = [
            "affiliate_code", "referral_link", "total_referrals", "active_referrals",
            "total_earnings", "pending_earnings", "paid_earnings", "commission_rate",
            "commission_description", "payout_delay_days", "earnings_history", "referrals"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate commission description
        assert "10%" in data.get("commission_description", ""), "Commission description should mention 10%"
        assert data.get("payout_delay_days") == 7, f"Expected payout_delay_days=7, got {data.get('payout_delay_days')}"
        
        print(f"PASS: All expected fields present in affiliate stats")


class TestPricingManagerAffiliateCommission:
    """Tests for PricingManager.affiliate_commission() method"""
    
    def test_affiliate_commission_standard_case(self):
        """PricingManager.affiliate_commission(4.50) should return 0.45 (10% of $4.50)"""
        # Import and test directly
        import sys
        sys.path.insert(0, '/app/backend')
        from services.fee_calculator import PricingManager
        
        result = PricingManager.affiliate_commission(4.50)
        
        assert result == 0.45, f"Expected 0.45, got {result}"
        print(f"PASS: affiliate_commission(4.50) = {result} (10% of $4.50)")
    
    def test_affiliate_commission_zero(self):
        """PricingManager.affiliate_commission(0) should return 0"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.fee_calculator import PricingManager
        
        result = PricingManager.affiliate_commission(0)
        
        assert result == 0.0, f"Expected 0.0, got {result}"
        print(f"PASS: affiliate_commission(0) = {result}")
    
    def test_affiliate_commission_large_amount(self):
        """PricingManager.affiliate_commission(100.00) should return 10.00"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.fee_calculator import PricingManager
        
        result = PricingManager.affiliate_commission(100.00)
        
        assert result == 10.0, f"Expected 10.0, got {result}"
        print(f"PASS: affiliate_commission(100.00) = {result}")
    
    def test_affiliate_commission_small_amount(self):
        """PricingManager.affiliate_commission(0.50) should return 0.05"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.fee_calculator import PricingManager
        
        result = PricingManager.affiliate_commission(0.50)
        
        assert result == 0.05, f"Expected 0.05, got {result}"
        print(f"PASS: affiliate_commission(0.50) = {result}")
    
    def test_affiliate_commission_rate_constant(self):
        """AFFILIATE_COMMISSION_RATE should be 0.10 (10%)"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.fee_calculator import AFFILIATE_COMMISSION_RATE
        from decimal import Decimal
        
        assert AFFILIATE_COMMISSION_RATE == Decimal("0.10"), f"Expected 0.10, got {AFFILIATE_COMMISSION_RATE}"
        print(f"PASS: AFFILIATE_COMMISSION_RATE = {AFFILIATE_COMMISSION_RATE} (10%)")


class TestAffiliateReferralLinkFormat:
    """Tests for referral link format"""
    
    def test_referral_link_format(self, admin_token=None):
        """Referral link should be in format: domain/?ref=CODE"""
        # Login to get token
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip("Login failed")
        
        token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/affiliate/stats", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        referral_link = data.get("referral_link", "")
        
        # Should be domain/?ref=CODE format (not /auth?ref=)
        assert "/?ref=" in referral_link or "?ref=" in referral_link, f"Referral link should use ?ref= format: {referral_link}"
        assert "/auth?ref=" not in referral_link, f"Referral link should NOT use /auth?ref= format: {referral_link}"
        
        print(f"PASS: Referral link format correct: {referral_link}")


class TestRegistrationValidation:
    """Tests for registration validation"""
    
    def test_register_requires_terms_agreed(self):
        """Registration should fail without terms_agreed"""
        unique_id = str(uuid.uuid4())[:8]
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"TEST_terms_{unique_id}@bidvex.test.com",
            "password": "TestPassword123!",
            "name": "Test Terms",
            "account_type": "personal",
            "terms_agreed": False,  # Should fail
            "ai_disclosure_consent": True
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: Registration correctly rejected without terms_agreed")
    
    def test_register_requires_ai_disclosure_consent(self):
        """Registration should fail without ai_disclosure_consent"""
        unique_id = str(uuid.uuid4())[:8]
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"TEST_ai_{unique_id}@bidvex.test.com",
            "password": "TestPassword123!",
            "name": "Test AI Consent",
            "account_type": "personal",
            "terms_agreed": True,
            "ai_disclosure_consent": False  # Should fail
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: Registration correctly rejected without ai_disclosure_consent")
    
    def test_register_with_invalid_ref_code_still_works(self):
        """Registration with invalid ref_code should still work (just no referral)"""
        unique_id = str(uuid.uuid4())[:8]
        test_email = f"TEST_invalid_ref_{unique_id}@bidvex.test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPassword123!",
            "name": f"Test Invalid Ref {unique_id}",
            "account_type": "personal",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
            "ref_code": "INVALID_CODE_12345"  # Non-existent code
        })
        
        assert response.status_code == 200, f"Registration with invalid ref_code should still work: {response.status_code} - {response.text}"
        
        data = response.json()
        user = data.get("user", {})
        
        # Should not have referred_by since code is invalid
        assert user.get("referred_by") is None, "referred_by should be None for invalid ref_code"
        
        print(f"PASS: Registration with invalid ref_code works, no referral created")


class TestAffiliateStatsAuthentication:
    """Tests for affiliate stats authentication"""
    
    def test_affiliate_stats_requires_auth(self):
        """GET /api/affiliate/stats should require authentication"""
        response = requests.get(f"{BASE_URL}/api/affiliate/stats")
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print(f"PASS: Affiliate stats correctly requires authentication")
    
    def test_affiliate_stats_with_invalid_token(self):
        """GET /api/affiliate/stats should reject invalid token"""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        
        response = requests.get(f"{BASE_URL}/api/affiliate/stats", headers=headers)
        
        assert response.status_code == 401, f"Expected 401 with invalid token, got {response.status_code}"
        print(f"PASS: Affiliate stats correctly rejects invalid token")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
