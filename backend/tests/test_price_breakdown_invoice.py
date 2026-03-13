"""
Test price breakdown with Stripe processing fee and branded PDF invoice features.
Features tested:
1. GET /api/subscriptions/price-breakdown - price with GST, QST, and processing fee
2. GET /api/invoices - list subscription invoices (excluding pdf_data)
3. GET /api/invoices/{invoice_id}/download - download branded PDF invoice
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if BASE_URL:
    BASE_URL = BASE_URL.rstrip('/')


class TestPriceBreakdown:
    """Test price breakdown endpoint with Stripe processing fee calculation."""

    def test_premium_price_breakdown(self):
        """Test Premium plan price breakdown - subtotal: 180, GST 5%, QST 9.975%, processing fee ~6.49"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=premium")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify structure
        assert "plan_id" in data
        assert "subtotal" in data
        assert "gst" in data
        assert "qst" in data
        assert "processing_fee" in data
        assert "total" in data
        
        # Verify Premium pricing - subtotal 180
        assert data["plan_id"] == "premium"
        assert data["subtotal"] == 180, f"Expected subtotal 180, got {data['subtotal']}"
        
        # GST = 180 * 0.05 = 9.0
        assert data["gst"] == 9.0, f"Expected GST 9.0, got {data['gst']}"
        
        # QST = 180 * 0.09975 = 17.955 -> 17.96 rounded
        assert abs(data["qst"] - 17.96) < 0.01, f"Expected QST ~17.96, got {data['qst']}"
        
        # Amount after tax = 180 + 9 + 17.96 = 206.96
        amount_after_tax = data["subtotal"] + data["gst"] + data["qst"]
        
        # Processing fee calculation: (amount + 0.30) / (1 - 0.029) - amount
        # = (206.96 + 0.30) / 0.971 - 206.96 = 213.45 - 206.96 = 6.49
        assert data["processing_fee"] > 6, f"Processing fee should be > 6, got {data['processing_fee']}"
        assert data["processing_fee"] < 7, f"Processing fee should be < 7, got {data['processing_fee']}"
        
        # Total = amount_after_tax + processing_fee ~= 213.45
        assert data["total"] > 213, f"Total should be > 213, got {data['total']}"
        assert data["total"] < 214, f"Total should be < 214, got {data['total']}"
        
        print(f"Premium breakdown: subtotal={data['subtotal']}, gst={data['gst']}, qst={data['qst']}, fee={data['processing_fee']}, total={data['total']}")

    def test_vip_price_breakdown(self):
        """Test VIP plan price breakdown - subtotal: 300, GST 5%, QST 9.975%, processing fee ~10.61"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=vip")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify VIP pricing - subtotal 300
        assert data["plan_id"] == "vip"
        assert data["subtotal"] == 300, f"Expected subtotal 300, got {data['subtotal']}"
        
        # GST = 300 * 0.05 = 15.0
        assert data["gst"] == 15.0, f"Expected GST 15.0, got {data['gst']}"
        
        # QST = 300 * 0.09975 = 29.925 -> 29.93 rounded
        assert abs(data["qst"] - 29.93) < 0.01, f"Expected QST ~29.93, got {data['qst']}"
        
        # Amount after tax = 300 + 15 + 29.93 = 344.93
        # Processing fee: (344.93 + 0.30) / 0.971 - 344.93 = 355.54 - 344.93 = 10.61
        assert data["processing_fee"] > 10, f"Processing fee should be > 10, got {data['processing_fee']}"
        assert data["processing_fee"] < 11, f"Processing fee should be < 11, got {data['processing_fee']}"
        
        # Total ~= 355.54
        assert data["total"] > 355, f"Total should be > 355, got {data['total']}"
        assert data["total"] < 356, f"Total should be < 356, got {data['total']}"
        
        print(f"VIP breakdown: subtotal={data['subtotal']}, gst={data['gst']}, qst={data['qst']}, fee={data['processing_fee']}, total={data['total']}")

    def test_starter_free_plan_breakdown(self):
        """Test Starter/Free plan - should return 0 for all amounts"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=free")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["subtotal"] == 0
        assert data["gst"] == 0
        assert data["qst"] == 0
        assert data["processing_fee"] == 0
        assert data["total"] == 0
        print("Free/Starter plan breakdown: all zeros - correct")

    def test_invalid_plan_returns_404(self):
        """Test that invalid plan_id returns 404"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=invalid")
        assert response.status_code == 404, f"Expected 404 for invalid plan, got {response.status_code}"


class TestInvoicesEndpoint:
    """Test invoices list and download endpoints."""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")

    def test_list_invoices_authenticated(self, auth_token):
        """Test GET /api/invoices returns invoices list without pdf_data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/invoices", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "invoices" in data, "Response should contain 'invoices' key"
        
        invoices = data["invoices"]
        print(f"Found {len(invoices)} invoices for user")
        
        if len(invoices) > 0:
            # Check first invoice structure
            inv = invoices[0]
            assert "id" in inv, "Invoice should have 'id'"
            assert "invoice_number" in inv, "Invoice should have 'invoice_number'"
            assert "pdf_data" not in inv, "Invoice should NOT contain 'pdf_data' (binary excluded)"
            print(f"Invoice: {inv.get('invoice_number')} - ${inv.get('total', 'N/A')} CAD")
            
            # Store invoice_id for download test
            pytest.shared_invoice_id = inv["id"]
            pytest.shared_invoice_number = inv.get("invoice_number")
        else:
            pytest.skip("No invoices found for user - cannot test download")
        
        return invoices

    def test_list_invoices_unauthenticated(self):
        """Test GET /api/invoices without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/invoices")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    def test_download_invoice_pdf(self, auth_token):
        """Test GET /api/invoices/{invoice_id}/download returns PDF"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # First get an invoice ID
        list_response = requests.get(f"{BASE_URL}/api/invoices", headers=headers)
        if list_response.status_code != 200:
            pytest.skip("Cannot list invoices")
        
        invoices = list_response.json().get("invoices", [])
        if len(invoices) == 0:
            pytest.skip("No invoices to download")
        
        invoice_id = invoices[0]["id"]
        invoice_number = invoices[0].get("invoice_number", "invoice")
        
        # Download PDF
        response = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}/download", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify Content-Type is application/pdf
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
        
        # Verify Content-Disposition header
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment header, got {content_disp}"
        
        # Verify PDF starts with PDF magic bytes
        pdf_bytes = response.content
        assert pdf_bytes[:4] == b'%PDF', "Response should be valid PDF (starts with %PDF)"
        
        print(f"Downloaded invoice {invoice_number}: {len(pdf_bytes)} bytes, valid PDF")

    def test_download_nonexistent_invoice(self, auth_token):
        """Test downloading non-existent invoice returns 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/invoices/nonexistent-uuid/download", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestStripeProcessingFeeFormula:
    """Verify the fee-on-top formula is correctly implemented."""

    def test_fee_formula_mathematically(self):
        """Verify: total = (amount + 0.30) / (1 - 0.029), fee = total - amount"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=premium")
        data = response.json()
        
        # Calculate expected fee
        amount_after_tax = data["subtotal"] + data["gst"] + data["qst"]
        expected_total = round((amount_after_tax + 0.30) / (1 - 0.029), 2)
        expected_fee = round(expected_total - amount_after_tax, 2)
        
        # Verify API returns same values
        assert abs(data["processing_fee"] - expected_fee) < 0.02, f"Fee mismatch: expected {expected_fee}, got {data['processing_fee']}"
        assert abs(data["total"] - expected_total) < 0.02, f"Total mismatch: expected {expected_total}, got {data['total']}"
        
        print(f"Fee formula verified: amount={amount_after_tax}, fee={expected_fee}, total={expected_total}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
