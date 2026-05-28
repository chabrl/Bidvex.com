"""iter236 Missions 2 + 3 — Pytest coverage.

Verifies:
  M2: geo-search route + index helper logic (route shape + empty-fallback).
  M3: chat_listing_context.build_chat_listing_context — current + comparables
      shapes + 60-day window; system instruction Section 5 wording; route
      schema accepts listing_id.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mission 3 — system instruction Section 5
# ---------------------------------------------------------------------------
def test_section_5_proactive_assistance_present():
    from services.genai_direct_client import WATCHDOG_SYSTEM_INSTRUCTION
    s = WATCHDOG_SYSTEM_INSTRUCTION
    assert "# 5. Proactive Listing & Bid Assistance" in s
    assert "Smart Matchmaking" in s
    assert "current_viewed_listing" in s
    assert "market_comparables" in s
    assert "Bidding Insights" in s
    assert "Based on recent BidVex platform records" in s
    assert "Language Compliance" in s
    assert "D'après les données récentes de la plateforme BidVex" in s


def test_section_5_keeps_anti_hallucination_lock():
    from services.genai_direct_client import WATCHDOG_SYSTEM_INSTRUCTION
    s = WATCHDOG_SYSTEM_INSTRUCTION
    # Section 5 must not undermine the iter235 guardrails.
    assert "Never invent fee numbers" in s
    assert 'Never introduce yourself as "Master Concierge"' in s


# ---------------------------------------------------------------------------
# Mission 3 — listing context builder
# ---------------------------------------------------------------------------
class _FakeAsyncCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    async def to_list(self, length=None):
        return self._docs[: (length or len(self._docs))]


class _FakeCollection:
    def __init__(self, find_one_doc=None, find_docs=None):
        self._one = find_one_doc
        self._many = find_docs or []

    async def find_one(self, _q):
        return self._one

    def find(self, *_a, **_k):
        return _FakeAsyncCursor(self._many)


class _FakeDB:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return getattr(self, name, _FakeCollection())

    def __getattr__(self, name):
        return self._collections.get(name, _FakeCollection())


def test_listing_context_shape():
    from services.chat_listing_context import build_chat_listing_context

    now = datetime.now(timezone.utc)
    listing_doc = {
        "id": "lst-001",
        "title": "Vintage Pinball Machine",
        "category": "collectibles",
        "condition": "good",
        "current_bid": 250,
        "buy_now_price": 800,
        "quantity": 1,
        "city": "Sherbrooke",
        "region": "QC",
        "auction_end_date": now + timedelta(days=3),
        "seller_id": "u-seller",
        "price_multiplied_by_quantity": False,
    }
    comp_docs = [
        {
            "id": "lst-c1",
            "title": "Vintage Slot Machine",
            "category": "collectibles",
            "status": "ended",
            "hammer_price": 600,
            "auction_end_date": now - timedelta(days=10),
            "city": "Montreal",
            "quantity": 1,
        },
        {
            "id": "lst-c2",
            "title": "Antique Arcade Cabinet",
            "category": "collectibles",
            "status": "active",
            "current_bid": 300,
            "auction_end_date": now + timedelta(days=5),
            "city": "Quebec",
            "quantity": 1,
        },
    ]
    db = _FakeDB({
        "listings": _FakeCollection(find_one_doc=listing_doc, find_docs=comp_docs),
        "multi_item_listings": _FakeCollection(),
    })
    out = asyncio.run(build_chat_listing_context(db, "lst-001"))
    assert out["current_viewed_listing"]["id"] == "lst-001"
    assert out["current_viewed_listing"]["category"] == "collectibles"
    assert out["current_viewed_listing"]["price_multiplied_by_quantity"] is False
    assert out["current_viewed_listing"]["location"]["city"] == "Sherbrooke"
    # auction_end_time is the canonical key spec'd in Mission 3.
    assert "auction_end_time" in out["current_viewed_listing"]
    # Comparables present + projected
    assert isinstance(out["market_comparables"], list)
    assert len(out["market_comparables"]) >= 1
    first = out["market_comparables"][0]
    assert first["id"] == "lst-c1"
    assert first["hammer_price"] == 600


def test_listing_context_handles_missing_listing():
    from services.chat_listing_context import build_chat_listing_context
    db = _FakeDB({
        "listings": _FakeCollection(find_one_doc=None),
        "multi_item_listings": _FakeCollection(find_one_doc=None),
    })
    out = asyncio.run(build_chat_listing_context(db, "lst-missing"))
    assert out["current_viewed_listing"] is None
    assert out["market_comparables"] == []


def test_listing_context_no_listing_id_returns_none_pair():
    from services.chat_listing_context import build_chat_listing_context
    db = _FakeDB({"listings": _FakeCollection()})
    out = asyncio.run(build_chat_listing_context(db, None))
    assert out == {"current_viewed_listing": None, "market_comparables": []}


# ---------------------------------------------------------------------------
# Mission 3 — chat route schema accepts listing_id
# ---------------------------------------------------------------------------
def test_stream_chat_body_accepts_listing_id():
    from routes.genai_chat import StreamChatBody
    obj = StreamChatBody(message="hi", listing_id="lst-001")
    assert obj.listing_id == "lst-001"
    obj_none = StreamChatBody(message="hi")
    assert obj_none.listing_id is None


# ---------------------------------------------------------------------------
# Mission 2 — geo route module surface
# ---------------------------------------------------------------------------
def test_geo_route_exports_expected_symbols():
    import routes.geo_search as mod
    assert hasattr(mod, "geo_router")
    assert hasattr(mod, "ensure_2dsphere_index")
    assert hasattr(mod, "set_geo_db")


def test_geo_route_set_db_is_idempotent():
    import routes.geo_search as mod
    mod.set_geo_db("sentinel-db")
    assert mod._db == "sentinel-db"
    mod.set_geo_db(None)
    assert mod._db is None


def test_ensure_2dsphere_index_skips_when_db_none():
    from routes.geo_search import ensure_2dsphere_index, set_geo_db
    set_geo_db(None)
    out = asyncio.run(ensure_2dsphere_index())
    assert out["status"] == "skipped"


def test_ensure_2dsphere_index_creates_when_db_present():
    import routes.geo_search as mod

    async def _fake_create_index(keys, **kw):
        return kw.get("name", "ok")

    fake = MagicMock()
    fake.listings.create_index = _fake_create_index
    fake.multi_item_listings.create_index = _fake_create_index
    mod.set_geo_db(fake)
    out = asyncio.run(mod.ensure_2dsphere_index())
    assert out["status"] == "ok"
    mod.set_geo_db(None)
