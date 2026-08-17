"""P6.2 Gate 4 — QC-only legacy calculators explicitly documented.

Gate 4 policy: `tax_engine.calculate_tax` and `tax_engine.calculate_gst_qst`
are QC-only preview helpers used solely by
`routes/payments_fees.py::/api/tax/calculate`, `.../tax/general`,
`.../tax/vehicle` — endpoints whose docstrings explicitly say
"Quebec taxes". They MUST NOT be used for province-aware calculation.

These regression tests:
1. Lock in the QC 14.975% behaviour so any silent-widening (e.g. a
   generic new caller) fails.
2. Verify `calculate_taxes_for_recipient` is the correct
   province-aware entry point.
3. Verify NEW imports of the deprecated helpers do not appear
   outside their known callers.
"""
from __future__ import annotations

import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, "/app/backend")

from services.tax_engine import (  # noqa: E402
    calculate_tax,
    calculate_gst_qst,
    calculate_taxes_for_recipient,
    GST_RATE, QST_RATE, COMBINED_TAX_RATE,
)


# ── QC-only behaviour is preserved (documented lock) ────────────────
def test_calculate_tax_is_qc_hardcoded_gst_5_qst_9_975():
    """Confirms the QC-only preview helper still returns 14.975% on $100."""
    r = calculate_tax(Decimal("100"))
    assert r.gst_amount == 5.00
    assert r.qst_amount == 9.98
    assert r.total_tax == 14.98
    assert r.total_with_tax == 114.98


def test_calculate_gst_qst_is_qc_hardcoded():
    r = calculate_gst_qst(100.0)
    assert r["province"] == "QC"
    assert r["total_tax"] == 14.98


# ── Province-aware alternative works ─────────────────────────────────
def test_calculate_taxes_for_recipient_is_province_aware():
    """The canonical alternative reads DB-backed rates per province."""
    for prov, expected_rate in [
        ("QC", Decimal("0.14975")),
        ("ON", Decimal("0.13")),
        ("AB", Decimal("0.05")),
        ("BC", Decimal("0.05")),
        ("SK", Decimal("0.05")),
        ("MB", Decimal("0.05")),
        ("NS", Decimal("0.14")),
        ("NB", Decimal("0.15")),
        ("INTL", Decimal("0")),
    ]:
        r = calculate_taxes_for_recipient(100.0, prov)
        expected_tax = Decimal(str(r["total_tax"]))
        assert (expected_tax - Decimal("100") * expected_rate).copy_abs() <= Decimal("0.02"), (prov, r)


# ── Import-graph lint: no NEW callers of the deprecated helpers ────
def test_no_new_production_imports_of_deprecated_calculate_tax():
    """P6.2 Gate 4 — allowlist of files permitted to import calculate_tax.
    New RED imports outside this list fail this test."""
    allowlist = {
        # Internal callers within tax_engine itself + routes.tax + legacy tests
        "services/tax_engine.py",
        "routes/tax.py",
        "routes/payments_fees.py",  # QC-preview endpoints
        "invoice_templates.py",     # legacy templating
        "tests/",                    # allowed everywhere in tests
    }
    backend = Path("/app/backend")
    offenders: list[str] = []
    pattern = re.compile(r"from services\.tax_engine import[^\n]*\bcalculate_tax\b|"
                         r"from services\.tax_engine import[^\n]*\bcalculate_gst_qst\b")
    for p in backend.rglob("*.py"):
        rel = p.relative_to(backend).as_posix()
        if any(rel.startswith(a) or rel == a for a in allowlist):
            continue
        try:
            content = p.read_text()
        except UnicodeDecodeError:
            continue
        if pattern.search(content):
            offenders.append(rel)
    assert not offenders, (
        f"NEW callers of QC-only calculate_tax/calculate_gst_qst detected. "
        f"Migrate them to calculate_taxes_for_recipient. Offenders:\n  " +
        "\n  ".join(offenders)
    )
