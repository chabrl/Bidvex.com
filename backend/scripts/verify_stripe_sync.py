#!/usr/bin/env python3
"""
iter329 — CI Stripe-Sync Drift Guard.

Verifies that the code-side mirror values in
  • services.pricing_config.SUBSCRIPTION_TIERS
  • services.subscription_service.SUBSCRIPTION_PRICES
match the live BidVex Stripe Price objects referenced by
  • services.subscription_service.STRIPE_PRICE_IDS

Exits 0 on full sync, exits 1 on any drift (so CI fails the build).

USAGE
-----
    STRIPE_API_KEY=sk_live_… python -m backend.scripts.verify_stripe_sync
    # or, if you've already loaded backend/.env:
    cd /app/backend && python scripts/verify_stripe_sync.py

CI INTEGRATION
--------------
Add to your deploy pipeline BEFORE `supervisorctl restart backend`:

    python /app/backend/scripts/verify_stripe_sync.py || exit 1

Any drift will print a clear "Stripe says $X, code says $Y" diff and
fail the build, forcing the operator to either:
    (a) update the Stripe Price object first, then mirror in code, OR
    (b) update the code mirror to match what Stripe already has.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Make backend/ importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env if STRIPE_API_KEY isn't already set (handles values containing spaces).
if "STRIPE_API_KEY" not in os.environ and "STRIPE_SECRET_KEY" not in os.environ:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import stripe  # noqa: E402

from services.pricing_config import SUBSCRIPTION_TIERS  # noqa: E402
from services.subscription_service import STRIPE_PRICE_IDS, SUBSCRIPTION_PRICES  # noqa: E402


# ─── Configuration ─────────────────────────────────────────────────────

stripe.api_key = (
    os.environ.get("STRIPE_API_KEY")
    or os.environ.get("STRIPE_SECRET_KEY")
    or ""
)


# Tiers we expect to be Stripe-backed (free is intentionally skipped).
PAID_TIERS: Tuple[str, ...] = ("premium", "vip", "partner_pro", "partner")


# ─── Drift detection ───────────────────────────────────────────────────


def _fetch_stripe_amount_cents(price_id: str) -> Tuple[int, str]:
    """Return (unit_amount_cents, currency) for a Stripe Price ID.
    Raises stripe.error.* on failure; the caller turns those into drift errors.
    """
    price = stripe.Price.retrieve(price_id)
    if price.unit_amount is None:
        raise RuntimeError(
            f"Price {price_id} has no unit_amount (tiered price?). Only flat prices supported."
        )
    return int(price.unit_amount), (price.currency or "").lower()


def check_drift() -> List[str]:
    """Return a list of human-readable drift messages.
    Empty list = perfect sync.
    """
    drifts: List[str] = []

    if not stripe.api_key:
        return [
            "❌ STRIPE_API_KEY is not set in the environment. Cannot reach Stripe — "
            "treating as drift to fail safe."
        ]

    for tier in PAID_TIERS:
        stripe_id = STRIPE_PRICE_IDS.get(tier)
        if not stripe_id:
            # No Stripe Price ID configured — informational, not a hard failure.
            print(f"   ⚪ {tier:<12}  no STRIPE_PRICE_IDS entry — skipped")
            continue

        # Mirror values in code.
        tiers_cents = SUBSCRIPTION_TIERS.get(tier, {}).get("amount_cents")
        prices_cents = SUBSCRIPTION_PRICES.get(tier, {}).get("amount")

        try:
            stripe_cents, stripe_currency = _fetch_stripe_amount_cents(stripe_id)
        except Exception as exc:
            drifts.append(
                f"❌ {tier}: failed to fetch Stripe Price {stripe_id} — {exc!s}"
            )
            continue

        # SUBSCRIPTION_TIERS check.
        if tiers_cents != stripe_cents:
            drifts.append(
                f"❌ {tier}: pricing_config.SUBSCRIPTION_TIERS says "
                f"{tiers_cents} cents, Stripe Price {stripe_id} says "
                f"{stripe_cents} cents ({stripe_currency.upper()}). "
                f"→ Update one of them."
            )
        # SUBSCRIPTION_PRICES check (allow None for free/basic).
        if prices_cents is not None and prices_cents != stripe_cents:
            drifts.append(
                f"❌ {tier}: subscription_service.SUBSCRIPTION_PRICES says "
                f"{prices_cents} cents, Stripe Price {stripe_id} says "
                f"{stripe_cents} cents ({stripe_currency.upper()}). "
                f"→ Update one of them."
            )
        if tiers_cents == stripe_cents and (prices_cents is None or prices_cents == stripe_cents):
            print(
                f"   ✅ {tier:<12}  code={tiers_cents:>6}¢   "
                f"stripe={stripe_cents:>6}¢   ({stripe_currency.upper()})"
            )

    return drifts


# ─── Entrypoint ────────────────────────────────────────────────────────


def main() -> int:
    print("BidVex Stripe-Sync Drift Guard (iter329)")
    print("=" * 70)
    drifts = check_drift()
    print("=" * 70)
    if drifts:
        print("\nDRIFT DETECTED — build should fail:")
        for d in drifts:
            print(f"  {d}")
        print(
            "\nResolution: Either update the Stripe Price object in the "
            "BidVex Stripe Dashboard, or update the mirror in code "
            "(pricing_config.SUBSCRIPTION_TIERS / "
            "subscription_service.SUBSCRIPTION_PRICES), then re-run."
        )
        return 1
    print("\n✅ All Stripe Price mirrors in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
