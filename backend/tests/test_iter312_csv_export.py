"""
iter312 — Admin CSV Export endpoint
====================================

Streams a CSV of every listing matching the supplied filters via
`GET /api/admin/listings/export`. Re-uses the iter311 $unionWith
aggregation pipeline (minus pagination + facet) and writes
row-by-row using `StreamingResponse`, so memory pressure stays flat
even on multi-thousand-row exports.

These tests lock in:
  • Admin-only access (non-admin → 403).
  • Correct Content-Type + Content-Disposition headers + UTF-8 BOM.
  • Header row + CSV column order match the canonical column list.
  • Filters (section / status / q / seller_id) propagate to the
    pipeline — i.e. what the admin sees is what the admin exports.
  • RFC-4180 quoting for titles containing commas / quotes / newlines.
  • `hard_cap` clamps within the [1, 200,000] range.
  • Frontend button is wired to the new endpoint with `responseType:
    'blob'` and the right filter mapping.
"""
from __future__ import annotations

import csv
import io
import os
import time
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv


pytestmark = pytest.mark.monetization

load_dotenv("/app/backend/.env")
BASE = (
    open("/app/frontend/.env")
    .read()
    .split("REACT_APP_BACKEND_URL=", 1)[1]
    .splitlines()[0]
    .strip()
)
API = f"{BASE}/api"
EXPORT = f"{API}/admin/listings/export"
LIST_ENDPOINT = f"{API}/admin/listings/all-collections"
ADMIN_EMAIL, ADMIN_PASSWORD = "charbel911@gmail.com", "Anderosli123!@#"


def _login(email: str, pwd: str) -> str:
    for _ in range(2):
        r = requests.post(
            f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15
        )
        if r.status_code == 200:
            return r.json()["access_token"]
        if r.status_code == 429:
            time.sleep(18)
            continue
        raise AssertionError(f"login {email}: HTTP {r.status_code} — {r.text[:200]}")
    raise AssertionError(f"login {email} still rate-limited")


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASSWORD)}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


# ─── Source integrity ────────────────────────────────────────────────


def test_export_endpoint_module_has_streaming_response_and_header_row():
    src = Path("/app/backend/routes/admin_listings_aggregated.py").read_text()
    for sig in (
        "/admin/listings/export",
        "StreamingResponse",
        "_build_match_pipeline",
        "_CSV_COLUMNS",
        "_csv_quote",
        '"X-BidVex-Export"',
        "hard_cap",
    ):
        assert sig in src, f"export module missing required signature: {sig}"
    # Confirms the export re-uses the same pipeline builder as the list
    # view — they must stay in lockstep.
    assert src.count("_build_match_pipeline(section_filter, q, status, seller_id)") >= 2


def test_frontend_export_button_calls_new_endpoint():
    src = Path("/app/frontend/src/pages/admin/ManageAllAuctions.js").read_text()
    assert "/admin/listings/export" in src, \
        "frontend export button not wired to the iter312 endpoint"
    assert "responseType: 'blob'" in src, \
        "frontend must request a blob to handle the streamed CSV"
    assert "section=marketplace,vehicle" in src or "'marketplace,vehicle'" in src, \
        "typeFilter='single' must map to section=marketplace,vehicle"
    assert "section=vehicle_multi,lots" in src or "'vehicle_multi,lots'" in src, \
        "typeFilter='multi' must map to section=vehicle_multi,lots"
    # The legacy client-side CSV builder must be gone (no more building
    # rows from `filteredListings` and joining with '\n').
    assert "['ID', 'Type', 'Title', 'Category', 'Seller ID', 'Status'" not in src, (
        "legacy client-side CSV builder still present — must use the "
        "server-streamed endpoint."
    )


# ─── Live behaviour ─────────────────────────────────────────────────


def test_export_returns_csv_with_canonical_headers(admin_headers):
    r = requests.get(EXPORT, headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert r.headers.get("content-type", "").startswith("text/csv"), r.headers
    cd = r.headers.get("content-disposition", "")
    assert "bidvex-listings-" in cd and ".csv" in cd, cd
    body = r.text
    # BOM for Excel auto-detect
    assert body.startswith("\ufeff"), "missing UTF-8 BOM at start of CSV"
    header_line = body.split("\n", 1)[0].lstrip("\ufeff").rstrip("\r")
    expected = (
        "Listing ID,Section,Title,Status,Seller ID,Seller Email,Created At,"
        "Auction End,Featured,Current Bid,Lot Count,City,Region"
    )
    assert header_line == expected, (
        f"unexpected header row.\nGOT: {header_line}\nEXPECTED: {expected}"
    )


def test_export_requires_admin():
    buyer = _login("testbuyer@bidvex.com", "TestBuyer2026!")
    r = requests.get(EXPORT, headers={"Authorization": f"Bearer {buyer}"}, timeout=10)
    assert r.status_code == 403


def test_export_section_filter_matches_list_endpoint(admin_headers):
    """The CSV row count for `?section=marketplace` must match the
    `by_section.marketplace` count from the list endpoint — proves the
    filter wiring is symmetric."""
    list_resp = requests.get(
        f"{LIST_ENDPOINT}?section=marketplace&limit=1",
        headers=admin_headers, timeout=20,
    ).json()
    expected = list_resp["by_section"].get("marketplace", 0)
    r = requests.get(
        f"{EXPORT}?section=marketplace&hard_cap=100000",
        headers=admin_headers, timeout=30,
    )
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text.lstrip("\ufeff"))))
    assert len(rows) >= 1
    data_row_count = len(rows) - 1  # subtract header
    assert data_row_count == expected, (
        f"CSV row count {data_row_count} != list by_section.marketplace {expected}"
    )


def test_export_status_filter_propagates(admin_headers, db):
    sample = db.listings.find_one({}, {"_id": 0, "status": 1}) or {}
    status = sample.get("status") or "active"
    r = requests.get(
        f"{EXPORT}?status={status}&hard_cap=100",
        headers=admin_headers, timeout=20,
    )
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text.lstrip("\ufeff"))))
    if len(rows) <= 1:
        pytest.skip("no rows match this status — filter wiring untestable")
    # Every data row must carry the requested status
    for data_row in rows[1:]:
        assert data_row[3] == status, (
            f"row leaked through status filter: {data_row}"
        )


def test_export_q_search_filter(admin_headers):
    fragment = "iter311 marketplace synthetic"
    r = requests.get(
        EXPORT,
        params={"q": fragment, "hard_cap": "10000"},
        headers=admin_headers, timeout=20,
    )
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text.lstrip("\ufeff"))))
    if len(rows) <= 1:
        pytest.skip("no rows match this q — run iter311_perf_seed first")
    for data_row in rows[1:]:
        haystack = " ".join(data_row).lower()
        assert fragment.lower() in haystack, (
            f"row missing q fragment in any column: {data_row}"
        )


def test_export_quoting_is_rfc_4180_safe(admin_headers, db):
    """Insert a synthetic row whose title contains a comma and a
    double-quote, export, and verify the CSV round-trips correctly
    through stdlib csv.reader."""
    import uuid
    from datetime import datetime, timezone

    rowid = f"iter312-csvquote-{uuid.uuid4().hex[:10]}"
    title_with_traps = 'Antique "Brass" lamp, mint, with comma'
    db.listings.insert_one({
        "id": rowid,
        "title": title_with_traps,
        "description": "iter312 quoting test",
        "category": "collectibles",
        "condition": "used",
        "starting_price": 1.0,
        "current_bid": 1.0,
        "status": "active",
        "seller_id": "iter312-fake",
        "user_email": "fake@iter312.test",
        "city": "Toronto",
        "region": "ON",
        "is_featured": False,
        "created_at": datetime.now(timezone.utc),
        "auction_end_date": datetime.now(timezone.utc),
        "_seed_tag": "iter312-csvquote",
    })
    try:
        r = requests.get(
            EXPORT,
            # q matches against id/title/seller_email — search by our row's id prefix
            params={"q": "iter312-csvquote", "hard_cap": "10"},
            headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.text.lstrip("\ufeff"))))
        # Find our row by id
        targets = [row for row in rows[1:] if row and row[0] == rowid]
        assert targets, "synthetic row not found in export — quoting may have broken parsing"
        assert targets[0][2] == title_with_traps, (
            f"title round-trip failed.\nGOT     : {targets[0][2]!r}\n"
            f"EXPECTED: {title_with_traps!r}"
        )
    finally:
        db.listings.delete_one({"id": rowid})


def test_export_invalid_section_returns_empty_csv_with_header(admin_headers):
    r = requests.get(f"{EXPORT}?section=does_not_exist", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    body = r.text.lstrip("\ufeff")
    lines = [ln for ln in body.split("\n") if ln.strip()]
    assert len(lines) == 1, "invalid section must yield header only (no data rows)"
    assert lines[0].startswith("Listing ID,Section,Title,")


def test_export_hard_cap_validates_range(admin_headers):
    # Above the upper bound → bilingual 400 from iter309 validation handler
    r = requests.get(f"{EXPORT}?hard_cap=999999", headers=admin_headers, timeout=15)
    assert r.status_code == 400, r.text[:200]
    assert r.json()["detail"]["code"] == "validation_error"


def test_export_streams_without_blowing_memory(admin_headers):
    """Sanity: a 5k-row export must complete under 10s and never 500.
    This is an upper-bound integration check, not a microbenchmark."""
    t0 = time.perf_counter()
    r = requests.get(f"{EXPORT}?hard_cap=5000", headers=admin_headers, timeout=30)
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200, r.text[:300]
    assert elapsed < 10.0, f"export of up to 5k rows took {elapsed:.1f}s — perf regressed"
    rows = list(csv.reader(io.StringIO(r.text.lstrip("\ufeff"))))
    # Should at least have the header
    assert len(rows) >= 1
    assert rows[0][0] == "Listing ID"
