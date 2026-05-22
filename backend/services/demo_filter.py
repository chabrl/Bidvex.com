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
    """Set `doc['is_demo'] = True` AND `doc['is_demo_sandbox'] = True` if the
    creating user is a demo account.

    iter223 — `is_demo_sandbox` is the iter223 sandbox-only flag used by
    the owner-self-include query (so the demo creator can still see their
    own listings inside the real product surfaces). `is_demo` is kept for
    legacy public-feed exclusion paths that haven't migrated yet.

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
        doc["is_demo_sandbox"] = True
    return doc


def public_listing_filter(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a Mongo filter that EXCLUDES demo listings (no user context).

    Usage:
      cursor = db.listings.find(public_listing_filter({"status": "active"}))
    """
    base = {"is_demo": {"$ne": True}, "is_demo_sandbox": {"$ne": True}}
    if extra:
        merged = dict(extra)
        if "is_demo" not in merged:
            merged["is_demo"] = base["is_demo"]
        if "is_demo_sandbox" not in merged:
            merged["is_demo_sandbox"] = base["is_demo_sandbox"]
        return merged
    return base


def sandbox_aware_filter(
    *,
    user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    seller_field: str = "seller_id",
) -> Dict[str, Any]:
    """iter223 — Listing-feed filter that hides public sandbox listings BUT
    shows the demo user their own creations inside the real product frame.

    - Anonymous / non-demo authenticated users → pure public filter.
    - Demo user with a valid `user_id` → `$or` clause: either the listing is
      not a sandbox listing, OR it belongs to this user.

    `seller_field` lets the caller adapt the field name for collections that
    use a different identifier (e.g., `owner_user_id` for multi-item).
    """
    base = dict(extra or {})
    if user_id:
        # Anyone authenticated gets the self-include $or so their own demo
        # creations surface. Non-demo users have no sandbox listings, so
        # this is effectively a no-op for them.
        base["$or"] = [
            {"is_demo_sandbox": {"$ne": True}, "is_demo": {"$ne": True}},
            {seller_field: user_id},
        ]
    else:
        base["is_demo_sandbox"] = {"$ne": True}
        base["is_demo"] = {"$ne": True}
    return base


async def is_demo_user(db, user_id: str) -> bool:
    """Tiny helper for code paths that need a boolean instead of mutating a doc."""
    if not user_id:
        return False
    row = await db.users.find_one({"id": user_id}, {"_id": 0, "is_demo_account": 1})
    return bool(row and row.get("is_demo_account"))
