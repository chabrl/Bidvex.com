"""
iter312 D3 — Draft expiry sweep tests.

Validates the daily scheduler hook:
  • Drafts older than 23 days but not yet expired → warning notification + email queued
  • Drafts older than 30 days → soft-archived (status='draft_expired')
  • Drafts younger than 23 days → untouched
  • Idempotency: re-running the sweep on a warned draft doesn't double-warn
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from pymongo import MongoClient  # noqa: E402


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_async_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    from deps import set_db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    set_db(client[os.environ["DB_NAME"]])
    yield
    client.close()


def _make_draft(db, collection: str, age_days: int, seller_id: str) -> str:
    listing_id = f"iter312-draft-{uuid.uuid4().hex[:8]}"
    anchor = datetime.now(timezone.utc) - timedelta(days=age_days)
    db[collection].insert_one({
        "id":          listing_id,
        "seller_id":   seller_id,
        "title":       f"iter312 draft age={age_days}d",
        "status":      "draft",
        "created_at":  anchor,
        "updated_at":  anchor,
    })
    return listing_id


def test_draft_under_23_days_left_alone(db):
    seller_id = f"iter312-seller-{uuid.uuid4().hex[:6]}"
    db.users.insert_one({"id": seller_id, "email": f"{seller_id}@test.example"})
    young_id = _make_draft(db, "listings", age_days=5, seller_id=seller_id)
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from deps import set_db
        from services.draft_expiry import run_draft_expiry_sweep

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            set_db(client[os.environ["DB_NAME"]])
            try:
                return await run_draft_expiry_sweep(client[os.environ["DB_NAME"]])
            finally:
                client.close()

        asyncio.run(_run())

        doc = db.listings.find_one({"id": young_id}, {"_id": 0})
        assert doc["status"] == "draft", "young draft was touched"
        assert "draft_expiry_warning_sent_at" not in doc
    finally:
        db.listings.delete_many({"id": young_id})
        db.users.delete_many({"id": seller_id})
        db.notifications.delete_many({"user_id": seller_id})


def test_draft_24_days_old_gets_warning(db):
    seller_id = f"iter312-seller-{uuid.uuid4().hex[:6]}"
    db.users.insert_one({"id": seller_id, "email": f"{seller_id}@test.example"})
    warn_id = _make_draft(db, "listings", age_days=24, seller_id=seller_id)
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from deps import set_db
        from services.draft_expiry import run_draft_expiry_sweep

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            set_db(client[os.environ["DB_NAME"]])
            try:
                return await run_draft_expiry_sweep(client[os.environ["DB_NAME"]])
            finally:
                client.close()

        result = asyncio.run(_run())
        assert result["warnings_sent"] >= 1

        doc = db.listings.find_one({"id": warn_id}, {"_id": 0})
        assert doc["status"] == "draft"
        assert doc.get("draft_expiry_warning_sent_at") is not None
        # Notification dropped.
        n = db.notifications.find_one({"user_id": seller_id, "kind": "draft_expiry_warning"})
        assert n is not None
        # Email queued.
        e = db.email_outbox.find_one({"kind": "draft_expiry_warning", "context.listing_id": warn_id})
        assert e is not None
    finally:
        db.listings.delete_many({"id": warn_id})
        db.users.delete_many({"id": seller_id})
        db.notifications.delete_many({"user_id": seller_id})
        db.email_outbox.delete_many({"context.listing_id": warn_id})


def test_draft_31_days_old_gets_archived(db):
    seller_id = f"iter312-seller-{uuid.uuid4().hex[:6]}"
    db.users.insert_one({"id": seller_id, "email": f"{seller_id}@test.example"})
    expired_id = _make_draft(db, "listings", age_days=31, seller_id=seller_id)
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from deps import set_db
        from services.draft_expiry import run_draft_expiry_sweep

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            set_db(client[os.environ["DB_NAME"]])
            try:
                return await run_draft_expiry_sweep(client[os.environ["DB_NAME"]])
            finally:
                client.close()

        result = asyncio.run(_run())
        assert result["drafts_archived"] >= 1

        doc = db.listings.find_one({"id": expired_id}, {"_id": 0})
        assert doc["status"] == "draft_expired"
        assert doc.get("archived") is True
        assert doc.get("draft_expired_at") is not None
    finally:
        db.listings.delete_many({"id": expired_id})
        db.users.delete_many({"id": seller_id})
        db.notifications.delete_many({"user_id": seller_id})


def test_draft_expiry_sweep_is_idempotent(db):
    """Running the sweep twice in the same day must not double-warn or double-archive."""
    seller_id = f"iter312-seller-{uuid.uuid4().hex[:6]}"
    db.users.insert_one({"id": seller_id, "email": f"{seller_id}@test.example"})
    warn_id = _make_draft(db, "listings", age_days=24, seller_id=seller_id)
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from deps import set_db
        from services.draft_expiry import run_draft_expiry_sweep

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            set_db(client[os.environ["DB_NAME"]])
            try:
                await run_draft_expiry_sweep(client[os.environ["DB_NAME"]])
                # second run within the same second
                return await run_draft_expiry_sweep(client[os.environ["DB_NAME"]])
            finally:
                client.close()

        second_run = asyncio.run(_run())
        # Second pass should NOT re-warn (idempotency guard <24h since last).
        assert second_run["warnings_sent"] == 0 or warn_id not in [
            r.get("listing_id") for r in db.email_outbox.find({"kind": "draft_expiry_warning"})
        ]

        # Exactly ONE warning row in notifications (idempotent upsert).
        n_count = db.notifications.count_documents({
            "user_id": seller_id, "kind": "draft_expiry_warning"
        })
        assert n_count == 1, f"expected 1 warning notification, got {n_count}"
    finally:
        db.listings.delete_many({"id": warn_id})
        db.users.delete_many({"id": seller_id})
        db.notifications.delete_many({"user_id": seller_id})
        db.email_outbox.delete_many({"context.listing_id": warn_id})


def test_draft_expiry_sweep_hits_all_5_collections():
    """The sweep must scan listings, multi_item_listings, vehicle_listings,
    vehicle_multi_lot_auctions, storage_auctions."""
    from services.draft_expiry import DRAFT_COLLECTIONS
    assert set(DRAFT_COLLECTIONS) == {
        "listings",
        "multi_item_listings",
        "vehicle_listings",
        "vehicle_multi_lot_auctions",
        "storage_auctions",
    }


def test_scheduler_registers_draft_expiry_job():
    """The daily scheduler must register a `draft_expiry_sweep` job."""
    import inspect
    from services import scheduler
    src = inspect.getsource(scheduler)
    assert 'id="draft_expiry_sweep"' in src
    assert "run_draft_expiry_sweep" in src
