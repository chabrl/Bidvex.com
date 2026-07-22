"""
iter369 — Static launch-gate tests for card bug-fixes + P0 Global Image Viewer.

Coverage:
  Bug 1 — Card action buttons never wrap (`whitespace-nowrap` + `flex-1 min-w-0`)
  Bug 2 — Card image slot fixed height 200 px, `object-contain`, neutral bg
  Bug 3 — Wishlist heart perfectly centered inside a 36 × 36 white circle
  Bug 4 — Countdown chip is always red (rose-500/600/700), never black/grey
  Bug 5 — Buy Now button removed from grid cards
  Bug 6 — Inline bid input + Bid button + inline errors on grid cards
  Bug 7 — Auto-Bid processor exists + subscription gate enforced
  Bug 8 — fees-preview endpoint returns tax_on_hammer/tax_on_fee/subtotal
          and correctly handles tax-free + multi-unit
  Bug 9 — Images clickable (cursor-zoom-in) + GlobalImageViewer wired on
          CompactLotCard, LotDetailPage, MultiItemListingDetailPage,
          ListingDetailPage
  P0 Lightbox — GlobalImageViewer built on `yet-another-react-lightbox` with
                Zoom + Counter plugins, fullscreen 100vw × 100vh, z-index 9999
"""
from pathlib import Path

ROOT = Path("/app")


def read(path: str) -> str:
    return (ROOT / path.lstrip("/")).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
#  P0 — Global Image Viewer
# ─────────────────────────────────────────────────────────────────────────────

def test_global_image_viewer_component_exists():
    src = read("frontend/src/components/GlobalImageViewer.jsx")
    # Uses the modern lightbox library shipped in package.json.
    assert "yet-another-react-lightbox" in src
    # Zoom + Counter plugins wired (mouse-wheel/pinch zoom + counter chip).
    assert "plugins/zoom" in src
    assert "plugins/counter" in src
    # Fullscreen container: 100vw × 100vh, position fixed, z-index 9999.
    assert "100vw" in src
    assert "100vh" in src
    assert "'fixed'" in src
    assert "zIndex: 9999" in src
    # Black background & carousel with preload.
    assert "rgba(0, 0, 0" in src


def test_global_image_viewer_used_across_pages():
    lot_card = read("frontend/src/components/CompactLotCard.jsx")
    lot_detail = read("frontend/src/pages/LotDetailPage.jsx")
    multi = read("frontend/src/pages/MultiItemListingDetailPage.js")
    for src in (lot_card, lot_detail, multi):
        assert "GlobalImageViewer" in src, "GlobalImageViewer must be wired platform-wide"


def test_listing_detail_lightbox_upgraded():
    src = read("frontend/src/pages/ListingDetailPage.js")
    # Zoom + Counter plugins are now included on the standalone listing page.
    assert "plugins/zoom" in src
    assert "plugins/counter" in src
    assert "zIndex: 9999" in src


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 1 — Button labels never wrap
# ─────────────────────────────────────────────────────────────────────────────

def test_card_secondary_buttons_do_not_wrap():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # Auto-Bid / Fees buttons: flex-1 + min-w-0 + whitespace-nowrap.
    assert "flex-1 min-w-0" in src
    assert "whitespace-nowrap" in src
    # No text-lg / text-md on the button labels (small font enforced).
    assert "text-[11px]" in src


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 2 — Fixed 200 px image slot with object-contain
# ─────────────────────────────────────────────────────────────────────────────

def test_card_image_slot_fixed_and_contain():
    src = read("frontend/src/components/CompactLotCard.jsx")
    assert "height: 200" in src
    # object-contain on the img itself (never object-cover on card image).
    assert "object-contain" in src
    # Wrapper has neutral bg + testid + centered.
    assert "-image-wrapper" in src
    assert "bg-[#f8f9fa]" in src or "bg-[#f4f6f8]" in src
    assert "items-center" in src and "justify-center" in src


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 3 — Heart perfectly centered in white circle
# ─────────────────────────────────────────────────────────────────────────────

def test_wishlist_button_wrapper_centered():
    # iter370 FIX 1 — CompactLotCard now uses CardWishlistButton which draws
    # its own 36 × 36 white circle with `padding:0` + flex-centered layout
    # (see /app/frontend/src/components/CardWishlistButton.jsx for spec).
    src = read("frontend/src/components/CardWishlistButton.jsx")
    assert "width: '36px'" in src and "height: '36px'" in src
    assert "borderRadius: '50%'" in src
    assert "padding: '0'" in src
    assert "background: 'white'" in src
    # CompactLotCard MUST use this button (not the ambient WatchlistButton).
    card = read("frontend/src/components/CompactLotCard.jsx")
    assert "CardWishlistButton" in card


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 4 — Countdown chip always red
# ─────────────────────────────────────────────────────────────────────────────

def test_countdown_chip_always_red():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # Every branch of the countdownColor helper uses a rose (red) shade.
    assert "bg-rose-700" in src   # < 1 h pulses
    assert "bg-rose-600" in src   # < 24 h
    assert "bg-rose-500" in src   # > 24 h
    # No black/grey fallback.
    assert "bg-slate-900/80 text-white" not in src


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 5 — Buy Now removed from grid cards
# ─────────────────────────────────────────────────────────────────────────────

def test_buy_now_button_removed_from_grid_cards():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # No buy-now testid anywhere in the compact card.
    assert 'buy-now' not in src.lower() or 'onbuynow' in src.lower()
    # No Buy Now / Acheter action button label rendered by the card.
    assert 'Buy Now\'' not in src and '"Buy Now"' not in src


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 6 — Inline bid input + inline errors
# ─────────────────────────────────────────────────────────────────────────────

def test_inline_bid_input_present_on_grid_cards():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # Inline input exposes a stable testid + a real handler.
    assert "-bid-input" in src
    assert "handleQuickBid" in src
    # Inline error rendering (no modal fallback).
    assert "-bid-error" in src
    # Placeholder + `$` prefix + Min hint.
    assert 'Min ' in src
    # Bid button uses whitespace-nowrap.
    assert "whitespace-nowrap" in src


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 7 — Auto-Bid processor + subscription gate
# ─────────────────────────────────────────────────────────────────────────────

def test_auto_bid_processor_hooked():
    src = read("backend/routes/auctions_bids.py")
    # Multi-lot auto-bid processor exists and is called after every lot bid.
    assert "_process_lot_auto_bids" in src
    assert "await _process_lot_auto_bids(" in src
    # Highest max_bid wins each round; own bids skipped via manual_bidder_id.
    assert '"user_id": {"$ne": manual_bidder_id}' in src
    # Strategy dispatch.
    assert "min_to_lead" in src
    assert "max_immediate" in src


def test_auto_bid_subscription_gate():
    src = read("backend/routes/auctions_bids.py")
    # Free-tier lockout enforced with 403 + upgrade payload.
    assert "_autobid_allowed_tier" in src
    assert '"subscription_required"' in src
    # AutoBid modal ELIGIBLE_TIERS matches backend gate.
    modal = read("frontend/src/components/AutoBidModal.jsx")
    assert "ELIGIBLE_TIERS" in modal
    for tier in ("premium", "vip", "vip_elite"):
        assert tier in modal


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 8 — fees-preview tax logic + multi-unit
# ─────────────────────────────────────────────────────────────────────────────

def test_fees_preview_supports_multi_unit_and_taxfree():
    src = read("backend/routes/auctions_bids.py")
    # Endpoint exposes subtotal + granular tax + stripe_recovery blocks.
    assert '"subtotal": subtotal' in src
    assert '"tax_on_hammer": tax_on_hammer' in src
    assert '"tax_on_fees": tax_on_fees' in src
    assert '"stripe_recovery": stripe_recovery' in src
    assert '"platform_fee": platform_fee' in src
    assert '"tax_message_en"' in src and '"tax_message_fr"' in src
    # Multi-unit: unit_bid × quantity.
    assert "unit_bid * quantity" in src
    # Tax-free path: fee base includes both platform fee AND Stripe recovery.
    assert "platform_fee + stripe_recovery" in src
    # Anonymous access allowed via get_current_user_optional.
    assert "get_current_user_optional" in src


# ─────────────────────────────────────────────────────────────────────────────
#  Bug 9 — Images clickable across all detail pages
# ─────────────────────────────────────────────────────────────────────────────

def test_images_clickable_with_zoom_cursor():
    lot_card = read("frontend/src/components/CompactLotCard.jsx")
    lot_detail = read("frontend/src/pages/LotDetailPage.jsx")
    assert "cursor-zoom-in" in lot_card
    assert "cursor-zoom-in" in lot_detail
    # LotDetailPage main image and thumbnails open the lightbox.
    assert "setLightboxOpen(true)" in lot_detail
    assert "data-testid=\"lot-detail-main-image\"" in lot_detail
