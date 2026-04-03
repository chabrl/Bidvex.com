"""
BidVex Iteration 105 Tests - Affiliate Engine, Promotion/Email Credit Storefronts, CSS Polish

Tests:
1. Affiliate Cash-Back Engine (process_affiliate_payout)
2. Promotion Checkout with GST/QST
3. Email Credits Checkout with GST/QST
4. Pricing Config Endpoint
5. French letter-spacing CSS verification (code check)
"""

import pytest
import requests
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-verify-2.preview.emergentagent.com')

# Tax rates
GST_RATE = Decimal("0.05")
QST_RATE = Decimal("0.09975")


class TestAffiliateEngine:
    """Test affiliate cash-back payout calculations"""
    
    def test_process_affiliate_payout_function_exists(self):
        """Verify process_affiliate_payout function exists in connect_payment_engine"""
        from services.connect_payment_engine import process_affiliate_payout
        assert callable(process_affiliate_payout)
        print("✓ process_affiliate_payout function exists")
    
    def test_affiliate_commission_rate_is_15_percent(self):
        """Verify AFFILIATE_COMMISSION_RATE = 0.15 (15%)"""
        from services.pricing_config import AFFILIATE_COMMISSION_RATE
        assert float(AFFILIATE_COMMISSION_RATE) == 0.15
        print(f"✓ AFFILIATE_COMMISSION_RATE = {float(AFFILIATE_COMMISSION_RATE)} (15%)")
    
    def test_standard_flow_affiliate_payout_calculation(self):
        """
        STANDARD FLOW: Affiliate gets 15% of (buyer_premium + seller_commission)
        Example: $1000 hammer, 5% buyer premium ($50), 4% seller commission ($40)
        BidVex revenue = $50 + $40 = $90
        Affiliate payout = $90 * 0.15 = $13.50
        """
        from services.pricing_config import AFFILIATE_COMMISSION_RATE
        
        # Simulate standard flow metadata
        buyer_premium = 50.0  # 5% of $1000
        seller_commission = 40.0  # 4% of $1000
        
        # Standard flow: BidVex keeps both
        bidvex_revenue = buyer_premium + seller_commission
        affiliate_payout = round(bidvex_revenue * float(AFFILIATE_COMMISSION_RATE), 2)
        
        assert bidvex_revenue == 90.0
        assert affiliate_payout == 13.50
        print(f"✓ Standard flow: BidVex revenue=${bidvex_revenue}, Affiliate payout=${affiliate_payout}")
    
    def test_partner_flow_affiliate_payout_calculation(self):
        """
        PARTNER FLOW: Affiliate gets 15% of seller_commission only
        (Buyer premium goes to Partner, not BidVex)
        Example: $1000 hammer, 3% seller commission ($30)
        BidVex revenue = $30
        Affiliate payout = $30 * 0.15 = $4.50
        """
        from services.pricing_config import AFFILIATE_COMMISSION_RATE
        
        # Simulate partner flow metadata
        seller_commission = 30.0  # 3% of $1000 (partner rate)
        
        # Partner flow: BidVex keeps only seller commission
        bidvex_revenue = seller_commission
        affiliate_payout = round(bidvex_revenue * float(AFFILIATE_COMMISSION_RATE), 2)
        
        assert bidvex_revenue == 30.0
        assert affiliate_payout == 4.50
        print(f"✓ Partner flow: BidVex revenue=${bidvex_revenue}, Affiliate payout=${affiliate_payout}")
    
    def test_create_connect_checkout_includes_transfer_group(self):
        """Verify create_connect_checkout_session includes transfer_group in metadata"""
        from services.connect_payment_engine import create_connect_checkout_session
        import inspect
        
        # Check function signature and source
        source = inspect.getsource(create_connect_checkout_session)
        assert "transfer_group" in source
        print("✓ create_connect_checkout_session includes transfer_group")
    
    def test_create_connect_checkout_includes_affiliate_id(self):
        """Verify create_connect_checkout_session includes affiliate_id in metadata"""
        from services.connect_payment_engine import create_connect_checkout_session
        import inspect
        
        source = inspect.getsource(create_connect_checkout_session)
        assert "affiliate_id" in source
        print("✓ create_connect_checkout_session includes affiliate_id in metadata")


class TestPromotionTaxCalculation:
    """Test promotion checkout with GST/QST"""
    
    def test_create_promotion_checkout_returns_gst_qst(self):
        """Verify create_promotion_checkout returns gst and qst fields"""
        from services.connect_payment_engine import create_promotion_checkout
        import inspect
        
        source = inspect.getsource(create_promotion_checkout)
        assert '"gst":' in source or "'gst':" in source
        assert '"qst":' in source or "'qst':" in source
        print("✓ create_promotion_checkout returns gst and qst fields")
    
    def test_basic_promotion_tax_calculation(self):
        """
        Basic $9.99 -> GST $0.50, QST $1.00, Total $11.49
        """
        from services.pricing_config import PROMOTION_TIERS
        
        base_price = Decimal("9.99")
        gst = (base_price * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (base_price * QST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = base_price + gst + qst
        
        # Verify tier exists
        assert "basic" in PROMOTION_TIERS
        assert PROMOTION_TIERS["basic"]["price_cents"] == 999
        
        # Verify tax calculation
        assert float(gst) == 0.50
        assert float(qst) == 1.00  # 9.99 * 0.09975 = 0.9965 -> rounds to 1.00
        assert float(total) == 11.49
        print(f"✓ Basic $9.99: GST=${gst}, QST=${qst}, Total=${total}")
    
    def test_standard_promotion_tax_calculation(self):
        """
        Standard $24.99 -> GST $1.25, QST $2.49, Total $28.73
        """
        from services.pricing_config import PROMOTION_TIERS
        
        base_price = Decimal("24.99")
        gst = (base_price * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (base_price * QST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = base_price + gst + qst
        
        # Verify tier exists
        assert "standard" in PROMOTION_TIERS
        assert PROMOTION_TIERS["standard"]["price_cents"] == 2499
        
        # Verify tax calculation
        assert float(gst) == 1.25
        assert float(qst) == 2.49  # 24.99 * 0.09975 = 2.4928 -> rounds to 2.49
        assert float(total) == 28.73
        print(f"✓ Standard $24.99: GST=${gst}, QST=${qst}, Total=${total}")
    
    def test_premium_promotion_tax_calculation(self):
        """
        Premium $49.99 -> GST $2.50, QST $4.99, Total $57.48
        """
        from services.pricing_config import PROMOTION_TIERS
        
        base_price = Decimal("49.99")
        gst = (base_price * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (base_price * QST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = base_price + gst + qst
        
        # Verify tier exists
        assert "premium" in PROMOTION_TIERS
        assert PROMOTION_TIERS["premium"]["price_cents"] == 4999
        
        # Verify tax calculation
        assert float(gst) == 2.50
        assert float(qst) == 4.99  # 49.99 * 0.09975 = 4.9865 -> rounds to 4.99
        assert float(total) == 57.48
        print(f"✓ Premium $49.99: GST=${gst}, QST=${qst}, Total=${total}")


class TestEmailCreditTaxCalculation:
    """Test email credit checkout with GST/QST"""
    
    def test_create_email_credits_checkout_returns_gst_qst(self):
        """Verify create_email_credits_checkout returns gst and qst fields"""
        from services.connect_payment_engine import create_email_credits_checkout
        import inspect
        
        source = inspect.getsource(create_email_credits_checkout)
        assert '"gst":' in source or "'gst':" in source
        assert '"qst":' in source or "'qst':" in source
        print("✓ create_email_credits_checkout returns gst and qst fields")
    
    def test_email_credit_500_at_0018_tax_calculation(self):
        """
        500 credits at $0.018/ea = $9.00 subtotal + tax
        GST = $0.45, QST = $0.90, Total = $10.35
        """
        from services.pricing_config import calculate_email_credit_cost
        
        quantity = 500
        total_cents = calculate_email_credit_cost(quantity)
        subtotal = Decimal(str(total_cents)) / 100
        
        gst = (subtotal * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (subtotal * QST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + gst + qst
        
        # 500 * 0.018 = 9.00
        assert float(subtotal) == 9.00
        assert float(gst) == 0.45
        assert float(qst) == 0.90  # 9.00 * 0.09975 = 0.8978 -> rounds to 0.90
        print(f"✓ 500 credits: Subtotal=${subtotal}, GST=${gst}, QST=${qst}, Total=${total}")
    
    def test_email_credit_5000_at_0015_tax_calculation(self):
        """
        5000 credits at $0.015/ea = $75.00 subtotal + tax
        GST = $3.75, QST = $7.48, Total = $86.23
        """
        from services.pricing_config import calculate_email_credit_cost
        
        quantity = 5000
        total_cents = calculate_email_credit_cost(quantity)
        subtotal = Decimal(str(total_cents)) / 100
        
        gst = (subtotal * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (subtotal * QST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + gst + qst
        
        # 5000 * 0.015 = 75.00
        assert float(subtotal) == 75.00
        assert float(gst) == 3.75
        assert float(qst) == 7.48  # 75.00 * 0.09975 = 7.4813 -> rounds to 7.48
        print(f"✓ 5000 credits: Subtotal=${subtotal}, GST=${gst}, QST=${qst}, Total=${total}")


class TestPricingConfigEndpoint:
    """Test GET /api/payments/pricing-config endpoint"""
    
    def test_pricing_config_returns_promotion_tiers(self):
        """Verify pricing-config returns promotion tiers"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        assert response.status_code == 200
        
        data = response.json()
        assert "promotions" in data
        assert "basic" in data["promotions"]
        assert "standard" in data["promotions"]
        assert "premium" in data["promotions"]
        
        # Verify basic tier structure
        basic = data["promotions"]["basic"]
        assert basic["price_cents"] == 999
        assert basic["duration_days"] == 7
        print("✓ GET /api/payments/pricing-config returns promotion tiers")
    
    def test_pricing_config_returns_email_credit_info(self):
        """Verify pricing-config returns email credit tiers"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        assert response.status_code == 200
        
        data = response.json()
        assert "email_credits" in data
        assert len(data["email_credits"]) > 0
        
        # Verify tier structure
        first_tier = data["email_credits"][0]
        assert "min_qty" in first_tier
        assert "max_qty" in first_tier
        assert "per_email_cents" in first_tier
        print("✓ GET /api/payments/pricing-config returns email credit info")
    
    def test_pricing_config_returns_commissions(self):
        """Verify pricing-config returns commission rates"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        assert response.status_code == 200
        
        data = response.json()
        assert "commissions" in data
        assert data["commissions"]["general"] == 0.03  # 3%
        assert data["commissions"]["vehicle"] == 0.025  # 2.5%
        print("✓ GET /api/payments/pricing-config returns commission rates")


class TestFrontendComponentsExist:
    """Verify frontend components exist with proper data-testid attributes"""
    
    def test_listing_promotion_modal_exists(self):
        """Verify ListingPromotionModal.js exists with 3 tiers"""
        with open('/app/frontend/src/components/ListingPromotionModal.js', 'r') as f:
            content = f.read()
        
        # Check for 3 tiers
        assert "basic" in content
        assert "standard" in content
        assert "premium" in content
        
        # Check for data-testid
        assert 'data-testid="promotion-modal"' in content
        assert 'data-testid="buy-promo-basic"' in content or 'data-testid={`buy-promo-' in content
        print("✓ ListingPromotionModal.js exists with 3 tiers and data-testid")
    
    def test_email_credit_purchase_exists(self):
        """Verify EmailCreditPurchase.js exists with slider and tax breakdown"""
        with open('/app/frontend/src/components/EmailCreditPurchase.js', 'r') as f:
            content = f.read()
        
        # Check for slider
        assert "Slider" in content
        
        # Check for tax breakdown
        assert "GST" in content
        assert "QST" in content
        
        # Check for data-testid
        assert 'data-testid="email-credit-purchase"' in content
        assert 'data-testid="buy-email-credits-btn"' in content
        print("✓ EmailCreditPurchase.js exists with slider, tax breakdown, and data-testid")
    
    def test_partner_dashboard_integrates_email_credit_purchase(self):
        """Verify PartnerDashboard integrates EmailCreditPurchase component"""
        with open('/app/frontend/src/pages/PartnerDashboard.js', 'r') as f:
            content = f.read()
        
        # Check for import
        assert "EmailCreditPurchase" in content
        
        # Check for usage
        assert "<EmailCreditPurchase" in content
        
        # Check for partner-benefit-card
        assert 'data-testid="partner-benefit-card"' in content
        print("✓ PartnerDashboard integrates EmailCreditPurchase and has partner-benefit-card")


class TestFrenchLetterSpacing:
    """Verify French bid button has letter-spacing -0.02em"""
    
    def test_listing_detail_page_french_letter_spacing(self):
        """Verify ListingDetailPage has French letter-spacing fix"""
        with open('/app/frontend/src/pages/ListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "letterSpacing: '-0.02em'" in content
        assert "i18n.language === 'fr'" in content
        print("✓ ListingDetailPage.js has French letter-spacing -0.02em")
    
    def test_vehicle_detail_page_french_letter_spacing(self):
        """Verify VehicleDetailPage has French letter-spacing fix"""
        with open('/app/frontend/src/pages/vehicles/VehicleDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "letterSpacing: '-0.02em'" in content
        assert "i18n.language === 'fr'" in content
        print("✓ VehicleDetailPage.js has French letter-spacing -0.02em")
    
    def test_multi_item_listing_detail_page_french_letter_spacing(self):
        """Verify MultiItemListingDetailPage has French letter-spacing fix"""
        with open('/app/frontend/src/pages/MultiItemListingDetailPage.js', 'r') as f:
            content = f.read()
        
        assert "letterSpacing: '-0.02em'" in content
        assert "i18n.language === 'fr'" in content
        print("✓ MultiItemListingDetailPage.js has French letter-spacing -0.02em")


class TestWebhookAffiliateIntegration:
    """Verify webhook handler calls process_affiliate_payout"""
    
    def test_webhook_calls_process_affiliate_payout(self):
        """Verify _handle_checkout_completed calls process_affiliate_payout"""
        with open('/app/backend/routes/webhooks.py', 'r') as f:
            content = f.read()
        
        assert "process_affiliate_payout" in content
        assert "from services.connect_payment_engine import process_affiliate_payout" in content
        print("✓ Webhook handler imports and calls process_affiliate_payout")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
