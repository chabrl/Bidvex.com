"""
[DEPRECATED — iteration 106 audit, superseded by iteration 165 spec]

Encoded pre-165 pricing math (tax on Hammer + Premium for buyer; partner
buyer_premium attribution differed from current spec).
Replacement: `test_seller_type_pricing_165.py`. Skipped at runtime.

BidVex Fee Schedule Audit - Iteration 106
Tests all pricing configurations against official BidVex fee document.

FIXES VERIFIED:
1. Subscription checkout (Premium $180, VIP $300, Partner $100) now includes GST/QST as separate line items
2. Frontend EmailCreditPurchase.js tier boundaries/rates aligned to backend

CORE RATES VERIFIED:
- §7.1 Standard 5%/4%, Premium 3.5%/2.5%, VIP Elite 3%/2%
- §7.2 Partner $100 annual, BidVex keeps ONLY 3% commission
- §7.3 Vehicle Platform Fee = 2.5%
- §7.4 GST 5% + QST 9.975% on (Hammer + Premium)
- §7.5 14-day overdue cron, 2%/month penalty
"""
import pytest
pytestmark = pytest.mark.skip(
    reason="Superseded by test_seller_type_pricing_165.py (iteration 165 spec)"
)

import pytest
import os
from decimal import Decimal, ROUND_HALF_UP

# Import pricing config directly for unit testing
import sys
sys.path.insert(0, '/app/backend')

from services.pricing_config import (
    BUYER_PREMIUM_RATES,
    SELLER_COMMISSION_RATES,
    SUBSCRIPTION_TIERS,
    EMAIL_RATES_DOLLARS,
    EMAIL_CREDIT_TIERS,
    PLATFORM_FEE_GENERAL,
    PLATFORM_FEE_VEHICLE,
    GST_RATE,
    QST_RATE,
    calculate_email_credit_cost,
    get_buyer_premium_rate,
    get_seller_commission_rate,
    get_platform_fee_rate,
)

from services.connect_payment_engine import (
    calculate_connect_checkout,
    build_itemized_line_items,
    _to_cents,
)


class TestTierRates:
    """§7.1 - User Tier Commission Rates"""
    
    def test_standard_tier_buyer_premium_5_percent(self):
        """Standard tier buyer premium = 5%"""
        assert BUYER_PREMIUM_RATES["free"] == Decimal("0.05")
        assert BUYER_PREMIUM_RATES["basic"] == Decimal("0.05")
        assert BUYER_PREMIUM_RATES["standard"] == Decimal("0.05")
        assert get_buyer_premium_rate("free") == Decimal("0.05")
        print("✓ Standard tier buyer premium = 5%")
    
    def test_standard_tier_seller_commission_4_percent(self):
        """Standard tier seller commission = 4%"""
        assert SELLER_COMMISSION_RATES["free"] == Decimal("0.04")
        assert SELLER_COMMISSION_RATES["basic"] == Decimal("0.04")
        assert SELLER_COMMISSION_RATES["standard"] == Decimal("0.04")
        assert get_seller_commission_rate("free") == Decimal("0.04")
        print("✓ Standard tier seller commission = 4%")
    
    def test_premium_tier_buyer_premium_3_5_percent(self):
        """Premium tier buyer premium = 3.5%"""
        assert BUYER_PREMIUM_RATES["premium"] == Decimal("0.035")
        assert get_buyer_premium_rate("premium") == Decimal("0.035")
        print("✓ Premium tier buyer premium = 3.5%")
    
    def test_premium_tier_seller_commission_2_5_percent(self):
        """Premium tier seller commission = 2.5%"""
        assert SELLER_COMMISSION_RATES["premium"] == Decimal("0.025")
        assert get_seller_commission_rate("premium") == Decimal("0.025")
        print("✓ Premium tier seller commission = 2.5%")
    
    def test_vip_elite_tier_buyer_premium_3_percent(self):
        """VIP Elite tier buyer premium = 3%"""
        assert BUYER_PREMIUM_RATES["vip"] == Decimal("0.03")
        assert BUYER_PREMIUM_RATES["vip_elite"] == Decimal("0.03")
        assert get_buyer_premium_rate("vip") == Decimal("0.03")
        print("✓ VIP Elite tier buyer premium = 3%")
    
    def test_vip_elite_tier_seller_commission_2_percent(self):
        """VIP Elite tier seller commission = 2%"""
        assert SELLER_COMMISSION_RATES["vip"] == Decimal("0.02")
        assert SELLER_COMMISSION_RATES["vip_elite"] == Decimal("0.02")
        assert get_seller_commission_rate("vip") == Decimal("0.02")
        print("✓ VIP Elite tier seller commission = 2%")


class TestPartnerTier:
    """§7.2 - Partner Annual Fee and Commission Structure"""
    
    def test_partner_annual_fee_100_cad(self):
        """Partner annual fee = $100 CAD (10000 cents). iter326 — value now derived from
        canonical services.subscription_pricing.DEFAULT_PLANS["partner"]."""
        assert SUBSCRIPTION_TIERS["partner"]["amount_cents"] == 10000
        assert SUBSCRIPTION_TIERS["partner"]["currency"] == "cad"
        assert SUBSCRIPTION_TIERS["partner"]["interval"] == "year"
        print("✓ Partner annual fee = $100 CAD (10000 cents)")
    
    def test_partner_flow_bidvex_keeps_only_3_percent_commission(self):
        """Partner flow: BidVex keeps ONLY 3% commission (general), 0% of buyer premium"""
        breakdown = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="partner",
            seller_is_partner=True,
        )
        
        assert breakdown["flow_type"] == "PARTNER_FLOW"
        assert breakdown["seller_is_partner"] == True
        
        # BidVex keeps only 3% platform commission
        expected_platform_fee = 5000 * 0.03  # $150
        assert breakdown["platform_fee"] == expected_platform_fee
        
        # Application fee = seller commission = platform fee for partners
        assert breakdown["application_fee"] == breakdown["seller_commission"]
        assert breakdown["seller_commission"] == expected_platform_fee
        
        # Partner retains 100% of buyer premium
        expected_buyer_premium = 5000 * 0.05  # $250 (5% standard rate)
        assert breakdown["buyer_premium"] == expected_buyer_premium
        assert breakdown["partner_premium_retained"] == expected_buyer_premium
        
        print(f"✓ Partner flow: BidVex keeps ${breakdown['application_fee']:.2f} (3% of $5000)")
        print(f"✓ Partner retains ${breakdown['partner_premium_retained']:.2f} buyer premium")


class TestVehiclePlatformFee:
    """§7.3 - Vehicle Platform Fee"""
    
    def test_vehicle_platform_fee_2_5_percent(self):
        """Vehicle platform fee = 2.5% (overrides standard 3%)"""
        assert PLATFORM_FEE_VEHICLE == Decimal("0.025")
        assert get_platform_fee_rate("vehicle") == Decimal("0.025")
        assert get_platform_fee_rate("car") == Decimal("0.025")
        assert get_platform_fee_rate("auto") == Decimal("0.025")
        assert get_platform_fee_rate("truck") == Decimal("0.025")
        assert get_platform_fee_rate("motorcycle") == Decimal("0.025")
        print("✓ Vehicle platform fee = 2.5%")
    
    def test_general_platform_fee_3_percent(self):
        """General platform fee = 3%"""
        assert PLATFORM_FEE_GENERAL == Decimal("0.03")
        assert get_platform_fee_rate("general") == Decimal("0.03")
        assert get_platform_fee_rate("electronics") == Decimal("0.03")
        print("✓ General platform fee = 3%")


class TestTaxCalculation:
    """§7.4 - GST/QST Tax Calculation"""
    
    def test_gst_rate_5_percent(self):
        """GST rate = 5%"""
        assert GST_RATE == Decimal("0.05")
        print("✓ GST rate = 5%")
    
    def test_qst_rate_9_975_percent(self):
        """QST rate = 9.975%"""
        assert QST_RATE == Decimal("0.09975")
        print("✓ QST rate = 9.975%")
    
    def test_tax_on_hammer_plus_premium_5000_general(self):
        """$5000 general auction: taxable = $5250, GST = $262.50, QST = $523.69"""
        breakdown = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=False,
        )
        
        # Taxable = Hammer + Buyer Premium = $5000 + $250 (5%) = $5250
        expected_taxable = 5000 + (5000 * 0.05)  # $5250
        assert breakdown["taxable_amount"] == expected_taxable
        
        # GST = $5250 * 5% = $262.50
        expected_gst = round(5250 * 0.05, 2)  # $262.50
        assert breakdown["gst"] == expected_gst
        
        # QST = $5250 * 9.975% = $523.69 (rounded)
        expected_qst = round(5250 * 0.09975, 2)  # $523.69
        assert breakdown["qst"] == expected_qst
        
        print(f"✓ $5000 general: taxable=${breakdown['taxable_amount']}, GST=${breakdown['gst']}, QST=${breakdown['qst']}")
    
    def test_separate_gst_qst_line_items_in_checkout(self):
        """build_itemized_line_items() returns separate GST and QST line items"""
        breakdown = calculate_connect_checkout(
            hammer_price=5000.0,
            category="general",
            buyer_tier="free",
            seller_tier="free",
            seller_is_partner=False,
        )
        
        line_items = build_itemized_line_items(
            breakdown=breakdown,
            listing_title="Test Auction",
            is_vehicle=False,
        )
        
        # Find GST and QST line items
        gst_item = next((item for item in line_items if "GST" in item["price_data"]["product_data"]["name"]), None)
        qst_item = next((item for item in line_items if "QST" in item["price_data"]["product_data"]["name"]), None)
        
        assert gst_item is not None, "GST line item should exist"
        assert qst_item is not None, "QST line item should exist"
        
        # Verify amounts
        gst_cents = gst_item["price_data"]["unit_amount"]
        qst_cents = qst_item["price_data"]["unit_amount"]
        
        assert gst_cents == 26250, f"GST should be 26250 cents, got {gst_cents}"
        assert qst_cents == 52369, f"QST should be 52369 cents, got {qst_cents}"
        
        print(f"✓ Separate GST line item: {gst_cents} cents")
        print(f"✓ Separate QST line item: {qst_cents} cents")


class TestOverduePayments:
    """§7.5 - Overdue Payment Processing"""
    
    def test_late_penalty_2_percent_per_month(self):
        """Late penalty = 2% * months_late * hammer_price"""
        # Test calculation logic (from scheduled_jobs.py)
        hammer_price = 5000
        days_late = 30  # 1 month
        months_late = max(1, (days_late + 29) // 30)  # = 1
        penalty_rate = 0.02 * months_late  # = 0.02
        penalty_amount = round(hammer_price * penalty_rate, 2)  # = $100
        
        assert months_late == 1
        assert penalty_rate == 0.02
        assert penalty_amount == 100.0
        print(f"✓ 1 month late on $5000: penalty = ${penalty_amount}")
        
        # Test 2 months late
        days_late = 60
        months_late = max(1, (days_late + 29) // 30)  # = 2
        penalty_rate = 0.02 * months_late  # = 0.04
        penalty_amount = round(hammer_price * penalty_rate, 2)  # = $200
        
        assert months_late == 2
        assert penalty_rate == 0.04
        assert penalty_amount == 200.0
        print(f"✓ 2 months late on $5000: penalty = ${penalty_amount}")


class TestEmailCreditPricing:
    """FIX: Email credit tier alignment between frontend and backend"""
    
    def test_email_rates_tier_1_to_1000(self):
        """1-1000 emails = $0.018/email"""
        tier = EMAIL_RATES_DOLLARS[0]
        assert tier["min_qty"] == 1
        assert tier["max_qty"] == 1000
        assert tier["rate"] == Decimal("0.018")
        print("✓ Tier 1-1000: $0.018/email")
    
    def test_email_rates_tier_1001_to_5000(self):
        """1001-5000 emails = $0.015/email"""
        tier = EMAIL_RATES_DOLLARS[1]
        assert tier["min_qty"] == 1001
        assert tier["max_qty"] == 5000
        assert tier["rate"] == Decimal("0.015")
        print("✓ Tier 1001-5000: $0.015/email")
    
    def test_email_rates_tier_5001_to_10000(self):
        """5001-10000 emails = $0.012/email"""
        tier = EMAIL_RATES_DOLLARS[2]
        assert tier["min_qty"] == 5001
        assert tier["max_qty"] == 10000
        assert tier["rate"] == Decimal("0.012")
        print("✓ Tier 5001-10000: $0.012/email")
    
    def test_email_rates_tier_10001_plus(self):
        """10001+ emails = $0.010/email"""
        tier = EMAIL_RATES_DOLLARS[3]
        assert tier["min_qty"] == 10001
        assert tier["max_qty"] is None
        assert tier["rate"] == Decimal("0.010")
        print("✓ Tier 10001+: $0.010/email")
    
    def test_calculate_email_credit_cost_500_qty(self):
        """FIX: calculate_email_credit_cost(500) returns 900 cents ($9.00 = 500 * $0.018)"""
        cost_cents = calculate_email_credit_cost(500)
        expected = 500 * 0.018 * 100  # 900 cents
        assert cost_cents == 900, f"Expected 900 cents, got {cost_cents}"
        print(f"✓ 500 emails = {cost_cents} cents ($9.00)")
    
    def test_calculate_email_credit_cost_5000_qty(self):
        """FIX: calculate_email_credit_cost(5000) returns 7500 cents ($75.00 = 5000 * $0.015)"""
        cost_cents = calculate_email_credit_cost(5000)
        expected = 5000 * 0.015 * 100  # 7500 cents
        assert cost_cents == 7500, f"Expected 7500 cents, got {cost_cents}"
        print(f"✓ 5000 emails = {cost_cents} cents ($75.00)")
    
    def test_calculate_email_credit_cost_10000_qty(self):
        """calculate_email_credit_cost(10000) returns 12000 cents ($120.00 = 10000 * $0.012)"""
        cost_cents = calculate_email_credit_cost(10000)
        expected = 10000 * 0.012 * 100  # 12000 cents
        assert cost_cents == 12000, f"Expected 12000 cents, got {cost_cents}"
        print(f"✓ 10000 emails = {cost_cents} cents ($120.00)")
    
    def test_calculate_email_credit_cost_15000_qty(self):
        """calculate_email_credit_cost(15000) returns 15000 cents ($150.00 = 15000 * $0.010)"""
        cost_cents = calculate_email_credit_cost(15000)
        expected = 15000 * 0.010 * 100  # 15000 cents
        assert cost_cents == 15000, f"Expected 15000 cents, got {cost_cents}"
        print(f"✓ 15000 emails = {cost_cents} cents ($150.00)")


class TestSubscriptionPricing:
    """FIX: Subscription checkout GST/QST line items"""
    
    def test_premium_subscription_180_cad(self):
        """Premium subscription = $180 CAD (18000 cents)"""
        assert SUBSCRIPTION_TIERS["premium"]["amount_cents"] == 18000
        print("✓ Premium subscription = $180 CAD")
    
    def test_vip_subscription_300_cad(self):
        """VIP subscription = $300 CAD (30000 cents)"""
        assert SUBSCRIPTION_TIERS["vip"]["amount_cents"] == 30000
        print("✓ VIP subscription = $300 CAD")
    
    def test_partner_subscription_100_cad(self):
        """Partner subscription = $100 CAD (10000 cents)"""
        assert SUBSCRIPTION_TIERS["partner"]["amount_cents"] == 10000
        print("✓ Partner subscription = $100 CAD")
    
    def test_premium_subscription_gst_qst_calculation(self):
        """Premium $180: GST=$9.00, QST=$17.96, Total=$206.96"""
        base = Decimal("180.00")
        gst = (base * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (base * Decimal("0.09975")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = base + gst + qst
        
        assert gst == Decimal("9.00"), f"Expected GST $9.00, got ${gst}"
        assert qst == Decimal("17.96"), f"Expected QST $17.96, got ${qst}"
        assert total == Decimal("206.96"), f"Expected total $206.96, got ${total}"
        
        print(f"✓ Premium $180: GST=${gst}, QST=${qst}, Total=${total}")
    
    def test_vip_subscription_gst_qst_calculation(self):
        """VIP $300: GST=$15.00, QST=$29.93, Total=$344.93"""
        base = Decimal("300.00")
        gst = (base * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (base * Decimal("0.09975")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = base + gst + qst
        
        assert gst == Decimal("15.00"), f"Expected GST $15.00, got ${gst}"
        assert qst == Decimal("29.93"), f"Expected QST $29.93, got ${qst}"
        assert total == Decimal("344.93"), f"Expected total $344.93, got ${total}"
        
        print(f"✓ VIP $300: GST=${gst}, QST=${qst}, Total=${total}")
    
    def test_partner_subscription_gst_qst_calculation(self):
        """Partner $100: GST=$5.00, QST=$9.98, Total=$114.98"""
        base = Decimal("100.00")
        gst = (base * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (base * Decimal("0.09975")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = base + gst + qst
        
        assert gst == Decimal("5.00"), f"Expected GST $5.00, got ${gst}"
        assert qst == Decimal("9.98"), f"Expected QST $9.98, got ${qst}"
        assert total == Decimal("114.98"), f"Expected total $114.98, got ${total}"
        
        print(f"✓ Partner $100: GST=${gst}, QST=${qst}, Total=${total}")


class TestSubscriptionCheckoutLineItems:
    """FIX: Verify subscription checkout creates separate GST/QST line items in subscriptions.py"""
    
    def test_subscription_checkout_code_has_gst_qst_line_items(self):
        """Verify subscriptions.py has GST/QST line items in create_subscription_checkout"""
        import ast
        
        with open('/app/backend/routes/subscriptions.py', 'r') as f:
            content = f.read()
        
        # Check for GST line item
        assert '"GST (TPS 5%)"' in content, "GST line item name not found"
        assert 'gst_cents' in content, "gst_cents variable not found"
        
        # Check for QST line item
        assert '"QST (TVQ 9.975%)"' in content, "QST line item name not found"
        assert 'qst_cents' in content, "qst_cents variable not found"
        
        # Check for 3 line items in the else branch (one-time payment mode)
        # The code should have base + GST + QST = 3 line items
        assert 'checkout_params["line_items"] = [' in content, "line_items array not found"
        
        print("✓ subscriptions.py has GST/QST as separate line items")
    
    def test_subscription_checkout_gst_qst_calculation_code(self):
        """Verify the GST/QST calculation code in subscriptions.py"""
        with open('/app/backend/routes/subscriptions.py', 'r') as f:
            content = f.read()
        
        # Check for correct GST calculation
        assert 'Decimal("0.05")' in content, "GST rate 0.05 not found"
        
        # Check for correct QST calculation
        assert 'Decimal("0.09975")' in content, "QST rate 0.09975 not found"
        
        # Check for ROUND_HALF_UP
        assert 'ROUND_HALF_UP' in content, "ROUND_HALF_UP not found"
        
        print("✓ subscriptions.py has correct GST/QST calculation code")


class TestFrontendEmailCreditAlignment:
    """FIX: Verify frontend EmailCreditPurchase.js matches backend rates"""
    
    def test_frontend_email_tiers_match_backend(self):
        """Verify EmailCreditPurchase.js EMAIL_TIERS matches backend EMAIL_RATES_DOLLARS"""
        with open('/app/frontend/src/components/EmailCreditPurchase.js', 'r') as f:
            content = f.read()
        
        # Check tier 1: 1-1000 = $0.018
        assert '{ min: 1, max: 1000, per_email: 0.018 }' in content, "Tier 1-1000 $0.018 not found"
        
        # Check tier 2: 1001-5000 = $0.015
        assert '{ min: 1001, max: 5000, per_email: 0.015 }' in content, "Tier 1001-5000 $0.015 not found"
        
        # Check tier 3: 5001-10000 = $0.012
        assert '{ min: 5001, max: 10000, per_email: 0.012 }' in content, "Tier 5001-10000 $0.012 not found"
        
        # Check tier 4: 10001+ = $0.010
        assert '{ min: 10001, max: 100000, per_email: 0.010 }' in content, "Tier 10001+ $0.010 not found"
        
        print("✓ Frontend EMAIL_TIERS matches backend EMAIL_RATES_DOLLARS")


class TestScheduledJobsExist:
    """§7.5 - Verify scheduled jobs exist"""
    
    def test_process_overdue_auction_payments_exists(self):
        """Verify process_overdue_auction_payments function exists in scheduled_jobs.py"""
        from services.scheduled_jobs import process_overdue_auction_payments
        assert callable(process_overdue_auction_payments)
        print("✓ process_overdue_auction_payments function exists")
    
    def test_send_auction_payment_reminders_exists(self):
        """Verify send_auction_payment_reminders function exists in scheduled_jobs.py"""
        from services.scheduled_jobs import send_auction_payment_reminders
        assert callable(send_auction_payment_reminders)
        print("✓ send_auction_payment_reminders function exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
