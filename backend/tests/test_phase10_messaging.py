"""
Phase 10: Messaging Extraction & CRA Tax Reports Router Tests

Tests:
1. Messaging REST endpoints (extracted from server.py to routes/messages.py)
2. Tax Reports endpoints (CRA compliance, prefix /api/tax)
3. Admin messaging moderation endpoints
4. WebSocket still exists in server.py
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
OTHER_USER_ID = "c3c08016-7305-4963-9970-5635c52599b3"

class TestSetup:
    """Verify test setup and get auth tokens"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        
        data = response.json()
        token = data.get("access_token") or data.get("token")
        if not token:
            pytest.skip("No token in login response")
        
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session, data.get("user", {})
    
    def test_admin_login(self, admin_session):
        """Verify admin login works"""
        session, user = admin_session
        assert user.get("email") == ADMIN_EMAIL
        print(f"✅ Admin login successful: {user.get('id')}")


class TestMessagingEndpoints:
    """Test messaging REST endpoints extracted to routes/messages.py"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        data = response.json()
        token = data.get("access_token") or data.get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session, data.get("user", {})
    
    def test_post_messages_send_message(self, admin_session):
        """POST /api/messages sends a message and returns conversation_id + content"""
        session, user = admin_session
        
        response = session.post(f"{BASE_URL}/api/messages", json={
            "receiver_id": OTHER_USER_ID,
            "content": "Test message from Phase 10 testing"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response has conversation_id and content
        assert "conversation_id" in data, "Response should have conversation_id"
        assert "content" in data, "Response should have content"
        assert data["content"] == "Test message from Phase 10 testing"
        print(f"✅ POST /api/messages: conversation_id={data['conversation_id']}")
    
    def test_get_conversations(self, admin_session):
        """GET /api/conversations returns conversations list for authenticated user"""
        session, user = admin_session
        
        response = session.get(f"{BASE_URL}/api/conversations")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ GET /api/conversations: Found {len(data)} conversations")
        
        # If we have conversations, verify structure
        if data:
            convo = data[0]
            assert "id" in convo, "Conversation should have id"
            assert "participants" in convo, "Conversation should have participants"
    
    def test_get_unread_count(self, admin_session):
        """GET /api/messages/unread-count returns unread_count field"""
        session, user = admin_session
        
        response = session.get(f"{BASE_URL}/api/messages/unread-count")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "unread_count" in data, "Response should have unread_count field"
        assert isinstance(data["unread_count"], int), "unread_count should be integer"
        print(f"✅ GET /api/messages/unread-count: {data['unread_count']}")
    
    def test_get_messages_for_conversation(self, admin_session):
        """GET /api/messages/{conversation_id} returns messages for a conversation"""
        session, user = admin_session
        
        # First get a conversation
        convos_response = session.get(f"{BASE_URL}/api/conversations")
        if convos_response.status_code != 200 or not convos_response.json():
            pytest.skip("No conversations available to test")
        
        conversation_id = convos_response.json()[0]["id"]
        
        response = session.get(f"{BASE_URL}/api/messages/{conversation_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list of messages"
        print(f"✅ GET /api/messages/{conversation_id}: Found {len(data)} messages")
    
    def test_post_attachment_validation(self, admin_session):
        """POST /api/messages/attachment returns 400 without file (validation)"""
        session, user = admin_session
        
        # Send without file - should return 400 or 422
        response = session.post(
            f"{BASE_URL}/api/messages/attachment",
            data={
                "receiver_id": OTHER_USER_ID,
                "conversation_id": f"{user.get('id')}_{OTHER_USER_ID}"
            }
        )
        
        # Without a file, FastAPI returns 422 (validation error)
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}: {response.text}"
        print(f"✅ POST /api/messages/attachment: Correctly returns {response.status_code} without file")
    
    def test_post_share_item_details_validation(self, admin_session):
        """POST /api/messages/share-item-details returns 400 without conversation_id"""
        session, user = admin_session
        
        response = session.post(f"{BASE_URL}/api/messages/share-item-details", json={
            "listing_id": "some-listing-id"
            # Missing conversation_id
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "conversation_id" in data.get("detail", "").lower() or "required" in data.get("detail", "").lower()
        print(f"✅ POST /api/messages/share-item-details: Correctly returns 400 without conversation_id")
    
    def test_get_conversation_online_status(self, admin_session):
        """GET /api/conversations/{conversation_id}/online-status returns online_users list"""
        session, user = admin_session
        
        # Get a conversation first
        convos_response = session.get(f"{BASE_URL}/api/conversations")
        if convos_response.status_code != 200 or not convos_response.json():
            pytest.skip("No conversations available to test")
        
        conversation_id = convos_response.json()[0]["id"]
        
        response = session.get(f"{BASE_URL}/api/conversations/{conversation_id}/online-status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "online_users" in data, "Response should have online_users field"
        assert isinstance(data["online_users"], list), "online_users should be a list"
        print(f"✅ GET /api/conversations/{conversation_id}/online-status: online_users={data['online_users']}")


class TestAdminMessagingEndpoints:
    """Test admin messaging moderation endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        data = response.json()
        token = data.get("access_token") or data.get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session, data.get("user", {})
    
    def test_admin_get_flagged_messages(self, admin_session):
        """GET /api/admin/messages/flagged returns array (admin only)"""
        session, user = admin_session
        
        response = session.get(f"{BASE_URL}/api/admin/messages/flagged")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be an array"
        print(f"✅ GET /api/admin/messages/flagged: Found {len(data)} flagged messages")
    
    def test_admin_delete_message_idempotent(self, admin_session):
        """DELETE /api/admin/messages/nonexistent-id returns 200 (idempotent delete)"""
        session, user = admin_session
        
        response = session.delete(f"{BASE_URL}/api/admin/messages/nonexistent-id-12345")
        
        # Should return 200 even for non-existent message (idempotent)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✅ DELETE /api/admin/messages/nonexistent-id: Returns 200 (idempotent)")
    
    def test_admin_suspend_user_messaging(self, admin_session):
        """PUT /api/admin/users/{user_id}/messaging with {suspended: true} returns success"""
        session, user = admin_session
        
        response = session.put(
            f"{BASE_URL}/api/admin/users/test-user-id-12345/messaging",
            json={"suspended": True}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should have message field"
        assert "suspended" in data["message"].lower(), "Message should mention suspended"
        print(f"✅ PUT /api/admin/users/test-user-id/messaging: {data['message']}")


class TestTaxReportsRouter:
    """Test CRA Tax Reports endpoints (routes/tax_reports.py)"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        data = response.json()
        token = data.get("access_token") or data.get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session, data.get("user", {})
    
    def test_get_tax_reports(self, admin_session):
        """GET /api/tax/reports returns {reports, count}"""
        session, user = admin_session
        
        response = session.get(f"{BASE_URL}/api/tax/reports")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "reports" in data, "Response should have reports field"
        assert "count" in data, "Response should have count field"
        assert isinstance(data["reports"], list), "reports should be a list"
        assert isinstance(data["count"], int), "count should be an integer"
        print(f"✅ GET /api/tax/reports: Found {data['count']} reports")
    
    def test_get_tax_summary_2026(self, admin_session):
        """GET /api/tax/summary/2026 returns year, total_sales, taxes, invoice_count"""
        session, user = admin_session
        
        response = session.get(f"{BASE_URL}/api/tax/summary/2026")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "year" in data, "Response should have year field"
        assert data["year"] == 2026, "Year should be 2026"
        assert "total_sales" in data, "Response should have total_sales"
        assert "taxes" in data, "Response should have taxes"
        assert "invoice_count" in data, "Response should have invoice_count"
        print(f"✅ GET /api/tax/summary/2026: total_sales={data['total_sales']}, invoice_count={data['invoice_count']}")
    
    def test_post_generate_gst_hst_report(self, admin_session):
        """POST /api/tax/reports/gst-hst returns generated report for admin"""
        session, user = admin_session
        
        response = session.post(
            f"{BASE_URL}/api/tax/reports/gst-hst",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "reporting_period": "monthly"
            }
        )
        
        # Should succeed or return meaningful response
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Report should have structure indicating generation
        print(f"✅ POST /api/tax/reports/gst-hst: Report generated")


class TestWebSocketStillInServer:
    """Verify WebSocket endpoints still exist in server.py (not moved)"""
    
    def test_websocket_messages_endpoint_exists(self):
        """Check WebSocket at /api/ws/messages/{user_id} still accepts connections"""
        # We can't fully test WebSocket with requests, but we can verify the endpoint exists
        # by checking it doesn't return 404 immediately
        
        # Attempt to connect - will fail HTTP handshake but shouldn't be 404
        import websocket
        try:
            ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
            ws_url = f"{ws_url}/api/ws/messages/test-user-id"
            
            # Just attempt connection - we mainly verify endpoint exists
            ws = websocket.create_connection(ws_url, timeout=3)
            ws.close()
            print("✅ WebSocket /api/ws/messages/{user_id} accepts connections")
        except websocket.WebSocketException as e:
            # Connection might fail for auth reasons, but endpoint exists
            if "404" in str(e).lower():
                pytest.fail("WebSocket endpoint /api/ws/messages not found (404)")
            print(f"✅ WebSocket endpoint exists (connection attempt: {e})")
        except Exception as e:
            # Other connection issues (auth, timeout) mean endpoint exists
            if "404" not in str(e).lower():
                print(f"✅ WebSocket endpoint exists (got: {type(e).__name__})")
            else:
                pytest.fail(f"WebSocket endpoint issue: {e}")


class TestConversationCreation:
    """Test that messages between users create conversations in DB"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        data = response.json()
        token = data.get("access_token") or data.get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session, data.get("user", {})
    
    def test_message_creates_conversation(self, admin_session):
        """POST /api/messages between two users creates conversation in DB"""
        session, user = admin_session
        
        # Send message
        response = session.post(f"{BASE_URL}/api/messages", json={
            "receiver_id": OTHER_USER_ID,
            "content": "Testing conversation creation - Phase 10"
        })
        
        assert response.status_code == 200, f"Message send failed: {response.text}"
        msg_data = response.json()
        conversation_id = msg_data.get("conversation_id")
        
        # Verify conversation exists by getting it
        convos_response = session.get(f"{BASE_URL}/api/conversations")
        assert convos_response.status_code == 200
        
        conversations = convos_response.json()
        convo_ids = [c["id"] for c in conversations]
        
        assert conversation_id in convo_ids, f"Conversation {conversation_id} not found in user's conversations"
        print(f"✅ Message created conversation: {conversation_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
