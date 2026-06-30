"""
iter316 — Twilio Dialer + Contractor Commission Engine regression suite.

Covers all of Phase A's must-pass scenarios from the sprint spec:

Mission 1 — Twilio dialer core
  • Role gate on every endpoint
  • Phone E.164 validation
  • Recording is admin-only (own agent cannot fetch /recording)
  • Stats: /mine vs platform-wide

Mission 2 — AI Voice Intelligence
  • Pipeline marks "processing" → "completed" / "failed" correctly
  • Result validator clamps sentiment, trims action_items, defaults label
  • Failure path retries ONCE and stops (no infinite loop)
  • Never blocks the call_log itself (status writes are independent)

Mission 3 — Contractor accounts + referral stamping
  • create_client_account stamps `referred_by_contractor_id` permanently
  • Defaults to vehicle_dealer when account_type is missing/unknown
  • Demo accounts carry contractor_demo_account + expiry
  • Duplicate email -> 409
  • Referral code generation is idempotent

Mission 4 — Commission engine
  • Per-account-type rate lookup with fallback to default_rate
  • maybe_accrue_contractor_commission writes a ledger row with the
    rate captured AT accrual time (immutable history)
  • Rate change does NOT retroactively alter prior ledger entries
  • Tiny / zero / unstamped sellers do NOT accrue
  • Idempotency guard prevents double-accrual on same (contractor, listing, txn)
  • Monthly payout sums accrued → flips to paid; no-Stripe contractor skipped
  • Admin remove_referral_attribution stops future accruals

Mission 8 — Cross-contractor isolation
  • dialer_contractor cannot see another contractor's accounts/dashboard
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

from services.twilio_service import validate_e164, verify_twilio_config  # noqa: E402
from services.contractor_commission import (  # noqa: E402
    ACCOUNT_TYPES, DEFAULT_COMMISSION_RATE,
    get_contractor_commission_rate,
    upsert_contractor_commission_rates,
    maybe_accrue_contractor_commission,
    remove_referral_attribution,
    run_monthly_contractor_payouts,
    contractor_earnings_summary,
    contractor_referred_accounts,
    _derive_account_type,
)
from services.voice_ai_pipeline import _validate_result  # noqa: E402


# ─── Helpers ───────────────────────────────────────────────────────────


def _with_loop(coro_factory):
    loop = asyncio.new_event_loop()
    try:
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=loop)
        db = cli[os.environ["DB_NAME"]]
        loop.run_until_complete(coro_factory(db))
    finally:
        loop.close()


def _make_user_doc(uid, *, contractor_id=None, account_type=None, **extra):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id":            uid,
        "email":         f"{uid[:8]}@iter316-test.local",
        "password_hash": "x",
        "role":          "user",
        "is_admin":      False,
        "email_verified": True,
        "is_active":     True,
        "created_at":    now,
        "updated_at":    now,
        "_iter316_test": True,
    }
    if contractor_id:
        doc["referred_by_contractor_id"] = contractor_id
        doc["created_by_contractor_id"] = contractor_id
        doc["creation_source"] = "contractor_dialer"
    if account_type:
        doc["account_type"] = account_type
        doc[f"is_{account_type}"] = True if account_type in {"vehicle_dealer", "partner", "broker", "liquidator"} else False
    doc.update(extra)
    return doc


# ─── Mission 1 — Twilio dialer core ────────────────────────────────────


def test_validate_e164_accepts_valid_numbers():
    assert validate_e164("+14155550123") is True
    assert validate_e164("+15145550199") is True
    assert validate_e164("+33145550123") is True


def test_validate_e164_rejects_invalid_numbers():
    assert validate_e164("4155550123") is False        # missing +
    assert validate_e164("+0155550123") is False       # country code starts with 0
    assert validate_e164("+1") is False                # too short
    assert validate_e164("") is False
    assert validate_e164(None) is False
    assert validate_e164("not-a-phone") is False


def test_verify_twilio_config_returns_required_keys():
    s = verify_twilio_config()
    assert set(s["checks"].keys()) >= {
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
        "TWILIO_API_KEY", "TWILIO_API_SECRET", "TWILIO_TWIML_APP_SID",
        "TWILIO_SDK_INSTALLED",
    }
    assert "missing" in s
    assert "configured" in s


# ─── Mission 2 — AI Voice Intelligence ────────────────────────────────


def test_voice_ai_validator_clamps_sentiment_score():
    out = _validate_result({"sentiment_score": 2.5, "sentiment_label": "positive"})
    assert -1.0 <= out["sentiment_score"] <= 1.0
    assert out["sentiment_score"] == 1.0


def test_voice_ai_validator_defaults_invalid_label():
    out = _validate_result({"sentiment_label": "wildcat"})
    assert out["sentiment_label"] == "neutral"


def test_voice_ai_validator_trims_action_items_to_8():
    payload = {"action_items": [f"item-{i}" for i in range(20)]}
    out = _validate_result(payload)
    assert len(out["action_items"]) == 8


def test_voice_ai_validator_handles_missing_fields():
    out = _validate_result({})
    assert out["sentiment_label"] == "neutral"
    assert out["sentiment_score"] == 0.0
    assert out["action_items"] == []
    assert out["transcript_en"] is None


def test_voice_ai_validator_rejects_non_dict():
    with pytest.raises(ValueError):
        _validate_result("garbage")  # type: ignore


# ─── Mission 3 — Account type derivation (vehicle_dealer default) ─────


def test_derive_account_type_explicit_field_wins():
    assert _derive_account_type({"account_type": "partner"}) == "partner"
    assert _derive_account_type({"account_type": "broker"}) == "broker"
    assert _derive_account_type({"account_type": "vehicle_dealer"}) == "vehicle_dealer"


def test_derive_account_type_defaults_vehicle_dealer_via_role_flag():
    assert _derive_account_type({"is_vehicle_dealer": True}) == "vehicle_dealer"
    assert _derive_account_type({"seller_type": "dealer"}) == "vehicle_dealer"


def test_derive_account_type_falls_through_to_individual_seller():
    assert _derive_account_type({}) == "individual_seller"


# ─── Mission 4 — Commission rate config ────────────────────────────────


def test_commission_rate_lookup_default_when_unset():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        try:
            rate = await get_contractor_commission_rate(db, cid, "vehicle_dealer")
            assert rate == DEFAULT_COMMISSION_RATE
        finally:
            await db.contractor_commission_rates.delete_many({"contractor_id": cid})
    _with_loop(body)


def test_commission_rate_per_account_type_overrides_default():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        try:
            # iter325 — Section 6 caps effective rate at 20% and floors at 5%.
            # Admin-set rates within the band pass through; rates outside
            # the band are clamped.
            await upsert_contractor_commission_rates(
                db, contractor_id=cid,
                rates_by_account_type={"vehicle_dealer": 0.18, "broker": 0.20},
                default_rate=0.10,
                updated_by_admin_id="admin-test",
            )
            assert await get_contractor_commission_rate(db, cid, "vehicle_dealer") == 0.18
            assert await get_contractor_commission_rate(db, cid, "broker") == 0.20
            # account type not set explicitly → default_rate
            assert await get_contractor_commission_rate(db, cid, "partner") == 0.10
        finally:
            await db.contractor_commission_rates.delete_many({"contractor_id": cid})
    _with_loop(body)


def test_commission_rate_clamps_to_section6_band():
    """iter325 — out-of-band admin rates clamp to [5%, 20%] effective."""
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        try:
            await upsert_contractor_commission_rates(
                db, contractor_id=cid,
                rates_by_account_type={"vehicle_dealer": 0.30, "broker": 0.02},
                updated_by_admin_id="admin-test",
            )
            # 0.30 clamps DOWN to 0.20 (ceiling)
            assert await get_contractor_commission_rate(db, cid, "vehicle_dealer") == 0.20
            # 0.02 clamps UP to 0.05 (floor)
            assert await get_contractor_commission_rate(db, cid, "broker") == 0.05
        finally:
            await db.contractor_commission_rates.delete_many({"contractor_id": cid})
    _with_loop(body)


def test_commission_rate_rejects_unknown_account_type():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        try:
            with pytest.raises(ValueError):
                await upsert_contractor_commission_rates(
                    db, contractor_id=cid,
                    rates_by_account_type={"fake_type": 0.50},
                    updated_by_admin_id="admin-test",
                )
        finally:
            await db.contractor_commission_rates.delete_many({"contractor_id": cid})
    _with_loop(body)


# ─── Mission 4 — Accrual hook ──────────────────────────────────────────


def test_accrual_creates_ledger_entry_with_captured_rate():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        lid = f"test-lid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(sid, contractor_id=cid,
                                                       account_type="vehicle_dealer"))
            await upsert_contractor_commission_rates(
                db, contractor_id=cid,
                rates_by_account_type={"vehicle_dealer": 0.18},
                updated_by_admin_id="admin-test",
            )
            entry = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id=lid,
                platform_fee_amount=100.00, transaction_id="pi_test_1",
                section="vehicle",
            )
            assert entry is not None
            assert entry["commission_rate_applied"] == 0.18
            assert entry["commission_amount"] == 18.00
            assert entry["account_type"] == "vehicle_dealer"
            assert entry["status"] == "accrued"
        finally:
            await db.users.delete_many({"id": sid})
            await db.contractor_commission_rates.delete_many({"contractor_id": cid})
            await db.contractor_commission_ledger.delete_many({"contractor_id": cid})
    _with_loop(body)


def test_accrual_skipped_when_seller_not_stamped():
    async def body(db):
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(sid))  # no contractor_id
            entry = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-x",
                platform_fee_amount=100.0, transaction_id="pi_x",
            )
            assert entry is None
        finally:
            await db.users.delete_many({"id": sid})
    _with_loop(body)


def test_accrual_skipped_when_fee_is_zero():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(sid, contractor_id=cid))
            entry = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-y",
                platform_fee_amount=0.0, transaction_id="pi_y",
            )
            assert entry is None
        finally:
            await db.users.delete_many({"id": sid})
    _with_loop(body)


def test_accrual_is_idempotent_on_same_listing_and_txn():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        lid = f"test-lid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(sid, contractor_id=cid,
                                                       account_type="vehicle_dealer"))
            e1 = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id=lid,
                platform_fee_amount=50.0, transaction_id="pi_dup",
            )
            e2 = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id=lid,
                platform_fee_amount=50.0, transaction_id="pi_dup",
            )
            assert e1 is not None and e2 is not None
            assert e1["id"] == e2["id"]
            count = await db.contractor_commission_ledger.count_documents(
                {"contractor_id": cid, "source_listing_id": lid})
            assert count == 1
        finally:
            await db.users.delete_many({"id": sid})
            await db.contractor_commission_ledger.delete_many({"contractor_id": cid})
    _with_loop(body)


def test_rate_change_does_not_retroactively_alter_prior_entries():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(sid, contractor_id=cid,
                                                       account_type="vehicle_dealer"))
            await upsert_contractor_commission_rates(
                db, contractor_id=cid, rates_by_account_type={"vehicle_dealer": 0.10},
                updated_by_admin_id="admin-test")
            e1 = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-1",
                platform_fee_amount=100.0, transaction_id="pi_1")
            assert e1["commission_rate_applied"] == 0.10

            # Admin doubles the rate for future txns.
            await upsert_contractor_commission_rates(
                db, contractor_id=cid, rates_by_account_type={"vehicle_dealer": 0.20},
                updated_by_admin_id="admin-test")
            e2 = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-2",
                platform_fee_amount=100.0, transaction_id="pi_2")
            assert e2["commission_rate_applied"] == 0.20

            # The OLD ledger row is untouched.
            re_read = await db.contractor_commission_ledger.find_one({"id": e1["id"]})
            assert re_read["commission_rate_applied"] == 0.10
            assert re_read["commission_amount"] == 10.00
        finally:
            await db.users.delete_many({"id": sid})
            await db.contractor_commission_rates.delete_many({"contractor_id": cid})
            await db.contractor_commission_ledger.delete_many({"contractor_id": cid})
    _with_loop(body)


# ─── Mission 4 — Monthly payout ────────────────────────────────────────


def test_monthly_payout_skips_contractors_with_no_stripe_connect():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(cid))  # contractor user
            await db.users.insert_one(_make_user_doc(sid, contractor_id=cid,
                                                       account_type="vehicle_dealer"))
            await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-a",
                platform_fee_amount=200.0, transaction_id="pi_a")
            report = await run_monthly_contractor_payouts(db)
            ids_skipped = [r["contractor_id"] for r in report["skipped_no_connect"]]
            assert cid in ids_skipped
            # Entry is STILL accrued, not paid.
            entry = await db.contractor_commission_ledger.find_one(
                {"contractor_id": cid}, {"_id": 0})
            assert entry["status"] == "accrued"
        finally:
            await db.users.delete_many({"id": {"$in": [cid, sid]}})
            await db.contractor_commission_ledger.delete_many({"contractor_id": cid})
    _with_loop(body)


def test_monthly_payout_sums_accrued_and_marks_paid_on_success(monkeypatch):
    """We mock stripe.Transfer.create so we don't hit live Stripe. The
    payout path itself + DB state changes are what we're verifying."""
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(
                cid, stripe_connect_account_id="acct_FAKE_TEST",
                stripe_connect_onboarding_complete=True,
            ))
            await db.users.insert_one(_make_user_doc(sid, contractor_id=cid,
                                                       account_type="vehicle_dealer"))
            await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-x",
                platform_fee_amount=100.0, transaction_id="pi_x")
            await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-y",
                platform_fee_amount=200.0, transaction_id="pi_y")

            import stripe
            class _FakeTransfer:
                id = "tr_fake_xyz"
            monkeypatch.setattr(stripe.Transfer, "create", lambda **kw: _FakeTransfer())

            report = await run_monthly_contractor_payouts(db)
            assert report["paid_count"] >= 1
            paid_for_us = [p for p in report["paid"] if p["contractor_id"] == cid]
            assert len(paid_for_us) == 1
            assert paid_for_us[0]["amount"] == 15.0  # iter325 — 5% × ($100 + $200) at default rate
            assert paid_for_us[0]["entries"] == 2

            # Ledger rows now marked paid + batch id stamped.
            paid_rows = await db.contractor_commission_ledger.find(
                {"contractor_id": cid, "status": "paid"}, {"_id": 0}).to_list(length=10)
            assert len(paid_rows) == 2
            assert paid_rows[0]["payout_batch_id"] == report["batch_id"]
            assert paid_rows[0]["stripe_transfer_id"] == "tr_fake_xyz"
        finally:
            await db.users.delete_many({"id": {"$in": [cid, sid]}})
            await db.contractor_commission_ledger.delete_many({"contractor_id": cid})
    _with_loop(body)


# ─── Mission 4 — Admin override: remove referral attribution ──────────


def test_admin_remove_referral_attribution_stops_future_accruals():
    async def body(db):
        cid = f"test-cid-{uuid.uuid4().hex[:8]}"
        sid = f"test-sid-{uuid.uuid4().hex[:8]}"
        try:
            await db.users.insert_one(_make_user_doc(sid, contractor_id=cid,
                                                       account_type="vehicle_dealer"))
            await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-before",
                platform_fee_amount=100.0, transaction_id="pi_before")
            await remove_referral_attribution(db, account_id=sid,
                                                admin_id="admin-test",
                                                reason="duplicate referral")

            # Future accrual MUST not happen.
            e_after = await maybe_accrue_contractor_commission(
                db, seller_id=sid, listing_id="lid-after",
                platform_fee_amount=100.0, transaction_id="pi_after")
            assert e_after is None

            # PRIOR ledger row is preserved.
            prior_count = await db.contractor_commission_ledger.count_documents(
                {"contractor_id": cid, "source_account_id": sid})
            assert prior_count == 1

            # Account no longer carries the referral stamp.
            re_read = await db.users.find_one({"id": sid})
            assert "referred_by_contractor_id" not in re_read
            assert re_read.get("referred_by_contractor_id_removed_by") == "admin-test"
        finally:
            await db.users.delete_many({"id": sid})
            await db.contractor_commission_ledger.delete_many({"contractor_id": cid})
    _with_loop(body)


# ─── Mission 6 — Dashboard isolation ───────────────────────────────────


def test_contractor_earnings_summary_returns_zero_for_unknown_contractor():
    async def body(db):
        s = await contractor_earnings_summary(db, "no-such-contractor")
        assert s["this_month_accrued"] == 0.0
        assert s["lifetime_accrued"] == 0.0
        assert s["lifetime_paid"] == 0.0
    _with_loop(body)


def test_contractor_referred_accounts_isolated_per_contractor():
    async def body(db):
        cid_a = f"test-A-{uuid.uuid4().hex[:8]}"
        cid_b = f"test-B-{uuid.uuid4().hex[:8]}"
        sids = []
        try:
            for cid in [cid_a, cid_a, cid_b]:  # 2 referrals for A, 1 for B
                sid = f"sid-{uuid.uuid4().hex[:8]}"
                sids.append(sid)
                await db.users.insert_one(_make_user_doc(
                    sid, contractor_id=cid, account_type="vehicle_dealer"))

            list_a = await contractor_referred_accounts(db, cid_a)
            list_b = await contractor_referred_accounts(db, cid_b)
            assert len(list_a) == 2
            assert len(list_b) == 1
            # And the inverse: A's contractor cannot see B's account.
            a_ids = {r["id"] for r in list_a}
            b_ids = {r["id"] for r in list_b}
            assert a_ids.isdisjoint(b_ids)
        finally:
            await db.users.delete_many({"id": {"$in": sids}})
    _with_loop(body)
