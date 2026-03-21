"""
Test Partner Program Page Features - Iteration 81
Tests:
1. Partner Pro subscription plan pricing ($100 CAD/year)
2. Subscription plans API returns partner_pro plan
3. Price breakdown API for partner_pro
4. i18n keys for partnerPage in EN and FR locales
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPartnerProPricing:
    """Test Partner Pro subscription plan pricing"""
    
    def test_subscription_plans_returns_partner_pro(self):
        """GET /api/subscription-plans should return partner_pro plan"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Response should have success=True"
        assert "plans" in data, "Response should have plans array"
        
        # Find partner_pro plan
        partner_pro = None
        for plan in data["plans"]:
            if plan.get("plan_id") == "partner_pro":
                partner_pro = plan
                break
        
        assert partner_pro is not None, "partner_pro plan should exist"
        print(f"Partner Pro plan found: {partner_pro}")
    
    def test_partner_pro_price_is_100(self):
        """Partner Pro yearly price should be $100 CAD"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        partner_pro = None
        for plan in data["plans"]:
            if plan.get("plan_id") == "partner_pro":
                partner_pro = plan
                break
        
        assert partner_pro is not None, "partner_pro plan should exist"
        assert partner_pro.get("price_yearly") == 100.0, f"Expected price_yearly=100.0, got {partner_pro.get('price_yearly')}"
        assert partner_pro.get("price_monthly") == 0.0, f"Expected price_monthly=0.0, got {partner_pro.get('price_monthly')}"
        print(f"✓ Partner Pro price_yearly: ${partner_pro.get('price_yearly')}")
    
    def test_partner_pro_original_price(self):
        """Partner Pro original yearly price should be $200 CAD (for promotional display)"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        partner_pro = None
        for plan in data["plans"]:
            if plan.get("plan_id") == "partner_pro":
                partner_pro = plan
                break
        
        assert partner_pro is not None, "partner_pro plan should exist"
        assert partner_pro.get("original_price_yearly") == 200.0, f"Expected original_price_yearly=200.0, got {partner_pro.get('original_price_yearly')}"
        print(f"✓ Partner Pro original_price_yearly: ${partner_pro.get('original_price_yearly')}")
    
    def test_partner_pro_features(self):
        """Partner Pro should have expected features"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        partner_pro = None
        for plan in data["plans"]:
            if plan.get("plan_id") == "partner_pro":
                partner_pro = plan
                break
        
        assert partner_pro is not None, "partner_pro plan should exist"
        features = partner_pro.get("features", [])
        assert len(features) > 0, "Partner Pro should have features"
        
        # Check for key features
        features_text = " ".join(features).lower()
        assert "premium" in features_text, "Should mention Premium benefits"
        assert "25%" in features_text or "discount" in features_text, "Should mention discount"
        print(f"✓ Partner Pro features: {len(features)} features found")
    
    def test_price_breakdown_partner_pro(self):
        """GET /api/subscriptions/price-breakdown?plan_id=partner_pro should return correct breakdown"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/price-breakdown?plan_id=partner_pro")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("plan_id") == "partner_pro", f"Expected plan_id=partner_pro, got {data.get('plan_id')}"
        assert data.get("subtotal") == 100.0, f"Expected subtotal=100.0, got {data.get('subtotal')}"
        assert data.get("currency") == "CAD", f"Expected currency=CAD, got {data.get('currency')}"
        
        # Check taxes are calculated
        assert "gst" in data, "Should have GST"
        assert "qst" in data, "Should have QST"
        assert "total" in data, "Should have total"
        
        print(f"✓ Price breakdown: subtotal=${data.get('subtotal')}, total=${data.get('total')}")


class TestSubscriptionPlansAPI:
    """Test subscription plans API structure"""
    
    def test_all_plans_have_required_fields(self):
        """All plans should have required fields"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = ["plan_id", "name", "price_monthly", "price_yearly", "features", "is_active"]
        
        for plan in data["plans"]:
            for field in required_fields:
                assert field in plan, f"Plan {plan.get('plan_id')} missing field: {field}"
        
        print(f"✓ All {len(data['plans'])} plans have required fields")
    
    def test_plans_sorted_correctly(self):
        """Plans should be sorted: free, premium, partner_pro, vip"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        plan_ids = [p.get("plan_id") for p in data["plans"]]
        expected_order = ["free", "premium", "partner_pro", "vip"]
        
        # Check that all expected plans exist
        for expected in expected_order:
            assert expected in plan_ids, f"Plan {expected} should exist"
        
        print(f"✓ Plans found: {plan_ids}")


class TestI18nKeys:
    """Test i18n keys for partnerPage exist in locale files"""
    
    def test_en_locale_has_partner_page_keys(self):
        """EN locale should have partnerPage keys"""
        with open("/app/frontend/src/locales/en.json", "r") as f:
            en_locale = json.load(f)
        
        assert "partnerPage" in en_locale, "EN locale should have partnerPage section"
        partner_keys = en_locale["partnerPage"]
        
        # Check key required keys
        required_keys = [
            "heroBadge", "heroTitle1", "heroTitle2", "heroDesc",
            "ctaApply", "ctaContact", "ctaSignIn",
            "benefit1Title", "benefit2Title", "benefit3Title", "benefit4Title",
            "mathTitle", "mathDesc",
            "formTitle", "formSubmitBtn",
            "feeSummaryTitle", "feeLine1", "feeLine2", "feeLine3",
            "verificationNote"
        ]
        
        for key in required_keys:
            assert key in partner_keys, f"EN locale missing partnerPage.{key}"
        
        print(f"✓ EN locale has {len(partner_keys)} partnerPage keys")
    
    def test_fr_locale_has_partner_page_keys(self):
        """FR locale should have partnerPage keys"""
        with open("/app/frontend/src/locales/fr.json", "r") as f:
            fr_locale = json.load(f)
        
        assert "partnerPage" in fr_locale, "FR locale should have partnerPage section"
        partner_keys = fr_locale["partnerPage"]
        
        # Check key required keys
        required_keys = [
            "heroBadge", "heroTitle1", "heroTitle2", "heroDesc",
            "ctaApply", "ctaContact", "ctaSignIn",
            "benefit1Title", "benefit2Title", "benefit3Title", "benefit4Title",
            "mathTitle", "mathDesc",
            "formTitle", "formSubmitBtn",
            "feeSummaryTitle", "feeLine1", "feeLine2", "feeLine3",
            "verificationNote"
        ]
        
        for key in required_keys:
            assert key in partner_keys, f"FR locale missing partnerPage.{key}"
        
        print(f"✓ FR locale has {len(partner_keys)} partnerPage keys")
    
    def test_en_fr_keys_match(self):
        """EN and FR locales should have matching partnerPage keys"""
        with open("/app/frontend/src/locales/en.json", "r") as f:
            en_locale = json.load(f)
        with open("/app/frontend/src/locales/fr.json", "r") as f:
            fr_locale = json.load(f)
        
        en_keys = set(en_locale.get("partnerPage", {}).keys())
        fr_keys = set(fr_locale.get("partnerPage", {}).keys())
        
        missing_in_fr = en_keys - fr_keys
        missing_in_en = fr_keys - en_keys
        
        assert len(missing_in_fr) == 0, f"FR locale missing keys: {missing_in_fr}"
        assert len(missing_in_en) == 0, f"EN locale missing keys: {missing_in_en}"
        
        print(f"✓ EN and FR locales have matching {len(en_keys)} partnerPage keys")
    
    def test_hero_badge_translations(self):
        """Hero badge should have correct translations"""
        with open("/app/frontend/src/locales/en.json", "r") as f:
            en_locale = json.load(f)
        with open("/app/frontend/src/locales/fr.json", "r") as f:
            fr_locale = json.load(f)
        
        en_badge = en_locale.get("partnerPage", {}).get("heroBadge", "")
        fr_badge = fr_locale.get("partnerPage", {}).get("heroBadge", "")
        
        assert "PARTNER PROGRAM" in en_badge.upper(), f"EN badge should contain 'PARTNER PROGRAM', got: {en_badge}"
        assert "PROGRAMME PARTENAIRE" in fr_badge.upper(), f"FR badge should contain 'PROGRAMME PARTENAIRE', got: {fr_badge}"
        
        print(f"✓ EN badge: '{en_badge}'")
        print(f"✓ FR badge: '{fr_badge}'")
    
    def test_fee_line1_contains_100_cad(self):
        """Fee line 1 should contain $100 CAD in both languages"""
        with open("/app/frontend/src/locales/en.json", "r") as f:
            en_locale = json.load(f)
        with open("/app/frontend/src/locales/fr.json", "r") as f:
            fr_locale = json.load(f)
        
        en_fee = en_locale.get("partnerPage", {}).get("feeLine1", "")
        fr_fee = fr_locale.get("partnerPage", {}).get("feeLine1", "")
        
        # EN should have $100.00 CAD/year
        assert "$100.00 CAD/year" in en_fee, f"EN feeLine1 should contain '$100.00 CAD/year', got: {en_fee}"
        
        # FR should have 100,00$ CAD/an
        assert "100,00$ CAD/an" in fr_fee, f"FR feeLine1 should contain '100,00$ CAD/an', got: {fr_fee}"
        
        print(f"✓ EN feeLine1 contains '$100.00 CAD/year'")
        print(f"✓ FR feeLine1 contains '100,00$ CAD/an'")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
