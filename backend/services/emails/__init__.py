"""
services/emails/__init__.py

Modular email package — was set up in iter241 (services.emails.bidding,
send_email, send_unified_email re-exports). iter294 P2 added three
type-bucketed submodules (vehicles / marketplace / system) so new code
can target the right concern without fishing through the 3000-line
legacy `services/email_notifications.py`.

Migration tracking
==================
- `send_unified_email()` is the canonical entry-point for ALL new
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
# iter294 P2 — type-bucketed submodules (re-exports for clean imports).
from services.emails.email_vehicles    import *  # noqa: F401, F403
from services.emails.email_marketplace import *  # noqa: F401, F403
from services.emails.email_system      import *  # noqa: F401, F403

__all__ = ["send_email", "send_unified_email"]
