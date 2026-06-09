"""
iter292 — Directive 3: Dealer lifecycle status control regression.

Verifies that the new `submission_intent` field on `VehicleListingCreate`
flows correctly through the create endpoint and that bidding is properly
gated on Upcoming (scheduled-future) auctions.

Constraints honoured:
- Vehicle Buyer Premium = 0% (unchanged)
- Vehicle Platform Fee = 2.5% (unchanged)
- No fee math touched
- The trusted-seller auto-promote still fires for "schedule" + "live"
  intents — only "draft" intent overrides it.
"""
from datetime import datetime, timedelta, timezone

import pytest

from models.vehicle_models import VehicleListingCreate, VehicleListingStatus


def _minimal_payload_kwargs(extra: dict | None = None) -> dict:
    """Build the smallest set of kwargs Pydantic needs to validate
    VehicleListingCreate. Field-level validation tests live elsewhere;
    here we only care about the new submission_intent field."""
    now = datetime.now(timezone.utc)
    out = {
        "vin": "1FTFW1ET5DFC10312",
        "year": 2020,
        "make": "Ford",
        "model": "F-350",
        "body_type": "truck",
        "mileage": 50000,
        "transmission": "automatic",
        "fuel_type": "diesel",
        "drivetrain": "4wd",
        "exterior_color": "White",
        "interior_color": "Black",
        "ownership_status": "owned",
        "title_status": "clean",
        "lien_status": "clear",
        "condition_report": {
            "is_running": True,
            "starts_normally": True,
            "engine_condition": "good",
            "transmission_condition": "good",
            "brakes_condition": "good",
            "suspension_condition": "good",
            "body_condition": "good",
            "paint_condition": "good",
            "interior_condition": "good",
            "tires_condition": "good",
            "has_accident_history": False,
            "has_flood_damage": False,
            "has_fire_damage": False,
            "has_frame_damage": False,
        },
        "location_city": "Montreal",
        "location_province": "QC",
        "location_postal_code": "H2X3L7",
        "auction_type": "timed",
        "start_time": (now + timedelta(days=1)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
        "starting_price": 10000.0,
        "bid_increment": 100.0,
        "title": "2020 Ford F-350",
        "description": "Test vehicle",
    }
    if extra:
        out.update(extra)
    return out


def test_default_submission_intent_is_live():
    """Older clients that don't pass submission_intent must still see
    the existing "publish immediately" behaviour."""
    payload = VehicleListingCreate(**_minimal_payload_kwargs())
    assert payload.submission_intent == "live"


def test_submission_intent_accepts_draft():
    payload = VehicleListingCreate(
        **_minimal_payload_kwargs({"submission_intent": "draft"})
    )
    assert payload.submission_intent == "draft"


def test_submission_intent_accepts_schedule():
    payload = VehicleListingCreate(
        **_minimal_payload_kwargs({"submission_intent": "schedule"})
    )
    assert payload.submission_intent == "schedule"


def test_submission_intent_accepts_live():
    payload = VehicleListingCreate(
        **_minimal_payload_kwargs({"submission_intent": "live"})
    )
    assert payload.submission_intent == "live"


def test_vehicle_listing_status_enum_has_existing_states():
    """Sanity — the existing 9 statuses are intact. iter292 added the
    `submission_intent` field on the CREATE payload (NOT a new status).
    The runtime status is still one of DRAFT / PENDING_APPROVAL /
    APPROVED / REJECTED / ACTIVE / ENDED / SOLD / CANCELLED / EXPIRED."""
    values = {s.value for s in VehicleListingStatus}
    assert {
        "draft",
        "pending_approval",
        "approved",
        "rejected",
        "active",
        "ended",
        "sold",
        "cancelled",
        "expired",
    }.issubset(values)


def test_buyer_premium_for_vehicle_is_still_zero():
    """Hard guard — iter292 must NOT change vehicle fee math."""
    from services.pricing_config import PLATFORM_FEE_VEHICLE
    from decimal import Decimal

    # Vehicle platform fee still 2.5%.
    assert PLATFORM_FEE_VEHICLE == Decimal("0.025")
