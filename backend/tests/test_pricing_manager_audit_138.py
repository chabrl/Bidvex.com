"""
BidVex Master Pricing Structure Audit - Iteration 138
Tests all 7 pricing rules per the Master Pricing Structure specification.

Rules tested:
1. Tier rates: Standard 5%/4%, Premium 3.5%/2.5%, VIP 3%/2%, Partner 0%/3%
2. Vehicle: buyer pays 2.5% platform fee only, seller $0
3. Non-vehicle Stripe: buyer=hammer+BP+stripe+tax; Cash: split invoices
4. Stripe recovery = (fees × 0.029) + 0.30
5. Tax on fees only, never hammer. Province lookup verified.
6. Subscriptions same formula
7. Split invoices per transaction type
"""

import pytest
import requests
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ============= DIRECT IMPORT TESTS =============

class TestPricingManagerImports:
    """Test that PricingManager class exists and has all required methods"""
    
    def test_pricing_manager_exists(self):
        """PricingManager class should be importable"""
        from services.pricing_manager import PricingManager
        assert PricingManager is not None
        print("✓ PricingManager class exists")
    
    def test_vehicle_auction_method_exists(self):
        """PricingManager.vehicle_auction should exist and return PricingResult"""
        from services.pricing_manager import PricingManager, PricingResult
        result = PricingManager.vehicle_auction(
            hammer_price=1000.0,
            buyer_province="QC",
            buyer_tier="free"
        )
        assert isinstance(result, PricingResult)
        assert result.transaction_type == "vehicle"
        print("✓ PricingManager.vehicle_auction exists and returns PricingResult")
    
    def test_non_vehicle_stripe_method_exists(self):
        """PricingManager.non_vehicle_stripe should exist and return PricingResult"""
        from services.pricing_manager import PricingManager, PricingResult
        result = PricingManager.non_vehicle_stripe(
            hammer_price=1000.0,
            buyer_province="QC",
            buyer_tier="free",
            seller_tier="free"
        )
        assert isinstance(result, PricingResult)
        assert result.transaction_type == "non_vehicle_stripe"
        print("✓ PricingManager.non_vehicle_stripe exists and returns PricingResult")
    
    def test_non_vehicle_cash_method_exists(self):
        """PricingManager.non_vehicle_cash should exist and return PricingResult"""
        from services.pricing_manager import PricingManager, PricingResult
        result = PricingManager.non_vehicle_cash(
            hammer_price=500.0,
            buyer_province="AB",
            buyer_tier="free",
            seller_tier="free"
        )
        assert isinstance(result, PricingResult)
        assert result.transaction_type == "non_vehicle_cash"
        print("✓ PricingManager.non_vehicle_cash exists and returns PricingResult")
    
    def test_flat_purchase_method_exists(self):
        """PricingManager.flat_purchase should exist and return PricingResult"""
        from services.pricing_manager import PricingManager, PricingResult
        result = PricingManager.flat_purchase(
            base_price=300.0,
            buyer_province="ON",
            label="Subscription"
        )
        assert isinstance(result, PricingResult)
        assert result.transaction_type == "flat_purchase"
        print("✓ PricingManager.flat_purchase exists and returns PricingResult")


class TestTierRates:
    """Rule 1: Verify tier-based rates match Master Pricing Structure"""
    
    def test_standard_tier_rates(self):
        """Standard tier: 5% buyer premium, 4% seller commission"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        # Standard/free/basic all map to 5%/4%
        assert BUYER_PREMIUM_RATES.get("free") == Decimal("0.05")
        assert BUYER_PREMIUM_RATES.get("basic") == Decimal("0.05")
        assert BUYER_PREMIUM_RATES.get("standard") == Decimal("0.05")
        
        assert SELLER_COMMISSION_RATES.get("free") == Decimal("0.04")
        assert SELLER_COMMISSION_RATES.get("basic") == Decimal("0.04")
        assert SELLER_COMMISSION_RATES.get("standard") == Decimal("0.04")
        print("✓ Standard tier: 5% BP, 4% SC")
    
    def test_premium_tier_rates(self):
        """Premium tier: 3.5% buyer premium, 2.5% seller commission"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        assert BUYER_PREMIUM_RATES.get("premium") == Decimal("0.035")
        assert SELLER_COMMISSION_RATES.get("premium") == Decimal("0.025")
        print("✓ Premium tier: 3.5% BP, 2.5% SC")
    
    def test_vip_tier_rates(self):
        """VIP tier: 3% buyer premium, 2% seller commission"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        assert BUYER_PREMIUM_RATES.get("vip") == Decimal("0.03")
        assert BUYER_PREMIUM_RATES.get("vip_elite") == Decimal("0.03")
        
        assert SELLER_COMMISSION_RATES.get("vip") == Decimal("0.02")
        assert SELLER_COMMISSION_RATES.get("vip_elite") == Decimal("0.02")
        print("✓ VIP tier: 3% BP, 2% SC")
    
    def test_partner_tier_rates(self):
        """Partner tier: 0% buyer premium, 3% seller commission"""
        from services.pricing_manager import BUYER_PREMIUM_RATES, SELLER_COMMISSION_RATES
        
        assert BUYER_PREMIUM_RATES.get("partner") == Decimal("0")
        assert SELLER_COMMISSION_RATES.get("partner") == Decimal("0.03")
        print("✓ Partner tier: 0% BP, 3% SC")


class TestProvincialTaxRates:
    """Rule 5: Verify provincial tax rates match Master Pricing Structure"""
    
    def test_quebec_tax_rate(self):
        """QC: GST+QST = 14.975%"""
        from services.vehicle_pricing import calculate_taxes
        tax = calculate_taxes(Decimal("100"), "QC")
        
        assert tax.tax_type == "GST+QST"
        assert tax.total_rate == Decimal("0.14975")
        print(f"✓ QC: {tax.tax_type} at {float(tax.total_rate)*100:.3f}%")
    
    def test_ontario_tax_rate(self):
        """ON: HST = 13%"""
        from services.vehicle_pricing import calculate_taxes
        tax = calculate_taxes(Decimal("100"), "ON")
        
        assert tax.tax_type == "HST"
        assert tax.total_rate == Decimal("0.13")
        print(f"✓ ON: {tax.tax_type} at {float(tax.total_rate)*100:.0f}%")
    
    def test_alberta_tax_rate(self):
        """AB: GST = 5%"""
        from services.vehicle_pricing import calculate_taxes
        tax = calculate_taxes(Decimal("100"), "AB")
        
        assert tax.tax_type == "GST"
        assert tax.total_rate == Decimal("0.05")
        print(f"✓ AB: {tax.tax_type} at {float(tax.total_rate)*100:.0f}%")
    
    def test_bc_tax_rate_gst_only(self):
        """BC: GST = 5% (NOT 12% GST+PST per Master Structure)"""
        from services.vehicle_pricing import calculate_taxes
        tax = calculate_taxes(Decimal("100"), "BC")
        
        assert tax.tax_type == "GST", f"BC should be GST only, got {tax.tax_type}"
        assert tax.total_rate == Decimal("0.05"), f"BC should be 5%, got {float(tax.total_rate)*100}%"
        print(f"✓ BC: {tax.tax_type} at {float(tax.total_rate)*100:.0f}% (NOT GST+PST)")
    
    def test_manitoba_tax_rate_gst_only(self):
        """MB: GST = 5% (NOT 12% GST+RST per Master Structure)"""
        from services.vehicle_pricing import calculate_taxes
        tax = calculate_taxes(Decimal("100"), "MB")
        
        assert tax.tax_type == "GST", f"MB should be GST only, got {tax.tax_type}"
        assert tax.total_rate == Decimal("0.05"), f"MB should be 5%, got {float(tax.total_rate)*100}%"
        print(f"✓ MB: {tax.tax_type} at {float(tax.total_rate)*100:.0f}% (NOT GST+RST)")
    
    def test_saskatchewan_tax_rate_gst_only(self):
        """SK: GST = 5% (NOT 11% GST+PST per Master Structure)"""
        from services.vehicle_pricing import calculate_taxes
        tax = calculate_taxes(Decimal("100"), "SK")
        
        assert tax.tax_type == "GST", f"SK should be GST only, got {tax.tax_type}"
        assert tax.total_rate == Decimal("0.05"), f"SK should be 5%, got {float(tax.total_rate)*100}%"
        print(f"✓ SK: {tax.tax_type} at {float(tax.total_rate)*100:.0f}% (NOT GST+PST)")
    
    def test_hst_provinces_15_percent(self):
        """NS/NB/NL/PE: HST = 15%"""
        from services.vehicle_pricing import calculate_taxes
        
        for prov in ["NS", "NB", "NL", "PE"]:
            tax = calculate_taxes(Decimal("100"), prov)
            assert tax.tax_type == "HST", f"{prov} should be HST"
            assert tax.total_rate == Decimal("0.15"), f"{prov} should be 15%"
            print(f"✓ {prov}: {tax.tax_type} at {float(tax.total_rate)*100:.0f}%")


class TestVehicleAuctionPricing:
    """Rule 2: Vehicle auctions - buyer pays 2.5% platform fee only, seller $0"""
    
    def test_vehicle_qc_1000_hammer(self):
        """
        Proof 1: Vehicle QC $1000 hammer → buyer_total = $29.93
        
        Calculation:
        - Platform fee: $1000 × 2.5% = $25.00
        - Stripe recovery: ($25.00 × 0.029) + $0.30 = $1.03
        - Taxable: $25.00 + $1.03 = $26.03
        - Tax (14.975%): $26.03 × 0.14975 = $3.90
        - Total: $25.00 + $1.03 + $3.90 = $29.93
        """
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(
            hammer_price=1000.0,
            buyer_province="QC",
            buyer_tier="free"
        )
        
        bi = result.buyer_invoice
        
        # Verify platform fee is 2.5%
        assert bi.fees_subtotal == 25.0, f"Platform fee should be $25.00, got ${bi.fees_subtotal}"
        
        # Verify stripe recovery formula: (fees × 0.029) + 0.30
        expected_stripe = round(25.0 * 0.029 + 0.30, 2)
        assert abs(bi.stripe_recovery - expected_stripe) < 0.01, f"Stripe recovery should be ${expected_stripe}, got ${bi.stripe_recovery}"
        
        # Verify tax type
        assert bi.tax_type == "GST+QST", f"Tax type should be GST+QST, got {bi.tax_type}"
        
        # Verify total is $29.93
        assert abs(bi.total - 29.93) < 0.02, f"Buyer total should be $29.93, got ${bi.total}"
        
        # Verify seller invoice is None (seller pays $0)
        assert result.seller_invoice is None, "Seller invoice should be None for vehicles"
        
        print(f"✓ Vehicle QC $1000: buyer_total=${bi.total:.2f} (expected $29.93)")
    
    def test_vehicle_on_1000_hammer(self):
        """Vehicle ON $1000 hammer - uses HST 13%"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(
            hammer_price=1000.0,
            buyer_province="ON",
            buyer_tier="free"
        )
        
        bi = result.buyer_invoice
        
        # Verify tax type is HST
        assert bi.tax_type == "HST", f"Tax type should be HST, got {bi.tax_type}"
        assert bi.tax_rate == 0.13, f"Tax rate should be 13%, got {bi.tax_rate*100}%"
        
        # Calculate expected total
        # Platform fee: $25.00
        # Stripe: $1.03
        # Taxable: $26.03
        # Tax (13%): $3.38
        # Total: $29.41
        expected_total = 25.0 + 1.03 + round(26.03 * 0.13, 2)
        assert abs(bi.total - expected_total) < 0.02, f"Buyer total should be ~${expected_total:.2f}, got ${bi.total}"
        
        print(f"✓ Vehicle ON $1000: buyer_total=${bi.total:.2f}, tax_type={bi.tax_type}")
    
    def test_vehicle_seller_pays_zero(self):
        """Vehicle: seller_invoice is None (seller pays $0)"""
        from services.pricing_manager import PricingManager
        
        result = PricingManager.vehicle_auction(
            hammer_price=50000.0,
            buyer_province="QC",
            buyer_tier="premium"
        )
        
        assert result.seller_invoice is None, "Seller invoice must be None for vehicles"
        print("✓ Vehicle: seller_invoice is None (seller pays $0)")


class TestNonVehicleStripePricing:
    """Rule 3 Path A: Non-vehicle Stripe - buyer=hammer+BP+stripe+tax"""
    
    def test_non_vehicle_stripe_qc_1000(self):
        """
        Proof 2: Non-vehicle Stripe QC $1000 hammer
        - buyer_total = $1059.50
        - seller_payout = $952.33
        
        Buyer calculation:
        - Hammer: $1000.00
        - BP (5%): $50.00
        - Stripe on BP: ($50 × 0.029) + $0.30 = $1.75
        - Taxable: $50.00 + $1.75 = $51.75
        - Tax (14.975%): $7.75
        - Total: $1000 + $50 + $1.75 + $7.75 = $1059.50
        
        Seller calculation:
        - Hammer: $1000.00
        - SC (4%): -$40.00
        - Stripe on SC: -$1.46
        - Tax on fees: -$6.21
        - Net: $1000 - $40 - $1.46 - $6.21 = $952.33
        """
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_stripe(
            hammer_price=1000.0,
            buyer_province="QC",
            buyer_tier="free",
            seller_tier="free"
        )
        
        bi = result.buyer_invoice
        si = result.seller_invoice
        
        # Verify buyer total is $1059.50
        assert abs(bi.total - 1059.50) < 0.10, f"Buyer total should be $1059.50, got ${bi.total}"
        
        # Verify seller payout is $952.33
        assert abs(si.total - 952.33) < 0.10, f"Seller payout should be $952.33, got ${si.total}"
        
        # Verify tax type
        assert bi.tax_type == "GST+QST"
        assert si.tax_type == "GST+QST"
        
        print(f"✓ Non-vehicle Stripe QC $1000: buyer=${bi.total:.2f}, seller=${si.total:.2f}")


class TestNonVehicleCashPricing:
    """Rule 3 Path B: Non-vehicle Cash - split invoices"""
    
    def test_non_vehicle_cash_ab_500(self):
        """
        Proof 4: Non-vehicle Cash AB $500 hammer
        - buyer_total = $27.33
        - seller_total = $21.92
        
        Buyer calculation (fees only, no hammer):
        - BP (5%): $25.00
        - Stripe: ($25 × 0.029) + $0.30 = $1.03
        - Taxable: $26.03
        - Tax (5% GST): $1.30
        - Total: $25 + $1.03 + $1.30 = $27.33
        
        Seller calculation (fees only):
        - SC (4%): $20.00
        - Stripe: ($20 × 0.029) + $0.30 = $0.88
        - Taxable: $20.88
        - Tax (5% GST): $1.04
        - Total: $20 + $0.88 + $1.04 = $21.92
        """
        from services.pricing_manager import PricingManager
        
        result = PricingManager.non_vehicle_cash(
            hammer_price=500.0,
            buyer_province="AB",
            buyer_tier="free",
            seller_tier="free"
        )
        
        bi = result.buyer_invoice
        si = result.seller_invoice
        
        # Verify buyer total is $27.33
        assert abs(bi.total - 27.33) < 0.10, f"Buyer total should be $27.33, got ${bi.total}"
        
        # Verify seller total is $21.92
        assert abs(si.total - 21.92) < 0.10, f"Seller total should be $21.92, got ${si.total}"
        
        # Verify tax type is GST (AB is GST only)
        assert bi.tax_type == "GST", f"Buyer tax type should be GST, got {bi.tax_type}"
        assert si.tax_type == "GST", f"Seller tax type should be GST, got {si.tax_type}"
        
        # Verify hammer is NOT included in buyer invoice (cash = split invoices)
        # Buyer only pays fees, not hammer
        assert bi.fees_subtotal == 25.0, f"Buyer fees should be $25.00, got ${bi.fees_subtotal}"
        
        print(f"✓ Non-vehicle Cash AB $500: buyer=${bi.total:.2f}, seller=${si.total:.2f}")


class TestSubscriptionPricing:
    """Rule 6: Subscriptions use same formula"""
    
    def test_subscription_on_300(self):
        """
        Proof 3: Subscription ON $300 base → total = $349.17
        
        Calculation:
        - Base: $300.00
        - Stripe: ($300 × 0.029) + $0.30 = $9.00
        - Taxable: $309.00
        - Tax (13% HST): $40.17
        - Total: $300 + $9.00 + $40.17 = $349.17
        """
        from services.pricing_manager import PricingManager
        
        result = PricingManager.flat_purchase(
            base_price=300.0,
            buyer_province="ON",
            label="Subscription"
        )
        
        bi = result.buyer_invoice
        
        # Verify total is $349.17
        assert abs(bi.total - 349.17) < 0.10, f"Subscription total should be $349.17, got ${bi.total}"
        
        # Verify tax type is HST
        assert bi.tax_type == "HST", f"Tax type should be HST, got {bi.tax_type}"
        
        # Verify stripe recovery formula
        expected_stripe = round(300.0 * 0.029 + 0.30, 2)
        assert abs(bi.stripe_recovery - expected_stripe) < 0.01
        
        print(f"✓ Subscription ON $300: total=${bi.total:.2f} (expected $349.17)")


class TestStripeRecoveryFormula:
    """Rule 4: Stripe recovery = (fees × 0.029) + 0.30"""
    
    def test_stripe_recovery_formula(self):
        """Verify stripe_recovery function matches formula"""
        from services.pricing_manager import stripe_recovery
        
        test_cases = [
            (Decimal("25.00"), 1.03),   # $25 × 0.029 + 0.30 = 1.025 → 1.03
            (Decimal("50.00"), 1.75),   # $50 × 0.029 + 0.30 = 1.75
            (Decimal("100.00"), 3.19),  # $100 × 0.029 + 0.30 = 3.19
            (Decimal("300.00"), 9.00),  # $300 × 0.029 + 0.30 = 9.00
        ]
        
        for fees, expected in test_cases:
            result = float(stripe_recovery(fees))
            assert abs(result - expected) < 0.02, f"stripe_recovery({fees}) should be {expected}, got {result}"
            print(f"✓ stripe_recovery(${fees}) = ${result:.2f}")


class TestCodePathImports:
    """Verify code paths import PricingManager correctly"""
    
    def test_vehicle_invoice_imports_pricing_manager(self):
        """vehicle_invoice.py should import PricingManager.vehicle_auction"""
        with open('/app/backend/services/vehicle_invoice.py', 'r') as f:
            content = f.read()
        
        assert 'from services.pricing_manager import PricingManager' in content or \
               'PricingManager.vehicle_auction' in content, \
               "vehicle_invoice.py should import/use PricingManager"
        print("✓ vehicle_invoice.py imports PricingManager")
    
    def test_auctions_route_imports_pricing_manager(self):
        """routes/auctions.py Path B should import PricingManager"""
        with open('/app/backend/routes/auctions.py', 'r') as f:
            content = f.read()
        
        assert 'from services.pricing_manager import PricingManager' in content or \
               'PricingManager.non_vehicle_cash' in content, \
               "routes/auctions.py should import/use PricingManager for cash payments"
        print("✓ routes/auctions.py imports PricingManager for Path B")


# ============= API ENDPOINT TESTS =============

def get_admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": "charbel911@gmail.com",
            "password": "Anderosli123!@#"
        }
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    return None


class TestPreviewInvoiceAPI:
    """Test the preview-invoice API endpoint with all proof scenarios"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for API tests"""
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        token = get_admin_token()
        if not token:
            pytest.skip("Could not authenticate as admin")
        
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        })
    
    def test_preview_invoice_vehicle_qc(self):
        """API: Vehicle QC $1000 → buyer_total = $29.93"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/email-templates/preview-invoice",
            json={
                "category": "vehicle",
                "hammer_price": 1000,
                "buyer_province": "QC",
                "buyer_tier": "free",
                "seller_tier": "free"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Response structure: data['invoice']['buyer_invoice']
        invoice = data.get("invoice", {})
        buyer_total = invoice.get("buyer_invoice", {}).get("total", 0)
        assert abs(buyer_total - 29.93) < 0.10, f"Buyer total should be $29.93, got ${buyer_total}"
        
        # Seller invoice should be None for vehicles
        assert invoice.get("seller_invoice") is None, "Seller invoice should be None for vehicles"
        
        print(f"✓ API Vehicle QC: buyer_total=${buyer_total:.2f}")
    
    def test_preview_invoice_vehicle_on(self):
        """API: Vehicle ON $1000 → uses HST 13%"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/email-templates/preview-invoice",
            json={
                "category": "vehicle",
                "hammer_price": 1000,
                "buyer_province": "ON",
                "buyer_tier": "free"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: data['invoice']['buyer_invoice']
        invoice = data.get("invoice", {})
        tax_type = invoice.get("buyer_invoice", {}).get("tax_type", "")
        assert tax_type == "HST", f"Tax type should be HST, got {tax_type}"
        
        tax_rate = invoice.get("buyer_invoice", {}).get("tax_rate", 0)
        assert tax_rate == 0.13, f"Tax rate should be 13%, got {tax_rate*100}%"
        
        print(f"✓ API Vehicle ON: tax_type={tax_type}, tax_rate={tax_rate*100}%")
    
    def test_preview_invoice_non_vehicle_stripe_qc(self):
        """API: Non-vehicle Stripe QC $1000 → buyer=$1059.50, seller=$952.33"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/email-templates/preview-invoice",
            json={
                "category": "non_vehicle_stripe",
                "hammer_price": 1000,
                "buyer_province": "QC",
                "buyer_tier": "free",
                "seller_tier": "free"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: data['invoice']['buyer_invoice'] and data['invoice']['seller_invoice']
        invoice = data.get("invoice", {})
        buyer_total = invoice.get("buyer_invoice", {}).get("total", 0)
        seller_total = invoice.get("seller_invoice", {}).get("total", 0)
        
        assert abs(buyer_total - 1059.50) < 0.10, f"Buyer total should be $1059.50, got ${buyer_total}"
        assert abs(seller_total - 952.33) < 0.10, f"Seller payout should be $952.33, got ${seller_total}"
        
        print(f"✓ API Non-vehicle Stripe QC: buyer=${buyer_total:.2f}, seller=${seller_total:.2f}")
    
    def test_preview_invoice_subscription_on(self):
        """API: Subscription ON $300 → total=$349.17"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/email-templates/preview-invoice",
            json={
                "category": "subscription",
                "hammer_price": 300,
                "buyer_province": "ON",
                "buyer_tier": "free"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: data['invoice']['buyer_invoice']
        invoice = data.get("invoice", {})
        buyer_total = invoice.get("buyer_invoice", {}).get("total", 0)
        assert abs(buyer_total - 349.17) < 0.10, f"Subscription total should be $349.17, got ${buyer_total}"
        
        print(f"✓ API Subscription ON: total=${buyer_total:.2f}")
    
    def test_preview_invoice_non_vehicle_cash_ab(self):
        """API: Non-vehicle Cash AB $500 → buyer=$27.33, seller=$21.92"""
        response = self.session.post(
            f"{BASE_URL}/api/admin/email-templates/preview-invoice",
            json={
                "category": "non_vehicle_cash",
                "hammer_price": 500,
                "buyer_province": "AB",
                "buyer_tier": "free",
                "seller_tier": "free"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Response structure: data['invoice']['buyer_invoice'] and data['invoice']['seller_invoice']
        invoice = data.get("invoice", {})
        buyer_total = invoice.get("buyer_invoice", {}).get("total", 0)
        seller_total = invoice.get("seller_invoice", {}).get("total", 0)
        
        assert abs(buyer_total - 27.33) < 0.10, f"Buyer total should be $27.33, got ${buyer_total}"
        assert abs(seller_total - 21.92) < 0.10, f"Seller total should be $21.92, got ${seller_total}"
        
        print(f"✓ API Non-vehicle Cash AB: buyer=${buyer_total:.2f}, seller=${seller_total:.2f}")


class TestFeeCalculatorTaxRates:
    """Verify fee_calculator.py TAX_RATES table matches Master Structure"""
    
    def test_fee_calculator_bc_gst_only(self):
        """fee_calculator.py: BC should be GST 5% only"""
        from services.fee_calculator import TAX_RATES
        
        bc_rates = TAX_RATES.get("BC", {})
        assert bc_rates.get("combined") == Decimal("0.05"), f"BC combined should be 5%, got {bc_rates.get('combined')}"
        assert bc_rates.get("name") == "GST (5%)", f"BC name should be 'GST (5%)', got {bc_rates.get('name')}"
        print("✓ fee_calculator BC: GST 5%")
    
    def test_fee_calculator_mb_gst_only(self):
        """fee_calculator.py: MB should be GST 5% only"""
        from services.fee_calculator import TAX_RATES
        
        mb_rates = TAX_RATES.get("MB", {})
        assert mb_rates.get("combined") == Decimal("0.05"), f"MB combined should be 5%, got {mb_rates.get('combined')}"
        assert mb_rates.get("name") == "GST (5%)", f"MB name should be 'GST (5%)', got {mb_rates.get('name')}"
        print("✓ fee_calculator MB: GST 5%")
    
    def test_fee_calculator_sk_gst_only(self):
        """fee_calculator.py: SK should be GST 5% only"""
        from services.fee_calculator import TAX_RATES
        
        sk_rates = TAX_RATES.get("SK", {})
        assert sk_rates.get("combined") == Decimal("0.05"), f"SK combined should be 5%, got {sk_rates.get('combined')}"
        assert sk_rates.get("name") == "GST (5%)", f"SK name should be 'GST (5%)', got {sk_rates.get('name')}"
        print("✓ fee_calculator SK: GST 5%")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
