"""
iter211 — Manual Settlement Layer

Covers Task 1 (Admin manual subscription settle), Task 2 (Hybrid commission
routing + safety gate), and Task 3 (integrity: Stripe void + bilingual receipts).

Strategy: a mix of unit tests against the service module (fast, no HTTP) and
live HTTP smoke tests against the preview env.
"""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ──────────────────────────────────────────────────────────────────────────
# Service-level unit tests (no HTTP, fast)
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_db():
    """Build an in-memory motor-shaped fake."""
    db = MagicMock()
    state = {"users": {}, "pending_commissions": [], "admin_financial_ledger": []}

    # users
    async def users_find_one(query, projection=None):
        uid = (query or {}).get("id")
        return state["users"].get(uid)

    async def users_update_one(query, update):
        uid = (query or {}).get("id")
        u = state["users"].setdefault(uid, {"id": uid})
        if "$set" in update:
            u.update(update["$set"])
        if "$inc" in update:
            for k, v in update["$inc"].items():
                u[k] = float(u.get(k) or 0) + float(v)
        return MagicMock(modified_count=1)

    db.users.find_one = users_find_one
    db.users.update_one = users_update_one

    # pending_commissions
    async def pc_insert_one(doc):
        state["pending_commissions"].append(doc)
        return MagicMock(inserted_id=doc["id"])

    async def pc_find_one(query, projection=None):
        for row in state["pending_commissions"]:
            if all(row.get(k) == v for k, v in query.items()):
                return row.copy()
        return None

    async def pc_update_one(query, update):
        for row in state["pending_commissions"]:
            if all(row.get(k) == v for k, v in query.items()):
                row.update(update.get("$set", {}))
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    async def pc_to_list(_n):
        return list(state["pending_commissions"])

    pc_cursor = MagicMock()
    pc_cursor.sort = lambda *a, **k: pc_cursor
    pc_cursor.to_list = pc_to_list

    def pc_find(_q, _p=None):
        return pc_cursor

    db.pending_commissions = MagicMock()
    db.pending_commissions.insert_one = pc_insert_one
    db.pending_commissions.find_one = pc_find_one
    db.pending_commissions.update_one = pc_update_one
    db.pending_commissions.find = pc_find

    # aggregate (for fall-back live-sum branch in safety gate)
    pc_agg_cursor = MagicMock()
    async def agg_to_list(_n):
        total = sum(r["commission_amount_cad"] for r in state["pending_commissions"] if r.get("status") == "pending")
        return [{"_id": None, "total": total}] if total else []
    pc_agg_cursor.to_list = agg_to_list
    db.pending_commissions.aggregate = lambda *_a, **_k: pc_agg_cursor

    # admin_financial_ledger
    async def lg_insert_one(doc):
        state["admin_financial_ledger"].append(doc)
        return MagicMock()
    db.admin_financial_ledger = MagicMock()
    db.admin_financial_ledger.insert_one = lg_insert_one

    # Allow dict-style db["pending_commissions"] access used by the service
    def _getitem(self_, key):
        return {
            "pending_commissions": db.pending_commissions,
            "admin_financial_ledger": db.admin_financial_ledger,
        }[key]
    db.__getitem__ = _getitem

    db._state = state
    return db


# ── Task 1 — Manual subscription settle ──────────────────────────────────


@pytest.mark.asyncio
async def test_manual_settle_subscription_activates_dealer(fake_db):
    from services.manual_settlement_service import manual_settle_subscription

    fake_db._state["users"]["u-dealer"] = {"id": "u-dealer", "email": "d@example.com"}
    with patch("services.manual_settlement_service._void_open_stripe_subscription_invoices",
               new=AsyncMock(return_value=[])):
        result = await manual_settle_subscription(
            fake_db,
            target_user_id="u-dealer",
            admin_user_id="admin-1",
            account_kind="vehicle_dealer",
            payment_method="e_transfer",
            reference_number="REF123",
            amount_cad=100.0,
        )
    assert result["ok"] is True
    u = fake_db._state["users"]["u-dealer"]
    assert u["dealer_subscription_active"] is True
    assert u["dealer_subscription_status"] == "active_manual"
    assert u["dealer_subscription_is_manual"] is True
    assert u["dealer_subscription_manual_method"] == "e_transfer"
    assert u["dealer_subscription_manual_reference"] == "REF123"
    assert u["vehicle_dealer_suspended"] is False  # also cleared

    # Ledger row written
    assert len(fake_db._state["admin_financial_ledger"]) == 1
    lg = fake_db._state["admin_financial_ledger"][0]
    assert lg["kind"] == "manual_subscription_settle"
    assert lg["admin_id"] == "admin-1"
    assert lg["amount_cad"] == 100.0


@pytest.mark.asyncio
async def test_manual_settle_subscription_rejects_unsupported_method(fake_db):
    from services.manual_settlement_service import manual_settle_subscription
    fake_db._state["users"]["u-1"] = {"id": "u-1", "email": "x@x.com"}
    with pytest.raises(ValueError, match="payment_method"):
        await manual_settle_subscription(
            fake_db, target_user_id="u-1", admin_user_id="a-1",
            account_kind="vehicle_dealer", payment_method="bitcoin",
            reference_number="X", amount_cad=100.0,
        )


@pytest.mark.asyncio
async def test_manual_settle_subscription_rejects_empty_reference(fake_db):
    from services.manual_settlement_service import manual_settle_subscription
    fake_db._state["users"]["u-1"] = {"id": "u-1", "email": "x@x.com"}
    with pytest.raises(ValueError, match="reference_number"):
        await manual_settle_subscription(
            fake_db, target_user_id="u-1", admin_user_id="a-1",
            account_kind="vehicle_dealer", payment_method="e_transfer",
            reference_number="   ", amount_cad=100.0,
        )


@pytest.mark.asyncio
async def test_manual_settle_subscription_voids_stripe_invoices(fake_db):
    """Zero-bug mandate: any open Stripe draft invoice must be voided."""
    from services.manual_settlement_service import manual_settle_subscription
    fake_db._state["users"]["u-1"] = {
        "id": "u-1", "email": "x@x.com",
        "dealer_stripe_subscription_id": "sub_test",
    }
    fake_void = AsyncMock(return_value=["in_test_1", "in_test_2"])
    with patch("services.manual_settlement_service._void_open_stripe_subscription_invoices",
               new=fake_void):
        result = await manual_settle_subscription(
            fake_db, target_user_id="u-1", admin_user_id="a-1",
            account_kind="vehicle_dealer", payment_method="cheque",
            reference_number="CHQ-1", amount_cad=100.0,
        )
    fake_void.assert_awaited_once_with("sub_test")
    assert result["stripe_invoices_voided"] == ["in_test_1", "in_test_2"]
    lg = fake_db._state["admin_financial_ledger"][0]
    assert lg["stripe_invoices_voided"] == ["in_test_1", "in_test_2"]


# ── Task 2 — Hybrid commission routing ───────────────────────────────────


@pytest.mark.asyncio
async def test_enqueue_manual_commission_increments_outstanding(fake_db):
    from services.manual_settlement_service import enqueue_manual_commission
    fake_db._state["users"]["u-partner"] = {"id": "u-partner"}
    r = await enqueue_manual_commission(
        fake_db,
        user_id="u-partner",
        auction_id="auc-1",
        listing_id="lst-1",
        listing_title="Test",
        commission_amount_cad=75.50,
    )
    assert r["ok"] is True
    assert fake_db._state["users"]["u-partner"]["outstanding_manual_commission_cad"] == 75.50
    assert len(fake_db._state["pending_commissions"]) == 1
    assert fake_db._state["pending_commissions"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_settle_pending_decrements_outstanding(fake_db):
    from services.manual_settlement_service import (
        enqueue_manual_commission, settle_pending_commission,
    )
    fake_db._state["users"]["u-1"] = {"id": "u-1"}
    enq = await enqueue_manual_commission(
        fake_db, user_id="u-1", auction_id=None, listing_id="L",
        listing_title="X", commission_amount_cad=120.00,
    )
    pid = enq["pending_commission_id"]

    res = await settle_pending_commission(
        fake_db, pending_id=pid, admin_user_id="admin-9",
        payment_method="cheque", reference_number="CHQ-XXX",
    )
    assert res["ok"] is True
    # Outstanding decremented
    assert fake_db._state["users"]["u-1"]["outstanding_manual_commission_cad"] == 0.0
    # Row marked paid
    row = fake_db._state["pending_commissions"][0]
    assert row["status"] == "paid"
    assert row["settled_by"] == "admin-9"
    assert row["payment_method"] == "cheque"
    # Ledger row written
    assert any(l["kind"] == "manual_commission_settle" for l in fake_db._state["admin_financial_ledger"])


@pytest.mark.asyncio
async def test_settle_pending_rejects_already_paid(fake_db):
    from services.manual_settlement_service import (
        enqueue_manual_commission, settle_pending_commission,
    )
    fake_db._state["users"]["u-1"] = {"id": "u-1"}
    enq = await enqueue_manual_commission(
        fake_db, user_id="u-1", auction_id=None, listing_id="L",
        listing_title="X", commission_amount_cad=50.00,
    )
    pid = enq["pending_commission_id"]
    await settle_pending_commission(
        fake_db, pending_id=pid, admin_user_id="a-1",
        payment_method="e_transfer", reference_number="R1",
    )
    with pytest.raises(ValueError, match="already_paid"):
        await settle_pending_commission(
            fake_db, pending_id=pid, admin_user_id="a-1",
            payment_method="e_transfer", reference_number="R2",
        )


@pytest.mark.asyncio
async def test_safety_gate_blocks_above_threshold(fake_db):
    from services.manual_settlement_service import (
        enqueue_manual_commission, user_is_blocked_by_outstanding_commission,
    )
    fake_db._state["users"]["u-1"] = {"id": "u-1"}
    # Below threshold
    await enqueue_manual_commission(
        fake_db, user_id="u-1", auction_id=None, listing_id="L1",
        listing_title="X", commission_amount_cad=100.0,
    )
    gate = await user_is_blocked_by_outstanding_commission(fake_db, "u-1")
    assert gate["blocked"] is False
    assert gate["outstanding_cad"] == 100.0

    # Push above threshold
    await enqueue_manual_commission(
        fake_db, user_id="u-1", auction_id=None, listing_id="L2",
        listing_title="X", commission_amount_cad=450.0,
    )
    gate = await user_is_blocked_by_outstanding_commission(fake_db, "u-1")
    assert gate["blocked"] is True
    assert gate["outstanding_cad"] == 550.0


# ── Static smoke tests ──────────────────────────────────────────────────


def test_listings_service_has_safety_gate():
    with open("/app/backend/services/listings_service.py", "r") as f:
        body = f.read()
    assert "user_is_blocked_by_outstanding_commission" in body, \
        "listings_service must enforce the safety gate"
    assert "outstanding_manual_commission" in body
    assert "402" in body, "safety gate must use HTTP 402 Payment Required"


def test_partner_card_routes_by_commission_method():
    with open("/app/backend/routes/partner_card.py", "r") as f:
        body = f.read()
    assert 'commission_payout_method' in body
    assert 'enqueue_manual_commission' in body, \
        "partner_card must enqueue manual commissions when user opted in"
    assert '"manual_payout": True' in body


def test_storage_close_routes_by_commission_method():
    with open("/app/backend/services/scheduled_jobs.py", "r") as f:
        body = f.read()
    assert 'commission_payout_method' in body
    assert 'enqueue_manual_commission' in body, \
        "storage close handler must enqueue manual commissions"


def test_admin_subscription_routes_registered():
    with open("/app/backend/server.py", "r") as f:
        body = f.read()
    assert "manual_settlement" in body, \
        "server must register the manual_settlement router"


def test_bilingual_receipt_includes_both_methods_translations():
    with open("/app/backend/routes/manual_settlement.py", "r") as f:
        body = f.read()
    # All 4 payment methods translated to FR
    assert "virement Interac" in body
    assert "chèque" in body
    assert "virement bancaire" in body
    assert "espèces" in body


def test_admin_ui_has_pending_commissions_tab():
    with open("/app/frontend/src/pages/admin/VehicleAdminManager.js", "r") as f:
        body = f.read()
    assert "pending-commissions" in body
    assert "PendingCommissionsTab" in body
    assert "admin-tab-pending-commissions" in body


def test_admin_ui_has_manual_settle_modal():
    with open("/app/frontend/src/pages/admin/DealerSubscriptionsTab.jsx", "r") as f:
        body = f.read()
    assert "ManualSettleSubscriptionModal" in body
    assert "manual-settle-btn-" in body


def test_seller_dashboard_has_payout_method_card():
    with open("/app/frontend/src/pages/SellerDashboard.js", "r") as f:
        body = f.read()
    assert "CommissionPayoutMethodCard" in body


# ── Live HTTP integration test ───────────────────────────────────────────


API_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com")


def _admin_token():
    import requests
    r = requests.post(
        f"{API_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip(f"Could not log in admin ({r.status_code}); skipping live test")
    return r.json().get("access_token") or r.json().get("token")


class TestManualSettlementLive:
    def test_pending_commissions_endpoint_admin_only(self):
        import requests
        r = requests.get(f"{API_URL}/api/admin/pending-commissions", timeout=10)
        assert r.status_code in (401, 403)

    def test_pending_commissions_returns_summary(self):
        import requests
        token = _admin_token()
        r = requests.get(
            f"{API_URL}/api/admin/pending-commissions",
            headers={"Authorization": f"Bearer {token}"}, timeout=10,
        )
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data and "rows" in data
        assert "threshold_cad" in data["summary"]
        assert "pending_count" in data["summary"]

    def test_financial_ledger_endpoint(self):
        import requests
        token = _admin_token()
        r = requests.get(
            f"{API_URL}/api/admin/financial-ledger?limit=5",
            headers={"Authorization": f"Bearer {token}"}, timeout=10,
        )
        assert r.status_code == 200
        assert "rows" in r.json()

    def test_manual_subscription_settle_via_http(self):
        """Live end-to-end test of admin manual settle."""
        import requests
        # iter302 — the legacy prod user id doesn't exist on every env;
        # seed a minimal target user so the test stays self-contained.
        import os as _os
        from pymongo import MongoClient as _MC
        from dotenv import load_dotenv as _ld
        _ld("/app/backend/.env")
        _db = _MC(_os.environ["MONGO_URL"])[_os.environ["DB_NAME"]]
        target_id = "d000524d-82f3-42d9-8a5a-e7c7f19d7546"
        if not _db.users.find_one({"id": target_id}):
            _db.users.insert_one({
                "id": target_id, "email": "iter211-settle-target@example.com",
                "name": "Iter211 Settle Target", "role": "user",
                "created_at": "2026-01-01T00:00:00+00:00",
            })
        token = _admin_token()
        # Use a stable user id (alexboul1993)
        body = {
            "target_user_id": "d000524d-82f3-42d9-8a5a-e7c7f19d7546",
            "account_kind": "vehicle_dealer",
            "payment_method": "wire",
            "reference_number": "WIRE-PYTEST-001",
            "amount_cad": 100.0,
            "notes": "pytest live test",
        }
        r = requests.post(
            f"{API_URL}/api/admin/manual-settle/subscription",
            headers={"Authorization": f"Bearer {token}"},
            json=body, timeout=10,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["ok"] is True
        assert data["renewal_until"]
        assert "ledger_id" in data
