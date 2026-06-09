"""
services/emails/__init__.py — iter295 P2

Modular email package. Function bodies live in the three bucketed
modules below; the shared SendGrid plumbing + helpers live in
`_email_core.py`. The legacy `services/email_notifications.py` is now
a re-export shim that points back into these files.

Migration tracking
==================
- `send_unified_email()` is the canonical entry-point for ALL new
  transactional emails — see `_email_core.py`.
- iter295 P2 physically migrated 50+ function bodies from
  `services/email_notifications.py` into the bucketed modules below.
"""
from services.emails._email_core import send_email, send_unified_email  # noqa: F401
# iter295 P2 — bucketed modules (re-exports for clean imports).
from services.emails.email_vehicles    import *  # noqa: F401, F403
from services.emails.email_marketplace import *  # noqa: F401, F403
from services.emails.email_system      import *  # noqa: F401, F403

__all__ = ["send_email", "send_unified_email"]
