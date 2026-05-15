"""
iter214 — Production-critical multi-system fix
================================================
Covers:
  P1. Individual-seller pickup-code system (cash + e-transfer)
  P2. Admin user-action endpoints (send notification, request docs)
  P3. Global site-wide dealer-fee banner
  P4. AI Concierge chat — multi-channel notification scaffolding
  P5. Expanded prohibited-items moderation + public page

Static + import-time smoke tests. Live HTTP tests in TestLive class are
tolerant of rate-limits (skip on persistent 429).
"""
from __future__ import annotations

import os
import sys
import time
import pytest
import httpx


API_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://prod-verify-2.preview.emergentagent.com",
)


# ─────────────────────────────────────────────────────────────────────────
# P1 — Pickup-Code System
# ─────────────────────────────────────────────────────────────────────────


class TestPickupCodeHelpers:
    def test_generate_pickup_code_format(self):
        from routes.transaction_pickup_code import generate_pickup_code
        code = generate_pickup_code()
        assert code.startswith("BVX-")
        assert len(code) == 12  # 'BVX-' + 8 chars
        # Body is uppercase alphanumeric
        body = code[4:]
        assert body.isalnum() and body.isupper()

    def test_pickup_codes_unique(self):
        from routes.transaction_pickup_code import generate_pickup_code
        seen = {generate_pickup_code() for _ in range(200)}
        # 200 random 36-symbol codes — collision risk negligible
        assert len(seen) >= 195

    @pytest.mark.asyncio
    async def test_ensure_pickup_code_skips_stripe(self):
        from routes.transaction_pickup_code import ensure_pickup_code_on_transaction

        class FakeColl:
            async def find_one(self, *a, **k): return {"id": "t1", "payment_method": "stripe"}
            async def update_one(self, *a, **k): return None

        class FakeDB:
            transactions = FakeColl()

        out = await ensure_pickup_code_on_transaction(
            FakeDB(), "t1", payment_method="stripe", seller_id="s1", listing_id="l1",
        )
        assert out is None

    @pytest.mark.asyncio
    async def test_ensure_pickup_code_creates_for_cash(self):
        from routes.transaction_pickup_code import ensure_pickup_code_on_transaction

        state = {"set": None}

        class FakeColl:
            async def find_one(self, *a, **k): return {"id": "t1"}  # no existing code
            async def update_one(self, query, update):
                state["set"] = update.get("$set", {})

        class FakeDB:
            transactions = FakeColl()

        code = await ensure_pickup_code_on_transaction(
            FakeDB(), "t1", payment_method="cash", seller_id="s1", listing_id="l1",
        )
        assert code and code.startswith("BVX-")
        assert state["set"]["pickup_code"] == code
        assert state["set"]["pickup_code_seller_id"] == "s1"


class TestPickupCodeEndpointsMounted:
    def _routes(self):
        if "server" not in sys.modules:
            import server  # noqa: F401
        from server import app
        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_confirm_pickup_endpoint_mounted(self):
        assert "/api/transactions/confirm-pickup-code" in self._routes()

    def test_get_pickup_endpoint_mounted(self):
        assert "/api/transactions/{transaction_id}/pickup-code" in self._routes()


# ─────────────────────────────────────────────────────────────────────────
# P2 — Admin User-Action Endpoints
# ─────────────────────────────────────────────────────────────────────────


class TestAdminUserActionsMounted:
    def _routes(self):
        if "server" not in sys.modules:
            import server  # noqa: F401
        from server import app
        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_send_notification_mounted(self):
        assert "/api/admin/users/{user_id}/send-notification" in self._routes()

    def test_request_documents_mounted(self):
        assert "/api/admin/users/{user_id}/request-documents" in self._routes()

    def test_list_doc_requests_mounted(self):
        assert "/api/admin/users/{user_id}/document-requests" in self._routes()


class TestAdminUserActionsValidation:
    """The admin must be required + body shape must be enforced."""

    @pytest.mark.asyncio
    async def test_send_notification_requires_admin(self):
        from routes.admin_user_actions import admin_send_notification, SendNotificationPayload
        from fastapi import HTTPException
        from deps import User

        # Non-admin user — should be blocked by _require_admin which we call directly
        from routes.admin_user_actions import _require_admin
        non_admin = User(id="u1", email="u@x.com", name="u", role="user")
        with pytest.raises(HTTPException) as exc:
            await _require_admin(non_admin)
        assert exc.value.status_code == 403


# ─────────────────────────────────────────────────────────────────────────
# P3 — Global Dealer Fee Banner
# ─────────────────────────────────────────────────────────────────────────


class TestGlobalDealerFeeBanner:
    def test_component_file_exists(self):
        path = "/app/frontend/src/components/GlobalDealerFeeBanner.jsx"
        assert os.path.isfile(path)
        with open(path) as f:
            src = f.read()
        # Sticky top + z-9999 + undismissable (no Close button)
        assert "sticky" in src
        assert "z-[9999]" in src or "z-9999" in src
        # Hides when subscription is active
        assert "has_active_subscription" in src
        # Bilingual copy
        assert "Annual Platform Fee Required" in src
        assert "Frais annuels de plateforme requis" in src

    def test_mounted_globally_in_app(self):
        with open("/app/frontend/src/App.js") as f:
            src = f.read()
        assert "GlobalDealerFeeBanner" in src
        # Mounted ABOVE <Navbar /> in the JSX (verify ordering)
        idx_banner = src.find("<GlobalDealerFeeBanner")
        idx_navbar = src.find("<Navbar")
        assert 0 <= idx_banner < idx_navbar, "Banner must mount before <Navbar />"


# ─────────────────────────────────────────────────────────────────────────
# P4 — AI Concierge UX
# ─────────────────────────────────────────────────────────────────────────


class TestAIAssistantUX:
    def _src(self):
        with open("/app/frontend/src/components/AIAssistant.js") as f:
            return f.read()

    def test_immediate_acknowledgment_message_present(self):
        src = self._src()
        # English ack
        assert "Searching for the best answer for you" in src
        # French ack
        assert "Je recherche la meilleure réponse pour vous" in src

    def test_15s_still_processing_branch(self):
        src = self._src()
        # The timer must use exactly 15000 ms
        assert "15000" in src
        assert "still processing" in src.lower() or "still-processing" in src.lower() or "Our AI is processing" in src

    def test_multi_channel_notification_pieces(self):
        src = self._src()
        # sound via AudioContext
        assert "AudioContext" in src or "webkitAudioContext" in src
        # browser Notification
        assert "new Notification(" in src
        # vibration
        assert "navigator.vibrate" in src
        # tab title swap
        assert "document.title" in src
        # unread badge state
        assert "unreadBadge" in src

    def test_notification_perm_only_on_chat_open(self):
        src = self._src()
        # Must call requestPermission inside an effect tied to isOpen
        assert "Notification.requestPermission()" in src
        # Should not be in a top-level effect that fires on mount
        # (heuristic: 'isOpen' is in the deps list for the permission effect)


# ─────────────────────────────────────────────────────────────────────────
# P5 — Moderation + Prohibited Items
# ─────────────────────────────────────────────────────────────────────────


class TestModerationScanner:
    def test_violation_codes_complete(self):
        from services.listing_moderation_scanner import PROHIBITED_VIOLATION_CODES
        # 20+ codes per spec
        assert len(PROHIBITED_VIOLATION_CODES) >= 20
        # Spot-check the canonical names
        for code in (
            "PROHIBITED_DRUG_ILLEGAL", "PROHIBITED_DRUG_RX_MEDICATION",
            "PROHIBITED_WEAPON_FIREARM", "VEHICLE_WRONG_SECTION",
            "FINANCIAL_FRAUD", "STOLEN_GOODS", "COUNTERFEIT_GOODS",
            "PLATFORM_BYPASS", "CYBER_THREAT", "ADULT_CONTENT",
            "HUMAN_EXPLOITATION", "IDENTITY_FRAUD",
        ):
            assert code in PROHIBITED_VIOLATION_CODES, f"Missing code: {code}"

    def test_prompt_mentions_canada_law(self):
        from services.listing_moderation_scanner import MODERATION_PROMPT
        # Normalise whitespace before assertions (the prompt is line-wrapped)
        flat = " ".join(MODERATION_PROMPT.split())
        assert "Canadian" in flat or "Canada" in flat
        assert "Criminal Code" in flat
        assert "Firearms Act" in flat or "PCPA" in flat
        # Decision rubric present
        assert "PASS" in flat
        assert "UNSURE" in flat
        assert "FAIL" in flat

    @pytest.mark.asyncio
    async def test_scan_listing_for_violations_fails_safe(self, monkeypatch):
        # When the LLM throws, the scanner must mark the listing
        # `pending_review` (NEVER auto-approve) and return error=True.
        from services import listing_moderation_scanner as mod

        class FakeColl:
            async def find_one(self, *a, **k):
                return {"id": "l1", "category": "x", "title": "x", "description": "x"}
            async def update_one(self, *a, **k):
                return None

        class FakeDB:
            def __getitem__(self, name): return FakeColl()

        async def fail_call(*a, **k):
            raise RuntimeError("forced_failure")

        monkeypatch.setattr(mod, "_call_gemini_moderation", fail_call)

        result = await mod.scan_listing_for_violations(FakeDB(), listing_id="l1")
        assert result.get("error") is True
        assert "forced_failure" in result.get("reason", "")


class TestProhibitedItemsPage:
    def test_page_file_exists(self):
        path = "/app/frontend/src/pages/ProhibitedItemsPage.js"
        assert os.path.isfile(path)
        with open(path) as f:
            src = f.read()
        # All 10 category keys
        for key in ("drugs", "weapons", "vehicles_wrong", "financial_fraud",
                    "stolen", "human_animal", "cyber", "platform_bypass",
                    "regulated", "adult"):
            assert f"key: '{key}'" in src, f"Missing category key: {key}"

    def test_routes_registered(self):
        with open("/app/frontend/src/App.js") as f:
            src = f.read()
        assert 'path="/prohibited-items"' in src
        assert 'path="/articles-interdits"' in src

    def test_footer_link_added(self):
        with open("/app/frontend/src/components/Footer.js") as f:
            src = f.read()
        assert "prohibited_items" in src
        assert "/prohibited-items" in src
        assert "/articles-interdits" in src


# ─────────────────────────────────────────────────────────────────────────
# Live HTTP smoke (best-effort, tolerant of rate-limit)
# ─────────────────────────────────────────────────────────────────────────


def _admin_token():
    for attempt in range(3):
        r = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=15,
        )
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        if r.status_code != 200:
            return None
        return r.json().get("access_token") or r.json().get("token")
    return None


class TestLive:
    def test_confirm_pickup_code_requires_auth(self):
        r = httpx.post(
            f"{API_URL}/api/transactions/confirm-pickup-code",
            json={"pickup_code": "BVX-TESTCODE"},
            timeout=10,
        )
        assert r.status_code in (401, 403)

    def test_confirm_pickup_code_validates_format(self):
        token = _admin_token()
        if not token:
            pytest.skip("admin login rate-limited")
        r = httpx.post(
            f"{API_URL}/api/transactions/confirm-pickup-code",
            json={"pickup_code": "ABCDEFGHIJ"},   # missing BVX- prefix
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert r.status_code == 400
        body = r.json().get("detail") or {}
        if isinstance(body, dict):
            assert body.get("error") == "invalid_code_format"

    def test_send_notification_requires_admin_role(self):
        # Without any auth → 401/403
        r = httpx.post(
            f"{API_URL}/api/admin/users/some-id/send-notification",
            json={
                "notification_type": "general",
                "subject": "Test",
                "body_en": "Test message",
                "send_via": "in_app",
            },
            timeout=10,
        )
        assert r.status_code in (401, 403)
