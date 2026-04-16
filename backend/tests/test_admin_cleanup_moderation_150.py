"""
BidVex Phase 7 - Admin Platform Cleanup & Moderation Controls Tests
Tests for:
- Platform Cleanup Preview & Execution
- Cascade Delete User
- Cascade Delete Listings (single & multi-item)
- Community Moderation (questions & replies)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


class TestAdminAuth:
    """Test admin authentication for cleanup/moderation endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        # Auth returns 'access_token' not 'token'
        token = data.get("access_token") or data.get("token")
        assert token, f"No token in response: {data}"
        return token
    
    def test_admin_login_success(self, admin_token):
        """Verify admin can login successfully"""
        assert admin_token is not None
        print(f"Admin login successful, token obtained")


class TestPlatformCleanupPreview:
    """Test GET /api/admin/platform-cleanup/preview endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_cleanup_preview_requires_auth(self):
        """Verify cleanup preview requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/platform-cleanup/preview")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Cleanup preview correctly requires authentication")
    
    def test_cleanup_preview_returns_counts(self, admin_token):
        """Verify cleanup preview returns test data counts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/platform-cleanup/preview", headers=headers)
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        # Verify expected fields exist
        expected_fields = [
            "test_users", "test_listings", "test_multi_listings", "test_bids",
            "test_messages", "test_notifications", "test_payment_methods",
            "test_escrows", "test_community_questions", "test_community_replies",
            "test_watchlist", "total_records"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
            assert isinstance(data[field], int), f"Field {field} should be int, got {type(data[field])}"
        
        print(f"Cleanup preview returned: {data['test_users']} test users, {data['total_records']} total records")
    
    def test_cleanup_preview_total_calculation(self, admin_token):
        """Verify total_records is sum of all counts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/platform-cleanup/preview", headers=headers)
        data = response.json()
        
        # Calculate expected total
        expected_total = sum([
            data.get("test_users", 0),
            data.get("test_listings", 0),
            data.get("test_multi_listings", 0),
            data.get("test_bids", 0),
            data.get("test_messages", 0),
            data.get("test_notifications", 0),
            data.get("test_payment_methods", 0),
            data.get("test_escrows", 0),
            data.get("test_community_questions", 0),
            data.get("test_community_replies", 0),
            data.get("test_watchlist", 0),
        ])
        
        assert data["total_records"] == expected_total, f"Total mismatch: {data['total_records']} != {expected_total}"
        print(f"Total records calculation verified: {expected_total}")


class TestPlatformCleanupExecution:
    """Test POST /api/admin/platform-cleanup endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_cleanup_requires_auth(self):
        """Verify cleanup execution requires authentication"""
        response = requests.post(f"{BASE_URL}/api/admin/platform-cleanup")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Cleanup execution correctly requires authentication")
    
    def test_cleanup_execution_returns_success(self, admin_token):
        """Verify cleanup execution returns success response"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/admin/platform-cleanup", headers=headers)
        assert response.status_code == 200, f"Cleanup failed: {response.text}"
        
        data = response.json()
        assert "success" in data, "Missing 'success' field"
        assert data["success"] == True, "Cleanup should return success=True"
        assert "message" in data, "Missing 'message' field"
        assert "deleted" in data, "Missing 'deleted' field"
        
        print(f"Cleanup executed: {data['message']}")
        if data.get("deleted"):
            print(f"Deleted records: {data['deleted']}")


class TestCommunityModerationList:
    """Test GET /api/admin/community/questions endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_community_list_requires_auth(self):
        """Verify community questions list requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/community/questions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Community questions list correctly requires authentication")
    
    def test_community_list_returns_questions(self, admin_token):
        """Verify community questions list returns proper structure"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/community/questions", headers=headers)
        assert response.status_code == 200, f"List failed: {response.text}"
        
        data = response.json()
        assert "questions" in data, "Missing 'questions' field"
        assert "total" in data, "Missing 'total' field"
        assert isinstance(data["questions"], list), "Questions should be a list"
        assert isinstance(data["total"], int), "Total should be an integer"
        
        print(f"Community questions: {data['total']} total, {len(data['questions'])} returned")
    
    def test_community_list_with_search(self, admin_token):
        """Verify community questions search works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/community/questions?search=test", headers=headers)
        assert response.status_code == 200, f"Search failed: {response.text}"
        
        data = response.json()
        assert "questions" in data
        print(f"Search returned {len(data['questions'])} questions matching 'test'")
    
    def test_community_list_with_limit(self, admin_token):
        """Verify community questions limit parameter works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/community/questions?limit=5", headers=headers)
        assert response.status_code == 200, f"Limit query failed: {response.text}"
        
        data = response.json()
        assert len(data["questions"]) <= 5, f"Limit not respected: got {len(data['questions'])} questions"
        print(f"Limit parameter working: returned {len(data['questions'])} questions")


class TestCommunityRepliesList:
    """Test GET /api/admin/community/questions/{question_id}/replies endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_replies_list_requires_auth(self):
        """Verify replies list requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/community/questions/fake-id/replies")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Replies list correctly requires authentication")
    
    def test_replies_list_returns_structure(self, admin_token):
        """Verify replies list returns proper structure (even for non-existent question)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Use a fake question ID - should return empty list, not error
        response = requests.get(f"{BASE_URL}/api/admin/community/questions/nonexistent-id/replies", headers=headers)
        assert response.status_code == 200, f"Replies list failed: {response.text}"
        
        data = response.json()
        assert "replies" in data, "Missing 'replies' field"
        assert isinstance(data["replies"], list), "Replies should be a list"
        print(f"Replies list structure verified, returned {len(data['replies'])} replies")


class TestDeleteQuestion:
    """Test DELETE /api/admin/comments/question/{question_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_delete_question_requires_auth(self):
        """Verify delete question requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/admin/comments/question/fake-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Delete question correctly requires authentication")
    
    def test_delete_nonexistent_question_returns_404(self, admin_token):
        """Verify deleting non-existent question returns 404"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.delete(f"{BASE_URL}/api/admin/comments/question/nonexistent-id", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("Delete non-existent question correctly returns 404")


class TestDeleteReply:
    """Test DELETE /api/admin/comments/reply/{reply_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_delete_reply_requires_auth(self):
        """Verify delete reply requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/admin/comments/reply/fake-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Delete reply correctly requires authentication")
    
    def test_delete_nonexistent_reply_returns_404(self, admin_token):
        """Verify deleting non-existent reply returns 404"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.delete(f"{BASE_URL}/api/admin/comments/reply/nonexistent-id", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("Delete non-existent reply correctly returns 404")


class TestCascadeDeleteUser:
    """Test DELETE /api/admin/users/{user_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_delete_user_requires_auth(self):
        """Verify delete user requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/admin/users/fake-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Delete user correctly requires authentication")
    
    def test_delete_nonexistent_user_returns_404(self, admin_token):
        """Verify deleting non-existent user returns 404"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.delete(f"{BASE_URL}/api/admin/users/nonexistent-id", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("Delete non-existent user correctly returns 404")
    
    def test_cannot_delete_self(self, admin_token):
        """Verify admin cannot delete their own account"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # First get current user info
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        if me_response.status_code == 200:
            my_id = me_response.json().get("id")
            if my_id:
                response = requests.delete(f"{BASE_URL}/api/admin/users/{my_id}", headers=headers)
                assert response.status_code == 400, f"Expected 400 for self-delete, got {response.status_code}"
                print("Admin correctly cannot delete their own account")
            else:
                pytest.skip("Could not get current user ID")
        else:
            pytest.skip("Could not get current user info")


class TestCascadeDeleteListing:
    """Test DELETE /api/admin/listings/{listing_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_delete_listing_requires_auth(self):
        """Verify delete listing requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/admin/listings/fake-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Delete listing correctly requires authentication")
    
    def test_delete_nonexistent_listing_returns_404(self, admin_token):
        """Verify deleting non-existent listing returns 404"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.delete(f"{BASE_URL}/api/admin/listings/nonexistent-id", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("Delete non-existent listing correctly returns 404")


class TestCascadeDeleteMultiItemListing:
    """Test DELETE /api/admin/multi-item-listings/{listing_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_delete_multi_listing_requires_auth(self):
        """Verify delete multi-item listing requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/admin/multi-item-listings/fake-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Delete multi-item listing correctly requires authentication")
    
    def test_delete_nonexistent_multi_listing_returns_404(self, admin_token):
        """Verify deleting non-existent multi-item listing returns 404"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.delete(f"{BASE_URL}/api/admin/multi-item-listings/nonexistent-id", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("Delete non-existent multi-item listing correctly returns 404")


class TestAdminUsersList:
    """Test admin users list endpoint for delete button context"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_users_list_returns_users(self, admin_token):
        """Verify admin can list users (for delete button context)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200, f"Users list failed: {response.text}"
        
        data = response.json()
        # Response could be list or object with users key
        users = data if isinstance(data, list) else data.get("users", [])
        assert isinstance(users, list), "Users should be a list"
        
        print(f"Admin users list returned {len(users)} users")
        
        # Verify user objects have expected fields for delete modal
        if users:
            user = users[0]
            expected_fields = ["id", "email", "name"]
            for field in expected_fields:
                assert field in user, f"User missing field: {field}"
            print(f"User object structure verified with fields: {list(user.keys())[:10]}...")


class TestAllListingsAdmin:
    """Test admin listings endpoints for delete button context"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_all_listings_returns_list(self, admin_token):
        """Verify admin can list all single listings"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/listings/all", headers=headers)
        assert response.status_code == 200, f"Listings list failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Listings should be a list"
        print(f"Admin listings list returned {len(data)} listings")
    
    def test_all_multi_listings_returns_list(self, admin_token):
        """Verify admin can list all multi-item listings"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/multi-item-listings/all", headers=headers)
        assert response.status_code == 200, f"Multi-listings list failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Multi-listings should be a list"
        print(f"Admin multi-item listings list returned {len(data)} listings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
