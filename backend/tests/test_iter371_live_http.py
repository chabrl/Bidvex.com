"""
iter371 live HTTP verification — hits the deployed backend via
REACT_APP_BACKEND_URL to prove that the code shipped in the container is
returning the expected shape for each of the 5 iter371 fixes.

FIX A — /api/multi-item-listings/{id}/lots/{n}/fees-preview override
FIX D — /api/multi-item-listings/{id}/terms/pdf serves valid PDF
FIX E — /api/listings/{id}/bids-public shape + masked initials + IP
"""
import os
import requests
import pytest

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com"
).rstrip("/")

LISTING_ID = "179b62b9-fa28-4140-b36d-f5903b033f48"  # Absolute Multi-Lot Clearance

TIMEOUT = 60  # cold-start friendly


# ─────────────────────────────────────────────────────────────────────────────
#  FIX A — fees-preview honours listing.is_tax_free override
# ─────────────────────────────────────────────────────────────────────────────

class TestFeesPreviewIsTaxFree:
    def test_fees_preview_returns_tax_free_true(self):
        url = f"{BASE_URL}/api/multi-item-listings/{LISTING_ID}/lots/1/fees-preview"
        r = requests.get(url, params={"bid_amount": 100}, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("is_tax_free") is True, d
        assert d.get("tax_on_hammer") == 0, d
        assert d.get("seller_account_type") == "individual", d
        # Public confirmation of the override having landed:
        assert d.get("tax_status") == "tax_free", d

    def test_fees_preview_math_bid_100_qty_2(self):
        """qty=2 × $100 → subtotal 200, BP 5% = 10, stripe recovery ≈ 0.59,
        tax_on_fees (14.975% of 10 + 0.59) ≈ 1.59; total 212.18 per spec."""
        url = f"{BASE_URL}/api/multi-item-listings/{LISTING_ID}/lots/1/fees-preview"
        r = requests.get(url, params={"bid_amount": 100}, timeout=TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d.get("hammer_subtotal") == 200.0, d
        assert d.get("platform_fee") == 10.0, d
        assert d.get("tax_on_hammer") == 0.0, d
        assert 210 <= d.get("total", 0) <= 213, f"total out of spec: {d}"
        # Spec explicit value from review request
        assert d.get("total") == 212.18, d


# ─────────────────────────────────────────────────────────────────────────────
#  FIX D — terms PDF endpoint returns a valid PDF
# ─────────────────────────────────────────────────────────────────────────────

class TestTermsPdf:
    def test_terms_pdf_returns_valid_pdf(self):
        url = f"{BASE_URL}/api/multi-item-listings/{LISTING_ID}/terms/pdf"
        r = requests.get(url, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
        assert r.content.startswith(b"%PDF-"), r.content[:20]
        assert len(r.content) > 500, len(r.content)


# ─────────────────────────────────────────────────────────────────────────────
#  FIX E — bids-public endpoints (multi-lot + single-listing)
# ─────────────────────────────────────────────────────────────────────────────

class TestBidsPublicEndpoints:
    def test_multi_lot_bids_public_shape(self):
        """The multi-lot bids-public endpoint should already be live and return
        the canonical shape MaskedBidHistory consumes."""
        url = f"{BASE_URL}/api/multi-item-listings/{LISTING_ID}/lots/1/bids-public"
        r = requests.get(url, timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        for key in ("total_bids", "unique_bidders", "leading_bidder_initials", "bids"):
            assert key in body, f"missing key {key}: {body.keys()}"
        assert isinstance(body["bids"], list)
        # No privacy leaks
        for b in body["bids"]:
            assert "bidder_name" not in b, f"privacy leak: {b}"
            assert "bidder_email" not in b, f"privacy leak: {b}"
            assert "ip_address" not in b, f"privacy leak: {b}"

    def test_single_listing_bids_public_endpoint_exists(self):
        """Even a made-up id should NOT 500; either 404 or 200 with an empty
        body — proves the route is registered."""
        r = requests.get(
            f"{BASE_URL}/api/listings/does-not-exist-xyz/bids-public", timeout=TIMEOUT
        )
        assert r.status_code in (200, 404), r.status_code

    def test_single_listing_bids_public_shape_when_present(self):
        """Look for a *real* single-listing (id without _lot_). If none exists
        on this env, skip — but still assert 404 semantics from the previous
        test prove the route works."""
        r = requests.get(f"{BASE_URL}/api/listings?limit=100&skip=0", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:200]
        rows = r.json()
        if not isinstance(rows, list):
            pytest.skip("no /api/listings array on this env")
        singles = [
            x for x in rows
            if isinstance(x, dict) and "_lot_" not in (x.get("id") or "")
        ]
        if not singles:
            pytest.skip("no true single-listings on this preview env")
        lid = singles[0]["id"]
        rr = requests.get(f"{BASE_URL}/api/listings/{lid}/bids-public", timeout=TIMEOUT)
        assert rr.status_code == 200, rr.text[:200]
        body = rr.json()
        for key in ("total_bids", "unique_bidders", "leading_bidder_initials", "bids"):
            assert key in body
        for b in body["bids"]:
            assert "bidder_name" not in b
            assert "ip_address" not in b
            assert "initials" in b
            assert "ip_masked" in b
