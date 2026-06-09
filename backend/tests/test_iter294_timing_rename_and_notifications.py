"""
iter294 — Timing-mode rename + notifications + countdown + email split tests.

Focus:
  1. Internal `staggered` / `sequential` API values are unchanged
     (display rename only).
  2. Pydantic V2 migration of broker_models still validates.
  3. emails/* shims expose the public surface used by the codebase.
  4. Upcoming-notify "starting_soon" trigger fires 15 min before start.

Constraints honoured:
- Vehicle Buyer Premium = 0% (unchanged)
- Vehicle Platform Fee = 2.5% (unchanged)
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# ── ADDENDUM — Timing-mode internal value preservation ───────────────


def test_timing_mode_internal_values_unchanged():
    """The display rename (Synchronized Wave / Sequential Spotlight)
    must NOT touch the internal sequential / staggered values used by
    the DB + scheduler."""
    from models.vehicle_multi_lot_models import MultiLotTimingMode

    assert MultiLotTimingMode.SEQUENTIAL.value == "sequential"
    assert MultiLotTimingMode.STAGGERED.value  == "staggered"
    # No new values introduced.
    assert set(MultiLotTimingMode) == {MultiLotTimingMode.SEQUENTIAL, MultiLotTimingMode.STAGGERED}


# ── P2 — Pydantic V2 migration of broker_models ──────────────────────


def test_broker_models_v2_validators_still_enforce():
    from models.broker_models import BrokerFeeStructure
    # Valid
    fs = BrokerFeeStructure(type="percentage", percentage_rate=0.03, fixed_amount_cad=0)
    assert fs.percentage_rate == 0.03
    # Out-of-range percentage
    with pytest.raises(Exception):
        BrokerFeeStructure(type="percentage", percentage_rate=1.5)
    with pytest.raises(Exception):
        BrokerFeeStructure(type="percentage", percentage_rate=-0.1)
    # Negative fixed
    with pytest.raises(Exception):
        BrokerFeeStructure(type="fixed", fixed_amount_cad=-5)


# ── P2 — emails/* package exposes the expected surface ───────────────


def test_emails_package_re_exports_public_senders():
    from services.emails import (
        send_email, send_unified_email,
        send_outbid_email, send_auction_won_email,
        send_welcome_email,
    )
    from services.emails.email_vehicles import send_dealer_license_approved_email
    from services.emails.email_marketplace import send_bid_placed_email
    from services.emails.email_system import send_invoice_created_email

    # Identity check — the new modules MUST be re-exporting the
    # legacy implementations, not redefining them. This guarantees
    # zero behavioural change.
    from services.email_notifications import (
        send_email as _se,
        send_outbid_email as _so,
        send_dealer_license_approved_email as _sd,
    )
    assert send_email is _se
    assert send_outbid_email is _so
    assert send_dealer_license_approved_email is _sd


# ── P1 — Upcoming-notify 15-min pre-start trigger ────────────────────


def test_upcoming_notify_warns_15_min_before_start(db):
    """Subscriber gets a pre-start email at T-15min and a separate
    'live' email at T+0. Both write distinct timestamps on the
    subscription row."""
    from routes.upcoming_notify import fire_live_transitions_once
    from motor.motor_asyncio import AsyncIOMotorClient

    # Seed an UPCOMING multi-lot event starting in 10 minutes.
    event_id = f"iter294-warn-{uuid.uuid4()}"
    soon = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.vehicle_multi_lot_auctions.insert_one({
        "id": event_id,
        "title": "iter294 warn event",
        "status": "upcoming",
        "start_time": soon,
        "lots": [],
        "seller_id": "seed",
        "timing_mode": "sequential",
        "created_at": datetime.now(timezone.utc),
    })
    # Seed a subscription
    sub_id = f"iter294-sub-{uuid.uuid4()}"
    db.upcoming_notify_subscribers.insert_one({
        "id": sub_id,
        "user_id": "test-user",
        "user_email": "qa@bidvex.com",
        "listing_id": event_id,
        "listing_type": "vehicle_multi_lot",
        "created_at": datetime.now(timezone.utc),
        "notified_at": None,
    })
    try:
        async def _run():
            async_db = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
            return await fire_live_transitions_once(async_db)
        asyncio.run(_run())
        doc = db.upcoming_notify_subscribers.find_one({"id": sub_id})
        # `warned_at` set; `notified_at` still None (not yet live).
        assert doc.get("warned_at") is not None
        assert doc.get("notified_at") is None
    finally:
        db.vehicle_multi_lot_auctions.delete_one({"id": event_id})
        db.upcoming_notify_subscribers.delete_one({"id": sub_id})


# ── Constraint guard ─────────────────────────────────────────────────


def test_vehicle_fee_constants_untouched():
    from services.pricing_config import PLATFORM_FEE_VEHICLE
    from decimal import Decimal
    assert PLATFORM_FEE_VEHICLE == Decimal("0.025")
