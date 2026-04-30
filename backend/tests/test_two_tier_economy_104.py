"""
[DEPRECATED — iteration 104 audit, superseded by iteration 165 spec]

This test file encoded the pre-iteration-165 pricing math:
  • Buyer Stripe Recovery on BP only (old; now: on hammer + BP)
  • Partner buyer.total = $0 (old; now: hammer + partner_bp; BidVex fee stays $0)

The replacement, definitive test suite is `test_seller_type_pricing_165.py`.
This file is kept for historical context but skipped at runtime so its
obsolete assertions don't block the regression gate.

BidVex Two-Tier Marketplace Economy Tests (Iteration 104)

Tests the new Two-Tier economy system:
- PARTNER FLOW (is_partner=True, $100/yr): BidVex takes ONLY Seller Commission (2.5%/3%)
- STANDARD FLOW (is_partner=False): BidVex takes BOTH Buyer Premium AND Seller Commission

Tax calculation: GST (5%) + QST (9.975%) on (Hammer + Premium)
"""

import pytest
pytestmark = pytest.mark.skip(
    reason="Superseded by test_seller_type_pricing_165.py (iteration 165 spec)"
)
import requests
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com')


class TestPricingConfigEndpoint:
    """Test the public pricing-config endpoint returns tier rates"""
    
    def test_pricing_config_returns_tier_rates(self):
        """GET /api/payments/pricing-config returns tier rates"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify commissions
        assert "commissions" in data
        assert data["commissions"]["general"] == 0.03, "General platform fee should be 3%"
        assert data["commissions"]["vehicle"] == 0.025, "Vehicle platform fee should be 2.5%"
        
        # Verify buyer premiums
        assert "buyer_premiums" in data
        assert data["buyer_premiums"]["free"] == 0.05, "Free tier buyer premium should be 5%"
        assert data["buyer_premiums"]["partner"] == 0.05, "Partner tier buyer premium should be 5%"
        
        # Verify seller commissions
        assert "seller_commissions" in data
        assert data["seller_commissions"]["free"] == 0.04, "Free tier seller commission should be 4%"
        
        print("✓ Pricing config endpoint returns correct tier rates")


class TestPartnerFlowCalculations:
    """Test PARTNER_FLOW calculations (seller_is_partner=True)"""
    
    def test_partner_flow_general_5000(self):
        """
        PARTNER FLOW for $5000 general item:
        - flow_type = PARTNER_FLOW
        - application_fee = seller_commission only (3% = $150)
        - stripe_processing_fee = $0 (Partner absorbs)
        - partner_premium_retained = buyer_premium (5% = $250)
        - Taxes on (Hammer + Premium) = $5250
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=True,
            include_stripe_fee=True
        )
        
        # Flow type
        assert result["flow_type"] == "PARTNER_FLOW", f"Expected PARTNER_FLOW, got {result['flow_type']}"
        assert result["seller_is_partner"] == True
        
        # Buyer premium (5% of $5000 = $250)
        assert result["buyer_premium"] == 250.0, f"Expected buyer_premium=250, got {result['buyer_premium']}"
        
        # Platform fee / seller commission (3% of $5000 = $150)
        assert result["platform_fee"] == 150.0, f"Expected platform_fee=150, got {result['platform_fee']}"
        assert result["seller_commission"] == 150.0, f"Expected seller_commission=150, got {result['seller_commission']}"
        
        # Partner retains buyer premium
        assert result["partner_premium_retained"] == 250.0, f"Expected partner_premium_retained=250, got {result['partner_premium_retained']}"
        
        # Stripe processing fee = $0 for Partner flow
        assert result["stripe_processing_fee"] == 0.0, f"Expected stripe_processing_fee=0, got {result['stripe_processing_fee']}"
        
        # Application fee = seller commission only (NOT buyer premium)
        assert result["application_fee"] == 150.0, f"Expected application_fee=150, got {result['application_fee']}"
        
        # Tax calculation: GST + QST on (Hammer + Premium) = $5250
        taxable = 5000 + 250  # $5250
        expected_gst = round(taxable * 0.05, 2)  # $262.50
        expected_qst = round(taxable * 0.09975, 2)  # $523.69
        
        assert result["taxable_amount"] == 5250.0, f"Expected taxable_amount=5250, got {result['taxable_amount']}"
        assert result["gst"] == expected_gst, f"Expected GST={expected_gst}, got {result['gst']}"
        assert abs(result["qst"] - expected_qst) < 0.02, f"Expected QST≈{expected_qst}, got {result['qst']}"
        
        print(f"✓ PARTNER FLOW $5000 general: flow_type={result['flow_type']}, app_fee=${result['application_fee']}, stripe_fee=${result['stripe_processing_fee']}, partner_retained=${result['partner_premium_retained']}")
        print(f"  Taxes: GST=${result['gst']}, QST=${result['qst']} on taxable=${result['taxable_amount']}")
    
    def test_partner_flow_vehicle_10000(self):
        """
        PARTNER FLOW for $10000 vehicle:
        - Platform fee = 2.5% = $250
        - Buyer premium = 5% = $500
        - Stripe fee = $0 (Partner absorbs)
        - Hammer NOT in Stripe charge (paid offline)
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=10000.0,
            category="vehicle",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=True,
            include_stripe_fee=True
        )
        
        assert result["flow_type"] == "PARTNER_FLOW"
        assert result["is_vehicle"] == True
        
        # Platform fee = 2.5% for vehicles
        assert result["platform_fee"] == 250.0, f"Expected platform_fee=250, got {result['platform_fee']}"
        
        # Buyer premium = 5%
        assert result["buyer_premium"] == 500.0, f"Expected buyer_premium=500, got {result['buyer_premium']}"
        
        # Stripe fee = $0 for Partner
        assert result["stripe_processing_fee"] == 0.0
        
        # Partner retains buyer premium
        assert result["partner_premium_retained"] == 500.0
        
        print(f"✓ PARTNER FLOW $10000 vehicle: platform_fee=${result['platform_fee']}, buyer_premium=${result['buyer_premium']}, stripe_fee=${result['stripe_processing_fee']}")


class TestStandardFlowCalculations:
    """Test STANDARD_FLOW calculations (seller_is_partner=False)"""
    
    def test_standard_flow_general_5000(self):
        """
        STANDARD FLOW for $5000 general item:
        - flow_type = STANDARD_FLOW
        - application_fee = buyer_premium + seller_commission + taxes
        - stripe_processing_fee > $0 (Buyer pays)
        - partner_premium_retained = $0
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=False,
            include_stripe_fee=True
        )
        
        # Flow type
        assert result["flow_type"] == "STANDARD_FLOW", f"Expected STANDARD_FLOW, got {result['flow_type']}"
        assert result["seller_is_partner"] == False
        
        # Buyer premium (5% of $5000 = $250)
        assert result["buyer_premium"] == 250.0
        
        # Seller commission (4% for free tier = $200)
        assert result["seller_commission"] == 200.0, f"Expected seller_commission=200, got {result['seller_commission']}"
        
        # Partner premium retained = $0 for Standard flow
        assert result["partner_premium_retained"] == 0.0, f"Expected partner_premium_retained=0, got {result['partner_premium_retained']}"
        
        # Stripe processing fee > $0 for Standard flow
        assert result["stripe_processing_fee"] > 0, f"Expected stripe_processing_fee > 0, got {result['stripe_processing_fee']}"
        
        # Application fee = buyer_premium + seller_commission + taxes (BidVex keeps both)
        expected_app_fee = result["buyer_premium"] + result["seller_commission"] + result["total_tax"]
        assert abs(result["application_fee"] - expected_app_fee) < 0.02, f"Expected application_fee≈{expected_app_fee}, got {result['application_fee']}"
        
        # Tax calculation: GST + QST on (Hammer + Premium) = $5250
        assert result["taxable_amount"] == 5250.0
        assert result["gst"] == 262.5, f"Expected GST=262.5, got {result['gst']}"
        
        print(f"✓ STANDARD FLOW $5000 general: flow_type={result['flow_type']}, app_fee=${result['application_fee']}, stripe_fee=${result['stripe_processing_fee']}")
        print(f"  BidVex keeps: buyer_premium=${result['buyer_premium']} + seller_commission=${result['seller_commission']} + taxes=${result['total_tax']}")
    
    def test_standard_flow_vehicle_10000(self):
        """
        STANDARD FLOW for $10000 vehicle:
        - Stripe fee > $0 (Buyer pays)
        - BidVex collects all fees (no Connect split for vehicles)
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=10000.0,
            category="vehicle",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=False,
            include_stripe_fee=True
        )
        
        assert result["flow_type"] == "STANDARD_FLOW"
        assert result["is_vehicle"] == True
        
        # Stripe fee > $0 for Standard flow
        assert result["stripe_processing_fee"] > 0, f"Expected stripe_processing_fee > 0, got {result['stripe_processing_fee']}"
        
        # Partner premium retained = $0
        assert result["partner_premium_retained"] == 0.0
        
        print(f"✓ STANDARD FLOW $10000 vehicle: stripe_fee=${result['stripe_processing_fee']}, partner_retained=${result['partner_premium_retained']}")


class TestTaxCalculations:
    """Test GST/QST calculations on (Hammer + Premium)"""
    
    def test_tax_on_5000_general(self):
        """
        For $5000 general item:
        - Taxable = Hammer + Premium = $5000 + $250 = $5250
        - GST (5%) = $262.50
        - QST (9.975%) = $523.69
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=False
        )
        
        # Taxable amount = Hammer + Premium
        expected_taxable = 5000 + 250  # $5250
        assert result["taxable_amount"] == expected_taxable, f"Expected taxable={expected_taxable}, got {result['taxable_amount']}"
        
        # GST = 5% of $5250 = $262.50
        expected_gst = 262.50
        assert result["gst"] == expected_gst, f"Expected GST={expected_gst}, got {result['gst']}"
        
        # QST = 9.975% of $5250 = $523.6875 ≈ $523.69
        expected_qst = round(5250 * 0.09975, 2)  # $523.69
        assert abs(result["qst"] - expected_qst) < 0.02, f"Expected QST≈{expected_qst}, got {result['qst']}"
        
        print(f"✓ Tax calculation for $5000 general: taxable=${result['taxable_amount']}, GST=${result['gst']}, QST=${result['qst']}")
    
    def test_tax_on_1000_premium_tier(self):
        """
        For $1000 general item with premium buyer tier:
        - Buyer premium = 3.5% = $35
        - Taxable = $1000 + $35 = $1035
        - GST = $51.75
        - QST = $103.24
        """
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=1000.0,
            category="general",
            buyer_tier="premium",
            seller_tier="free",
            seller_is_partner=False
        )
        
        # Buyer premium = 3.5% for premium tier
        assert result["buyer_premium"] == 35.0, f"Expected buyer_premium=35, got {result['buyer_premium']}"
        
        # Taxable = $1035
        assert result["taxable_amount"] == 1035.0, f"Expected taxable=1035, got {result['taxable_amount']}"
        
        # GST = 5% of $1035 = $51.75
        assert result["gst"] == 51.75, f"Expected GST=51.75, got {result['gst']}"
        
        print(f"✓ Tax calculation for $1000 premium tier: buyer_premium=${result['buyer_premium']}, taxable=${result['taxable_amount']}, GST=${result['gst']}")


class TestLineItemsGeneration:
    """Test build_itemized_line_items for Partner vs Standard flows"""
    
    def test_partner_flow_no_processing_fee_line(self):
        """PARTNER FLOW: build_itemized_line_items does NOT include 'Processing Fee' line"""
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items
        
        breakdown = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=True
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test Item",
            is_vehicle=False
        )
        
        # Check that no line item contains "Processing Fee"
        processing_fee_items = [
            item for item in line_items 
            if "Processing" in item["price_data"]["product_data"]["name"]
        ]
        
        assert len(processing_fee_items) == 0, f"PARTNER FLOW should NOT have Processing Fee line, found: {processing_fee_items}"
        
        # Verify buyer premium description mentions Partner
        premium_items = [
            item for item in line_items 
            if "Buyer Premium" in item["price_data"]["product_data"]["name"]
        ]
        assert len(premium_items) == 1
        assert "Partner" in premium_items[0]["price_data"]["product_data"]["description"], "Buyer Premium should mention Partner"
        
        print(f"✓ PARTNER FLOW line items: {len(line_items)} items, no Processing Fee line")
    
    def test_standard_flow_includes_processing_fee_line(self):
        """STANDARD FLOW: build_itemized_line_items includes 'Processing Fee' line"""
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items
        
        breakdown = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=False
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test Item",
            is_vehicle=False
        )
        
        # Check that Processing Fee line exists
        processing_fee_items = [
            item for item in line_items 
            if "Processing" in item["price_data"]["product_data"]["name"]
        ]
        
        assert len(processing_fee_items) == 1, f"STANDARD FLOW should have Processing Fee line, found: {len(processing_fee_items)}"
        
        print(f"✓ STANDARD FLOW line items: {len(line_items)} items, includes Processing Fee line")
    
    def test_line_items_sum_equals_buyer_total_cents(self):
        """Line items sum matches buyer_total_cents for both flows"""
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items, _to_cents
        
        for is_partner in [True, False]:
            breakdown = calculate_connect_checkout(
                hammer_price=5000.0,
                category="general",
                buyer_tier="free",
                seller_tier="free",
                seller_is_partner=is_partner
            )
            
            line_items = build_itemized_line_items(
                breakdown=breakdown,
                listing_title="Test Item",
                is_vehicle=False
            )
            
            # Sum all line item amounts
            total_cents = sum(item["price_data"]["unit_amount"] for item in line_items)
            
            flow_type = "PARTNER" if is_partner else "STANDARD"
            assert total_cents == breakdown["buyer_total_cents"], \
                f"{flow_type} FLOW: Line items sum ({total_cents}) != buyer_total_cents ({breakdown['buyer_total_cents']})"
            
            print(f"✓ {flow_type} FLOW: Line items sum = {total_cents} cents = buyer_total_cents")
    
    def test_vehicle_flow_no_hammer_in_line_items(self):
        """Vehicle flows: hammer not in line items, platform fee IS in line items"""
        from services.connect_payment_engine import calculate_connect_checkout, build_itemized_line_items
        
        breakdown = calculate_connect_checkout(
            hammer_price=10000.0,
            category="vehicle",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=True
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test Vehicle",
            is_vehicle=True
        )
        
        # Check no hammer price line (vehicles pay hammer offline)
        hammer_items = [
            item for item in line_items 
            if "Winning bid" in item["price_data"]["product_data"].get("description", "")
        ]
        assert len(hammer_items) == 0, "Vehicle flow should NOT have hammer price in line items"
        
        # Check platform fee IS in line items for vehicles
        platform_fee_items = [
            item for item in line_items 
            if "Platform Fee" in item["price_data"]["product_data"]["name"]
        ]
        assert len(platform_fee_items) == 1, "Vehicle flow should have Platform Fee in line items"
        
        print(f"✓ Vehicle flow: No hammer in line items, Platform Fee present")


class TestPartnerStatsEndpoint:
    """Test GET /api/partner/stats returns partner_benefit object"""
    
    def test_partner_stats_requires_auth(self):
        """Partner stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/partner/stats")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Partner stats endpoint requires authentication")
    
    def test_partner_stats_returns_partner_benefit(self):
        """GET /api/partner/stats returns partner_benefit with premiums_retained_this_month"""
        # Login as admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "charbeladmin@bidvex.com", "password": "Admin123!"}
        )
        
        if login_response.status_code != 200:
            pytest.skip("Admin login failed - skipping partner stats test")
        
        data = login_response.json()
        token = data.get("access_token") or data.get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/partner/stats", headers=headers)
        
        # Admin may not be a partner, but endpoint should work
        if response.status_code == 403:
            print("✓ Partner stats endpoint correctly restricts non-partner access")
            return
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check partner_benefit object exists
        assert "partner_benefit" in data, "Response should contain partner_benefit object"
        
        partner_benefit = data["partner_benefit"]
        assert "premiums_retained_this_month" in partner_benefit, "partner_benefit should have premiums_retained_this_month"
        assert "transactions_this_month" in partner_benefit, "partner_benefit should have transactions_this_month"
        
        print(f"✓ Partner stats returns partner_benefit: premiums_retained=${partner_benefit['premiums_retained_this_month']}, transactions={partner_benefit['transactions_this_month']}")


class TestStripeMetadataFlowType:
    """Test that Stripe metadata includes flow_type field"""
    
    def test_breakdown_includes_flow_type(self):
        """calculate_connect_checkout returns flow_type in breakdown"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        # Partner flow
        partner_result = calculate_connect_checkout(
            hammer_price=1000.0,
            category="general",
            seller_is_partner=True
        )
        assert partner_result["flow_type"] == "PARTNER_FLOW"
        
        # Standard flow
        standard_result = calculate_connect_checkout(
            hammer_price=1000.0,
            category="general",
            seller_is_partner=False
        )
        assert standard_result["flow_type"] == "STANDARD_FLOW"
        
        print("✓ Breakdown includes flow_type field for both Partner and Standard flows")


class TestApplicationFeeCalculation:
    """Test application_fee calculation differs between Partner and Standard flows"""
    
    def test_partner_application_fee_is_seller_commission_only(self):
        """PARTNER FLOW: application_fee = seller_commission only"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=True
        )
        
        # For Partner flow, application_fee should equal seller_commission (platform fee)
        assert result["application_fee"] == result["seller_commission"], \
            f"PARTNER: application_fee ({result['application_fee']}) should equal seller_commission ({result['seller_commission']})"
        
        # And NOT include buyer_premium
        assert result["application_fee"] != result["buyer_premium"] + result["seller_commission"], \
            "PARTNER: application_fee should NOT include buyer_premium"
        
        print(f"✓ PARTNER application_fee = seller_commission = ${result['application_fee']}")
    
    def test_standard_application_fee_includes_premium_and_commission(self):
        """STANDARD FLOW: application_fee = buyer_premium + seller_commission + taxes"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=False
        )
        
        # For Standard flow, application_fee should include buyer_premium + seller_commission + taxes
        expected = result["buyer_premium"] + result["seller_commission"] + result["total_tax"]
        assert abs(result["application_fee"] - expected) < 0.02, \
            f"STANDARD: application_fee ({result['application_fee']}) should equal premium+commission+tax ({expected})"
        
        print(f"✓ STANDARD application_fee = ${result['application_fee']} (premium + commission + tax)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
