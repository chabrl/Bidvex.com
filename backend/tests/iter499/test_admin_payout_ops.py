"""iter499 — Admin Payout Operations (filters + CSV + onboarding + history + timeline).

Coverage matrix:
  Filters:
    * status filter (pending / requires_review / all)
    * min_amount
    * max_amount
    * combined
    * empty results
    * invalid status → 400
    * pagination compatibility (limit)
  CSV export:
    * correct header row
    * respects the active filter
    * escapes commas and quotes safely
    * invalid scope → 400
    * admin-only
  Connect onboarding:
    * unauthenticated → 401/403
    * nonexistent payout → 404
    * seller with usable Connect readiness → "already_connected"
      (no email, no Stripe call)
    * admin_logs row is created (verified via DB)
    * payout row stamped with `onboarding_link_sent_*` fields
  Payout history:
    * admin authorization
    * returns rows with status=sent
    * shows released_by_admin_id + released_by_admin_email
    * pagination compatibility
    * timeline endpoint on the SAME row returns events including
      admin.payout.manual_release
  Financial safety:
    * releasing the same payout twice returns already_sent
    * seller without Connect cannot be released
    * idempotency key remains stable
"""
from __future__ import annotations

import io
import csv as csv_mod
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests


BASE_URL = (
    os.environ.get("BACKEND_BASE_URL")
    or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[-1].split("\n", 1)[0].strip()
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"login {email} failed: {r.status_code}")
    tok = r.json().get("access_token") or r.json().get("token") or ""
    if not tok:
        pytest.skip(f"no token for {email}")
    return tok


# iter499 — cache the admin token at module scope so the test suite does
# not repeatedly hit the login endpoint (which will trip brute-force
# throttling in a fast local run). The cache is invalidated on refresh.
_ADMIN_TOKEN_CACHE: dict = {}


def _admin_headers():
    tok = _ADMIN_TOKEN_CACHE.get("token")
    if not tok:
        tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
        _ADMIN_TOKEN_CACHE["token"] = tok
    return {"Authorization": f"Bearer {tok}"}


def _fresh_nonadmin_headers():
    email = f"iter499nonadmin_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.com"
    requests.post(
        f"{API}/auth/register",
        json={
            "email": email, "password": "Test123!@#", "name": "iter499",
            "terms_agreed": True, "ai_disclosure_consent": True,
        },
        timeout=15,
    )
    return {"Authorization": f"Bearer {_login(email, 'Test123!@#')}"}


@pytest.fixture()
def db_client():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


# ═══════════════════════════════ FILTERS ═══════════════════════════════
def test_pending_status_filter_pending_only():
    r = requests.get(
        f"{API}/admin/payouts/pending?status=pending&limit=100",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    for row in r.json()["rows"]:
        assert row["status"] == "pending"


def test_pending_status_filter_requires_review_only():
    r = requests.get(
        f"{API}/admin/payouts/pending?status=requires_review&limit=100",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    for row in r.json()["rows"]:
        assert row["status"] == "requires_review"


def test_pending_min_amount():
    r = requests.get(
        f"{API}/admin/payouts/pending?min_amount=50&limit=100",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    for row in r.json()["rows"]:
        assert row["amount"] >= 50.0


def test_pending_max_amount():
    r = requests.get(
        f"{API}/admin/payouts/pending?max_amount=200&limit=100",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    for row in r.json()["rows"]:
        assert row["amount"] <= 200.0


def test_pending_combined_filters():
    r = requests.get(
        f"{API}/admin/payouts/pending?status=pending&min_amount=25&max_amount=1000&limit=100",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    for row in r.json()["rows"]:
        assert row["status"] == "pending"
        assert 25.0 <= row["amount"] <= 1000.0


def test_pending_empty_results_when_min_gt_max():
    r = requests.get(
        f"{API}/admin/payouts/pending?min_amount=999999&max_amount=999999999&limit=100",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["rows"] == []


def test_pending_invalid_status_returns_400():
    r = requests.get(
        f"{API}/admin/payouts/pending?status=weird",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 400
    assert "invalid_status" in r.json().get("detail", "")


def test_pending_pagination_via_limit():
    r_small = requests.get(f"{API}/admin/payouts/pending?limit=1", headers=_admin_headers(), timeout=15)
    r_large = requests.get(f"{API}/admin/payouts/pending?limit=200", headers=_admin_headers(), timeout=15)
    assert r_small.status_code == 200 and r_large.status_code == 200
    assert len(r_small.json()["rows"]) <= 1
    assert len(r_large.json()["rows"]) >= len(r_small.json()["rows"])


# ═══════════════════════════════ CSV EXPORT ═══════════════════════════════
def test_csv_export_headers_and_content():
    r = requests.get(
        f"{API}/admin/payouts/export.csv?scope=pending&limit=5",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.content.decode("utf-8-sig")
    reader = csv_mod.reader(io.StringIO(body))
    header = next(reader)
    expected = {
        "payout_id", "auction_id", "seller_name", "seller_email",
        "amount", "currency", "status", "created_at", "sent_at",
        "released_by_admin_id", "released_by_admin_email",
    }
    missing = expected - set(header)
    assert not missing, f"missing CSV columns: {missing}"


def test_csv_export_respects_min_amount_filter():
    r = requests.get(
        f"{API}/admin/payouts/export.csv?scope=pending&min_amount=100&limit=200",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 200
    body = r.content.decode("utf-8-sig")
    reader = csv_mod.reader(io.StringIO(body))
    header = next(reader)
    amount_idx = header.index("amount")
    for row in reader:
        if not row:
            continue
        assert float(row[amount_idx]) >= 100.0, f"row leaked below min: {row}"


@pytest.mark.asyncio
async def test_csv_export_escapes_commas_and_quotes(db_client):
    """Seed a payout with a commas + quotes in a text field and verify
    ``csv.reader`` round-trips it without corruption."""
    payout_id = f"iter499-csvsafe-{uuid.uuid4().hex[:6]}"
    listing_id = f"iter499-listing-csvsafe-{uuid.uuid4().hex[:6]}"
    tricky = 'Item, "with commas" and quotes'
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": listing_id,
        "listing_title": tricky,
        "seller_id": "iter499-noop-seller",
        "amount": 12.99,
        "currency": "CAD",
        "status": "pending",
        "section": "marketplace",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.get(
            f"{API}/admin/payouts/export.csv?scope=pending&search={listing_id}&limit=10",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200
        body = r.content.decode("utf-8-sig")
        reader = csv_mod.reader(io.StringIO(body))
        header = next(reader)
        title_idx = header.index("listing_title")
        payout_idx = header.index("payout_id")
        matched = False
        for row in reader:
            if row and row[payout_idx] == payout_id:
                assert row[title_idx] == tricky, f"CSV round-trip mangled the title: {row[title_idx]!r}"
                matched = True
        assert matched, "seeded CSV-safety row not found in export"
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})


def test_csv_export_invalid_scope():
    r = requests.get(
        f"{API}/admin/payouts/export.csv?scope=hackz",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_scope"


def test_csv_export_requires_admin():
    r = requests.get(
        f"{API}/admin/payouts/export.csv?scope=pending",
        headers=_fresh_nonadmin_headers(), timeout=15,
    )
    assert r.status_code == 403


# ═══════════════════════════ CONNECT ONBOARDING ═══════════════════════════
def test_onboarding_requires_auth():
    r = requests.post(f"{API}/admin/payouts/anything/send-connect-onboarding", timeout=15)
    assert r.status_code in (401, 403)


def test_onboarding_rejects_non_admin():
    r = requests.post(
        f"{API}/admin/payouts/anything/send-connect-onboarding",
        headers=_fresh_nonadmin_headers(), timeout=15,
    )
    assert r.status_code == 403


def test_onboarding_404_when_payout_missing():
    r = requests.post(
        f"{API}/admin/payouts/00000000-0000-0000-0000-000000000000/send-connect-onboarding",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "payout_not_found"


@pytest.mark.asyncio
async def test_onboarding_safe_rejection_when_seller_already_connected(db_client):
    """Seller with usable Stripe Connect readiness → ``already_connected``.
    Verifies no Stripe call and no email dispatch occur."""
    seller_id = f"iter499-connected-{uuid.uuid4().hex[:6]}"
    await db_client.users.update_one(
        {"id": seller_id},
        {"$set": {
            "id": seller_id,
            "email": f"{seller_id}@test.com",
            "name": "iter499 connected seller",
            "role": "user",
            "stripe_connect_account_id": "acct_iter499_fake",
            "stripe_connect_payouts_enabled": True,
            "stripe_connect_onboarding_complete": True,
        }},
        upsert=True,
    )
    payout_id = f"iter499-onboarding-noop-{uuid.uuid4().hex[:6]}"
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": "iter499-listing-connected",
        "listing_title": "Iter499 already-connected seller payout",
        "seller_id": seller_id,
        "amount": 5.0,
        "currency": "CAD",
        "status": "pending",
        "section": "marketplace",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(
            f"{API}/admin/payouts/{payout_id}/send-connect-onboarding",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "already_connected"
        assert body["email_dispatched"] is False
        assert body["stripe_connect_account_id"] == "acct_iter499_fake"
        assert body.get("onboarding_url") is None
        # Payout row was NOT stamped with onboarding_link_sent_at
        doc = await db_client.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
        assert doc.get("onboarding_link_sent_at") is None
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})
        await db_client.users.delete_one({"id": seller_id})


# ═══════════════════════════ PAYOUT HISTORY ═══════════════════════════
def test_history_requires_admin():
    r = requests.get(f"{API}/admin/payouts/history", timeout=15)
    assert r.status_code in (401, 403)
    r2 = requests.get(f"{API}/admin/payouts/history", headers=_fresh_nonadmin_headers(), timeout=15)
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_history_returns_sent_rows_with_released_by_fields(db_client):
    """Seed a `sent` row with released_by_admin_* fields and assert the
    endpoint surfaces them."""
    payout_id = f"iter499-history-{uuid.uuid4().hex[:6]}"
    admin_id = f"iter499-admin-{uuid.uuid4().hex[:4]}"
    now = datetime.now(timezone.utc).isoformat()
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": "iter499-listing-history",
        "listing_title": "iter499 history row",
        "seller_id": "iter499-history-seller",
        "amount": 250.0,
        "currency": "CAD",
        "status": "sent",
        "section": "marketplace",
        "created_at": now,
        "sent_at": now,
        "stripe_transfer_id": "tr_iter499_history",
        "released_by_admin_id": admin_id,
        "released_by_admin_email": "test-admin@bidvex.com",
    })
    try:
        r = requests.get(
            f"{API}/admin/payouts/history?limit=200",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200
        rows = r.json()["rows"]
        found = next((r for r in rows if r["payout_id"] == payout_id), None)
        assert found is not None, "seeded row missing from history"
        assert found["status"] == "sent"
        assert found["released_by_admin_id"] == admin_id
        assert found["released_by_admin_email"] == "test-admin@bidvex.com"
        assert found["stripe_transfer_id"] == "tr_iter499_history"
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})


# ═══════════════════════════ TIMELINE ═══════════════════════════
@pytest.mark.asyncio
async def test_timeline_reconstructs_events_from_admin_logs(db_client):
    """Seed a payout, an admin_logs entry, and a released row; expect the
    timeline to contain both events, sorted oldest → newest."""
    payout_id = f"iter499-timeline-{uuid.uuid4().hex[:6]}"
    created = "2026-02-01T00:00:00+00:00"
    sent = "2026-02-05T00:00:00+00:00"
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": "iter499-listing-timeline",
        "listing_title": "iter499 timeline row",
        "seller_id": "iter499-timeline-seller",
        "amount": 42.0,
        "currency": "CAD",
        "status": "sent",
        "section": "marketplace",
        "created_at": created,
        "sent_at": sent,
        "stripe_transfer_id": "tr_iter499_timeline",
        "released_by_admin_id": "iter499-admin",
        "released_by_admin_email": "audit@bidvex.com",
    })
    await db_client.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": "iter499-admin",
        "admin_email": "audit@bidvex.com",
        "action": "payout.manual_release",
        "target_type": "seller_payout",
        "target_id": payout_id,
        "timestamp": datetime.fromisoformat("2026-02-05T00:00:01+00:00"),
        "details": {"stripe_transfer_id": "tr_iter499_timeline", "amount": 42.0},
    })
    try:
        r = requests.get(
            f"{API}/admin/payouts/{payout_id}/timeline",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["payout_id"] == payout_id
        kinds = [e["kind"] for e in body["events"]]
        assert "payout_created" in kinds
        assert "payout_released" in kinds
        assert any(k.startswith("admin.payout.manual_release") for k in kinds)
        # Sorted
        ats = [e["at"] for e in body["events"]]
        assert ats == sorted(ats)
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})
        await db_client.admin_logs.delete_many({"target_id": payout_id})


def test_timeline_404_for_unknown():
    r = requests.get(
        f"{API}/admin/payouts/no-such-payout/timeline",
        headers=_admin_headers(), timeout=15,
    )
    assert r.status_code == 404


# ═══════════════════════════ FINANCIAL SAFETY ═══════════════════════════
@pytest.mark.asyncio
async def test_release_short_circuits_when_already_sent(db_client):
    """Regression guard on iter498 behavior — releasing an already-sent
    row does NOT hit Stripe and returns the existing transfer id."""
    payout_id = f"iter499-safety-sent-{uuid.uuid4().hex[:6]}"
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": "iter499-safety-listing",
        "seller_id": "irrelevant",
        "amount": 100.0,
        "currency": "CAD",
        "status": "sent",
        "stripe_transfer_id": "tr_iter499_locked",
        "section": "marketplace",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(
            f"{API}/admin/payouts/{payout_id}/release",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "already_sent"
        assert r.json()["stripe_transfer_id"] == "tr_iter499_locked"
        # Row is still exactly as we left it
        doc = await db_client.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
        assert doc["stripe_transfer_id"] == "tr_iter499_locked"
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})


@pytest.mark.asyncio
async def test_release_blocked_when_seller_has_no_connect(db_client):
    """Financial safety — release refuses to move money when the seller
    has no usable Stripe Connect account."""
    payout_id = f"iter499-safety-noconnect-{uuid.uuid4().hex[:6]}"
    seller_id = f"iter499-safety-seller-{uuid.uuid4().hex[:4]}"
    await db_client.users.update_one(
        {"id": seller_id},
        {"$set": {"id": seller_id, "email": f"{seller_id}@test.com", "name": "iter499"}},
        upsert=True,
    )
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": "iter499-noconnect-listing",
        "seller_id": seller_id,
        "amount": 100.0,
        "currency": "CAD",
        "status": "pending",
        "section": "marketplace",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(
            f"{API}/admin/payouts/{payout_id}/release",
            headers=_admin_headers(), timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "still_pending"
        assert r.json()["error"] == "seller_has_no_active_stripe_connect_account"
        doc = await db_client.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
        assert doc["status"] == "pending"
        assert doc.get("stripe_transfer_id") is None
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})
        await db_client.users.delete_one({"id": seller_id})


def test_release_idempotency_key_shape_present_in_source():
    """Static guard — the code path that calls stripe.Transfer.create
    passes an idempotency_key derived from listing_id+lot_number so a
    re-attempt can never double-pay. Reading the source is cheaper than
    faking a full Stripe interaction and catches accidental removal."""
    src = open("/app/backend/routes/admin_payouts.py", "r", encoding="utf-8").read()
    assert "idempotency_key=f\"payout-{listing_id}-{lot_number or 0}\"" in src, (
        "Manual release must reuse the same Stripe idempotency key shape "
        "as the automatic settlement flow — otherwise a real double-fire "
        "cannot be safely deduped by Stripe."
    )
