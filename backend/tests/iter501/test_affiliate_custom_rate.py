"""iter501 — Per-affiliate custom commission rate + approval gate tests.

Covers:
  * Default-rate fallback (referrer has no commission_rate → 3%)
  * Custom-rate override (commission_rate=0.05 → 5% applied + snapshotted
    on the credit row)
  * Historical rows never retroactively change when admin bumps rate
  * Inactive-status referrer (status="none"/"pending"/"revoked") → no
    commission awarded, no side effects
  * Admin set-status endpoint — 400 on out-of-range rate, idempotent
  * Admin set-rate endpoint — 400 on out-of-range rate, audit log
  * Backfill migration — promotes prior-earning users to "active" only if
    their status is unset/none (never overrides explicit statuses)
  * Legacy PUT /admin/users/{id}/affiliate shim → writes to user doc
    canonically (no db.affiliates row)
"""
from __future__ import annotations

import os
import sys
import uuid
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
    _backfill_active_affiliates,
    _resolve_effective_rate,
    _validate_rate,
    admin_set_affiliate_rate,
    admin_set_affiliate_status,
    award_affiliate_commission,
)
from deps import User, set_db as _set_deps_db  # noqa: E402


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    # Bind the test DB into deps.get_db() so admin endpoints (which call
    # get_db() internally) see the same handle the fixture uses.
    _set_deps_db(database)
    yield database
    client.close()


def _admin() -> User:
    return User(
        id=f"iter501-admin-{uuid.uuid4().hex[:6]}",
        email="test-admin@bidvex.com",
        name="Test Admin",
        role="super_admin",
    )


def _non_admin() -> User:
    return User(
        id=f"iter501-user-{uuid.uuid4().hex[:6]}",
        email="test-user@bidvex.com",
        name="Test User",
        role="user",
    )


async def _seed_referrer_payer(db, *, status: str = "active",
                                commission_rate=None):
    suffix = uuid.uuid4().hex[:8]
    referrer_id = f"iter501-ref-{suffix}"
    payer_id = f"iter501-payer-{suffix}"
    code = f"I501{suffix[:4].upper()}"
    referrer_doc = {
        "id": referrer_id,
        "name": "Ref User",
        "email": f"{referrer_id}@example.com",
        "affiliate_code": code,
        "affiliate_status": status,
    }
    if commission_rate is not None:
        referrer_doc["commission_rate"] = commission_rate
    await db.users.insert_one(referrer_doc)
    await db.users.insert_one({
        "id": payer_id,
        "name": "Payer User",
        "email": f"{payer_id}@example.com",
        "referred_by_code": code,
    })
    return referrer_id, payer_id, code, suffix


async def _cleanup(db, *ids):
    await db.users.delete_many({"id": {"$in": list(ids)}})
    for uid in ids:
        await db.platform_credits.delete_many({"user_id": uid})
    await db.admin_action_logs.delete_many({"target_user_id": {"$in": list(ids)}})


# ─────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────

def test_resolve_effective_rate_falls_back_when_null():
    assert _resolve_effective_rate({}) == AFFILIATE_PROFIT_SHARE_RATE
    assert _resolve_effective_rate(None) == AFFILIATE_PROFIT_SHARE_RATE
    assert _resolve_effective_rate({"commission_rate": None}) == AFFILIATE_PROFIT_SHARE_RATE
    assert _resolve_effective_rate({"commission_rate": "bad"}) == AFFILIATE_PROFIT_SHARE_RATE


def test_resolve_effective_rate_uses_override():
    assert _resolve_effective_rate({"commission_rate": 0.05}) == 0.05
    assert _resolve_effective_rate({"commission_rate": 0.0}) == 0.0


def test_resolve_effective_rate_out_of_range_falls_back():
    assert _resolve_effective_rate({"commission_rate": -0.01}) == AFFILIATE_PROFIT_SHARE_RATE
    assert _resolve_effective_rate({"commission_rate": 0.99}) == AFFILIATE_PROFIT_SHARE_RATE


def test_validate_rate_accepts_valid():
    assert _validate_rate(0.05) == 0.05
    assert _validate_rate("0.1") == 0.1
    assert _validate_rate(0) == 0.0
    assert _validate_rate(MAX_AFFILIATE_COMMISSION_RATE) == MAX_AFFILIATE_COMMISSION_RATE
    assert _validate_rate(None) is None


def test_validate_rate_rejects_out_of_range():
    with pytest.raises(HTTPException) as e1:
        _validate_rate(-0.01)
    assert e1.value.status_code == 400
    with pytest.raises(HTTPException) as e2:
        _validate_rate(0.80)  # iter502 — above the 75% ceiling
    assert e2.value.status_code == 400
    with pytest.raises(HTTPException) as e3:
        _validate_rate("not-a-number")
    assert e3.value.status_code == 400


# ─────────────────────────────────────────────────────────────────────
# award_affiliate_commission — approval gate + custom rate
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_default_rate_when_no_override(db):
    referrer_id, payer_id, _, suffix = await _seed_referrer_payer(
        db, status="active")
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee", reference_id=f"iter501:default:{suffix}",
        )
        assert credit is not None
        assert credit["amount"] == 3.0  # 3% of $100
        assert credit["commission_rate"] == AFFILIATE_PROFIT_SHARE_RATE
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.asyncio
async def test_custom_rate_override_used_and_snapshot_on_row(db):
    referrer_id, payer_id, _, suffix = await _seed_referrer_payer(
        db, status="active", commission_rate=0.05)
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee", reference_id=f"iter501:custom:{suffix}",
        )
        assert credit is not None
        assert credit["amount"] == 5.0
        assert credit["commission_rate"] == 0.05  # snapshotted on row

        # Now change the admin's rate — old row should NOT change.
        await db.users.update_one({"id": referrer_id},
                                  {"$set": {"commission_rate": 0.10}})
        row = await db.platform_credits.find_one({"id": credit["id"]})
        assert row["commission_rate"] == 0.05
        assert row["amount"] == 5.0

        # But NEW awards use the new rate.
        credit2 = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee", reference_id=f"iter501:custom-2:{suffix}",
        )
        assert credit2 is not None
        assert credit2["amount"] == 10.0
        assert credit2["commission_rate"] == 0.10
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.parametrize("status", ["none", "pending", "revoked"])
@pytest.mark.asyncio
async def test_inactive_status_no_commission(db, status):
    referrer_id, payer_id, _, suffix = await _seed_referrer_payer(
        db, status=status)
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee",
            reference_id=f"iter501:inactive-{status}:{suffix}",
        )
        assert credit is None
        # And no row was written
        count = await db.platform_credits.count_documents(
            {"user_id": referrer_id, "source": "referral"})
        assert count == 0
    finally:
        await _cleanup(db, referrer_id, payer_id)


@pytest.mark.asyncio
async def test_missing_status_field_no_commission(db):
    """A referrer whose user doc has no affiliate_status field at all
    (default "none") should not accrue commissions. This is the exact
    behaviour that protects the platform from users who auto-generate a
    code but were never approved."""
    suffix = uuid.uuid4().hex[:8]
    referrer_id = f"iter501-ref-{suffix}"
    payer_id = f"iter501-payer-{suffix}"
    code = f"I501{suffix[:4].upper()}"
    # No affiliate_status field at all.
    await db.users.insert_one({
        "id": referrer_id, "name": "Ref", "email": f"{referrer_id}@x.com",
        "affiliate_code": code,
    })
    await db.users.insert_one({
        "id": payer_id, "name": "Payer", "email": f"{payer_id}@x.com",
        "referred_by_code": code,
    })
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee", reference_id=f"iter501:missing:{suffix}",
        )
        assert credit is None
    finally:
        await _cleanup(db, referrer_id, payer_id)


# ─────────────────────────────────────────────────────────────────────
# admin_set_affiliate_status endpoint
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_set_status_active_with_rate(db):
    admin = _admin()
    target_id = f"iter501-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({
        "id": target_id, "name": "Target", "email": f"{target_id}@x.com",
    })
    try:
        result = await admin_set_affiliate_status(
            {"user_id": target_id, "status": "active", "commission_rate": 0.05,
             "note": "Promoted to affiliate"},
            current_user=admin,
        )
        assert result["success"] is True
        assert result["changed"] is True
        assert result["affiliate_status"] == "active"
        assert result["commission_rate"] == 0.05
        assert result["effective_rate"] == 0.05
        # A referral code was auto-generated
        u = await db.users.find_one({"id": target_id})
        assert u["affiliate_status"] == "active"
        assert u["commission_rate"] == 0.05
        assert u.get("affiliate_code")
        # Admin log
        log = await db.admin_action_logs.find_one({
            "target_user_id": target_id,
            "action": "affiliate_status_change",
        })
        assert log is not None
        assert log["before"]["affiliate_status"] == "none"
        assert log["after"]["affiliate_status"] == "active"
        assert log["after"]["commission_rate"] == 0.05
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_admin_set_status_rejects_out_of_range_rate(db):
    admin = _admin()
    target_id = f"iter501-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({"id": target_id, "name": "T", "email": f"{target_id}@x.com"})
    try:
        with pytest.raises(HTTPException) as exc:
            await admin_set_affiliate_status(
                {"user_id": target_id, "status": "active", "commission_rate": 0.85},
                current_user=admin,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"] == "commission_rate_out_of_range"
        # User doc must not have been mutated
        u = await db.users.find_one({"id": target_id})
        assert "affiliate_status" not in u or u["affiliate_status"] == "none"
        assert "commission_rate" not in u or u.get("commission_rate") is None
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_admin_set_status_is_idempotent(db):
    admin = _admin()
    target_id = f"iter501-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({
        "id": target_id, "name": "T", "email": f"{target_id}@x.com",
        "affiliate_status": "active", "commission_rate": 0.05,
    })
    try:
        # First identical set should be a no-op (no log written)
        r = await admin_set_affiliate_status(
            {"user_id": target_id, "status": "active", "commission_rate": 0.05},
            current_user=admin,
        )
        assert r["changed"] is False
        log_count = await db.admin_action_logs.count_documents(
            {"target_user_id": target_id})
        assert log_count == 0
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_admin_set_status_non_admin_denied(db):
    non_admin = _non_admin()
    target_id = f"iter501-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({"id": target_id, "name": "T", "email": f"{target_id}@x.com"})
    try:
        with pytest.raises(HTTPException) as exc:
            await admin_set_affiliate_status(
                {"user_id": target_id, "status": "active"},
                current_user=non_admin,
            )
        assert exc.value.status_code == 403
    finally:
        await _cleanup(db, target_id)


# ─────────────────────────────────────────────────────────────────────
# admin_set_affiliate_rate endpoint
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_set_rate_adjusts_without_touching_status(db):
    admin = _admin()
    target_id = f"iter501-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({
        "id": target_id, "name": "T", "email": f"{target_id}@x.com",
        "affiliate_status": "active", "commission_rate": 0.03,
    })
    try:
        result = await admin_set_affiliate_rate(
            {"user_id": target_id, "commission_rate": 0.08, "note": "Bump to 8%"},
            current_user=admin,
        )
        assert result["success"] is True
        assert result["changed"] is True
        assert result["commission_rate"] == 0.08
        assert result["affiliate_status"] == "active"  # untouched
        # Log recorded with before/after snapshot
        log = await db.admin_action_logs.find_one({
            "target_user_id": target_id,
            "action": "affiliate_rate_change",
        })
        assert log is not None
        assert log["before"]["commission_rate"] == 0.03
        assert log["after"]["commission_rate"] == 0.08
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_admin_set_rate_null_clears_override(db):
    admin = _admin()
    target_id = f"iter501-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({
        "id": target_id, "name": "T", "email": f"{target_id}@x.com",
        "affiliate_status": "active", "commission_rate": 0.10,
    })
    try:
        result = await admin_set_affiliate_rate(
            {"user_id": target_id, "commission_rate": None, "note": "Back to default"},
            current_user=admin,
        )
        assert result["success"] is True
        assert result["commission_rate"] is None
        # Effective rate should now be the default
        assert result["effective_rate"] == AFFILIATE_PROFIT_SHARE_RATE
    finally:
        await _cleanup(db, target_id)


@pytest.mark.asyncio
async def test_admin_set_rate_rejects_out_of_range(db):
    admin = _admin()
    target_id = f"iter501-target-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({
        "id": target_id, "name": "T", "email": f"{target_id}@x.com",
        "affiliate_status": "active", "commission_rate": 0.03,
    })
    try:
        with pytest.raises(HTTPException) as exc:
            await admin_set_affiliate_rate(
                {"user_id": target_id, "commission_rate": 0.85},
                current_user=admin,
            )
        assert exc.value.status_code == 400
        # User doc must not have been touched
        u = await db.users.find_one({"id": target_id})
        assert u["commission_rate"] == 0.03
    finally:
        await _cleanup(db, target_id)


# ─────────────────────────────────────────────────────────────────────
# Backfill migration
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_backfill_promotes_existing_earners_to_active(db):
    suffix = uuid.uuid4().hex[:8]
    # User A — has a platform_credits row (source=referral), no affiliate_status
    a_id = f"iter501-bf-a-{suffix}"
    # User B — has referred_by_code pointing at C's affiliate_code
    b_id = f"iter501-bf-b-{suffix}"
    c_id = f"iter501-bf-c-{suffix}"
    c_code = f"BFC{suffix[:5].upper()}"
    # User D — already has an explicit status="revoked"; must be untouched
    d_id = f"iter501-bf-d-{suffix}"
    await db.users.insert_one({"id": a_id, "email": f"{a_id}@x.com", "name": "A"})
    await db.users.insert_one({"id": c_id, "email": f"{c_id}@x.com", "name": "C",
                               "affiliate_code": c_code})
    await db.users.insert_one({"id": b_id, "email": f"{b_id}@x.com", "name": "B",
                               "referred_by_code": c_code})
    await db.users.insert_one({"id": d_id, "email": f"{d_id}@x.com", "name": "D",
                               "affiliate_status": "revoked"})
    # Existing referral credit for user A
    await db.platform_credits.insert_one({
        "id": f"REF-BF-{suffix}", "user_id": a_id, "amount": 3.0,
        "source": "referral", "commission_rate": 0.03, "commission_base": 100.0,
        "created_at": "2024-01-01T00:00:00Z",
    })
    # Add a credit for D too — must not override their explicit "revoked"
    await db.platform_credits.insert_one({
        "id": f"REF-BF2-{suffix}", "user_id": d_id, "amount": 1.0,
        "source": "referral", "commission_rate": 0.03, "commission_base": 33.0,
        "created_at": "2024-01-01T00:00:00Z",
    })
    try:
        result = await _backfill_active_affiliates(db)
        assert result["promoted"] >= 2  # A + C
        assert result["candidates"] >= 3  # A + C + D
        # A + C flipped to active
        ua = await db.users.find_one({"id": a_id})
        assert ua["affiliate_status"] == "active"
        uc = await db.users.find_one({"id": c_id})
        assert uc["affiliate_status"] == "active"
        # D untouched
        ud = await db.users.find_one({"id": d_id})
        assert ud["affiliate_status"] == "revoked"

        # Idempotency — second call promotes nothing new
        r2 = await _backfill_active_affiliates(db)
        assert r2["promoted"] == 0
    finally:
        await _cleanup(db, a_id, b_id, c_id, d_id)


# ─────────────────────────────────────────────────────────────────────
# Legacy PUT shim
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_legacy_put_shim_writes_to_user_doc_not_affiliates_collection(db):
    from routes.admin_ops import admin_set_affiliate_status_legacy

    admin = _admin()
    # Force role check to pass (the shim uses require_admin normally; here we call
    # it directly, so the underlying set-status admin gate is what enforces role).
    target_id = f"iter501-legacy-{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({"id": target_id, "name": "T", "email": f"{target_id}@x.com"})
    try:
        # Enable via legacy shim
        result = await admin_set_affiliate_status_legacy(
            target_id, {"is_affiliate": True}, current_user=admin,
        )
        assert result["success"] is True
        u = await db.users.find_one({"id": target_id})
        assert u["affiliate_status"] == "active"
        # Legacy db.affiliates should NOT contain a row for this user.
        legacy_row = await db.affiliates.find_one({"user_id": target_id})
        assert legacy_row is None

        # Disable via legacy shim
        result2 = await admin_set_affiliate_status_legacy(
            target_id, {"is_affiliate": False}, current_user=admin,
        )
        assert result2["success"] is True
        u2 = await db.users.find_one({"id": target_id})
        assert u2["affiliate_status"] == "revoked"
    finally:
        await _cleanup(db, target_id)
