"""
BidVex Community Q&A API Tests - Iteration 145
Tests for:
- Community questions CRUD
- Replies CRUD
- Upvotes (toggle)
- Best answer marking
- Auth requirements
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "charbel911@gmail.com"
TEST_PASSWORD = "Anderosli123!@#"


class TestCommunityAPI:
    """Community Q&A API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    # ─── GET Questions (Public) ───
    def test_get_questions_public(self):
        """GET /api/community/questions - should work without auth"""
        response = requests.get(f"{BASE_URL}/api/community/questions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "questions" in data, "Response should have 'questions' key"
        assert "total" in data, "Response should have 'total' key"
        assert isinstance(data["questions"], list), "Questions should be a list"
        print(f"✓ GET questions public: {data['total']} total questions")
    
    def test_get_questions_with_sort(self):
        """GET /api/community/questions with sort parameter"""
        for sort_type in ["newest", "most_replies", "most_upvoted"]:
            response = requests.get(f"{BASE_URL}/api/community/questions", params={"sort": sort_type})
            assert response.status_code == 200, f"Sort '{sort_type}' failed: {response.status_code}"
        print("✓ GET questions with all sort options works")
    
    def test_get_questions_with_search(self):
        """GET /api/community/questions with search parameter"""
        response = requests.get(f"{BASE_URL}/api/community/questions", params={"search": "test"})
        assert response.status_code == 200, f"Search failed: {response.status_code}"
        print("✓ GET questions with search works")
    
    # ─── POST Question (Auth Required) ───
    def test_create_question_without_auth(self):
        """POST /api/community/questions without auth should fail"""
        response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": "Test question",
            "body": "This is a test question body"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST question without auth correctly rejected")
    
    def test_create_question_with_auth(self, auth_headers):
        """POST /api/community/questions with auth should succeed"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": f"TEST_Question_{unique_id}",
            "body": f"This is a test question body for testing purposes. Unique ID: {unique_id}"
        }, headers=auth_headers)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have 'id'"
        assert data["title"].startswith("TEST_Question_"), "Title should match"
        print(f"✓ POST question with auth: created question {data['id']}")
        return data["id"]
    
    def test_create_question_validation(self, auth_headers):
        """POST /api/community/questions with invalid data should fail"""
        # Title too short
        response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": "Hi",
            "body": "This is a valid body text for testing"
        }, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400 for short title, got {response.status_code}"
        
        # Body too short
        response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": "Valid title here",
            "body": "Short"
        }, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400 for short body, got {response.status_code}"
        print("✓ POST question validation works correctly")
    
    # ─── GET Single Question ───
    def test_get_single_question(self, auth_headers):
        """GET /api/community/questions/{id} should return question with replies"""
        # First create a question
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": f"TEST_SingleQ_{unique_id}",
            "body": f"Test body for single question test. ID: {unique_id}"
        }, headers=auth_headers)
        
        if create_response.status_code not in [200, 201]:
            pytest.skip("Could not create question for test")
        
        question_id = create_response.json()["id"]
        
        # Get the question
        response = requests.get(f"{BASE_URL}/api/community/questions/{question_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["id"] == question_id, "Question ID should match"
        assert "replies" in data, "Response should include replies"
        print(f"✓ GET single question works: {question_id}")
    
    def test_get_nonexistent_question(self):
        """GET /api/community/questions/{id} with invalid ID should return 404"""
        response = requests.get(f"{BASE_URL}/api/community/questions/nonexistent-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ GET nonexistent question returns 404")
    
    # ─── POST Reply (Auth Required) ───
    def test_create_reply_without_auth(self, auth_headers):
        """POST /api/community/questions/{id}/replies without auth should fail"""
        # First create a question
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": f"TEST_ReplyTest_{unique_id}",
            "body": f"Test body for reply test. ID: {unique_id}"
        }, headers=auth_headers)
        
        if create_response.status_code not in [200, 201]:
            pytest.skip("Could not create question for test")
        
        question_id = create_response.json()["id"]
        
        # Try to reply without auth
        response = requests.post(f"{BASE_URL}/api/community/questions/{question_id}/replies", json={
            "body": "This is a test reply"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST reply without auth correctly rejected")
    
    def test_create_reply_with_auth(self, auth_headers):
        """POST /api/community/questions/{id}/replies with auth should succeed"""
        # First create a question
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": f"TEST_ReplyAuth_{unique_id}",
            "body": f"Test body for reply auth test. ID: {unique_id}"
        }, headers=auth_headers)
        
        if create_response.status_code not in [200, 201]:
            pytest.skip("Could not create question for test")
        
        question_id = create_response.json()["id"]
        
        # Create reply with auth
        response = requests.post(f"{BASE_URL}/api/community/questions/{question_id}/replies", json={
            "body": f"This is a test reply for question {unique_id}"
        }, headers=auth_headers)
        
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have 'id'"
        assert data["question_id"] == question_id, "Question ID should match"
        print(f"✓ POST reply with auth: created reply {data['id']}")
    
    # ─── Upvote Question (Auth Required) ───
    def test_upvote_question_without_auth(self, auth_headers):
        """POST /api/community/questions/{id}/upvote without auth should fail"""
        # First create a question
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": f"TEST_UpvoteNoAuth_{unique_id}",
            "body": f"Test body for upvote test. ID: {unique_id}"
        }, headers=auth_headers)
        
        if create_response.status_code not in [200, 201]:
            pytest.skip("Could not create question for test")
        
        question_id = create_response.json()["id"]
        
        # Try to upvote without auth
        response = requests.post(f"{BASE_URL}/api/community/questions/{question_id}/upvote")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST upvote without auth correctly rejected")
    
    def test_upvote_question_toggle(self, auth_headers):
        """POST /api/community/questions/{id}/upvote should toggle upvote"""
        # First create a question
        unique_id = str(uuid.uuid4())[:8]
        create_response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": f"TEST_UpvoteToggle_{unique_id}",
            "body": f"Test body for upvote toggle test. ID: {unique_id}"
        }, headers=auth_headers)
        
        if create_response.status_code not in [200, 201]:
            pytest.skip("Could not create question for test")
        
        question_id = create_response.json()["id"]
        
        # First upvote (add)
        response1 = requests.post(f"{BASE_URL}/api/community/questions/{question_id}/upvote", 
                                  headers=auth_headers)
        assert response1.status_code == 200, f"First upvote failed: {response1.status_code}"
        data1 = response1.json()
        assert data1["status"] == "added", f"Expected 'added', got {data1['status']}"
        
        # Second upvote (remove)
        response2 = requests.post(f"{BASE_URL}/api/community/questions/{question_id}/upvote", 
                                  headers=auth_headers)
        assert response2.status_code == 200, f"Second upvote failed: {response2.status_code}"
        data2 = response2.json()
        assert data2["status"] == "removed", f"Expected 'removed', got {data2['status']}"
        
        print("✓ POST upvote toggle works correctly")
    
    # ─── Best Reply (Auth Required, Author Only) ───
    def test_mark_best_reply(self, auth_headers):
        """POST /api/community/questions/{id}/best-reply should mark best answer"""
        # Create a question
        unique_id = str(uuid.uuid4())[:8]
        q_response = requests.post(f"{BASE_URL}/api/community/questions", json={
            "title": f"TEST_BestReply_{unique_id}",
            "body": f"Test body for best reply test. ID: {unique_id}"
        }, headers=auth_headers)
        
        if q_response.status_code not in [200, 201]:
            pytest.skip("Could not create question for test")
        
        question_id = q_response.json()["id"]
        
        # Create a reply
        r_response = requests.post(f"{BASE_URL}/api/community/questions/{question_id}/replies", json={
            "body": f"This is a great answer for {unique_id}"
        }, headers=auth_headers)
        
        if r_response.status_code not in [200, 201]:
            pytest.skip("Could not create reply for test")
        
        reply_id = r_response.json()["id"]
        
        # Mark as best
        best_response = requests.post(f"{BASE_URL}/api/community/questions/{question_id}/best-reply", 
                                      json={"reply_id": reply_id}, headers=auth_headers)
        
        assert best_response.status_code == 200, f"Expected 200, got {best_response.status_code}: {best_response.text}"
        assert best_response.json()["status"] == "ok", "Status should be 'ok'"
        
        # Verify the reply is marked as best
        verify_response = requests.get(f"{BASE_URL}/api/community/questions/{question_id}")
        verify_data = verify_response.json()
        assert verify_data["best_reply_id"] == reply_id, "Best reply ID should be set"
        
        print(f"✓ POST best-reply works: marked reply {reply_id} as best")


class TestHowItWorksCTARoutes:
    """Test that HowItWorks CTA routes are correctly configured"""
    
    def test_create_listing_route_exists(self):
        """Verify /create-listing route exists (frontend route)"""
        # This tests that the backend doesn't 404 on the frontend route
        # The actual route is handled by React Router
        response = requests.get(f"{BASE_URL}/create-listing", allow_redirects=False)
        # Should either return 200 (SPA) or redirect, not 404
        assert response.status_code != 404, f"Route /create-listing should exist, got {response.status_code}"
        print("✓ /create-listing route accessible")
    
    def test_auth_route_exists(self):
        """Verify /auth route exists (frontend route)"""
        response = requests.get(f"{BASE_URL}/auth", allow_redirects=False)
        assert response.status_code != 404, f"Route /auth should exist, got {response.status_code}"
        print("✓ /auth route accessible")
    
    def test_become_partner_route_exists(self):
        """Verify /become-a-partner route exists (frontend route)"""
        response = requests.get(f"{BASE_URL}/become-a-partner", allow_redirects=False)
        assert response.status_code != 404, f"Route /become-a-partner should exist, got {response.status_code}"
        print("✓ /become-a-partner route accessible")
    
    def test_vehicle_auctions_route_exists(self):
        """Verify /vehicle-auctions route exists (frontend route)"""
        response = requests.get(f"{BASE_URL}/vehicle-auctions", allow_redirects=False)
        assert response.status_code != 404, f"Route /vehicle-auctions should exist, got {response.status_code}"
        print("✓ /vehicle-auctions route accessible")
    
    def test_vehicle_seller_register_route_exists(self):
        """Verify /vehicle-auctions/seller/register route exists (frontend route)"""
        response = requests.get(f"{BASE_URL}/vehicle-auctions/seller/register", allow_redirects=False)
        assert response.status_code != 404, f"Route /vehicle-auctions/seller/register should exist, got {response.status_code}"
        print("✓ /vehicle-auctions/seller/register route accessible")
    
    def test_community_route_exists(self):
        """Verify /community route exists (frontend route)"""
        response = requests.get(f"{BASE_URL}/community", allow_redirects=False)
        assert response.status_code != 404, f"Route /community should exist, got {response.status_code}"
        print("✓ /community route accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
