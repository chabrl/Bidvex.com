"""
Test Email Marketing Campaign Management Endpoints
- DELETE /api/admin/marketing/campaigns/{campaign_id}
- POST /api/admin/marketing/campaigns/{campaign_id}/clone
- POST /api/admin/marketing/campaigns/{campaign_id}/resend
- GET /api/admin/marketing/campaigns
- POST /api/ai-chat/message (AI Chatbot)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Admin123!"


class TestEmailMarketingCampaigns:
    """Test suite for Email Marketing Campaign Management"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        # Login returns 'access_token' field
        token = data.get("access_token") or data.get("token")
        assert token, f"No token in response: {data}"
        return token
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    # ========== GET /api/admin/marketing/campaigns ==========
    def test_list_campaigns(self, auth_headers):
        """Test listing all campaigns"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing/campaigns", headers=auth_headers)
        assert response.status_code == 200, f"List campaigns failed: {response.text}"
        data = response.json()
        assert "campaigns" in data, "Response should contain 'campaigns' key"
        assert isinstance(data["campaigns"], list), "Campaigns should be a list"
        print(f"PASS: List campaigns - found {len(data['campaigns'])} campaigns")
    
    # ========== POST /api/admin/marketing/campaigns (Create for testing) ==========
    @pytest.fixture(scope="class")
    def test_campaign(self, auth_headers):
        """Create a test campaign for other tests"""
        campaign_data = {
            "name": f"TEST_Campaign_{uuid.uuid4().hex[:8]}",
            "subject": "Test Subject",
            "html_content": "<html><body>Test content</body></html>",
            "plain_text_content": "Test content",
            "audience_filters": {
                "subscription_tiers": [],
                "account_types": [],
                "regions": [],
                "activity_status": "",
                "exclude_unsubscribed": True
            }
        }
        response = requests.post(f"{BASE_URL}/api/admin/marketing/campaigns", 
                                 json=campaign_data, headers=auth_headers)
        assert response.status_code == 200, f"Create campaign failed: {response.text}"
        data = response.json()
        assert "id" in data, "Campaign should have an ID"
        print(f"PASS: Created test campaign with ID: {data['id']}")
        return data
    
    # ========== POST /api/admin/marketing/campaigns/{id}/clone ==========
    def test_clone_campaign(self, auth_headers, test_campaign):
        """Test cloning a campaign"""
        campaign_id = test_campaign["id"]
        response = requests.post(f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/clone", 
                                 json={}, headers=auth_headers)
        assert response.status_code == 200, f"Clone campaign failed: {response.text}"
        data = response.json()
        
        # Verify clone properties
        assert "id" in data, "Cloned campaign should have an ID"
        assert data["id"] != campaign_id, "Cloned campaign should have different ID"
        assert "(Copy)" in data["name"], f"Cloned campaign name should contain '(Copy)', got: {data['name']}"
        assert data["status"] == "draft", f"Cloned campaign should be in draft status, got: {data['status']}"
        print(f"PASS: Cloned campaign - new ID: {data['id']}, name: {data['name']}")
        
        # Cleanup: delete the cloned campaign
        requests.delete(f"{BASE_URL}/api/admin/marketing/campaigns/{data['id']}", headers=auth_headers)
        return data
    
    # ========== POST /api/admin/marketing/campaigns/{id}/resend ==========
    def test_resend_draft_campaign_should_fail(self, auth_headers, test_campaign):
        """Test that resending a draft campaign returns 400"""
        campaign_id = test_campaign["id"]
        response = requests.post(f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/resend", 
                                 json={}, headers=auth_headers)
        # Draft campaigns cannot be resent - should return 400
        assert response.status_code == 400, f"Resend draft should return 400, got: {response.status_code}"
        data = response.json()
        assert "detail" in data, "Error response should have 'detail'"
        print(f"PASS: Resend draft campaign correctly returned 400 - {data.get('detail')}")
    
    # ========== DELETE /api/admin/marketing/campaigns/{id} ==========
    def test_delete_campaign(self, auth_headers):
        """Test deleting a campaign"""
        # Create a campaign to delete
        campaign_data = {
            "name": f"TEST_ToDelete_{uuid.uuid4().hex[:8]}",
            "subject": "Delete Test",
            "html_content": "<html><body>Delete me</body></html>",
            "audience_filters": {}
        }
        create_response = requests.post(f"{BASE_URL}/api/admin/marketing/campaigns", 
                                        json=campaign_data, headers=auth_headers)
        assert create_response.status_code == 200, f"Create campaign failed: {create_response.text}"
        campaign_id = create_response.json()["id"]
        
        # Delete the campaign
        delete_response = requests.delete(f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}", 
                                          headers=auth_headers)
        assert delete_response.status_code == 200, f"Delete campaign failed: {delete_response.text}"
        data = delete_response.json()
        assert data.get("success") == True, f"Delete should return success=True, got: {data}"
        print(f"PASS: Deleted campaign {campaign_id}")
        
        # Verify campaign is deleted
        get_response = requests.get(f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}", 
                                    headers=auth_headers)
        assert get_response.status_code == 404, f"Deleted campaign should return 404, got: {get_response.status_code}"
        print("PASS: Verified campaign no longer exists")
    
    def test_delete_nonexistent_campaign(self, auth_headers):
        """Test deleting a non-existent campaign returns 404"""
        fake_id = f"nonexistent-{uuid.uuid4().hex}"
        response = requests.delete(f"{BASE_URL}/api/admin/marketing/campaigns/{fake_id}", 
                                   headers=auth_headers)
        assert response.status_code == 404, f"Delete nonexistent should return 404, got: {response.status_code}"
        print("PASS: Delete nonexistent campaign correctly returned 404")
    
    # ========== Cleanup ==========
    def test_cleanup_test_campaign(self, auth_headers, test_campaign):
        """Cleanup: delete the test campaign"""
        campaign_id = test_campaign["id"]
        response = requests.delete(f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}", 
                                   headers=auth_headers)
        # May already be deleted, so accept 200 or 404
        assert response.status_code in [200, 404], f"Cleanup failed: {response.text}"
        print(f"PASS: Cleaned up test campaign {campaign_id}")


class TestAIChatbot:
    """Test suite for AI Chatbot endpoint"""
    
    def test_ai_chat_message_anonymous(self):
        """Test AI chat endpoint without authentication (anonymous user)"""
        response = requests.post(f"{BASE_URL}/api/ai-chat/message", json={
            "message": "Hello, what is BidVex?",
            "language": "en"
        })
        assert response.status_code == 200, f"AI chat failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data, "Response should have 'success' field"
        assert "message" in data, "Response should have 'message' field"
        assert "language" in data, "Response should have 'language' field"
        
        # Check success
        assert data["success"] == True, f"AI chat should return success=True, got: {data}"
        assert len(data["message"]) > 0, "AI response message should not be empty"
        print(f"PASS: AI chat responded successfully - message length: {len(data['message'])} chars")
    
    def test_ai_chat_message_authenticated(self):
        """Test AI chat endpoint with authentication"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("access_token") or login_response.json().get("token")
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{BASE_URL}/api/ai-chat/message", json={
            "message": "What are the subscription tiers?",
            "language": "en"
        }, headers=headers)
        
        assert response.status_code == 200, f"AI chat failed: {response.text}"
        data = response.json()
        assert data["success"] == True, f"AI chat should return success=True, got: {data}"
        print(f"PASS: Authenticated AI chat responded successfully")
    
    def test_ai_chat_french_language(self):
        """Test AI chat with French language"""
        response = requests.post(f"{BASE_URL}/api/ai-chat/message", json={
            "message": "Bonjour, comment fonctionne BidVex?",
            "language": "fr"
        })
        assert response.status_code == 200, f"AI chat failed: {response.text}"
        data = response.json()
        assert data["success"] == True, f"AI chat should return success=True"
        # Language should be detected or set to French
        print(f"PASS: French AI chat responded - language: {data.get('language')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
