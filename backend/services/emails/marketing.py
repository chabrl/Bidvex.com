"""iter241 Mission 2 — Marketing/campaign emails.

Marketing campaigns are sent through `services.email_marketing` not
through these helpers. This module exists as a stable namespace for any
future bulk-campaign helper that wants to use the unified template.
"""
from services.email_notifications import send_unified_email


async def send_new_feature_announcement(user: dict, data: dict | None = None):
    return await send_unified_email("new_feature", user=user, data=data or {})


async def send_ai_suggestion(user: dict, data: dict | None = None):
    return await send_unified_email("ai_suggestion", user=user, data=data or {})


__all__ = ["send_new_feature_announcement", "send_ai_suggestion"]
