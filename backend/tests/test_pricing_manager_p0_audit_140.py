"""
BidVex PricingManager P0 Audit - Iteration 140
Tests for Seller Commission Tier Audit + Full Pricing Validation

Test Coverage:
1. SELLER_COMMISSION_RATES dict verification (free=0.04, standard=0.04, premium=0.025, vip=0.02, vip_elite=0.02, partner=0.03)
2. 4 new proofs (A-D) for $50 table sold in Ontario:
   - A(Standard): buyer=$54.88, seller=$47.33
   - B(Premium): buyer=$54.01, seller=$48.20
   - C(VIP): buyer=$53.72, seller=$48.50
   - D(Partner): buyer=$0, seller=$2.08
3. non_vehicle_stripe buyer stripe_recovery on (hammer+BP) = $1.82 for $50 ON Standard
4. non_vehicle_cash buyer stripe_recovery still on BP only (not hammer+BP)
5. Existing proofs unchanged: vehicle_auction, flat_purchase, non_vehicle_cash, partner_auction
"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from decimal import Decimal


# ============ SELLER_COMMISSION_RATES DICT VERIFICATION ============
class TestSellerCommissionRatesDict:
    """Verify SELLER_COMMISSION_RATES dict has correct keys and values"""
    
    def test_seller_commission_rates_free(self):
        """free tier should have 4% seller commission"""
        from services.pricing_manager import SELLER_COMMISSION_RATES
        
        assert "free" in SELLER_COMMISSION_RATES, "free key should exist"
        assert SELLER_COMMISSION_RATES["free"] == Decimal("0.04"), f"free SC should be 4%, got {SELLER_COMMISSION_RATES['free']}"
        print("PASS: SELLER_COMMISSION_RATES['free'] = 0.04 (4%)")
    
    def test_seller_commission_rates_standard(self):
        """standard tier should have 4% seller commission"""
        from services.pricing_manager import SELLER_COMMISSION_RATES
        
        assert "standard" in SELLER_COMMISSION_RATES, "standard key should exist"
        assert SELLER_COMMISSION_RATES["standard"] == Decimal("0.04"), f"standard SC should be 4%, got {SELLER_COMMISSION_RATES['standard']}"
        print("PASS: SELLER_COMMISSION_RATES['standard'] = 0.04 (4%)")
    
    def test_seller_commission_rates_premium(self):
        """premium tier should have 2.5% seller commission"""
        from services.pricing_manager import SELLER_COMMISSION_RATES
        
        assert "premium" in SELLER_COMMISSION_RATES, "premium key should exist"
        assert SELLER_COMMISSION_RATES["premium"] == Decimal("0.025"), f"premium SC should be 2.5%, got {SELLER_COMMISSION_RATES['premium']}"
        print("PASS: SELLER_COMMISSION_RATES['premium'] = 0.025 (2.5%)")
    
    def test_seller_commission_rates_vip(self):
        """vip tier should have 2% seller commission"""
        from services.pricing_manager import SELLER_COMMISSION_RATES
        
        assert "vip" in SELLER_COMMISSION_RATES, "vip key should exist"
        assert SELLER_COMMISSION_RATES["vip"] == Decimal("0.02"), f"vip SC should be 2%, got {SELLER_COMMISSION_RATES['vip']}"
        print("PASS: SELLER_COMMISSION_RATES['vip'] = 0.02 (2%)")
    
    def test_seller_commission_rates_vip_elite(self):
        """vip_elite tier should have 2% seller commission"""
        from services.pricing_manager import SELLER_COMMISSION_RATES
        
        assert "vip_elite" in SELLER_COMMISSION_RATES, "vip_elite key should exist"
        assert SELLER_COMMISSION_RATES["vip_elite"] == Decimal("0.02"), f"vip_elite SC should be 2%, got {SELLER_COMMISSION_RATES['vip_elite']}"
        print("PASS: SELLER_COMMISSION_RATES['vip_elite'] = 0.02 (2%)")
    
    def test_seller_commission_rates_partner(self):
        """partner tier should have 3% seller commission"""
        from services.pricing_manager import SELLER_COMMISSION_RATES
        
        assert "partner" in SELLER_COMMISSION_RATES, "partner key should exist"
        assert SELLER_COMMISSION_RATES["partner"] == Decimal("0.03"), f"partner SC should be 3%, got {SELLER_COMMISSION_RATES['partner']}"
        print("PASS: SELLER_COMMISSION_RATES['partner'] = 0.03 (3%)")


# ============ PROOF A: $50 ON Standard => buyer=$54.88, seller=$47.33 ============
class TestProofA_Standard:
    """Proof A: PricingManager.non_vehicle_stripe(50, 'ON', 'free', 'free') returns buyer=$54.88 seller=$47.33"""
    
    def test_proof_a_buyer_total(self):
        """$50 ON Standard buyer_total should be $54.88"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'free', 'free')
        
        # Expected buyer calculation:
        # Hammer: $50
        # Buyer Premium (5%): $2.50
        # Stripe recovery on (hammer+BP): (52.50 * 0.029) + 0.30 = $1.82
        # Taxable: 2.50 + 1.82 = $4.32
        # Tax (13% HST): $0.56
        # Total: 50 + 2.50 + 1.82 + 0.56 = $54.88
        
        assert result.buyer_invoice.total == 54.88, f"Expected buyer_total=54.88, got {result.buyer_invoice.total}"
        print(f"PASS: Proof A - non_vehicle_stripe(50, 'ON', 'free', 'free') => buyer_total=${result.buyer_invoice.total}")
    
    def test_proof_a_seller_payout(self):
        """$50 ON Standard seller_payout should be $47.33"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'free', 'free')
        
        # Expected seller calculation:
        # Hammer: $50
        # Seller Commission (4%): $2.00
        # Stripe recovery on SC: (2.00 * 0.029) + 0.30 = $0.36
        # Taxable: 2.00 + 0.36 = $2.36
        # Tax (13% HST): $0.31
        # Net payout: 50 - 2.00 - 0.36 - 0.31 = $47.33
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 47.33, f"Expected seller_payout=47.33, got {result.seller_invoice.total}"
        print(f"PASS: Proof A - non_vehicle_stripe(50, 'ON', 'free', 'free') => seller_payout=${result.seller_invoice.total}")
    
    def test_proof_a_stripe_recovery_on_hammer_plus_bp(self):
        """$50 ON Standard buyer stripe_recovery should be $1.82 (on hammer+BP=$52.50)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'free', 'free')
        
        # Stripe recovery on (hammer+BP): (52.50 * 0.029) + 0.30 = 1.5225 + 0.30 = 1.8225 => $1.82
        assert result.buyer_invoice.stripe_recovery == 1.82, f"Expected buyer stripe_recovery=1.82, got {result.buyer_invoice.stripe_recovery}"
        print(f"PASS: Proof A - buyer stripe_recovery=${result.buyer_invoice.stripe_recovery} (on hammer+BP=$52.50)")


# ============ PROOF B: $50 ON Premium => buyer=$54.01, seller=$48.20 ============
class TestProofB_Premium:
    """Proof B: PricingManager.non_vehicle_stripe(50, 'ON', 'premium', 'premium') returns buyer=$54.01 seller=$48.20"""
    
    def test_proof_b_buyer_total(self):
        """$50 ON Premium buyer_total should be $54.01"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'premium', 'premium')
        
        # Expected buyer calculation:
        # Hammer: $50
        # Buyer Premium (3.5%): $1.75
        # Stripe recovery on (hammer+BP): (51.75 * 0.029) + 0.30 = $1.80
        # Taxable: 1.75 + 1.80 = $3.55
        # Tax (13% HST): $0.46
        # Total: 50 + 1.75 + 1.80 + 0.46 = $54.01
        
        assert result.buyer_invoice.total == 54.01, f"Expected buyer_total=54.01, got {result.buyer_invoice.total}"
        print(f"PASS: Proof B - non_vehicle_stripe(50, 'ON', 'premium', 'premium') => buyer_total=${result.buyer_invoice.total}")
    
    def test_proof_b_seller_payout(self):
        """$50 ON Premium seller_payout should be $48.20"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'premium', 'premium')
        
        # Expected seller calculation:
        # Hammer: $50
        # Seller Commission (2.5%): $1.25
        # Stripe recovery on SC: (1.25 * 0.029) + 0.30 = $0.34
        # Taxable: 1.25 + 0.34 = $1.59
        # Tax (13% HST): $0.21
        # Net payout: 50 - 1.25 - 0.34 - 0.21 = $48.20
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 48.20, f"Expected seller_payout=48.20, got {result.seller_invoice.total}"
        print(f"PASS: Proof B - non_vehicle_stripe(50, 'ON', 'premium', 'premium') => seller_payout=${result.seller_invoice.total}")


# ============ PROOF C: $50 ON VIP => buyer=$53.72, seller=$48.50 ============
class TestProofC_VIP:
    """Proof C: PricingManager.non_vehicle_stripe(50, 'ON', 'vip', 'vip') returns buyer=$53.72 seller=$48.50"""
    
    def test_proof_c_buyer_total(self):
        """$50 ON VIP buyer_total should be $53.72"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'vip', 'vip')
        
        # Expected buyer calculation:
        # Hammer: $50
        # Buyer Premium (3%): $1.50
        # Stripe recovery on (hammer+BP): (51.50 * 0.029) + 0.30 = $1.79
        # Taxable: 1.50 + 1.79 = $3.29
        # Tax (13% HST): $0.43
        # Total: 50 + 1.50 + 1.79 + 0.43 = $53.72
        
        assert result.buyer_invoice.total == 53.72, f"Expected buyer_total=53.72, got {result.buyer_invoice.total}"
        print(f"PASS: Proof C - non_vehicle_stripe(50, 'ON', 'vip', 'vip') => buyer_total=${result.buyer_invoice.total}")
    
    def test_proof_c_seller_payout(self):
        """$50 ON VIP seller_payout should be $48.50"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'vip', 'vip')
        
        # Expected seller calculation:
        # Hammer: $50
        # Seller Commission (2%): $1.00
        # Stripe recovery on SC: (1.00 * 0.029) + 0.30 = $0.33
        # Taxable: 1.00 + 0.33 = $1.33
        # Tax (13% HST): $0.17
        # Net payout: 50 - 1.00 - 0.33 - 0.17 = $48.50
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 48.50, f"Expected seller_payout=48.50, got {result.seller_invoice.total}"
        print(f"PASS: Proof C - non_vehicle_stripe(50, 'ON', 'vip', 'vip') => seller_payout=${result.seller_invoice.total}")


# ============ PROOF D: $50 ON Partner => buyer=$0, seller=$2.08 ============
class TestProofD_Partner:
    """Proof D: PricingManager.partner_auction(50, 'ON') returns buyer=$0.00 seller=$2.08"""
    
    def test_proof_d_buyer_total(self):
        """$50 ON Partner buyer_total reflects spec: hammer + partner BP (BidVex fee = $0)."""
        from services.pricing_manager import PricingManager

        # Spec semantics: buyer.total = hammer + partner_bp (what buyer pays partner).
        # BidVex's portion (`fees_subtotal`) stays $0.
        # When partner_bp_rate is 0 → buyer.total == hammer.
        result = PricingManager.partner_auction(50, 'ON', partner_bp_rate=0.0)

        assert result.buyer_invoice.fees_subtotal == 0.0, "BidVex must charge buyer $0 fee"
        assert result.buyer_invoice.total == 50.0, (
            f"Expected buyer_total=50.0 (hammer + partner_bp 0%), got {result.buyer_invoice.total}"
        )
        print(f"PASS: Proof D - partner_auction(50, 'ON', 0%) => "
              f"buyer_total=${result.buyer_invoice.total} (BidVex fee = $0)")
    
    def test_proof_d_seller_total(self):
        """$50 ON Partner seller_total should be $2.08"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.partner_auction(50, 'ON')
        
        # Expected seller calculation:
        # Seller Commission (3% flat): $1.50
        # Stripe recovery: (1.50 * 0.029) + 0.30 = $0.34
        # Taxable: 1.50 + 0.34 = $1.84
        # Tax (13% HST): $0.24
        # Total: 1.50 + 0.34 + 0.24 = $2.08
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 2.08, f"Expected seller_total=2.08, got {result.seller_invoice.total}"
        print(f"PASS: Proof D - partner_auction(50, 'ON') => seller_total=${result.seller_invoice.total}")


# ============ STRIPE RECOVERY FORMULA VERIFICATION ============
class TestStripeRecoveryFormulas:
    """Verify stripe recovery formulas differ between non_vehicle_stripe and non_vehicle_cash"""
    
    def test_non_vehicle_stripe_buyer_sr_on_hammer_plus_bp(self):
        """non_vehicle_stripe buyer stripe_recovery should be on (hammer+BP)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(50, 'ON', 'free', 'free')
        
        # For $50 ON Standard:
        # hammer = $50, BP = $2.50, hammer+BP = $52.50
        # stripe_recovery = (52.50 * 0.029) + 0.30 = 1.5225 + 0.30 = 1.8225 => $1.82
        
        assert result.buyer_invoice.stripe_recovery == 1.82, f"Expected buyer SR=1.82 (on hammer+BP), got {result.buyer_invoice.stripe_recovery}"
        print(f"PASS: non_vehicle_stripe buyer stripe_recovery=${result.buyer_invoice.stripe_recovery} (on hammer+BP=$52.50)")
    
    def test_non_vehicle_cash_buyer_sr_on_bp_only(self):
        """non_vehicle_cash buyer stripe_recovery should be on BP only (not hammer+BP)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_cash(50, 'ON', 'free', 'free')
        
        # For $50 ON Standard Cash:
        # BP = $2.50
        # stripe_recovery = (2.50 * 0.029) + 0.30 = 0.0725 + 0.30 = 0.3725 => $0.37
        
        assert result.buyer_invoice.stripe_recovery == 0.37, f"Expected buyer SR=0.37 (on BP only), got {result.buyer_invoice.stripe_recovery}"
        print(f"PASS: non_vehicle_cash buyer stripe_recovery=${result.buyer_invoice.stripe_recovery} (on BP only=$2.50)")


# ============ EXISTING PROOFS UNCHANGED ============
class TestExistingProofsUnchanged:
    """Verify existing proofs from iteration 139 are unchanged"""
    
    def test_vehicle_auction_qc_1000_unchanged(self):
        """vehicle_auction(1000, 'QC') should still return buyer_total=$29.93"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(1000, 'QC')
        
        assert result.buyer_invoice.total == 29.93, f"Expected buyer_total=29.93, got {result.buyer_invoice.total}"
        print(f"PASS: vehicle_auction(1000, 'QC') => buyer_total=${result.buyer_invoice.total} (unchanged)")
    
    def test_flat_purchase_on_300_unchanged(self):
        """flat_purchase(300, 'ON') should still return total=$349.17"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.flat_purchase(300, 'ON')
        
        assert result.buyer_invoice.total == 349.17, f"Expected total=349.17, got {result.buyer_invoice.total}"
        print(f"PASS: flat_purchase(300, 'ON') => total=${result.buyer_invoice.total} (unchanged)")
    
    def test_non_vehicle_cash_ab_500_buyer_unchanged(self):
        """non_vehicle_cash(500, 'AB', 'free', 'free') buyer should still be $27.33"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_cash(500, 'AB', 'free', 'free')
        
        assert result.buyer_invoice.total == 27.33, f"Expected buyer_total=27.33, got {result.buyer_invoice.total}"
        print(f"PASS: non_vehicle_cash(500, 'AB') => buyer_total=${result.buyer_invoice.total} (unchanged)")
    
    def test_non_vehicle_cash_ab_500_seller_unchanged(self):
        """non_vehicle_cash(500, 'AB', 'free', 'free') seller should still be $21.92"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_cash(500, 'AB', 'free', 'free')
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 21.92, f"Expected seller_total=21.92, got {result.seller_invoice.total}"
        print(f"PASS: non_vehicle_cash(500, 'AB') => seller_total=${result.seller_invoice.total} (unchanged)")
    
    def test_partner_auction_on_2000_buyer_unchanged(self):
        """partner_auction(2000, 'ON', 0%) buyer total = hammer (BidVex fee still $0)"""
        from services.pricing_manager import PricingManager

        # Per spec: buyer.total now reflects hammer + partner_bp (what buyer pays partner).
        # BidVex's portion stays $0 — that is the invariant the spec preserves.
        result = PricingManager.partner_auction(2000, 'ON', partner_bp_rate=0.0)

        assert result.buyer_invoice.fees_subtotal == 0.0, "BidVex fee must stay $0"
        assert result.buyer_invoice.total == 2000.0, (
            f"Expected buyer_total=2000.0 (hammer + 0% BP), got {result.buyer_invoice.total}"
        )
        print(f"PASS: partner_auction(2000, 'ON', 0%) => buyer_total=${result.buyer_invoice.total} "
              f"(BidVex fee $0 unchanged)")
    
    def test_partner_auction_on_2000_seller_unchanged(self):
        """partner_auction(2000, 'ON') seller should still be $70.11"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.partner_auction(2000, 'ON')
        
        assert result.seller_invoice is not None, "Seller invoice should exist"
        assert result.seller_invoice.total == 70.11, f"Expected seller_total=70.11, got {result.seller_invoice.total}"
        print(f"PASS: partner_auction(2000, 'ON') => seller_total=${result.seller_invoice.total} (unchanged)")


# ============ CONNECT PAYMENT ENGINE VERIFICATION ============
class TestConnectPaymentEngineGeneral:
    """Verify connect_payment_engine.calculate_connect_checkout with general ON returns correct stripe_charge"""
    
    def test_connect_checkout_general_on_returns_correct_stripe_charge(self):
        """calculate_connect_checkout with general ON should return correct stripe_charge"""
        from services.connect_payment_engine import calculate_connect_checkout
        
        result = calculate_connect_checkout(
            hammer_price=50,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            province="ON",
        )
        
        # Non-vehicle Stripe: buyer pays hammer + BP + stripe + tax
        # Expected: $54.88 (same as Proof A)
        assert result["stripe_charge"] == 54.88, f"Expected stripe_charge=54.88, got {result['stripe_charge']}"
        print(f"PASS: calculate_connect_checkout(50, 'general', 'ON') => stripe_charge=${result['stripe_charge']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
