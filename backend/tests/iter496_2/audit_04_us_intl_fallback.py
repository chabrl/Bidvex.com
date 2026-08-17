"""P6.1.1 — US/INTL fallback trace + PST/RST decomposition (READ-ONLY).

Enumerates every occurrence of US / INTL / '' being coerced to another
value (QC, ALBERTA, INTL) across the 8 tax calculators and their file
neighbourhood. Emits us_intl_fallback.json.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

TARGET_FILES = [
    "/app/backend/services/tax_engine.py",
    "/app/backend/services/tax_rate_config.py",
    "/app/backend/services/invoice_service.py",
    "/app/backend/services/vehicle_pricing.py",
    "/app/backend/services/fee_calculator.py",
    "/app/backend/routes/tax_dashboard.py",
    "/app/backend/services/auction_settlement.py",
    "/app/backend/services/stripe_connect_service.py",
    "/app/backend/services/connect_payment_engine.py",
    "/app/backend/routes/auctions.py",
    "/app/backend/routes/auctions_bids.py",
    "/app/backend/routes/broker_compliance.py",
    "/app/backend/routes/fees.py",
    "/app/backend/routes/invoices.py",
    "/app/backend/routes/partner_card.py",
    "/app/backend/routes/payments.py",
    "/app/backend/services/broker_fee_engine.py",
    "/app/backend/services/invoice_generator.py",
]

# Patterns of fallback coercion to inspect.
PATTERNS = {
    "silent_QC_default": r'or\s+"QC"|=\s*"QC"|default[_\s]*=?\s*"QC"|Province\.QUEBEC\s+#\s*default',
    "silent_ALBERTA_default": r"Province\.ALBERTA",
    "US_to_QC": r'"US".*"QC"|USA.*QC',
    "US_or_INTL_zero_rated": r'"US"[^\n]*(0|zero|INTL)|USA[^\n]*(0|zero|INTL)|INTL[^\n]*0',
    "unknown_province_fallback": r"(unknown|except|else).{0,60}(\"QC\"|Province\.ALBERTA|INTL)",
}


def scan_file(path: str) -> list[dict]:
    hits: list[dict] = []
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        return hits
    lines = text.splitlines()
    for lineno, line in enumerate(lines, 1):
        for pat_name, pat in PATTERNS.items():
            if re.search(pat, line, flags=re.IGNORECASE):
                hits.append({
                    "file": path,
                    "line": lineno,
                    "pattern": pat_name,
                    "excerpt": line.strip()[:180],
                })
    return hits


def classify(hit: dict) -> str:
    """RED/AMBER/BLUE/GREEN/GRAY per operator's confirmed legal input."""
    ex = hit["excerpt"].lower()
    pat = hit["pattern"]
    file = hit["file"]

    # tax_rate_config.py normalize_province → INTL is GREEN (fail-closed).
    if "tax_rate_config" in file and pat == "unknown_province_fallback":
        if "intl" in ex:
            return "GREEN — fail-closed to INTL (0%)"

    # US/USA/INTERNATIONAL → INTL alias in tax_rate_config is GREEN.
    if "tax_rate_config" in file and pat == "US_to_QC":
        return "BLUE — false positive (alias-to-INTL, not QC)"

    # Vehicle_pricing calculate_taxes early-return for US/USA/EU/'' is GREEN
    # (matches confirmed legal position US/INTL = 0%).
    if "vehicle_pricing" in file and pat == "US_or_INTL_zero_rated":
        return "GREEN — early-return 0% for US/USA/EU/'' (confirmed policy)"

    # Any 'or "QC"' silent default outside the alias table is RED.
    if pat == "silent_QC_default":
        return "RED — silent QC default (over-collection risk if unknown)"

    if pat == "silent_ALBERTA_default":
        return "AMBER — silent Alberta fallback (5% GST-only); safer than QC but still not fail-closed"

    return "GRAY — needs manual review"


def main() -> dict:
    all_hits: list[dict] = []
    for f in TARGET_FILES:
        for h in scan_file(f):
            h["classification"] = classify(h)
            all_hits.append(h)

    per_class: dict[str, int] = {}
    for h in all_hits:
        c = h["classification"].split(" ", 1)[0]
        per_class[c] = per_class.get(c, 0) + 1

    out = {
        "audit": "P6.1.1 — US/INTL Fallback Trace",
        "files_scanned": len(TARGET_FILES),
        "hits": len(all_hits),
        "classification_counts": per_class,
        "hits_detail": all_hits,
    }
    Path("/app/backend/tests/iter496_2/us_intl_fallback.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, default=str)
    )
    print(json.dumps({"summary": {"hits": len(all_hits), "counts": per_class}}, indent=2))
    return out


if __name__ == "__main__":
    main()
