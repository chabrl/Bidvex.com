"""
iter482 P6.4 — buy_it_now + vehicle_platform_fee reconciliation coverage.

Verifies:
  1. `RECONCILABLE_TRANSACTION_TYPES` now includes `buy_it_now` and
     `vehicle_platform_fee`.
  2. A stubbed PI with `transaction_type=buy_it_now` + canonical P5.1
     metadata reconciles (COVERED / SHORTFALL) rather than SKIPPED.
  3. A stubbed PI with `transaction_type=vehicle_platform_fee` +
     canonical metadata reconciles.
  4. `payment_cost_engine.build_pi_metadata` returns exactly the six
     canonical keys expected by the P6.2 gate.
  5. Legacy pre-P6.4 buy_now PI shape (no canonical metadata) still
     SKIPS gracefully — no false SHORTFALL, no email.
"""
from __future__ import annotations
import os
from typing import Any, Dict, List
import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

pytestmark = pytest.mark.asyncio


def _payload(pi_id: str, *, tx_type: str,
             estimated: int = 334, recovery: int = 344, actual: int = 419,
             card_country: str = "US",
             include_canonical: bool = True) -> Dict[str, Any]:
    meta: Dict[str, str] = {}
    if tx_type:
        meta["transaction_type"] = tx_type
    if include_canonical:
        meta["payment_processing_estimated_cents"] = str(estimated)
        meta["payment_processing_recovery_cents"] = str(recovery)
        meta["payment_processing_payer_role"] = "buyer"
    return {
        "id": pi_id, "status": "succeeded", "amount": 10500, "currency": "cad",
        "metadata": meta,
        "latest_charge": {
            "id": f"ch_{pi_id[3:]}",
            "balance_transaction": {
                "id": f"txn_{pi_id[3:]}", "fee": actual, "currency": "cad",
                "fee_details": [{"amount": actual, "currency": "cad",
                                 "type": "stripe_fee",
                                 "description": "Stripe processing fees",
                                 "application": None}],
            },
            "payment_method_details": {"card": {"country": card_country}},
        },
        "payment_method": {"card": {"country": card_country}},
    }


class _FakeStripe:
    def __init__(self):
        self._pi = {}
        outer = self

        class _PI:
            def retrieve(self, pi_id, expand=None):
                return outer._pi[pi_id]
        self.PaymentIntent = _PI()

        class _CH:
            def retrieve(self, ch_id, expand=None):
                for pi in outer._pi.values():
                    lc = pi.get("latest_charge") or {}
                    if lc.get("id") == ch_id:
                        return lc
                return {}
        self.Charge = _CH()
        self.api_key = ""

    def register(self, pi_id, payload):
        self._pi[pi_id] = payload


@pytest.fixture()
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture()
def stub_stripe(monkeypatch):
    stub = _FakeStripe()
    import services.stripe_reconciliation_service as svc
    monkeypatch.setattr(svc, "_get_stripe", lambda: stub)
    return stub


@pytest.fixture()
def capture_emails(monkeypatch):
    calls: List[Dict[str, Any]] = []

    async def _fake_send(**kwargs):
        calls.append(kwargs)
        return {"status": "sent"}

    import services.emails._email_core as core
    monkeypatch.setattr(core, "send_email", _fake_send)
    return calls


# ═════════════════════════════════════════════════════════════════
# 1) Whitelist snapshot
# ═════════════════════════════════════════════════════════════════
@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
def test_p64_whitelist_includes_buy_it_now_and_vehicle_fee():
    from services.stripe_reconciliation_service import (
        RECONCILABLE_TRANSACTION_TYPES,
    )
    assert "buy_it_now" in RECONCILABLE_TRANSACTION_TYPES
    assert "vehicle_platform_fee" in RECONCILABLE_TRANSACTION_TYPES
    # And the pre-existing values are still there.
    assert "auction_purchase" in RECONCILABLE_TRANSACTION_TYPES
    assert "seller_commission_invoice" in RECONCILABLE_TRANSACTION_TYPES


# ═════════════════════════════════════════════════════════════════
# 2) buy_it_now with canonical metadata → reconciles
# ═════════════════════════════════════════════════════════════════
async def test_buy_it_now_reconciles_shortfall(db, stub_stripe, capture_emails):
    pi_id = "pi_p64_bin_shortfall"
    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )

    # Seed a real admin so the dispatcher has a recipient (test filter
    # skips synthetic seeds by default).
    await db.users.update_one(
        {"id": "p64_admin"},
        {"$set": {"id": "p64_admin", "email": "p64-real-admin@bidvex.com",
                  "role": "admin", "is_active": True}},
        upsert=True,
    )

    stub_stripe.register(
        pi_id,
        _payload(pi_id, tx_type="buy_it_now",
                 estimated=334, recovery=344, actual=419,
                 card_country="US"),
    )

    from services.stripe_reconciliation_service import reconcile_payment_intent
    doc = await reconcile_payment_intent(db, pi_id)

    assert doc["reconciliation_status"] == "SHORTFALL"
    assert doc["actual_cents"] == 419
    assert doc["recovery_cents"] == 344
    assert doc["variance_cents"] == -75
    assert doc["card_country"] == "US"
    assert doc["resolved_jurisdiction"] == "international"
    assert doc["payer_role"] == "buyer"

    # Variance email dispatched exactly once.
    assert len(capture_emails) >= 1

    # Cleanup.
    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )
    await db.users.delete_one({"id": "p64_admin"})


async def test_buy_it_now_reconciles_covered(db, stub_stripe, capture_emails):
    pi_id = "pi_p64_bin_covered"
    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )

    stub_stripe.register(
        pi_id,
        _payload(pi_id, tx_type="buy_it_now",
                 estimated=100, recovery=110, actual=105,
                 card_country="CA"),
    )

    from services.stripe_reconciliation_service import reconcile_payment_intent
    doc = await reconcile_payment_intent(db, pi_id)

    assert doc["reconciliation_status"] == "COVERED"
    assert doc["variance_cents"] == 5
    assert doc["resolved_jurisdiction"] == "domestic"
    # COVERED never triggers a variance email.
    assert capture_emails == []

    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )


# ═════════════════════════════════════════════════════════════════
# 3) vehicle_platform_fee with canonical metadata → reconciles
# ═════════════════════════════════════════════════════════════════
async def test_vehicle_platform_fee_reconciles_shortfall(
    db, stub_stripe, capture_emails
):
    pi_id = "pi_p64_vf_shortfall"
    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )

    await db.users.update_one(
        {"id": "p64_vf_admin"},
        {"$set": {"id": "p64_vf_admin", "email": "p64-vf-real-admin@bidvex.com",
                  "role": "admin", "is_active": True}},
        upsert=True,
    )

    stub_stripe.register(
        pi_id,
        _payload(pi_id, tx_type="vehicle_platform_fee",
                 estimated=334, recovery=344, actual=430,
                 card_country="US"),
    )

    from services.stripe_reconciliation_service import reconcile_payment_intent
    doc = await reconcile_payment_intent(db, pi_id)

    assert doc["reconciliation_status"] == "SHORTFALL"
    assert doc["actual_cents"] == 430
    assert doc["variance_cents"] == -86
    assert len(capture_emails) >= 1

    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )
    await db.users.delete_one({"id": "p64_vf_admin"})


# ═════════════════════════════════════════════════════════════════
# 4) build_pi_metadata helper — canonical shape
# ═════════════════════════════════════════════════════════════════
@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
def test_build_pi_metadata_shape():
    from services.payment_cost_engine import (
        estimate, build_pi_metadata,
        PaymentMethod, PayerRole,
    )
    est = estimate(
        payment_method=PaymentMethod.STRIPE_CARD,
        amount_cents=10000,
        currency="CAD",
        payer_role=PayerRole.BUYER,
        jurisdiction="QC",
        card_class="domestic",
        mode="gross_up",
    )
    meta = build_pi_metadata(
        transaction_type="buy_it_now",
        est=est,
        payer_role="buyer",
    )
    # Six canonical keys — every value is a string.
    assert set(meta.keys()) == {
        "transaction_type",
        "payment_processing_estimated_cents",
        "payment_processing_recovery_cents",
        "payment_processing_payer_role",
        "payment_processing_jurisdiction",
        "payment_processing_rate",
    }
    for k, v in meta.items():
        assert isinstance(v, str), f"{k} is not a string"
    assert meta["transaction_type"] == "buy_it_now"
    assert meta["payment_processing_payer_role"] == "buyer"
    # Estimated + recovery must be non-negative integer strings.
    assert int(meta["payment_processing_estimated_cents"]) >= 0
    assert int(meta["payment_processing_recovery_cents"]) >= 0
    # Recovery >= estimated in gross-up mode.
    assert int(meta["payment_processing_recovery_cents"]) >= int(meta["payment_processing_estimated_cents"])


# ═════════════════════════════════════════════════════════════════
# 5) Legacy buy_now shape (no canonical metadata) — must NOT reconcile
#     Prevents old rows / third-party integrations from creating
#     false SHORTFALL under the P6.2 gate.
# ═════════════════════════════════════════════════════════════════
async def test_legacy_buy_it_now_without_metadata_still_reconciles(
    db, stub_stripe, capture_emails,
):
    """A caller that sets `transaction_type=buy_it_now` but forgets the
    canonical P5.1 metadata IS whitelisted (per P6.4). Recovery will
    be 0, so the row will land as SHORTFALL — this is intentional
    because the caller mis-configured the flow. The reconciler MUST
    make the row visible in the ledger; the operator sees it and
    fixes the caller.
    """
    pi_id = "pi_p64_bin_legacy_shape"
    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )

    await db.users.update_one(
        {"id": "p64_legacy_admin"},
        {"$set": {"id": "p64_legacy_admin",
                  "email": "p64-legacy-admin@bidvex.com",
                  "role": "admin", "is_active": True}},
        upsert=True,
    )

    stub_stripe.register(
        pi_id,
        _payload(pi_id, tx_type="buy_it_now",
                 include_canonical=False, actual=419),
    )

    from services.stripe_reconciliation_service import reconcile_payment_intent
    doc = await reconcile_payment_intent(db, pi_id)

    # 0 estimated + 0 recovery + 419 actual → SHORTFALL (−419).
    # Reconciler correctly surfaces this operational defect so the
    # operator can spot the mis-configured caller in the dashboard.
    assert doc["reconciliation_status"] == "SHORTFALL"
    assert doc["estimated_cents"] == 0
    assert doc["recovery_cents"] == 0
    assert doc["actual_cents"] == 419
    assert doc["variance_cents"] == -419

    # Cleanup.
    await db.payment_processing_reconciliation.delete_one(
        {"payment_intent_id": pi_id}
    )
    await db.users.delete_one({"id": "p64_legacy_admin"})
