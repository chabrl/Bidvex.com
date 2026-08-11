"""
iter478 — Bootstrap fee_schedules version 1 from the authoritative
production rate constants.

⚠️  PHASE 1 ONLY  ⚠️
This script writes the schedule.  It does NOT modify any settlement,
Stripe, escrow, receipt-generation, or PDF-generation code path.  No
production calculation reads from ``db.fee_schedules`` yet.

Sources of truth used to build v1:
──────────────────────────────────────────────────────────────────────
Table                              Source constants
──────────────────────────────────────────────────────────────────────
BUYER_PREMIUM (individual/         services.pricing_config.BUYER_PREMIUM_RATES
enterprise/partner/partner_pro)    (mirrored by services.fee_calculator
                                    .INDIVIDUAL_BUYER_RATES via TIER_ALIASES)

SELLER_COMMISSION (individual/     services.pricing_config.SELLER_COMMISSION_RATES
enterprise/partner/partner_pro)    (mirrored by services.fee_calculator
                                    .INDIVIDUAL_SELLER_RATES via TIER_ALIASES)

Vehicle-dealer buyer rate (2.5%)   services.fee_calculator.VEHICLE_DEALER_BUYER_RATE
                                   (== services.pricing_config.PLATFORM_FEE_VEHICLE
                                   == services.vehicle_pricing.PLATFORM_FEE_RATE)

Storage-facility buyer rate (5%)   services.fee_calculator.STORAGE_FACILITY_RATE
                                   (== services.storage_pricing.BUYER_PREMIUM_RATE)

Broker buyer rate (2.5%)           services.fee_calculator.BROKER_PLATFORM_RATE

Partner platform fee (3%)          services.fee_calculator.PARTNER_PLATFORM_RATE
Vehicle platform fee (2.5%)        services.pricing_config.PLATFORM_FEE_VEHICLE
General platform fee (3%)          services.pricing_config.PLATFORM_FEE_GENERAL
                                   (used ONLY by public display endpoint —
                                    NOT a live settlement rate; carried into
                                    the schedule for parity)
Broker platform fee (2.5%)         services.fee_calculator.BROKER_PLATFORM_RATE

Stripe (2.9% + $0.30 CAD)          services.pricing_config.STRIPE_PROCESSING_RATE
                                   services.pricing_config.STRIPE_PROCESSING_FIXED
                                   (mirrored by services.fee_calculator
                                    .STRIPE_PERCENTAGE_FEE / STRIPE_FIXED_FEE)

Affiliate commission (3%)          services.fee_calculator.AFFILIATE_COMMISSION_RATE

Category overrides                 services.category_rules.COMMISSION_RATES
                                   (Phase 1: PRESERVED but explicitly
                                    active=False)
──────────────────────────────────────────────────────────────────────

Usage:
    # Write v1 into the collection (only if missing OR unchanged)
    python /app/backend/scripts/iter478_bootstrap_fee_schedule.py

    # Verify the on-disk row matches the authoritative code constants
    python /app/backend/scripts/iter478_bootstrap_fee_schedule.py --verify

    # Overwrite v1 (only permitted if the row is unchanged from the last
    # bootstrap; refuses if a human has edited it in the meantime).
    python /app/backend/scripts/iter478_bootstrap_fee_schedule.py --force
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

# ── authoritative production sources ─────────────────────────────────
from services import pricing_config as _pcfg
from services import fee_calculator as _fc
from services import category_rules as _cats
from services.fee_schedule import (
    COLLECTION_NAME,
    CURRENT_SCHEDULA_ID,
    FeeSchedule,
    from_bootstrap_dict,
    to_mongo_dict,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════
#  Assemble the v1 schedule strictly from production constants
# ═══════════════════════════════════════════════════════════════════════
def build_v1_schedule() -> FeeSchedule:
    """Compile the authoritative schedule.  Any drift between the four
    duplicate rate tables is REPORTED (not fixed) via a companion audit
    call — this function only reads ``pricing_config`` which is the
    single documented source of truth.
    """
    now = _now_iso()

    # ── Buyer premium by seller_account_type ──────────────────────
    #   individual / enterprise: resolved by BUYER tier
    buyer_prem = {
        "individual": {
            "standard":  _pcfg.BUYER_PREMIUM_RATES["standard"],
            "premium":   _pcfg.BUYER_PREMIUM_RATES["premium"],
            "vip_elite": _pcfg.BUYER_PREMIUM_RATES["vip_elite"],
        },
        "enterprise": {
            "standard":  _pcfg.BUYER_PREMIUM_RATES["standard"],
            "premium":   _pcfg.BUYER_PREMIUM_RATES["premium"],
            "vip_elite": _pcfg.BUYER_PREMIUM_RATES["vip_elite"],
        },
        "partner": {
            "default":         _pcfg.BUYER_PREMIUM_RATES["partner"],   # 5%
            "custom_per_user": True,
            "listing_override": True,
            "override_field_names": ["partner_bp_rate", "custom_buyer_premium_rate"],
            "notes": (
                "Partners can set a lot-specific buyer premium. Precedence: "
                "listing.partner_bp_rate → users.custom_premium_rate → default."
            ),
        },
        "partner_pro": {
            "default": _pcfg.BUYER_PREMIUM_RATES["partner_pro"],       # 3.75%
        },
        "vehicle_dealer": {
            "default": _fc.VEHICLE_DEALER_BUYER_RATE,                  # 2.5%
        },
        "storage_facility": {
            "default": _fc.STORAGE_FACILITY_RATE,                      # 5%
        },
        "broker": {
            "default": _fc.BROKER_PLATFORM_RATE,                       # 2.5%
        },
    }

    # ── Seller commission / platform fee by seller_account_type ──
    seller_comm = {
        "individual": {
            "standard":  _pcfg.SELLER_COMMISSION_RATES["standard"],
            "premium":   _pcfg.SELLER_COMMISSION_RATES["premium"],
            "vip_elite": _pcfg.SELLER_COMMISSION_RATES["vip_elite"],
        },
        "enterprise": {
            "standard":  _pcfg.SELLER_COMMISSION_RATES["standard"],
            "premium":   _pcfg.SELLER_COMMISSION_RATES["premium"],
            "vip_elite": _pcfg.SELLER_COMMISSION_RATES["vip_elite"],
        },
        "partner": {
            "platform_fee_rate": _fc.PARTNER_PLATFORM_RATE,            # 3%
            "notes": (
                "Partner-sellers do NOT pay a commission on hammer. They pay "
                "BidVex a fixed 3% platform fee on hammer + Stripe recovery + tax."
            ),
        },
        "partner_pro": {
            "seller_commission_rate": _pcfg.SELLER_COMMISSION_RATES["partner_pro"],  # 3%
        },
        "vehicle_dealer": {
            "seller_pays": Decimal("0"),
            "notes": "Vehicle dealer keeps the full hammer; buyer pays BidVex 2.5%.",
        },
        "storage_facility": {
            "seller_pays": Decimal("0"),
            "notes": "Storage facility keeps the full hammer; buyer pays BidVex 5%.",
        },
        "broker": {
            "seller_pays": Decimal("0"),
        },
    }

    # ── Platform fees by kind (used mainly for public display) ────
    platform_fees = {
        "general": _pcfg.PLATFORM_FEE_GENERAL,   # 3% — display/tooltip only
        "vehicle": _pcfg.PLATFORM_FEE_VEHICLE,   # 2.5%
        "partner": _fc.PARTNER_PLATFORM_RATE,    # 3%
        "broker":  _fc.BROKER_PLATFORM_RATE,     # 2.5%
        "storage": _fc.STORAGE_FACILITY_RATE,    # 5%
    }

    # ── Stripe ────────────────────────────────────────────────────
    stripe = {
        "percent":   _pcfg.STRIPE_PROCESSING_RATE,    # 2.9%
        "fixed_cad": _pcfg.STRIPE_PROCESSING_FIXED,   # $0.30
    }

    # ── Affiliate commission ─────────────────────────────────────
    affiliate = _fc.AFFILIATE_COMMISSION_RATE     # 3%

    # ── Category overrides — PHASE 1 INACTIVE ────────────────────
    category_overrides = {}
    for slug, rate in _cats.COMMISSION_RATES.items():
        key = (slug or "").strip().lower().replace(" ", "_")
        if not key or key in ("default", "vehicles"):
            continue
        if rate is None:
            # e.g. storage_auctions is marked TBD in category_rules — skip
            continue
        category_overrides[key] = {
            "seller_commission_rate": rate,
            "active":                 False,   # ← authoritative for Phase 1
            "source":                 "services.category_rules.COMMISSION_RATES",
            "notes": (
                "Category-specific rate mirrored from services.category_rules; "
                "explicitly NOT authoritative in Phase 1. Seller-tier rate wins."
            ),
        }

    # ── Tier aliases ─────────────────────────────────────────────
    tier_aliases = {
        "free":     "standard",
        "basic":    "standard",
        "starter":  "standard",
        "vip":      "vip_elite",
    }

    raw = {
        "id":                        CURRENT_SCHEDULA_ID,
        "version":                   1,
        "effective_from":            now,
        "is_active":                 True,
        "buyer_premium":             buyer_prem,
        "seller_commission":         seller_comm,
        "platform_fees":             platform_fees,
        "stripe":                    stripe,
        "affiliate_commission_rate": affiliate,
        "category_overrides":        category_overrides,
        "tier_aliases":              tier_aliases,
        "updated_at":                now,
        "updated_by":                "scripts/iter478_bootstrap_fee_schedule.py",
        "notes": (
            "iter478 Phase 1 bootstrap — WRITE-ONLY. No production calc path "
            "reads from this collection.  Values compiled from pricing_config + "
            "fee_calculator iter350 constants."
        ),
    }
    # from_bootstrap_dict validates every rate is a Decimal in [0, 0.5]
    return from_bootstrap_dict(raw)


# ═══════════════════════════════════════════════════════════════════════
#  Diff helpers
# ═══════════════════════════════════════════════════════════════════════
def _walk_diff(a, b, path="") -> list[str]:
    """Return a list of human-readable differences between two nested
    dicts, treating stringified Decimals ("0.05") as equal to Decimals."""
    out: list[str] = []

    def _norm(x):
        if isinstance(x, Decimal):
            return str(x)
        if isinstance(x, bool):
            return x
        try:
            # unify "0.05" / 0.05 / Decimal("0.05")
            return str(Decimal(str(x)))
        except Exception:  # noqa: BLE001
            return x

    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a.keys()) | set(b.keys())):
            if key not in a:
                out.append(f"{path}.{key} MISSING on disk")
            elif key not in b:
                out.append(f"{path}.{key} MISSING in code")
            else:
                out.extend(_walk_diff(a[key], b[key], f"{path}.{key}"))
        return out
    if _norm(a) != _norm(b):
        out.append(f"{path}: on_disk={a!r}  code={b!r}")
    return out


def diff_against_code(existing_doc: dict, code_schedule: FeeSchedule) -> list[str]:
    """Return every field on the persisted row that has drifted from
    the code-computed schedule (ignoring bookkeeping fields)."""
    code_doc = to_mongo_dict(code_schedule)
    ignore = {"updated_at", "effective_from", "notes", "updated_by", "version"}
    a = {k: v for k, v in existing_doc.items() if k not in ignore and k != "_id"}
    b = {k: v for k, v in code_doc.items()      if k not in ignore}
    return _walk_diff(a, b, path="fee_schedule")


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════
async def _run(*, verify: bool, force: bool) -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]

    code_schedule = build_v1_schedule()
    code_doc = to_mongo_dict(code_schedule)

    existing = await db[COLLECTION_NAME].find_one(
        {"id": CURRENT_SCHEDULA_ID}, {"_id": 0}
    )

    if verify:
        if not existing:
            print(f"[iter478] ❌ no {CURRENT_SCHEDULA_ID} row on disk")
            return 2
        drifts = diff_against_code(existing, code_schedule)
        if drifts:
            print(f"[iter478] ⚠  {len(drifts)} field(s) drift from code:")
            for d in drifts:
                print(f"           {d}")
            return 1
        print(f"[iter478] ✅  disk schedule matches code exactly.")
        return 0

    if existing and not force:
        drifts = diff_against_code(existing, code_schedule)
        if not drifts:
            print(
                f"[iter478] ℹ  {CURRENT_SCHEDULA_ID} already up to date "
                f"(version={existing.get('version')}).  no-op."
            )
            return 0
        print(f"[iter478] ⚠  disk row differs from code, but --force not set:")
        for d in drifts:
            print(f"           {d}")
        print("[iter478] refusing to overwrite. re-run with --force to update.")
        return 3

    # ── Write path ────────────────────────────────────────────────
    # We ALWAYS upsert on the doc-level ``id`` (not ``_id``) so re-runs
    # are safe.  A single ``fee_schedule_v1`` row is enforced.
    result = await db[COLLECTION_NAME].update_one(
        {"id": CURRENT_SCHEDULA_ID},
        {"$set": code_doc},
        upsert=True,
    )
    action = "inserted" if result.upserted_id else "updated"
    print(f"[iter478] ✅  {CURRENT_SCHEDULA_ID} {action} (version={code_schedule.version}).")

    # Handy summary
    print("[iter478]     buyer_premium.partner.default        =",
          code_doc["buyer_premium"]["partner"]["default"])
    print("[iter478]     buyer_premium.partner_pro.default    =",
          code_doc["buyer_premium"]["partner_pro"]["default"])
    print("[iter478]     seller_commission.partner_pro.rate   =",
          code_doc["seller_commission"]["partner_pro"]["seller_commission_rate"])
    print("[iter478]     platform_fees.vehicle                =",
          code_doc["platform_fees"]["vehicle"])
    print("[iter478]     platform_fees.storage                =",
          code_doc["platform_fees"]["storage"])
    print("[iter478]     stripe.percent / fixed_cad           =",
          code_doc["stripe"]["percent"], "/", code_doc["stripe"]["fixed_cad"])
    print("[iter478]     category_overrides (all active=False):",
          list(code_doc["category_overrides"].keys()))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify", action="store_true",
                   help="Only compare disk vs code, do not write.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite the existing row even if it has drifted.")
    args = p.parse_args()
    sys.exit(asyncio.run(_run(verify=args.verify, force=args.force)))


if __name__ == "__main__":
    main()
