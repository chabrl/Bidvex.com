"""
BidVex Partner System Phase 2 Tests
Tests for:
- Partner fee preview endpoint with custom buyer premium
- Stripe Connect destination charges service (calculate_partner_listing_checkout)
- Tax registration numbers in tax_engine.py
- PARTNER_PLATFORM_FEE_RATE constant (3%)
- Checkout fee breakdown endpoint
- Admin partner endpoints
- Partner apply endpoint with file uploads
"""

import pytest
import requests
import os
from decimal import Decimal

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestPartnerFeePreview:
    """Test GET /api/partner/fee-preview endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin to get token for authenticated endpoints"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip(f"Could not login: {response.status_code}")
    
    def test_fee_preview_10000_hammer_18_percent_premium(self):
        """
        Test fee preview with hammer_price=10000 and 18% custom buyer premium.
        Expected:
        - platform_fee = 300 (3% of 10000)
        - buyer_premium = 1800 (18% of 10000)
        - stripe_fee ~361.69 (recovered via Net-Zero formula)
        - total ~12461.69
        """
        response = requests.get(
            f"{BASE_URL}/api/partner/fee-preview",
            params={"hammer_price": 10000, "custom_buyer_premium_rate": 0.18},
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify platform fee (3%)
        assert data.get("platform_fee") == 300, f"Expected platform_fee=300, got {data.get('platform_fee')}"
        assert data.get("platform_fee_rate") == 0.03, f"Expected platform_fee_rate=0.03, got {data.get('platform_fee_rate')}"
        
        # Verify buyer premium (18%)
        assert data.get("buyer_premium") == 1800, f"Expected buyer_premium=1800, got {data.get('buyer_premium')}"
        assert data.get("buyer_premium_rate") == 0.18, f"Expected buyer_premium_rate=0.18, got {data.get('buyer_premium_rate')}"
        
        # Verify hammer price
        assert data.get("hammer_price") == 10000, f"Expected hammer_price=10000, got {data.get('hammer_price')}"
        
        # Verify stripe fee recovery (should be around 361.69)
        stripe_fee = data.get("stripe_fee_recovery")
        assert stripe_fee is not None, "stripe_fee_recovery should be present"
        assert 360 < stripe_fee < 365, f"Expected stripe_fee ~361.69, got {stripe_fee}"
        
        # Verify total to charge buyer (~12461.69)
        total = data.get("total_to_charge_buyer")
        assert total is not None, "total_to_charge_buyer should be present"
        assert 12460 < total < 12465, f"Expected total ~12461.69, got {total}"
        
        # Verify transfer to partner (hammer + buyer premium = 11800)
        transfer = data.get("transfer_to_partner")
        assert transfer == 11800, f"Expected transfer_to_partner=11800, got {transfer}"
        
        # Verify application fee (platform_fee + stripe_recovery)
        app_fee = data.get("application_fee")
        assert 660 < app_fee < 665, f"Expected application_fee ~661.69, got {app_fee}"
        
        print(f"✅ Fee preview test passed: platform_fee={data['platform_fee']}, buyer_premium={data['buyer_premium']}, "
              f"stripe_fee={stripe_fee:.2f}, total={total:.2f}")
    
    def test_fee_preview_5000_hammer_5_percent_premium(self):
        """
        Test fee preview with hammer_price=5000 and 5% custom buyer premium.
        Expected:
        - platform_fee = 150 (3% of 5000)
        - buyer_premium = 250 (5% of 5000)
        """
        response = requests.get(
            f"{BASE_URL}/api/partner/fee-preview",
            params={"hammer_price": 5000, "custom_buyer_premium_rate": 0.05},
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify platform fee (3%)
        assert data.get("platform_fee") == 150, f"Expected platform_fee=150, got {data.get('platform_fee')}"
        
        # Verify buyer premium (5%)
        assert data.get("buyer_premium") == 250, f"Expected buyer_premium=250, got {data.get('buyer_premium')}"
        
        print(f"✅ Fee preview 5000/5% test passed: platform_fee={data['platform_fee']}, buyer_premium={data['buyer_premium']}")
    
    def test_fee_preview_zero_premium(self):
        """Test fee preview with 0% buyer premium (partner collects no premium)"""
        response = requests.get(
            f"{BASE_URL}/api/partner/fee-preview",
            params={"hammer_price": 10000, "custom_buyer_premium_rate": 0},
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("platform_fee") == 300, f"Expected platform_fee=300"
        assert data.get("buyer_premium") == 0, f"Expected buyer_premium=0, got {data.get('buyer_premium')}"
        
        print("✅ Zero premium test passed")


class TestCheckoutFeeBreakdown:
    """Test GET /api/checkout/fee-breakdown endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip(f"Could not login: {response.status_code}")
    
    def test_fee_breakdown_nonexistent_listing(self):
        """Test fee breakdown returns 404 for nonexistent listing"""
        response = requests.get(
            f"{BASE_URL}/api/checkout/fee-breakdown",
            params={"listing_id": "NONEXISTENT_LISTING_ID_12345"},
            headers=self.headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Checkout fee breakdown 404 test passed")


class TestPartnerStatus:
    """Test GET /api/partner/status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip(f"Could not login: {response.status_code}")
    
    def test_partner_status_returns_200(self):
        """Test partner status endpoint returns user's partner status"""
        response = requests.get(f"{BASE_URL}/api/partner/status", headers=self.headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should return partner-related fields
        assert "is_partner" in data or "verification_status" in data, \
            f"Expected partner status fields, got: {data.keys()}"
        
        print(f"✅ Partner status test passed: {data}")


class TestAdminPartners:
    """Test GET /api/admin/partners endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip(f"Could not login: {response.status_code}")
    
    def test_admin_partners_list(self):
        """Test admin partners list returns applications"""
        response = requests.get(f"{BASE_URL}/api/admin/partners", headers=self.headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should return a list or dict with applications
        assert "applications" in data or isinstance(data, list), \
            f"Expected applications list, got: {type(data)}"
        
        print(f"✅ Admin partners list test passed")


class TestTaxEngineConstants:
    """Test tax_engine.py has correct constants"""
    
    def test_partner_platform_fee_rate_constant(self):
        """Test PARTNER_PLATFORM_FEE_RATE = 0.03 (3%)"""
        from services.tax_engine import PARTNER_PLATFORM_FEE_RATE
        
        assert PARTNER_PLATFORM_FEE_RATE == Decimal("0.03"), \
            f"Expected PARTNER_PLATFORM_FEE_RATE=0.03, got {PARTNER_PLATFORM_FEE_RATE}"
        
        print("✅ PARTNER_PLATFORM_FEE_RATE constant test passed")
    
    def test_gst_number_correct(self):
        """Test GST registration number is correct: 706766367RT0001"""
        from services.tax_engine import BIDVEX_GST_NUMBER
        
        assert BIDVEX_GST_NUMBER == "706766367RT0001", \
            f"Expected GST=706766367RT0001, got {BIDVEX_GST_NUMBER}"
        
        print("✅ GST number test passed")
    
    def test_qst_number_correct(self):
        """Test QST registration number is correct: 1233530880TQ0001"""
        from services.tax_engine import BIDVEX_QST_NUMBER
        
        assert BIDVEX_QST_NUMBER == "1233530880TQ0001", \
            f"Expected QST=1233530880TQ0001, got {BIDVEX_QST_NUMBER}"
        
        print("✅ QST number test passed")


class TestStripeConnectService:
    """Test calculate_partner_listing_checkout function in stripe_connect_service.py"""
    
    def test_calculate_partner_listing_checkout_fund_split(self):
        """
        Test calculate_partner_listing_checkout correctly splits funds:
        - transfer_to_partner = hammer + buyer_premium
        - application_fee = platform_fee (3%) + stripe_fee_recovery
        """
        from services.stripe_connect_service import calculate_partner_listing_checkout
        
        breakdown = calculate_partner_listing_checkout(
            hammer_price=10000.0,
            custom_buyer_premium_rate=0.18,
            partner_is_tax_registered=False,
            include_processing_fee=True
        )
        
        # Verify hammer price
        assert float(breakdown.hammer_price) == 10000.0
        
        # Verify platform fee (3%)
        assert float(breakdown.platform_fee) == 300.0, \
            f"Expected platform_fee=300, got {breakdown.platform_fee}"
        
        # Verify buyer premium (18%)
        assert float(breakdown.buyer_premium) == 1800.0, \
            f"Expected buyer_premium=1800, got {breakdown.buyer_premium}"
        
        # Verify transfer to partner = hammer + BP (no tax since not registered)
        # transfer_to_partner should be at least hammer + buyer_premium = 11800
        transfer = breakdown.stripe_transfer_amount_cents / 100  # Convert from cents
        assert transfer >= 11800, \
            f"Expected transfer >= 11800, got {transfer}"
        
        # Verify application fee includes platform fee
        app_fee = breakdown.stripe_application_fee_cents / 100  # Convert from cents
        assert app_fee >= 300, \
            f"Expected application_fee >= 300 (platform fee), got {app_fee}"
        
        # Verify processing fee is calculated
        assert breakdown.processing_fee > 0, "Processing fee should be positive"
        
        print(f"✅ calculate_partner_listing_checkout test passed")
        print(f"   hammer={breakdown.hammer_price}, platform_fee={breakdown.platform_fee}, "
              f"buyer_premium={breakdown.buyer_premium}")
        print(f"   transfer_cents={breakdown.stripe_transfer_amount_cents}, "
              f"app_fee_cents={breakdown.stripe_application_fee_cents}")
    
    def test_partner_listing_with_tax_registration(self):
        """Test partner listing with tax-registered partner"""
        from services.stripe_connect_service import calculate_partner_listing_checkout
        
        breakdown = calculate_partner_listing_checkout(
            hammer_price=10000.0,
            custom_buyer_premium_rate=0.18,
            partner_is_tax_registered=True,
            include_processing_fee=True
        )
        
        # With tax registration, there should be tax on hammer and BP
        assert float(breakdown.hammer_tax_total) > 0, "Expected tax on hammer for registered partner"
        
        print(f"✅ Tax-registered partner test passed: hammer_tax={breakdown.hammer_tax_total}")


class TestPartnerApply:
    """Test POST /api/partner/apply endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip(f"Could not login: {response.status_code}")
    
    def test_partner_apply_endpoint_exists(self):
        """Test partner apply endpoint exists and requires proper data"""
        # Create minimal test files
        neq_file = ("neq_test.pdf", b"Test NEQ document content", "application/pdf")
        cert_file = ("cert_test.pdf", b"Test certification content", "application/pdf")
        
        # Note: Don't include auth header in files dict, only in headers
        response = requests.post(
            f"{BASE_URL}/api/partner/apply",
            data={
                "company_name": "Test Auction Company",
                "neq_number": "1234567890"
            },
            files={
                "neq_document": neq_file,
                "certification_documents": cert_file
            },
            headers=self.headers
        )
        
        # Could be 200 (success), 400 (validation), or 422 (already applied)
        # Any of these indicates the endpoint exists and is working
        assert response.status_code in [200, 201, 400, 422], \
            f"Expected 200/201/400/422, got {response.status_code}: {response.text}"
        
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Partner apply test passed: {data.get('message', 'Success')}")
        elif response.status_code == 422:
            print(f"✅ Partner apply test passed (already applied)")
        else:
            print(f"✅ Partner apply endpoint exists (validation error expected)")


# Additional test to verify server.py constants match
class TestServerConstants:
    """Test server.py fee constants"""
    
    def test_partner_platform_fee_rate_in_server(self):
        """Test PARTNER_PLATFORM_FEE_RATE = 0.03 in server.py"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Import from server module
        from server import PARTNER_PLATFORM_FEE_RATE
        
        assert PARTNER_PLATFORM_FEE_RATE == 0.03, \
            f"Expected PARTNER_PLATFORM_FEE_RATE=0.03, got {PARTNER_PLATFORM_FEE_RATE}"
        
        print("✅ Server PARTNER_PLATFORM_FEE_RATE test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
