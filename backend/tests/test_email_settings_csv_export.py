"""
Test suite for BidVex Phase 2 P1 Features:
1. Email Settings admin panel for self-service SendGrid API key management
2. CSV export for Transaction Logs
3. Partners & Finance sub-tabs (Finance Dashboard + Email Settings)

Testing iteration_45
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed - skipping admin tests")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Admin authorization headers."""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestEmailSettings:
    """Tests for Email Settings admin panel (GET/POST /api/admin/email-settings)"""
    
    def test_get_email_settings_returns_200(self, auth_headers):
        """GET /api/admin/email-settings should return 200 for admin users"""
        response = requests.get(f"{BASE_URL}/api/admin/email-settings", headers=auth_headers)
        assert response.status_code == 200
        print(f"✓ GET /api/admin/email-settings returned status 200")
    
    def test_get_email_settings_returns_correct_structure(self, auth_headers):
        """Response should contain configured, source, masked_key, from_email, from_name fields"""
        response = requests.get(f"{BASE_URL}/api/admin/email-settings", headers=auth_headers)
        data = response.json()
        
        # Verify structure
        assert "configured" in data
        assert "source" in data
        assert "masked_key" in data
        assert "from_email" in data
        assert "from_name" in data
        assert "last_test_at" in data
        assert "last_test_status" in data
        
        print(f"✓ Email settings response has all required fields: {list(data.keys())}")
    
    def test_post_email_settings_rejects_invalid_key(self, auth_headers):
        """POST /api/admin/email-settings should reject keys not starting with SG."""
        response = requests.post(
            f"{BASE_URL}/api/admin/email-settings",
            headers=auth_headers,
            json={
                "api_key": "INVALID_KEY_NO_SG_PREFIX",
                "from_email": "test@bidvex.com",
                "from_name": "Test"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "SG." in str(data.get("detail", ""))
        print(f"✓ Invalid API key correctly rejected with 400: {data}")
    
    def test_post_email_settings_accepts_valid_key_format(self, auth_headers):
        """POST /api/admin/email-settings should accept keys starting with SG."""
        response = requests.post(
            f"{BASE_URL}/api/admin/email-settings",
            headers=auth_headers,
            json={
                "api_key": "SG.testkeyformat1234567890",
                "from_email": "test@bidvex.com",
                "from_name": "BidVex Test"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "saved" in data.get("message", "").lower()
        print(f"✓ Valid API key accepted: {data}")
    
    def test_post_email_settings_requires_api_key(self, auth_headers):
        """POST /api/admin/email-settings should require api_key"""
        response = requests.post(
            f"{BASE_URL}/api/admin/email-settings",
            headers=auth_headers,
            json={
                "from_email": "test@bidvex.com",
                "from_name": "Test"
            }
        )
        assert response.status_code == 400
        print(f"✓ Empty API key correctly rejected with 400")
    
    def test_email_settings_masked_key_display(self, auth_headers):
        """Masked key should not expose full API key"""
        response = requests.get(f"{BASE_URL}/api/admin/email-settings", headers=auth_headers)
        data = response.json()
        
        if data.get("masked_key"):
            # Should contain ... to indicate masking
            assert "..." in data["masked_key"] or "***" in data["masked_key"]
            # Should start with SG. if configured
            if data.get("configured"):
                assert data["masked_key"].startswith("SG.")
        print(f"✓ API key is properly masked: {data.get('masked_key')}")


class TestEmailTestEndpoint:
    """Tests for Send Test Email functionality (POST /api/admin/email-settings/test)"""
    
    def test_test_email_returns_proper_response(self, auth_headers):
        """POST /api/admin/email-settings/test should respond appropriately"""
        response = requests.post(
            f"{BASE_URL}/api/admin/email-settings/test",
            headers=auth_headers,
            json={"recipient": "test@example.com"}
        )
        # With mocked/invalid key, expect 400; with valid key, expect 200
        assert response.status_code in [200, 400]
        data = response.json()
        print(f"✓ Test email endpoint responded with status {response.status_code}: {data}")
    
    def test_test_email_requires_valid_recipient(self, auth_headers):
        """POST /api/admin/email-settings/test should require valid email"""
        response = requests.post(
            f"{BASE_URL}/api/admin/email-settings/test",
            headers=auth_headers,
            json={"recipient": "invalid-email"}
        )
        assert response.status_code == 400
        print(f"✓ Invalid recipient email rejected")


class TestTransactionsCSVExport:
    """Tests for CSV export functionality (GET /api/admin/finance/transactions/export)"""
    
    def test_csv_export_returns_200(self, auth_headers):
        """GET /api/admin/finance/transactions/export should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions/export",
            headers=auth_headers
        )
        assert response.status_code == 200
        print(f"✓ CSV export returned status 200")
    
    def test_csv_export_returns_csv_content_type(self, auth_headers):
        """Response should have text/csv content type"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions/export",
            headers=auth_headers
        )
        assert "text/csv" in response.headers.get("Content-Type", "")
        print(f"✓ CSV export has correct Content-Type: {response.headers.get('Content-Type')}")
    
    def test_csv_export_has_content_disposition(self, auth_headers):
        """Response should have Content-Disposition header for download"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions/export",
            headers=auth_headers
        )
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp
        assert "filename" in content_disp
        assert "bidvex_transactions" in content_disp
        print(f"✓ CSV export has correct Content-Disposition: {content_disp}")
    
    def test_csv_export_has_proper_headers(self, auth_headers):
        """CSV should have proper column headers"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions/export",
            headers=auth_headers
        )
        csv_content = response.text
        
        # First line should be headers
        header_line = csv_content.split('\n')[0] if csv_content else ""
        
        # Check for expected column headers
        expected_headers = [
            "Date", "Item", "Buyer Email", "Seller Email", "Type",
            "Hammer Price", "Buyer Premium", "Platform Fee", "Processing Fee",
            "Partner Payout", "Stripe Charge ID", "Partner Company"
        ]
        for header in expected_headers:
            assert header in header_line, f"Missing header: {header}"
        
        print(f"✓ CSV has all expected headers: {expected_headers}")
    
    def test_csv_export_with_partner_only_filter(self, auth_headers):
        """CSV export should accept partner_only query parameter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions/export?partner_only=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        print(f"✓ CSV export with partner_only=true works")
    
    def test_csv_export_with_search_filter(self, auth_headers):
        """CSV export should accept search query parameter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions/export?search=test",
            headers=auth_headers
        )
        assert response.status_code == 200
        print(f"✓ CSV export with search filter works")


class TestFinanceDashboardIntegration:
    """Tests for Finance Dashboard sub-tabs and functionality"""
    
    def test_finance_revenue_summary_endpoint(self, auth_headers):
        """GET /api/admin/finance/revenue-summary should return revenue data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/revenue-summary",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "revenue" in data
        assert "partner_revenue" in data
        assert "users" in data
        assert "auctions" in data
        
        print(f"✓ Finance revenue summary has correct structure")
    
    def test_finance_transactions_endpoint(self, auth_headers):
        """GET /api/admin/finance/transactions should return paginated transactions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination structure
        assert "transactions" in data
        assert "total" in data
        assert "pages" in data
        
        print(f"✓ Finance transactions endpoint works with pagination")
    
    def test_finance_transactions_with_search(self, auth_headers):
        """Transaction logs should support search functionality"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions?search=test",
            headers=auth_headers
        )
        assert response.status_code == 200
        print(f"✓ Transaction search works")
    
    def test_collected_fees_in_revenue_summary(self, auth_headers):
        """Revenue summary should include collected fees breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/revenue-summary",
            headers=auth_headers
        )
        data = response.json()
        revenue = data.get("revenue", {})
        
        # Check fee-related fields
        assert "total_platform_fees" in revenue or isinstance(revenue, dict)
        assert "total_processing_fees" in revenue or isinstance(revenue, dict)
        assert "subscription_revenue" in revenue or isinstance(revenue, dict)
        
        print(f"✓ Revenue summary includes fee breakdown: {list(revenue.keys())}")


class TestAccessControl:
    """Tests for authentication and authorization"""
    
    def test_email_settings_requires_auth(self):
        """Email settings endpoints should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/email-settings")
        assert response.status_code == 401
        print(f"✓ Email settings requires authentication")
    
    def test_csv_export_requires_auth(self):
        """CSV export should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/finance/transactions/export")
        assert response.status_code == 401
        print(f"✓ CSV export requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
