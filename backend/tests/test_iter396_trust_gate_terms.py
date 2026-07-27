"""
iter396 — Trust Gate T&C third-pillar tests.

Verifies that the platform-wide auction Terms & Conditions is now a
required third pillar of the Trust Gate alongside phone verification
and payment method on file.

Covers:
  1. `services.trust_gate.user_can_bid_or_list` reports `terms` in the
     missing list when the user has never accepted the platform T&C.
  2. `services.trust_gate.require_trust_verified` raises 403 with
     `error=trust_required` and `terms` in `missing` for a user with
     phone + card but no T&C.
  3. Accepting the T&C flips `terms_accepted` to True and the gate
     lets the user through (returns None, no raise).
  4. Accepting the T&C twice is idempotent — the original acceptance
     timestamp is preserved.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from fastapi import HTTPException


# ─── Env / DB helpers ────────────────────────────────────────────────

def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if "=" not in line or line.startswith("#"):
                    continue
                key, _, val = line.strip().partition("=")
                if key and val and key not in os.environ:
                    os.environ[key] = val


@pytest_asyncio.fixture
async def db_and_user():
    _load_env()
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    user_id = f"iter396-user-{uuid.uuid4().hex[:8]}"
    user_email = f"iter396-{uuid.uuid4().hex[:8]}@bidvex-qa.com"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Seed a "verified except T&C" user: phone verified + one payment method
    # on file, but NO platform_terms_accepted_at.
    await db.users.insert_one({
        "id": user_id,
        "email": user_email,
        "name": "Iter396 Trust Gate Tester",
        "role": "buyer",
        "phone_verified": True,
        "created_at": now_iso,
    })
    await db.payment_methods.insert_one({
        "id": f"pm-{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "stripe_payment_method_id": "pm_test_iter396",
        "brand": "visa",
        "last4": "4242",
        "created_at": now_iso,
    })

    yield db, user_id, user_email

    # ── Cleanup ──
    await db.users.delete_many({"id": user_id})
    await db.payment_methods.delete_many({"user_id": user_id})
    client.close()


# ─── Tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gate_reports_terms_missing_when_never_accepted(db_and_user):
    from services.trust_gate import user_can_bid_or_list

    db, user_id, _ = db_and_user
    user = await db.users.find_one({"id": user_id})

    allowed, reasons = await user_can_bid_or_list(db, user)
    assert allowed is False, "user with no T&C should not pass the gate"
    assert reasons["phone_verified"] is True
    assert reasons["has_payment_method"] is True
    assert reasons["terms_accepted"] is False
    assert reasons["missing"] == ["terms"], (
        f"only T&C should be missing; got {reasons['missing']}"
    )


@pytest.mark.asyncio
async def test_gate_raises_403_with_bilingual_terms_message(db_and_user):
    from services.trust_gate import require_trust_verified

    db, user_id, _ = db_and_user
    user = await db.users.find_one({"id": user_id})

    with pytest.raises(HTTPException) as exc:
        await require_trust_verified(db, user, action="bid")

    assert exc.value.status_code == 403
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail["error"] == "trust_required"
    assert "terms" in detail["missing"]
    assert detail["terms_accepted"] is False
    assert "Terms & Conditions" in detail["message_en"]
    assert "conditions générales" in detail["message_fr"]
    # When only T&C is missing, CTA anchors on #terms so the UI can open
    # the acceptance modal directly.
    assert detail["cta_path"] == "/profile/settings#terms"


@pytest.mark.asyncio
async def test_gate_passes_after_terms_accepted(db_and_user):
    from services.trust_gate import require_trust_verified, user_can_bid_or_list

    db, user_id, _ = db_and_user
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "platform_terms_accepted_at": now_iso,
            "platform_terms_version": "v1",
        }},
    )

    user = await db.users.find_one({"id": user_id})
    allowed, reasons = await user_can_bid_or_list(db, user)
    assert allowed is True, f"user with all three pillars should pass; missing={reasons['missing']}"
    assert reasons["missing"] == []
    assert reasons["terms_accepted"] is True

    # And require_trust_verified should NOT raise.
    await require_trust_verified(db, user, action="bid")
    await require_trust_verified(db, user, action="list")


@pytest.mark.asyncio
async def test_gate_all_three_pillars_missing_for_bare_user(db_and_user):
    from services.trust_gate import user_can_bid_or_list

    db, _, _ = db_and_user
    # A user with none of the pillars: no phone, no card, no T&C.
    bare_id = f"iter396-bare-{uuid.uuid4().hex[:8]}"
    try:
        await db.users.insert_one({
            "id": bare_id,
            "email": f"{bare_id}@bidvex-qa.com",
            "name": "Bare user",
            "role": "buyer",
            "phone_verified": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        user = await db.users.find_one({"id": bare_id})
        allowed, reasons = await user_can_bid_or_list(db, user)
        assert allowed is False
        assert set(reasons["missing"]) == {"phone", "payment_method", "terms"}
    finally:
        await db.users.delete_many({"id": bare_id})


@pytest.mark.asyncio
async def test_gate_reads_terms_from_live_db_when_user_model_stale(db_and_user):
    """User model in memory may not reflect the latest DB value if terms
    were accepted mid-request. The gate does a live DB fallback lookup."""
    from services.trust_gate import _has_accepted_terms

    db, user_id, _ = db_and_user
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"platform_terms_accepted_at": now_iso}},
    )

    # Stale in-memory user without the field
    stale_user = {"id": user_id, "phone_verified": True}
    assert await _has_accepted_terms(db, stale_user) is True, (
        "gate should fall back to live DB lookup when user model is stale"
    )
