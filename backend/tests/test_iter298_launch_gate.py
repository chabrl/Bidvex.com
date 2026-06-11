"""
iter298 — Final pre-launch hardening pass (launch gate).

  CLEANUP — ESLint clean + email_notifications.py shim fully deleted
  BUG 1   — "Ending Soon" computed dynamically (24h window, all 4 sections)
  BUG 2   — Zero-bid end → ended_no_sale + relist email/notification + relist API
  BUG 3   — Automatic commission/fee charging on auction close (payment lifecycle)
  BUG 4   — Buyer receipts + seller statements (email + dashboard)
  BUG 5   — Buyer + seller dashboard correctness
"""
import os
import uuid
import glob
import importlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _motor_db():
    """Fresh Motor client per test — avoids cross-test event-loop reuse."""
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


def _read(rel):
    with open(os.path.join("/app/backend", rel), encoding="utf-8") as fh:
        return fh.read()


# ═══ CLEANUP — shim deleted, zero callers ═════════════════════════════

def test_shim_file_deleted_and_no_callers():
    assert not os.path.exists("/app/backend/services/email_notifications.py")
    offenders = []
    for root, _dirs, files in os.walk("/app/backend"):
        if "__pycache__" in root or "/tests" in root:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            src = open(path, encoding="utf-8", errors="ignore").read()
            if "from services.email_notifications import" in src \
               or "from services import email_notifications" in src \
               or "import services.email_notifications" in src:
                offenders.append(path)
    assert not offenders, f"live imports of deleted shim remain: {offenders}"


def test_shim_import_fails():
    import sys
    for mod in list(sys.modules):
        if mod.endswith("email_notifications"):
            del sys.modules[mod]
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("services.email_notifications")


# ═══ BUG 1 — Ending Soon (dynamic, 24h, 4 sections) ═══════════════════

def _mk_listing(db, *, hours_from_now, status="active"):
    lid = f"iter298-es-{uuid.uuid4().hex[:8]}"
    end = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).isoformat()
    db.listings.insert_one({
        "id": lid, "title": f"ES test {lid}", "status": status,
        "seller_id": "iter298-seller", "category": "electronics",
        "starting_price": 10, "current_price": 10, "bid_count": 0,
        "images": [], "created_at": datetime.now(timezone.utc).isoformat(),
        "auction_start_date": datetime.now(timezone.utc).isoformat(),
        "auction_end_date": end,
    })
    return lid


def test_ending_soon_marketplace_dynamic_window(db):
    inside = _mk_listing(db, hours_from_now=2)
    outside = _mk_listing(db, hours_from_now=72)
    try:
        # The universal feed cache may need a refresh — call with a
        # cache-busting search? The endpoint rebuilds its cache every
        # 30s; force=true param not available, so directly verify the
        # filter logic accepts/rejects via the live endpoint.
        r = requests.get(f"{BASE_URL}/api/marketplace/items",
                         params={"ending_soon": "true", "limit": 100}, timeout=20)
        assert r.status_code == 200
        items = r.json().get("items", [])
        now_iso = datetime.now(timezone.utc).isoformat()
        cutoff = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        for it in items:
            assert it.get("auction_end_date"), "ending_soon item missing end date"
            assert now_iso < str(it["auction_end_date"]) <= cutoff, \
                f"item {it['id']} outside the 24h window"
        ids = {i["id"] for i in items}
        assert outside not in ids, "72h-out listing leaked into ending_soon"
    finally:
        db.listings.delete_many({"id": {"$in": [inside, outside]}})


def test_ending_soon_lots_endpoint(db):
    r = requests.get(f"{BASE_URL}/api/multi-item-listings",
                     params={"ending_soon": "true"}, timeout=20)
    assert r.status_code == 200
    body = r.json()
    listings = body if isinstance(body, list) else body.get("listings", [])
    cutoff = datetime.now(timezone.utc) + timedelta(hours=24)
    for l in listings:
        end_raw = l.get("auction_end_date")
        assert end_raw, "lots ending_soon item missing auction_end_date"
        end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        assert end <= cutoff


def test_ending_soon_vehicles_endpoint():
    r = requests.get(f"{BASE_URL}/api/vehicles",
                     params={"ending_soon": "true"}, timeout=20)
    assert r.status_code == 200


def test_ending_soon_storage_window_is_24h():
    src = _read("routes/storage_auctions.py")
    assert "timedelta(hours=24)" in src, "storage ending_soon window must be 24h"


def test_ending_soon_not_scheduler_flag():
    """Ending Soon must be computed at query time, never read from a
    scheduler-written flag."""
    for rel in ("routes/marketplace.py", "routes/listings.py", "routes/vehicles.py"):
        src = _read(rel)
        assert '"ending_soon": True' not in src and "'ending_soon': True" not in src


# ═══ BUG 2 — ended_no_sale + relist flow ══════════════════════════════

@pytest.mark.asyncio
async def test_zero_bid_close_sets_ended_no_sale_and_notifies(monkeypatch):
    import routes.auctions as auctions_mod
    from routes.auctions import process_ended_auctions

    mdb = _motor_db()
    monkeypatch.setattr(auctions_mod, "_db", mdb)

    seller_id = f"iter298-s-{uuid.uuid4().hex[:8]}"
    lid = f"iter298-nb-{uuid.uuid4().hex[:8]}"
    await mdb.users.insert_one({"id": seller_id, "email": f"{seller_id}@t.com",
                                "name": "NoBids Seller"})
    await mdb.listings.insert_one({
        "id": lid, "title": "zero-bid test item", "status": "active",
        "seller_id": seller_id, "category": "electronics",
        "starting_price": 10, "current_price": 10, "bid_count": 0,
        "auction_end_date": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    })
    try:
        with patch("services.emails.email_vehicles.send_seller_auction_no_bids_email",
                   new=AsyncMock(return_value={"ok": True})) as mock_email:
            await process_ended_auctions()
        doc = await mdb.listings.find_one({"id": lid}, {"_id": 0})
        assert doc["status"] == "ended_no_sale", f"got {doc['status']}"
        assert doc.get("ended_at")
        assert not doc.get("winner_user_id")
        # Email fired with end time + bid count.
        assert mock_email.await_count == 1
        kwargs = mock_email.await_args.kwargs
        assert kwargs["bid_count"] == 0
        assert kwargs["auction_end_time"]
        # Bilingual notification created.
        notif = await mdb.notifications.find_one(
            {"user_id": seller_id, "type": "auction_ended_no_winner"}, {"_id": 0})
        assert notif, "auction_ended_no_winner notification missing"
        assert notif.get("title_en") and notif.get("title_fr")
        assert notif.get("message_en") and notif.get("message_fr")
        assert "Relist" in notif["message_en"]
    finally:
        await mdb.listings.delete_many({"id": lid})
        await mdb.notifications.delete_many({"user_id": seller_id})
        await mdb.users.delete_one({"id": seller_id})


_TOKEN_CACHE = {}


def _login(email, password):
    if email in _TOKEN_CACHE:
        return _TOKEN_CACHE[email]
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    out = ((j.get("access_token") or j.get("token")),
           (j.get("user", {}).get("id") or j.get("id")))
    _TOKEN_CACHE[email] = out
    return out


def test_relist_now_duplicates_and_resets(db):
    token, admin_id = _login("charbel911@gmail.com", "Anderosli123!@#")
    lid = f"iter298-rl-{uuid.uuid4().hex[:8]}"
    started = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    ended = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    db.listings.insert_one({
        "id": lid, "title": "relist source", "status": "ended_no_sale",
        "seller_id": admin_id, "category": "electronics",
        "starting_price": 25, "current_price": 25, "bid_count": 0,
        "auction_start_date": started, "auction_end_date": ended,
        "ended_at": ended, "images": ["http://example.com/x.jpg"],
    })
    new_id = None
    try:
        r = requests.post(
            f"{BASE_URL}/api/listings/{lid}/relist?mode=now",
            headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        new_id = body["new_listing_id"]
        assert body["status"] == "active"

        new_doc = db.listings.find_one({"id": new_id}, {"_id": 0})
        assert new_doc["status"] == "active"
        assert new_doc["bid_count"] == 0
        assert new_doc["current_price"] == 25
        assert new_doc["relisted_from"] == lid
        assert not new_doc.get("winner_user_id")
        # New end ≈ now + original duration (7 days).
        end = datetime.fromisoformat(new_doc["auction_end_date"])
        dur = end - datetime.now(timezone.utc)
        assert timedelta(days=6) < dur < timedelta(days=8)

        # Source stamped + second relist blocked.
        src = db.listings.find_one({"id": lid}, {"_id": 0})
        assert src["relisted_to"] == new_id
        r2 = requests.post(
            f"{BASE_URL}/api/listings/{lid}/relist?mode=now",
            headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r2.status_code == 409
    finally:
        db.listings.delete_many({"id": {"$in": [x for x in (lid, new_id) if x]}})


def test_relist_rejected_for_sold_listing(db):
    token, admin_id = _login("charbel911@gmail.com", "Anderosli123!@#")
    lid = f"iter298-rs-{uuid.uuid4().hex[:8]}"
    db.listings.insert_one({
        "id": lid, "title": "sold source", "status": "ended",
        "seller_id": admin_id, "winner_user_id": "someone",
        "starting_price": 5, "current_price": 50,
    })
    try:
        r = requests.post(
            f"{BASE_URL}/api/listings/{lid}/relist?mode=now",
            headers={"Authorization": f"Bearer {_login('charbel911@gmail.com', 'Anderosli123!@#')[0]}"},
            timeout=15)
        assert r.status_code == 409
    finally:
        db.listings.delete_one({"id": lid})


def test_no_bids_email_has_three_ctas():
    src = _read("services/emails/email_vehicles.py")
    assert "Relist Now" in src
    assert "Edit &amp; Relist" in src
    assert "Promote This Listing" in src
    assert "bid_count" in src and "auction_end_time" in src


# ═══ BUG 3 — payment lifecycle ════════════════════════════════════════

@pytest.mark.asyncio
async def test_finalize_payment_success_path():
    from services.payment_collection import finalize_auction_payment

    mdb = _motor_db()
    buyer_id = f"iter298-b-{uuid.uuid4().hex[:8]}"
    seller_id = f"iter298-s2-{uuid.uuid4().hex[:8]}"
    lid = f"iter298-pc-{uuid.uuid4().hex[:8]}"
    await mdb.users.insert_one({"id": buyer_id, "email": f"{buyer_id}@t.com", "name": "Buyer X"})
    await mdb.users.insert_one({"id": seller_id, "email": f"{seller_id}@t.com", "name": "Seller Y"})
    await mdb.listings.insert_one({
        "id": lid, "title": "paid item", "status": "ended",
        "seller_id": seller_id, "winner_user_id": buyer_id,
        "final_price": 100.0, "current_price": 100.0,
    })
    settlement = {
        "buyer_charge": {"amount": 110.0, "stripe_pi": "pi_test_iter298"},
        "warnings": [],
        "fee_breakdown": {
            "hammer_price": 100.0, "buyer_premium": 2.5, "buyer_taxes": 5.0,
            "buyer_stripe_fee": 3.3, "buyer_total_charged": 110.8,
            "seller_commission": 2.5, "seller_payout": 97.5,
        },
    }
    try:
        with patch("services.emails.email_system.send_buyer_receipt_email",
                   new=AsyncMock(return_value={"ok": True})), \
             patch("services.emails.email_system.send_seller_statement_email",
                   new=AsyncMock(return_value={"ok": True})):
            listing = await mdb.listings.find_one({"id": lid}, {"_id": 0})
            out = await finalize_auction_payment(
                mdb, listing=listing, collection="listings",
                settlement=settlement, section="marketplace")
        assert out["payment_status"] == "payment_collected"

        doc = await mdb.listings.find_one({"id": lid}, {"_id": 0})
        assert doc["payment_status"] == "payment_collected"
        assert doc["net_payout_amount"] == 97.5
        assert doc["payment_transaction_id"] == "pi_test_iter298"
        assert doc.get("buyer_receipt_id")
        assert doc.get("seller_statement_id")

        # Non-custodial: payout_pending row for admin review.
        payout = await mdb.pending_payouts.find_one({"listing_id": lid}, {"_id": 0})
        assert payout and payout["status"] == "payout_pending"
        assert payout["amount"] == 97.5

        # Receipts: buyer + seller rows in CAD.
        rcpt = await mdb.receipts.find_one(
            {"listing_id": lid, "type": "buyer_receipt"}, {"_id": 0})
        stmt = await mdb.receipts.find_one(
            {"listing_id": lid, "type": "seller_statement"}, {"_id": 0})
        assert rcpt and rcpt["currency"] == "CAD" and rcpt["hammer_price"] == 100.0
        assert stmt and stmt["net_payout"] == 97.5
        assert stmt["buyer_first_name"] == "Buyer"

        # Bilingual notifications for both parties.
        bn = await mdb.notifications.find_one(
            {"user_id": buyer_id, "type": "payment_collected"}, {"_id": 0})
        sn = await mdb.notifications.find_one(
            {"user_id": seller_id, "type": "payment_collected_seller"}, {"_id": 0})
        assert bn and bn.get("message_en") and bn.get("message_fr")
        assert sn and sn.get("message_en") and sn.get("message_fr")

        # Idempotent: second finalize doesn't duplicate receipts/payouts.
        with patch("services.emails.email_system.send_buyer_receipt_email",
                   new=AsyncMock(return_value={"ok": True})), \
             patch("services.emails.email_system.send_seller_statement_email",
                   new=AsyncMock(return_value={"ok": True})):
            await finalize_auction_payment(
                mdb, listing=listing, collection="listings",
                settlement=settlement, section="marketplace")
        assert await mdb.receipts.count_documents({"listing_id": lid}) == 2
        assert await mdb.pending_payouts.count_documents({"listing_id": lid}) == 1
    finally:
        await mdb.listings.delete_one({"id": lid})
        await mdb.receipts.delete_many({"listing_id": lid})
        await mdb.pending_payouts.delete_many({"listing_id": lid})
        await mdb.notifications.delete_many({"user_id": {"$in": [buyer_id, seller_id]}})
        await mdb.users.delete_many({"id": {"$in": [buyer_id, seller_id]}})


@pytest.mark.asyncio
async def test_finalize_payment_no_pm_sets_48h_deadline():
    from services.payment_collection import finalize_auction_payment

    mdb = _motor_db()
    buyer_id = f"iter298-b3-{uuid.uuid4().hex[:8]}"
    lid = f"iter298-np-{uuid.uuid4().hex[:8]}"
    await mdb.users.insert_one({"id": buyer_id, "email": f"{buyer_id}@t.com", "name": "NoPM"})
    await mdb.listings.insert_one({
        "id": lid, "title": "no-pm item", "status": "ended",
        "seller_id": "s", "winner_user_id": buyer_id, "final_price": 80.0,
    })
    settlement = {"buyer_charge": None, "warnings": ["buyer_no_pm"],
                  "fee_breakdown": {"buyer_total_charged": 92.0, "buyer_premium": 2.0,
                                    "seller_commission": 2.0}}
    try:
        with patch("services.payment_collection.create_buyer_payment_link",
                   new=AsyncMock(return_value="https://pay.stripe.test/link298")), \
             patch("services.emails.email_system.send_payment_link_email",
                   new=AsyncMock(return_value={"ok": True})) as mock_link_email:
            listing = await mdb.listings.find_one({"id": lid}, {"_id": 0})
            out = await finalize_auction_payment(
                mdb, listing=listing, collection="listings",
                settlement=settlement, section="marketplace")
        assert out["payment_status"] == "pending_payment"
        assert out["payment_link_url"] == "https://pay.stripe.test/link298"
        assert mock_link_email.await_count == 1

        doc = await mdb.listings.find_one({"id": lid}, {"_id": 0})
        assert doc["payment_status"] == "pending_payment"
        assert doc["payment_link_url"] == "https://pay.stripe.test/link298"
        deadline = datetime.fromisoformat(doc["payment_deadline"])
        delta = deadline - datetime.now(timezone.utc)
        assert timedelta(hours=71) < delta <= timedelta(hours=72), f"deadline {delta}"  # iter302: 72h
        # Overdue cron compatibility: winner_id stamped.
        assert doc["winner_id"] == buyer_id
    finally:
        await mdb.listings.delete_one({"id": lid})
        await mdb.notifications.delete_many({"user_id": buyer_id})
        await mdb.users.delete_one({"id": buyer_id})


@pytest.mark.asyncio
async def test_finalize_payment_failure_alerts_admin():
    from services.payment_collection import finalize_auction_payment

    mdb = _motor_db()
    buyer_id = f"iter298-b4-{uuid.uuid4().hex[:8]}"
    lid = f"iter298-pf-{uuid.uuid4().hex[:8]}"
    await mdb.users.insert_one({"id": buyer_id, "email": f"{buyer_id}@t.com", "name": "Failer"})
    await mdb.listings.insert_one({
        "id": lid, "title": "fail item", "status": "ended",
        "seller_id": "s", "winner_user_id": buyer_id, "final_price": 60.0,
    })
    settlement = {"buyer_charge": None,
                  "warnings": ["buyer_charge_failed: card_declined"],
                  "fee_breakdown": {"buyer_total_charged": 69.0}}
    try:
        with patch("services.emails.email_system.send_payment_failed_email",
                   new=AsyncMock(return_value={"ok": True})) as mock_fail_email:
            listing = await mdb.listings.find_one({"id": lid}, {"_id": 0})
            out = await finalize_auction_payment(
                mdb, listing=listing, collection="listings",
                settlement=settlement, section="marketplace")
        assert out["payment_status"] == "payment_failed"
        assert mock_fail_email.await_count == 1

        doc = await mdb.listings.find_one({"id": lid}, {"_id": 0})
        assert doc["payment_status"] == "payment_failed"
        assert "card_declined" in doc["payment_failure_reason"]

        alert = await mdb.admin_alerts.find_one(
            {"listing_id": lid, "type": "payment_failed"}, {"_id": 0})
        assert alert and alert["resolved"] is False

        notif = await mdb.notifications.find_one(
            {"user_id": buyer_id, "type": "payment_failed"}, {"_id": 0})
        assert notif and notif.get("message_en") and notif.get("message_fr")
    finally:
        await mdb.listings.delete_one({"id": lid})
        await mdb.admin_alerts.delete_many({"listing_id": lid})
        await mdb.notifications.delete_many({"user_id": buyer_id})
        await mdb.users.delete_one({"id": buyer_id})


def test_settlement_is_non_custodial():
    """No automatic Stripe destination-charge payouts to sellers —
    everything flows through the payout_pending admin queue."""
    src = _read("services/auction_settlement.py")
    assert "transfer_destination=seller_connect_id" not in src
    assert "payout_pending" in src
    assert "fee_breakdown" in src


def test_marketplace_close_wires_payment_finalize():
    src = _read("routes/auctions.py")
    assert "finalize_auction_payment" in src
    assert "ended_no_sale" in src


def test_vehicle_and_storage_close_wire_payment_lifecycle():
    v = _read("services/vehicle_auction_handler.py")
    assert "payment_collected" in v and "payment_failed" in v
    assert "issue_transaction_records" in v
    s = _read("services/scheduled_jobs.py")
    assert "settle_storage_stripe" in s
    ml = _read("services/vehicle_multi_lot_settlement.py")
    assert "create_vehicle_fee_charge" in ml and "payment_collected" in ml


# ═══ BUG 4 — receipts + statements ════════════════════════════════════

def test_receipts_endpoint_requires_auth():
    r = requests.get(f"{BASE_URL}/api/receipts/mine", timeout=15)
    assert r.status_code in (401, 403)


def test_receipts_endpoint_returns_rows(db):
    token, uid = _login("charbel911@gmail.com", "Anderosli123!@#")
    rid = str(uuid.uuid4())
    db.receipts.insert_one({
        "id": rid, "type": "buyer_receipt", "user_id": uid,
        "listing_id": "iter298-rc-x", "listing_title": "Receipt test",
        "hammer_price": 10.0, "platform_fee": 0.25, "taxes": 0.0,
        "processing_fee": 0.59, "total_charged": 10.84, "net_payout": 9.75,
        "currency": "CAD", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.get(f"{BASE_URL}/api/receipts/mine",
                         params={"role": "buyer"},
                         headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r.status_code == 200
        rows = r.json()["receipts"]
        assert any(row["id"] == rid for row in rows)
        # Single receipt fetch + ownership guard.
        r2 = requests.get(f"{BASE_URL}/api/receipts/{rid}",
                          headers={"Authorization": f"Bearer {token}"}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["currency"] == "CAD"
    finally:
        db.receipts.delete_one({"id": rid})


def test_receipt_emails_have_letterhead_and_are_outlook_safe():
    src = _read("services/emails/email_system.py")
    assert "761 Rue Chalifoux" in src
    assert "1175253974" in src
    assert "send_buyer_receipt_email" in src
    assert "send_seller_statement_email" in src
    assert "send_payment_link_email" in src
    assert "send_payment_failed_email" in src
    # Outlook-safety invariants (no div / no gradients) for everything
    # iter298 added (receipts/statements/payment emails) + the fully
    # table-based email_vehicles module. Legacy div templates elsewhere
    # predate this invariant (tracked: BIDVEX-EMAIL-TABLES).
    marker = "iter298 BUG 4"
    assert marker in src
    new_block = src[src.index(marker):]
    blob = new_block + _read("services/emails/email_vehicles.py")
    assert "<div" not in blob.lower()
    assert "linear-gradient" not in blob.lower()


# ═══ BUG 5 — dashboards ═══════════════════════════════════════════════

def test_buyer_dashboard_new_fields():
    token, _uid = _login("charbel911@gmail.com", "Anderosli123!@#")
    r = requests.get(f"{BASE_URL}/api/dashboard/buyer",
                     headers={"Authorization": f"Bearer {token}"}, timeout=20)
    assert r.status_code == 200
    body = r.json()
    for key in ("active_bids", "winning_bids", "won_items", "won_items_detail",
                "lost_bids", "deposits", "total_bids"):
        assert key in body, f"buyer dashboard missing {key}"
    assert isinstance(body["won_items_detail"], list)
    assert isinstance(body["deposits"], list)


def test_seller_dashboard_split_counts(db):
    token, uid = _login("charbel911@gmail.com", "Anderosli123!@#")
    lid = f"iter298-sd-{uuid.uuid4().hex[:8]}"
    db.listings.insert_one({
        "id": lid, "title": "no-sale dash test", "status": "ended_no_sale",
        "seller_id": uid, "starting_price": 9, "current_price": 9, "bid_count": 0,
    })
    try:
        r = requests.get(f"{BASE_URL}/api/dashboard/seller",
                         headers={"Authorization": f"Bearer {token}"}, timeout=25)
        assert r.status_code == 200
        body = r.json()
        counts = body.get("counts") or {}
        for key in ("ended", "sold", "ended_no_sale", "payment_collected",
                    "payment_failed", "completed"):
            assert key in counts, f"seller counts missing {key}"
        assert counts["ended_no_sale"] >= 1
        # ended bucket includes the no-sale doc.
        assert counts["ended"] >= counts["ended_no_sale"]
        assert "net_payout_total" in body and "collected_sales" in body
    finally:
        db.listings.delete_one({"id": lid})


def test_notifications_i18n_payment_kinds():
    from services.notifications_i18n import build_notification
    for kind in ("payment_collected", "payment_collected_seller",
                 "payment_link_sent", "payment_failed", "auction_ended_no_winner"):
        out = build_notification(
            user_id="iter298-test", kind=kind,
            params={"title": "Test Item", "amount": 42.5})
        assert out["title_en"] and out["title_fr"], kind
        assert out["message_en"] and out["message_fr"], kind
        assert out["message_en"] != out["message_fr"], kind
