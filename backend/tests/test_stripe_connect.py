"""
Tests for Stripe Connect Payment Service
Tests destination charges, gross-up formula, and checkout calculations
"""

import pytest
from decimal import Decimal
from services.stripe_connect_service import (
    calculate_general_checkout,
    calculate_vehicle_checkout,
    calculate_processing_fee,
    STRIPE_PERCENTAGE_FEE,
    STRIPE_FIXED_FEE,
    _gross_up,
)


class TestGrossUpFormula:
    """Test the gross-up formula for processing fees"""
    
    def test_gross_up_100_dollars(self):
        """Test gross-up for $100 net"""
        net = Decimal("100.00")
        gross = _gross_up(net)
        
        # Verify: gross * 0.029 + 0.30 = gross - net
        stripe_fee = gross * STRIPE_PERCENTAGE_FEE + STRIPE_FIXED_FEE
        received = gross - stripe_fee
        
        # Should receive approximately $100 (within 1 cent due to rounding)
        assert abs(float(received) - 100.0) < 0.02
    
    def test_gross_up_1000_dollars(self):
        """Test gross-up for $1000 net"""
        net = Decimal("1000.00")
        gross = _gross_up(net)
        
        # Gross should be higher than net
        assert gross > net
        
        # Stripe fee should be covered
        stripe_fee = gross * STRIPE_PERCENTAGE_FEE + STRIPE_FIXED_FEE
        received = gross - stripe_fee
        
        # Should receive approximately $1000
        assert abs(float(received) - 1000.0) < 0.02
    
    def test_processing_fee_calculation(self):
        """Test standalone processing fee calculation"""
        amount = Decimal("100.00")
        fee = calculate_processing_fee(amount)
        
        # 100 * 0.029 + 0.30 = 3.20
        expected = Decimal("3.20")
        assert fee == expected


class TestGeneralCheckout:
    """Test general auction checkout calculations"""
    
    def test_private_seller_1000(self):
        """Test checkout for $1000 item, private seller"""
        result = calculate_general_checkout(
            hammer_price=1000,
            buyer_tier="basic",
            seller_tier="basic",
            seller_is_tax_registered=False,
            include_processing_fee=True
        )
        
        # Verify basic calculations
        assert result.hammer_price == Decimal("1000")
        assert result.buyer_premium_rate == Decimal("0.05")
        assert result.buyer_premium == Decimal("50.00")
        assert result.seller_commission_rate == Decimal("0.04")
        assert result.seller_commission == Decimal("40.00")
        
        # No tax on hammer for private seller
        assert result.hammer_tax_total == Decimal("0")
        
        # Tax on fees (5% + 9.975% on $90 = $13.48)
        assert result.bidvex_fees_subtotal == Decimal("90.00")
        assert result.fees_tax_total > 0
        
        # Processing fee should be positive
        assert result.processing_fee > 0
        
        # Buyer total should include hammer + premium + fees tax + processing
        assert result.buyer_total > Decimal("1050")
    
    def test_business_seller_1000(self):
        """Test checkout for $1000 item, business seller (tax registered)"""
        result = calculate_general_checkout(
            hammer_price=1000,
            buyer_tier="basic",
            seller_tier="basic",
            seller_is_tax_registered=True,
            include_processing_fee=True
        )
        
        # Tax on hammer for business seller (14.975% on $1000)
        assert result.hammer_tax_total > Decimal("149")
        
        # Buyer total should be higher (includes hammer tax)
        assert result.buyer_total > Decimal("1200")
        
        # Seller receives tax collected on their behalf
        assert result.seller_receives_tax > 0
    
    def test_stripe_parameters(self):
        """Test Stripe destination charge parameters"""
        result = calculate_general_checkout(
            hammer_price=1000,
            seller_is_tax_registered=False,
            include_processing_fee=True
        )
        
        # Stripe amounts should be integers (cents)
        assert isinstance(result.stripe_charge_amount_cents, int)
        assert isinstance(result.stripe_application_fee_cents, int)
        assert isinstance(result.stripe_transfer_amount_cents, int)
        
        # Application fee = BidVex fees (premium + commission) + tax on fees
        # Does NOT include processing fee (that's Stripe's cut)
        assert result.stripe_application_fee_cents > 0
        
        # Transfer = hammer - commission (what seller receives)
        assert result.stripe_transfer_amount_cents > 0
        
        # Total charge = application fee + transfer + processing fee
        # (Processing fee goes to Stripe, not to either party)
        assert result.stripe_charge_amount_cents > (
            result.stripe_application_fee_cents + result.stripe_transfer_amount_cents
        )
    
    def test_premium_tier_rates(self):
        """Test premium tier gets better rates"""
        basic_result = calculate_general_checkout(1000, buyer_tier="basic", seller_tier="basic")
        premium_result = calculate_general_checkout(1000, buyer_tier="premium", seller_tier="premium")
        
        # Premium should have lower rates
        assert premium_result.buyer_premium_rate < basic_result.buyer_premium_rate
        assert premium_result.seller_commission_rate < basic_result.seller_commission_rate
        
        # Premium pays less in fees
        assert premium_result.buyer_premium < basic_result.buyer_premium


class TestVehicleCheckout:
    """Test vehicle auction checkout calculations"""
    
    def test_vehicle_10000(self):
        """Test vehicle checkout for $10,000"""
        result = calculate_vehicle_checkout(
            hammer_price=10000,
            buyer_tier="basic"
        )
        
        # Verify basic calculations
        assert result.hammer_price == Decimal("10000")
        assert result.is_vehicle is True
        
        # Buyer premium and platform fee
        assert result.buyer_premium == Decimal("500.00")  # 5%
        assert result.platform_fee == Decimal("250.00")   # 2.5%
        assert result.bidvex_fees_subtotal == Decimal("750.00")
        
        # No hammer tax for vehicles (paid offline)
        assert result.hammer_tax_total == Decimal("0")
        
        # Tax only on fees
        assert result.fees_tax_total > 0
        
        # Processing fee
        assert result.processing_fee > 0
    
    def test_vehicle_no_seller_commission(self):
        """Vehicles should not have seller commission"""
        result = calculate_vehicle_checkout(10000, buyer_tier="basic")
        
        assert result.seller_commission == Decimal("0")
        assert result.seller_commission_rate == Decimal("0")
    
    def test_vehicle_stripe_all_to_bidvex(self):
        """All Stripe charge goes to BidVex for vehicles"""
        result = calculate_vehicle_checkout(10000, buyer_tier="basic")
        
        # Application fee should equal total charge (all to BidVex)
        assert result.stripe_application_fee_cents == result.stripe_charge_amount_cents
        
        # No transfer to seller (hammer paid offline)
        assert result.stripe_transfer_amount_cents == 0
    
    def test_vehicle_seller_payout_equals_hammer(self):
        """Seller should receive full hammer price via Bank Draft"""
        result = calculate_vehicle_checkout(25000, buyer_tier="premium")
        
        assert result.seller_payout == Decimal("25000")


class TestTierCombinations:
    """Test various tier combinations"""
    
    def test_vip_buyer_basic_seller(self):
        """VIP buyer with basic seller"""
        result = calculate_general_checkout(
            hammer_price=5000,
            buyer_tier="vip",
            seller_tier="basic",
            seller_is_tax_registered=False
        )
        
        # VIP buyer premium is 3%
        assert result.buyer_premium_rate == Decimal("0.03")
        assert result.buyer_premium == Decimal("150.00")
        
        # Basic seller commission is 4%
        assert result.seller_commission_rate == Decimal("0.04")
        assert result.seller_commission == Decimal("200.00")
    
    def test_basic_buyer_vip_seller(self):
        """Basic buyer with VIP seller"""
        result = calculate_general_checkout(
            hammer_price=5000,
            buyer_tier="basic",
            seller_tier="vip",
            seller_is_tax_registered=True
        )
        
        # Basic buyer premium is 5%
        assert result.buyer_premium_rate == Decimal("0.05")
        
        # VIP seller commission is 2%
        assert result.seller_commission_rate == Decimal("0.02")


class TestEdgeCases:
    """Test edge cases"""
    
    def test_very_small_amount(self):
        """Test with $10 hammer price"""
        result = calculate_general_checkout(10, include_processing_fee=True)
        
        assert result.hammer_price == Decimal("10")
        assert result.buyer_total > 0
    
    def test_large_amount(self):
        """Test with $500,000 hammer price"""
        result = calculate_vehicle_checkout(500000, buyer_tier="vip")
        
        assert result.hammer_price == Decimal("500000")
        assert result.seller_payout == Decimal("500000")
    
    def test_no_processing_fee(self):
        """Test with processing fee disabled"""
        result = calculate_general_checkout(
            hammer_price=1000,
            include_processing_fee=False
        )
        
        assert result.processing_fee == Decimal("0")
    
    def test_to_dict_serialization(self):
        """Test that result can be serialized"""
        result = calculate_general_checkout(1000)
        
        data = result.to_dict()
        
        # All values should be JSON serializable (floats, not Decimals)
        assert isinstance(data["hammer_price"], float)
        assert isinstance(data["buyer_total"], float)
        assert isinstance(data["stripe_charge_amount_cents"], int)


class TestTaxCalculations:
    """Test tax calculation accuracy"""
    
    def test_gst_qst_rates(self):
        """Verify GST (5%) and QST (9.975%) rates"""
        result = calculate_general_checkout(
            hammer_price=1000,
            seller_is_tax_registered=True
        )
        
        # GST on hammer = 5% of $1000 = $50
        assert result.gst_on_hammer == Decimal("50.00")
        
        # QST on hammer = 9.975% of $1000 = $99.75
        assert result.qst_on_hammer == Decimal("99.75")
        
        # Total hammer tax = $149.75
        assert result.hammer_tax_total == Decimal("149.75")
    
    def test_fees_tax(self):
        """Verify tax on BidVex fees"""
        result = calculate_general_checkout(
            hammer_price=1000,
            buyer_tier="basic",
            seller_tier="basic",
            seller_is_tax_registered=False
        )
        
        # BidVex fees = $50 (premium) + $40 (commission) = $90
        assert result.bidvex_fees_subtotal == Decimal("90.00")
        
        # GST on fees = 5% of $90 = $4.50
        assert result.gst_on_fees == Decimal("4.50")
        
        # QST on fees = 9.975% of $90 = $8.98 (rounded)
        assert result.qst_on_fees == Decimal("8.98")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
