"""
BidVex Connect Payment Engine Tests - Iteration 103
Tests for Stripe Connect payment calculations, tier-based fees, deposits, and line items.

Features tested:
1. GET /api/payments/pricing-config - tier rates (Standard: 5%/4%, Premium: 3.5%/2.5%, VIP Elite: 3%/2%)
2. POST /api/auth/login - admin credentials
3. GET /api/deposits/status/{listing_id} - deposit status
4. calculate_connect_checkout math for Standard tier general auction ($1000)
5. calculate_connect_checkout math for VIP tier vehicle auction ($15000)
6. build_itemized_line_items for general auction (no platform fee)
7. build_itemized_line_items for vehicle auction (no hammer, includes platform fee)
8. Sum of line items equals buyer_total_cents
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestPricingConfig:
    """Test GET /api/payments/pricing-config endpoint for tier rates"""
    
    def test_pricing_config_returns_200(self):
        """Verify pricing-config endpoint is accessible (public)"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/payments/pricing-config returns 200")
    
    def test_pricing_config_buyer_premium_rates(self):
        """Verify buyer premium rates: Standard 5%, Premium 3.5%, VIP Elite 3%"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        data = response.json()
        
        buyer_premiums = data.get("buyer_premiums", {})
        
        # Standard tier (free/basic/standard) = 5%
        assert buyer_premiums.get("free") == 0.05, f"Expected free=0.05, got {buyer_premiums.get('free')}"
        assert buyer_premiums.get("basic") == 0.05, f"Expected basic=0.05, got {buyer_premiums.get('basic')}"
        assert buyer_premiums.get("standard") == 0.05, f"Expected standard=0.05, got {buyer_premiums.get('standard')}"
        
        # Premium tier = 3.5%
        assert buyer_premiums.get("premium") == 0.035, f"Expected premium=0.035, got {buyer_premiums.get('premium')}"
        
        # VIP Elite tier = 3%
        assert buyer_premiums.get("vip") == 0.03, f"Expected vip=0.03, got {buyer_premiums.get('vip')}"
        assert buyer_premiums.get("vip_elite") == 0.03, f"Expected vip_elite=0.03, got {buyer_premiums.get('vip_elite')}"
        
        print("✓ Buyer premium rates correct: Standard=5%, Premium=3.5%, VIP Elite=3%")
    
    def test_pricing_config_seller_commission_rates(self):
        """Verify seller commission rates: Standard 4%, Premium 2.5%, VIP Elite 2%"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        data = response.json()
        
        seller_commissions = data.get("seller_commissions", {})
        
        # Standard tier (free/basic/standard) = 4%
        assert seller_commissions.get("free") == 0.04, f"Expected free=0.04, got {seller_commissions.get('free')}"
        assert seller_commissions.get("basic") == 0.04, f"Expected basic=0.04, got {seller_commissions.get('basic')}"
        assert seller_commissions.get("standard") == 0.04, f"Expected standard=0.04, got {seller_commissions.get('standard')}"
        
        # Premium tier = 2.5%
        assert seller_commissions.get("premium") == 0.025, f"Expected premium=0.025, got {seller_commissions.get('premium')}"
        
        # VIP Elite tier = 2%
        assert seller_commissions.get("vip") == 0.02, f"Expected vip=0.02, got {seller_commissions.get('vip')}"
        assert seller_commissions.get("vip_elite") == 0.02, f"Expected vip_elite=0.02, got {seller_commissions.get('vip_elite')}"
        
        print("✓ Seller commission rates correct: Standard=4%, Premium=2.5%, VIP Elite=2%")
    
    def test_pricing_config_platform_fees(self):
        """Verify platform fees: General 3%, Vehicle 2.5%"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        data = response.json()
        
        commissions = data.get("commissions", {})
        
        assert commissions.get("general") == 0.03, f"Expected general=0.03, got {commissions.get('general')}"
        assert commissions.get("vehicle") == 0.025, f"Expected vehicle=0.025, got {commissions.get('vehicle')}"
        
        print("✓ Platform fees correct: General=3%, Vehicle=2.5%")
    
    def test_pricing_config_deposit_info(self):
        """Verify deposit threshold ($10k) and amount ($1000)"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        data = response.json()
        
        deposit = data.get("deposit", {})
        
        assert deposit.get("threshold_cad") == 10000, f"Expected threshold=10000, got {deposit.get('threshold_cad')}"
        assert deposit.get("amount_dollars") == 1000, f"Expected amount=1000, got {deposit.get('amount_dollars')}"
        
        print("✓ Deposit config correct: Threshold=$10,000, Amount=$1,000")


class TestAdminLogin:
    """Test POST /api/auth/login with admin credentials"""
    
    def test_admin_login_success(self):
        """Verify admin can login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Response should contain access_token"
        assert data.get("token_type") == "bearer", f"Expected token_type=bearer, got {data.get('token_type')}"
        
        print(f"✓ Admin login successful: {ADMIN_EMAIL}")
        return data.get("access_token")
    
    def test_admin_login_invalid_password(self):
        """Verify login fails with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword123!"
        })
        
        assert response.status_code in [401, 400], f"Expected 401/400, got {response.status_code}"
        print("✓ Invalid password correctly rejected")


class TestDepositStatus:
    """Test GET /api/deposits/status/{listing_id} endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_deposit_status_requires_auth(self):
        """Verify deposit status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/deposits/status/test-listing-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Deposit status endpoint requires authentication")
    
    def test_deposit_status_with_auth(self, auth_token):
        """Verify deposit status returns proper structure with auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Use a fake listing ID - should return has_deposit: false
        response = requests.get(
            f"{BASE_URL}/api/deposits/status/nonexistent-listing-123",
            headers=headers
        )
        
        # Should return 200 with deposit status info
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "has_deposit" in data, "Response should contain has_deposit field"
        assert "requires_deposit" in data, "Response should contain requires_deposit field"
        
        print(f"✓ Deposit status response: has_deposit={data.get('has_deposit')}, requires_deposit={data.get('requires_deposit')}")


class TestConnectPaymentEngineMath:
    """Test calculate_connect_checkout math directly"""
    
    def test_standard_tier_general_auction_1000(self):
        """
        Verify calculate_connect_checkout for Standard tier general auction ($1000)
        
        Expected breakdown:
        - Hammer: $1000
        - Buyer Premium (5%): $50
        - Platform Fee (3%): $30 (internal, not charged to buyer directly)
        - Seller Commission (4%): $40
        - Taxable = buyer_premium + platform_fee = $50 + $30 = $80
        - GST (5% of $80): $4.00
        - QST (9.975% of $80): $7.98
        - Pre-stripe total = hammer + buyer_premium + tax = $1000 + $50 + $11.98 = $1061.98
        - Stripe fee (2.9% + $0.30): ~$31.10
        - Stripe charge = $1061.98 + $31.10 = $1093.08
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        breakdown = calculate_connect_checkout(
            hammer_price=1000.0,
            category="general",
            buyer_tier="free",  # Standard tier
            seller_tier="free",
            currency="CAD",
            province="QC",
            include_stripe_fee=True
        )
        
        # Verify rates
        assert breakdown["buyer_premium_rate"] == 0.05, f"Expected buyer_premium_rate=0.05, got {breakdown['buyer_premium_rate']}"
        assert breakdown["seller_commission_rate"] == 0.04, f"Expected seller_commission_rate=0.04, got {breakdown['seller_commission_rate']}"
        assert breakdown["platform_fee_rate"] == 0.03, f"Expected platform_fee_rate=0.03, got {breakdown['platform_fee_rate']}"
        
        # Verify amounts
        assert breakdown["hammer_price"] == 1000.0, f"Expected hammer=1000, got {breakdown['hammer_price']}"
        assert breakdown["buyer_premium"] == 50.0, f"Expected buyer_premium=50, got {breakdown['buyer_premium']}"
        assert breakdown["platform_fee"] == 30.0, f"Expected platform_fee=30, got {breakdown['platform_fee']}"
        assert breakdown["seller_commission"] == 40.0, f"Expected seller_commission=40, got {breakdown['seller_commission']}"
        
        # Verify taxes (on buyer_premium + platform_fee = $80)
        assert breakdown["gst"] == 4.0, f"Expected gst=4.0, got {breakdown['gst']}"
        assert abs(breakdown["qst"] - 7.98) < 0.01, f"Expected qst≈7.98, got {breakdown['qst']}"
        
        # Verify is_vehicle is False
        assert breakdown["is_vehicle"] == False, f"Expected is_vehicle=False, got {breakdown['is_vehicle']}"
        
        # Verify buyer_total_cents equals stripe_charge in cents
        stripe_charge_cents = int(breakdown["stripe_charge"] * 100)
        assert abs(breakdown["buyer_total_cents"] - stripe_charge_cents) <= 1, \
            f"buyer_total_cents ({breakdown['buyer_total_cents']}) should equal stripe_charge in cents ({stripe_charge_cents})"
        
        print(f"✓ Standard tier general auction ($1000) breakdown verified:")
        print(f"  - Buyer Premium: ${breakdown['buyer_premium']}")
        print(f"  - GST: ${breakdown['gst']}, QST: ${breakdown['qst']}")
        print(f"  - Stripe Fee: ${breakdown['stripe_processing_fee']}")
        print(f"  - Stripe Charge: ${breakdown['stripe_charge']}")
        print(f"  - buyer_total_cents: {breakdown['buyer_total_cents']}")
    
    def test_vip_tier_vehicle_auction_15000(self):
        """
        Verify calculate_connect_checkout for VIP tier vehicle auction ($15000)
        
        Vehicle auctions: hammer paid offline, only fees through Stripe
        
        Expected breakdown:
        - Hammer: $15000 (paid offline)
        - Buyer Premium (3% VIP): $450
        - Platform Fee (2.5% vehicle): $375
        - Seller Commission (2% VIP): $300
        - Taxable = buyer_premium + platform_fee = $450 + $375 = $825
        - GST (5% of $825): $41.25
        - QST (9.975% of $825): $82.29
        - Pre-stripe total (vehicle) = buyer_premium + platform_fee + tax = $450 + $375 + $123.54 = $948.54
        - Stripe fee (2.9% + $0.30): ~$27.81
        - Stripe charge = $948.54 + $27.81 = $976.35
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        breakdown = calculate_connect_checkout(
            hammer_price=15000.0,
            category="vehicle",
            buyer_tier="vip",  # VIP Elite tier
            seller_tier="vip",
            currency="CAD",
            province="QC",
            include_stripe_fee=True
        )
        
        # Verify rates
        assert breakdown["buyer_premium_rate"] == 0.03, f"Expected buyer_premium_rate=0.03, got {breakdown['buyer_premium_rate']}"
        assert breakdown["seller_commission_rate"] == 0.02, f"Expected seller_commission_rate=0.02, got {breakdown['seller_commission_rate']}"
        assert breakdown["platform_fee_rate"] == 0.025, f"Expected platform_fee_rate=0.025, got {breakdown['platform_fee_rate']}"
        
        # Verify amounts
        assert breakdown["hammer_price"] == 15000.0, f"Expected hammer=15000, got {breakdown['hammer_price']}"
        assert breakdown["buyer_premium"] == 450.0, f"Expected buyer_premium=450, got {breakdown['buyer_premium']}"
        assert breakdown["platform_fee"] == 375.0, f"Expected platform_fee=375, got {breakdown['platform_fee']}"
        assert breakdown["seller_commission"] == 300.0, f"Expected seller_commission=300, got {breakdown['seller_commission']}"
        
        # Verify taxes (on buyer_premium + platform_fee = $825)
        assert breakdown["gst"] == 41.25, f"Expected gst=41.25, got {breakdown['gst']}"
        assert abs(breakdown["qst"] - 82.29) < 0.01, f"Expected qst≈82.29, got {breakdown['qst']}"
        
        # Verify is_vehicle is True
        assert breakdown["is_vehicle"] == True, f"Expected is_vehicle=True, got {breakdown['is_vehicle']}"
        
        # For vehicles, stripe_charge should NOT include hammer (paid offline)
        # stripe_charge = buyer_premium + platform_fee + tax + stripe_fee
        expected_pre_stripe = 450 + 375 + 41.25 + 82.29  # ~948.54
        assert breakdown["stripe_charge"] < 1000, f"Vehicle stripe_charge should be < $1000 (fees only), got {breakdown['stripe_charge']}"
        
        # Verify buyer_total_cents equals stripe_charge in cents
        stripe_charge_cents = int(breakdown["stripe_charge"] * 100)
        assert abs(breakdown["buyer_total_cents"] - stripe_charge_cents) <= 1, \
            f"buyer_total_cents ({breakdown['buyer_total_cents']}) should equal stripe_charge in cents ({stripe_charge_cents})"
        
        print(f"✓ VIP tier vehicle auction ($15000) breakdown verified:")
        print(f"  - Buyer Premium: ${breakdown['buyer_premium']}")
        print(f"  - Platform Fee: ${breakdown['platform_fee']}")
        print(f"  - GST: ${breakdown['gst']}, QST: ${breakdown['qst']}")
        print(f"  - Stripe Fee: ${breakdown['stripe_processing_fee']}")
        print(f"  - Stripe Charge (fees only): ${breakdown['stripe_charge']}")
        print(f"  - buyer_total_cents: {breakdown['buyer_total_cents']}")


class TestBuildItemizedLineItems:
    """Test build_itemized_line_items function"""
    
    def test_general_auction_line_items_no_platform_fee(self):
        """
        Verify build_itemized_line_items for general auction does NOT include platform fee
        
        General auction line items should include:
        - Hammer price
        - Buyer Premium
        - GST
        - QST
        - Stripe Processing Fee
        
        Should NOT include:
        - Platform fee (internal, part of application_fee)
        """
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items
        
        breakdown = calculate_connect_checkout(
            hammer_price=1000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            currency="CAD",
            province="QC",
            include_stripe_fee=True
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test General Auction",
            late_penalty=0.0,
            is_vehicle=False
        )
        
        # Check line item names
        item_names = [item["price_data"]["product_data"]["name"] for item in line_items]
        
        # Should have hammer price
        assert any("Test General Auction" in name for name in item_names), \
            f"Should include hammer price item, got: {item_names}"
        
        # Should have buyer premium
        assert any("Buyer Premium" in name for name in item_names), \
            f"Should include Buyer Premium, got: {item_names}"
        
        # Should have GST and QST
        assert any("GST" in name for name in item_names), f"Should include GST, got: {item_names}"
        assert any("QST" in name for name in item_names), f"Should include QST, got: {item_names}"
        
        # Should have processing fee
        assert any("Processing Fee" in name for name in item_names), \
            f"Should include Processing Fee, got: {item_names}"
        
        # Should NOT have platform fee (for general auctions)
        assert not any("Platform Fee" in name for name in item_names), \
            f"General auction should NOT include Platform Fee in line items, got: {item_names}"
        
        print(f"✓ General auction line items correct (no platform fee): {item_names}")
    
    def test_vehicle_auction_line_items_no_hammer_includes_platform_fee(self):
        """
        Verify build_itemized_line_items for vehicle auction:
        - Does NOT include hammer price (paid offline)
        - DOES include platform fee (explicitly charged to buyer)
        
        Vehicle auction line items should include:
        - Buyer Premium
        - Platform Fee
        - GST
        - QST
        - Stripe Processing Fee
        
        Should NOT include:
        - Hammer price (paid offline via bank draft)
        """
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items
        
        breakdown = calculate_connect_checkout(
            hammer_price=15000.0,
            category="vehicle",
            buyer_tier="vip",
            seller_tier="vip",
            currency="CAD",
            province="QC",
            include_stripe_fee=True
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test Vehicle Auction",
            late_penalty=0.0,
            is_vehicle=True
        )
        
        # Check line item names
        item_names = [item["price_data"]["product_data"]["name"] for item in line_items]
        
        # Should NOT have hammer price (vehicle pays offline)
        # Check that no item has the listing title as name with "Winning bid" description
        has_hammer = any(
            item["price_data"]["product_data"]["name"] == "Test Vehicle Auction" and 
            "Winning bid" in item["price_data"]["product_data"].get("description", "")
            for item in line_items
        )
        assert not has_hammer, \
            f"Vehicle auction should NOT include hammer price, got: {item_names}"
        
        # Should have buyer premium
        assert any("Buyer Premium" in name for name in item_names), \
            f"Should include Buyer Premium, got: {item_names}"
        
        # Should have platform fee (for vehicles)
        assert any("Platform Fee" in name for name in item_names), \
            f"Vehicle auction SHOULD include Platform Fee, got: {item_names}"
        
        # Should have GST and QST
        assert any("GST" in name for name in item_names), f"Should include GST, got: {item_names}"
        assert any("QST" in name for name in item_names), f"Should include QST, got: {item_names}"
        
        # Should have processing fee
        assert any("Processing Fee" in name for name in item_names), \
            f"Should include Processing Fee, got: {item_names}"
        
        print(f"✓ Vehicle auction line items correct (no hammer, includes platform fee): {item_names}")
    
    def test_line_items_sum_equals_buyer_total_cents_general(self):
        """Verify sum of line items equals buyer_total_cents for general auction"""
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items
        
        breakdown = calculate_connect_checkout(
            hammer_price=1000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            currency="CAD",
            province="QC",
            include_stripe_fee=True
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test General Auction",
            late_penalty=0.0,
            is_vehicle=False
        )
        
        # Sum all line item amounts
        total_cents = sum(item["price_data"]["unit_amount"] for item in line_items)
        
        # Should equal buyer_total_cents
        assert abs(total_cents - breakdown["buyer_total_cents"]) <= 1, \
            f"Line items sum ({total_cents}) should equal buyer_total_cents ({breakdown['buyer_total_cents']})"
        
        print(f"✓ General auction line items sum ({total_cents}) equals buyer_total_cents ({breakdown['buyer_total_cents']})")
    
    def test_line_items_sum_equals_buyer_total_cents_vehicle(self):
        """Verify sum of line items equals buyer_total_cents for vehicle auction"""
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items
        
        breakdown = calculate_connect_checkout(
            hammer_price=15000.0,
            category="vehicle",
            buyer_tier="vip",
            seller_tier="vip",
            currency="CAD",
            province="QC",
            include_stripe_fee=True
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test Vehicle Auction",
            late_penalty=0.0,
            is_vehicle=True
        )
        
        # Sum all line item amounts
        total_cents = sum(item["price_data"]["unit_amount"] for item in line_items)
        
        # Should equal buyer_total_cents
        assert abs(total_cents - breakdown["buyer_total_cents"]) <= 1, \
            f"Line items sum ({total_cents}) should equal buyer_total_cents ({breakdown['buyer_total_cents']})"
        
        print(f"✓ Vehicle auction line items sum ({total_cents}) equals buyer_total_cents ({breakdown['buyer_total_cents']})")


class TestAuctionWinnerPreview:
    """Test auction-winner-preview endpoint for tier-based breakdown with GST/QST"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed")
    
    def test_auction_winner_preview_endpoint_exists(self, auth_token):
        """Verify auction-winner-preview endpoint exists"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Try to access the endpoint with a fake listing ID
        # It should return 404 (listing not found) not 405 (method not allowed)
        response = requests.get(
            f"{BASE_URL}/api/payments/checkout/preview/nonexistent-listing-123",
            headers=headers
        )
        
        # Should be 404 (listing not found) not 405 (endpoint doesn't exist)
        assert response.status_code in [200, 404], \
            f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        print(f"✓ Auction winner preview endpoint exists (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
