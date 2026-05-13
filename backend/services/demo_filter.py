"""
iter211 P4 — Demo Account Isolation Helpers

Two cross-cutting helpers used across every listing-creation and public-list
endpoint to enforce the demo-mode contract:

  ▸ `tag_listing_if_demo(db, user_id, doc)` — mutates the listing dict in
    place, setting `is_demo=True` when the creator is a demo account.

  ▸ `public_listing_filter(extra=None)` — returns a Mongo query fragment
    that excludes `is_demo=True` rows, designed to be merged with the
    endpoint's own filters.

Why centralise: prevents 12 different list endpoints from drifting on their
own filter logic, and keeps the demo-tag write path consistent. Reviewers
just need to grep for these two function names to audit the surface.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


async def tag_listing_if_demo(db, user_id: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    """Set `doc['is_demo'] = True` if the creating user is a demo account.

    Idempotent: if the doc is already tagged or the user is not a demo
    account, the doc is returned untouched. Always returns the same dict
    instance for fluent chaining.
    """
    if not user_id or doc is None:
        return doc
    user_row = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "is_demo_account": 1},
    )
    if user_row and user_row.get("is_demo_account") is True:
        doc["is_demo"] = True
    return doc


def public_listing_filter(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a Mongo filter that EXCLUDES demo listings.

    Usage:
      cursor = db.listings.find(public_listing_filter({"status": "active"}))
    """
    base = {"is_demo": {"$ne": True}}
    if extra:
        merged = dict(extra)
        # If caller already specified an is_demo clause, respect it; otherwise inject.
        if "is_demo" not in merged:
            merged["is_demo"] = base["is_demo"]
        return merged
    return base


async def is_demo_user(db, user_id: str) -> bool:
    """Tiny helper for code paths that need a boolean instead of mutating a doc."""
    if not user_id:
        return False
    row = await db.users.find_one({"id": user_id}, {"_id": 0, "is_demo_account": 1})
    return bool(row and row.get("is_demo_account"))
