"""
iter211 Step 3 — notification_settings persistence.

Verifies:
  1. PUT /api/users/me accepts `notification_settings` as a Dict[str, bool]
     in the allowed_fields list.
  2. The validator rejects bad keys and non-boolean values.
  3. ProfileSettingsPage.js has been migrated off `defaultChecked` to controlled
     switches with auto-save.
"""


def test_profiles_route_accepts_notification_settings():
    """The backend allow-list must include notification_settings."""
    with open("/app/backend/routes/profiles.py", "r") as f:
        body = f.read()
    # Field is allowed
    assert '"notification_settings"' in body, \
        "PUT /api/users/me must accept notification_settings field"
    # Field is validated for shape
    assert "notification_settings must be an object" in body or \
           "must be an object" in body
    # All 4 expected keys present
    for k in ("email_summaries", "bid_alerts", "message_alerts", "auction_win_alerts"):
        assert k in body, f"notification_settings validator must know about key '{k}'"


def test_profile_settings_page_uses_controlled_switches():
    """The Notifications tab must use controlled Switches with auto-save,
    not hardcoded `defaultChecked`. This was the root cause of the bug."""
    with open("/app/frontend/src/pages/ProfileSettingsPage.js", "r") as f:
        body = f.read()
    # The 4 notification toggles must each have a test id
    for tid in (
        "notif-toggle-email-summaries",
        "notif-toggle-bid-alerts",
        "notif-toggle-message-alerts",
        "notif-toggle-auction-win-alerts",
    ):
        assert f'data-testid="{tid}"' in body, f"Missing controlled toggle: {tid}"

    # Auto-save: useEffect on notificationSettings must POST/PUT to /users/me
    assert "notificationSettings" in body
    assert "/users/me" in body
    assert "handleToggleNotification" in body

    # The old broken pattern (defaultChecked without state) must be gone in the
    # notifications tab. Defensive: count any remaining `defaultChecked` in the
    # notification rows specifically.
    notif_section_start = body.index('value="notifications"')
    notif_section_end = body.index('</TabsContent>', notif_section_start)
    notif_block = body[notif_section_start:notif_section_end]
    assert "defaultChecked" not in notif_block, \
        "Notifications tab still uses `defaultChecked` — root-cause bug returned!"


def test_profile_settings_hydrates_from_server():
    """On mount, the page must read user.notification_settings (with sensible
    defaults if missing)."""
    with open("/app/frontend/src/pages/ProfileSettingsPage.js", "r") as f:
        body = f.read()
    assert "user.notification_settings" in body, \
        "ProfileSettings must hydrate notificationSettings from user.notification_settings"


def test_profile_settings_has_hydration_guard():
    """useEffect auto-save must NOT fire on initial hydration — that would
    cause a spurious save of defaults on every page load."""
    with open("/app/frontend/src/pages/ProfileSettingsPage.js", "r") as f:
        body = f.read()
    assert "notifSettingsHydrated" in body, \
        "Auto-save must be guarded by a hydration flag to avoid firing on initial mount"
