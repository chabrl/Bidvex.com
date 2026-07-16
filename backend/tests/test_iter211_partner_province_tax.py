"""
iter211 → iter350 MIGRATION — Canadian Province Tax Router.

Updated to match iter350 canonical CRA-compliant math:
  * Stripe recovery applied ONLY to the BidVex fee (not the whole payment).
  * Tax base = (BidVex_fee + stripe_recovery), taxed at the RECIPIENT's province.
  * Partner flow: BidVex charges partner 3% + SR + tax (at partner's province).
                  BidVex charges the buyer $0 (buyer pays partner directly).
  * Individual/enterprise/vehicle/storage flows ALSO honor per-user Place-of-Supply
    (iter211 QC-locked behavior removed in iter350 — CRA §142.1 compliance).

Reference: /app/memory/PAYMENT_INFRASTRUCTURE.md §5 (Tax & Province Routing).
"""
import math
import pytest
from decimal import Decimal

from services.fee_calculator import (
    calculate_fee,
    calculate_partner_taxes,
    PROVINCE_TAX_REGIME,
)


def _approx(a, b, tol=0.01):
    return math.isclose(a, b, abs_tol=tol)


# ─── Province registry — still valid; iter350 preserves the map ─────────
class TestProvinceRegistry:
    def test_all_13_provinces_present(self):
        expected = {"QC", "ON", "NB", "NS", "PE", "NL", "AB", "BC", "SK", "MB", "NT", "NU", "YT"}
        assert set(PROVINCE_TAX_REGIME.keys()) == expected

    @pytest.mark.parametrize("code,expected_type,expected_combined", [
        ("QC", "GST+QST", 0.14975),
        ("ON", "HST", 0.13),
        ("NB", "HST", 0.15),
        ("NS", "HST", 0.15),
        ("PE", "HST", 0.15),
        ("NL", "HST", 0.15),
        ("AB", "GST", 0.05),
        ("BC", "GST", 0.05),
        ("SK", "GST", 0.05),
        ("MB", "GST", 0.05),
        ("NT", "GST", 0.05),
        ("NU", "GST", 0.05),
        ("YT", "GST", 0.05),
    ])
    def test_province_regime_correct(self, code, expected_type, expected_combined):
        regime = PROVINCE_TAX_REGIME[code]
        assert regime["type"] == expected_type
        assert float(regime["combined"]) == pytest.approx(expected_combined)


# ─── calculate_partner_taxes helper — legacy shape still works ─────────
class TestPartnerTaxesHelper:
    def test_qc_300_yields_gst_15_qst_29_93(self):
        bd = calculate_partner_taxes(Decimal("300"), "QC")
        assert bd["type"] == "GST+QST"
        assert bd["province"] == "QC"
        assert float(bd["gst"]) == pytest.approx(15.00, abs=0.01)
        assert float(bd["qst"]) == pytest.approx(29.93, abs=0.01)
        assert float(bd["total"]) == pytest.approx(44.93, abs=0.01)

    def test_on_300_yields_hst_39(self):
        bd = calculate_partner_taxes(Decimal("300"), "ON")
        assert bd["type"] == "HST"
        assert float(bd["hst"]) == pytest.approx(39.00, abs=0.01)
        assert float(bd["total"]) == pytest.approx(39.00, abs=0.01)

    def test_nb_300_yields_hst_45(self):
        bd = calculate_partner_taxes(Decimal("300"), "NB")
        assert bd["type"] == "HST"
        assert float(bd["hst"]) == pytest.approx(45.00, abs=0.01)

    def test_ab_300_yields_gst_15_only(self):
        bd = calculate_partner_taxes(Decimal("300"), "AB")
        assert bd["type"] == "GST"
        assert float(bd["gst"]) == pytest.approx(15.00, abs=0.01)
        assert float(bd["total"]) == pytest.approx(15.00, abs=0.01)

    def test_full_province_name_aliases(self):
        assert calculate_partner_taxes(Decimal("100"), "Quebec")["province"] == "QC"
        assert calculate_partner_taxes(Decimal("100"), "Ontario")["province"] == "ON"
        assert calculate_partner_taxes(Decimal("100"), "British Columbia")["province"] == "BC"
        assert calculate_partner_taxes(Decimal("100"), "Newfoundland and Labrador")["province"] == "NL"

    def test_missing_province_defaults_to_qc(self):
        """Legacy back-compat: `calculate_partner_taxes` shim still falls back to QC."""
        assert calculate_partner_taxes(Decimal("100"), "")["province"] == "QC"
        assert calculate_partner_taxes(Decimal("100"), None)["province"] == "QC"
        assert calculate_partner_taxes(Decimal("100"), "Bermuda")["province"] == "QC"


# ─── iter350 partner Stripe path — partner province routes SC tax ───────
class TestPartnerFeeStripeByProvince:
    """iter350: BidVex charges buyer $0 in partner deals. BidVex bills the
    PARTNER 3% + Stripe recovery + tax at the PARTNER's province."""

    @pytest.mark.parametrize("province,expected_tax_label,expected_seller_owes", [
        # $10,000 hammer, 0% partner BP → BidVex 3% = $300
        # SR = 300 × 0.029 + 0.30 = 9.00
        # taxable = 300 + 9 = 309
        # tax QC = 309 × 0.14975 = 46.27 → total = 300 + 9 + 46.27 = 355.27
        ("QC", "GST + QST (14.975%)", 355.27),
        # ON: tax = 309 × 0.13 = 40.17 → 300 + 9 + 40.17 = 349.17
        ("ON", "HST (13%)", 349.17),
        # NB/NL/NS/PE: tax = 309 × 0.15 = 46.35 → 300 + 9 + 46.35 = 355.35
        ("NB", "HST (15%)", 355.35),
        # AB/BC/SK/MB/YT: tax = 309 × 0.05 = 15.45 → 300 + 9 + 15.45 = 324.45
        ("AB", "GST (5%)", 324.45),
        ("BC", "GST (5%)", 324.45),
    ])
    def test_partner_stripe_10000_partner_owes(self, province, expected_tax_label, expected_seller_owes):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="lots",
            seller_account_type="partner",
            partner_bp_rate=0.0,
            payment_method="stripe",
            seller_province=province,
            partner_province=province,
            buyer_province=province,
        )
        assert fee["seller_commission"] == 300.00
        assert fee["seller_tax_label"] == expected_tax_label
        assert _approx(fee["seller_payout"], expected_seller_owes), (
            f"{province}: partner owes ${fee['seller_payout']} (expected ${expected_seller_owes})"
        )
        # Under iter350, BidVex charges the BUYER $0 in partner deals — regardless of province.
        assert fee["buyer_taxes"] == 0.0
        assert fee["buyer_stripe_recovery"] == 0.0


# ─── iter350 partner cash/e-transfer — partner card charged 3% + SR + tax ─
class TestPartnerFeeCashByProvince:
    """iter350: cash/e-transfer partner deals — BidVex auto-charges partner
    card the 3% + Stripe recovery + tax at partner's province."""

    @pytest.mark.parametrize("province,expected_partner_owes", [
        ("QC", 355.27),
        ("ON", 349.17),
        ("NB", 355.35),
        ("AB", 324.45),
    ])
    def test_partner_cash_10000(self, province, expected_partner_owes):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="lots",
            seller_account_type="partner",
            partner_bp_rate=0.0,
            payment_method="cash",
            partner_province=province,
            seller_province=province,
        )
        assert fee["seller_commission"] == 300.00
        assert _approx(fee["seller_payout"], expected_partner_owes)


# ─── iter350 CRA compliance: NON-partner flows also route by province ─────
class TestNonPartnerFlowsAreNowProvinceAware:
    """iter350 CRITICAL CHANGE: individual, vehicle, storage flows are NOW
    province-aware (previously locked to QC in iter211). This is the CRA
    compliance fix — buyers in AB/BC/SK/etc no longer overpay Quebec rates."""

    def test_individual_on_seller_uses_on_tax(self):
        fee = calculate_fee(
            hammer_price=100,
            auction_type="lots",
            seller_account_type="individual",
            buyer_tier="premium", seller_tier="starter",
            buyer_province="ON", seller_province="ON",
        )
        # iter350: ON HST 13% (buyer premium = $3.50; SR = 0.30 + 0.10 = 0.40 (approx))
        # tax = (3.50 + SR) × 0.13
        assert fee["buyer_tax_label"] == "HST (13%)"
        assert fee["seller_tax_label"] == "HST (13%)"

    def test_vehicle_dealer_ab_buyer_pays_ab_tax(self):
        fee = calculate_fee(
            hammer_price=5000,
            auction_type="vehicle",
            seller_account_type="vehicle_dealer",
            buyer_province="AB",
        )
        # iter350: tax = 5% GST at buyer's province AB (not 14.975% QC)
        assert fee["buyer_tax_label"] == "GST (5%)"
        # BidVex 2.5% = $125; SR = 3.925 → 3.93; tax = (125+3.93)×0.05 = 6.45
        assert _approx(fee["buyer_taxes"], 6.45)

    def test_storage_facility_on_facility_uses_on_tax(self):
        fee = calculate_fee(
            hammer_price=800,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="stripe",
            facility_province="ON",
            buyer_province="ON",
        )
        # iter350: 5% commission taxed at facility's province (ON HST 13%)
        assert fee["seller_tax_label"] == "HST (13%)"
        # Buyer pays $0 in BidVex fees on storage regardless of province
        assert fee["buyer_taxes"] == 0.0


# ─── Default behavior — iter350 uses INTL (zero-rated) as safe fallback ──
class TestDefaultBehaviorWithoutProvince:
    """iter350 SAFETY: unknown/missing province defaults to INTL (0%) so
    BidVex never over-collects tax on missing data (CRA rebate liability).
    Legacy `calculate_partner_taxes` shim still defaults to QC for
    back-compat with older test suites."""

    def test_calculate_fee_defaults_to_intl(self):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="lots",
            seller_account_type="partner",
            partner_bp_rate=0.10,
            payment_method="cash",
            # no province → INTL (0%)
        )
        assert fee["seller_tax_province"] == "INTL"
        assert fee["seller_taxes"] == 0.0
