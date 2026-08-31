"""iter503 — Affiliate Center dashboard data-sync bug fix.

Covers:
  * `_resolve_effective_rate` treats commission_rate=0 as "no override"
    (revoked status is the correct way to zero out an affiliate).
  * `_has_custom_rate` returns True ONLY for intentional non-null,
    non-zero flat overrides.  A partner in tiers → False.
  * `_partner_tier_snapshot` reports tier_1 / tier_2 / None correctly.
  * `_partner_tier_snapshot` respects the flat-override escape hatch:
    when there's a real flat rate, partner_tier is None even if the
    user is enrolled in the program (so the "(custom rate)" tag lights
    up rather than the tier copy).
  * End-to-end Alex scenario: partner_program=true, tier_1_rate=0.5,
    tier_1_duration_months=12, tier_2_rate=0.05, start=recent →
    effective_rate=0.5, partner_tier='tier_1', has_custom_rate=False.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from routes.affiliate import (
    AFFILIATE_PROFIT_SHARE_RATE,
    _has_custom_rate,
    _partner_tier_snapshot,
    _resolve_effective_rate,
)


# ─── _resolve_effective_rate ────────────────────────────────────────

def test_zero_commission_rate_falls_through_for_partner():
    """The exact Alex bug: partner_program=true, commission_rate=0,
    tier_1_rate=0.5 → must return 0.5, not 0."""
    doc = {
        "commission_rate": 0.0,  # bad data from prior UI mishap
        "partner_program": True,
        "tier_1_rate": 0.5,
        "tier_1_duration_months": 12,
        "tier_2_rate": 0.05,
        "partnership_start_date": datetime.now(timezone.utc).isoformat(),
    }
    assert _resolve_effective_rate(doc) == 0.5


def test_zero_commission_rate_falls_through_for_non_partner():
    doc = {"commission_rate": 0.0}
    assert _resolve_effective_rate(doc) == AFFILIATE_PROFIT_SHARE_RATE


def test_positive_commission_rate_still_wins():
    doc = {
        "commission_rate": 0.10,
        "partner_program": True,
        "tier_1_rate": 0.5,
    }
    assert _resolve_effective_rate(doc) == 0.10


# ─── _has_custom_rate ────────────────────────────────────────────────

def test_has_custom_rate_true_for_positive_override():
    assert _has_custom_rate({"commission_rate": 0.05}) is True


@pytest.mark.parametrize("val", [None, 0, 0.0, "not-a-number"])
def test_has_custom_rate_false_for_missing_or_zero(val):
    assert _has_custom_rate({"commission_rate": val}) is False


def test_has_custom_rate_false_when_field_missing():
    assert _has_custom_rate({}) is False
    assert _has_custom_rate(None) is False


# ─── _partner_tier_snapshot ─────────────────────────────────────────

def test_snapshot_tier_1_within_window():
    doc = {
        "partner_program": True,
        "tier_1_rate": 0.5,
        "tier_1_duration_months": 12,
        "tier_2_rate": 0.05,
        "partnership_start_date": (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat(),
    }
    snap = _partner_tier_snapshot(doc)
    assert snap["partner_program"] is True
    assert snap["partner_tier"] == "tier_1"
    assert snap["tier_1_rate"] == 0.5
    assert snap["tier_1_duration_months"] == 12
    assert snap["tier_ends_at"] is not None
    assert snap["has_custom_rate"] is False


def test_snapshot_tier_2_after_window():
    doc = {
        "partner_program": True,
        "tier_1_rate": 0.5,
        "tier_1_duration_months": 6,
        "tier_2_rate": 0.05,
        "partnership_start_date": (
            datetime.now(timezone.utc) - timedelta(days=365)
        ).isoformat(),
    }
    snap = _partner_tier_snapshot(doc)
    assert snap["partner_tier"] == "tier_2"
    assert snap["tier_ends_at"] is None


def test_snapshot_flat_override_disables_tier():
    """When the admin sets a flat rate, the tier snapshot goes cold
    even for a partner user — the "(custom rate)" tag takes over."""
    doc = {
        "commission_rate": 0.10,
        "partner_program": True,
        "tier_1_rate": 0.5,
        "tier_1_duration_months": 12,
        "tier_2_rate": 0.05,
        "partnership_start_date": datetime.now(timezone.utc).isoformat(),
    }
    snap = _partner_tier_snapshot(doc)
    assert snap["partner_tier"] is None
    assert snap["has_custom_rate"] is True


def test_snapshot_non_partner_is_cold():
    snap = _partner_tier_snapshot({"partner_program": False})
    assert snap["partner_program"] is False
    assert snap["partner_tier"] is None
    assert snap["has_custom_rate"] is False


# ─── Alex end-to-end scenario ───────────────────────────────────────

def test_alex_end_to_end_scenario():
    """The exact record the user asked us to verify:
    partner_program=true, tier_1_rate=50%, tier_1_duration_months=12,
    tier_2_rate=5%, start=recent → dashboard must resolve to 50%."""
    doc = {
        "commission_rate": None,  # after data reconciliation
        "partner_program": True,
        "tier_1_rate": 0.5,
        "tier_1_duration_months": 12,
        "tier_2_rate": 0.05,
        "partnership_start_date": "2026-08-31T17:23:53.855455+00:00",
    }
    # If tested "now" while still inside the 12-month window from Aug 2026,
    # the effective rate is Tier 1 = 50%.
    now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert _resolve_effective_rate(doc, now=now) == 0.5
    snap = _partner_tier_snapshot(doc, now=now)
    assert snap["partner_program"] is True
    assert snap["partner_tier"] == "tier_1"
    assert snap["tier_1_rate"] == 0.5
    assert snap["tier_1_duration_months"] == 12
    assert snap["has_custom_rate"] is False


def test_alex_bad_zero_override_recovers_via_new_semantics():
    """Alex's exact bug: commission_rate=0.0 in DB from a bad UI save.
    With the iter503 fix, the tier schedule now takes over automatically
    without needing manual data cleanup."""
    doc = {
        "commission_rate": 0.0,  # bad data
        "partner_program": True,
        "tier_1_rate": 0.5,
        "tier_1_duration_months": 12,
        "tier_2_rate": 0.05,
        "partnership_start_date": "2026-08-31T17:23:53.855455+00:00",
    }
    now = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert _resolve_effective_rate(doc, now=now) == 0.5
    snap = _partner_tier_snapshot(doc, now=now)
    # Zero override no longer counts as a real override:
    assert snap["has_custom_rate"] is False
    assert snap["partner_tier"] == "tier_1"
