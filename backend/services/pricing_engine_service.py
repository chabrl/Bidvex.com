"""
iter210 Step 3 — Admin-Controlled Pricing Engine

Replaces the hardcoded $200/yr base + LAUNCH50 coupon with admin-editable
settings stored in MongoDB collection `pricing_settings`. Each key is one
fee surface (e.g. "vehicle_dealer_annual_fee", "partner_annual_fee").

Sample document:
    {
      "key": "vehicle_dealer_annual_fee",
      "base_price_cad": 200.00,
      "launch_discount_percent": 50,
      "launch_window_days": 90,
      "launch_start_date": datetime,
      "launch_cutoff_date": launch_start_date + launch_window_days,
      "stripe_product_id": "prod_xxx",
      "stripe_price_id":   "price_xxx",
      "stripe_coupon_id":  "LAUNCH50_v2",
      "updated_at": datetime,
      "updated_by": admin_email
    }

When admin saves new settings:
  * base_price_cad changed   → create a NEW Stripe Price (idempotent — same price-spec re-uses)
  * launch_discount_percent  → create a NEW Stripe Coupon if not idempotent
  * launch_window_days       → recompute launch_cutoff_date
EXISTING dealer subscriptions are GRANDFATHERED — their Subscription.items[0].price
is NOT migrated when the admin bumps prices.

`is_within_launch_window(db, key)` is the single source of truth that callers
ask before deciding whether to apply the coupon at subscription creation.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import stripe

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_API_KEY")

PRODUCT_DEFINITIONS = {
    "vehicle_dealer_annual_fee": {
        "product_name": "BidVex Vehicle Dealer Platform Access",
        "product_metadata_tag": "vehicle_dealer_subscription",
        "currency": "cad",
        "interval": "year",
        "default_base_price_cad": 200.0,
        "default_launch_discount_percent": 50,
        "default_launch_window_days": 90,
    },
    "partner_annual_fee": {
        "product_name": "BidVex Partner Platform Access",
        "product_metadata_tag": "partner_subscription",
        "currency": "cad",
        "interval": "year",
        "default_base_price_cad": 100.0,
        "default_launch_discount_percent": 50,
        "default_launch_window_days": 90,
    },
}


# ─── Read / Update ─────────────────────────────────────────────────────────
async def get_pricing(db, key: str) -> dict:
    """Return the persisted pricing doc, seeding defaults on first read."""
    if key not in PRODUCT_DEFINITIONS:
        raise ValueError(f"unknown pricing key: {key}")
    doc = await db.pricing_settings.find_one({"key": key}, {"_id": 0})
    if doc:
        return doc

    # Seed defaults
    defs = PRODUCT_DEFINITIONS[key]
    now = datetime.now(timezone.utc)
    doc = {
        "key": key,
        "base_price_cad": defs["default_base_price_cad"],
        "launch_discount_percent": defs["default_launch_discount_percent"],
        "launch_window_days": defs["default_launch_window_days"],
        "launch_start_date": now,
        "launch_cutoff_date": now + timedelta(days=defs["default_launch_window_days"]),
        "stripe_product_id": None,
        "stripe_price_id": None,
        "stripe_coupon_id": None,
        "updated_at": now,
        "updated_by": "system",
    }
    await db.pricing_settings.insert_one(doc)
    return doc


def effective_price(doc: dict) -> float:
    """Return the CAD price after the launch discount is applied."""
    base = float(doc.get("base_price_cad") or 0)
    pct = float(doc.get("launch_discount_percent") or 0)
    discount = base * (pct / 100.0)
    return round(max(0.0, base - discount), 2)


def is_within_launch_window(doc: dict, now: datetime | None = None) -> bool:
    """The Single Truth function: should a NEW subscription get the launch coupon?"""
    cutoff = doc.get("launch_cutoff_date")
    if not cutoff:
        return False
    if now is None:
        now = datetime.now(timezone.utc)
    if isinstance(cutoff, str):
        cutoff = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    # Mongo strips tzinfo on round-trip → normalize to UTC
    if isinstance(cutoff, datetime) and cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return now <= cutoff


# ─── Stripe wiring ────────────────────────────────────────────────────────
async def _ensure_product_id(db, key: str, doc: dict) -> str:
    if doc.get("stripe_product_id"):
        return doc["stripe_product_id"]
    defs = PRODUCT_DEFINITIONS[key]
    tag = defs["product_metadata_tag"]
    # Idempotency: re-use any existing Stripe Product with our metadata tag
    for p in stripe.Product.list(limit=100).data:
        if (p.metadata or {}).get("bidvex_role") == tag:
            doc["stripe_product_id"] = p.id
            return p.id
    p = stripe.Product.create(name=defs["product_name"], metadata={"bidvex_role": tag})
    doc["stripe_product_id"] = p.id
    return p.id


async def _ensure_price(db, key: str, doc: dict) -> str:
    """Create a Stripe Price matching the current base_price_cad. Idempotent."""
    defs = PRODUCT_DEFINITIONS[key]
    product_id = await _ensure_product_id(db, key, doc)
    base_cents = int(round(float(doc["base_price_cad"]) * 100))

    # Look up existing prices on this product
    for pr in stripe.Price.list(product=product_id, limit=100).data:
        r = pr.recurring or {}
        if (pr.unit_amount == base_cents
                and pr.currency == defs["currency"]
                and r.get("interval") == defs["interval"]
                and pr.active):
            doc["stripe_price_id"] = pr.id
            return pr.id

    pr = stripe.Price.create(
        product=product_id,
        unit_amount=base_cents,
        currency=defs["currency"],
        recurring={"interval": defs["interval"]},
        metadata={"bidvex_role": defs["product_metadata_tag"], "base_price_cad": str(doc["base_price_cad"])},
    )
    doc["stripe_price_id"] = pr.id
    return pr.id


async def _ensure_coupon(db, key: str, doc: dict) -> str:
    """Create / reuse a Stripe Coupon with the current launch_discount_percent.

    Coupon IDs are versioned by percent so a percent change yields a NEW coupon
    rather than mutating an existing one (Stripe coupons are immutable on percent).
    """
    pct = float(doc.get("launch_discount_percent") or 0)
    if pct <= 0:
        doc["stripe_coupon_id"] = None
        return ""

    # Versioned ID: "LAUNCH50_VDA" / "LAUNCH75_VDA"
    short_key = "VDA" if key == "vehicle_dealer_annual_fee" else "PRT"
    coupon_id = f"LAUNCH{int(pct)}_{short_key}"
    try:
        existing = stripe.Coupon.retrieve(coupon_id)
        doc["stripe_coupon_id"] = existing.id
        return existing.id
    except stripe.InvalidRequestError:
        c = stripe.Coupon.create(
            id=coupon_id,
            percent_off=pct,
            duration="forever",
            name=f"BidVex Launch {int(pct)}% Discount ({short_key})",
            metadata={"bidvex_role": PRODUCT_DEFINITIONS[key]["product_metadata_tag"]},
        )
        doc["stripe_coupon_id"] = c.id
        return c.id


async def update_pricing(
    db,
    key: str,
    *,
    base_price_cad: float | None = None,
    launch_discount_percent: float | None = None,
    launch_window_days: int | None = None,
    admin_email: str | None = None,
) -> dict:
    """Persist updated settings and ensure matching Stripe objects exist."""
    doc = await get_pricing(db, key)
    changed = []
    if base_price_cad is not None and float(base_price_cad) != float(doc["base_price_cad"]):
        if float(base_price_cad) < 0:
            raise ValueError("base_price_cad must be >= 0")
        doc["base_price_cad"] = float(base_price_cad)
        doc["stripe_price_id"] = None  # force a new Stripe Price
        changed.append("base_price_cad")
    if launch_discount_percent is not None and float(launch_discount_percent) != float(doc["launch_discount_percent"]):
        if not (0 <= float(launch_discount_percent) <= 100):
            raise ValueError("launch_discount_percent must be 0..100")
        doc["launch_discount_percent"] = float(launch_discount_percent)
        doc["stripe_coupon_id"] = None  # force a new Stripe Coupon
        changed.append("launch_discount_percent")
    if launch_window_days is not None and int(launch_window_days) != int(doc["launch_window_days"]):
        if int(launch_window_days) < 0:
            raise ValueError("launch_window_days must be >= 0")
        doc["launch_window_days"] = int(launch_window_days)
        start = doc.get("launch_start_date") or datetime.now(timezone.utc)
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        doc["launch_cutoff_date"] = start + timedelta(days=int(launch_window_days))
        changed.append("launch_window_days")

    # Always reconcile Stripe (creates objects on first run)
    await _ensure_price(db, key, doc)
    await _ensure_coupon(db, key, doc)

    doc["updated_at"] = datetime.now(timezone.utc)
    doc["updated_by"] = admin_email or "system"
    await db.pricing_settings.update_one(
        {"key": key}, {"$set": doc}, upsert=True,
    )
    return {**doc, "changed_fields": changed, "effective_price_cad": effective_price(doc)}


# ─── Public read with effective_price annotation ──────────────────────────
async def read_pricing(db, key: str) -> dict:
    doc = await get_pricing(db, key)
    return {
        **doc,
        "effective_price_cad": effective_price(doc),
        "is_within_launch_window": is_within_launch_window(doc),
    }
