"""
BidVex — Admin bulk operations on marketplace listings.

POST /api/admin/listings/bulk-action
  body: { action: "delete" | "pause" | "resume" | "archive" | "feature" |
          "unfeature" | "cancel",
          listing_ids: ["id1","id2",...] }

iter310 — CROSS-COLLECTION CASCADE
==================================
The single Admin "Manage All Auctions" view aggregates listings from four
top-level collections (marketplace, vehicles, vehicle multi-lot events,
multi-item parents). The previous implementation only touched
`db.listings`, which is why deleting 92 vehicle multi-lot listings
returned "0 succeeded, 92 failed" — every id was a vehicle_multi_lot_auctions
doc, none lived in `db.listings`.

This rewrite:
  • Probes all four collections per id (first hit wins).
  • For DELETE on a multi-lot parent, atomically removes the parent
    (the lots[] and bids[] arrays are embedded — single delete
    takes them with it) AND scrubs any rows in the
    `lot_bids` collection that reference any of the child lot ids.
  • For DELETE on a regular listing, atomically deletes the parent
    AND its rows in the `bids` collection.
  • Wraps each id's multi-document work in a MongoDB transaction
    (replica-set sessions). When sessions aren't available we fall
    back to best-effort sequential deletes with a per-doc error
    capture, so the endpoint still returns a clean per-id report.
  • Writes a single batched audit row to `admin_action_logs` (the
    canonical audit collection per iter154; we also write to the
    legacy `admin_logs` for backwards compat).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Literal, Tuple, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)
admin_bulk_router = APIRouter(tags=["Admin Bulk"])


# ─── Collection registry ──────────────────────────────────────────────
# (collection_name, default_status_field, child-cascade map for DELETE)
#
# child cascade is a list of (collection, foreign_key_on_child, the
# attribute on the parent that produces the matching value).
# Use None for `parent_attr` to match the parent id itself.
_LISTING_COLLECTIONS: Tuple[Tuple[str, Optional[List[Tuple[str, str, Optional[str]]]]], ...] = (
    # Standard marketplace listings — bid rows reference listing_id
    ("listings", [("bids", "listing_id", None)]),
    # Single-vehicle listings (dealers) — vehicle_bids → vehicle_id
    ("vehicle_listings", [
        ("bids", "listing_id", None),
        ("vehicle_bids", "vehicle_id", None),
    ]),
    # Vehicle multi-lot auction events — embedded lots[], embedded bids[]
    # + optional standalone lot_bids rows referencing per-lot ids.
    # Special-cased below because the cascade key is per-lot, not parent.
    ("vehicle_multi_lot_auctions", "MULTI_LOT_SPECIAL"),
    # Multi-item listings (older non-vehicle multi-lot)
    ("multi_item_listings", [("lot_bids", "parent_listing_id", None)]),
)


# ─── Payload ──────────────────────────────────────────────────────────


class BulkListingAction(BaseModel):
    action: Literal[
        "delete", "pause", "resume", "archive", "feature", "unfeature", "cancel"
    ]
    listing_ids: List[str] = Field(..., min_length=1, max_length=500)


# ─── Helpers ──────────────────────────────────────────────────────────


async def _locate(db, listing_id: str) -> Optional[Tuple[str, dict]]:
    """Return (collection_name, doc) for the first collection that has
    a document with id=listing_id. None if no collection claims it."""
    for coll_name, _ in _LISTING_COLLECTIONS:
        doc = await db[coll_name].find_one({"id": listing_id})
        if doc:
            return (coll_name, doc)
    return None


async def _cascade_delete(db, coll_name: str, doc: dict, session=None) -> dict:
    """Hard-delete `doc` from `coll_name` and clean up its child rows.
    Returns a dict with per-collection deleted_count for the audit row.
    Caller is responsible for the transaction session boundary."""
    listing_id = doc["id"]
    deleted = {coll_name: 0}

    # Multi-lot parents — also clean up any standalone lot_bids rows
    # whose lot_id matches one of the embedded lot ids
    if coll_name == "vehicle_multi_lot_auctions":
        lot_ids = [lot.get("id") for lot in (doc.get("lots") or []) if lot.get("id")]
        if lot_ids:
            res = await db.lot_bids.delete_many(
                {"lot_id": {"$in": lot_ids}}, session=session
            )
            deleted["lot_bids"] = res.deleted_count
    else:
        # Other collections — use the static cascade map
        for entry in _LISTING_COLLECTIONS:
            if entry[0] != coll_name:
                continue
            children = entry[1]
            if children == "MULTI_LOT_SPECIAL":
                break
            for child_coll, fk, parent_attr in children:
                value = listing_id if parent_attr is None else doc.get(parent_attr)
                if value is None:
                    continue
                res = await db[child_coll].delete_many(
                    {fk: value}, session=session
                )
                deleted[child_coll] = res.deleted_count
            break

    # Finally the parent
    res = await db[coll_name].delete_one({"id": listing_id}, session=session)
    deleted[coll_name] = res.deleted_count
    return deleted


async def _apply_status(db, coll_name: str, listing_id: str, status: str, now: datetime, session=None):
    return await db[coll_name].update_one(
        {"id": listing_id},
        {"$set": {"status": status, "updated_at": now}},
        session=session,
    )


async def _apply_feature(db, coll_name: str, listing_id: str, is_featured: bool, now: datetime, session=None):
    return await db[coll_name].update_one(
        {"id": listing_id},
        {"$set": {"is_featured": is_featured, "updated_at": now}},
        session=session,
    )


# ─── Endpoint ─────────────────────────────────────────────────────────


@admin_bulk_router.post("/admin/listings/bulk-action")
async def bulk_listing_action(
    data: BulkListingAction,
    current_user: User = Depends(require_admin),
):
    """Apply `data.action` to many listings across all four listing
    collections. Returns a per-id success/failure report."""
    db = get_db()
    now = datetime.now(timezone.utc)

    status_map = {
        "pause": "paused",
        "resume": "active",
        "archive": "archived",
        "cancel": "cancelled",
    }

    succeeded: list = []
    failed: list = []
    cascade_totals: dict = {}

    # Use a session for ACID multi-doc work. Transactions only work
    # against a replica set; we fall back gracefully if unavailable.
    client = db.client
    try:
        session_cm = await client.start_session()
        supports_txn = True
    except Exception:  # pragma: no cover — single-node test envs
        session_cm = None
        supports_txn = False

    try:
        for lid in data.listing_ids:
            try:
                located = await _locate(db, lid)
                if not located:
                    failed.append({"id": lid, "reason": "not found in any listing collection"})
                    continue
                coll_name, doc = located

                async def _do_work(session):
                    if data.action == "delete":
                        d = await _cascade_delete(db, coll_name, doc, session=session)
                        for k, v in d.items():
                            cascade_totals[k] = cascade_totals.get(k, 0) + v
                        return d[coll_name] > 0
                    if data.action in ("feature", "unfeature"):
                        res = await _apply_feature(
                            db, coll_name, lid, data.action == "feature", now, session=session
                        )
                        return res.matched_count > 0
                    new_status = status_map[data.action]
                    res = await _apply_status(db, coll_name, lid, new_status, now, session=session)
                    return res.matched_count > 0

                ok = False
                if supports_txn:
                    try:
                        async with session_cm.start_transaction():
                            ok = await _do_work(session_cm)
                    except Exception as txn_exc:
                        # Fall back to non-transactional path so a single
                        # id failure doesn't poison the whole batch.
                        logger.warning(
                            "transaction failed for %s, falling back: %s", lid, txn_exc
                        )
                        ok = await _do_work(None)
                else:
                    ok = await _do_work(None)

                if ok:
                    succeeded.append({"id": lid, "collection": coll_name})
                else:
                    failed.append({"id": lid, "reason": "no document matched"})
            except Exception as e:
                logger.exception("bulk %s failed for %s", data.action, lid)
                failed.append({"id": lid, "reason": str(e)[:240]})
    finally:
        if session_cm is not None:
            try:
                await session_cm.end_session()
            except Exception:  # pragma: no cover
                pass

    # Batched audit — write to BOTH the canonical iter154 audit and the
    # legacy log so dashboards on either side keep working.
    audit_doc = {
        "id": f"bulk-{now.strftime('%Y%m%dT%H%M%SZ')}-{data.action}",
        "action": f"bulk_listing_{data.action}",
        "admin_email": getattr(current_user, "email", None),
        "admin_id": getattr(current_user, "id", None),
        "target_listing_ids": [s["id"] if isinstance(s, dict) else s for s in succeeded],
        "details": {
            "action": data.action,
            "attempted": len(data.listing_ids),
            "succeeded": len(succeeded),
            "failed": len(failed),
            "cascade_totals": cascade_totals,
        },
        "timestamp": now,
    }
    try:
        await db.admin_action_logs.insert_one(dict(audit_doc))
    except Exception:
        logger.exception("admin_action_logs insert failed")
    try:
        legacy = dict(audit_doc)
        legacy["timestamp"] = now.isoformat()
        legacy["id"] = audit_doc["id"] + "-legacy"
        await db.admin_logs.insert_one(legacy)
    except Exception:
        logger.exception("admin_logs insert failed")

    return {
        "action": data.action,
        "total": len(data.listing_ids),
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "succeeded": succeeded,
        "failed": failed,
        "cascade_totals": cascade_totals,
    }
