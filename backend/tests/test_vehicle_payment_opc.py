"""
OPC compliance tests for Vehicle Payment Infrastructure (P0 fix).

Covers:
  - PricingManager.vehicle_auction numeric correctness + province tax matrix
  - send_auction_won_email HTML output (vehicle, non-vehicle, cross-border, back-compat)
  - vehicle_payment.PaymentService source-level verification (capture_method='manual',
    process_deposit_refund, capture_deposit)
  - vehicle_auction_handler source-level verification (no apply_deposit_credit, uses
    process_deposit_refund for winner + losers)
  - routes/vehicles.py bid placement accepts deposit status 'paid' OR 'authorized'

NOTE: No live Stripe/SendGrid calls — send_email is monkeypatched to capture HTML.
"""
import os
import re
import sys
import inspect
import pytest
from pathlib import Path

# Ensure backend on sys.path so `import services.*` works
BACKEND_DIR = Path("/app/backend")
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ─── Pricing ──────────────────────────────────────────────────────────
# PricingManager.vehicle_auction
class TestVehiclePricing:
    def test_vehicle_qc_10000_canonical(self):
        from services.pricing_manager import PricingManager
        r = PricingManager.vehicle_auction(10000, "QC")
        assert r.transaction_type == "vehicle"
        assert r.hammer_price == 10000
        assert r.seller_invoice is None, "Seller must receive zero / no invoice"
        assert r.buyer_invoice.fees_subtotal == 250.00
        assert r.buyer_invoice.total == 296.12, f"got {r.buyer_invoice.total}"
        assert r.buyer_invoice.tax_type == "GST+QST"
        # Ensure hammer price is NOT a line item buyer pays (only a label)
        hammer_lines = [ln for ln in r.buyer_invoice.lines if ln.line_type == "hammer"]
        assert hammer_lines == [], "Buyer invoice must not include hammer line"

    @pytest.mark.parametrize(
        "prov,tax_type,rate",
        [
            ("QC", "GST+QST", 0.14975),
            ("ON", "HST", 0.13),
            ("AB", "GST", 0.05),
            ("BC", "GST", 0.05),
        ],
    )
    def test_vehicle_province_tax(self, prov, tax_type, rate):
        from services.pricing_manager import PricingManager
        r = PricingManager.vehicle_auction(10000, prov)
        assert r.buyer_invoice.tax_type == tax_type
        assert abs(r.buyer_invoice.tax_rate - rate) < 1e-6, (
            f"{prov}: expected {rate}, got {r.buyer_invoice.tax_rate}"
        )
        assert r.buyer_invoice.fees_subtotal == 250.00
        assert r.seller_invoice is None


# ─── Email: send_auction_won_email ────────────────────────────────────
@pytest.fixture
def captured_email(monkeypatch):
    """Monkeypatch send_email to capture html_content instead of sending."""
    from services import email_notifications as en

    captured = {}

    async def fake_send_email(to_email, subject, html_content, attachments=None):
        captured["to_email"] = to_email
        captured["subject"] = subject
        captured["html_content"] = html_content
        return {"status": "logged"}

    monkeypatch.setattr(en, "send_email", fake_send_email)
    return captured


class TestAuctionWonEmail:
    @pytest.mark.asyncio
    async def test_vehicle_notice_bilingual(self, captured_email):
        from services.email_notifications import send_auction_won_email
        await send_auction_won_email(
            to_email="buyer@example.com",
            to_name="Alice",
            auction_id="veh-123",
            item_name="2020 Toyota Camry",
            hammer_price=10000.00,
            platform_fee=250.00,
            seller_name="Bob Dealer",
            seller_contact="bob@dealer.com",
            is_vehicle=True,
            is_cross_border=False,
            buyer_province="QC",
        )
        html = captured_email["html_content"]
        # EN + FR headlines
        assert "VEHICLE PAYMENT NOTICE" in html
        assert "AVIS DE PAIEMENT DU V" in html  # accent-safe
        # Seller info
        assert "Bob Dealer" in html
        assert "bob@dealer.com" in html
        # EN $ formatting
        assert "$10,000.00" in html
        assert "$250.00" in html
        # FR $ suffix formatting: "10 000,00 $" and "250,00 $"
        assert re.search(r"10\s000,00\s?\$", html), "FR hammer format missing"
        assert "250,00" in html and "$" in html
        # Subject indicates vehicle
        assert "Vehicle" in captured_email["subject"]

    @pytest.mark.asyncio
    async def test_non_vehicle_no_notice(self, captured_email):
        from services.email_notifications import send_auction_won_email
        await send_auction_won_email(
            to_email="b@x.com",
            to_name="Bob",
            auction_id="a1",
            item_name="Rare Coin",
            hammer_price=500.00,
            platform_fee=25.00,
            is_vehicle=False,
        )
        html = captured_email["html_content"]
        assert "VEHICLE PAYMENT NOTICE" not in html
        assert "AVIS DE PAIEMENT" not in html
        assert "Complete Payment" in html

    @pytest.mark.asyncio
    async def test_cross_border_notice(self, captured_email):
        from services.email_notifications import send_auction_won_email
        await send_auction_won_email(
            to_email="b@x.com",
            to_name="Bob",
            auction_id="a1",
            item_name="Car",
            hammer_price=8000.00,
            platform_fee=200.00,
            is_vehicle=True,
            is_cross_border=True,
            buyer_province="ON",
        )
        html = captured_email["html_content"]
        assert "Cross-Border" in html or "cross-border" in html.lower()
        # FR portion
        assert "fronti" in html.lower()  # frontières
        assert "(ON)" in html

    @pytest.mark.asyncio
    async def test_back_compat_legacy_kwargs(self, captured_email):
        from services.email_notifications import send_auction_won_email
        # Legacy caller — uses winner_email/winner_name/item_title/final_price/listing_id
        result = await send_auction_won_email(
            winner_email="legacy@x.com",
            winner_name="Legacy",
            item_title="Old Item",
            final_price=1234.56,
            listing_id="legacy-1",
            payment_deadline="2026-02-01",
        )
        assert result is not None
        html = captured_email["html_content"]
        assert "Old Item" in html
        assert "$1,234.56" in html
        assert captured_email["to_email"] == "legacy@x.com"
        assert "VEHICLE PAYMENT NOTICE" not in html  # default is_vehicle=False


# ─── vehicle_payment.py source-level verification ────────────────────
class TestVehiclePaymentService:
    def test_create_deposit_checkout_manual_capture_in_source(self):
        src = Path("/app/backend/services/vehicle_payment.py").read_text()
        # Extract create_deposit_checkout method body
        assert "async def create_deposit_checkout" in src
        # payment_intent_data with capture_method='manual' must be present
        assert re.search(
            r"payment_intent_data\s*=\s*\{[^}]*['\"]capture_method['\"]\s*:\s*['\"]manual['\"]",
            src,
            re.DOTALL,
        ), "capture_method='manual' not found inside payment_intent_data"

    def test_payment_service_has_refund_and_capture_methods(self):
        from services.vehicle_payment import PaymentService
        assert hasattr(PaymentService, "process_deposit_refund")
        assert hasattr(PaymentService, "capture_deposit")
        # Both must be coroutines
        assert inspect.iscoroutinefunction(PaymentService.process_deposit_refund)
        assert inspect.iscoroutinefunction(PaymentService.capture_deposit)
        # Signatures
        refund_sig = inspect.signature(PaymentService.process_deposit_refund)
        capture_sig = inspect.signature(PaymentService.capture_deposit)
        assert "deposit_id" in refund_sig.parameters
        assert "deposit_id" in capture_sig.parameters

    def test_refund_cancels_pi_capture_captures_pi_source(self):
        src = Path("/app/backend/services/vehicle_payment.py").read_text()
        # process_deposit_refund body must contain stripe.PaymentIntent.cancel
        assert "stripe.PaymentIntent.cancel" in src, "refund must cancel PI"
        # capture_deposit must call stripe.PaymentIntent.capture
        assert "stripe.PaymentIntent.capture" in src, "capture_deposit must capture PI"
        # Status transitions
        assert '"status": "released"' in src or "'status': 'released'" in src
        assert '"status": "captured"' in src or "'status': 'captured'" in src


# ─── vehicle_auction_handler.py source-level verification ────────────
class TestAuctionHandlerDepositFlow:
    def test_no_apply_deposit_credit_and_uses_refund(self):
        src = Path("/app/backend/services/vehicle_auction_handler.py").read_text()
        # Must NOT call legacy apply_deposit_credit
        assert "apply_deposit_credit" not in src, (
            "process_ended_auction must not call apply_deposit_credit (OPC fix)"
        )
        # Must call process_deposit_refund (at least twice — winner + losers)
        occurrences = src.count("process_deposit_refund")
        assert occurrences >= 2, (
            f"process_deposit_refund should be called for winner AND losers; "
            f"found {occurrences} occurrence(s)"
        )
        # Winner release reason tag present
        assert "winner_fee_charged_separately" in src
        assert "non_winning_bidder" in src


# ─── routes/vehicles.py bid placement accepts 'authorized' ──────────
class TestBidRouteDepositStatus:
    def test_deposit_status_check_accepts_authorized(self):
        src = Path("/app/backend/routes/vehicles.py").read_text()
        # The query must accept BOTH 'paid' and 'authorized'
        # Match e.g. status: {"$in": ["paid", "authorized"]}
        pattern = r'status["\']\s*:\s*\{\s*["\']?\$in["\']?\s*:\s*\[[^\]]*["\']paid["\'][^\]]*["\']authorized["\']'
        pattern_rev = r'status["\']\s*:\s*\{\s*["\']?\$in["\']?\s*:\s*\[[^\]]*["\']authorized["\'][^\]]*["\']paid["\']'
        assert re.search(pattern, src) or re.search(pattern_rev, src), (
            "Bid-placement deposit check must accept both 'paid' and 'authorized' statuses"
        )
