"""
iter350 — 8 Mandatory Proofs from /app/memory/PAYMENT_INFRASTRUCTURE.md Appendix A.

Every calculation flows through `calculate_fee()` / `calculate_broker_transaction()` /
`calculate_contractor_commission()`. These 8 proofs are the acceptance gate for
Part B of the Payment Sprint — if any one fails, the migration is INVALID.

Reference: /app/memory/PAYMENT_INFRASTRUCTURE.md §18 (Appendix A).
"""
from decimal import Decimal

import pytest

from services.fee_calculator import (
    calculate_fee,
    calculate_broker_transaction,
    calculate_contractor_commission,
    calculate_stripe_recovery,
    tax_on,
    FEE_MODEL_VERSION,
)


# Tolerance for penny-level rounding drift on displayed totals
CENT = 0.01


class TestProof1_IndividualStarterQC500:
    """§18.1 Individual Starter buyer/seller, QC, $500 hammer."""

    def test_buyer_side(self):
        fee = calculate_fee(
            hammer_price=500.0,
            auction_type="lots",
            seller_account_type="individual",
            seller_tier="starter",
            buyer_tier="starter",
            payment_method="stripe",
            buyer_province="QC",
            seller_province="QC",
        )
        assert fee["fee_model_version"] == FEE_MODEL_VERSION
        assert fee["buyer_premium"] == pytest.approx(25.00, abs=CENT)
        assert fee["buyer_stripe_recovery"] == pytest.approx(1.03, abs=CENT)
        assert fee["buyer_taxes"] == pytest.approx(3.90, abs=CENT)
        assert fee["buyer_total_charged"] == pytest.approx(529.93, abs=CENT)
        assert fee["buyer_tax_label"].startswith("GST + QST")

    def test_seller_side(self):
        fee = calculate_fee(
            hammer_price=500.0,
            auction_type="lots",
            seller_account_type="individual",
            seller_tier="starter",
            buyer_tier="starter",
            payment_method="stripe",
            buyer_province="QC",
            seller_province="QC",
        )
        assert fee["seller_commission"] == pytest.approx(20.00, abs=CENT)
        assert fee["seller_stripe_recovery"] == pytest.approx(0.88, abs=CENT)
        assert fee["seller_taxes"] == pytest.approx(3.13, abs=CENT)
        assert fee["seller_payout"] == pytest.approx(475.99, abs=CENT)


class TestProof2_Partner12pctQC2000:
    """§18.2 Partner 12% BP, QC, $2000 hammer."""

    def test_partner_flow(self):
        fee = calculate_fee(
            hammer_price=2000.0,
            auction_type="lots",
            seller_account_type="partner",
            partner_bp_rate=0.12,
            payment_method="stripe",
            buyer_province="QC",
            seller_province="QC",
            partner_province="QC",
        )
        assert fee["fee_model_version"] == FEE_MODEL_VERSION
        # Partner sets 12% BP → $240 (goes to partner)
        assert fee["buyer_premium"] == pytest.approx(240.00, abs=CENT)
        # BidVex 3% platform fee → $60
        assert fee["seller_commission"] == pytest.approx(60.00, abs=CENT)
        # Stripe recovery on $60 = $2.04
        assert fee["seller_stripe_recovery"] == pytest.approx(2.04, abs=CENT)
        # Tax on ($60 + $2.04) × 14.975% = $9.29
        assert fee["seller_taxes"] == pytest.approx(9.29, abs=CENT)
        # Partner owes BidVex = $60 + $2.04 + $9.29 = $71.33
        # (spec shows $71.34 due to rounding; we accept either within CENT)
        assert fee["seller_payout"] == pytest.approx(71.33, abs=CENT)


class TestProof3_EnterprisePremiumON1000:
    """§18.3 Enterprise Premium buyer/seller, ON, $1000 hammer."""

    def test_buyer_side(self):
        fee = calculate_fee(
            hammer_price=1000.0,
            auction_type="lots",
            seller_account_type="enterprise",
            seller_tier="premium",
            buyer_tier="premium",
            payment_method="stripe",
            buyer_province="ON",
            seller_province="ON",
        )
        assert fee["buyer_premium"] == pytest.approx(35.00, abs=CENT)
        assert fee["buyer_stripe_recovery"] == pytest.approx(1.32, abs=CENT)
        assert fee["buyer_taxes"] == pytest.approx(4.72, abs=CENT)
        assert fee["buyer_total_charged"] == pytest.approx(1041.04, abs=CENT)
        assert fee["buyer_tax_label"] == "HST (13%)"

    def test_seller_side(self):
        fee = calculate_fee(
            hammer_price=1000.0,
            auction_type="lots",
            seller_account_type="enterprise",
            seller_tier="premium",
            buyer_tier="premium",
            payment_method="stripe",
            buyer_province="ON",
            seller_province="ON",
        )
        assert fee["seller_commission"] == pytest.approx(25.00, abs=CENT)
        assert fee["seller_stripe_recovery"] == pytest.approx(1.03, abs=CENT)
        assert fee["seller_taxes"] == pytest.approx(3.38, abs=CENT)
        assert fee["seller_payout"] == pytest.approx(970.59, abs=CENT)


class TestProof4_VehicleDealerQC20000:
    """§18.4 Vehicle dealer, QC buyer, $20,000 hammer."""

    def test_vehicle_qc(self):
        fee = calculate_fee(
            hammer_price=20000.0,
            auction_type="vehicle",
            seller_account_type="vehicle_dealer",
            buyer_province="QC",
        )
        # 2.5% platform fee → $500
        assert fee["buyer_premium"] == pytest.approx(500.00, abs=CENT)
        # Stripe recovery = (500 × 2.9%) + 0.30 = 14.80
        assert fee["buyer_stripe_recovery"] == pytest.approx(14.80, abs=CENT)
        # Tax QC = (500 + 14.80) × 14.975% = 77.09
        assert fee["buyer_taxes"] == pytest.approx(77.09, abs=CENT)
        # Buyer pays BidVex = 500 + 14.80 + 77.09 = 591.89
        assert fee["buyer_total_charged"] == pytest.approx(591.89, abs=CENT)
        # Dealer collects hammer directly - $0 to BidVex per transaction
        assert fee["seller_commission"] == 0.0


class TestProof5_VehicleDealerAB5000:
    """§18.5 Vehicle dealer, AB buyer, $5,000 hammer.

    Non-QC province path — must use 5% GST (not 14.975% QC).
    This is the specific CRA compliance bug the migration fixes.
    """

    def test_vehicle_ab(self):
        fee = calculate_fee(
            hammer_price=5000.0,
            auction_type="vehicle",
            seller_account_type="vehicle_dealer",
            buyer_province="AB",
        )
        # 2.5% platform fee → $125
        assert fee["buyer_premium"] == pytest.approx(125.00, abs=CENT)
        # Stripe recovery = (125 × 2.9%) + 0.30 = 3.93
        assert fee["buyer_stripe_recovery"] == pytest.approx(3.93, abs=CENT)
        # Tax AB (GST 5%) = (125 + 3.93) × 5% = 6.45
        assert fee["buyer_taxes"] == pytest.approx(6.45, abs=CENT)
        # Buyer pays BidVex = 125 + 3.93 + 6.45 = 135.38
        assert fee["buyer_total_charged"] == pytest.approx(135.38, abs=CENT)
        # CRA compliance: tax label reflects AB, not QC
        assert fee["buyer_tax_label"] == "GST (5%)"


class TestProof6_StorageQC800:
    """§18.6 Storage QC, $800 hammer."""

    def test_storage_qc(self):
        fee = calculate_fee(
            hammer_price=800.0,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="cash",  # facility pays BidVex directly (via card on file)
            facility_province="QC",
            buyer_province="QC",
        )
        # 5% commission = $40
        assert fee["seller_commission"] == pytest.approx(40.00, abs=CENT)
        # Stripe recovery = (40 × 2.9%) + 0.30 = 1.46
        assert fee["seller_stripe_recovery"] == pytest.approx(1.46, abs=CENT)
        # Tax QC on (40 + 1.46) × 14.975% = 6.21
        assert fee["seller_taxes"] == pytest.approx(6.21, abs=CENT)
        # Facility owes BidVex = 40 + 1.46 + 6.21 = 47.67
        assert fee["seller_payout"] == pytest.approx(47.67, abs=CENT)
        # Buyer pays $0 in BidVex fees on storage
        assert fee["buyer_total_charged"] == 0.0


class TestProof7_BrokerQC15000_3pct:
    """§18.7 Broker deal, QC buyer, $15,000 hammer, 3% broker fee."""

    def test_broker_qc(self):
        result = calculate_broker_transaction(
            hammer_price=15000.0,
            broker_fee_structure={"type": "percentage", "percentage_rate": 0.03},
            buyer_province="QC",
        )
        # BidVex 2.5% = $375, Broker 3% = $450, Combined = $825
        assert result["bidvex_platform_fee"] == pytest.approx(375.00, abs=CENT)
        assert result["broker_fee"] == pytest.approx(450.00, abs=CENT)
        assert result["combined_fees"] == pytest.approx(825.00, abs=CENT)
        # Stripe recovery = (825 × 2.9%) + 0.30 = 24.23
        assert result["stripe_recovery"] == pytest.approx(24.23, abs=CENT)
        # Tax base = 825 + 24.23 = 849.23
        # GST QC = 849.23 × 5% = 42.46; QST = 849.23 × 9.975% = 84.71; total = 127.17
        assert result["gst"] == pytest.approx(42.46, abs=CENT)
        assert result["qst"] == pytest.approx(84.71, abs=CENT)
        assert result["tax_total"] == pytest.approx(127.17, abs=CENT)
        # Total due from buyer = 15000 + 825 + 24.23 + 127.17 = 15976.40
        assert result["total_due_from_buyer"] == pytest.approx(15976.40, abs=CENT)
        # buyer pays BidVex-only portion (excluding hammer to dealer)
        assert result["buyer_pays_bidvex_only"] == pytest.approx(976.40, abs=CENT)


class TestProof8_Contractor300Fee_20pct:
    """§18.8 Contractor commission, $300 BidVex fee, 20% rate → $60."""

    def test_contractor(self):
        commission = calculate_contractor_commission(300.0, 0.20)
        assert commission == Decimal("60.00")


# ─── Bonus: cross-province routing sanity checks ──────────────────────

class TestPerUserPlaceOfSupplyCompliance:
    """CRA §142.1 Place-of-Supply: each user's fee taxed at THEIR own province."""

    def test_qc_buyer_on_seller_split_tax(self):
        """QC buyer + ON seller → 14.975% on buyer's BP, 13% HST on seller's SC."""
        fee = calculate_fee(
            hammer_price=1000.0,
            auction_type="lots",
            seller_account_type="individual",
            seller_tier="starter",
            buyer_tier="starter",
            payment_method="stripe",
            buyer_province="QC",
            seller_province="ON",
        )
        # Buyer premium taxed at 14.975% QC
        assert fee["buyer_tax_label"] == "GST + QST (14.975%)"
        # Seller commission taxed at 13% HST ON
        assert fee["seller_tax_label"] == "HST (13%)"
        # Amounts:
        # BP = 1000 × 5% = 50 → SR = (50 × 2.9%) + 0.30 = 1.75 → tax = (50 + 1.75) × 14.975% = 7.75
        assert fee["buyer_premium"] == pytest.approx(50.00, abs=CENT)
        assert fee["buyer_stripe_recovery"] == pytest.approx(1.75, abs=CENT)
        assert fee["buyer_taxes"] == pytest.approx(7.75, abs=CENT)
        # SC = 1000 × 4% = 40 → SR = (40 × 2.9%) + 0.30 = 1.46 → tax = (40 + 1.46) × 13% = 5.39
        assert fee["seller_commission"] == pytest.approx(40.00, abs=CENT)
        assert fee["seller_stripe_recovery"] == pytest.approx(1.46, abs=CENT)
        assert fee["seller_taxes"] == pytest.approx(5.39, abs=CENT)

    def test_us_buyer_zero_rated(self):
        """US buyer → zero-rated per Sched. VI Part V §7."""
        fee = calculate_fee(
            hammer_price=1000.0,
            auction_type="lots",
            seller_account_type="individual",
            seller_tier="starter",
            buyer_tier="starter",
            payment_method="stripe",
            buyer_province="US",
            seller_province="QC",
        )
        assert fee["buyer_taxes"] == 0.0
        assert fee["buyer_tax_label"] == "Exported Service (0%)"
        # Seller remains taxed at QC
        assert fee["seller_tax_label"] == "GST + QST (14.975%)"


class TestStripeRecoveryFormula:
    """Canonical (fee × 2.9%) + $0.30, applied ONLY on BidVex fee."""

    def test_stripe_recovery_100(self):
        assert calculate_stripe_recovery(100) == Decimal("3.20")

    def test_stripe_recovery_zero(self):
        assert calculate_stripe_recovery(0) == Decimal("0.00")

    def test_stripe_recovery_1000(self):
        assert calculate_stripe_recovery(1000) == Decimal("29.30")


class TestTaxOnByProvince:
    """tax_on() routes rates by province — every CRA-supported code covered."""

    @pytest.mark.parametrize("prov,rate,label", [
        ("QC",   Decimal("0.14975"), "GST + QST (14.975%)"),
        ("ON",   Decimal("0.13"),    "HST (13%)"),
        ("NB",   Decimal("0.15"),    "HST (15%)"),
        ("NL",   Decimal("0.15"),    "HST (15%)"),
        ("NS",   Decimal("0.15"),    "HST (15%)"),
        ("PE",   Decimal("0.15"),    "HST (15%)"),
        ("AB",   Decimal("0.05"),    "GST (5%)"),
        ("BC",   Decimal("0.05"),    "GST (5%)"),
        ("MB",   Decimal("0.05"),    "GST (5%)"),
        ("SK",   Decimal("0.05"),    "GST (5%)"),
        ("YT",   Decimal("0.05"),    "GST (5%)"),
        ("NT",   Decimal("0.05"),    "GST (5%)"),
        ("NU",   Decimal("0.05"),    "GST (5%)"),
        ("INTL", Decimal("0"),       "Exported Service (0%)"),
    ])
    def test_province_rate(self, prov, rate, label):
        bd = tax_on(100, prov)
        assert bd["province"] == prov
        assert bd["combined_rate"] == rate
        assert bd["label"] == label
        # Total is quantized to cents per bankers' rounding (CRA ROUND_HALF_UP).
        expected_total = (Decimal("100") * rate).quantize(Decimal("0.01"))
        assert bd["total"] == expected_total
