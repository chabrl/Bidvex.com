"""
iter482 P5.1 — Stripe Actual-Fee Reconciliation Tests
======================================================

Covers:
  1. reconcile_payment_intent persists estimated/recovery/actual/variance
  2. Status resolves to COVERED / SHORTFALL / UNKNOWN correctly
  3. Idempotency — re-running the reconciliation on the same PI updates
     the existing row without duplicating.
  4. Card country resolution from payment_method_details.card.country
  5. Admin endpoints require admin role
  6. Admin summary aggregates covered/shortfall/unknown counts correctly
  7. build_reconciliation_from_event is pure and matches API result
  8. Rate matrix regression: CA and INT gross-up unchanged post-P5.1
"""

from __future__ import annotations
import os
import asyncio
import pytest
import uuid
import httpx
from unittest.mock import patch, MagicMock
from decimal import Decimal
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE_URL = "http://localhost:8001"
HTTP_TIMEOUT = 30.0


def _mongo():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


# ═══════════════════════════════════════════════════════════════════
# Unit: build_reconciliation_from_event pure logic
# ═══════════════════════════════════════════════════════════════════
def test_build_reconciliation_covered():
    from services.stripe_reconciliation_service import build_reconciliation_from_event
    event = {
        "id": "pi_test_covered",
        "metadata": {
            "payment_processing_estimated_cents": "320",
            "payment_processing_recovery_cents": "330",
        },
        "charges": {"data": [{
            "id": "ch_test",
            "balance_transaction": {
                "id": "txn_test",
                "fee": 321,
                "fee_details": [{"type": "stripe_fee", "amount": 321, "currency": "cad"}],
            },
        }]},
    }
    r = build_reconciliation_from_event(event)
    assert r["estimated_cents"] == 320
    assert r["recovery_cents"] == 330
    assert r["actual_cents"] == 321
    assert r["variance_cents"] == 9
    assert r["reconciliation_status"] == "COVERED"


def test_build_reconciliation_shortfall():
    from services.stripe_reconciliation_service import build_reconciliation_from_event
    event = {
        "id": "pi_test_short",
        "metadata": {
            "payment_processing_estimated_cents": "320",
            "payment_processing_recovery_cents": "300",  # under-recovery
        },
        "charges": {"data": [{
            "balance_transaction": {"fee": 321, "fee_details": []},
        }]},
    }
    r = build_reconciliation_from_event(event)
    assert r["recovery_cents"] == 300
    assert r["actual_cents"] == 321
    assert r["variance_cents"] == -21
    assert r["reconciliation_status"] == "SHORTFALL"


def test_build_reconciliation_unknown_when_no_actual():
    from services.stripe_reconciliation_service import build_reconciliation_from_event
    event = {
        "id": "pi_test_unknown",
        "metadata": {"payment_processing_estimated_cents": "320", "payment_processing_recovery_cents": "330"},
        "charges": {"data": []},
    }
    r = build_reconciliation_from_event(event)
    assert r["actual_cents"] == 0
    assert r["reconciliation_status"] == "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════
# Integration: reconcile_payment_intent persists + is idempotent
# ═══════════════════════════════════════════════════════════════════
def _fake_pi(pi_id, *, recovery=330, actual=321, country="CA",
             transaction_type="auction_purchase"):
    """Build a fake Stripe PaymentIntent object for patch().

    iter482 P6.2 — `transaction_type` defaults to `auction_purchase`
    so these pre-existing reconciliation tests continue to exercise
    the reconciliation code path (rather than the new SKIPPED gate).
    """
    return {
        "id": pi_id,
        "metadata": {
            "transaction_type": transaction_type,
            "payment_processing_estimated_cents": "320",
            "payment_processing_recovery_cents": str(recovery),
            "payment_processing_payer_role": "buyer",
            "payment_processing_rate": "0.029",
            "payment_processing_jurisdiction": "domestic",
        },
        "latest_charge": {
            "id": "ch_" + pi_id,
            "balance_transaction": {
                "id": "txn_" + pi_id,
                "fee": actual,
                "currency": "cad",
                "fee_details": [{"type": "stripe_fee", "amount": actual, "currency": "cad"}],
            },
            "payment_method_details": {"card": {"country": country}},
        },
        "payment_method": {"card": {"country": country}},
    }


def test_reconcile_payment_intent_persists_and_is_idempotent(monkeypatch):
    from services import stripe_reconciliation_service as svc

    pi_id = f"pi_test_{uuid.uuid4().hex[:8]}"

    class _StubStripe:
        class PaymentIntent:
            @staticmethod
            def retrieve(*args, **kwargs):
                return _fake_pi(pi_id, recovery=330, actual=321, country="CA")

    monkeypatch.setattr(svc, "_get_stripe", lambda: _StubStripe)

    async def _t():
        db = _mongo()
        try:
            r1 = await svc.reconcile_payment_intent(db, pi_id)
            assert r1["reconciliation_status"] == "COVERED"
            assert r1["actual_cents"] == 321
            assert r1["recovery_cents"] == 330
            assert r1["variance_cents"] == 9
            assert r1["card_country"] == "CA"
            assert r1["resolved_jurisdiction"] == "domestic"
            # Idempotency — second call updates same row
            r2 = await svc.reconcile_payment_intent(db, pi_id)
            count = await db.payment_processing_reconciliation.count_documents({"payment_intent_id": pi_id})
            assert count == 1, f"Reconciliation duplicated: {count} rows"
            assert r2["reconciliation_status"] == "COVERED"
        finally:
            await db.payment_processing_reconciliation.delete_many({"payment_intent_id": pi_id})

    asyncio.run(_t())


def test_reconcile_payment_intent_shortfall(monkeypatch):
    from services import stripe_reconciliation_service as svc
    pi_id = f"pi_test_short_{uuid.uuid4().hex[:8]}"

    class _StubStripe:
        class PaymentIntent:
            @staticmethod
            def retrieve(*args, **kwargs):
                # recovery under actual
                return _fake_pi(pi_id, recovery=200, actual=321, country="US")

    monkeypatch.setattr(svc, "_get_stripe", lambda: _StubStripe)

    async def _t():
        db = _mongo()
        try:
            r = await svc.reconcile_payment_intent(db, pi_id)
            assert r["reconciliation_status"] == "SHORTFALL"
            assert r["variance_cents"] == -121
            assert r["card_country"] == "US"
            assert r["resolved_jurisdiction"] == "international"
        finally:
            await db.payment_processing_reconciliation.delete_many({"payment_intent_id": pi_id})

    asyncio.run(_t())


def test_reconcile_payment_intent_error_when_stripe_fails(monkeypatch):
    from services import stripe_reconciliation_service as svc
    pi_id = f"pi_test_error_{uuid.uuid4().hex[:8]}"

    class _StubStripe:
        class PaymentIntent:
            @staticmethod
            def retrieve(*args, **kwargs):
                raise RuntimeError("network fail")

    monkeypatch.setattr(svc, "_get_stripe", lambda: _StubStripe)

    async def _t():
        db = _mongo()
        try:
            r = await svc.reconcile_payment_intent(db, pi_id)
            assert r is None
            row = await db.payment_processing_reconciliation.find_one({"payment_intent_id": pi_id})
            assert row is not None
            assert row["reconciliation_status"] == "ERROR"
            assert "network fail" in row["error"]
        finally:
            await db.payment_processing_reconciliation.delete_many({"payment_intent_id": pi_id})

    asyncio.run(_t())


# ═══════════════════════════════════════════════════════════════════
# HTTP: admin endpoints require admin
# ═══════════════════════════════════════════════════════════════════
async def _register_regular_user(client):
    email = f"iter482p51-{uuid.uuid4().hex[:8]}@test.com"
    r = await client.post("/api/auth/register", json={
        "name": "P5.1 User",
        "email": email,
        "password": "TestP51!23",
        "role": "user",
        "terms_agreed": True,
        "ai_disclosure_consent": True,
        "accepted_terms": True,
        "terms_accepted": True,
        "province": "QC",
    })
    assert r.status_code in (200, 201), r.text
    token = r.json().get("access_token") or r.json().get("token")
    return email, token


def test_http_admin_endpoints_require_admin():
    async def _t():
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            email, token = await _register_regular_user(c)
            try:
                for path in ("/api/admin/stripe-reconciliation",
                             "/api/admin/stripe-reconciliation/summary"):
                    r = await c.get(path, headers={"Authorization": f"Bearer {token}"})
                    assert r.status_code == 403, f"{path}: {r.status_code} {r.text}"
            finally:
                db = _mongo()
                await db.users.delete_one({"email": email})
    asyncio.run(_t())


def test_http_admin_summary_returns_totals_for_admin():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            # Login as configured admin
            r = await c.post("/api/auth/login", json={
                "email": "charbel911@gmail.com",
                "password": "Anderosli123!@#",
            })
            assert r.status_code == 200, r.text
            token = r.json().get("access_token") or r.json().get("token")

            # Seed reconciliation rows across statuses
            seed = [
                {"payment_intent_id": f"pi_p51_seed_a_{uuid.uuid4().hex[:6]}", "reconciliation_status": "COVERED", "variance_cents": 9, "updated_at": "2026-02-12T12:00:00Z", "created_at": "2026-02-12T12:00:00Z"},
                {"payment_intent_id": f"pi_p51_seed_b_{uuid.uuid4().hex[:6]}", "reconciliation_status": "COVERED", "variance_cents": 11, "updated_at": "2026-02-12T12:00:01Z", "created_at": "2026-02-12T12:00:01Z"},
                {"payment_intent_id": f"pi_p51_seed_c_{uuid.uuid4().hex[:6]}", "reconciliation_status": "SHORTFALL", "variance_cents": -25, "updated_at": "2026-02-12T12:00:02Z", "created_at": "2026-02-12T12:00:02Z"},
            ]
            ids = [row["payment_intent_id"] for row in seed]
            await db.payment_processing_reconciliation.insert_many(seed)

            try:
                r = await c.get("/api/admin/stripe-reconciliation/summary",
                                headers={"Authorization": f"Bearer {token}"})
                assert r.status_code == 200, r.text
                data = r.json()
                assert data["total_rows"] >= 3
                assert data["covered"] >= 2
                assert data["shortfall"] >= 1

                # List endpoint filters by status
                r2 = await c.get("/api/admin/stripe-reconciliation?status=SHORTFALL&limit=10",
                                  headers={"Authorization": f"Bearer {token}"})
                assert r2.status_code == 200, r2.text
                assert r2.json()["count"] >= 1
                statuses = {row["reconciliation_status"] for row in r2.json()["rows"]}
                assert statuses == {"SHORTFALL"}
            finally:
                await db.payment_processing_reconciliation.delete_many({"payment_intent_id": {"$in": ids}})

    asyncio.run(_t())


# ═══════════════════════════════════════════════════════════════════
# Regression: rate matrix, gross-up cent-exact, offline stays $0
# ═══════════════════════════════════════════════════════════════════
def test_regression_gross_up_examples_unchanged_post_p51():
    from services.payment_cost_engine import estimate, PayerRole, LegalGate
    for amount_cents, card_class, additive, recovery in [
        (10000, "domestic", 320, 330),
        (10000, "international", 420, 438),
        (700, "domestic", 50, 52),
        (100000, "domestic", 2930, 3018),
    ]:
        e = estimate(payment_method="stripe_card", amount_cents=amount_cents,
                     currency="CAD", payer_role=PayerRole.BUYER,
                     jurisdiction="QC", card_class=card_class, mode="gross_up")
        assert e.estimated_cents == additive
        assert e.recovery_cents == recovery
        assert e.legal_gate_status is LegalGate.CLEARED


# ═══════════════════════════════════════════════════════════════════
# ANTI-REGRESSION: Stripe payment must never silently show $0
# ═══════════════════════════════════════════════════════════════════
def test_anti_regression_stripe_never_silent_zero():
    """A normal Stripe/card payment MUST have processing_fee > 0 or a
    documented reason_code.  Guards against a future L-1 flip that
    silently returns 0."""
    from services.payment_cost_engine import estimate, PayerRole
    for payer in (PayerRole.BUYER, PayerRole.SELLER):
        for prov in ("QC", "ON", "AB", "BC"):
            e = estimate(
                payment_method="stripe_card",
                amount_cents=10000,
                currency="CAD",
                payer_role=payer,
                jurisdiction=prov,
                mode="gross_up",
            )
            if e.recovery_cents == 0:
                # Must have a documented reason code
                assert e.reason_code in {
                    "offline_method", "legally_gated", "prohibited",
                    "platform_absorbed", "unknown_rate_matrix",
                }, f"Silent 0 for {payer}/{prov}: {e.reason_code}"
            else:
                # Non-zero must be sourced from the canonical rate matrix
                assert e.reason_code == "estimated_from_rate_matrix"
                assert e.recovery_cents >= e.estimated_cents
