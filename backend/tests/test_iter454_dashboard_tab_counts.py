"""
iter454 — Seller Dashboard status-tab count consistency regression.
====================================================================

Reproduces + locks in the fix for the "Sold (1) blank tab" defect where
`counts.sold` reported a number but the Sold tab rendered zero cards.

Tabs audited (each independently):
    All | Active | Pending Review | Draft | Ended
    All-Ended | Sold | No Sale | Payment Collected |
    Payment Failed | Completed

Invariant: for every tab X, `counts[X] == len(filter_by(X, all_listings))`.

Special-case coverage:
  • Orphan seller_statement receipts (listing purged after settlement)
    are materialized as synthetic rows in `all_listings` — Sold count
    matches Sold-tab card count.
  • Multi-item listing where ONE lot has a winner (parent status =
    'ended', no parent winner_user_id) counts as Sold and appears in
    the Sold tab.
  • Multi-item listing whose ONE lot has payment_status =
    'payment_collected' counts as Payment Collected (subset of Sold).
  • Multi-item listing where ONE lot has payment_status =
    'payment_failed' counts as Payment Failed (subset of Sold).
  • Multi-item listing with any Buy-Now sold_quantity > 0 counts as
    Sold even without a winner_user_id.
  • Fully-unsold ended listing → No Sale (not Sold).
  • Pickup-confirmed sold listing → Completed.

The Python predicates below MIRROR the JavaScript predicates in
frontend/src/pages/SellerDashboard.js so counts and tabs stay in sync.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ─── Frontend-mirror predicates (kept in sync with SellerDashboard.js) ──
_PENDING_STATUSES = {"pending_ai_review", "pending_admin_review", "pending_review"}
_ENDED_STATUSES = {"sold", "ended", "expired", "completed", "ended_no_sale", "unsold"}


def _lots(l):
    v = l.get("lots")
    return v if isinstance(v, list) else []


def _has_any_won(l):
    if l.get("winner_user_id") or l.get("winner_id") or l.get("highest_bidder_id"):
        return True
    for lot in _lots(l):
        if lot.get("winner_user_id") or lot.get("winner_id") or lot.get("highest_bidder_id"):
            return True
        if int(lot.get("sold_quantity") or 0) > 0:
            return True
    return False


def _has_any_payment_collected(l):
    if l.get("payment_status") == "payment_collected":
        return True
    for lot in _lots(l):
        if lot.get("payment_status") == "payment_collected":
            return True
    return False


def _has_any_payment_failed(l):
    if l.get("payment_status") in ("payment_failed", "payment_failed_final"):
        return True
    for lot in _lots(l):
        if lot.get("payment_status") in ("payment_failed", "payment_failed_final"):
            return True
    return False


def _is_sold(l):
    if l.get("status") == "sold":
        return True
    if l.get("status") in ("ended", "expired", "completed") and _has_any_won(l):
        return True
    return False


def _is_no_sale(l):
    if l.get("status") in ("ended_no_sale", "unsold"):
        return True
    if l.get("status") in ("ended", "expired") and not _has_any_won(l):
        return True
    return False


def _is_completed(l):
    if l.get("status") == "completed":
        return True
    if l.get("pickup_confirmed") is True and _has_any_payment_collected(l):
        return True
    return False


def _tab_filter(name: str, all_listings: List[Dict[str, Any]]):
    if name == "all":
        return list(all_listings)
    if name == "active":
        return [l for l in all_listings if l.get("status") == "active"]
    if name == "pending_review":
        return [l for l in all_listings if l.get("status") in _PENDING_STATUSES]
    if name == "draft":
        return [l for l in all_listings if l.get("status") == "draft"]
    if name == "ended":
        return [l for l in all_listings if l.get("status") in _ENDED_STATUSES]
    if name == "sold":
        return [l for l in all_listings if _is_sold(l)]
    if name == "no_sale":
        return [l for l in _tab_filter("ended", all_listings) if _is_no_sale(l)]
    if name == "payment_collected":
        return [l for l in _tab_filter("sold", all_listings) if _has_any_payment_collected(l)]
    if name == "payment_failed":
        return [l for l in _tab_filter("sold", all_listings) if _has_any_payment_failed(l)]
    if name == "completed":
        return [l for l in all_listings if _is_completed(l)]
    return []


# ─── Test infrastructure ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(policy.new_event_loop())


@pytest.fixture(scope="module")
def db(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def app_client():
    from server import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture(scope="module")
def user(event_loop, db):
    """Create an isolated seller so this suite doesn't collide with the
    admin's real dashboard data."""
    async def _mk():
        # Use the admin login for token — but create a scratch seller
        # user whose ID we can filter to.
        uid = f"iter454-seller-{uuid.uuid4().hex[:10]}"
        pw_hash = "$2b$12$CANOT_LOGIN_STUB_HASH_PLACEHOLDER_______________"  # not used for login
        doc = {
            "id": uid,
            "email": f"{uid}@iter454.test",
            "name": "iter454 scratch seller",
            "phone": "+15145550454",
            "billing_address": "-",
            "province": "QC",
            "subscription_tier": "free",
            "role": "user",
            "account_type": "user",
            "password_hash": pw_hash,
        }
        await db.users.insert_one(doc)
        return doc
    d = event_loop.run_until_complete(_mk())
    yield d
    # cleanup
    async def _rm():
        await db.users.delete_one({"id": d["id"]})
        await db.listings.delete_many({"seller_id": d["id"]})
        await db.multi_item_listings.delete_many({"seller_id": d["id"]})
        await db.receipts.delete_many({"user_id": d["id"]})
    event_loop.run_until_complete(_rm())


@pytest.fixture(scope="module")
def user_token(event_loop, app_client, db, user):
    """Log in as admin, then hijack the dashboard endpoint by seeding
    from the same seller_id used by our scratch user. We fetch as admin
    but re-target `seller_id` in the seed docs."""
    async def _login():
        r = await app_client.post(
            "/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        )
        assert r.status_code == 200, r.text
        return r.json().get("access_token") or r.json().get("token")
    return event_loop.run_until_complete(_login())


# ─── Test helpers to build listings for the ADMIN seller ────────────────
@pytest.fixture(scope="module")
def admin_id(event_loop, db):
    async def _get():
        u = await db.users.find_one({"email": "charbel911@gmail.com"})
        return u["id"]
    return event_loop.run_until_complete(_get())


def _base_single(seller_id, **overrides):
    d = {
        "id": f"iter454-mkt-{uuid.uuid4().hex[:10]}",
        "seller_id": seller_id,
        "title": "iter454 single listing",
        "description": "-",
        "category": "other",
        "condition": "used",
        "location": "Montreal, QC",
        "city": "Montreal",
        "region": "QC",
        "starting_price": 5.0,
        "current_price": 5.0,
        "auction_start_date": "2026-02-01T00:00:00+00:00",
        "auction_end_date": "2026-02-07T00:00:00+00:00",
        "status": "active",
        "images": [],
    }
    d.update(overrides)
    return d


def _base_multi(seller_id, lots, **overrides):
    d = {
        "id": f"iter454-multi-{uuid.uuid4().hex[:10]}",
        "seller_id": seller_id,
        "title": "iter454 multi listing",
        "description": "-",
        "city": "Montreal",
        "region": "QC",
        "location": "-",
        "auction_start_date": "2026-02-01T00:00:00+00:00",
        "auction_end_date": "2026-02-07T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0,
        "commission_rate": 4.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
        "currency": "CAD",
        "premium_percentage": 5.0,
        "status": "ended",
        "lots": lots,
    }
    d.update(overrides)
    return d


async def _clear(db, admin_id):
    """Purge any iter454 debris + the admin's pre-existing dashboard
    seed data isn't touched (only our iter454-prefixed docs)."""
    await db.listings.delete_many({"id": {"$regex": "^iter454-"}})
    await db.multi_item_listings.delete_many({"id": {"$regex": "^iter454-"}})
    await db.receipts.delete_many({"id": {"$regex": "^iter454-"}})


async def _fetch_dashboard(app_client, token):
    r = await app_client.get(
        "/api/dashboard/seller",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────
# Scenario A — Bug reproduction: orphan receipt → Sold(1) blank
# ─────────────────────────────────────────────────────────────
class TestScenarioA_OrphanReceiptSoldBlank:
    def test_A1_receipt_only_sale_appears_in_sold_tab_matching_count(
        self, event_loop, db, admin_id, app_client, user_token
    ):
        async def _run():
            await _clear(db, admin_id)
            receipt = {
                "id": f"iter454-r-{uuid.uuid4().hex[:8]}",
                "type": "seller_statement",
                "user_id": admin_id,
                "listing_id": f"iter454-purged-{uuid.uuid4().hex[:8]}",
                "listing_title": "iter454 purged listing",
                "buyer_id": "iter454-buyer",
                "hammer_price": 100.00,
                "total_charged": 105.00,
                "net_payout": 96.00,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            # Baseline dashboard BEFORE seeding
            base = await _fetch_dashboard(app_client, user_token)
            base_sold = base["counts"]["sold"]
            base_visible = len(_tab_filter("sold", base["all_listings"]))
            assert base_sold == base_visible, (
                f"Pre-seed dashboard inconsistent: counts.sold={base_sold} "
                f"but Sold-tab visible={base_visible}"
            )
            await db.receipts.insert_one(receipt)
            try:
                data = await _fetch_dashboard(app_client, user_token)
                counts = data["counts"]
                all_listings = data["all_listings"]
                visible_sold = _tab_filter("sold", all_listings)
                # Bug scenario would have counts.sold == base_sold+1 but
                # visible_sold == base_visible. Fix: both must move together.
                assert counts["sold"] == base_sold + 1, (
                    f"Expected sold count to go from {base_sold} to "
                    f"{base_sold + 1}, got {counts['sold']}"
                )
                assert len(visible_sold) == counts["sold"], (
                    f"REGRESSION: counts.sold={counts['sold']} but Sold-tab "
                    f"cards={len(visible_sold)}"
                )
                # And the synthetic row must be flagged so the UI can show
                # a badge / handle read-only actions.
                synthetic = [l for l in all_listings if l.get("receipt_id") == receipt["id"]]
                assert len(synthetic) == 1
                s = synthetic[0]
                assert s["_synthetic_from_receipt"] is True
                assert s["status"] == "sold"
                assert s["payment_status"] == "payment_collected"
                assert s["final_price"] == 100.00
                assert s["net_payout_amount"] == 96.00
            finally:
                await db.receipts.delete_one({"id": receipt["id"]})
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario B — Every tab count matches its filtered list
# ─────────────────────────────────────────────────────────────
class TestScenarioB_EveryTabConsistent:
    def test_B1_all_tabs_have_matching_counts_and_visible_cards(
        self, event_loop, db, admin_id, app_client, user_token
    ):
        async def _run():
            await _clear(db, admin_id)
            now_iso = datetime.now(timezone.utc).isoformat()
            # Build a fixture set covering every tab.
            seeds = [
                # 1× Active
                _base_single(admin_id, status="active"),
                # 1× Draft
                _base_single(admin_id, status="draft"),
                # 1× Pending Review (AI)
                _base_single(admin_id, status="pending_ai_review"),
                # 1× Pending Review (Admin)
                _base_single(admin_id, status="pending_admin_review"),
                # 1× No Sale (ended_no_sale)
                _base_single(admin_id, status="ended_no_sale"),
                # 1× No Sale (ended, no winner)
                _base_single(admin_id, status="ended"),
                # 1× Sold (single, parent status=sold)
                _base_single(admin_id, status="sold",
                             winner_user_id="iter454-buyer",
                             final_price=50.0),
                # 1× Payment Collected (subset of Sold)
                _base_single(admin_id, status="sold",
                             winner_user_id="iter454-buyer",
                             payment_status="payment_collected",
                             final_price=75.0, net_payout_amount=71.25),
                # 1× Payment Failed (subset of Sold)
                _base_single(admin_id, status="sold",
                             winner_user_id="iter454-buyer",
                             payment_status="payment_failed",
                             final_price=60.0),
                # 1× Completed (single: pickup_confirmed + payment_collected)
                _base_single(admin_id, status="completed",
                             winner_user_id="iter454-buyer",
                             payment_status="payment_collected",
                             pickup_confirmed=True,
                             completed_at=now_iso,
                             final_price=80.0),
                # 1× Multi-item Sold (parent 'ended', lot has winner)
                _base_multi(admin_id, lots=[
                    {"lot_number": 1, "title": "A", "description": "-",
                     "quantity": 5, "sold_quantity": 0,
                     "starting_price": 5.0, "current_price": 12.0,
                     "final_price": 60.0, "winner_user_id": "iter454-buyer",
                     "winning_quantity": 5, "winning_unit_price": 12.0,
                     "lot_status": "ended", "status": "sold"},
                ]),
                # 1× Multi-item Sold via Buy-Now sold_quantity
                _base_multi(admin_id, lots=[
                    {"lot_number": 1, "title": "BN", "description": "-",
                     "quantity": 5, "sold_quantity": 2,
                     "available_quantity": 3,
                     "starting_price": 5.0, "current_price": 5.0,
                     "buy_now_price": 7.0, "buy_now_enabled": True,
                     "lot_status": "partially_sold", "status": "ended"},
                ]),
                # 1× Multi-item Payment Collected (lot-level status)
                _base_multi(admin_id, lots=[
                    {"lot_number": 1, "title": "MPC", "description": "-",
                     "quantity": 3, "sold_quantity": 0,
                     "starting_price": 5.0, "current_price": 12.0,
                     "final_price": 36.0,
                     "winner_user_id": "iter454-buyer",
                     "winning_quantity": 3, "winning_unit_price": 12.0,
                     "payment_status": "payment_collected",
                     "lot_status": "ended", "status": "sold"},
                ]),
                # 1× Multi-item Payment Failed
                _base_multi(admin_id, lots=[
                    {"lot_number": 1, "title": "MPF", "description": "-",
                     "quantity": 3, "sold_quantity": 0,
                     "starting_price": 5.0, "current_price": 12.0,
                     "final_price": 36.0,
                     "winner_user_id": "iter454-buyer",
                     "winning_quantity": 3, "winning_unit_price": 12.0,
                     "payment_status": "payment_failed",
                     "lot_status": "ended", "status": "sold"},
                ]),
                # 1× Multi-item Completed (parent status=completed)
                _base_multi(admin_id, lots=[
                    {"lot_number": 1, "title": "MC", "description": "-",
                     "quantity": 3, "sold_quantity": 0,
                     "starting_price": 5.0, "current_price": 12.0,
                     "final_price": 36.0,
                     "winner_user_id": "iter454-buyer",
                     "winning_quantity": 3, "winning_unit_price": 12.0,
                     "payment_status": "payment_collected",
                     "lot_status": "ended", "status": "sold"},
                ], status="completed", pickup_confirmed=True),
                # 1× Multi-item ended, no winner anywhere → No Sale
                _base_multi(admin_id, lots=[
                    {"lot_number": 1, "title": "NS", "description": "-",
                     "quantity": 5, "sold_quantity": 0,
                     "starting_price": 5.0, "current_price": 5.0,
                     "lot_status": "ended", "status": "ended"},
                ], status="ended_no_sale"),
                # 1× Orphan receipt (Sold via receipt-recovery)
            ]
            # Insert single vs multi based on presence of `lots`.
            for d in seeds:
                if "lots" in d:
                    await db.multi_item_listings.insert_one(d)
                else:
                    await db.listings.insert_one(d)
            receipt = {
                "id": f"iter454-r-{uuid.uuid4().hex[:8]}",
                "type": "seller_statement",
                "user_id": admin_id,
                "listing_id": f"iter454-purged-{uuid.uuid4().hex[:8]}",
                "listing_title": "iter454 purged sale",
                "buyer_id": "iter454-buyer",
                "hammer_price": 200.00,
                "total_charged": 210.00,
                "net_payout": 192.00,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.receipts.insert_one(receipt)
            try:
                data = await _fetch_dashboard(app_client, user_token)
                counts = data["counts"]
                al = data["all_listings"]
                iter454 = [l for l in al if str(l.get("id", "")).startswith(
                    ("iter454-", ))]
                # Baseline uses only iter454-prefixed listings so the
                # scratch admin's real historical rows don't skew asserts.
                report = {}
                mismatches = []
                for tab in ("all", "active", "pending_review", "draft",
                            "ended", "sold", "no_sale", "payment_collected",
                            "payment_failed", "completed"):
                    # Backend does NOT expose "all"/"no_sale" as top-level
                    # keys — map them.
                    if tab == "all":
                        c = counts.get("total", 0)
                    elif tab == "no_sale":
                        c = counts.get("ended_no_sale", 0)
                    else:
                        c = counts.get(tab, 0)
                    filtered_all = _tab_filter(tab, al)
                    filtered_iter454 = _tab_filter(tab, iter454)
                    report[tab] = (c, len(filtered_all), len(filtered_iter454))
                    if c != len(filtered_all):
                        mismatches.append(
                            f"{tab}: counts={c} vs filtered={len(filtered_all)}"
                        )
                # Print report for debugging
                for tab, (c, fa, fi) in report.items():
                    print(f"  {tab:20s} count={c:3d}  filtered_all={fa:3d}  "
                          f"iter454={fi:3d}")
                assert not mismatches, (
                    "Tab counts don't match visible cards:\n" + "\n".join(mismatches)
                )

                # Explicit expectations against iter454-prefixed docs:
                assert len([l for l in iter454 if l.get("status") == "active"]) == 1
                assert len([l for l in iter454 if l.get("status") == "draft"]) == 1
                assert len([l for l in iter454 if l.get("status") in _PENDING_STATUSES]) == 2
                # Sold: 5 single-listing sold + 4 multi-item sold + 1 orphan receipt
                #  = 10
                iter454_plus_synthetic = iter454  # synthetic rows are already
                # in iter454 (their id begins with "iter454-purged-").
                sold_iter454 = _tab_filter("sold", iter454_plus_synthetic)
                assert len(sold_iter454) == 10, (
                    f"Expected 10 sold iter454 listings, got "
                    f"{len(sold_iter454)}: "
                    f"{[l.get('id') for l in sold_iter454]}"
                )
                # Payment collected: single-collected + multi-collected +
                # multi-completed (payment_collected on the lot) +
                # single-completed (payment_collected) + orphan receipt
                # = 5
                pc = _tab_filter("payment_collected", iter454_plus_synthetic)
                assert len(pc) == 5, (
                    f"expected 5 payment_collected, got {len(pc)}"
                )
                # Payment failed: 1 single + 1 multi = 2
                pf = _tab_filter("payment_failed", iter454_plus_synthetic)
                assert len(pf) == 2
                # Completed: 1 single + 1 multi = 2
                comp = _tab_filter("completed", iter454_plus_synthetic)
                assert len(comp) == 2
                # No Sale: 1 single ended_no_sale + 1 single ended (no
                # winner) + 1 multi ended_no_sale = 3
                ns = _tab_filter("no_sale", iter454_plus_synthetic)
                assert len(ns) == 3
            finally:
                await _clear(db, admin_id)
                await db.receipts.delete_one({"id": receipt["id"]})
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario C — Multi-item lot-level outcomes matter more than parent
# ─────────────────────────────────────────────────────────────
class TestScenarioC_MultiItemLotLevel:
    def test_C1_multi_item_sold_via_lot_winner_only(
        self, event_loop, db, admin_id, app_client, user_token
    ):
        """Parent status='ended' with no parent winner but a lot has
        winner_user_id → must count as Sold."""
        async def _run():
            await _clear(db, admin_id)
            doc = _base_multi(admin_id, lots=[
                {"lot_number": 1, "title": "L1", "description": "-",
                 "quantity": 3, "sold_quantity": 0,
                 "starting_price": 5.0, "current_price": 12.0,
                 "final_price": 36.0,
                 "winner_user_id": "iter454-buyer",
                 "winning_quantity": 3, "winning_unit_price": 12.0,
                 "lot_status": "ended", "status": "sold"},
            ], status="ended")
            await db.multi_item_listings.insert_one(doc)
            try:
                data = await _fetch_dashboard(app_client, user_token)
                al = data["all_listings"]
                iter454 = [l for l in al if str(l.get("id", "")) == doc["id"]]
                assert len(iter454) == 1
                l = iter454[0]
                assert _is_sold(l), "Multi-item lot-won listing NOT sold"
                # And it should be in the backend's sold count
                sold_ids = {l["id"] for l in _tab_filter("sold", al)}
                assert doc["id"] in sold_ids
            finally:
                await _clear(db, admin_id)
        event_loop.run_until_complete(_run())

    def test_C2_multi_item_payment_collected_lot_level(
        self, event_loop, db, admin_id, app_client, user_token
    ):
        async def _run():
            await _clear(db, admin_id)
            doc = _base_multi(admin_id, lots=[
                {"lot_number": 1, "title": "L1", "description": "-",
                 "quantity": 3, "sold_quantity": 0,
                 "starting_price": 5.0, "current_price": 12.0,
                 "final_price": 36.0,
                 "winner_user_id": "iter454-buyer",
                 "winning_quantity": 3, "winning_unit_price": 12.0,
                 "payment_status": "payment_collected",
                 "lot_status": "ended", "status": "sold"},
            ], status="ended")
            await db.multi_item_listings.insert_one(doc)
            try:
                data = await _fetch_dashboard(app_client, user_token)
                al = data["all_listings"]
                pc_ids = {l["id"] for l in _tab_filter("payment_collected", al)}
                assert doc["id"] in pc_ids, (
                    "Lot-level payment_collected NOT surfaced in "
                    "Payment Collected tab"
                )
                # Payment Collected must be a SUBSET of Sold
                sold_ids = {l["id"] for l in _tab_filter("sold", al)}
                assert doc["id"] in sold_ids
            finally:
                await _clear(db, admin_id)
        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario D — Bilingual-safe: dashboard state does not depend on locale
# ─────────────────────────────────────────────────────────────
class TestScenarioD_BilingualStable:
    def test_D1_dashboard_endpoint_is_language_agnostic(
        self, event_loop, db, admin_id, app_client, user_token
    ):
        """Endpoint returns identical counts regardless of ?lang query.
        (Frontend translations only affect labels.)"""
        async def _run():
            await _clear(db, admin_id)
            doc = _base_single(admin_id, status="sold",
                               winner_user_id="iter454-buyer",
                               payment_status="payment_collected",
                               final_price=50.0)
            await db.listings.insert_one(doc)
            try:
                r_en = await app_client.get(
                    "/api/dashboard/seller?lang=en",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                r_fr = await app_client.get(
                    "/api/dashboard/seller?lang=fr",
                    headers={"Authorization": f"Bearer {user_token}"},
                )
                a = r_en.json()["counts"]
                b = r_fr.json()["counts"]
                assert a == b, (
                    f"Counts diverge across locales: EN={a} FR={b}"
                )
            finally:
                await _clear(db, admin_id)
        event_loop.run_until_complete(_run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
