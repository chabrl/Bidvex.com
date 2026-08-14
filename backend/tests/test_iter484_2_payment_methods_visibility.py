"""
iter484.2 — Payment Methods Visibility Tests
============================================

Regression tests for the buyer-facing accepted_payment_methods pipeline.

Root cause reference: /app/docs/PAYMENT_METHODS_RCA_REPORT.md
Post-bid lock audit:  /app/docs/POST_BID_LOCK_AUDIT.md

Focus areas:
  1. `MultiItemListing` Pydantic model must NOT strip
     `accepted_payment_methods` / `_snapshot` / `_locked_at`.
  2. `Listing` (single-item) model regression — must still emit the field.
  3. `VehicleListing` model regression — must still emit the field.
  4. Snapshot precedence — locked snapshot wins over live list on read.
  5. Post-bid guard — 409 when seller tries to edit after first bid.
  6. Vehicle bid path snapshot idempotency (dormant but wired).
"""
from __future__ import annotations
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List

from models.auction_models import Listing, MultiItemListing
from models.vehicle_models import VehicleListing
from services.seller_payment_methods_service import (
    effective_methods,
    is_locked,
    snapshot_at_first_bid,
    guard_edit,
    assert_selection_allowed,
    PaymentMethodsLockedError,
    PaymentMethodNotAcceptedError,
)


# ─────────────────────────────────────────────────────────────────────
# 1. MultiItemListing model — the ROOT CAUSE fix
# ─────────────────────────────────────────────────────────────────────
def _minimal_multi_item_doc(**overrides) -> Dict[str, Any]:
    """Minimal valid MultiItemListing doc for round-trip serialization tests."""
    base = {
        "id": "iter484_test_multi",
        "seller_id": "seller_iter484",
        "title": "Test Multi Auction",
        "description": "test",
        "category": "test",
        "location": "Montreal, QC",
        "city": "Montreal",
        "region": "QC",
        "auction_end_date": datetime.now(timezone.utc),
        "lots": [
            {
                "lot_number": 1,
                "title": "Lot 1",
                "description": "d",
                "quantity": 1,
                "starting_price": 10.0,
                "current_price": 10.0,
                "condition": "good",
            }
        ],
    }
    base.update(overrides)
    return base


def test_multi_item_listing_emits_accepted_payment_methods():
    """Regression on ROOT CAUSE Defect A — Pydantic must NOT drop the field."""
    doc = _minimal_multi_item_doc(
        accepted_payment_methods=["stripe", "etransfer", "cash", "cheque"],
    )
    m = MultiItemListing(**doc)
    body = m.model_dump()
    assert body.get("accepted_payment_methods") == ["stripe", "etransfer", "cash", "cheque"], (
        "MultiItemListing must declare `accepted_payment_methods` so Pydantic's "
        "`extra=ignore` doesn't silently drop it — see /app/docs/PAYMENT_METHODS_RCA_REPORT.md §2"
    )


def test_multi_item_listing_emits_snapshot_when_locked():
    """Snapshot MUST reach the buyer response (used to render locked badge + accurate methods)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = _minimal_multi_item_doc(
        accepted_payment_methods=["stripe", "cash", "etransfer", "cheque"],
        accepted_payment_methods_snapshot=["stripe", "cash"],
        accepted_payment_methods_locked_at=now_iso,
    )
    m = MultiItemListing(**doc)
    body = m.model_dump()
    assert body.get("accepted_payment_methods_snapshot") == ["stripe", "cash"]
    assert body.get("accepted_payment_methods_locked_at") is not None


def test_multi_item_listing_none_when_missing():
    """Backward-compat: pre-P4A rows without the field must serialize as None."""
    doc = _minimal_multi_item_doc()
    m = MultiItemListing(**doc)
    body = m.model_dump()
    assert body.get("accepted_payment_methods") is None
    assert body.get("accepted_payment_methods_snapshot") is None
    assert body.get("accepted_payment_methods_locked_at") is None


# ─────────────────────────────────────────────────────────────────────
# 2. Listing (single-item) — regression on the already-declared field
# ─────────────────────────────────────────────────────────────────────
def _minimal_single_doc(**overrides) -> Dict[str, Any]:
    base = {
        "seller_id": "seller_iter484",
        "title": "Test Single",
        "description": "d",
        "category": "test",
        "condition": "good",
        "starting_price": 10.0,
        "current_price": 10.0,
        "location": "Montreal, QC",
        "auction_end_date": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return base


def test_single_item_listing_still_emits_field():
    doc = _minimal_single_doc(accepted_payment_methods=["stripe", "cheque"])
    m = Listing(**doc)
    body = m.model_dump()
    assert body.get("accepted_payment_methods") == ["stripe", "cheque"]


# ─────────────────────────────────────────────────────────────────────
# 3. VehicleListing — regression on the newly-added declaration
# ─────────────────────────────────────────────────────────────────────
def test_vehicle_listing_model_declares_apm():
    """Sanity: VehicleListing model has the field declared (iter484.2 add)."""
    fields = VehicleListing.model_fields
    assert "accepted_payment_methods" in fields
    assert "accepted_payment_methods_snapshot" in fields
    assert "accepted_payment_methods_locked_at" in fields


# ─────────────────────────────────────────────────────────────────────
# 4. Snapshot precedence — effective_methods() invariant
# ─────────────────────────────────────────────────────────────────────
def test_effective_methods_snapshot_wins():
    listing = {
        "id": "x",
        "accepted_payment_methods": ["stripe", "cash", "etransfer", "cheque"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    assert effective_methods(listing) == ["stripe"], (
        "Snapshot must win over live list (mirrors bidder-terms at first bid)."
    )


def test_effective_methods_live_when_no_snapshot():
    listing = {"id": "x", "accepted_payment_methods": ["stripe", "cheque"]}
    assert effective_methods(listing) == ["stripe", "cheque"]


def test_effective_methods_legacy_fallback():
    listing = {"id": "x", "payment_method": "stripe"}
    assert effective_methods(listing) == ["stripe"]


# ─────────────────────────────────────────────────────────────────────
# 5. Post-bid guard — cannot change methods once first bid is in
# ─────────────────────────────────────────────────────────────────────
def test_guard_edit_raises_when_locked():
    listing = {
        "id": "x",
        "accepted_payment_methods": ["stripe"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    with pytest.raises(PaymentMethodsLockedError):
        guard_edit(listing, ["stripe", "cash"])


def test_guard_edit_allowed_pre_bid():
    listing = {"id": "x", "accepted_payment_methods": ["stripe"]}
    result = guard_edit(listing, ["stripe", "cash"])
    assert result == ["stripe", "cash"]


# ─────────────────────────────────────────────────────────────────────
# 6. Snapshot at first bid — idempotency + shape
# ─────────────────────────────────────────────────────────────────────
def test_snapshot_at_first_bid_produces_update():
    listing = {"id": "x", "accepted_payment_methods": ["stripe", "cash"]}
    upd = snapshot_at_first_bid(listing)
    assert upd is not None
    assert upd["accepted_payment_methods_snapshot"] == ["stripe", "cash"]
    assert "accepted_payment_methods_locked_at" in upd


def test_snapshot_at_first_bid_idempotent_when_already_locked():
    listing = {
        "id": "x",
        "accepted_payment_methods": ["stripe", "cash"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    assert snapshot_at_first_bid(listing) is None, (
        "Idempotent: an already-locked listing must return None so the "
        "route doesn't overwrite the immutable snapshot on repeat calls."
    )


# ─────────────────────────────────────────────────────────────────────
# 7. Buyer selection gate honours snapshot
# ─────────────────────────────────────────────────────────────────────
def test_buyer_selection_rejected_when_not_in_snapshot():
    listing = {
        "id": "x",
        "accepted_payment_methods": ["stripe", "cash", "cheque"],
        "accepted_payment_methods_snapshot": ["stripe"],  # locked to stripe only
    }
    with pytest.raises(PaymentMethodNotAcceptedError):
        assert_selection_allowed(listing, "cash")


def test_buyer_selection_ok_when_in_snapshot():
    listing = {
        "id": "x",
        "accepted_payment_methods": ["stripe"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    assert assert_selection_allowed(listing, "stripe") == "stripe"


# ─────────────────────────────────────────────────────────────────────
# 8. is_locked() invariant
# ─────────────────────────────────────────────────────────────────────
def test_is_locked_when_snapshot_populated():
    assert is_locked({"accepted_payment_methods_snapshot": ["stripe"]}) is True
    assert is_locked({"accepted_payment_methods_snapshot": []}) is False
    assert is_locked({"accepted_payment_methods": ["stripe"]}) is False
    assert is_locked({}) is False
