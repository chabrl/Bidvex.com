"""
P7 golden snapshot generator.

Runs each calculator on the full matrix, dumps CURRENT output to
/app/backend/tests/p7/golden/*.json — this file is committed and the
tests assert against it.  Snapshot pattern: no math in the tests, just
byte-for-byte equality.

Usage:
    cd /app/backend && python -m tests.p7.generate_golden_snapshots

The generator is IDEMPOTENT — re-running produces the same output as
long as the underlying calculators are unchanged.  When the calculators
DO change intentionally, the operator regenerates the snapshots and
commits the diff for review.
"""
from __future__ import annotations
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

# When run as ``python -m tests.p7.generate_golden_snapshots`` from
# /app/backend the parent dir is the module root — nothing to configure.
# When run as a plain script we need to insert /app/backend on the path.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from services.fee_calculator import calculate_fee                       # noqa: E402
from services.tax_engine import (                                       # noqa: E402
    calculate_tax as legacy_calculate_tax,
    calculate_vehicle_payment as legacy_calc_vehicle,
    calculate_general_payment as legacy_calc_general,
    calculate_gst_qst as legacy_calc_gst_qst,
    calculate_taxes_for_recipient as legacy_calc_recipient,
)
from services.broker_fee_engine import calculate_broker_transaction     # noqa: E402
from services.invoice_service import calculate_province_tax             # noqa: E402


GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
GOLDEN_DIR.mkdir(exist_ok=True)


AMOUNTS = [
    "0.01", "0.99", "1.00", "9.99", "10.00", "99.99", "100.00",
    "999.99", "1000.00", "25000.00", "125000.00", "500000.00",
]
JURISDICTIONS = ["QC", "ON", "AB", "BC"]
MISSING = ["", "  ", "ZZ", "PLUTO"]


def _r(x):
    """Round for comparison — Decimal cents."""
    return int((Decimal(str(x)) * 100).quantize(Decimal("1")))


def _keep(d: dict, keys: list[str]) -> dict:
    """Extract just the keys we golden-snapshot to keep files stable."""
    return {k: (_r(d[k]) if isinstance(d.get(k), (int, float)) else d.get(k)) for k in keys}


# ─── Snapshot table for canonical calculate_fee ──────────────────────
def _snapshot_canonical() -> dict:
    keys = [
        "buyer_premium", "buyer_stripe_recovery", "buyer_gst", "buyer_qst",
        "buyer_hst", "buyer_taxes", "buyer_tax_province", "buyer_total_charged",
        "seller_commission", "seller_stripe_recovery", "seller_gst",
        "seller_qst", "seller_hst", "seller_taxes", "seller_tax_province",
        "seller_payout", "bidvex_revenue", "tax_rate",
    ]
    out = {}
    # Individual matrix
    for amount in AMOUNTS:
        for buyer_prov in JURISDICTIONS:
            for seller_prov in ["QC", "ON"]:
                for payment in ["stripe", "etransfer"]:
                    key = f"individual|{amount}|{buyer_prov}|{seller_prov}|{payment}"
                    r = calculate_fee(
                        hammer_price=float(amount),
                        auction_type="timed",
                        seller_account_type="individual",
                        seller_tier="free",
                        buyer_province=buyer_prov,
                        seller_province=seller_prov,
                        payment_method=payment,
                    )
                    out[key] = _keep(r, keys)
    # Partner matrix
    for amount in ["100.00", "1000.00", "25000.00", "125000.00"]:
        for partner_prov in JURISDICTIONS:
            for buyer_prov in JURISDICTIONS:
                for bp_rate in [0.05, 0.10, 0.15]:
                    key = f"partner|{amount}|{partner_prov}|{buyer_prov}|{bp_rate}"
                    r = calculate_fee(
                        hammer_price=float(amount),
                        auction_type="timed",
                        seller_account_type="partner",
                        buyer_province=buyer_prov,
                        partner_province=partner_prov,
                        partner_bp_rate=bp_rate,
                    )
                    out[key] = _keep(r, keys)
    # Vehicle dealer matrix
    for amount in ["100.00", "1000.00", "25000.00", "125000.00", "500000.00"]:
        for buyer_prov in JURISDICTIONS:
            key = f"vehicle_dealer|{amount}|{buyer_prov}"
            r = calculate_fee(
                hammer_price=float(amount),
                auction_type="timed",
                seller_account_type="vehicle_dealer",
                buyer_province=buyer_prov,
            )
            out[key] = _keep(r, keys)
    # Storage matrix
    for amount in ["10.00", "100.00", "1000.00"]:
        for facility_prov in JURISDICTIONS:
            for buyer_prov in JURISDICTIONS:
                for payment in ["stripe", "cash"]:
                    key = f"storage|{amount}|{facility_prov}|{buyer_prov}|{payment}"
                    r = calculate_fee(
                        hammer_price=float(amount),
                        auction_type="timed",
                        seller_account_type="storage_facility",
                        facility_province=facility_prov,
                        buyer_province=buyer_prov,
                        payment_method=payment,
                    )
                    out[key] = _keep(r, keys)
    # Missing/invalid province — CRITICAL P6 risk snapshot
    for bad in MISSING + [None]:
        key = f"missing|{bad!r}"
        r = calculate_fee(
            hammer_price=100.00, auction_type="timed",
            seller_account_type="individual", seller_tier="free",
            buyer_province=bad, seller_province=bad,
        )
        out[key] = _keep(r, keys)
    return out


# ─── Snapshot table for the LEGACY tax_engine (QC-hardcoded) ─────────
def _snapshot_legacy_tax_engine() -> dict:
    keys_v = ["total_stripe_charge", "buyer_premium", "platform_fee", "fees_tax_gst",
              "fees_tax_qst", "fees_tax_total", "seller_receives"]
    keys_g = ["total_stripe_charge", "buyer_premium", "platform_fee", "fees_tax_gst",
              "fees_tax_qst", "fees_tax_total", "hammer_price", "seller_receives_hammer",
              "commission_amount"]
    out = {}
    for amount in AMOUNTS:
        # calculate_tax (bare, no province param — always QC 14.975%)
        t = legacy_calculate_tax(Decimal(str(amount)))
        out[f"legacy_calculate_tax|{amount}"] = {
            "gst_cents": t.gst_amount_cents,
            "qst_cents": t.qst_amount_cents,
            "total_tax_cents": t.total_tax_cents,
            "total_with_tax_cents": t.total_with_tax_cents,
        }
        # vehicle
        v = legacy_calc_vehicle(float(amount), "basic")
        out[f"legacy_vehicle|{amount}"] = _keep(v.to_dict(), keys_v)
        # general (non-vehicle)
        g = legacy_calc_general(float(amount), "basic")
        out[f"legacy_general|{amount}"] = _keep(g.to_dict(), keys_g)
        # gst_qst public helper — always uses QC 14.975%
        r = legacy_calc_gst_qst(float(amount), currency="CAD")
        out[f"legacy_gst_qst_cad|{amount}"] = {k: _r(r[k]) for k in ("gst_amount", "qst_amount", "total_tax", "total_with_tax")}
        r_usd = legacy_calc_gst_qst(float(amount), currency="USD")
        out[f"legacy_gst_qst_usd|{amount}"] = {k: _r(r_usd[k]) for k in ("gst_amount", "qst_amount", "total_tax", "total_with_tax")}
    # recipient-typed — this helper takes `province` (positional), not `recipient_type`
    for amount in ["100.00", "1000.00", "25000.00"]:
        for prov in JURISDICTIONS + ["", "ZZ"]:
            r = legacy_calc_recipient(float(amount), province=prov)
            out[f"legacy_recipient|{amount}|{prov or 'MISSING'}"] = {
                "gst": _r(r.get("gst_amount", r.get("gst", 0))),
                "qst": _r(r.get("qst_amount", r.get("qst", 0))),
                "hst": _r(r.get("hst_amount", r.get("hst", 0))),
                "total_tax": _r(r.get("total_tax", 0)),
                "province": r.get("province"),
            }
    return out


# ─── Snapshot table for broker_fee_engine (QST-or-zero bug) ──────────
def _snapshot_broker_fee_engine() -> dict:
    """Confirms `broker_fee_engine.calculate_broker_transaction()`
    UNDER-COLLECTS on HST provinces: buyer in ON only gets 5% GST + 0
    QST instead of 13% HST.  DO NOT FIX — flag as C for legal review.
    """
    keys = ["platform_fee", "broker_fee", "subtotal_taxable", "gst", "qst",
            "stripe_subtotal", "stripe_processing_fee", "stripe_total_charged"]
    out = {}
    fs = {"type": "percentage", "rate_value": 0.03}   # 3% broker fee
    for amount in ["100.00", "1000.00", "25000.00", "125000.00"]:
        for buyer_prov in JURISDICTIONS + ["", None]:
            r = calculate_broker_transaction(
                hammer_price=float(amount),
                broker_fee_structure=fs,
                buyer_province=buyer_prov,
                deposit_held_cad=500.0,
            )
            key = f"broker|{amount}|{buyer_prov or 'MISSING'}"
            out[key] = {k: _r(r[k]) for k in keys}
    return out


# ─── Snapshot table for invoice_service (non-QC zero-tax risk) ───────
def _snapshot_invoice_service() -> dict:
    """Captures per-province tax lines from `invoice_service.calculate_province_tax`
    across the full matrix + missing province."""
    out = {}
    for amount in AMOUNTS:
        for prov in JURISDICTIONS + ["", "ZZ"]:
            r = calculate_province_tax(Decimal(str(amount)), buyer_province=prov)
            out[f"invoice|{amount}|{prov or 'MISSING'}"] = {
                "gst_cents": _r(r.tax_gst),
                "qst_cents": _r(r.tax_pst_qst),
                "hst_cents": _r(r.tax_hst),
                "total_tax_cents": _r(r.total_tax),
                "province": r.province,
                "tax_type": r.tax_type,
            }
    return out


def main():
    print(f"[P7] Writing golden snapshots → {GOLDEN_DIR}")
    for name, gen in [
        ("canonical_fee_calculator", _snapshot_canonical),
        ("legacy_tax_engine",        _snapshot_legacy_tax_engine),
        ("broker_fee_engine",        _snapshot_broker_fee_engine),
        ("invoice_service",          _snapshot_invoice_service),
    ]:
        try:
            data = gen()
        except Exception as exc:                                        # noqa: BLE001
            print(f"  ⚠ {name}: generator raised {type(exc).__name__}: {exc}")
            continue
        path = GOLDEN_DIR / f"{name}.json"
        with path.open("w") as f:
            json.dump(data, f, indent=2, sort_keys=True, default=str)
        print(f"  ✓ {name}: {len(data)} rows → {path.name}")


if __name__ == "__main__":
    main()
