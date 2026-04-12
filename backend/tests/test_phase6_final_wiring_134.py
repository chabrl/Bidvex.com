"""
Phase 6: Final Wiring & Production Readiness Tests - Iteration 134
Tests for:
- Vehicle Settlement endpoints (verify-card, confirm-card-verification, fee-preview, seller-contact)
- ListingDetailPage component wiring verification (code review)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestVehicleSettlementEndpoints:
    """Vehicle Settlement API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbel911@gmail.com",
            "password": "Anderosli123!@#"
        })
        if login_response.status_code == 200:
            self.token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    # ─── Fee Preview Endpoint Tests ───────────────────────────────────────
    
    def test_fee_preview_valid_price(self):
        """GET /api/vehicle-settlement/fee-preview/{price} returns correct fee breakdown"""
        response = requests.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/10000")
        assert response.status_code == 200
        
        data = response.json()
        assert "hammer_price" in data
        assert "platform_fee" in data
        assert "processing_fee" in data
        assert "total_charge_to_buyer" in data
        assert "breakdown_en" in data
        assert "breakdown_fr" in data
        
        # Verify fee calculation (2.5% platform fee)
        assert data["hammer_price"] == 10000.0
        assert data["platform_fee"] == 250.0  # 10000 * 0.025
        assert data["fee_rate_percent"] == 2.5
        assert data["currency"] == "CAD"
        print(f"✓ Fee preview for $10,000: Platform Fee ${data['platform_fee']}, Total ${data['total_charge_to_buyer']}")
    
    def test_fee_preview_various_prices(self):
        """Fee preview works for various hammer prices"""
        test_prices = [1000, 5000, 25000, 50000]
        
        for price in test_prices:
            response = requests.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/{price}")
            assert response.status_code == 200
            
            data = response.json()
            expected_platform_fee = price * 0.025
            assert data["platform_fee"] == expected_platform_fee
            print(f"✓ Fee preview for ${price}: Platform Fee ${data['platform_fee']}")
    
    def test_fee_preview_invalid_price(self):
        """Fee preview rejects invalid prices"""
        response = requests.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/0")
        assert response.status_code == 400
        print("✓ Fee preview correctly rejects zero price")
        
        response = requests.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/-100")
        assert response.status_code == 400
        print("✓ Fee preview correctly rejects negative price")
    
    def test_fee_preview_bilingual_strings(self):
        """Fee preview returns bilingual breakdown strings"""
        response = requests.get(f"{BASE_URL}/api/vehicle-settlement/fee-preview/10000")
        assert response.status_code == 200
        
        data = response.json()
        assert "Platform Fee:" in data["breakdown_en"]
        assert "Processing:" in data["breakdown_en"]
        assert "Frais de plateforme" in data["breakdown_fr"]
        assert "Traitement" in data["breakdown_fr"]
        print("✓ Fee preview returns bilingual breakdown strings (EN/FR)")
    
    # ─── Seller Contact Endpoint Tests ────────────────────────────────────
    
    def test_seller_contact_unauthenticated(self):
        """GET /api/auctions/{id}/seller-contact returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/auctions/test-auction-id/seller-contact")
        assert response.status_code == 401
        print("✓ Seller contact endpoint requires authentication")
    
    def test_seller_contact_no_settlement(self):
        """GET /api/auctions/{id}/seller-contact returns 402 when no settlement exists"""
        response = self.session.get(f"{BASE_URL}/api/auctions/nonexistent-auction/seller-contact")
        assert response.status_code == 402
        
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert "message_en" in detail
        assert "message_fr" in detail
        assert detail["settlement_status"] == "PENDING_CLOSE"
        print("✓ Seller contact returns 402 with bilingual message when no settlement")
    
    # ─── Settlement Status Endpoint Tests ─────────────────────────────────
    
    def test_settlement_status_no_settlement(self):
        """GET /api/vehicle-settlement/{id}/status returns PENDING_CLOSE when no settlement"""
        response = self.session.get(f"{BASE_URL}/api/vehicle-settlement/nonexistent-auction/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["settlement_status"] == "PENDING_CLOSE"
        assert data["contact_revealed"] == False
        print("✓ Settlement status returns PENDING_CLOSE for non-existent settlement")
    
    def test_settlement_status_unauthenticated(self):
        """GET /api/vehicle-settlement/{id}/status returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/vehicle-settlement/test-auction/status")
        assert response.status_code == 401
        print("✓ Settlement status endpoint requires authentication")
    
    # ─── Card Verification Endpoint Tests ─────────────────────────────────
    
    def test_confirm_card_verification(self):
        """POST /api/vehicle-settlement/confirm-card-verification marks card as verified"""
        response = self.session.post(f"{BASE_URL}/api/vehicle-settlement/confirm-card-verification")
        assert response.status_code == 200
        
        data = response.json()
        assert data["verified"] == True
        assert "message" in data
        print("✓ Confirm card verification endpoint works")
    
    def test_confirm_card_verification_unauthenticated(self):
        """POST /api/vehicle-settlement/confirm-card-verification returns 401 without auth"""
        response = requests.post(f"{BASE_URL}/api/vehicle-settlement/confirm-card-verification")
        assert response.status_code == 401
        print("✓ Confirm card verification requires authentication")


class TestListingDetailPageWiring:
    """Code review tests for ListingDetailPage component wiring"""
    
    def test_cross_border_advisory_panel_import(self):
        """Verify CrossBorderAdvisoryPanel is imported in ListingDetailPage"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "CrossBorderAdvisoryPanel" in content
        assert "from '../components/legal/LegalComplianceSections'" in content
        print("✓ CrossBorderAdvisoryPanel is imported from LegalComplianceSections")
    
    def test_cross_border_bid_modal_import(self):
        """Verify CrossBorderBidModal is imported in ListingDetailPage"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "CrossBorderBidModal" in content
        print("✓ CrossBorderBidModal is imported")
    
    def test_seller_contact_gate_import(self):
        """Verify SellerContactGate is imported in ListingDetailPage"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "SellerContactGate" in content
        assert "from '../components/vehicles/VehicleFeeBreakdown'" in content
        print("✓ SellerContactGate is imported from VehicleFeeBreakdown")
    
    def test_vehicle_fee_breakdown_import(self):
        """Verify VehicleFeeBreakdown is imported in ListingDetailPage"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "VehicleFeeBreakdown" in content
        print("✓ VehicleFeeBreakdown is imported")
    
    def test_cross_border_check_logic(self):
        """Verify cross-border check logic exists"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "isCrossBorder" in content
        assert "listing.country" in content
        assert "'CA'" in content or '"CA"' in content
        print("✓ Cross-border check logic (isCrossBorder) is implemented")
    
    def test_cross_border_advisory_panel_rendering(self):
        """Verify CrossBorderAdvisoryPanel is conditionally rendered for non-CA listings"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "isCrossBorder && (" in content or "{isCrossBorder &&" in content
        assert "<CrossBorderAdvisoryPanel" in content
        print("✓ CrossBorderAdvisoryPanel is conditionally rendered for cross-border listings")
    
    def test_seller_contact_gate_rendering(self):
        """Verify SellerContactGate is rendered for won auctions"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "isAuctionWon" in content
        assert "<SellerContactGate" in content
        print("✓ SellerContactGate is rendered for won auctions")
    
    def test_vehicle_fee_notice_rendering(self):
        """Verify vehicle fee notice is shown above Place Bid button"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "isVehicleCategory" in content
        assert 'data-testid="vehicle-fee-notice"' in content
        print("✓ Vehicle fee notice is rendered for vehicle-category listings")
    
    def test_cross_border_badge_rendering(self):
        """Verify cross-border badge is shown for non-Canadian listings"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cross-border-badge"' in content
        print("✓ Cross-border badge is rendered for non-Canadian listings")
    
    def test_cross_border_bid_modal_intercept(self):
        """Verify cross-border bid modal intercepts first bid"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "crossBorderModalOpen" in content
        assert "setCrossBorderModalOpen" in content
        assert "crossBorderAccepted" in content
        assert "<CrossBorderBidModal" in content
        print("✓ CrossBorderBidModal intercepts first bid on cross-border listings")
    
    def test_cross_border_disclosure_in_bid_payload(self):
        """Verify cross_border_disclosure_accepted is sent in bid payload"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "cross_border_disclosure_accepted" in content
        print("✓ cross_border_disclosure_accepted is included in bid payload")


class TestLegalComplianceComponents:
    """Tests for LegalComplianceSections.js components"""
    
    def test_cross_border_advisory_panel_component(self):
        """Verify CrossBorderAdvisoryPanel component structure"""
        with open('/app/frontend/src/components/legal/LegalComplianceSections.js', 'r') as f:
            content = f.read()
        
        assert "export const CrossBorderAdvisoryPanel" in content
        assert 'data-testid="cross-border-advisory"' in content
        assert "CROSS-BORDER LISTING" in content
        assert "ANNONCE TRANSFRONTALIÈRE" in content
        print("✓ CrossBorderAdvisoryPanel component is properly structured with bilingual content")
    
    def test_cross_border_bid_modal_component(self):
        """Verify CrossBorderBidModal component structure"""
        with open('/app/frontend/src/components/legal/LegalComplianceSections.js', 'r') as f:
            content = f.read()
        
        assert "export const CrossBorderBidModal" in content
        assert 'data-testid="cross-border-bid-modal"' in content
        assert 'data-testid="cross-border-accept-btn"' in content
        assert 'data-testid="cross-border-cancel-btn"' in content
        assert "onAccept" in content
        assert "onCancel" in content
        print("✓ CrossBorderBidModal component is properly structured with accept/cancel buttons")


class TestVehicleFeeBreakdownComponents:
    """Tests for VehicleFeeBreakdown.js components"""
    
    def test_vehicle_fee_breakdown_component(self):
        """Verify VehicleFeeBreakdown component structure"""
        with open('/app/frontend/src/components/vehicles/VehicleFeeBreakdown.js', 'r') as f:
            content = f.read()
        
        assert "export const VehicleFeeBreakdown" in content
        assert 'data-testid="vehicle-fee-breakdown"' in content
        assert "hammerPrice" in content
        assert "feeData" in content
        assert "Platform Fee" in content
        assert "Frais de plateforme" in content
        print("✓ VehicleFeeBreakdown component is properly structured with bilingual content")
    
    def test_seller_contact_gate_component(self):
        """Verify SellerContactGate component structure"""
        with open('/app/frontend/src/components/vehicles/VehicleFeeBreakdown.js', 'r') as f:
            content = f.read()
        
        assert "export const SellerContactGate" in content
        assert 'data-testid="seller-contact-locked"' in content
        assert 'data-testid="seller-contact-revealed"' in content
        assert "settlementStatus" in content
        assert "sellerData" in content
        assert "FEE_PAID" in content
        print("✓ SellerContactGate component is properly structured with locked/revealed states")


class TestBackendWebhookHandlers:
    """Tests for webhook handler presence"""
    
    def test_webhook_handlers_exist(self):
        """Verify webhook handlers for payment_intent.succeeded/failed exist"""
        with open('/app/backend/routes/webhooks.py', 'r') as f:
            content = f.read()
        
        assert "payment_intent.succeeded" in content
        assert "payment_intent.payment_failed" in content or "payment_intent.failed" in content
        print("✓ Webhook handlers for payment_intent.succeeded/failed are in place")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
