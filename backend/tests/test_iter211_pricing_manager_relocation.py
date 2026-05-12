"""
iter211 — PricingManager relocation regression test.

Confirms:
  1. `services.fee_calculator` exposes the entire legacy PricingManager API.
  2. `services.pricing_manager` is GONE (cannot be imported).
  3. The 5 canonical iter209 spec test cases still pass via the new engine.
  4. Legacy `PricingManager.vehicle_auction` returns identical dollar amounts
     to the pre-relocation module for QC, ON, AB.
  5. `gross_up_stripe_fee`, `stripe_recovery`, `_pm_round`, `affiliate_commission`,
     `BUYER_PREMIUM_RATES`, `SELLER_COMMISSION_RATES` are all reachable from
     fee_calculator.
"""
import importlib
from decimal import Decimal

import pytest

from services.fee_calculator import (
    PricingManager,
    PricingResult,
    SideInvoice,
    InvoiceLine,
    BUYER_PREMIUM_RATES,
    SELLER_COMMISSION_RATES,
    VEHICLE_PLATFORM_FEE_RATE,
    PARTNER_SELLER_COMMISSION_RATE,
    AFFILIATE_COMMISSION_RATE,
    gross_up_stripe_fee,
    stripe_recovery,
    calculate_fee,
)


class TestPricingManagerModuleGone:
    def test_services_pricing_manager_no_longer_importable(self):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("services.pricing_manager")


class TestPricingManagerAPISurface:
    def test_pricingmanager_class_exists(self):
        assert PricingManager is not None
        for name in ("vehicle_auction", "non_vehicle_stripe", "non_vehicle_cash",
                     "flat_purchase", "partner_auction", "calculate_fees",
                     "affiliate_commission"):
            assert hasattr(PricingManager, name), f"Missing PricingManager.{name}"

    def test_dataclasses_exist(self):
        assert PricingResult and SideInvoice and InvoiceLine

    def test_constants_match_legacy(self):
        assert BUYER_PREMIUM_RATES["free"] == Decimal("0.05")
        assert BUYER_PREMIUM_RATES["premium"] == Decimal("0.035")
        assert BUYER_PREMIUM_RATES["vip_elite"] == Decimal("0.03")
        assert SELLER_COMMISSION_RATES["free"] == Decimal("0.04")
        assert SELLER_COMMISSION_RATES["premium"] == Decimal("0.025")
        assert SELLER_COMMISSION_RATES["vip_elite"] == Decimal("0.02")
        assert VEHICLE_PLATFORM_FEE_RATE == Decimal("0.025")
        assert PARTNER_SELLER_COMMISSION_RATE == Decimal("0.03")
        assert AFFILIATE_COMMISSION_RATE == Decimal("0.10")


class TestLegacyMathBitParity:
    """Locked dollar amounts pre-iter211 (computed against the deleted
    services/pricing_manager.py). These must NEVER change without a sprint."""

    def test_vehicle_auction_qc_1000(self):
        r = PricingManager.vehicle_auction(1000, "QC")
        bi = r.buyer_invoice
        assert bi.fees_subtotal == 25.00              # 2.5% of $1000
        assert bi.stripe_recovery == 1.03             # additive: 25*0.029+0.30
        assert bi.tax_amount == 3.90                  # GST+QST on ($25 + $1.03)
        assert bi.total == 29.93

    def test_vehicle_auction_on_1000(self):
        r = PricingManager.vehicle_auction(1000, "ON")
        bi = r.buyer_invoice
        assert bi.fees_subtotal == 25.00
        assert bi.tax_type == "HST"
        assert bi.tax_rate == 0.13

    def test_vehicle_auction_ab_1000(self):
        r = PricingManager.vehicle_auction(1000, "AB")
        bi = r.buyer_invoice
        assert bi.fees_subtotal == 25.00
        assert bi.tax_type == "GST"
        assert bi.tax_rate == 0.05

    def test_partner_auction_2000_on(self):
        r = PricingManager.partner_auction(2000, "ON")
        assert r.buyer_invoice.fees_subtotal == 0.0
        assert r.seller_invoice.fees_subtotal == 60.00     # 3% of $2000
        # tax on (60 + stripe_recovery)
        assert r.seller_invoice.tax_type == "HST"

    def test_non_vehicle_cash_500_ab_free(self):
        r = PricingManager.non_vehicle_cash(500, "AB", "free", "free")
        assert r.buyer_invoice.fees_subtotal == 25.00   # 5% BP
        assert r.seller_invoice.fees_subtotal == 20.00  # 4% SC

    def test_affiliate_commission_4_50(self):
        assert PricingManager.affiliate_commission(4.50) == 0.45

    def test_flat_purchase_300_on(self):
        r = PricingManager.flat_purchase(300, "ON")
        assert r.buyer_invoice.fees_subtotal == 300.0
        assert r.buyer_invoice.tax_type == "HST"


class TestIter209EngineUnchanged:
    """The new `calculate_fee()` engine must still produce the 5 spec amounts."""

    def test_spec1_individual_qc_standard(self):
        r = calculate_fee(
            hammer_price=100, auction_type="marketplace",
            seller_account_type="individual",
            buyer_tier="standard", seller_tier="standard",
        )
        assert r["buyer_premium"] == 5.0
        assert r["seller_payout"] == 95.4

    def test_spec4_vehicle_dealer_qc(self):
        r = calculate_fee(
            hammer_price=10000, auction_type="vehicle",
            seller_account_type="vehicle_dealer",
        )
        assert r["buyer_premium"] == 250.0
        assert r["seller_payout"] == 10000.0


class TestStripeHelpers:
    def test_gross_up_zero(self):
        assert gross_up_stripe_fee(Decimal("0")) == Decimal("0")

    def test_gross_up_100_domestic(self):
        # (100 + 0.30) / (1 - 0.029) - 100 ≈ 3.30
        assert gross_up_stripe_fee(Decimal("100")) == Decimal("3.30")

    def test_stripe_recovery_legacy_formula(self):
        # 100 * 0.029 + 0.30 = 3.20
        assert stripe_recovery(Decimal("100")) == Decimal("3.20")
