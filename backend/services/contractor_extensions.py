"""
iter323 — Contractor extension number assignment + IVR routing helpers.

Each `dialer_contractor` user is assigned a unique, immutable 4-digit
extension starting at 1220 and incrementing forever (never reused).
Inbound clients dial +1 450 634 3099 → enter extension → Twilio bridges
to the contractor's `personal_phone_number`.

Why never-reuse?
  If contractor A (ext 1220) is deactivated and contractor B is later
  assigned 1220, any old business card or email signature still floating
  around would route the wrong client to the wrong contractor. The cost
  of "wasted" extension numbers in a 10000-slot 4-digit space is trivial
  compared to the trust+privacy risk of accidental cross-routing.

Sequence storage:
  We use a dedicated counter collection `system_counters` keyed by
  `"contractor_extension"`. `findAndModify`-style atomic increment so two
  parallel `assign_extension()` calls cannot race and produce duplicates.
  A unique index on `users.extension_number` is also enforced as a
  belt-and-suspenders backstop.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# First extension assigned — every subsequent contractor gets ext +1.
EXTENSION_START = 1220


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def ensure_extension_index(db) -> None:
    """Idempotent. Creates the unique sparse index on users.extension_number
    so duplicate assignment is impossible even under a race. `sparse=True`
    means users without the field (the entire pre-iter323 historical base)
    don't conflict with each other."""
    try:
        await db.users.create_index(
            "extension_number",
            unique=True,
            sparse=True,
            name="users_extension_number_uniq",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[contractor-extensions] index ensure failed: {e}")


async def assign_extension(db, contractor_id: str) -> int:
    """Assigns the next available extension number to `contractor_id`.
    Idempotent — if the contractor already has one, return it unchanged.

    Returns the assigned extension (int).

    Raises ValueError if `contractor_id` does not point to a user.
    """
    await ensure_extension_index(db)

    existing = await db.users.find_one(
        {"id": contractor_id}, {"_id": 0, "id": 1, "extension_number": 1},
    )
    if existing is None:
        raise ValueError(f"unknown contractor_id: {contractor_id}")
    if existing.get("extension_number"):
        return int(existing["extension_number"])

    # Atomic counter bump: find_one_and_update with upsert returns the
    # NEW document (or the pre-update doc; we use returnDocument=AFTER).
    # The first time this runs in a fresh DB, `seed_value` initialises
    # the counter to EXTENSION_START - 1 so the first increment lands
    # exactly on EXTENSION_START.
    from pymongo import ReturnDocument

    counter = await db.system_counters.find_one_and_update(
        {"_id": "contractor_extension"},
        {
            "$inc":         {"value": 1},
            "$setOnInsert": {"created_at": _now_iso()},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    next_ext = int(counter.get("value") or 0)
    # If the counter was just created, mongo will have set value=1 because
    # $setOnInsert can't combine with $inc on the same field. Bring it up
    # to EXTENSION_START on the first assignment.
    if next_ext < EXTENSION_START:
        next_ext = EXTENSION_START
        await db.system_counters.update_one(
            {"_id": "contractor_extension"},
            {"$set": {"value": next_ext}},
        )

    # Defensive collision check (the unique index should catch this; the
    # loop here is for graceful recovery if a legacy row happened to be
    # backfilled to the same number).
    for _ in range(20):
        clash = await db.users.find_one(
            {"extension_number": next_ext}, {"_id": 0, "id": 1},
        )
        if not clash:
            break
        next_ext += 1
        await db.system_counters.update_one(
            {"_id": "contractor_extension"},
            {"$set": {"value": next_ext}},
        )
    else:
        raise RuntimeError(
            "[contractor-extensions] could not find a free extension after 20 tries"
        )

    await db.users.update_one(
        {"id": contractor_id, "extension_number": {"$exists": False}},
        {"$set": {
            "extension_number":         next_ext,
            "extension_assigned_at":    _now_iso(),
        }},
    )

    # Re-read in case another writer beat us to it (still rare; the
    # unique index would have raised above, but we double-check).
    refreshed = await db.users.find_one(
        {"id": contractor_id}, {"_id": 0, "extension_number": 1},
    )
    return int(refreshed.get("extension_number") or next_ext)


async def get_extension_for_contractor(db, contractor_id: str) -> Optional[int]:
    """Returns the contractor's assigned extension, or None if unassigned."""
    doc = await db.users.find_one(
        {"id": contractor_id}, {"_id": 0, "extension_number": 1},
    )
    if not doc:
        return None
    val = doc.get("extension_number")
    return int(val) if val else None


async def lookup_contractor_by_extension(db, extension: int) -> Optional[dict]:
    """Inbound IVR uses this to map a digit-string entered by a caller
    back to the owning contractor. Returns the user document (sans _id +
    password) or None if not found."""
    if not extension or not isinstance(extension, int):
        return None
    return await db.users.find_one(
        {"extension_number": int(extension), "role": "dialer_contractor"},
        {"_id": 0, "password": 0, "password_hash": 0},
    )


async def backfill_extensions(db) -> int:
    """One-off helper to assign extensions to every existing contractor
    who doesn't have one yet. Returns the number of contractors backfilled.

    Safe to call repeatedly — only touches contractors missing an extension.
    """
    cursor = db.users.find(
        {"role": "dialer_contractor", "extension_number": {"$exists": False}},
        {"_id": 0, "id": 1, "created_at": 1},
    ).sort("created_at", 1)
    count = 0
    async for u in cursor:
        try:
            await assign_extension(db, u["id"])
            count += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[contractor-extensions] backfill failed for {u.get('id')}: {e}")
    return count


__all__ = [
    "EXTENSION_START",
    "ensure_extension_index",
    "assign_extension",
    "get_extension_for_contractor",
    "lookup_contractor_by_extension",
    "backfill_extensions",
]
