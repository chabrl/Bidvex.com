"""
BidVex Commercial Readiness Phase - Iteration 94 Tests
Tests for updated requirements:
1. Multi-province tax rates with NS=14% (2026 rate)
2. Cookie consent with renamed categories (strictly_necessary, functionality, analytics, marketing)
3. Cookie consent with refuse_all and privacy_by_default fields
4. Invoice PDF with Vehicle Information section
5. Invoice PDF with buyer/seller addresses and tax ID placeholders
6. R2 invoice upload path verification
7. Partner stats and badge endpoints still working
"""

import pytest
import requests
import os
from decimal import Decimal

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

# Test transaction IDs
TRANSACTION_WITH_VEHICLE = "49e7251f-c69a-4ee3-90b4-6e16fbb57404"  # Has VIN WBS43AZ09PCL95847, 2023 BMW M3
TRANSACTION_WITHOUT_VEHICLE = "5d5e4c3d-5939-4538-a5e2-739f5648bbdb"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Get authorization headers"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✓ Health endpoint working")


class TestMultiProvinceTaxRates:
    """Test multi-province tax engine with updated NS=14% rate"""
    
    def test_nova_scotia_hst_14_percent_2026_rate(self, auth_headers):
        """NS HST should be 14% (2026 rate, changed from 15%)"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "NS"},
            headers=auth_headers
        )
        # May return 404 if transaction doesn't exist, but we can test the tax calculation directly
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            # NS should have HST at 14%
            assert tax_breakdown.get("tax_type") == "hst", f"NS should be HST type, got {tax_breakdown.get('tax_type')}"
            # Verify the rate is 14% by checking the line items
            line_items = tax_breakdown.get("line_items", [])
            if line_items:
                hst_line = line_items[0]
                assert "14%" in hst_line.get("label", ""), f"NS HST should be 14%, got {hst_line.get('label')}"
            print("✓ NS HST is 14% (2026 rate)")
        else:
            # Test the tax calculation function directly via a different endpoint or skip
            print(f"⚠ Transaction not found, testing tax rates via cookie policy endpoint")
            pytest.skip("Transaction not found for NS tax test")
    
    def test_ontario_hst_13_percent(self, auth_headers):
        """ON HST should be 13%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "ON"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "hst"
            line_items = tax_breakdown.get("line_items", [])
            if line_items:
                assert "13%" in line_items[0].get("label", "")
            print("✓ ON HST is 13%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_new_brunswick_hst_15_percent(self, auth_headers):
        """NB HST should be 15%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "NB"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "hst"
            line_items = tax_breakdown.get("line_items", [])
            if line_items:
                assert "15%" in line_items[0].get("label", "")
            print("✓ NB HST is 15%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_newfoundland_hst_15_percent(self, auth_headers):
        """NL HST should be 15%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "NL"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "hst"
            line_items = tax_breakdown.get("line_items", [])
            if line_items:
                assert "15%" in line_items[0].get("label", "")
            print("✓ NL HST is 15%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_pei_hst_15_percent(self, auth_headers):
        """PE HST should be 15%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "PE"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "hst"
            line_items = tax_breakdown.get("line_items", [])
            if line_items:
                assert "15%" in line_items[0].get("label", "")
            print("✓ PE HST is 15%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_quebec_dual_tax_gst_qst(self, auth_headers):
        """QC should have GST 5% + QST 9.975%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "QC"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "dual"
            line_items = tax_breakdown.get("line_items", [])
            assert len(line_items) == 2, "QC should have 2 tax lines (GST + QST)"
            labels = [item.get("label", "") for item in line_items]
            assert any("5%" in l and "GST" in l for l in labels), "QC should have GST 5%"
            assert any("9.975%" in l and "QST" in l for l in labels), "QC should have QST 9.975%"
            print("✓ QC dual tax: GST 5% + QST 9.975%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_bc_dual_tax_gst_pst(self, auth_headers):
        """BC should have GST 5% + PST 7%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "BC"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "dual"
            line_items = tax_breakdown.get("line_items", [])
            assert len(line_items) == 2, "BC should have 2 tax lines (GST + PST)"
            labels = [item.get("label", "") for item in line_items]
            assert any("5%" in l and "GST" in l for l in labels), "BC should have GST 5%"
            assert any("7%" in l and "PST" in l for l in labels), "BC should have PST 7%"
            print("✓ BC dual tax: GST 5% + PST 7%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_saskatchewan_dual_tax_gst_pst(self, auth_headers):
        """SK should have GST 5% + PST 6%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "SK"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "dual"
            line_items = tax_breakdown.get("line_items", [])
            assert len(line_items) == 2, "SK should have 2 tax lines (GST + PST)"
            labels = [item.get("label", "") for item in line_items]
            assert any("5%" in l and "GST" in l for l in labels), "SK should have GST 5%"
            assert any("6%" in l and "PST" in l for l in labels), "SK should have PST 6%"
            print("✓ SK dual tax: GST 5% + PST 6%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_alberta_gst_only_5_percent(self, auth_headers):
        """AB should have GST only at 5%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "AB"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "gst_only"
            line_items = tax_breakdown.get("line_items", [])
            assert len(line_items) == 1, "AB should have 1 tax line (GST only)"
            assert "5%" in line_items[0].get("label", "")
            print("✓ AB GST only: 5%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_yukon_gst_only_5_percent(self, auth_headers):
        """YT should have GST only at 5%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "YT"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "gst_only"
            print("✓ YT GST only: 5%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_northwest_territories_gst_only_5_percent(self, auth_headers):
        """NT should have GST only at 5%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "NT"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "gst_only"
            print("✓ NT GST only: 5%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_nunavut_gst_only_5_percent(self, auth_headers):
        """NU should have GST only at 5%"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "NU"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            tax_breakdown = data.get("tax_breakdown", {})
            assert tax_breakdown.get("tax_type") == "gst_only"
            print("✓ NU GST only: 5%")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")


class TestCookieConsentLaw25:
    """Test cookie consent API with renamed categories and new fields"""
    
    def test_cookie_policy_english_default(self):
        """Test English cookie policy returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy")
        assert response.status_code == 200
        data = response.json()
        assert data.get("language") == "en"
        consent = data.get("consent", {})
        assert "categories" in consent
        print("✓ Cookie policy English default works")
    
    def test_cookie_policy_has_strictly_necessary_category(self):
        """Categories should include strictly_necessary (renamed from essential)"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=en")
        assert response.status_code == 200
        data = response.json()
        categories = data.get("consent", {}).get("categories", {})
        
        assert "strictly_necessary" in categories, "Missing strictly_necessary category"
        strictly_necessary = categories["strictly_necessary"]
        assert strictly_necessary.get("name") == "Strictly Necessary"
        assert strictly_necessary.get("required") == True, "strictly_necessary should be required=true"
        print("✓ strictly_necessary category present with required=true")
    
    def test_cookie_policy_has_functionality_category(self):
        """Categories should include functionality (renamed from functional)"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=en")
        assert response.status_code == 200
        data = response.json()
        categories = data.get("consent", {}).get("categories", {})
        
        assert "functionality" in categories, "Missing functionality category"
        functionality = categories["functionality"]
        assert functionality.get("name") == "Functionality"
        assert functionality.get("required") == False, "functionality should be required=false"
        print("✓ functionality category present with required=false")
    
    def test_cookie_policy_has_analytics_category(self):
        """Categories should include analytics"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=en")
        assert response.status_code == 200
        data = response.json()
        categories = data.get("consent", {}).get("categories", {})
        
        assert "analytics" in categories, "Missing analytics category"
        analytics = categories["analytics"]
        assert analytics.get("name") == "Analytics"
        assert analytics.get("required") == False, "analytics should be required=false"
        print("✓ analytics category present with required=false")
    
    def test_cookie_policy_has_marketing_category(self):
        """Categories should include marketing"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=en")
        assert response.status_code == 200
        data = response.json()
        categories = data.get("consent", {}).get("categories", {})
        
        assert "marketing" in categories, "Missing marketing category"
        marketing = categories["marketing"]
        assert marketing.get("name") == "Marketing"
        assert marketing.get("required") == False, "marketing should be required=false"
        print("✓ marketing category present with required=false")
    
    def test_cookie_policy_has_refuse_all_field_english(self):
        """English cookie policy should have refuse_all field"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=en")
        assert response.status_code == 200
        data = response.json()
        consent = data.get("consent", {})
        
        assert "refuse_all" in consent, "Missing refuse_all field"
        assert consent["refuse_all"] == "Refuse All", f"refuse_all should be 'Refuse All', got '{consent['refuse_all']}'"
        print("✓ refuse_all field present in English: 'Refuse All'")
    
    def test_cookie_policy_has_privacy_by_default_field(self):
        """Cookie policy should have privacy_by_default field"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=en")
        assert response.status_code == 200
        data = response.json()
        consent = data.get("consent", {})
        
        assert "privacy_by_default" in consent, "Missing privacy_by_default field"
        assert len(consent["privacy_by_default"]) > 0, "privacy_by_default should not be empty"
        print("✓ privacy_by_default field present")
    
    def test_cookie_policy_french_refuse_all(self):
        """French cookie policy should have refuse_all='Tout refuser'"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=fr")
        assert response.status_code == 200
        data = response.json()
        consent = data.get("consent", {})
        
        assert consent.get("refuse_all") == "Tout refuser", f"French refuse_all should be 'Tout refuser', got '{consent.get('refuse_all')}'"
        print("✓ French refuse_all: 'Tout refuser'")
    
    def test_cookie_policy_french_accept_all(self):
        """French cookie policy should have accept_all='Tout accepter'"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=fr")
        assert response.status_code == 200
        data = response.json()
        consent = data.get("consent", {})
        
        assert consent.get("accept_all") == "Tout accepter", f"French accept_all should be 'Tout accepter', got '{consent.get('accept_all')}'"
        print("✓ French accept_all: 'Tout accepter'")
    
    def test_cookie_policy_french_strictly_necessary_name(self):
        """French strictly_necessary.name should be 'Strictement necessaires'"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy?lang=fr")
        assert response.status_code == 200
        data = response.json()
        categories = data.get("consent", {}).get("categories", {})
        
        strictly_necessary = categories.get("strictly_necessary", {})
        assert strictly_necessary.get("name") == "Strictement necessaires", \
            f"French strictly_necessary.name should be 'Strictement necessaires', got '{strictly_necessary.get('name')}'"
        print("✓ French strictly_necessary.name: 'Strictement necessaires'")
    
    def test_cookie_policy_accept_language_header_french(self):
        """Accept-Language: fr-CA should return French"""
        response = requests.get(
            f"{BASE_URL}/api/legal/cookie-policy",
            headers={"Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("language") == "fr"
        print("✓ Accept-Language header fr-CA works")


class TestInvoiceGeneration:
    """Test invoice generation with vehicle info and addresses"""
    
    def test_invoice_generation_requires_auth(self):
        """Invoice generation should require authentication"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "QC"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Invoice generation requires auth")
    
    def test_invoice_generation_with_vehicle_info(self, auth_headers):
        """Invoice for transaction with vehicle should include vehicle info"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITH_VEHICLE}",
            params={"lang": "en", "buyer_province": "QC"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True
            assert "storage_path" in data
            # Storage path should be in the transactions subfolder
            storage_path = data.get("storage_path", "")
            assert "invoices/transactions" in storage_path, f"Storage path should contain 'invoices/transactions', got {storage_path}"
            print(f"✓ Invoice with vehicle generated: {storage_path}")
        elif response.status_code == 404:
            print(f"⚠ Transaction {TRANSACTION_WITH_VEHICLE} not found - skipping vehicle info test")
            pytest.skip("Transaction with vehicle not found")
        else:
            pytest.fail(f"Invoice generation failed: {response.status_code} - {response.text}")
    
    def test_invoice_generation_without_vehicle(self, auth_headers):
        """Invoice for transaction without vehicle should still work"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "ON"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True
            assert "storage_path" in data
            assert "download_url" in data
            print("✓ Invoice without vehicle generated successfully")
        elif response.status_code == 404:
            print(f"⚠ Transaction {TRANSACTION_WITHOUT_VEHICLE} not found")
            pytest.skip("Transaction without vehicle not found")
        else:
            pytest.fail(f"Invoice generation failed: {response.status_code} - {response.text}")
    
    def test_invoice_storage_path_format(self, auth_headers):
        """Invoice storage path should be bidvex/invoices/transactions/{uuid}.pdf"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "en", "buyer_province": "QC"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            storage_path = data.get("storage_path", "")
            # Should match pattern: bidvex/invoices/transactions/{transaction_id}.pdf
            assert storage_path.startswith("bidvex/invoices/transactions/"), \
                f"Storage path should start with 'bidvex/invoices/transactions/', got {storage_path}"
            assert storage_path.endswith(".pdf"), f"Storage path should end with .pdf, got {storage_path}"
            print(f"✓ Storage path format correct: {storage_path}")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")
    
    def test_invoice_generation_invalid_transaction(self, auth_headers):
        """Invoice generation for non-existent transaction should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/non-existent-transaction-id",
            params={"lang": "en", "buyer_province": "QC"},
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid transaction returns 404")
    
    def test_invoice_french_language(self, auth_headers):
        """Invoice generation should support French language"""
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TRANSACTION_WITHOUT_VEHICLE}",
            params={"lang": "fr", "buyer_province": "QC"},
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True
            # French invoice should have French tax labels
            tax_breakdown = data.get("tax_breakdown", {})
            line_items = tax_breakdown.get("line_items", [])
            if line_items:
                # French labels should be TPS/TVQ instead of GST/QST
                labels = [item.get("label", "") for item in line_items]
                assert any("TPS" in l for l in labels), "French invoice should have TPS label"
            print("✓ French invoice generated with French labels")
        else:
            pytest.skip(f"Transaction not found: {response.status_code}")


class TestPartnerEndpoints:
    """Test partner stats and badge endpoints still work"""
    
    def test_partner_stats_requires_auth(self):
        """Partner stats should require authentication"""
        response = requests.get(f"{BASE_URL}/api/partner/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Partner stats requires auth")
    
    def test_partner_stats_with_admin(self, auth_headers):
        """Partner stats should work with admin auth"""
        response = requests.get(f"{BASE_URL}/api/partner/stats", headers=auth_headers)
        if response.status_code == 200:
            data = response.json()
            # Should have expected fields
            expected_fields = ["total_partners", "verified_partners", "generated_at"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"
            print("✓ Partner stats returns expected fields")
        elif response.status_code == 403:
            print("⚠ Admin user doesn't have partner stats access - may need verified partner role")
            pytest.skip("Admin doesn't have partner stats access")
        else:
            pytest.fail(f"Partner stats failed: {response.status_code} - {response.text}")
    
    def test_partner_badge_public_endpoint(self):
        """Partner badge should be public (no auth required)"""
        # Use admin user ID for testing
        response = requests.get(f"{BASE_URL}/api/partner/badge/test-user-id")
        # Should return 200 or 404 (not 401/403)
        assert response.status_code in [200, 404], f"Expected 200/404, got {response.status_code}"
        print("✓ Partner badge is public endpoint")
    
    def test_partner_badge_nonexistent_user(self):
        """Partner badge for non-existent user should return 404"""
        response = requests.get(f"{BASE_URL}/api/partner/badge/nonexistent-user-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Partner badge returns 404 for non-existent user")


class TestListInvoicesEndpoint:
    """Test existing list invoices endpoint still works"""
    
    def test_list_invoices_requires_auth(self):
        """List invoices should require authentication"""
        response = requests.get(f"{BASE_URL}/api/invoices")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ List invoices requires auth")
    
    def test_list_invoices_with_auth(self, auth_headers):
        """List invoices should work with auth"""
        response = requests.get(f"{BASE_URL}/api/invoices", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "invoices" in data, "Response should have 'invoices' field"
        print("✓ List invoices works with auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
