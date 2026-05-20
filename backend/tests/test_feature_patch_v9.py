"""
FEATURE PATCH v9 — Backend pytest coverage for:
  1. Admin Edit Auction End Time
  3. AI Watchdog Admin Review Flow
  4. Quantity field for listings + broker_fee_engine math
"""
from __future__ import annotations

import asyncio
import importlib
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from services.broker_fee_engine import (
    calculate_broker_transaction,
    BIDVEX_PLATFORM_FEE_RATE,
)


# ── Feature 4: Quantity-aware broker_fee_engine ─────────────────────────

def test_quantity_default_one_no_multiplier_keeps_v7_math():
    """When quantity=1 (default), the v7 math output is unchanged."""
    r = calculate_broker_transaction(
        hammer_price=15_000.0,
        broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500.0},
        buyer_province="QC",
    )
    assert r["quantity"] == 1
    assert r["multiply_hammer_by_quantity"] is False
    assert r["hammer_price"] == 15_000.0
    assert r["base_amount"] == 15_000.0
    assert r["hammer_total"] == 15_000.0
    # platform_fee = 2.5% * 15_000 = 375
    assert r["platform_fee"] == 375.00
    assert r["broker_fee"] == 500.00
    # Hammer NEVER touches Stripe — confirm Stripe charge excludes hammer
    assert r["stripe_total_charged"] < r["hammer_price"]
    assert r["summary"]["buyer_pays_direct"] == 15_000.0
    assert r["summary"]["buyer_pays_stripe"] == r["stripe_total_charged"]


def test_quantity_with_multiplier_scales_base_amount_and_fees():
    """quantity=3 + multiplier=True → platform fee + broker fee scaled."""
    r = calculate_broker_transaction(
        hammer_price=10_000.0,
        broker_fee_structure={"type": "percentage", "percentage_rate": 0.10},
        buyer_province="QC",
        quantity=3,
        multiply_hammer_by_quantity=True,
    )
    assert r["quantity"] == 3
    assert r["multiply_hammer_by_quantity"] is True
    assert r["base_amount"] == 30_000.0
    assert r["hammer_total"] == 30_000.0
    # platform_fee = 2.5% * 30_000 = 750
    assert r["platform_fee"] == 750.00
    # broker_fee = 10% * 30_000 = 3000
    assert r["broker_fee"] == 3_000.00
    # Subtotal taxable = 750 + 3000 = 3750
    assert r["subtotal_taxable"] == 3_750.00
    # buyer_pays_direct (hammer) = 30_000 — paid OUTSIDE Stripe
    assert r["summary"]["buyer_pays_direct"] == 30_000.0
    # Stripe charge MUST NOT include hammer
    assert r["stripe_total_charged"] < 30_000.0
    # buyer_total_cost = stripe + hammer
    assert abs(r["summary"]["buyer_total_cost"] - (r["stripe_total_charged"] + 30_000.0)) < 0.02


def test_quantity_without_multiplier_does_not_scale_fees():
    """quantity=5 but multiplier=False → base_amount=hammer_price (single-unit)."""
    r = calculate_broker_transaction(
        hammer_price=10_000.0,
        broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500.0},
        buyer_province="ON",
        quantity=5,
        multiply_hammer_by_quantity=False,
    )
    assert r["quantity"] == 5
    assert r["multiply_hammer_by_quantity"] is False
    assert r["base_amount"] == 10_000.0
    assert r["hammer_total"] == 10_000.0
    assert r["platform_fee"] == 250.00  # 2.5% of 10_000


def test_quantity_one_multiplier_true_is_idempotent():
    """quantity=1 + multiplier=True → still single-unit (multiplier=1)."""
    r = calculate_broker_transaction(
        hammer_price=10_000.0,
        broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500.0},
        buyer_province="ON",
        quantity=1,
        multiply_hammer_by_quantity=True,
    )
    # The output normalises this: qty=1 means multiplier ineffective
    assert r["quantity"] == 1
    assert r["multiply_hammer_by_quantity"] is False
    assert r["base_amount"] == 10_000.0


def test_hammer_never_in_stripe_with_quantity():
    """LEGAL CRITICAL — vehicle hammer NEVER touches Stripe even at qty > 1."""
    r = calculate_broker_transaction(
        hammer_price=8_000.0,
        broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500.0},
        buyer_province="QC",
        quantity=10,
        multiply_hammer_by_quantity=True,
    )
    # base_amount = 80,000
    assert r["base_amount"] == 80_000.0
    # Hammer total (paid direct) = 80,000 — outside Stripe
    assert r["summary"]["buyer_pays_direct"] == 80_000.0
    # Stripe charge is service fees + taxes only — must be a small fraction of hammer
    assert r["stripe_total_charged"] < 5_000.0
    # platform_fee = 2.5% * 80_000 = 2_000
    assert r["platform_fee"] == 2_000.00


def test_invalid_quantity_clamps_to_one():
    for bad in (0, -1, None):
        r = calculate_broker_transaction(
            hammer_price=10_000.0,
            broker_fee_structure={"type": "fixed", "fixed_amount_cad": 500.0},
            buyer_province="ON",
            quantity=bad,
            multiply_hammer_by_quantity=True,
        )
        assert r["quantity"] == 1
        assert r["base_amount"] == 10_000.0


# ── Feature 1 + Feature 3: route registration check ─────────────────────

def test_end_time_router_imports():
    mod = importlib.import_module("routes.admin_end_time")
    assert hasattr(mod, "admin_end_time_router")
    paths = {r.path for r in mod.admin_end_time_router.routes}
    assert "/admin/auctions/{listing_id}/end-time" in paths
    assert "/admin/auctions/{listing_id}/end-time-history" in paths


def test_ai_review_router_imports():
    mod = importlib.import_module("routes.admin_ai_review")
    assert hasattr(mod, "ai_review_router")
    paths = {r.path for r in mod.ai_review_router.routes}
    assert "/listings/{listing_id}/flag-for-ai-review" in paths
    assert "/admin/listing-reviews" in paths
    assert "/admin/listing-reviews/{review_id}/approve" in paths
    assert "/admin/listing-reviews/{review_id}/reject" in paths
    assert "/listings/{listing_id}/correct-category" in paths
    assert "/listings/{listing_id}/withdraw-from-review" in paths


# ── Feature 4: ListingCreate model accepts quantity + multiplier ────────

def test_listing_create_model_accepts_quantity_fields():
    from models import ListingCreate
    payload = {
        "title": "Lot of 5 chairs",
        "description": "Five matching dining chairs",
        "category": "Furniture",
        "condition": "good",
        "starting_price": 50.0,
        "location": "Sherbrooke, QC",
        "city": "Sherbrooke",
        "region": "QC",
        "auction_end_date": datetime.now(timezone.utc) + timedelta(days=5),
        "quantity": 5,
        "multiply_hammer_by_quantity": True,
    }
    obj = ListingCreate(**payload)
    assert obj.quantity == 5
    assert obj.multiply_hammer_by_quantity is True


def test_listing_create_model_quantity_defaults_to_one():
    from models import ListingCreate
    obj = ListingCreate(
        title="Single chair",
        description="One chair",
        category="Furniture",
        condition="good",
        starting_price=20.0,
        location="Sherbrooke, QC",
        city="Sherbrooke",
        region="QC",
        auction_end_date=datetime.now(timezone.utc) + timedelta(days=3),
    )
    assert obj.quantity == 1
    assert obj.multiply_hammer_by_quantity is False


def test_lot_model_supports_multiply_flag():
    from models.auction_models import Lot
    lot = Lot(
        lot_number=1,
        title="Sample",
        description="Sample lot",
        quantity=10,
        starting_price=15.0,
        current_price=15.0,
        condition="good",
        multiply_hammer_by_quantity=True,
    )
    assert lot.multiply_hammer_by_quantity is True
    assert lot.quantity == 10
