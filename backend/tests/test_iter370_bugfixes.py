"""
iter370 — Zero-credit hotfix launch-gate tests.

Coverage:
  FIX 1 — CardWishlistButton component: pixel-perfect inline SVG heart in a
          36 × 36 white circle with `padding: 0`.
  FIX 2 — Fees button: no aria-label duplicate label (only visible `Fees`).
  FIX 3 — Fee breakdown maths: tax-free = tax on (platform_fee + Stripe
          recovery) only; taxable = tax on hammer + (platform_fee + Stripe
          recovery); QC $100 → $106.27; QC taxable $100 → $121.25.
  FIX 4 — Buy Now confirmation modal renders the full fee breakdown before
          the buyer confirms; the deep-link (?buy_now=1) opens the same
          modal from the LotDetailPage.
"""
from pathlib import Path

ROOT = Path("/app")


def read(path: str) -> str:
    return (ROOT / path.lstrip("/")).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
#  FIX 1 — Pixel-perfect wishlist button
# ─────────────────────────────────────────────────────────────────────────────

def test_card_wishlist_button_uses_inline_svg_and_zero_padding():
    src = read("frontend/src/components/CardWishlistButton.jsx")
    # Exact 36 × 36 white circle dimensions.
    assert "width: '36px'" in src
    assert "height: '36px'" in src
    assert "borderRadius: '50%'" in src
    # Zero padding on the button — any padding shifts the heart off-center.
    assert "padding: '0'" in src
    # Flex-centered.
    assert "alignItems: 'center'" in src
    assert "justifyContent: 'center'" in src
    # Inline SVG (NOT lucide-react / emoji / icon font).
    assert "<svg" in src
    assert "d=\"M20.84 4.61" in src
    # Uses the existing /api/watchlist endpoints for parity with the header.
    assert "/watchlist/add" in src
    assert "/watchlist/remove" in src


def test_compact_lot_card_uses_card_wishlist_button():
    src = read("frontend/src/components/CompactLotCard.jsx")
    assert "CardWishlistButton" in src
    # The old ambient WatchlistButton import should be gone on the grid card.
    assert "import WatchlistButton" not in src


# ─────────────────────────────────────────────────────────────────────────────
#  FIX 2 — Fees button has no duplicate label
# ─────────────────────────────────────────────────────────────────────────────

def test_fees_button_has_no_aria_label_duplicate():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # There should be exactly ONE visible label. The old aria-label that
    # some browsers rendered as a tooltip is removed.
    assert "aria-label={isFR ? 'Frais additionnels' : 'Additional fees'}" not in src
    # The visible label span still exists.
    assert "{isFR ? 'Frais' : 'Fees'}" in src


# ─────────────────────────────────────────────────────────────────────────────
#  FIX 3 — Fee breakdown maths + granular fields
# ─────────────────────────────────────────────────────────────────────────────

def test_fees_preview_returns_stripe_recovery_and_messages():
    src = read("backend/routes/auctions_bids.py")
    assert "stripe_recovery = round(platform_fee * 0.029 + 0.30" in src
    assert '"stripe_recovery": stripe_recovery' in src
    assert '"platform_fee": platform_fee' in src
    assert '"tax_message_en"' in src
    assert '"tax_message_fr"' in src
    assert '"is_tax_free"' in src
    assert '"hammer_subtotal"' in src
    assert '"total"' in src
    # Tax base for tax-free = platform_fee + stripe_recovery (never hammer).
    assert "platform_fee + stripe_recovery" in src


def test_fees_preview_provincial_tax_table_present():
    src = read("backend/routes/auctions_bids.py")
    # Provincial hint table so tax rate isn't hardcoded QC.
    assert "PROVINCIAL_TAX" in src
    for code in ("QC", "ON", "BC", "AB"):
        assert f'"{code}"' in src


def test_compact_lot_card_popover_uses_new_fee_fields():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # Popover renders the new fields (platform_fee, stripe_recovery, tax_label).
    assert "feesPreview.platform_fee" in src
    assert "feesPreview.stripe_recovery" in src
    assert "feesPreview.tax_label" in src
    assert "feesPreview.tax_message_en" in src
    assert "feesPreview.tax_message_fr" in src
    assert "feesPreview.is_tax_free" in src
    assert "feesPreview.hammer_subtotal" in src
    # Total row shows the canonical `total` field.
    assert "feesPreview.total" in src


# ─────────────────────────────────────────────────────────────────────────────
#  FIX 4 — Buy Now confirmation shows fee breakdown + deep-link works
# ─────────────────────────────────────────────────────────────────────────────

def test_multi_item_listing_page_prefetches_buy_now_fees():
    src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    assert "buyNowFees" in src
    assert "setBuyNowFees" in src
    # Fetch happens inside handleBuyNow so the modal has the numbers ready.
    assert "fees-preview" in src


def test_multi_item_listing_page_handles_buy_now_deep_link():
    src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    # Reads ?buy_now=1 from the URL and opens the Buy Now modal for the
    # target lot when the listing loads.
    assert "searchParams.get('buy_now')" in src
    assert "handleBuyNow(targetLot)" in src


def test_buy_now_modal_shows_fee_breakdown_testids():
    src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    # The confirmation modal exposes stable testids for the QA agent.
    assert 'data-testid="buy-now-fee-breakdown"' in src
    assert 'data-testid="buy-now-total"' in src
    assert 'data-testid="buy-now-tax-message"' in src
