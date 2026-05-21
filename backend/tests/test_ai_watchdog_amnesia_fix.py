"""
HOTFIX — Eliminate AI Watchdog Amnesia Loop
3 targeted pytest tests covering:
  1. Approved listing edit → scanner bypass kicks in (returns admin_whitelisted)
  2. Duplicate review insert → returns existing row, no second insert
  3. Rejected listing edit → bypass flags cleared, scanner runs again
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME") or "bazario_db"


@pytest.fixture
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    db_instance = client[DB_NAME]
    import routes.admin_ai_review as mod
    original = mod.get_db
    mod.get_db = lambda: db_instance
    yield db_instance
    mod.get_db = original
    client.close()


def _seller_user(seller_id: str):
    class _U:
        pass
    u = _U()
    u.id = seller_id
    u.email = f"{seller_id[:8]}@seller.test"
    u.role = "user"
    u.account_type = "personal"
    return u


def _admin_user():
    class _U:
        pass
    u = _U()
    u.id = "admin-test-id"
    u.email = "charbel911@gmail.com"
    u.role = "admin"
    return u


@pytest.mark.asyncio
async def test_approved_listing_edit_bypasses_ai_scanner(db):
    """FIX 1 — When a listing carries the admin_approved_override passport,
    POST /listings/{id}/flag-for-ai-review must short-circuit and return
    reason=admin_whitelisted without creating a new review row."""
    from routes.admin_ai_review import flag_listing_for_ai_review, FlagForReviewRequest

    seller_id = f"sel-bypass-{uuid.uuid4().hex[:8]}"
    listing_id = f"lst-bypass-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Seed an already-approved listing
    await db.listings.insert_one({
        "id": listing_id,
        "seller_id": seller_id,
        "title": "Approved Listing",
        "status": "active",
        "category": "Furniture",
        "admin_approved_override": True,  # Passport stamped
        "ai_scan_bypass": True,
        "admin_approved_by": "admin-test-id",
        "admin_approved_at": now,
        "created_at": now,
    })

    result = await flag_listing_for_ai_review(
        listing_id=listing_id,
        payload=FlagForReviewRequest(
            listing_type="single",
            ai_reason_en="Test re-scan attempt",
            ai_reason_fr="Tentative de re-scan de test",
            suggested_category="Antiques",
        ),
        current_user=_seller_user(seller_id),
    )

    # Assertions
    assert result["flagged"] is False
    assert result["reason"] == "admin_whitelisted"
    assert result.get("review_id") is None

    # CRITICAL: No new review row was created
    review_count = await db.listing_reviews.count_documents({"listing_id": listing_id})
    assert review_count == 0, "Bypass MUST NOT insert a listing_reviews row"

    # Listing must still be active + still carry passport flags
    fresh = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    assert fresh["status"] == "active"
    assert fresh["admin_approved_override"] is True
    assert fresh["ai_scan_bypass"] is True

    # Cleanup
    await db.listings.delete_one({"id": listing_id})


@pytest.mark.asyncio
async def test_duplicate_review_insert_returns_existing_row(db):
    """FIX 4 (b) — A second flag-for-ai-review call for the same listing
    must return the existing pending review row, NOT insert a duplicate."""
    from routes.admin_ai_review import flag_listing_for_ai_review, FlagForReviewRequest

    seller_id = f"sel-dup-{uuid.uuid4().hex[:8]}"
    listing_id = f"lst-dup-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Seed a listing (no passport — scanner is allowed to run)
    await db.listings.insert_one({
        "id": listing_id,
        "seller_id": seller_id,
        "title": "Duplicate Test Listing",
        "status": "active",
        "category": "Furniture",
        "created_at": now,
    })

    payload = FlagForReviewRequest(
        listing_type="single",
        ai_reason_en="Test scan",
        ai_reason_fr="Test de scan",
        suggested_category="Antiques",
    )

    # First call — should create a review row
    r1 = await flag_listing_for_ai_review(
        listing_id=listing_id, payload=payload, current_user=_seller_user(seller_id),
    )
    assert r1["success"] is True
    assert r1["review_id"] is not None
    first_review_id = r1["review_id"]

    # Second call — same listing, same seller. Must DEDUPE.
    r2 = await flag_listing_for_ai_review(
        listing_id=listing_id, payload=payload, current_user=_seller_user(seller_id),
    )
    assert r2["success"] is True
    assert r2.get("deduped") is True
    assert r2["review_id"] == first_review_id, "Second call must return the same review id"

    # CRITICAL: exactly ONE review row, not two
    review_count = await db.listing_reviews.count_documents({"listing_id": listing_id})
    assert review_count == 1, f"Expected exactly 1 review row, got {review_count}"

    # Cleanup
    await db.listings.delete_one({"id": listing_id})
    await db.listing_reviews.delete_many({"listing_id": listing_id})


@pytest.mark.asyncio
async def test_rejected_listing_edit_runs_scanner_again(db):
    """FIX 3 — When admin rejects a listing, the immunity-passport flags must
    be CLEARED so a corrected resubmission gets scanned fresh."""
    from routes.admin_ai_review import (
        flag_listing_for_ai_review, FlagForReviewRequest,
        admin_reject_listing_review, ReviewActionRequest,
    )

    seller_id = f"sel-rej-{uuid.uuid4().hex[:8]}"
    listing_id = f"lst-rej-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    # Seed a listing that previously got a passport (e.g. from a now-deleted
    # earlier approval) — simulates the state right before rejection.
    await db.listings.insert_one({
        "id": listing_id,
        "seller_id": seller_id,
        "title": "Reject Test Listing",
        "status": "pending_ai_review",
        "category": "Furniture",
        "admin_approved_override": True,  # Previously stamped
        "ai_scan_bypass": True,
        "created_at": now,
    })
    # Seed the matching pending review row
    review_id = f"rev-rej-{uuid.uuid4().hex[:8]}"
    await db.listing_reviews.insert_one({
        "id": review_id,
        "listing_id": listing_id,
        "listing_type": "single",
        "collection": "listings",
        "seller_id": seller_id,
        "listing_title": "Reject Test Listing",
        "seller_category": "Furniture",
        "suggested_category": "Antiques",
        "ai_confidence": 0.7,
        "ai_reason_en": "Test",
        "ai_reason_fr": "Test",
        "previous_status": "active",
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    })

    # Admin rejects the listing
    await admin_reject_listing_review(
        review_id=review_id,
        payload=ReviewActionRequest(admin_note="Not authentic per supplier records"),
        current_user=_admin_user(),
    )

    # Assert passport flags were CLEARED
    fresh = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    assert fresh["admin_approved_override"] is False, "Reject MUST clear admin_approved_override"
    assert fresh["ai_scan_bypass"] is False, "Reject MUST clear ai_scan_bypass"
    assert fresh["status"] == "rejected"

    # Now seller corrects + resubmits — scanner MUST run fresh (not bypass)
    # Flip status back to active so the seller can re-trigger a flag
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "active"}})
    result = await flag_listing_for_ai_review(
        listing_id=listing_id,
        payload=FlagForReviewRequest(
            listing_type="single",
            ai_reason_en="Re-scan after rejection",
            ai_reason_fr="Re-scan après rejet",
            suggested_category="Antiques",
        ),
        current_user=_seller_user(seller_id),
    )

    # Scanner ran fresh — reason is NOT admin_whitelisted
    assert result.get("reason") != "admin_whitelisted", "Scanner must run after reject"
    # A new review row exists for the resubmission (or dedupe of the rejected one
    # would have triggered — but rejected rows have status='rejected' so dedupe
    # filter for status='pending' won't match → fresh insert is created).
    pending_count = await db.listing_reviews.count_documents({
        "listing_id": listing_id, "status": "pending",
    })
    assert pending_count == 1, "Resubmission must create a new pending review row"

    # Cleanup
    await db.listings.delete_one({"id": listing_id})
    await db.listing_reviews.delete_many({"listing_id": listing_id})
