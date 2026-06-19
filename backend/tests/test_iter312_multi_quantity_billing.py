"""
iter312 — P0 Multi-Quantity Hammer Price Multiplier
====================================================

Locks in the financial-leak fix: when a listing has Quantity > 1 and an
auction closes, every part of the settlement engine must multiply the
per-unit hammer price by the won quantity before computing platform
fees, total due, and net payout.

Pre-iter312 (the bug):
  Quantity=2, final_price=$1.10 → Settle Payment modal showed
    hammer=$1.10, fee=$0.03, total=$1.13

Post-iter312 (the fix):
  Quantity=2, final_price=$1.10 → Settle Payment modal shows
    unit_hammer_price=$1.10, quantity=2,
    hammer_price=$2.20, fee=$0.06, total=$2.26, net_payout=$2.14

These tests assert the invariant across:
  • `_amounts()` direct unit tests (every code path computes the same
    multiplied total).
  • `_quantity()` clamps NULL / zero / non-numeric values to 1 so a
    bad listing record never zero-outs the charge.
  • `finalize_auction_payment` defense-in-depth: when no
    `hammer_override` is passed, it derives the gross from
    `listing.quantity` directly.
  • Live HTTP trace against the seller settlement panel for a
    Quantity=2 listing — proves the response shape carries
    `unit_hammer_price` + `quantity` + multiplied `hammer_price`.
  • The 2.5% platform fee is computed off the MULTIPLIED base, not
    the per-unit price (so platform revenue scales with quantity).
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv


pytestmark = pytest.mark.monetization

load_dotenv("/app/backend/.env")
BASE = (
    open("/app/frontend/.env")
    .read()
    .split("REACT_APP_BACKEND_URL=", 1)[1]
    .splitlines()[0]
    .strip()
)
API = f"{BASE}/api"

ADMIN_EMAIL, ADMIN_PASSWORD = "charbel911@gmail.com", "Anderosli123!@#"


def _login(email: str, pwd: str) -> str:
    for _ in range(2):
        r = requests.post(
            f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15
        )
        if r.status_code == 200:
            return r.json()["access_token"]
        if r.status_code == 429:
            time.sleep(18)
            continue
        raise AssertionError(f"login {email}: HTTP {r.status_code} — {r.text[:200]}")
    raise AssertionError(f"login {email} still rate-limited")


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASSWORD)}"}


@pytest.fixture(scope="module")
def admin_id():
    cli = MongoClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    admin = db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0, "id": 1})
    cli.close()
    assert admin, "admin user missing — re-seed via scripts/iter308_reseed_test_fixtures.py"
    return admin["id"]


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


# ─── Unit tests on `_amounts` ────────────────────────────────────────


def test_amounts_multiplies_hammer_by_quantity():
    """The P0 repro from image_1f5000.jpg: Quantity=2, hammer=$1.10."""
    from routes.settlement import _amounts
    result = _amounts({
        "final_price": 1.10,
        "quantity": 2,
        "buyer_taxes": 0,
    })
    assert result["unit_hammer_price"] == 1.10
    assert result["quantity"] == 2
    assert result["hammer_price"] == 2.20, (
        f"hammer_price must equal unit × qty (got {result['hammer_price']})"
    )
    # Platform fee is 2.5% of the MULTIPLIED base
    assert result["platform_fee"] == round(2.20 * 0.025, 2)  # 0.06 (2.5% of $2.20 = $0.055)
    assert result["total_due"] == 2.26
    assert result["net_payout"] == round(2.20 - 0.06, 2)


def test_amounts_quantity_1_matches_pre_iter312_behavior():
    """Backwards compat — quantity=1 listings behave exactly as
    before (no change for the 99% case)."""
    from routes.settlement import _amounts
    result = _amounts({
        "final_price": 100.00,
        "quantity": 1,
        "buyer_taxes": 0,
    })
    assert result["hammer_price"] == 100.0
    assert result["quantity"] == 1
    assert result["unit_hammer_price"] == 100.0
    assert result["platform_fee"] == 2.50  # 2.5% of 100
    assert result["total_due"] == 102.50


def test_amounts_quantity_missing_defaults_to_one():
    """Older `listings` docs may not carry a `quantity` field at all
    — fall back to 1, never crash."""
    from routes.settlement import _amounts
    result = _amounts({"final_price": 50.0})
    assert result["quantity"] == 1
    assert result["hammer_price"] == 50.0
    assert result["platform_fee"] == 1.25  # 2.5% of $50


def test_amounts_zero_or_negative_quantity_clamps_to_one():
    """A bad listing must NEVER zero-out the charge. Quantity=0 or
    negative is treated as 1 to avoid silent revenue loss."""
    from routes.settlement import _amounts
    for bad_qty in (0, -1, None, "not a number"):
        result = _amounts({"final_price": 5.0, "quantity": bad_qty})
        assert result["quantity"] == 1, f"bad quantity {bad_qty!r} not clamped to 1"
        assert result["hammer_price"] == 5.0
        assert result["total_due"] > 0


def test_amounts_large_quantity_scales_fee_linearly():
    """Quantity=100 on a $7.50 unit — platform fee should be 2.5% of
    $750, not $7.50."""
    from routes.settlement import _amounts
    result = _amounts({
        "final_price": 7.50,
        "quantity": 100,
        "buyer_taxes": 0,
    })
    assert result["hammer_price"] == 750.0
    assert result["platform_fee"] == 18.75  # 2.5% of 750
    assert result["total_due"] == 768.75


def test_amounts_quantity_won_takes_precedence_over_quantity():
    """Partial-quantity wins / batched lots may set `quantity_won`
    explicitly — that wins over the listing-level `quantity`."""
    from routes.settlement import _amounts
    result = _amounts({
        "final_price": 10.0,
        "quantity": 5,         # listed qty
        "quantity_won": 3,     # actually won
    })
    assert result["quantity"] == 3
    assert result["hammer_price"] == 30.0  # 10 × 3


def test_amounts_includes_taxes_after_multiplying(monkeypatch=None):
    """Taxes from the listing doc are added on top of the multiplied
    base — they must not themselves be multiplied (taxes are already
    in dollar terms, not per-unit)."""
    from routes.settlement import _amounts
    result = _amounts({
        "final_price": 50.0,
        "quantity": 2,
        "buyer_taxes": 5.0,
    })
    assert result["hammer_price"] == 100.0
    assert result["platform_fee"] == 2.50
    assert result["taxes"] == 5.0
    assert result["total_due"] == 107.50


# ─── Live HTTP trace — seller settlement panel ──────────────────────


@pytest.fixture
def multi_qty_listing(db, admin_id):
    """Seed an ENDED multi-quantity listing owned by admin so the
    /settlement/panel endpoint returns it."""
    listing_id = f"iter312-mq-{uuid.uuid4().hex[:10]}"
    buyer_id = "85b3ce59-f264-4d43-8d12-19b3449ec8b3"  # iter225buyer
    db.listings.insert_one({
        "id": listing_id,
        "title": "iter312 multi-qty repro",
        "description": "synthetic for the iter312 P0 fix",
        "category": "collectibles",
        "condition": "used",
        "status": "ended",
        "seller_id": admin_id,
        "user_id": admin_id,
        "user_email": ADMIN_EMAIL,
        "starting_price": 0.1,
        "current_bid": 1.10,
        "final_price": 1.10,
        "quantity": 2,
        "winner_id": buyer_id,
        "winner_user_id": buyer_id,
        "highest_bidder_id": buyer_id,
        "city": "Toronto",
        "region": "ON",
        "_seed_tag": "iter312",
    })
    yield listing_id
    db.listings.delete_one({"id": listing_id})


def test_settlement_panel_shows_multiplied_amounts(
    admin_headers, multi_qty_listing, db,
):
    """The exact bug repro — image_1f5000.jpg's $1.13 popup is now
    $2.26 with quantity multiplied."""
    r = requests.get(
        f"{API}/settlement/panel/{multi_qty_listing}",
        headers=admin_headers, timeout=20,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data["unit_hammer_price"] == 1.10, data
    assert data["quantity"] == 2, data
    assert data["hammer_price"] == 2.20, (
        f"hammer_price still leaking per-unit: {data}"
    )
    assert data["platform_fee"] == round(2.20 * 0.025, 2)  # 2.5% of multiplied base
    assert data["total_due"] == 2.26
    assert data["net_payout"] == round(2.20 - data["platform_fee"], 2)


def test_settle_context_shows_multiplied_amounts_for_winner(db, multi_qty_listing):
    """The winning buyer's settle-context endpoint returns the same
    multiplied amounts — the modal NEVER sees the per-unit number."""
    buyer_tok = _login("iter225buyer@bidvex.com", "TestBuyer225!")
    r = requests.get(
        f"{API}/settlement/settle-context/{multi_qty_listing}",
        headers={"Authorization": f"Bearer {buyer_tok}"}, timeout=20,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data.get("already_paid") is False
    assert data["unit_hammer_price"] == 1.10
    assert data["quantity"] == 2
    assert data["hammer_price"] == 2.20
    assert data["total_due"] == 2.26


def test_response_blocks_single_unit_fallback_leak(
    admin_headers, multi_qty_listing,
):
    """Even if a stale frontend asks for ?quantity=1, the SERVER must
    return the multiplied gross. There must be no way for a client
    to coerce the engine into the per-unit fallback."""
    # Server doesn't accept a quantity query param — it always reads
    # from the listing. Confirm by hitting with a bogus override:
    r = requests.get(
        f"{API}/settlement/panel/{multi_qty_listing}?quantity=1&hammer_price=1.10",
        headers=admin_headers, timeout=20,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    # Despite the bogus query string, server returns the multiplied total
    assert data["hammer_price"] == 2.20, (
        f"single-unit leak still possible via query coercion: {data}"
    )
    assert data["total_due"] == 2.26


# ─── Defense-in-depth: finalize_auction_payment honours quantity ─────


def test_finalize_auction_payment_multiplies_when_no_override():
    """Async unit test of the ledger writer's quantity coercion.
    When `hammer_override` is omitted, it must read `listing.quantity`
    and multiply `final_price` by it before computing payouts."""
    import services.payment_collection as pc

    captured = {}

    # Stub the heavy side-effect helpers so the function body returns
    # quickly. We're only asserting the `hammer` value it computes.
    async def fake_stamp(*args, **kwargs):
        return None

    async def fake_ensure_pickup_code(*a, **kw):
        captured["pickup_hammer"] = kw.get("hammer")
        return "PICK-1234"

    async def fake_process_payout(*a, **kw):
        captured["payout_amount"] = kw.get("net_amount")
        return {"status": "queued"}

    async def fake_issue_records(*a, **kw):
        captured["records_hammer"] = kw.get("hammer_price")
        return {"receipt_id": "r1", "statement_id": "s1"}

    async def fake_create_notification(*a, **kw):
        return None

    async def fake_enqueue_payout_pending(*a, **kw):
        return None

    # The Mongo writes inside _stamp / pickup_code etc go through a
    # collection name — we'll wire them out by monkeypatching at the
    # module import points used inside finalize_auction_payment.
    import unittest.mock as mock

    listing = {
        "id": "iter312-coverage-listing",
        "title": "iter312 coverage",
        "winner_user_id": "buyer-xx",
        "seller_id": "seller-xx",
        "final_price": 1.10,
        "quantity": 2,
        "current_bid": 1.10,
    }
    settlement = {
        "buyer_charge": {"stripe_pi": "pi_test", "amount": 2.26},
        "fee_breakdown": {
            "buyer_premium": 0.06, "buyer_taxes": 0,
            "buyer_total_charged": 2.26, "seller_commission": 0.06,
        },
    }

    fake_db = mock.MagicMock()
    fake_db.users.find_one = mock.AsyncMock(return_value={"email": "x"})
    fake_db.payment_methods.find_one = mock.AsyncMock(return_value=None)

    with mock.patch.object(pc, "_stamp", side_effect=fake_stamp), \
         mock.patch.object(pc, "_ensure_stripe_pickup_code", side_effect=fake_ensure_pickup_code), \
         mock.patch.object(pc, "_enqueue_payout_pending", side_effect=fake_enqueue_payout_pending), \
         mock.patch("services.seller_payouts.process_seller_payout", side_effect=fake_process_payout), \
         mock.patch("services.receipts.issue_transaction_records", side_effect=fake_issue_records), \
         mock.patch("services.notifications_i18n.create_notification", side_effect=fake_create_notification):
        asyncio.run(pc.finalize_auction_payment(
            fake_db, listing=listing, collection="listings",
            settlement=settlement, section="marketplace",
        ))

    # The ledger row's hammer must be the MULTIPLIED total (2.20),
    # not the per-unit final_price (1.10).
    assert captured.get("pickup_hammer") == 2.20, (
        f"pickup-code hammer leaked per-unit: {captured.get('pickup_hammer')}"
    )
    assert captured.get("records_hammer") == 2.20, (
        f"receipt hammer_price leaked per-unit: {captured.get('records_hammer')}"
    )


# ─── Source-integrity ───────────────────────────────────────────────


def test_settlement_module_contains_iter312_marker():
    src = Path("/app/backend/routes/settlement.py").read_text()
    assert "iter312" in src.lower()
    # `_amounts` must produce the multiplied figures and expose
    # `unit_hammer_price` + `quantity` to the response.
    assert '"unit_hammer_price"' in src
    assert '"quantity"' in src
    assert "_quantity(doc)" in src
    assert "unit_hammer * quantity" in src


def test_payment_collection_module_contains_iter312_marker():
    src = Path("/app/backend/services/payment_collection.py").read_text()
    assert "iter312" in src.lower()
    assert 'listing.get("quantity_won") or listing.get("quantity")' in src
    assert "unit * quantity" in src
