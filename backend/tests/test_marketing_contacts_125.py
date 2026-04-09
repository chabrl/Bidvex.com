"""
Test suite for User Marketing Contacts API endpoints
Tests the fix for 500 Internal Server Error on POST /api/user/marketing/contacts
Verifies Pydantic models: UserContactCreateRequest, UserContactBulkRequest, UserCampaignCreateRequest
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Admin123!"
STARTER_EMAIL = "starter@test.com"
STARTER_PASSWORD = "TestUser2026!"

# Test data prefix for cleanup
TEST_PREFIX = f"TEST_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def starter_token():
    """Get starter user auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": STARTER_EMAIL,
        "password": STARTER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Starter login failed: {response.status_code} - {response.text}")


@pytest.fixture
def admin_headers(admin_token):
    """Headers with admin auth"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def starter_headers(starter_token):
    """Headers with starter user auth"""
    return {
        "Authorization": f"Bearer {starter_token}",
        "Content-Type": "application/json"
    }


class TestMarketingAccess:
    """Test /api/user/marketing/access endpoint"""
    
    def test_access_returns_200(self, admin_headers):
        """GET /api/user/marketing/access should return 200"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/access", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_access_returns_correct_structure(self, admin_headers):
        """Access endpoint should return subscription details"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/access", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "can_access" in data
        assert "can_send" in data
        assert "subscription_tier" in data
        assert "limits" in data
        assert "quota" in data
        assert "contact_limit" in data
    
    def test_access_no_auth_returns_401(self):
        """Access endpoint without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/access")
        assert response.status_code == 401


class TestAddSingleContact:
    """Test POST /api/user/marketing/contacts - add single contact"""
    
    def test_add_contact_success(self, admin_headers):
        """Add single contact with email, name, consent_confirmed should return 200"""
        test_email = f"{TEST_PREFIX}_single@test.com"
        payload = {
            "email": test_email,
            "name": "Test Contact",
            "consent_confirmed": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["email"] == test_email.lower()
        assert data["name"] == "Test Contact"
        assert data["consent_confirmed"] == True
        assert data["status"] == "active"
    
    def test_add_contact_minimal_fields(self, admin_headers):
        """Add contact with only email (minimal required field)"""
        test_email = f"{TEST_PREFIX}_minimal@test.com"
        payload = {
            "email": test_email
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["email"] == test_email.lower()
        assert data["consent_confirmed"] == False  # Default value
    
    def test_add_contact_with_tags(self, admin_headers):
        """Add contact with tags"""
        test_email = f"{TEST_PREFIX}_tags@test.com"
        payload = {
            "email": test_email,
            "name": "Tagged Contact",
            "tags": ["vip", "auction-buyer"],
            "consent_confirmed": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["tags"] == ["vip", "auction-buyer"]
    
    def test_add_duplicate_contact_returns_400(self, admin_headers):
        """Adding duplicate email should return 400"""
        test_email = f"{TEST_PREFIX}_dup@test.com"
        payload = {"email": test_email, "consent_confirmed": True}
        
        # First add
        response1 = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json=payload
        )
        assert response1.status_code == 200
        
        # Duplicate add
        response2 = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json=payload
        )
        assert response2.status_code == 400, f"Expected 400 for duplicate, got {response2.status_code}"
        assert "already exists" in response2.json().get("detail", "").lower()
    
    def test_add_invalid_email_returns_error(self, admin_headers):
        """Invalid email format should return 400 or 422"""
        payload = {
            "email": "not-an-email",
            "consent_confirmed": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json=payload
        )
        
        # Pydantic validation returns 422, service validation returns 400
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
    
    def test_add_contact_no_auth_returns_401(self):
        """Adding contact without auth should return 401"""
        payload = {"email": "noauth@test.com", "consent_confirmed": True}
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            json=payload
        )
        assert response.status_code == 401


class TestBulkAddContacts:
    """Test POST /api/user/marketing/contacts/bulk - add multiple contacts"""
    
    def test_bulk_add_success(self, admin_headers):
        """Bulk add contacts with emails array and consent_confirmed"""
        emails = [
            f"{TEST_PREFIX}_bulk1@test.com",
            f"{TEST_PREFIX}_bulk2@test.com",
            f"{TEST_PREFIX}_bulk3@test.com"
        ]
        payload = {
            "emails": emails,
            "consent_confirmed": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts/bulk",
            headers=admin_headers,
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "added" in data
        assert "added_count" in data
        assert "duplicates" in data
        assert "invalid" in data
        assert data["added_count"] == 3
    
    def test_bulk_add_detects_duplicates(self, admin_headers):
        """Bulk add should detect duplicates within the batch and existing contacts"""
        # First add a contact
        first_email = f"{TEST_PREFIX}_bulkdup1@test.com"
        requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json={"email": first_email, "consent_confirmed": True}
        )
        
        # Now bulk add including the duplicate
        emails = [
            first_email,  # Already exists
            f"{TEST_PREFIX}_bulkdup2@test.com",  # New
        ]
        payload = {
            "emails": emails,
            "consent_confirmed": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts/bulk",
            headers=admin_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["duplicates_count"] >= 1
        assert data["added_count"] == 1
    
    def test_bulk_add_handles_invalid_emails(self, admin_headers):
        """Bulk add should report invalid emails"""
        emails = [
            f"{TEST_PREFIX}_bulkvalid@test.com",
            "invalid-email-format",
            "another-bad-one"
        ]
        payload = {
            "emails": emails,
            "consent_confirmed": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts/bulk",
            headers=admin_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["invalid_count"] == 2
        assert data["added_count"] == 1
    
    def test_bulk_add_empty_list(self, admin_headers):
        """Bulk add with empty list should return success with 0 added"""
        payload = {
            "emails": [],
            "consent_confirmed": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts/bulk",
            headers=admin_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] == 0


class TestGetContacts:
    """Test GET /api/user/marketing/contacts - list contacts"""
    
    def test_get_contacts_returns_200(self, admin_headers):
        """GET contacts should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers
        )
        assert response.status_code == 200
    
    def test_get_contacts_returns_correct_structure(self, admin_headers):
        """GET contacts should return contacts array with total count"""
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "contacts" in data
        assert "total" in data
        assert isinstance(data["contacts"], list)
    
    def test_get_contacts_with_search(self, admin_headers):
        """GET contacts with search parameter"""
        # First add a contact with unique name
        unique_name = f"SearchTest_{TEST_PREFIX}"
        requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json={"email": f"{TEST_PREFIX}_search@test.com", "name": unique_name, "consent_confirmed": True}
        )
        
        # Search for it
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            params={"search": unique_name}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should find at least the one we added
        assert data["total"] >= 1


class TestGetContactStats:
    """Test GET /api/user/marketing/contacts/stats"""
    
    def test_stats_returns_200(self, admin_headers):
        """GET stats should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/contacts/stats",
            headers=admin_headers
        )
        assert response.status_code == 200
    
    def test_stats_returns_correct_structure(self, admin_headers):
        """Stats should return total, active counts"""
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/contacts/stats",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "active" in data
        assert "contact_limit" in data


class TestDeleteContact:
    """Test DELETE /api/user/marketing/contacts/{contact_id}"""
    
    def test_delete_contact_success(self, admin_headers):
        """Delete contact should return success"""
        # First create a contact
        test_email = f"{TEST_PREFIX}_delete@test.com"
        create_response = requests.post(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            json={"email": test_email, "consent_confirmed": True}
        )
        assert create_response.status_code == 200
        contact_id = create_response.json()["id"]
        
        # Delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/user/marketing/contacts/{contact_id}",
            headers=admin_headers
        )
        
        assert delete_response.status_code == 200
        assert delete_response.json().get("status") == "deleted"
    
    def test_delete_nonexistent_contact_returns_404(self, admin_headers):
        """Delete non-existent contact should return 404"""
        fake_id = str(uuid.uuid4())
        response = requests.delete(
            f"{BASE_URL}/api/user/marketing/contacts/{fake_id}",
            headers=admin_headers
        )
        # Note: Admin has free tier, so delete requires Premium/VIP
        # This might return 403 instead of 404
        assert response.status_code in [403, 404]


class TestCampaignCreate:
    """Test POST /api/user/marketing/campaigns - campaign creation with new fields"""
    
    def test_campaign_create_with_html_content(self, admin_headers):
        """Campaign create should accept html_content, plain_text_content, auction_id"""
        payload = {
            "name": f"Test Campaign {TEST_PREFIX}",
            "subject": "Test Subject",
            "html_content": "<html><body><h1>Test</h1></body></html>",
            "plain_text_content": "Test plain text",
            "auction_id": "test-auction-123"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/user/marketing/campaigns",
            headers=admin_headers,
            json=payload
        )
        
        # Admin is free tier, so campaign creation requires Premium/VIP
        # Should return 403 for free tier
        assert response.status_code in [200, 403], f"Expected 200 or 403, got {response.status_code}: {response.text}"
        
        if response.status_code == 403:
            # Expected for free tier - verify error message
            assert "upgrade" in response.json().get("detail", "").lower() or "premium" in response.json().get("detail", "").lower()


class TestCleanup:
    """Cleanup test contacts after tests"""
    
    def test_cleanup_test_contacts(self, admin_headers):
        """Clean up all test contacts created during testing"""
        # Get all contacts
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/contacts",
            headers=admin_headers,
            params={"limit": 500}
        )
        
        if response.status_code == 200:
            contacts = response.json().get("contacts", [])
            test_contacts = [c for c in contacts if TEST_PREFIX in c.get("email", "")]
            
            for contact in test_contacts:
                try:
                    requests.delete(
                        f"{BASE_URL}/api/user/marketing/contacts/{contact['id']}",
                        headers=admin_headers
                    )
                except:
                    pass  # Ignore cleanup errors
        
        # This test always passes - it's just for cleanup
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
