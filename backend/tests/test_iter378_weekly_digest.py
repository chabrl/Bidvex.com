"""
iter378 — Weekly marketing digest coverage test.

Verifies:
  1. Payload builder returns the right structure for a user with (a)
     followed sellers, (b) watchlisted lots, and (c) interest history.
  2. Payload builder returns None when the user has nothing personal
     (never send an empty marketing email).
  3. Template renders both EN and FR flavours with correct subject line
     and section headers.
  4. `send_weekly_digest_to_user` respects the marketing suppression
     (mock-driven — no live SendGrid call).
  5. Scheduler is wired via a proper async wrapper, not a broken
     `lambda: safe_run(...)`.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Ensure repo root import path is right (test runs from /app root).
sys.path.insert(0, "/app/backend")


def _load_env():
    p = Path("/app/backend/.env")
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


class FakeCursor:
    def __init__(self, docs, chained=False):
        self._docs = list(docs)
        self._chained = chained

    def sort(self, *a, **kw): return self
    def limit(self, *a, **kw): return self
    def to_list(self, *a, **kw):
        async def _it():
            return list(self._docs)
        return _it()

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._docs):
            raise StopAsyncIteration
        d = self._docs[self._i]
        self._i += 1
        return d


class FakeAggregateCursor:
    def __init__(self, docs): self._docs = list(docs)
    def __aiter__(self):
        self._i = 0
        return self
    async def __anext__(self):
        if self._i >= len(self._docs):
            raise StopAsyncIteration
        d = self._docs[self._i]; self._i += 1; return d


class FakeCollection:
    def __init__(self, docs=None, agg=None):
        self._docs = list(docs or [])
        self._agg = list(agg or [])
        self.inserted = []

    def find(self, q=None, proj=None):    return FakeCursor(self._docs)
    def find_one(self, q=None, proj=None):
        async def _run():
            return self._docs[0] if self._docs else None
        return _run()
    def aggregate(self, pipeline, *a, **kw):  return FakeAggregateCursor(self._agg)
    def insert_one(self, doc):
        self.inserted.append(doc)
        async def _r(): return type("R", (), {"inserted_id": "x"})()
        return _r()
    def count_documents(self, q=None):
        async def _r(): return len(self._docs)
        return _r()


class FakeDB:
    def __init__(self, **cols):
        for name, coll in cols.items():
            setattr(self, name, coll)


# ─── Tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_payload_returns_none_when_user_has_no_signal():
    _load_env()
    from services.weekly_digest import build_user_digest
    db = FakeDB(
        seller_follows=FakeCollection([]),
        listings=FakeCollection([]),
        watchlist=FakeCollection([]),
        user_interests=FakeCollection(agg=[]),
    )
    user = {"id": "u1", "email": "a@b.com", "preferred_language": "en"}
    out = await build_user_digest(db, user)
    assert out is None, "should skip send when there's nothing personal to say"


@pytest.mark.asyncio
async def test_payload_contains_all_three_sections():
    _load_env()
    from services.weekly_digest import build_user_digest
    end_iso = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()

    seller_follows = FakeCollection([{"seller_id": "s1"}])
    seller_listing_row = {
        "id": "L1", "title": "Followed seller lot", "seller_id": "s1",
        "current_bid": 250, "image_url": "http://x/l1.jpg", "category": "electronics",
        "auction_end_time": end_iso, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    watch_listing_row = {
        "id": "W1", "title": "Watched lot", "current_bid": 100,
        "auction_end_time": end_iso, "image_url": "http://x/w1.jpg", "category": "electronics",
    }
    interest_listing_row = {
        "id": "I1", "title": "New match", "current_bid": None,
        "starting_price": 50, "image_url": "http://x/i1.jpg", "category": "electronics",
        "auction_end_time": end_iso, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    users_seller = {"id": "s1", "name": "Bob's Auctions"}

    class ScopedListings(FakeCollection):
        """Return seller-listing row on first call, interest-listing row on next."""
        def __init__(self):
            super().__init__([])
            self._calls = 0
        def find(self, q=None, proj=None):
            self._calls += 1
            # seller-listings query has seller_id: {"$in": [...]}
            if q and isinstance(q.get("seller_id"), dict) and "$in" in q["seller_id"]:
                return FakeCursor([seller_listing_row])
            # interest query has category:$in
            if q and isinstance(q.get("category"), dict) and "$in" in q["category"]:
                return FakeCursor([interest_listing_row])
            # watchlist enrichment uses id:$in
            if q and isinstance(q.get("id"), dict) and "$in" in q["id"]:
                return FakeCursor([watch_listing_row])
            return FakeCursor([])

    class ScopedUsers(FakeCollection):
        def find(self, q=None, proj=None):
            return FakeCursor([users_seller])

    db = FakeDB(
        seller_follows=seller_follows,
        listings=ScopedListings(),
        watchlist=FakeCollection([{"listing_id": "W1", "created_at": "z"}]),
        user_interests=FakeCollection(agg=[{"_id": "electronics", "n": 12}]),
        users=ScopedUsers(),
    )

    user = {"id": "u2", "email": "b@c.com", "first_name": "Alex", "preferred_language": "fr"}
    payload = await build_user_digest(db, user)

    assert payload is not None
    assert payload["lang"] == "fr", "should honor preferred_language=fr"
    assert payload["email"] == "b@c.com"
    assert payload["name"] == "Alex"
    assert len(payload["seller_listings"]) == 1
    assert payload["seller_listings"][0]["seller_name"] == "Bob's Auctions"
    assert len(payload["watchlist_updates"]) == 1
    assert payload["watchlist_updates"][0]["ends_in_seconds"] > 0
    assert len(payload["interest_listings"]) == 1
    assert payload["interest_listings"][0]["id"] == "I1"
    assert "electronics" in payload["categories"]


def test_template_renders_bilingual_html():
    from services.templates.weekly_digest_template import (
        render_weekly_digest_html, render_weekly_digest_subject,
    )
    payload = {
        "user_id": "u1", "email": "a@b.com", "name": "Sam", "lang": "en",
        "seller_listings": [{"id": "L1", "title": "Test lot", "current_bid": 100,
                             "auction_end_time": None, "seller_name": "Acme Auctions"}],
        "watchlist_updates": [{"id": "W1", "title": "Watched", "current_bid": 50,
                               "ends_in_seconds": 3600 * 26}],
        "interest_listings": [{"id": "I1", "title": "Match", "starting_price": 25}],
        "categories": ["electronics"],
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    subject_en = render_weekly_digest_subject(payload)
    assert "weekly" in subject_en.lower() or "picks" in subject_en.lower()
    html_en = render_weekly_digest_html(payload)
    assert "<!DOCTYPE html>" in html_en
    assert "This week on BidVex" in html_en
    assert "New from sellers you follow" in html_en, "seller section header missing (EN)"
    assert "Watchlist updates" in html_en
    assert "Matches for your interests" in html_en
    assert "Acme Auctions" in html_en
    assert "1d 2h" in html_en, "time_remaining should render as `1d 2h` for 26h"
    assert 'href="' in html_en, "cards must link to the lot page"

    payload["lang"] = "fr"
    subject_fr = render_weekly_digest_subject(payload)
    assert subject_fr != subject_en, "subject line should localize"
    html_fr = render_weekly_digest_html(payload)
    assert "Cette semaine sur BidVex" in html_fr
    assert "Nouveautés des vendeurs suivis" in html_fr
    assert "Se termine dans" in html_fr


@pytest.mark.asyncio
async def test_send_helper_respects_marketing_suppression(monkeypatch):
    """When the send_email dispatcher reports `status: skipped`, the audit
    row must be persisted with that status (and no error raised)."""
    _load_env()
    from services import weekly_digest as wd

    # Patch build_user_digest to return a canned payload.
    canned = {
        "user_id": "u9", "email": "opt@out.com", "name": "Opt", "lang": "en",
        "seller_listings": [{"id": "L1", "title": "T", "current_bid": 10, "seller_name": "S"}],
        "watchlist_updates": [], "interest_listings": [], "categories": [],
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    async def _fake_build(db, u): return canned
    monkeypatch.setattr(wd, "build_user_digest", _fake_build)

    # Patch send_email to simulate marketing suppression.
    from services.emails import _email_core as core
    async def _fake_send(**kw):
        return {"status": "skipped", "reason": "marketing_opt_out",
                "to": kw.get("to_email"), "subject": kw.get("subject")}
    monkeypatch.setattr(core, "send_email", _fake_send)

    class Audit(FakeCollection): pass
    audit = Audit()
    db = FakeDB(weekly_digest_sends=audit)

    out = await wd.send_weekly_digest_to_user(db, {"id": "u9", "email": "opt@out.com"})
    assert out["status"] == "skipped"
    assert len(audit.inserted) == 1
    assert audit.inserted[0]["status"] == "skipped"
    assert audit.inserted[0]["reason"] == "marketing_opt_out"


# ─── Scheduler wiring ─────────────────────────────────────────────────

def test_scheduler_uses_async_wrapper_not_lambda():
    src = Path("/app/backend/server.py").read_text()
    assert "async def _weekly_marketing_digest_tick" in src, (
        "iter378 scheduler wrapper missing"
    )
    assert "'weekly_marketing_digest'" in src or '"weekly_marketing_digest"' in src
    # Must not use the broken `lambda: safe_run(...)` pattern (iter377 lesson).
    assert "lambda: safe_run(\"weekly_marketing_digest\"" not in src
    assert "lambda: safe_run('weekly_marketing_digest'" not in src


def test_scheduler_uses_weekly_cron_trigger():
    src = Path("/app/backend/server.py").read_text()
    # Job runs once a week — assert weekly cron trigger config
    assert "day_of_week='mon'" in src or 'day_of_week="mon"' in src
    assert "id='weekly_marketing_digest'" in src or 'id="weekly_marketing_digest"' in src
