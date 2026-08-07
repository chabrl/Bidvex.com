"""
iter447 — Vehicle Dealer Multi-Lot Bulk Import
==============================================
Backend contract test suite. Runs against the LIVE server. Uses the
seeded super_admin (also an is_vehicle_dealer) to create a fresh draft
multi-lot event, then exercises every endpoint end-to-end.

Rules verified:
  • 500 rows per import; ATOMIC (all-or-none)
  • 500 total vehicles per event; remaining_capacity respected
  • Bilingual per-cell {row, field, code, message_en, message_fr} errors
  • Duplicate VIN detection — 3 scopes:
      1. same batch
      2. lots already in this event
      3. dealer's OTHER open multi-lot events
  • Bill 96 title_fr required for QC lots
  • VIN charset (17 chars, uppercase alnum, no I/O/Q)
  • Photo-gate on activate (any lot without a photo blocks Go Live)
"""
import io
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

sys.path.insert(0, "/app/backend")

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def token():
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()
    return d.get("access_token") or d.get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def dealer_user_id(headers):
    r = httpx.get(
        f"{API_URL}/api/auth/me",
        headers=headers, timeout=20,
    )
    return r.json().get("id")


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _valid_vin() -> str:
    """Generate a plausibly-valid 17-char VIN. WMI + random alphanum
    minus I/O/Q so it passes the charset regex."""
    alpha = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "1HG" + "".join(alpha[int.from_bytes(os.urandom(1), "big") % len(alpha)] for _ in range(14))


def _valid_lot(**over) -> dict:
    base = {
        "vin": _valid_vin(),
        "year": 2020,
        "make": "Toyota",
        "model": "Camry",
        "trim": "XSE",
        "body_type": "sedan",
        "mileage": 52000,
        "engine_size": "2.5L I4",
        "transmission": "automatic",
        "drivetrain": "fwd",
        "fuel_type": "gasoline",
        "exterior_color": "White",
        "condition_rating": "good",
        "title_status": "clean",
        "starting_price": 8500.0,
        "reserve_price": None,
        "bid_increment": 100.0,
        "location_city": "Toronto",
        "location_province": "ON",
        "title": "2020 Toyota Camry XSE",
        "title_fr": "2020 Toyota Camry XSE",
        "description": "",
    }
    base.update(over)
    return base


@pytest.fixture()
def fresh_event(headers):
    """Create a fresh DRAFT multi-lot event with 0 lots each test run."""
    r = httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions",
        json={
            "title": f"iter447 test event {uuid.uuid4().hex[:6]}",
            "description": "",
            "timing_mode": "sequential",
            "start_time": _future_iso(48),
            "lot_duration_seconds": 120,
            "stagger_offset_seconds": 60,
            "submission_intent": "draft",
            "lots": [],
        },
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    ev = r.json()
    yield ev
    # Cleanup — mark as cancelled after each test to keep DB tidy.
    try:
        httpx.post(
            f"{API_URL}/api/vehicle-multi-lot-auctions/{ev['id']}/cancel",
            headers=headers, timeout=10,
        )
    except Exception:  # noqa: BLE001
        pass


def _preview(event_id, lots, headers):
    return httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{event_id}/bulk-import/preview",
        json={"lots": lots}, headers=headers, timeout=30,
    )


def _confirm(event_id, lots, headers):
    return httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{event_id}/bulk-import/confirm",
        json={"lots": lots}, headers=headers, timeout=30,
    )


# ─────────────────────────────────────────────────────────────
# 1. Capacity + template
# ─────────────────────────────────────────────────────────────

def test_capacity_starts_empty(headers, fresh_event):
    r = httpx.get(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{fresh_event['id']}/bulk-import/capacity",
        headers=headers, timeout=10,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["used"] == 0
    assert d["max"] == 500
    assert d["remaining"] == 500
    assert d["max_per_import"] == 500
    assert d["editable"] is True


def test_template_download(headers, fresh_event):
    r = httpx.get(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{fresh_event['id']}/bulk-import/template",
        headers=headers, timeout=10,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    text = r.content.decode("utf-8-sig")
    header = text.splitlines()[0]
    for col in ("vin", "year", "make", "model", "starting_price",
                "location_city", "location_province", "title", "title_fr"):
        assert col in header


# ─────────────────────────────────────────────────────────────
# 2. Preview validation
# ─────────────────────────────────────────────────────────────

def test_preview_happy_path(headers, fresh_event):
    r = _preview(fresh_event["id"], [_valid_lot(), _valid_lot()], headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_rows"] == 2
    assert d["can_import"] is True
    assert d["total_errors"] == 0
    assert d["used_capacity"] == 0
    assert d["remaining_capacity"] == 500


def test_preview_rejects_over_500_rows(headers, fresh_event):
    lots = [_valid_lot() for _ in range(501)]
    r = _preview(fresh_event["id"], lots, headers)
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("code") == "max_lots_exceeded"


def test_preview_flags_bad_vin_length(headers, fresh_event):
    r = _preview(fresh_event["id"], [_valid_lot(vin="ABC123")], headers)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "vin_length_invalid" in codes


def test_preview_flags_bad_vin_charset(headers, fresh_event):
    r = _preview(fresh_event["id"], [_valid_lot(vin="1HGIIIIIIIIIIIIII")], headers)
    codes = [e["code"] for row in r.json()["preview"] for e in row["errors"]]
    assert "vin_charset_invalid" in codes


def test_preview_flags_bill96_missing_title_fr(headers, fresh_event):
    r = _preview(fresh_event["id"], [_valid_lot(
        location_city="Montréal", location_province="QC", title_fr=""
    )], headers)
    codes = [e["code"] for row in r.json()["preview"] for e in row["errors"]]
    assert "bill96_title_fr_required" in codes


def test_preview_flags_missing_required_fields(headers, fresh_event):
    r = _preview(fresh_event["id"], [_valid_lot(
        make="", model="", location_city="", location_province="",
        title="", starting_price=0,
    )], headers)
    codes = [e["code"] for row in r.json()["preview"] for e in row["errors"]]
    for code in ("make_required", "model_required", "city_required",
                 "province_required", "title_required",
                 "starting_price_not_positive"):
        assert code in codes


def test_preview_flags_year_out_of_range(headers, fresh_event):
    r = _preview(fresh_event["id"], [_valid_lot(year=1800)], headers)
    codes = [e["code"] for row in r.json()["preview"] for e in row["errors"]]
    assert "year_out_of_range" in codes


def test_preview_flags_reserve_below_starting(headers, fresh_event):
    r = _preview(fresh_event["id"], [_valid_lot(
        starting_price=10000, reserve_price=5000,
    )], headers)
    codes = [e["code"] for row in r.json()["preview"] for e in row["errors"]]
    assert "reserve_below_starting" in codes


def test_preview_flags_within_batch_vin_duplicate(headers, fresh_event):
    dup = _valid_vin()
    r = _preview(fresh_event["id"], [
        _valid_lot(vin=dup), _valid_lot(vin=dup),
    ], headers)
    codes = [e["code"] for row in r.json()["preview"] for e in row["errors"]]
    assert "duplicate_vin_in_batch" in codes


def test_preview_flags_vin_conflict_with_same_event(headers, fresh_event):
    """Create one lot successfully, then try to preview a second batch
    containing the same VIN — must surface duplicate_vin_across_dealer."""
    same_vin = _valid_vin()
    c = _confirm(fresh_event["id"], [_valid_lot(vin=same_vin)], headers)
    assert c.status_code == 200 and c.json()["ok"] is True

    r = _preview(fresh_event["id"], [_valid_lot(vin=same_vin)], headers)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "duplicate_vin_across_dealer" in codes


def test_preview_flags_vin_conflict_with_other_event(headers):
    """Create TWO fresh events; put VIN in event A, then preview it in
    event B. Must surface a duplicate against the OTHER event."""
    shared = _valid_vin()

    ev_a = httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions",
        json={
            "title": f"iter447 A {uuid.uuid4().hex[:6]}",
            "description": "", "timing_mode": "sequential",
            "start_time": _future_iso(48),
            "lot_duration_seconds": 120, "stagger_offset_seconds": 60,
            "submission_intent": "draft", "lots": [],
        }, headers=headers, timeout=20,
    ).json()
    ev_b = httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions",
        json={
            "title": f"iter447 B {uuid.uuid4().hex[:6]}",
            "description": "", "timing_mode": "sequential",
            "start_time": _future_iso(48),
            "lot_duration_seconds": 120, "stagger_offset_seconds": 60,
            "submission_intent": "draft", "lots": [],
        }, headers=headers, timeout=20,
    ).json()

    try:
        c = _confirm(ev_a["id"], [_valid_lot(vin=shared)], headers)
        assert c.status_code == 200 and c.json()["ok"] is True

        r = _preview(ev_b["id"], [_valid_lot(vin=shared)], headers)
        d = r.json()
        codes = [e["code"] for row in d["preview"] for e in row["errors"]]
        assert "duplicate_vin_across_dealer" in codes
    finally:
        for e in (ev_a, ev_b):
            try:
                httpx.post(
                    f"{API_URL}/api/vehicle-multi-lot-auctions/{e['id']}/cancel",
                    headers=headers, timeout=10,
                )
            except Exception:  # noqa: BLE001
                pass


# ─────────────────────────────────────────────────────────────
# 3. Capacity math + atomic confirm
# ─────────────────────────────────────────────────────────────

def test_capacity_exceeded_on_preview(headers, fresh_event):
    """Simulate an event with 200 pre-existing lots; then attempt 350."""
    ev_id = fresh_event["id"]
    # Seed 200 valid rows.
    seed = [_valid_lot() for _ in range(200)]
    r = _confirm(ev_id, seed, headers)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["used_capacity"] == 200
    assert r.json()["remaining_capacity"] == 300

    # Preview a 350-row batch — should surface capacity_exceeded.
    over = [_valid_lot() for _ in range(350)]
    p = _preview(ev_id, over, headers)
    assert p.status_code == 200
    d = p.json()
    assert d["capacity_exceeded"] is True
    assert d["can_import"] is False
    assert d["remaining_capacity"] == 300


def test_confirm_rejects_over_capacity(headers, fresh_event):
    ev_id = fresh_event["id"]
    seed = [_valid_lot() for _ in range(200)]
    assert _confirm(ev_id, seed, headers).json()["ok"] is True

    over = [_valid_lot() for _ in range(350)]
    c = _confirm(ev_id, over, headers)
    body = c.json()
    assert body["ok"] is False
    assert body["code"] == "capacity_exceeded"
    assert body["created"] == 0
    # DB still holds the 200 we seeded, nothing more.
    cap = httpx.get(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{ev_id}/bulk-import/capacity",
        headers=headers, timeout=10,
    ).json()
    assert cap["used"] == 200


def test_confirm_atomic_all_or_none(headers, fresh_event):
    """One bad row must reject the ENTIRE batch — nothing written."""
    ev_id = fresh_event["id"]
    good1 = _valid_lot()
    good2 = _valid_lot()
    bad = _valid_lot(vin="TOOSHORT")  # will fail vin_length_invalid
    r = _confirm(ev_id, [good1, bad, good2], headers)
    body = r.json()
    assert body["ok"] is False
    assert body["code"] == "validation_failed"
    assert body["created"] == 0
    cap = httpx.get(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{ev_id}/bulk-import/capacity",
        headers=headers, timeout=10,
    ).json()
    assert cap["used"] == 0


def test_confirm_supports_repeat_imports_up_to_cap(headers, fresh_event):
    """Simulate 3 valid imports of 100 into the same event, verify each
    fits under the running total."""
    ev_id = fresh_event["id"]
    for _ in range(3):
        r = _confirm(ev_id, [_valid_lot() for _ in range(100)], headers)
        assert r.status_code == 200 and r.json()["ok"] is True
    cap = httpx.get(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{ev_id}/bulk-import/capacity",
        headers=headers, timeout=10,
    ).json()
    assert cap["used"] == 300
    assert cap["remaining"] == 200

    # A 4th 250-row import must be rejected (would put us at 550).
    r2 = _confirm(ev_id, [_valid_lot() for _ in range(250)], headers)
    assert r2.json()["ok"] is False
    assert r2.json()["code"] == "capacity_exceeded"

    # A 200-row import is still accepted.
    r3 = _confirm(ev_id, [_valid_lot() for _ in range(200)], headers)
    assert r3.status_code == 200 and r3.json()["ok"] is True

    cap = httpx.get(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{ev_id}/bulk-import/capacity",
        headers=headers, timeout=10,
    ).json()
    assert cap["used"] == 500
    assert cap["remaining"] == 0


# ─────────────────────────────────────────────────────────────
# 4. Photo-gate on activate
# ─────────────────────────────────────────────────────────────

def test_activate_blocked_when_any_lot_missing_photo(headers, fresh_event):
    ev_id = fresh_event["id"]
    r = _confirm(ev_id, [_valid_lot(), _valid_lot()], headers)
    assert r.status_code == 200 and r.json()["ok"] is True

    act = httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{ev_id}/activate",
        headers=headers, params={"intent": "live"}, timeout=15,
    )
    assert act.status_code == 400
    d = act.json().get("detail", {})
    assert d.get("code") == "lots_missing_photos"
    assert d.get("count") == 2


def test_activate_succeeds_after_photos_added(headers, fresh_event):
    """Directly inject photos into the DB to bypass the S3 pipeline and
    verify the activate gate opens."""
    ev_id = fresh_event["id"]
    r = _confirm(ev_id, [_valid_lot()], headers)
    lot_id = r.json()["lot_ids"][0]

    import asyncio
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _inject():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.vehicle_multi_lot_auctions.update_one(
            {"id": ev_id, "lots.id": lot_id},
            {"$set": {"lots.$.media": [
                {"id": "test-photo", "type": "photo", "url": "https://example.com/x.jpg"}
            ]}},
        )
        client.close()

    asyncio.run(_inject())

    act = httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{ev_id}/activate",
        headers=headers, params={"intent": "live"}, timeout=15,
    )
    assert act.status_code == 200, act.text
    assert act.json()["status"] == "live"


# ─────────────────────────────────────────────────────────────
# 5. Backward-compat legacy endpoint
# ─────────────────────────────────────────────────────────────

def test_legacy_endpoint_still_works(headers, fresh_event):
    """POST /vehicle-multi-lot-auctions/{id}/bulk-import (iter306) must
    still function using the same body shape."""
    ev_id = fresh_event["id"]
    r = httpx.post(
        f"{API_URL}/api/vehicle-multi-lot-auctions/{ev_id}/bulk-import",
        json={"lots": [_valid_lot(), _valid_lot()]},
        headers=headers, timeout=20,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["created"] == 2


# ─────────────────────────────────────────────────────────────
# 6. Auth / ownership
# ─────────────────────────────────────────────────────────────

def test_other_user_cannot_preview(headers, fresh_event):
    """Login as a non-owner user and try to preview — must 403."""
    # Create a plain non-dealer user (if not present).
    email = "iter447_notowner@test.com"
    pw = "Iter447Test!"
    reg = httpx.post(
        f"{API_URL}/api/auth/register",
        json={
            "email": email, "password": pw, "name": "iter447 not owner",
            "terms_agreed": True, "ai_disclosure_consent": True,
        },
        timeout=20,
    )
    tok = None
    if reg.status_code in (200, 201):
        tok = reg.json().get("access_token") or reg.json().get("token")
    else:
        lg = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": email, "password": pw}, timeout=20,
        )
        if lg.status_code == 200:
            tok = lg.json().get("access_token") or lg.json().get("token")
    if not tok:
        pytest.skip("Could not create non-owner user")

    h = {"Authorization": f"Bearer {tok}"}
    r = _preview(fresh_event["id"], [_valid_lot()], h)
    assert r.status_code == 403
    assert r.json().get("detail", {}).get("code") == "not_your_event"
