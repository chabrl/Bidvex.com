"""
iter478 — Fee Schedule (Phase 1 infrastructure ONLY)
=====================================================

Versioned, auditable, DB-backed fee schedule.

⚠️  PHASE 1 CONTRACT ⚠️
This module MUST NOT be imported by any production calculation, settlement,
Stripe, escrow, receipt-generation, or PDF-generation path.

Its sole purposes in Phase 1 are:
  1. Provide a stable Python surface for the bootstrap script to WRITE the
     schedule row into ``db.fee_schedules``.
  2. Provide read-only helpers used ONLY by the Phase 1 verification tests
     and (later) by the admin UI + Phase 2 dual-read harness.

Existing calculation behaviour is preserved 100%: `services/fee_calculator.py`,
`services/vehicle_pricing.py`, `services/storage_pricing.py`,
`services/fee_calculation_engine.py`, and the PricingManager block continue
to hold their own rate constants and remain the authoritative source of
truth for settlement math until Phase 3 explicitly cuts over.

──────────────────────────────────────────────────────────────────────────
UNIT CONVENTION (financial safety)
──────────────────────────────────────────────────────────────────────────
* Every rate persisted in the schedule and every rate returned by the
  ``resolve_*`` helpers is a ``Decimal`` fraction.  5% is ``Decimal("0.05")``.
* Percent-style representations (``5.0``) are REJECTED by
  ``_validate_rate`` — the loader raises rather than silently coercing.
* Stripe fixed is stored as a Decimal dollar amount (``Decimal("0.30")``).

──────────────────────────────────────────────────────────────────────────
BUYER PREMIUM PRECEDENCE (iter478 Section 3)
──────────────────────────────────────────────────────────────────────────
When a new listing/settlement needs a buyer-premium rate, the resolver
checks in this order and returns the FIRST hit:

  1. Immutable settlement/listing snapshot   (caller passes ``snapshot_rate``)
  2. Listing-specific partner override        (caller passes ``listing_override``)
  3. User-specific override                   (caller passes ``custom_per_user``)
  4. Partner default from the active schedule (schedule.buyer_premium.partner.default)
  5. Tier rate from the active schedule       (schedule.buyer_premium[account_type][tier])

There is intentionally NO silent fallback to an unrelated tier — the
resolver raises ``FeeScheduleResolutionError`` if no rate can be resolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, Optional


# ═══════════════════════════════════════════════════════════════════════
#  Constants — never used for CALCULATION (that stays in fee_calculator);
#  used only by the bootstrap script + Phase 1 tests to describe the
#  expected shape and unit of the persisted schedule row.
# ═══════════════════════════════════════════════════════════════════════
COLLECTION_NAME = "fee_schedules"
CURRENT_SCHEDULA_ID = "fee_schedule_v1"    # single "active" row id
SUPPORTED_SELLER_ACCOUNT_TYPES = (
    "individual", "enterprise", "partner", "partner_pro",
    "vehicle_dealer", "storage_facility", "broker",
)
SUPPORTED_TIERS = ("standard", "premium", "vip_elite")

# Legal (per-schema) rate window — anything outside means the value is
# almost-certainly stored in the wrong unit and MUST be rejected.
MIN_RATE = Decimal("0")
MAX_RATE = Decimal("0.5")     # 50 % — no legitimate BidVex rate approaches this


# ═══════════════════════════════════════════════════════════════════════
#  Errors
# ═══════════════════════════════════════════════════════════════════════
class FeeScheduleError(Exception):
    """Base exception for schedule-related failures."""


class FeeScheduleValidationError(FeeScheduleError):
    """Raised when a rate is out of range or in the wrong unit."""


class FeeScheduleResolutionError(FeeScheduleError):
    """Raised when a rate lookup cannot be satisfied from the schedule."""


# ═══════════════════════════════════════════════════════════════════════
#  Type-level container for the deserialized schedule row
# ═══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class FeeSchedule:
    """In-memory, Decimal-clean view of one row in ``fee_schedules``.

    Only ever constructed by ``from_db`` or ``from_bootstrap_dict``.  The
    dataclass is *frozen* so a resolver can never mutate the schedule while
    computing a lookup.
    """
    id: str
    version: int
    effective_from: str
    is_active: bool
    buyer_premium: Mapping[str, Mapping[str, Any]]
    seller_commission: Mapping[str, Mapping[str, Any]]
    platform_fees: Mapping[str, Decimal]
    stripe: Mapping[str, Decimal]
    affiliate_commission_rate: Decimal
    category_overrides: Mapping[str, Mapping[str, Any]]
    tier_aliases: Mapping[str, str]
    updated_at: str
    updated_by: str
    notes: str = ""

    # ── convenience predicates ──────────────────────────────────────
    def alias(self, tier: Optional[str]) -> str:
        """Fold ``free/basic/starter/vip`` → the canonical tier key."""
        if not tier:
            return "standard"
        t = tier.strip().lower()
        return self.tier_aliases.get(t, t)


# ═══════════════════════════════════════════════════════════════════════
#  Rate validation
# ═══════════════════════════════════════════════════════════════════════
def _validate_rate(value: Any, *, field_name: str) -> Decimal:
    """Guarantee ``value`` is a Decimal fraction in ``[MIN_RATE, MAX_RATE]``.

    Rejects percent-style representations (anything > MAX_RATE) so a
    5.0-vs-0.05 mix-up cannot land silently.  ``bool`` is rejected too
    because ``isinstance(True, int)`` is True and we don't want a
    subscription flag masquerading as a rate.
    """
    if isinstance(value, bool):
        raise FeeScheduleValidationError(
            f"{field_name}: boolean is not a valid rate"
        )
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FeeScheduleValidationError(
            f"{field_name}: cannot coerce {value!r} to Decimal"
        ) from exc
    if not (MIN_RATE <= dec <= MAX_RATE):
        raise FeeScheduleValidationError(
            f"{field_name}: {dec} is outside [{MIN_RATE}, {MAX_RATE}] — "
            f"value must be a Decimal FRACTION (e.g. 0.05 for 5%)"
        )
    return dec


def _validate_fixed_amount(value: Any, *, field_name: str) -> Decimal:
    """Validate a fixed-dollar amount (Stripe $0.30 fixed)."""
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FeeScheduleValidationError(
            f"{field_name}: cannot coerce {value!r} to Decimal"
        ) from exc
    if not (Decimal("0") <= dec <= Decimal("10")):
        raise FeeScheduleValidationError(
            f"{field_name}: {dec} outside [0, 10] CAD — is it stored in cents "
            "by mistake?"
        )
    return dec


# ═══════════════════════════════════════════════════════════════════════
#  Deserialization
# ═══════════════════════════════════════════════════════════════════════
def _to_decimal_map(src: Mapping[str, Any], *, parent: str) -> Dict[str, Any]:
    """Walk the nested rate dict from Mongo and coerce every rate entry to
    Decimal.  Non-rate keys (booleans, strings, None, other maps) are
    preserved unchanged."""
    out: Dict[str, Any] = {}
    for key, value in src.items():
        path = f"{parent}.{key}"
        if isinstance(value, Mapping):
            out[key] = _to_decimal_map(value, parent=path)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            # Any numeric leaf goes through the fraction validator so an
            # accidental percent (e.g. 5.0) is loudly rejected.  A raw 0
            # (e.g. ``seller_pays: 0``) is permitted.
            out[key] = _validate_rate(value, field_name=path)
        elif isinstance(value, str):
            # Numeric strings ("0.05") are coerced; free-text keeps its type.
            try:
                out[key] = _validate_rate(value, field_name=path)
            except FeeScheduleValidationError:
                out[key] = value
        else:
            out[key] = value
    return out


def from_bootstrap_dict(raw: Dict[str, Any]) -> FeeSchedule:
    """Build an in-memory FeeSchedule from a bootstrap-shaped dict.  All
    numeric leaves are validated + coerced to Decimal in transit."""
    required = (
        "id", "version", "effective_from",
        "buyer_premium", "seller_commission", "platform_fees",
        "stripe", "affiliate_commission_rate",
        "category_overrides", "tier_aliases",
    )
    missing = [k for k in required if k not in raw]
    if missing:
        raise FeeScheduleValidationError(
            f"bootstrap dict missing required keys: {missing}"
        )

    buyer_prem  = _to_decimal_map(raw["buyer_premium"], parent="buyer_premium")
    seller_comm = _to_decimal_map(raw["seller_commission"], parent="seller_commission")
    platform    = {k: _validate_rate(v, field_name=f"platform_fees.{k}")
                   for k, v in raw["platform_fees"].items()}
    stripe      = {
        "percent":   _validate_rate(raw["stripe"]["percent"], field_name="stripe.percent"),
        "fixed_cad": _validate_fixed_amount(raw["stripe"]["fixed_cad"], field_name="stripe.fixed_cad"),
    }
    aff = _validate_rate(raw["affiliate_commission_rate"], field_name="affiliate_commission_rate")

    categories = _to_decimal_map(raw["category_overrides"], parent="category_overrides")

    return FeeSchedule(
        id=str(raw["id"]),
        version=int(raw["version"]),
        effective_from=str(raw["effective_from"]),
        is_active=bool(raw.get("is_active", True)),
        buyer_premium=buyer_prem,
        seller_commission=seller_comm,
        platform_fees=platform,
        stripe=stripe,
        affiliate_commission_rate=aff,
        category_overrides=categories,
        tier_aliases=dict(raw["tier_aliases"]),
        updated_at=str(raw.get("updated_at", raw["effective_from"])),
        updated_by=str(raw.get("updated_by", "")),
        notes=str(raw.get("notes", "")),
    )


def from_db(doc: Mapping[str, Any]) -> FeeSchedule:
    """Deserialize a Mongo document into a FeeSchedule.  Strips ``_id``."""
    clean = {k: v for k, v in doc.items() if k != "_id"}
    return from_bootstrap_dict(clean)


def to_mongo_dict(schedule: FeeSchedule) -> Dict[str, Any]:
    """Serialize back to a Mongo-writable dict.  Decimals are stored as
    strings so BSON round-trips are byte-exact (Mongo's Decimal128 is not
    installed in this project's Motor stack)."""
    def _walk(node: Any) -> Any:
        if isinstance(node, Decimal):
            return str(node)
        if isinstance(node, Mapping):
            return {k: _walk(v) for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            return [_walk(v) for v in node]
        return node
    return {
        "id":                        schedule.id,
        "version":                   schedule.version,
        "effective_from":            schedule.effective_from,
        "is_active":                 schedule.is_active,
        "buyer_premium":             _walk(schedule.buyer_premium),
        "seller_commission":         _walk(schedule.seller_commission),
        "platform_fees":             _walk(schedule.platform_fees),
        "stripe":                    _walk(schedule.stripe),
        "affiliate_commission_rate": _walk(schedule.affiliate_commission_rate),
        "category_overrides":        _walk(schedule.category_overrides),
        "tier_aliases":              dict(schedule.tier_aliases),
        "updated_at":                schedule.updated_at,
        "updated_by":                schedule.updated_by,
        "notes":                     schedule.notes,
    }


# ═══════════════════════════════════════════════════════════════════════
#  READ API (used by tests + future admin UI; NOT used by settlement)
# ═══════════════════════════════════════════════════════════════════════
async def get_active_schedule(db) -> FeeSchedule:
    """Return the currently-active schedule row.  Raises if none exists."""
    doc = await db[COLLECTION_NAME].find_one(
        {"is_active": True}, {"_id": 0}, sort=[("version", -1)],
    )
    if not doc:
        raise FeeScheduleResolutionError(
            "no active row in fee_schedules — run "
            "scripts/iter478_bootstrap_fee_schedule.py"
        )
    return from_db(doc)


# ═══════════════════════════════════════════════════════════════════════
#  RESOLVERS — Phase 1 exposes these but no production calc path uses them
# ═══════════════════════════════════════════════════════════════════════
def resolve_buyer_premium_rate(
    schedule: FeeSchedule,
    *,
    seller_account_type: str,
    buyer_tier: Optional[str] = None,
    snapshot_rate: Optional[Decimal] = None,
    listing_override: Optional[Decimal] = None,
    custom_per_user: Optional[Decimal] = None,
) -> Decimal:
    """Apply the Section-3 precedence chain.  Return the resolved Decimal
    fraction. Never silently falls back to an unrelated tier."""
    if snapshot_rate is not None:
        return _validate_rate(snapshot_rate, field_name="snapshot_rate")

    seller_account_type = (seller_account_type or "").strip().lower()
    if seller_account_type not in SUPPORTED_SELLER_ACCOUNT_TYPES:
        raise FeeScheduleResolutionError(
            f"unsupported seller_account_type: {seller_account_type!r}"
        )

    # Partner + partner_pro have explicit override mechanics
    if seller_account_type == "partner":
        if listing_override is not None:
            return _validate_rate(listing_override, field_name="listing_override")
        if custom_per_user is not None:
            return _validate_rate(custom_per_user, field_name="custom_per_user")
        default = schedule.buyer_premium.get("partner", {}).get("default")
        if default is None:
            raise FeeScheduleResolutionError(
                "partner buyer premium default missing from schedule"
            )
        return _validate_rate(default, field_name="schedule.buyer_premium.partner.default")

    if seller_account_type == "partner_pro":
        if listing_override is not None:
            return _validate_rate(listing_override, field_name="listing_override")
        default = schedule.buyer_premium.get("partner_pro", {}).get("default")
        if default is None:
            raise FeeScheduleResolutionError(
                "partner_pro buyer premium default missing from schedule"
            )
        return _validate_rate(default, field_name="schedule.buyer_premium.partner_pro.default")

    # Vehicle dealer / storage facility / broker — single default
    node = schedule.buyer_premium.get(seller_account_type)
    if node is None:
        raise FeeScheduleResolutionError(
            f"no buyer_premium node for {seller_account_type!r}"
        )
    if "default" in node:
        return _validate_rate(node["default"],
                              field_name=f"schedule.buyer_premium.{seller_account_type}.default")

    # Individual / enterprise — resolve by buyer tier
    tier = schedule.alias(buyer_tier)
    if tier not in node:
        raise FeeScheduleResolutionError(
            f"buyer_premium.{seller_account_type}.{tier} not defined "
            f"(buyer_tier={buyer_tier!r})"
        )
    return _validate_rate(node[tier],
                          field_name=f"schedule.buyer_premium.{seller_account_type}.{tier}")


def resolve_seller_commission_rate(
    schedule: FeeSchedule,
    *,
    seller_account_type: str,
    seller_tier: Optional[str] = None,
    category: Optional[str] = None,  # accepted for future compat — NOT applied in Phase 1
    snapshot_rate: Optional[Decimal] = None,
) -> Decimal:
    """Resolve the seller-commission rate.

    Category-specific overrides in ``schedule.category_overrides`` are
    INACTIVE for Phase 1 (they are stored but not consulted).  The
    ``category`` parameter is accepted so future callers do not need a
    signature change.
    """
    if snapshot_rate is not None:
        return _validate_rate(snapshot_rate, field_name="snapshot_rate")

    seller_account_type = (seller_account_type or "").strip().lower()
    if seller_account_type not in SUPPORTED_SELLER_ACCOUNT_TYPES:
        raise FeeScheduleResolutionError(
            f"unsupported seller_account_type: {seller_account_type!r}"
        )

    node = schedule.seller_commission.get(seller_account_type)
    if node is None:
        raise FeeScheduleResolutionError(
            f"no seller_commission node for {seller_account_type!r}"
        )

    # Partner sellers pay a platform_fee_rate (not a commission on hammer)
    if "platform_fee_rate" in node:
        return _validate_rate(node["platform_fee_rate"],
                              field_name=f"schedule.seller_commission.{seller_account_type}.platform_fee_rate")

    # Partner Pro / stand-alone dedicated commission field
    if "seller_commission_rate" in node:
        return _validate_rate(node["seller_commission_rate"],
                              field_name=f"schedule.seller_commission.{seller_account_type}.seller_commission_rate")

    # Storage facility / vehicle dealer — seller pays 0
    if "seller_pays" in node:
        return _validate_rate(node["seller_pays"],
                              field_name=f"schedule.seller_commission.{seller_account_type}.seller_pays")

    # Individual / enterprise — resolve by seller tier
    tier = schedule.alias(seller_tier)
    if tier not in node:
        raise FeeScheduleResolutionError(
            f"seller_commission.{seller_account_type}.{tier} not defined "
            f"(seller_tier={seller_tier!r})"
        )
    return _validate_rate(node[tier],
                          field_name=f"schedule.seller_commission.{seller_account_type}.{tier}")


def resolve_platform_fee_rate(schedule: FeeSchedule, *, kind: str) -> Decimal:
    kind = (kind or "").strip().lower()
    if kind not in schedule.platform_fees:
        raise FeeScheduleResolutionError(
            f"platform_fees.{kind} not defined"
        )
    return _validate_rate(schedule.platform_fees[kind],
                          field_name=f"schedule.platform_fees.{kind}")


def resolve_stripe(schedule: FeeSchedule) -> Dict[str, Decimal]:
    return {
        "percent":   _validate_rate(schedule.stripe["percent"], field_name="schedule.stripe.percent"),
        "fixed_cad": _validate_fixed_amount(schedule.stripe["fixed_cad"], field_name="schedule.stripe.fixed_cad"),
    }


def category_override(schedule: FeeSchedule, *, category: str) -> Optional[Mapping[str, Any]]:
    """Return the category-override node if present + active.

    Phase 1: ``active=False`` for every category so this ALWAYS returns
    ``None``.  Kept as a public helper so the Phase 2 dual-read harness
    can consult it without a signature change.
    """
    node = schedule.category_overrides.get((category or "").strip().lower())
    if not node:
        return None
    if not node.get("active"):
        return None
    return node


__all__ = [
    "COLLECTION_NAME",
    "CURRENT_SCHEDULA_ID",
    "SUPPORTED_SELLER_ACCOUNT_TYPES",
    "SUPPORTED_TIERS",
    "FeeSchedule",
    "FeeScheduleError",
    "FeeScheduleValidationError",
    "FeeScheduleResolutionError",
    "from_bootstrap_dict",
    "from_db",
    "to_mongo_dict",
    "get_active_schedule",
    "resolve_buyer_premium_rate",
    "resolve_seller_commission_rate",
    "resolve_platform_fee_rate",
    "resolve_stripe",
    "category_override",
]
