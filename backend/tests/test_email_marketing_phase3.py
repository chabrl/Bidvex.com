"""
BidVex Email Marketing Phase 3 Tests
Tests for: dashboard-stats, sync-contacts, segment-filters, campaigns CRUD
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def auth_session():
    """Get authenticated session for admin"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    
    if response.status_code == 200:
        token = response.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        print(f"Auth successful for {ADMIN_EMAIL}")
        return session
    else:
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")


class TestEmailMarketingPhase3:
    """Email Marketing Phase 3 API Tests"""
            
    # ========== Dashboard Stats Tests ==========
    
    def test_dashboard_stats_requires_auth(self):
        """Test dashboard-stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing/dashboard-stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: dashboard-stats requires auth")
        
    def test_dashboard_stats_returns_expected_fields(self, auth_session):
        """Test dashboard-stats returns total_campaigns, total_sent, open_rate, click_rate, recent_campaigns"""
        response = auth_session.get(f"{BASE_URL}/api/admin/marketing/dashboard-stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required fields
        assert "total_campaigns" in data, "Missing total_campaigns"
        assert "total_sent" in data, "Missing total_sent"
        assert "open_rate" in data, "Missing open_rate"
        assert "click_rate" in data, "Missing click_rate"
        assert "recent_campaigns" in data, "Missing recent_campaigns"
        
        # Verify types
        assert isinstance(data["total_campaigns"], int), "total_campaigns should be int"
        assert isinstance(data["total_sent"], int), "total_sent should be int"
        assert isinstance(data["open_rate"], (int, float)), "open_rate should be numeric"
        assert isinstance(data["click_rate"], (int, float)), "click_rate should be numeric"
        assert isinstance(data["recent_campaigns"], list), "recent_campaigns should be list"
        
        print(f"PASS: dashboard-stats returns expected fields: total_campaigns={data['total_campaigns']}, total_sent={data['total_sent']}, open_rate={data['open_rate']}%, click_rate={data['click_rate']}%")
        
    # ========== Sync Contacts Tests ==========
    
    def test_sync_contacts_requires_auth(self):
        """Test sync-contacts endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/admin/marketing/sync-contacts")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: sync-contacts requires auth")
        
    def test_sync_contacts_returns_synced_count(self, auth_session):
        """Test sync-contacts returns {synced: N, total_users: N}"""
        response = auth_session.post(f"{BASE_URL}/api/admin/marketing/sync-contacts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "synced" in data, "Missing synced field"
        assert "total_users" in data, "Missing total_users field"
        assert isinstance(data["synced"], int), "synced should be int"
        assert isinstance(data["total_users"], int), "total_users should be int"
        assert data["synced"] >= 0, "synced should be >= 0"
        assert data["total_users"] >= 0, "total_users should be >= 0"
        
        print(f"PASS: sync-contacts returns synced={data['synced']}, total_users={data['total_users']}")
        
    # ========== Segment Filters Tests ==========
    
    def test_segment_filters_requires_auth(self):
        """Test segment-filters endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing/segment-filters")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: segment-filters requires auth")
        
    def test_segment_filters_includes_user_role(self, auth_session):
        """Test segment-filters returns filters including user_role with buyers/sellers/partners"""
        response = auth_session.get(f"{BASE_URL}/api/admin/marketing/segment-filters")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "filters" in data, "Missing filters field"
        filters = data["filters"]
        
        # Check user_role exists
        assert "user_role" in filters, "Missing user_role in filters"
        user_roles = filters["user_role"]
        
        # Verify buyers, sellers, partners are present
        assert "buyers" in user_roles, "Missing 'buyers' in user_role"
        assert "sellers" in user_roles, "Missing 'sellers' in user_role"
        assert "partners" in user_roles, "Missing 'partners' in user_role"
        
        print(f"PASS: segment-filters includes user_role with {user_roles}")
        
    def test_segment_filters_includes_other_filters(self, auth_session):
        """Test segment-filters returns other expected filter types"""
        response = auth_session.get(f"{BASE_URL}/api/admin/marketing/segment-filters")
        assert response.status_code == 200
        
        data = response.json()
        filters = data["filters"]
        
        # Check other expected filters
        expected_filters = ["subscription_tier", "account_type", "region", "activity_status"]
        for f in expected_filters:
            assert f in filters, f"Missing {f} in filters"
            
        print(f"PASS: segment-filters includes all expected filter types: {list(filters.keys())}")
        
    # ========== Campaigns List Tests ==========
    
    def test_campaigns_list_requires_auth(self):
        """Test campaigns list endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing/campaigns")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: campaigns list requires auth")
        
    def test_campaigns_list_returns_campaigns_and_count(self, auth_session):
        """Test campaigns list returns campaigns array and count"""
        response = auth_session.get(f"{BASE_URL}/api/admin/marketing/campaigns")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "campaigns" in data, "Missing campaigns field"
        assert "count" in data, "Missing count field"
        assert isinstance(data["campaigns"], list), "campaigns should be list"
        assert isinstance(data["count"], int), "count should be int"
        
        print(f"PASS: campaigns list returns {data['count']} campaigns")
        
    # ========== Campaign Create Tests ==========
    
    def test_campaign_create_requires_auth(self):
        """Test campaign create endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/admin/marketing/campaigns", json={
            "name": "Test Campaign",
            "subject": "Test Subject",
            "html_content": "<p>Test</p>",
            "audience_filters": {}
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: campaign create requires auth")
        
    def test_campaign_create_success(self, auth_session):
        """Test creating a new campaign"""
        campaign_data = {
            "name": "TEST_Phase3_Campaign",
            "subject": "Test Subject for Phase 3",
            "html_content": "<html><body><p>Hello {{name}}</p></body></html>",
            "plain_text_content": "Hello {{name}}",
            "audience_filters": {
                "subscription_tiers": ["free"],
                "exclude_unsubscribed": True
            }
        }
        
        response = auth_session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Missing campaign id"
        assert data["name"] == campaign_data["name"], "Name mismatch"
        assert data["subject"] == campaign_data["subject"], "Subject mismatch"
        assert data["status"] == "draft", f"Expected draft status, got {data['status']}"
        
        print(f"PASS: Campaign created with id={data['id']}, status={data['status']}")
        
        # Cleanup - delete the test campaign
        delete_response = auth_session.delete(f"{BASE_URL}/api/admin/marketing/campaigns/{data['id']}")
        if delete_response.status_code in [200, 204]:
            print(f"CLEANUP: Deleted test campaign {data['id']}")
            
    def test_campaign_create_with_user_role_filter(self, auth_session):
        """Test creating a campaign with user_role segment filter"""
        campaign_data = {
            "name": "TEST_UserRole_Campaign",
            "subject": "Test for Buyers",
            "html_content": "<html><body><p>Hello Buyer {{name}}</p></body></html>",
            "plain_text_content": "Hello Buyer {{name}}",
            "audience_filters": {
                "user_role": "buyers",
                "exclude_unsubscribed": True
            }
        }
        
        response = auth_session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Missing campaign id"
        assert data["audience_filters"].get("user_role") == "buyers", "user_role filter not saved"
        
        print(f"PASS: Campaign with user_role=buyers created, id={data['id']}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/admin/marketing/campaigns/{data['id']}")


class TestCommunityQA:
    """Community Q&A API Tests"""
        
    def test_community_questions_list(self):
        """Test GET /api/community/questions returns questions"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.get(f"{BASE_URL}/api/community/questions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "questions" in data, "Missing questions field"
        assert isinstance(data["questions"], list), "questions should be list"
        
        print(f"PASS: Community questions list returns {len(data['questions'])} questions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
