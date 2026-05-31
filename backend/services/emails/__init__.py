"""
iter241 Mission 2 — Modular email package.

Per-type submodules that re-export the canonical helpers from the legacy
`services.email_notifications` module. This gives callers a clean import
path (`from services.emails.bidding import send_bid_placed_email`) without
forcing a risky 3000-line mechanical refactor in a single sprint.

Migration tracking
==================
- `send_unified_email()` is now the canonical entry-point for ALL new
  transactional emails — see services/email_notifications.py.
- Legacy helpers that already route through `send_unified_email()`
  (bid_placed, outbid, the 3 storage variants, etc.) are listed in
  EMAIL_MIGRATION_TODO.md as DONE.
- Helpers that retain bespoke branded HTML (vehicle compliance, invoices,
  payment receipts, etc.) are listed as REMAINING. They continue to call
  `send_email()` directly until iter242 expands the unified template
  registry to cover their rich content.
"""

from services.email_notifications import send_email, send_unified_email

__all__ = ["send_email", "send_unified_email"]
