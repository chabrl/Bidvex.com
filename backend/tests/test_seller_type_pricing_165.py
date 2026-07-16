"""
SELLER TYPE, TAX LOGIC & PRICING ENGINE — iter350 CANONICAL PROOFS
Migrated from iter165 spec (old Stripe-gross-up model) to iter350
(per-user CRA Place-of-Supply + Stripe recovery on BidVex fee ONLY).

These 3 proofs are the canonical truth for:
  • Individual seller (tier-based BP/SC, tax at each user's province)
  • Partner seller    (buyer pays $0 BidVex; partner owes 3% + tax)
  • Enterprise seller (tier-based BP/SC, tax at each user's province)

Tax applies ONLY to BidVex fees (never the hammer price).
See /app/memory/PAYMENT_INFRASTRUCTURE.md §18 Appendix A for the source math.
"""
import pytest

from services.fee_calculator import PricingManager, calculate_fee


CENT = 0.01


class TestSpecProof1IndividualQC:
    """Proof 1 — Individual QC, $500, Starter buyer/seller, Stripe. iter350 spec §18.1."""

    def test_buyer_side_iter350(self):
        fee = calculate_fee(
            hammer_price=500, seller_account_type="individual",
            auction_type="lots",
            buyer_province="QC", seller_province="QC",
            buyer_tier="starter", seller_tier="starter",
            payment_method="stripe",
        )
        # iter350 canonical: BP=$25, SR=$1.03, tax=$3.90, total_charged=$529.93
        assert fee["buyer_premium"] == pytest.approx(25.00, abs=CENT)
        assert fee["buyer_stripe_recovery"] == pytest.approx(1.03, abs=CENT)
        assert fee["buyer_taxes"] == pytest.approx(3.90, abs=CENT)
        assert fee["buyer_total_charged"] == pytest.approx(529.93, abs=CENT)
        assert fee["fee_model_version"] == "iter350"

    def test_seller_side_iter350(self):
        fee = calculate_fee(
            hammer_price=500, seller_account_type="individual",
            auction_type="lots",
            buyer_province="QC", seller_province="QC",
            buyer_tier="starter", seller_tier="starter",
            payment_method="stripe",
        )
        # iter350: SC=$20, SR=$0.88, tax=$3.13, payout=$475.99
        assert fee["seller_commission"] == pytest.approx(20.00, abs=CENT)
        assert fee["seller_stripe_recovery"] == pytest.approx(0.88, abs=CENT)
        assert fee["seller_taxes"] == pytest.approx(3.13, abs=CENT)
        assert fee["seller_payout"] == pytest.approx(475.99, abs=CENT)


class TestSpecProof2PartnerQC:
    """Proof 2 — Partner QC, $2000, partner_bp_rate=12%, Stripe. iter350 spec §18.2."""

    def test_buyer_pays_partner_2240(self):
        # Under iter350 the partner charges the buyer's premium themselves;
        # BidVex charges the buyer $0. Buyer pays partner directly:
        # hammer $2000 + partner_bp $240 = $2240.
        fee = calculate_fee(
            hammer_price=2000, seller_account_type="partner",
            auction_type="lots",
            buyer_province="QC", seller_province="QC", partner_province="QC",
            partner_bp_rate=0.12, payment_method="stripe",
        )
        assert fee["buyer_taxes"] == 0.0  # BidVex charges buyer nothing directly
        assert fee["buyer_total_charged"] == pytest.approx(2240.00, abs=CENT)

    def test_partner_owes_71_33(self):
        fee = calculate_fee(
            hammer_price=2000, seller_account_type="partner",
            auction_type="lots",
            buyer_province="QC", seller_province="QC", partner_province="QC",
            partner_bp_rate=0.12, payment_method="stripe",
        )
        # BidVex 3% platform fee = $60, SR = $2.04, tax = $9.29 → $71.33 owed by partner
        assert fee["seller_commission"] == pytest.approx(60.00, abs=CENT)
        assert fee["seller_stripe_recovery"] == pytest.approx(2.04, abs=CENT)
        assert fee["seller_taxes"] == pytest.approx(9.29, abs=CENT)
        assert fee["seller_payout"] == pytest.approx(71.33, abs=CENT)


class TestSpecProof3EnterpriseON:
    """Proof 3 — Enterprise ON, $1000, Premium buyer/seller, Stripe. iter350 spec §18.3."""

    def test_buyer_total_1041_04(self):
        # iter350 (Stripe recovery on BidVex fee ONLY, tax on buyer's province ON):
        # BP=$35, SR=$1.32, HST=$4.72, total_charged=$1041.04
        fee = calculate_fee(
            hammer_price=1000, seller_account_type="enterprise",
            auction_type="lots",
            buyer_province="ON", seller_province="ON",
            buyer_tier="premium", seller_tier="premium",
            payment_method="stripe",
        )
        assert fee["buyer_premium"] == pytest.approx(35.00, abs=CENT)
        assert fee["buyer_stripe_recovery"] == pytest.approx(1.32, abs=CENT)
        assert fee["buyer_taxes"] == pytest.approx(4.72, abs=CENT)
        assert fee["buyer_total_charged"] == pytest.approx(1041.04, abs=CENT)
        assert fee["buyer_tax_label"] == "HST (13%)"

    def test_seller_receives_970_59(self):
        fee = calculate_fee(
            hammer_price=1000, seller_account_type="enterprise",
            auction_type="lots",
            buyer_province="ON", seller_province="ON",
            buyer_tier="premium", seller_tier="premium",
            payment_method="stripe",
        )
        assert fee["seller_commission"] == pytest.approx(25.00, abs=CENT)
        assert fee["seller_stripe_recovery"] == pytest.approx(1.03, abs=CENT)
        assert fee["seller_taxes"] == pytest.approx(3.38, abs=CENT)
        assert fee["seller_payout"] == pytest.approx(970.59, abs=CENT)
        assert fee["seller_tax_label"] == "HST (13%)"


class TestTaxAlwaysAppliesAllSellerTypes:
    """iter350: Tax applies to every BidVex-fee supply, per CRA Place-of-Supply."""

    def test_individual_qc_tax_applied(self):
        fee = calculate_fee(
            hammer_price=100, seller_account_type="individual",
            auction_type="lots",
            buyer_province="QC", seller_province="QC",
            buyer_tier="starter", seller_tier="starter",
        )
        assert fee["buyer_taxes"] > 0
        assert fee["seller_taxes"] > 0

    def test_enterprise_on_tax_applied(self):
        fee = calculate_fee(
            hammer_price=100, seller_account_type="enterprise",
            auction_type="lots",
            buyer_province="ON", seller_province="ON",
            buyer_tier="starter", seller_tier="starter",
        )
        assert fee["buyer_taxes"] > 0
        assert fee["seller_taxes"] > 0

    def test_partner_seller_qc_tax_applied(self):
        fee = calculate_fee(
            hammer_price=100, seller_account_type="partner",
            auction_type="lots",
            buyer_province="QC", partner_province="QC",
            partner_bp_rate=0.05,
        )
        # BidVex 3% fee taxed at partner's province
        assert fee["seller_taxes"] > 0


class TestUnknownSellerTypeRaises:
    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="bogus"):
            calculate_fee(
                hammer_price=100, seller_account_type="bogus",
                auction_type="lots", buyer_province="ON",
            )


class TestLegacyPricingManagerStillCompiles:
    """iter350 keeps PricingManager as-is (legacy pre-CRA math) for callers
    that haven't migrated yet — new code MUST use `calculate_fee()`."""

    def test_pricing_manager_still_callable(self):
        # PricingManager math is untouched (legacy); it doesn't need to match
        # iter350 canonical numbers. This test only verifies the class remains
        # importable so vehicle_invoice / tax_engine callers don't break.
        r = PricingManager.calculate_fees(
            hammer_price=500, seller_type="individual",
            buyer_province="QC", buyer_tier="standard", seller_tier="standard",
        )
        assert r.buyer_invoice.fees_subtotal == 25.00
        assert r.buyer_invoice.tax_amount > 0
