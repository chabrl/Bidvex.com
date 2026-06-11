"""
iter196 — Messaging Transaction Gate Tests
Validates _can_open_thread() across all listing types and all 6 gate codes.

Run: cd /app/backend && pytest tests/test_messaging_gate_iter196.py -v
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    yield database
    cli.close()


async def _seed(db, listing_type: str, **fields):
    """Seed a listing in the right collection. Returns (collection_name, doc)."""
    coll_map = {
        "marketplace": "listings",
        "lots": "multi_item_listings",
        "storage": "storage_auctions",
        "vehicle": "vehicle_listings",
    }
    coll = coll_map[listing_type]
    doc = {"id": f"itergate-{uuid.uuid4().hex[:10]}", **fields}
    await db[coll].insert_one(doc)
    return coll, doc


async def _cleanup(db, ids: list[str]):
    if not ids:
        return
    for c in ("listings", "multi_item_listings", "storage_auctions", "vehicle_listings", "vehicle_sellers", "conversations"):
        await db[c].delete_many({"id": {"$in": ids}})


@pytest.mark.asyncio
async def test_admin_always_allowed():
    """Admins bypass all gates."""
    from routes.messages import _can_open_thread, set_messages_db

    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    err = await _can_open_thread("admin-uid", "user-uid", None, is_admin=True)
    assert err is None
    cli.close()


@pytest.mark.asyncio
async def test_no_listing_id_blocks():
    from routes.messages import _can_open_thread, set_messages_db
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    err = await _can_open_thread("user-a", "user-b", None, is_admin=False)
    assert err == "thread_requires_listing_context"
    cli.close()


@pytest.mark.asyncio
async def test_listing_not_found():
    from routes.messages import _can_open_thread, set_messages_db
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    err = await _can_open_thread("user-a", "user-b", "nonexistent-listing", is_admin=False)
    assert err == "listing_not_found"
    cli.close()


@pytest.mark.asyncio
async def test_marketplace_active_blocks():
    """iter301 update: while a listing is ACTIVE, any signed-in user may
    message the SELLER (pre-sale Q&A), but messaging anyone else in the
    context of that listing is blocked."""
    from routes.messages import _can_open_thread, set_messages_db
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    coll, doc = await _seed(database, "marketplace",
                             seller_id="seller-A", winner_id=None,
                             status="active", end_time=future)
    try:
        # Pre-sale Q&A with the seller — now allowed (iter301 P1)
        err = await _can_open_thread("buyer-X", "seller-A", doc["id"], is_admin=False)
        assert err is None
        # Messaging a non-seller third party on the active listing — blocked
        err2 = await _can_open_thread("buyer-X", "random-user-Z", doc["id"], is_admin=False)
        assert err2 == "presale_must_message_seller"
    finally:
        await _cleanup(database, [doc["id"]])
        cli.close()


@pytest.mark.asyncio
async def test_marketplace_ended_winner_seller_pair_allowed():
    from routes.messages import _can_open_thread, set_messages_db
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    coll, doc = await _seed(database, "marketplace",
                             seller_id="seller-A", winner_id="winner-W",
                             status="ended", end_time=past)
    try:
        err = await _can_open_thread("winner-W", "seller-A", doc["id"], is_admin=False)
        assert err is None
        err = await _can_open_thread("seller-A", "winner-W", doc["id"], is_admin=False)
        assert err is None
        # Outsider blocked
        err = await _can_open_thread("stranger", "seller-A", doc["id"], is_admin=False)
        assert err == "not_party_to_transaction"
    finally:
        await _cleanup(database, [doc["id"]])
        cli.close()


@pytest.mark.asyncio
async def test_vehicle_unlock_unpaid_blocks_winner():
    from routes.messages import _can_open_thread, set_messages_db
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    seller_user_id = "veh-seller-user-1"
    seller_doc_id = f"veh-seller-{uuid.uuid4().hex[:6]}"
    await database.vehicle_sellers.insert_one({"id": seller_doc_id, "user_id": seller_user_id})
    coll, doc = await _seed(database, "vehicle",
                             seller_id=seller_doc_id, winner_id="veh-winner-1",
                             unlock_paid_at=None, status="ended")
    try:
        # Winner before paying unlock — blocked
        err = await _can_open_thread("veh-winner-1", seller_user_id, doc["id"], is_admin=False)
        assert err == "vehicle_unlock_fee_unpaid"
    finally:
        await database.vehicle_sellers.delete_one({"id": seller_doc_id})
        await _cleanup(database, [doc["id"]])
        cli.close()


@pytest.mark.asyncio
async def test_vehicle_unlock_paid_winner_to_seller_allowed():
    from routes.messages import _can_open_thread, set_messages_db
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    seller_user_id = "veh-seller-user-2"
    seller_doc_id = f"veh-seller-{uuid.uuid4().hex[:6]}"
    await database.vehicle_sellers.insert_one({"id": seller_doc_id, "user_id": seller_user_id})
    coll, doc = await _seed(database, "vehicle",
                             seller_id=seller_doc_id, winner_id="veh-winner-2",
                             unlock_paid_at=datetime.now(timezone.utc).isoformat(),
                             status="ended")
    try:
        # Winner → seller allowed
        err = await _can_open_thread("veh-winner-2", seller_user_id, doc["id"], is_admin=False)
        assert err is None
        # Seller → winner allowed
        err = await _can_open_thread(seller_user_id, "veh-winner-2", doc["id"], is_admin=False)
        assert err is None
        # Stranger → seller blocked
        err = await _can_open_thread("stranger", seller_user_id, doc["id"], is_admin=False)
        assert err == "not_party_to_transaction"
        # Winner → wrong recipient blocked
        err = await _can_open_thread("veh-winner-2", "stranger", doc["id"], is_admin=False)
        assert err == "must_message_seller"
    finally:
        await database.vehicle_sellers.delete_one({"id": seller_doc_id})
        await _cleanup(database, [doc["id"]])
        cli.close()


@pytest.mark.asyncio
async def test_existing_conversation_allows_replies():
    from routes.messages import _can_open_thread, set_messages_db
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = cli[os.environ["DB_NAME"]]
    set_messages_db(database)
    user_a, user_b = "conv-user-a", "conv-user-b"
    conv_id = "_".join(sorted([user_a, user_b]))
    await database.conversations.insert_one({
        "id": conv_id,
        "participants": [user_a, user_b],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        # Even without a listing context, an existing conversation allows new messages
        err = await _can_open_thread(user_a, user_b, None, is_admin=False)
        assert err is None
    finally:
        await database.conversations.delete_one({"id": conv_id})
        cli.close()
