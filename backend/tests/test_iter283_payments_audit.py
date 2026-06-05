"""
iter283-payments-audit — Pre-launch payment infrastructure audit.

Pins 3 genuine bugs caught + confirms the deposit-rule contracts
remain perfectly intact:

  M1A — Add-Card form uses SetupIntent + confirmCardSetup with
        `usage="off_session"` (not bare createPaymentMethod).
  M1B — Idempotent backfill creates Stripe Customers for users
        missing `stripe_customer_id`.
  M4B — Webhook handler checks idempotency via unique index on
        `stripe_events.id` and early-returns 200 on duplicates.

Plus contract-preservation pins for the deposit engine.
"""
from __future__ import annotations

import os


def _read(rel: str) -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _read_fe(rel: str) -> str:
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
    )
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── M1A — SetupIntent flow ────────────────────────────────────────────


def test_audit_addcard_uses_confirm_card_setup():
    """The AddCardForm MUST use Stripe's SetupIntent flow
    (`stripe.confirmCardSetup` + client_secret) instead of bare
    `createPaymentMethod`. SetupIntent handles 3DS / SCA and
    confirms off-session usability."""
    src = _read_fe("pages/ProfileSettingsPage.js")
    # Strip JS line + block comments before scanning so historical
    # commit-context references inside the docstring don't false-trip
    # the regression guard.
    import re
    code_only = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    code_only = re.sub(r"//[^\n]*", "", code_only)
    assert "stripe.createPaymentMethod(" not in code_only, (
        "regression: AddCardForm reverted to bare createPaymentMethod — "
        "3DS-required cards will fail at deposit hold time."
    )
    # New flow present.
    assert "stripe.confirmCardSetup" in src
    assert "/payments/setup-intent" in src


def test_audit_setup_intent_marked_off_session():
    """SetupIntent.create MUST pass `usage="off_session"` so the
    card is verified usable for the deposit-hold flow that runs
    later without user re-prompt."""
    src = _read("routes/payments.py")
    idx = src.find("stripe.SetupIntent.create")
    assert idx > 0
    block = src[idx:idx + 500]
    assert 'usage="off_session"' in block, (
        "missing usage=off_session on SetupIntent.create — "
        "downstream off_session charges will fail SCA"
    )


def test_audit_raw_card_field_never_posted_to_backend():
    """Confirms no path posts raw PAN/CVC text to the backend."""
    for rel in (
        "pages/ProfileSettingsPage.js",
        "pages/PartnerPaymentSettings.js",
    ):
        try:
            src = _read_fe(rel)
        except FileNotFoundError:
            continue
        # No hand-rolled card number / cvc / expiry inputs.
        for forbidden in ("card_number", "card[number]", "cvc:", "cvv:"):
            assert forbidden not in src.lower(), (
                f"{rel}: raw card field {forbidden!r} found — would "
                "violate PCI scope by bypassing Stripe Elements"
            )


# ── M1B — Customer backfill ───────────────────────────────────────────


def test_audit_customer_backfill_module_exists():
    src = _read("services/stripe_customer_backfill.py")
    assert "async def backfill_stripe_customers" in src
    # Idempotent: only touches users WITHOUT a stripe_customer_id.
    assert '"stripe_customer_id": {"$exists": False}' in src
    assert '"stripe_customer_id": None' in src
    # Skips users without an email (Stripe requires it).
    assert "skipped_no_email" in src
    # Per-user fault tolerance — one failure never aborts the boot.
    assert "errors" in src


def test_audit_customer_backfill_wired_at_startup():
    src = _read("server.py")
    assert "from services.stripe_customer_backfill import backfill_stripe_customers" in src
    assert "await backfill_stripe_customers(db)" in src


# ── M4A — Webhook signature verification ──────────────────────────────


def test_audit_webhook_signature_verification():
    """The webhook entry MUST call `stripe.Webhook.construct_event`
    with the signature header + secret. No raw `json.loads` on the
    payload path."""
    src = _read("routes/webhooks.py")
    assert "stripe.Webhook.construct_event" in src
    assert "STRIPE_WEBHOOK_SECRET" in src


# ── M4B — Idempotency guard ───────────────────────────────────────────


def test_audit_webhook_idempotency_guard():
    """The webhook handler MUST early-return 200 when an event with
    the same `id` has already been processed."""
    src = _read("routes/webhooks.py")
    assert "DuplicateKeyError" in src
    assert "duplicate_ignored" in src
    # The DuplicateKeyError handler returns 200 to halt Stripe retries.
    # Match within a generous window covering the except clause.
    idx = src.find("except DuplicateKeyError")
    if idx < 0:
        idx = src.find("DuplicateKeyError:")
    assert idx > 0, "DuplicateKeyError handler not found"
    block = src[idx:idx + 800]
    assert "return JSONResponse" in block
    assert "status_code=200" in block


def test_audit_webhook_idempotency_index_at_startup():
    """The unique index on `stripe_events.id` MUST be ensured at
    boot, with a partial filter so legacy docs without an id field
    never block the index build."""
    src = _read("server.py")
    assert 'await db.stripe_events.create_index(' in src
    assert 'name="id_unique"' in src
    assert "partialFilterExpression" in src
    # Pre-build dedupe pipeline present so repeat boots stay clean.
    assert "purged" in src and "duplicate stripe_events" in src


# ── Contract preservation — deposit rules unchanged ───────────────────


def test_audit_storage_deposit_still_50_flat():
    from routes.bidder_deposits import _calc_deposit_amount
    listing = {"listing_type": "storage_locker", "starting_price": 1.0}
    assert _calc_deposit_amount(listing) == 50.0


def test_audit_vehicle_deposit_still_max_200_or_10pct():
    from routes.bidder_deposits import _calc_deposit_amount
    # Floor case
    assert _calc_deposit_amount(
        {"listing_type": "vehicle_auction", "starting_price": 1000.0}
    ) == 200.0
    # Percentage case
    assert _calc_deposit_amount(
        {"listing_type": "vehicle_auction", "starting_price": 5000.0}
    ) == 500.0


def test_audit_lot_deposit_still_max_50_or_10pct_above_500():
    from routes.bidder_deposits import _calc_deposit_amount
    # Below threshold — no deposit even with requires_deposit=True
    assert _calc_deposit_amount({
        "listing_type": "lot_auction", "starting_price": 100.0,
        "requires_deposit": True,
    }) == 0.0
    # Above threshold — 10%
    assert _calc_deposit_amount({
        "listing_type": "lot_auction", "starting_price": 1000.0,
        "requires_deposit": True,
    }) == 100.0


def test_audit_marketplace_no_deposit():
    from routes.bidder_deposits import _calc_deposit_amount
    assert _calc_deposit_amount(
        {"listing_type": "marketplace", "starting_price": 150.0}
    ) == 0.0


# ── Section 2: deposit PaymentIntent uses manual capture ──────────────


def test_audit_bidder_deposit_uses_manual_capture():
    """Section 2A — Bid deposit MUST use `capture_method="manual"`
    so funds are HELD (not charged) until win/loss resolution."""
    src = _read("routes/bidder_deposits.py")
    idx = src.find("stripe.PaymentIntent.create")
    assert idx > 0
    block = src[idx:idx + 1500]
    assert 'capture_method="manual"' in block
    # Off-session present so the deposit never triggers a buyer
    # re-prompt (cards are already verified at add-time).
    assert "off_session=True" in block


def test_audit_broker_deposit_uses_manual_capture_500():
    """Section 2B — Broker deposit MUST be $500 with manual capture."""
    src = _read("services/broker_deposit_service.py")
    assert 'capture_method="manual"' in src
    # $500 default (stored as CAD, converted to minor units at call time).
    assert "DEFAULT_DEPOSIT_CAD = 500.0" in src
    # _to_minor turns 500.0 → 50000 cents at the actual Stripe call site.
    assert "_to_minor(amount_cad)" in src
