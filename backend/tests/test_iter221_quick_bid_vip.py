"""
iter221 — Quick Bid VIP premium parity + Marketplace card responsive layout.

Backend coverage:
- `/api/payments/tax/calculate` returns the correct buyer_premium_rate per
  tier so the FE Quick Bid → BidConfirmationDialog can mirror it exactly.

FE coverage is via screenshot tooling (see /tmp/marketplace_card_iter221.jpg
+ /tmp/quick_bid_vip_iter221.jpg in the main agent's screenshot output).
"""
import pytest
import requests


def _api_base() -> str:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.strip().split("=", 1)[1].rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL missing")


BASE_URL = _api_base()


@pytest.mark.parametrize(
    "tier, expected_rate",
    [
        ("standard",  0.050),
        ("premium",   0.035),
        ("vip",       0.030),  # alias → vip_elite
        ("vip_elite", 0.030),
        ("free",      0.050),  # alias → standard
        ("basic",     0.050),  # legacy → standard
        ("",          0.050),  # empty → standard
    ],
)
def test_tax_calculate_returns_correct_buyer_premium_rate_per_tier(tier, expected_rate):
    """Backend MUST return the correct buyer_premium_rate for every tier the
    FE might submit. The Quick Bid BidConfirmationDialog mirrors this rate
    so any backend regression here surfaces immediately in the buyer's price."""
    r = requests.post(
        f"{BASE_URL}/api/payments/tax/calculate",
        json={
            "hammer_price": 100.0,
            "category": "general",
            "buyer_tier": tier,
            "seller_tier": "standard",
            "seller_is_business": True,
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "buyer_premium_rate" in body, f"missing buyer_premium_rate for tier={tier!r}"
    assert abs(body["buyer_premium_rate"] - expected_rate) < 1e-6, (
        f"tier={tier!r} expected rate={expected_rate}, got {body['buyer_premium_rate']}"
    )


def test_vip_premium_is_exactly_three_percent_of_hammer():
    """VIP buyers get 3.0% — locking down via direct cents math."""
    r = requests.post(
        f"{BASE_URL}/api/payments/tax/calculate",
        json={
            "hammer_price": 1000.0,
            "category": "general",
            "buyer_tier": "vip",
            "seller_tier": "standard",
            "seller_is_business": True,
        },
        timeout=15,
    )
    body = r.json()
    assert body["buyer_premium_rate"] == 0.03
    assert abs(body["buyer_premium"] - 30.0) < 1e-6, (
        f"VIP premium on $1000 hammer should be exactly $30.00, got {body['buyer_premium']}"
    )
