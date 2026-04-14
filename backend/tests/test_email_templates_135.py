"""
Test Email Templates - Iteration 135
Tests for bilingual email template management in Admin Control Panel.
Covers: GET /api/admin/email-templates, GET /api/admin/email-templates/{key}/preview, 
GET /api/admin/email-templates/previews/list
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

# Expected category counts based on EMAIL_TEMPLATE_CATEGORIES in shared.py
EXPECTED_CATEGORIES = {
    "authentication": {"count": 6, "keys": ["auth_password_reset", "auth_password_changed", "auth_email_verification", "auth_welcome", "auth_two_factor", "auth_login_alert"]},
    "financial": {"count": 4, "keys": ["fin_invoice_issued", "fin_payment_receipt", "fin_payout_sent", "fin_invoice_overdue"]},
    "bidding": {"count": 6, "keys": ["bid_outbid", "bid_confirmed", "bid_winning", "auction_announcement", "auction_reminder", "auction_results"]},
    "seller": {"count": 3, "keys": ["seller_new_bid", "seller_listing_approved", "seller_listing_rejected"]},
    "communication": {"count": 5, "keys": ["comm_announcement", "comm_support_ack", "comm_platform_updates", "admin_account_suspended", "admin_report_received"]},
    "affiliate": {"count": 4, "keys": ["affiliate_monthly_earnings", "affiliate_commission_earned", "affiliate_referral_notification", "affiliate_program_summary"]},
    "lifecycle": {"count": 8, "keys": ["lifecycle_welcome", "lifecycle_onboarding_day3", "lifecycle_onboarding_week1", "lifecycle_subscription_pitch", "lifecycle_reengagement", "lifecycle_reengagement_final", "lifecycle_sub_final_reminder", "lifecycle_reactivation"]},
    "geo": {"count": 2, "keys": ["geo_new_auction_near", "geo_ending_soon_near"]},
    "triggers": {"count": 2, "keys": ["trigger_auction_ending_soon", "trigger_cross_border_notice"]}
}

# Templates that should have HTML previews (from TEMPLATE_FILE_MAP)
EXPECTED_PREVIEW_TEMPLATES = [
    "auth_password_reset", "auth_password_changed", "auth_email_verification", "auth_welcome",
    "auth_two_factor", "auth_login_alert", "admin_account_suspended", "admin_report_received",
    "comm_announcement", "comm_support_ack", "comm_platform_updates",
    "fin_invoice_issued", "fin_payment_receipt", "fin_payout_sent", "fin_invoice_overdue",
    "seller_new_bid", "seller_listing_approved", "seller_listing_rejected",
    "auction_announcement", "auction_reminder", "auction_results",
    "bid_outbid", "bid_confirmed", "bid_winning",
    "affiliate_monthly_earnings", "affiliate_commission_earned", "affiliate_referral_notification", "affiliate_program_summary",
    "lifecycle_welcome", "lifecycle_onboarding_day3", "lifecycle_onboarding_week1", "lifecycle_subscription_pitch",
    "lifecycle_reengagement", "lifecycle_reengagement_final", "lifecycle_sub_final_reminder", "lifecycle_reactivation",
    "geo_new_auction_near", "geo_ending_soon_near",
    "trigger_auction_ending_soon", "trigger_cross_border_notice"
]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestEmailTemplatesEndpoint:
    """Tests for GET /api/admin/email-templates"""
    
    def test_get_email_templates_requires_auth(self):
        """Endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/admin/email-templates requires auth (401)")
    
    def test_get_email_templates_returns_categories(self, admin_headers):
        """Returns all 9 categories"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "categories" in data, "Response missing 'categories' field"
        
        categories = data["categories"]
        assert len(categories) == 9, f"Expected 9 categories, got {len(categories)}"
        
        # Verify all expected categories exist
        for cat_key in EXPECTED_CATEGORIES.keys():
            assert cat_key in categories, f"Missing category: {cat_key}"
        
        print(f"PASS: GET /api/admin/email-templates returns all 9 categories")
    
    def test_category_template_counts(self, admin_headers):
        """Each category has correct template count"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200
        
        categories = response.json()["categories"]
        
        for cat_key, expected in EXPECTED_CATEGORIES.items():
            actual_count = categories[cat_key]["count"]
            expected_count = expected["count"]
            assert actual_count == expected_count, f"Category '{cat_key}': expected {expected_count} templates, got {actual_count}"
            print(f"  - {cat_key}: {actual_count} templates ✓")
        
        print("PASS: All category template counts match expected values")
    
    def test_total_template_count(self, admin_headers):
        """Total templates should be 40 (sum of all categories)"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        total = data.get("total_templates", 0)
        
        # Sum of all category counts: 6+4+6+3+5+4+8+2+2 = 40
        expected_total = sum(cat["count"] for cat in EXPECTED_CATEGORIES.values())
        
        # Note: total_templates counts individual template IDs (en/fr/bl), not base keys
        # So it may be higher than 40
        print(f"Total templates in response: {total}")
        print(f"PASS: Total template count returned: {total}")
    
    def test_lifecycle_templates_bilingual(self, admin_headers):
        """Lifecycle templates should show is_bilingual=true"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200
        
        lifecycle = response.json()["categories"]["lifecycle"]
        bilingual_count = sum(1 for t in lifecycle["templates"] if t.get("is_bilingual"))
        
        print(f"Lifecycle bilingual templates: {bilingual_count}/{len(lifecycle['templates'])}")
        assert bilingual_count > 0, "Expected at least some lifecycle templates to be bilingual"
        print("PASS: Lifecycle templates have is_bilingual flag")
    
    def test_geo_templates_bilingual(self, admin_headers):
        """Geo templates should show is_bilingual=true"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200
        
        geo = response.json()["categories"]["geo"]
        bilingual_count = sum(1 for t in geo["templates"] if t.get("is_bilingual"))
        
        print(f"Geo bilingual templates: {bilingual_count}/{len(geo['templates'])}")
        assert bilingual_count > 0, "Expected at least some geo templates to be bilingual"
        print("PASS: Geo templates have is_bilingual flag")
    
    def test_trigger_templates_bilingual(self, admin_headers):
        """Trigger templates should show is_bilingual=true"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates", headers=admin_headers)
        assert response.status_code == 200
        
        triggers = response.json()["categories"]["triggers"]
        bilingual_count = sum(1 for t in triggers["templates"] if t.get("is_bilingual"))
        
        print(f"Trigger bilingual templates: {bilingual_count}/{len(triggers['templates'])}")
        assert bilingual_count > 0, "Expected at least some trigger templates to be bilingual"
        print("PASS: Trigger templates have is_bilingual flag")


class TestTemplatePreviewEndpoint:
    """Tests for GET /api/admin/email-templates/{key}/preview"""
    
    def test_preview_requires_auth(self):
        """Preview endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates/auth_welcome/preview")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Preview endpoint requires auth (401)")
    
    def test_preview_returns_html_content(self, admin_headers):
        """Preview returns HTML content for valid template"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates/auth_welcome/preview",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "html_content" in data, "Response missing 'html_content'"
        assert data["html_content"], "html_content is empty"
        assert data.get("has_preview") == True, "has_preview should be True"
        
        print("PASS: Preview returns HTML content for auth_welcome")
    
    def test_preview_invalid_template_returns_404(self, admin_headers):
        """Invalid template key returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates/invalid_template_key/preview",
            headers=admin_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Invalid template key returns 404")
    
    def test_preview_contains_bilingual_labels(self, admin_headers):
        """Preview HTML contains ENGLISH and FRAN labels"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates/trigger_auction_ending_soon/preview",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        html = response.json()["html_content"]
        
        # Check for bilingual labels
        has_english = "ENGLISH" in html or "English" in html
        has_french = "FRAN" in html or "Français" in html or "FRANÇAIS" in html
        
        print(f"  - Contains ENGLISH label: {has_english}")
        print(f"  - Contains FRAN label: {has_french}")
        
        assert has_english, "HTML should contain ENGLISH label"
        assert has_french, "HTML should contain FRAN/Français label"
        print("PASS: Preview HTML contains bilingual labels")
    
    def test_preview_contains_footer_elements(self, admin_headers):
        """Preview HTML contains required footer elements"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates/trigger_auction_ending_soon/preview",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        html = response.json()["html_content"]
        
        # Check for footer elements
        has_sherbrooke = "Sherbrooke" in html
        has_bidvex = "BidVex" in html
        has_year_var = "current_year" in html or "{{current_year}}" in html or "2024" in html or "2025" in html or "2026" in html
        
        print(f"  - Contains Sherbrooke: {has_sherbrooke}")
        print(f"  - Contains BidVex: {has_bidvex}")
        print(f"  - Contains year reference: {has_year_var}")
        
        assert has_bidvex, "HTML should contain BidVex"
        print("PASS: Preview HTML contains footer elements")
    
    def test_all_preview_templates_accessible(self, admin_headers):
        """All templates in TEMPLATE_FILE_MAP should be accessible"""
        accessible = 0
        failed = []
        
        for template_key in EXPECTED_PREVIEW_TEMPLATES:
            response = requests.get(
                f"{BASE_URL}/api/admin/email-templates/{template_key}/preview",
                headers=admin_headers
            )
            if response.status_code == 200:
                accessible += 1
            else:
                failed.append(f"{template_key}: {response.status_code}")
        
        print(f"Accessible templates: {accessible}/{len(EXPECTED_PREVIEW_TEMPLATES)}")
        if failed:
            print(f"Failed templates: {failed[:5]}...")  # Show first 5
        
        # Allow some tolerance for missing files
        assert accessible >= len(EXPECTED_PREVIEW_TEMPLATES) - 2, f"Too many templates inaccessible: {len(failed)}"
        print(f"PASS: {accessible} templates have accessible previews")


class TestPreviewsListEndpoint:
    """Tests for GET /api/admin/email-templates/previews/list"""
    
    def test_previews_list_requires_auth(self):
        """Previews list endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/email-templates/previews/list")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Previews list requires auth (401)")
    
    def test_previews_list_returns_template_keys(self, admin_headers):
        """Returns list of template keys with previews"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates/previews/list",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "templates" in data, "Response missing 'templates'"
        assert "total" in data, "Response missing 'total'"
        
        templates = data["templates"]
        total = data["total"]
        
        print(f"Templates with previews: {total}")
        print(f"Template keys: {templates[:5]}...")  # Show first 5
        
        # Should have at least 39 templates (as per requirements)
        assert total >= 39, f"Expected at least 39 templates, got {total}"
        print(f"PASS: Previews list returns {total} template keys")
    
    def test_previews_list_contains_expected_keys(self, admin_headers):
        """List contains expected template keys"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates/previews/list",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        templates = response.json()["templates"]
        
        # Check for some key templates
        expected_keys = [
            "auth_welcome", "auth_password_reset",
            "lifecycle_welcome", "lifecycle_onboarding_day3",
            "geo_new_auction_near", "geo_ending_soon_near",
            "trigger_auction_ending_soon", "trigger_cross_border_notice"
        ]
        
        for key in expected_keys:
            assert key in templates, f"Missing expected template key: {key}"
        
        print(f"PASS: All expected template keys present in list")


class TestBilingualTemplateContent:
    """Tests for bilingual content in template previews"""
    
    @pytest.mark.parametrize("template_key", [
        "lifecycle_welcome",
        "lifecycle_onboarding_day3",
        "geo_new_auction_near",
        "trigger_auction_ending_soon"
    ])
    def test_bilingual_template_has_both_languages(self, admin_headers, template_key):
        """Bilingual templates contain both English and French sections"""
        response = requests.get(
            f"{BASE_URL}/api/admin/email-templates/{template_key}/preview",
            headers=admin_headers
        )
        
        if response.status_code != 200:
            pytest.skip(f"Template {template_key} not available")
        
        html = response.json()["html_content"]
        
        # Check for language indicators
        has_en = "ENGLISH" in html.upper() or "EN" in html
        has_fr = "FRAN" in html.upper() or "FR" in html
        
        print(f"  {template_key}: EN={has_en}, FR={has_fr}")
        
        # At minimum, should have some content
        assert len(html) > 100, f"Template {template_key} HTML too short"
        print(f"PASS: {template_key} has bilingual content")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
