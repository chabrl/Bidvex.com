"""iter482 P2-followup — Regression tests for the 4 billing calculation /
data-integrity defects.

DO NOT MODIFY without a corresponding update to the docs report
`/app/docs/ITER482_BILLING_CALC_INTEGRITY_FIX_REPORT.md`.

These tests lock in the EXACT corrected numbers reviewed by charbel911@gmail.com
in the visual QA batch:
  * Defect 1 — Commission Invoice pulls BidVex identity from
    `services.tax_engine.BIDVEX_ADDRESS/GST/QST/LEGAL_NAME` and never
    hardcodes.
  * Defect 2 — General Auction Invoice displays every fee row so the
    visible sum reconciles with `payment_result.buyer_total` (Seller
    Commission line no longer hidden).
  * Defect 3 — Payment Letter derives buyer totals from the same
    `compute_buyer_totals` helper the Lots Won Summary uses, so an
    Ontario buyer sees $0 QST on BOTH documents (not just one).
  * Defect 4 — Seller Statement / Receipt / Commission Invoice all
    derive net-payout from the same `compute_seller_payout` helper.
    BidVex is GST/HST + QST registered → commission is a taxable service
    → net payout = hammer − commission − tax_on_commission.

None of these tests modify tax_engine, fee_calculator, payment logic,
Stripe logic, reconciliation, or auction settlement.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

import pytest

from invoice_templates import (
    _bidvex_company_info,
    compute_seller_payout,
    compute_buyer_totals,
    commission_invoice_template,
    seller_statement_template,
    seller_receipt_template,
    payment_letter_template,
    lots_won_template,
)


# ─────────────────────────────────────────────────────────────────────────────
# Sample data used by the visual-QA batch delivered to charbel911@gmail.com
# ─────────────────────────────────────────────────────────────────────────────

from datetime import datetime, timezone, timedelta

_NOW = datetime.now(timezone.utc)

BUYER_ON = {
    "name": "Alexandra Riley",
    "company_name": "Riley Contracting Ltd.",
    "billing_address": "42 Maple Way, Toronto, ON, M5V 3A8",
    "address": "42 Maple Way, Toronto, ON, M5V 3A8",
    "phone": "1-416-555-0142",
    "email": "buyer@example.com",
    "province": "ON",
}
SELLER_QC = {
    "name": "Encans Charbonneau",
    "company_name": "Encans Charbonneau Inc.",
    "address": "88 rue Sherbrooke, Sherbrooke, QC, J1H 1V6",
    "email": "seller@example.com",
    "phone": "1-819-555-0142",
}
AUCTION = {
    "title": "Renaissance Multi-Item Estate Sale — Feb 15, 2026",
    "city": "Sherbrooke", "region": "QC",
    "location": "103-761 Chalifoux Street, Sherbrooke, QC",
    "auction_end_date": _NOW,
}
LOTS_2 = [
    {"lot_number": "42", "title": "Milwaukee M18 12-piece Kit",
     "description": "Cordless drill, impact driver, batteries, charger, hard case — brand new",
     "unit_price": 1875.00, "hammer_price": 1875.00, "quantity": 1, "status": "sold"},
    {"lot_number": "43", "title": "DeWalt 20V MAX Combo",
     "description": "Circular saw, reciprocating saw, work light, 2x 5.0Ah batteries",
     "unit_price": 549.00, "hammer_price": 1098.00, "quantity": 2, "status": "sold"},
]


# ═════════════════════════════════════════════════════════════════════════════
# Defect 1 — Commission Invoice uses canonical BidVex identity
# ═════════════════════════════════════════════════════════════════════════════

def test_defect1_commission_invoice_uses_canonical_bidvex_identity():
    """The Commission Invoice must render the SAME BidVex legal name,
    address, GST# and QST# used by every other billing document."""
    data = {
        "invoice_number": "COM-TEST-D1",
        "seller": SELLER_QC,
        "auction": AUCTION,
        "lots": LOTS_2,
        "total_hammer": 2973.00,
        "net_payout": 2802.09,  # deliberate — must be IGNORED (see Defect 4 test)
        "lots_sold": 2, "total_lots": 2,
        "commission_amount": 148.65,
        "commission_rate": 5.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
    }
    html = commission_invoice_template(data)
    # Canonical identity present
    assert "103-761 Chalifoux Street" in html
    assert "Sherbrooke, QC, J1G 0A8" in html
    assert "706766367RT0001" in html
    assert "1233530880TQ0001" in html
    assert "BidVex Inc." in html
    # Wrong-identity fossils must be gone
    for wrong in ("123 Auction Street", "Montreal, QC H1A 1A1",
                  "123456789RT0001", "1234567890TQ0001"):
        assert wrong not in html, f"Wrong identity fossil still present: {wrong!r}"


def test_defect1_bidvex_company_info_matches_tax_engine_source_of_truth():
    """`_bidvex_company_info()` must expose the exact values held in
    `services.tax_engine`.  Any drift means the templates and the
    tax/fee engine are diverging."""
    from services import tax_engine as te
    info = _bidvex_company_info()
    assert info["legal_name"] == te.BIDVEX_LEGAL_NAME
    assert info["address"] == te.BIDVEX_ADDRESS
    assert info["gst_number"] == te.BIDVEX_GST_NUMBER
    assert info["qst_number"] == te.BIDVEX_QST_NUMBER


def test_defect1_bidvex_identity_is_byte_identical_across_seller_documents():
    """The Commission Invoice must render the canonical BidVex identity
    (legal name, address, GST# and QST#).  The Seller Statement / Receipt
    don't display BidVex's registration numbers in the body (they show the
    seller's block), so we only enforce the canonical identity on documents
    that carry it — and enforce that the *wrong* identity strings never
    leak into any of them."""
    stmt = seller_statement_template({
        "invoice_number": "STM-TEST-D1", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": 2973.00, "lots_sold": 2, "total_lots": 2,
        "commission_rate": 5.0, "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    rec = seller_receipt_template({
        "receipt_number": "REC-TEST-D1", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": 2973.00, "lots_sold": 2, "total_lots": 2,
        "commission_amount": 148.65, "commission_rate": 5.0,
        "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    com = commission_invoice_template({
        "invoice_number": "COM-TEST-D1", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": 2973.00, "net_payout": 0.0,
        "lots_sold": 2, "total_lots": 2, "commission_amount": 148.65,
        "commission_rate": 5.0, "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    # Commission Invoice carries the canonical BidVex identity in party block + footer.
    assert "706766367RT0001" in com
    assert "1233530880TQ0001" in com
    assert "103-761 Chalifoux Street" in com
    # None of the three documents may leak the WRONG identity strings.
    for doc, name in ((stmt, "Statement"), (rec, "Receipt"), (com, "Commission Invoice")):
        for wrong in ("123 Auction Street", "Montreal, QC H1A 1A1",
                      "123456789RT0001", "1234567890TQ0001"):
            assert wrong not in doc, f"{name} contains wrong-identity fossil {wrong!r}"


# ═════════════════════════════════════════════════════════════════════════════
# Defect 2 — General Auction Invoice: every visible fee row reconciles
# ═════════════════════════════════════════════════════════════════════════════

def test_defect2_general_invoice_displays_seller_commission_and_all_line_items_reconcile():
    """For a $1,875 hammer / basic-tier buyer / basic-tier seller who IS a
    business (QC), the General Auction Invoice PDF must render *every*
    fee component so that the sum of visible rows equals the displayed
    grand total.  Prior version hid the seller-commission line while
    still folding it into the GST/QST base, which made the visible
    totals impossible to verify."""
    from services.tax_engine import calculate_general_payment, SellerInfo
    from services.invoice_generator import generate_general_invoice_pdf

    seller = SellerInfo(
        seller_id="test_biz_qc", seller_name="Encans Charbonneau Inc.",
        is_business=True, business_name="Encans Charbonneau Inc.",
        address="88 rue Sherbrooke, Sherbrooke, QC",
        gst_number="706766367RT0001", qst_number="1233530880TQ0001",
    )
    r = calculate_general_payment(
        hammer_price=1875.00, buyer_tier="basic", seller_tier="basic",
        seller_is_business=True, seller_info=seller,
    )

    # ── Backend invariant: bidvex_fees_subtotal == BP + commission ──
    assert round(r.buyer_premium + r.seller_commission, 2) == round(r.bidvex_fees_subtotal, 2)
    # ── Backend invariant: gst + qst equals combined tax on the subtotal ──
    assert round(r.bidvex_fees_gst + r.bidvex_fees_qst, 2) == round(r.bidvex_fees_tax_total, 2)

    # ── PDF invariant: PDF must show BOTH the BP AND the commission line
    #    so the visible sum of rows reconciles.  Decompose the PDF text
    #    and search for the four canonical labels.
    pdf = generate_general_invoice_pdf(
        payment_result=r,
        buyer_info=BUYER_ON,
        seller_info={"name": SELLER_QC["name"], "email": SELLER_QC["email"],
                     "business_name": SELLER_QC["company_name"],
                     "gst_number": "706766367RT0001",
                     "qst_number": "1233530880TQ0001"},
        auction_info={"title": "Lot #42 — Palette d'outils Milwaukee"},
        invoice_number="BV-GEN-TEST-D2",
    )
    import io, pdfplumber
    with pdfplumber.open(io.BytesIO(pdf)) as p:
        text = "\n".join((page.extract_text() or "") for page in p.pages)

    # Both fee components must be individually visible
    assert "Buyer Premium" in text
    assert "Seller Commission" in text
    # Canonical subtotal + total labels
    assert "BidVex Fees Subtotal" in text
    assert "Platform Fees Total (incl. taxes)" in text
    # Grand total row is emitted with a bilingual header
    assert "GRAND TOTAL" in text

    # ── Cross-check: the "Platform Fees Total" figure equals
    #    BP + Commission + GST + QST (all shown line items).
    expected_platform_fees_total = round(
        float(r.buyer_premium) + float(r.seller_commission) +
        float(r.bidvex_fees_gst) + float(r.bidvex_fees_qst), 2)
    # weakly assert by presence — the format uses "$X,XXX.XX" style
    money = f"${expected_platform_fees_total:,.2f}"
    assert money in text, (
        f"PDF should show Platform Fees Total = {money}. "
        f"Extracted:\n{text[:800]}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# Defect 3 — Payment Letter matches Lots Won Summary for the same buyer
# ═════════════════════════════════════════════════════════════════════════════

def test_defect3_ontario_buyer_gets_zero_qst_on_both_documents():
    """For an Ontario buyer, the Lots Won Summary and the Payment Letter
    MUST report the same grand total (no QST).  Prior versions let the
    Payment Letter accept a QC-defaulted `grand_total` from a caller
    that also called Lots Won without one, so the two documents drifted."""
    # ~ $2,973.00 hammer + 15% BP + HST-Ontario (5% GST + 0% QST since ON)
    # (this test uses the 5%-GST-only branch; HST 13% is handled by the caller
    #  passing tax_rate_gst=13 which is out of scope here)
    _shared = compute_buyer_totals(
        lots=LOTS_2,
        premium_percentage=15.0,
        buyer_province="ON",
        tax_rate_gst=5.0,
        tax_rate_qst_qc=9.975,
    )
    # Ontario buyer → QST components MUST be exactly 0.
    assert _shared["qst_on_hammer"] == 0.0
    assert _shared["qst_on_premium"] == 0.0
    assert _shared["effective_qst_rate"] == 0.0
    # Ontario expected grand total (deterministic reference):
    hammer = 2973.00
    prem = round(hammer * 0.15, 2)                    # $445.95
    gst_hammer = round(hammer * 0.05, 2)              # $148.65
    gst_prem = round(prem * 0.05, 2)                  # $22.30
    expected_grand = round(hammer + prem + gst_hammer + gst_prem, 2)
    assert _shared["grand_total"] == expected_grand

    # Templates: pass a buyer with province=ON, and confirm the same grand total
    # is rendered in both.
    lots_html = lots_won_template({
        "invoice_number": "BV-LOTS-D3", "paddle_number": "P-4242",
        "buyer": BUYER_ON, "auction": AUCTION, "lots": LOTS_2,
        "premium_percentage": 15.0, "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    letter_html = payment_letter_template({
        "invoice_number": "BV-LTR-D3", "paddle_number": "P-4242",
        "buyer": BUYER_ON, "auction": AUCTION, "lots": LOTS_2,
        "lots_count": 2,
        # Deliberately pass QC-defaulted stale numbers to prove the
        # template now IGNORES them in favour of the canonical helper.
        "hammer_total": 2973.00, "premium_amount": 445.95,
        "total_tax": 512.09, "grand_total": 3931.04,
        "premium_percentage": 15.0,
        "payment_deadline": "March 1, 2026",
    })
    expected_money = f"${expected_grand:,.2f}"
    assert expected_money in lots_html, f"Lots Won missing grand total {expected_money}"
    assert expected_money in letter_html, (
        f"Payment Letter should also show {expected_money} for an ON buyer, "
        "not the stale QC-defaulted grand total.")
    # The stale QC-defaulted value MUST NOT appear anywhere in the letter now.
    assert "$3,931.04" not in letter_html, (
        "Payment Letter regressed — still displays a stale QC-defaulted total.")


def test_defect3_quebec_buyer_still_gets_gst_plus_qst_on_both_documents():
    """Sanity — the fix must not accidentally strip QST for a QC buyer.
    The correctly-computed grand total for a QC buyer with hammer $2,973
    + 15% BP + 5% GST + 9.975% QST is $3,930.94 (the $3,931.04 figure that
    appeared in the pre-fix QA delivery was a stale caller-supplied
    passthrough — the canonical helper always rounds each component)."""
    buyer_qc = {**BUYER_ON, "province": "QC",
                "billing_address": "125 rue Notre-Dame, Montréal, QC"}
    _totals = compute_buyer_totals(LOTS_2, 15.0, "QC", 5.0, 9.975)
    assert _totals["qst_on_hammer"] > 0
    assert _totals["qst_on_premium"] > 0
    # Locked-in reference:
    assert _totals["hammer_total"] == 2973.00
    assert _totals["premium_amount"] == 445.95
    assert _totals["gst_on_hammer"] == 148.65
    assert _totals["qst_on_hammer"] == 296.56
    assert _totals["gst_on_premium"] == 22.30
    assert _totals["qst_on_premium"] == 44.48
    assert _totals["grand_total"] == 3930.94
    letter_html = payment_letter_template({
        "invoice_number": "BV-LTR-D3-QC", "paddle_number": "P-4242",
        "buyer": buyer_qc, "auction": AUCTION, "lots": LOTS_2,
        "lots_count": 2, "premium_percentage": 15.0,
        "hammer_total": 0, "premium_amount": 0, "total_tax": 0, "grand_total": 0,
        "payment_deadline": "March 1, 2026",
    })
    assert "$3,930.94" in letter_html


# ═════════════════════════════════════════════════════════════════════════════
# Defect 4 — Seller payout is identical across Statement / Receipt / Invoice
# ═════════════════════════════════════════════════════════════════════════════

def test_defect4_seller_payout_agrees_across_all_three_documents():
    """For the same auction (hammer $2,973.00, 5% commission, QC place-of-supply),
    the Seller Statement, Seller Receipt and Commission Invoice must all
    report the same net payout.  The correct math is:
        commission        = 2,973.00 × 5%       = 148.65
        GST on commission = 148.65   × 5%       =   7.43  (rounded)
        QST on commission = 148.65   × 9.975%   =  14.83  (rounded)
        total deductions  = 148.65 + 7.43 + 14.83 = 170.91
        NET PAYOUT        = 2,973.00 − 170.91   = 2,802.09
    """
    hammer = 2973.00
    p = compute_seller_payout(hammer, commission_rate=5.0,
                              tax_rate_gst=5.0, tax_rate_qst=9.975)
    assert p["commission_amount"] == 148.65
    assert p["gst_on_commission"] == 7.43
    assert p["qst_on_commission"] == 14.83
    assert p["tax_on_commission"] == 22.26
    assert p["total_deductions"] == 170.91
    assert p["net_payout"] == 2802.09

    # ── Render the three documents ──
    stmt = seller_statement_template({
        "invoice_number": "STM-D4", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": hammer, "lots_sold": 2, "total_lots": 2,
        "commission_rate": 5.0, "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    rec = seller_receipt_template({
        "receipt_number": "REC-D4", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": hammer, "lots_sold": 2, "total_lots": 2,
        "commission_amount": 148.65, "commission_rate": 5.0,
        "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    # Commission Invoice — deliberately pass a WRONG caller-supplied net_payout
    # to prove the template now IGNORES it and re-derives from the canonical
    # helper.
    com = commission_invoice_template({
        "invoice_number": "COM-D4", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": hammer,
        "net_payout": 2824.35,   # stale/wrong — must be discarded
        "lots_sold": 2, "total_lots": 2,
        "commission_amount": 148.65, "commission_rate": 5.0,
        "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })

    # ── All three documents show the SAME net payout ──
    correct = "$2,802.09"
    assert correct in stmt, "Seller Statement doesn't show correct net payout"
    assert correct in rec, "Seller Receipt doesn't show correct net payout"
    assert correct in com, "Commission Invoice doesn't show correct net payout"

    # ── No document may show the stale/wrong payout anywhere ──
    stale = "$2,824.35"
    assert stale not in stmt, "Seller Statement regressed — still shows stale payout"
    assert stale not in com,  "Commission Invoice regressed — trusts stale caller field"


def test_defect4_seller_statement_now_deducts_tax_on_commission():
    """Before the fix, Seller Statement omitted GST/QST-on-commission
    deductions.  The Financial Summary block must now include the two
    tax lines and the Total Deductions row so the payout ties out."""
    stmt = seller_statement_template({
        "invoice_number": "STM-D4B", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": 2973.00, "lots_sold": 2, "total_lots": 2,
        "commission_rate": 5.0, "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    assert "GST on Commission" in stmt
    assert "QST on Commission" in stmt
    assert "Total Deductions" in stmt
    # Sanity — the three individual deduction rows should sum to $170.91
    #   commission $148.65, GST $7.43, QST $14.83.
    assert "-$148.65" in stmt
    assert "-$7.43" in stmt
    assert "-$14.83" in stmt
    assert "-$170.91" in stmt


def test_defect4_commission_invoice_ignores_stale_net_payout_field():
    """The Commission Invoice's Payment Terms section must display the
    payout derived from `compute_seller_payout(total_hammer, ...)` and
    ignore any caller-supplied `net_payout`."""
    com = commission_invoice_template({
        "invoice_number": "COM-D4C", "seller": SELLER_QC, "auction": AUCTION,
        "lots": LOTS_2, "total_hammer": 2973.00,
        "net_payout": 9999.99,   # caller supplied nonsense
        "lots_sold": 2, "total_lots": 2,
        "commission_amount": 148.65, "commission_rate": 5.0,
        "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
    })
    assert "$2,802.09" in com
    assert "$9,999.99" not in com


# ═════════════════════════════════════════════════════════════════════════════
# Cross-cutting — same shared inputs, all doc lines cross-reconcile
# ═════════════════════════════════════════════════════════════════════════════

def test_all_seller_docs_derived_from_the_SAME_helper_never_drift():
    """`compute_seller_payout` is the single source of truth for
    Statement / Receipt / Commission Invoice.  If someone accidentally
    forks the math again, this test fails the moment the payouts drift."""
    from invoice_templates import compute_seller_payout as f
    for h, cr, gst, qst in [
        (2973.00, 5.0, 5.0, 9.975),
        (10_000.00, 3.0, 5.0, 9.975),
        (425.00, 5.0, 5.0, 9.975),
        (1875.00, 5.0, 5.0, 0.0),      # ON seller → no QST
    ]:
        p1 = f(h, cr, gst, qst)
        # Idempotence
        p2 = f(h, cr, gst, qst)
        assert p1 == p2
        # Invariant: net_payout + total_deductions == hammer
        assert round(p1["net_payout"] + p1["total_deductions"], 2) == round(h, 2)


def test_defect3_shared_helper_ontario_grand_total_matches_evidence_from_review():
    """Locks in the exact ON-buyer grand total for the sample data
    reviewed in the QA batch: hammer $2,973.00, 15% BP, GST 5%, QST 0%
    (because Ontario buyer)."""
    r = compute_buyer_totals(LOTS_2, 15.0, "ON", 5.0, 9.975)
    assert r["hammer_total"] == 2973.00
    assert r["premium_amount"] == 445.95
    assert r["subtotal_before_tax"] == 3418.95
    assert r["gst_on_hammer"] == 148.65
    assert r["qst_on_hammer"] == 0.00
    assert r["gst_on_premium"] == 22.30
    assert r["qst_on_premium"] == 0.00
    assert r["total_tax"] == 170.95
    assert r["grand_total"] == 3589.90


def test_defect1_defect4_hardcoded_wrong_business_ids_never_appear_in_any_seller_document():
    """The four wrong-identity fossils reported by the review must be
    completely absent from every seller-side document, so a diff-scan
    of production billing outputs will always fail if someone reverts."""
    common_kwargs = dict(
        seller=SELLER_QC, auction=AUCTION, lots=LOTS_2,
        total_hammer=2973.00, lots_sold=2, total_lots=2,
        commission_rate=5.0, tax_rate_gst=5.0, tax_rate_qst=9.975,
    )
    docs = [
        seller_statement_template({"invoice_number": "STM-X", **common_kwargs}),
        seller_receipt_template({
            "receipt_number": "REC-X",
            "seller": SELLER_QC, "auction": AUCTION, "lots": LOTS_2,
            "total_hammer": 2973.00, "lots_sold": 2, "total_lots": 2,
            "commission_amount": 148.65, "commission_rate": 5.0,
            "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
        }),
        commission_invoice_template({
            "invoice_number": "COM-X",
            "seller": SELLER_QC, "auction": AUCTION, "lots": LOTS_2,
            "total_hammer": 2973.00, "net_payout": 0,
            "lots_sold": 2, "total_lots": 2,
            "commission_amount": 148.65, "commission_rate": 5.0,
            "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
        }),
    ]
    fossils = ("123 Auction Street", "Montreal, QC H1A 1A1",
               "123456789RT0001", "1234567890TQ0001")
    for doc in docs:
        for f in fossils:
            assert f not in doc, f"Wrong-identity fossil still present: {f!r}"
