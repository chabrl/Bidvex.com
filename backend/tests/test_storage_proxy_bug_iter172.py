"""
Iteration 172 — Storage Auction proxy-bid CORRECTNESS regression.

Locks in the spec-defined behavior:
  1. A submitter is never auto-outbid on their own bid.
  2. A bid_record's amount = the submitter's own max_bid (their intent),
     never an auto-advanced leader-proxy value.
  3. Idempotency: double-click within 2 seconds is collapsed.
  4. When an other user's max < standing leader's max, leader stays, current
     advances by increment capped by leader's max.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.storage_auction_service import place_bid


class FakeCursor:
    def __init__(self, data): self._data = data
    def to_list(self, n): return self._data


class FakeUpdateResult:
    matched_count = 1


class FakeAuctionsColl:
    """
    In-memory mock for db.storage_auctions.
    Supports find_one + update_one with $set / $push / $inc.
    """
    def __init__(self, doc):
        self._doc = doc

    async def find_one(self, q, proj=None):
        return dict(self._doc)

    async def update_one(self, q, upd):
        s = upd.get("$set", {})
        for k, v in s.items():
            self._doc[k] = v
        p = upd.get("$push", {})
        for k, v in p.items():
            self._doc.setdefault(k, []).append(v)
        i = upd.get("$inc", {})
        for k, v in i.items():
            self._doc[k] = self._doc.get(k, 0) + v
        return FakeUpdateResult()


class FakeDB:
    def __init__(self, auction):
        self.storage_auctions = FakeAuctionsColl(auction)


def _fresh_auction(**kw):
    base = {
        "id": "auc-1",
        "status": "active",
        "starting_price": 1.0,
        "current_bid": 1.0,
        "bid_increment": 1.0,
        "end_time": "2099-01-01T00:00:00+00:00",
        "bid_count": 0,
        "bids": [],
        "soft_close_enabled": False,
    }
    base.update(kw)
    return base


# ─────────────────────────────────────────────────────────────
# CRITICAL BUG REGRESSION — user is never outbid on their own bid
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_A_places_11_is_winning_no_auto_counter():
    """User A places $11 on a fresh auction → A is winning, no auto-counter fires."""
    db = FakeDB(_fresh_auction())
    r = await place_bid(db, "auc-1", bidder_id="A", max_bid=11)
    assert r["you_are_winning"] is True
    assert r["leader_id"] == "A"
    assert r["bid_count"] == 1
    # Only ONE bid in the record (A's). The auto-advance is not its own record.
    assert len(db.storage_auctions._doc["bids"]) == 1
    only = db.storage_auctions._doc["bids"][0]
    assert only["bidder_id"] == "A"
    # Amount attributed to A equals A's own max, never a leader-proxy auto-advance.
    assert only["amount"] == 11
    assert only["max_bid"] == 11


@pytest.mark.asyncio
async def test_user_B_lower_bid_does_not_steal_lead_from_user_A():
    """After A max=25 leads, B max=12 → A still leads, B's record attributes $12 to B."""
    auc = _fresh_auction(starting_price=1, bid_increment=1)
    db = FakeDB(auc)
    await place_bid(db, "auc-1", bidder_id="A", max_bid=25)
    r = await place_bid(db, "auc-1", bidder_id="B", max_bid=12)
    # A still leading
    assert db.storage_auctions._doc["winning_bidder_id"] == "A"
    assert r["you_are_winning"] is False
    assert r["leader_id"] == "A"
    # B's record correctly attributed to B at amount=12 (NOT $13 auto-advance).
    last = db.storage_auctions._doc["bids"][-1]
    assert last["bidder_id"] == "B"
    assert last["amount"] == 12
    assert last["max_bid"] == 12
    # current_bid on auction advances to min(A's max, B's max+1) = 13
    assert db.storage_auctions._doc["current_bid"] == 13


@pytest.mark.asyncio
async def test_user_B_higher_bid_takes_lead():
    """A max=25 leads. B max=60 → B takes lead at min(60, 25+1)=26."""
    auc = _fresh_auction(starting_price=1, bid_increment=1)
    db = FakeDB(auc)
    await place_bid(db, "auc-1", bidder_id="A", max_bid=25)
    r = await place_bid(db, "auc-1", bidder_id="B", max_bid=60)
    assert db.storage_auctions._doc["winning_bidder_id"] == "B"
    assert r["leader_id"] == "B"
    assert db.storage_auctions._doc["current_bid"] == 26
    # B's record: bidder=B, amount=60 (their own intent), max=60.
    last = db.storage_auctions._doc["bids"][-1]
    assert last["bidder_id"] == "B"
    assert last["amount"] == 60


@pytest.mark.asyncio
async def test_user_A_raises_own_ceiling_no_phantom_bid():
    """A max=25 leads. A then raises to max=40 → A still leads; visible unchanged; amount=40."""
    auc = _fresh_auction(starting_price=1, bid_increment=1)
    db = FakeDB(auc)
    await place_bid(db, "auc-1", bidder_id="A", max_bid=25)
    await place_bid(db, "auc-1", bidder_id="A", max_bid=40)
    assert db.storage_auctions._doc["winning_bidder_id"] == "A"
    # Current bid unchanged (no competitor)
    assert db.storage_auctions._doc["current_bid"] == 1
    last = db.storage_auctions._doc["bids"][-1]
    assert last["bidder_id"] == "A"
    assert last["amount"] == 40


# ─────────────────────────────────────────────────────────────
# Idempotency — double-click collapse
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_identical_rapid_double_click_is_deduped():
    """User rapidly submits max=50 twice → only 1 record, 2nd returns is_duplicate=True."""
    auc = _fresh_auction(starting_price=1, bid_increment=1)
    db = FakeDB(auc)
    r1 = await place_bid(db, "auc-1", bidder_id="X", max_bid=50)
    assert r1["is_duplicate"] is False
    r2 = await place_bid(db, "auc-1", bidder_id="X", max_bid=50)
    assert r2["is_duplicate"] is True
    # Only the first bid is in the bids array
    assert len(db.storage_auctions._doc["bids"]) == 1


# ─────────────────────────────────────────────────────────────
# Full 4-step user-spec scenario
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spec_full_scenario():
    """
    1. A places max=11 → A winning, no counter
    2. B places max=10 → min_required fails (must be ≥ 1+inc=2 OR > current_bid)
       — NOTE: starting_price=1, current_bid=1, increment=1. Min required for B
       is 1+1=2. So B=10 passes. A still leads at visible 1+1=2.
    3. B places max=15 → B beats A, A's ceiling was 11 so A no longer leads.
                         current_bid = min(15, 11+1)=12. Winner=B.
    4. Re-check leaderboard invariants.
    """
    auc = _fresh_auction(starting_price=1, bid_increment=1)
    db = FakeDB(auc)
    # Step 1
    await place_bid(db, "auc-1", "A", 11)
    assert db.storage_auctions._doc["winning_bidder_id"] == "A"
    # Step 2 — B bids $10 (< A's ceiling)
    r2 = await place_bid(db, "auc-1", "B", 10)
    assert r2["leader_id"] == "A"
    assert r2["you_are_winning"] is False
    # Auto-advance to min(A's max=11, B's max+inc=11) = 11
    assert db.storage_auctions._doc["current_bid"] == 11
    # Step 3 — B bids $15 (> A's ceiling)
    r3 = await place_bid(db, "auc-1", "B", 15)
    assert r3["leader_id"] == "B"
    assert r3["you_are_winning"] is True
    assert r3["outbid_user_id"] == "A"
    # current_bid = min(15, 11+1) = 12
    assert db.storage_auctions._doc["current_bid"] == 12
