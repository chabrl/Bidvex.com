"""
iter349 — Business-hours-aware bilingual IVR.

Verifies the time-based branch in `/api/twilio/ivr/main-menu`:
  - Mon-Fri 08:00 - 18:59 America/Toronto → interactive <Gather>
    with EN + FR bilingual "dial extension / press 1 support / press 0
    general inquiries" prompt.
  - All other times (weekend, weekday <08:00 or ≥19:00) → informational
    bilingual <Say> + <Hangup>. No keypress prompted.

Also verifies that `/api/twilio/handle-menu` treats both `1` AND `0` as
support-line routes (`+15149490038`), and that 4-digit extensions still
dial the contractor as before (iter347 regression).
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path("/app/backend")))
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

os.environ["TWILIO_SKIP_SIGNATURE_VERIFY"] = "1"

from pymongo import MongoClient
from zoneinfo import ZoneInfo


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


API = _api_base() + "/api"
MTL = ZoneInfo("America/Toronto")


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


# ─── Unit tests: is_business_hours_now with mocked time ─────────────────

class TestBusinessHoursCheck:

    def test_wednesday_noon_is_business_hours(self, monkeypatch):
        import routes.contractor_ivr_inbound as mod
        # 2026-02-11 (a Wednesday) 12:00 Montreal → business hours.
        monkeypatch.setattr(
            mod, "_current_montreal_time",
            lambda: datetime(2026, 2, 11, 12, 0, 0, tzinfo=MTL),
        )
        assert mod.is_business_hours_now() is True

    def test_monday_0800_is_business_hours_edge(self, monkeypatch):
        import routes.contractor_ivr_inbound as mod
        # 08:00 exactly is the lower edge — must be True.
        monkeypatch.setattr(
            mod, "_current_montreal_time",
            lambda: datetime(2026, 2, 9, 8, 0, 0, tzinfo=MTL),  # Monday
        )
        assert mod.is_business_hours_now() is True

    def test_friday_1859_is_business_hours(self, monkeypatch):
        import routes.contractor_ivr_inbound as mod
        # 18:59 is inside the window.
        monkeypatch.setattr(
            mod, "_current_montreal_time",
            lambda: datetime(2026, 2, 13, 18, 59, 0, tzinfo=MTL),
        )
        assert mod.is_business_hours_now() is True

    def test_friday_1900_is_after_hours_edge(self, monkeypatch):
        import routes.contractor_ivr_inbound as mod
        # 19:00 exactly is the upper edge — must be False (< 19).
        monkeypatch.setattr(
            mod, "_current_montreal_time",
            lambda: datetime(2026, 2, 13, 19, 0, 0, tzinfo=MTL),
        )
        assert mod.is_business_hours_now() is False

    def test_monday_0759_is_after_hours(self, monkeypatch):
        import routes.contractor_ivr_inbound as mod
        monkeypatch.setattr(
            mod, "_current_montreal_time",
            lambda: datetime(2026, 2, 9, 7, 59, 0, tzinfo=MTL),
        )
        assert mod.is_business_hours_now() is False

    def test_saturday_noon_is_after_hours(self, monkeypatch):
        import routes.contractor_ivr_inbound as mod
        monkeypatch.setattr(
            mod, "_current_montreal_time",
            lambda: datetime(2026, 2, 14, 12, 0, 0, tzinfo=MTL),  # Saturday
        )
        assert mod.is_business_hours_now() is False

    def test_sunday_all_day_after_hours(self, monkeypatch):
        import routes.contractor_ivr_inbound as mod
        for hour in (10, 12, 15, 18):
            monkeypatch.setattr(
                mod, "_current_montreal_time",
                lambda h=hour: datetime(2026, 2, 15, h, 0, 0, tzinfo=MTL),  # Sunday
            )
            assert mod.is_business_hours_now() is False, f"Sunday {hour}:00 should be after-hours"


# ─── Server integration: force server-side time via HTTP header trick ──
#
# The FastAPI process runs in its own timezone context; we can't monkey-
# patch its `_current_montreal_time` from a remote HTTP call. Instead
# we verify BOTH branches by leveraging the current wall-clock:
# whichever branch is active RIGHT NOW is verifiable end-to-end.
# The unit tests above give us deterministic coverage of both branches.

def _current_branch_is_business() -> bool:
    """Return the live server-side business-hours branch by inspecting
    the wall-clock in Montreal. Tests below dispatch to the appropriate
    assertion set based on this value."""
    from routes.contractor_ivr_inbound import is_business_hours_now
    return is_business_hours_now()


class TestLiveIVRBranch:
    """End-to-end integration against the actual preview URL. Only the
    branch active at test time is asserted here; the other branch has
    dedicated unit-test coverage above."""

    def test_live_branch_returns_expected_twiml(self, db):
        call_sid = f"iter349-CA-{uuid.uuid4().hex[:12]}"
        try:
            r = requests.post(
                f"{API}/twilio/ivr/main-menu",
                data={
                    "CallSid": call_sid,
                    "From":    "+15145559999",
                    "To":      "+14506343099",
                },
                timeout=30,
            )
            assert r.status_code == 200
            body = r.content.decode("utf-8")

            row = db.inbound_extension_calls.find_one({"call_sid": call_sid})
            assert row is not None, "call row not persisted"
            assert row.get("menu_variant") == "iter349_time_aware"
            assert "business_hours" in row
            assert isinstance(row["business_hours"], bool)
            assert row.get("montreal_time")
            assert row.get("montreal_weekday") in (
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            )

            live_business = _current_branch_is_business()
            if live_business:
                # Business hours branch — interactive Gather.
                assert "<Gather" in body
                assert "<Hangup" not in body
                # New EN + FR strings from iter349.
                assert "Hello, thank you for calling BidVex" in body
                assert "Bonjour, merci d'avoir appelé BidVex" in body
                # Press 0 / press 1 prompts.
                assert "press 1 for support" in body.lower()
                assert "press 0 for general" in body.lower()
                assert "appuyez sur 1 pour le support" in body.lower()
                assert "appuyez sur 0 pour les demandes générales" in body.lower()
            else:
                # After-hours branch — informational + hangup.
                assert "<Gather" not in body
                assert "<Hangup" in body
                # No keypress options offered.
                assert "press 1" not in body.lower()
                assert "press 0" not in body.lower()
                # Bilingual after-hours strings.
                assert "office is currently closed" in body.lower()
                assert "monday to friday" in body.lower()
                assert "8:00 am to 7:00 pm" in body.lower()
                assert "nos bureaux sont actuellement fermés" in body.lower() or \
                       "nos bureaux sont actuellement fermes" in body.lower()
                assert "lundi au vendredi" in body.lower()
                assert "8h00 à 19h00" in body.lower() or "8h00 a 19h00" in body.lower()
                # Row must reflect the after-hours outcome.
                row2 = db.inbound_extension_calls.find_one({"call_sid": call_sid})
                assert row2.get("outcome") == "after_hours_hangup"
                assert row2.get("status") == "ended_after_hours"
        finally:
            db.inbound_extension_calls.delete_many({"call_sid": call_sid})


class TestHandleMenuZeroAndOne:
    """iter349 — handle-menu accepts BOTH 0 (general) and 1 (support)."""

    def test_press_0_dials_support(self):
        r = requests.post(
            f"{API}/twilio/handle-menu",
            data={
                "CallSid": f"iter349-CA-{uuid.uuid4().hex[:12]}",
                "Digits":  "0",
                "From":    "+15145559999",
            },
            timeout=30,
        )
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "+15149490038" in body, f"support number not in TwiML: {body[:300]}"
        assert "<Dial" in body
        # Greeting mentions "general inquiries" for the 0 branch.
        assert "general inquiries" in body.lower()

    def test_press_1_still_dials_support(self):
        r = requests.post(
            f"{API}/twilio/handle-menu",
            data={
                "CallSid": f"iter349-CA-{uuid.uuid4().hex[:12]}",
                "Digits":  "1",
                "From":    "+15145559999",
            },
            timeout=30,
        )
        assert r.status_code == 200
        body = r.content.decode("utf-8")
        assert "+15149490038" in body
        assert "<Dial" in body
        # Greeting for the 1 branch specifically says "support team".
        assert "support team" in body.lower()

    def test_valid_extension_still_dials_contractor(self, db):
        """iter347 regression — 4-digit contractor path unchanged."""
        ext = 5432
        contractor_id = str(uuid.uuid4())
        db.users.delete_many({"extension_number": ext, "role": "dialer_contractor"})
        db.users.insert_one({
            "id":                    contractor_id,
            "email":                 f"iter349_c_{contractor_id[:8]}@test.com",
            "name":                  "Iter349 Contractor",
            "role":                  "dialer_contractor",
            "extension_number":      ext,
            "personal_phone_number": "+15145558877",
            "is_active":             True,
            "created_at":            datetime.now(dt_timezone.utc).isoformat(),
        })
        try:
            r = requests.post(
                f"{API}/twilio/handle-menu",
                data={
                    "CallSid": f"iter349-CA-{uuid.uuid4().hex[:12]}",
                    "Digits":  str(ext),
                    "From":    "+15145559999",
                },
                timeout=30,
            )
            assert r.status_code == 200
            body = r.content.decode("utf-8")
            assert "+15145558877" in body, f"contractor personal_phone missing: {body[:400]}"
            assert 'callerId="+14506343099"' in body
        finally:
            db.users.delete_one({"id": contractor_id})
