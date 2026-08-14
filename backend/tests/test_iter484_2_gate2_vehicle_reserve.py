"""
iter484.2 Gate 2 — Vehicle Reserve UI + Security Masking Tests
==============================================================

Verifies that the buyer-facing vehicle detail response NEVER emits the
raw ``reserve_price`` amount and correctly derives the three reserve
states: ``none``, ``met``, ``not_met``.

Also covers the multi-lot event masking (each lot).
"""
from __future__ import annotations
import pytest

from services.reserve_price_gate import (
    mask_reserve_for_buyer,
    mask_reserve_for_buyer_with_lots,
    _derive_reserve_state,
    is_reserve_met,
)


# ─────────────────────────────────────────────────────────────────
# 1. Derived state — no reserve
# ─────────────────────────────────────────────────────────────────
def test_derive_state_no_reserve():
    assert _derive_reserve_state(None, 100.0, None) == "none"
    assert _derive_reserve_state(0, 100.0, None) == "none"
    assert _derive_reserve_state(-5, 100.0, None) == "none"


# ─────────────────────────────────────────────────────────────────
# 2. Derived state — reserve met (via stored flag)
# ─────────────────────────────────────────────────────────────────
def test_derive_state_met_via_stored_flag():
    """The stored `reserve_met=True` MUST take precedence — it is
    authoritative because the bid handler sets it at the crossing
    bid, even if the current_bid snapshot is stale."""
    assert _derive_reserve_state(1000.0, 500.0, True) == "met"


# ─────────────────────────────────────────────────────────────────
# 3. Derived state — reserve met (via bid comparison)
# ─────────────────────────────────────────────────────────────────
def test_derive_state_met_via_bid():
    assert _derive_reserve_state(1000.0, 1000.0, None) == "met"
    assert _derive_reserve_state(1000.0, 1500.0, None) == "met"


# ─────────────────────────────────────────────────────────────────
# 4. Derived state — reserve NOT met
# ─────────────────────────────────────────────────────────────────
def test_derive_state_not_met():
    assert _derive_reserve_state(1000.0, 900.0, None) == "not_met"
    assert _derive_reserve_state(1000.0, 0, None) == "not_met"
    assert _derive_reserve_state(1000.0, None, None) == "not_met"


# ─────────────────────────────────────────────────────────────────
# 5. Mask — reserve amount is NEVER present on the returned dict
# ─────────────────────────────────────────────────────────────────
def test_mask_removes_reserve_price():
    doc = {
        "id": "v1",
        "title": "2024 BMW M3",
        "reserve_price": 45_000.0,
        "current_bid": 42_000.0,
        "starting_price": 30_000.0,
    }
    out = mask_reserve_for_buyer(doc)
    assert "reserve_price" not in out
    assert out["has_reserve"] is True
    assert out["reserve_state"] == "not_met"
    assert out["reserve_met"] is False
    # Original dict is unchanged (non-destructive shallow copy).
    assert doc["reserve_price"] == 45_000.0


def test_mask_removes_reserve_price_when_met():
    doc = {
        "id": "v2",
        "reserve_price": 40_000.0,
        "current_bid": 42_000.0,
        "reserve_met": True,
    }
    out = mask_reserve_for_buyer(doc)
    assert "reserve_price" not in out
    assert out["has_reserve"] is True
    assert out["reserve_state"] == "met"
    assert out["reserve_met"] is True


def test_mask_no_reserve_case():
    doc = {"id": "v3", "current_bid": 42_000.0}
    out = mask_reserve_for_buyer(doc)
    assert "reserve_price" not in out  # never leaks
    assert out["has_reserve"] is False
    assert out["reserve_state"] == "none"
    assert out["reserve_met"] is False


def test_mask_passthrough_on_non_dict():
    assert mask_reserve_for_buyer(None) is None
    assert mask_reserve_for_buyer("string") == "string"
    assert mask_reserve_for_buyer(42) == 42


# ─────────────────────────────────────────────────────────────────
# 6. Multi-lot event masking — every lot processed
# ─────────────────────────────────────────────────────────────────
def test_mask_multi_lot_event():
    event = {
        "id": "event1",
        "reserve_price": 0,  # top-level: none
        "lots": [
            {"id": "lot1", "reserve_price": 30_000.0, "current_bid": 25_000.0},
            {"id": "lot2", "reserve_price": 40_000.0, "current_bid": 45_000.0, "reserve_met": True},
            {"id": "lot3", "current_bid": 10_000.0},  # no reserve
        ],
    }
    out = mask_reserve_for_buyer_with_lots(event)
    # Top-level
    assert "reserve_price" not in out
    assert out["reserve_state"] == "none"
    # Per lot
    lots = out["lots"]
    assert len(lots) == 3
    for lot in lots:
        assert "reserve_price" not in lot, f"amount leaked on lot {lot['id']}"
    assert lots[0]["reserve_state"] == "not_met"
    assert lots[0]["has_reserve"] is True
    assert lots[1]["reserve_state"] == "met"
    assert lots[1]["has_reserve"] is True
    assert lots[2]["reserve_state"] == "none"
    assert lots[2]["has_reserve"] is False


# ─────────────────────────────────────────────────────────────────
# 7. Regression on existing `is_reserve_met` (settlement path)
# ─────────────────────────────────────────────────────────────────
def test_is_reserve_met_unaffected_by_gate2():
    """Sanity — the settlement gate must stay bit-for-bit unchanged."""
    assert is_reserve_met(500.0, 1000.0) is False
    assert is_reserve_met(1000.0, 1000.0) is True
    assert is_reserve_met(1500.0, 1000.0) is True
    assert is_reserve_met(500.0, None) is True
    assert is_reserve_met(500.0, 0) is True
