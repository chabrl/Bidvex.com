"""
Test suite for Client Email Marketing feature (User-level marketing)
This module tests user-level email marketing functionality for Premium/VIP users.
Key Features:
- Contact management (CRUD)
- Campaign creation/management
- Subscription-based limits (Free: 50 contacts, Premium: 5000, VIP: 25000)
- Rate limits (Premium: 500/day, 5000/month; VIP: 2000/day, 50000/month)
- Pre-built templates
"""

import pytest
import requests
import os
import time
from datetime import datetime

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials - VIP user
VIP_USER_EMAIL = "charbeladmin@bidvex.com"
VIP_USER_PASSWORD = "Admin123!"

class TestClientEmailMarketing:
    """Test suite for Client Email Marketing API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token for VIP user"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": VIP_USER_EMAIL,
            "password": VIP_USER_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        data = login_response.json()
        self.token = data.get("access_token")
        self.user = data.get("user")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Store test contact IDs for cleanup
        self.created_contact_ids = []
        self.created_campaign_ids = []
        
        yield
        
        # Cleanup: Delete test contacts after tests
        for contact_id in self.created_contact_ids:
            try:
                requests.delete(f"{BASE_URL}/api/user/marketing/contacts/{contact_id}", headers=self.headers)
            except:
                pass
    
    # ========== ACCESS & LIMITS TESTS ==========
    
    def test_marketing_access_vip_user(self):
        """Test GET /api/user/marketing/access returns correct limits for VIP user"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/access", headers=self.headers)
        
        assert response.status_code == 200, f"Access check failed: {response.text}"
        data = response.json()
        
        # Verify access structure
        assert "can_access" in data
        assert "can_send" in data
        assert "subscription_tier" in data
        assert "limits" in data
        assert "quota" in data
        
        # VIP user should have full access
        assert data["can_access"] == True
        assert data["can_send"] == True
        assert data["subscription_tier"] == "vip"
        
        # Verify VIP limits
        limits = data["limits"]
        assert limits["daily"] == 2000, f"Expected daily_limit=2000, got {limits.get('daily')}"
        assert limits["monthly"] == 50000, f"Expected monthly_limit=50000, got {limits.get('monthly')}"
        assert limits["contacts"] == 25000, f"Expected contact_limit=25000, got {limits.get('contacts')}"
        
        # Verify quota structure
        quota = data["quota"]
        assert "daily_limit" in quota
        assert "monthly_limit" in quota
        assert "contact_limit" in quota
        assert quota["daily_limit"] == 2000
        assert quota["monthly_limit"] == 50000
        assert quota["contact_limit"] == 25000
        
        print(f"✅ VIP access check passed - limits: daily={limits['daily']}, monthly={limits['monthly']}, contacts={limits['contacts']}")
    
    def test_subscription_limits_structure(self):
        """Test that subscription limits are correctly returned"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/access", headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify complete structure
        assert "limits" in data
        limits = data["limits"]
        
        # VIP limits per the requirements
        assert limits == {
            "daily": 2000,
            "monthly": 50000,
            "contacts": 25000
        }
        
        print(f"✅ Subscription limits verified: {limits}")
    
    # ========== TEMPLATES TESTS ==========
    
    def test_get_templates_returns_5_templates(self):
        """Test GET /api/user/marketing/templates returns 5 pre-built templates"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/templates", headers=self.headers)
        
        assert response.status_code == 200, f"Templates fetch failed: {response.text}"
        data = response.json()
        
        assert "templates" in data
        templates = data["templates"]
        
        # Verify we have 5 templates
        assert len(templates) == 5, f"Expected 5 templates, got {len(templates)}"
        
        # Verify template keys
        expected_keys = ["new_auction", "ending_soon", "new_inventory", "vip_preview", "price_drop"]
        for key in expected_keys:
            assert key in templates, f"Missing template: {key}"
            template = templates[key]
            assert "name" in template
            assert "subject" in template
            assert "description" in template
            assert "html_content" in template
        
        # Verify template names
        assert templates["new_auction"]["name"] == "New Auction Announcement"
        assert templates["ending_soon"]["name"] == "Ending Soon Reminder"
        assert templates["new_inventory"]["name"] == "New Inventory Alert"
        assert templates["vip_preview"]["name"] == "Exclusive VIP Preview"
        assert templates["price_drop"]["name"] == "Price Drop Alert"
        
        print(f"✅ Templates test passed - found {len(templates)} templates: {list(templates.keys())}")
    
    # ========== CONTACT MANAGEMENT TESTS ==========
    
    def test_add_contact_with_consent(self):
        """Test POST /api/user/marketing/contacts - add a contact with consent_confirmed"""
        test_email = f"TEST_contact_{int(time.time())}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/user/marketing/contacts", 
            headers=self.headers,
            json={
                "email": test_email,
                "name": "Test Contact",
                "consent_confirmed": True
            }
        )
        
        assert response.status_code == 200, f"Add contact failed: {response.text}"
        data = response.json()
        
        # Verify contact structure
        assert "id" in data
        assert data["email"] == test_email.lower()  # Backend normalizes to lowercase
        assert data["name"] == "Test Contact"
        assert data["consent_confirmed"] == True
        assert data["status"] == "active"
        
        # Store for cleanup
        self.created_contact_ids.append(data["id"])
        
        print(f"✅ Contact added successfully: {data['email']} (ID: {data['id']})")
    
    def test_list_contacts(self):
        """Test GET /api/user/marketing/contacts - list contacts"""
        # First add a test contact
        test_email = f"TEST_list_{int(time.time())}@example.com"
        add_response = requests.post(f"{BASE_URL}/api/user/marketing/contacts", 
            headers=self.headers,
            json={
                "email": test_email,
                "name": "List Test Contact",
                "consent_confirmed": True
            }
        )
        assert add_response.status_code == 200
        contact_id = add_response.json()["id"]
        self.created_contact_ids.append(contact_id)
        
        # Now list contacts
        response = requests.get(f"{BASE_URL}/api/user/marketing/contacts", headers=self.headers)
        
        assert response.status_code == 200, f"List contacts failed: {response.text}"
        data = response.json()
        
        assert "contacts" in data
        assert "total" in data
        assert isinstance(data["contacts"], list)
        assert data["total"] >= 1
        
        # Verify the contact we added is in the list (lowercase normalized)
        contact_emails = [c["email"] for c in data["contacts"]]
        assert test_email.lower() in contact_emails, f"Added contact not found in list"
        
        print(f"✅ List contacts passed - total: {data['total']}")
    
    def test_get_contact_stats(self):
        """Test GET /api/user/marketing/contacts/stats - get contact statistics"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/contacts/stats", headers=self.headers)
        
        assert response.status_code == 200, f"Contact stats failed: {response.text}"
        data = response.json()
        
        # Verify stats structure
        assert "total" in data
        assert "active" in data
        assert "unsubscribed" in data
        assert "bounced" in data
        assert "contact_limit" in data
        
        # Verify contact_limit has proper structure
        contact_limit = data["contact_limit"]
        assert "limit" in contact_limit
        assert "current" in contact_limit
        assert "remaining" in contact_limit
        assert "can_add" in contact_limit
        
        print(f"✅ Contact stats passed - total: {data['total']}, active: {data['active']}")
    
    def test_delete_contact(self):
        """Test DELETE /api/user/marketing/contacts/{contact_id}"""
        # First add a test contact
        test_email = f"TEST_delete_{int(time.time())}@example.com"
        add_response = requests.post(f"{BASE_URL}/api/user/marketing/contacts", 
            headers=self.headers,
            json={
                "email": test_email,
                "consent_confirmed": True
            }
        )
        assert add_response.status_code == 200
        contact_id = add_response.json()["id"]
        
        # Delete the contact
        delete_response = requests.delete(
            f"{BASE_URL}/api/user/marketing/contacts/{contact_id}", 
            headers=self.headers
        )
        
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        # Verify contact is deleted
        get_response = requests.get(
            f"{BASE_URL}/api/user/marketing/contacts/{contact_id}",
            headers=self.headers
        )
        assert get_response.status_code == 404
        
        print(f"✅ Contact deleted successfully: {contact_id}")
    
    def test_bulk_add_contacts(self):
        """Test POST /api/user/marketing/contacts/bulk - add multiple contacts"""
        test_emails = [
            f"TEST_bulk1_{int(time.time())}@example.com",
            f"TEST_bulk2_{int(time.time())}@example.com",
            f"TEST_bulk3_{int(time.time())}@example.com"
        ]
        
        response = requests.post(f"{BASE_URL}/api/user/marketing/contacts/bulk",
            headers=self.headers,
            json={
                "emails": test_emails,
                "consent_confirmed": True
            }
        )
        
        assert response.status_code == 200, f"Bulk add failed: {response.text}"
        data = response.json()
        
        assert "added_count" in data
        assert "duplicates_count" in data
        assert "invalid_count" in data
        assert data["added_count"] == 3
        
        # Get the added contacts for cleanup
        list_response = requests.get(f"{BASE_URL}/api/user/marketing/contacts?limit=10", headers=self.headers)
        contacts = list_response.json().get("contacts", [])
        for contact in contacts:
            if contact["email"] in test_emails:
                self.created_contact_ids.append(contact["id"])
        
        print(f"✅ Bulk add passed - added: {data['added_count']}")
    
    # ========== CAMPAIGN MANAGEMENT TESTS ==========
    
    def test_create_campaign(self):
        """Test POST /api/user/marketing/campaigns - create a campaign"""
        campaign_name = f"TEST_Campaign_{int(time.time())}"
        
        response = requests.post(f"{BASE_URL}/api/user/marketing/campaigns",
            headers=self.headers,
            json={
                "name": campaign_name,
                "subject": "Test Subject Line",
                "html_content": "<html><body><p>Test content</p></body></html>",
                "plain_text_content": "Test content"
            }
        )
        
        assert response.status_code == 200, f"Create campaign failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name"] == campaign_name
        assert data["subject"] == "Test Subject Line"
        assert data["status"] == "draft"
        assert "html_content" in data
        
        self.created_campaign_ids.append(data["id"])
        
        print(f"✅ Campaign created: {data['name']} (ID: {data['id']})")
    
    def test_list_campaigns(self):
        """Test GET /api/user/marketing/campaigns - list campaigns"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/campaigns", headers=self.headers)
        
        assert response.status_code == 200, f"List campaigns failed: {response.text}"
        data = response.json()
        
        assert "campaigns" in data
        assert "total" in data
        assert isinstance(data["campaigns"], list)
        
        print(f"✅ List campaigns passed - total: {data['total']}")
    
    def test_get_single_campaign(self):
        """Test GET /api/user/marketing/campaigns/{campaign_id}"""
        # First create a campaign
        campaign_name = f"TEST_SingleGet_{int(time.time())}"
        create_response = requests.post(f"{BASE_URL}/api/user/marketing/campaigns",
            headers=self.headers,
            json={
                "name": campaign_name,
                "subject": "Test Subject",
                "html_content": "<p>Test</p>"
            }
        )
        assert create_response.status_code == 200
        campaign_id = create_response.json()["id"]
        self.created_campaign_ids.append(campaign_id)
        
        # Get the campaign
        response = requests.get(
            f"{BASE_URL}/api/user/marketing/campaigns/{campaign_id}",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Get campaign failed: {response.text}"
        data = response.json()
        
        assert data["id"] == campaign_id
        assert data["name"] == campaign_name
        
        print(f"✅ Get single campaign passed: {data['name']}")
    
    def test_update_campaign(self):
        """Test PUT /api/user/marketing/campaigns/{campaign_id}"""
        # First create a campaign
        create_response = requests.post(f"{BASE_URL}/api/user/marketing/campaigns",
            headers=self.headers,
            json={
                "name": f"TEST_Update_{int(time.time())}",
                "subject": "Original Subject",
                "html_content": "<p>Original</p>"
            }
        )
        assert create_response.status_code == 200
        campaign_id = create_response.json()["id"]
        self.created_campaign_ids.append(campaign_id)
        
        # Update the campaign
        response = requests.put(
            f"{BASE_URL}/api/user/marketing/campaigns/{campaign_id}",
            headers=self.headers,
            json={
                "subject": "Updated Subject",
                "html_content": "<p>Updated content</p>"
            }
        )
        
        assert response.status_code == 200, f"Update campaign failed: {response.text}"
        data = response.json()
        
        assert data["subject"] == "Updated Subject"
        assert "Updated content" in data["html_content"]
        
        print(f"✅ Update campaign passed")


class TestClientMarketingQuotas:
    """Test suite for quota and limit enforcement"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": VIP_USER_EMAIL,
            "password": VIP_USER_PASSWORD
        })
        assert login_response.status_code == 200
        
        data = login_response.json()
        self.token = data.get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_quota_structure(self):
        """Test that quota structure is complete for VIP user"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/access", headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        
        quota = data["quota"]
        
        # Verify all quota fields
        assert "daily_limit" in quota
        assert "daily_used" in quota
        assert "daily_remaining" in quota
        assert "monthly_limit" in quota
        assert "monthly_used" in quota
        assert "monthly_remaining" in quota
        assert "contact_limit" in quota
        assert "can_send" in quota
        assert "tier" in quota
        
        # VIP values
        assert quota["daily_limit"] == 2000
        assert quota["monthly_limit"] == 50000
        assert quota["contact_limit"] == 25000
        assert quota["tier"] == "vip"
        
        print(f"✅ Quota structure verified: daily_remaining={quota['daily_remaining']}, monthly_remaining={quota['monthly_remaining']}")
    
    def test_contact_limit_check(self):
        """Test that contact limit is returned correctly"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/access", headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        
        contact_limit = data["contact_limit"]
        
        assert "limit" in contact_limit
        assert "current" in contact_limit
        assert "remaining" in contact_limit
        assert "can_add" in contact_limit
        
        # VIP should have 25000 contact limit
        assert contact_limit["limit"] == 25000
        
        print(f"✅ Contact limit check passed: {contact_limit['current']}/{contact_limit['limit']}")


class TestTemplateDetails:
    """Test template content and structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": VIP_USER_EMAIL,
            "password": VIP_USER_PASSWORD
        })
        assert login_response.status_code == 200
        
        data = login_response.json()
        self.token = data.get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_template_subjects(self):
        """Verify template subjects match requirements"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/templates", headers=self.headers)
        
        assert response.status_code == 200
        templates = response.json()["templates"]
        
        expected_subjects = {
            "new_auction": "New Auction: {{auction_title}}",
            "ending_soon": "Ending Soon: {{auction_title}} - Don't Miss Out!",
            "new_inventory": "Fresh Inventory Just Listed!",
            "vip_preview": "VIP Preview: Early Access to Upcoming Auction",
            "price_drop": "Price Drop Alert: {{auction_title}}"
        }
        
        for key, expected_subject in expected_subjects.items():
            assert templates[key]["subject"] == expected_subject, f"Template {key} subject mismatch"
        
        print(f"✅ All template subjects verified")
    
    def test_templates_have_unsubscribe_link(self):
        """Verify all templates include unsubscribe link placeholder"""
        response = requests.get(f"{BASE_URL}/api/user/marketing/templates", headers=self.headers)
        
        assert response.status_code == 200
        templates = response.json()["templates"]
        
        for key, template in templates.items():
            html_content = template["html_content"]
            assert "{{unsubscribe_url}}" in html_content or "unsubscribe_url" in html_content, \
                f"Template {key} missing unsubscribe link"
        
        print(f"✅ All templates have unsubscribe link placeholder")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
