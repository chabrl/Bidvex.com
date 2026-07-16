"""
BidVex Tax Rate Configuration — iter350 (CRA / Revenu Québec compliant).

Single source of truth for Canadian GST/HST/QST rates.

Design:
  * Rates live in db.tax_rate_config (one row per province + INTL fallback).
  * Bootstrapped from BOOTSTRAP_RATES on first boot (idempotent).
  * calculate_fee() and any callable that needs a tax rate MUST use
    `get_tax_rate(province)` from this module — NEVER hardcode.
  * Admin editable via /api/admin/pricing/tax-rates (see routes/pricing_engine.py).
  * Effective-date support: `effective_from` on every row so we can
    hot-swap rates when CRA changes them without breaking historical
    invoices (past invoices carry `fee_model_version="iter350"` and the
    snapshot of the rate they used at the time).

Legal basis:
  * Excise Tax Act, R.S.C. 1985, c. E-15, Part IX (GST/HST).
  * CRA GST/HST Technical Information Bulletin B-103.
  * Act respecting the Québec sales tax, R.S.Q., c. T-0.1 (QST).
  * Revenu Québec IN-203-V.

Effective-date policy:
  * Every rate row is stamped with `effective_from` (ISO datetime UTC).
  * When a rate is updated, the OLD row is copied into
    db.tax_rate_config_history keyed on (province, effective_to). This
    provides an immutable audit trail for CRA re-audit of historical
    invoices.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ─── Bootstrap defaults ────────────────────────────────────────────────────
# These are the CRA rates in effect Feb 2026. If CRA changes a rate in the
# future, the operator updates db.tax_rate_config via the admin UI — the code
# never needs to be redeployed.
BOOTSTRAP_RATES: Dict[str, Dict[str, Decimal | str]] = {
    # Quebec — Federal GST 5% + Provincial QST 9.975%
    "QC": {"gst": Decimal("0.05"), "qst": Decimal("0.09975"), "hst": Decimal("0"),
           "combined": Decimal("0.14975"), "label": "GST + QST (14.975%)"},
    # HST provinces (Ontario / Atlantic)
    "ON": {"gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.13"),
           "combined": Decimal("0.13"), "label": "HST (13%)"},
    "NB": {"gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"),
           "combined": Decimal("0.15"), "label": "HST (15%)"},
    "NL": {"gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"),
           "combined": Decimal("0.15"), "label": "HST (15%)"},
    "NS": {"gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"),
           "combined": Decimal("0.15"), "label": "HST (15%)"},
    "PE": {"gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"),
           "combined": Decimal("0.15"), "label": "HST (15%)"},
    # GST-only provinces / territories (PST is the vendor's local obligation
    # in the customer's province; BidVex does not remit PST on B2B services)
    "AB": {"gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"),
           "combined": Decimal("0.05"), "label": "GST (5%)"},
    "BC": {"gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"),
           "combined": Decimal("0.05"), "label": "GST (5%)"},
    "MB": {"gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"),
           "combined": Decimal("0.05"), "label": "GST (5%)"},
    "SK": {"gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"),
           "combined": Decimal("0.05"), "label": "GST (5%)"},
    "YT": {"gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"),
           "combined": Decimal("0.05"), "label": "GST (5%)"},
    "NT": {"gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"),
           "combined": Decimal("0.05"), "label": "GST (5%)"},
    "NU": {"gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"),
           "combined": Decimal("0.05"), "label": "GST (5%)"},
    # Zero-rated — Exported Service per ETA Sched. VI Part V §7
    "INTL": {"gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0"),
             "combined": Decimal("0"), "label": "Exported Service (0%)"},
}

# Province-code aliases (defensive against upstream data quality issues)
_PROVINCE_ALIASES: Dict[str, str] = {
    "QUEBEC": "QC", "QUEBECOIS": "QC", "QC.": "QC",
    "ONTARIO": "ON", "ON.": "ON",
    "ALBERTA": "AB", "BRITISH COLUMBIA": "BC", "BC.": "BC",
    "SASKATCHEWAN": "SK", "MANITOBA": "MB",
    "NEW BRUNSWICK": "NB", "NOVA SCOTIA": "NS",
    "PRINCE EDWARD ISLAND": "PE",
    "NEWFOUNDLAND": "NL", "NEWFOUNDLAND AND LABRADOR": "NL",
    "YUKON": "YT", "NORTHWEST TERRITORIES": "NT", "NUNAVUT": "NU",
    # International synonyms → INTL
    "US": "INTL", "USA": "INTL", "UNITED STATES": "INTL",
    "INTERNATIONAL": "INTL", "EXPORT": "INTL", "OUTSIDE CANADA": "INTL",
}


# ─── In-memory cache (5-minute TTL) ────────────────────────────────────────
_CACHE: Dict[str, Dict[str, Decimal | str]] = {}
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL_SECONDS = 300  # 5 minutes


def normalize_province(prov: Optional[str]) -> str:
    """Coerce any province input to a canonical 2-letter code + INTL fallback.

    Accepts: 'QC', 'Quebec', 'Québec', 'ontario', 'US', 'international', ''.
    Never raises — unknown inputs default to 'INTL' (zero-rated) with a
    warning, so mis-typed provinces NEVER over-collect tax by defaulting
    to the highest rate.
    """
    if not prov:
        return "INTL"
    p = str(prov).strip().upper().replace("É", "E")
    if p in BOOTSTRAP_RATES:
        return p
    resolved = _PROVINCE_ALIASES.get(p)
    if resolved:
        return resolved
    logger.warning(f"[tax_rate_config] Unknown province '{prov}' — defaulting to INTL (0%)")
    return "INTL"


def get_tax_rate_sync(province: str) -> Dict[str, Decimal | str]:
    """Synchronous accessor — returns the currently cached rate row.

    Callers on the hot path (calculate_fee) use this. The cache is
    refreshed by `refresh_cache_from_db()` on boot + every 5 min. If the
    cache is empty (very first call before DB warm-up finishes), falls
    back to BOOTSTRAP_RATES.
    """
    code = normalize_province(province)
    row = _CACHE.get(code)
    if row:
        return row
    return dict(BOOTSTRAP_RATES.get(code, BOOTSTRAP_RATES["INTL"]))


async def get_tax_rate(province: str, db=None) -> Dict[str, Decimal | str]:
    """Async accessor — refreshes the cache if stale, then returns the row.

    Every call from `calculate_fee_async()` or route handlers should use
    this variant. Synchronous callers (unit tests, legacy paths) use
    `get_tax_rate_sync()`.
    """
    global _CACHE_TIMESTAMP
    if db is not None:
        now = asyncio.get_event_loop().time()
        if now - _CACHE_TIMESTAMP > _CACHE_TTL_SECONDS:
            await refresh_cache_from_db(db)
    return get_tax_rate_sync(province)


async def refresh_cache_from_db(db) -> None:
    """Reload the in-memory cache from db.tax_rate_config.

    Should be called on FastAPI startup + every 5 minutes via a scheduler
    heartbeat (already added in services/scheduler.py). If the collection
    is empty (fresh install), seeds with BOOTSTRAP_RATES first.
    """
    global _CACHE, _CACHE_TIMESTAMP
    try:
        docs = await db.tax_rate_config.find({}, {"_id": 0}).to_list(length=100)
        if not docs:
            await seed_bootstrap_rates(db)
            docs = await db.tax_rate_config.find({}, {"_id": 0}).to_list(length=100)

        new_cache: Dict[str, Dict[str, Decimal | str]] = {}
        for d in docs:
            prov = normalize_province(d.get("province"))
            new_cache[prov] = {
                "gst": Decimal(str(d.get("gst", "0"))),
                "qst": Decimal(str(d.get("qst", "0"))),
                "hst": Decimal(str(d.get("hst", "0"))),
                "combined": Decimal(str(d.get("combined", "0"))),
                "label": str(d.get("label", "")),
            }
        # Ensure every code we bootstrap is present in the cache
        for code, row in BOOTSTRAP_RATES.items():
            new_cache.setdefault(code, dict(row))
        _CACHE = new_cache
        _CACHE_TIMESTAMP = asyncio.get_event_loop().time()
        logger.info(f"[tax_rate_config] cache refreshed — {len(_CACHE)} provinces")
    except Exception as exc:
        logger.error(f"[tax_rate_config] refresh_cache failed: {exc} — using BOOTSTRAP")
        _CACHE = {k: dict(v) for k, v in BOOTSTRAP_RATES.items()}


async def seed_bootstrap_rates(db) -> None:
    """Idempotent — inserts BOOTSTRAP_RATES rows if missing. Called on startup."""
    now = datetime.now(timezone.utc).isoformat()
    for province, row in BOOTSTRAP_RATES.items():
        exists = await db.tax_rate_config.find_one({"province": province}, {"_id": 1})
        if exists:
            continue
        await db.tax_rate_config.insert_one({
            "province": province,
            "gst": str(row["gst"]),
            "qst": str(row["qst"]),
            "hst": str(row["hst"]),
            "combined": str(row["combined"]),
            "label": str(row["label"]),
            "effective_from": now,
            "source": "bootstrap_iter350",
        })
    logger.info("[tax_rate_config] bootstrap rates seeded (idempotent)")


async def update_tax_rate(
    db,
    province: str,
    *,
    gst: Optional[Decimal] = None,
    qst: Optional[Decimal] = None,
    hst: Optional[Decimal] = None,
    label: Optional[str] = None,
    updated_by_user_id: Optional[str] = None,
) -> Dict:
    """Admin-facing mutation. Snapshots the current row into
    db.tax_rate_config_history for audit trail before writing the update."""
    code = normalize_province(province)
    now = datetime.now(timezone.utc).isoformat()
    current = await db.tax_rate_config.find_one({"province": code}, {"_id": 0})
    if current:
        # Snapshot to history
        await db.tax_rate_config_history.insert_one({
            **{k: v for k, v in current.items() if k != "_id"},
            "effective_to": now,
            "superseded_by_user_id": updated_by_user_id,
        })
    new_gst = gst if gst is not None else Decimal(str(current.get("gst", "0"))) if current else Decimal("0")
    new_qst = qst if qst is not None else Decimal(str(current.get("qst", "0"))) if current else Decimal("0")
    new_hst = hst if hst is not None else Decimal(str(current.get("hst", "0"))) if current else Decimal("0")
    combined = new_gst + new_qst + new_hst
    payload = {
        "province": code,
        "gst": str(new_gst),
        "qst": str(new_qst),
        "hst": str(new_hst),
        "combined": str(combined),
        "label": label or (current.get("label") if current else ""),
        "effective_from": now,
        "updated_by_user_id": updated_by_user_id,
    }
    await db.tax_rate_config.update_one(
        {"province": code},
        {"$set": payload},
        upsert=True,
    )
    global _CACHE_TIMESTAMP
    _CACHE_TIMESTAMP = 0.0  # force refresh on next call
    return payload


# Warm the cache with bootstrap constants immediately at import time so
# synchronous callers before the first DB refresh still get correct answers.
_CACHE = {k: dict(v) for k, v in BOOTSTRAP_RATES.items()}
