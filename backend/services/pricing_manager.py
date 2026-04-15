"""
BidVex — PricingManager (Master Pricing Structure v1)
Canonical pricing engine for ALL transaction types.

Rules implemented:
  1. Tier-based rates (Standard/Premium/VIP/Partner)
  2. Vehicle auctions (2.5% platform fee to buyer only, seller $0)
  3. Non-vehicle Stripe (hammer + BP + stripe + tax) / Cash (split invoices)
  4. Stripe margin protection on every invoice
  5. Jurisdiction-aware tax on fees only (never hammer)
  6. Subscriptions/Promotions (flat price + stripe + tax)
  7. Two separate Stripe charges per transaction
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field, asdict
from typing import Optional

from services.vehicle_pricing import calculate_taxes, TaxBreakdown

# ─── Constants ────────────────────────────────────────────────
STRIPE_PCT = Decimal("0.029")
STRIPE_FIXED = Decimal("0.30")
VEHICLE_PLATFORM_FEE_RATE = Decimal("0.025")
PARTNER_SELLER_COMMISSION_RATE = Decimal("0.03")

BUYER_PREMIUM_RATES = {
    "free": Decimal("0.05"), "basic": Decimal("0.05"), "standard": Decimal("0.05"),
    "premium": Decimal("0.035"),
    "vip": Decimal("0.03"), "vip_elite": Decimal("0.03"),
    "partner": Decimal("0"),
}
SELLER_COMMISSION_RATES = {
    "free": Decimal("0.04"), "basic": Decimal("0.04"), "standard": Decimal("0.04"),
    "premium": Decimal("0.025"),
    "vip": Decimal("0.02"), "vip_elite": Decimal("0.02"),
    "partner": Decimal("0.03"),
}


def _r(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _f(v) -> float:
    return float(v) if isinstance(v, Decimal) else v


def stripe_recovery(fees_subtotal: Decimal) -> Decimal:
    """Rule 4 — (fees_subtotal × 0.029) + 0.30. Returns $0 if no fees."""
    if fees_subtotal <= 0:
        return Decimal("0")
    return _r(fees_subtotal * STRIPE_PCT + STRIPE_FIXED)


def _tier(raw: str) -> str:
    return (raw or "free").lower().strip()


def _tax_label(tb: TaxBreakdown) -> str:
    t = tb.tax_type
    if t == "HST":
        return f"HST ({_f(tb.total_rate * 100):.0f}%)"
    if t == "GST+QST":
        return "GST + QST (14.975%)"
    if t == "GST":
        return f"GST ({_f(tb.total_rate * 100):.0f}%)"
    return t


# ─── Result dataclasses ──────────────────────────────────────

@dataclass
class InvoiceLine:
    description: str
    amount: float
    line_type: str  # fee, stripe, tax, hammer, deduction
    rate: Optional[float] = None

@dataclass
class SideInvoice:
    """One side of a split invoice (buyer OR seller)."""
    lines: list = field(default_factory=list)
    fees_subtotal: float = 0.0
    stripe_recovery: float = 0.0
    tax_amount: float = 0.0
    tax_rate: float = 0.0
    tax_type: str = ""
    tax_label: str = ""
    total: float = 0.0

    def to_dict(self):
        d = asdict(self)
        d["lines"] = [asdict(ln) for ln in self.lines]
        return d

@dataclass
class PricingResult:
    """Complete pricing result for any transaction type."""
    transaction_type: str  # vehicle, non_vehicle_stripe, non_vehicle_cash, subscription
    hammer_price: float = 0.0
    buyer_invoice: SideInvoice = field(default_factory=SideInvoice)
    seller_invoice: Optional[SideInvoice] = None
    buyer_tier: str = "free"
    seller_tier: str = "free"
    province: str = ""
    bidvex_revenue: float = 0.0

    def to_dict(self):
        d = {
            "transaction_type": self.transaction_type,
            "hammer_price": self.hammer_price,
            "buyer_tier": self.buyer_tier,
            "seller_tier": self.seller_tier,
            "province": self.province,
            "bidvex_revenue": self.bidvex_revenue,
            "buyer_invoice": self.buyer_invoice.to_dict(),
        }
        if self.seller_invoice:
            d["seller_invoice"] = self.seller_invoice.to_dict()
        return d


# ─── PricingManager ───────────────────────────────────────────

class PricingManager:
    """
    Canonical pricing engine. Call the appropriate method per transaction type.

    Every method returns a PricingResult with buyer_invoice and optional seller_invoice,
    each containing exact line items, stripe recovery, tax, and total.
    """

    # ── Rule 2: Vehicle Auction ──────────────────────────────
    @staticmethod
    def vehicle_auction(
        hammer_price: float,
        buyer_province: str,
        buyer_tier: str = "free",
    ) -> PricingResult:
        """
        Vehicle auctions — Non-custodial.
        Buyer pays: 2.5% platform fee + stripe recovery + tax.
        Seller pays: $0. Hammer settled directly buyer↔seller.
        """
        hp = Decimal(str(hammer_price))
        platform_fee = _r(hp * VEHICLE_PLATFORM_FEE_RATE)

        sr = stripe_recovery(platform_fee)
        taxable = platform_fee + sr
        tax = calculate_taxes(taxable, buyer_province)

        total = _r(platform_fee + sr + tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine("Vehicle Platform Fee (2.5%)", _f(platform_fee), "fee", 0.025),
                InvoiceLine("Stripe Processing Fee", _f(sr), "stripe"),
                InvoiceLine(f"Tax — {_tax_label(tax)}", _f(tax.total_tax), "tax", _f(tax.total_rate)),
            ],
            fees_subtotal=_f(platform_fee),
            stripe_recovery=_f(sr),
            tax_amount=_f(tax.total_tax),
            tax_rate=_f(tax.total_rate),
            tax_type=tax.tax_type,
            tax_label=_tax_label(tax),
            total=_f(total),
        )

        return PricingResult(
            transaction_type="vehicle",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=None,  # seller pays $0
            buyer_tier=buyer_tier,
            seller_tier="n/a",
            province=buyer_province.upper(),
            bidvex_revenue=_f(platform_fee),
        )

    # ── Rule 3 Path A: Non-Vehicle, Stripe Payment ──────────
    @staticmethod
    def non_vehicle_stripe(
        hammer_price: float,
        buyer_province: str,
        buyer_tier: str = "free",
        seller_tier: str = "free",
    ) -> PricingResult:
        """
        Non-vehicle, seller chose Stripe.
        BidVex collects full hammer from buyer, pays out seller minus commission.
        Buyer: hammer + BP + stripe_recovery(on BP) + tax(on BP + stripe).
        Seller: hammer - SC - stripe_transfer(on SC) - tax(on SC + stripe).
        """
        hp = Decimal(str(hammer_price))
        bt = _tier(buyer_tier)
        st = _tier(seller_tier)

        bp_rate = BUYER_PREMIUM_RATES.get(bt, BUYER_PREMIUM_RATES["free"])
        sc_rate = SELLER_COMMISSION_RATES.get(st, SELLER_COMMISSION_RATES["free"])

        bp = _r(hp * bp_rate)
        sc = _r(hp * sc_rate)

        # Buyer side — stripe recovery on BP only (the BidVex fee)
        b_sr = stripe_recovery(bp)
        b_taxable = bp + b_sr
        b_tax = calculate_taxes(b_taxable, buyer_province)
        b_total = _r(hp + bp + b_sr + b_tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine("Hammer Price", _f(hp), "hammer"),
                InvoiceLine(f"Buyer Premium ({_f(bp_rate * 100):.1f}%)", _f(bp), "fee", _f(bp_rate)),
                InvoiceLine("Stripe Processing Fee", _f(b_sr), "stripe"),
                InvoiceLine(f"Tax — {_tax_label(b_tax)}", _f(b_tax.total_tax), "tax", _f(b_tax.total_rate)),
            ],
            fees_subtotal=_f(bp),
            stripe_recovery=_f(b_sr),
            tax_amount=_f(b_tax.total_tax),
            tax_rate=_f(b_tax.total_rate),
            tax_type=b_tax.tax_type,
            tax_label=_tax_label(b_tax),
            total=_f(b_total),
        )

        # Seller side — stripe transfer fee on SC, tax on (SC + stripe)
        s_sr = stripe_recovery(sc)
        s_taxable = sc + s_sr
        s_tax = calculate_taxes(s_taxable, buyer_province)
        s_net = _r(hp - sc - s_sr - s_tax.total_tax)

        seller = SideInvoice(
            lines=[
                InvoiceLine("Hammer Price (Gross)", _f(hp), "hammer"),
                InvoiceLine(f"Seller Commission ({_f(sc_rate * 100):.1f}%)", -_f(sc), "deduction", _f(sc_rate)),
                InvoiceLine("Stripe Transfer Fee", -_f(s_sr), "stripe"),
                InvoiceLine(f"Tax on Fees — {_tax_label(s_tax)}", -_f(s_tax.total_tax), "tax", _f(s_tax.total_rate)),
            ],
            fees_subtotal=_f(sc),
            stripe_recovery=_f(s_sr),
            tax_amount=_f(s_tax.total_tax),
            tax_rate=_f(s_tax.total_rate),
            tax_type=s_tax.tax_type,
            tax_label=_tax_label(s_tax),
            total=_f(s_net),
        )

        return PricingResult(
            transaction_type="non_vehicle_stripe",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=seller,
            buyer_tier=bt,
            seller_tier=st,
            province=buyer_province.upper(),
            bidvex_revenue=_f(bp + sc),
        )

    # ── Rule 3 Path B: Non-Vehicle, Cash / E-Transfer ───────
    @staticmethod
    def non_vehicle_cash(
        hammer_price: float,
        buyer_province: str,
        buyer_tier: str = "free",
        seller_tier: str = "free",
    ) -> PricingResult:
        """
        Non-vehicle, seller chose Cash or E-Transfer.
        BidVex does NOT collect the hammer price.
        Buyer invoice: BP + stripe_recovery(on BP) + tax.
        Seller invoice: SC + stripe_recovery(on SC) + tax.
        Hammer settled directly buyer↔seller.
        """
        hp = Decimal(str(hammer_price))
        bt = _tier(buyer_tier)
        st = _tier(seller_tier)

        bp_rate = BUYER_PREMIUM_RATES.get(bt, BUYER_PREMIUM_RATES["free"])
        sc_rate = SELLER_COMMISSION_RATES.get(st, SELLER_COMMISSION_RATES["free"])

        bp = _r(hp * bp_rate)
        sc = _r(hp * sc_rate)

        # Buyer invoice — BP only
        b_sr = stripe_recovery(bp)
        b_taxable = bp + b_sr
        b_tax = calculate_taxes(b_taxable, buyer_province)
        b_total = _r(bp + b_sr + b_tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine(f"Buyer Premium ({_f(bp_rate * 100):.1f}%)", _f(bp), "fee", _f(bp_rate)),
                InvoiceLine("Stripe Processing Fee", _f(b_sr), "stripe"),
                InvoiceLine(f"Tax — {_tax_label(b_tax)}", _f(b_tax.total_tax), "tax", _f(b_tax.total_rate)),
            ],
            fees_subtotal=_f(bp),
            stripe_recovery=_f(b_sr),
            tax_amount=_f(b_tax.total_tax),
            tax_rate=_f(b_tax.total_rate),
            tax_type=b_tax.tax_type,
            tax_label=_tax_label(b_tax),
            total=_f(b_total),
        )

        # Seller invoice — SC only
        s_sr = stripe_recovery(sc)
        s_taxable = sc + s_sr
        s_tax = calculate_taxes(s_taxable, buyer_province)
        s_total = _r(sc + s_sr + s_tax.total_tax)

        seller = SideInvoice(
            lines=[
                InvoiceLine(f"Seller Commission ({_f(sc_rate * 100):.1f}%)", _f(sc), "fee", _f(sc_rate)),
                InvoiceLine("Stripe Processing Fee", _f(s_sr), "stripe"),
                InvoiceLine(f"Tax — {_tax_label(s_tax)}", _f(s_tax.total_tax), "tax", _f(s_tax.total_rate)),
            ],
            fees_subtotal=_f(sc),
            stripe_recovery=_f(s_sr),
            tax_amount=_f(s_tax.total_tax),
            tax_rate=_f(s_tax.total_rate),
            tax_type=s_tax.tax_type,
            tax_label=_tax_label(s_tax),
            total=_f(s_total),
        )

        return PricingResult(
            transaction_type="non_vehicle_cash",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=seller,
            buyer_tier=bt,
            seller_tier=st,
            province=buyer_province.upper(),
            bidvex_revenue=_f(bp + sc),
        )

    # ── Rule 6: Subscription / Promotion / Email Marketing ──
    @staticmethod
    def flat_purchase(
        base_price: float,
        buyer_province: str,
        label: str = "Subscription",
    ) -> PricingResult:
        """
        Flat-price purchase (subscription, promotion, email marketing).
        total = base_price + stripe_recovery(on base_price) + tax(on base_price + stripe_recovery).
        """
        price = Decimal(str(base_price))
        sr = stripe_recovery(price)
        taxable = price + sr
        tax = calculate_taxes(taxable, buyer_province)
        total = _r(price + sr + tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine(label, _f(price), "fee"),
                InvoiceLine("Stripe Processing Fee", _f(sr), "stripe"),
                InvoiceLine(f"Tax — {_tax_label(tax)}", _f(tax.total_tax), "tax", _f(tax.total_rate)),
            ],
            fees_subtotal=_f(price),
            stripe_recovery=_f(sr),
            tax_amount=_f(tax.total_tax),
            tax_rate=_f(tax.total_rate),
            tax_type=tax.tax_type,
            tax_label=_tax_label(tax),
            total=_f(total),
        )

        return PricingResult(
            transaction_type="flat_purchase",
            hammer_price=0,
            buyer_invoice=buyer,
            seller_invoice=None,
            province=buyer_province.upper(),
            bidvex_revenue=_f(price),
        )


    # ── Partner Auction ──────────────────────────────────────
    @staticmethod
    def partner_auction(
        hammer_price: float,
        buyer_province: str,
    ) -> PricingResult:
        """
        Partner-tier seller listing.
        Buyer pays: $0 BP from BidVex. Partner sets and keeps their own BP.
        Seller (Partner) pays: 3% flat commission + stripe recovery + tax.
        BidVex has no visibility or claim on the Partner's own buyer premium.
        """
        hp = Decimal(str(hammer_price))

        # BUYER INVOICE — BidVex charges buyer nothing
        buyer = SideInvoice(
            lines=[
                InvoiceLine("Buyer Premium (Partner listing — $0 BidVex fee)", 0.0, "fee", 0.0),
            ],
            fees_subtotal=0.0,
            stripe_recovery=0.0,
            tax_amount=0.0,
            tax_rate=0.0,
            tax_type="N/A",
            tax_label="N/A",
            total=0.0,
        )

        # SELLER (PARTNER) INVOICE — 3% flat commission
        sc = _r(hp * PARTNER_SELLER_COMMISSION_RATE)
        sr = stripe_recovery(sc)
        taxable = sc + sr
        tax = calculate_taxes(taxable, buyer_province)
        s_total = _r(sc + sr + tax.total_tax)

        seller = SideInvoice(
            lines=[
                InvoiceLine("Seller Commission (3.0% flat — Partner)", _f(sc), "fee", 0.03),
                InvoiceLine("Stripe Processing Fee", _f(sr), "stripe"),
                InvoiceLine(f"Tax — {_tax_label(tax)}", _f(tax.total_tax), "tax", _f(tax.total_rate)),
            ],
            fees_subtotal=_f(sc),
            stripe_recovery=_f(sr),
            tax_amount=_f(tax.total_tax),
            tax_rate=_f(tax.total_rate),
            tax_type=tax.tax_type,
            tax_label=_tax_label(tax),
            total=_f(s_total),
        )

        return PricingResult(
            transaction_type="partner_auction",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=seller,
            buyer_tier="partner",
            seller_tier="partner",
            province=buyer_province.upper(),
            bidvex_revenue=_f(sc),
        )
