"""
iter371 — Zero-credit hotfix launch-gate tests.

Coverage:
  FIX A — Listing.is_tax_free override wins over seller_account_type.
          Set on the "Absolute Multi-Lot Clearance" listing so it renders as
          tax-free (private sale from a broker's personal items).
  FIX B — Terms-of-service PDF endpoint no longer depends on weasyprint;
          uses reportlab (already installed).
  FIX C — Global ScrollToTop hardened: three failsafes + hash/query skip.
  FIX D — MaskedBidHistory usable from ListingDetailPage and
          MultiItemListingDetailPage; PublicBidHistory replaced.
  FIX E — Fees button gets spellcheck=false + translate=no (no browser
          spellcheck-squiggle overlay under "Fees").
"""
from pathlib import Path

ROOT = Path("/app")


def read(path: str) -> str:
    return (ROOT / path.lstrip("/")).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
#  FIX A — listing.is_tax_free override
# ─────────────────────────────────────────────────────────────────────────────

def test_fees_preview_reads_listing_is_tax_free_override():
    src = read("backend/routes/auctions_bids.py")
    # Reads the explicit `is_tax_free` flag before falling back to seller type.
    assert 'listing.get("is_tax_free")' in src
    assert "listing_tax_free_override is True" in src
    assert "listing_tax_free_override is False" in src


# ─────────────────────────────────────────────────────────────────────────────
#  FIX B — PDF via reportlab, no more weasyprint
# ─────────────────────────────────────────────────────────────────────────────

def test_terms_pdf_uses_reportlab_not_weasyprint():
    src = read("backend/routes/listings.py")
    assert "from weasyprint" not in src
    assert "from reportlab" in src or "reportlab" in src
    # Uses SimpleDocTemplate + Response so it works out of the box.
    assert "SimpleDocTemplate" in src
    assert "media_type=\"application/pdf\"" in src


# ─────────────────────────────────────────────────────────────────────────────
#  FIX C — Global scroll-to-top hardened
# ─────────────────────────────────────────────────────────────────────────────

def test_scroll_to_top_has_all_failsafes():
    src = read("frontend/src/components/ScrollToTop.js")
    # useLayoutEffect (immediate) + requestAnimationFrame (post-paint) +
    # multiple timeouts (60 ms / 300 ms / 700 ms) for async content settlement.
    assert "useLayoutEffect" in src
    assert "requestAnimationFrame" in src
    assert "forceScrollTop" in src
    # Skips when the URL has an anchor / deep-link param so hash-scroll +
    # ?lot=N / ?buy_now=1 keep working.
    assert "hash" in src
    assert "/[?&](lot|buy_now|target_lot)=/" in src


# ─────────────────────────────────────────────────────────────────────────────
#  FIX D — MaskedBidHistory covers both single + multi-lot pages
# ─────────────────────────────────────────────────────────────────────────────

def test_masked_bid_history_supports_both_endpoints():
    src = read("frontend/src/components/MaskedBidHistory.jsx")
    # Component accepts listingId (single listing) or (auctionId, lotNumber).
    assert "listingId" in src
    assert "/listings/${listingId}/bids-public" in src
    assert "/multi-item-listings/${auctionId}/lots/${lotNumber}/bids-public" in src


def test_single_listing_bids_public_endpoint_exists():
    src = read("backend/routes/auctions_bids.py")
    assert "@bids_router.get(\"/listings/{listing_id}/bids-public\")" in src
    # Same shape as multi-lot version.
    assert "get_listing_bids_public" in src
    assert "\"leading_bidder_initials\": leader_initials" in src


def test_listing_and_multi_listing_pages_use_masked_bid_history():
    listing_src = read("frontend/src/pages/ListingDetailPage.js")
    multi_src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    assert "MaskedBidHistory" in listing_src
    assert "MaskedBidHistory" in multi_src
    # PublicBidHistory (unmasked, leaks pseudo-names) no longer used.
    assert "<PublicBidHistory" not in multi_src


# ─────────────────────────────────────────────────────────────────────────────
#  FIX E — Fees button spellcheck / translate flags to kill overlay
# ─────────────────────────────────────────────────────────────────────────────

def test_fees_button_disables_browser_spellcheck_and_translate():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # Buttons + inner spans opt-out of spell-check and Google Translate so
    # they don't render coloured squiggles / overlay markup under "Fees".
    assert "spellCheck={false}" in src
    assert 'translate="no"' in src
    # aria-label was already stripped in iter370 — still gone.
    assert "aria-label={isFR ? 'Frais additionnels' : 'Additional fees'}" not in src
