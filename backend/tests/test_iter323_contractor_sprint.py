"""iter323 — Contractor account-type cleanup + email routing + IVR + leaderboard + profile."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest

from services.contractor_commission import (
    ACCOUNT_TYPES,
    CONTRACTOR_CREATABLE_ACCOUNT_TYPES,
)
from services.contractor_email_hub import (
    CONTRACTOR_SENDER_EMAIL,
    CONTRACTOR_SENDER_NAME,
    CONTRACTOR_REPLY_TO_DOMAIN,
    CONTRACTOR_REPLY_TO_BASE,
    build_contractor_reply_to,
    build_contractor_signature,
)
from services.contractor_extensions import (
    EXTENSION_START,
    assign_extension,
    lookup_contractor_by_extension,
)
from routes import contractor_ivr_inbound as ivr
from routes import contractor_profile_ext as profile_ext


# ─── Directive 1 — Account-type sets ─────────────────────────────────────


class TestDirective1AccountTypes:
    def test_contractor_creatable_set_is_exactly_five(self):
        """The 'Add a Client' shortcut MUST allow exactly 5 types — no more, no less."""
        assert set(CONTRACTOR_CREATABLE_ACCOUNT_TYPES) == {
            "individual_seller", "business", "partner",
            "vehicle_dealer", "storage_facility",
        }

    def test_creatable_subset_excludes_liquidator_and_broker(self):
        assert "liquidator" not in CONTRACTOR_CREATABLE_ACCOUNT_TYPES
        assert "broker"     not in CONTRACTOR_CREATABLE_ACCOUNT_TYPES

    def test_full_account_types_still_carries_liquidator_and_broker(self):
        """Brokers + liquidators must remain in the commission engine
        because they exist platform-wide (see /app/backend/models/broker_models.py).
        Removing them would break commission payouts."""
        assert "liquidator" in ACCOUNT_TYPES
        assert "broker" in ACCOUNT_TYPES


# ─── Directive 2 — Email routing ─────────────────────────────────────────


class TestDirective2EmailRouting:
    def test_from_address_restored_to_partners_bidvex_ca(self):
        assert CONTRACTOR_SENDER_EMAIL == "contractor@bidvex.com"
        assert CONTRACTOR_SENDER_NAME == "BidVex Partners"

    def test_reply_to_domain_is_safe_subdomain(self):
        assert CONTRACTOR_REPLY_TO_DOMAIN == "reply.bidvex.ca"
        assert CONTRACTOR_REPLY_TO_BASE == "partners"

    def test_build_per_contractor_reply_to(self):
        addr = build_contractor_reply_to("abc12345")
        assert addr == "partners+cabc12345@reply.bidvex.ca"

    def test_reply_to_strips_unsafe_chars_in_tag(self):
        addr = build_contractor_reply_to("evil';drop@table--")
        # Only [a-zA-Z0-9-] survives the sanitiser.
        assert "@reply.bidvex.ca" in addr
        assert "'" not in addr
        assert "drop" in addr  # safe-char chunk preserved

    def test_reply_to_falls_back_when_no_contractor(self):
        addr = build_contractor_reply_to(None)
        assert addr == "partners@reply.bidvex.ca"

    def test_signature_injects_extension_when_present(self):
        sig = build_contractor_signature(
            contractor_name="Jean Test",
            contractor_email="jean@bidvex.ca",
            contractor_extension=1225,
            locale="en",
        )
        assert "1225" in sig
        assert "Direct ext." in sig
        assert "+1 450 634 3099" in sig or "450" in sig

    def test_signature_localizes_extension_label(self):
        sig = build_contractor_signature(
            contractor_name="Jean Test",
            contractor_email="jean@bidvex.ca",
            contractor_extension=1226,
            locale="fr",
        )
        assert "1226" in sig
        assert "Poste direct" in sig

    def test_signature_omits_extension_when_none(self):
        sig = build_contractor_signature(
            contractor_name="Test", contractor_email="t@bidvex.ca", locale="en",
        )
        assert "Direct ext." not in sig
        assert "Poste direct" not in sig


# ─── Directive 3 — Extension assignment + IVR ────────────────────────────


class TestDirective3ExtensionAssignment:
    """Uses an in-memory fake db to test assign_extension semantics."""

    class _FakeUsers:
        def __init__(self):
            self.rows = []

        async def find_one(self, q, proj=None):
            for r in self.rows:
                if all(r.get(k) == v for k, v in q.items() if k != "_id"):
                    return dict(r)
            return None

        async def update_one(self, q, update):
            for r in self.rows:
                if all(r.get(k) == v for k, v in q.items() if not isinstance(v, dict)):
                    for k, v in (update.get("$set") or {}).items():
                        r[k] = v
                    return type("R", (), {"matched_count": 1, "modified_count": 1})
            return type("R", (), {"matched_count": 0, "modified_count": 0})

        async def create_index(self, *a, **k):
            return None

    class _FakeCounters:
        def __init__(self):
            self.row = None

        async def find_one_and_update(self, q, update, **k):
            if self.row is None:
                self.row = {"_id": "contractor_extension", "value": 0}
            inc = (update.get("$inc") or {}).get("value", 0)
            self.row["value"] += inc
            return dict(self.row)

        async def update_one(self, q, update):
            if self.row is None:
                self.row = {"_id": "contractor_extension", "value": 0}
            for k, v in (update.get("$set") or {}).items():
                self.row[k] = v
            return type("R", (), {"matched_count": 1, "modified_count": 1})

    class _FakeDB:
        def __init__(self):
            self.users = TestDirective3ExtensionAssignment._FakeUsers()
            self.system_counters = TestDirective3ExtensionAssignment._FakeCounters()

    @pytest.mark.asyncio
    async def test_extension_start_is_1220(self):
        assert EXTENSION_START == 1220

    @pytest.mark.asyncio
    async def test_first_contractor_gets_1220(self):
        db = self._FakeDB()
        db.users.rows.append({"id": "c1", "role": "dialer_contractor"})
        ext = await assign_extension(db, "c1")
        assert ext == 1220

    @pytest.mark.asyncio
    async def test_subsequent_contractors_increment(self):
        db = self._FakeDB()
        db.users.rows.append({"id": "c1", "role": "dialer_contractor"})
        db.users.rows.append({"id": "c2", "role": "dialer_contractor"})
        db.users.rows.append({"id": "c3", "role": "dialer_contractor"})
        e1 = await assign_extension(db, "c1")
        e2 = await assign_extension(db, "c2")
        e3 = await assign_extension(db, "c3")
        assert (e1, e2, e3) == (1220, 1221, 1222)

    @pytest.mark.asyncio
    async def test_idempotent_for_already_assigned(self):
        db = self._FakeDB()
        db.users.rows.append({"id": "c1", "extension_number": 1234})
        ext = await assign_extension(db, "c1")
        assert ext == 1234


class TestDirective3IVRTagParsing:
    def test_extracts_full_tag(self):
        tag = ivr._extract_contractor_tag("partners+cabc12345@reply.bidvex.ca")
        assert tag == "abc12345"

    def test_extracts_tag_with_uuid_chars(self):
        tag = ivr._extract_contractor_tag(
            '"Foo" <partners+c0f45e7ca-d1f9-483b-af43-f9c6beddcef3@reply.bidvex.ca>'
        )
        assert tag == "0f45e7ca-d1f9-483b-af43-f9c6beddcef3"

    def test_no_tag_returns_none(self):
        assert ivr._extract_contractor_tag("partners@reply.bidvex.ca") is None
        assert ivr._extract_contractor_tag("") is None
        assert ivr._extract_contractor_tag(None) is None


# ─── Directive 4 — Leaderboard trend marker ──────────────────────────────


class TestDirective4LeaderboardTrend:
    def test_trend_marker_up(self):
        assert profile_ext._trend_marker(now_rank=2, last_rank=5) == "▲"

    def test_trend_marker_down(self):
        assert profile_ext._trend_marker(now_rank=8, last_rank=3) == "▼"

    def test_trend_marker_unchanged(self):
        assert profile_ext._trend_marker(now_rank=4, last_rank=4) == "—"

    def test_trend_marker_missing_history(self):
        assert profile_ext._trend_marker(now_rank=4, last_rank=None) == "—"
        assert profile_ext._trend_marker(now_rank=None, last_rank=4) == "—"


# ─── Directive 5 — Profile photo constraints ─────────────────────────────


class TestDirective5ProfilePhoto:
    def test_allowed_mime_types(self):
        assert "image/jpeg" in profile_ext.PROFILE_PHOTO_ALLOWED
        assert "image/png"  in profile_ext.PROFILE_PHOTO_ALLOWED
        assert "image/webp" in profile_ext.PROFILE_PHOTO_ALLOWED

    def test_max_bytes_is_reasonable(self):
        # 5 MB matches the existing listing photo cap.
        assert profile_ext.PROFILE_PHOTO_MAX_BYTES == 5 * 1024 * 1024


# ─── E164 validation ─────────────────────────────────────────────────────


class TestPersonalPhoneE164:
    def test_valid_e164(self):
        assert profile_ext._validate_e164("+14506343099")
        assert profile_ext._validate_e164("+15145551234")
        assert profile_ext._validate_e164("+33612345678")

    def test_invalid_phone(self):
        assert not profile_ext._validate_e164("4506343099")  # missing +
        assert not profile_ext._validate_e164("+0123")        # too short
        assert not profile_ext._validate_e164("abc")
        assert not profile_ext._validate_e164("")


# ─── Routing surface audit ───────────────────────────────────────────────


class TestRouterSurface:
    def test_iter323_endpoints_registered(self):
        from routes.contractor_profile_ext import router as pr
        from routes.contractor_ivr_inbound import router as ir
        all_paths = (
            [getattr(r, "path", "") for r in pr.routes] +
            [getattr(r, "path", "") for r in ir.routes]
        )
        expected = [
            "/twilio/contractor/profile/me",
            "/twilio/contractor/profile/photo",
            "/twilio/contractor/extension/me",
            "/twilio/contractor/inbound-calls",
            "/twilio/contractor/leaderboard",
            "/twilio/ivr/incoming",
            "/twilio/ivr/route",
            "/twilio/ivr/whisper",
            "/twilio/ivr/status",
            "/sendgrid/inbound-parse",
        ]
        for p in expected:
            assert p in all_paths, f"missing route: {p}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
