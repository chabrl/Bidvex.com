"""
services/bid_guard.py — iter300 P1

Bidding-privilege gate. Buyers whose payment went unrecovered after 3
auto-capture attempts (services/overdue_autocapture.py) get
`bidding_suspended=True` on their user document and every bid endpoint
must return 403. Admin can lift the suspension from User Management.
"""
from __future__ import annotations

from fastapi import HTTPException


async def ensure_bidding_allowed(db, user_id: str) -> None:
    """Raise 403 when the user's bidding privileges are suspended."""
    row = await db.users.find_one(
        {"id": user_id}, {"_id": 0, "bidding_suspended": 1})
    if row and row.get("bidding_suspended"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "bidding_suspended",
                "message_en": ("Your bidding privileges are suspended due to an unresolved "
                               "overdue payment. Please contact service@bidvex.com."),
                "message_fr": ("Vos privilèges d'enchères sont suspendus en raison d'un paiement "
                               "en retard non résolu. Veuillez contacter service@bidvex.com."),
            },
        )
