"""
iter215 — Banner auto-refresh fix + Full Admin User Management
================================================================

Covers:
  • GlobalDealerFeeBanner reads correct status fields
    (`active` / `dealer_subscription_active`) — the previous version
    looked at a non-existent `has_active_subscription` flag and stayed
    visible even after admin manual-settle.
  • Banner re-fetches on tab focus + 60 s polling so it disappears
    without requiring a hard refresh.
  • New admin endpoints under /api/admin/users/{user_id}:
      PATCH /profile
      POST  /reset-password
      POST  /change-tier
      POST  /convert-to-demo
      GET   /transactions
      GET   /subscription-status
  • /api/admin/users/filter now supports 6 buckets:
      individual, partner, vehicle_dealer, storage_facility, demo, all.
  • EnhancedUserManager renders the 6 filter buttons + the More-Actions
    dropdown (Edit Profile, Reset Password, Change Tier, Convert to Demo,
    View Transactions, View Subscription).
"""
import os
import re
import sys
import pytest


# ─────────────────────────────────────────────────────────────────────
# Frontend smoke
# ─────────────────────────────────────────────────────────────────────


class TestBannerStatusFieldFix:
    def test_banner_reads_correct_status_field(self):
        with open("/app/frontend/src/components/GlobalDealerFeeBanner.jsx") as f:
            src = f.read()
        # Must look at .active OR dealer_subscription_active
        assert "status?.active" in src
        assert "dealer_subscription_active" in src
        # Must keep backwards-compat with has_active_subscription
        assert "has_active_subscription" in src

    def test_banner_has_focus_refresh_and_polling(self):
        with open("/app/frontend/src/components/GlobalDealerFeeBanner.jsx") as f:
            src = f.read()
        # visibilitychange listener present
        assert "visibilitychange" in src
        # window-focus listener present
        assert "addEventListener('focus'" in src or 'addEventListener("focus"' in src
        # 60 s polling
        assert "60_000" in src or "60000" in src


class TestAdminFilterBuckets:
    """The 6 filter buttons in the Users tab must be rendered."""

    def test_buttons_render(self):
        with open("/app/frontend/src/pages/admin/EnhancedUserManager.js") as f:
            src = f.read()
        for testid in (
            "filter-individual", "filter-partner", "filter-vehicle-dealer",
            "filter-storage-facility", "filter-demo",
        ):
            assert f'data-testid="{testid}"' in src, f"Missing filter button: {testid}"


class TestAdminMoreActionsDropdown:
    """The More-Actions dropdown must expose every new admin action."""

    def test_dropdown_items(self):
        with open("/app/frontend/src/pages/admin/EnhancedUserManager.js") as f:
            src = f.read()
        for testid in (
            "more-actions-",      # generic per-row trigger
            "edit-profile-",
            "reset-password-",
            "change-tier-",
            "convert-demo-",
            "view-txns-",
            "view-sub-",
        ):
            assert testid in src, f"Missing dropdown item testid: {testid}"

    def test_modals_render(self):
        with open("/app/frontend/src/pages/admin/EnhancedUserManager.js") as f:
            src = f.read()
        for testid in (
            "edit-profile-modal", "change-tier-modal", "view-txn-modal",
            "view-sub-modal",
        ):
            assert f'data-testid="{testid}"' in src, f"Missing modal testid: {testid}"


# ─────────────────────────────────────────────────────────────────────
# Backend
# ─────────────────────────────────────────────────────────────────────


class TestNewEndpointsMounted:
    def _routes(self):
        if "server" not in sys.modules:
            import server  # noqa: F401
        from server import app
        return [r.path for r in app.routes if hasattr(r, "path")]

    def test_profile_patch_mounted(self):
        assert "/api/admin/users/{user_id}/profile" in self._routes()

    def test_reset_password_mounted(self):
        assert "/api/admin/users/{user_id}/reset-password" in self._routes()

    def test_change_tier_mounted(self):
        assert "/api/admin/users/{user_id}/change-tier" in self._routes()

    def test_convert_demo_mounted(self):
        assert "/api/admin/users/{user_id}/convert-to-demo" in self._routes()

    def test_transactions_mounted(self):
        assert "/api/admin/users/{user_id}/transactions" in self._routes()

    def test_subscription_status_mounted(self):
        assert "/api/admin/users/{user_id}/subscription-status" in self._routes()


class TestFilterEndpointBuckets:
    """The /admin/users/filter endpoint must accept the 6 bucket values."""

    def test_bucket_logic_in_source(self):
        with open("/app/backend/routes/admin_ops.py") as f:
            src = f.read()
        # Each bucket should appear as a string literal in the bucket-handling block
        for bucket in (
            '"individual"', '"partner"', '"vehicle_dealer"',
            '"storage_facility"', '"demo"',
        ):
            assert bucket in src, f"Missing bucket literal {bucket} in filter handler"
        # Demo bucket queries is_demo_account
        assert 'is_demo_account' in src
        # Vehicle dealer bucket queries is_vehicle_dealer
        assert 'is_vehicle_dealer' in src


class TestChangeTierValidation:
    @pytest.mark.asyncio
    async def test_change_tier_rejects_invalid_tier(self):
        from routes.admin_user_actions import admin_change_buyer_tier, ChangeTierPayload
        from fastapi import HTTPException
        from deps import User

        admin = User(id="a1", email="a@x.com", name="Admin", role="admin")
        with pytest.raises(HTTPException) as exc:
            await admin_change_buyer_tier(
                user_id="u1",
                payload=ChangeTierPayload(tier="UNKNOWN"),
                current_user=admin,
            )
        assert exc.value.status_code == 400
        assert exc.value.detail["error"] == "invalid_tier"


class TestEditProfileValidation:
    @pytest.mark.asyncio
    async def test_edit_profile_empty_payload_returns_400(self):
        from routes.admin_user_actions import admin_edit_user_profile, EditProfilePayload
        from fastapi import HTTPException
        from deps import User
        import deps as deps_module

        class FakeColl:
            async def find_one(self, *a, **k):
                return {"id": "u1", "email": "old@x.com"}
            async def update_one(self, *a, **k):
                return None

        class FakeDB:
            users = FakeColl()
            admin_actions = FakeColl()

        deps_module.set_db(FakeDB())
        admin = User(id="a1", email="a@x.com", name="Admin", role="admin")
        with pytest.raises(HTTPException) as exc:
            await admin_edit_user_profile(
                user_id="u1",
                payload=EditProfilePayload(),  # nothing to update
                current_user=admin,
            )
        assert exc.value.status_code == 400


class TestSubscriptionStatusSnapshot:
    @pytest.mark.asyncio
    async def test_returns_snapshot_for_dealer(self):
        from routes.admin_user_actions import admin_user_subscription_status
        from deps import User
        import deps as deps_module

        class FakeColl:
            async def find_one(self, *a, **k):
                return {
                    "is_vehicle_dealer": True,
                    "dealer_subscription_active": True,
                    "dealer_subscription_status": "paid",
                    "dealer_subscription_renewal": "2027-05-14",
                    "buyer_tier": "standard",
                }

        class FakeDB:
            users = FakeColl()

        deps_module.set_db(FakeDB())
        admin = User(id="a1", email="a@x.com", name="Admin", role="admin")
        result = await admin_user_subscription_status(user_id="u1", current_user=admin)
        assert result["is_vehicle_dealer"] is True
        assert result["dealer_subscription_active"] is True
        assert result["dealer_subscription_status"] == "paid"


class TestConvertDemoToggles:
    @pytest.mark.asyncio
    async def test_flip_off_then_on(self):
        from routes.admin_user_actions import admin_convert_to_demo
        from deps import User
        import deps as deps_module

        state = {"is_demo_account": False}

        class FakeUsersColl:
            async def find_one(self, *a, **k):
                return {"id": "u1", **state}
            async def update_one(self, query, update):
                state["is_demo_account"] = update["$set"]["is_demo_account"]

        class FakeActionsColl:
            async def insert_one(self, *a, **k):
                return None

        class FakeDB:
            users = FakeUsersColl()
            admin_actions = FakeActionsColl()

        deps_module.set_db(FakeDB())
        admin = User(id="a1", email="a@x.com", name="Admin", role="admin")
        # 1st call → True
        r1 = await admin_convert_to_demo("u1", admin)
        assert r1["is_demo_account"] is True
        # 2nd call → False (toggle)
        r2 = await admin_convert_to_demo("u1", admin)
        assert r2["is_demo_account"] is False
