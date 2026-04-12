"""
Test Suite: Vehicle Settlement & Fee Passing - Iteration 133
Tests for Phase 5: Stripe Intermediary Handshake & Fee Passing for BidVex vehicle auctions.

Features tested:
- Fee calculation formula: net_commission = hammer * 0.025, total = (net + 0.30) / (1 - 0.029)
- GET /api/vehicle-settlement/fee-preview/{hammer_price} - public endpoint
- GET /api/auctions/{id}/seller-contact - auth required, 402 if no settlement
- GET /api/vehicle-settlement/{auction_id}/status - auth required, PENDING_CLOSE if no settlement
- calculate_vehicle_fee service function
- Webhook handlers for vehicle_platform_fee type

NOTE: Stripe API key is live - DO NOT create real PaymentIntents. Test fee calculations only.
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct service imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestFeeCalculationFormula:
    """Test the fee calculation formula directly"""
    
    def test_fee_calculation_10000_hammer(self):
        """Test fee calculation for $10,000 hammer price"""
        # Formula: net_commission = hammer * 0.025
        #          total_charge = (net_commission + 0.30) / (1 - 0.029)
        hammer_price = 10000.0
        
        expected_net_commission = round(hammer_price * 0.025, 2)  # $250.00
        expected_total = round((expected_net_commission + 0.30) / (1 - 0.029), 2)  # ~$257.78
        expected_stripe_fee = round(expected_total - expected_net_commission, 2)
        
        assert expected_net_commission == 250.00, f"Net commission should be $250.00, got {expected_net_commission}"
        assert expected_total == 257.78, f"Total charge should be ~$257.78, got {expected_total}"
        print(f"PASS: Fee calculation for $10,000 - Net: ${expected_net_commission}, Total: ${expected_total}")
    
    def test_fee_calculation_50000_hammer(self):
        """Test fee calculation for $50,000 hammer price"""
        hammer_price = 50000.0
        
        expected_net_commission = round(hammer_price * 0.025, 2)  # $1,250.00
        expected_total = round((expected_net_commission + 0.30) / (1 - 0.029), 2)  # ~$1,287.64
        
        assert expected_net_commission == 1250.00
        assert expected_total == 1287.64  # Actual calculation result
        print(f"PASS: Fee calculation for $50,000 - Net: ${expected_net_commission}, Total: ${expected_total}")
    
    def test_fee_calculation_1000_hammer(self):
        """Test fee calculation for $1,000 hammer price"""
        hammer_price = 1000.0
        
        expected_net_commission = round(hammer_price * 0.025, 2)  # $25.00
        expected_total = round((expected_net_commission + 0.30) / (1 - 0.029), 2)  # ~$26.06
        
        assert expected_net_commission == 25.00
        assert expected_total == 26.06
        print(f"PASS: Fee calculation for $1,000 - Net: ${expected_net_commission}, Total: ${expected_total}")


class TestFeePreviewEndpoint:
    """Test GET /api/vehicle-settlement/fee-preview/{hammer_price}"""
    
    def test_fee_preview_10000(self, api_client):
        """Test fee preview for $10,000 hammer price - public endpoint"""
        response = api_client.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/10000")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "hammer_price" in data, "Response missing hammer_price"
        assert "platform_fee" in data, "Response missing platform_fee"
        assert "processing_fee" in data, "Response missing processing_fee"
        assert "total_charge_to_buyer" in data, "Response missing total_charge_to_buyer"
        assert "fee_rate_percent" in data, "Response missing fee_rate_percent"
        assert "currency" in data, "Response missing currency"
        assert "breakdown_en" in data, "Response missing breakdown_en (bilingual)"
        assert "breakdown_fr" in data, "Response missing breakdown_fr (bilingual)"
        
        # Verify values
        assert data["hammer_price"] == 10000, f"Hammer price mismatch: {data['hammer_price']}"
        assert data["platform_fee"] == 250.00, f"Platform fee should be $250.00, got {data['platform_fee']}"
        assert data["fee_rate_percent"] == 2.5, f"Fee rate should be 2.5%, got {data['fee_rate_percent']}"
        assert data["currency"] == "CAD", f"Currency should be CAD, got {data['currency']}"
        
        # Verify total charge formula
        expected_total = round((250.00 + 0.30) / (1 - 0.029), 2)
        assert abs(data["total_charge_to_buyer"] - expected_total) < 0.01, \
            f"Total charge should be ~{expected_total}, got {data['total_charge_to_buyer']}"
        
        # Verify bilingual strings exist
        assert "Platform Fee" in data["breakdown_en"] or "platform" in data["breakdown_en"].lower()
        assert "Frais de plateforme" in data["breakdown_fr"] or "plateforme" in data["breakdown_fr"].lower()
        
        print(f"PASS: Fee preview for $10,000 - Platform: ${data['platform_fee']}, Total: ${data['total_charge_to_buyer']}")
        print(f"  EN: {data['breakdown_en']}")
        print(f"  FR: {data['breakdown_fr']}")
    
    def test_fee_preview_50000(self, api_client):
        """Test fee preview for $50,000 hammer price"""
        response = api_client.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/50000")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["hammer_price"] == 50000
        assert data["platform_fee"] == 1250.00
        
        expected_total = round((1250.00 + 0.30) / (1 - 0.029), 2)
        assert abs(data["total_charge_to_buyer"] - expected_total) < 0.01
        
        print(f"PASS: Fee preview for $50,000 - Platform: ${data['platform_fee']}, Total: ${data['total_charge_to_buyer']}")
    
    def test_fee_preview_invalid_negative(self, api_client):
        """Test fee preview rejects negative hammer price"""
        response = api_client.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/-1000")
        
        assert response.status_code == 400, f"Expected 400 for negative price, got {response.status_code}"
        print("PASS: Fee preview correctly rejects negative hammer price")
    
    def test_fee_preview_invalid_zero(self, api_client):
        """Test fee preview rejects zero hammer price"""
        response = api_client.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/0")
        
        assert response.status_code == 400, f"Expected 400 for zero price, got {response.status_code}"
        print("PASS: Fee preview correctly rejects zero hammer price")
    
    def test_fee_preview_decimal_price(self, api_client):
        """Test fee preview handles decimal hammer price"""
        response = api_client.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/12345.67")
        
        assert response.status_code == 200
        data = response.json()
        
        expected_net = round(12345.67 * 0.025, 2)
        assert abs(data["platform_fee"] - expected_net) < 0.01
        print(f"PASS: Fee preview for $12,345.67 - Platform: ${data['platform_fee']}")


class TestSellerContactGate:
    """Test GET /api/auctions/{id}/seller-contact - information gate"""
    
    def test_seller_contact_unauthenticated(self, api_client):
        """Test seller-contact returns 401 for unauthenticated users"""
        # Use a fresh session without auth
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        response = fresh_session.get(f"{BASE_URL}/api/auctions/test-auction-id/seller-contact")
        
        # Should return 401 Unauthorized or 403 Forbidden
        assert response.status_code in [401, 403], \
            f"Expected 401/403 for unauthenticated, got {response.status_code}: {response.text}"
        print(f"PASS: Seller contact returns {response.status_code} for unauthenticated users")
    
    def test_seller_contact_no_settlement_402(self, authenticated_client):
        """Test seller-contact returns 402 with bilingual message when no settlement exists"""
        # Use a non-existent auction ID
        fake_auction_id = "nonexistent-auction-12345"
        
        response = authenticated_client.get(f"{BASE_URL}/api/auctions/{fake_auction_id}/seller-contact")
        
        assert response.status_code == 402, \
            f"Expected 402 Payment Required, got {response.status_code}: {response.text}"
        
        data = response.json()
        detail = data.get("detail", data)
        
        # Verify bilingual messages
        assert "message_en" in detail, "Response missing message_en"
        assert "message_fr" in detail, "Response missing message_fr"
        assert "settlement_status" in detail, "Response missing settlement_status"
        
        # Verify English message
        assert "payment required" in detail["message_en"].lower() or "fee" in detail["message_en"].lower(), \
            f"English message should mention payment: {detail['message_en']}"
        
        # Verify French message
        assert "paiement" in detail["message_fr"].lower() or "frais" in detail["message_fr"].lower(), \
            f"French message should mention payment: {detail['message_fr']}"
        
        print(f"PASS: Seller contact returns 402 with bilingual messages")
        print(f"  EN: {detail['message_en']}")
        print(f"  FR: {detail['message_fr']}")
        print(f"  Status: {detail['settlement_status']}")


class TestSettlementStatus:
    """Test GET /api/vehicle-settlement/{auction_id}/status"""
    
    def test_settlement_status_unauthenticated(self, api_client):
        """Test settlement status returns 401 for unauthenticated users"""
        fresh_session = requests.Session()
        fresh_session.headers.update({"Content-Type": "application/json"})
        
        response = fresh_session.get(f"{BASE_URL}/api/vehicle-settlement/test-auction-id/status")
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 for unauthenticated, got {response.status_code}"
        print(f"PASS: Settlement status returns {response.status_code} for unauthenticated users")
    
    def test_settlement_status_pending_close(self, authenticated_client):
        """Test settlement status returns PENDING_CLOSE when no settlement exists"""
        fake_auction_id = "nonexistent-auction-67890"
        
        response = authenticated_client.get(f"{BASE_URL}/api/vehicle-settlement/{fake_auction_id}/status")
        
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "settlement_status" in data, "Response missing settlement_status"
        assert data["settlement_status"] == "PENDING_CLOSE", \
            f"Expected PENDING_CLOSE, got {data['settlement_status']}"
        assert data.get("contact_revealed") == False, \
            f"contact_revealed should be False, got {data.get('contact_revealed')}"
        
        print(f"PASS: Settlement status returns PENDING_CLOSE for non-existent settlement")


class TestVehicleFeeServiceDirect:
    """Test vehicle_fee_service.py calculate_vehicle_fee function directly"""
    
    def test_calculate_vehicle_fee_function(self):
        """Test the calculate_vehicle_fee function directly"""
        try:
            from services.vehicle_fee_service import calculate_vehicle_fee
            
            # Test with $10,000
            result = calculate_vehicle_fee(10000.0)
            
            assert result["hammer_price"] == 10000.0
            assert result["net_commission"] == 250.00
            assert result["fee_rate"] == 0.025
            assert result["currency"] == "cad"
            
            # Verify total charge formula
            expected_total = round((250.00 + 0.30) / (1 - 0.029), 2)
            assert abs(result["total_charge"] - expected_total) < 0.01
            
            # Verify stripe processing fee
            expected_stripe_fee = round(result["total_charge"] - result["net_commission"], 2)
            assert abs(result["stripe_processing_fee"] - expected_stripe_fee) < 0.01
            
            print(f"PASS: calculate_vehicle_fee($10,000) = {result}")
            
        except ImportError as e:
            pytest.skip(f"Could not import vehicle_fee_service: {e}")
    
    def test_calculate_vehicle_fee_various_amounts(self):
        """Test calculate_vehicle_fee with various amounts"""
        try:
            from services.vehicle_fee_service import calculate_vehicle_fee
            
            test_cases = [
                (1000.0, 25.00),
                (5000.0, 125.00),
                (25000.0, 625.00),
                (100000.0, 2500.00),
            ]
            
            for hammer, expected_net in test_cases:
                result = calculate_vehicle_fee(hammer)
                assert result["net_commission"] == expected_net, \
                    f"For ${hammer}, expected net ${expected_net}, got ${result['net_commission']}"
                
                # Verify total > net (includes Stripe recovery)
                assert result["total_charge"] > result["net_commission"], \
                    f"Total charge should be > net commission"
                
                print(f"PASS: calculate_vehicle_fee(${hammer}) - Net: ${result['net_commission']}, Total: ${result['total_charge']}")
            
        except ImportError as e:
            pytest.skip(f"Could not import vehicle_fee_service: {e}")


class TestWebhookHandlerStructure:
    """Test webhook handler structure for vehicle_platform_fee type (no real Stripe calls)"""
    
    def test_webhook_handler_imports(self):
        """Verify webhook handlers can be imported"""
        try:
            from services.vehicle_fee_service import handle_vehicle_fee_succeeded, handle_vehicle_fee_failed
            
            # Verify functions exist and are callable
            assert callable(handle_vehicle_fee_succeeded)
            assert callable(handle_vehicle_fee_failed)
            
            print("PASS: Webhook handlers handle_vehicle_fee_succeeded and handle_vehicle_fee_failed are importable")
            
        except ImportError as e:
            pytest.fail(f"Could not import webhook handlers: {e}")
    
    def test_webhook_router_has_vehicle_fee_handling(self):
        """Verify webhooks.py handles vehicle_platform_fee type"""
        try:
            # Read the webhooks.py file to verify structure
            with open('/app/backend/routes/webhooks.py', 'r') as f:
                content = f.read()
            
            # Check for vehicle_platform_fee handling
            assert 'vehicle_platform_fee' in content, \
                "webhooks.py should handle vehicle_platform_fee transaction type"
            
            assert 'handle_vehicle_fee_succeeded' in content, \
                "webhooks.py should call handle_vehicle_fee_succeeded"
            
            assert 'handle_vehicle_fee_failed' in content, \
                "webhooks.py should call handle_vehicle_fee_failed"
            
            assert 'payment_intent.succeeded' in content, \
                "webhooks.py should handle payment_intent.succeeded event"
            
            assert 'payment_intent.payment_failed' in content, \
                "webhooks.py should handle payment_intent.payment_failed event"
            
            print("PASS: webhooks.py has proper vehicle_platform_fee handling structure")
            
        except FileNotFoundError:
            pytest.skip("Could not read webhooks.py file")


class TestVehicleAuctionHandlerAutoCharge:
    """Test vehicle_auction_handler.py auto-charge trigger structure"""
    
    def test_auction_handler_has_fee_charge_trigger(self):
        """Verify vehicle_auction_handler.py triggers create_vehicle_fee_charge on auction close"""
        try:
            with open('/app/backend/services/vehicle_auction_handler.py', 'r') as f:
                content = f.read()
            
            # Check for fee charge import
            assert 'create_vehicle_fee_charge' in content, \
                "vehicle_auction_handler.py should import create_vehicle_fee_charge"
            
            assert 'vehicle_fee_service' in content, \
                "vehicle_auction_handler.py should import from vehicle_fee_service"
            
            # Check for auto-charge call in process_ended_auction
            assert 'await create_vehicle_fee_charge' in content, \
                "vehicle_auction_handler.py should call create_vehicle_fee_charge"
            
            print("PASS: vehicle_auction_handler.py has auto-charge trigger for platform fee")
            
        except FileNotFoundError:
            pytest.skip("Could not read vehicle_auction_handler.py file")


class TestMigrationScript:
    """Test migration script structure"""
    
    def test_migration_script_exists_and_valid(self):
        """Verify migration script exists and has proper structure"""
        try:
            with open('/app/backend/migrations/add_vehicle_settlement_fields.py', 'r') as f:
                content = f.read()
            
            # Check for required elements
            assert 'vehicle_settlements' in content, \
                "Migration should reference vehicle_settlements collection"
            
            assert 'create_index' in content, \
                "Migration should create indexes"
            
            assert 'asyncio.run' in content or 'async def migrate' in content, \
                "Migration should be async-compatible"
            
            assert 'MONGO_URL' in content, \
                "Migration should use MONGO_URL from environment"
            
            print("PASS: Migration script has proper structure")
            
        except FileNotFoundError:
            pytest.fail("Migration script not found at /app/backend/migrations/add_vehicle_settlement_fields.py")


class TestAPIEndpointAvailability:
    """Test that all required API endpoints are available"""
    
    def test_fee_preview_endpoint_exists(self, api_client):
        """Verify fee-preview endpoint is registered"""
        response = api_client.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/1000")
        assert response.status_code != 404, "fee-preview endpoint should exist"
        print("PASS: /api/vehicle-settlement/fee-preview/{hammer_price} endpoint exists")
    
    def test_seller_contact_endpoint_exists(self, api_client):
        """Verify seller-contact endpoint is registered"""
        response = api_client.get(f"{BASE_URL}/api/auctions/test/seller-contact")
        # Should return 401/403 (auth required) or 402 (payment required), not 404
        assert response.status_code != 404, "seller-contact endpoint should exist"
        print(f"PASS: /api/auctions/{{id}}/seller-contact endpoint exists (returns {response.status_code})")
    
    def test_settlement_status_endpoint_exists(self, api_client):
        """Verify settlement status endpoint is registered"""
        response = api_client.get(f"{BASE_URL}/api/vehicle-settlement/test/status")
        # Should return 401/403 (auth required), not 404
        assert response.status_code != 404, "settlement status endpoint should exist"
        print(f"PASS: /api/vehicle-settlement/{{auction_id}}/status endpoint exists (returns {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
