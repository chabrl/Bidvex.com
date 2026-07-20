"""
iter366 — Regression tripwires for the 3 fixes in this fork:
  Item 1: Compare button = small circular icon-only, bottom-14 right-2 (above timer strip).
  Item 2: Buyer payment receipt email uses the redesigned structure.
  Item 3: Unsubscribe URL in email footer resolves to a signed one-click token URL.
"""
import os
import re


# ═══════════════════════════════════════════════════════════════════════
# Item 1 — Compare button repositioned + icon-only
# ═══════════════════════════════════════════════════════════════════════

def test_compare_checkbox_is_icon_only_no_text_label():
    text = open("/app/frontend/src/components/CompareBar.jsx", "r", encoding="utf-8").read()
    # w-8 h-8 rounded-full → small circular icon.
    assert "w-8 h-8 rounded-full" in text
    # aria-label references the label for a11y.
    assert "aria-label=" in text
    # The visible text label (`<span>{t.label}</span>`) is gone — only icon.
    assert "<span>{t.label}</span>" not in text


def test_compare_button_positioned_bottom_14_right_2_on_all_cards():
    for p in (
        "/app/frontend/src/components/FlattenedMarketplace.js",
        "/app/frontend/src/pages/LotsMarketplacePage.js",
        "/app/frontend/src/pages/storage/StorageAuctionCard.js",
        "/app/frontend/src/components/vehicles/VehicleListingCard.js",
    ):
        text = open(p, "r", encoding="utf-8").read()
        # The wrapper positions the button ABOVE the timer strip (bottom-3).
        # bottom-14 = 56px = safely above the timer + bid-count row.
        assert "bottom-14 right-2" in text, f"{p} missing bottom-14 right-2 Compare positioning"
        # The old bottom-2 right-2 (which overlaps the timer strip) must be gone.
        assert 'bottom-2 right-2 z-20" onClick={(e) => e.stopPropagation()}>\n            <CompareCheckbox' not in text
        assert 'bottom-2 left-2 z-20' not in text  # Old iter364 position removed


# ═══════════════════════════════════════════════════════════════════════
# Item 2 — Redesigned buyer receipt email
# ═══════════════════════════════════════════════════════════════════════

def test_receipt_seller_name_and_order_number_populated():
    text = open("/app/backend/services/receipts.py", "r", encoding="utf-8").read()
    # `seller_name` + `order_number` are enriched onto the receipt dict.
    assert 'base["seller_name"]' in text
    assert 'base["order_number"]' in text
    # BVX-XXXXXXXX (8 chars) shape
    assert 'f"BVX-{_short}"' in text


def test_receipt_email_has_all_five_sections():
    """The redesigned buyer receipt must include: success header, purchase-info,
    price breakdown with TOTAL PAID, pickup section, payment info."""
    text = open("/app/backend/services/emails/email_system.py", "r", encoding="utf-8").read()
    # 1. Success heading
    assert '"Payment Successful"' in text
    assert '"Paiement r&eacute;ussi"' in text
    # 2. Purchase Information — labelled rows
    assert '"Purchase Information"' in text
    assert '"Informations d\'achat"' in text
    # 3. TOTAL PAID visually highlighted
    assert '"TOTAL PAID"' in text
    assert '"TOTAL PAY&Eacute;"' in text
    # 4. Pickup heading + help text
    assert '"YOUR PICKUP CODE"' in text
    assert '"VOTRE CODE DE COLLECTE"' in text
    assert "Show this code to the seller" in text
    # 5. Payment Information section
    assert '"Payment Information"' in text
    assert "Transaction ID:" in text


def test_receipt_email_no_stale_old_heading():
    """The old 'Payment Receipt' generic heading + minimal layout is gone."""
    text = open("/app/backend/services/emails/email_system.py", "r", encoding="utf-8").read()
    # The old copy said "here is your receipt for <strong>{title}</strong>. Thank you for bidding on BidVex."
    assert "Thank you for bidding on BidVex" not in text
    assert "here is your receipt for" not in text


# ═══════════════════════════════════════════════════════════════════════
# Item 3 — Unsubscribe URL works
# ═══════════════════════════════════════════════════════════════════════

def test_list_unsubscribe_header_uses_signed_token_url():
    """The `List-Unsubscribe` header must resolve to /unsubscribe?token=..."""
    text = open("/app/backend/services/emails/_email_core.py", "r", encoding="utf-8").read()
    # Old broken URL scheme (?email=…) must NOT be the primary path any more.
    assert 'unsub_url = f"https://bidvex.com/unsubscribe?email={to_email}"' not in text
    # build_unsubscribe_urls() is now used.
    assert "build_unsubscribe_urls(to_email)" in text


def test_base_template_has_visible_unsubscribe_placeholder():
    text = open("/app/backend/services/emails/_email_core.py", "r", encoding="utf-8").read()
    # The visible in-body link uses the placeholder that gets filled per-email.
    assert "{{UNSUBSCRIBE_URL}}" in text or "{{{{UNSUBSCRIBE_URL}}}}" in text
    assert "Don&apos;t want marketing emails" in text
    assert "Transactional emails" in text


def test_send_via_unified_replaces_unsubscribe_placeholder():
    text = open("/app/backend/services/emails/_email_core.py", "r", encoding="utf-8").read()
    # Placeholder replacement runs BEFORE the SendGrid Mail() is constructed.
    assert 'if "{{UNSUBSCRIBE_URL}}" in html_content:' in text
    assert 'html_content.replace("{{UNSUBSCRIBE_URL}}"' in text


def test_unsubscribe_page_frontend_reads_token_query():
    text = open("/app/frontend/src/pages/UnsubscribePage.js", "r", encoding="utf-8").read()
    # Frontend must call the API with the token from ?token=.
    assert "auto-verify" in text or "/unsubscribe/verify" in text
    assert "searchParams.get" in text
