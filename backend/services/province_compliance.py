"""
services/province_compliance.py — iter295 P0

Single source of truth for Canadian-province vehicle-purchase
compliance rules. Replaces the previously duplicated
`RESTRICTED_PROVINCES` constants that lived inside
`routes/vehicle_buyer_verification.py` and were re-imported by every
caller (vehicles.py, vehicle_multi_lot.py, broker compliance tests,
etc.).

Regulator map (Canada):
    ON  — OMVIC          (Ontario)         → restricted
    NB  — NBMVRA         (New Brunswick)   → restricted
    NS  — UARB           (Nova Scotia)     → restricted
    PE  — IRAC           (PEI)             → restricted
    NL  — DMVR           (Newfoundland)    → restricted
    QC  — OPC / SAAQ     (Quebec)          → open + LPC disclosure
    BC  — VSA            (British Columbia)→ open
    AB  — AMVIC          (Alberta)         → open
    SK  — SMVID          (Saskatchewan)    → open
    MB  — MPI / RBM      (Manitoba)        → open
    YT / NT / NU         (Territories)     → advisory only

A "restricted" province bars individual buyers from bidding directly
on dealer vehicle auctions unless they have either:
    1. Verified themselves as a dealer / dealer rep (existing flow), or
    2. Bound an approved broker (broker-buyer relationship).
"""
from __future__ import annotations

from typing import Optional, Set


# ── Constants ──────────────────────────────────────────────────────────

RESTRICTED_PROVINCES: Set[str] = {"ON", "NB", "NS", "PE", "NL"}
"""Provinces where individual buyers are HARD-BLOCKED unless they
verify as a dealer / rep OR bind an approved broker."""

OPEN_PROVINCES: Set[str] = {"BC", "AB", "SK", "MB"}
"""Provinces where individual buyers may bid without a broker gate."""

QC_DISCLOSURE_PROVINCE: str = "QC"
"""Quebec — allowed but requires per-listing LPC (Loi sur la
protection du consommateur) disclosure acknowledgement."""

TERRITORY_PROVINCES: Set[str] = {"YT", "NT", "NU"}
"""Territories — advisory only; not restricted, not gated."""

ALL_KNOWN_PROVINCES: Set[str] = (
    RESTRICTED_PROVINCES
    | OPEN_PROVINCES
    | TERRITORY_PROVINCES
    | {QC_DISCLOSURE_PROVINCE}
)


# ── Helpers ────────────────────────────────────────────────────────────

def is_restricted_province(code: Optional[str]) -> bool:
    """True if the given two-letter code is a restricted (broker-gated)
    province. Case-insensitive; safe with None/empty input."""
    if not code:
        return False
    return code.strip().upper() in RESTRICTED_PROVINCES


def is_open_province(code: Optional[str]) -> bool:
    if not code:
        return False
    return code.strip().upper() in OPEN_PROVINCES


def is_territory(code: Optional[str]) -> bool:
    if not code:
        return False
    return code.strip().upper() in TERRITORY_PROVINCES


def get_buyer_province(user_doc: Optional[dict]) -> Optional[str]:
    """Read the buyer's province preference from a user dict. Prefer the
    structured `province` field; tolerate falsy/whitespace input.

    Returns the upper-case two-letter code if valid, else None.
    """
    if not user_doc:
        return None
    p = (
        user_doc.get("province")
        or user_doc.get("location_province")
        or ""
    ).strip().upper()
    if p in ALL_KNOWN_PROVINCES:
        return p
    return None
