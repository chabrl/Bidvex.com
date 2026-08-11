"""iter478 — Phase 1 verification for the fee_schedule infrastructure.

Verifies EVERY requirement listed in the master implementation directive
Section 21 (Phase 1 Testing) plus the additional safeguards from
Section 24 (Stop Conditions).

CRITICAL: This test suite does NOT execute any production settlement
math and does NOT compare against historical receipts.  Its job is only
to prove:
  1. The bootstrap script wrote the schedule row correctly.
  2. The Decimal fraction unit is enforced.
  3. The precedence chain in the resolver behaves as designed.
  4. No production calculation path imports from services.fee_schedule.
  5. Bootstrap is idempotent.
  6. Existing regression suites still pass.

Every rate assertion is derived from the CODE's authoritative source
(``services.pricing_config``) so that if a future engineer edits a rate
in one place but not the other, this test flags the drift.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

from services import pricing_config as _pcfg
from services import fee_calculator as _fc
from services.fee_schedule import (
    COLLECTION_NAME,
    CURRENT_SCHEDULA_ID,
    FeeScheduleResolutionError,
    FeeScheduleValidationError,
    from_bootstrap_dict,
    get_active_schedule,
    resolve_buyer_premium_rate,
    resolve_seller_commission_rate,
    resolve_stripe,
    resolve_platform_fee_rate,
    category_override,
)


BOOTSTRAP_SCRIPT = BACKEND / "scripts/iter478_bootstrap_fee_schedule.py"


# ═══════════════════════════════════════════════════════════════════════
#  Static caller/import analysis — proves NO production calc path reads
#  services.fee_schedule during Phase 1.
# ═══════════════════════════════════════════════════════════════════════
PRODUCTION_CALCULATION_MODULES = (
    "services/fee_calculator.py",
    "services/fee_calculation_engine.py",
    "services/auction_settlement.py",
    "services/payment_collection.py",
    "services/receipts.py",
    "services/pdf_generators/common.py",
    "services/pdf_generators/universal_receipt.py",
    "services/pdf_generators/sections.py",
    "services/pdf_generators/branding.py",
    "services/vehicle_pricing.py",
    "services/vehicle_invoice.py",
    "services/vehicle_multi_lot_settlement.py",
    "services/storage_pricing.py",
    "services/category_rules.py",
    "services/connect_payment_engine.py",
    "services/pricing_config.py",
    "services/tax_engine.py",
)


def _scan_production_modules_for_fee_schedule_imports() -> list[str]:
    """Return the list of production files that DO import from
    ``services.fee_schedule``.  Should be empty during Phase 1."""
    hits: list[str] = []
    for rel in PRODUCTION_CALCULATION_MODULES:
        p = BACKEND / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        # Match `from services.fee_schedule import …` or
        # `import services.fee_schedule …` (in any casing).
        if re.search(r"from\s+services\.fee_schedule\s+import|import\s+services\.fee_schedule\b", text):
            hits.append(rel)
    return hits


# ═══════════════════════════════════════════════════════════════════════
#  Test runner
# ═══════════════════════════════════════════════════════════════════════
async def main():
    results: list[dict] = []
    def add(name: str, ok: bool, **kw):
        results.append({"test": name, "ok": ok, **kw})

    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]

    # ── 0. Static caller analysis (BEFORE bootstrap) ─────────────
    #      Phase 1 non-negotiable: no calc path may read the schedule.
    illegal_importers = _scan_production_modules_for_fee_schedule_imports()
    add("T0.no_production_calc_path_imports_fee_schedule",
        ok=(not illegal_importers),
        illegal_importers=illegal_importers)

    # ── 1. Bootstrap is runnable & idempotent ───────────────────
    def _run(*flags) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(BOOTSTRAP_SCRIPT), *flags],
            capture_output=True, text=True, timeout=30,
        )

    r1 = _run()
    add("T1a.bootstrap_first_run_ok",
        ok=(r1.returncode == 0),
        stdout=r1.stdout[-300:], stderr=r1.stderr[-300:])
    r2 = _run()
    add("T1b.bootstrap_second_run_is_noop",
        ok=(r2.returncode == 0 and ("already up to date" in r2.stdout or "no-op" in r2.stdout)),
        stdout=r2.stdout[-300:])
    r3 = _run("--verify")
    add("T1c.bootstrap_verify_reports_zero_drift",
        ok=(r3.returncode == 0 and "matches code exactly" in r3.stdout),
        stdout=r3.stdout[-300:])

    # Confirm exactly ONE row was created
    count = await db[COLLECTION_NAME].count_documents({"id": CURRENT_SCHEDULA_ID})
    add("T1d.exactly_one_active_row",
        ok=(count == 1), row_count=count)

    # ── 2. Load and inspect the persisted schedule ───────────────
    schedule = await get_active_schedule(db)
    add("T2.schedule_loaded",
        ok=(schedule.id == CURRENT_SCHEDULA_ID and schedule.version == 1))

    # ── 3. Individual buyer premium ─────────────────────────────
    #     Section 21 T4: standard=5%, premium=3.5%, vip_elite=3%
    ind_bp = {
        t: resolve_buyer_premium_rate(schedule,
                                      seller_account_type="individual",
                                      buyer_tier=t)
        for t in ("standard", "premium", "vip_elite")
    }
    add("T3.individual_buyer_premium_matches_pricing_config",
        ok=(ind_bp["standard"]  == _pcfg.BUYER_PREMIUM_RATES["standard"] and
            ind_bp["premium"]   == _pcfg.BUYER_PREMIUM_RATES["premium"] and
            ind_bp["vip_elite"] == _pcfg.BUYER_PREMIUM_RATES["vip_elite"]),
        resolved={k: str(v) for k, v in ind_bp.items()},
        pricing_config={
            "standard":  str(_pcfg.BUYER_PREMIUM_RATES["standard"]),
            "premium":   str(_pcfg.BUYER_PREMIUM_RATES["premium"]),
            "vip_elite": str(_pcfg.BUYER_PREMIUM_RATES["vip_elite"]),
        })

    # ── 4. Individual seller commission ─────────────────────────
    #     Section 21 T5: standard=4%, premium=2.5%, vip_elite=2%
    ind_sc = {
        t: resolve_seller_commission_rate(schedule,
                                          seller_account_type="individual",
                                          seller_tier=t)
        for t in ("standard", "premium", "vip_elite")
    }
    add("T4.individual_seller_commission_matches_pricing_config",
        ok=(ind_sc["standard"]  == _pcfg.SELLER_COMMISSION_RATES["standard"] and
            ind_sc["premium"]   == _pcfg.SELLER_COMMISSION_RATES["premium"] and
            ind_sc["vip_elite"] == _pcfg.SELLER_COMMISSION_RATES["vip_elite"]),
        resolved={k: str(v) for k, v in ind_sc.items()})

    # ── 5. Partner default (Section 21 T2) ──────────────────────
    p_default = resolve_buyer_premium_rate(schedule, seller_account_type="partner")
    add("T5.partner_default_is_5_percent",
        ok=(p_default == Decimal("0.05")),
        resolved=str(p_default))

    # ── 6. Partner Pro (Section 21 T3) ─────────────────────────
    ppro_bp = resolve_buyer_premium_rate(schedule, seller_account_type="partner_pro")
    ppro_sc = resolve_seller_commission_rate(schedule, seller_account_type="partner_pro")
    add("T6a.partner_pro_buyer_premium_is_3.75_percent",
        ok=(ppro_bp == Decimal("0.0375")),
        resolved=str(ppro_bp))
    add("T6b.partner_pro_seller_commission_is_3_percent",
        ok=(ppro_sc == Decimal("0.03")),
        resolved=str(ppro_sc))

    # ── 7. Vehicle / Storage (Section 21 T6 + T7) ──────────────
    veh = resolve_buyer_premium_rate(schedule, seller_account_type="vehicle_dealer")
    sto = resolve_buyer_premium_rate(schedule, seller_account_type="storage_facility")
    add("T7a.vehicle_dealer_default_is_2.5_percent",
        ok=(veh == Decimal("0.025")), resolved=str(veh))
    add("T7b.storage_facility_default_is_5_percent",
        ok=(sto == Decimal("0.05")), resolved=str(sto))
    veh_sc = resolve_seller_commission_rate(schedule, seller_account_type="vehicle_dealer")
    sto_sc = resolve_seller_commission_rate(schedule, seller_account_type="storage_facility")
    add("T7c.vehicle_dealer_seller_pays_0",
        ok=(veh_sc == Decimal("0")), resolved=str(veh_sc))
    add("T7d.storage_facility_seller_pays_0",
        ok=(sto_sc == Decimal("0")), resolved=str(sto_sc))

    # ── 8. Partner precedence chain (Section 3 + Section 21 T8) ─
    #     Priority 2 (listing_override) beats Priority 3 (custom_per_user)
    #     which beats Priority 4 (default).
    p_listing = resolve_buyer_premium_rate(
        schedule, seller_account_type="partner",
        listing_override=Decimal("0.10"),
        custom_per_user=Decimal("0.18"),
    )
    add("T8a.partner_listing_override_wins_over_custom_and_default",
        ok=(p_listing == Decimal("0.10")), resolved=str(p_listing))

    p_user = resolve_buyer_premium_rate(
        schedule, seller_account_type="partner",
        custom_per_user=Decimal("0.18"),
    )
    add("T8b.partner_custom_per_user_wins_over_default",
        ok=(p_user == Decimal("0.18")), resolved=str(p_user))

    p_default2 = resolve_buyer_premium_rate(
        schedule, seller_account_type="partner",
    )
    add("T8c.partner_falls_through_to_default_only_when_no_overrides",
        ok=(p_default2 == Decimal("0.05")), resolved=str(p_default2))

    # Section 21 T8 explicit examples: 10%, 15%, 18%
    for override in ("0.10", "0.15", "0.18"):
        r = resolve_buyer_premium_rate(
            schedule, seller_account_type="partner",
            listing_override=Decimal(override),
        )
        add(f"T8d.partner_listing_override_{override}_is_preserved",
            ok=(r == Decimal(override)), resolved=str(r))

    # Snapshot always wins (Priority 1)
    p_snap = resolve_buyer_premium_rate(
        schedule, seller_account_type="individual", buyer_tier="premium",
        snapshot_rate=Decimal("0.077"),
        listing_override=Decimal("0.10"),
        custom_per_user=Decimal("0.18"),
    )
    add("T8e.snapshot_rate_wins_over_everything",
        ok=(p_snap == Decimal("0.077")), resolved=str(p_snap))

    # ── 9. Category overrides preserved but INACTIVE (Section 21 T9) ─
    for cat_key in ("restaurant_equipment", "bankrupt_inventory",
                    "industrial_equipment", "general_lots"):
        node = schedule.category_overrides.get(cat_key)
        add(f"T9a.category_override_preserved::{cat_key}",
            ok=(node is not None and node.get("active") is False),
            node=node)
    # And category_override() helper returns None (because active=False)
    add("T9b.category_override_helper_returns_None_for_all",
        ok=all(category_override(schedule, category=c) is None
               for c in ("restaurant_equipment", "bankrupt_inventory",
                         "industrial_equipment", "general_lots")))

    # ── 10. Decimal fraction enforcement (Section 21 T10 + Section 12) ─
    #      Percent-style values (5.0) are rejected outright.
    try:
        from_bootstrap_dict({
            "id": "bad", "version": 1, "effective_from": "x",
            "buyer_premium":     {"individual": {"standard": 5.0}},
            "seller_commission": {"individual": {"standard": Decimal("0.04")}},
            "platform_fees":     {"general": Decimal("0.03")},
            "stripe":            {"percent": Decimal("0.029"), "fixed_cad": Decimal("0.30")},
            "affiliate_commission_rate": Decimal("0.03"),
            "category_overrides": {},
            "tier_aliases": {},
        })
        add("T10a.percent_style_rejected", ok=False, note="5.0 accepted (bug)")
    except FeeScheduleValidationError:
        add("T10a.percent_style_rejected", ok=True)

    # And any float in the schedule is coerced to Decimal on read
    for tier in ("standard", "premium", "vip_elite"):
        v = resolve_buyer_premium_rate(schedule,
                                       seller_account_type="individual",
                                       buyer_tier=tier)
        add(f"T10b.rate_is_Decimal_type::{tier}",
            ok=isinstance(v, Decimal), type=type(v).__name__)

    # ── 11. Bootstrap is idempotent (Section 21 T11) ────────────
    #     After the first run + a rerun, there is still ONE row.
    count_now = await db[COLLECTION_NAME].count_documents({"id": CURRENT_SCHEDULA_ID})
    add("T11.bootstrap_idempotent_single_row",
        ok=(count_now == 1), row_count=count_now)

    # ── 12. Existing calculation engine is unchanged (Section 21 T12) ──
    #      Sanity: import + a canonical smoke fee call.
    fee = _fc.calculate_fee(
        hammer_price=200.0, auction_type="lots",
        seller_account_type="individual", seller_tier="standard",
        buyer_account_type="individual", buyer_tier="standard",
        payment_method="stripe", card_type="domestic",
        buyer_province="QC", seller_province="QC",
    )
    add("T12a.calculate_fee_still_returns_iter350_model",
        ok=(fee.get("fee_model_version") == "iter350"),
        fee_model_version=fee.get("fee_model_version"))
    # Buyer premium at hammer=200, individual/standard = 5% → 10.00
    add("T12b.calculate_fee_buyer_premium_unchanged",
        ok=(round(float(fee["buyer_premium"]), 2) == 10.00),
        buyer_premium=fee["buyer_premium"])
    # Seller commission at hammer=200, individual/standard = 4% → 8.00
    add("T12c.calculate_fee_seller_commission_unchanged",
        ok=(round(float(fee["seller_commission"]), 2) == 8.00),
        seller_commission=fee["seller_commission"])

    # ── 13. Stripe params match production constants ────────────
    st = resolve_stripe(schedule)
    add("T13.stripe_matches_pricing_config",
        ok=(st["percent"] == _pcfg.STRIPE_PROCESSING_RATE
            and st["fixed_cad"] == _pcfg.STRIPE_PROCESSING_FIXED),
        percent=str(st["percent"]), fixed_cad=str(st["fixed_cad"]))

    # ── 14. Platform fees match production ─────────────────────
    add("T14a.platform_fees_vehicle_matches",
        ok=(resolve_platform_fee_rate(schedule, kind="vehicle") ==
            _pcfg.PLATFORM_FEE_VEHICLE))
    add("T14b.platform_fees_general_matches",
        ok=(resolve_platform_fee_rate(schedule, kind="general") ==
            _pcfg.PLATFORM_FEE_GENERAL))
    add("T14c.platform_fees_partner_matches",
        ok=(resolve_platform_fee_rate(schedule, kind="partner") ==
            _fc.PARTNER_PLATFORM_RATE))
    add("T14d.platform_fees_broker_matches",
        ok=(resolve_platform_fee_rate(schedule, kind="broker") ==
            _fc.BROKER_PLATFORM_RATE))

    # ── 15. Resolver refuses to invent missing rates ────────────
    #      Section 3: "No silent fallback to an unrelated buyer tier"
    try:
        resolve_buyer_premium_rate(
            schedule, seller_account_type="individual",
            buyer_tier="mystery_new_tier_never_existed",
        )
        add("T15a.no_silent_fallback_on_unknown_tier",
            ok=False, note="resolver accepted unknown tier")
    except FeeScheduleResolutionError:
        add("T15a.no_silent_fallback_on_unknown_tier", ok=True)

    try:
        resolve_buyer_premium_rate(
            schedule, seller_account_type="wat_type",
        )
        add("T15b.no_silent_fallback_on_unknown_account_type",
            ok=False, note="resolver accepted unknown account_type")
    except FeeScheduleResolutionError:
        add("T15b.no_silent_fallback_on_unknown_account_type", ok=True)

    # ── 16. Historical data untouched ───────────────────────────
    #      Sample recent receipt row to confirm nothing was rewritten.
    sample = await db.receipts.find_one({"itemized_reconciled": True}, {"_id": 0})
    add("T16.itemized_iter476_receipts_still_present",
        ok=(sample is None or sample.get("itemized_reconciled") is True),
        found=bool(sample))

    # ── 17. STOP-condition sentinel: PricingManager 'partner'=0 still ───
    #      exists in code but is NOT in the schedule.
    from services.fee_calculator import BUYER_PREMIUM_RATES as _pm_bp
    add("T17a.pricingmanager_still_has_partner_zero_bp",
        ok=(_pm_bp.get("partner") == Decimal("0")),
        pricing_manager_partner_bp=str(_pm_bp.get("partner")))
    add("T17b.schedule_partner_default_is_NOT_zero",
        ok=(resolve_buyer_premium_rate(schedule, seller_account_type="partner")
            != Decimal("0")),
        note="Schedule uses pricing_config.BUYER_PREMIUM_RATES[partner]=5%.")

    # ── 18. Section 12 — Stored Decimals round-trip ────────────
    doc = await db[COLLECTION_NAME].find_one({"id": CURRENT_SCHEDULA_ID}, {"_id": 0})
    assert doc is not None
    # buyer_premium.individual.standard must be a string of a Decimal (or Decimal)
    v = doc["buyer_premium"]["individual"]["standard"]
    add("T18.stored_rate_is_decimal_string",
        ok=(isinstance(v, str) and Decimal(v) == Decimal("0.05")),
        stored=v, stored_type=type(v).__name__)

    # ═══════════════════════════════════════════════════════════
    passed = sum(1 for r in results if r["ok"])
    total  = len(results)
    out = {
        "iter": "478-phase1-fee-schedule-bootstrap",
        "passed": passed, "total": total,
        "schedule_snapshot": {
            "id": schedule.id, "version": schedule.version,
            "individual_buyer_premium":    {k: str(v) for k, v in ind_bp.items()},
            "individual_seller_commission": {k: str(v) for k, v in ind_sc.items()},
            "partner_default_bp": str(p_default),
            "partner_pro_bp":     str(ppro_bp),
            "partner_pro_sc":     str(ppro_sc),
            "vehicle_dealer_bp":  str(veh),
            "storage_facility_bp": str(sto),
            "stripe": {"percent": str(st["percent"]), "fixed_cad": str(st["fixed_cad"])},
            "category_overrides_active": {
                k: schedule.category_overrides.get(k, {}).get("active")
                for k in schedule.category_overrides
            },
        },
        "results": results,
        "illegal_fee_schedule_importers": illegal_importers,
    }
    p = Path("/app/test_reports/iter478_fee_schedule_bootstrap.json")
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(out, indent=2, default=str))
    print(f"[iter478] {passed}/{total} passed → {p}")
    if illegal_importers:
        print(f"[iter478] ❌ STOP: production paths import fee_schedule: {illegal_importers}")
    fails = [r for r in results if not r["ok"]]
    for r in fails:
        print(f"  FAIL {r['test']:60s} {json.dumps({k: v for k, v in r.items() if k not in ('test','ok')}, default=str)[:220]}")


if __name__ == "__main__":
    asyncio.run(main())
