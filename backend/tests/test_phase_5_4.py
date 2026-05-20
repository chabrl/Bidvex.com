"""
Phase 5.4 — Backend tests for:
  Task 1 : Weekly funnel digest cron — math, zero-division safety, idempotency, HTML quality.
  Task 2 : (frontend testid + cookie auto-dismiss are JS-side, tested via smoke screenshot)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from jobs.analytics_digest_cron import (
    _delta_pct,
    _safe_pct,
    _render_digest_rows,
    _render_digest_html,
    _format_delta_html,
)


# ── _delta_pct safety ────────────────────────────────────────────────────

def test_delta_pct_handles_zero_prior_with_zero_this_week():
    """No traffic at all in either window → 0%, NOT NaN."""
    assert _delta_pct(0, 0) == 0.0


def test_delta_pct_handles_zero_prior_with_positive_this_week():
    """Brand-new traffic → returns +inf (rendered as 'New' in HTML)."""
    assert _delta_pct(50, 0) == float("inf")


def test_delta_pct_positive_growth():
    assert _delta_pct(120, 100) == 20.0


def test_delta_pct_negative_growth():
    assert _delta_pct(80, 100) == -20.0


def test_delta_pct_rounding():
    assert _delta_pct(33, 100) == -67.0
    assert _delta_pct(7, 11) == round(100.0 * (7 - 11) / 11, 2)


def test_safe_pct_zero_denom_returns_zero():
    assert _safe_pct(0, 0) == 0.0
    assert _safe_pct(100, 0) == 0.0


# ── _format_delta_html safety ────────────────────────────────────────────

def test_format_delta_html_none():
    assert "&mdash;" in _format_delta_html(None)


def test_format_delta_html_infinite():
    out = _format_delta_html(float("inf"))
    assert "New" in out


def test_format_delta_html_positive():
    assert "+15.0%" in _format_delta_html(15.0)


def test_format_delta_html_negative():
    assert "-15.0%" in _format_delta_html(-15.0)


def test_format_delta_html_zero():
    assert "0%" in _format_delta_html(0.0)


# ── _render_digest_rows shape ────────────────────────────────────────────

def test_render_digest_rows_returns_4_stages():
    rows = _render_digest_rows(
        {"views": 100, "bids_proxies": 30, "binding_matches": 5, "settled": 2},
        {"views":  80, "bids_proxies": 20, "binding_matches": 4, "settled": 1},
    )
    assert len(rows) == 4
    assert {r["key"] for r in rows} == {"views", "bids_proxies", "binding_matches", "settled"}
    by_key = {r["key"]: r for r in rows}
    assert by_key["views"]["this_week"] == 100
    assert by_key["views"]["prior_week"] == 80
    assert by_key["views"]["delta_pct"] == 25.0


def test_render_digest_rows_with_all_zeros():
    """If both windows are empty the math should NOT crash."""
    rows = _render_digest_rows(
        {"views": 0, "bids_proxies": 0, "binding_matches": 0, "settled": 0},
        {"views": 0, "bids_proxies": 0, "binding_matches": 0, "settled": 0},
    )
    for r in rows:
        assert r["delta_pct"] == 0.0
        assert r["this_week"] == 0
        assert r["prior_week"] == 0


# ── _render_digest_html ──────────────────────────────────────────────────

def test_render_digest_html_contains_required_content():
    since_this  = datetime(2026, 5, 11, 0, 0, tzinfo=timezone.utc)
    until_this  = datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc)
    since_prior = datetime(2026, 5, 4,  0, 0, tzinfo=timezone.utc)
    until_prior = since_this
    this_week  = {"views": 1000, "bids_proxies": 100, "binding_matches": 12, "settled": 8}
    prior_week = {"views":  800, "bids_proxies":  90, "binding_matches": 10, "settled": 5}
    rows = _render_digest_rows(this_week, prior_week)
    html = _render_digest_html(
        this_week=this_week, prior_week=prior_week, rows=rows,
        since_this=since_this, until_this=until_this,
        since_prior=since_prior, until_prior=until_prior,
    )
    assert "<!DOCTYPE html>" in html
    assert "Weekly Conversion Funnel Digest" in html
    assert "Bilan hebdomadaire" in html
    # All 4 stages rendered
    assert "Auction Views" in html
    assert "Bids / Proxy Auth." in html
    assert "Broker Bindings Matched" in html
    assert "Settled Transactions" in html
    # Numbers rendered with comma thousands-separator
    assert "1,000" in html
    # Overall conversion line
    assert "Overall view" in html
    # Live dashboard CTA
    assert "/admin?tab=conversion-funnel" in html
    # Footer brand
    assert "BidVex Canada" in html


def test_render_digest_html_with_zero_traffic_no_nan():
    """Empty windows on both sides must NOT produce NaN / Infinity in the HTML."""
    since_this  = datetime(2026, 5, 11, tzinfo=timezone.utc)
    until_this  = datetime(2026, 5, 18, tzinfo=timezone.utc)
    since_prior = datetime(2026, 5, 4,  tzinfo=timezone.utc)
    until_prior = since_this
    empty = {"views": 0, "bids_proxies": 0, "binding_matches": 0, "settled": 0}
    rows = _render_digest_rows(empty, empty)
    html = _render_digest_html(
        this_week=empty, prior_week=empty, rows=rows,
        since_this=since_this, until_this=until_this,
        since_prior=since_prior, until_prior=until_prior,
    )
    assert "NaN" not in html
    assert "Infinity" not in html
    assert "0.00%" in html


# ── queue_weekly_funnel_digest — uses local Mongo via Motor (codebase pattern) ─

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

_TEST_DB_NAME = os.environ.get("DB_NAME", "bidvex_local") + "_p54_test"


@pytest.fixture
def db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[_TEST_DB_NAME]


@pytest.fixture(autouse=True)
def _cleanup_isolated_db():
    """Drop the isolated phase-5.4 test DB before and after each test."""
    sync = MongoClient(os.environ["MONGO_URL"])
    sync.drop_database(_TEST_DB_NAME)
    yield
    sync.drop_database(_TEST_DB_NAME)
    sync.close()


@pytest.mark.asyncio
async def test_queue_weekly_funnel_digest_inserts_row(db):
    """End-to-end: feeds an empty db and confirms the digest row lands in email_outbox."""
    from jobs.analytics_digest_cron import queue_weekly_funnel_digest

    result = await queue_weekly_funnel_digest(db)
    assert result["queued"] is True
    assert result["recipient"]
    row = await db.email_outbox.find_one({"id": result["row_id"]}, {"_id": 0})
    assert row is not None
    assert row["kind"] == "weekly_funnel_digest"
    assert row["subject"].startswith("[BidVex] Weekly Funnel Digest")
    assert row["html"].startswith("<!DOCTYPE html>")
    assert row["to_email"]
    # No float('inf') stored — Mongo BSON cannot serialise inf
    for r in row["context"]["rows"]:
        assert r["delta_pct"] is None or isinstance(r["delta_pct"], (int, float))


@pytest.mark.asyncio
async def test_queue_weekly_funnel_digest_idempotent_per_day(db):
    """Calling twice on the same UTC date should NOT queue twice."""
    from jobs.analytics_digest_cron import queue_weekly_funnel_digest
    a = await queue_weekly_funnel_digest(db)
    b = await queue_weekly_funnel_digest(db)
    assert a["queued"] is True
    assert b["queued"] is False
    assert b["reason"] == "already_queued_today"
    count = await db.email_outbox.count_documents({"kind": "weekly_funnel_digest"})
    assert count == 1


@pytest.mark.asyncio
async def test_queue_weekly_funnel_digest_aggregates_real_traffic(db):
    """Seed views + bids + matched binding + settled invoice rows in BOTH
    windows and confirm the digest math reflects the seed data."""
    from jobs.analytics_digest_cron import queue_weekly_funnel_digest

    now = datetime.now(timezone.utc)
    this_window_created = now - timedelta(days=2)   # falls inside last 7d
    prior_window_created = now - timedelta(days=10)  # falls inside prior 7d

    # Stage 1 — views on listings (single-item + multi-item)
    await db.listings.insert_many([
        {"id": "l1", "views": 1000, "created_at": this_window_created},
        {"id": "l2", "views": 500,  "created_at": prior_window_created},
    ])
    await db.multi_item_listings.insert_many([
        {"id": "m1", "views": 200, "created_at": this_window_created},
    ])
    # Stage 2 — bids + proxies
    await db.bids.insert_many([
        {"id": "b1", "created_at": this_window_created},
        {"id": "b2", "created_at": this_window_created},
        {"id": "b3", "created_at": prior_window_created},
    ])
    await db.broker_proxy_authorizations.insert_many([
        {"id": "p1", "created_at": this_window_created},
    ])
    # Stage 3 — matched binding
    await db.broker_binding_requests.insert_many([
        {"id": "br1", "status": "matched", "created_at": this_window_created},
        {"id": "br2", "status": "pending", "created_at": this_window_created},  # not counted
    ])
    # Stage 4 — settled
    await db.broker_invoices.insert_many([
        {"id": "i1", "status": "paid",    "created_at": this_window_created},
        {"id": "i2", "status": "settled", "created_at": prior_window_created},
        {"id": "i3", "status": "pending", "created_at": this_window_created},  # not counted
    ])

    result = await queue_weekly_funnel_digest(db)
    assert result["queued"] is True
    assert result["this_week"]["views"] == 1200    # 1000 + 200
    assert result["this_week"]["bids_proxies"] == 3  # 2 bids + 1 proxy
    assert result["this_week"]["binding_matches"] == 1
    assert result["this_week"]["settled"] == 1
    assert result["prior_week"]["views"] == 500
    assert result["prior_week"]["bids_proxies"] == 1
    assert result["prior_week"]["binding_matches"] == 0
    assert result["prior_week"]["settled"] == 1
