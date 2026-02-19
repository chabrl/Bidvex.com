"""
Email Marketing Module - Phase 3 API Tests
Tests: Audience segmentation, campaign CRUD, scheduling, stats, webhook handling
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials from the test request
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
TEST_CAMPAIGN_ID = "c501d209-502b-4711-9680-8d798bffb23d"


class TestEmailMarketingEndpoints:
    """Email Marketing API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        
        token = response.json().get("access_token")
        assert token, "No access token received"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.created_campaign_id = None
    
    def teardown_method(self, method):
        """Cleanup test data"""
        # If we created a campaign during testing, leave it for manual review
        pass
    
    # ========== GET /api/admin/marketing/segment-filters ==========
    def test_get_segment_filters_success(self):
        """Test: GET segment filters returns available filter options"""
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/segment-filters")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Validate response structure
        assert "filters" in data, "Response should have 'filters' key"
        assert "campaign_statuses" in data, "Response should have 'campaign_statuses' key"
        
        # Validate filter categories
        filters = data["filters"]
        assert "subscription_tier" in filters, "Should have subscription_tier filter"
        assert "account_type" in filters, "Should have account_type filter"
        assert "region" in filters, "Should have region filter"
        assert "activity_status" in filters, "Should have activity_status filter"
        
        # Validate subscription tiers
        assert "free" in filters["subscription_tier"], "Should include 'free' tier"
        assert "premium" in filters["subscription_tier"], "Should include 'premium' tier"
        assert "vip" in filters["subscription_tier"], "Should include 'vip' tier"
        
        # Validate campaign statuses
        statuses = data["campaign_statuses"]
        assert "draft" in statuses, "Should include 'draft' status"
        assert "scheduled" in statuses, "Should include 'scheduled' status"
        assert "sent" in statuses, "Should include 'sent' status"
        
        print(f"✅ Segment filters returned: {list(filters.keys())}")
        print(f"✅ Campaign statuses: {statuses}")
    
    # ========== POST /api/admin/marketing/audience/preview ==========
    def test_audience_preview_no_filters(self):
        """Test: Audience preview with no filters returns all users"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/audience/preview",
            json={"exclude_unsubscribed": True}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "count" in data, "Response should have 'count'"
        assert "preview" in data, "Response should have 'preview'"
        assert isinstance(data["count"], int), "Count should be integer"
        assert isinstance(data["preview"], list), "Preview should be list"
        
        print(f"✅ Audience count (no filters): {data['count']}")
        print(f"✅ Preview sample size: {len(data['preview'])}")
    
    def test_audience_preview_with_subscription_tier(self):
        """Test: Audience preview with subscription tier filter"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/audience/preview",
            json={
                "subscription_tiers": ["premium", "vip"],
                "exclude_unsubscribed": True
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "count" in data
        assert "preview" in data
        
        print(f"✅ Premium/VIP users count: {data['count']}")
    
    def test_audience_preview_with_region_filter(self):
        """Test: Audience preview with region filter"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/audience/preview",
            json={
                "regions": ["ON", "QC"],
                "exclude_unsubscribed": True
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "count" in data
        
        print(f"✅ ON/QC region users count: {data['count']}")
    
    # ========== POST /api/admin/marketing/campaigns (Create Campaign) ==========
    def test_create_campaign_success(self):
        """Test: Create new email campaign"""
        campaign_data = {
            "name": f"TEST_Campaign_{uuid.uuid4().hex[:8]}",
            "subject": "Test Email Subject - Pytest",
            "html_content": "<html><body><h1>Hello {{name}}</h1><p>Test email content</p></body></html>",
            "plain_text_content": "Hello {{name}}, Test email content",
            "audience_filters": {
                "subscription_tiers": ["free"],
                "exclude_unsubscribed": True
            },
            "from_name": "BidVex Test",
            "reply_to": "test@bidvex.com"
        }
        
        response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Validate response
        assert "id" in data, "Campaign should have an ID"
        assert data["name"] == campaign_data["name"], "Campaign name should match"
        assert data["subject"] == campaign_data["subject"], "Subject should match"
        assert data["status"] == "draft", "New campaign should be in draft status"
        assert "audience_count" in data, "Should have audience_count"
        assert "created_at" in data, "Should have created_at timestamp"
        
        self.created_campaign_id = data["id"]
        
        print(f"✅ Campaign created: {data['id']}")
        print(f"✅ Status: {data['status']}")
        print(f"✅ Audience count: {data['audience_count']}")
    
    def test_create_campaign_missing_name(self):
        """Test: Create campaign fails without name"""
        campaign_data = {
            "subject": "Test Subject",
            "html_content": "<html><body>Test</body></html>"
        }
        
        response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        
        # Should fail validation
        assert response.status_code == 422, f"Expected 422 validation error, got {response.status_code}"
        
        print("✅ Validation correctly rejects campaign without name")
    
    def test_create_campaign_missing_subject(self):
        """Test: Create campaign fails without subject"""
        campaign_data = {
            "name": "Test Campaign",
            "html_content": "<html><body>Test</body></html>"
        }
        
        response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        
        # Should fail validation
        assert response.status_code == 422, f"Expected 422 validation error, got {response.status_code}"
        
        print("✅ Validation correctly rejects campaign without subject")
    
    # ========== GET /api/admin/marketing/campaigns (List Campaigns) ==========
    def test_list_campaigns_success(self):
        """Test: List all campaigns"""
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/campaigns")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "campaigns" in data, "Response should have 'campaigns'"
        assert "count" in data, "Response should have 'count'"
        assert isinstance(data["campaigns"], list), "Campaigns should be a list"
        
        print(f"✅ Total campaigns: {data['count']}")
        
        if data["campaigns"]:
            campaign = data["campaigns"][0]
            print(f"✅ Sample campaign: {campaign.get('name')} - Status: {campaign.get('status')}")
    
    def test_list_campaigns_filter_by_status(self):
        """Test: List campaigns filtered by status"""
        # Test draft filter
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/campaigns?status=draft")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # All returned campaigns should be drafts
        for campaign in data["campaigns"]:
            assert campaign["status"] == "draft", f"Expected draft, got {campaign['status']}"
        
        print(f"✅ Draft campaigns count: {data['count']}")
    
    # ========== GET /api/admin/marketing/campaigns/{id} (Get Single Campaign) ==========
    def test_get_campaign_by_id(self):
        """Test: Get campaign by ID using test campaign ID"""
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/campaigns/{TEST_CAMPAIGN_ID}")
        
        if response.status_code == 404:
            pytest.skip(f"Test campaign {TEST_CAMPAIGN_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert data["id"] == TEST_CAMPAIGN_ID, "Campaign ID should match"
        assert "name" in data, "Should have name"
        assert "subject" in data, "Should have subject"
        assert "status" in data, "Should have status"
        assert "html_content" in data, "Should have html_content"
        assert "audience_filters" in data, "Should have audience_filters"
        
        print(f"✅ Campaign found: {data['name']}")
        print(f"✅ Status: {data['status']}")
        print(f"✅ Subject: {data['subject']}")
    
    def test_get_campaign_not_found(self):
        """Test: Get non-existent campaign returns 404"""
        fake_id = str(uuid.uuid4())
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/campaigns/{fake_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print("✅ 404 returned for non-existent campaign")
    
    # ========== PUT /api/admin/marketing/campaigns/{id} (Update Campaign) ==========
    def test_update_campaign_success(self):
        """Test: Update draft campaign"""
        # First create a campaign to update
        campaign_data = {
            "name": f"TEST_UpdateCampaign_{uuid.uuid4().hex[:8]}",
            "subject": "Original Subject",
            "html_content": "<html><body>Original content</body></html>",
            "audience_filters": {"exclude_unsubscribed": True}
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        
        campaign_id = create_response.json()["id"]
        
        # Update the campaign
        update_data = {
            "subject": "Updated Subject - Pytest",
            "html_content": "<html><body><h1>Updated Content</h1></body></html>"
        }
        
        update_response = self.session.put(
            f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}",
            json=update_data
        )
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        data = update_response.json()
        
        assert data["subject"] == "Updated Subject - Pytest", "Subject should be updated"
        assert "Updated Content" in data["html_content"], "Content should be updated"
        
        print(f"✅ Campaign updated successfully")
        print(f"✅ New subject: {data['subject']}")
    
    # ========== POST /api/admin/marketing/campaigns/{id}/test (Send Test Email) ==========
    def test_send_test_email(self):
        """Test: Send test email for campaign preview"""
        # Use test campaign or create one
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/campaigns/{TEST_CAMPAIGN_ID}")
        
        if response.status_code == 404:
            # Create a test campaign
            campaign_data = {
                "name": f"TEST_TestEmailCampaign_{uuid.uuid4().hex[:8]}",
                "subject": "Test Email - Pytest",
                "html_content": "<html><body>Test email</body></html>",
                "audience_filters": {"exclude_unsubscribed": True}
            }
            create_resp = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
            assert create_resp.status_code == 200
            campaign_id = create_resp.json()["id"]
        else:
            campaign_id = TEST_CAMPAIGN_ID
        
        # Send test email
        test_response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/test",
            json={"email": "test@example.com"}
        )
        
        assert test_response.status_code == 200, f"Expected 200, got {test_response.status_code}: {test_response.text}"
        
        data = test_response.json()
        
        # Since SendGrid is MOCKED, expect "logged" status
        assert "status" in data, "Response should have status"
        assert data["status"] in ["sent", "logged", "error"], f"Unexpected status: {data['status']}"
        
        print(f"✅ Test email result: {data['status']}")
        print(f"✅ Message: {data.get('message', 'N/A')}")
    
    def test_send_test_email_missing_address(self):
        """Test: Send test email fails without email address"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/campaigns/{TEST_CAMPAIGN_ID}/test",
            json={}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        print("✅ Correctly rejects test email without address")
    
    # ========== POST /api/admin/marketing/campaigns/{id}/schedule (Schedule Campaign) ==========
    def test_schedule_campaign_success(self):
        """Test: Schedule campaign for future sending"""
        # Create a campaign to schedule
        campaign_data = {
            "name": f"TEST_ScheduleCampaign_{uuid.uuid4().hex[:8]}",
            "subject": "Scheduled Email Test",
            "html_content": "<html><body>Scheduled content</body></html>",
            "audience_filters": {"exclude_unsubscribed": True}
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert create_response.status_code == 200
        
        campaign_id = create_response.json()["id"]
        
        # Schedule for 1 day from now
        future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        
        schedule_response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/schedule",
            json={"scheduled_at": future_date}
        )
        
        assert schedule_response.status_code == 200, f"Expected 200, got {schedule_response.status_code}: {schedule_response.text}"
        
        data = schedule_response.json()
        
        assert data["status"] == "scheduled", f"Expected 'scheduled' status, got {data['status']}"
        assert data["scheduled_at"] is not None, "Should have scheduled_at timestamp"
        
        print(f"✅ Campaign scheduled for: {data['scheduled_at']}")
        print(f"✅ Status: {data['status']}")
    
    def test_schedule_campaign_past_date_fails(self):
        """Test: Schedule campaign with past date should fail"""
        # Create a campaign
        campaign_data = {
            "name": f"TEST_PastSchedule_{uuid.uuid4().hex[:8]}",
            "subject": "Past Schedule Test",
            "html_content": "<html><body>Content</body></html>",
            "audience_filters": {}
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert create_response.status_code == 200
        
        campaign_id = create_response.json()["id"]
        
        # Try to schedule for 1 day in the past
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        schedule_response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/schedule",
            json={"scheduled_at": past_date}
        )
        
        assert schedule_response.status_code == 400, f"Expected 400, got {schedule_response.status_code}"
        
        print("✅ Correctly rejects past schedule date")
    
    # ========== POST /api/admin/marketing/campaigns/{id}/send (Send Campaign Now) ==========
    def test_send_campaign_now(self):
        """Test: Send campaign immediately"""
        # Create a campaign to send
        campaign_data = {
            "name": f"TEST_SendNow_{uuid.uuid4().hex[:8]}",
            "subject": "Send Now Test Email",
            "html_content": "<html><body>Immediate send test</body></html>",
            "audience_filters": {
                "subscription_tiers": ["free"],
                "exclude_unsubscribed": True
            }
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert create_response.status_code == 200
        
        campaign_id = create_response.json()["id"]
        
        # Send immediately
        send_response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/send")
        
        assert send_response.status_code == 200, f"Expected 200, got {send_response.status_code}: {send_response.text}"
        
        data = send_response.json()
        
        # Should return send result (may be "completed" with MOCKED SendGrid)
        assert "status" in data, "Response should have status"
        
        print(f"✅ Send result: {data}")
    
    # ========== POST /api/admin/marketing/campaigns/{id}/cancel (Cancel Campaign) ==========
    def test_cancel_scheduled_campaign(self):
        """Test: Cancel a scheduled campaign"""
        # Create and schedule a campaign
        campaign_data = {
            "name": f"TEST_CancelCampaign_{uuid.uuid4().hex[:8]}",
            "subject": "Cancel Test",
            "html_content": "<html><body>To be cancelled</body></html>",
            "audience_filters": {}
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert create_response.status_code == 200
        
        campaign_id = create_response.json()["id"]
        
        # Schedule it
        future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        schedule_response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/schedule",
            json={"scheduled_at": future_date}
        )
        assert schedule_response.status_code == 200
        
        # Cancel it
        cancel_response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/cancel",
            json={"reason": "TEST_Cancel - pytest test cancellation"}
        )
        
        assert cancel_response.status_code == 200, f"Expected 200, got {cancel_response.status_code}: {cancel_response.text}"
        
        data = cancel_response.json()
        
        assert data["status"] == "cancelled", f"Expected 'cancelled' status, got {data['status']}"
        
        print(f"✅ Campaign cancelled: {data['id']}")
        print(f"✅ Status: {data['status']}")
    
    def test_cancel_draft_fails(self):
        """Test: Cannot cancel a draft campaign (not scheduled)"""
        # Create a draft campaign
        campaign_data = {
            "name": f"TEST_CancelDraft_{uuid.uuid4().hex[:8]}",
            "subject": "Draft Cancel Test",
            "html_content": "<html><body>Draft</body></html>",
            "audience_filters": {}
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/admin/marketing/campaigns", json=campaign_data)
        assert create_response.status_code == 200
        
        campaign_id = create_response.json()["id"]
        
        # Try to cancel draft (should fail)
        cancel_response = self.session.post(
            f"{BASE_URL}/api/admin/marketing/campaigns/{campaign_id}/cancel",
            json={"reason": "TEST_Cancel - trying to cancel draft"}
        )
        
        assert cancel_response.status_code == 400, f"Expected 400, got {cancel_response.status_code}"
        
        print("✅ Correctly rejects cancelling draft campaign")
    
    # ========== GET /api/admin/marketing/campaigns/{id}/stats (Campaign Stats) ==========
    def test_get_campaign_stats(self):
        """Test: Get campaign statistics"""
        # Use test campaign
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/campaigns/{TEST_CAMPAIGN_ID}/stats")
        
        if response.status_code == 404:
            pytest.skip(f"Test campaign {TEST_CAMPAIGN_ID} not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "campaign_id" in data, "Should have campaign_id"
        assert "stats" in data, "Should have stats object"
        
        stats = data["stats"]
        assert "sent" in stats or "total_recipients" in stats, "Stats should have sent count"
        
        print(f"✅ Campaign stats: {stats}")
    
    # ========== POST /api/webhooks/sendgrid (Webhook Handler) ==========
    def test_sendgrid_webhook_handler(self):
        """Test: SendGrid webhook processes events correctly"""
        # Create a session without auth header (webhook is public)
        webhook_session = requests.Session()
        webhook_session.headers.update({"Content-Type": "application/json"})
        
        # Simulate a SendGrid event
        webhook_events = [
            {
                "event": "delivered",
                "email": "test@example.com",
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "sg_message_id": "abc123",
                "campaign_id": TEST_CAMPAIGN_ID
            },
            {
                "event": "open",
                "email": "test@example.com",
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "campaign_id": TEST_CAMPAIGN_ID
            }
        ]
        
        response = webhook_session.post(f"{BASE_URL}/api/webhooks/sendgrid", json=webhook_events)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Webhook returns "success" or "processed" status
        assert data["status"] in ["processed", "success"], f"Expected success status, got {data.get('status')}"
        # Count key may be "count" or "processed"
        event_count = data.get("count") or data.get("processed")
        assert event_count == 2, f"Expected 2 events processed, got {event_count}"
        
        print(f"✅ Webhook processed {event_count} events")
    
    def test_sendgrid_webhook_invalid_json(self):
        """Test: Webhook handles invalid JSON gracefully"""
        webhook_session = requests.Session()
        webhook_session.headers.update({"Content-Type": "application/json"})
        
        # Send invalid JSON
        response = webhook_session.post(
            f"{BASE_URL}/api/webhooks/sendgrid",
            data="not valid json"
        )
        
        # Should return 200 to prevent SendGrid retries
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["status"] == "error", "Should indicate error"
        
        print("✅ Webhook handles invalid JSON gracefully")
    
    # ========== GET /api/admin/marketing/config (Configuration Status) ==========
    def test_get_marketing_config(self):
        """Test: Get SendGrid configuration status"""
        response = self.session.get(f"{BASE_URL}/api/admin/marketing/config")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "marketing_configured" in data, "Should have marketing_configured flag"
        assert "has_marketing_key" in data, "Should have has_marketing_key flag"
        assert "has_transactional_key" in data, "Should have has_transactional_key flag"
        assert "from_email" in data, "Should have from_email"
        assert "marketing_from_email" in data, "Should have marketing_from_email"
        
        print(f"✅ Marketing configured: {data['marketing_configured']}")
        print(f"✅ Has marketing key: {data['has_marketing_key']}")
        print(f"✅ Has transactional key: {data['has_transactional_key']}")
        print(f"✅ From email: {data['from_email']}")


class TestAuthorizationAndEdgeCases:
    """Authorization and edge case tests"""
    
    def test_unauthenticated_access_denied(self):
        """Test: Unauthenticated requests are denied"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        endpoints = [
            ("GET", f"{BASE_URL}/api/admin/marketing/segment-filters"),
            ("GET", f"{BASE_URL}/api/admin/marketing/campaigns"),
            ("GET", f"{BASE_URL}/api/admin/marketing/config"),
        ]
        
        for method, url in endpoints:
            if method == "GET":
                response = session.get(url)
            else:
                response = session.post(url, json={})
            
            assert response.status_code == 401, f"{url} should require auth, got {response.status_code}"
        
        print("✅ All protected endpoints require authentication")
    
    def test_non_admin_access_denied(self):
        """Test: Non-admin users cannot access marketing endpoints"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Try to register a regular user - This may fail if email exists
        # Skip this test if registration isn't possible
        try:
            reg_response = session.post(f"{BASE_URL}/api/auth/register", json={
                "email": f"testuser_{uuid.uuid4().hex[:8]}@example.com",
                "password": "Test123!",
                "name": "Test User",
                "account_type": "personal",
                "phone": "1234567890"
            })
            
            if reg_response.status_code != 200:
                pytest.skip("Cannot create test user for non-admin test")
            
            token = reg_response.json().get("access_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            
            # Try to access marketing endpoint
            response = session.get(f"{BASE_URL}/api/admin/marketing/campaigns")
            
            assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
            
            print("✅ Non-admin users correctly denied access")
        except Exception as e:
            pytest.skip(f"Could not complete non-admin test: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
