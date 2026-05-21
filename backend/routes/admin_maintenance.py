"""
BidVex — Admin maintenance endpoints.
Phase 6.0 hotfix — Task 2 (TEST_V9 purge).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

admin_maintenance_router = APIRouter(tags=["Admin Maintenance"])


class PurgeRequest(BaseModel):
    dry_run: bool = True


@admin_maintenance_router.post("/admin/maintenance/purge-test-data")
async def admin_purge_test_data(
    payload: PurgeRequest,
    current_user: User = Depends(require_admin),
):
    """Purge agent/test-seeded rows (anything containing TEST_V9, synthetic
    vehicle-block::* listing ids, etc.) across:
      - listings
      - multi_item_listings
      - manual_review_requests
      - listing_reviews
      - broker_invoices
      - bids (only seller_id matching ^test-)
      - email_outbox

    Body:  {"dry_run": true|false}
    Default is dry_run=true so admins can preview the impact before applying.
    """
    db = get_db()
    from scripts.purge_test_v9 import purge_test_data
    report = await purge_test_data(db, dry_run=payload.dry_run)
    logger.info(f"[admin_maintenance] {current_user.email} purge_test_data dry_run={payload.dry_run} → {report}")
    return {
        "success":   True,
        "dry_run":   payload.dry_run,
        "report":    report,
        "executed_by": current_user.email,
    }
