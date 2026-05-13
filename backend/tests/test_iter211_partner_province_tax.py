"""
iter211 Step 2 — Canadian Province Tax Router for Partner fees.

Verifies that calculate_fee() routes partner taxes correctly across all 13
Canadian provinces and territories:
  • QC                          → 5% GST + 9.975% QST (=14.975%)
  • ON                          → 13% HST
  • NB, NS, PE, NL              → 15% HST
  • AB, BC, SK, MB, NT, NU, YT  → 5% GST only

Worked example used to lock numbers: $10,000 hammer, partner_bp_rate=0,
seller_commission = 3% of hammer = $300. Taxes apply to the $300.

  QC  → GST $15.00 + QST $29.93 = $44.93           (commission_total $344.93)
  ON  → HST $39.00                                  (commission_total $339.00)
  NB  → HST $45.00                                  (commission_total $345.00)
  AB  → GST $15.00                                  (commission_total $315.00)
"""
import math
import pytest

from services.fee_calculator import (
    calculate_fee,
    calculate_partner_taxes,
    PROVINCE_TAX_REGIME,
)


def _approx(a, b, tol=0.01):
    return math.isclose(a, b, abs_tol=tol)


# ─── Province registry ───────────────────────────────────────────────────
class TestProvinceRegistry:
    def test_all_13_provinces_present(self):
        expected = {"QC", "ON", "NB", "NS", "PE", "NL", "AB", "BC", "SK", "MB", "NT", "NU", "YT"}
        assert set(PROVINCE_TAX_REGIME.keys()) == expected, \
            f"Missing or extra provinces: {expected.symmetric_difference(PROVINCE_TAX_REGIME.keys())}"

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


# ─── calculate_partner_taxes helper ───────────────────────────────────────
class TestPartnerTaxesHelper:
    def test_qc_300_yields_gst_15_qst_29_93(self):
        from decimal import Decimal
        bd = calculate_partner_taxes(Decimal("300"), "QC")
        assert bd["type"] == "GST+QST"
        assert bd["province"] == "QC"
        assert float(bd["gst"]) == pytest.approx(15.00, abs=0.01)
        assert float(bd["qst"]) == pytest.approx(29.93, abs=0.01)
        assert float(bd["hst"]) == 0.0
        assert float(bd["total"]) == pytest.approx(44.93, abs=0.01)

    def test_on_300_yields_hst_39(self):
        from decimal import Decimal
        bd = calculate_partner_taxes(Decimal("300"), "ON")
        assert bd["type"] == "HST"
        assert float(bd["gst"]) == 0.0
        assert float(bd["hst"]) == pytest.approx(39.00, abs=0.01)
        assert float(bd["total"]) == pytest.approx(39.00, abs=0.01)

    def test_nb_300_yields_hst_45(self):
        from decimal import Decimal
        bd = calculate_partner_taxes(Decimal("300"), "NB")
        assert bd["type"] == "HST"
        assert float(bd["hst"]) == pytest.approx(45.00, abs=0.01)

    def test_ab_300_yields_gst_15_only(self):
        from decimal import Decimal
        bd = calculate_partner_taxes(Decimal("300"), "AB")
        assert bd["type"] == "GST"
        assert float(bd["gst"]) == pytest.approx(15.00, abs=0.01)
        assert float(bd["qst"]) == 0.0
        assert float(bd["hst"]) == 0.0
        assert float(bd["total"]) == pytest.approx(15.00, abs=0.01)

    def test_full_province_name_aliases(self):
        """Accept 'Quebec', 'Ontario', etc. — not just 2-letter codes."""
        from decimal import Decimal
        assert calculate_partner_taxes(Decimal("100"), "Quebec")["province"] == "QC"
        assert calculate_partner_taxes(Decimal("100"), "Ontario")["province"] == "ON"
        assert calculate_partner_taxes(Decimal("100"), "British Columbia")["province"] == "BC"
        assert calculate_partner_taxes(Decimal("100"), "Newfoundland and Labrador")["province"] == "NL"

    def test_missing_province_defaults_to_qc(self):
        """Unknown/missing province must fall back to Quebec for back-compat."""
        from decimal import Decimal
        assert calculate_partner_taxes(Decimal("100"), "")["province"] == "QC"
        assert calculate_partner_taxes(Decimal("100"), None)["province"] == "QC"
        assert calculate_partner_taxes(Decimal("100"), "Bermuda")["province"] == "QC"


# ─── calculate_fee() partner routing — Cash/E-transfer payment ────────────
class TestPartnerFeeCashByProvince:
    """Partner on cash sale: seller card auto-charged commission + taxes + Stripe gross-up.
    Test the SELLER-side commission tax by province."""

    @pytest.mark.parametrize("province,expected_tax_type,expected_commission_total", [
        ("QC", "GST+QST", 344.93),     # 300 + 15 + 29.93
        ("ON", "HST", 339.00),          # 300 + 39
        ("NB", "HST", 345.00),          # 300 + 45
        ("NS", "HST", 345.00),          # 300 + 45
        ("PE", "HST", 345.00),
        ("NL", "HST", 345.00),
        ("AB", "GST", 315.00),          # 300 + 15
        ("BC", "GST", 315.00),
        ("SK", "GST", 315.00),
        ("MB", "GST", 315.00),
        ("YT", "GST", 315.00),
    ])
    def test_partner_cash_10000_seller_taxes(self, province, expected_tax_type, expected_commission_total):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="lots",
            seller_account_type="partner",
            partner_bp_rate=0.0,
            payment_method="cash",
            seller_province=province,
        )
        assert fee["seller_commission"] == 300.0
        assert fee["tax_type"] == expected_tax_type
        assert fee["tax_province"] == province
        assert _approx(fee["seller_commission_total"], expected_commission_total), \
            f"{province}: got ${fee['seller_commission_total']}, expected ${expected_commission_total}"


# ─── calculate_fee() partner routing — Stripe payment ─────────────────────
class TestPartnerFeeStripeByProvince:
    """Partner on Stripe: buyer pays hammer + BP + taxes ON THE BP, BidVex deducts
    3% + commission tax from partner's payout. Test BUYER-side BP tax by province."""

    @pytest.mark.parametrize("province,expected_tax_type,expected_buyer_tax", [
        # $10,000 hammer with 10% partner BP = $1,000 BP
        ("QC", "GST+QST", 149.75),    # 50 + 99.75
        ("ON", "HST", 130.00),
        ("NB", "HST", 150.00),
        ("AB", "GST", 50.00),
        ("BC", "GST", 50.00),
    ])
    def test_partner_stripe_10000_buyer_bp_taxes(self, province, expected_tax_type, expected_buyer_tax):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="lots",
            seller_account_type="partner",
            partner_bp_rate=0.10,  # 10% buyer's premium
            payment_method="stripe",
            seller_province=province,
        )
        assert fee["buyer_premium"] == 1000.0
        assert fee["tax_type"] == expected_tax_type
        # Tax routed by partner's province as per spec
        actual_tax = fee["buyer_gst"] + fee["buyer_qst"] + fee["buyer_hst"]
        assert _approx(actual_tax, expected_buyer_tax), \
            f"{province}: got ${actual_tax}, expected ${expected_buyer_tax}"


# ─── Back-compat: non-partner flows MUST stay QC-only ─────────────────────
class TestNonPartnerFlowsStayQC:
    """The user spec scopes province routing to PARTNER flows only.
    Individual, vehicle_dealer, and storage_facility must remain QC-locked
    so the iter209 spec amounts don't drift."""

    def test_individual_stays_qc_even_with_on_province(self):
        fee = calculate_fee(
            hammer_price=100,
            auction_type="lots",
            seller_account_type="individual",
            buyer_tier="premium",
            seller_tier="standard",
            seller_province="ON",   # should be IGNORED for non-partner flows
        )
        assert fee["tax_province"] == "QC"
        assert fee["tax_type"] == "GST+QST"
        # iter209 spec lock — $95.40 payout must NOT change
        assert _approx(fee["seller_payout"], 95.40)

    def test_vehicle_dealer_unaffected(self):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="vehicle",
            seller_account_type="vehicle_dealer",
            seller_province="ON",
        )
        assert _approx(fee["seller_payout"], 10_000.00)
        assert fee["buyer_premium"] == 250.00

    def test_storage_facility_stays_qc(self):
        fee = calculate_fee(
            hammer_price=100,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="stripe",
            seller_province="ON",
        )
        assert fee["tax_province"] == "QC"
        # iter211 P0 lock — facility payout must remain $94.25
        assert _approx(fee["seller_payout"], 94.25)


# ─── Default behavior (no province supplied) ──────────────────────────────
class TestPartnerDefaultsToQuebec:
    """If seller_province is not supplied (legacy callers), partner taxes
    default to Quebec so existing math/tests stay unchanged."""

    def test_no_province_means_qc(self):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="lots",
            seller_account_type="partner",
            partner_bp_rate=0.10,
            payment_method="cash",
            # no seller_province
        )
        assert fee["tax_province"] == "QC"
        assert fee["tax_type"] == "GST+QST"
