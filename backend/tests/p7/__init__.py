"""
iter484.2 Gate 3 — P7 Cent-Perfect Financial Regression Matrix
==============================================================

Purpose: capture the CURRENT financial behaviour of every tax /
fee calculator on the platform so any future P6 tax-engine
consolidation cannot silently move a penny.

Rules held during this suite:
  * NO production tax / fee / commission / Stripe / escrow / payout
    logic is modified.
  * A test failure ≠ automatic bug.  Every case is classified:
      A — Expected current behavior (no action)
      B — Technical defect (needs engineering fix)
      C — Tax/legal ambiguity (needs legal review)
      D — Known P6 consolidation issue (defer to P6)
  * When two calculators produce different totals for the same
    input, both current values are captured (not "corrected").

Exact-cent policy: every assertion uses ``Decimal`` cents.  No
floating-point tolerances.  See ``P7_CENT_PERFECT_REGRESSION_REPORT.md``.
"""
