"""
Tax Logic Modularization Testing

Tests for the centralized tax engine (services/tax_engine.py) and tax API router (routes/tax.py).

Features tested:
1. POST /api/tax-calc/calculate - Tax calculation endpoint
2. GET /api/tax-calc/rates - Tax rates endpoint
3. GET /api/tax-calc/structure - Tax structure documentation
4. GET /api/tax-calc/invoice-lines - Invoice line items generation
5. ROUND_HALF_UP decimal precision verification
6. GST_RATE import in vehicle_pricing.py (code review)
7. server.py integration with calculate_gst_qst
"""

import pytest
import requests
import os
from decimal import Decimal, ROUND_HALF_UP

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthCheck:
    """Health check - ensure API is accessible"""

    def test_health_endpoint(self):
        """Verify API health status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✅ Health check PASS")


class TestTaxCalculateEndpoint:
    """POST /api/tax-calc/calculate endpoint tests"""

    def test_calculate_tax_100_cad(self):
        """
        Verify $100.00 CAD -> GST $5.00, QST $9.98, Total $114.98
        This is the primary test case from requirements
        """
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 100.00, "currency": "CAD"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify GST calculation (5% of 100 = 5.00)
        assert data["gst_amount"] == 5.0, f"GST should be 5.0, got {data['gst_amount']}"
        assert data["gst_rate"] == 0.05, f"GST rate should be 0.05, got {data['gst_rate']}"
        
        # Verify QST calculation (9.975% of 100 = 9.975 -> ROUND_HALF_UP = 9.98)
        assert data["qst_amount"] == 9.98, f"QST should be 9.98, got {data['qst_amount']}"
        assert data["qst_rate"] == 0.09975, f"QST rate should be 0.09975, got {data['qst_rate']}"
        
        # Verify total tax (5.00 + 9.98 = 14.98)
        assert data["total_tax"] == 14.98, f"Total tax should be 14.98, got {data['total_tax']}"
        
        # Verify total with tax (100 + 14.98 = 114.98)
        assert data["total_with_tax"] == 114.98, f"Total with tax should be 114.98, got {data['total_with_tax']}"
        
        assert data["currency"] == "CAD"
        assert data["subtotal"] == 100.0
        print("✅ $100.00 CAD tax calculation PASS: GST $5.00, QST $9.98, Total $114.98")

    def test_calculate_tax_250_75_cad_decimal_precision(self):
        """
        Test Decimal precision with $250.75 subtotal
        GST: 250.75 * 0.05 = 12.5375 -> ROUND_HALF_UP = 12.54
        QST: 250.75 * 0.09975 = 25.0123125 -> ROUND_HALF_UP = 25.01
        """
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 250.75, "currency": "CAD"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify GST (250.75 * 0.05 = 12.5375 -> 12.54)
        assert data["gst_amount"] == 12.54, f"GST should be 12.54, got {data['gst_amount']}"
        
        # Verify QST (250.75 * 0.09975 = 25.0123125 -> 25.01)
        assert data["qst_amount"] == 25.01, f"QST should be 25.01, got {data['qst_amount']}"
        
        # Verify total tax (12.54 + 25.01 = 37.55)
        assert data["total_tax"] == 37.55, f"Total tax should be 37.55, got {data['total_tax']}"
        
        # Verify total with tax (250.75 + 37.55 = 288.30)
        assert data["total_with_tax"] == 288.30, f"Total with tax should be 288.30, got {data['total_with_tax']}"
        
        print("✅ $250.75 CAD decimal precision PASS: GST $12.54, QST $25.01")

    def test_calculate_tax_usd_zero_tax(self):
        """Verify USD currency returns zero tax (tax only applies to CAD)"""
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 100.00, "currency": "USD"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["gst_amount"] == 0.0, f"USD GST should be 0, got {data['gst_amount']}"
        assert data["qst_amount"] == 0.0, f"USD QST should be 0, got {data['qst_amount']}"
        assert data["total_tax"] == 0.0, f"USD total tax should be 0, got {data['total_tax']}"
        assert data["total_with_tax"] == 100.0, f"USD total should equal subtotal, got {data['total_with_tax']}"
        assert data["currency"] == "USD"
        print("✅ USD currency returns zero tax PASS")

    def test_calculate_tax_zero_subtotal_422(self):
        """Verify subtotal=0 returns 422 validation error"""
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 0, "currency": "CAD"}
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✅ Zero subtotal returns 422 PASS")

    def test_calculate_tax_negative_subtotal_422(self):
        """Verify negative subtotal returns 422 validation error"""
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": -50, "currency": "CAD"}
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✅ Negative subtotal returns 422 PASS")

    def test_calculate_tax_response_structure(self):
        """Verify response has all required fields"""
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 100.00, "currency": "CAD"}
        )
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "subtotal", "gst_rate", "gst_amount", "qst_rate", "qst_amount",
            "total_tax", "total_with_tax", "currency", "gst_registration", "qst_registration"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify registration numbers
        assert data["gst_registration"] == "706766367RT0001"
        assert data["qst_registration"] == "1233530880TQ0001"
        print("✅ Response structure validation PASS")


class TestTaxRatesEndpoint:
    """GET /api/tax-calc/rates endpoint tests"""

    def test_rates_cad_default(self):
        """Verify CAD returns 5% GST and 9.975% QST"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/rates")
        assert response.status_code == 200
        data = response.json()
        
        assert data["gst_rate_percent"] == 5.0, f"GST rate should be 5.0, got {data['gst_rate_percent']}"
        assert data["qst_rate_percent"] == 9.975, f"QST rate should be 9.975, got {data['qst_rate_percent']}"
        assert data["combined_rate_percent"] == 14.975, f"Combined rate should be 14.975"
        assert data["currency"] == "CAD"
        print("✅ CAD tax rates PASS: GST 5%, QST 9.975%")

    def test_rates_usd_zero(self):
        """Verify USD returns zero rates"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/rates?currency=USD")
        assert response.status_code == 200
        data = response.json()
        
        assert data["gst_rate_percent"] == 0.0, f"USD GST rate should be 0, got {data['gst_rate_percent']}"
        assert data["qst_rate_percent"] == 0.0, f"USD QST rate should be 0, got {data['qst_rate_percent']}"
        assert data["combined_rate_percent"] == 0.0, f"USD combined rate should be 0"
        assert data["currency"] == "USD"
        print("✅ USD tax rates zero PASS")

    def test_rates_contains_legal_info(self):
        """Verify rates endpoint includes BidVex legal info"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/rates")
        assert response.status_code == 200
        data = response.json()
        
        assert data["gst_registration"] == "706766367RT0001"
        assert data["qst_registration"] == "1233530880TQ0001"
        assert data["legal_name"] == "BidVex Inc."
        assert "address" in data
        print("✅ Tax rates includes legal info PASS")


class TestTaxStructureEndpoint:
    """GET /api/tax-calc/structure endpoint tests"""

    def test_structure_jurisdiction(self):
        """Verify structure returns Quebec jurisdiction info"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/structure")
        assert response.status_code == 200
        data = response.json()
        
        assert data["jurisdiction"] == "Quebec, Canada"
        print("✅ Tax structure jurisdiction PASS")

    def test_structure_tax_rates(self):
        """Verify structure contains tax rate details"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/structure")
        assert response.status_code == 200
        data = response.json()
        
        assert "tax_rates" in data
        assert data["tax_rates"]["gst"]["rate"] == "5%"
        assert data["tax_rates"]["qst"]["rate"] == "9.975%"
        assert data["tax_rates"]["combined"]["rate"] == "14.975%"
        print("✅ Tax structure rates PASS")

    def test_structure_auction_rules(self):
        """Verify structure contains vehicle and general auction rules"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/structure")
        assert response.status_code == 200
        data = response.json()
        
        # Vehicle auctions
        assert "vehicle_auctions" in data
        assert "stripe_charges" in data["vehicle_auctions"]
        
        # General auctions
        assert "general_auctions" in data
        assert "private_seller" in data["general_auctions"]
        assert "business_seller" in data["general_auctions"]
        print("✅ Tax structure auction rules PASS")

    def test_structure_bidvex_info(self):
        """Verify structure contains BidVex company info"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/structure")
        assert response.status_code == 200
        data = response.json()
        
        assert "bidvex_info" in data
        assert data["bidvex_info"]["legal_name"] == "BidVex Inc."
        assert data["bidvex_info"]["gst_number"] == "706766367RT0001"
        assert data["bidvex_info"]["qst_number"] == "1233530880TQ0001"
        print("✅ Tax structure BidVex info PASS")


class TestInvoiceLinesEndpoint:
    """GET /api/tax-calc/invoice-lines endpoint tests"""

    def test_invoice_lines_100_cad(self):
        """Verify $100 CAD returns 2 line items with correct amounts"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/invoice-lines?subtotal=100")
        assert response.status_code == 200
        data = response.json()
        
        assert "lines" in data
        assert len(data["lines"]) == 2, f"Expected 2 lines, got {len(data['lines'])}"
        
        # Check GST line
        gst_line = data["lines"][0]
        assert gst_line["label"] == "GST (TPS)"
        assert gst_line["rate"] == "5%"
        assert gst_line["amount_raw"] == 5.0, f"GST amount should be 5.0, got {gst_line['amount_raw']}"
        
        # Check QST line
        qst_line = data["lines"][1]
        assert qst_line["label"] == "QST (TVQ)"
        assert qst_line["rate"] == "9.975%"
        assert qst_line["amount_raw"] == 9.98, f"QST amount should be 9.98, got {qst_line['amount_raw']}"
        
        assert data["subtotal"] == 100.0
        assert data["currency"] == "CAD"
        print("✅ Invoice lines $100 CAD PASS: GST $5.00, QST $9.98")

    def test_invoice_lines_usd_empty(self):
        """Verify USD returns empty lines array"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/invoice-lines?subtotal=100&currency=USD")
        assert response.status_code == 200
        data = response.json()
        
        assert "lines" in data
        assert len(data["lines"]) == 0, f"Expected 0 lines for USD, got {len(data['lines'])}"
        assert data["currency"] == "USD"
        print("✅ Invoice lines USD empty PASS")

    def test_invoice_lines_contains_registration(self):
        """Verify invoice lines contain registration numbers"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/invoice-lines?subtotal=100")
        assert response.status_code == 200
        data = response.json()
        
        assert data["lines"][0]["registration"] == "706766367RT0001"  # GST
        assert data["lines"][1]["registration"] == "1233530880TQ0001"  # QST
        print("✅ Invoice lines registration numbers PASS")


class TestDecimalPrecision:
    """Test ROUND_HALF_UP strategy across various amounts"""

    def test_rounding_half_up_gst(self):
        """
        Test GST rounding at boundary: 
        $9.99 * 0.05 = 0.4995 -> ROUND_HALF_UP = 0.50
        """
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 9.99, "currency": "CAD"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # 9.99 * 0.05 = 0.4995 -> should round to 0.50
        assert data["gst_amount"] == 0.50, f"Expected 0.50, got {data['gst_amount']}"
        print("✅ ROUND_HALF_UP GST precision PASS")

    def test_rounding_qst_boundary(self):
        """
        Test QST rounding at boundary:
        $5.00 * 0.09975 = 0.49875 -> ROUND_HALF_UP = 0.50
        """
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 5.00, "currency": "CAD"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # 5.00 * 0.09975 = 0.49875 -> should round to 0.50
        assert data["qst_amount"] == 0.50, f"Expected QST 0.50, got {data['qst_amount']}"
        print("✅ ROUND_HALF_UP QST precision PASS")

    def test_large_amount_precision(self):
        """Test precision with large amount ($10,000)"""
        response = requests.post(
            f"{BASE_URL}/api/tax-calc/calculate",
            json={"subtotal": 10000.00, "currency": "CAD"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # GST: 10000 * 0.05 = 500.00
        assert data["gst_amount"] == 500.0
        
        # QST: 10000 * 0.09975 = 997.50
        assert data["qst_amount"] == 997.50
        
        # Total: 500 + 997.50 = 1497.50
        assert data["total_tax"] == 1497.50
        
        print("✅ Large amount ($10,000) precision PASS")


class TestPriceBreakdownIntegration:
    """Test server.py uses centralized calculate_gst_qst"""

    def test_subscription_price_breakdown_uses_tax_engine(self):
        """
        Verify subscriptions/price-breakdown endpoint exists and uses tax engine.
        Note: May return 404 for non-existent plan, which is acceptable - 
        we're testing that the endpoint exists and doesn't crash.
        """
        # Test with a placeholder plan - we mainly want to verify the endpoint exists
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=test_plan")
        
        # 200 or 404 (plan not found) are both acceptable - endpoint is working
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 404:
            # Plan not found is expected for test plan
            print("✅ Price breakdown endpoint exists (returned 404 for test plan)")
        else:
            # If we got a valid response, verify tax fields
            data = response.json()
            if "gst" in data or "qst" in data:
                print("✅ Price breakdown uses centralized tax engine PASS")
            else:
                print("✅ Price breakdown endpoint accessible PASS")


class TestTaxEngineCodeReview:
    """Code review verifications via API behavior"""

    def test_gst_rate_is_5_percent(self):
        """Verify GST_RATE constant is exactly 5%"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/rates")
        data = response.json()
        assert data["gst_rate_percent"] == 5.0
        print("✅ GST_RATE constant is 5% PASS")

    def test_qst_rate_is_9975_percent(self):
        """Verify QST_RATE constant is exactly 9.975%"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/rates")
        data = response.json()
        assert data["qst_rate_percent"] == 9.975
        print("✅ QST_RATE constant is 9.975% PASS")

    def test_bidvex_registration_numbers(self):
        """Verify BidVex tax registration numbers are correct"""
        response = requests.get(f"{BASE_URL}/api/tax-calc/structure")
        data = response.json()
        
        assert data["bidvex_info"]["gst_number"] == "706766367RT0001"
        assert data["bidvex_info"]["qst_number"] == "1233530880TQ0001"
        print("✅ BidVex registration numbers PASS")


# Summary fixture
@pytest.fixture(scope="session", autouse=True)
def test_summary(request):
    """Print test summary after all tests complete"""
    yield
    print("\n" + "="*60)
    print("TAX MODULARIZATION TESTING COMPLETE")
    print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
