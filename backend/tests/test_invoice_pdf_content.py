"""
Test PDF Invoice Content - Verifies dynamic PDF regeneration fix
Tests:
- PDF download returns valid PDF with correct content-type
- PDF contains correct address: '103-761 Chalifoux'
- PDF contains correct GST number: '706766367RT0001'
- PDF contains correct QST number: '1233530880TQ0001'
- PDF contains logo image
- Price breakdown endpoint returns correct tax values
"""
import pytest
import requests
import os
import tempfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPriceBreakdown:
    """Test price breakdown endpoint returns correct tax calculations"""
    
    def test_premium_price_breakdown(self):
        """GET /api/subscriptions/price-breakdown?plan_id=premium returns correct values"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=premium")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["plan_id"] == "premium"
        assert data["subtotal"] == 180, f"Expected subtotal 180, got {data['subtotal']}"
        assert data["gst"] == 9.0, f"Expected gst 9.0, got {data['gst']}"
        assert data["qst"] == 17.96, f"Expected qst 17.96, got {data['qst']}"
        assert "processing_fee" in data
        assert "total" in data
        print(f"PASS: Premium price breakdown - subtotal={data['subtotal']}, gst={data['gst']}, qst={data['qst']}")
    
    def test_vip_price_breakdown(self):
        """GET /api/subscriptions/price-breakdown?plan_id=vip returns correct values"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=vip")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["plan_id"] == "vip"
        assert data["subtotal"] == 300, f"Expected subtotal 300, got {data['subtotal']}"
        assert data["gst"] == 15.0, f"Expected gst 15.0, got {data['gst']}"
        assert data["qst"] == 29.93, f"Expected qst 29.93, got {data['qst']}"
        print(f"PASS: VIP price breakdown - subtotal={data['subtotal']}, gst={data['gst']}, qst={data['qst']}")


class TestInvoicePDFContent:
    """Test invoice PDF download returns valid PDF with correct branding content"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Auth failed: {response.status_code} - {response.text}"
        return response.json().get("access_token")
    
    def test_invoice_download_returns_valid_pdf(self, auth_token):
        """GET /api/invoices/{invoice_id}/download returns valid PDF"""
        invoice_id = "3b986cca-bf4a-4391-a825-32e4c6d2264c"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/invoices/{invoice_id}/download",
            headers=headers
        )
        
        assert response.status_code == 200, f"Download failed: {response.status_code}"
        assert response.headers.get("Content-Type") == "application/pdf", \
            f"Wrong content-type: {response.headers.get('Content-Type')}"
        assert len(response.content) > 1000, f"PDF too small: {len(response.content)} bytes"
        print(f"PASS: PDF download successful - {len(response.content)} bytes, Content-Type: application/pdf")
    
    def test_pdf_contains_correct_address(self, auth_token):
        """PDF contains official address '103-761 Chalifoux'"""
        import fitz  # pymupdf
        
        invoice_id = "3b986cca-bf4a-4391-a825-32e4c6d2264c"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/invoices/{invoice_id}/download",
            headers=headers
        )
        assert response.status_code == 200
        
        # Write PDF to temp file and extract text
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(response.content)
            temp_path = f.name
        
        try:
            doc = fitz.open(temp_path)
            text = doc[0].get_text()
            doc.close()
            
            assert "103-761 Chalifoux" in text, f"Address '103-761 Chalifoux' not found in PDF text: {text[:500]}"
            print(f"PASS: PDF contains correct address '103-761 Chalifoux'")
        finally:
            os.unlink(temp_path)
    
    def test_pdf_contains_correct_gst_number(self, auth_token):
        """PDF contains GST number '706766367RT0001'"""
        import fitz
        
        invoice_id = "3b986cca-bf4a-4391-a825-32e4c6d2264c"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/invoices/{invoice_id}/download",
            headers=headers
        )
        assert response.status_code == 200
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(response.content)
            temp_path = f.name
        
        try:
            doc = fitz.open(temp_path)
            text = doc[0].get_text()
            doc.close()
            
            assert "706766367RT0001" in text, f"GST number '706766367RT0001' not found in PDF text: {text[:500]}"
            print(f"PASS: PDF contains correct GST number '706766367RT0001'")
        finally:
            os.unlink(temp_path)
    
    def test_pdf_contains_correct_qst_number(self, auth_token):
        """PDF contains QST number '1233530880TQ0001'"""
        import fitz
        
        invoice_id = "3b986cca-bf4a-4391-a825-32e4c6d2264c"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/invoices/{invoice_id}/download",
            headers=headers
        )
        assert response.status_code == 200
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(response.content)
            temp_path = f.name
        
        try:
            doc = fitz.open(temp_path)
            text = doc[0].get_text()
            doc.close()
            
            assert "1233530880TQ0001" in text, f"QST number '1233530880TQ0001' not found in PDF text: {text[:500]}"
            print(f"PASS: PDF contains correct QST number '1233530880TQ0001'")
        finally:
            os.unlink(temp_path)
    
    def test_pdf_contains_logo_image(self, auth_token):
        """PDF contains logo image (page.get_images() returns non-empty)"""
        import fitz
        
        invoice_id = "3b986cca-bf4a-4391-a825-32e4c6d2264c"
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/invoices/{invoice_id}/download",
            headers=headers
        )
        assert response.status_code == 200
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(response.content)
            temp_path = f.name
        
        try:
            doc = fitz.open(temp_path)
            images = doc[0].get_images()
            doc.close()
            
            assert len(images) > 0, f"No images found in PDF (expected logo)"
            print(f"PASS: PDF contains {len(images)} image(s) (logo)")
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
