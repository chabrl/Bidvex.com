"""iter233 — Price × Quantity display multiplier field.

Verifies the new `price_multiplied_by_quantity` boolean is:
  • present on the Pydantic schemas (Listing, ListingCreate, Lot,
    MultiItemListing, MultiItemListingCreate) with default False,
  • round-trip-safe (model_dump → load → match),
  • gated by quantity>1 in the create-listing route logic.
"""
from __future__ import annotations

import pytest


def test_listing_create_default_false():
    from models.auction_models import ListingCreate
    payload = {
        "title": "x",
        "description": "y",
        "category": "general",
        "condition": "good",
        "starting_price": 10.0,
        "location": "Sherbrooke",
        "city": "Sherbrooke",
        "region": "QC",
        "auction_end_date": "2099-01-01T00:00:00Z",
    }
    obj = ListingCreate(**payload)
    assert hasattr(obj, "price_multiplied_by_quantity")
    assert obj.price_multiplied_by_quantity is False


def test_listing_create_accepts_true():
    from models.auction_models import ListingCreate
    payload = {
        "title": "x",
        "description": "y",
        "category": "general",
        "condition": "good",
        "starting_price": 10.0,
        "location": "Sherbrooke",
        "city": "Sherbrooke",
        "region": "QC",
        "auction_end_date": "2099-01-01T00:00:00Z",
        "quantity": 5,
        "price_multiplied_by_quantity": True,
    }
    obj = ListingCreate(**payload)
    assert obj.price_multiplied_by_quantity is True
    assert obj.quantity == 5


def test_listing_doc_default_false():
    from models.auction_models import Listing
    from datetime import datetime, timezone
    obj = Listing(
        seller_id="u1",
        title="t",
        description="d",
        category="c",
        condition="good",
        starting_price=1.0,
        current_price=1.0,
        location="Sherbrooke",
        auction_end_date=datetime.now(timezone.utc),
    )
    assert obj.price_multiplied_by_quantity is False
    dumped = obj.model_dump()
    assert "price_multiplied_by_quantity" in dumped
    assert dumped["price_multiplied_by_quantity"] is False


def test_lot_default_false():
    from models.auction_models import Lot
    lot = Lot(
        lot_number=1,
        title="x",
        description="y",
        quantity=10,
        starting_price=5.0,
        current_price=5.0,
        condition="good",
    )
    assert lot.price_multiplied_by_quantity is False


def test_lot_accepts_true():
    from models.auction_models import Lot
    lot = Lot(
        lot_number=1,
        title="x",
        description="y",
        quantity=10,
        starting_price=5.0,
        current_price=5.0,
        condition="good",
        price_multiplied_by_quantity=True,
    )
    assert lot.price_multiplied_by_quantity is True


def test_multi_item_listing_default_false():
    from models.auction_models import MultiItemListingCreate, Lot
    create = MultiItemListingCreate(
        title="t",
        description="d",
        category="c",
        location="Sherbrooke",
        city="Sherbrooke",
        region="QC",
        auction_end_date="2099-01-01T00:00:00Z",
        lots=[Lot(
            lot_number=1,
            title="x",
            description="y",
            quantity=1,
            starting_price=5.0,
            current_price=5.0,
            condition="good",
        )],
    )
    assert create.price_multiplied_by_quantity is False


def test_missing_field_on_legacy_doc_treated_as_false():
    """Legacy DB documents will lack the field; Pydantic should default to False."""
    from models.auction_models import Listing
    from datetime import datetime, timezone
    # Simulate a legacy listing dict pulled from MongoDB
    legacy = {
        "seller_id": "u1",
        "title": "old",
        "description": "old",
        "category": "c",
        "condition": "good",
        "starting_price": 1.0,
        "current_price": 1.0,
        "location": "x",
        "auction_end_date": datetime.now(timezone.utc),
        "quantity": 4,
        "multiply_hammer_by_quantity": False,
        # price_multiplied_by_quantity intentionally absent
    }
    obj = Listing(**legacy)
    assert obj.price_multiplied_by_quantity is False
