"""
Tests for the Quebec Tax & Compliance Engine
Tests both VEHICLE and GENERAL auction tax calculations

Quebec Tax Rates:
- GST (Federal): 5%
- QST (Provincial): 9.975%
- Combined: 14.975%
"""

import pytest
from decimal import Decimal
from services.tax_engine import (
    calculate_tax,
    calculate_vehicle_payment,
    calculate_general_payment,
    get_tax_structure_summary,
    SellerInfo,
    GST_RATE,
    QST_RATE,
    COMBINED_TAX_RATE,
    BIDVEX_GST_NUMBER,
    BIDVEX_QST_NUMBER,
)


class TestTaxCalculation:
    """Test basic tax calculations"""
    
    def test_tax_on_100_dollars(self):
        """Test tax calculation on $100"""
        result = calculate_tax(Decimal("100"))
        
        assert result.taxable_amount == 100.0
        assert result.gst_rate == 0.05
        assert result.gst_amount == 5.0
        assert result.qst_rate == 0.09975
        assert result.qst_amount == 9.98  # Rounded from 9.975
        assert result.total_tax == 14.98
        assert result.total_with_tax == 114.98
    
    def test_tax_on_1000_dollars(self):
        """Test tax calculation on $1,000"""
        result = calculate_tax(Decimal("1000"))
        
        assert result.gst_amount == 50.0
        assert result.qst_amount == 99.75
        assert result.total_tax == 149.75
        assert result.total_with_tax == 1149.75
    
    def test_tax_cents_conversion(self):
        """Test that cents values are integers"""
        result = calculate_tax(Decimal("99.99"))
        
        assert isinstance(result.taxable_amount_cents, int)
        assert isinstance(result.gst_amount_cents, int)
        assert isinstance(result.qst_amount_cents, int)
        assert isinstance(result.total_tax_cents, int)
        assert isinstance(result.total_with_tax_cents, int)
    
    def test_tax_on_small_amount(self):
        """Test tax on very small amount"""
        result = calculate_tax(Decimal("1.00"))
        
        assert result.gst_amount == 0.05
        assert result.qst_amount == 0.10
        assert result.total_tax == 0.15
        assert result.total_with_tax == 1.15


class TestVehiclePayment:
    """Test VEHICLE auction payment calculations"""
    
    def test_vehicle_basic_10000(self):
        """Test vehicle payment with $10,000 hammer price (basic tier)"""
        result = calculate_vehicle_payment(10000, buyer_tier="basic")
        
        # Input validation
        assert result.hammer_price == 10000.0
        assert result.category == "vehicle"
        assert result.buyer_tier == "basic"
        
        # BidVex fees
        assert result.buyer_premium_rate == 0.05  # 5%
        assert result.buyer_premium == 500.0
        assert result.platform_fee_rate == 0.025  # 2.5%
        assert result.platform_fee == 250.0
        assert result.bidvex_fees_subtotal == 750.0
        
        # Tax on fees (14.975% on $750)
        assert result.bidvex_fees_gst == 37.50
        assert result.bidvex_fees_qst == 74.81  # 750 * 0.09975 = 74.8125 -> 74.81
        assert result.bidvex_fees_tax_total == 112.31
        
        # Stripe charge (fees + tax only)
        assert result.stripe_charge_total == 862.31
        assert result.stripe_charge_total_cents == 86231
        
        # Balance due to seller (full hammer price)
        assert result.seller_balance_due == 10000.0
        assert result.seller_balance_due_cents == 1000000
    
    def test_vehicle_premium_25000(self):
        """Test vehicle payment with $25,000 hammer price (premium tier)"""
        result = calculate_vehicle_payment(25000, buyer_tier="premium")
        
        # Premium buyer gets 3.5% buyer premium
        assert result.buyer_premium_rate == 0.035
        assert result.buyer_premium == 875.0
        assert result.platform_fee == 625.0
        assert result.bidvex_fees_subtotal == 1500.0
        
        # Tax on $1500
        assert result.bidvex_fees_gst == 75.0
        assert result.bidvex_fees_qst == 149.63
        
        # Seller gets full $25,000 via bank draft
        assert result.seller_balance_due == 25000.0
    
    def test_vehicle_vip_50000(self):
        """Test vehicle payment with $50,000 hammer price (VIP tier)"""
        result = calculate_vehicle_payment(50000, buyer_tier="vip")
        
        # VIP buyer gets 3% buyer premium
        assert result.buyer_premium_rate == 0.03
        assert result.buyer_premium == 1500.0
        assert result.platform_fee == 1250.0  # 2.5%
        assert result.bidvex_fees_subtotal == 2750.0
        
        # Seller gets full $50,000
        assert result.seller_balance_due == 50000.0
    
    def test_vehicle_has_next_steps_message(self):
        """Test that vehicle payment includes next steps message"""
        result = calculate_vehicle_payment(10000)
        
        assert "Bank Draft" in result.next_steps_message
        assert "14 days" in result.next_steps_message
    
    def test_vehicle_invoice_lines(self):
        """Test vehicle payment generates correct invoice lines"""
        result = calculate_vehicle_payment(10000)
        
        assert len(result.invoice_lines) >= 4
        
        descriptions = [line["description"] for line in result.invoice_lines]
        assert "BidVex Buyer Premium" in descriptions
        assert "BidVex Platform Fee" in descriptions
        assert any("GST" in d for d in descriptions)
        assert any("QST" in d for d in descriptions)


class TestGeneralPaymentPrivateSeller:
    """Test GENERAL auction payments with PRIVATE seller (no hammer tax)"""
    
    def test_general_private_basic_1000(self):
        """Test general payment with $1,000 hammer price (private seller, basic tier)"""
        result = calculate_general_payment(1000, seller_is_business=False)
        
        # Basics
        assert result.hammer_price == 1000.0
        assert result.category == "general"
        assert result.seller_is_business is False
        
        # No tax on hammer price for private seller
        assert result.hammer_tax_applicable is False
        assert result.hammer_gst == 0.0
        assert result.hammer_qst == 0.0
        assert result.hammer_tax_total == 0.0
        
        # BidVex fees (buyer premium + seller commission = $90)
        assert result.buyer_premium_rate == 0.05
        assert result.buyer_premium == 50.0
        assert result.seller_commission == 40.0
        assert result.bidvex_fees_subtotal == 90.0
        
        # Tax on full BidVex fees ($90 * 5% = $4.50)
        assert result.bidvex_fees_gst == 4.50
        
        # Buyer total: $1000 + $50 (premium) + $7.49 (tax on premium) = $1057.49
        assert result.buyer_total == 1057.49
    
    def test_general_private_no_hammer_tax(self):
        """Verify private sellers don't trigger hammer price taxation"""
        result = calculate_general_payment(10000, seller_is_business=False)
        
        assert result.hammer_tax_applicable is False
        assert result.hammer_tax_total == 0.0
        assert result.buyer_pays_hammer_tax == 0.0


class TestGeneralPaymentBusinessSeller:
    """Test GENERAL auction payments with BUSINESS seller (hammer price taxed)"""
    
    def test_general_business_1000(self):
        """Test general payment with $1,000 hammer price (business seller)"""
        result = calculate_general_payment(1000, seller_is_business=True)
        
        # Hammer price IS taxed for business seller
        assert result.hammer_tax_applicable is True
        assert result.hammer_gst == 50.0  # 5% of $1000
        assert result.hammer_qst == 99.75  # 9.975% of $1000
        assert result.hammer_tax_total == 149.75
        
        # Buyer pays hammer + hammer tax + fees + fees tax
        assert result.buyer_pays_hammer == 1000.0
        assert result.buyer_pays_hammer_tax == 149.75
    
    def test_general_business_10000(self):
        """Test general payment with $10,000 hammer price (business seller)"""
        result = calculate_general_payment(10000, seller_is_business=True)
        
        # Hammer tax
        assert result.hammer_gst == 500.0
        assert result.hammer_qst == 997.50
        assert result.hammer_tax_total == 1497.50
    
    def test_general_business_seller_receives_tax(self):
        """Test that business seller receives the hammer price tax"""
        result = calculate_general_payment(1000, seller_is_business=True)
        
        # Seller receives hammer tax (collected on their behalf)
        assert result.seller_receives_hammer_tax == 149.75


class TestStripeParameters:
    """Test Stripe integration parameters"""
    
    def test_vehicle_stripe_params(self):
        """Test Stripe parameters for vehicle payment"""
        result = calculate_vehicle_payment(10000)
        
        # Only fees are charged via Stripe
        assert result.stripe_charge_total_cents == 86231  # $862.31
        # No transfer to seller (paid via bank draft)
    
    def test_general_private_stripe_params(self):
        """Test Stripe parameters for general payment (private seller)"""
        result = calculate_general_payment(1000, seller_is_business=False)
        
        # All integers for Stripe
        assert isinstance(result.stripe_amount_cents, int)
        assert isinstance(result.stripe_application_fee_cents, int)
        assert isinstance(result.stripe_transfer_amount_cents, int)
    
    def test_general_business_stripe_params(self):
        """Test Stripe parameters for general payment (business seller)"""
        result = calculate_general_payment(1000, seller_is_business=True)
        
        # Application fee should include BidVex fees + tax
        # Transfer should include seller payout + tax collected for seller
        assert result.stripe_amount_cents > 0
        assert result.stripe_application_fee_cents > 0
        assert result.stripe_transfer_amount_cents > 0


class TestMixedTiers:
    """Test different buyer/seller tier combinations"""
    
    def test_vip_buyer_basic_seller(self):
        """Test VIP buyer with basic seller"""
        result = calculate_general_payment(
            1000,
            buyer_tier="vip",
            seller_tier="basic",
            seller_is_business=False
        )
        
        assert result.buyer_premium_rate == 0.03  # VIP rate
        assert result.seller_commission_rate == 0.04  # Basic rate
    
    def test_basic_buyer_vip_seller(self):
        """Test basic buyer with VIP seller"""
        result = calculate_general_payment(
            1000,
            buyer_tier="basic",
            seller_tier="vip",
            seller_is_business=False
        )
        
        assert result.buyer_premium_rate == 0.05  # Basic rate
        assert result.seller_commission_rate == 0.02  # VIP rate
    
    def test_premium_both(self):
        """Test premium tier for both parties"""
        result = calculate_general_payment(
            5000,
            buyer_tier="premium",
            seller_tier="premium",
            seller_is_business=False
        )
        
        assert result.buyer_premium_rate == 0.035
        assert result.seller_commission_rate == 0.025


class TestTaxStructureSummary:
    """Test tax structure documentation"""
    
    def test_summary_contains_rates(self):
        """Test that summary includes tax rates"""
        summary = get_tax_structure_summary()
        
        assert "tax_rates" in summary
        assert "gst" in summary["tax_rates"]
        assert "qst" in summary["tax_rates"]
        assert "combined" in summary["tax_rates"]
    
    def test_summary_contains_vehicle_info(self):
        """Test that summary explains vehicle auction handling"""
        summary = get_tax_structure_summary()
        
        assert "vehicle_auctions" in summary
        assert "stripe_charges" in summary["vehicle_auctions"]
        assert "hammer_price" in summary["vehicle_auctions"]
    
    def test_summary_contains_general_info(self):
        """Test that summary explains general auction handling"""
        summary = get_tax_structure_summary()
        
        assert "general_auctions" in summary
        assert "private_seller" in summary["general_auctions"]
        assert "business_seller" in summary["general_auctions"]
    
    def test_summary_contains_bidvex_info(self):
        """Test that summary includes BidVex registration info"""
        summary = get_tax_structure_summary()
        
        assert "bidvex_info" in summary
        assert BIDVEX_GST_NUMBER in str(summary["bidvex_info"])
        assert BIDVEX_QST_NUMBER in str(summary["bidvex_info"])


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_very_small_amount(self):
        """Test with $1 hammer price"""
        result = calculate_vehicle_payment(1.00)
        
        assert result.hammer_price == 1.0
        assert result.bidvex_fees_subtotal == 0.08  # $0.05 + $0.03 (rounded)
    
    def test_large_amount(self):
        """Test with $500,000 hammer price"""
        result = calculate_vehicle_payment(500000)
        
        assert result.hammer_price == 500000.0
        assert result.seller_balance_due == 500000.0
        # BidVex fees: $25,000 (5%) + $12,500 (2.5%) = $37,500
        assert result.bidvex_fees_subtotal == 37500.0
    
    def test_tier_normalization(self):
        """Test various tier string formats"""
        for tier in ["basic", "Basic", "BASIC", "standard", "free", ""]:
            result = calculate_vehicle_payment(1000, buyer_tier=tier)
            assert result.buyer_premium_rate == 0.05
        
        for tier in ["vip", "VIP", "vip_elite", "elite"]:
            result = calculate_vehicle_payment(1000, buyer_tier=tier)
            assert result.buyer_premium_rate == 0.03
    
    def test_decimal_precision(self):
        """Test that decimal amounts don't have floating point errors"""
        # $333.33 tests rounding
        result = calculate_vehicle_payment(333.33)
        
        # All amounts should be rounded to 2 decimal places
        assert result.buyer_premium == round(333.33 * 0.05, 2)
        assert result.platform_fee == round(333.33 * 0.025, 2)


class TestSellerInfo:
    """Test SellerInfo dataclass"""
    
    def test_seller_info_with_numbers(self):
        """Test creating SellerInfo with tax numbers"""
        info = SellerInfo(
            seller_id="seller123",
            seller_name="Test Business",
            is_business=True,
            business_name="Test Business Inc.",
            gst_number="123456789RT0001",
            qst_number="1234567890TQ0001"
        )
        
        assert info.is_business is True
        assert info.gst_number == "123456789RT0001"
        assert info.qst_number == "1234567890TQ0001"
    
    def test_seller_info_private(self):
        """Test SellerInfo for private seller"""
        info = SellerInfo(
            seller_id="seller456",
            seller_name="John Doe",
            is_business=False
        )
        
        assert info.is_business is False
        assert info.gst_number is None
        assert info.qst_number is None


class TestInvoiceLines:
    """Test invoice line item generation"""
    
    def test_vehicle_invoice_lines_structure(self):
        """Test vehicle payment invoice lines have correct structure"""
        result = calculate_vehicle_payment(10000)
        
        for line in result.invoice_lines:
            assert "description" in line
            assert "amount" in line
    
    def test_general_invoice_lines_sections(self):
        """Test general payment invoice lines have section info"""
        result = calculate_general_payment(1000, seller_is_business=True)
        
        # Should have sections for Item Sale and Platform Service Fees
        sections = [line.get("section") for line in result.invoice_lines if "section" in line]
        assert "Item Sale" in sections
        assert "Platform Service Fees" in sections


class TestConstants:
    """Test tax constants"""
    
    def test_gst_rate(self):
        """Test GST rate is 5%"""
        assert GST_RATE == Decimal("0.05")
    
    def test_qst_rate(self):
        """Test QST rate is 9.975%"""
        assert QST_RATE == Decimal("0.09975")
    
    def test_combined_rate(self):
        """Test combined rate is 14.975%"""
        assert COMBINED_TAX_RATE == Decimal("0.14975")
    
    def test_bidvex_numbers(self):
        """Test BidVex tax registration numbers are defined"""
        assert BIDVEX_GST_NUMBER is not None
        assert BIDVEX_QST_NUMBER is not None
        assert "RT" in BIDVEX_GST_NUMBER  # GST format
        assert "TQ" in BIDVEX_QST_NUMBER  # QST format


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
