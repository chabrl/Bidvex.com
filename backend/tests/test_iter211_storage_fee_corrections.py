"""
iter211 (Part 1 P0) — Storage Fee Logic Correction tests.

The corrected model:
  • storage_facility + payment_method ∈ {cash, e_transfer, etransfer}:
        buyer pays facility direct, BidVex auto-charges facility card
        5% + GST/QST + Stripe gross-up (= $6.23 on a $100 hammer)
  • storage_facility + payment_method == "stripe":
        buyer pays ONLY hammer via Stripe, facility receives
        hammer minus (5% + GST/QST) = $94.25 on a $100 hammer

In BOTH cases: BUYER never pays a BidVex fee on storage auctions.
"""
import math
import pytest

from services.fee_calculator import calculate_fee


def _approx(actual, expected, tol=0.005):
    return math.isclose(actual, expected, abs_tol=tol)


class TestStorageCashPayment:
    def test_buyer_pays_zero_via_bidvex(self):
        fee = calculate_fee(
            hammer_price=100.0,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="cash",
        )
        assert fee["charge_buyer_via_stripe"] is False
        assert _approx(fee["buyer_total_charged"], 0.00)
        assert _approx(fee["buyer_premium"], 0.00)
        assert _approx(fee["buyer_stripe_fee"], 0.00)

    def test_facility_card_charged_6_23(self):
        fee = calculate_fee(
            hammer_price=100.0,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="cash",
        )
        # 5% commission + GST + QST + Stripe gross-up = $6.23
        total_facility = fee["seller_commission_total"] + fee["seller_stripe_fee"]
        assert _approx(total_facility, 6.23, tol=0.02), \
            f"Facility card charge expected $6.23, got ${total_facility}"
        assert _approx(fee["seller_commission"], 5.00)
        assert _approx(fee["seller_gst"], 0.25)
        assert _approx(fee["seller_qst"], 0.50)
        assert fee["charge_seller_card_separately"] is True

    def test_etransfer_aliases_to_cash_behavior(self):
        fee = calculate_fee(
            hammer_price=100.0,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="etransfer",
        )
        assert fee["charge_buyer_via_stripe"] is False
        assert fee["charge_seller_card_separately"] is True
        assert _approx(fee["seller_commission"], 5.00)

    def test_e_transfer_with_underscore_aliases_to_cash(self):
        fee = calculate_fee(
            hammer_price=100.0,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="e_transfer",
        )
        assert fee["charge_buyer_via_stripe"] is False
        assert fee["charge_seller_card_separately"] is True


class TestStorageStripePayment:
    def test_buyer_pays_exactly_hammer_via_stripe(self):
        fee = calculate_fee(
            hammer_price=100.0,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="stripe",
        )
        assert fee["charge_buyer_via_stripe"] is True
        # No BP, no buyer tax, no buyer Stripe gross-up
        assert _approx(fee["buyer_premium"], 0.00)
        assert _approx(fee["buyer_gst"], 0.00)
        assert _approx(fee["buyer_qst"], 0.00)
        assert _approx(fee["buyer_stripe_fee"], 0.00)
        assert _approx(fee["buyer_subtotal"], 100.00)
        assert _approx(fee["buyer_total_charged"], 100.00)

    def test_facility_payout_is_94_25(self):
        fee = calculate_fee(
            hammer_price=100.0,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="stripe",
        )
        # 100 - 5 (commission) - 0.25 (GST) - 0.50 (QST) = 94.25
        assert fee["charge_seller_card_separately"] is False
        assert _approx(fee["seller_payout"], 94.25), \
            f"Facility payout expected $94.25, got ${fee['seller_payout']}"
        assert _approx(fee["seller_commission"], 5.00)
        assert _approx(fee["seller_commission_total"], 5.75)
        assert _approx(fee["seller_stripe_fee"], 0.00)
        assert _approx(fee["bidvex_revenue"], 5.00)


class TestNonStorageUnaffected:
    """Make sure the corrected storage path didn't break the other 4 spec cases."""

    def test_individual_qc_100_still_yields_95_40_payout(self):
        fee = calculate_fee(
            hammer_price=100,
            auction_type="lots",
            seller_account_type="individual",
            buyer_tier="premium",
            seller_tier="standard",
        )
        assert _approx(fee["seller_payout"], 95.40)
        assert _approx(fee["buyer_subtotal"], 104.03)

    def test_vehicle_dealer_10000_still_yields_10000_payout(self):
        fee = calculate_fee(
            hammer_price=10_000,
            auction_type="vehicle",
            seller_account_type="vehicle_dealer",
        )
        assert _approx(fee["seller_payout"], 10_000.00)
        assert _approx(fee["buyer_premium"], 250.00)


class TestVariousHammerPrices:
    """Spot-check the formula at $250 and $1000 so we know rounding is stable."""

    @pytest.mark.parametrize("hammer,expected_facility_card_min,expected_facility_card_max", [
        (250.0, 15.05, 15.20),    # 5% of $250 = $12.50 + GST + QST + Stripe ≈ $15.12
        (1000.0, 59.45, 59.60),   # 5% of $1000 = $50 + GST + QST + Stripe ≈ $59.52
    ])
    def test_cash_facility_card_grows_with_hammer(self, hammer, expected_facility_card_min, expected_facility_card_max):
        fee = calculate_fee(
            hammer_price=hammer,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="cash",
        )
        total = fee["seller_commission_total"] + fee["seller_stripe_fee"]
        assert expected_facility_card_min <= total <= expected_facility_card_max, \
            f"Facility card on ${hammer} hammer was ${total}, expected ${expected_facility_card_min}-${expected_facility_card_max}"

    @pytest.mark.parametrize("hammer,expected_payout", [
        (250.0, 235.62),    # 250 - 12.50 - 0.63 (GST) - 1.25 (QST) = 235.62
        (1000.0, 942.50),   # 1000 - 50 - 2.50 - 4.99 (QST 9.975%) ≈ 942.51
    ])
    def test_stripe_facility_payout_grows_with_hammer(self, hammer, expected_payout):
        fee = calculate_fee(
            hammer_price=hammer,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method="stripe",
        )
        assert _approx(fee["seller_payout"], expected_payout, tol=0.05), \
            f"Stripe facility payout on ${hammer} was ${fee['seller_payout']}, expected ${expected_payout}"


class TestBuyerNeverPaysBidvexFee:
    """Lock down the core promise: a storage buyer never pays a BidVex fee."""

    @pytest.mark.parametrize("payment_method", ["cash", "etransfer", "e_transfer", "stripe"])
    @pytest.mark.parametrize("hammer", [50, 100, 500, 1000, 5000])
    def test_buyer_premium_is_zero_for_every_combo(self, payment_method, hammer):
        fee = calculate_fee(
            hammer_price=hammer,
            auction_type="storage",
            seller_account_type="storage_facility",
            payment_method=payment_method,
            buyer_tier="vip_elite",  # must be ignored
        )
        assert fee["buyer_premium"] == 0.0
        assert fee["buyer_gst"] == 0.0
        assert fee["buyer_qst"] == 0.0
