"""
P7 conftest — shared cent-perfect helpers.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Union

Number = Union[int, float, str, Decimal]


def to_cents(x: Number) -> int:
    """Convert any numeric to integer cents (banker-safe HALF_UP).

    Never uses ``float()`` for the final quantisation — the ``Decimal``
    constructor takes a string so 0.1 doesn't become 0.100000000...004.
    """
    d = Decimal(str(x))
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((q * 100).to_integral_value(ROUND_HALF_UP))


def cents_to_str(c: int) -> str:
    """Pretty-print cents as $X.YY for report output."""
    sign = "-" if c < 0 else ""
    v = abs(c)
    return f"{sign}${v // 100}.{v % 100:02d}"


def diff_cents(actual: int, expected: int) -> int:
    return actual - expected


# ─── Classification enums used across P7 tests ──────────────────────
CLASS_A_EXPECTED = "A_expected_current_behavior"
CLASS_B_TECHNICAL_DEFECT = "B_technical_defect"
CLASS_C_LEGAL_REVIEW = "C_requires_tax_legal_review"
CLASS_D_KNOWN_P6 = "D_known_p6_consolidation_issue"

VALID_CLASSES = {
    CLASS_A_EXPECTED,
    CLASS_B_TECHNICAL_DEFECT,
    CLASS_C_LEGAL_REVIEW,
    CLASS_D_KNOWN_P6,
}


def make_case_id(prefix: str, *parts: Any) -> str:
    """Stable ID for pytest parametrize — printable in test output."""
    slug = "_".join(str(p).replace(".", "p").replace("-", "n").replace("$", "") for p in parts)
    return f"{prefix}__{slug}"
