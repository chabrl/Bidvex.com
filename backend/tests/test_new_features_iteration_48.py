"""
BidVex Iteration 48 - New Features Testing
Tests for:
1. Signup Terms & Policy Consent (clickwrap checkbox)
2. Admin RBAC Team Management (invite, roles, permissions)
3. AI Chatbot Claude Sonnet 4.5 with pricing knowledge

Admin credentials: charbeladmin@bidvex.com / Admin123!
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "charbeladmin@bidvex.com",
        "password": "Admin123!"
    })
    if response.status_code != 200:
        pytest.skip("Admin login failed - skipping tests")
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Admin auth headers"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ============================================================
# FEATURE 1: Registration Terms & Policy Consent Tests
# ============================================================

class TestRegistrationTermsConsent:
    """Test registration with terms_agreed validation (Feature 1)"""

    def test_register_without_terms_agreed_fails(self):
        """Registration without terms_agreed=true should fail with 400"""
        test_email = f"test_no_terms_{uuid.uuid4().hex[:8]}@test.com"
        payload = {
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test User NoTerms",
            "account_type": "personal",
            "phone": "5141234567",
            "terms_agreed": False
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        # Assert status code is 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        # Assert error message mentions terms
        data = response.json()
        assert "detail" in data
        assert "Terms" in data["detail"] or "terms" in data["detail"].lower() or "agree" in data["detail"].lower()
        print(f"✓ Registration without terms fails with 400: {data['detail']}")

    def test_register_with_terms_agreed_succeeds(self):
        """Registration with terms_agreed=true should succeed and return token"""
        test_email = f"test_with_terms_{uuid.uuid4().hex[:8]}@test.com"
        payload = {
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test User WithTerms",
            "account_type": "personal",
            "phone": "5141234568",
            "terms_agreed": True
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        # Assert status code is 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Assert response contains token and user
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert len(data["access_token"]) > 0
        print(f"✓ Registration with terms succeeds, token length: {len(data['access_token'])}")

    def test_register_missing_terms_field_defaults_false(self):
        """Registration without terms_agreed field should fail (defaults to False)"""
        test_email = f"test_missing_terms_{uuid.uuid4().hex[:8]}@test.com"
        payload = {
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test User MissingTerms",
            "account_type": "personal",
            "phone": "5141234569"
            # terms_agreed field intentionally omitted
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        # Should fail with 400 since terms_agreed defaults to False
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Registration without terms_agreed field fails as expected")


# ============================================================
# FEATURE 2: Team Management RBAC Tests
# ============================================================

class TestTeamManagementRBAC:
    """Test Admin RBAC Team Management endpoints (Feature 2)"""

    def test_get_roles_info(self):
        """GET /api/team/roles returns role definitions and permissions"""
        response = requests.get(f"{BASE_URL}/api/team/roles")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "roles" in data
        assert "permissions" in data
        
        # Verify all 3 roles exist
        role_ids = [r["id"] for r in data["roles"]]
        assert "admin" in role_ids
        assert "manager" in role_ids
        assert "support" in role_ids
        
        # Verify permissions structure
        assert "admin" in data["permissions"]
        assert "manager" in data["permissions"]
        assert "support" in data["permissions"]
        
        # Verify support is view-only (no manage_* permissions)
        support_perms = data["permissions"]["support"]
        assert support_perms.get("manage_team") == False
        assert support_perms.get("manage_users") == False
        assert support_perms.get("manage_auctions") == False
        assert support_perms.get("view_analytics") == True
        print("✓ GET /api/team/roles returns correct role definitions")

    def test_invite_requires_admin(self):
        """POST /api/team/invite requires admin authentication"""
        # Without auth should fail
        response = requests.post(f"{BASE_URL}/api/team/invite", json={
            "email": "test@example.com",
            "role": "support"
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ POST /api/team/invite requires authentication")

    def test_invite_team_member_as_admin(self, admin_headers):
        """POST /api/team/invite creates invitation (admin only)"""
        test_email = f"invite_test_{uuid.uuid4().hex[:8]}@testteam.com"
        payload = {
            "email": test_email,
            "role": "support",
            "name": "Test Support User"
        }
        response = requests.post(f"{BASE_URL}/api/team/invite", json=payload, headers=admin_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert "invite_link" in data
        assert "invitation_id" in data
        assert test_email in data["message"]
        print(f"✓ POST /api/team/invite creates invitation: {data['invitation_id']}")
        return data

    def test_list_team_members_as_admin(self, admin_headers):
        """GET /api/team/members lists team members (admin only)"""
        response = requests.get(f"{BASE_URL}/api/team/members", headers=admin_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "members" in data
        assert isinstance(data["members"], list)
        print(f"✓ GET /api/team/members returns {len(data['members'])} members")

    def test_list_team_members_requires_admin(self):
        """GET /api/team/members requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/team/members")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/team/members requires admin auth")

    def test_list_invitations_as_admin(self, admin_headers):
        """GET /api/team/invitations lists invitations (admin only)"""
        response = requests.get(f"{BASE_URL}/api/team/invitations", headers=admin_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "invitations" in data
        assert isinstance(data["invitations"], list)
        print(f"✓ GET /api/team/invitations returns {len(data['invitations'])} invitations")

    def test_invite_info_and_accept_flow(self, admin_headers):
        """Test full invite flow: create -> get info -> accept"""
        # Step 1: Create invitation
        test_email = f"accept_test_{uuid.uuid4().hex[:8]}@testteam.com"
        create_res = requests.post(f"{BASE_URL}/api/team/invite", json={
            "email": test_email,
            "role": "manager",
            "name": "Test Manager"
        }, headers=admin_headers)
        
        assert create_res.status_code == 200, f"Failed to create invite: {create_res.text}"
        invite_link = create_res.json()["invite_link"]
        token = invite_link.split("/invite/")[-1]
        print(f"✓ Created invitation with token: {token[:20]}...")

        # Step 2: Get invite info
        info_res = requests.get(f"{BASE_URL}/api/team/invite/{token}/info")
        assert info_res.status_code == 200, f"Failed to get invite info: {info_res.text}"
        
        info_data = info_res.json()
        assert info_data["email"] == test_email
        assert info_data["role"] == "manager"
        assert "invited_by_name" in info_data
        assert "expires_at" in info_data
        print(f"✓ GET /api/team/invite/{token[:10]}.../info returns correct data")

        # Step 3: Accept invitation
        accept_res = requests.post(f"{BASE_URL}/api/team/invite/{token}/accept", json={
            "name": "Test Manager Accepted",
            "password": "SecurePass123!"
        })
        
        assert accept_res.status_code == 200, f"Failed to accept invite: {accept_res.text}"
        
        accept_data = accept_res.json()
        assert accept_data["success"] == True
        assert accept_data["role"] == "manager"
        print(f"✓ POST /api/team/invite/{token[:10]}.../accept creates user with role")

        # Step 4: Verify user can login with created credentials
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": "SecurePass123!"
        })
        assert login_res.status_code == 200, f"New team member cannot login: {login_res.text}"
        print("✓ New team member can login with created credentials")

    def test_invalid_token_returns_404(self):
        """GET /api/team/invite/{invalid_token}/info returns 404"""
        response = requests.get(f"{BASE_URL}/api/team/invite/invalid-token-12345/info")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid token returns 404")

    def test_update_member_role(self, admin_headers):
        """PUT /api/team/members/{id}/role updates member role"""
        # First get members to find one to update
        members_res = requests.get(f"{BASE_URL}/api/team/members", headers=admin_headers)
        members = members_res.json()["members"]
        
        # Find a non-admin member to update
        target_member = None
        for m in members:
            if m["role"] != "admin" and m.get("team_member"):
                target_member = m
                break
        
        if not target_member:
            pytest.skip("No non-admin team member found to test role update")
        
        # Update role to support
        new_role = "support" if target_member["role"] != "support" else "manager"
        update_res = requests.put(
            f"{BASE_URL}/api/team/members/{target_member['id']}/role",
            json={"role": new_role},
            headers=admin_headers
        )
        
        assert update_res.status_code == 200, f"Failed to update role: {update_res.text}"
        assert update_res.json()["success"] == True
        print(f"✓ PUT /api/team/members/{target_member['id'][:8]}.../role updated to {new_role}")

    def test_cancel_invitation(self, admin_headers):
        """DELETE /api/team/invitations/{id} cancels invitation"""
        # Create a new invitation to cancel
        test_email = f"cancel_test_{uuid.uuid4().hex[:8]}@testteam.com"
        create_res = requests.post(f"{BASE_URL}/api/team/invite", json={
            "email": test_email,
            "role": "support"
        }, headers=admin_headers)
        
        assert create_res.status_code == 200
        invitation_id = create_res.json()["invitation_id"]
        
        # Cancel the invitation
        cancel_res = requests.delete(
            f"{BASE_URL}/api/team/invitations/{invitation_id}",
            headers=admin_headers
        )
        
        assert cancel_res.status_code == 200, f"Failed to cancel: {cancel_res.text}"
        assert cancel_res.json()["success"] == True
        print(f"✓ DELETE /api/team/invitations/{invitation_id[:8]}... cancels invitation")


# ============================================================
# FEATURE 3: AI Chatbot Claude Sonnet 4.5 Tests
# ============================================================

class TestAIChatbotClaude:
    """Test AI Chatbot with Claude Sonnet 4.5 and pricing knowledge (Feature 3)"""

    def test_ai_chat_responds(self, admin_headers):
        """POST /api/ai-chat/message responds with Claude output"""
        payload = {"message": "Hello, what can you help me with?"}
        response = requests.post(f"{BASE_URL}/api/ai-chat/message", json=payload, headers=admin_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0
        print(f"✓ AI chat responds with message of length {len(data['message'])}")

    def test_ai_chat_knows_premium_price(self, admin_headers):
        """Chatbot knows Premium price is $213.45/month"""
        payload = {"message": "What is the price of the Premium subscription?"}
        response = requests.post(f"{BASE_URL}/api/ai-chat/message", json=payload, headers=admin_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        message = data["message"].lower()
        
        # Check if response mentions Premium price
        assert "213" in message or "$213.45" in data["message"], f"Premium price not mentioned: {data['message'][:200]}"
        print(f"✓ AI knows Premium price ($213.45)")

    def test_ai_chat_knows_vip_price(self, admin_headers):
        """Chatbot knows VIP price is $355.54/month"""
        payload = {"message": "How much does VIP Elite subscription cost?"}
        response = requests.post(f"{BASE_URL}/api/ai-chat/message", json=payload, headers=admin_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        message = data["message"]
        
        # Check if response mentions VIP price
        assert "355" in message or "$355.54" in message, f"VIP price not mentioned: {message[:200]}"
        print(f"✓ AI knows VIP Elite price ($355.54)")

    def test_ai_chat_knows_refund_policy(self, admin_headers):
        """Chatbot knows about No Refund policy"""
        payload = {"message": "What is BidVex's refund policy? Can I get a refund?"}
        response = requests.post(f"{BASE_URL}/api/ai-chat/message", json=payload, headers=admin_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        message = data["message"].lower()
        
        # Check if response mentions no refund policy
        refund_keywords = ["no refund", "non-refund", "not refund", "cannot be refund", "final", "non refund"]
        has_refund_info = any(kw in message for kw in refund_keywords)
        assert has_refund_info, f"Refund policy not mentioned: {data['message'][:300]}"
        print("✓ AI knows about No Refund policy")


# ============================================================
# Run tests if executed directly
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
