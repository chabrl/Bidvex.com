"""
Tests for the Hybrid Fee Calculation Engine
Tests both VEHICLE and GENERAL auction fee structures
"""

import pytest
from decimal import Decimal
from services.fee_calculation_engine import (
    calculate_fees,
    calculate_vehicle_fees,
    calculate_general_fees,
    get_fee_structure_summary,
    AuctionCategory,
    SubscriptionTier,
    BUYER_PREMIUM_RATES,
    SELLER_COMMISSION_RATES,
    VEHICLE_PLATFORM_FEE_RATE,
)


class TestVehicleFeeCalculation:
    """Test VEHICLE auction fee structure"""
    
    def test_vehicle_basic_tier_10000(self):
        """Test basic tier vehicle auction with $10,000 hammer price"""
        result = calculate_vehicle_fees(10000, buyer_tier="basic")
        
        assert result.category == "vehicle"
        assert result.hammer_price == 10000.0
        
        # Buyer pays: 10000 + (10000 * 0.05) + (10000 * 0.025) = 10750
        assert result.buyer_premium_rate == 0.05
        assert result.buyer_premium == 500.0
        assert result.platform_fee_rate == 0.025
        assert result.platform_fee == 250.0
        assert result.buyer_total == 10750.0
        assert result.buyer_total_cents == 1075000
        
        # Seller gets 100% of hammer price
        assert result.seller_commission_rate == 0.0
        assert result.seller_commission == 0.0
        assert result.seller_net_payout == 10000.0
        assert result.seller_net_payout_cents == 1000000
        
        # BidVex keeps premium + platform fee
        assert result.bidvex_revenue == 750.0
        assert result.bidvex_revenue_cents == 75000
        
        # Stripe parameters
        assert result.stripe_amount_cents == 1075000
        assert result.stripe_application_fee_cents == 75000
        assert result.stripe_transfer_amount_cents == 1000000
    
    def test_vehicle_premium_tier_25000(self):
        """Test premium tier vehicle auction with $25,000 hammer price"""
        result = calculate_vehicle_fees(25000, buyer_tier="premium")
        
        # Buyer pays: 25000 + (25000 * 0.035) + (25000 * 0.025) = 26500
        assert result.buyer_premium_rate == 0.035
        assert result.buyer_premium == 875.0
        assert result.platform_fee == 625.0
        assert result.buyer_total == 26500.0
        
        # Seller gets 100%
        assert result.seller_net_payout == 25000.0
        
        # BidVex revenue
        assert result.bidvex_revenue == 1500.0
    
    def test_vehicle_vip_tier_50000(self):
        """Test VIP tier vehicle auction with $50,000 hammer price"""
        result = calculate_vehicle_fees(50000, buyer_tier="vip")
        
        # Buyer pays: 50000 + (50000 * 0.03) + (50000 * 0.025) = 52750
        assert result.buyer_premium_rate == 0.03
        assert result.buyer_premium == 1500.0
        assert result.platform_fee == 1250.0
        assert result.buyer_total == 52750.0
        
        # Seller gets 100%
        assert result.seller_net_payout == 50000.0
        
        # BidVex revenue
        assert result.bidvex_revenue == 2750.0
    
    def test_vehicle_category_detection(self):
        """Test that vehicle-related categories are correctly detected"""
        # These should all be detected as vehicle auctions
        vehicle_categories = [
            "vehicle", "Vehicle", "VEHICLE",
            "car", "cars", "automobile",
            "truck", "SUV", "motorcycle",
            "Vehicle - Sedan", "Used Car"
        ]
        
        for category in vehicle_categories:
            result = calculate_fees(10000, category=category)
            assert result.category == "vehicle", f"Failed for category: {category}"
            assert result.platform_fee > 0, f"Vehicle should have platform fee: {category}"


class TestGeneralFeeCalculation:
    """Test GENERAL auction fee structure"""
    
    def test_general_basic_tier_10000(self):
        """Test basic tier general auction with $10,000 hammer price"""
        result = calculate_general_fees(10000, buyer_tier="basic", seller_tier="basic")
        
        assert result.category == "general"
        assert result.hammer_price == 10000.0
        
        # Buyer pays: 10000 + (10000 * 0.05) = 10500
        assert result.buyer_premium_rate == 0.05
        assert result.buyer_premium == 500.0
        assert result.platform_fee_rate == 0.0
        assert result.platform_fee == 0.0
        assert result.buyer_total == 10500.0
        assert result.buyer_total_cents == 1050000
        
        # Seller gets: 10000 - (10000 * 0.04) = 9600
        assert result.seller_commission_rate == 0.04
        assert result.seller_commission == 400.0
        assert result.seller_net_payout == 9600.0
        assert result.seller_net_payout_cents == 960000
        
        # BidVex keeps: 500 + 400 = 900
        assert result.bidvex_revenue == 900.0
        assert result.bidvex_revenue_cents == 90000
    
    def test_general_premium_tier_5000(self):
        """Test premium tier general auction with $5,000 hammer price"""
        result = calculate_general_fees(5000, buyer_tier="premium", seller_tier="premium")
        
        # Buyer pays: 5000 + (5000 * 0.035) = 5175
        assert result.buyer_premium_rate == 0.035
        assert result.buyer_premium == 175.0
        assert result.buyer_total == 5175.0
        
        # Seller gets: 5000 - (5000 * 0.025) = 4875
        assert result.seller_commission_rate == 0.025
        assert result.seller_commission == 125.0
        assert result.seller_net_payout == 4875.0
        
        # BidVex: 175 + 125 = 300
        assert result.bidvex_revenue == 300.0
    
    def test_general_vip_tier_20000(self):
        """Test VIP tier general auction with $20,000 hammer price"""
        result = calculate_general_fees(20000, buyer_tier="vip", seller_tier="vip")
        
        # Buyer pays: 20000 + (20000 * 0.03) = 20600
        assert result.buyer_premium_rate == 0.03
        assert result.buyer_premium == 600.0
        assert result.buyer_total == 20600.0
        
        # Seller gets: 20000 - (20000 * 0.02) = 19600
        assert result.seller_commission_rate == 0.02
        assert result.seller_commission == 400.0
        assert result.seller_net_payout == 19600.0
        
        # BidVex: 600 + 400 = 1000
        assert result.bidvex_revenue == 1000.0
    
    def test_mixed_tiers(self):
        """Test with different buyer and seller tiers"""
        # VIP buyer, Basic seller
        result = calculate_general_fees(10000, buyer_tier="vip", seller_tier="basic")
        
        assert result.buyer_premium_rate == 0.03  # VIP buyer rate
        assert result.seller_commission_rate == 0.04  # Basic seller rate
        
        assert result.buyer_premium == 300.0
        assert result.seller_commission == 400.0
        assert result.bidvex_revenue == 700.0


class TestStripeIntegration:
    """Test Stripe-related calculations"""
    
    def test_cents_conversion(self):
        """Test that all amounts are correctly converted to cents"""
        result = calculate_fees(99.99, category="general")
        
        # All cents values should be integers
        assert isinstance(result.hammer_price_cents, int)
        assert isinstance(result.buyer_premium_cents, int)
        assert isinstance(result.buyer_total_cents, int)
        assert isinstance(result.seller_net_payout_cents, int)
        assert isinstance(result.bidvex_revenue_cents, int)
        assert isinstance(result.stripe_amount_cents, int)
        assert isinstance(result.stripe_application_fee_cents, int)
        assert isinstance(result.stripe_transfer_amount_cents, int)
    
    def test_stripe_params_vehicle(self):
        """Test Stripe parameters for vehicle auction"""
        result = calculate_vehicle_fees(10000)
        
        # Amount charged to buyer = hammer + premium + platform fee
        assert result.stripe_amount_cents == 1075000
        
        # Application fee = BidVex revenue
        assert result.stripe_application_fee_cents == 75000
        
        # Transfer to seller = hammer price (100%)
        assert result.stripe_transfer_amount_cents == 1000000
        
        # Verify: amount - application_fee should equal transfer
        # Note: In Stripe Connect, the transfer is done separately
        # Application fee is taken from the amount charged
    
    def test_stripe_params_general(self):
        """Test Stripe parameters for general auction"""
        result = calculate_general_fees(10000)
        
        # Amount charged to buyer = hammer + premium
        assert result.stripe_amount_cents == 1050000
        
        # Application fee = buyer premium + seller commission
        assert result.stripe_application_fee_cents == 90000
        
        # Transfer to seller = hammer - commission
        assert result.stripe_transfer_amount_cents == 960000
    
    def test_rounding(self):
        """Test that decimal amounts are properly rounded"""
        # $333.33 should test rounding behavior
        result = calculate_fees(333.33, category="vehicle", buyer_tier="basic")
        
        # Verify amounts are properly rounded to 2 decimal places
        assert result.buyer_premium == 16.67  # 333.33 * 0.05 = 16.6665 -> 16.67
        assert result.platform_fee == 8.33  # 333.33 * 0.025 = 8.33325 -> 8.33


class TestFeeStructure:
    """Test fee structure constants and summary"""
    
    def test_buyer_premium_rates(self):
        """Test buyer premium rate constants"""
        assert BUYER_PREMIUM_RATES[SubscriptionTier.BASIC] == Decimal("0.05")
        assert BUYER_PREMIUM_RATES[SubscriptionTier.PREMIUM] == Decimal("0.035")
        assert BUYER_PREMIUM_RATES[SubscriptionTier.VIP_ELITE] == Decimal("0.03")
    
    def test_seller_commission_rates(self):
        """Test seller commission rate constants"""
        assert SELLER_COMMISSION_RATES[SubscriptionTier.BASIC] == Decimal("0.04")
        assert SELLER_COMMISSION_RATES[SubscriptionTier.PREMIUM] == Decimal("0.025")
        assert SELLER_COMMISSION_RATES[SubscriptionTier.VIP_ELITE] == Decimal("0.02")
    
    def test_vehicle_platform_fee(self):
        """Test vehicle platform fee constant"""
        assert VEHICLE_PLATFORM_FEE_RATE == Decimal("0.025")
    
    def test_fee_structure_summary(self):
        """Test fee structure summary endpoint"""
        summary = get_fee_structure_summary()
        
        assert "vehicle" in summary
        assert "general" in summary
        
        # Vehicle should have platform fee
        assert summary["vehicle"]["buyer_fees"]["platform_fee"] == "2.5%"
        assert summary["vehicle"]["seller_fees"]["commission"] == "0%"
        
        # General should have seller commission
        assert summary["general"]["buyer_fees"]["platform_fee"] == "0%"
        assert "basic" in summary["general"]["seller_fees"]["commission"]


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_small_amount(self):
        """Test with very small amount"""
        result = calculate_fees(1.00, category="general")
        
        assert result.buyer_premium == 0.05
        assert result.buyer_total == 1.05
        assert result.seller_commission == 0.04
        assert result.seller_net_payout == 0.96
    
    def test_large_amount(self):
        """Test with large amount (100k)"""
        result = calculate_vehicle_fees(100000)
        
        assert result.buyer_premium == 5000.0
        assert result.platform_fee == 2500.0
        assert result.buyer_total == 107500.0
        assert result.seller_net_payout == 100000.0
        assert result.bidvex_revenue == 7500.0
    
    def test_tier_normalization(self):
        """Test various tier string formats"""
        # All these should map to basic
        for tier in ["basic", "Basic", "BASIC", "standard", "free", ""]:
            result = calculate_fees(1000, category="general", buyer_tier=tier)
            assert result.buyer_premium_rate == 0.05
        
        # VIP variations
        for tier in ["vip", "VIP", "vip_elite", "elite"]:
            result = calculate_fees(1000, category="general", buyer_tier=tier)
            assert result.buyer_premium_rate == 0.03
    
    def test_category_normalization(self):
        """Test various category string formats"""
        # Vehicle categories
        for cat in ["vehicle", "Vehicle", "car", "automobile", "truck"]:
            result = calculate_fees(1000, category=cat)
            assert result.platform_fee > 0
        
        # General categories
        for cat in ["general", "electronics", "art", "collectibles", ""]:
            result = calculate_fees(1000, category=cat)
            assert result.platform_fee == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
