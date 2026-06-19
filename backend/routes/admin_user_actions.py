"""
iter310 — Compat shim
=====================
This file used to host ALL admin → user-tab endpoints (~750 lines). In
iter310 it was split into:

  • `admin_user_management.py` — user/business account CRUD (notify,
    request-docs, edit-profile, reset-password, demo-toggle, email
    journey, bidding-suspension).
  • `admin_user_billing.py`    — tier overrides, transactions,
    subscription-status snapshot.

This module now just re-exports a combined `router` so the existing
`from routes.admin_user_actions import router` in `server.py` keeps
working with zero edits. Any new admin → users endpoint should be added
to the appropriate split module above, NOT this shim.
"""
from __future__ import annotations

from fastapi import APIRouter

from routes.admin_user_management import router as _management_router
from routes.admin_user_billing import router as _billing_router


router = APIRouter()
router.include_router(_management_router)
router.include_router(_billing_router)
