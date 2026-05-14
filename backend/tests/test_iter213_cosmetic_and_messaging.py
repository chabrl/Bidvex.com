"""
iter213 — Verification banner backend + In-app messaging fix + cosmetics

Covers:
  • POST /api/storage-facilities/dashboard now allows unverified-registration
    facilities to fetch their dashboard (so the frontend banner can show).
  • routes.messages.create_auction_won_conversation accepts BOTH the legacy
    (item_title, final_price) and the new (listing_title, winning_amount,
    winner_info, seller_info, lot_number) signatures without TypeError.
  • Bilingual EN+FR auction-thread email helper exists and renders.
  • Admin oversight endpoints /admin/messages/threads + /thread/{id} mounted.
  • Server uses FastAPI lifespan (no @app.on_event decorators left).
  • Pydantic Query() uses `pattern=` (no `regex=`).
  • JSX uses fetchPriority (no lowercase fetchpriority).
"""
import os
import re
import sys
import pytest


# ───────────────────────────────────────────────────────────────────────
# Static smoke (no HTTP)
# ───────────────────────────────────────────────────────────────────────

class TestLifespanMigration:
    def test_no_legacy_on_event_decorators(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        # No `@app.on_event("startup")` / `@app.on_event("shutdown")` anywhere
        assert "@app.on_event(" not in src, (
            "Found legacy @app.on_event handler; should be migrated to lifespan."
        )

    def test_lifespan_handler_is_registered(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        assert "FastAPI(lifespan=lifespan)" in src
        assert "@asynccontextmanager" in src
        assert "async def lifespan" in src


class TestQueryPatternMigration:
    def test_no_regex_kwarg_remaining(self):
        import subprocess
        out = subprocess.run(
            ["grep", "-rn", '\\bregex="', "/app/backend/routes", "/app/backend/services"],
            capture_output=True, text=True,
        )
        # grep returns 1 with no matches; if there *are* matches stdout != ""
        assert out.stdout.strip() == "", (
            f"Found legacy regex= kwargs (use pattern= instead):\n{out.stdout}"
        )


class TestFetchPriorityCasing:
    def test_no_lowercase_fetchpriority(self):
        import subprocess
        out = subprocess.run(
            ["grep", "-rn", "fetchpriority", "/app/frontend/src"],
            capture_output=True, text=True,
        )
        assert out.stdout.strip() == "", (
            f"Found lowercase fetchpriority (React expects fetchPriority):\n{out.stdout}"
        )


class TestMessagesSignatureFix:
    """The function must accept BOTH legacy and new kwarg sets."""

    @pytest.mark.asyncio
    async def test_legacy_signature_call(self, monkeypatch):
        # Lazy import + stub the db / side-effect modules
        import deps as deps_module
        from routes import messages as msgs

        class FakeColl:
            async def find_one(self, *a, **k): return None
            async def insert_one(self, *a, **k): return None
            async def update_one(self, *a, **k): return None

        class FakeDB:
            conversations = FakeColl()
            messages = FakeColl()
            users = FakeColl()

        # ws_manager + email + sms must be no-ops
        msgs.ws_manager = None
        async def _noop(*a, **k): return True
        monkeypatch.setattr(
            "services.email_notifications.send_auction_thread_opened_email",
            _noop,
            raising=False,
        )

        result = await msgs.create_auction_won_conversation(
            db=FakeDB(),
            listing_id="lst-1",
            seller_id="seller-1",
            winner_id="winner-1",
            final_price=199.0,
            item_title="Old-style call",
        )
        # Should return a conversation id (uuid) rather than None
        assert isinstance(result, str) and len(result) >= 32

    @pytest.mark.asyncio
    async def test_new_signature_call_with_kwargs(self, monkeypatch):
        from routes import messages as msgs

        class FakeColl:
            async def find_one(self, *a, **k): return None
            async def insert_one(self, *a, **k): return None
            async def update_one(self, *a, **k): return None

        class FakeDB:
            conversations = FakeColl()
            messages = FakeColl()
            users = FakeColl()

        msgs.ws_manager = None
        async def _noop(*a, **k): return True
        monkeypatch.setattr(
            "services.email_notifications.send_auction_thread_opened_email",
            _noop,
            raising=False,
        )

        # This is exactly how routes/auctions.py calls the function (the
        # signature that was broken before iter213).
        result = await msgs.create_auction_won_conversation(
            db=FakeDB(),
            listing_id="lst-2",
            listing_title="Vintage Camera",
            winner_id="winner-2",
            seller_id="seller-2",
            winning_amount=2500.0,
            winner_info={"id": "winner-2", "name": "Alice", "email": "alice@x.com"},
            seller_info={"id": "seller-2", "name": "Bob", "email": "bob@x.com"},
            lot_number=7,
        )
        assert isinstance(result, str) and len(result) >= 32


class TestBilingualThreadEmail:
    @pytest.mark.asyncio
    async def test_winner_email_bilingual_and_link(self, monkeypatch):
        from services import email_notifications as en
        captured = {}

        async def fake_send_email(*, to_email, subject, html_content):
            captured.update(to_email=to_email, subject=subject, html=html_content)
            return True

        monkeypatch.setattr(en, "send_email", fake_send_email)

        ok = await en.send_auction_thread_opened_email(
            recipient={"email": "alice@x.com", "name": "Alice"},
            role="winner",
            counterparty={"name": "Bob"},
            listing_title="Vintage Camera",
            listing_id="abcd1234efgh5678",
            conversation_id="conv-uuid",
            winning_amount=2500.0,
        )
        assert ok is True
        # English copy
        assert "Congratulations" in captured["html"]
        assert "won the auction" in captured["html"].lower()
        # French copy
        assert "Félicitations" in captured["html"]
        assert "remporté" in captured["html"]
        # Deep link
        assert "messages?conversation=conv-uuid" in captured["html"]
        # CTA text bilingual
        assert "Open message thread" in captured["html"]
        assert "Ouvrir le fil" in captured["html"]

    @pytest.mark.asyncio
    async def test_seller_email_bilingual(self, monkeypatch):
        from services import email_notifications as en
        captured = {}

        async def fake_send_email(*, to_email, subject, html_content):
            captured.update(to_email=to_email, subject=subject, html=html_content)
            return True

        monkeypatch.setattr(en, "send_email", fake_send_email)

        ok = await en.send_auction_thread_opened_email(
            recipient={"email": "bob@x.com", "name": "Bob"},
            role="seller",
            counterparty={"name": "Alice"},
            listing_title="Vintage Camera",
            listing_id="abcd1234efgh5678",
            conversation_id="conv-uuid",
            winning_amount=2500.0,
        )
        assert ok is True
        # Seller subject EN
        assert "Sold" in captured["subject"] or "sold" in captured["html"].lower()
        # Bilingual
        assert "annonce" in captured["html"]


class TestAdminThreadOversight:
    def _routes(self):
        # Import the server module without reloading (to avoid lifespan flakiness)
        if "server" not in sys.modules:
            import server  # noqa: F401
        from server import app
        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_admin_threads_endpoint_mounted(self):
        assert "/api/admin/messages/threads" in self._routes()

    def test_admin_thread_detail_endpoint_mounted(self):
        assert "/api/admin/messages/thread/{conversation_id}" in self._routes()


class TestStorageDashboardSoftened:
    """The /storage-facilities/dashboard endpoint must NOT require the strict
    `_require_verified_facility` gate so unverified facilities can see the
    progress banner.
    """

    def test_dashboard_uses_facility_owner_dep(self):
        with open("/app/backend/routes/storage_auctions.py") as f:
            src = f.read()
        # The dashboard function definition must NOT depend on `_require_verified_facility`
        # Find the dashboard function
        m = re.search(
            r'@storage_router\.get\("/storage-facilities/dashboard"\).*?def facility_dashboard\([^)]*\)',
            src, re.S,
        )
        assert m, "Could not locate facility_dashboard definition"
        sig = m.group(0)
        assert "_require_verified_facility" not in sig, (
            "Dashboard must not use the strict verified-facility gate — it locks "
            "facilities out from seeing the verification progress banner."
        )

    def test_my_auctions_uses_soft_gate(self):
        with open("/app/backend/routes/storage_auctions.py") as f:
            src = f.read()
        m = re.search(
            r'@storage_router\.get\("/storage-facilities/my-auctions"\).*?def my_facility_auctions\([^)]*\)',
            src, re.S,
        )
        assert m
        sig = m.group(0)
        assert "_require_verified_facility" not in sig


class TestAnalyticsEvents:
    def test_analytics_events_file_exists(self):
        path = "/app/frontend/src/utils/analytics_events.js"
        assert os.path.isfile(path), "analytics_events.js missing"
        with open(path) as f:
            src = f.read()
        assert "trackPartnerRegistrationConversion" in src
        assert "AW-18140095337" in src
        assert "gtag" in src

    def test_track_partner_registration_signature(self):
        with open("/app/frontend/src/utils/analytics_events.js") as f:
            src = f.read()
        # Function must accept (conversionLabel, extras=)
        assert "trackPartnerRegistrationConversion = (conversionLabel" in src
        # And forward `send_to` with the Ads account
        assert "send_to: `${ADS_ACCOUNT_ID}" in src
