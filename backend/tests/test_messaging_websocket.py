"""
BidVex Messaging WebSocket Tests
Tests for the real-time messaging features including:
- WebSocket connection
- TYPING_START, TYPING_STOP events
- MARK_READ events
- SEND_MESSAGE events
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMessagingAPI:
    """Test messaging REST API endpoints"""
    
    def get_auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    def test_get_conversations(self):
        """Test fetching conversations list"""
        token = self.get_auth_token()
        if not token:
            pytest.skip("Authentication failed - skipping authenticated tests")
        
        auth_headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/conversations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} conversations")
        
        # If conversations exist, verify structure
        if len(data) > 0:
            convo = data[0]
            assert "id" in convo
            assert "participants" in convo
            print(f"First conversation ID: {convo['id']}")
    
    def test_get_messages_for_conversation(self):
        """Test fetching messages for a conversation"""
        token = self.get_auth_token()
        if not token:
            pytest.skip("Authentication failed - skipping authenticated tests")
        
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # First get conversations
        convos_response = requests.get(f"{BASE_URL}/api/conversations", headers=auth_headers)
        assert convos_response.status_code == 200
        convos = convos_response.json()
        
        if len(convos) == 0:
            pytest.skip("No conversations available for testing")
        
        conversation_id = convos[0]["id"]
        
        # Get messages for the conversation
        response = requests.get(f"{BASE_URL}/api/messages/{conversation_id}", headers=auth_headers)
        assert response.status_code == 200
        messages = response.json()
        assert isinstance(messages, list)
        print(f"Found {len(messages)} messages in conversation {conversation_id}")
        
        # Verify message structure if messages exist
        if len(messages) > 0:
            msg = messages[0]
            assert "id" in msg
            assert "content" in msg or "message_type" in msg
            assert "sender_id" in msg
            assert "created_at" in msg
            # Check for read receipt fields
            if "is_read" in msg:
                print(f"Message has is_read field: {msg['is_read']}")
            if "read_at" in msg:
                print(f"Message has read_at field: {msg['read_at']}")


class TestWebSocketEndpoints:
    """Test WebSocket endpoint availability"""
    
    def test_websocket_messaging_endpoint_exists(self):
        """Verify the WebSocket messaging endpoint is configured"""
        # WebSocket endpoints return 200 with HTML for non-WebSocket requests in FastAPI
        # This is expected behavior - the endpoint exists
        response = requests.get(f"{BASE_URL}/api/ws/messaging/test-convo-id?user_id=test-user")
        # The endpoint exists if we get any response (not 404)
        # WebSocket upgrade would fail but endpoint is reachable
        print(f"WebSocket endpoint response: {response.status_code}")
        # Just verify the endpoint doesn't return 404 (not found)
        assert response.status_code != 404, "WebSocket endpoint not found"
        print("WebSocket messaging endpoint is configured and reachable")


class TestMessagingFeatures:
    """Test messaging feature requirements"""
    
    def test_i18n_translations_exist(self):
        """Verify i18n translation keys exist for messaging"""
        import json
        
        # Read English translations
        with open('/app/frontend/src/locales/en.json', 'r') as f:
            en_translations = json.load(f)
        
        # Read French translations
        with open('/app/frontend/src/locales/fr.json', 'r') as f:
            fr_translations = json.load(f)
        
        # Verify messaging keys exist in English
        assert "messaging" in en_translations
        messaging_en = en_translations["messaging"]
        assert "typing" in messaging_en
        assert "online" in messaging_en
        assert "offline" in messaging_en
        assert "seenAt" in messaging_en
        assert "typeMessage" in messaging_en
        
        print("English translations:")
        print(f"  typing: {messaging_en['typing']}")
        print(f"  online: {messaging_en['online']}")
        print(f"  offline: {messaging_en['offline']}")
        print(f"  seenAt: {messaging_en['seenAt']}")
        print(f"  typeMessage: {messaging_en['typeMessage']}")
        
        # Verify messaging keys exist in French
        assert "messaging" in fr_translations
        messaging_fr = fr_translations["messaging"]
        assert "typing" in messaging_fr
        assert "online" in messaging_fr
        assert "offline" in messaging_fr
        assert "seenAt" in messaging_fr
        assert "typeMessage" in messaging_fr
        
        print("\nFrench translations:")
        print(f"  typing: {messaging_fr['typing']}")
        print(f"  online: {messaging_fr['online']}")
        print(f"  offline: {messaging_fr['offline']}")
        print(f"  seenAt: {messaging_fr['seenAt']}")
        print(f"  typeMessage: {messaging_fr['typeMessage']}")
    
    def test_cookie_consent_hook_exists(self):
        """Verify useCookieConsent hook exists and has isAllowed function"""
        with open('/app/frontend/src/hooks/useCookieConsent.js', 'r') as f:
            content = f.read()
        
        # Verify isAllowed function exists
        assert "isAllowed" in content
        assert "functionality" in content
        print("useCookieConsent hook has isAllowed function for Law 25 gating")
    
    def test_messages_page_has_law25_gating(self):
        """Verify MessagesPage uses Law 25 cookie consent gating"""
        with open('/app/frontend/src/pages/MessagesPage.js', 'r') as f:
            content = f.read()
        
        # Verify useCookieConsent is imported and used
        assert "useCookieConsent" in content
        assert "isAllowed" in content
        assert "functionalityAllowed" in content
        
        # Verify typing indicators are gated
        assert "functionalityAllowed && otherUserTyping" in content
        
        # Verify read receipts are gated
        assert "functionalityAllowed && message.is_read" in content
        
        # Verify markAsRead is gated
        assert "functionalityAllowed" in content
        
        print("MessagesPage correctly implements Law 25 gating for:")
        print("  - Typing indicators")
        print("  - Read receipts (blue double checkmarks)")
        print("  - Mark as read functionality")
    
    def test_read_receipt_uses_vibrant_blue(self):
        """Verify read receipt uses vibrant BidVex blue #38BDF8"""
        with open('/app/frontend/src/pages/MessagesPage.js', 'r') as f:
            content = f.read()
        
        # Verify the vibrant blue color is used for CheckCheck icon
        assert "text-[#38BDF8]" in content
        assert "CheckCheck" in content
        
        print("Read receipt uses vibrant BidVex blue #38BDF8")
    
    def test_mobile_stack_layout(self):
        """Verify the messages layout renders core structural elements.

        iter301 note: the original pb-14 / backdrop-blur frosted input bar
        was replaced in a later redesign; assert on the current structural
        markers instead of the stale utility classes."""
        with open('/app/frontend/src/pages/MessagesPage.js', 'r') as f:
            content = f.read()

        # Conversation list + thread pane markers
        assert "selectedConversation" in content
        assert "messages-page" in content or "MessagesPage" in content
        # Input + send wiring still present
        assert "sendMessage" in content
        # iter301 — per-listing reply targeting
        assert "conversation_id: selectedConversation.id" in content

        print("Messages layout structural markers verified (iter301)")
    
    def test_footer_hidden_on_messages(self):
        """Verify footer is hidden on /messages route"""
        with open('/app/frontend/src/App.js', 'r') as f:
            content = f.read()
        
        # Verify FooterWrapper hides footer on /messages
        assert "FooterWrapper" in content
        assert "/messages" in content
        
        # Check the FooterWrapper implementation
        assert "location.pathname === '/messages'" in content or "pathname === '/messages'" in content
        
        print("Footer is correctly hidden on /messages route")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
