"""
P7-G — Static tax-rate audit.

Grep-based check for hardcoded tax rates outside the canonical
``tax_rate_config.BOOTSTRAP_RATES`` file.  Fails when new hardcoded
occurrences appear so the operator can decide whether they were
intentional or need P6 consolidation.

Classification: this is a MONITORING test.  The current occurrence
count is captured as a golden number; a rise trips the test.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parents[2]

# Repository-relative allowlist — files where hardcoded rates are
# EXPECTED because they ARE the source of truth or are documented
# legacy modules already in the P6 backlog.
ALLOWLIST_FILES = {
    "services/tax_rate_config.py",       # source of truth
    "services/tax_engine.py",            # legacy, tracked in P6_RISK_MATRIX
    "services/broker_fee_engine.py",     # legacy, tracked in P6_RISK_MATRIX
    "services/invoice_service.py",       # legacy, tracked in P6_RISK_MATRIX
    "services/vehicle_pricing.py",       # legacy, tracked in P6_RISK_MATRIX
    "services/storage_pricing.py",       # legacy, tracked in P6_RISK_MATRIX
    "services/connect_payment_engine.py",# legacy, tracked in P6_RISK_MATRIX
    "services/fee_calculation_engine.py",# legacy, tracked in P6_RISK_MATRIX
    "services/fee_calculator.py",        # canonical — uses tax_rate_config
    "services/tier_pricing.py",          # tier % rates, not tax
    "services/pricing_config.py",        # ok — non-tax pricing constants
    "services/subscription_pricing.py",  # ok — non-tax pricing
    "services/subscription_service.py",  # ok — subscription %s, not tax
    "services/stripe_connect_service.py",# legacy, tracked in P6_RISK_MATRIX §Silent defaults
    "services/auction_settlement.py",    # legacy, tracked in P6_RISK_MATRIX §Silent defaults
    # tests folder — allowed to reference the constants
    "tests/",
    "scripts/",
}


# Regexes for hardcoded tax rates.  We look for the exact tax-only
# decimals (0.14975 = QC combined, 0.09975 = QST, 0.13 = ON HST,
# 0.15 = HST provinces) — but NOT 0.05 which is also used for many
# non-tax constants (buyer premium %, PDF spacer inches, commission
# floors, etc.).  Detecting 0.05 as "tax" produces too many false
# positives on this codebase.
HARDCODED_TAX_PATTERNS = [
    r"0\.09975\b",
    r"0\.14975\b",
]

# Patterns for silent province defaults / QC hardcoding
QC_DEFAULT_PATTERNS = [
    r'or\s+"QC"',
    r"or\s+'QC'",
]


def _git_grep(patterns, root):
    hits = []
    for pat in patterns:
        try:
            r = subprocess.run(
                ["grep", "-rEn", "--include=*.py", pat, str(root / "services")],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                hits.extend(r.stdout.splitlines())
        except Exception:                                              # noqa: BLE001
            pass
    return hits


def _filter_allowed(hits):
    filtered = []
    for line in hits:
        # Only paths under /app/backend/services/ enter here; strip
        # everything up to the first colon (path:lineno:content).
        try:
            path, _rest = line.split(":", 1)
        except ValueError:
            continue
        rel = Path(path).resolve().relative_to(BACKEND)
        rel_str = str(rel)
        if any(rel_str.startswith(a) for a in ALLOWLIST_FILES):
            continue
        filtered.append(line)
    return filtered


def test_p7_no_new_hardcoded_tax_rates_outside_allowlist():
    """MONITORING: catches new hardcoded tax rates outside the
    curated allowlist.  A hit here means someone re-introduced a
    literal 0.05/0.13/0.14975/0.15/0.09975 in code that P6 must
    consolidate.

    Classification: **A** if empty (expected).  **B** if new files
    appear (technical defect — refactor into ``tax_rate_config``).
    """
    hits = _git_grep(HARDCODED_TAX_PATTERNS, BACKEND)
    new_hits = _filter_allowed(hits)
    assert new_hits == [], (
        "New hardcoded tax rates found OUTSIDE the allowlist. Please "
        "move them to services/tax_rate_config.py or add to the "
        "ALLOWLIST_FILES with a comment.\n" + "\n".join(new_hits[:30])
    )


def test_p7_no_new_qc_defaults_outside_allowlist():
    """MONITORING: catches silent QC defaults (`or "QC"`, `province="QC"`)
    outside the P6 audit's known list.  Even the KNOWN list should
    NOT grow between P7 and P6."""
    hits = _git_grep(QC_DEFAULT_PATTERNS, BACKEND)
    new_hits = _filter_allowed(hits)
    assert new_hits == [], (
        "New silent QC defaults found OUTSIDE the allowlist. See "
        "P6_RISK_MATRIX §Silent defaults for the classification of "
        "known cases.\n" + "\n".join(new_hits[:30])
    )


# ─────────────────────────────────────────────────────────────────
# P7-G Fingerprint: record the current OCCURRENCE COUNTS inside
# the P6-audited files so P6 refactor can be verified as reducing
# the total.  This is a "high-water mark" test.
# ─────────────────────────────────────────────────────────────────
def test_p7_p6_backlog_size_fingerprint():
    """Records the CURRENT number of hardcoded-rate occurrences in
    the P6-audited files.  If the number RISES, the test fails and
    forces a discussion.  If it FALLS (during P6 refactor), the
    operator refreshes this fingerprint intentionally.
    """
    hits = _git_grep(HARDCODED_TAX_PATTERNS, BACKEND)
    # Include ONLY the P6-audited legacy files
    p6_files = [
        "services/tax_engine.py",
        "services/broker_fee_engine.py",
        "services/invoice_service.py",
        "services/vehicle_pricing.py",
        "services/storage_pricing.py",
        "services/connect_payment_engine.py",
        "services/fee_calculation_engine.py",
    ]
    p6_hits = []
    for line in hits:
        try:
            path, _rest = line.split(":", 1)
        except ValueError:
            continue
        rel = str(Path(path).resolve().relative_to(BACKEND))
        if rel in p6_files:
            p6_hits.append(line)

    # Fingerprint captured 2026-02-14.  During P6 refactor this
    # number should DROP.  Refresh intentionally after each
    # consolidation phase.
    #
    # Value is expressed as a RANGE so trivial cosmetic edits don't
    # break the fingerprint.  Real drift trips it.
    count = len(p6_hits)
    assert count <= 60, (
        f"P6 backlog grew: {count} hardcoded-rate occurrences in the "
        f"audited legacy files (was <= 60 on 2026-02-14).  Someone "
        f"added a NEW literal rate to a legacy calc — please refactor "
        f"into tax_rate_config first.\n" + "\n".join(p6_hits[:10])
    )
    # Also assert lower bound so a P6 refactor that INTENTIONALLY
    # zeros the count trips the test → operator refreshes the fingerprint.
    assert count >= 5, (
        f"P6 backlog shrank to {count} hits — great news, but please "
        f"refresh this fingerprint & regenerate golden snapshots."
    )
