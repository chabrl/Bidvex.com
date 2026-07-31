"""
BidVex Storage Auction Pricing — iter443 CORRECTED MODEL
======================================================================
Three payment methods (facility chooses per listing).
CORE RULE (iter443): BidVex ALWAYS charges the WINNING BUYER a 5%
buyer's premium on the hammer price. The storage facility is NEVER
charged by BidVex regardless of payment method.

OPTION A — STRIPE (online)
  Buyer pays via Stripe (BidVex collects):
    hammer_price + (hammer_price × 5%) + stripe_recovery + tax_on_(5%+stripe)
  stripe_recovery = (hammer + 5%) × 2.9% + $0.30
  tax = (5% BP + stripe_recovery) × buyer's provincial rate
  Facility receives: full hammer_price. BidVex keeps 5% + recovery + tax.

OPTION B/C — CASH or E-TRANSFER (offline for hammer, online for BP)
  Buyer pays facility directly: hammer_price (off-platform, cash or Interac).
  BidVex separately charges the BUYER's card on file:
    (hammer × 5%) + stripe_recovery_on_5% + tax_on_(5%+stripe_recovery)
  stripe_recovery_on_5% = (5% fee × 2.9%) + $0.30
  tax = (5% BP + stripe_recovery) × buyer's provincial rate
  Facility receives: full hammer_price (offline). BidVex never invoices facility.

Tax always applies to BidVex's 5% BP and is anchored at the BUYER's
province (Place-of-Supply: buyer is the recipient of BidVex's supply-
of-service under CRA §142.1). Provincial sales tax on the actual goods
is the FACILITY's responsibility (unchanged from previous iter).

Spec proofs verified inline at module load when run as __main__.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional


BUYER_PREMIUM_RATE = Decimal("0.05")   # iter443 — flat 5% BUYER'S PREMIUM
STRIPE_PERCENT = Decimal("0.029")
STRIPE_FIXED = Decimal("0.30")

# iter443 legacy alias — kept so any downstream code still importing the
# old name won't crash. Numerically identical (0.05).
SELLER_COMMISSION_RATE = BUYER_PREMIUM_RATE


# Province → (rate, label)
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
    deposit_amount: Optional[float] = None,
) -> Dict:
    """
    Returns a dict with:
      payment_method, province, tax_rate, tax_label,
      buyer_invoice {...}, facility_invoice {...}, bidvex_revenue
    """
    bid = Decimal(str(winning_bid or 0))
    deposit = Decimal(str(deposit_amount or 0))
    rate, label = get_storage_tax(province)
    pm = (payment_method or "").lower()

    fee_rate = BUYER_PREMIUM_RATE
    platform_fee = bid * fee_rate

    if pm == "stripe":
        # ── BUYER pays via Stripe (BidVex collects all of it) ──
        # stripe recovery on FULL amount (hammer + 5% fee)
        stripe_recovery = (bid + platform_fee) * STRIPE_PERCENT + STRIPE_FIXED
        tax = (platform_fee + stripe_recovery) * rate
        buyer_total = bid + platform_fee + stripe_recovery + tax
        buyer_remaining = max(buyer_total - deposit, Decimal("0"))

        return {
            "payment_method": "stripe",
            "province": (province or "").upper(),
            "tax_rate": _f(rate),
            "tax_label": label,
            "buyer_invoice": {
                "hammer_price": _f(bid),
                "platform_fee": _f(platform_fee),
                "platform_fee_rate": "5.0%",
                "stripe_recovery": _f(stripe_recovery),
                "tax": _f(tax),
                "tax_label": label,
                "deposit_paid": _f(deposit),
                "total": _f(buyer_total),
                "remaining_after_deposit": _f(buyer_remaining),
                "fee_payer": "buyer",
                "note_en": "BidVex charges you a 5% buyer's premium + Stripe processing + tax on top of the hammer price. Facility receives the full hammer.",
                "note_fr": "BidVex vous facture une prime acheteur de 5 % + frais de traitement Stripe + taxes en plus du prix marteau. La facilité reçoit le prix marteau complet.",
            },
            "facility_invoice": {
                "hammer_price": _f(bid),
                "bidvex_fee": 0.0,
                "platform_fee": 0.0,
                "stripe_recovery": 0.0,
                "tax": 0.0,
                "facility_owes_bidvex": 0.0,
                "facility_receives": _f(bid),
                "facility_net": _f(bid),
                "note_en": "You receive the full hammer price. BidVex charged its 5% buyer's premium to the buyer's card.",
                "note_fr": "Vous recevez le prix marteau complet. BidVex a facturé sa prime acheteur de 5 % à la carte de l'acheteur.",
            },
            "bidvex_revenue": _f(platform_fee + stripe_recovery + tax),
        }

    # ── CASH / E-TRANSFER ── iter443: BidVex charges the BUYER's card for
    # its 5% BP + Stripe recovery + tax. Facility receives full hammer
    # OFFLINE (cash/etransfer) and is never invoiced by BidVex.
    stripe_recovery = platform_fee * STRIPE_PERCENT + STRIPE_FIXED
    tax = (platform_fee + stripe_recovery) * rate
    buyer_bidvex_charge = platform_fee + stripe_recovery + tax
    buyer_remaining = max(buyer_bidvex_charge - deposit, Decimal("0"))

    method_en = "cash" if pm == "cash" else "Interac e-Transfer"
    method_fr = "comptant" if pm == "cash" else "virement Interac"

    return {
        "payment_method": pm if pm in ("cash", "etransfer") else "cash",
        "province": (province or "").upper(),
        "tax_rate": _f(rate),
        "tax_label": label,
        "buyer_invoice": {
            "hammer_price": _f(bid),
            "platform_fee": _f(platform_fee),
            "platform_fee_rate": "5.0%",
            "stripe_recovery": _f(stripe_recovery),
            "tax": _f(tax),
            "tax_label": label,
            "deposit_paid": _f(deposit),
            "total": _f(buyer_bidvex_charge),
            "remaining_after_deposit": _f(buyer_remaining),
            "fee_payer": "buyer",
            "note_en": f"Pay ${_f(bid):.2f} CAD directly to the facility via {method_en}. BidVex separately charges your card on file for the 5% buyer's premium + Stripe processing + tax.",
            "note_fr": f"Payez {_f(bid):.2f} $ CAD directement à la facilité par {method_fr}. BidVex facture séparément votre carte enregistrée pour la prime acheteur de 5 % + frais de traitement Stripe + taxes.",
        },
        "facility_invoice": {
            "hammer_price": _f(bid),
            "bidvex_platform_fee": 0.0,
            "platform_fee": 0.0,
            "platform_fee_rate": "0%",
            "stripe_recovery": 0.0,
            "tax": 0.0,
            "tax_label": label,
            "facility_owes_bidvex": 0.0,
            "facility_receives": _f(bid),
            "facility_net": _f(bid),
            "note_en": f"Buyer pays you ${_f(bid):.2f} directly (offline). BidVex separately charges the buyer for its 5% buyer's premium — you are never invoiced.",
            "note_fr": f"L'acheteur vous paie {_f(bid):.2f} $ directement (hors ligne). BidVex facture séparément l'acheteur pour sa prime de 5 % — vous n'êtes jamais facturé.",
        },
        "bidvex_revenue": _f(buyer_bidvex_charge),
    }


# ─────────────────────────────────────────────────────────────
# Inline spec verification — runs only when executed directly.
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # PROOF 1 — Stripe Payment, $800 hammer, QC, $100 deposit
    p1 = calculate_storage_pricing(800, "QC", "stripe", deposit_amount=100)
    print("PROOF 1 — Stripe QC $800 + $100 deposit:")
    print(f"  Hammer:                {p1['buyer_invoice']['hammer_price']:>8.2f}  (spec: 800.00)")
    print(f"  Platform Fee (5%):     {p1['buyer_invoice']['platform_fee']:>8.2f}  (spec: 40.00)")
    print(f"  Stripe Recovery:       {p1['buyer_invoice']['stripe_recovery']:>8.2f}  (spec: 24.66)")
    print(f"  Tax QC (14.975%):      {p1['buyer_invoice']['tax']:>8.2f}  (spec: 9.68)")
    print(f"  Buyer Total:           {p1['buyer_invoice']['total']:>8.2f}  (spec: 874.34)")
    print(f"  After deposit:         {p1['buyer_invoice']['remaining_after_deposit']:>8.2f}  (spec: 774.34)")
    print(f"  Facility receives:     {p1['facility_invoice']['facility_receives']:>8.2f}  (spec: 800.00)")
    assert abs(p1["buyer_invoice"]["platform_fee"] - 40.00) < 0.01
    assert abs(p1["buyer_invoice"]["stripe_recovery"] - 24.66) < 0.01
    assert abs(p1["buyer_invoice"]["tax"] - 9.68) < 0.01
    assert abs(p1["buyer_invoice"]["total"] - 874.34) < 0.01
    assert abs(p1["buyer_invoice"]["remaining_after_deposit"] - 774.34) < 0.01
    assert abs(p1["facility_invoice"]["facility_receives"] - 800.00) < 0.01

    # PROOF 2 — Cash, $800 hammer, QC, $100 deposit (iter443 — buyer billed, not facility)
    p2 = calculate_storage_pricing(800, "QC", "cash", deposit_amount=100)
    print("\nPROOF 2 — iter443 Cash QC $800 + $100 deposit:")
    print(f"  Hammer (offline → facility): {p2['buyer_invoice']['hammer_price']:>8.2f}  (spec: 800.00)")
    print(f"  BidVex 5% BP (→ buyer card): {p2['buyer_invoice']['platform_fee']:>8.2f}  (spec: 40.00)")
    print(f"  Stripe Recovery on BP:       {p2['buyer_invoice']['stripe_recovery']:>8.2f}  (spec: 1.46)")
    print(f"  Tax QC on BP+recovery:       {p2['buyer_invoice']['tax']:>8.2f}  (spec: 6.21)")
    print(f"  Buyer BidVex total:          {p2['buyer_invoice']['total']:>8.2f}  (spec: 47.67)")
    print(f"  After deposit ($100):        {p2['buyer_invoice']['remaining_after_deposit']:>8.2f}  (spec: 0.00)")
    print(f"  Facility receives (offline): {p2['facility_invoice']['facility_receives']:>8.2f}  (spec: 800.00)")
    print(f"  Facility owes BidVex:        {p2['facility_invoice']['facility_owes_bidvex']:>8.2f}  (spec: 0.00)")
    assert abs(p2["buyer_invoice"]["platform_fee"] - 40.00) < 0.01
    assert abs(p2["buyer_invoice"]["stripe_recovery"] - 1.46) < 0.01
    assert abs(p2["buyer_invoice"]["tax"] - 6.21) < 0.01
    assert abs(p2["buyer_invoice"]["total"] - 47.67) < 0.01
    assert abs(p2["buyer_invoice"]["remaining_after_deposit"] - 0.00) < 0.01
    assert abs(p2["facility_invoice"]["facility_receives"] - 800.00) < 0.01
    assert abs(p2["facility_invoice"]["facility_owes_bidvex"] - 0.00) < 0.01

    # PROOF 3 — E-Transfer, $1500 ON, no deposit (iter443 — buyer billed, not facility)
    p3 = calculate_storage_pricing(1500, "ON", "etransfer", deposit_amount=None)
    print("\nPROOF 3 — iter443 E-Transfer ON $1500 (no deposit):")
    print(f"  Hammer (offline → facility): {p3['buyer_invoice']['hammer_price']:>8.2f}  (spec: 1500.00)")
    print(f"  BidVex 5% BP (→ buyer card): {p3['buyer_invoice']['platform_fee']:>8.2f}  (spec: 75.00)")
    print(f"  Stripe Recovery on BP:       {p3['buyer_invoice']['stripe_recovery']:>8.2f}  (spec: 2.48)")
    print(f"  Tax ON HST on BP+recovery:   {p3['buyer_invoice']['tax']:>8.2f}  (spec: 10.07)")
    print(f"  Buyer BidVex total:          {p3['buyer_invoice']['total']:>8.2f}  (spec: 87.55)")
    print(f"  Facility receives (offline): {p3['facility_invoice']['facility_receives']:>8.2f}  (spec: 1500.00)")
    print(f"  Facility owes BidVex:        {p3['facility_invoice']['facility_owes_bidvex']:>8.2f}  (spec: 0.00)")
    assert abs(p3["buyer_invoice"]["platform_fee"] - 75.00) < 0.01
    assert abs(p3["buyer_invoice"]["stripe_recovery"] - 2.48) < 0.01
    assert abs(p3["buyer_invoice"]["tax"] - 10.07) < 0.01
    assert abs(p3["buyer_invoice"]["total"] - 87.55) < 0.01
    assert abs(p3["facility_invoice"]["facility_receives"] - 1500.00) < 0.01
    assert abs(p3["facility_invoice"]["facility_owes_bidvex"] - 0.00) < 0.01

    print("\n✓ All 3 spec proofs passed.")
