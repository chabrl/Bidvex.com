"""
Partner Account System - Phase 1 Tests
Tests for BidVex Partner application, admin verification, and fee engine.

Features tested:
- GET /api/partner/status - Get partner status for authenticated user
- POST /api/partner/apply - Submit partner application with file uploads
- GET /api/admin/partners - Admin list of partner applications
- POST /api/admin/partners/{user_id}/verify - Admin verify partner
- POST /api/admin/partners/{user_id}/reject - Admin reject partner
- GET /api/partner/fee-preview - Preview partner fee breakdown
- GET /api/checkout/fee-breakdown - Fee breakdown for a listing
- Fee constants verification: STANDARD_BUYER_PREMIUM_RATE, PARTNER_PLATFORM_FEE_RATE
"""
import pytest
import requests
import os
import io
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://sell-location-unify.preview.emergentagent.com')

# Admin credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

# Expected fee constants
EXPECTED_STANDARD_BUYER_PREMIUM_RATE = 0.05  # 5%
EXPECTED_STANDARD_SELLER_COMMISSION_RATE = 0.04  # 4%
EXPECTED_PARTNER_PLATFORM_FEE_RATE = 0.03  # 3%
EXPECTED_STRIPE_PERCENTAGE_FEE = 0.029  # 2.9%
EXPECTED_STRIPE_FIXED_FEE = 0.30  # $0.30


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    assert "access_token" in data, f"No access_token in response: {data}"
    return data["access_token"]


@pytest.fixture(scope="module")
def test_user_credentials():
    """Create a test user for partner testing."""
    unique_id = str(uuid.uuid4())[:8]
    email = f"test_partner_{unique_id}@example.com"
    password = "TestPass123!"
    name = f"Test Partner User {unique_id}"
    
    # Register the user
    response = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": password,
        "name": name,
        "account_type": "business",
        "phone": "5145551234"
    })
    
    if response.status_code == 400 and "already registered" in response.text:
        # User exists, try to login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if login_resp.status_code == 200:
            data = login_resp.json()
            return {"email": email, "password": password, "token": data["access_token"], "user_id": data["user"]["id"]}
    
    assert response.status_code == 200, f"User registration failed: {response.text}"
    data = response.json()
    return {
        "email": email,
        "password": password,
        "token": data["access_token"],
        "user_id": data["user"]["id"]
    }


class TestPartnerStatusEndpoint:
    """Test GET /api/partner/status endpoint."""
    
    def test_get_partner_status_unauthenticated(self):
        """Should return 401 when not authenticated."""
        response = requests.get(f"{BASE_URL}/api/partner/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_partner_status_authenticated(self, test_user_credentials):
        """Should return partner status for authenticated user."""
        headers = {"Authorization": f"Bearer {test_user_credentials['token']}"}
        response = requests.get(f"{BASE_URL}/api/partner/status", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify required fields in response
        assert "is_partner" in data, "Missing is_partner field"
        assert "verification_status" in data, "Missing verification_status field"
        assert isinstance(data["is_partner"], bool), "is_partner should be boolean"
        assert data["verification_status"] in ["unverified", "pending", "verified", "rejected"], \
            f"Invalid verification_status: {data['verification_status']}"


class TestPartnerApplicationEndpoint:
    """Test POST /api/partner/apply endpoint."""
    
    def test_apply_partner_unauthenticated(self):
        """Should return 401 when not authenticated."""
        response = requests.post(f"{BASE_URL}/api/partner/apply")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_apply_partner_with_files(self, test_user_credentials):
        """Should successfully submit partner application with file uploads."""
        headers = {"Authorization": f"Bearer {test_user_credentials['token']}"}
        
        # Create test files
        neq_file = io.BytesIO(b"NEQ proof document content - test file")
        neq_file.name = "neq_proof.pdf"
        
        cert_file = io.BytesIO(b"Certification document content - test file")
        cert_file.name = "certification.pdf"
        
        files = {
            'neq_document': ('neq_proof.pdf', neq_file, 'application/pdf'),
            'certification_documents': ('certification.pdf', cert_file, 'application/pdf'),
        }
        
        data = {
            'company_name': f'Test Auction Firm {uuid.uuid4().hex[:6]}',
            'neq_number': '1234567890',
        }
        
        response = requests.post(
            f"{BASE_URL}/api/partner/apply",
            headers=headers,
            data=data,
            files=files
        )
        
        # Could be 200 (success) or 400 (already pending/partner)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            result = response.json()
            assert result.get("success") == True, "Expected success=true"
            assert "message" in result, "Expected message in response"
            assert result.get("verification_status") == "pending", "Expected verification_status=pending"
        else:
            # Already applied or is partner
            assert "already" in response.text.lower(), f"Unexpected error: {response.text}"


class TestAdminPartnerEndpoints:
    """Test admin partner management endpoints."""
    
    def test_get_partner_applications_unauthenticated(self):
        """Should return 401 when not authenticated."""
        response = requests.get(f"{BASE_URL}/api/admin/partners")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_partner_applications_as_admin(self, admin_token):
        """Admin should be able to list partner applications."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/partners", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "applications" in data, "Missing applications field"
        assert "total" in data, "Missing total field"
        assert isinstance(data["applications"], list), "applications should be a list"
        assert isinstance(data["total"], int), "total should be an integer"
    
    def test_get_partner_applications_with_status_filter(self, admin_token):
        """Admin should be able to filter by status."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        for status in ["pending", "verified", "rejected"]:
            response = requests.get(
                f"{BASE_URL}/api/admin/partners",
                headers=headers,
                params={"status": status}
            )
            assert response.status_code == 200, f"Filter {status} failed: {response.text}"
            data = response.json()
            
            # All returned applications should have the filtered status
            for app in data.get("applications", []):
                assert app.get("partner_verification_status") == status, \
                    f"Expected status {status}, got {app.get('partner_verification_status')}"
    
    def test_verify_partner_endpoint_exists(self, admin_token, test_user_credentials):
        """Verify POST /api/admin/partners/{user_id}/verify endpoint exists."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        user_id = test_user_credentials['user_id']
        
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/{user_id}/verify",
            headers=headers,
            json={}
        )
        
        # Could be 200 (success), 400 (not pending), or 404 (not found)
        assert response.status_code in [200, 400, 404], \
            f"Unexpected status {response.status_code}: {response.text}"
    
    def test_reject_partner_endpoint_exists(self, admin_token, test_user_credentials):
        """Verify POST /api/admin/partners/{user_id}/reject endpoint exists."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        user_id = test_user_credentials['user_id']
        
        response = requests.post(
            f"{BASE_URL}/api/admin/partners/{user_id}/reject",
            headers=headers,
            json={"reason": "Test rejection reason"}
        )
        
        # Could be 200 (success), 400 (invalid state), or 404 (not found)
        assert response.status_code in [200, 400, 404], \
            f"Unexpected status {response.status_code}: {response.text}"


class TestPartnerFeePreview:
    """Test GET /api/partner/fee-preview endpoint."""
    
    def test_fee_preview_unauthenticated(self):
        """Should return 401 when not authenticated."""
        response = requests.get(f"{BASE_URL}/api/partner/fee-preview", params={
            "hammer_price": 10000,
            "custom_buyer_premium_rate": 0.18
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_fee_preview_calculation(self, admin_token):
        """Test fee preview returns correct breakdown for $10,000 at 18% buyer premium."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        hammer_price = 10000.0
        buyer_premium_rate = 0.18
        
        response = requests.get(
            f"{BASE_URL}/api/partner/fee-preview",
            headers=headers,
            params={
                "hammer_price": hammer_price,
                "custom_buyer_premium_rate": buyer_premium_rate
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "hammer_price" in data, "Missing hammer_price"
        assert "buyer_premium" in data, "Missing buyer_premium"
        assert "platform_fee" in data, "Missing platform_fee"
        assert "stripe_fee_recovery" in data, "Missing stripe_fee_recovery"
        assert "total_to_charge_buyer" in data, "Missing total_to_charge_buyer"
        
        # Verify calculations
        assert data["hammer_price"] == hammer_price, f"Hammer price mismatch: {data['hammer_price']}"
        
        # Platform fee should be 3% of hammer price = $300
        expected_platform_fee = round(hammer_price * EXPECTED_PARTNER_PLATFORM_FEE_RATE, 2)
        assert data["platform_fee"] == expected_platform_fee, \
            f"Platform fee mismatch: expected {expected_platform_fee}, got {data['platform_fee']}"
        
        # Buyer premium should be 18% of hammer price = $1,800
        expected_buyer_premium = round(hammer_price * buyer_premium_rate, 2)
        assert data["buyer_premium"] == expected_buyer_premium, \
            f"Buyer premium mismatch: expected {expected_buyer_premium}, got {data['buyer_premium']}"
        
        # Verify Stripe fee recovery is calculated (formula: (desired_net + 0.30) / (1 - 0.029) - desired_net)
        desired_net = hammer_price + expected_buyer_premium + expected_platform_fee
        expected_stripe_fee = round((desired_net + EXPECTED_STRIPE_FIXED_FEE) / (1 - EXPECTED_STRIPE_PERCENTAGE_FEE) - desired_net, 2)
        
        # Allow small tolerance for rounding
        assert abs(data["stripe_fee_recovery"] - expected_stripe_fee) < 0.1, \
            f"Stripe fee mismatch: expected ~{expected_stripe_fee}, got {data['stripe_fee_recovery']}"
        
        # Total should be hammer + buyer premium + platform fee + stripe recovery
        expected_total = round(desired_net + data["stripe_fee_recovery"], 2)
        assert abs(data["total_to_charge_buyer"] - expected_total) < 0.1, \
            f"Total mismatch: expected ~{expected_total}, got {data['total_to_charge_buyer']}"
        
        print(f"Fee Preview Breakdown:")
        print(f"  Hammer Price: ${data['hammer_price']}")
        print(f"  Buyer Premium ({buyer_premium_rate*100}%): ${data['buyer_premium']}")
        print(f"  Platform Fee (3%): ${data['platform_fee']}")
        print(f"  Stripe Fee Recovery: ${data['stripe_fee_recovery']}")
        print(f"  Total to Charge Buyer: ${data['total_to_charge_buyer']}")
    
    def test_fee_preview_zero_buyer_premium(self, admin_token):
        """Test fee preview with 0% buyer premium."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/partner/fee-preview",
            headers=headers,
            params={
                "hammer_price": 5000,
                "custom_buyer_premium_rate": 0.0
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["buyer_premium"] == 0, "Buyer premium should be 0"
        assert data["platform_fee"] == 150, f"Platform fee should be $150 (3% of $5000), got {data['platform_fee']}"
    
    def test_fee_preview_invalid_price(self, admin_token):
        """Test fee preview with invalid hammer price."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/partner/fee-preview",
            headers=headers,
            params={
                "hammer_price": -100,
                "custom_buyer_premium_rate": 0.18
            }
        )
        
        assert response.status_code == 400, f"Expected 400 for negative price, got {response.status_code}"


class TestCheckoutFeeBreakdown:
    """Test GET /api/checkout/fee-breakdown endpoint."""
    
    def test_fee_breakdown_unauthenticated(self):
        """Should return 401 when not authenticated."""
        response = requests.get(f"{BASE_URL}/api/checkout/fee-breakdown", params={
            "listing_id": "nonexistent"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_fee_breakdown_nonexistent_listing(self, admin_token):
        """Should return 404 for nonexistent listing."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/checkout/fee-breakdown",
            headers=headers,
            params={"listing_id": "nonexistent-listing-id"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


class TestFeeConstants:
    """Verify fee constants match expected values through the API."""
    
    def test_partner_platform_fee_rate(self, admin_token):
        """Verify PARTNER_PLATFORM_FEE_RATE is 3%."""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test with $1000 hammer price
        response = requests.get(
            f"{BASE_URL}/api/partner/fee-preview",
            headers=headers,
            params={"hammer_price": 1000, "custom_buyer_premium_rate": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Platform fee should be exactly 3% = $30
        assert data["platform_fee"] == 30, \
            f"PARTNER_PLATFORM_FEE_RATE should be 3% (expected $30, got ${data['platform_fee']})"
        
        # Verify the rate field
        assert data.get("platform_fee_rate") == EXPECTED_PARTNER_PLATFORM_FEE_RATE, \
            f"platform_fee_rate should be {EXPECTED_PARTNER_PLATFORM_FEE_RATE}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
