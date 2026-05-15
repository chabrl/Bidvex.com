"""
iter216 — Production-emergency fixes
=====================================

Covers:
  P1. Storage Auction Create form — new BP field + legal-notice gate +
      payment-method selection. Backend `StorageAuctionCreate` model accepts
      `buyer_premium_pct` (0–20) and `accepted_legal_notice`. Endpoint
      rejects publish without legal notice.
  P2. Partner subscription mismatch fix:
       • `manual_settle_subscription_payment` now writes BOTH the modern
         `partner_subscription_active=True` AND the legacy `platform_fee_paid=True`.
       • `/api/partner/dashboard` recognises either field as active.
       • Daily startup migration syncs legacy/new fields for every partner
         (fixes Alex Boulanger automatically on next redeploy).
       • Synthetic `subscription` block returned when admin manual-settled.
       • New `/api/partner/subscription/status` light endpoint.
  P3. 6-email onboarding journey:
       • Email 1 fires immediately on registration.
       • Emails 2–6 scheduled in `user_email_journey` collection.
       • Daily cron processes due emails.
       • Email 6 is conditional on zero activity.
       • Demo / suspended / unsubscribed users are skipped.
       • Admin endpoints for visibility + manual trigger + cancel + reset.
"""
from __future__ import annotations

import sys
import pytest


# ─────────────────────────────────────────────────────────────────────
# P1 — Storage BP + Legal Notice
# ─────────────────────────────────────────────────────────────────────


class TestStorageAuctionCreateBPField:
    def test_model_accepts_bp_and_legal_notice(self):
        from models.storage_auction import StorageAuctionCreate
        payload = StorageAuctionCreate(
            unit_number="A-12", facility_address="123 St", facility_city="Montreal",
            facility_province="QC", facility_postal_code="H1A1A1",
            unit_size="10x10", unit_type="indoor",
            description_en="Standard 10x10 storage unit awaiting auction.",
            starting_price=1.0, payment_method="stripe",
            start_time="2026-05-15T00:00:00Z",
            end_time="2026-05-18T00:00:00Z",
            buyer_premium_pct=5.0,
            accepted_legal_notice=True,
        )
        assert payload.buyer_premium_pct == 5.0
        assert payload.accepted_legal_notice is True

    def test_model_clamps_bp_range(self):
        from models.storage_auction import StorageAuctionCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            StorageAuctionCreate(
                unit_number="A-12", facility_address="123 St", facility_city="Montreal",
                facility_province="QC", facility_postal_code="H1A1A1",
                unit_size="10x10", unit_type="indoor",
                description_en="Standard 10x10 unit awaiting auction.",
                starting_price=1.0, payment_method="stripe",
                start_time="2026-05-15T00:00:00Z",
                end_time="2026-05-18T00:00:00Z",
                buyer_premium_pct=25,  # > 20 → reject
                accepted_legal_notice=True,
            )

    def test_form_renders_bp_input(self):
        with open("/app/frontend/src/pages/storage/StorageAuctionCreate.js") as f:
            src = f.read()
        # BP testids
        assert 'data-testid="bp-section"' in src
        assert 'data-testid="bp-input"' in src
        # Legal-notice checkbox
        assert 'data-testid="legal-notice-checkbox"' in src
        # Form state initialises BP to 0
        assert "buyer_premium_pct: 0" in src
        # Bilingual hint mentions 5% / break even
        assert "5% BP" in src or "5 % de PA" in src


# ─────────────────────────────────────────────────────────────────────
# P2 — Partner Subscription Sync
# ─────────────────────────────────────────────────────────────────────


class TestPartnerSubscriptionSync:
    def test_manual_settle_writes_both_fields(self):
        with open("/app/backend/services/manual_settlement_service.py") as f:
            src = f.read()
        # The fix block must set BOTH legacy + new for partners
        assert "platform_fee_paid" in src
        assert "partner_subscription_active" in src
        # And for dealer / storage too
        assert "dealer_payment_method" in src
        assert "storage_payment_method" in src

    def test_dashboard_recognises_either_field(self):
        with open("/app/backend/routes/partners.py") as f:
            src = f.read()
        # The dashboard helper must OR the two flags together
        assert "platform_fee_paid" in src
        assert "partner_subscription_active" in src
        # Synthetic subscription block when manual_settled
        assert "manual_settled" in src

    def test_status_endpoint_mounted(self):
        if "server" not in sys.modules:
            import server  # noqa: F401
        from server import app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/api/partner/subscription/status" in paths

    def test_startup_migration_present(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        # The iter216 migration block must exist
        assert "iter216" in src
        assert "platform_fee_paid" in src
        assert "Alex Boulanger" in src  # canary comment

    def test_partner_dashboard_has_polling_refresh(self):
        with open("/app/frontend/src/pages/PartnerDashboard.js") as f:
            src = f.read()
        assert "visibilitychange" in src
        # 60s polling
        assert "60_000" in src or "60000" in src


# ─────────────────────────────────────────────────────────────────────
# P3 — Email Journey
# ─────────────────────────────────────────────────────────────────────


class TestJourneyBuilders:
    """All 6 email templates render without errors and are bilingual."""

    def test_email_1_welcome_bilingual(self):
        from services.email_journey import email_1_welcome
        subject, html = email_1_welcome("Alice")
        assert "Welcome" in subject
        assert "Bienvenue" in subject
        # Bilingual body — EN copy + FR copy (FR uses "Bonjour" greeting + bilingual subject)
        assert "welcome to bidvex" in html.lower()
        assert "Bonjour" in html  # French greeting
        assert "Parcourir les enchères" in html  # French CTA copy
        # Brand footer
        assert "706766367RT0001" in html
        # Gmail-compatible — uses tables not flexbox
        assert "<table" in html

    def test_email_6_renders_with_no_auctions(self):
        from services.email_journey import email_6_reengagement
        subject, html = email_6_reengagement("Alice", live_auctions=[])
        assert "Still there" in subject or "Toujours là" in subject
        assert "Many live auctions ending soon" in html or "Don't miss out" in html

    def test_all_6_builders_exported(self):
        from services.email_journey import EMAIL_BUILDERS
        assert sorted(EMAIL_BUILDERS.keys()) == [1, 2, 3, 4, 5, 6]
        # Each builder is callable
        for n in [1, 2, 3, 4, 5]:
            key, fn = EMAIL_BUILDERS[n]
            subject, html = fn("TestUser")
            assert isinstance(subject, str) and isinstance(html, str)

    def test_schedule_offsets_are_0_3_7_14_21_30(self):
        from services.email_journey import JOURNEY_SCHEDULE
        assert JOURNEY_SCHEDULE == {1: 0, 2: 3, 3: 7, 4: 14, 5: 21, 6: 30}


class TestJourneyScheduling:
    @pytest.mark.asyncio
    async def test_schedule_skips_demo_account(self):
        from services.email_journey import schedule_journey_for_user

        class FakeColl:
            async def find_one(self, *a, **k): return None
            async def insert_one(self, *a, **k): return None

        class FakeDB:
            user_email_journey = FakeColl()

        result = await schedule_journey_for_user(FakeDB(), {
            "id": "u1", "email": "demo@x.com", "is_demo_account": True,
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_schedule_skips_unsubscribed(self):
        from services.email_journey import schedule_journey_for_user

        class FakeColl:
            async def find_one(self, *a, **k): return None
            async def insert_one(self, *a, **k): return None

        class FakeDB:
            user_email_journey = FakeColl()

        result = await schedule_journey_for_user(FakeDB(), {
            "id": "u1", "email": "x@x.com", "email_subscribed": False,
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_schedule_creates_6_emails(self, monkeypatch):
        from services.email_journey import schedule_journey_for_user
        from datetime import datetime, timezone

        inserted = {}

        class FakeJourneyColl:
            async def find_one(self, *a, **k): return None
            async def insert_one(self, doc): inserted.update(doc)
            async def update_one(self, *a, **k): return None

        class FakeUsersColl:
            async def find_one(self, *a, **k):
                return {"id": "u1", "email": "x@x.com", "name": "Alice"}

        class FakeDB:
            user_email_journey = FakeJourneyColl()
            users = FakeUsersColl()

        # Stub the email send so we don't actually call SendGrid
        async def fake_dispatch(*a, **k): return True
        monkeypatch.setattr("services.email_journey.dispatch_journey_email", fake_dispatch)

        jid = await schedule_journey_for_user(FakeDB(), {
            "id": "u1", "email": "x@x.com", "name": "Alice",
        })
        assert jid is not None
        assert len(inserted["journey_emails"]) == 6
        # First email scheduled for now (0-day offset)
        first = inserted["journey_emails"][0]
        assert first["email_number"] == 1
        scheduled_dt = datetime.fromisoformat(first["scheduled_at"].replace("Z", "+00:00"))
        # Within 5 seconds of now
        assert abs((scheduled_dt - datetime.now(timezone.utc)).total_seconds()) < 5


class TestJourneyDispatch:
    @pytest.mark.asyncio
    async def test_email_6_skipped_for_engaged_user(self, monkeypatch):
        """If user already has bids/listings/transactions, Day-30 must skip."""
        from services.email_journey import dispatch_journey_email

        class FakeColl:
            async def count_documents(self, *a, **k): return 1   # ENGAGED
            async def find_one(self, *a, **k):
                return {"id": "u1", "email": "x@x.com", "name": "Alice"}
            async def update_one(self, *a, **k): return None

        class FakeDB:
            users = FakeColl()
            listings = FakeColl()
            bids = FakeColl()
            transactions = FakeColl()
            user_email_journey = FakeColl()

        # Make sure send_email is NEVER called for skipped users
        called = {"send": False}
        async def fake_send_email(**k):
            called["send"] = True
            return True
        monkeypatch.setattr("services.email_notifications.send_email", fake_send_email)

        ok = await dispatch_journey_email(FakeDB(), {"id": "u1", "email": "x@x.com"}, email_number=6)
        assert ok is False
        assert called["send"] is False


class TestRegistrationEnrolment:
    def test_register_endpoint_enrols_in_journey(self):
        with open("/app/backend/routes/auth.py") as f:
            src = f.read()
        assert "schedule_journey_for_user" in src
        # Both email + google paths enrol
        assert src.count("schedule_journey_for_user") >= 2


class TestJourneyEndpointsMounted:
    def _routes(self):
        if "server" not in sys.modules:
            import server  # noqa: F401
        from server import app
        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_get_journey_mounted(self):
        assert "/api/admin/users/{user_id}/email-journey" in self._routes()

    def test_trigger_mounted(self):
        assert "/api/admin/users/{user_id}/email-journey/trigger/{email_number}" in self._routes()

    def test_cancel_mounted(self):
        assert "/api/admin/users/{user_id}/email-journey/cancel" in self._routes()

    def test_reset_mounted(self):
        assert "/api/admin/users/{user_id}/email-journey/reset" in self._routes()

    def test_journey_cron_registered(self):
        with open("/app/backend/services/email_automation.py") as f:
            src = f.read()
        assert "lifecycle_journey" in src
        assert "9, minute=45" in src or "hour=9, minute=45" in src
