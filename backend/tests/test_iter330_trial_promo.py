"""iter330 — Tests for trial + first-listing-free promo service.

Covers:
  • is_trial_eligible — fresh user, redeemed user, missing user, ineligible tier.
  • mark_trial_redeemed — happy path + double-redeem race.
  • is_first_listing_free_eligible — fresh / used / missing.
  • try_consume_first_listing_free — single-shot, idempotent on double-call.
  • get_promo_state — all field combinations.
  • Empty-projection-dict bug guard (find_one returns {} when projected
    fields don't exist on the doc — must NOT be treated as "user not found").
"""
from __future__ import annotations

import sys
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Make backend/ importable when run directly.
sys.path.insert(0, "/app/backend")

# Load env so MONGO_URL is available.
if "MONGO_URL" not in os.environ:
    env_file = Path("/app/backend/.env")
    if env_file.exists():
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.trial_promo import (  # noqa: E402
    TRIAL_ELIGIBLE_TIERS,
    TRIAL_DAYS,
    is_trial_eligible,
    mark_trial_redeemed,
    is_first_listing_free_eligible,
    try_consume_first_listing_free,
    get_promo_state,
)


def _with_loop(coro_factory):
    loop = asyncio.new_event_loop()
    try:
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        loop.run_until_complete(coro_factory(db))
    finally:
        loop.close()


async def _seed_user(db, uid: str, **fields):
    doc = {"id": uid, "email": f"{uid}@test.local", "role": "buyer", **fields}
    await db.users.replace_one({"id": uid}, doc, upsert=True)


async def _cleanup(db, uid: str):
    await db.users.delete_one({"id": uid})


# ─── Constants check ──────────────────────────────────────────────────


def test_trial_days_is_30():
    assert TRIAL_DAYS == 30


def test_eligible_tiers_complete():
    assert "premium" in TRIAL_ELIGIBLE_TIERS
    assert "vip" in TRIAL_ELIGIBLE_TIERS
    assert "partner" in TRIAL_ELIGIBLE_TIERS
    assert "partner_pro" in TRIAL_ELIGIBLE_TIERS
    assert "vehicle_dealer" in TRIAL_ELIGIBLE_TIERS
    assert "storage_facility" in TRIAL_ELIGIBLE_TIERS
    assert "free" not in TRIAL_ELIGIBLE_TIERS
    assert "basic" not in TRIAL_ELIGIBLE_TIERS


# ─── is_trial_eligible ────────────────────────────────────────────────


def test_trial_eligible_fresh_user():
    async def body(db):
        uid = f"test-trial-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            assert await is_trial_eligible(db, uid) is True
            assert await is_trial_eligible(db, uid, tier="premium") is True
            assert await is_trial_eligible(db, uid, tier="vehicle_dealer") is True
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


def test_trial_NOT_eligible_after_redeem():
    async def body(db):
        uid = f"test-trial-redeemed-{datetime.now().timestamp()}"
        await _seed_user(db, uid, trial_redeemed_at=datetime.now(timezone.utc).isoformat())
        try:
            assert await is_trial_eligible(db, uid) is False
            assert await is_trial_eligible(db, uid, tier="premium") is False
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


def test_trial_NOT_eligible_for_free_tier():
    async def body(db):
        uid = f"test-trial-free-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            # Even a fresh user is ineligible if they ask for the free tier.
            assert await is_trial_eligible(db, uid, tier="free") is False
            assert await is_trial_eligible(db, uid, tier="basic") is False
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


def test_trial_NOT_eligible_when_user_missing():
    async def body(db):
        # Never seed — user doesn't exist.
        uid = "test-nonexistent-user-12345-iter330"
        assert await is_trial_eligible(db, uid) is False
    _with_loop(body)


def test_trial_eligible_handles_empty_projection_dict():
    """Regression for the find_one-returns-{} bug.

    When `find_one` projects fields that don't exist on the doc, MongoDB
    returns an empty dict. The eligibility check must NOT mistake {} for
    "user not found" — the user still exists, they just lack the flag.
    """
    async def body(db):
        uid = f"test-empty-proj-{datetime.now().timestamp()}"
        # Seed user WITHOUT the trial_redeemed_at field.
        await _seed_user(db, uid)
        try:
            # Should be eligible — fresh user, no trial ever taken.
            assert await is_trial_eligible(db, uid) is True
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


# ─── mark_trial_redeemed ──────────────────────────────────────────────


def test_mark_trial_redeemed_happy_path():
    async def body(db):
        uid = f"test-redeem-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            assert await mark_trial_redeemed(db, uid, "premium") is True
            doc = await db.users.find_one({"id": uid})
            assert doc.get("trial_redeemed_at") is not None
            assert doc.get("trial_redeemed_tier") == "premium"
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


def test_double_redeem_race_returns_false():
    async def body(db):
        uid = f"test-double-redeem-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            # First call wins, returns True.
            assert await mark_trial_redeemed(db, uid, "premium") is True
            # Second call must return False (already redeemed).
            assert await mark_trial_redeemed(db, uid, "vip") is False
            # And the original tier is preserved (not overwritten).
            doc = await db.users.find_one({"id": uid})
            assert doc.get("trial_redeemed_tier") == "premium"
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


# ─── first-listing-free ───────────────────────────────────────────────


def test_first_listing_free_eligible_fresh_user():
    async def body(db):
        uid = f"test-flf-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            assert await is_first_listing_free_eligible(db, uid) is True
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


def test_first_listing_free_consume_idempotent():
    async def body(db):
        uid = f"test-flf-consume-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            # First consume returns True (eligible → consumed now).
            assert await try_consume_first_listing_free(db, uid) is True
            # Second consume returns False (already consumed).
            assert await try_consume_first_listing_free(db, uid) is False
            assert await try_consume_first_listing_free(db, uid) is False
            assert await is_first_listing_free_eligible(db, uid) is False
            doc = await db.users.find_one({"id": uid})
            assert doc.get("first_listing_free_used") is True
            assert doc.get("first_listing_free_consumed_at") is not None
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


# ─── get_promo_state ──────────────────────────────────────────────────


def test_get_promo_state_fresh_user():
    async def body(db):
        uid = f"test-state-fresh-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            state = await get_promo_state(db, uid)
            assert state["trial_eligible"] is True
            assert state["trial_redeemed_at"] is None
            assert state["trial_redeemed_tier"] is None
            assert state["first_listing_free_eligible"] is True
            assert state["first_listing_free_used"] is False
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


def test_get_promo_state_missing_user():
    async def body(db):
        state = await get_promo_state(db, "nonexistent-iter330-xyz")
        assert state["trial_eligible"] is False
        assert state["first_listing_free_eligible"] is False
    _with_loop(body)


def test_get_promo_state_after_both_consumed():
    async def body(db):
        uid = f"test-state-fully-used-{datetime.now().timestamp()}"
        await _seed_user(db, uid)
        try:
            await mark_trial_redeemed(db, uid, "vip")
            await try_consume_first_listing_free(db, uid)
            state = await get_promo_state(db, uid)
            assert state["trial_eligible"] is False
            assert state["trial_redeemed_tier"] == "vip"
            assert state["first_listing_free_eligible"] is False
            assert state["first_listing_free_used"] is True
        finally:
            await _cleanup(db, uid)
    _with_loop(body)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
