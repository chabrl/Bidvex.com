"""iter479 — Phase 2 READ-ONLY production impact queries.

Runs THREE independent read-only analyses required by the master directive
before Phase 2 dual-read execution:

  1. PricingManager BUYER_PREMIUM_RATES["partner"]=0 impact
     → Count users with subscription_tier="partner" who have BUYER-side
       purchases through the affected code paths.  No settlement changed.

  2. Partner hammer-tax discrepancy between
        _iter350_partner (never taxes hammer)
      vs
        stripe_connect_service.calculate_partner_listing_checkout
        (taxes hammer if partner_is_tax_registered=True)
     → Sample recent partner-seller receipts and see whether
       ``hammer_gst`` / ``hammer_qst`` are populated in the persisted row
       and whether they are non-zero for any historical partner sale.

  3. Historical receipt integrity sanity: pick recent iter476-itemized
     receipts, verify each row still reconciles buyer/seller totals.
     Purely observational.

Writes ``/app/test_reports/iter479_phase2_impact_analysis.json``.
NEVER modifies any collection.  Never expose PII.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

from services.receipts import reconcile_itemized, ITEMIZED_KEYS
from services.fee_calculator import BUYER_PREMIUM_RATES as _PM_BP_RATES

# ═══════════════════════════════════════════════════════════════
def _mask_uid(uid: str) -> str:
    """De-identify user IDs to first-6 characters for the audit log."""
    if not uid or not isinstance(uid, str):
        return "—"
    return uid[:6] + "…" + uid[-3:] if len(uid) > 9 else uid


async def query1_pricingmanager_partner_zero_impact(db) -> dict:
    """1. PricingManager Partner=0 impact query."""
    # ── Users with subscription_tier="partner" ──
    # Some Bidvex flows also mint a `partner_tier` field. Union both.
    partner_users_cursor = db.users.find(
        {"$or": [
            {"subscription_tier": {"$regex": r"^partner$", "$options": "i"}},
            {"partner_tier": {"$exists": True, "$ne": None}},
        ]},
        {"_id": 0, "id": 1, "email": 1, "subscription_tier": 1,
         "account_type": 1, "custom_premium_rate": 1, "created_at": 1},
    )
    partner_users = await partner_users_cursor.to_list(2000)

    # Filter to users whose subscription_tier is literally "partner"
    # (case-insensitive) — that is what PricingManager keys off.
    strict_partner_tier = [
        u for u in partner_users
        if str(u.get("subscription_tier", "")).strip().lower() == "partner"
    ]

    # ── Count BUYER purchases (receipts where they are the buyer) ──
    buyer_hits = []
    for u in strict_partner_tier:
        uid = u.get("id")
        rec_count = await db.receipts.count_documents({
            "user_id": uid, "type": "buyer_receipt",
        })
        if rec_count > 0:
            # Sample the most recent 3 to inspect for the affected code path
            sample = await db.receipts.find(
                {"user_id": uid, "type": "buyer_receipt"},
                {"_id": 0, "id": 1, "section": 1, "created_at": 1,
                 "hammer_price": 1, "buyer_premium": 1,
                 "buyer_premium_rate": 1, "total_charged": 1,
                 "fee_model_version": 1, "itemized_reconciled": 1},
                sort=[("created_at", -1)], limit=3,
            ).to_list(3)
            buyer_hits.append({
                "user_id_masked": _mask_uid(uid),
                "subscription_tier": u.get("subscription_tier"),
                "created_at": u.get("created_at"),
                "receipt_count": rec_count,
                "sample_receipts": [
                    {
                        "id":              r.get("id"),
                        "section":         r.get("section"),
                        "created_at":      r.get("created_at"),
                        "hammer_price":    r.get("hammer_price"),
                        "buyer_premium":   r.get("buyer_premium"),
                        "buyer_premium_rate": r.get("buyer_premium_rate"),
                        "total_charged":   r.get("total_charged"),
                        "fee_model_version": r.get("fee_model_version"),
                        "itemized_reconciled": r.get("itemized_reconciled"),
                    }
                    for r in sample
                ],
            })

    return {
        "test": "1.pricingmanager_partner_zero_impact",
        "authoritative_source": (
            "PricingManager.BUYER_PREMIUM_RATES[\"partner\"] = "
            + str(_PM_BP_RATES.get("partner", "MISSING"))
        ),
        "total_users_with_partner_related_tier": len(partner_users),
        "users_with_strict_subscription_tier_partner": len(strict_partner_tier),
        "users_with_partner_tier_and_buyer_purchases": len(buyer_hits),
        "sample_impacted_users": buyer_hits[:10],
        "interpretation": (
            "PricingManager's `partner`=0 buyer premium row is keyed by the "
            "BUYER's `subscription_tier`, not the seller's account type. "
            "It is only hit when a buyer whose subscription_tier is "
            "literally 'partner' checks out through PricingManager.non_vehicle_stripe "
            "or connect_payment_engine.  If `users_with_partner_tier_and_buyer_purchases == 0` "
            "no production settlement has ever been affected."
        ),
    }


async def query2_partner_hammer_tax_discrepancy(db) -> dict:
    """2. Partner hammer-tax discrepancy analysis."""
    # Find partner-seller receipts (buyer receipts where seller was partner)
    # We infer partner-sales from the persisted itemized row: partner sales
    # store fee_model_version="iter350" AND seller_commission_rate ≈ 0.03
    # (matches PARTNER_PLATFORM_RATE).
    partner_receipts = await db.receipts.find(
        {
            "type": "buyer_receipt",
            "itemized_reconciled": True,
            "seller_commission_rate": {"$gte": 0.029, "$lte": 0.031},
        },
        {"_id": 0, "id": 1, "section": 1, "listing_id": 1, "created_at": 1,
         "hammer_price": 1, "hammer_gst": 1, "hammer_qst": 1,
         "buyer_premium": 1, "buyer_premium_gst": 1, "buyer_premium_qst": 1,
         "service_fee": 1, "seller_commission": 1,
         "stripe_fee": 1, "total_charged": 1, "fee_model_version": 1,
         "seller_is_tax_registered": 1},
        sort=[("created_at", -1)], limit=100,
    ).to_list(100)

    # Bucket by hammer-tax population
    with_hammer_tax = []
    without_hammer_tax = []
    for r in partner_receipts:
        h_gst = float(r.get("hammer_gst") or 0)
        h_qst = float(r.get("hammer_qst") or 0)
        summary = {
            "id":                     r.get("id"),
            "section":                r.get("section"),
            "created_at":             r.get("created_at"),
            "hammer_price":           r.get("hammer_price"),
            "hammer_gst":             h_gst,
            "hammer_qst":             h_qst,
            "buyer_premium":          r.get("buyer_premium"),
            "seller_commission":      r.get("seller_commission"),
            "service_fee":            r.get("service_fee"),
            "seller_is_tax_registered": r.get("seller_is_tax_registered"),
        }
        if h_gst > 0 or h_qst > 0:
            with_hammer_tax.append(summary)
        else:
            without_hammer_tax.append(summary)

    return {
        "test": "2.partner_hammer_tax_discrepancy",
        "code_paths_compared": {
            "iter350_partner":
                "services.fee_calculator._iter350_partner — never taxes hammer. "
                "buyer_gst/buyer_qst always == tax_on(bidvex_fee+stripe_recovery, partner_prov). "
                "hammer_gst/hammer_qst never populated.",
            "checkout_partner":
                "services.stripe_connect_service.calculate_partner_listing_checkout — "
                "taxes hammer IF partner_is_tax_registered=True. Otherwise 0.",
        },
        "sample_partner_receipts_last_100": len(partner_receipts),
        "receipts_with_nonzero_hammer_tax": len(with_hammer_tax),
        "receipts_without_hammer_tax":      len(without_hammer_tax),
        "with_hammer_tax_sample":    with_hammer_tax[:5],
        "without_hammer_tax_sample": without_hammer_tax[:5],
        "interpretation": (
            "If `receipts_with_nonzero_hammer_tax == 0`, no production partner "
            "sale has ever collected hammer tax via the settlement path.  This "
            "means the CheckoutBreakdown 'if partner_is_tax_registered' branch "
            "has never been exercised on a persisted receipt, OR the auction_settlement "
            "path (which uses _iter350_partner and drops hammer_gst=0.0) is the "
            "authoritative production path.  Either way, no behavior change is "
            "authorized in Phase 2 — this is a business/tax-policy decision for "
            "you to make in Phase 3."
        ),
    }


async def query3_historical_receipt_sanity(db) -> dict:
    """3. Sample recent iter476-itemized receipts, verify each still reconciles."""
    recent = await db.receipts.find(
        {"itemized_reconciled": True},
        {"_id": 0},
        sort=[("created_at", -1)], limit=25,
    ).to_list(25)

    results = []
    for r in recent:
        itemized = {k: r.get(k) for k in ITEMIZED_KEYS}
        # Skip QA seeds from iter477 tests
        if str(r.get("id", "")).startswith("iter477"):
            continue
        rec = reconcile_itemized(
            hammer_price=r.get("hammer_price"),
            itemized=itemized,
            total_charged=r.get("total_charged"),
            net_payout=r.get("net_payout"),
        )
        results.append({
            "receipt_id":       r.get("id"),
            "section":          r.get("section"),
            "created_at":       r.get("created_at"),
            "itemized_reconciled": r.get("itemized_reconciled"),
            "replay_ok":        rec["ok"],
            "replay_buyer_delta_cents":  rec["buyer_delta_cents"],
            "replay_seller_delta_cents": rec["seller_delta_cents"],
        })

    passing = sum(1 for x in results if x["replay_ok"])
    return {
        "test": "3.historical_receipt_reconciliation_sanity",
        "sample_size":  len(results),
        "reconciles":   passing,
        "does_not_reconcile": len(results) - passing,
        "detail":       results,
        "interpretation": (
            "Every persisted iter476 itemized receipt is expected to reconcile "
            "(reconcile_itemized runs on write).  A drop below 100% would "
            "indicate that a persisted row has been mutated after settlement — "
            "which is a STOP condition."
        ),
    }


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc).isoformat()
    q1 = await query1_pricingmanager_partner_zero_impact(db)
    q2 = await query2_partner_hammer_tax_discrepancy(db)
    q3 = await query3_historical_receipt_sanity(db)

    # STOP-condition tallies
    stop_conditions = []
    if q1["users_with_partner_tier_and_buyer_purchases"] > 0:
        stop_conditions.append(
            f"⚠ {q1['users_with_partner_tier_and_buyer_purchases']} users with "
            "subscription_tier=partner have BUYER purchases → PricingManager 0% "
            "path may have affected production."
        )
    if q2["receipts_with_nonzero_hammer_tax"] > 0:
        stop_conditions.append(
            f"⚠ {q2['receipts_with_nonzero_hammer_tax']} partner receipts have "
            "non-zero hammer_gst/qst → CheckoutBreakdown path was used, and the "
            "_iter350_partner divergence matters."
        )
    if q3["does_not_reconcile"] > 0:
        stop_conditions.append(
            f"⚠ {q3['does_not_reconcile']} historical iter476 receipts fail "
            "reconciliation replay → immutability violation."
        )

    report = {
        "iter": "479-phase2-read-only-impact-analysis",
        "generated_at": now,
        "query_1_pricingmanager_partner_zero": q1,
        "query_2_partner_hammer_tax_discrepancy": q2,
        "query_3_historical_receipt_sanity": q3,
        "stop_conditions_detected": stop_conditions,
    }
    p = Path("/app/test_reports/iter479_phase2_impact_analysis.json")
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(report, indent=2, default=str))
    print(f"[iter479] impact analysis → {p}")
    print(f"[iter479]  Q1: {q1['users_with_partner_tier_and_buyer_purchases']} users with partner-tier + buyer purchases")
    print(f"[iter479]  Q2: {q2['receipts_with_nonzero_hammer_tax']}/{q2['sample_partner_receipts_last_100']} partner receipts have hammer tax")
    print(f"[iter479]  Q3: {q3['reconciles']}/{q3['sample_size']} historical receipts reconcile")
    if stop_conditions:
        print("[iter479] STOP CONDITIONS:")
        for s in stop_conditions:
            print(f"           {s}")
    else:
        print("[iter479] no stop conditions triggered by production data.")


if __name__ == "__main__":
    asyncio.run(main())
