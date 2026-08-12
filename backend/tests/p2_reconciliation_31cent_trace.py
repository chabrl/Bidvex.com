"""P2 — $0.31 reconciliation trace.

Systematically simulate hammer=$7 through every buyer-side calculator
found in P1, comparing the resulting components against the reported
receipt values:
    Hammer         $7.00
    BidVex Fee     $0.25
    Taxes          $0.08
    Processing     $0.00 (displayed)
    TOTAL PAID     $7.64
    Δ              $0.31 unexplained
"""
from decimal import Decimal, ROUND_HALF_UP
import json
import sys

sys.path.insert(0, "/app/backend")

REPORT = {
    "reported_receipt": {
        "hammer": 7.00,
        "bidvex_fee": 0.25,
        "taxes": 0.08,
        "processing_displayed": 0.00,
        "total_paid": 7.64,
        "displayed_sum": 7.33,
        "unexplained_delta": 0.31,
    },
    "candidates": [],
}


def _round(x):
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def add_candidate(**kw):
    kw["match_total"] = abs(kw.get("computed_total", 0) - 7.64) < 0.005
    kw["match_processing_amount"] = abs(kw.get("processing", 0) - 0.31) < 0.005
    REPORT["candidates"].append(kw)


# Candidate 1 — Storage buyer flow (Stripe rail, hammer paid via Stripe)
# storage_pricing.py:99  stripe_recovery = (bid + platform_fee) * STRIPE_PERCENT + STRIPE_FIXED
# STRIPE_PERCENT=0.029, STRIPE_FIXED=0.30, BP rate = 0.05 (STORAGE_FACILITY_RATE)
bid = 7.00
bp = _round(bid * 0.05)  # 0.35
stripe_rec_s1 = _round((bid + bp) * 0.029 + 0.30)
tax_s1 = _round((bp + stripe_rec_s1) * 0.14975)  # QC
total_s1 = _round(bid + bp + stripe_rec_s1 + tax_s1)
add_candidate(
    name="Storage buyer — Stripe path (STRIPE_PERCENT × (bid+BP) + 0.30)",
    location="services/storage_pricing.py:99",
    hammer=bid, bidvex_fee=bp, taxes=tax_s1, processing=stripe_rec_s1,
    computed_total=total_s1,
    note="BP is 5% × $7 = $0.35, not $0.25. Processing = $0.51. Doesn't match.",
)

# Candidate 2 — Storage buyer — CASH/E-TRANSFER (offline hammer, BidVex-only Stripe charge)
# storage_pricing.py:141  stripe_recovery = platform_fee * STRIPE_PERCENT + STRIPE_FIXED
# BidVex-only charge = BP + stripe_recovery + tax_on_(BP + stripe_recovery)
bp2 = _round(bid * 0.05)  # 0.35
stripe_rec_s2 = _round(bp2 * 0.029 + 0.30)  # $0.35 * 2.9% + $0.30 = $0.31
tax_s2 = _round((bp2 + stripe_rec_s2) * 0.14975)  # QC
bidvex_charge_s2 = _round(bp2 + stripe_rec_s2 + tax_s2)
# Buyer also pays hammer OFFLINE to facility — total "collected" from buyer
# includes hammer if all displayed, but Stripe charge is only the BidVex portion
total_s2_offline = _round(bid + bp2 + stripe_rec_s2 + tax_s2)
add_candidate(
    name="Storage buyer — CASH/E-TRANSFER path (stripe_recovery = BP × 2.9% + $0.30)",
    location="services/storage_pricing.py:141",
    hammer=bid, bidvex_fee=bp2, taxes=tax_s2, processing=stripe_rec_s2,
    computed_total=total_s2_offline,
    bidvex_stripe_charge_only=bidvex_charge_s2,
    note=(
        f"STRIPE recovery = $0.35 × 0.029 + $0.30 = ${stripe_rec_s2:.2f}  ← EXACTLY $0.31 hit. "
        f"Total (hammer offline + BidVex Stripe) = ${total_s2_offline:.2f}. But BP is $0.35 not $0.25."
    ),
)

# Candidate 3 — Vehicle fee gross-up formula
# vehicle_fee_service.py:34  total = (net + 0.30) / (1 - 0.029)
# If net_commission = platform_fee = hammer * 0.025 = $0.175 → total = ($0.175 + 0.30) / 0.971 = $0.489
# Doesn't produce $0.31 delta directly, skip

# Candidate 4 — Non-Partner auction ("free" seller tier, non-storage)
# stripe_connect_service.calculate_checkout_breakdown for a "free" seller w/ Standard buyer:
#   BP rate = 0.05, SC = 0.04
#   BP = hammer × 0.05, SC = hammer × 0.04
#   fees_subtotal = BP + SC = $0.63
#   gst_on_fees = 0.63 × 0.05 = $0.0315 → $0.03
#   qst_on_fees = 0.63 × 0.09975 = $0.0629 → $0.06
#   fees_tax = $0.09
#   gross_amount (processing include) = (subtotal_before_processing + 0.30) / 0.971
#   subtotal_before_processing = hammer + BP + SC + tax = 7 + 0.35 + 0.28 + 0.09 = 7.72
#   gross = (7.72 + 0.30) / 0.971 = 8.263 → $8.26. Δ = $0.54. Not our case.

# Candidate 5 — Partner listing (10% BP), QC, not tax registered, hammer $7
# BP = $0.70, platform_fee = $0.21, fees_tax = 0.21 × 0.14975 = $0.031 → $0.03
# app_fee = $0.24, transfer = $7.46. Buyer pays $7.70. Not our case.

# Candidate 6 — Storage but hammer paid to facility offline AND buyer charge = BidVex only
# Reported total_paid = $7.64.  If the offline hammer is $7 and BidVex charge is $0.64:
# BP + stripe + tax should be $0.64.
# Try BP = $0.25 (rate = 3.57%?), stripe = $0.31, tax = $0.08:
#   sum = $0.64. Match!
# What gives BP = $0.25 at hammer $7?  0.25/7 = 0.0357 → 3.57%.  Not a standard rate.
# BUT — maybe hammer_effective was DIFFERENT from displayed hammer $7?
# If actual BP = 5% × $5 = $0.25, then internal hammer was $5, not $7.
# Then processing = $0.25 × 0.029 + $0.30 = $0.307 → $0.31.
# tax = ($0.25 + $0.31) × 0.14975 = $0.084 → $0.08.
# BidVex Stripe charge = $0.25 + $0.31 + $0.08 = $0.64.
# TOTAL PAID (hammer offline + BidVex Stripe) = $5 + $0.64 = $5.64.  NOT $7.64.
# BUT — what if the receipt displayed hammer $7 (final_price for a 2-unit lot, unit=$3.50) 
# while BP was computed on $5 due to a bug?
# OR — what if the buyer paid BOTH $7 (Stripe hammer) AND $0.64 (BidVex Stripe recovery)
# on top? Then Stripe collected $7 + $0.64 = $7.64.  MATCH!
bp3 = 0.25  # observed
proc3 = _round(bp3 * 0.029 + 0.30)  # $0.31
tax3 = _round((bp3 + proc3) * 0.14975)
bidvex_charge_s3 = _round(bp3 + proc3 + tax3)  # $0.64
total_s3 = _round(bid + bidvex_charge_s3)  # $7.64
add_candidate(
    name=(
        "Storage buyer — Stripe-mode with BP computed on subordinate base ($5) but "
        "hammer displayed at $7. The BidVex Stripe charge (BP + stripe_recovery + tax) is "
        "collected as a SECOND Stripe charge on top of the hammer paid via Stripe. "
        "Total collected = hammer + BidVex Stripe charge = $7 + $0.64 = $7.64."
    ),
    location="services/storage_pricing.py:141 (BidVex-only path) + duplicate Stripe charge for hammer",
    hammer=bid, bidvex_fee=bp3, taxes=tax3, processing=proc3,
    computed_total=total_s3,
    bidvex_stripe_charge_only=bidvex_charge_s3,
    note=(
        "MATCHES exactly. BP $0.25 + processing $0.31 + tax $0.08 = $0.64 BidVex Stripe charge; "
        "buyer also paid $7 hammer via Stripe or offline; total Stripe collected = $7.64. "
        "The RECEIPT DISPLAY shows Processing = $0.00 but the $0.31 WAS actually collected."
    ),
)

# Candidate 7 — Same math but starting from a $5 internal base (2 items @ $2.50)
# hammer_display = $5 × 1 = $5 or unit $3.50 × qty 2 = $7 hammer but BP was calculated
# on stale unit_price=$5.  This would surface if the code uses stale current_price
# before resolve_hammer_total in the BP branch.
# BP = $0.25 = 5% × $5 → suggests BP was computed on $5, not $7.

# Print the reconciliation
print(json.dumps(REPORT, indent=2))
print()
print("=" * 70)
print("EXACT $0.31 MATCH FOUND IN:")
for c in REPORT["candidates"]:
    if c.get("match_processing_amount"):
        print(f"  • {c['name']}")
        print(f"    Location: {c['location']}")
        print(f"    Processing = ${c['processing']:.2f}, total = ${c['computed_total']:.2f}")
print()
print("KEY DIAGNOSIS:")
print("  storage_pricing.py:141 formula:  stripe_recovery = BP × 0.029 + $0.30")
print("  With BP = $0.25 → stripe_recovery = $0.25 × 0.029 + $0.30 = $0.31 EXACT")
print("  This $0.31 IS charged to the buyer (part of BidVex Stripe charge)")
print("  BUT the receipt DISPLAY renders Payment Processing = $0.00, hiding the $0.31")
