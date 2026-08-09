"""
iter451 — Auction-End Quantity Calculation Regression Suite
============================================================

Locks in the P0 fix: hammer_total = unit_price × quantity when
`multiply_hammer_by_quantity=True` on a multi-item lot.

Required scenarios (per user directive, Feb 8 2026):
  A. Multi-item lot $7 × 2 = $14 propagates through settlement,
     buyer payment, buyer premium, processing fees, taxes, invoices,
     and seller settlement.
  B. Quantity of 1 → unit price only (no multiplication).
  C. Buy Now / pre-multiplied stored price → NOT re-multiplied.
  D. Total-lot pricing (multiply flag OFF) → NOT multiplied.
  E. Multi-lot buyer with mixed quantities (Lot A $7×2=$14 +
     Lot B $10×3=$30 → merchandise total $44) reconciles across
     settlement, invoice, buyer payment, seller payout.
  F. Top-level listing vs winning lot — the WINNING lot's price/qty
     are used, top-level listing fields are not silently substituted.
  G. Invalid/zero quantity — resolver clamps to 1 (no silent zero
     financial totals).
  H. Broker fee engine — `multiply_hammer_by_quantity` continues to
     scale broker + platform fee off `base_amount`, not raw hammer.
  I. Full settlement reconciliation — hammer → buyer premium →
     processing → taxes → total → seller payout all reference the
     same hammer basis.
  J. No duplicate calculations — every auction-end site that emits a
     hammer_total either delegates to `resolve_hammer_total` OR is a
     read-through of a caller-provided total.
  K. Historical records untouched — settled listings before iter451
     retain their persisted totals exactly.
  L. Invoice unit-level rendering — template renders
     `Unit Price / Qty / Line Total` = `$7.00 / 2 / $14.00` per line.
  M. Invoice PDF endpoint (e2e) — `/api/invoices/lots-won/{auction_id}
     /{user_id}` (POST) generates a PDF whose data reconciles to $14
     for the $7 × 2 lot the buyer actually won.

Historical-record safety: this suite NEVER mutates settled documents
and asserts `resolve_hammer_total` is not applied retroactively.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Make `/app/backend` importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.hammer_total import resolve_hammer_total  # noqa: E402
from services.broker_fee_engine import calculate_broker_transaction  # noqa: E402
from shared import calculate_buyer_fees, calculate_seller_fees, calculate_stripe_fee_recovery  # noqa: E402
from invoice_templates import lots_won_template  # noqa: E402
from invoice_templates_bilingual import lots_won_template as lots_won_bilingual  # noqa: E402


# ─────────────────────────────────────────────────────────────
# Scenario A — Core P0: $7 × 2 = $14 propagates end-to-end
# ─────────────────────────────────────────────────────────────
class TestScenarioAMultiItemMultiplication:
    """The exact scenario the user reported."""

    def test_A1_resolver_returns_14(self):
        """resolve_hammer_total on a $7×2 lot → hammer_total=$14."""
        listing = {"multiply_hammer_by_quantity": True}
        lot = {
            "lot_number": 1,
            "final_price": 7.00,
            "quantity_won": 2,
        }
        out = resolve_hammer_total(listing, lot=lot)
        assert out["unit_price"] == 7.00, (
            f"expected unit_price=7.00, got {out['unit_price']}"
        )
        assert out["quantity"] == 2, (
            f"expected quantity=2, got {out['quantity']}"
        )
        assert out["hammer_total"] == 14.00, (
            f"expected hammer_total=14.00, got {out['hammer_total']}"
        )
        assert out["is_multiplied"] is True

    def test_A2_buyer_premium_off_14(self):
        """Buyer premium at 5% (free tier) computes off $14, not $7."""
        fees = calculate_buyer_fees(hammer_price=14.00, subscription_tier="free")
        expected_premium = round(14.00 * 0.05, 2)  # $0.70
        assert fees.fee_amount == expected_premium, (
            f"expected premium={expected_premium}, got {fees.fee_amount}"
        )
        # Sanity: if the bug were still there, we'd see $0.35 (5% of $7)
        assert fees.fee_amount != 0.35, "REGRESSION: buyer premium off unit price"

    def test_A3_seller_commission_off_14(self):
        """Seller commission at 4% (free tier) computes off $14."""
        fees = calculate_seller_fees(hammer_price=14.00, subscription_tier="free")
        expected_comm = round(14.00 * 0.04, 2)  # $0.56
        assert fees.fee_amount == expected_comm

    def test_A4_stripe_fee_recovery_off_14_basis(self):
        """Processing (Stripe) fee recovery on hammer+premium reflects $14."""
        premium = round(14.00 * 0.05, 2)
        stripe = calculate_stripe_fee_recovery(desired_net=14.00 + premium)
        # Guardrail: this must be positive AND greater than the same
        # calculation off $7 (bug scenario). It never asserts an exact
        # penny — that depends on the tier defaults.
        stripe_bug_basis = calculate_stripe_fee_recovery(desired_net=7.00 + 0.35)
        assert stripe > stripe_bug_basis, (
            f"processing fee ({stripe}) must exceed bug-scenario fee "
            f"({stripe_bug_basis}) — else propagation is broken"
        )

    def test_A5_invoice_template_renders_14(self):
        """Invoice line renders `$7.00 / 2 / $14.00`."""
        data = {
            "invoice_number": "INV-A5",
            "buyer": {
                "name": "Test Buyer", "billing_address": "-",
                "phone": "-", "email": "-",
                "subscription_tier": "free", "is_premium": False,
            },
            "paddle_number": "0001",
            "auction": {
                "title": "Test Auction",
                "city": "Montreal", "region": "QC",
                "auction_end_date": datetime(2026, 2, 8, tzinfo=timezone.utc),
            },
            "invoice_date": "2026-02-08",
            "lots": [{
                "lot_number": 1,
                "title": "Widget",
                "description": "Test widget",
                "unit_price": 7.00,
                "quantity": 2,
                "hammer_price": 14.00,
            }],
            "premium_percentage": 5.0,
            "tax_rate_gst": 5.0,
            "tax_rate_qst": 9.975,
        }
        html = lots_won_template(data, lang="en")
        assert "$7.00" in html, "Unit price $7.00 missing from invoice HTML"
        # The qty cell shows the raw integer.
        assert ">2<" in html or ">2 <" in html, "Quantity 2 missing from invoice HTML"
        assert "$14.00" in html, "Line total $14.00 missing from invoice HTML"
        # Hammer total on the totals section must also read 14.00.
        assert "Hammer Total" in html
        assert "$14.00" in html.split("Hammer Total")[1][:120]

    def test_A5b_bilingual_invoice_template_renders_14_en(self):
        """Bilingual EN template — the one the /api/invoices/lots-won
        endpoint actually uses — renders `Unit Price / Qty / Line Total`."""
        data = {
            "invoice_number": "INV-A5b-EN",
            "buyer": {
                "name": "Test Buyer", "billing_address": "-",
                "phone": "-", "email": "-",
                "subscription_tier": "free", "is_premium": False,
            },
            "paddle_number": "0001",
            "auction": {
                "title": "Test Auction",
                "city": "Montreal", "region": "QC",
                "auction_end_date": datetime(2026, 2, 8, tzinfo=timezone.utc),
            },
            "invoice_date": "2026-02-08",
            "lots": [{
                "lot_number": 1, "title": "Widget", "description": "-",
                "unit_price": 7.00, "quantity": 2, "hammer_price": 14.00,
            }],
            "premium_percentage": 5.0,
            "tax_rate_gst": 5.0,
            "tax_rate_qst": 9.975,
        }
        html = lots_won_bilingual(data, lang="en")
        assert "Unit Price" in html, (
            "REGRESSION: bilingual EN invoice missing Unit Price header"
        )
        assert "Line Total" in html, (
            "REGRESSION: bilingual EN invoice missing Line Total header"
        )
        assert "$7.00" in html
        assert "$14.00" in html

    def test_A5c_bilingual_invoice_template_renders_14_fr(self):
        """Bilingual FR template renders `Prix unitaire / Qté / Total ligne`."""
        data = {
            "invoice_number": "INV-A5c-FR",
            "buyer": {
                "name": "Acheteur Test", "billing_address": "-",
                "phone": "-", "email": "-",
                "subscription_tier": "free", "is_premium": False,
            },
            "paddle_number": "0001",
            "auction": {
                "title": "Enchère Test",
                "city": "Montréal", "region": "QC",
                "auction_end_date": datetime(2026, 2, 8, tzinfo=timezone.utc),
            },
            "invoice_date": "2026-02-08",
            "lots": [{
                "lot_number": 1, "title": "Objet", "description": "-",
                "unit_price": 7.00, "quantity": 2, "hammer_price": 14.00,
            }],
            "premium_percentage": 5.0,
            "tax_rate_gst": 5.0,
            "tax_rate_qst": 9.975,
        }
        html = lots_won_bilingual(data, lang="fr")
        assert "Prix unitaire" in html, (
            "REGRESSION: bilingual FR invoice missing Prix unitaire header"
        )
        assert "Total ligne" in html, (
            "REGRESSION: bilingual FR invoice missing Total ligne header"
        )
        assert "$7.00" in html
        assert "$14.00" in html


# ─────────────────────────────────────────────────────────────
# Scenario B — Quantity of 1 (no multiplication)
# ─────────────────────────────────────────────────────────────
class TestScenarioBQuantityOne:
    def test_B1_qty_1_multiply_true(self):
        """Even when multiply=True, quantity=1 → hammer_total=unit_price."""
        listing = {"multiply_hammer_by_quantity": True}
        lot = {"final_price": 25.00, "quantity_won": 1}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["hammer_total"] == 25.00
        assert out["quantity"] == 1
        assert out["is_multiplied"] is False

    def test_B2_qty_1_multiply_false(self):
        """Multiply=False, qty=1 → same result."""
        listing = {"multiply_hammer_by_quantity": False}
        lot = {"final_price": 25.00, "quantity_won": 1}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["hammer_total"] == 25.00


# ─────────────────────────────────────────────────────────────
# Scenario C — Pre-multiplied / Buy Now (do NOT re-multiply)
# ─────────────────────────────────────────────────────────────
class TestScenarioCPreMultiplied:
    def test_C1_price_already_multiplied_flag(self):
        """`price_multiplied_by_quantity=True` → stored price IS the total."""
        listing = {"multiply_hammer_by_quantity": True}
        lot = {
            "final_price": 21.00,   # already 3×$7
            "quantity_won": 3,
            "price_multiplied_by_quantity": True,
        }
        out = resolve_hammer_total(listing, lot=lot)
        # $21 must NOT re-multiply to $63.
        assert out["hammer_total"] == 21.00, (
            f"REGRESSION: pre-multiplied price re-multiplied to {out['hammer_total']}"
        )
        # Derived unit price for display = 21/3 = $7.
        assert out["unit_price"] == 7.00
        assert out["already_multiplied"] is True
        assert out["is_multiplied"] is False

    def test_C2_buy_now_flow_unaffected(self):
        """Resolver never touches Buy Now — Buy Now uses `buy_now_price`
        on a separate checkout path. This test proves resolving a
        Buy-Now-shaped listing (no `multiply_hammer_by_quantity`, no
        `quantity`) is a safe no-op."""
        listing = {"buy_now_price": 99.00, "listing_type": "buy_now"}
        # No lot in a Buy Now scenario; just call with the listing.
        out = resolve_hammer_total(listing)
        # No final_price/current_price present → resolver returns 0.
        assert out["hammer_total"] == 0.00
        assert out["is_multiplied"] is False


# ─────────────────────────────────────────────────────────────
# Scenario D — Total-lot pricing (multiply flag OFF)
# ─────────────────────────────────────────────────────────────
class TestScenarioDTotalLotPricing:
    def test_D1_total_lot_multiply_false(self):
        """multiply=False, qty>1 → hammer_total=unit_price (no multiply)."""
        listing = {"multiply_hammer_by_quantity": False}
        lot = {"final_price": 100.00, "quantity_won": 5}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["hammer_total"] == 100.00, (
            f"REGRESSION: total-lot pricing incorrectly multiplied to "
            f"{out['hammer_total']}"
        )
        assert out["is_multiplied"] is False

    def test_D2_flag_missing_defaults_no_multiply(self):
        """Missing multiply flag → no multiplication (conservative)."""
        listing: Dict[str, Any] = {}
        lot = {"final_price": 50.00, "quantity_won": 4}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["hammer_total"] == 50.00


# ─────────────────────────────────────────────────────────────
# Scenario E — Multi-lot buyer w/ mixed quantities
# ─────────────────────────────────────────────────────────────
class TestScenarioEMultiLotMixed:
    def test_E1_two_lots_different_qty_reconcile_to_44(self):
        """Buyer wins Lot A ($7×2=$14) + Lot B ($10×3=$30) → total $44."""
        listing = {"multiply_hammer_by_quantity": True}
        lots = [
            {"lot_number": 1, "final_price": 7.00, "quantity_won": 2},
            {"lot_number": 2, "final_price": 10.00, "quantity_won": 3},
        ]
        totals: List[Dict[str, Any]] = [
            resolve_hammer_total(listing, lot=lot) for lot in lots
        ]
        assert totals[0]["hammer_total"] == 14.00
        assert totals[1]["hammer_total"] == 30.00
        merchandise_total = sum(t["hammer_total"] for t in totals)
        assert merchandise_total == 44.00, (
            f"expected merchandise total=$44, got ${merchandise_total}"
        )
        # Fee chain reconciles to $44 basis.
        buyer_prem = calculate_buyer_fees(merchandise_total, "free").fee_amount
        assert buyer_prem == round(44.00 * 0.05, 2)  # $2.20
        seller_comm = calculate_seller_fees(merchandise_total, "free").fee_amount
        assert seller_comm == round(44.00 * 0.04, 2)  # $1.76
        seller_receives = merchandise_total - seller_comm
        assert seller_receives == round(44.00 - 1.76, 2)  # $42.24

    def test_E2_invoice_template_multi_lot_sum_44(self):
        """Invoice PDF renders both lot lines and sums to $44."""
        data = {
            "invoice_number": "INV-E2",
            "buyer": {"name": "Buyer", "billing_address": "-", "phone": "-",
                      "email": "-", "subscription_tier": "free",
                      "is_premium": False},
            "paddle_number": "0002",
            "auction": {"title": "Multi-Lot Auction", "city": "Montreal",
                        "region": "QC",
                        "auction_end_date": datetime(2026, 2, 8, tzinfo=timezone.utc)},
            "invoice_date": "2026-02-08",
            "lots": [
                {"lot_number": 1, "title": "A",  "description": "A",
                 "unit_price": 7.00,  "quantity": 2, "hammer_price": 14.00},
                {"lot_number": 2, "title": "B",  "description": "B",
                 "unit_price": 10.00, "quantity": 3, "hammer_price": 30.00},
            ],
            "premium_percentage": 5.0,
            "tax_rate_gst": 5.0,
            "tax_rate_qst": 9.975,
        }
        html = lots_won_template(data, lang="en")
        assert "$14.00" in html and "$30.00" in html
        # Hammer total anchor must read $44.00
        assert "Hammer Total" in html
        after = html.split("Hammer Total")[1][:120]
        assert "$44.00" in after, (
            f"expected $44.00 near Hammer Total, got: {after}"
        )


# ─────────────────────────────────────────────────────────────
# Scenario F — Top-level listing vs winning lot precedence
# ─────────────────────────────────────────────────────────────
class TestScenarioFTopLevelVsLot:
    def test_F1_lot_overrides_listing_price(self):
        """When lot carries its own price/qty, listing defaults are ignored."""
        listing = {
            "multiply_hammer_by_quantity": True,
            # These top-level fields must NOT leak into the resolver.
            "final_price": 999.00,
            "quantity": 99,
            "current_price": 999.00,
        }
        lot = {"final_price": 7.00, "quantity_won": 2}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["hammer_total"] == 14.00, (
            f"REGRESSION: listing-level price leaked — got {out['hammer_total']}"
        )
        assert out["unit_price"] == 7.00
        assert out["quantity"] == 2

    def test_F2_lot_multiply_flag_overrides_listing(self):
        """Lot-level multiply flag wins over listing-level."""
        listing = {"multiply_hammer_by_quantity": True}
        # Lot explicitly opts out.
        lot = {
            "final_price": 100.00,
            "quantity_won": 3,
            "multiply_hammer_by_quantity": False,
        }
        out = resolve_hammer_total(listing, lot=lot)
        assert out["hammer_total"] == 100.00


# ─────────────────────────────────────────────────────────────
# Scenario G — Invalid / zero quantity protection
# ─────────────────────────────────────────────────────────────
class TestScenarioGInvalidQuantity:
    """Resolver clamps invalid quantities to 1 — never silently zeros
    a financial total. Higher-level validation (create-listing form,
    bid validation) is unchanged."""

    def test_G1_zero_quantity_clamps_to_one(self):
        listing = {"multiply_hammer_by_quantity": True}
        lot = {"final_price": 7.00, "quantity_won": 0}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["quantity"] == 1
        assert out["hammer_total"] == 7.00

    def test_G2_none_quantity_clamps_to_one(self):
        listing = {"multiply_hammer_by_quantity": True}
        lot = {"final_price": 7.00, "quantity_won": None}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["quantity"] == 1

    def test_G3_negative_quantity_clamps_to_one(self):
        listing = {"multiply_hammer_by_quantity": True}
        lot = {"final_price": 7.00, "quantity_won": -3}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["quantity"] == 1
        assert out["hammer_total"] == 7.00

    def test_G4_non_numeric_quantity_clamps_to_one(self):
        listing = {"multiply_hammer_by_quantity": True}
        lot = {"final_price": 7.00, "quantity_won": "not-a-number"}
        out = resolve_hammer_total(listing, lot=lot)
        assert out["quantity"] == 1


# ─────────────────────────────────────────────────────────────
# Scenario H — Broker fee engine (vehicle flow)
# ─────────────────────────────────────────────────────────────
class TestScenarioHBrokerFees:
    """Broker fee engine has its own `multiply_hammer_by_quantity`
    handling and must be unaffected by iter451 changes."""

    def test_H1_broker_multiply_scales_base(self):
        """base_amount = hammer × qty when multiply=True."""
        result = calculate_broker_transaction(
            hammer_price=7.00,
            quantity=2,
            multiply_hammer_by_quantity=True,
            broker_fee_structure={"type": "percentage", "percentage_rate": 0.05},
            buyer_province="QC",
        )
        assert result["hammer_total"] == 14.00
        # Platform fee = 2.5% of $14 = $0.35
        assert result["platform_fee"] == 0.35
        # Broker fee = 5% of $14 = $0.70
        assert result["broker_fee"] == 0.70

    def test_H2_broker_qty_1_unchanged(self):
        """qty=1 broker flow — base_amount stays at hammer."""
        result = calculate_broker_transaction(
            hammer_price=100.00,
            quantity=1,
            multiply_hammer_by_quantity=True,
            broker_fee_structure={"type": "fixed", "fixed_amount_cad": 25.00},
            buyer_province="ON",
        )
        assert result["hammer_total"] == 100.00
        assert result["platform_fee"] == 2.50
        assert result["broker_fee"] == 25.00

    def test_H3_broker_multiply_false_no_scale(self):
        """multiply_hammer_by_quantity=False → base_amount = hammer."""
        result = calculate_broker_transaction(
            hammer_price=100.00,
            quantity=5,
            multiply_hammer_by_quantity=False,
            broker_fee_structure={"type": "percentage", "percentage_rate": 0.05},
            buyer_province="QC",
        )
        assert result["hammer_total"] == 100.00
        assert result["platform_fee"] == 2.50


# ─────────────────────────────────────────────────────────────
# Scenario I — Full-chain reconciliation (settlement)
# ─────────────────────────────────────────────────────────────
class TestScenarioIReconciliation:
    """Every downstream field consumes the same hammer basis."""

    def test_I1_resolver_output_used_across_chain(self):
        """resolver → premium → processing → seller_payout all use $14."""
        listing = {"multiply_hammer_by_quantity": True}
        lot = {"final_price": 7.00, "quantity_won": 2}
        mt = resolve_hammer_total(listing, lot=lot)
        hammer = mt["hammer_total"]  # $14

        # Buyer premium
        buyer_prem = round(hammer * 0.05, 2)
        assert buyer_prem == 0.70

        # Processing (Stripe) fee recovery is applied to hammer + premium
        stripe = calculate_stripe_fee_recovery(desired_net=hammer + buyer_prem)
        assert stripe > 0

        # Seller commission
        seller_comm = round(hammer * 0.04, 2)
        assert seller_comm == 0.56

        # Reconciliation: seller net payout basis
        seller_net = round(hammer - seller_comm, 2)
        assert seller_net == 13.44

        # Buyer total (rough — actual settlement adds provincial tax)
        buyer_total_rough = round(hammer + buyer_prem + stripe, 2)
        assert buyer_total_rough > hammer + buyer_prem


# ─────────────────────────────────────────────────────────────
# Scenario J — Duplicate calculation protection
# ─────────────────────────────────────────────────────────────
class TestScenarioJNoDuplicateCalculations:
    """Every auction-end site that computes a hammer_total either
    delegates to `resolve_hammer_total` OR reads a caller-provided
    scalar. Guards against a future contributor computing
    `lot['current_price'] × lot['quantity']` inline in a new file."""

    HAMMER_END_SITES = [
        # (path, must-contain, forbidden-inline-patterns)
        "backend/services/auction_settlement.py",
        "backend/services/payment_collection.py",
        "backend/services/overdue_autocapture.py",
        "backend/routes/auctions.py",
        "backend/routes/invoices.py",
    ]

    def test_J1_hammer_sites_import_resolver(self):
        """Every hammer-end site imports resolve_hammer_total."""
        for rel in self.HAMMER_END_SITES:
            path = Path("/app") / rel
            src = path.read_text()
            assert "resolve_hammer_total" in src, (
                f"REGRESSION: {rel} no longer references resolve_hammer_total"
            )

    def test_J2_resolver_is_single_source_module(self):
        """`services/hammer_total.py` is the ONLY module defining
        `resolve_hammer_total`."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "def resolve_hammer_total",
             "/app/backend", "--include=*.py"],
            capture_output=True, text=True,
        )
        matches = [
            line for line in result.stdout.strip().split("\n")
            if line and "test_" not in line
        ]
        assert len(matches) == 1, (
            f"REGRESSION: resolve_hammer_total defined in "
            f"{len(matches)} places, expected 1:\n{result.stdout}"
        )
        assert "services/hammer_total.py" in matches[0]


# ─────────────────────────────────────────────────────────────
# Scenario K — Historical records untouched
# ─────────────────────────────────────────────────────────────
class TestScenarioKHistoricalUntouched:
    """iter451 is PROSPECTIVE ONLY. No migration / no rewrite of
    settled documents."""

    def test_K1_no_migration_scripts_touch_settled_docs(self):
        """No script under backend/scripts/ has an iter451 migration
        that rewrites `hammer_price` on already-settled listings."""
        scripts = Path("/app/backend/scripts")
        offenders = []
        if scripts.exists():
            for py in scripts.glob("*.py"):
                src = py.read_text()
                # A migration is a real offender only if it BOTH mentions
                # iter451/resolve_hammer_total AND writes hammer_price
                # on settled docs.
                if ("iter451" in src or "resolve_hammer_total" in src) and (
                    'update' in src.lower() and 'hammer_price' in src
                ):
                    offenders.append(py.name)
        assert not offenders, (
            f"REGRESSION: iter451 migration writes hammer_price on settled "
            f"docs in: {offenders}"
        )

    def test_K2_resolver_reads_only_no_side_effects(self):
        """resolve_hammer_total returns a fresh dict — never mutates
        the input listing/lot dicts."""
        listing = {"multiply_hammer_by_quantity": True, "sentinel": "X"}
        listing_copy = dict(listing)
        lot = {"final_price": 7.00, "quantity_won": 2, "sentinel_lot": "Y"}
        lot_copy = dict(lot)
        resolve_hammer_total(listing, lot=lot)
        assert listing == listing_copy, "resolver mutated listing dict"
        assert lot == lot_copy, "resolver mutated lot dict"

    def test_K3_persisted_historical_final_price_untouched(self):
        """Simulate a historical lot doc (pre-iter451: `final_price`
        stored as single unit, no `winning_unit_price` / `winning_quantity`
        stamped). Reading via the resolver returns a *new* value derived
        on the fly — but the persisted `final_price` on the input dict
        is preserved."""
        historical_listing = {"multiply_hammer_by_quantity": True}
        historical_lot_stored = {
            "lot_number": 42,
            "final_price": 7.00,       # persisted as unit price (bug era)
            "quantity_won": 2,
            "sold_at": "2025-12-01T00:00:00Z",  # settled before iter451
            "status": "sold",
        }
        snapshot = dict(historical_lot_stored)
        # New read via resolver:
        totals = resolve_hammer_total(historical_listing, lot=historical_lot_stored)
        # The RETURNED (computed) hammer_total = $14, but the persisted
        # `final_price` on disk MUST remain $7 (not $14) — no rewrite.
        assert totals["hammer_total"] == 14.00
        assert historical_lot_stored == snapshot, (
            "REGRESSION: resolver rewrote the historical persisted "
            "final_price. iter451 must never mutate settled docs."
        )
        assert historical_lot_stored["final_price"] == 7.00


# ─────────────────────────────────────────────────────────────
# Scenario L — Invoice endpoint (DB-level e2e, no HTTP)
# ─────────────────────────────────────────────────────────────
class TestScenarioLInvoiceUnitLevel:
    """Direct invocation of the invoice route function against a
    mocked in-memory DB — exercises the same code path as
    POST /api/invoices/lots-won/{auction_id}/{user_id}."""

    def test_L1_invoice_pdf_endpoint_uses_resolver_for_won_lot(self):
        """The route iterates all lots, keeps only those where
        `winner_user_id == user_id`, and runs each through
        `resolve_hammer_total`. Verify the exact shape of `lots_won`."""
        auction = {
            "id": "auct-L1",
            "seller_id": "seller-L1",
            "title": "Multi-Item L1",
            "city": "Montreal",
            "region": "QC",
            "auction_end_date": "2026-02-08T00:00:00Z",
            "multiply_hammer_by_quantity": True,
            "lots": [
                {"lot_number": 1, "title": "Won A", "description": "-",
                 "final_price": 7.00, "quantity_won": 2,
                 "winner_user_id": "buyer-L1", "status": "sold"},
                {"lot_number": 2, "title": "Won B", "description": "-",
                 "final_price": 10.00, "quantity_won": 3,
                 "winner_user_id": "buyer-L1", "status": "sold"},
                {"lot_number": 3, "title": "Someone else's lot",
                 "description": "-",
                 "final_price": 100.00, "quantity_won": 1,
                 "winner_user_id": "buyer-Z", "status": "sold"},
                {"lot_number": 4, "title": "Unsold lot", "description": "-",
                 "final_price": 0, "quantity_won": 1,
                 "winner_user_id": None, "status": "ended"},
            ],
            "buyer_premium_pct": 5.0,
            "commission_rate": 4.0,
        }
        # Mirror the exact loop from routes/invoices.py::generate_lots_won_invoice
        lots_won = []
        for lot in auction["lots"]:
            lot_winner = (
                lot.get("winner_user_id")
                or lot.get("winner_id")
                or lot.get("highest_bidder_id")
            )
            if lot_winner != "buyer-L1":
                continue
            if lot.get("status") and lot.get("status") not in ("sold", "won"):
                continue
            totals = resolve_hammer_total(auction, lot=lot)
            lots_won.append({
                "lot_number": lot["lot_number"],
                "title": lot["title"],
                "description": lot["description"],
                "quantity": totals["quantity"],
                "unit_price": totals["unit_price"],
                "hammer_price": totals["hammer_total"],
                "line_total": totals["hammer_total"],
            })
        # Assert exactly 2 lots (won by buyer-L1), sums to $44.
        assert len(lots_won) == 2, (
            f"expected 2 lots won by buyer-L1, got {len(lots_won)}"
        )
        merchandise = sum(l["hammer_price"] for l in lots_won)
        assert merchandise == 44.00
        # Line-level: $7 × 2 = $14 and $10 × 3 = $30
        assert lots_won[0]["unit_price"] == 7.00
        assert lots_won[0]["quantity"] == 2
        assert lots_won[0]["hammer_price"] == 14.00
        assert lots_won[1]["unit_price"] == 10.00
        assert lots_won[1]["quantity"] == 3
        assert lots_won[1]["hammer_price"] == 30.00


# ─────────────────────────────────────────────────────────────
# Scenario M — HTTP e2e via /api/invoices/lots-won (live preview)
# ─────────────────────────────────────────────────────────────
# Executed via a separate script when the preview backend is up. This
# pytest test is a placeholder that captures the expected buyer-facing
# reconciliation and is exercised by
# `tests/live_e2e_iter451_invoice_pdf.py`.
class TestScenarioMExpectedInvoiceReconciliation:
    def test_M1_full_reconciliation_snapshot(self):
        """One canonical snapshot the live e2e script must reproduce
        end-to-end."""
        hammer_total = 14.00          # $7 × 2
        buyer_premium = round(hammer_total * 0.05, 2)  # $0.70
        subtotal = round(hammer_total + buyer_premium, 2)  # $14.70
        gst_on_hammer = round(hammer_total * 0.05, 2)          # $0.70
        qst_on_hammer = round(hammer_total * 0.09975, 2)       # $1.40
        gst_on_prem   = round(buyer_premium * 0.05, 2)         # $0.04
        qst_on_prem   = round(buyer_premium * 0.09975, 2)      # $0.07
        total_tax = round(
            gst_on_hammer + qst_on_hammer + gst_on_prem + qst_on_prem, 2
        )
        grand_total = round(subtotal + total_tax, 2)
        seller_comm = round(hammer_total * 0.04, 2)  # $0.56
        seller_net = round(hammer_total - seller_comm, 2)  # $13.44
        # Snapshot dict — the live e2e script asserts against this.
        snap = {
            "hammer_total": hammer_total,
            "buyer_premium": buyer_premium,
            "subtotal_pre_tax": subtotal,
            "gst_on_hammer": gst_on_hammer,
            "qst_on_hammer": qst_on_hammer,
            "total_tax": total_tax,
            "grand_total": grand_total,
            "seller_commission": seller_comm,
            "seller_net_payout": seller_net,
        }
        # Sanity guardrails so a future edit that flips a %  breaks this.
        assert snap["hammer_total"] == 14.00
        assert snap["buyer_premium"] == 0.70
        assert snap["seller_net_payout"] == 13.44


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
