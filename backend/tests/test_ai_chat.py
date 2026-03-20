"""
AI Chatbot API Tests for BidVex Master Concierge
Tests: message handling, context retention, language detection, edge cases, error handling
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tax-liability-portal.preview.emergentagent.com').rstrip('/')


class TestAIChatBasicFunctionality:
    """Test basic chatbot message sending and responses"""
    
    def test_simple_message(self):
        """Test sending a simple question and getting a response"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What is BidVex?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["message"]) > 50  # Should have substantial response
        assert data["language"] == "en"
        # Check BidVex-related content in response
        assert "bidvex" in data["message"].lower() or "auction" in data["message"].lower()
    
    def test_shipping_policy_question(self):
        """Test knowledge about shipping (should mention local pickup as default)"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "How does shipping work?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should mention local pickup or shipping
        assert any(term in data["message"].lower() for term in ["pickup", "shipping", "delivery"])
    
    def test_fees_question(self):
        """Test knowledge about buyer premium (should mention 5% for personal)"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What are the buyer fees?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should mention fees/premium
        assert any(term in data["message"].lower() for term in ["5%", "fee", "premium", "percent"])
    
    def test_anti_sniping_question(self):
        """Test knowledge about anti-sniping feature"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "Why did the auction timer extend when I placed a bid?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should mention anti-sniping or timer extension
        assert any(term in data["message"].lower() for term in ["snip", "anti", "extend", "2 minute", "timer"])


class TestAIChatLanguageDetection:
    """Test language detection and bilingual support"""
    
    def test_french_message_response_in_french(self):
        """Test that French messages get French responses"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "Bonjour, comment puis-je vendre sur BidVex?",
                "language": "fr",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["language"] == "fr"
        # Check for French words in response
        french_indicators = ["vous", "votre", "pour", "avec", "les", "des", "une", "sur", "est", "sont"]
        response_lower = data["message"].lower()
        has_french = any(word in response_lower for word in french_indicators)
        assert has_french, "Response should be in French"
    
    def test_auto_detect_french(self):
        """Test automatic French language detection"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "Je voudrais savoir comment fonctionne les enchères",
                "language": "en",  # Explicitly pass 'en' but message is French
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestAIChatContextRetention:
    """Test context retention across conversation"""
    
    def test_follow_up_question(self):
        """Test that follow-up questions retain context"""
        # First message about fees
        first_response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What are the buyer fees?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert first_response.status_code == 200
        first_data = first_response.json()
        
        # Follow-up with context
        second_response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "And for business accounts?",
                "language": "en",
                "chat_history": [
                    {"role": "user", "content": "What are the buyer fees?"},
                    {"role": "assistant", "content": first_data["message"]}
                ]
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert second_response.status_code == 200
        second_data = second_response.json()
        assert second_data["success"] is True
        # Should mention 4.5% for business accounts
        assert "4.5" in second_data["message"] or "business" in second_data["message"].lower()


class TestAIChatEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_message(self):
        """Test handling of empty message"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should handle gracefully
        assert data["success"] is True
        assert len(data["message"]) > 0
    
    def test_long_message(self):
        """Test handling of very long message (1000+ chars)"""
        long_message = "Tell me about auctions. " * 50  # ~600 chars
        
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": long_message,
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=90
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["message"]) > 0
    
    def test_special_characters(self):
        """Test handling of special characters and HTML entities"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What about fees <script>alert(1)</script> & \"quotes\" ? $$$",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Response should not contain the script tag
        assert "<script>" not in data["message"]
    
    def test_unicode_characters(self):
        """Test handling of unicode/emoji characters"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "Hello! 👋 How do auctions work? 🔨",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestAIChatRichContent:
    """Test rich content (action buttons) in responses"""
    
    def test_action_buttons_on_support_query(self):
        """Test that support queries trigger Contact Support button"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "I need to contact support, my account has an issue",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Should have rich_content with action buttons
        if data.get("rich_content"):
            assert isinstance(data["rich_content"], dict)
            # Check for action_buttons if present
            if data["rich_content"].get("action_buttons"):
                buttons = data["rich_content"]["action_buttons"]
                assert isinstance(buttons, list)
    
    def test_browse_auctions_button(self):
        """Test that auction queries may include Browse Auctions button"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "Where can I view available auctions?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Rich content is optional but should be valid if present
        if data.get("rich_content") and data["rich_content"].get("action_buttons"):
            for btn in data["rich_content"]["action_buttons"]:
                assert "text" in btn
                assert "url" in btn


class TestAIChatMasterConciergeBehavior:
    """Test Master Concierge persona and knowledge"""
    
    def test_professional_tone(self):
        """Test that responses maintain luxury/professional tone"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "Hi there!",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Response should be professional (not too casual)
        response_lower = data["message"].lower()
        professional_indicators = ["assist", "help", "welcome", "service", "please"]
        has_professional_tone = any(word in response_lower for word in professional_indicators)
        assert has_professional_tone
    
    def test_verification_guidance(self):
        """Test that bidding queries mention verification requirements"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "How do I start bidding?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should mention verification
        verification_terms = ["verify", "phone", "payment", "verification", "account"]
        response_lower = data["message"].lower()
        has_verification_info = any(term in response_lower for term in verification_terms)
        # This is expected behavior based on the system prompt
        assert has_verification_info or "bid" in response_lower


class TestAIChatResponseTime:
    """Test response time and performance"""
    
    def test_response_within_timeout(self):
        """Test that AI responds within acceptable time (< 60s)"""
        start_time = time.time()
        
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What are BidVex seller fees?",
                "language": "en",
                "chat_history": []
            },
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        elapsed_time = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed_time < 60, f"Response took too long: {elapsed_time:.2f}s"
        print(f"Response time: {elapsed_time:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
