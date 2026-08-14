"""
P7 — Cent-perfect snapshot regression suite.

Each calculator is run against a matrix of inputs and asserted equal
to the previously-captured golden JSON in ``golden/``.  Any drift
fails the test with the exact key + expected/actual cents delta.

Classification of every row is documented in
``/app/docs/P7_CENT_PERFECT_REGRESSION_REPORT.md``.

To refresh the golden files after an INTENTIONAL calculator change:
    cd /app/backend && python -m tests.p7.generate_golden_snapshots
Then review the diff in git before committing.
"""
from __future__ import annotations
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

import pytest

from services.fee_calculator import calculate_fee
from services.tax_engine import (
    calculate_tax as legacy_calculate_tax,
    calculate_vehicle_payment as legacy_calc_vehicle,
    calculate_general_payment as legacy_calc_general,
    calculate_gst_qst as legacy_calc_gst_qst,
    calculate_taxes_for_recipient as legacy_calc_recipient,
)
from services.broker_fee_engine import calculate_broker_transaction
from services.invoice_service import calculate_province_tax


GOLDEN = Path(__file__).resolve().parent / "golden"


def _r(x) -> int:
    """Round to integer cents."""
    return int((Decimal(str(x)) * 100).quantize(Decimal("1")))


def _load(name: str) -> Dict[str, Any]:
    path = GOLDEN / f"{name}.json"
    with path.open() as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────
# P7-B — Canonical fee_calculator snapshot
# ─────────────────────────────────────────────────────────────────
_CANON = _load("canonical_fee_calculator")


def _dispatch_canonical(key: str) -> Dict[str, Any]:
    """Rehydrate a call from the snapshot key."""
    parts = key.split("|")
    st = parts[0]
    if st == "individual":
        _, amount, buyer_prov, seller_prov, payment = parts
        return calculate_fee(
            hammer_price=float(amount), auction_type="timed",
            seller_account_type="individual", seller_tier="free",
            buyer_province=buyer_prov, seller_province=seller_prov,
            payment_method=payment,
        )
    if st == "partner":
        _, amount, partner_prov, buyer_prov, bp_rate = parts
        return calculate_fee(
            hammer_price=float(amount), auction_type="timed",
            seller_account_type="partner",
            buyer_province=buyer_prov, partner_province=partner_prov,
            partner_bp_rate=float(bp_rate),
        )
    if st == "vehicle_dealer":
        _, amount, buyer_prov = parts
        return calculate_fee(
            hammer_price=float(amount), auction_type="timed",
            seller_account_type="vehicle_dealer",
            buyer_province=buyer_prov,
        )
    if st == "storage":
        _, amount, facility_prov, buyer_prov, payment = parts
        return calculate_fee(
            hammer_price=float(amount), auction_type="timed",
            seller_account_type="storage_facility",
            facility_province=facility_prov, buyer_province=buyer_prov,
            payment_method=payment,
        )
    if st == "missing":
        # key form: "missing|repr(bad)"
        raw = parts[1]
        if raw == "None":
            val = None
        else:
            # strip the outer quotes from repr('...') form
            val = raw.strip().strip("'").strip('"')
        return calculate_fee(
            hammer_price=100.00, auction_type="timed",
            seller_account_type="individual", seller_tier="free",
            buyer_province=val, seller_province=val,
        )
    raise ValueError(f"Unknown snapshot key: {key}")


@pytest.mark.parametrize("key", sorted(_CANON.keys()))
def test_p7_canonical_snapshot(key):
    """Cent-perfect canonical calculator regression.

    Classification: **A — Expected current behavior.**
    A failure here means production math drifted; the operator must
    regenerate the golden file INTENTIONALLY via
    ``python -m tests.p7.generate_golden_snapshots``.
    """
    expected = _CANON[key]
    r = _dispatch_canonical(key)
    diffs = []
    for k, exp_v in expected.items():
        actual = r.get(k)
        if isinstance(exp_v, int) and isinstance(actual, (int, float)):
            act_cents = _r(actual)
            if act_cents != exp_v:
                diffs.append(f"{k}: expected={exp_v}c actual={act_cents}c delta={act_cents-exp_v}c")
        elif exp_v != actual:
            diffs.append(f"{k}: expected={exp_v!r} actual={actual!r}")
    assert not diffs, f"canonical snapshot drift on {key}:\n  " + "\n  ".join(diffs)


# ─────────────────────────────────────────────────────────────────
# P7-C — Legacy tax_engine snapshot
# Classification: **D — Known P6 consolidation issue**.  The legacy
# engine hardcodes QC 14.975%.  This suite locks its CURRENT behavior
# so P6 refactor cannot silently move a penny; it does NOT claim the
# behavior is correct.  See P6_RISK_MATRIX §2 / §5.
# ─────────────────────────────────────────────────────────────────
_LEGACY = _load("legacy_tax_engine")


def _dispatch_legacy(key: str):
    parts = key.split("|")
    kind = parts[0]
    amount = parts[1]
    if kind == "legacy_calculate_tax":
        t = legacy_calculate_tax(Decimal(str(amount)))
        return {
            "gst_cents": t.gst_amount_cents,
            "qst_cents": t.qst_amount_cents,
            "total_tax_cents": t.total_tax_cents,
            "total_with_tax_cents": t.total_with_tax_cents,
        }
    if kind == "legacy_vehicle":
        v = legacy_calc_vehicle(float(amount), "basic")
        return v.to_dict()
    if kind == "legacy_general":
        g = legacy_calc_general(float(amount), "basic")
        return g.to_dict()
    if kind == "legacy_gst_qst_cad":
        return legacy_calc_gst_qst(float(amount), currency="CAD")
    if kind == "legacy_gst_qst_usd":
        return legacy_calc_gst_qst(float(amount), currency="USD")
    if kind == "legacy_recipient":
        prov = parts[2] if parts[2] != "MISSING" else ""
        r = legacy_calc_recipient(float(amount), province=prov)
        # Normalise to snapshot key names
        return {
            "gst": r.get("gst_amount", r.get("gst", 0)),
            "qst": r.get("qst_amount", r.get("qst", 0)),
            "hst": r.get("hst_amount", r.get("hst", 0)),
            "total_tax": r.get("total_tax", 0),
            "province": r.get("province"),
        }
    raise ValueError(f"Unknown legacy key: {key}")


@pytest.mark.parametrize("key", sorted(_LEGACY.keys()))
def test_p7_legacy_tax_engine_snapshot(key):
    """CURRENT behavior of the legacy tax_engine.

    Classification: **D** for the QC-hardcoded rows (`legacy_calculate_tax`,
    `legacy_vehicle`, `legacy_general`, `legacy_gst_qst_cad`).
    Classification: **A** for `legacy_gst_qst_usd` (correctly zero-rated
    for non-CAD).
    Classification: **A** for `legacy_recipient` (province-aware helper —
    the ONE legacy helper that already reads from tax_rate_config).
    """
    expected = _LEGACY[key]
    r = _dispatch_legacy(key)
    diffs = []
    for k, exp_v in expected.items():
        actual = r.get(k)
        if isinstance(exp_v, int) and isinstance(actual, (int, float)):
            # Fields whose snapshot value is already in cents (name ends
            # with "_cents") must be compared without extra multiplication.
            if k.endswith("_cents"):
                act_cents = int(actual)
            else:
                act_cents = _r(actual)
            if act_cents != exp_v:
                diffs.append(f"{k}: expected={exp_v}c actual={act_cents}c delta={act_cents-exp_v}c")
        elif exp_v != actual:
            diffs.append(f"{k}: expected={exp_v!r} actual={actual!r}")
    assert not diffs, f"legacy_tax_engine snapshot drift on {key}:\n  " + "\n  ".join(diffs)


# ─────────────────────────────────────────────────────────────────
# P7-D — broker_fee_engine snapshot (QST-or-zero bug locked-in)
# Classification: **C — REQUIRES_TAX_LEGAL_REVIEW**.
# Documented in P6_RISK_MATRIX Risk #1 (under-collection on HST provinces).
# ─────────────────────────────────────────────────────────────────
_BROKER = _load("broker_fee_engine")

_BROKER_FS = {"type": "percentage", "rate_value": 0.03}


@pytest.mark.parametrize("key", sorted(_BROKER.keys()))
def test_p7_broker_fee_snapshot(key):
    """Locks the broker_fee_engine's current QST-or-zero behavior.

    Classification: **C** — the buyer in ON pays 5% GST instead of
    13% HST (under-collection of ~8% of the service fees).  DO NOT
    FIX in P7.  Recorded here so any future edit trips the test.
    """
    expected = _BROKER[key]
    _, amount, buyer_prov = key.split("|")
    if buyer_prov == "MISSING":
        buyer_prov_arg = None
    else:
        buyer_prov_arg = buyer_prov
    r = calculate_broker_transaction(
        hammer_price=float(amount),
        broker_fee_structure=_BROKER_FS,
        buyer_province=buyer_prov_arg,
        deposit_held_cad=500.0,
    )
    diffs = []
    for k, exp_v in expected.items():
        actual = r.get(k)
        if isinstance(exp_v, int) and isinstance(actual, (int, float)):
            act_cents = _r(actual)
            if act_cents != exp_v:
                diffs.append(f"{k}: expected={exp_v}c actual={act_cents}c delta={act_cents-exp_v}c")
    assert not diffs, f"broker_fee snapshot drift on {key}:\n  " + "\n  ".join(diffs)


# ─────────────────────────────────────────────────────────────────
# P7-E — invoice_service snapshot (missing-province → QC bug locked-in)
# Classification: **D — Known P6 consolidation issue**.
# When buyer_province is missing / unknown, the invoice defaults to
# QC 14.975% (over-collection).  Recorded here for P6 to fix, not P7.
# ─────────────────────────────────────────────────────────────────
_INVOICE = _load("invoice_service")


@pytest.mark.parametrize("key", sorted(_INVOICE.keys()))
def test_p7_invoice_service_snapshot(key):
    """Locks invoice_service.calculate_province_tax current behavior.

    Classification per key:
      * QC/ON/AB/BC rows        → **A** (correct behavior)
      * MISSING / ZZ rows       → **D** (silently defaults to QC — P6 fix)
    """
    expected = _INVOICE[key]
    _, amount, prov = key.split("|")
    if prov == "MISSING":
        prov_arg = ""
    else:
        prov_arg = prov
    r = calculate_province_tax(Decimal(str(amount)), buyer_province=prov_arg)
    actual = {
        "gst_cents": _r(r.tax_gst),
        "qst_cents": _r(r.tax_pst_qst),
        "hst_cents": _r(r.tax_hst),
        "total_tax_cents": _r(r.total_tax),
        "province": r.province,
        "tax_type": r.tax_type,
    }
    assert actual == expected, (
        f"invoice_service snapshot drift on {key}:\n"
        f"  expected: {expected}\n  actual:   {actual}"
    )


# ─────────────────────────────────────────────────────────────────
# P7-F — Explicit critical-risk assertions (fingerprint the KNOWN bugs)
# These tests EXIST so if the underlying bug is ever silently "fixed",
# the P7 suite fails and forces a report update.
# ─────────────────────────────────────────────────────────────────
class TestKnownP6Risks:
    """Named regression fingerprints for every P6 risk in the audit."""

    def test_risk_broker_qst_or_zero_underfines_hst_ontario(self):
        """RISK: `broker_fee_engine` charges 5% GST + 0 QST on ON buyer,
        instead of 13% HST.  UNDER-collection = ~$4.68 per $100 fees."""
        r = calculate_broker_transaction(
            hammer_price=100_000.0,
            broker_fee_structure=_BROKER_FS,
            buyer_province="ON",
            deposit_held_cad=500.0,
        )
        # Actual current behavior — QST is zero on ON, GST is 5% of subtotal
        assert _r(r["qst"]) == 0, "REPORT: broker no longer under-collects — refresh P6_RISK_MATRIX §1"
        expected_gst = _r(Decimal(str(r["subtotal_taxable"])) * Decimal("0.05"))
        assert _r(r["gst"]) == expected_gst

    def test_risk_invoice_silently_defaults_missing_province_to_qc(self):
        """RISK: `invoice_service.calculate_province_tax('')` returns QC
        14.975% instead of INTL 0%.  OVER-collection on non-QC buyers."""
        r = calculate_province_tax(Decimal("100"), buyer_province="")
        assert r.province == "QC", "REPORT: invoice_service no longer defaults to QC — refresh P6_RISK_MATRIX §5"
        # And it computes the QC combined rate
        assert _r(r.total_tax) == 1498  # $14.98 on $100

    def test_risk_legacy_calc_tax_hardcodes_qc_1497(self):
        """RISK: `tax_engine.calculate_tax(100)` hardcodes 14.975% regardless
        of caller's province.  Locks the current behavior."""
        t = legacy_calculate_tax(Decimal("100"))
        assert t.total_tax_cents == 1498  # QC 14.975% on $100

    def test_risk_canonical_missing_province_falls_to_intl(self):
        """SAFETY: the CANONICAL fee_calculator MUST NOT silently default
        to QC.  This is the invariant we want P6 to spread to legacy calcs."""
        r = calculate_fee(
            hammer_price=100.00, auction_type="timed",
            seller_account_type="individual", seller_tier="free",
            buyer_province=None, seller_province=None,
        )
        assert r["buyer_tax_province"] == "INTL"
        assert _r(r["buyer_taxes"]) == 0

    def test_risk_canonical_no_hst_leakage_on_ab_bc(self):
        """SAFETY: the CANONICAL calc treats AB/BC as 5% GST, NOT the QC
        combined rate.  Prevents over-collection on non-HST GST provinces."""
        for prov in ("AB", "BC"):
            r = calculate_fee(
                hammer_price=100.00, auction_type="timed",
                seller_account_type="individual", seller_tier="free",
                buyer_province=prov, seller_province=prov,
            )
            assert r["buyer_tax_province"] == prov
            assert abs(float(r["tax_rate"]) - 0.05) < 1e-9, r
