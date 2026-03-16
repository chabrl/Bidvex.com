"""
Test AI Chatbot Partner Fee Knowledge - Iteration 49
Tests that the chatbot knows:
1. Partner account fees ($100 CAD/year + 3% commission)
2. BidVex address (103-761 Chalifoux Street, Sherbrooke)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestChatbotPartnerFees:
    """Test AI chatbot knowledge of partner fees and address"""
    
    def test_chatbot_knows_partner_fees(self):
        """Test that chatbot responds with partner fee information"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What are the Partner account fees on BidVex?",
                "language": "en"
            },
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        message = data.get("message", "").lower()
        
        # Check for $100 CAD/year mention
        assert "$100" in message or "100 cad" in message.lower() or "100.00 cad" in message.lower(), \
            f"Expected $100 CAD annual fee mentioned. Response: {message[:500]}"
        
        # Check for 3% commission mention
        assert "3%" in message, f"Expected 3% commission mentioned. Response: {message[:500]}"
        
        print(f"PASS: Chatbot response contains partner fee info: $100 and 3%")
        print(f"Response snippet: {message[:300]}...")
    
    def test_chatbot_knows_address(self):
        """Test that chatbot responds with correct address"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What is the BidVex mailing address?",
                "language": "en"
            },
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        
        message = data.get("message", "")
        
        # Check for correct address components
        assert "103-761" in message or "103 761" in message or "103761" in message.replace("-", "").replace(" ", ""), \
            f"Expected 103-761 in address. Response: {message[:500]}"
        
        assert "chalifoux" in message.lower(), \
            f"Expected Chalifoux Street mentioned. Response: {message[:500]}"
        
        assert "sherbrooke" in message.lower(), \
            f"Expected Sherbrooke mentioned. Response: {message[:500]}"
        
        print(f"PASS: Chatbot response contains correct address")
        print(f"Response snippet: {message[:300]}...")
    
    def test_chatbot_endpoint_health(self):
        """Basic test that chatbot endpoint is working"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "Hello",
                "language": "en"
            },
            timeout=15
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data, f"Expected 'message' in response: {data}"
        print(f"PASS: Chatbot endpoint is healthy")


class TestPartnerFeesInContext:
    """Test partner fee knowledge in different conversation contexts"""
    
    def test_chatbot_annual_fee_detail(self):
        """Test specific question about annual fee"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "How much is the annual platform fee for Partner accounts?",
                "language": "en"
            },
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        message = data.get("message", "").lower()
        
        # Should mention $100 or 100 CAD
        has_hundred = "$100" in message or "100 cad" in message or "100.00" in message
        assert has_hundred, f"Expected $100 CAD annual fee. Response: {message[:500]}"
        print(f"PASS: Annual fee of $100 CAD correctly mentioned")
    
    def test_chatbot_commission_detail(self):
        """Test specific question about hammer price commission"""
        response = requests.post(
            f"{BASE_URL}/api/ai-chat/message",
            json={
                "message": "What commission does BidVex charge Partners on the hammer price?",
                "language": "en"
            },
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        message = data.get("message", "")
        
        # Should mention 3%
        assert "3%" in message, f"Expected 3% commission. Response: {message[:500]}"
        print(f"PASS: 3% commission correctly mentioned")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
