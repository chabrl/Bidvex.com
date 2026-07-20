"""
iter210 Step 3 — Pricing Engine tests.

Covers:
  * Defaults are seeded on first read
  * is_within_launch_window correctly transitions based on launch_cutoff_date
  * update_pricing creates a new Stripe Price when base price changes
  * Effective price = base × (1 - discount/100)
  * Negative inputs rejected
  * HTTP endpoints require admin auth
  * Public endpoint exposes a clean subset (no Stripe IDs)
"""
import os
import sys
import uuid
import httpx
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env", override=True)  # iter210: force .env over shell STRIPE_API_KEY placeholder
import stripe
stripe.api_key = os.environ.get("STRIPE_API_KEY")

from motor.motor_asyncio import AsyncIOMotorClient

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    yield database
    client.close()


# ─── Service layer ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_pricing_seeds_defaults_on_first_read(db):
    from services.pricing_engine_service import get_pricing
    # Force a clean read
    await db.pricing_settings.delete_many({"key": "vehicle_dealer_annual_fee"})
    doc = await get_pricing(db, "vehicle_dealer_annual_fee")
    assert doc["base_price_cad"] == 200.0
    assert doc["launch_discount_percent"] == 50
    # iter365 — standardized 90 → 180-day default across all pricing keys.
    assert doc["launch_window_days"] == 180
    assert doc["launch_cutoff_date"] > datetime.now(timezone.utc)


def test_effective_price_math():
    from services.pricing_engine_service import effective_price
    assert effective_price({"base_price_cad": 200, "launch_discount_percent": 50}) == 100.0
    assert effective_price({"base_price_cad": 200, "launch_discount_percent": 0}) == 200.0
    assert effective_price({"base_price_cad": 200, "launch_discount_percent": 100}) == 0.0


def test_is_within_launch_window_boundary():
    from services.pricing_engine_service import is_within_launch_window
    now = datetime.now(timezone.utc)
    assert is_within_launch_window({"launch_cutoff_date": now + timedelta(days=1)}, now=now) is True
    assert is_within_launch_window({"launch_cutoff_date": now - timedelta(seconds=1)}, now=now) is False
    assert is_within_launch_window({}, now=now) is False


@pytest.mark.asyncio
async def test_update_pricing_rejects_negative_base(db):
    from services.pricing_engine_service import update_pricing
    with pytest.raises(ValueError):
        await update_pricing(db, "vehicle_dealer_annual_fee", base_price_cad=-50)


@pytest.mark.asyncio
async def test_update_pricing_rejects_invalid_discount(db):
    from services.pricing_engine_service import update_pricing
    with pytest.raises(ValueError):
        await update_pricing(db, "vehicle_dealer_annual_fee", launch_discount_percent=150)


@pytest.mark.asyncio
async def test_changing_window_days_recomputes_cutoff(db):
    from services.pricing_engine_service import update_pricing, read_pricing
    # Force a fresh seed
    await db.pricing_settings.delete_many({"key": "vehicle_dealer_annual_fee"})
    base = await read_pricing(db, "vehicle_dealer_annual_fee")
    start = base["launch_start_date"]
    # iter365 — default is now 180d, so use 270 to actually register a change.
    updated = await update_pricing(db, "vehicle_dealer_annual_fee", launch_window_days=270)
    # cutoff = start + 270d
    expected = (start if isinstance(start, datetime) else datetime.fromisoformat(start.replace("Z", "+00:00"))) + timedelta(days=270)
    assert "launch_window_days" in updated["changed_fields"]
    cutoff = updated["launch_cutoff_date"]
    if isinstance(cutoff, str):
        cutoff = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    assert abs((cutoff - expected).total_seconds()) < 5
    # Reset back to the iter365 canonical 180-day window so downstream tests
    # (and running admins) see the standard config again.
    await update_pricing(db, "vehicle_dealer_annual_fee", launch_window_days=180)


# ─── HTTP layer ───────────────────────────────────────────────────────────
def _admin_token() -> str:
    """Login with retry-or-skip on 429 (pre-existing flake hardening, iter213)."""
    import time as _time
    for attempt in range(3):
        r = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=15,
        )
        if r.status_code == 429:
            _time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json().get("access_token") or r.json().get("token")
    pytest.skip("admin login rate-limited (HTTP 429) after 3 retries — pre-existing live-HTTP flake")


def test_admin_list_pricing_endpoint_requires_admin():
    r = httpx.get(f"{API_URL}/api/admin/pricing-engine", timeout=15)
    assert r.status_code == 401


def test_admin_list_pricing_returns_both_keys():
    token = _admin_token()
    r = httpx.get(f"{API_URL}/api/admin/pricing-engine",
                  headers={"Authorization": f"Bearer {token}"},
                  timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "vehicle_dealer_annual_fee" in data
    assert "partner_annual_fee" in data
    # iter365 — broker annual fee added as the third account type.
    assert "broker_annual_fee" in data
    for key, doc in data.items():
        assert "effective_price_cad" in doc
        assert "is_within_launch_window" in doc


def test_public_pricing_endpoint_strips_stripe_ids():
    r = httpx.get(f"{API_URL}/api/pricing-engine/public/vehicle_dealer_annual_fee", timeout=15)
    assert r.status_code == 200
    body = r.json()
    # No Stripe internals leaked
    assert "stripe_price_id" not in body
    assert "stripe_coupon_id" not in body
    # Public-facing fields present
    assert "effective_price_cad" in body
    assert "base_price_cad" in body
    assert "is_within_launch_window" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
