"""P6.1.1 — Full calculator divergence matrix (READ-ONLY).

Independently re-runs every tax calculator identified by P6.1 at
$0.01 / $1 / $100 / $1,000 / $500,000 for every province + US/INTL.

Compares outputs against confirmed reference expectations to distinguish
GST/HST divergence from PST/RST inclusion from foreign fallback.

NEVER writes to the DB. Never edits production code.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, "/app/backend")

# ── The eight calculators identified in P6.1 ───────────────────────────
from services.tax_engine import (  # noqa: E402
    calculate_tax,
    calculate_gst_qst,
    calculate_taxes_for_recipient,
)
from services.vehicle_pricing import calculate_taxes as vp_calculate_taxes  # noqa: E402
from services.fee_calculator import (  # noqa: E402
    tax_on,
    calculate_partner_taxes,
)
from services.invoice_service import calculate_province_tax  # noqa: E402
from routes.tax_dashboard import compute_tax_for_transaction  # noqa: E402

PROVINCES = ["QC", "ON", "AB", "BC", "MB", "SK", "NB", "NL", "NS", "PE",
             "YT", "NT", "NU", "US", "INTL"]
AMOUNTS = [Decimal("0.01"), Decimal("1"), Decimal("100"),
           Decimal("1000"), Decimal("500000")]


# ── Confirmed reference expectation (per operator's legal input) ──────
# * Federal GST/HST per CRA 2026 (NS = 14%, all others per Canada.ca).
# * Provincial PST/RST/QST NOT collected by BidVex per current
#   BOOTSTRAP_RATES policy (INTL/US = 0%, GST-only provinces = GST only).
#   BidVex is a Canadian-resident-operated platform; §211.1 applies
#   to non-resident vendors and does not automatically obligate
#   BidVex to collect the provincial layer.
# * US/INTL = 0% (ETA Sched. VI Part V §7 zero-rated exported service).
REFERENCE_FEDERAL: dict[str, Decimal] = {
    "AB": Decimal("0.05"),  "BC": Decimal("0.05"),  "MB": Decimal("0.05"),
    "NB": Decimal("0.15"),  "NL": Decimal("0.15"),  "NS": Decimal("0.14"),
    "NT": Decimal("0.05"),  "NU": Decimal("0.05"),  "ON": Decimal("0.13"),
    "PE": Decimal("0.15"),  "QC": Decimal("0.05"),  "SK": Decimal("0.05"),
    "YT": Decimal("0.05"),  "US": Decimal("0.00"),  "INTL": Decimal("0.00"),
}
# QC has QST 9.975% as separately administered by Revenu Québec.  For
# BidVex's supply of platform services to a QC recipient, BOTH GST and
# QST are collectible — QC is the only province where BidVex currently
# collects the provincial layer, because BidVex itself is QC-registered.
REFERENCE_QST_FOR_QC = Decimal("0.09975")


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def expected_tax_total(prov: str, amount: Decimal) -> Decimal:
    """Reference expectation for BidVex's supply-of-service tax."""
    p = prov.upper()
    fed = REFERENCE_FEDERAL.get(p, Decimal("0"))
    fed_amt = _q(amount * fed)
    qst = _q(amount * REFERENCE_QST_FOR_QC) if p == "QC" else Decimal("0")
    return fed_amt + qst


def run_calculator(name: str, prov: str, amount: Decimal) -> dict:
    """Call every calculator with (prov, amount) and normalize the output."""
    result: dict = {"calculator": name, "province": prov, "amount": str(amount)}
    try:
        if name == "tax_engine.calculate_tax":
            # QC-hardcoded
            r = calculate_tax(amount)
            result["total_tax"] = str(r.total_tax)
            result["notes"] = "QC-hardcoded — province ignored"
        elif name == "tax_engine.calculate_gst_qst":
            r = calculate_gst_qst(float(amount))
            result["total_tax"] = str(r["total_tax"])
            result["notes"] = "hardcodes QC — ignores caller province"
        elif name == "tax_engine.calculate_taxes_for_recipient":
            r = calculate_taxes_for_recipient(float(amount), prov)
            result["total_tax"] = str(r["total_tax"])
            result["notes"] = "DB-backed per-province via tax_rate_config"
        elif name == "vehicle_pricing.calculate_taxes":
            r = vp_calculate_taxes(amount, prov)
            result["total_tax"] = str(r.total_tax)
            result["notes"] = "hardcoded PROVINCIAL_TAX_RATES; USA/EU/'' → 0%"
        elif name == "fee_calculator.tax_on":
            r = tax_on(amount, prov)
            result["total_tax"] = str(r["total"])
            result["notes"] = "iter350 canonical DB-backed"
        elif name == "fee_calculator.calculate_partner_taxes":
            r = calculate_partner_taxes(amount, prov)
            result["total_tax"] = str(r["total"])
            result["notes"] = "legacy shim — unknown → QC via _resolve_province"
        elif name == "invoice_service.calculate_province_tax":
            r = calculate_province_tax(float(amount), prov)
            # r.total_tax already includes PST/QST layer for BC/SK/MB/QC
            result["total_tax"] = str(r.total_tax)
            result["tax_gst"] = str(r.tax_gst)
            result["tax_hst"] = str(r.tax_hst)
            result["tax_pst_qst"] = str(r.tax_pst_qst)
            result["notes"] = "includes PST/QST/RST for BC/SK/MB/QC"
        elif name == "tax_dashboard.compute_tax_for_transaction":
            # This function reads transaction fields; simulate a tx.
            tx = {"platform_fee": float(amount), "buyer_premium": 0,
                  "seller_region": prov}
            r = compute_tax_for_transaction(tx)
            result["total_tax"] = str(r["total_tax"])
            result["notes"] = "uses seller_region, GST+QST for QC, GST-only elsewhere"
        else:
            result["error"] = f"unknown calculator {name}"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["total_tax"] = None
    return result


def main() -> dict:
    calculators = [
        "tax_engine.calculate_tax",
        "tax_engine.calculate_gst_qst",
        "tax_engine.calculate_taxes_for_recipient",
        "vehicle_pricing.calculate_taxes",
        "fee_calculator.tax_on",
        "fee_calculator.calculate_partner_taxes",
        "invoice_service.calculate_province_tax",
        "tax_dashboard.compute_tax_for_transaction",
    ]
    rows: list[dict] = []
    for prov in PROVINCES:
        for amount in AMOUNTS:
            exp = expected_tax_total(prov, amount)
            for calc in calculators:
                res = run_calculator(calc, prov, amount)
                actual = res.get("total_tax")
                divergence = None
                if actual is not None:
                    try:
                        divergence = str(_q(Decimal(actual) - exp))
                    except Exception:
                        divergence = None
                res["expected_reference"] = str(exp)
                res["divergence"] = divergence
                rows.append(res)

    # Aggregate divergence per calculator
    per_calc: dict[str, dict] = {}
    for r in rows:
        c = r["calculator"]
        per_calc.setdefault(c, {"matches": 0, "diverges": 0, "errors": 0})
        if r.get("error"):
            per_calc[c]["errors"] += 1
        elif r.get("divergence") == "0.00":
            per_calc[c]["matches"] += 1
        else:
            per_calc[c]["diverges"] += 1

    out = {
        "audit": "P6.1.1 — Calculator Divergence Matrix",
        "calculators_tested": calculators,
        "provinces": PROVINCES,
        "amounts": [str(a) for a in AMOUNTS],
        "reference_note": (
            "Reference = CRA 2026 GST/HST (NS=14%) + QST for QC only. "
            "PST/RST for BC/SK/MB NOT collected by BidVex per current "
            "internal legal position (see tax_rate_config.py comments)."
        ),
        "rows": rows,
        "summary_per_calculator": per_calc,
    }
    Path("/app/backend/tests/iter496_2/calculator_matrix.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, default=str)
    )
    print(json.dumps({"summary": per_calc}, indent=2))
    return out


if __name__ == "__main__":
    main()
