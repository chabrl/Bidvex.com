"""
iter482 P4A — Foundation tests
================================

Coverage:
  * services/payment_methods_registry.py — canonical constants + aliases
  * services/seller_payment_methods_service.py — snapshot + guards
  * models/auction_models.py + storage_auction.py + vehicle_models.py —
    Pydantic field validation
  * scripts/iter482_p4a_backfill_accepted_payment_methods.py — pure
    helper functions

Guardrails: no live database, no Stripe calls, no side effects.

Run:
    cd /app/backend
    python -m pytest tests/test_iter482_p4a_foundation.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from services.payment_methods_registry import (  # noqa: E402
    ALL_METHODS,
    STRIPE, ETRANSFER, CASH, CHEQUE,
    STRIPE_RAIL_METHODS, OFFLINE_METHODS,
    normalise, normalise_list,
    is_offline, carries_stripe_rail,
    InvalidPaymentMethodError,
)
from services.seller_payment_methods_service import (  # noqa: E402
    effective_methods, is_locked,
    validate_new_declaration, guard_edit,
    snapshot_at_first_bid, assert_selection_allowed,
    PaymentMethodsLockedError,
    PaymentMethodNotAcceptedError,
    PaymentMethodsMissingError,
)


# ═════════════════════════════════════════════════════════════════════
# Registry — canonical constants + aliases
# ═════════════════════════════════════════════════════════════════════

def test_registry_has_exactly_four_methods():
    assert ALL_METHODS == ["stripe", "etransfer", "cash", "cheque"]
    assert {STRIPE, ETRANSFER, CASH, CHEQUE} == set(ALL_METHODS)


def test_registry_partitions_online_and_offline():
    assert STRIPE_RAIL_METHODS == {STRIPE}
    assert OFFLINE_METHODS == {ETRANSFER, CASH, CHEQUE}
    assert STRIPE_RAIL_METHODS.isdisjoint(OFFLINE_METHODS)
    assert STRIPE_RAIL_METHODS | OFFLINE_METHODS == set(ALL_METHODS)


@pytest.mark.parametrize("raw,expected", [
    ("stripe",       STRIPE),
    ("Stripe",       STRIPE),
    ("STRIPE",       STRIPE),
    ("stripe_card",  STRIPE),
    ("card",         STRIPE),
    ("etransfer",    ETRANSFER),
    ("e_transfer",   ETRANSFER),
    ("e-transfer",   ETRANSFER),
    ("E-Transfer",   ETRANSFER),
    ("cash",         CASH),
    ("Cash",         CASH),
    ("cheque",       CHEQUE),
    ("Check",        CHEQUE),
    ("check",        CHEQUE),
])
def test_normalise_valid_inputs(raw, expected):
    assert normalise(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "bitcoin", "paypal", "  ", "unknown"])
def test_normalise_rejects_invalid_inputs(raw):
    with pytest.raises((InvalidPaymentMethodError, TypeError)):
        normalise(raw)


def test_normalise_list_dedupes_and_canonicalises():
    assert normalise_list(["stripe", "Stripe", "card"]) == [STRIPE]
    assert normalise_list(["cash", "e-transfer", "cash", "check"]) == [CASH, ETRANSFER, CHEQUE]


def test_normalise_list_preserves_first_occurrence_order():
    assert normalise_list(["cheque", "stripe", "cash"]) == [CHEQUE, STRIPE, CASH]


def test_normalise_list_empty_rejected():
    with pytest.raises(ValueError):
        normalise_list([])
    with pytest.raises(ValueError):
        normalise_list(None)


def test_helpers_is_offline_and_carries_stripe_rail():
    assert is_offline("cash") is True
    assert is_offline("cheque") is True
    assert is_offline("etransfer") is True
    assert is_offline("stripe") is False
    assert carries_stripe_rail("stripe") is True
    assert carries_stripe_rail("cash") is False


# ═════════════════════════════════════════════════════════════════════
# Seller payment methods service — resolution + guards
# ═════════════════════════════════════════════════════════════════════

def test_effective_methods_prefers_snapshot_over_live():
    listing = {
        "accepted_payment_methods": ["stripe", "cash"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    assert effective_methods(listing) == ["stripe"]


def test_effective_methods_uses_live_when_no_snapshot():
    listing = {"accepted_payment_methods": ["cash", "cheque"]}
    assert effective_methods(listing) == ["cash", "cheque"]


def test_effective_methods_falls_back_to_legacy_singleton():
    # Pre-P4 rows have only `payment_method` singleton
    listing = {"payment_method": "e-transfer"}
    assert effective_methods(listing) == ["etransfer"]


def test_effective_methods_raises_when_no_data():
    with pytest.raises(PaymentMethodsMissingError):
        effective_methods({"id": "orphan_row"})


def test_is_locked_true_only_when_snapshot_set():
    assert is_locked({"accepted_payment_methods_snapshot": ["stripe"]}) is True
    assert is_locked({"accepted_payment_methods": ["stripe"]}) is False
    assert is_locked({}) is False


def test_validate_new_declaration_canonicalises():
    assert validate_new_declaration(["Stripe", "e-transfer"]) == [STRIPE, ETRANSFER]


def test_validate_new_declaration_rejects_empty():
    with pytest.raises(ValueError):
        validate_new_declaration([])


def test_guard_edit_allows_pre_bid_edit():
    listing = {"accepted_payment_methods": ["stripe"]}
    assert guard_edit(listing, ["stripe", "cash"]) == [STRIPE, CASH]


def test_guard_edit_blocks_post_bid_edit():
    listing = {
        "accepted_payment_methods": ["stripe"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    with pytest.raises(PaymentMethodsLockedError):
        guard_edit(listing, ["stripe", "cash"])


def test_snapshot_at_first_bid_produces_update_dict():
    listing = {"accepted_payment_methods": ["stripe", "cash"]}
    upd = snapshot_at_first_bid(listing)
    assert upd is not None
    assert upd["accepted_payment_methods_snapshot"] == [STRIPE, CASH]
    assert "accepted_payment_methods_locked_at" in upd
    # Idempotent: applying twice returns None
    listing.update(upd)
    assert snapshot_at_first_bid(listing) is None


def test_snapshot_falls_back_to_legacy_singleton():
    listing = {"payment_method": "cash"}
    upd = snapshot_at_first_bid(listing)
    assert upd is not None
    assert upd["accepted_payment_methods_snapshot"] == [CASH]


def test_snapshot_raises_when_no_data():
    with pytest.raises(PaymentMethodsMissingError):
        snapshot_at_first_bid({"id": "orphan"})


# ═════════════════════════════════════════════════════════════════════
# Buyer-selection gate
# ═════════════════════════════════════════════════════════════════════

def test_assert_selection_allowed_ok():
    listing = {"accepted_payment_methods": ["stripe", "cash"]}
    assert assert_selection_allowed(listing, "Stripe") == STRIPE
    assert assert_selection_allowed(listing, "cash") == CASH


def test_assert_selection_rejected_when_not_in_list():
    listing = {"accepted_payment_methods": ["stripe"]}
    with pytest.raises(PaymentMethodNotAcceptedError):
        assert_selection_allowed(listing, "cash")


def test_assert_selection_uses_snapshot_after_lock():
    # After lock, live edits are ignored — buyer sees the snapshot terms
    listing = {
        "accepted_payment_methods":          ["stripe", "cash"],  # live (would allow cash)
        "accepted_payment_methods_snapshot": ["stripe"],           # frozen at first bid
    }
    with pytest.raises(PaymentMethodNotAcceptedError):
        assert_selection_allowed(listing, "cash")
    assert assert_selection_allowed(listing, "stripe") == STRIPE


def test_assert_selection_rejects_invalid_method():
    listing = {"accepted_payment_methods": ["stripe"]}
    with pytest.raises(PaymentMethodNotAcceptedError):
        assert_selection_allowed(listing, "paypal")


# ═════════════════════════════════════════════════════════════════════
# Model validation — Pydantic
# ═════════════════════════════════════════════════════════════════════

def test_listing_create_model_canonicalises_accepted_methods():
    from models.auction_models import ListingCreate
    from datetime import datetime, timezone
    m = ListingCreate(
        title="test", description="test", category="misc", condition="new",
        starting_price=1.0, location="Test", city="Test", region="QC",
        auction_end_date=datetime.now(timezone.utc),
        accepted_payment_methods=["Stripe", "e-transfer", "Cash"],
    )
    assert m.accepted_payment_methods == [STRIPE, ETRANSFER, CASH]


def test_listing_create_rejects_bad_method():
    from models.auction_models import ListingCreate
    from datetime import datetime, timezone
    with pytest.raises(Exception):  # Pydantic ValidationError wraps ours
        ListingCreate(
            title="test", description="test", category="misc", condition="new",
            starting_price=1.0, location="Test", city="Test", region="QC",
            auction_end_date=datetime.now(timezone.utc),
            accepted_payment_methods=["bitcoin"],
        )


def test_listing_create_omit_is_permitted():
    """accepted_payment_methods is optional at the Pydantic layer
    (route layer enforces it going forward, but pre-P4 rows can still
    be constructed without)."""
    from models.auction_models import ListingCreate
    from datetime import datetime, timezone
    m = ListingCreate(
        title="test", description="test", category="misc", condition="new",
        starting_price=1.0, location="Test", city="Test", region="QC",
        auction_end_date=datetime.now(timezone.utc),
    )
    assert m.accepted_payment_methods is None


def test_multi_item_listing_create_validates():
    from models.auction_models import MultiItemListingCreate, Lot
    from datetime import datetime, timezone
    m = MultiItemListingCreate(
        title="t", description="d", location="l", city="c", region="QC",
        auction_end_date=datetime.now(timezone.utc),
        lots=[Lot(
            lot_number=1, title="a", description="a", quantity=1,
            starting_price=1.0, current_price=1.0, condition="new",
        )],
        accepted_payment_methods=["e-transfer", "cheque"],
    )
    assert m.accepted_payment_methods == [ETRANSFER, CHEQUE]


def test_storage_auction_create_validates():
    from models.storage_auction import StorageAuctionCreate
    from datetime import datetime, timezone, timedelta
    m = StorageAuctionCreate(
        unit_number="A1", unit_size="10x10", unit_type="indoor",
        description_en="A test storage locker",
        starting_price=1.0,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(days=1),
        accepted_payment_methods=["Stripe", "cash"],
    )
    assert m.accepted_payment_methods == [STRIPE, CASH]


def test_vehicle_listing_create_validates():
    from models.vehicle_models import VehicleListingCreate
    from datetime import datetime, timezone, timedelta
    m = VehicleListingCreate(
        vin="1HGCM82633A004352",  # valid VIN format
        year=2020, make="Honda", model="Accord", trim="EX", body_type="sedan",
        transmission="automatic", drivetrain="fwd", fuel_type="gasoline",
        exterior_color="Black", interior_color="Black",
        ownership_status="owned", title_status="clean",
        lien_status="clear", condition_report={"is_running": True, "grade": "good"},
        mileage=50000,
        title="A test listing", description="A test listing description",
        starting_price=1.0, reserve_price=None, buy_now_price=None,
        requires_deposit=False,
        auction_type="timed", start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc) + timedelta(days=1),
        location_city="Test", location_province="QC",
        location_postal_code="H1A 1A1",
        accepted_payment_methods=["cash", "cheque"],
    )
    assert m.accepted_payment_methods == [CASH, CHEQUE]


# ═════════════════════════════════════════════════════════════════════
# Backfill helper — pure function (no DB)
# ═════════════════════════════════════════════════════════════════════

def test_backfill_default_methods_prefers_legacy_singleton():
    from scripts.iter482_p4a_backfill_accepted_payment_methods import _default_methods
    assert _default_methods("stripe")    == [STRIPE]
    assert _default_methods("e-transfer")== [ETRANSFER]
    assert _default_methods("cash")      == [CASH]


def test_backfill_default_methods_uses_stripe_when_missing():
    from scripts.iter482_p4a_backfill_accepted_payment_methods import _default_methods
    assert _default_methods(None) == [STRIPE]
    assert _default_methods("")   == [STRIPE]


def test_backfill_default_methods_falls_back_on_invalid_legacy():
    from scripts.iter482_p4a_backfill_accepted_payment_methods import _default_methods
    assert _default_methods("bitcoin") == [STRIPE]
    assert _default_methods("paypal")  == [STRIPE]


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v"], check=False)
