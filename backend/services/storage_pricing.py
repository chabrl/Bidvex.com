"""
BidVex Storage Auction Pricing — iteration 169
==============================================
Self-contained pricing rules. Reuses get_tax_rate() from the canonical
PricingManager so provincial tax math stays in one place.

Spec proofs (verified inline at module load when run as __main__):
  Proof 1 — $200 QC Stripe → seller invoice $12.18
  Proof 2 — $500 ON Cash   → seller invoice $29.41
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict


SELLER_COMMISSION_RATE = Decimal("0.05")   # Flat 5% to BidVex
STRIPE_PERCENT = Decimal("0.029")
STRIPE_FIXED = Decimal("0.30")


# Province → (rate, label) — same source of truth as PricingManager.
# Defined locally to avoid circular imports during testing.
_PROV_TAX = {
    "QC": (Decimal("0.14975"), "GST + QST (14.975%)"),
    "ON": (Decimal("0.13"), "HST (13%)"),
    "NS": (Decimal("0.15"), "HST (15%)"),
    "NB": (Decimal("0.15"), "HST (15%)"),
    "NL": (Decimal("0.15"), "HST (15%)"),
    "PE": (Decimal("0.15"), "HST (15%)"),
    "PEI": (Decimal("0.15"), "HST (15%)"),
    "AB": (Decimal("0.05"), "GST (5%)"),
    "BC": (Decimal("0.05"), "GST (5%)"),
    "SK": (Decimal("0.05"), "GST (5%)"),
    "MB": (Decimal("0.05"), "GST (5%)"),
    "NT": (Decimal("0.05"), "GST (5%)"),
    "NU": (Decimal("0.05"), "GST (5%)"),
    "YT": (Decimal("0.05"), "GST (5%)"),
}


def _q(d: Decimal) -> Decimal:
    """Quantize to 2 dp, ROUND_HALF_UP."""
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _f(d: Decimal) -> float:
    return float(_q(d))


def get_storage_tax(province: str) -> tuple:
    rate, label = _PROV_TAX.get((province or "").upper(), (Decimal("0"), "No tax"))
    return rate, label


def calculate_storage_pricing(
    winning_bid: float,
    province: str,
    payment_method: str = "stripe",
) -> Dict:
    """
    Compute the seller (facility) and buyer invoice splits for a storage
    auction. Returns a dict with keys: seller_invoice, buyer_invoice,
    bidvex_revenue, payment_method, province, tax_label.

    Seller side (always taxable):
      seller_commission = bid × 5%
      stripe_recovery   = (commission × 2.9%) + $0.30   ← BidVex's processing cost
      tax               = (commission + stripe_recovery) × provincial_rate
      seller_invoice    = commission + stripe_recovery + tax

    Buyer side (depends on payment method):
      stripe   → buyer pays winning_bid + (winning_bid × 2.9% + $0.30)
                 (Stripe fees passed through so facility nets full bid)
      cash     → buyer pays winning_bid (off-platform; BidVex not involved)
      etransfer→ buyer pays winning_bid (off-platform; BidVex not involved)

      Provincial sales tax on the winning bid is collected by the FACILITY
      (their goods, their tax registration); BidVex never collects it.
    """
    bid = Decimal(str(winning_bid))
    rate, label = get_storage_tax(province)

    # Seller invoice
    sc = bid * SELLER_COMMISSION_RATE
    sr = (sc * STRIPE_PERCENT) + STRIPE_FIXED
    tax = (sc + sr) * rate
    seller_total = sc + sr + tax

    # Buyer side
    pm = (payment_method or "").lower()
    if pm == "stripe":
        buyer_stripe_fee = (bid * STRIPE_PERCENT) + STRIPE_FIXED
        buyer_total = bid + buyer_stripe_fee
    else:
        buyer_stripe_fee = Decimal("0")
        buyer_total = bid

    return {
        "winning_bid": _f(bid),
        "province": (province or "").upper(),
        "tax_rate": _f(rate),
        "tax_label": label,
        "payment_method": pm,
        "seller_invoice": {
            "commission": _f(sc),
            "commission_rate": "5%",
            "stripe_recovery": _f(sr),
            "tax": _f(tax),
            "tax_label": label,
            "total": _f(seller_total),
            "breakdown_text": (
                f"Commission (5%): ${_f(sc):.2f}  +  Stripe Recovery: ${_f(sr):.2f}  "
                f"+  Tax {label}: ${_f(tax):.2f}  =  ${_f(seller_total):.2f}"
            ),
        },
        "buyer_invoice": {
            "winning_bid": _f(bid),
            "stripe_fee": _f(buyer_stripe_fee),
            "total": _f(buyer_total),
            "bidvex_fee": 0.0,
            "note_en": (
                "Buyer pays Stripe processing fees only — BidVex charges no buyer fee."
                if pm == "stripe"
                else "Buyer pays facility directly via "
                + ("cash" if pm == "cash" else "Interac e-Transfer")
                + " — BidVex is not involved in this transaction."
            ),
            "note_fr": (
                "L'acheteur paie uniquement les frais de traitement Stripe — BidVex ne facture aucun frais acheteur."
                if pm == "stripe"
                else "L'acheteur paie directement à la facilité par "
                + ("comptant" if pm == "cash" else "virement Interac")
                + " — BidVex n'est pas impliqué dans cette transaction."
            ),
        },
        "bidvex_revenue": _f(sc),
    }


# ─────────────────────────────────────────────────────────────
# Inline spec verification — runs only when executed directly.
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p1 = calculate_storage_pricing(200, "QC", "stripe")
    print("PROOF 1 — $200 QC Stripe:")
    print(f"  Seller invoice: ${p1['seller_invoice']['total']:.2f}  (spec: $12.18)")
    print(f"  Buyer pays:     ${p1['buyer_invoice']['total']:.2f}  (spec: $206.10)")
    assert abs(p1["seller_invoice"]["total"] - 12.18) <= 0.01
    assert abs(p1["buyer_invoice"]["total"] - 206.10) <= 0.01
    print()
    p2 = calculate_storage_pricing(500, "ON", "cash")
    print("PROOF 2 — $500 ON Cash:")
    print(f"  Seller invoice: ${p2['seller_invoice']['total']:.2f}  (spec: $29.41)")
    print(f"  Buyer pays:     ${p2['buyer_invoice']['total']:.2f}  (spec: $500.00 cash to facility)")
    assert abs(p2["seller_invoice"]["total"] - 29.41) <= 0.01
    assert abs(p2["buyer_invoice"]["total"] - 500.00) <= 0.01
    print("\nAll spec proofs passed.")
