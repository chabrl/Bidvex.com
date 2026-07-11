"""
iter342 SPRINT — Tests for:
  P0  Vehicle gate false positives (Alex's listings: multi-lot clearance +
      glass cylinder vase) & "Ninja" context rules
  P0  Typed block-reason enum (BLOCK_MESSAGES) + 403 payload
  P0  Universal admin block notifications (office@bidvex.com, 6h dedup)
  P1  Careers general application endpoint + notification routing
  P1  Email address updates (contractor FROM, careers inbox, Contact page)
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

from services.vehicle_listing_guard import is_vehicle_listing
from services.block_messages import BLOCK_MESSAGES, BLOCK_REASONS, get_block_message


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE = _api_base()
API = BASE + "/api"

ALEX_TITLE = "Absolute Multi-Lot Clearance: Bicycles, Furniture & Extra Goods"
ALEX_VASE = "Large Clear Glass Cylinder Floor Vase with Decorative Bamboo & Wavy Brown Accents"


# ═══ ITEM 2 — Vehicle gate false positives ══════════════════════════════

class TestVehicleGateFalsePositives:
    def test_alex_multi_lot_clearance_not_flagged(self):
        flagged, signals, strength = is_vehicle_listing(None, ALEX_TITLE, None)
        assert flagged is False, f"signals={signals} strength={strength}"

    def test_alex_multi_lot_with_household_description_not_flagged(self):
        desc = ("Estate clearance in Ontario. Includes a Ninja blender, patio "
                "furniture, interior decor and extra household goods.")
        flagged, signals, strength = is_vehicle_listing(None, ALEX_TITLE, desc)
        assert flagged is False, f"signals={signals} strength={strength}"

    def test_alex_cylinder_vase_not_flagged(self):
        """iter342 root cause — 'cylinder' alone must NOT auto-flag."""
        flagged, signals, strength = is_vehicle_listing(None, ALEX_VASE, None)
        assert flagged is False, f"signals={signals} strength={strength}"

    def test_ninja_blender_not_flagged(self):
        flagged, signals, _ = is_vehicle_listing(
            None, "Ninja blender", "Kitchen countertop blender, 1200W, like new.")
        assert flagged is False, f"signals={signals}"

    def test_ninja_motorcycle_2019_flagged(self):
        flagged, signals, _ = is_vehicle_listing(None, "Ninja motorcycle 2019", None)
        assert flagged is True, f"signals={signals}"

    def test_kawasaki_ninja_with_year_flagged(self):
        flagged, signals, _ = is_vehicle_listing(None, "2019 Kawasaki Ninja 650", None)
        assert flagged is True, f"signals={signals}"

    def test_hydraulic_cylinder_not_flagged(self):
        flagged, signals, _ = is_vehicle_listing(
            None, "Hydraulic cylinder replacement part", None)
        assert flagged is False, f"signals={signals}"

    def test_numeric_engine_cylinder_still_flags(self):
        flagged, signals, _ = is_vehicle_listing(
            None, "2018 sedan, 4-cylinder engine, great condition", None)
        assert flagged is True, f"signals={signals}"

    def test_iter338_regressions_still_pass(self):
        # Word-boundary cases fixed in iter338 must stay fixed
        cases_not_vehicle = [
            ("Fatbike seven peaks 17\" New in box", None),
            ("Antique furniture from Ontario estate", "Beautiful interior pieces"),
            ("Corsair RAM 32GB with i7 CPU", "Gaming PC parts"),
        ]
        for title, desc in cases_not_vehicle:
            flagged, signals, _ = is_vehicle_listing(None, title, desc)
            assert flagged is False, f"{title!r} flagged with {signals}"
        # Real vehicles still flag
        flagged, signals, _ = is_vehicle_listing(None, "2018 Honda Civic low mileage", None)
        assert flagged is True, f"signals={signals}"


# ═══ ITEM 4 — Typed block reasons ═══════════════════════════════════════

class TestBlockReasons:
    def test_enum_complete(self):
        assert set(BLOCK_REASONS) == {
            "vehicle_dealer_required", "prohibited_item",
            "ai_review_required", "false_positive_suspected",
        }
        for reason in BLOCK_REASONS:
            assert BLOCK_MESSAGES[reason]["en"]
            assert BLOCK_MESSAGES[reason]["fr"]

    def test_vehicle_message_mentions_dealer_licence(self):
        assert "dealer licence" in BLOCK_MESSAGES["vehicle_dealer_required"]["en"]
        assert "vehicles@bidvex.com" in BLOCK_MESSAGES["vehicle_dealer_required"]["en"]

    def test_prohibited_message_never_mentions_dealer(self):
        for reason in ("prohibited_item", "ai_review_required", "false_positive_suspected"):
            assert "dealer" not in BLOCK_MESSAGES[reason]["en"].lower(), reason
            assert "OMVIC" not in BLOCK_MESSAGES[reason]["en"], reason

    def test_get_block_message_localizes(self):
        assert get_block_message("prohibited_item", "fr").startswith("Cette annonce")
        assert get_block_message("prohibited_item", "en").startswith("This listing")

    def test_vehicle_gate_403_returns_typed_reason(self):
        """enforce_vehicle_dealer_gate must raise 403 with block_reason enum."""
        from fastapi import HTTPException
        from services.vehicle_listing_guard import enforce_vehicle_dealer_gate

        class _FakeCollection:
            async def find_one(self, *a, **k): return {"id": "u1", "email": "x@y.com"}
            async def insert_one(self, *a, **k): return None
            def find(self, *a, **k):
                class _C:
                    def limit(self, n): return self
                    def __aiter__(self): return self
                    async def __anext__(self): raise StopAsyncIteration
                return _C()

        class _FakeDB:
            def __getattr__(self, name): return _FakeCollection()

        class _FakeUser:
            id = "u1"

        with pytest.raises(HTTPException) as exc:
            asyncio.get_event_loop().run_until_complete(
                enforce_vehicle_dealer_gate(
                    _FakeDB(), _FakeUser(),
                    category="vehicles", title="2018 Honda Civic", description=None,
                )
            )
        detail = exc.value.detail
        assert exc.value.status_code == 403
        assert detail["block_reason"] == "vehicle_dealer_required"
        assert detail["error"] == "vehicle_listing_dealer_required"
        assert "message_en" in detail and "message_fr" in detail

    def test_moderation_scanner_sets_prohibited_block_reason(self):
        src = open("/app/backend/services/listing_moderation_scanner.py").read()
        assert '"block_reason"] = "prohibited_item"' in src
        assert '"block_reason"] = "ai_review_required"' in src
        assert "notify_admins_of_violation" in src


# ═══ ITEM 3 — Admin block notifications ═════════════════════════════════

class TestAdminBlockNotifications:
    def test_office_email_is_always_a_recipient(self):
        from services.compliance_notifier import OFFICE_NOTIFICATION_EMAIL, _admin_recipients

        assert OFFICE_NOTIFICATION_EMAIL == "office@bidvex.com"

        class _FakeUsers:
            def find(self, *a, **k):
                class _C:
                    def limit(self, n): return self
                    def __aiter__(self): return self
                    async def __anext__(self): raise StopAsyncIteration
                return _C()

        class _FakeDB:
            users = _FakeUsers()

        recipients = asyncio.get_event_loop().run_until_complete(
            _admin_recipients(_FakeDB()))
        assert "office@bidvex.com" in recipients

    def test_six_hour_dedup_blocks_duplicate_email(self):
        """Same seller + same title within 6h → in-app row written, email skipped."""
        from services import compliance_notifier as cn

        sent = {"count": 0}
        inserted = []

        class _AdminNotifs:
            async def find_one(self, *a, **k): return {"_id": "recent"}  # dedup hit
            async def insert_one(self, doc): inserted.append(doc)

        class _Users:
            async def find_one(self, *a, **k): return {"name": "Alex", "email": "a@b.com"}
            def find(self, *a, **k):
                class _C:
                    def limit(self, n): return self
                    def __aiter__(self): return self
                    async def __anext__(self): raise StopAsyncIteration
                return _C()

        class _FakeDB:
            admin_notifications = _AdminNotifs()
            users = _Users()

        async def _run():
            return await cn.notify_admins_of_violation(
                _FakeDB(), kind="blocked_prohibited_item",
                listing={"id": "l1", "title": "Test", "category": None, "seller_id": "s1"},
                signals=["PROHIBITED_WEAPON_FIREARM"],
                seller_email="a@b.com",
            )

        res = asyncio.get_event_loop().run_until_complete(_run())
        assert res["kind"] == "blocked_prohibited_item"
        assert len(inserted) == 1                    # in-app row always written
        assert sent["count"] == 0                    # no email dispatched

    def test_notification_email_has_action_links(self):
        src = open("/app/backend/services/compliance_notifier.py").read()
        assert "Approve &amp; Whitelist" in src
        assert "Confirm Block" in src
        assert "office@bidvex.com" in src

    def test_all_gates_wired_to_notifier(self):
        for f in ("vehicle_listing_guard.py", "vehicle_listing_scanner.py",
                  "safety_watchdog.py", "listing_moderation_scanner.py"):
            src = open(f"/app/backend/services/{f}").read()
            assert "notify_admins_of_violation" in src, f
        # storage path schedules the prohibited-items scan
        storage_src = open("/app/backend/routes/storage_auctions.py").read()
        assert "scan_listing_for_violations" in storage_src


# ═══ ITEM 5 — Careers notifications ═════════════════════════════════════

class TestCareersNotifications:
    def test_admin_notification_routes_to_careers_inbox(self):
        from services.careers_notifications import _admin_notification_email
        os.environ.pop("CAREERS_NOTIFICATION_EMAIL", None)
        assert _admin_notification_email() == "careers@bidvex.com"

    def test_admin_subject_format(self):
        src = open("/app/backend/services/careers_notifications.py").read()
        assert 'New Career Application — ' in src
        assert 'reply_to="careers@bidvex.com"' in src

    def test_general_apply_endpoint_live(self):
        payload = {
            "first_name": "Iter342", "last_name": "Test",
            "email": f"iter342-{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+15145550142", "position": "General Application",
            "message": "Automated sprint test — safe to ignore.", "locale": "en",
        }
        r = requests.post(f"{API}/careers/apply", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["success"] is True
        assert body["applicant_id"]

    def test_general_apply_validates_email(self):
        r = requests.post(f"{API}/careers/apply", json={
            "first_name": "A", "last_name": "B", "email": "not-an-email",
            "phone": "+15145550142", "position": "X",
        }, timeout=30)
        assert r.status_code in (400, 422)


# ═══ ITEM 6 — Email address updates ═════════════════════════════════════

class TestEmailAddressUpdates:
    def test_contractor_hub_sends_from_contractor_address(self):
        from services.contractor_email_hub import CONTRACTOR_SENDER_EMAIL
        assert CONTRACTOR_SENDER_EMAIL == "contractor@bidvex.com"

    def test_no_legacy_addresses_in_backend(self):
        import subprocess
        out = subprocess.run(
            ["grep", "-rl", "-e", "support@bidvex.com", "-e", "info@bidvex.com",
             "-e", "partners@bidvex.ca",
             "--include=*.py", "/app/backend/routes", "/app/backend/services"],
            capture_output=True, text=True,
        )
        assert out.stdout.strip() == "", f"legacy addresses remain: {out.stdout}"

    def test_contact_page_lists_all_nine_addresses(self):
        src = open("/app/frontend/src/pages/ContactUsPage.jsx").read()
        for addr in ("office@bidvex.com", "service@bidvex.com", "vehicles@bidvex.com",
                     "broker@bidvex.com", "dispute@bidvex.com", "payment@bidvex.com",
                     "privacy@bidvex.com", "marketing@bidvex.com", "careers@bidvex.com"):
            assert addr in src, addr


# ═══ ITEM 7 — Twilio auth validation ════════════════════════════════════

class TestTwilioAuthValidation:
    def test_verify_twilio_auth_exists_and_returns_status(self):
        from services.twilio_service import verify_twilio_auth
        res = asyncio.get_event_loop().run_until_complete(verify_twilio_auth())
        assert "valid" in res and "error" in res

    def test_dialer_config_exposes_auth_fields(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": "charbel911@gmail.com",
                                "password": "Anderosli123!@#"}, timeout=30)
        assert r.status_code == 200
        token = r.json().get("access_token") or r.json().get("token")
        r2 = requests.get(f"{API}/twilio/config",
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r2.status_code == 200, r2.text[:200]
        body = r2.json()
        assert "auth_valid" in body
        assert "auth_error" in body
