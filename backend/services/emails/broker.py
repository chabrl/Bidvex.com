"""iter241 Mission 2 — Broker emails scaffold.

The legacy email_notifications.py module does not yet contain broker
helpers. New broker-related transactional emails should be authored via
`send_unified_email()` and added below.
"""
from services.emails._email_core import send_unified_email


async def send_broker_application_received(user: dict, data: dict | None = None):
    """iter241 — Acknowledge a broker application via the unified template."""
    return await send_unified_email("welcome", user=user, data=data or {})


async def send_broker_approval(user: dict, data: dict | None = None):
    """iter241 — Notify a broker that they've been approved."""
    return await send_unified_email("welcome", user=user, data=data or {})


__all__ = ["send_broker_application_received", "send_broker_approval"]
