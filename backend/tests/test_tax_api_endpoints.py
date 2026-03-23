"""
API Endpoint Tests for Quebec Tax & Payment Calculator
Tests the /api/payments/tax/* endpoints for the Total Cost Calculator feature

Endpoints tested:
- POST /api/payments/tax/calculate - Main calculation endpoint
- GET /api/payments/tax/vehicle - Vehicle-specific calculations  
- GET /api/payments/tax/general - General auction calculations
- GET /api/payments/tax/rates - Quebec tax rates

Quebec Tax Rates:
- GST (Federal): 5%
- QST (Provincial): 9.975%
- Combined: 14.975%
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-fix-critical.preview.emergentagent.com')


class TestTaxRatesEndpoint:
    """Tests for GET /api/payments/tax/rates"""
    
    def test_get_tax_rates_status(self):
        """Test tax rates endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/payments/tax/rates")
        assert response.status_code == 200
    
    def test_tax_rates_gst_value(self):
        """Test GST rate is 5%"""
        response = requests.get(f"{BASE_URL}/api/payments/tax/rates")
        data = response.json()
        
        assert "gst" in data
        assert data["gst"]["rate"] == 0.05
        assert data["gst"]["rate_display"] == "5%"
    
    def test_tax_rates_qst_value(self):
        """Test QST rate is 9.975%"""
        response = requests.get(f"{BASE_URL}/api/payments/tax/rates")
        data = response.json()
        
        assert "qst" in data
        assert data["qst"]["rate"] == 0.09975
        assert data["qst"]["rate_display"] == "9.975%"
    
    def test_tax_rates_combined(self):
        """Test combined rate is 14.975%"""
        response = requests.get(f"{BASE_URL}/api/payments/tax/rates")
        data = response.json()
        
        assert "combined" in data
        assert data["combined"]["rate"] == 0.14975
        assert data["combined"]["rate_display"] == "14.975%"
    
    def test_tax_rates_jurisdiction(self):
        """Test jurisdiction is Quebec"""
        response = requests.get(f"{BASE_URL}/api/payments/tax/rates")
        data = response.json()
        
        assert data["jurisdiction"] == "Quebec, Canada"


class TestTaxCalculateEndpoint:
    """Tests for POST /api/payments/tax/calculate"""
    
    def test_calculate_general_private_seller(self):
        """Test general auction with private seller (no hammer tax)"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyer_tier": "basic",
                "seller_tier": "basic",
                "seller_is_business": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify payment type
        assert data["payment_type"] == "general"
        
        # Private seller - no hammer tax
        assert data["hammer_tax_applicable"] == False
        assert data["hammer_tax_total"] == 0.0
        
        # Buyer premium 5% = $50
        assert data["buyer_premium"] == 50.0
        assert data["buyer_premium_rate"] == 0.05
    
    def test_calculate_general_business_seller(self):
        """Test general auction with business seller (hammer price taxed)"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyer_tier": "basic",
                "seller_is_business": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Business seller - hammer IS taxed
        assert data["hammer_tax_applicable"] == True
        assert data["hammer_gst"] == 50.0  # 5% of $1000
        assert data["hammer_qst"] == 99.75  # 9.975% of $1000
        assert data["hammer_tax_total"] == 149.75
        
        # Buyer total should include hammer tax
        assert data["buyer_total"] == 1207.24  # $1000 + $50 + $149.75 + $7.49
    
    def test_calculate_vehicle_auction(self):
        """Test vehicle auction (only fees charged via Stripe)"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 10000,
                "category": "vehicle",
                "buyer_tier": "basic"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify vehicle payment type
        assert data["payment_type"] == "vehicle"
        assert "BidVex fees charged via Stripe" in data["description"]
        
        # Buyer premium 5% + Platform fee 2.5% on $10,000
        assert data["buyer_premium"] == 500.0
        assert data["platform_fee"] == 250.0
        assert data["bidvex_fees_subtotal"] == 750.0
        
        # Only fees are taxed
        assert data["bidvex_fees_gst"] == 37.5
        assert data["bidvex_fees_qst"] == 74.81
        
        # Seller gets full hammer price via Bank Draft
        assert data["seller_balance_due"] == 10000.0
        
        # Stripe only charges fees + tax
        assert data["stripe_charge_total"] == 862.31
    
    def test_calculate_vehicle_with_car_category(self):
        """Test that 'car' category triggers vehicle payment"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 5000,
                "category": "car"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["payment_type"] == "vehicle"
    
    def test_calculate_vehicle_with_motorcycle_category(self):
        """Test that 'motorcycle' category triggers vehicle payment"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 5000,
                "category": "motorcycle"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["payment_type"] == "vehicle"


class TestVehicleEndpoint:
    """Tests for GET /api/payments/tax/vehicle"""
    
    def test_vehicle_endpoint_status(self):
        """Test vehicle endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={"price": 10000, "buyer_tier": "basic"}
        )
        assert response.status_code == 200
    
    def test_vehicle_payment_method(self):
        """Test vehicle payment is hybrid (Stripe + Bank Draft)"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={"price": 10000}
        )
        data = response.json()
        
        assert data["auction_type"] == "vehicle"
        assert data["payment_method"] == "hybrid"
        assert "Bank Draft" in data["description"]
    
    def test_vehicle_premium_tier(self):
        """Test vehicle with premium tier (3.5% buyer premium)"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={"price": 10000, "buyer_tier": "premium"}
        )
        data = response.json()
        
        assert data["buyer_premium_rate"] == 0.035
        assert data["buyer_premium"] == 350.0
    
    def test_vehicle_vip_tier(self):
        """Test vehicle with VIP tier (3% buyer premium)"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={"price": 10000, "buyer_tier": "vip"}
        )
        data = response.json()
        
        assert data["buyer_premium_rate"] == 0.03
        assert data["buyer_premium"] == 300.0
    
    def test_vehicle_stripe_charge(self):
        """Test Stripe only charges fees (not hammer price)"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={"price": 25000, "buyer_tier": "basic"}
        )
        data = response.json()
        
        # Fees: 5% + 2.5% = $1875
        # Tax on fees: $1875 * 14.975% = $280.78
        # Stripe total = $2155.78
        assert data["stripe_charge_total"] == 2155.78
        
        # Seller balance (Bank Draft) = full hammer price
        assert data["seller_balance_due"] == 25000.0


class TestGeneralEndpoint:
    """Tests for GET /api/payments/tax/general"""
    
    def test_general_endpoint_status(self):
        """Test general endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/general",
            params={"price": 1000}
        )
        assert response.status_code == 200
    
    def test_general_payment_method(self):
        """Test general payment is full Stripe"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/general",
            params={"price": 1000}
        )
        data = response.json()
        
        assert data["auction_type"] == "general"
        assert data["payment_method"] == "stripe_full"
    
    def test_general_private_seller_no_tax(self):
        """Test private seller doesn't trigger hammer tax"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/general",
            params={"price": 1000, "seller_is_business": False}
        )
        data = response.json()
        
        assert data["hammer_tax_applicable"] == False
        assert data["hammer_tax_total"] == 0.0
    
    def test_general_business_seller_with_tax(self):
        """Test business seller triggers 14.975% hammer tax"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/general",
            params={"price": 1000, "seller_is_business": True}
        )
        data = response.json()
        
        assert data["hammer_tax_applicable"] == True
        assert data["hammer_gst"] == 50.0
        assert data["hammer_qst"] == 99.75
        assert data["hammer_tax_total"] == 149.75
    
    def test_general_different_tiers(self):
        """Test different buyer/seller tier combinations"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/general",
            params={
                "price": 1000,
                "buyer_tier": "vip",
                "seller_tier": "premium"
            }
        )
        data = response.json()
        
        # VIP buyer: 3% premium
        assert data["buyer_premium_rate"] == 0.03
        # Premium seller: 2.5% commission
        assert data["seller_commission_rate"] == 0.025


class TestBuyerCostCalculations:
    """Test buyer cost calculations are correct"""
    
    def test_private_seller_1000(self):
        """Test buyer total for $1000 item with private seller"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "seller_is_business": False
            }
        )
        data = response.json()
        
        # $1000 + $50 premium + $7.49 tax on premium = $1057.49
        assert data["buyer_total"] == 1057.49
    
    def test_business_seller_1000(self):
        """Test buyer total for $1000 item with business seller"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "seller_is_business": True
            }
        )
        data = response.json()
        
        # $1000 + $149.75 hammer tax + $50 premium + $7.49 fee tax = $1207.24
        assert data["buyer_total"] == 1207.24
    
    def test_vehicle_buyer_cost(self):
        """Test buyer cost for vehicle (only fees paid online)"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 10000,
                "category": "vehicle"
            }
        )
        data = response.json()
        
        # Stripe charge = fees + tax = $862.31
        # Plus seller balance via Bank Draft = $10,000
        # Total out of pocket = $10,862.31
        assert data["stripe_charge_total"] == 862.31
        assert data["seller_balance_due"] == 10000.0


class TestInvoiceLines:
    """Test invoice line generation"""
    
    def test_vehicle_invoice_has_bank_draft_line(self):
        """Test vehicle invoice includes Bank Draft payment line"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={"price": 10000}
        )
        data = response.json()
        
        descriptions = [line["description"] for line in data["invoice_lines"]]
        assert "Balance Due to Seller (via Bank Draft)" in descriptions
    
    def test_general_invoice_has_sections(self):
        """Test general invoice has proper sections"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/general",
            params={"price": 1000, "seller_is_business": True}
        )
        data = response.json()
        
        sections = [line.get("section") for line in data["invoice_lines"] if "section" in line]
        assert "Item Sale" in sections
        assert "Platform Service Fees" in sections


class TestEdgeCases:
    """Test edge cases"""
    
    def test_small_amount(self):
        """Test calculation with small amount"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={"hammer_price": 10, "category": "general"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hammer_price"] == 10.0
    
    def test_large_amount(self):
        """Test calculation with large amount"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={"hammer_price": 500000, "category": "vehicle"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hammer_price"] == 500000.0
        assert data["seller_balance_due"] == 500000.0
    
    def test_invalid_price(self):
        """Test validation rejects invalid price"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={"hammer_price": -100, "category": "general"}
        )
        # Should return 422 validation error
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
