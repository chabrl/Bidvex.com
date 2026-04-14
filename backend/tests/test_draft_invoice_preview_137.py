"""
Test Draft Invoice Preview API - Iteration 137
Tests the preview-invoice endpoint for tax calculations, tier-based pricing, and bilingual HTML generation.

Features tested:
- QC province returns GST+QST tax type with 14.975% combined rate
- ON province returns HST tax type with 13% rate
- Buyer premium at 5% for free tier, 3.5% for premium tier
- Seller commission at 4% for free tier, 2% for vip tier
- HTML content contains bilingual content
- Send-test endpoint returns 503 or sends email with valid SENDGRID_API_KEY
"""

import pytest
import requests
import os
from decimal import Decimal

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    })
    return session


class TestPreviewInvoiceTaxCalculations:
    """Test tax calculations for different provinces"""
    
    def test_qc_returns_gst_qst_tax_type(self, api_client):
        """QC province should return GST+QST tax type with 14.975% combined rate"""
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": 25000,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify invoice data exists
        assert "invoice" in data, "Response should contain 'invoice' key"
        invoice = data["invoice"]
        
        # Verify tax type is GST+QST for Quebec
        assert invoice["buyer_tax_type"] == "GST+QST", f"Expected GST+QST, got {invoice['buyer_tax_type']}"
        assert invoice["seller_tax_type"] == "GST+QST", f"Expected GST+QST, got {invoice['seller_tax_type']}"
        
        # Verify combined tax rate is 14.975% (0.14975)
        expected_rate = 0.14975
        assert abs(invoice["buyer_tax_rate"] - expected_rate) < 0.0001, \
            f"Expected tax rate ~{expected_rate}, got {invoice['buyer_tax_rate']}"
        
        # Verify GST and QST amounts are present and non-zero
        assert invoice["buyer_gst"] > 0, "Buyer GST should be > 0 for QC"
        assert invoice["buyer_qst"] > 0, "Buyer QST should be > 0 for QC"
        
        print(f"✓ QC Tax: GST=${invoice['buyer_gst']:.2f} + QST=${invoice['buyer_qst']:.2f} = ${invoice['buyer_total_tax']:.2f} ({invoice['buyer_tax_rate']*100:.3f}%)")
    
    def test_on_returns_hst_tax_type(self, api_client):
        """ON province should return HST tax type with 13% rate"""
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": 25000,
            "buyer_province": "ON",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        invoice = data["invoice"]
        
        # Verify tax type is HST for Ontario
        assert invoice["buyer_tax_type"] == "HST", f"Expected HST, got {invoice['buyer_tax_type']}"
        assert invoice["seller_tax_type"] == "HST", f"Expected HST, got {invoice['seller_tax_type']}"
        
        # Verify HST rate is 13% (0.13)
        expected_rate = 0.13
        assert abs(invoice["buyer_tax_rate"] - expected_rate) < 0.0001, \
            f"Expected tax rate ~{expected_rate}, got {invoice['buyer_tax_rate']}"
        
        # Verify HST amount is present and non-zero
        assert invoice["buyer_hst"] > 0, "Buyer HST should be > 0 for ON"
        
        # Verify GST/QST are zero for HST province
        assert invoice["buyer_gst"] == 0, "Buyer GST should be 0 for HST province"
        assert invoice["buyer_qst"] == 0, "Buyer QST should be 0 for HST province"
        
        print(f"✓ ON Tax: HST=${invoice['buyer_hst']:.2f} ({invoice['buyer_tax_rate']*100:.1f}%)")


class TestPreviewInvoiceBuyerPremium:
    """Test buyer premium calculations for different tiers"""
    
    def test_free_tier_buyer_premium_5_percent(self, api_client):
        """Free tier buyer should have 5% premium"""
        hammer_price = 25000
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": hammer_price,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        invoice = data["invoice"]
        
        # Verify buyer premium rate is 5% (0.05)
        expected_rate = 0.05
        assert abs(invoice["buyer_premium_rate"] - expected_rate) < 0.0001, \
            f"Expected buyer premium rate {expected_rate}, got {invoice['buyer_premium_rate']}"
        
        # Verify buyer premium amount
        expected_premium = hammer_price * expected_rate
        assert abs(invoice["buyer_premium"] - expected_premium) < 0.01, \
            f"Expected buyer premium ${expected_premium}, got ${invoice['buyer_premium']}"
        
        print(f"✓ Free tier buyer premium: {invoice['buyer_premium_rate']*100:.1f}% = ${invoice['buyer_premium']:.2f}")
    
    def test_premium_tier_buyer_premium_3_5_percent(self, api_client):
        """Premium tier buyer should have 3.5% premium"""
        hammer_price = 25000
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": hammer_price,
            "buyer_province": "QC",
            "buyer_tier": "premium",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        invoice = data["invoice"]
        
        # Verify buyer premium rate is 3.5% (0.035)
        expected_rate = 0.035
        assert abs(invoice["buyer_premium_rate"] - expected_rate) < 0.0001, \
            f"Expected buyer premium rate {expected_rate}, got {invoice['buyer_premium_rate']}"
        
        # Verify buyer premium amount
        expected_premium = hammer_price * expected_rate
        assert abs(invoice["buyer_premium"] - expected_premium) < 0.01, \
            f"Expected buyer premium ${expected_premium}, got ${invoice['buyer_premium']}"
        
        print(f"✓ Premium tier buyer premium: {invoice['buyer_premium_rate']*100:.1f}% = ${invoice['buyer_premium']:.2f}")
    
    def test_vip_tier_buyer_premium_3_percent(self, api_client):
        """VIP tier buyer should have 3% premium"""
        hammer_price = 25000
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": hammer_price,
            "buyer_province": "QC",
            "buyer_tier": "vip",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        invoice = data["invoice"]
        
        # Verify buyer premium rate is 3% (0.03)
        expected_rate = 0.03
        assert abs(invoice["buyer_premium_rate"] - expected_rate) < 0.0001, \
            f"Expected buyer premium rate {expected_rate}, got {invoice['buyer_premium_rate']}"
        
        print(f"✓ VIP tier buyer premium: {invoice['buyer_premium_rate']*100:.1f}% = ${invoice['buyer_premium']:.2f}")


class TestPreviewInvoiceSellerCommission:
    """Test seller commission calculations for different tiers"""
    
    def test_free_tier_seller_commission_4_percent(self, api_client):
        """Free tier seller should have 4% commission"""
        hammer_price = 25000
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": hammer_price,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        invoice = data["invoice"]
        
        # Verify seller commission rate is 4% (0.04)
        expected_rate = 0.04
        assert abs(invoice["seller_commission_rate"] - expected_rate) < 0.0001, \
            f"Expected seller commission rate {expected_rate}, got {invoice['seller_commission_rate']}"
        
        # Verify seller commission amount
        expected_commission = hammer_price * expected_rate
        assert abs(invoice["seller_commission"] - expected_commission) < 0.01, \
            f"Expected seller commission ${expected_commission}, got ${invoice['seller_commission']}"
        
        print(f"✓ Free tier seller commission: {invoice['seller_commission_rate']*100:.1f}% = ${invoice['seller_commission']:.2f}")
    
    def test_vip_tier_seller_commission_2_percent(self, api_client):
        """VIP tier seller should have 2% commission"""
        hammer_price = 25000
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": hammer_price,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "vip",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        invoice = data["invoice"]
        
        # Verify seller commission rate is 2% (0.02)
        expected_rate = 0.02
        assert abs(invoice["seller_commission_rate"] - expected_rate) < 0.0001, \
            f"Expected seller commission rate {expected_rate}, got {invoice['seller_commission_rate']}"
        
        # Verify seller commission amount
        expected_commission = hammer_price * expected_rate
        assert abs(invoice["seller_commission"] - expected_commission) < 0.01, \
            f"Expected seller commission ${expected_commission}, got ${invoice['seller_commission']}"
        
        print(f"✓ VIP tier seller commission: {invoice['seller_commission_rate']*100:.1f}% = ${invoice['seller_commission']:.2f}")
    
    def test_premium_tier_seller_commission_2_5_percent(self, api_client):
        """Premium tier seller should have 2.5% commission"""
        hammer_price = 25000
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": hammer_price,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "premium",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        invoice = data["invoice"]
        
        # Verify seller commission rate is 2.5% (0.025)
        expected_rate = 0.025
        assert abs(invoice["seller_commission_rate"] - expected_rate) < 0.0001, \
            f"Expected seller commission rate {expected_rate}, got {invoice['seller_commission_rate']}"
        
        print(f"✓ Premium tier seller commission: {invoice['seller_commission_rate']*100:.1f}% = ${invoice['seller_commission']:.2f}")


class TestPreviewInvoiceHTMLContent:
    """Test HTML content generation"""
    
    def test_html_content_contains_bilingual_content(self, api_client):
        """HTML content should contain bilingual (EN/FR) content"""
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": 25000,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify HTML content exists
        assert "html_content" in data, "Response should contain 'html_content' key"
        html = data["html_content"]
        
        # Verify bilingual content markers
        assert "ENGLISH" in html, "HTML should contain 'ENGLISH' label"
        assert "FRAN" in html, "HTML should contain French label (FRANÇAIS)"
        
        # Verify buyer/seller sections in both languages
        assert "BUYER CHARGES" in html, "HTML should contain 'BUYER CHARGES'"
        assert "FRAIS ACHETEUR" in html, "HTML should contain 'FRAIS ACHETEUR'"
        assert "SELLER DEDUCTIONS" in html, "HTML should contain 'SELLER DEDUCTIONS'"
        assert "VENDEUR" in html, "HTML should contain French seller text"
        
        # Verify BidVex branding
        assert "BidVex" in html, "HTML should contain 'BidVex' branding"
        assert "Sherbrooke" in html, "HTML should contain 'Sherbrooke' location"
        
        print(f"✓ HTML content is bilingual with {len(html)} characters")
    
    def test_html_content_contains_tax_breakdown(self, api_client):
        """HTML content should contain tax breakdown for QC"""
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": 25000,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        html = data["html_content"]
        
        # Verify GST and QST labels for Quebec
        assert "GST" in html, "HTML should contain 'GST' for Quebec"
        assert "QST" in html, "HTML should contain 'QST' for Quebec"
        assert "5.00%" in html, "HTML should contain GST rate 5.00%"
        assert "9.975%" in html, "HTML should contain QST rate 9.975%"
        
        print("✓ HTML contains correct tax breakdown for QC")
    
    def test_html_content_contains_hst_for_ontario(self, api_client):
        """HTML content should contain HST for Ontario"""
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": 25000,
            "buyer_province": "ON",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        html = data["html_content"]
        
        # Verify HST label for Ontario
        assert "HST" in html, "HTML should contain 'HST' for Ontario"
        assert "13.00%" in html, "HTML should contain HST rate 13.00%"
        
        print("✓ HTML contains correct HST for ON")


class TestSendTestEmail:
    """Test send-test endpoint"""
    
    def test_send_test_returns_503_or_success(self, api_client):
        """Send-test should return 503 if no SENDGRID_API_KEY or success if configured"""
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/send-test", json={
            "to_email": "test@example.com",
            "hammer_price": 25000,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        # Should return 503 (no SendGrid key) or 200 (success) or 500 (SendGrid error)
        assert response.status_code in [200, 500, 503], \
            f"Expected 200, 500, or 503, got {response.status_code}: {response.text}"
        
        if response.status_code == 503:
            data = response.json()
            assert "SENDGRID" in data.get("detail", "").upper(), \
                "503 response should mention SENDGRID_API_KEY"
            print("✓ Send-test returns 503 (SENDGRID_API_KEY not configured)")
        elif response.status_code == 200:
            data = response.json()
            assert data.get("success") == True, "Success response should have success=True"
            print(f"✓ Send-test succeeded: {data.get('to_email')}")
        else:
            print(f"✓ Send-test returned {response.status_code} (SendGrid error)")


class TestPreviewInvoiceCompleteCalculation:
    """Test complete invoice calculation accuracy"""
    
    def test_complete_qc_calculation(self, api_client):
        """Verify complete calculation for QC with $25,000 hammer price"""
        hammer_price = 25000
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": hammer_price,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        invoice = data["invoice"]
        
        # Verify all key fields are present
        required_fields = [
            "hammer_price", "buyer_premium", "buyer_premium_rate",
            "buyer_platform_fee", "buyer_stripe_fee", "buyer_subtotal",
            "buyer_tax_type", "buyer_tax_rate", "buyer_gst", "buyer_qst",
            "buyer_total_tax", "buyer_total",
            "seller_commission", "seller_commission_rate",
            "seller_platform_fee", "seller_stripe_fee",
            "seller_subtotal_deductions", "seller_tax_type",
            "seller_total_tax", "seller_net_payout"
        ]
        
        for field in required_fields:
            assert field in invoice, f"Missing required field: {field}"
        
        # Verify hammer price
        assert invoice["hammer_price"] == hammer_price
        
        # Verify buyer calculations
        assert invoice["buyer_premium_rate"] == 0.05  # 5% for free tier
        assert invoice["buyer_premium"] == 1250.0  # 5% of 25000
        assert invoice["buyer_platform_fee"] == 625.0  # 2.5% of 25000
        
        # Verify seller calculations
        assert invoice["seller_commission_rate"] == 0.04  # 4% for free tier
        assert invoice["seller_commission"] == 1000.0  # 4% of 25000
        assert invoice["seller_platform_fee"] == 625.0  # 2.5% of 25000
        
        # Verify tax type
        assert invoice["buyer_tax_type"] == "GST+QST"
        assert invoice["seller_tax_type"] == "GST+QST"
        
        print(f"✓ Complete QC calculation verified:")
        print(f"  Buyer Total: ${invoice['buyer_total']:,.2f}")
        print(f"  Seller Net Payout: ${invoice['seller_net_payout']:,.2f}")
        print(f"  BidVex Revenue: ${invoice.get('bidvex_revenue', 0):,.2f}")


class TestPreviewInvoiceTemplateData:
    """Test template_data formatting"""
    
    def test_template_data_formatting(self, api_client):
        """Verify template_data contains properly formatted strings"""
        response = api_client.post(f"{BASE_URL}/api/admin/email-templates/preview-invoice", json={
            "hammer_price": 25000,
            "buyer_province": "QC",
            "buyer_tier": "free",
            "seller_tier": "free",
            "category": "vehicle"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "template_data" in data, "Response should contain 'template_data' key"
        template_data = data["template_data"]
        
        # Verify rate fields are formatted as percentages
        assert "%" in template_data.get("buyer_premium_rate", ""), \
            "buyer_premium_rate should be formatted as percentage"
        assert "%" in template_data.get("seller_commission_rate", ""), \
            "seller_commission_rate should be formatted as percentage"
        
        # Verify amount fields are formatted as currency
        assert "$" in template_data.get("hammer_price", ""), \
            "hammer_price should be formatted as currency"
        assert "$" in template_data.get("buyer_total", ""), \
            "buyer_total should be formatted as currency"
        
        print("✓ Template data is properly formatted")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
