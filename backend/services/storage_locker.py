"""
BidVex — Phase 6.0 / Task 3
Storage Locker / Abandoned Unit listing helpers.

Centralises the validation + normalisation of `storage_metadata` and the
"single absolute lot block" quantity policy. Importable from both the
listings route (creation flow) and the broker_fee_engine / checkout flow.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

LISTING_TYPE_STORAGE_LOCKER = "storage_locker"

# Allowed cleanout deadline (hours) presets surfaced in the UI.
ALLOWED_CLEANOUT_HOURS = {24, 48, 72, 168}   # 168 = 1 week

# Allowed security-deposit preset amounts surfaced in the UI. Buyer can also
# provide a custom value; we clamp it to [50, 5000].
ALLOWED_DEPOSIT_PRESETS = (100.00, 250.00, 500.00, 1000.00)
DEPOSIT_MIN = 50.00
DEPOSIT_MAX = 5000.00


def is_storage_locker(listing: Dict[str, Any] | object) -> bool:
    """True when this listing carries the storage-locker listing_type."""
    if isinstance(listing, dict):
        return (listing.get("listing_type") or "").lower() == LISTING_TYPE_STORAGE_LOCKER
    return (getattr(listing, "listing_type", "") or "").lower() == LISTING_TYPE_STORAGE_LOCKER


def normalize_storage_metadata(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Coerce the user-submitted storage_metadata into a clean dict with
    defaults applied. Required field `facility_name` is enforced — missing
    or empty triggers a ValueError.

    Schema produced:
        facility_name              : str   (required)
        facility_address           : str   (optional)
        locker_size                : str   (e.g. "10x10")
        locker_number              : str
        cleanout_deadline_hours    : int   (default 72; clamped to ALLOWED_CLEANOUT_HOURS)
        security_deposit_amount    : float (default 100.00, clamped to [DEPOSIT_MIN, DEPOSIT_MAX])
        lien_compliance_verified   : bool  (default False)
        facility_manager_email     : str   (optional)
        facility_manager_phone     : str   (optional)
        notes                      : str   (optional)
    """
    raw = raw or {}

    facility_name = str(raw.get("facility_name") or "").strip()
    if not facility_name:
        raise ValueError("storage_metadata.facility_name is required for storage_locker listings.")

    try:
        cleanout_hours = int(raw.get("cleanout_deadline_hours") or 72)
    except Exception:
        cleanout_hours = 72
    if cleanout_hours not in ALLOWED_CLEANOUT_HOURS:
        # Snap to the nearest allowed value to avoid sneaky 1h/0h deadlines.
        cleanout_hours = min(ALLOWED_CLEANOUT_HOURS, key=lambda h: abs(h - cleanout_hours))

    try:
        deposit_amount = float(raw.get("security_deposit_amount") or 100.00)
    except Exception:
        deposit_amount = 100.00
    deposit_amount = max(DEPOSIT_MIN, min(DEPOSIT_MAX, deposit_amount))
    deposit_amount = round(deposit_amount, 2)

    return {
        "facility_name":             facility_name[:200],
        "facility_address":          str(raw.get("facility_address") or "").strip()[:300],
        "locker_size":               str(raw.get("locker_size") or "").strip()[:30],
        "locker_number":             str(raw.get("locker_number") or "").strip()[:30],
        "cleanout_deadline_hours":   cleanout_hours,
        "security_deposit_amount":   deposit_amount,
        "lien_compliance_verified":  bool(raw.get("lien_compliance_verified", False)),
        "facility_manager_email":    str(raw.get("facility_manager_email") or "").strip()[:200],
        "facility_manager_phone":    str(raw.get("facility_manager_phone") or "").strip()[:30],
        "notes":                     str(raw.get("notes") or "").strip()[:1000],
    }


def storage_quantity_policy(quantity: Optional[int]) -> tuple[int, bool]:
    """Storage lockers are sold as ONE absolute lot block — the entire
    contents of the unit. We force quantity=1 and multiply_hammer=False
    regardless of what the seller posted.

    Returns (quantity, multiply_hammer_by_quantity).
    """
    return 1, False


def storage_deposit_amount_for_listing(listing: Dict[str, Any] | object) -> float:
    """Pull the cleanout security deposit amount (CAD) from the listing's
    storage_metadata. Defaults to 100.00 when missing."""
    if isinstance(listing, dict):
        meta = listing.get("storage_metadata") or {}
    else:
        meta = getattr(listing, "storage_metadata", None) or {}
    try:
        return float(meta.get("security_deposit_amount") or 100.00)
    except Exception:
        return 100.00
