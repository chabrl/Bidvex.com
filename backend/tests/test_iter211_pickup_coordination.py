"""
iter211 — Pickup Coordination tests (P1.C)

Covers:
  1. send_pickup_coordination_emails inserts 2 rows in pickup_notifications
     and tags each with payment_intent_id.
  2. Idempotent: re-calling with same payment_intent_id is a no-op.
  3. Skipped when buyer or seller email is missing.
  4. Bilingual EN/FR copy detection.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def fake_db():
    """Build a fake Motor-like db that records insert/find/update calls."""
    db = MagicMock()
    db.pickup_notifications = MagicMock()
    db.users = MagicMock()
    db.listings = MagicMock()

    state = {"notifications": [], "unique_pi": set()}

    async def fake_pn_find_one(query, projection=None):
        pi = (query or {}).get("payment_intent_id")
        if pi and pi in state["unique_pi"]:
            return {"id": "dup", "payment_intent_id": pi}
        return None

    async def fake_pn_insert_many(docs):
        for d in docs:
            state["notifications"].append(d)
            if d.get("payment_intent_id"):
                state["unique_pi"].add(d["payment_intent_id"])
        rv = MagicMock()
        rv.inserted_ids = [d["id"] for d in docs]
        return rv

    async def fake_users_find_one(query, projection=None):
        uid = (query or {}).get("id")
        return state.get(f"user:{uid}")

    async def fake_listings_find_one(query, projection=None):
        return {"id": (query or {}).get("id"), "title": "Vintage Hammer"}

    db.pickup_notifications.find_one = fake_pn_find_one
    db.pickup_notifications.insert_many = fake_pn_insert_many
    db.users.find_one = fake_users_find_one
    db.listings.find_one = fake_listings_find_one
    db.__getitem__ = lambda self, k: db.pickup_notifications if k == "pickup_notifications" else None
    db._state = state  # type: ignore
    return db


@pytest.mark.asyncio
async def test_dispatches_both_emails_and_inserts_2_rows(fake_db):
    fake_db._state["user:buyer-1"] = {
        "id": "buyer-1", "email": "buyer@test.com", "full_name": "Bob Buyer",
        "phone": "+15145551111", "city": "Montreal", "province": "QC",
    }
    fake_db._state["user:seller-1"] = {
        "id": "seller-1", "email": "seller@test.com", "full_name": "Sam Seller",
        "phone": "+14165552222", "city": "Toronto", "province": "ON",
    }

    with patch(
        "services.pickup_coordination_service._send_bilingual_pickup_email",
        return_value=True,
    ) as mock_send:
        from services.pickup_coordination_service import send_pickup_coordination_emails
        result = await send_pickup_coordination_emails(
            db=fake_db,
            listing_id="lst-1",
            buyer_id="buyer-1",
            seller_id="seller-1",
            payment_intent_id="pi_abc",
            listing_title="Vintage Hammer",
        )
        assert result["status"] == "ok"
        assert result["buyer_email_sent"] is True
        assert result["seller_email_sent"] is True
        assert result["notifications_created"] == 2
        # Both bilingual emails fired
        assert mock_send.call_count == 2
        # 2 rows persisted with correct roles
        assert len(fake_db._state["notifications"]) == 2
        kinds = sorted(n["kind"] for n in fake_db._state["notifications"])
        assert kinds == ["pickup_coordination_seller", "pickup_coordination_winner"]
        # Winner row links to seller as counterparty, seller row links to buyer
        winner_row = next(n for n in fake_db._state["notifications"] if n["kind"] == "pickup_coordination_winner")
        seller_row = next(n for n in fake_db._state["notifications"] if n["kind"] == "pickup_coordination_seller")
        assert winner_row["counterparty_id"] == "seller-1"
        assert winner_row["counterparty_email"] == "seller@test.com"
        assert winner_row["title_en"].startswith("Coordinate pickup with the seller")
        assert winner_row["title_fr"].startswith("Coordonner la collecte avec le vendeur")
        assert seller_row["counterparty_id"] == "buyer-1"
        assert seller_row["counterparty_email"] == "buyer@test.com"


@pytest.mark.asyncio
async def test_idempotent_on_duplicate_pi(fake_db):
    fake_db._state["user:buyer-1"] = {"id": "buyer-1", "email": "buyer@test.com"}
    fake_db._state["user:seller-1"] = {"id": "seller-1", "email": "seller@test.com"}
    fake_db._state["unique_pi"].add("pi_dup")

    with patch(
        "services.pickup_coordination_service._send_bilingual_pickup_email",
        return_value=True,
    ) as mock_send:
        from services.pickup_coordination_service import send_pickup_coordination_emails
        result = await send_pickup_coordination_emails(
            db=fake_db,
            listing_id="lst-1",
            buyer_id="buyer-1",
            seller_id="seller-1",
            payment_intent_id="pi_dup",
            listing_title="X",
        )
        assert result["status"] == "duplicate"
        assert mock_send.call_count == 0


@pytest.mark.asyncio
async def test_skipped_when_buyer_email_missing(fake_db):
    fake_db._state["user:buyer-1"] = {"id": "buyer-1"}  # no email
    fake_db._state["user:seller-1"] = {"id": "seller-1", "email": "seller@test.com"}

    from services.pickup_coordination_service import send_pickup_coordination_emails
    result = await send_pickup_coordination_emails(
        db=fake_db,
        listing_id="lst-1",
        buyer_id="buyer-1",
        seller_id="seller-1",
        payment_intent_id="pi_skip",
        listing_title="X",
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "missing_email"
    assert len(fake_db._state["notifications"]) == 0


@pytest.mark.asyncio
async def test_french_winner_gets_french_subject(fake_db):
    fake_db._state["user:buyer-fr"] = {
        "id": "buyer-fr", "email": "buyer@quebec.ca", "preferred_language": "fr",
        "full_name": "Pierre", "phone": "+15145553333",
    }
    fake_db._state["user:seller-en"] = {
        "id": "seller-en", "email": "seller@ontario.ca", "preferred_language": "en",
        "full_name": "John",
    }
    sent_subjects = []

    def fake_send(**kwargs):
        sent_subjects.append((kwargs.get("to_email"), kwargs.get("counterparty_name"), kwargs.get("role"), kwargs.get("language")))
        return True

    with patch(
        "services.pickup_coordination_service._send_bilingual_pickup_email",
        side_effect=lambda **k: sent_subjects.append((k.get("to_email"), k.get("role"), k.get("language"))) or True,
    ):
        from services.pickup_coordination_service import send_pickup_coordination_emails
        await send_pickup_coordination_emails(
            db=fake_db,
            listing_id="lst-2",
            buyer_id="buyer-fr",
            seller_id="seller-en",
            payment_intent_id="pi_fr",
            listing_title="Marteau",
        )
        # Buyer (French) called with fr; seller (English) called with en
        buyer_calls = [c for c in sent_subjects if c[0] == "buyer@quebec.ca"]
        seller_calls = [c for c in sent_subjects if c[0] == "seller@ontario.ca"]
        assert len(buyer_calls) == 1
        assert len(seller_calls) == 1
        assert buyer_calls[0][2] == "fr"
        assert seller_calls[0][2] == "en"
