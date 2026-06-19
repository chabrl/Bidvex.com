"""
iter311 — Admin "All Collections" unified listing endpoint
============================================================

Locks in the server-aggregated `GET /api/admin/listings/all-collections`
behavior:

  • Admins get a normalized union across the 4 listing collections.
  • Non-admins are blocked (403).
  • Filters (q, status, section, seller_id) hit MongoDB, not the client.
  • Sort + pagination work consistently across collections.
  • `by_section` count summary is accurate and uses the canonical
    section tags (`marketplace`, `vehicle`, `vehicle_multi`, `lots`).
  • `perf_ms` is present and reasonable.

Smoke-data: assumes the iter311 perf-seed has been run at least once,
so we have non-trivial counts across all 4 collections. Falls back to
soft assertions when a collection is empty.
"""
from __future__ import annotations

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
ENDPOINT = f"{API}/admin/listings/all-collections"

ADMIN_EMAIL, ADMIN_PASSWORD = "charbel911@gmail.com", "Anderosli123!@#"


def _login(email: str, pwd: str) -> str:
    for _ in range(2):
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": pwd}, timeout=15)
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


# ─── Source-integrity ───────────────────────────────────────────────


def test_admin_listings_aggregated_module_exists():
    path = Path("/app/backend/routes/admin_listings_aggregated.py")
    assert path.is_file()
    src = path.read_text()
    for sig in (
        "/admin/listings/all-collections",
        "$unionWith",
        '"coll": "vehicle_listings"',
        '"coll": "vehicle_multi_lot_auctions"',
        '"coll": "multi_item_listings"',
        "$facet",
        "by_section",
        "perf_ms",
        "require_admin",
    ):
        assert sig in src, f"admin_listings_aggregated.py missing required signature: {sig}"


def test_endpoint_is_registered_in_server():
    src = Path("/app/backend/server.py").read_text()
    assert "admin_listings_aggregated" in src
    assert "from routes.admin_listings_aggregated import router" in src


# ─── Live behaviour ──────────────────────────────────────────────────


def test_endpoint_returns_200_for_admin_and_shape_is_canonical(admin_headers):
    r = requests.get(f"{ENDPOINT}?limit=5", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    for key in ("total", "by_section", "limit", "offset", "rows", "perf_ms"):
        assert key in body, f"response missing {key}"
    assert isinstance(body["rows"], list)
    assert isinstance(body["by_section"], dict)
    assert body["limit"] == 5
    assert body["offset"] == 0
    # Every row has the normalized shape
    for row in body["rows"]:
        for k in ("id", "_section", "title", "status", "created_at"):
            assert k in row, f"row missing field {k}: {row}"
        assert row["_section"] in {"marketplace", "vehicle", "vehicle_multi", "lots"}


def test_endpoint_requires_admin():
    buyer = _login("testbuyer@bidvex.com", "TestBuyer2026!")
    r = requests.get(ENDPOINT, headers={"Authorization": f"Bearer {buyer}"}, timeout=10)
    assert r.status_code == 403, f"non-admin got {r.status_code}"


def test_by_section_counts_match_db(admin_headers, db):
    r = requests.get(f"{ENDPOINT}?limit=1", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text[:300]
    by_section = r.json()["by_section"]
    expected = {
        "marketplace": db.listings.count_documents({}),
        "vehicle": db.vehicle_listings.count_documents({}),
        "vehicle_multi": db.vehicle_multi_lot_auctions.count_documents({}),
        "lots": db.multi_item_listings.count_documents({}),
    }
    # Endpoint omits sections with zero rows — only assert presence
    # for the non-empty ones.
    for sec, n in expected.items():
        if n > 0:
            assert by_section.get(sec) == n, (
                f"by_section[{sec}] = {by_section.get(sec)}, expected {n}"
            )


def test_section_filter_restricts_results(admin_headers):
    r = requests.get(f"{ENDPOINT}?section=marketplace&limit=20",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert all(row["_section"] == "marketplace" for row in body["rows"])
    # by_section should also be restricted (no other sections appear)
    assert set(body["by_section"].keys()) <= {"marketplace"}


def test_multi_section_csv_filter(admin_headers):
    r = requests.get(f"{ENDPOINT}?section=vehicle,vehicle_multi&limit=20",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200
    body = r.json()
    allowed = {"vehicle", "vehicle_multi"}
    for row in body["rows"]:
        assert row["_section"] in allowed, row
    for sec in body["by_section"].keys():
        assert sec in allowed


def test_status_filter_works(admin_headers, db):
    # Find some status that actually exists in the data
    sample = db.listings.find_one({}, {"status": 1, "_id": 0}) or {}
    status = sample.get("status") or "active"
    r = requests.get(f"{ENDPOINT}?status={status}&limit=20",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200
    body = r.json()
    for row in body["rows"]:
        assert row["status"] == status, f"row leaked through filter: {row}"


def test_q_search_filter_matches_title_substring(admin_headers, db):
    # Pick a known seeded title fragment from iter311
    sample = db.listings.find_one({"_seed_tag": "iter311-perf-seed"}, {"title": 1, "_id": 0})
    if not sample:
        pytest.skip("no iter311-perf-seed marketplace docs present")
    fragment = "iter311 marketplace synthetic"
    r = requests.get(f"{ENDPOINT}?q={fragment}&limit=20",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    for row in body["rows"]:
        assert fragment.lower() in (row.get("title") or "").lower() or \
            fragment.lower() in (row.get("seller_email") or "").lower() or \
            fragment.lower() in (row.get("id") or "").lower()


def test_seller_id_filter(admin_headers):
    admin_seller_id = "8940074d-da97-43ca-9a0b-c59d39411ed6"
    r = requests.get(f"{ENDPOINT}?seller_id={admin_seller_id}&limit=20",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200
    for row in r.json()["rows"]:
        assert row.get("seller_id") == admin_seller_id


def test_pagination_offset_advances_window(admin_headers):
    first = requests.get(f"{ENDPOINT}?limit=10&offset=0&sort=created_at_desc",
                         headers=admin_headers, timeout=20).json()
    second = requests.get(f"{ENDPOINT}?limit=10&offset=10&sort=created_at_desc",
                          headers=admin_headers, timeout=20).json()
    if len(first["rows"]) < 10 or len(second["rows"]) == 0:
        pytest.skip("not enough rows to verify pagination window")
    first_ids = {r["id"] for r in first["rows"]}
    second_ids = {r["id"] for r in second["rows"]}
    assert first_ids.isdisjoint(second_ids), \
        "offset=10 returned overlapping rows with offset=0"


def test_sort_created_at_desc_is_default(admin_headers):
    r = requests.get(f"{ENDPOINT}?limit=10", headers=admin_headers, timeout=20)
    rows = r.json()["rows"]
    if len(rows) < 2:
        pytest.skip("need at least 2 rows to verify sort")
    # Parse timestamps via datetime so we compare values (not BSON
    # mixed-type strings). Some legacy `listings` rows have `created_at`
    # stored as a tz-naive string while iter311/iter312-seeded rows have
    # tz-aware datetimes — Python string sort would interleave them
    # incorrectly. We coerce both to UTC `datetime` for the compare.
    from datetime import datetime, timezone

    def _to_utc(s):
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    parsed = [_to_utc(row.get("created_at")) for row in rows]
    parsed = [d for d in parsed if d is not None]
    if len(parsed) < 2:
        pytest.skip("not enough parseable timestamps to verify sort")
    assert parsed == sorted(parsed, reverse=True), \
        "default sort is not created_at_desc"


def test_invalid_section_returns_empty_not_500(admin_headers):
    r = requests.get(f"{ENDPOINT}?section=does_not_exist",
                     headers=admin_headers, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["rows"] == []


def test_limit_caps_at_500(admin_headers):
    r = requests.get(f"{ENDPOINT}?limit=9999", headers=admin_headers, timeout=20)
    # FastAPI Query(ge=1, le=500) raises a validation error → iter309's
    # global RequestValidationError handler converts it to a bilingual 400.
    assert r.status_code == 400, r.text[:300]
    body = r.json()["detail"]
    assert body.get("code") == "validation_error"


def test_perf_ms_is_reasonable(admin_headers):
    """Server-side aggregation should land well under the old 800ms
    multi-fetch baseline. We allow up to 1500ms in CI to absorb any
    cold-start variance, but the typical value is <100ms."""
    # Warm-up + measure
    requests.get(f"{ENDPOINT}?limit=10", headers=admin_headers, timeout=20)
    samples = []
    for _ in range(3):
        r = requests.get(f"{ENDPOINT}?limit=50", headers=admin_headers, timeout=20)
        samples.append(r.json().get("perf_ms", 9999))
    median = sorted(samples)[len(samples) // 2]
    assert median < 1500, f"server perf_ms median {median} > 1500ms — agg pipeline regressed"


def test_perf_baseline_script_exists():
    """The before/after baseline script lives in repo and is runnable."""
    assert Path("/app/backend/scripts/iter311_perf_baseline.py").is_file()
    assert Path("/app/backend/scripts/iter311_perf_seed.py").is_file()


def test_index_install_script_exists():
    """iter311 compound-index installer must exist and cover all 4 collections."""
    path = Path("/app/backend/scripts/iter311_install_indexes.py")
    assert path.is_file()
    src = path.read_text()
    for coll in ("listings", "vehicle_listings", "vehicle_multi_lot_auctions", "multi_item_listings"):
        assert coll in src, f"index installer missing {coll}"
    assert "iter311_status_1_created_at_-1" in src
    assert "iter311_seller_id_1" in src


def test_indexes_actually_installed_on_atlas(db):
    """The 4 collections must carry the iter311_status_1_created_at_-1
    compound index after the installer has been run."""
    for coll_name in ("listings", "vehicle_listings",
                       "vehicle_multi_lot_auctions", "multi_item_listings"):
        names = [idx["name"] for idx in db[coll_name].list_indexes()]
        has_iter311 = any("iter311" in n for n in names)
        # Allow the listings collection to satisfy via the pre-existing
        # `idx_listings_status_created` (same key shape, different name).
        has_equivalent = any(
            ("status_created" in n) or ("iter311" in n) or
            (n.startswith("status_1_") and "created" in n)
            for n in names
        )
        assert has_iter311 or has_equivalent, (
            f"{coll_name} missing the status+created_at compound index. "
            f"Found: {names}. Run scripts/iter311_install_indexes.py."
        )


def test_frontend_swapped_to_unified_endpoint():
    """Admin Manage-All-Auctions page must call the new endpoint, not
    the legacy /admin/listings/all + /admin/multi-item-listings/all
    fan-out pattern."""
    src = Path("/app/frontend/src/pages/admin/ManageAllAuctions.js").read_text()
    assert "/admin/listings/all-collections" in src, \
        "frontend not wired to the iter311 unified endpoint"
    # Legacy multi-fetch must be gone
    assert "/admin/listings/all'" not in src and \
           "/admin/multi-item-listings/all'" not in src, \
        "frontend still calls the legacy multi-fetch endpoints"
    # Single state array replaces the old singleListings/multiListings split
    assert "setAllListings" in src
    assert "setSingleListings" not in src
    assert "setMultiListings" not in src
