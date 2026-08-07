"""
iter446 — Storage Facility CSV Bulk Import
==========================================
Backend contract test suite. Exercises every endpoint end-to-end against
the RUNNING server. Uses the seeded super_admin who owns the verified
"Bidvex Inc." storage facility in QC.

  1. GET  /api/storage-facilities/bulk-import/template
  2. POST /api/storage-facilities/bulk-import  (PREVIEW; no writes)
  3. POST /api/storage-facilities/bulk-import/confirm  (drafts)
  4. POST /api/storage-facilities/bulk-import/{id}/photos  (attach)
  5. POST /api/storage-facilities/bulk-import/{id}/publish  (photo-gated)
  6. POST /api/storage-facilities/bulk-import/publish-batch
  7. GET  /api/storage-facilities/bulk-import/pending

Behaviour under test:
  • 50-row cap enforced.
  • Duplicate unit_number blocked within-batch AND against facility's
    open auctions. Ended / cancelled auctions free the unit_number.
  • Bill 96 French description required for QC facility.
  • Lien unit requires past_due_balance > 0.
  • Deposit-required rows must carry deposit_amount + deposit_type.
  • start_time < end_time, end_time in future.
  • CSV does NOT accept `accepted_legal_notice`; must be actively
    accepted at the Confirm step; a spreadsheet value would be ignored.
  • Every draft is written with `buyer_premium_pct=5.0`, regardless of
    any client attempt to override.
  • Publish requires ≥ 1 photo.
"""
import csv
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


# CSV column order — MUST NOT include accepted_legal_notice.
CSV_COLUMNS = [
    "unit_number", "unit_size", "unit_type", "is_lien_unit",
    "past_due_balance", "description_en", "description_fr", "video_url",
    "starting_price", "reserve_price", "bid_increment", "start_time",
    "end_time", "cleanup_deadline_hours", "payment_method", "currency",
    "deposit_required", "deposit_amount", "deposit_type",
]


def _future_iso(days: int = 7) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _unique_unit(prefix: str = "T") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def _make_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for r in rows:
        w.writerow([r.get(c, "") for c in CSV_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")


def _valid_row(**overrides) -> dict:
    base = {
        "unit_number": _unique_unit("T"),
        "unit_size": "10x10",
        "unit_type": "indoor",
        "is_lien_unit": "N",
        "past_due_balance": "",
        "description_en": (
            "Household items — boxes, small appliances, furniture visible."
        ),
        # QC facility → description_fr required.
        "description_fr": (
            "Articles ménagers — boîtes, petits électroménagers visibles."
        ),
        "video_url": "",
        "starting_price": "50.00",
        "reserve_price": "",
        "bid_increment": "10",
        "start_time": _future_iso(1),
        "end_time": _future_iso(8),
        "cleanup_deadline_hours": "72",
        "payment_method": "stripe",
        "currency": "CAD",
        "deposit_required": "N",
        "deposit_amount": "",
        "deposit_type": "",
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────
# 1. Template download
# ─────────────────────────────────────────────────────────────

def test_template_download_is_bilingual_csv(headers):
    r = httpx.get(
        f"{API_URL}/api/storage-facilities/bulk-import/template",
        headers=headers,
        timeout=20,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    text = r.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    # Header + at least one example row.
    assert len(rows) >= 2
    assert rows[0] == CSV_COLUMNS
    # SECURITY: no accepted_legal_notice column in the template.
    assert "accepted_legal_notice" not in rows[0]
    # SECURITY: no buyer_premium column in the template.
    assert not any(
        "buyer_premium" in (c or "").lower() for c in rows[0]
    )


def test_template_requires_auth():
    r = httpx.get(
        f"{API_URL}/api/storage-facilities/bulk-import/template",
        timeout=20,
    )
    assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────
# 2. Preview validation
# ─────────────────────────────────────────────────────────────

def _preview(csv_bytes: bytes, headers):
    files = {"file": ("storage.csv", csv_bytes, "text/csv")}
    return httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import",
        headers=headers,
        files=files,
        timeout=30,
    )


def test_preview_happy_path(headers):
    csv_bytes = _make_csv([_valid_row(), _valid_row()])
    r = _preview(csv_bytes, headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_rows"] == 2
    assert d["can_import"] is True
    assert d["total_errors"] == 0


def test_preview_rejects_over_50_rows(headers):
    csv_bytes = _make_csv([_valid_row() for _ in range(51)])
    r = _preview(csv_bytes, headers)
    assert r.status_code == 400
    body = r.json()
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        assert detail.get("code") == "row_limit_exceeded"


def test_preview_flags_missing_required_columns(headers):
    # Drop unit_number column entirely.
    columns = [c for c in CSV_COLUMNS if c != "unit_number"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    w.writerow(["10x10"] + [""] * (len(columns) - 1))
    csv_bytes = buf.getvalue().encode("utf-8-sig")
    r = _preview(csv_bytes, headers)
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("code") == "missing_columns"


def test_preview_rejects_non_csv_type(headers):
    files = {"file": ("bogus.txt", b"not a csv", "text/plain")}
    r = httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import",
        headers=headers,
        files=files,
        timeout=15,
    )
    assert r.status_code == 400
    assert r.json().get("detail", {}).get("code") == "invalid_file_type"


def test_preview_flags_within_batch_duplicate_unit_number(headers):
    dup_unit = _unique_unit("DUP")
    csv_bytes = _make_csv([
        _valid_row(unit_number=dup_unit),
        _valid_row(unit_number=dup_unit),
    ])
    r = _preview(csv_bytes, headers)
    assert r.status_code == 200
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "duplicate_unit_in_batch" in codes


def test_preview_flags_bill96_missing_french_for_qc_facility(headers):
    row = _valid_row(description_fr="")
    csv_bytes = _make_csv([row])
    r = _preview(csv_bytes, headers)
    assert r.status_code == 200
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "bill96_description_fr_required" in codes


def test_preview_flags_invalid_unit_size_and_type(headers):
    csv_bytes = _make_csv([
        _valid_row(unit_size="99x99", unit_type="hovercraft"),
    ])
    r = _preview(csv_bytes, headers)
    assert r.status_code == 200
    codes = [
        e["code"] for row in r.json()["preview"] for e in row["errors"]
    ]
    assert "unit_size_invalid" in codes
    assert "unit_type_invalid" in codes


def test_preview_flags_lien_missing_past_due(headers):
    csv_bytes = _make_csv([
        _valid_row(is_lien_unit="Y", past_due_balance=""),
    ])
    r = _preview(csv_bytes, headers)
    codes = [
        e["code"] for row in r.json()["preview"] for e in row["errors"]
    ]
    assert "past_due_required_for_lien" in codes


def test_preview_flags_deposit_amount_missing_when_required(headers):
    csv_bytes = _make_csv([
        _valid_row(deposit_required="Y", deposit_amount="", deposit_type=""),
    ])
    r = _preview(csv_bytes, headers)
    codes = [
        e["code"] for row in r.json()["preview"] for e in row["errors"]
    ]
    assert "deposit_amount_required" in codes


def test_preview_flags_end_before_start(headers):
    csv_bytes = _make_csv([
        _valid_row(
            start_time=_future_iso(10),
            end_time=_future_iso(2),
        ),
    ])
    r = _preview(csv_bytes, headers)
    codes = [
        e["code"] for row in r.json()["preview"] for e in row["errors"]
    ]
    assert "end_before_start" in codes


def test_preview_flags_end_time_in_past(headers):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    csv_bytes = _make_csv([_valid_row(end_time=past)])
    r = _preview(csv_bytes, headers)
    codes = [
        e["code"] for row in r.json()["preview"] for e in row["errors"]
    ]
    # `end_before_start` OR `end_time_past` — both are correct behaviour.
    assert "end_time_past" in codes or "end_before_start" in codes


def test_preview_flags_reserve_below_starting(headers):
    csv_bytes = _make_csv([
        _valid_row(starting_price="500", reserve_price="100"),
    ])
    r = _preview(csv_bytes, headers)
    codes = [
        e["code"] for row in r.json()["preview"] for e in row["errors"]
    ]
    assert "reserve_below_starting" in codes


def test_preview_flags_invalid_payment_method_and_currency(headers):
    csv_bytes = _make_csv([
        _valid_row(payment_method="bitcoin", currency="EUR"),
    ])
    r = _preview(csv_bytes, headers)
    codes = [
        e["code"] for row in r.json()["preview"] for e in row["errors"]
    ]
    assert "payment_method_invalid" in codes
    assert "currency_invalid" in codes


# ─────────────────────────────────────────────────────────────
# 3. Confirm (drafts + legal notice)
# ─────────────────────────────────────────────────────────────

def _confirm(rows_norm: list[dict], accepted: bool, headers):
    return httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import/confirm",
        headers={**headers, "Content-Type": "application/json"},
        json={"rows": rows_norm, "accepted_legal_notice": accepted},
        timeout=30,
    )


def _normalize_for_confirm(preview_json) -> list[dict]:
    return [row["normalized"] for row in preview_json["preview"]]


def test_confirm_requires_active_legal_notice(headers):
    csv_bytes = _make_csv([_valid_row()])
    pv = _preview(csv_bytes, headers).json()
    r = _confirm(_normalize_for_confirm(pv), accepted=False, headers=headers)
    assert r.status_code == 400
    assert r.json().get("detail", {}).get("code") == "legal_notice_required"


def test_confirm_creates_drafts_and_stamps_5pct_bp(headers):
    csv_bytes = _make_csv([_valid_row()])
    pv = _preview(csv_bytes, headers).json()
    r = _confirm(_normalize_for_confirm(pv), accepted=True, headers=headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["created"] == 1
    draft = d["drafts"][0]
    assert draft["needs_photos"] is True
    assert draft["image_count"] == 0
    # Ensure the DB row was written as a draft with BP = 5 %.
    import asyncio
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _fetch():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        doc = await db.storage_auctions.find_one(
            {"id": draft["id"]},
            {"_id": 0}
        )
        client.close()
        return doc

    doc = asyncio.run(_fetch())
    assert doc is not None
    assert doc["status"] == "draft"
    assert doc["source"] == "csv_bulk_import"
    assert doc["buyer_premium_pct"] == 5.0
    assert doc.get("accepted_legal_notice") is True
    assert doc.get("accepted_legal_notice_source") == "bulk_import_wizard"


def test_confirm_ignores_attempted_bp_override(headers):
    """Even if a client somehow smuggles buyer_premium into the confirm
    payload, the server MUST stamp 5.0 on every draft. Pydantic drops
    unknown fields at parse time, but we verify the DB result anyway."""
    csv_bytes = _make_csv([_valid_row()])
    pv = _preview(csv_bytes, headers).json()
    rows = _normalize_for_confirm(pv)
    # Smuggle an override into every row.
    for r in rows:
        r["buyer_premium_pct"] = 0.0
        r["custom_buyer_premium_rate"] = 0.0

    resp = httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import/confirm",
        headers={**headers, "Content-Type": "application/json"},
        json={"rows": rows, "accepted_legal_notice": True},
        timeout=30,
    )
    assert resp.status_code == 200
    d = resp.json()
    draft_id = d["drafts"][0]["id"]

    import asyncio
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _fetch():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        doc = await db.storage_auctions.find_one({"id": draft_id}, {"_id": 0})
        client.close()
        return doc

    doc = asyncio.run(_fetch())
    assert doc is not None
    assert doc["buyer_premium_pct"] == 5.0  # locked


def test_confirm_blocks_duplicate_against_existing_open_draft(headers):
    """Second confirm using the SAME unit_number must be rejected because
    the first import produced a draft (which is an OPEN status)."""
    unit = _unique_unit("EXO")
    csv_bytes = _make_csv([_valid_row(unit_number=unit)])
    pv = _preview(csv_bytes, headers).json()
    first = _confirm(_normalize_for_confirm(pv), accepted=True, headers=headers)
    assert first.status_code == 200
    assert first.json()["ok"] is True

    # Second attempt with the same unit_number should surface a
    # duplicate_unit_in_facility error on preview.
    csv_bytes2 = _make_csv([_valid_row(unit_number=unit)])
    pv2 = _preview(csv_bytes2, headers).json()
    codes = [
        e["code"] for row in pv2["preview"] for e in row["errors"]
    ]
    assert "duplicate_unit_in_facility" in codes

    # And confirm must NOT create a second draft.
    second = _confirm(
        _normalize_for_confirm(pv2), accepted=True, headers=headers
    )
    assert second.status_code == 200
    assert second.json()["ok"] is False
    assert second.json()["created"] == 0


def test_ended_auction_frees_unit_number_for_reuse(headers):
    """A unit_number belonging to an ENDED auction is NOT considered a
    conflict — reuse must succeed."""
    unit = _unique_unit("REUSE")
    csv_bytes = _make_csv([_valid_row(unit_number=unit)])
    pv = _preview(csv_bytes, headers).json()
    r = _confirm(_normalize_for_confirm(pv), accepted=True, headers=headers)
    draft_id = r.json()["drafts"][0]["id"]

    # Force the first draft into `cancelled` (a non-open status).
    import asyncio
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _end():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.storage_auctions.update_one(
            {"id": draft_id},
            {"$set": {"status": "cancelled"}},
        )
        client.close()

    asyncio.run(_end())

    # Now reuse the same unit_number — should have no conflict error.
    csv_bytes2 = _make_csv([_valid_row(unit_number=unit)])
    pv2 = _preview(csv_bytes2, headers).json()
    codes = [
        e["code"] for row in pv2["preview"] for e in row["errors"]
    ]
    assert "duplicate_unit_in_facility" not in codes
    r2 = _confirm(
        _normalize_for_confirm(pv2), accepted=True, headers=headers
    )
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


# ─────────────────────────────────────────────────────────────
# 4. Photos + publish gate
# ─────────────────────────────────────────────────────────────

def test_publish_blocked_without_photo(headers):
    csv_bytes = _make_csv([_valid_row(unit_number=_unique_unit("NOPHOTO"))])
    pv = _preview(csv_bytes, headers).json()
    r = _confirm(_normalize_for_confirm(pv), accepted=True, headers=headers)
    draft_id = r.json()["drafts"][0]["id"]

    resp = httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import/{draft_id}/publish",
        headers=headers,
        timeout=15,
    )
    assert resp.status_code == 400
    assert resp.json().get("detail", {}).get("code") == "missing_photo"


def test_photos_attach_and_publish(headers):
    csv_bytes = _make_csv([_valid_row(unit_number=_unique_unit("PUB"))])
    pv = _preview(csv_bytes, headers).json()
    r = _confirm(_normalize_for_confirm(pv), accepted=True, headers=headers)
    draft_id = r.json()["drafts"][0]["id"]

    # Attach a fake URL — bulk import route doesn't hit S3.
    resp = httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import/{draft_id}/photos",
        headers={**headers, "Content-Type": "application/json"},
        json={"image_urls": ["https://example.com/unit.jpg"]},
        timeout=15,
    )
    assert resp.status_code == 200
    assert resp.json()["image_count"] == 1
    assert resp.json()["needs_photos"] is False

    # Now publish — should succeed and transition to active/upcoming.
    resp2 = httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import/{draft_id}/publish",
        headers=headers,
        timeout=15,
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] in ("active", "upcoming")


def test_publish_batch_reports_pending_photos(headers):
    # Two units — one with a photo, one without.
    u1 = _unique_unit("BATCH-A")
    u2 = _unique_unit("BATCH-B")
    csv_bytes = _make_csv([
        _valid_row(unit_number=u1),
        _valid_row(unit_number=u2),
    ])
    pv = _preview(csv_bytes, headers).json()
    r = _confirm(_normalize_for_confirm(pv), accepted=True, headers=headers)
    d1_id, d2_id = [d["id"] for d in r.json()["drafts"]]

    # Attach photo only to d1.
    httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import/{d1_id}/photos",
        headers={**headers, "Content-Type": "application/json"},
        json={"image_urls": ["https://example.com/x.jpg"]},
        timeout=15,
    )

    batch = httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import/publish-batch",
        headers=headers,
        timeout=20,
    )
    assert batch.status_code == 200
    body = batch.json()
    assert d1_id in body["published_ids"]
    # d2 should be in pending_photos.
    pending_ids = [p["id"] for p in body["pending_photos"]]
    assert d2_id in pending_ids


def test_pending_endpoint_lists_drafts(headers):
    csv_bytes = _make_csv([_valid_row(unit_number=_unique_unit("PEND"))])
    pv = _preview(csv_bytes, headers).json()
    _confirm(_normalize_for_confirm(pv), accepted=True, headers=headers)

    r = httpx.get(
        f"{API_URL}/api/storage-facilities/bulk-import/pending",
        headers=headers,
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert any(d.get("needs_photos") for d in body["drafts"])


# ─────────────────────────────────────────────────────────────
# 5. Auth gate (non-facility user)
# ─────────────────────────────────────────────────────────────

def test_endpoints_reject_non_facility_user():
    """A regular user (no verified facility profile) must get 403 on
    every bulk-import endpoint."""
    # Login as a plain test user (create if missing).
    reg = httpx.post(
        f"{API_URL}/api/auth/register",
        json={
            "email": "iter446_notfacility@test.com",
            "password": "Iter446Test!",
            "name": "iter446 non-facility",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        },
        timeout=20,
    )
    # 200 (created) or 400 (already exists) both fine.
    if reg.status_code in (200, 201):
        tok = reg.json().get("access_token") or reg.json().get("token")
    else:
        lg = httpx.post(
            f"{API_URL}/api/auth/login",
            json={
                "email": "iter446_notfacility@test.com",
                "password": "Iter446Test!",
            },
            timeout=20,
        )
        if lg.status_code != 200:
            pytest.skip("Could not create a non-facility test user")
        tok = lg.json().get("access_token") or lg.json().get("token")
    h = {"Authorization": f"Bearer {tok}"}

    r1 = httpx.get(
        f"{API_URL}/api/storage-facilities/bulk-import/template",
        headers=h, timeout=10,
    )
    assert r1.status_code == 403

    csv_bytes = _make_csv([_valid_row()])
    r2 = httpx.post(
        f"{API_URL}/api/storage-facilities/bulk-import",
        headers=h,
        files={"file": ("s.csv", csv_bytes, "text/csv")},
        timeout=15,
    )
    assert r2.status_code == 403
