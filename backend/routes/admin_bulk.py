"""
BidVex — Admin bulk operations on marketplace listings.

POST /api/admin/listings/bulk-action
  body: { action: "delete" | "pause" | "resume" | "archive" | "feature" | "unfeature",
          listing_ids: ["id1","id2",...] }

Returns a per-id success/failure report.
"""
from typing import List, Literal
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import logging

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)
admin_bulk_router = APIRouter(tags=["Admin Bulk"])


class BulkListingAction(BaseModel):
    action: Literal["delete", "pause", "resume", "archive", "feature", "unfeature", "cancel"]
    listing_ids: List[str] = Field(..., min_length=1, max_length=500)


@admin_bulk_router.post("/admin/listings/bulk-action")
async def bulk_listing_action(
    data: BulkListingAction,
    current_user: User = Depends(require_admin),
):
    """
    Apply a single action to many listings in one call. Returns a report
    including successes, failures, and the total count.

    - delete → hard delete from `listings`
    - pause/resume/archive/cancel → update status
    - feature/unfeature → flip is_featured flag
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    status_map = {
        "pause": "paused",
        "resume": "active",
        "archive": "archived",
        "cancel": "cancelled",
    }

    succeeded, failed = [], []
    for lid in data.listing_ids:
        try:
            if data.action == "delete":
                res = await db.listings.delete_one({"id": lid})
                if res.deleted_count:
                    succeeded.append(lid)
                else:
                    failed.append({"id": lid, "reason": "not found"})
            elif data.action in ("feature", "unfeature"):
                res = await db.listings.update_one(
                    {"id": lid},
                    {"$set": {"is_featured": data.action == "feature", "updated_at": now}},
                )
                (succeeded if res.matched_count else failed).append(
                    lid if res.matched_count else {"id": lid, "reason": "not found"}
                )
            else:
                new_status = status_map[data.action]
                res = await db.listings.update_one(
                    {"id": lid},
                    {"$set": {"status": new_status, "updated_at": now}},
                )
                (succeeded if res.matched_count else failed).append(
                    lid if res.matched_count else {"id": lid, "reason": "not found"}
                )
        except Exception as e:
            logger.exception(f"bulk {data.action} failed for {lid}")
            failed.append({"id": lid, "reason": str(e)[:120]})

    # Audit once for the whole batch
    await db.admin_logs.insert_one({
        "id": f"bulk-{lid}-{int(now.timestamp())}",
        "action": f"bulk_listing_{data.action}",
        "admin_email": getattr(current_user, "email", None),
        "admin_id": getattr(current_user, "id", None),
        "details": {
            "action": data.action,
            "attempted": len(data.listing_ids),
            "succeeded": len(succeeded),
            "failed": len(failed),
        },
        "timestamp": now.isoformat(),
    })

    return {
        "action": data.action,
        "total": len(data.listing_ids),
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "succeeded": succeeded,
        "failed": failed,
    }
