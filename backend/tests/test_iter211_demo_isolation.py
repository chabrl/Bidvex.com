"""
iter211 P4 — Demo Account Isolation tests.

Verifies:
  1. tag_listing_if_demo() correctly tags listing dicts created by demo users.
  2. public_listing_filter() excludes demo listings.
  3. is_demo_user() returns the right boolean.
  4. Dealer-fee Stripe checkout is blocked for demo users.
"""
from unittest.mock import MagicMock

import pytest


# ─── Helpers fixture: fake db with user collection ───────────────────────
class _FakeUsers:
    def __init__(self, users_by_id):
        self._users = users_by_id

    async def find_one(self, query, projection=None):
        uid = (query or {}).get("id")
        return self._users.get(uid)


@pytest.fixture
def fake_db():
    db = MagicMock()
    db.users = _FakeUsers({
        "demo-1": {"id": "demo-1", "is_demo_account": True},
        "real-1": {"id": "real-1", "is_demo_account": False},
        "real-no-flag": {"id": "real-no-flag"},
    })
    return db


# ─── tag_listing_if_demo ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_tags_demo_user_listings(fake_db):
    from services.demo_filter import tag_listing_if_demo
    doc = {"id": "l1", "title": "Hammer"}
    out = await tag_listing_if_demo(fake_db, "demo-1", doc)
    assert out["is_demo"] is True


@pytest.mark.asyncio
async def test_does_not_tag_real_user_listings(fake_db):
    from services.demo_filter import tag_listing_if_demo
    doc = {"id": "l2", "title": "Hammer"}
    await tag_listing_if_demo(fake_db, "real-1", doc)
    assert "is_demo" not in doc


@pytest.mark.asyncio
async def test_handles_missing_user_gracefully(fake_db):
    from services.demo_filter import tag_listing_if_demo
    doc = {"id": "l3"}
    await tag_listing_if_demo(fake_db, "ghost-user", doc)
    assert "is_demo" not in doc


@pytest.mark.asyncio
async def test_handles_no_user_id(fake_db):
    from services.demo_filter import tag_listing_if_demo
    doc = {"id": "l4"}
    out = await tag_listing_if_demo(fake_db, "", doc)
    assert "is_demo" not in out


# ─── public_listing_filter ───────────────────────────────────────────────
def test_filter_excludes_demo_by_default():
    from services.demo_filter import public_listing_filter
    f = public_listing_filter()
    assert f == {"is_demo": {"$ne": True}}


def test_filter_merges_extra():
    from services.demo_filter import public_listing_filter
    f = public_listing_filter({"status": "active", "category": "tools"})
    assert f == {
        "status": "active",
        "category": "tools",
        "is_demo": {"$ne": True},
    }


def test_filter_respects_caller_is_demo_override():
    """If a caller explicitly wants to query demo listings (admin tooling),
    the helper does NOT clobber their is_demo clause."""
    from services.demo_filter import public_listing_filter
    f = public_listing_filter({"is_demo": True, "status": "active"})
    assert f == {"is_demo": True, "status": "active"}


# ─── is_demo_user ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_is_demo_user_true(fake_db):
    from services.demo_filter import is_demo_user
    assert await is_demo_user(fake_db, "demo-1") is True


@pytest.mark.asyncio
async def test_is_demo_user_false_for_real(fake_db):
    from services.demo_filter import is_demo_user
    assert await is_demo_user(fake_db, "real-1") is False


@pytest.mark.asyncio
async def test_is_demo_user_false_for_missing(fake_db):
    from services.demo_filter import is_demo_user
    assert await is_demo_user(fake_db, "no-such-user") is False


@pytest.mark.asyncio
async def test_is_demo_user_false_for_empty_id(fake_db):
    from services.demo_filter import is_demo_user
    assert await is_demo_user(fake_db, "") is False


# ─── Smoke: every listing-creation site has the demo tag call ────────────
def test_listings_service_has_demo_tag_call():
    """Static smoke check — make sure the iter211 demo tag was wired into
    each persist function. If a refactor accidentally removes it, this test
    catches it."""
    with open("/app/backend/services/listings_service.py", "r") as f:
        body = f.read()
    assert "tag_listing_if_demo" in body, \
        "services/listings_service.py must call tag_listing_if_demo before insert"


def test_multi_item_listings_has_demo_tag_call():
    with open("/app/backend/routes/listings.py", "r") as f:
        body = f.read()
    assert "tag_listing_if_demo" in body, \
        "routes/listings.py (multi-item creation) must call tag_listing_if_demo"


def test_vehicles_listing_has_demo_tag_call():
    with open("/app/backend/routes/vehicles.py", "r") as f:
        body = f.read()
    assert "tag_listing_if_demo" in body, \
        "routes/vehicles.py vehicle creation must call tag_listing_if_demo"


def test_storage_auctions_has_demo_tag_call():
    with open("/app/backend/routes/storage_auctions.py", "r") as f:
        body = f.read()
    assert "tag_listing_if_demo" in body, \
        "routes/storage_auctions.py must call tag_listing_if_demo"


# ─── Smoke: bid endpoint enforces demo isolation ─────────────────────────
def test_bid_endpoint_enforces_demo_isolation():
    with open("/app/backend/routes/auctions_bids.py", "r") as f:
        body = f.read()
    assert "is_demo_user" in body, "Bid endpoint must call is_demo_user"
    assert "demo_cannot_bid_on_real" in body, "Bid endpoint must reject demo→real bids"


# ─── Smoke: public list endpoints all filter is_demo ─────────────────────
def test_marketplace_filters_demo():
    with open("/app/backend/routes/marketplace.py", "r") as f:
        body = f.read()
    assert body.count('"is_demo": {"$ne": True}') >= 2, \
        "marketplace.py must filter is_demo on listings + multi_item_listings"


def test_storage_filters_demo():
    with open("/app/backend/routes/storage_auctions.py", "r") as f:
        body = f.read()
    assert '"is_demo": {"$ne": True}' in body, \
        "storage_auctions.py public list must filter is_demo"


def test_vehicles_filters_demo():
    with open("/app/backend/routes/vehicles.py", "r") as f:
        body = f.read()
    assert '"is_demo": {"$ne": True}' in body, \
        "vehicles.py public list must filter is_demo"


def test_carousel_filters_demo():
    with open("/app/backend/routes/carousel.py", "r") as f:
        body = f.read()
    assert body.count('"is_demo": {"$ne": True}') >= 2, \
        "carousel.py ending-soon and featured endpoints must filter is_demo"


# ─── Smoke: dealer fee checkout endpoint blocks demo accounts ────────────
def test_dealer_checkout_blocks_demo():
    with open("/app/backend/routes/dealer_subscription_routes.py", "r") as f:
        body = f.read()
    assert "is_demo_account" in body, \
        "dealer subscription routes must block demo accounts from Stripe checkout"
    assert "demo_mode_payments_disabled" in body, \
        "dealer subscription must raise the standard demo block error"
