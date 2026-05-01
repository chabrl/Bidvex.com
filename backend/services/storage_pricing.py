"""
BidVex Storage Auction Pricing — iteration 170 (PAYMENT-METHOD-AWARE)
======================================================================
Three payment methods (facility chooses per listing):

OPTION A — STRIPE (online)
  Buyer pays via Stripe (BidVex collects):
    hammer_price + (hammer_price × 5%) + stripe_recovery + tax_on_(5%+stripe)
  stripe_recovery = (hammer + 5%) × 2.9% + $0.30
  tax = (5% fee + stripe_recovery) × provincial_rate
  Facility receives: full hammer_price (BidVex's fee already collected from buyer)

OPTION B/C — CASH or E-TRANSFER (offline)
  Buyer pays facility directly: hammer_price (off-platform)
  BidVex invoices the FACILITY:
    (hammer × 5%) + stripe_recovery_on_5% + tax_on_(5%+stripe_recovery)
  stripe_recovery_on_5% = (5% fee × 2.9%) + $0.30
  tax = (5% fee + stripe_recovery) × provincial_rate
  Facility net = hammer_price − facility_owes_bidvex

Tax always applies to BidVex's 5% commission for ALL provinces. Provincial
sales tax on the actual goods is the FACILITY's responsibility (not BidVex's).

Spec proofs verified inline at module load when run as __main__.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional


SELLER_COMMISSION_RATE = Decimal("0.05")   # Flat 5% to BidVex
STRIPE_PERCENT = Decimal("0.029")
STRIPE_FIXED = Decimal("0.30")


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

    fee_rate = SELLER_COMMISSION_RATE
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
                "note_en": "BidVex collects platform fee + Stripe + tax via your card. Facility receives full hammer price.",
                "note_fr": "BidVex perçoit les frais + Stripe + taxes via votre carte. La facilité reçoit le prix marteau complet.",
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
                "note_en": "BidVex fee collected from buyer — facility receives full hammer price.",
                "note_fr": "Les frais BidVex sont perçus auprès de l'acheteur — la facilité reçoit le prix marteau complet.",
            },
            "bidvex_revenue": _f(platform_fee + stripe_recovery + tax),
        }

    # ── CASH / E-TRANSFER ── BidVex invoices the FACILITY
    stripe_recovery = platform_fee * STRIPE_PERCENT + STRIPE_FIXED
    tax = (platform_fee + stripe_recovery) * rate
    facility_owes = platform_fee + stripe_recovery + tax
    facility_net = bid - facility_owes

    method_en = "cash" if pm == "cash" else "Interac e-Transfer"
    method_fr = "comptant" if pm == "cash" else "virement Interac"
    buyer_remaining_cash = max(bid - deposit, Decimal("0"))

    return {
        "payment_method": pm if pm in ("cash", "etransfer") else "cash",
        "province": (province or "").upper(),
        "tax_rate": _f(rate),
        "tax_label": label,
        "buyer_invoice": {
            "hammer_price": _f(bid),
            "platform_fee": 0.0,
            "stripe_recovery": 0.0,
            "tax": 0.0,
            "deposit_paid": _f(deposit),
            "total": _f(bid),
            "remaining_after_deposit": _f(buyer_remaining_cash),
            "fee_payer": "facility",
            "note_en": f"Pay ${_f(bid):.2f} CAD directly to facility via {method_en}. BidVex charges no buyer fee.",
            "note_fr": f"Payez {_f(bid):.2f} $ CAD directement à la facilité par {method_fr}. BidVex ne facture aucun frais acheteur.",
        },
        "facility_invoice": {
            "hammer_price": _f(bid),
            "bidvex_platform_fee": _f(platform_fee),
            "platform_fee_rate": "5.0%",
            "stripe_recovery": _f(stripe_recovery),
            "tax": _f(tax),
            "tax_label": label,
            "facility_owes_bidvex": _f(facility_owes),
            "facility_net": _f(facility_net),
            "facility_receives": _f(facility_net),
            "note_en": f"Buyer pays you ${_f(bid):.2f} directly. BidVex invoices your card on file for ${_f(facility_owes):.2f}.",
            "note_fr": f"L'acheteur vous paie {_f(bid):.2f} $ directement. BidVex facture votre carte enregistrée de {_f(facility_owes):.2f} $.",
        },
        "bidvex_revenue": _f(facility_owes),
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

    # PROOF 2 — Cash, $800 hammer, QC, $100 deposit
    p2 = calculate_storage_pricing(800, "QC", "cash", deposit_amount=100)
    print("\nPROOF 2 — Cash QC $800 + $100 deposit:")
    print(f"  Buyer pays facility:   {p2['buyer_invoice']['total']:>8.2f}  (spec: 800.00 cash to facility)")
    print(f"  After deposit (cash):  {p2['buyer_invoice']['remaining_after_deposit']:>8.2f}  (spec: 700.00)")
    print(f"  Platform fee (5%):     {p2['facility_invoice']['bidvex_platform_fee']:>8.2f}  (spec: 40.00)")
    print(f"  Stripe Recovery:       {p2['facility_invoice']['stripe_recovery']:>8.2f}  (spec: 1.46)")
    print(f"  Tax QC:                {p2['facility_invoice']['tax']:>8.2f}  (spec: 6.21)")
    print(f"  Facility owes BidVex:  {p2['facility_invoice']['facility_owes_bidvex']:>8.2f}  (spec: 47.67)")
    print(f"  Facility net:          {p2['facility_invoice']['facility_net']:>8.2f}  (spec: 752.33)")
    assert abs(p2["facility_invoice"]["bidvex_platform_fee"] - 40.00) < 0.01
    assert abs(p2["facility_invoice"]["stripe_recovery"] - 1.46) < 0.01
    assert abs(p2["facility_invoice"]["tax"] - 6.21) < 0.01
    assert abs(p2["facility_invoice"]["facility_owes_bidvex"] - 47.67) < 0.01
    assert abs(p2["facility_invoice"]["facility_net"] - 752.33) < 0.01
    assert abs(p2["buyer_invoice"]["remaining_after_deposit"] - 700.00) < 0.01

    # PROOF 3 — E-Transfer, $1500 ON, no deposit
    p3 = calculate_storage_pricing(1500, "ON", "etransfer", deposit_amount=None)
    print("\nPROOF 3 — E-Transfer ON $1500 (no deposit):")
    print(f"  Buyer pays facility:   {p3['buyer_invoice']['total']:>8.2f}  (spec: 1500.00)")
    print(f"  Platform fee (5%):     {p3['facility_invoice']['bidvex_platform_fee']:>8.2f}  (spec: 75.00)")
    print(f"  Stripe Recovery:       {p3['facility_invoice']['stripe_recovery']:>8.2f}  (spec: 2.48)")
    print(f"  Tax ON HST (13%):      {p3['facility_invoice']['tax']:>8.2f}  (spec: 10.07)")
    print(f"  Facility owes BidVex:  {p3['facility_invoice']['facility_owes_bidvex']:>8.2f}  (spec: 87.55)")
    print(f"  Facility net:          {p3['facility_invoice']['facility_net']:>8.2f}  (spec: 1412.45)")
    assert abs(p3["facility_invoice"]["bidvex_platform_fee"] - 75.00) < 0.01
    assert abs(p3["facility_invoice"]["stripe_recovery"] - 2.48) < 0.01
    assert abs(p3["facility_invoice"]["tax"] - 10.07) < 0.01
    assert abs(p3["facility_invoice"]["facility_owes_bidvex"] - 87.55) < 0.01
    assert abs(p3["facility_invoice"]["facility_net"] - 1412.45) < 0.01

    print("\n✓ All 3 spec proofs passed.")
