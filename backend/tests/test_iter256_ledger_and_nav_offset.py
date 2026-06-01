"""
iter256 — Mobile nav offset boost + Annual Partner Fee ledger correction.

Test roster (4 tests):
  1. All 3 B2B dashboards carry pt-16+ safe-area padding to clear the
     promo banner + fixed nav stack on mobile.
  2. The literal string "$499.00" is NOT present anywhere in
     PartnerDashboard.js — the hardcoded placeholder is gone.
  3. PartnerDashboard.js renders the corrected "Annual Partner Fee"
     label (not "Listing Fee") tied to the ledger-listing-fee data-testid.
  4. Default base fee fallback in the ledger and validate POST is $100.
"""
from __future__ import annotations

import os
import re


FRONTEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "pages")
)


def _read(rel):
    with open(os.path.join(FRONTEND, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def test_iter256_b2b_dashboards_have_promo_banner_safe_padding():
    """Each B2B dashboard outer wrapper must carry pt-16 or higher to
    clear the promo banner + fixed nav stack on mobile."""
    for rel, testid in (
        ("PartnerDashboard.js", "partner-dashboard"),
        ("BrokerDashboardPage.jsx", "broker-dashboard-page"),
        ("storage/StorageDashboard.js", "storage-dashboard"),
    ):
        src = _read(rel)
        m = re.search(rf'<div[^>]*data-testid=["\']{re.escape(testid)}["\'][^>]*>', src)
        assert m, f"could not find wrapper {testid} in {rel}"
        chunk = m.group(0)
        pts = [int(g) for g in re.findall(r"\bpt-(\d+)", chunk)]
        assert pts and max(pts) >= 16, f"{rel} {testid} needs pt-16+; found {pts}"


def test_iter256_partner_dashboard_strips_hardcoded_499_listing_fee():
    """The literal "$499" placeholder must be GONE from PartnerDashboard.js."""
    src = _read("PartnerDashboard.js")
    assert "$499" not in src, "$499 placeholder still present in PartnerDashboard.js"
    assert "499.00" not in src
    # The validate POST + ledger fallback must reference 100.
    assert "platform_fee || 100" in src, "default fee fallback must be 100, not 499"


def test_iter256_ledger_renders_annual_partner_fee_label_not_listing_fee():
    """The ledger row anchored at data-testid=ledger-listing-fee MUST
    show "Annual Partner Fee:" — never "Listing Fee:" (BidVex is
    commission-based for listings; the only baseline annual line item
    is the partner program fee)."""
    src = _read("PartnerDashboard.js")
    # Locate the ledger block.
    idx = src.find('data-testid="ledger-listing-fee"')
    assert idx > 0, "ledger-listing-fee data-testid not found"
    # Walk back ~250 chars to find the row label.
    window = src[max(0, idx - 300):idx]
    assert "Annual Partner Fee" in window, (
        "ledger row must say 'Annual Partner Fee:', not 'Listing Fee:'"
    )
    assert "<span>Listing Fee:</span>" not in src


def test_iter256_default_base_amount_in_validate_call_is_100():
    """The POST /api/promotions/validate call from the dashboard must
    use $100 as the base_amount_cad fallback (matches the Annual Partner
    Fee, not the obsolete $499 placeholder)."""
    src = _read("PartnerDashboard.js")
    m = re.search(r"base_amount_cad:\s*Number\(dashboard\?\.platform_fee\s*\|\|\s*(\d+)\)", src)
    assert m, "could not find base_amount_cad fallback in PartnerDashboard.js"
    assert int(m.group(1)) == 100, f"base_amount_cad fallback must be 100, got {m.group(1)}"
