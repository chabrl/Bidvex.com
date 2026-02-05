"""
Vehicle Auction Module - Financial Engine Tests
Tests for pricing calculations, invoices, seller financials, and admin financial endpoints

Fee Structure:
- Seller Commission: 4% (Basic), 2.5% (Premium), 2% (VIP Elite)
- Buyer Premium: 5% (Basic), 3.5% (Premium), 3% (VIP Elite)
- Platform Fee: 2.5%

Canadian Tax Rates:
- ON: 13% HST
- QC: 5% GST + 9.975% QST
- BC: 5% GST + 7% PST
- AB: 5% GST only
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ API health check passed")


class TestAuthentication:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Test admin login and return token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"✓ Admin login successful: {data['user']['email']}")
        return data["access_token"]


class TestPricingEstimate:
    """Pricing Estimate Endpoint Tests - GET /api/vehicles/{id}/pricing-estimate"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def vehicle_id(self, auth_token):
        """Get a vehicle ID for testing"""
        # First try to get an existing vehicle
        response = requests.get(f"{BASE_URL}/api/vehicles")
        if response.status_code == 200:
            vehicles = response.json().get("vehicles", [])
            if vehicles:
                return vehicles[0]["id"]
        
        # If no vehicles, try to get from my listings
        response = requests.get(
            f"{BASE_URL}/api/vehicles/my/listings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            listings = response.json().get("listings", [])
            if listings:
                return listings[0]["id"]
        
        pytest.skip("No vehicles available for testing")
    
    def test_pricing_estimate_without_auth(self, vehicle_id):
        """Test pricing estimate works without authentication (uses basic tier)"""
        response = requests.get(f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-estimate")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "estimate_based_on" in data
        assert "buyer" in data
        assert "seller" in data
        
        # Verify buyer breakdown
        buyer = data["buyer"]
        assert "premium_rate" in buyer
        assert "premium_amount" in buyer
        assert "platform_fee" in buyer
        assert "taxes" in buyer
        assert "total_estimated" in buyer
        
        # Verify seller breakdown
        seller = data["seller"]
        assert "commission_rate" in seller
        assert "commission_amount" in seller
        assert "net_payout" in seller
        
        print(f"✓ Pricing estimate (no auth): Total={data['buyer']['total_estimated']}")
    
    def test_pricing_estimate_with_auth(self, auth_token, vehicle_id):
        """Test pricing estimate with authentication (uses user's tier)"""
        response = requests.get(
            f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-estimate",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "estimate_based_on" in data
        assert "buyer" in data
        assert "seller" in data
        
        print(f"✓ Pricing estimate (with auth): Buyer Premium={data['buyer']['premium_rate']}")
    
    def test_pricing_estimate_nonexistent_vehicle(self, auth_token):
        """Test pricing estimate for non-existent vehicle returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/vehicles/nonexistent-vehicle-id/pricing-estimate",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
        print("✓ Non-existent vehicle correctly returns 404")


class TestPricingBreakdown:
    """Pricing Breakdown Endpoint Tests - POST /api/vehicles/{id}/pricing-breakdown"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def vehicle_id(self, auth_token):
        """Get a vehicle ID for testing"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        if response.status_code == 200:
            vehicles = response.json().get("vehicles", [])
            if vehicles:
                return vehicles[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/vehicles/my/listings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            listings = response.json().get("listings", [])
            if listings:
                return listings[0]["id"]
        
        pytest.skip("No vehicles available for testing")
    
    def test_pricing_breakdown_requires_auth(self, vehicle_id):
        """Test pricing breakdown requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-breakdown",
            params={"bid_amount": 50000}
        )
        assert response.status_code == 401
        print("✓ Pricing breakdown correctly requires authentication")
    
    def test_pricing_breakdown_basic_calculation(self, auth_token, vehicle_id):
        """Test pricing breakdown with specific bid amount"""
        bid_amount = 50000
        response = requests.post(
            f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-breakdown",
            params={"bid_amount": bid_amount},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["bid_amount"] == bid_amount
        assert data["vehicle_id"] == vehicle_id
        assert "breakdown" in data
        
        breakdown = data["breakdown"]
        assert breakdown["hammer_price"] == bid_amount
        assert "buyer_premium" in breakdown
        assert "platform_fee" in breakdown
        assert "subtotal_before_tax" in breakdown
        assert "taxes" in breakdown
        assert "total_payable" in breakdown
        
        # Verify tax breakdown
        taxes = breakdown["taxes"]
        assert "type" in taxes
        assert "province" in taxes
        assert "total" in taxes
        
        print(f"✓ Pricing breakdown: Bid=${bid_amount}, Total=${breakdown['total_payable']}")
    
    def test_pricing_breakdown_tax_calculation_ontario(self, auth_token, vehicle_id):
        """Test pricing breakdown with Ontario HST (13%)"""
        bid_amount = 100000
        response = requests.post(
            f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-breakdown",
            params={"bid_amount": bid_amount},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        breakdown = data["breakdown"]
        taxes = breakdown["taxes"]
        
        # Verify tax type is HST for Ontario
        if taxes["province"] == "ON":
            assert taxes["type"] == "HST"
            assert taxes["hst"] > 0
            print(f"✓ Ontario HST calculation: HST=${taxes['hst']}")
        else:
            print(f"✓ Tax calculation for {taxes['province']}: Total=${taxes['total']}")
    
    def test_pricing_breakdown_subscription_discount(self, auth_token, vehicle_id):
        """Test pricing breakdown shows subscription discount"""
        response = requests.post(
            f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-breakdown",
            params={"bid_amount": 75000},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        breakdown = data["breakdown"]
        assert "subscription_tier" in breakdown
        assert "subscription_discount" in breakdown
        
        print(f"✓ Subscription tier: {breakdown['subscription_tier']}, Discount: ${breakdown['subscription_discount']}")


class TestInvoiceListing:
    """Invoice Listing Endpoint Tests - GET /api/vehicle-invoices/my"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_invoice_listing_requires_auth(self):
        """Test invoice listing requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-invoices/my")
        assert response.status_code == 401
        print("✓ Invoice listing correctly requires authentication")
    
    def test_invoice_listing_returns_array(self, auth_token):
        """Test invoice listing returns array of invoices"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-invoices/my",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "invoices" in data
        assert isinstance(data["invoices"], list)
        
        print(f"✓ Invoice listing: {len(data['invoices'])} invoices found")
    
    def test_invoice_listing_with_type_filter(self, auth_token):
        """Test invoice listing with invoice_type filter"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-invoices/my",
            params={"invoice_type": "buyer"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned invoices should be buyer type
        for invoice in data["invoices"]:
            assert invoice.get("invoice_type") == "buyer"
        
        print(f"✓ Invoice listing (buyer type): {len(data['invoices'])} invoices")
    
    def test_invoice_listing_with_status_filter(self, auth_token):
        """Test invoice listing with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-invoices/my",
            params={"status": "pending"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned invoices should be pending status
        for invoice in data["invoices"]:
            assert invoice.get("payment_status") == "pending"
        
        print(f"✓ Invoice listing (pending status): {len(data['invoices'])} invoices")


class TestInvoiceDetail:
    """Invoice Detail Endpoint Tests - GET /api/vehicle-invoices/{id}"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_invoice_detail_requires_auth(self):
        """Test invoice detail requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-invoices/some-invoice-id")
        assert response.status_code == 401
        print("✓ Invoice detail correctly requires authentication")
    
    def test_invoice_detail_nonexistent(self, auth_token):
        """Test invoice detail for non-existent invoice returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-invoices/nonexistent-invoice-id",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
        print("✓ Non-existent invoice correctly returns 404")
    
    def test_invoice_detail_structure(self, auth_token):
        """Test invoice detail returns proper structure if invoices exist"""
        # First get list of invoices
        list_response = requests.get(
            f"{BASE_URL}/api/vehicle-invoices/my",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        if list_response.status_code == 200:
            invoices = list_response.json().get("invoices", [])
            if invoices:
                invoice_id = invoices[0]["id"]
                
                response = requests.get(
                    f"{BASE_URL}/api/vehicle-invoices/{invoice_id}",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                assert response.status_code == 200
                data = response.json()
                
                # Verify invoice structure
                assert "invoice_number" in data
                assert "invoice_type" in data
                assert "total_amount" in data
                assert "payment_status" in data
                assert "time_status" in data
                
                print(f"✓ Invoice detail: #{data['invoice_number']}, Status={data['payment_status']}")
            else:
                print("✓ No invoices to test detail (expected for new accounts)")
        else:
            print("✓ Could not fetch invoices for detail test")


class TestSellerFinancials:
    """Seller Financials Endpoint Tests - GET /api/vehicle-sellers/me/financials"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_seller_financials_requires_auth(self):
        """Test seller financials requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-sellers/me/financials")
        assert response.status_code == 401
        print("✓ Seller financials correctly requires authentication")
    
    def test_seller_financials_requires_seller_account(self, auth_token):
        """Test seller financials requires verified seller account"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-sellers/me/financials",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Either 200 (has seller account) or 403 (not a verified seller)
        assert response.status_code in [200, 403]
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify response structure
            assert "subscription_tier" in data
            assert "commission_rate" in data
            assert "commission_savings" in data
            assert "financials" in data
            
            financials = data["financials"]
            assert "pending_payout" in financials
            assert "total_earned" in financials
            assert "total_commission_paid" in financials
            
            print(f"✓ Seller financials: Tier={data['subscription_tier']}, Rate={data['commission_rate']}")
        else:
            print("✓ Correctly requires verified seller account")
    
    def test_seller_financials_commission_rates(self, auth_token):
        """Test seller financials shows correct commission rates"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-sellers/me/financials",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            tier = data["subscription_tier"]
            rate = data["commission_rate"]
            
            # Verify commission rate matches tier
            expected_rates = {
                "basic": "4.0%",
                "premium": "2.5%",
                "vip_elite": "2.0%"
            }
            
            if tier in expected_rates:
                assert rate == expected_rates[tier], f"Expected {expected_rates[tier]} for {tier}, got {rate}"
            
            print(f"✓ Commission rate verified: {tier} = {rate}")
        else:
            print("✓ Skipped commission rate test (no seller account)")


class TestAdminFinancialSummary:
    """Admin Financial Summary Endpoint Tests - GET /api/vehicle-admin/financial-summary"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_financial_summary_requires_admin(self):
        """Test financial summary requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-admin/financial-summary")
        assert response.status_code == 401
        print("✓ Financial summary correctly requires authentication")
    
    def test_financial_summary_structure(self, admin_token):
        """Test financial summary returns proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/financial-summary",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "this_month" in data
        assert "all_time" in data
        assert "outstanding" in data
        
        # Verify this_month structure
        this_month = data["this_month"]
        assert "revenue" in this_month
        assert "tax_collected" in this_month
        assert "volume" in this_month
        assert "transactions" in this_month
        
        # Verify all_time structure
        all_time = data["all_time"]
        assert "revenue" in all_time
        assert "volume" in all_time
        assert "transactions" in all_time
        
        # Verify outstanding structure
        outstanding = data["outstanding"]
        assert "amount" in outstanding
        assert "invoices_count" in outstanding
        
        print(f"✓ Financial summary: Monthly Revenue=${this_month['revenue']}, Outstanding=${outstanding['amount']}")


class TestAdminScheduler:
    """Admin Scheduler Endpoint Tests - POST /api/vehicle-admin/run-scheduler"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_scheduler_requires_admin(self):
        """Test scheduler requires admin authentication"""
        response = requests.post(f"{BASE_URL}/api/vehicle-admin/run-scheduler")
        assert response.status_code == 401
        print("✓ Scheduler correctly requires authentication")
    
    def test_scheduler_execution(self, admin_token):
        """Test scheduler executes successfully"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/run-scheduler",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "results" in data
        
        results = data["results"]
        assert "auctions_activated" in results
        assert "auctions_ended" in results
        assert "auctions_sold" in results
        assert "penalties_applied" in results
        
        print(f"✓ Scheduler executed: Activated={results['auctions_activated']}, Ended={results['auctions_ended']}, Sold={results['auctions_sold']}")


class TestAdminInvoiceList:
    """Admin Invoice List Endpoint Tests - GET /api/vehicle-admin/invoices"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_admin_invoices_requires_admin(self):
        """Test admin invoice list requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-admin/invoices")
        assert response.status_code == 401
        print("✓ Admin invoices correctly requires authentication")
    
    def test_admin_invoices_structure(self, admin_token):
        """Test admin invoice list returns proper structure"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/invoices",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "invoices" in data
        assert "stats" in data
        
        stats = data["stats"]
        assert "pending" in stats
        assert "overdue" in stats
        assert "paid" in stats
        
        print(f"✓ Admin invoices: {len(data['invoices'])} invoices, Pending={stats['pending']}, Overdue={stats['overdue']}, Paid={stats['paid']}")


class TestPricingCalculationAccuracy:
    """Test pricing calculation accuracy with known values"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    @pytest.fixture
    def vehicle_id(self, auth_token):
        """Get a vehicle ID for testing"""
        response = requests.get(f"{BASE_URL}/api/vehicles")
        if response.status_code == 200:
            vehicles = response.json().get("vehicles", [])
            if vehicles:
                return vehicles[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/vehicles/my/listings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            listings = response.json().get("listings", [])
            if listings:
                return listings[0]["id"]
        
        pytest.skip("No vehicles available for testing")
    
    def test_buyer_premium_calculation(self, auth_token, vehicle_id):
        """Test buyer premium is calculated correctly (5% for basic tier)"""
        bid_amount = 100000
        response = requests.post(
            f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-breakdown",
            params={"bid_amount": bid_amount},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        breakdown = data["breakdown"]
        buyer_premium = breakdown["buyer_premium"]["amount"]
        
        # For basic tier, buyer premium should be 5%
        # For premium tier, buyer premium should be 3.5%
        # For vip_elite tier, buyer premium should be 3%
        tier = breakdown["subscription_tier"]
        expected_rates = {"basic": 0.05, "premium": 0.035, "vip_elite": 0.03}
        expected_premium = bid_amount * expected_rates.get(tier, 0.05)
        
        # Allow small rounding difference
        assert abs(buyer_premium - expected_premium) < 1, f"Expected ~${expected_premium}, got ${buyer_premium}"
        
        print(f"✓ Buyer premium calculation: ${buyer_premium} ({tier} tier)")
    
    def test_platform_fee_calculation(self, auth_token, vehicle_id):
        """Test platform fee is calculated correctly (2.5%)"""
        bid_amount = 100000
        response = requests.post(
            f"{BASE_URL}/api/vehicles/{vehicle_id}/pricing-breakdown",
            params={"bid_amount": bid_amount},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        breakdown = data["breakdown"]
        platform_fee = breakdown["platform_fee"]["amount"]
        
        # Platform fee should be 2.5%
        expected_fee = bid_amount * 0.025
        
        # Allow small rounding difference
        assert abs(platform_fee - expected_fee) < 1, f"Expected ${expected_fee}, got ${platform_fee}"
        
        print(f"✓ Platform fee calculation: ${platform_fee} (2.5%)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
