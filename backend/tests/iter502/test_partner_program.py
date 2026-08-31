"""iter502 — Influencer Partner Program time-bound rate schedule tests.

Covers:
  * Rate ceiling raised from 20% → 75% (both flat commission_rate and
    tier rates accept up to 0.75).
  * _resolve_effective_rate precedence:
      1) flat commission_rate override wins
      2) partner_program tier schedule (T1 window → T2)
      3) global default 3%
  * Auto-stamp partnership_start_date on activation when partner_program=True.
  * Partner rates snapshotted at commission-award time on the credit row.
  * Automatic tier fall-through (no cron): re-run the same call after the
    tier-1 window elapses and the awarded rate switches to tier_2.
  * Non-partner affiliates: zero behavior change (still 3% or their flat
    commission_rate override).
  * Admin endpoints accept + validate partner fields.
  * Idempotency for partner-field updates.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

from routes.affiliate import (  # noqa: E402
    AFFILIATE_PROFIT_SHARE_RATE,
    MAX_AFFILIATE_COMMISSION_RATE,
    PARTNER_PROGRAM_TIER1_DURATION_MONTHS_DEFAULT,
    PARTNER_PROGRAM_TIER1_RATE_DEFAULT,
    PARTNER_PROGRAM_TIER2_RATE_DEFAULT,
    _resolve_effective_rate,
    _validate_partner_fields,
    admin_set_affiliate_rate,
    admin_set_affiliate_status,
    award_affiliate_commission,
)
from deps import User, set_db as _set_deps_db  # noqa: E402


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    _set_deps_db(database)
    yield database
    client.close()


def _admin() -> User:
    return User(
        id=f"iter502-admin-{uuid.uuid4().hex[:6]}",
        email="test-admin@bidvex.com",
        name="Test Admin",
        role="super_admin",
    )


async def _cleanup(db, *ids):
    await db.users.delete_many({"id": {"$in": list(ids)}})
    for uid in ids:
        await db.platform_credits.delete_many({"user_id": uid})
    await db.admin_action_logs.delete_many({"target_user_id": {"$in": list(ids)}})


# ─────────────────────────────────────────────────────────────────────
# Rate ceiling raised to 75%
# ─────────────────────────────────────────────────────────────────────

def test_ceiling_raised_to_75_percent():
    assert MAX_AFFILIATE_COMMISSION_RATE >= 0.75 - 1e-9


def test_partner_program_defaults():
    assert PARTNER_PROGRAM_TIER1_RATE_DEFAULT == pytest.approx(0.50)
    assert PARTNER_PROGRAM_TIER1_DURATION_MONTHS_DEFAULT == 6
    assert PARTNER_PROGRAM_TIER2_RATE_DEFAULT == pytest.approx(0.05)


# ─────────────────────────────────────────────────────────────────────
# _resolve_effective_rate — precedence
# ─────────────────────────────────────────────────────────────────────

def test_flat_override_wins_over_partner_program():
    doc = {
        "commission_rate": 0.42,
        "partner_program": True,
        "tier_1_rate": 0.50,
        "tier_1_duration_months": 6,
        "tier_2_rate": 0.05,
        "partnership_start_date": datetime.now(timezone.utc).isoformat(),
    }
    assert _resolve_effective_rate(doc) == 0.42


def test_partner_tier_1_within_window():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    doc = {
        "partner_program": True,
        "tier_1_rate": 0.50,
        "tier_1_duration_months": 6,
        "tier_2_rate": 0.05,
        "partnership_start_date": (now - timedelta(days=30)).isoformat(),
    }
    # 30 days in, tier-1 lasts 6 months → still tier 1.
    assert _resolve_effective_rate(doc, now=now) == 0.50


def test_partner_tier_2_after_window():
    now = datetime(2026, 6, 15, tzinfo=timezone.utc)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)  # >12 months ago
    doc = {
        "partner_program": True,
        "tier_1_rate": 0.50,
        "tier_1_duration_months": 6,
        "tier_2_rate": 0.05,
        "partnership_start_date": start.isoformat(),
    }
    assert _resolve_effective_rate(doc, now=now) == 0.05


def test_partner_tier_1_when_no_start_date_yet():
    """Guard for the edge where the user is flagged partner_program=True
    but the migration hasn't stamped a start date yet.  The opener rate
    (tier_1) should still apply — never falls back to the global 3%."""
    doc = {
        "partner_program": True,
        "tier_1_rate": 0.50,
        "tier_2_rate": 0.05,
    }
    assert _resolve_effective_rate(doc) == 0.50


def test_partner_uses_program_defaults_when_fields_missing():
    doc = {
        "partner_program": True,
        # no tier fields set
        "partnership_start_date": datetime.now(timezone.utc).isoformat(),
    }
    assert _resolve_effective_rate(doc) == PARTNER_PROGRAM_TIER1_RATE_DEFAULT


def test_non_partner_still_uses_3pct_default():
    doc = {"partner_program": False}
    assert _resolve_effective_rate(doc) == AFFILIATE_PROFIT_SHARE_RATE


def test_non_partner_flat_override_wins():
    doc = {"partner_program": False, "commission_rate": 0.10}
    assert _resolve_effective_rate(doc) == 0.10


def test_partner_tier_boundary_moment_uses_tier_2():
    """The instant the tier-1 window closes we flip to tier-2."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    doc = {
        "partner_program": True,
        "tier_1_rate": 0.50,
        "tier_1_duration_months": 6,
        "tier_2_rate": 0.05,
        "partnership_start_date": start.isoformat(),
    }
    # 6 months * 30.4375 days = 182.625 days.  A microsecond past that
    # boundary is tier-2.
    boundary = start + timedelta(days=6 * 30.4375, microseconds=1)
    assert _resolve_effective_rate(doc, now=boundary) == 0.05
    # A microsecond before → still tier-1.
    before = start + timedelta(days=6 * 30.4375, microseconds=-1)
    assert _resolve_effective_rate(doc, now=before) == 0.50


def test_partner_stale_out_of_range_rate_clamped():
    """A DB row with a stale huge rate must clamp to the ceiling —
    the read-side never blocks a legitimate award."""
    doc = {
        "partner_program": True,
        "tier_1_rate": 5.0,  # 500% — clearly bogus
        "tier_1_duration_months": 6,
        "tier_2_rate": 0.05,
    }
    assert _resolve_effective_rate(doc) == MAX_AFFILIATE_COMMISSION_RATE


# ─────────────────────────────────────────────────────────────────────
# _validate_partner_fields
# ─────────────────────────────────────────────────────────────────────

def test_validate_partner_fields_accepts_valid_partial():
    out = _validate_partner_fields({"partner_program": True, "tier_1_rate": 0.5})
    assert out == {"partner_program": True, "tier_1_rate": 0.5}


def test_validate_partner_fields_ceiling_75_accepted():
    out = _validate_partner_fields({"tier_1_rate": 0.75})
    assert out["tier_1_rate"] == 0.75


def test_validate_partner_fields_ceiling_over_75_rejected():
    with pytest.raises(HTTPException) as exc:
        _validate_partner_fields({"tier_1_rate": 0.80})
    assert exc.value.status_code == 400


def test_validate_partner_fields_negative_duration_rejected():
    with pytest.raises(HTTPException) as exc:
        _validate_partner_fields({"tier_1_duration_months": 0})
    assert exc.value.status_code == 400


def test_validate_partner_fields_bad_date_rejected():
    with pytest.raises(HTTPException) as exc:
        _validate_partner_fields({"partnership_start_date": "not-a-date"})
    assert exc.value.status_code == 400


def test_validate_partner_fields_iso_date_accepted():
    out = _validate_partner_fields({"partnership_start_date": "2026-01-15T00:00:00Z"})
    assert out["partnership_start_date"] is not None


def test_validate_partner_fields_empty_payload_is_empty():
    assert _validate_partner_fields({}) == {}


# ─────────────────────────────────────────────────────────────────────
# admin_set_affiliate_status — partner fields
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_activate_partner_auto_stamps_start_date(db):
    admin = _admin()
    target_id = f"iter502-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({"id": target_id, "name": "T", "email": f"{target_id}@x.com"})
    try:
        before = datetime.now(timezone.utc)
        result = await admin_set_affiliate_status(
            {"user_id": target_id, "status": "active",
             "partner_program": True,
             "tier_1_rate": 0.60},
            current_user=admin,
        )
        after = datetime.now(timezone.utc)
        assert result["success"] is True
        assert result["partner_program"] is True
        assert result["tier_1_rate"] == 0.60
        assert result["partnership_start_date"] is not None
        stamped = datetime.fromisoformat(
            result["partnership_start_date"].replace("Z", "+00:00"))
        # Must land inside our window.
        assert before - timedelta(seconds=1) <= stamped <= after + timedelta(seconds=1)
        # Effective rate = tier_1_rate (60%)
        assert result["effective_rate"] == 0.60
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_activate_partner_respects_explicit_start_date(db):
    admin = _admin()
    target_id = f"iter502-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({"id": target_id, "name": "T", "email": f"{target_id}@x.com"})
    try:
        explicit = "2026-01-01T00:00:00+00:00"
        result = await admin_set_affiliate_status(
            {"user_id": target_id, "status": "active",
             "partner_program": True,
             "partnership_start_date": explicit},
            current_user=admin,
        )
        assert result["partnership_start_date"] == explicit
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_partner_fields_audit_log_captured(db):
    admin = _admin()
    target_id = f"iter502-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({"id": target_id, "name": "T", "email": f"{target_id}@x.com"})
    try:
        await admin_set_affiliate_status(
            {"user_id": target_id, "status": "active",
             "partner_program": True, "tier_1_rate": 0.40,
             "tier_1_duration_months": 3, "tier_2_rate": 0.07},
            current_user=admin,
        )
        log = await db.admin_action_logs.find_one({
            "target_user_id": target_id,
            "action": "affiliate_status_change",
        })
        assert log is not None
        # Before must record no partner data
        assert log["before"].get("partner_program") in (None, False)
        # After captures the new tier snapshot
        assert log["after"]["partner_program"] is True
        assert log["after"]["tier_1_rate"] == 0.40
        assert log["after"]["tier_1_duration_months"] == 3
        assert log["after"]["tier_2_rate"] == 0.07
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_partner_setup_idempotent(db):
    admin = _admin()
    target_id = f"iter502-target-{uuid.uuid4().hex[:6]}"
    start = datetime.now(timezone.utc).isoformat()
    await db.users.insert_one({
        "id": target_id, "name": "T", "email": f"{target_id}@x.com",
        "affiliate_status": "active",
        "partner_program": True,
        "tier_1_rate": 0.50, "tier_1_duration_months": 6, "tier_2_rate": 0.05,
        "partnership_start_date": start,
    })
    try:
        r = await admin_set_affiliate_rate(
            {"user_id": target_id,
             "partner_program": True, "tier_1_rate": 0.50,
             "tier_1_duration_months": 6, "tier_2_rate": 0.05},
            current_user=admin,
        )
        assert r["changed"] is False
        n_logs = await db.admin_action_logs.count_documents(
            {"target_user_id": target_id})
        assert n_logs == 0
    finally:
        await _cleanup(db, target_id)


# ─────────────────────────────────────────────────────────────────────
# End-to-end: award_affiliate_commission uses tier rate
# ─────────────────────────────────────────────────────────────────────

async def _seed_partner_pair(db, *, start_offset_days: int = 0,
                              tier_1_rate: float = 0.50,
                              tier_2_rate: float = 0.05,
                              tier_1_duration_months: int = 6):
    suffix = uuid.uuid4().hex[:8]
    referrer_id = f"iter502-partner-{suffix}"
    payer_id = f"iter502-payer-{suffix}"
    code = f"P502{suffix[:4].upper()}"
    start_dt = datetime.now(timezone.utc) - timedelta(days=start_offset_days)
    await db.users.insert_one({
        "id": referrer_id, "email": f"{referrer_id}@x.com", "name": "Partner",
        "affiliate_code": code, "affiliate_status": "active",
        "partner_program": True,
        "tier_1_rate": tier_1_rate,
        "tier_1_duration_months": tier_1_duration_months,
        "tier_2_rate": tier_2_rate,
        "partnership_start_date": start_dt.isoformat(),
    })
    await db.users.insert_one({
        "id": payer_id, "email": f"{payer_id}@x.com", "name": "Payer",
        "referred_by_code": code,
    })
    return referrer_id, payer_id, suffix


@pytest.mark.asyncio
async def test_award_uses_tier_1_within_window(db):
    referrer_id, payer_id, suffix = await _seed_partner_pair(
        db, start_offset_days=30, tier_1_rate=0.50)
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=200.0,
            source="auction_buyer_fee",
            reference_id=f"iter502:t1:{suffix}",
        )
        assert credit is not None
        assert credit["commission_rate"] == 0.50
        assert credit["amount"] == 100.0  # 50% of $200
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.asyncio
async def test_award_uses_tier_2_after_window(db):
    """Partner whose 6-month tier-1 window has already lapsed (started
    12 months ago) receives 5% automatically — no cron, no admin flip."""
    referrer_id, payer_id, suffix = await _seed_partner_pair(
        db, start_offset_days=365, tier_1_rate=0.50, tier_2_rate=0.05,
        tier_1_duration_months=6)
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=200.0,
            source="auction_buyer_fee",
            reference_id=f"iter502:t2:{suffix}",
        )
        assert credit is not None
        assert credit["commission_rate"] == 0.05
        assert credit["amount"] == 10.0  # 5% of $200
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.asyncio
async def test_award_flat_override_wins_over_partner_tiers(db):
    """A partner with an explicit commission_rate override still uses
    that override — the tier schedule is disabled by the escape hatch."""
    referrer_id, payer_id, suffix = await _seed_partner_pair(
        db, start_offset_days=30, tier_1_rate=0.50)
    await db.users.update_one({"id": referrer_id},
                              {"$set": {"commission_rate": 0.10}})
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee",
            reference_id=f"iter502:flat:{suffix}",
        )
        assert credit is not None
        assert credit["commission_rate"] == 0.10
        assert credit["amount"] == 10.0
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.asyncio
async def test_non_partner_general_affiliate_unchanged(db):
    """A general affiliate (partner_program=False, no override) still
    earns exactly 3% — zero behaviour change."""
    suffix = uuid.uuid4().hex[:8]
    referrer_id = f"iter502-gen-{suffix}"
    payer_id = f"iter502-payer-{suffix}"
    code = f"G502{suffix[:4].upper()}"
    await db.users.insert_one({
        "id": referrer_id, "email": f"{referrer_id}@x.com", "name": "Gen",
        "affiliate_code": code, "affiliate_status": "active",
    })
    await db.users.insert_one({
        "id": payer_id, "email": f"{payer_id}@x.com", "name": "Payer",
        "referred_by_code": code,
    })
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=200.0,
            source="auction_buyer_fee",
            reference_id=f"iter502:gen:{suffix}",
        )
        assert credit is not None
        assert credit["commission_rate"] == AFFILIATE_PROFIT_SHARE_RATE
        assert credit["amount"] == 6.0  # 3% of $200
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.asyncio
async def test_partner_high_rate_awarded_when_ceiling_allows(db):
    """Now that the ceiling is 75%, a 70% partner rate works end-to-end."""
    admin = _admin()
    referrer_id, payer_id, suffix = await _seed_partner_pair(
        db, start_offset_days=10, tier_1_rate=0.05)  # placeholder
    # Bump tier_1 to 70 % — must be accepted with the raised ceiling
    await admin_set_affiliate_rate(
        {"user_id": referrer_id, "tier_1_rate": 0.70},
        current_user=admin,
    )
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee",
            reference_id=f"iter502:high:{suffix}",
        )
        assert credit is not None
        assert credit["commission_rate"] == 0.70
        assert credit["amount"] == 70.0
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.asyncio
async def test_snapshot_survives_tier_config_change(db):
    """Once a credit is written it MUST NOT change if the partner's tier
    config is later edited.  History is immutable."""
    referrer_id, payer_id, suffix = await _seed_partner_pair(
        db, start_offset_days=15, tier_1_rate=0.50)
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee",
            reference_id=f"iter502:snap:{suffix}",
        )
        assert credit["commission_rate"] == 0.50
        # Admin edits tier_1_rate
        await db.users.update_one(
            {"id": referrer_id}, {"$set": {"tier_1_rate": 0.25}},
        )
        row = await db.platform_credits.find_one({"id": credit["id"]})
        assert row["commission_rate"] == 0.50
        assert row["amount"] == 50.0
    finally:
        await _cleanup(db, referrer_id, payer_id)
