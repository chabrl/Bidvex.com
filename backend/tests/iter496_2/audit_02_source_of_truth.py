"""P6.1.1 — Internal Source-of-Truth reconciliation (READ-ONLY).

Compares BOOTSTRAP_RATES (services/tax_rate_config.py) against live
db.tax_rate_config, then reconciles both against authoritative CRA 2026
rates. Emits a divergence table to internal_source_of_truth.json.

NEVER writes to the DB. Never edits any production file.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "/app/backend")

from services.tax_rate_config import BOOTSTRAP_RATES, normalize_province  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

# ── Authoritative CRA 2026 (verified via canada.ca on 2026-02-17) ──────
# Source: https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html
# NS = 14% effective April 1, 2025 (CRA Notice 342).
CRA_2026_GST_HST: dict[str, Decimal] = {
    "AB": Decimal("0.05"),   # GST only
    "BC": Decimal("0.05"),   # GST only (federal); provincial PST 7% is separate
    "MB": Decimal("0.05"),   # GST only (federal); provincial RST 7% is separate
    "NB": Decimal("0.15"),   # HST
    "NL": Decimal("0.15"),   # HST
    "NS": Decimal("0.14"),   # HST — 14% since 2025-04-01 (Notice 342)
    "NT": Decimal("0.05"),   # GST only
    "NU": Decimal("0.05"),   # GST only
    "ON": Decimal("0.13"),   # HST
    "PE": Decimal("0.15"),   # HST
    "QC": Decimal("0.05"),   # GST (federal); provincial QST 9.975% is separate
    "SK": Decimal("0.05"),   # GST only (federal); provincial PST 6% is separate
    "YT": Decimal("0.05"),   # GST only
    "INTL": Decimal("0.00"), # ETA Sched. VI Part V §7 zero-rated (per code)
}

# Provincial-side taxes (NOT GST/HST — separately administered by province)
CRA_2026_PROVINCIAL_PST_RST: dict[str, Decimal] = {
    "QC": Decimal("0.09975"),  # QST — Revenu Québec
    "BC": Decimal("0.07"),     # PST — Ministry of Finance BC
    "SK": Decimal("0.06"),     # PST — Government of Saskatchewan
    "MB": Decimal("0.07"),     # RST — Manitoba Finance (7% since Jul 2019)
    # AB, HST provinces, territories, INTL: no separate provincial layer
}


def _to_dec(x) -> Decimal:
    return Decimal(str(x))


async def load_db_rates() -> list[dict]:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        return []
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    docs = await db.tax_rate_config.find({}, {"_id": 0}).to_list(length=100)
    client.close()
    return docs


def build_reconciliation(db_docs: list[dict]) -> list[dict]:
    db_by_prov = {d.get("province"): d for d in db_docs}
    rows: list[dict] = []
    for prov in sorted(BOOTSTRAP_RATES.keys()) + ["US"]:
        code = normalize_province(prov) if prov != "US" else "INTL"  # US alias
        bootstrap = BOOTSTRAP_RATES.get(code, BOOTSTRAP_RATES["INTL"])
        db_row = db_by_prov.get(code) or {}
        bs_gst = _to_dec(bootstrap["gst"])
        bs_hst = _to_dec(bootstrap["hst"])
        bs_qst = _to_dec(bootstrap["qst"])
        bs_combined = _to_dec(bootstrap["combined"])
        db_combined = _to_dec(db_row.get("combined", "0"))
        cra_federal = CRA_2026_GST_HST.get(code, Decimal("0"))
        cra_pst_rst = CRA_2026_PROVINCIAL_PST_RST.get(code, Decimal("0"))
        # "Federal-only" bootstrap value for compare
        bs_federal_only = bs_gst + bs_hst
        federal_match = bs_federal_only == cra_federal
        db_match_bootstrap = db_combined == bs_combined if db_row else None
        rows.append({
            "province": code,
            "bootstrap": {
                "gst": str(bs_gst),
                "hst": str(bs_hst),
                "qst_or_pst": str(bs_qst),
                "combined": str(bs_combined),
                "label": bootstrap.get("label", ""),
            },
            "db_row_present": bool(db_row),
            "db_combined": str(db_combined) if db_row else None,
            "authoritative_cra_2026": {
                "federal_gst_hst": str(cra_federal),
                "provincial_pst_rst": str(cra_pst_rst) if cra_pst_rst else "0",
                "provincial_authority": {
                    "QC": "Revenu Québec (QST)",
                    "BC": "BC Ministry of Finance (PST)",
                    "SK": "Government of Saskatchewan (PST)",
                    "MB": "Manitoba Finance (RST)",
                }.get(code, "N/A"),
            },
            "bootstrap_federal_matches_cra": bool(federal_match),
            "db_matches_bootstrap": db_match_bootstrap,
            "classification": (
                "GREEN — federal matches CRA and no PST layer"
                if federal_match and not cra_pst_rst
                else "GREEN — federal matches CRA; PST/RST/QST tracked separately"
                if federal_match and cra_pst_rst
                else "RED — federal does NOT match authoritative CRA 2026"
            ),
        })
    return rows


async def main() -> dict:
    db_docs = await load_db_rates()
    rows = build_reconciliation(db_docs)
    reds = [r for r in rows if r["classification"].startswith("RED")]
    ambers = [r for r in rows if r["classification"].startswith("AMBER")]
    out = {
        "audit": "P6.1.1 — Internal Source-of-Truth Reconciliation",
        "authoritative_source": "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html",
        "authoritative_source_ns_notice": "https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/notice342.html",
        "row_count": len(rows),
        "red_findings": len(reds),
        "amber_findings": len(ambers),
        "db_rows_loaded": len(db_docs),
        "rows": rows,
    }
    Path("/app/backend/tests/iter496_2/internal_source_of_truth.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, default=str)
    )
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return out


if __name__ == "__main__":
    asyncio.run(main())
