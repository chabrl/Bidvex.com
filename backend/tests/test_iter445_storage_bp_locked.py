"""
iter445 — Storage buyer's premium is FIXED PLATFORM POLICY (5 %)
=================================================================
Enforces (and regression-tests):

  1. `storage_pricing.calculate_storage_pricing` returns exactly 5 %
     for card / cash / e-transfer paths at any hammer.
  2. `fee_calculator.calculate_fee` on `storage_facility` returns
     buyer_premium_rate=0.05 and seller_commission=0 for every payment
     method (facility NEVER charged, iter443 flip).
  3. `services.listings_service.apply_partner_tags` DISCARDS a client-
     sent BP override on a storage_locker listing (sets
     custom_buyer_premium_rate=None).
  4. The `PUT /api/listings/{id}` update path DISCARDS any BP override
     on a storage_locker listing (silently coerces to None).
  5. Legacy reconciliation script `iter445_reconcile_storage_bp.py`
     is idempotent — running it twice makes no additional changes.
"""
import os
import sys
import asyncio

import pytest

sys.path.insert(0, "/app/backend")

from services.storage_pricing import calculate_storage_pricing, BUYER_PREMIUM_RATE
from services.fee_calculator import calculate_fee, STORAGE_FACILITY_RATE
from services.listings_service import apply_partner_tags


# ─────────────────────────────────────────────────────────────
# 1) storage_pricing enforces 5 % on every payment method
# ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("payment", ["stripe", "cash", "etransfer"])
@pytest.mark.parametrize("hammer, province, expected_bp", [
    (100, "QC", 5.00),
    (800, "QC", 40.00),
    (1500, "ON", 75.00),
    (2500, "BC", 125.00),
    (10, "AB", 0.50),
])
def test_storage_pricing_is_locked_to_5pct(payment, hammer, province, expected_bp):
    p = calculate_storage_pricing(hammer, province, payment, deposit_amount=0)
    assert p["buyer_invoice"]["platform_fee"] == pytest.approx(expected_bp, abs=0.01)
    assert p["buyer_invoice"]["platform_fee_rate"] == "5.0%"
    # Facility NEVER charged.
    assert p["facility_invoice"]["facility_owes_bidvex"] == 0.0
    assert p["facility_invoice"]["facility_receives"] == pytest.approx(hammer, abs=0.01)


def test_buyer_premium_rate_constant():
    """The single source of truth for the storage BP rate is 5 %."""
    from decimal import Decimal
    assert BUYER_PREMIUM_RATE == Decimal("0.05")
    assert STORAGE_FACILITY_RATE == Decimal("0.050")


# ─────────────────────────────────────────────────────────────
# 2) fee_calculator.calculate_fee — storage seller_type → 5 % BP
# ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("payment", ["stripe", "cash", "etransfer"])
def test_calculate_fee_storage_always_5pct(payment):
    fee = calculate_fee(
        hammer_price=100.0,
        auction_type="storage",
        seller_account_type="storage_facility",
        buyer_account_type="individual",
        buyer_tier="vip_elite",       # MUST NOT change storage BP
        payment_method=payment,
        buyer_province="QC",
        facility_province="QC",
    )
    assert fee["buyer_premium"] == 5.00
    assert fee["buyer_premium_rate"] == 0.05
    assert fee["seller_commission"] == 0.00
    assert fee["seller_commission_rate"] == 0.00
    assert fee["seller_payout"] == 100.00


# ─────────────────────────────────────────────────────────────
# 3) apply_partner_tags DISCARDS storage_locker BP override
# ─────────────────────────────────────────────────────────────
class _StubUser:
    id = "user-storage-1"


class _StubDB:
    """Minimal Motor-look-alike returning a verified storage-facility user
    with zero outstanding commissions (so `apply_partner_tags` proceeds
    past the manual-settlement gate)."""

    class _Users:
        @staticmethod
        async def find_one(query, projection=None):
            return {
                "id": "user-storage-1",
                "is_partner": False,
                "is_storage_facility": True,
                "partner_verification_status": None,
                "province": "QC",
                "city": "Montreal",
                "seller_account_type": "storage_facility",
                "is_verified_firm": False,
                "outstanding_manual_commission_cad": 0.0,
            }

    class _EmptyCursor:
        async def to_list(self, *_args, **_kwargs):
            return []

    class _EmptyColl:
        def aggregate(self, *_args, **_kwargs):
            return _StubDB._EmptyCursor()

        async def find_one(self, *_args, **_kwargs):
            return None

    users = _Users()

    def __getitem__(self, name):
        # Any collection lookup other than `users` returns an empty stub.
        return self._EmptyColl()


@pytest.mark.asyncio
async def test_apply_partner_tags_drops_bp_on_storage_locker_by_category():
    listing = {
        "category": "storage_locker",
        "region": "QC",
        "city": "Montreal",
    }
    await apply_partner_tags(_StubDB(), _StubUser(), listing, buyers_premium_rate=0.15)
    assert listing["custom_buyer_premium_rate"] is None
    assert "buyers_premium_percent" not in listing


@pytest.mark.asyncio
async def test_apply_partner_tags_drops_bp_on_storage_locker_by_listing_type():
    listing = {
        "listing_type": "storage_locker",
        "region": "QC",
        "city": "Montreal",
    }
    await apply_partner_tags(_StubDB(), _StubUser(), listing, buyers_premium_rate=0.20)
    assert listing["custom_buyer_premium_rate"] is None


# ─────────────────────────────────────────────────────────────
# 4) End-to-end through the running server — PUT /api/listings/{id}
#     silently drops a BP override on a storage listing.
# ─────────────────────────────────────────────────────────────
import httpx

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def token():
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                   timeout=20)
    r.raise_for_status()
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _make_storage_listing(headers) -> str:
    """Create a storage_locker listing via the general listings endpoint
    and return its id. Uses the admin's super_admin role to bypass any
    facility-verification gate."""
    from datetime import datetime, timezone, timedelta
    payload = {
        "title": f"iter445 storage lock test {datetime.now().timestamp()}",
        "description": "iter445 test",
        "category": "storage_locker",
        "listing_type": "storage_locker",
        "condition": "as_is",
        "starting_price": 100,
        "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "country": "CA",
        "region": "QC",
        "city": "Montreal",
        "postal_code": "H1A 1A1",
        "location": "Montreal, QC",
        "images": ["https://example.com/img.jpg"],
        "quantity": 1,
        # Intentionally send a 15 % BP override — server must DISCARD it.
        "buyers_premium_rate": 0.15,
        "storage_metadata": {"facility_name": "T", "unit_number": "A", "unit_size_sqft": 25},
    }
    r = httpx.post(f"{API_URL}/api/listings", headers=headers, json=payload, timeout=25)
    r.raise_for_status()
    return r.json()["id"]


def test_create_storage_listing_discards_bp_override(headers):
    listing_id = _make_storage_listing(headers)
    # Read back the listing — custom_buyer_premium_rate MUST be None.
    r = httpx.get(f"{API_URL}/api/listings/{listing_id}", headers=headers, timeout=15)
    d = r.json()
    assert d.get("custom_buyer_premium_rate") in (None, 0), \
        f"Expected custom_buyer_premium_rate to be discarded on storage, got {d.get('custom_buyer_premium_rate')}"


def test_update_storage_listing_discards_bp_override(headers):
    listing_id = _make_storage_listing(headers)
    # Attempt to set a 20 % BP on the storage listing after creation.
    r = httpx.put(
        f"{API_URL}/api/listings/{listing_id}",
        headers=headers,
        json={"buyers_premium_rate": 0.20},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("custom_buyer_premium_rate") in (None, 0)


def test_fee_breakdown_returns_5pct_on_storage(headers):
    listing_id = _make_storage_listing(headers)
    r = httpx.get(f"{API_URL}/api/checkout/fee-breakdown?listing_id={listing_id}",
                  headers=headers, timeout=15)
    d = r.json()
    # BP rate must be exactly 5 % (0.05).
    assert d.get("buyer_premium_rate") == pytest.approx(0.05, abs=1e-6), \
        f"Expected 0.05 buyer_premium_rate on storage, got {d.get('buyer_premium_rate')}"
    # BP amount on a $100 hammer = $5.
    assert d.get("buyer_premium") == pytest.approx(5.0, abs=0.01)


# ─────────────────────────────────────────────────────────────
# 5) Reconciliation script is idempotent
# ─────────────────────────────────────────────────────────────
def test_reconciliation_script_is_idempotent():
    import subprocess
    r1 = subprocess.run(
        ["python", "/app/backend/scripts/iter445_reconcile_storage_bp.py"],
        capture_output=True, text=True, timeout=30,
    )
    assert r1.returncode == 0
    r2 = subprocess.run(
        ["python", "/app/backend/scripts/iter445_reconcile_storage_bp.py"],
        capture_output=True, text=True, timeout=30,
    )
    assert r2.returncode == 0
    # Second run must have found ZERO rows to fix.
    assert "0 rows" in r2.stdout or "on 0 rows" in r2.stdout
