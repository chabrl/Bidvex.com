"""
iter315 — Legacy-logo patcher regression test.

Validates that the one-shot patcher in
`scripts/iter315_patch_legacy_logo.py`:
  • Identifies rows whose HTML lacks the canonical BidVex logo
  • Rewrites email_outbox rows in-place via inject_bidvex_logo_header()
  • Rewrites external_email_campaigns rows in-place via
    wrap_external_campaign_body() (per body_html_{en,fr})
  • Is idempotent (a second pass reports 0 affected)
  • Respects the dry-run / --execute flag boundary
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from scripts.iter315_patch_legacy_logo import (  # noqa: E402
    patch_email_outbox,
    patch_external_campaigns,
    OUTBOX_STATUSES_DEFAULT,
    CAMPAIGN_STATUSES_DEFAULT,
)
from services.emails._email_core import BIDVEX_LOGO_URL  # noqa: E402


def _with_loop(coro_factory):
    """Run an async test body with a fresh loop + motor client.
    `coro_factory` is a callable that takes the motor db and returns
    a coroutine."""
    loop = asyncio.new_event_loop()
    try:
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=loop)
        db = cli[os.environ["DB_NAME"]]
        loop.run_until_complete(coro_factory(db))
    finally:
        loop.close()


def test_patcher_rewrites_outbox_rows():
    """A queued outbox row without the canonical logo URL gets patched."""
    oid = str(uuid.uuid4())

    async def body(db):
        await db.email_outbox.insert_one({
            "id": oid, "status": "scheduled",
            "subject": "iter315 outbox patcher test",
            "to_email": "test@example.com",
            "html_content": "<table><tr><td>Plain body without logo</td></tr></table>",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_iter315_test": True,
        })
        try:
            rep_dry = await patch_email_outbox(
                db, execute=False, statuses=OUTBOX_STATUSES_DEFAULT, sample_n=3)
            assert rep_dry["affected"] >= 1
            doc = await db.email_outbox.find_one({"id": oid})
            assert BIDVEX_LOGO_URL not in doc["html_content"]

            rep_exec = await patch_email_outbox(
                db, execute=True, statuses=OUTBOX_STATUSES_DEFAULT, sample_n=3)
            assert rep_exec["affected"] >= 1
            doc = await db.email_outbox.find_one({"id": oid})
            assert BIDVEX_LOGO_URL in doc["html_content"]
            assert doc.get("iter315_patched_at")

            await patch_email_outbox(
                db, execute=True, statuses=OUTBOX_STATUSES_DEFAULT, sample_n=3)
            doc = await db.email_outbox.find_one({"id": oid})
            assert doc["html_content"].count(BIDVEX_LOGO_URL) == 1
        finally:
            await db.email_outbox.delete_one({"id": oid})

    _with_loop(body)


def test_patcher_wraps_external_campaigns():
    """An external_email_campaigns row gets header + CASL footer wrap."""
    cid = str(uuid.uuid4())

    async def body(db):
        await db.external_email_campaigns.insert_one({
            "id": cid, "name": "iter315 patcher test",
            "subject_en": "patcher test", "status": "draft",
            "body_html_en": "<h2>Hello from BidVex</h2>",
            "body_html_fr": "<h2>Bonjour</h2>",
            "recipient_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "_iter315_test": True,
        })
        try:
            rep_dry = await patch_external_campaigns(
                db, execute=False, statuses=CAMPAIGN_STATUSES_DEFAULT, sample_n=3)
            assert rep_dry["affected"] >= 1
            doc = await db.external_email_campaigns.find_one({"id": cid})
            assert BIDVEX_LOGO_URL not in doc["body_html_en"]

            rep_exec = await patch_external_campaigns(
                db, execute=True, statuses=CAMPAIGN_STATUSES_DEFAULT, sample_n=3)
            assert rep_exec["affected"] >= 1
            doc = await db.external_email_campaigns.find_one({"id": cid})
            assert BIDVEX_LOGO_URL in doc["body_html_en"]
            assert BIDVEX_LOGO_URL in doc["body_html_fr"]
            assert "{unsubscribe_url}" in doc["body_html_en"]
            assert doc.get("iter315_patched_at")

            doc1 = await db.external_email_campaigns.find_one({"id": cid})
            await patch_external_campaigns(
                db, execute=True, statuses=CAMPAIGN_STATUSES_DEFAULT, sample_n=3)
            doc2 = await db.external_email_campaigns.find_one({"id": cid})
            assert doc1["body_html_en"] == doc2["body_html_en"]
            assert doc1["body_html_fr"] == doc2["body_html_fr"]
        finally:
            await db.external_email_campaigns.delete_one({"id": cid})

    _with_loop(body)


def test_patcher_skips_already_logo_rows():
    """A row with the canonical URL already present is NOT touched."""
    oid = str(uuid.uuid4())
    pre_html = (
        f'<table><tr><td><img src="{BIDVEX_LOGO_URL}"></td></tr>'
        '<tr><td>body</td></tr></table>'
    )

    async def body(db):
        await db.email_outbox.insert_one({
            "id": oid, "status": "scheduled",
            "subject": "iter315 already-logo'd",
            "to_email": "test@example.com",
            "html_content": pre_html,
            "_iter315_test": True,
        })
        try:
            rep = await patch_email_outbox(
                db, execute=True, statuses=OUTBOX_STATUSES_DEFAULT, sample_n=3)
            affected_ids = {s.get("id") for s in rep["samples"]}
            assert oid not in affected_ids
            doc = await db.email_outbox.find_one({"id": oid})
            assert doc["html_content"] == pre_html
            assert "iter315_patched_at" not in doc
        finally:
            await db.email_outbox.delete_one({"id": oid})

    _with_loop(body)
