"""
Backend API Tests for Subscription Override System (Phase 2)
Tests Admin Panel subscription management: override, extend, revoke, history

Endpoints tested:
- GET /api/admin/users/{user_id}/subscription
- POST /api/admin/users/{user_id}/subscription/override
- POST /api/admin/users/{user_id}/subscription/extend
- POST /api/admin/users/{user_id}/subscription/revoke
- GET /api/admin/users/{user_id}/subscription/history
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
TEST_USER_EMAIL = "buyer.test@bidvex.com"


class TestSubscriptionOverrideSystem:
    """Test suite for admin subscription override system"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Get headers with admin auth"""
        return {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_user_id(self, admin_headers):
        """Get test user ID from user list"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        assert response.status_code == 200, f"Failed to fetch users: {response.text}"
        users = response.json()
        
        # Find test buyer user
        test_user = None
        for user in users:
            if user.get("email") == TEST_USER_EMAIL:
                test_user = user
                break
        
        # If test user not found, use first non-admin user
        if not test_user:
            for user in users:
                if user.get("role") not in ["admin", "super_admin"]:
                    test_user = user
                    break
        
        assert test_user, "No suitable test user found"
        return test_user.get("id")
    
    # ============ GET SUBSCRIPTION TESTS ============
    
    def test_get_user_subscription(self, admin_headers, test_user_id):
        """Test GET /api/admin/users/{user_id}/subscription returns subscription details"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Failed to get subscription: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "user_id" in data
        assert "email" in data
        assert "subscription" in data
        assert "stripe" in data
        assert "override_info" in data
        assert "plan_benefits" in data
        
        # Validate subscription object
        sub = data["subscription"]
        assert "plan" in sub
        assert sub["plan"] in ["free", "premium", "vip"]
        assert "status" in sub
        assert "source" in sub
        
        # Validate stripe object
        assert "has_subscription" in data["stripe"]
        
        print(f"✅ GET subscription: user={data['email']}, plan={sub['plan']}, source={sub['source']}")
    
    def test_get_subscription_nonexistent_user(self, admin_headers):
        """Test GET subscription for non-existent user returns 404"""
        fake_user_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{fake_user_id}/subscription",
            headers=admin_headers
        )
        
        assert response.status_code == 404
        print("✅ GET subscription for non-existent user correctly returns 404")
    
    def test_get_subscription_without_auth(self, test_user_id):
        """Test GET subscription without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription"
        )
        
        assert response.status_code == 401
        print("✅ GET subscription without auth correctly returns 401")
    
    # ============ OVERRIDE SUBSCRIPTION TESTS ============
    
    def test_override_subscription_to_premium(self, admin_headers, test_user_id):
        """Test POST /api/admin/users/{user_id}/subscription/override to Premium"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "duration_days": 30,
                "reason": "TEST_override - Testing premium upgrade"
            }
        )
        
        # Check if blocked due to Stripe subscription (409) or success (200)
        if response.status_code == 409:
            data = response.json()
            assert "Stripe subscription" in data.get("detail", "")
            print(f"⚠️ Override blocked: User has active Stripe subscription (expected behavior)")
            pytest.skip("User has active Stripe subscription - override blocked as expected")
        
        assert response.status_code == 200, f"Override failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data["subscription"]["plan"] == "premium"
        assert data["subscription"]["source"] == "manual"
        assert data["subscription"]["status"] == "active"
        assert "end_date" in data["subscription"]
        
        print(f"✅ Override to Premium successful: end_date={data['subscription']['end_date']}")
    
    def test_override_subscription_to_vip(self, admin_headers, test_user_id):
        """Test override to VIP plan"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "vip",
                "duration_days": 365,
                "reason": "TEST_override - Testing VIP upgrade"
            }
        )
        
        if response.status_code == 409:
            pytest.skip("User has active Stripe subscription")
        
        assert response.status_code == 200, f"VIP override failed: {response.text}"
        data = response.json()
        
        assert data["subscription"]["plan"] == "vip"
        assert data["subscription"]["days_remaining"] == 365
        
        print(f"✅ Override to VIP successful: days_remaining={data['subscription']['days_remaining']}")
    
    def test_override_with_custom_end_date(self, admin_headers, test_user_id):
        """Test override with custom end_date"""
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "end_date": future_date,
                "reason": "TEST_override - Testing custom end date"
            }
        )
        
        if response.status_code == 409:
            pytest.skip("User has active Stripe subscription")
        
        assert response.status_code == 200, f"Custom date override failed: {response.text}"
        data = response.json()
        
        assert data["subscription"]["plan"] == "premium"
        assert future_date in data["subscription"]["end_date"]
        
        print(f"✅ Override with custom end date successful")
    
    def test_override_invalid_plan(self, admin_headers, test_user_id):
        """Test override with invalid plan returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "invalid_plan",
                "duration_days": 30,
                "reason": "TEST_override"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid plan" in response.json().get("detail", "")
        print("✅ Override with invalid plan correctly returns 400")
    
    def test_override_without_reason(self, admin_headers, test_user_id):
        """Test override without reason - should fail validation"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "duration_days": 30
                # Missing reason
            }
        )
        
        assert response.status_code == 422  # Pydantic validation error
        print("✅ Override without reason correctly returns 422 validation error")
    
    def test_override_past_end_date(self, admin_headers, test_user_id):
        """Test override with past end date returns 400"""
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "end_date": past_date,
                "reason": "TEST_override"
            }
        )
        
        if response.status_code == 409:
            pytest.skip("User has active Stripe subscription")
        
        assert response.status_code == 400
        assert "future" in response.json().get("detail", "").lower()
        print("✅ Override with past end date correctly returns 400")
    
    # ============ EXTEND SUBSCRIPTION TESTS ============
    
    def test_extend_subscription(self, admin_headers, test_user_id):
        """Test POST /api/admin/users/{user_id}/subscription/extend"""
        # First ensure user has a paid plan
        setup_response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "duration_days": 30,
                "reason": "TEST_setup for extend test"
            }
        )
        
        if setup_response.status_code == 409:
            pytest.skip("User has active Stripe subscription")
        
        # Now extend
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/extend",
            headers=admin_headers,
            json={
                "additional_days": 15,
                "reason": "TEST_extend - Testing subscription extension"
            }
        )
        
        if response.status_code == 409:
            pytest.skip("Cannot extend Stripe subscription from admin panel")
        
        assert response.status_code == 200, f"Extend failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "new_end_date" in data
        assert "days_remaining" in data
        
        print(f"✅ Extend successful: new_end={data['new_end_date']}, days_remaining={data['days_remaining']}")
    
    def test_extend_free_plan_fails(self, admin_headers, test_user_id):
        """Test extending Free plan fails"""
        # First downgrade to free
        requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "free",
                "reason": "TEST_setup for free extend test"
            }
        )
        
        # Try to extend free plan
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/extend",
            headers=admin_headers,
            json={
                "additional_days": 30,
                "reason": "TEST_extend"
            }
        )
        
        assert response.status_code == 400
        assert "Free plan" in response.json().get("detail", "")
        print("✅ Extending Free plan correctly returns 400")
    
    def test_extend_zero_days(self, admin_headers, test_user_id):
        """Test extending with 0 days fails"""
        # Setup paid plan first
        requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "duration_days": 30,
                "reason": "TEST_setup"
            }
        )
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/extend",
            headers=admin_headers,
            json={
                "additional_days": 0,
                "reason": "TEST_extend"
            }
        )
        
        assert response.status_code == 400
        print("✅ Extending with 0 days correctly returns 400")
    
    # ============ REVOKE SUBSCRIPTION TESTS ============
    
    def test_revoke_subscription(self, admin_headers, test_user_id):
        """Test POST /api/admin/users/{user_id}/subscription/revoke"""
        # First ensure user has a paid plan
        setup_response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "duration_days": 30,
                "reason": "TEST_setup for revoke test"
            }
        )
        
        if setup_response.status_code == 409:
            pytest.skip("User has active Stripe subscription")
        
        # Now revoke
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/revoke",
            headers=admin_headers,
            json={
                "reason": "TEST_revoke - Testing subscription revocation"
            }
        )
        
        if response.status_code == 409:
            pytest.skip("Cannot revoke Stripe subscription from admin panel")
        
        assert response.status_code == 200, f"Revoke failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("previous_plan") == "premium"
        assert "downgraded to Free" in data.get("message", "")
        
        # Verify user is now on free plan
        verify_response = requests.get(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription",
            headers=admin_headers
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["subscription"]["plan"] == "free"
        
        print("✅ Revoke successful: User downgraded to Free")
    
    def test_revoke_free_plan_fails(self, admin_headers, test_user_id):
        """Test revoking Free plan fails"""
        # Ensure user is on free plan
        requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "free",
                "reason": "TEST_setup for free revoke test"
            }
        )
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/revoke",
            headers=admin_headers,
            json={
                "reason": "TEST_revoke"
            }
        )
        
        assert response.status_code == 400
        assert "already on Free" in response.json().get("detail", "")
        print("✅ Revoking Free plan correctly returns 400")
    
    def test_revoke_without_reason(self, admin_headers, test_user_id):
        """Test revoke without reason fails"""
        # Setup paid plan
        requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "premium",
                "duration_days": 30,
                "reason": "TEST_setup"
            }
        )
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/revoke",
            headers=admin_headers,
            json={
                "reason": ""  # Empty reason
            }
        )
        
        assert response.status_code == 400
        assert "required" in response.json().get("detail", "").lower()
        print("✅ Revoke without reason correctly returns 400")
    
    # ============ SUBSCRIPTION HISTORY TESTS ============
    
    def test_get_subscription_history(self, admin_headers, test_user_id):
        """Test GET /api/admin/users/{user_id}/subscription/history"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/history",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Failed to get history: {response.text}"
        data = response.json()
        
        assert "user_id" in data
        assert "history" in data
        assert isinstance(data["history"], list)
        
        # Check history entries have expected fields
        if len(data["history"]) > 0:
            entry = data["history"][0]
            assert "action" in entry
            assert "timestamp" in entry
            assert entry["action"] in ["subscription_override", "subscription_extended", "subscription_revoked"]
        
        print(f"✅ GET history successful: {data['history_count']} entries")
    
    def test_get_history_nonexistent_user(self, admin_headers):
        """Test GET history for non-existent user returns 404"""
        fake_user_id = str(uuid.uuid4())
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{fake_user_id}/subscription/history",
            headers=admin_headers
        )
        
        assert response.status_code == 404
        print("✅ GET history for non-existent user correctly returns 404")
    
    # ============ ACCESS CONTROL TESTS ============
    
    def test_non_admin_cannot_access_subscription(self):
        """Test non-admin user cannot access subscription endpoints"""
        # Login as regular user
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": "Test123!"
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Could not login as test user: {login_response.text}")
        
        user_token = login_response.json().get("access_token")
        user_headers = {"Authorization": f"Bearer {user_token}"}
        
        # Try to access admin subscription endpoint
        user_id = login_response.json()["user"]["id"]
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{user_id}/subscription",
            headers=user_headers
        )
        
        assert response.status_code == 403
        print("✅ Non-admin correctly blocked from subscription endpoints")
    
    # ============ CLEANUP ============
    
    def test_cleanup_test_user(self, admin_headers, test_user_id):
        """Cleanup: Reset test user to free plan"""
        # This is just cleanup, don't fail the test suite
        try:
            requests.post(
                f"{BASE_URL}/api/admin/users/{test_user_id}/subscription/override",
                headers=admin_headers,
                json={
                    "plan": "free",
                    "reason": "TEST_cleanup - Resetting to free plan after tests"
                }
            )
            print("✅ Cleanup: Test user reset to Free plan")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")


class TestStripeConflictBlocking:
    """Test suite for Stripe subscription conflict blocking"""
    
    @pytest.fixture(scope="class")
    def admin_headers(self):
        """Get admin authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return {
            "Authorization": f"Bearer {response.json()['access_token']}",
            "Content-Type": "application/json"
        }
    
    def test_stripe_user_override_blocked(self, admin_headers):
        """Test that users with active Stripe subscriptions are blocked from manual override"""
        # Find a user with stripe subscription or skip
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        users = response.json()
        
        stripe_user = None
        for user in users:
            if user.get("stripe_subscription_id") and user.get("stripe_subscription_status") == "active":
                stripe_user = user
                break
        
        if not stripe_user:
            pytest.skip("No user with active Stripe subscription found")
        
        # Try to override
        override_response = requests.post(
            f"{BASE_URL}/api/admin/users/{stripe_user['id']}/subscription/override",
            headers=admin_headers,
            json={
                "plan": "vip",
                "duration_days": 30,
                "reason": "TEST_stripe_block"
            }
        )
        
        assert override_response.status_code == 409
        assert "Stripe subscription" in override_response.json().get("detail", "")
        print("✅ Stripe subscription user correctly blocked from manual override (409)")
    
    def test_stripe_user_extend_blocked(self, admin_headers):
        """Test that users with Stripe subscriptions cannot be extended"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers)
        users = response.json()
        
        stripe_user = None
        for user in users:
            if user.get("stripe_subscription_id"):
                stripe_user = user
                break
        
        if not stripe_user:
            pytest.skip("No user with Stripe subscription found")
        
        extend_response = requests.post(
            f"{BASE_URL}/api/admin/users/{stripe_user['id']}/subscription/extend",
            headers=admin_headers,
            json={
                "additional_days": 30,
                "reason": "TEST_stripe_extend_block"
            }
        )
        
        assert extend_response.status_code == 409
        assert "Stripe" in extend_response.json().get("detail", "")
        print("✅ Stripe subscription user correctly blocked from extension (409)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
