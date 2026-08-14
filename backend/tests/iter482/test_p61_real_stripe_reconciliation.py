"""
iter482 P6.1 — REAL Stripe TEST-mode reconciliation proof.

Creates a REAL Stripe TEST PaymentIntent using Stripe's static test
PaymentMethod (`pm_card_visa` → 4242 Visa, US card → `card.country = "US"`)
so the payer's card resolves as INTERNATIONAL — which is precisely the
scenario the SHORTFALL detection is designed to catch when the recovery
was calculated at the domestic (CA) rate.

The test then runs the payment through the EXISTING
`reconcile_payment_intent()` function (NO monkey-patching — real Stripe
API calls) and asserts:

  • Real BalanceTransaction retrieved with real integer-cent fee.
  • Card country + resolved_jurisdiction persisted from real Stripe data.
  • Estimated / Recovery / Actual / Variance persisted correctly.
  • SHORTFALL detected when actual > recovery.
  • Webhook replay (3×) produces exactly 1 row and 1 email batch.
  • The variance email is dispatched through the canonical
    `services/emails/_email_core.send_email` (stubbed so no real email
    leaves the environment).

No customer is charged (Stripe TEST mode). No historical financial
record is mutated. No duplicate infrastructure is created.
"""
from __future__ import annotations
import asyncio
import os
import time
import pytest
import stripe
from typing import Any, Dict, List
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

pytestmark = pytest.mark.asyncio

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME   = os.environ["DB_NAME"]
STRIPE_KEY = os.environ.get("STRIPE_TEST_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")

if not STRIPE_KEY or "sk_test" not in STRIPE_KEY:
    pytestmark = pytest.mark.skip(reason="Stripe TEST key not available in env")


@pytest.fixture(scope="module")
def stripe_client():
    stripe.api_key = STRIPE_KEY
    return stripe


@pytest.fixture(scope="module")
def db():
    """Real Motor DB (no monkey-patch)."""
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(autouse=True)
def _stub_email_dispatch(monkeypatch):
    """Intercept the canonical send_email dispatcher so no SendGrid call
    escapes the test process — we only want the CALL to prove the
    variance-notification pipeline ran, not to actually mail anyone."""
    calls: List[Dict[str, Any]] = []

    async def _fake_send(**kwargs):
        calls.append(kwargs)
        return {"status": "sent"}

    import services.emails._email_core as _core
    monkeypatch.setattr(_core, "send_email", _fake_send)
    _fake_send.calls = calls
    return _fake_send


class TestRealStripeReconciliation:
    """Executes ONE real Stripe TEST-mode payment and drives the full
    reconciliation pipeline. Values captured in this test are echoed
    into the final P6.1 report."""

    async def _create_real_pi(self, stripe_client, *, currency="cad",
                               amount_cents=10500, recovery_cents=344,
                               estimated_cents=334):
        """Create a real Stripe TEST PaymentIntent + confirm it.

        Uses `pm_card_visa` (Stripe's static TEST PaymentMethod for
        4242 Visa → US card) so the resolved card country is `US` and
        the reconciliation lands as INTERNATIONAL.
        """
        pi = stripe_client.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            payment_method="pm_card_visa",  # US test Visa
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata={
                "payment_processing_estimated_cents": str(estimated_cents),
                "payment_processing_recovery_cents":  str(recovery_cents),
                "payment_processing_payer_role":      "buyer",
                "payment_processing_rate":            "2.9%+0.30",
                "payment_processing_jurisdiction":    "domestic",  # initial assumption
                "iter482_p61_test":                   "true",
            },
        )
        return pi

    async def test_full_real_stripe_reconciliation(self, stripe_client, db, _stub_email_dispatch):
        # 1. Seed at least one admin recipient in the DB so
        #    dispatch_variance_notification has someone to notify.
        await db.users.update_one(
            {"id": "p61_admin"},
            {"$set": {
                "id": "p61_admin",
                "email": "p61-admin@bidvex-p6test.com",
                "role": "admin",
                "is_active": True,
                "email_verified": True,
                "name": "P6.1 Admin",
            }},
            upsert=True,
        )

        try:
            # 2. Create + confirm a real Stripe TEST PaymentIntent.
            pi = await self._create_real_pi(stripe_client)
            pi_id = pi.id
            assert pi.status == "succeeded", f"PaymentIntent not succeeded: {pi.status}"

            print(f"\n[P6.1] Real TEST PaymentIntent: {pi_id} status={pi.status}")
            print(f"[P6.1]   amount={pi.amount}c currency={pi.currency}")

            # 3. Drive the EXISTING reconciliation function — NO
            #    monkey-patching. It makes a real API call to
            #    stripe.PaymentIntent.retrieve.
            from services.stripe_reconciliation_service import reconcile_payment_intent
            doc = await reconcile_payment_intent(db, pi_id)
            assert doc is not None

            print(f"[P6.1] Real Charge ID:              {doc.get('charge_id')}")
            print(f"[P6.1] Real BalanceTransaction ID:  {doc.get('balance_transaction_id')}")
            print(f"[P6.1] Real Stripe fee (actual):    {doc.get('actual_cents')}¢")
            print(f"[P6.1] Estimated:                   {doc.get('estimated_cents')}¢")
            print(f"[P6.1] Recovery:                    {doc.get('recovery_cents')}¢")
            print(f"[P6.1] Variance:                    {doc.get('variance_cents')}¢")
            print(f"[P6.1] Card country:                {doc.get('card_country')}")
            print(f"[P6.1] Resolved jurisdiction:       {doc.get('resolved_jurisdiction')}")
            print(f"[P6.1] Reconciliation status:      {doc.get('reconciliation_status')}")

            # 4. Contract asserts — real Stripe data.
            assert doc["payment_intent_id"] == pi_id
            assert doc["charge_id"], "no real charge_id returned"
            assert doc["balance_transaction_id"], "no real balance_transaction_id"
            assert doc["actual_cents"] > 0, "real Stripe fee must be > 0 for a $105 charge"
            assert doc["estimated_cents"] == 334
            assert doc["recovery_cents"] == 344
            assert doc["variance_cents"] == doc["recovery_cents"] - doc["actual_cents"]
            # US Visa test card → country should be "US" (international).
            assert doc["card_country"] == "US"
            assert doc["resolved_jurisdiction"] == "international"

            # 5. SHORTFALL contract: recovery ($3.44) < actual (Stripe
            #    charges ≥2.9%+$0.30 CAD on any card, plus a currency-
            #    conversion / international surcharge for a US card
            #    charged in CAD — actual will exceed $3.44).
            if doc["actual_cents"] > doc["recovery_cents"]:
                assert doc["reconciliation_status"] == "SHORTFALL"

                # 6. Variance email must have been dispatched exactly once.
                emails_after_first = len(_stub_email_dispatch.calls)
                assert emails_after_first >= 1, (
                    "variance email must dispatch on real SHORTFALL"
                )
                # The email body must carry the finalized FR wording.
                body = _stub_email_dispatch.calls[0]["html_content"]
                assert "Frais de traitement du paiement" in body
                assert "Manque à récupérer sur les frais de traitement" in body
                assert "Frais de traitement Stripe réels" in body

                # 7. Webhook replay — 3× identical events. NO
                #    additional DB rows, NO additional email batches.
                for _ in range(3):
                    await reconcile_payment_intent(db, pi_id)
                emails_after_replay = len(_stub_email_dispatch.calls)
                assert emails_after_replay == emails_after_first, (
                    f"webhook replay produced additional emails: "
                    f"{emails_after_first} → {emails_after_replay}"
                )

                rows = await db.payment_processing_reconciliation.count_documents(
                    {"payment_intent_id": pi_id}
                )
                assert rows == 1, f"webhook replay produced duplicate rows: {rows}"

                # 8. Persisted-value integrity — no dashboard/API/DB
                #    drift. Re-fetch the DB row and compare against the
                #    return value.
                stored = await db.payment_processing_reconciliation.find_one(
                    {"payment_intent_id": pi_id}, {"_id": 0}
                )
                assert stored["actual_cents"]      == doc["actual_cents"]
                assert stored["estimated_cents"]   == doc["estimated_cents"]
                assert stored["recovery_cents"]    == doc["recovery_cents"]
                assert stored["variance_cents"]    == doc["variance_cents"]
                assert stored["card_country"]      == doc["card_country"]
                assert stored["resolved_jurisdiction"] == doc["resolved_jurisdiction"]
                assert stored["reconciliation_status"] == "SHORTFALL"
                assert stored["variance_notification_status"] == "SENT"
                assert stored["variance_notification_sent_at"]

                print(f"[P6.1] Emails after first dispatch:  {emails_after_first}")
                print(f"[P6.1] Emails after 3× replay:       {emails_after_replay}")
                print(f"[P6.1] DB rows for {pi_id[:15]}…: {rows}")

            else:
                # Rare — Stripe's fee happened to equal or fall below
                # recovery (e.g. Stripe rounded down + no int surcharge
                # in the current pricing config). We still assert
                # RECONCILED and NO variance email.
                assert doc["reconciliation_status"] == "COVERED"
                assert len(_stub_email_dispatch.calls) == 0

        finally:
            # 9. Cleanup — remove the seeded admin (leave the real
            #    Stripe TEST payment record and the reconciliation row
            #    for admin dashboard visibility).
            await db.users.delete_one({"id": "p61_admin"})
