"""
iter350 — Subscription tax routing tests (CRA Place-of-Supply compliance).

Verifies that /api/subscriptions/price-breakdown correctly taxes each
subscriber at THEIR own province — not the platform's (QC) province.

This is the key CRA §142.1 compliance fix — a Premium subscriber in
Alberta was previously being charged 14.975% QC tax on their $180/yr
subscription; under iter350 they now correctly pay only 5% GST.
"""
import pytest

from services.tax_engine import calculate_taxes_for_recipient


CENT = 0.01


class TestSubscriptionTaxByProvince:
    """Every Canadian jurisdiction charges the right rate on a $180 Premium sub."""

    @pytest.mark.parametrize("province,expected_gst,expected_qst,expected_hst,expected_total,label", [
        ("QC",   9.00, 17.96, 0.00,   206.96, "GST + QST (14.975%)"),
        ("ON",   0.00,  0.00, 23.40,  203.40, "HST (13%)"),
        ("NB",   0.00,  0.00, 27.00,  207.00, "HST (15%)"),
        ("NL",   0.00,  0.00, 27.00,  207.00, "HST (15%)"),
        ("NS",   0.00,  0.00, 27.00,  207.00, "HST (15%)"),
        ("PE",   0.00,  0.00, 27.00,  207.00, "HST (15%)"),
        ("AB",   9.00,  0.00, 0.00,   189.00, "GST (5%)"),
        ("BC",   9.00,  0.00, 0.00,   189.00, "GST (5%)"),
        ("SK",   9.00,  0.00, 0.00,   189.00, "GST (5%)"),
        ("MB",   9.00,  0.00, 0.00,   189.00, "GST (5%)"),
        ("YT",   9.00,  0.00, 0.00,   189.00, "GST (5%)"),
        ("NT",   9.00,  0.00, 0.00,   189.00, "GST (5%)"),
        ("NU",   9.00,  0.00, 0.00,   189.00, "GST (5%)"),
        ("INTL", 0.00,  0.00, 0.00,   180.00, "Exported Service (0%)"),
    ])
    def test_premium_180_by_province(self, province, expected_gst, expected_qst, expected_hst, expected_total, label):
        tax = calculate_taxes_for_recipient(180, province)
        assert tax["province"] == province
        assert tax["tax_label"] == label
        assert tax["gst_amount"] == pytest.approx(expected_gst, abs=CENT)
        assert tax["qst_amount"] == pytest.approx(expected_qst, abs=CENT)
        assert tax["hst_amount"] == pytest.approx(expected_hst, abs=CENT)
        assert tax["total_with_tax"] == pytest.approx(expected_total, abs=CENT)


class TestLegacyGstQstShimStillReturnsQC:
    """Legacy `calculate_gst_qst()` (no province arg) MUST still default to QC
    so pre-iter350 SendGrid templates & callers keep working."""

    def test_legacy_shim_defaults_to_qc(self):
        from services.tax_engine import calculate_gst_qst
        tax = calculate_gst_qst(100)
        assert tax["gst_amount"] == pytest.approx(5.00, abs=CENT)
        assert tax["qst_amount"] == pytest.approx(9.98, abs=CENT)
        assert tax["total_with_tax"] == pytest.approx(114.98, abs=CENT)


class TestNonCADCurrencyZeroTax:
    def test_usd_returns_zero_tax(self):
        tax = calculate_taxes_for_recipient(100, "QC", currency="USD")
        assert tax["gst_amount"] == 0.0
        assert tax["qst_amount"] == 0.0
        assert tax["hst_amount"] == 0.0
        assert tax["total_with_tax"] == 100
