"""
iter455 — Escrow Pickup-Code Compatibility Regression Suite
============================================================

Locks in the fix: the buyer's canonical `BVX-XXXXXXXX` pickup code is
accepted by the seller escrow-confirmation endpoint. Case, hyphens, and
whitespace are normalized safely.

Coverage:
  A. Canonical BVX-XXXXXXXX generation
  B. Confirm-pickup accepts the exact code shown to the buyer
  C. Confirm-pickup accepts safe formatting variants (lowercase,
     without hyphen, with spaces)
  D. Wrong / partial / different code is rejected with 400
  E. Already-confirmed (reused) code returns error and does not
     re-release funds
  F. Expired code returns 410
  G. Legacy 6-char stored code still validates when the seller enters it
  H. `create_escrow_hold` reuses an existing `transactions.pickup_code`
     for the same auction so buyer + seller docs converge on one code

The suite runs entirely against the DB helpers with `stripe.Transfer.create`
patched so no real funds move. No historical records are mutated —
every fixture is seeded and cleaned up.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

from services.escrow_service import (  # noqa: E402
    generate_pickup_code, confirm_pickup, normalize_pickup_code,
    create_escrow_hold,
)


# ─── Shared infra ─────────────────────────────────────────────
@pytest.fixture(scope="module")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(policy.new_event_loop())


@pytest.fixture(scope="module")
def db(event_loop):
    c = AsyncIOMotorClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture
def seller_id():
    return f"iter455-seller-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def buyer_id():
    return f"iter455-buyer-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def auction_id():
    return f"iter455-auction-{uuid.uuid4().hex[:8]}"


async def _seed_escrow(db, *, auction_id, seller_id, buyer_id,
                       pickup_code, expires_delta=timedelta(hours=48),
                       status="held"):
    now = datetime.now(timezone.utc)
    doc = {
        "auction_id": auction_id,
        "listing_id": auction_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "hammer_price_cents": 1400,
        "total_charged_cents": 1500,
        "application_fee_cents": 100,
        "stripe_payment_intent_id": f"pi_test_{auction_id}",
        "stripe_transfer_id": None,
        "escrow_status": status,
        "pickup_code": pickup_code,
        "pickup_code_expires_at": (now + expires_delta).isoformat(),
        "pickup_code_entered_at": None,
        "pickup_confirmed_at": None,
        "funds_released_at": None,
        "auto_release_scheduled_at": (now + expires_delta).isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "item_type": "non_vehicle",
        "province": "QC",
    }
    await db.escrow_transactions.insert_one(doc)


async def _seed_seller_with_connect(db, seller_id: str):
    await db.users.update_one(
        {"id": seller_id},
        {"$set": {
            "id": seller_id,
            "email": f"{seller_id}@iter455.test",
            "name": "iter455 seller",
            "stripe_connect_account_id": f"acct_test_{seller_id}",
        }},
        upsert=True,
    )


async def _cleanup(db, seller_id, buyer_id=None, auction_id=None):
    q = {"$or": [
        {"seller_id": seller_id},
        {"pickup_code_seller_id": seller_id},
    ]}
    if auction_id:
        q["$or"].append({"auction_id": auction_id})
        q["$or"].append({"listing_id": auction_id})
    await db.escrow_transactions.delete_many(q)
    await db.transactions.delete_many(q)
    await db.pickup_attempt_log.delete_many({"seller_id": seller_id})
    await db.users.delete_many({"id": seller_id})
    if buyer_id:
        await db.users.delete_many({"id": buyer_id})


# ─────────────────────────────────────────────────────────────
# Scenario A — Canonical generation
# ─────────────────────────────────────────────────────────────
class TestScenarioA_CanonicalGeneration:
    def test_A1_generated_code_is_bvx_prefix_and_12_chars(
        self, event_loop, db,
    ):
        async def _run():
            code = await generate_pickup_code(db)
            assert code.startswith("BVX-"), f"expected BVX- prefix, got {code}"
            assert len(code) == 12, f"expected 12 chars, got {len(code)}"
            body = code[4:]
            assert body.isalnum() and body == body.upper()
            # No confusable characters (0, O, I, 1, L)
            for ch in body:
                assert ch not in "0OIL1", f"forbidden confusable char {ch}"
        event_loop.run_until_complete(_run())

    def test_A2_normalize_handles_variants(self):
        # Exact canonical → identical strip
        assert normalize_pickup_code("BVX-ARKC661T") == "BVXARKC661T"
        # Lowercase → uppercase strip
        assert normalize_pickup_code("bvx-arkc661t") == "BVXARKC661T"
        # No hyphen
        assert normalize_pickup_code("BVXARKC661T") == "BVXARKC661T"
        # With spaces
        assert normalize_pickup_code(" BVX ARKC 661T ") == "BVXARKC661T"
        # With extra hyphens
        assert normalize_pickup_code("BVX--ARKC--661T") == "BVXARKC661T"
        # Legacy 6-char preserved
        assert normalize_pickup_code("ARKC66") == "ARKC66"
        # Empty / None handled safely
        assert normalize_pickup_code("") == ""
        assert normalize_pickup_code(None) == ""


# ─────────────────────────────────────────────────────────────
# Scenario B — Buyer's exact code accepted (mocked Stripe transfer)
# ─────────────────────────────────────────────────────────────
class TestScenarioB_BuyerExactCode:
    def test_B1_exact_buyer_code_releases_funds(
        self, event_loop, db, seller_id, buyer_id, auction_id,
    ):
        async def _run():
            await _seed_seller_with_connect(db, seller_id)
            code = "BVX-ARKC661T"
            await _seed_escrow(db,
                               auction_id=auction_id,
                               seller_id=seller_id,
                               buyer_id=buyer_id,
                               pickup_code=code)
            try:
                # Patch Stripe transfer so no real funds move
                with patch("services.escrow_service.stripe.Transfer.create",
                           return_value=MagicMock(id="tr_test_iter455_B1")):
                    result = await confirm_pickup(db, seller_id, auction_id, code)
                assert result["status"] == "released"
                assert result["transfer_id"] == "tr_test_iter455_B1"
                # Escrow row updated to released
                row = await db.escrow_transactions.find_one(
                    {"auction_id": auction_id})
                assert row["escrow_status"] == "released"
                assert row["stripe_transfer_id"] == "tr_test_iter455_B1"
                assert row["funds_released_at"] is not None
                # Buyer historical record unchanged (no fields we didn't own)
                assert row["hammer_price_cents"] == 1400
                assert row["total_charged_cents"] == 1500
            finally:
                await _cleanup(db, seller_id, buyer_id, auction_id)
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario C — Safe formatting variants accepted
# ─────────────────────────────────────────────────────────────
class TestScenarioC_SafeVariants:
    @pytest.mark.parametrize("variant", [
        "bvx-arkc661t",         # lowercase
        "BVXARKC661T",          # no hyphen
        "BVX ARKC 661T",        # spaces
        " BVX-ARKC661T ",       # padded whitespace
        "bvx-ARKC-661T",        # mixed case + extra hyphen
    ])
    def test_C1_variant_accepted(
        self, event_loop, db, seller_id, buyer_id, auction_id, variant,
    ):
        async def _run():
            await _seed_seller_with_connect(db, seller_id)
            code = "BVX-ARKC661T"
            await _seed_escrow(db,
                               auction_id=auction_id,
                               seller_id=seller_id,
                               buyer_id=buyer_id,
                               pickup_code=code)
            try:
                with patch("services.escrow_service.stripe.Transfer.create",
                           return_value=MagicMock(id="tr_iter455_C")):
                    result = await confirm_pickup(db, seller_id, auction_id, variant)
                assert result["status"] == "released", (
                    f"variant {variant!r} rejected — must be accepted"
                )
            finally:
                await _cleanup(db, seller_id, buyer_id, auction_id)
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario D — Wrong / partial code rejected
# ─────────────────────────────────────────────────────────────
class TestScenarioD_WrongCodeRejected:
    @pytest.mark.parametrize("bad", [
        "BVX-WRONG123",   # completely wrong
        "BVX-ARKC661",    # missing last char
        "BVX-ARKC66TZ",   # extra char
        "ARKC661T",       # missing prefix
        "",               # empty
        "   ",            # whitespace only
        "!!@@##",         # garbage
    ])
    def test_D1_bad_codes_return_400_and_do_not_release(
        self, event_loop, db, seller_id, buyer_id, auction_id, bad,
    ):
        async def _run():
            await _seed_seller_with_connect(db, seller_id)
            good = "BVX-ARKC661T"
            await _seed_escrow(db,
                               auction_id=auction_id,
                               seller_id=seller_id,
                               buyer_id=buyer_id,
                               pickup_code=good)
            try:
                from fastapi import HTTPException
                with patch("services.escrow_service.stripe.Transfer.create",
                           return_value=MagicMock(id="MUST_NOT_TRANSFER")):
                    with pytest.raises(HTTPException) as exc:
                        await confirm_pickup(db, seller_id, auction_id, bad)
                assert exc.value.status_code == 400, (
                    f"bad code {bad!r} did not return 400: got {exc.value.status_code}"
                )
                # Escrow row still held
                row = await db.escrow_transactions.find_one(
                    {"auction_id": auction_id})
                assert row["escrow_status"] == "held"
                assert row["stripe_transfer_id"] is None
                # Failed-attempt logged for codes that normalize to a
                # non-empty string (empty/whitespace/pure-punctuation
                # short-circuit before reaching the compare path).
                from services.escrow_service import normalize_pickup_code as _n
                if _n(bad):
                    log = await db.pickup_attempt_log.find_one(
                        {"auction_id": auction_id})
                    assert log is not None
            finally:
                await _cleanup(db, seller_id, buyer_id, auction_id)
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario E — Already-confirmed code cannot re-release
# ─────────────────────────────────────────────────────────────
class TestScenarioE_NoReusedRelease:
    def test_E1_already_released_code_returns_404(
        self, event_loop, db, seller_id, buyer_id, auction_id,
    ):
        async def _run():
            await _seed_seller_with_connect(db, seller_id)
            code = "BVX-REPLAYTST"
            # Seed with escrow already in released state.
            await _seed_escrow(db,
                               auction_id=auction_id,
                               seller_id=seller_id,
                               buyer_id=buyer_id,
                               pickup_code=code,
                               status="released")
            try:
                from fastapi import HTTPException
                with patch("services.escrow_service.stripe.Transfer.create",
                           return_value=MagicMock(id="MUST_NOT_TRANSFER")):
                    with pytest.raises(HTTPException) as exc:
                        await confirm_pickup(db, seller_id, auction_id, code)
                # Not a "held" escrow → 404 escrow_not_found
                assert exc.value.status_code == 404
                # Ensure no second transfer happened (no state mutation)
                row = await db.escrow_transactions.find_one(
                    {"auction_id": auction_id})
                assert row["escrow_status"] == "released"
                assert row["stripe_transfer_id"] is None  # was already None from seed
            finally:
                await _cleanup(db, seller_id, buyer_id, auction_id)
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario F — Expired code returns 410 / does not release
# ─────────────────────────────────────────────────────────────
class TestScenarioF_ExpiredCode:
    def test_F1_expired_code_returns_410(
        self, event_loop, db, seller_id, buyer_id, auction_id,
    ):
        async def _run():
            await _seed_seller_with_connect(db, seller_id)
            code = "BVX-EXPIRED8"
            # Seed with expiry 1 hour in the past.
            await _seed_escrow(db,
                               auction_id=auction_id,
                               seller_id=seller_id,
                               buyer_id=buyer_id,
                               pickup_code=code,
                               expires_delta=-timedelta(hours=1))
            try:
                from fastapi import HTTPException
                with patch("services.escrow_service.stripe.Transfer.create",
                           return_value=MagicMock(id="MUST_NOT_TRANSFER")):
                    with pytest.raises(HTTPException) as exc:
                        await confirm_pickup(db, seller_id, auction_id, code)
                assert exc.value.status_code == 410
            finally:
                await _cleanup(db, seller_id, buyer_id, auction_id)
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario G — Legacy 6-char code still validates
# ─────────────────────────────────────────────────────────────
class TestScenarioG_LegacySixCharCompat:
    def test_G1_legacy_6char_code_still_accepted(
        self, event_loop, db, seller_id, buyer_id, auction_id,
    ):
        async def _run():
            await _seed_seller_with_connect(db, seller_id)
            legacy = "ARKC66"  # pre-iter455 format
            await _seed_escrow(db,
                               auction_id=auction_id,
                               seller_id=seller_id,
                               buyer_id=buyer_id,
                               pickup_code=legacy)
            try:
                with patch("services.escrow_service.stripe.Transfer.create",
                           return_value=MagicMock(id="tr_iter455_G")):
                    # Buyer of a legacy escrow still has the 6-char code.
                    # Seller enters it directly.
                    result = await confirm_pickup(db, seller_id, auction_id, legacy)
                assert result["status"] == "released"
                # Same code with lowercase
                # (would need re-seed to test — this test only proves the
                # first release worked)
            finally:
                await _cleanup(db, seller_id, buyer_id, auction_id)
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario H — Escrow + transactions share ONE code (iter455 core)
# ─────────────────────────────────────────────────────────────
class TestScenarioH_SharedCodeAcrossCollections:
    def test_H1_create_escrow_hold_reuses_transactions_pickup_code(
        self, event_loop, db, seller_id, buyer_id, auction_id,
    ):
        """When a transactions row (from payment_collection._pickup_code_for_win)
        already has a BVX-XXXXXXXX code for this auction, create_escrow_hold
        must REUSE it rather than issuing a second, different code."""
        async def _run():
            await _seed_seller_with_connect(db, seller_id)
            # Simulate the payment_collection.py path: transactions row
            # with a pre-existing BVX code.
            shared_code = "BVX-SHARE888"
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "listing_id": auction_id,
                "pickup_code_listing_id": auction_id,
                "pickup_code": shared_code,
                "pickup_code_seller_id": seller_id,
                "buyer_id": buyer_id,
                "seller_id": seller_id,
                "hammer_price": 14.0,
                "amount": 14.0,
                "payment_method": "stripe",
                "commission_already_collected": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            try:
                # Prevent send_pickup_code_email from actually running.
                with patch(
                    "services.email_service.send_pickup_code_email",
                    return_value=None,
                ):
                    escrow = await create_escrow_hold(
                        db=db,
                        auction_id=auction_id,
                        listing_id=auction_id,
                        buyer_id=buyer_id,
                        seller_id=seller_id,
                        hammer_price_cents=1400,
                        total_charged_cents=1500,
                        application_fee_cents=100,
                        stripe_payment_intent_id=f"pi_H1_{auction_id}",
                        province="QC",
                    )
                # The escrow row must reuse the buyer-facing BVX code.
                assert escrow["pickup_code"] == shared_code, (
                    f"escrow generated {escrow['pickup_code']} instead of "
                    f"reusing transactions code {shared_code}"
                )
                # And now the seller can enter that SAME code and release.
                with patch(
                    "services.escrow_service.stripe.Transfer.create",
                    return_value=MagicMock(id="tr_iter455_H1"),
                ):
                    result = await confirm_pickup(
                        db, seller_id, auction_id, shared_code
                    )
                assert result["status"] == "released"
            finally:
                await _cleanup(db, seller_id, buyer_id, auction_id)
        event_loop.run_until_complete(_run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
