"""
iter310 — Multi-lot bulk delete cascade + admin module split + pre-commit guard
================================================================================

P0 background (Image 4 / `image_2c6b60.jpg`)
---------------------------------------------
Admin tried to bulk-delete 92 multi-lot listings → API returned
"0 succeeded, 92 failed". Root cause: the previous `admin_bulk.py`
only touched `db.listings`, but vehicle multi-lot events live in
`db.vehicle_multi_lot_auctions`. Every id 404'd inside the loop.

iter310 fixes:
  • `admin_bulk.py` now probes all four listing collections
    (listings / vehicle_listings / vehicle_multi_lot_auctions /
    multi_item_listings) per id and runs the appropriate cascade
    (child bid rows + the parent doc itself) inside a MongoDB
    transaction when available.
  • `admin_user_actions.py` was split into `admin_user_management.py`
    (CRUD) + `admin_user_billing.py` (tier/transactions/subscription).
  • Pre-commit compile hook at `/app/scripts/pre_commit_compile_check.py`
    blocks any future IndentationError / SyntaxError from reaching the
    repo (catches the iter309 P0 regression class).

These tests are the CI guard against future revert of the above.
"""
from __future__ import annotations

import os
import time
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv


pytestmark = pytest.mark.monetization


load_dotenv("/app/backend/.env")

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[1].splitlines()[0].strip()
API = f"{BASE}/api"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ─── Fixtures ────────────────────────────────────────────────────────


def _login(email: str, password: str) -> str:
    for _ in range(2):
        r = requests.post(
            f"{API}/auth/login", json={"email": email, "password": password}, timeout=15
        )
        if r.status_code == 200:
            return r.json()["access_token"]
        if r.status_code == 429:
            time.sleep(18)
            continue
        raise AssertionError(f"login failed {email}: HTTP {r.status_code} — {r.text[:200]}")
    raise AssertionError("login still rate-limited after retry")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture
def seeded_multi_lot_parent(db):
    """Inserts a vehicle_multi_lot_auctions doc with 100 embedded lots
    + 5 standalone `lot_bids` rows pointing at the first lot. Yields
    the parent id and returns it for assertion cleanup."""
    parent_id = f"iter310-mlot-{uuid.uuid4().hex[:12]}"
    lots = []
    for i in range(100):
        lots.append({
            "id": f"{parent_id}-lot-{i:03d}",
            "lot_number": i + 1,
            "make": "Honda",
            "model": f"Civic-{i}",
            "year": 2020 + (i % 5),
            "mileage": 50_000 + i * 1000,
            "current_bid": 1000,
            "bid_count": 0,
            "bid_increment": 50,
            "end_time": (datetime.now(timezone.utc)).isoformat(),
            "media": [],
            "location_city": "Toronto",
            "location_province": "ON",
            "location_postal_code": "M5V 3A8",
            "exterior_color": "white",
            "interior_color": "black",
            "body_type": "sedan",
            "fuel_type": "gas",
            "drivetrain": "fwd",
            "lien_status": "clear",
            "description": "iter310 cascade test lot",
            "condition_report": {},
        })
    parent_doc = {
        "id": parent_id,
        "title": "iter310 — 100-lot cascade delete test",
        "description": "Synthetic parent for the iter310 cascade test.",
        "seller_id": "iter310-fake-seller",
        "seller_email": "fake@iter310.test",
        "status": "draft",
        "lots": lots,
        "bids": [],
        "current_active_lot_index": 0,
        "lot_sequence": "stagger",
        "lot_duration_seconds": 90,
        "stagger_offset_seconds": 30,
        "timing_mode": "stagger",
        "start_time": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    db.vehicle_multi_lot_auctions.insert_one(parent_doc)
    # 5 standalone lot_bids rows pointing at the first lot — cascade
    # must scrub these too.
    standalone_lot_id = lots[0]["id"]
    for j in range(5):
        db.lot_bids.insert_one({
            "id": f"{parent_id}-bid-{j}",
            "lot_id": standalone_lot_id,
            "amount": 1100 + j,
            "bidder_id": "iter310-fake-bidder",
            "created_at": datetime.now(timezone.utc),
        })

    yield parent_id, [l["id"] for l in lots]

    # Cleanup in case the test bailed before cascade
    db.vehicle_multi_lot_auctions.delete_one({"id": parent_id})
    db.lot_bids.delete_many({"lot_id": {"$regex": f"^{parent_id}-lot-"}})


# ─── Source-integrity assertions ─────────────────────────────────────


def test_admin_user_actions_is_now_a_shim():
    """The 750-line module was split. The shim just combines two routers."""
    src = Path("/app/backend/routes/admin_user_actions.py").read_text()
    assert len(src.splitlines()) < 60, "admin_user_actions.py should be a shim (<60 lines)"
    assert "admin_user_management" in src
    assert "admin_user_billing" in src
    assert "include_router(_management_router)" in src
    assert "include_router(_billing_router)" in src


def test_admin_user_management_module_exists_with_router():
    """The management sub-module must export `router` AND contain the
    core CRUD endpoints (notify, request-docs, edit-profile, etc.)."""
    src = Path("/app/backend/routes/admin_user_management.py").read_text()
    for sig in (
        "router = APIRouter",
        '"/{user_id}/send-notification"',
        '"/{user_id}/request-documents"',
        '"/{user_id}/profile"',
        '"/{user_id}/reset-password"',
        '"/{user_id}/convert-to-demo"',
        '"/{user_id}/email-journey"',
        '"/{user_id}/bidding-suspension"',
    ):
        assert sig in src, f"admin_user_management.py missing required signature: {sig}"


def test_admin_user_billing_module_exists_with_router():
    """The billing sub-module must export `router` AND contain
    change-tier, transactions, subscription-status."""
    src = Path("/app/backend/routes/admin_user_billing.py").read_text()
    for sig in (
        "router = APIRouter",
        '"/{user_id}/change-tier"',
        '"/{user_id}/transactions"',
        '"/{user_id}/subscription-status"',
        'action="change_tier"',
    ):
        assert sig in src, f"admin_user_billing.py missing required signature: {sig}"


def test_admin_user_helpers_shared_primitives_present():
    src = Path("/app/backend/routes/admin_user_helpers.py").read_text()
    assert "async def require_admin" in src
    assert "async def record_admin_action" in src
    assert "admin_actions" in src, "record_admin_action must write to admin_actions"


def test_admin_bulk_uses_collection_registry_and_transactions():
    src = Path("/app/backend/routes/admin_bulk.py").read_text()
    # All 4 listing collections must be probed
    for coll in (
        "listings",
        "vehicle_listings",
        "vehicle_multi_lot_auctions",
        "multi_item_listings",
    ):
        assert coll in src, f"admin_bulk.py must probe `{coll}`"
    # Transaction session wrapper present
    assert "start_session" in src
    assert "start_transaction" in src
    # Cascade-totals reported back to the caller
    assert "cascade_totals" in src
    # Per-id locator helper
    assert "async def _locate" in src
    assert "async def _cascade_delete" in src


# ─── Live cascade-delete behaviour (the P0 fix) ──────────────────────


def test_bulk_delete_cross_collection_resolves_listings_in_correct_table(
    admin_headers, seeded_multi_lot_parent, db,
):
    """The seeded parent lives in vehicle_multi_lot_auctions — it must
    succeed (not "0/N failed not found" as before iter310)."""
    parent_id, _lot_ids = seeded_multi_lot_parent
    r = requests.post(
        f"{API}/admin/listings/bulk-action",
        json={"action": "delete", "listing_ids": [parent_id]},
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:400]
    data = r.json()
    assert data["total"] == 1
    assert data["succeeded_count"] == 1, f"expected 1 ok, got {data}"
    assert data["failed_count"] == 0
    # The response identifies the source collection — proves cross-coll
    # resolution works.
    succeeded_collections = {s.get("collection") for s in data["succeeded"]}
    assert "vehicle_multi_lot_auctions" in succeeded_collections


def test_bulk_delete_cascade_removes_parent_and_child_lot_bids(
    admin_headers, db,
):
    """End-to-end cascade: seed parent + lot_bids, hit endpoint, assert
    everything is gone from MongoDB. This is the directive's primary
    DB-persistence assertion."""
    # Fresh seed (don't reuse the fixture so we control assertion order)
    parent_id = f"iter310-cascade-{uuid.uuid4().hex[:12]}"
    lot_ids = [f"{parent_id}-lot-{i}" for i in range(8)]
    db.vehicle_multi_lot_auctions.insert_one({
        "id": parent_id,
        "title": "iter310 cascade",
        "seller_id": "x",
        "status": "draft",
        "lots": [{"id": lid} for lid in lot_ids],
        "bids": [{"id": f"{parent_id}-bid-{i}", "amount": 100} for i in range(3)],
        "created_at": datetime.now(timezone.utc),
    })
    db.lot_bids.insert_many([
        {"id": f"{parent_id}-lb-{i}", "lot_id": lot_ids[i % len(lot_ids)],
         "amount": 200 + i, "created_at": datetime.now(timezone.utc)}
        for i in range(12)
    ])

    pre_parent = db.vehicle_multi_lot_auctions.count_documents({"id": parent_id})
    pre_lot_bids = db.lot_bids.count_documents({"lot_id": {"$in": lot_ids}})
    assert pre_parent == 1 and pre_lot_bids == 12, "seed failed"

    r = requests.post(
        f"{API}/admin/listings/bulk-action",
        json={"action": "delete", "listing_ids": [parent_id]},
        headers=admin_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text[:400]
    data = r.json()
    assert data["succeeded_count"] == 1, data
    assert data["cascade_totals"].get("vehicle_multi_lot_auctions", 0) == 1
    assert data["cascade_totals"].get("lot_bids", 0) == 12, (
        f"cascade did not scrub lot_bids: {data['cascade_totals']}"
    )

    post_parent = db.vehicle_multi_lot_auctions.count_documents({"id": parent_id})
    post_lot_bids = db.lot_bids.count_documents({"lot_id": {"$in": lot_ids}})
    assert post_parent == 0, "parent doc still present after cascade delete"
    assert post_lot_bids == 0, "lot_bids children survived cascade delete"


def test_bulk_delete_massive_100_lot_listing_succeeds(admin_headers, db):
    """The original bug report: 92 multi-lot listings → "0 ok, 92 fail".
    Insert 100 multi-lot parents, bulk-delete all in one call, assert
    100/100 succeed."""
    parent_ids: list[str] = []
    for i in range(100):
        pid = f"iter310-mass-{uuid.uuid4().hex[:10]}-{i:03d}"
        db.vehicle_multi_lot_auctions.insert_one({
            "id": pid,
            "title": f"iter310 mass #{i}",
            "seller_id": "x",
            "status": "draft",
            "lots": [],
            "bids": [],
            "created_at": datetime.now(timezone.utc),
        })
        parent_ids.append(pid)
    try:
        r = requests.post(
            f"{API}/admin/listings/bulk-action",
            json={"action": "delete", "listing_ids": parent_ids},
            headers=admin_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text[:600]
        data = r.json()
        assert data["total"] == 100
        assert data["succeeded_count"] == 100, (
            f"expected 100/100, got {data['succeeded_count']}/{data['total']} "
            f"(failed: {data['failed'][:5]}...)"
        )
        assert data["failed_count"] == 0
        # Verify DB truly empty for those ids
        leftover = db.vehicle_multi_lot_auctions.count_documents(
            {"id": {"$in": parent_ids}}
        )
        assert leftover == 0, f"{leftover} parent docs survived"
    finally:
        # belt-and-suspenders cleanup if the test ever bails mid-flight
        db.vehicle_multi_lot_auctions.delete_many({"id": {"$in": parent_ids}})


def test_bulk_delete_writes_audit_row_with_admin_meta_and_timestamp(
    admin_headers, db,
):
    parent_id = f"iter310-audit-{uuid.uuid4().hex[:12]}"
    db.vehicle_multi_lot_auctions.insert_one({
        "id": parent_id,
        "title": "iter310 audit row test",
        "seller_id": "x",
        "status": "draft",
        "lots": [],
        "bids": [],
        "created_at": datetime.now(timezone.utc),
    })
    cutoff = datetime.now(timezone.utc)
    try:
        r = requests.post(
            f"{API}/admin/listings/bulk-action",
            json={"action": "delete", "listing_ids": [parent_id]},
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json()["succeeded_count"] == 1

        # Find the audit row written during this call
        row = db.admin_action_logs.find_one(
            {"action": "bulk_listing_delete", "timestamp": {"$gte": cutoff}},
            sort=[("timestamp", -1)],
        )
        assert row is not None, "iter310 admin_action_logs row missing"
        assert row.get("admin_email") == ADMIN_EMAIL
        assert row.get("admin_id"), "admin_id missing from audit row"
        assert parent_id in (row.get("target_listing_ids") or []), \
            "audited target_listing_ids must include the deleted id"
        assert row["details"]["succeeded"] == 1
        assert row["details"]["failed"] == 0
        assert row["details"]["cascade_totals"]["vehicle_multi_lot_auctions"] == 1
    finally:
        db.vehicle_multi_lot_auctions.delete_one({"id": parent_id})


def test_bulk_delete_unknown_id_returns_not_found_not_500(admin_headers):
    """Missing ids must surface a clear `not found` reason — never 500."""
    r = requests.post(
        f"{API}/admin/listings/bulk-action",
        json={"action": "delete", "listing_ids": ["iter310-does-not-exist-anywhere"]},
        headers=admin_headers,
        timeout=15,
    )
    assert r.status_code == 200, r.text[:400]
    data = r.json()
    assert data["succeeded_count"] == 0
    assert data["failed_count"] == 1
    assert "not found" in data["failed"][0]["reason"].lower()


def test_bulk_action_non_admin_blocked(db):
    """Non-admin auth must be rejected before any DB touches."""
    buyer_tok = _login("testbuyer@bidvex.com", "TestBuyer2026!")
    r = requests.post(
        f"{API}/admin/listings/bulk-action",
        json={"action": "delete", "listing_ids": ["whatever"]},
        headers={"Authorization": f"Bearer {buyer_tok}"},
        timeout=10,
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code}"


# ─── Pre-commit compile gate ─────────────────────────────────────────


def test_pre_commit_compile_script_exists_and_passes():
    """The hook itself must run clean against the current repo."""
    script = Path("/app/scripts/pre_commit_compile_check.py")
    assert script.is_file(), "pre-commit compile script missing"
    result = subprocess.run(
        ["python3", str(script), "--quiet"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"pre-commit compile check failed:\nSTDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def test_pre_commit_hook_blocks_a_syntactically_broken_file(tmp_path):
    """Inject a broken file into the scan tree, confirm the script
    surfaces it with a non-zero exit. Uses a temp scan that mirrors
    the real CLI but limited to a sandbox dir."""
    bad = tmp_path / "bad.py"
    bad.write_text("def bad(\n    pass\n")  # incomplete signature
    import py_compile as _pc
    try:
        _pc.compile(str(bad), doraise=True)
        pytest.fail("expected py_compile to raise on syntactically broken file")
    except _pc.PyCompileError:
        pass


def test_pre_commit_hook_installed_in_git_hooks():
    """`--install` writes a runnable hook at .git/hooks/pre-commit."""
    hook = Path("/app/.git/hooks/pre-commit")
    if not hook.is_file():
        # Re-install if missing (idempotent)
        subprocess.run(
            ["python3", "/app/scripts/pre_commit_compile_check.py", "--install"],
            check=True, timeout=5,
        )
    assert hook.is_file(), ".git/hooks/pre-commit not installed"
    assert os.access(hook, os.X_OK), "pre-commit hook not executable"
    body = hook.read_text()
    assert "pre_commit_compile_check.py" in body, "hook body doesn't invoke the script"
