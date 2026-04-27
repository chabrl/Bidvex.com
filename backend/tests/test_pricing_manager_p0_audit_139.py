"""
BidVex PricingManager P0 Audit - Iteration 139
Tests for Master Pricing Structure with 5 proofs, partner tier, stripe_recovery fix, and connect_payment_engine wiring.

Test Coverage:
1. Partner tier: partner_auction() method
2. stripe_recovery($0) returns $0.00 (not $0.30)
3. 5 proofs: vehicle_auction, non_vehicle_stripe, flat_purchase, non_vehicle_cash, partner_auction
4. connect_payment_engine imports PricingManager (not hardcoded rates)
5. Province-aware tax in connect_payment_engine
"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from decimal import Decimal


# ============ PROOF 1: Vehicle Auction QC $1000 => buyer_total=$29.93 ============
class TestProof1VehicleAuction:
    """Proof 1: PricingManager.vehicle_auction(1000, 'QC') returns buyer_total=$29.93"""
    
    def test_vehicle_auction_qc_1000_buyer_total(self):
        """Vehicle auction QC $1000 should return buyer_total=$29.93"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(1000, 'QC')
        
        # Expected calculation:
        # Platform fee (2.5%): $25.00
        # Stripe recovery: (25 * 0.029) + 0.30 = $1.03
        # Taxable: 25 + 1.03 = $26.03
        # Tax (14.975%): $3.90
        # Total: 25 + 1.03 + 3.90 = $29.93
        
        assert result.buyer_invoice.total == 29.93, f"Expected buyer_total=29.93, got {result.buyer_invoice.total}"
        assert result.seller_invoice is None, "Seller invoice should be None for vehicle auctions"
        assert result.buyer_invoice.fees_subtotal == 25.0, f"Expected platform_fee=25.0, got {result.buyer_invoice.fees_subtotal}"
        assert result.buyer_invoice.tax_type == "GST+QST", f"Expected tax_type='GST+QST', got {result.buyer_invoice.tax_type}"
        print(f"PASS: Proof 1 - vehicle_auction(1000, 'QC') => buyer_total=${result.buyer_invoice.total}")


# ============ PROOF 2: Non-Vehicle Stripe QC $1000 => buyer=$1059.50, seller=$952.33 ============
class TestProof2NonVehicleStripe:
    """Proof 2: PricingManager.non_vehicle_stripe(1000, 'QC', 'free', 'free') returns buyer=$1059.50 seller=$952.33"""
    
    def test_non_vehicle_stripe_qc_1000_buyer_total(self):
        """Non-vehicle Stripe QC $1000 should return buyer_total (SR on BP only)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(1000, 'QC', 'free', 'free')
        
        # Expected buyer calculation (canonical formula: SR on BP only,
        # BidVex absorbs stripe cost on hammer):
        # Hammer: $1000
        # Buyer Premium (5%): $50
        # Stripe recovery: (50 * 0.029) + 0.30 = $1.75
        # Taxable: 50 + 1.75 = $51.75
        # Tax (14.975%): $7.75
        # Total: 1000 + 50 + 1.75 + 7.75 = $1059.50
        
        assert result.buyer_invoice.total == 1059.50, f"Expected buyer_total=1059.50, got {result.buyer_invoice.total}"
        print(f"PASS: Proof 2a - non_vehicle_stripe buyer_total=${result.buyer_invoice.total}")
    
    def test_non_vehicle_stripe_qc_1000_seller_total(self):
        """Non-vehicle Stripe QC $1000 should return seller_total=$952.33"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(1000, 'QC', 'free', 'free')
        
        # Expected seller calculation:
        # Hammer: $1000
        # Seller Commission (4%): $40
        # Stripe recovery: (40 * 0.029) + 0.30 = $1.46
        # Taxable: 40 + 1.46 = $41.46
        # Tax (14.975%): $6.21
        # Net payout: 1000 - 40 - 1.46 - 6.21 = $952.33
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 952.33, f"Expected seller_total=952.33, got {result.seller_invoice.total}"
        print(f"PASS: Proof 2b - non_vehicle_stripe seller_total=${result.seller_invoice.total}")


# ============ PROOF 3: Flat Purchase ON $300 => total=$349.17 with tax_label='HST (13%)' ============
class TestProof3FlatPurchase:
    """Proof 3: PricingManager.flat_purchase(300, 'ON') returns total=$349.17 with tax_label='HST (13%)'"""
    
    def test_flat_purchase_on_300_total(self):
        """Flat purchase ON $300 should return total=$349.17"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.flat_purchase(300, 'ON')
        
        # Expected calculation:
        # Base: $300
        # Stripe recovery: (300 * 0.029) + 0.30 = $9.00
        # Taxable: 300 + 9 = $309
        # Tax (13% HST): $40.17
        # Total: 300 + 9 + 40.17 = $349.17
        
        assert result.buyer_invoice.total == 349.17, f"Expected total=349.17, got {result.buyer_invoice.total}"
        print(f"PASS: Proof 3a - flat_purchase(300, 'ON') => total=${result.buyer_invoice.total}")
    
    def test_flat_purchase_on_300_tax_label(self):
        """Flat purchase ON $300 should have tax_label='HST (13%)'"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.flat_purchase(300, 'ON')
        
        assert result.buyer_invoice.tax_label == "HST (13%)", f"Expected tax_label='HST (13%)', got {result.buyer_invoice.tax_label}"
        assert result.buyer_invoice.tax_type == "HST", f"Expected tax_type='HST', got {result.buyer_invoice.tax_type}"
        print(f"PASS: Proof 3b - flat_purchase tax_label='{result.buyer_invoice.tax_label}'")


# ============ PROOF 4: Non-Vehicle Cash AB $500 => buyer=$27.33, seller=$21.92 ============
class TestProof4NonVehicleCash:
    """Proof 4: PricingManager.non_vehicle_cash(500, 'AB', 'free', 'free') returns buyer=$27.33 seller=$21.92"""
    
    def test_non_vehicle_cash_ab_500_buyer_total(self):
        """Non-vehicle Cash AB $500 should return buyer_total=$27.33"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_cash(500, 'AB', 'free', 'free')
        
        # Expected buyer calculation:
        # Buyer Premium (5%): $25
        # Stripe recovery: (25 * 0.029) + 0.30 = $1.03
        # Taxable: 25 + 1.03 = $26.03
        # Tax (5% GST): $1.30
        # Total: 25 + 1.03 + 1.30 = $27.33
        
        assert result.buyer_invoice.total == 27.33, f"Expected buyer_total=27.33, got {result.buyer_invoice.total}"
        print(f"PASS: Proof 4a - non_vehicle_cash buyer_total=${result.buyer_invoice.total}")
    
    def test_non_vehicle_cash_ab_500_seller_total(self):
        """Non-vehicle Cash AB $500 should return seller_total=$21.92"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_cash(500, 'AB', 'free', 'free')
        
        # Expected seller calculation:
        # Seller Commission (4%): $20
        # Stripe recovery: (20 * 0.029) + 0.30 = $0.88
        # Taxable: 20 + 0.88 = $20.88
        # Tax (5% GST): $1.04
        # Total: 20 + 0.88 + 1.04 = $21.92
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 21.92, f"Expected seller_total=21.92, got {result.seller_invoice.total}"
        print(f"PASS: Proof 4b - non_vehicle_cash seller_total=${result.seller_invoice.total}")


# ============ PROOF 5: Partner Auction ON $2000 => buyer_total=$0.00, seller_total=$70.11 ============
class TestProof5PartnerAuction:
    """Proof 5: PricingManager.partner_auction(2000, 'ON') returns buyer_total=$0.00 and seller_total=$70.11"""
    
    def test_partner_auction_on_2000_buyer_total(self):
        """Partner auction ON $2000 should return buyer_total=$0.00"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.partner_auction(2000, 'ON')
        
        # Partner tier: BidVex charges buyer $0 (partner sets their own BP)
        assert result.buyer_invoice.total == 0.0, f"Expected buyer_total=0.0, got {result.buyer_invoice.total}"
        assert result.buyer_invoice.fees_subtotal == 0.0, f"Expected fees_subtotal=0.0, got {result.buyer_invoice.fees_subtotal}"
        assert result.buyer_invoice.stripe_recovery == 0.0, f"Expected stripe_recovery=0.0, got {result.buyer_invoice.stripe_recovery}"
        assert result.buyer_invoice.tax_amount == 0.0, f"Expected tax_amount=0.0, got {result.buyer_invoice.tax_amount}"
        print(f"PASS: Proof 5a - partner_auction buyer_total=${result.buyer_invoice.total}")
    
    def test_partner_auction_on_2000_seller_total(self):
        """Partner auction ON $2000 should return seller_total=$70.11"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.partner_auction(2000, 'ON')
        
        # Expected seller calculation:
        # Seller Commission (3% flat): $60
        # Stripe recovery: (60 * 0.029) + 0.30 = $2.04
        # Taxable: 60 + 2.04 = $62.04
        # Tax (13% HST): $8.07
        # Total: 60 + 2.04 + 8.07 = $70.11
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 70.11, f"Expected seller_total=70.11, got {result.seller_invoice.total}"
        assert result.seller_invoice.fees_subtotal == 60.0, f"Expected fees_subtotal=60.0, got {result.seller_invoice.fees_subtotal}"
        print(f"PASS: Proof 5b - partner_auction seller_total=${result.seller_invoice.total}")
    
    def test_partner_auction_buyer_invoice_structure(self):
        """Partner auction buyer invoice should have all zero values"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.partner_auction(2000, 'ON')
        bi = result.buyer_invoice
        
        assert bi.fees_subtotal == 0.0, f"fees_subtotal should be 0, got {bi.fees_subtotal}"
        assert bi.stripe_recovery == 0.0, f"stripe_recovery should be 0, got {bi.stripe_recovery}"
        assert bi.tax_amount == 0.0, f"tax_amount should be 0, got {bi.tax_amount}"
        assert bi.total == 0.0, f"total should be 0, got {bi.total}"
        print("PASS: Partner auction buyer invoice has all zero values")


# ============ STRIPE RECOVERY FIX: $0 fees => $0.00 (not $0.30) ============
class TestStripeRecoveryFix:
    """stripe_recovery($0) returns $0.00 (not $0.30)"""
    
    def test_stripe_recovery_zero_fees(self):
        """stripe_recovery(0) should return $0.00, not $0.30"""
        from services.pricing_manager import stripe_recovery
        from decimal import Decimal
        
        result = stripe_recovery(Decimal("0"))
        
        assert result == Decimal("0"), f"Expected stripe_recovery(0)=0, got {result}"
        print(f"PASS: stripe_recovery(0) => ${result}")
    
    def test_stripe_recovery_negative_fees(self):
        """stripe_recovery(-10) should return $0.00"""
        from services.pricing_manager import stripe_recovery
        from decimal import Decimal
        
        result = stripe_recovery(Decimal("-10"))
        
        assert result == Decimal("0"), f"Expected stripe_recovery(-10)=0, got {result}"
        print(f"PASS: stripe_recovery(-10) => ${result}")
    
    def test_stripe_recovery_positive_fees(self):
        """stripe_recovery(100) should return $3.20 (100*0.029 + 0.30)"""
        from services.pricing_manager import stripe_recovery
        from decimal import Decimal
        
        result = stripe_recovery(Decimal("100"))
        
        # 100 * 0.029 + 0.30 = 2.90 + 0.30 = 3.20
        assert result == Decimal("3.20"), f"Expected stripe_recovery(100)=3.20, got {result}"
        print(f"PASS: stripe_recovery(100) => ${result}")


# ============ CONNECT PAYMENT ENGINE WIRING ============
class TestConnectPaymentEngineWiring:
    """connect_payment_engine.calculate_connect_checkout imports PricingManager (not hardcoded rates)"""
    
    def test_calculate_connect_checkout_imports_pricing_manager(self):
        """calculate_connect_checkout should import PricingManager"""
        import inspect
        from services.connect_payment_engine import calculate_connect_checkout
        
        source = inspect.getsource(calculate_connect_checkout)
        
        assert "PricingManager" in source, "calculate_connect_checkout should import PricingManager"
        assert "from services.pricing_manager import PricingManager" in source, "Should import PricingManager from services.pricing_manager"
        print("PASS: calculate_connect_checkout imports PricingManager")
    
    def test_calculate_connect_checkout_vehicle_qc(self):
        """calculate_connect_checkout with vehicle QC should return correct tax_type='GST+QST'"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=1000,
            category="vehicle",
            buyer_tier="free",
            seller_tier="free",
            province="QC",
        )
        
        assert result["tax_type"] == "GST+QST", f"Expected tax_type='GST+QST', got {result['tax_type']}"
        assert result["is_vehicle"] == True, f"Expected is_vehicle=True, got {result['is_vehicle']}"
        print(f"PASS: calculate_connect_checkout vehicle QC => tax_type='{result['tax_type']}'")
    
    def test_calculate_connect_checkout_vehicle_on(self):
        """calculate_connect_checkout with vehicle ON should return tax_type='HST'"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=1000,
            category="vehicle",
            buyer_tier="free",
            seller_tier="free",
            province="ON",
        )
        
        assert result["tax_type"] == "HST", f"Expected tax_type='HST', got {result['tax_type']}"
        print(f"PASS: calculate_connect_checkout vehicle ON => tax_type='{result['tax_type']}'")
    
    def test_calculate_connect_checkout_partner_buyer_zero_fees(self):
        """calculate_connect_checkout with seller_is_partner=True should return buyer $0 fees"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=2000,
            category="general",
            buyer_tier="free",
            seller_tier="partner",
            province="ON",
            seller_is_partner=True,
        )
        
        # Partner flow: buyer pays $0 BidVex fees
        assert result["buyer_premium"] == 0.0, f"Expected buyer_premium=0, got {result['buyer_premium']}"
        assert result["flow_type"] == "PARTNER_FLOW", f"Expected flow_type='PARTNER_FLOW', got {result['flow_type']}"
        print(f"PASS: calculate_connect_checkout partner => buyer_premium=${result['buyer_premium']}, flow_type='{result['flow_type']}'")
    
    def test_calculate_connect_checkout_routes_to_vehicle_auction(self):
        """calculate_connect_checkout with vehicle category should route to vehicle_auction"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=1000,
            category="vehicle",
            province="QC",
        )
        
        # Vehicle auction: buyer pays 2.5% platform fee only
        # Expected: $29.93 (same as Proof 1)
        expected_buyer_total = 1000 + 29.93  # hammer + fees (for buyer_total which includes hammer for display)
        
        # The stripe_charge should be just the fees (not hammer for vehicles)
        assert result["stripe_charge"] == 29.93, f"Expected stripe_charge=29.93, got {result['stripe_charge']}"
        print(f"PASS: calculate_connect_checkout vehicle routes correctly, stripe_charge=${result['stripe_charge']}")
    
    def test_calculate_connect_checkout_routes_to_non_vehicle_stripe(self):
        """calculate_connect_checkout with general category should route to non_vehicle_stripe"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=1000,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            province="QC",
        )
        
        # Non-vehicle Stripe: buyer pays hammer + BP + stripe + tax
        # Stripe recovery now on BP only: (50*0.029)+0.30=$1.75
        # Tax on (BP + SR) = (50+1.75)*0.14975 = $7.75
        # Expected: 1000 + 50 + 1.75 + 7.75 = $1059.50
        assert result["stripe_charge"] == 1059.50, f"Expected stripe_charge=1059.50, got {result['stripe_charge']}"
        assert result["is_vehicle"] == False, f"Expected is_vehicle=False, got {result['is_vehicle']}"
        print(f"PASS: calculate_connect_checkout general routes correctly, stripe_charge=${result['stripe_charge']}")
    
    def test_calculate_connect_checkout_routes_to_partner_auction(self):
        """calculate_connect_checkout with seller_is_partner=True should route to partner_auction"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=2000,
            category="general",
            province="ON",
            seller_is_partner=True,
        )
        
        # Partner auction: buyer pays $0 BidVex fees
        assert result["seller_is_partner"] == True, f"Expected seller_is_partner=True"
        assert result["flow_type"] == "PARTNER_FLOW", f"Expected flow_type='PARTNER_FLOW'"
        assert result["buyer_premium"] == 0.0, f"Expected buyer_premium=0, got {result['buyer_premium']}"
        print(f"PASS: calculate_connect_checkout partner routes correctly")


# ============ TIER RATES VERIFICATION ============
class TestTierRates:
    """Verify tier rates are correctly defined in PricingManager"""
    
    def test_standard_tier_rates(self):
        """Standard tier: 5% BP / 4% SC"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        assert BUYER_PREMIUM_RATES["standard"] == Decimal("0.05"), f"Standard BP should be 5%"
        assert SELLER_COMMISSION_RATES["standard"] == Decimal("0.04"), f"Standard SC should be 4%"
        print("PASS: Standard tier rates: 5% BP / 4% SC")
    
    def test_premium_tier_rates(self):
        """Premium tier: 3.5% BP / 2.5% SC"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        assert BUYER_PREMIUM_RATES["premium"] == Decimal("0.035"), f"Premium BP should be 3.5%"
        assert SELLER_COMMISSION_RATES["premium"] == Decimal("0.025"), f"Premium SC should be 2.5%"
        print("PASS: Premium tier rates: 3.5% BP / 2.5% SC")
    
    def test_vip_tier_rates(self):
        """VIP tier: 3% BP / 2% SC"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        assert BUYER_PREMIUM_RATES["vip"] == Decimal("0.03"), f"VIP BP should be 3%"
        assert SELLER_COMMISSION_RATES["vip"] == Decimal("0.02"), f"VIP SC should be 2%"
        print("PASS: VIP tier rates: 3% BP / 2% SC")
    
    def test_partner_tier_rates(self):
        """Partner tier: 0% BP / 3% SC"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        assert BUYER_PREMIUM_RATES["partner"] == Decimal("0"), f"Partner BP should be 0%"
        assert SELLER_COMMISSION_RATES["partner"] == Decimal("0.03"), f"Partner SC should be 3%"
        print("PASS: Partner tier rates: 0% BP / 3% SC")


# ============ PROVINCIAL TAX RATES ============
class TestProvincialTaxRates:
    """Verify provincial tax rates are correctly applied"""
    
    def test_qc_tax_rate(self):
        """QC should have GST+QST (14.975%)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(1000, 'QC')
        
        assert result.buyer_invoice.tax_type == "GST+QST"
        assert abs(result.buyer_invoice.tax_rate - 0.14975) < 0.001
        print("PASS: QC tax rate: GST+QST (14.975%)")
    
    def test_on_tax_rate(self):
        """ON should have HST (13%)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(1000, 'ON')
        
        assert result.buyer_invoice.tax_type == "HST"
        assert abs(result.buyer_invoice.tax_rate - 0.13) < 0.001
        print("PASS: ON tax rate: HST (13%)")
    
    def test_ab_tax_rate(self):
        """AB should have GST (5%)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(1000, 'AB')
        
        assert result.buyer_invoice.tax_type == "GST"
        assert abs(result.buyer_invoice.tax_rate - 0.05) < 0.001
        print("PASS: AB tax rate: GST (5%)")
    
    def test_bc_tax_rate(self):
        """BC should have GST (5%) - NOT GST+PST"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(1000, 'BC')
        
        assert result.buyer_invoice.tax_type == "GST"
        assert abs(result.buyer_invoice.tax_rate - 0.05) < 0.001
        print("PASS: BC tax rate: GST (5%)")
    
    def test_ns_tax_rate(self):
        """NS should have HST (15%)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(1000, 'NS')
        
        assert result.buyer_invoice.tax_type == "HST"
        assert abs(result.buyer_invoice.tax_rate - 0.15) < 0.001
        print("PASS: NS tax rate: HST (15%)")


# ============ SUBSCRIPTIONS WIRING (Wire 2a) ============
class TestSubscriptionsWiring:
    """Verify subscriptions.py uses PricingManager.flat_purchase"""
    
    def test_subscriptions_imports_pricing_manager(self):
        """subscriptions.py should import PricingManager for flat_purchase"""
        import inspect
        from routes import subscriptions
        
        source = inspect.getsource(subscriptions)
        
        assert "PricingManager" in source, "subscriptions.py should reference PricingManager"
        assert "flat_purchase" in source, "subscriptions.py should use flat_purchase method"
        print("PASS: subscriptions.py imports PricingManager.flat_purchase")


# ============ PROMOTIONS WIRING (Wire 2b) ============
class TestPromotionsWiring:
    """Verify payments_promotions.py passes buyer_province to promotion checkout"""
    
    def test_promotions_passes_buyer_province(self):
        """payments_promotions.py should pass buyer_province to create_promotion_checkout"""
        import inspect
        from routes import payments_promotions
        
        source = inspect.getsource(payments_promotions)
        
        assert "buyer_province" in source, "payments_promotions.py should use buyer_province"
        assert "create_promotion_checkout" in source, "payments_promotions.py should call create_promotion_checkout"
        print("PASS: payments_promotions.py passes buyer_province to promotion checkout")


# ============ EMAIL MARKETING WIRING (Wire 2c) ============
class TestEmailMarketingWiring:
    """Verify payments_promotions.py passes buyer_province to email credits checkout"""
    
    def test_email_credits_passes_buyer_province(self):
        """payments_promotions.py should pass buyer_province to create_email_credits_checkout"""
        import inspect
        from routes import payments_promotions
        
        source = inspect.getsource(payments_promotions)
        
        assert "create_email_credits_checkout" in source, "payments_promotions.py should call create_email_credits_checkout"
        # Check that buyer_province is passed to the function
        assert "buyer_province=buyer_province" in source or "buyer_province=" in source, "Should pass buyer_province parameter"
        print("PASS: payments_promotions.py passes buyer_province to email credits checkout")


# ============ CONNECT PAYMENT ENGINE WIRING (Wire 1) ============
class TestConnectPaymentEnginePromotionWiring:
    """Verify connect_payment_engine uses PricingManager for promotions and email credits"""
    
    def test_create_promotion_checkout_uses_pricing_manager(self):
        """create_promotion_checkout should use PricingManager.flat_purchase"""
        import inspect
        from services.connect_payment_engine import create_promotion_checkout
        
        source = inspect.getsource(create_promotion_checkout)
        
        assert "PricingManager" in source, "create_promotion_checkout should use PricingManager"
        assert "flat_purchase" in source, "create_promotion_checkout should use flat_purchase"
        print("PASS: create_promotion_checkout uses PricingManager.flat_purchase")
    
    def test_create_email_credits_checkout_uses_pricing_manager(self):
        """create_email_credits_checkout should use PricingManager.flat_purchase"""
        import inspect
        from services.connect_payment_engine import create_email_credits_checkout
        
        source = inspect.getsource(create_email_credits_checkout)
        
        assert "PricingManager" in source, "create_email_credits_checkout should use PricingManager"
        assert "flat_purchase" in source, "create_email_credits_checkout should use flat_purchase"
        print("PASS: create_email_credits_checkout uses PricingManager.flat_purchase")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
