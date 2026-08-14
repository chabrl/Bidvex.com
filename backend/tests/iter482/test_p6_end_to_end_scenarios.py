"""
iter482 P6 — End-to-end reconciliation scenario tests.

Simulates the two authoritative billing scenarios exactly as the user
requested:

    A. Canadian card
       Hammer $100.00 + BP $5.00 → subtotal $105.00
       Estimated fee at 2.9% + $0.30 = 334¢ ($3.34)
       Recovery at gross-up ≈ 344¢
       Stripe TEST returns actual $3.34 (334¢)  → RECONCILED
       Variance = +10¢  (BidVex over-collected slightly — OK)

    B. International card
       Same subtotal
       System initially recovered at 2.9% + $0.30 = 344¢
       Stripe TEST returns actual $4.20 (420¢)   → SHORTFALL
       Variance = -76¢  (BidVex is out of pocket)

The tests exercise the real
`reconcile_payment_intent` function in `stripe_reconciliation_service.py`
against a monkey-patched Stripe SDK — no live Stripe calls, no live
BalanceTransaction retrieval, no live SendGrid. The variance-email
dispatch inside the real service is also intercepted so we can assert:

  • variance_notification_status transitions
  • only ONE email is dispatched even after a webhook replay
  • RECONCILED payments do NOT trigger any email
"""
from __future__ import annotations
import asyncio
import os
import pytest
from typing import Any, Dict, List
from datetime import datetime, timezone

pytestmark = pytest.mark.asyncio


# ─── fake motor db reused from p6 variance-notification tests ───
from tests.iter482.test_p6_variance_notification import _FakeDB


class _FakeStripe:
    """Monkey-patch target for services.stripe_reconciliation_service._get_stripe.

    The PaymentIntent.retrieve response mirrors the shape the real
    Stripe SDK returns (dot-notation-accessible dict). Test setups
    push the payload they want returned onto the class attribute.
    """
    class PaymentIntent:
        _next: Dict[str, Any] = {}

        @classmethod
        def retrieve(cls, pi_id: str, expand=None):
            payload = dict(cls._next)
            payload["id"] = pi_id
            return payload


@pytest.fixture(autouse=True)
def _patch_stripe(monkeypatch):
    import services.stripe_reconciliation_service as svc
    monkeypatch.setattr(svc, "_get_stripe", lambda: _FakeStripe)
    yield


@pytest.fixture(autouse=True)
def _stub_email_dispatch(monkeypatch):
    """Intercept the canonical send_email dispatcher so no SendGrid call
    escapes the test process, and count invocations for idempotency
    asserts."""
    calls: List[Dict[str, Any]] = []

    async def _fake_send(**kwargs):
        calls.append(kwargs)
        return {"status": "sent"}

    import services.emails._email_core as _core
    monkeypatch.setattr(_core, "send_email", _fake_send)
    _fake_send.calls = calls  # attach so tests can read
    yield _fake_send


def _pi_payload(*, meta, actual_cents: int, card_country: str) -> Dict[str, Any]:
    """Build a minimal PaymentIntent shape that ``reconcile_payment_intent``
    reads (metadata + latest_charge + payment_method_details).

    iter482 P6.2 — Auto-injects `transaction_type=auction_purchase` on
    every payload that doesn't already declare one so these pre-P6.2
    scenarios continue to exercise the reconciliation code path
    instead of the SKIPPED gate.  Explicit transaction_types in caller
    metadata (e.g. `seller_commission_invoice`) are preserved.
    """
    meta = dict(meta)
    meta.setdefault("transaction_type", "auction_purchase")
    return {
        "metadata": meta,
        "latest_charge": {
            "id": f"ch_test_{card_country}_{actual_cents}",
            "payment_method_details": {"card": {"country": card_country}},
            "balance_transaction": {
                "id":  f"btxn_test_{card_country}_{actual_cents}",
                "fee": actual_cents,
                "currency": "cad",
                "fee_details": [
                    {"type": "stripe_fee",
                     "amount": actual_cents,
                     "currency": "cad",
                     "description":
                         "Stripe processing fees" if card_country == "CA"
                         else "International card fees"},
                ],
            },
        },
        "payment_method": {"card": {"country": card_country}},
    }


class TestCanadianCardScenario:
    """Buyer pays via a Canadian card — recovery covers actual fee, so
    the reconciliation lands as COVERED (RECONCILED in P6 vocabulary).
    No variance email is dispatched."""

    async def test_reconciled_no_email(self, _stub_email_dispatch):
        from services.stripe_reconciliation_service import reconcile_payment_intent

        db = _FakeDB()
        pi_id = "pi_ca_test_1"
        _FakeStripe.PaymentIntent._next = _pi_payload(
            meta={
                "payment_processing_estimated_cents": 334,
                "payment_processing_recovery_cents":  344,
                "payment_processing_payer_role":      "buyer",
                "payment_processing_rate":            "2.9%+0.30",
                "payment_processing_jurisdiction":    "domestic",
            },
            actual_cents=334,  # Stripe returned $3.34 (matches estimate exactly)
            card_country="CA",
        )

        doc = await reconcile_payment_intent(db, pi_id)
        assert doc is not None
        assert doc["reconciliation_status"] == "COVERED"
        assert doc["actual_cents"] == 334
        assert doc["recovery_cents"] == 344
        assert doc["variance_cents"] == 10          # BidVex over-collected 10¢
        assert doc["resolved_jurisdiction"] == "domestic"
        # No SendGrid call must occur — COVERED never emails.
        assert _stub_email_dispatch.calls == []


class TestInternationalCardShortfall:
    """The buyer's card resolves as international (US) — Stripe's
    actual fee at 3.9% + $0.30 exceeds the recovery. Reconciliation
    must persist SHORTFALL and dispatch exactly ONE variance email."""

    async def test_shortfall_and_one_email(self, _stub_email_dispatch):
        from services.stripe_reconciliation_service import reconcile_payment_intent

        db = _FakeDB()
        pi_id = "pi_int_test_1"
        # Seed a fake admin recipient so the dispatcher has someone to
        # notify.
        db.users.docs.append({"role": "admin", "email": "billing@bidvex.test"})

        _FakeStripe.PaymentIntent._next = _pi_payload(
            meta={
                "payment_processing_estimated_cents": 334,
                "payment_processing_recovery_cents":  344,
                "payment_processing_payer_role":      "buyer",
                "payment_processing_rate":            "2.9%+0.30",
                "payment_processing_jurisdiction":    "domestic",
            },
            actual_cents=420,   # Stripe returned $4.20 (international rate)
            card_country="US",
        )

        doc = await reconcile_payment_intent(db, pi_id)
        assert doc is not None
        assert doc["reconciliation_status"] == "SHORTFALL"
        assert doc["actual_cents"] == 420
        assert doc["recovery_cents"] == 344
        assert doc["variance_cents"] == -76        # BidVex out of pocket 76¢
        assert doc["resolved_jurisdiction"] == "international"
        assert doc["card_country"] == "US"

        # One variance BATCH must have been dispatched. The dispatcher
        # sends one email PER recipient inside the same batch, so the
        # call count equals the number of resolved admin recipients.
        # We assert at least one call went out AND the batch attributes
        # the same payment_intent_id.
        assert len(_stub_email_dispatch.calls) >= 1
        pis = {
            (c.get("custom_args") or {}).get("payment_intent_id")
            for c in _stub_email_dispatch.calls
        }
        assert pis == {pi_id}, f"expected single-PI batch, got {pis}"
        # The dispatched email carries the finalized FR wording.
        html = _stub_email_dispatch.calls[0]["html_content"]
        assert "Frais de traitement du paiement" in html
        assert "Manque à récupérer sur les frais de traitement" in html
        assert "Frais de traitement Stripe réels" in html


class TestWebhookReplayIdempotency:
    """Replaying the same PaymentIntent event MUST NOT produce a
    second reconciliation row OR a second variance email."""

    async def test_replay_no_duplicate_email(self, _stub_email_dispatch):
        from services.stripe_reconciliation_service import reconcile_payment_intent

        db = _FakeDB()
        pi_id = "pi_int_replay_1"
        db.users.docs.append({"role": "admin", "email": "billing@bidvex.test"})

        payload = _pi_payload(
            meta={
                "payment_processing_estimated_cents": 334,
                "payment_processing_recovery_cents":  344,
                "payment_processing_payer_role":      "buyer",
                "payment_processing_jurisdiction":    "domestic",
            },
            actual_cents=420,
            card_country="US",
        )
        _FakeStripe.PaymentIntent._next = payload

        # First webhook delivery.
        await reconcile_payment_intent(db, pi_id)
        after_first = len(_stub_email_dispatch.calls)
        assert after_first >= 1
        # Second (retry) — identical event.
        await reconcile_payment_intent(db, pi_id)
        after_second = len(_stub_email_dispatch.calls)
        # Third (defensive).
        await reconcile_payment_intent(db, pi_id)
        after_third = len(_stub_email_dispatch.calls)

        # Exactly ONE row persisted.
        rows = [d for d in db.payment_processing_reconciliation.docs
                if d.get("payment_intent_id") == pi_id]
        assert len(rows) == 1

        # ZERO additional sends after the first batch — idempotency
        # is enforced by the variance_notification_status flag.
        assert after_second == after_first, (
            f"webhook replay produced additional email(s): "
            f"first={after_first} second={after_second}"
        )
        assert after_third == after_first


class TestReconciledAfterShortfallFixed:
    """A rare but real case — Stripe's BalanceTransaction is amended
    between the first and second webhook delivery (fee reversal),
    ending as COVERED. The dashboard should reflect the amended state
    while retaining the earlier SHORTFALL variance email (that email
    is a historical record — never rescinded)."""

    async def test_amended_status_is_updated(self, _stub_email_dispatch):
        from services.stripe_reconciliation_service import reconcile_payment_intent

        db = _FakeDB()
        pi_id = "pi_int_amend_1"
        db.users.docs.append({"role": "admin", "email": "billing@bidvex.test"})

        # First delivery — SHORTFALL.
        _FakeStripe.PaymentIntent._next = _pi_payload(
            meta={
                "payment_processing_estimated_cents": 334,
                "payment_processing_recovery_cents":  344,
                "payment_processing_payer_role":      "buyer",
                "payment_processing_jurisdiction":    "domestic",
            },
            actual_cents=420, card_country="US",
        )
        first = await reconcile_payment_intent(db, pi_id)
        assert first["reconciliation_status"] == "SHORTFALL"
        emails_after_first = len(_stub_email_dispatch.calls)
        assert emails_after_first >= 1

        # Second delivery — Stripe amended the fee downward.
        _FakeStripe.PaymentIntent._next = _pi_payload(
            meta={
                "payment_processing_estimated_cents": 334,
                "payment_processing_recovery_cents":  344,
                "payment_processing_payer_role":      "buyer",
                "payment_processing_jurisdiction":    "domestic",
            },
            actual_cents=344, card_country="US",
        )
        second = await reconcile_payment_intent(db, pi_id)
        assert second["reconciliation_status"] == "COVERED"

        # No additional variance email — the amendment is not a new
        # variance event.
        assert len(_stub_email_dispatch.calls) == emails_after_first
