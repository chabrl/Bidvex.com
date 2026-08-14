# LEGAL TAX REVIEW REQUIRED
**Purpose:** Collect every BidVex tax rule that requires validation by a
Canadian tax professional (CPA / CRA / Revenu Québec practitioner)
BEFORE the P6 consolidation writes code.

**No legal interpretations are made in this file.** Each item is a
question backed by evidence pointing to the code location; a legal
opinion is required on each. Do NOT implement any tax treatment based
on assumptions gathered here.

---

## 1. Interprovincial Taxation — CRA Place-of-Supply (§142.1)

**Current behaviour** (see `services/fee_calculator.py::_iter350_individual`):
- Buyer premium is taxed at the **buyer's province** (recipient rule).
- Seller commission is taxed at the **seller's province**.
- Partner platform fee is taxed at the **partner's province**.
- Vehicle 2.5% is taxed at the **buyer's province**.
- Storage 5% is taxed at the **buyer's province** (iter443 model).
- Broker's own fee + BidVex 2.5% both taxed at the **buyer's province**.

**Questions requiring legal review:**
1. Is CRA §142.1 the correct authority for splitting the recipient
   between buyer and seller when BidVex is the merchant of record for
   both fees on a single settlement?
2. If a QC-registered seller sells to an ON buyer, is BidVex's 4% seller
   commission taxable at QC (seller/recipient) or ON (place of supply
   under §142.1(1)(b))? The current code taxes at seller province — is
   this correct for services rendered to a QC-based seller regardless of
   where the buyer is?
3. If a partner has partner_province=QC but sells to a buyer in
   Ontario, and the partner is the MERCHANT of record (Model A₁), does
   BidVex's 3% platform fee owe QC 14.975% or ON 13%? Code currently
   taxes at partner_prov.

**Evidence:** `services/fee_calculator.py` lines 456–478 (individual),
537–553 (partner), 630–636 (vehicle), 702–708 (storage).

---

## 2. Marketplace Facilitator Rules (ETA §211.1, Bill C-30)

**Current behaviour:** BidVex collects and remits GST/QST/HST on
its buyer premium and seller commission. Hammer price is
NOT taxed on non-business sellers ("private sale" default).

**Questions:**
1. Under ETA §211.1(1) (marketplace facilitator rule, effective July 2021),
   is BidVex REQUIRED to collect and remit tax on the hammer price of a
   third-party seller's supply through its digital platform, regardless
   of the seller's registration status?
2. If yes, the current "individual seller → no hammer tax" branch (in
   `services/tax_engine.py::calculate_general_payment` lines 466–469
   AND `services/fee_calculator.py::FeeCalculator.calculate_buyer_total`
   line 1001–1004) is a defect. Confirm.
3. Does the "private sale — tax free" badge shown on the buyer-facing
   auction detail page (`ListingDetailPage.js:855` and
   `LotDetailPage.jsx:416`) reflect a correct legal position under
   Bill C-30, or does it need to be removed / relabelled?
4. What is BidVex's own marketplace-facilitator threshold ($30k rolling
   4-quarter, or the specific facilitator-supply rule)? Any tax
   computed above/below that threshold?

**Evidence:** All hammer-tax branches consistently gate on
`seller_is_business` — never on `bidvex_is_facilitator`.

---

## 3. Escrow Taxation Treatment

**Current behaviour:** Escrow releases go through the same settlement
pipeline (`services/auction_settlement.settle_auction`) that computes
buyer premium, seller commission, and taxes on both. The escrow release
itself (the movement of buyer's funds out of BidVex's holding account
to the seller) is treated as a non-taxable event.

**Questions:**
1. Is the release of held escrow funds a taxable "supply" under ETA
   §165? Current implementation says NO. Confirm.
2. If the seller invoices BidVex for storage service fees or dispute
   resolution fees on top of the escrow, would that be a taxable
   supply requiring GST/HST? Currently no such fee exists.
3. Bilingual receipts show "Escrow" as a line item — does the label
   itself need tax registration disclosure?

**Evidence:** No matches in the codebase for tax on escrow — search
`services/*escrow*`, `routes/*escrow*`. Escrow releases are
non-taxed by omission.

---

## 4. Deposit Taxation Treatment

**Current behaviour:**
- **Bid deposits** (`db.bidding_deposits`): held Stripe PaymentIntent
  with `capture_method=manual`. Captured on win, refunded on loss.
  No tax computed on the deposit itself.
- **Vehicle deposits** (`db.broker_deposits`, $500 CAD, iter350):
  same pattern. No tax.
- **Storage deposits** (`db.storage_deposits`): same.
- **Security deposits** (broker workflow): same.

**Questions:**
1. CRA generally treats refundable security deposits as
   non-taxable until forfeited (§168(9)). Confirm this applies to
   BidVex bid deposits.
2. When a deposit is CAPTURED on a winning bid, it becomes part of the
   buyer's payment against the invoice. The captured amount is
   already netted into `buyer_total` (which IS taxed). Confirm no
   double-tax risk.
3. Forfeited deposits (no-show, buyer default) currently flow to
   BidVex as revenue with no tax attached. If a forfeited deposit is a
   liquidated damage payment, it is generally non-taxable — but if it
   is a service fee (e.g., "no-show penalty"), it IS taxable. See §5.

**Evidence:**
- `services/deposit_auto_capture.py`, `services/deposit_refund_queue.py`,
  `services/broker_deposit_service.py` — no tax code.

---

## 5. Penalty Taxation Treatment

**Current behaviour:**
- **No-show penalties**, **bidder penalties**, **seller penalties**,
  **administrative penalties** — no tax computed anywhere.

**Questions:**
1. Under CRA IT-467R2, "damages" are non-taxable but "service
   penalties" or "administrative fees" are TAXABLE.
2. Classify each of the four penalty types by that test. If any are
   service-based (e.g., "administrative fee for late payment"), they
   MUST carry GST/HST/QST at the payer's province.
3. Current implementation charges every penalty via Stripe as a raw
   dollar amount with no tax line. Confirm this is correct for each
   penalty type OR list which penalty types need tax added.

**Evidence:** `grep tax /app/backend/services/*penalt*` returns zero
matches. Penalties are non-taxed by omission.

---

## 6. Subscription Taxation Treatment

**Current behaviour** (see `services/subscription_service.py`):
- Subscription prices displayed as `"$180 CAD/year + taxes"` (line 106).
- No tax value is attached to the Stripe Subscription object.
- Stripe collects the base price only.

**Questions:**
1. BidVex's subscription is a "supply of digital service" under
   ETA §143(1) — taxable at the SUBSCRIBER's province of residence.
2. Currently the subscription price is sent to Stripe as a bare amount
   with no tax rate. Stripe does support "tax rate" objects — is
   BidVex REQUIRED to use them for CRA-compliant remittance, or is a
   post-hoc invoice remittance acceptable?
3. If tax must be added:
   - Partner ($100/y) → +14.975% QC / +13% ON / etc. per subscriber
     province — up to $115 CAD/y.
   - Premium ($180/y) → up to $207 CAD/y.
   - Partner Pro ($240/y) → up to $276 CAD/y.
   - VIP ($300/y) → up to $345 CAD/y.
   Do the current customer-facing marketing pages / signup flows need
   to disclose the "+ taxes" reality with the estimated final price?
4. Trial and promo subscription lines (e.g. Canada Day promo, first
   month free) — how is tax handled when the base is $0?

**Evidence:** `services/subscription_service.py` lines 57–60; no
`services/*tax*` reference in the subscription lifecycle.

---

## 7. Marketing / Advertising / Ad Campaigns Taxation

**Current behaviour:**
- `services/email_marketing.py`, `services/marketing_flows.py`,
  `services/user_email_marketing.py`, `routes/ad_campaigns.py`,
  `routes/external_campaigns.py` — no tax computed on any invoice
  or promotion charge.

**Questions:**
1. Are marketing invoices ("promoted listing", "featured slot",
   "ad campaign purchase") supplies of a digital service? Yes → each
   should carry tax at the purchaser's province.
2. What is the exact tax base for a "featured slot" purchase where
   BidVex is the merchant? Current code sends bare dollar amount to
   Stripe. Confirm this is a defect or intentional.
3. Ad-campaign referrals + affiliate commissions (3% per iter338) —
   are they taxable services if paid to a Canadian resident? Foreign
   affiliate?

**Evidence:** Empty grep for tax in marketing files.

---

## 8. Buyer Premium Taxation Treatment

**Current behaviour:** Buyer premium is taxed at the BUYER's province
under §142.1 recipient rule. `services/fee_calculator.py::_iter350_individual`
line 462.

**Questions:**
1. Is buyer premium legally a "buyer service fee" (BidVex supplies to
   buyer) or a "seller commission" (partly paid by buyer on behalf of
   seller)? The former puts tax at buyer prov (current); the latter
   would put it at seller prov.
2. Case law citation requested for Canadian auction platforms —
   which precedent controls?

---

## 9. Partner Buyer-Premium Sharing

**Current behaviour** (see `_iter350_partner`):
- Buyer pays partner's own BP directly to partner (100% → partner).
- BidVex charges partner 3% platform fee separately.
- BidVex 3% is taxed at PARTNER's province.
- Partner's own BP is NOT taxed by BidVex (partner remits their own tax).

**Questions:**
1. When a partner shares a portion of the BP with BidVex (revenue
   share), is BidVex's share taxable at partner prov (current) or
   buyer prov?
2. If the partner is a business-registered entity in QC and the buyer
   is in AB, and partner's BP is 5% while BidVex takes 3%, what is
   the correct GST/QST/HST treatment on each slice? Confirm the
   current implementation is correct.

---

## 10. Vehicle Auction Tax Split

**Current behaviour** (`_iter350_vehicle`):
- Hammer paid DIRECTLY buyer↔dealer (BidVex not custodial).
- BidVex charges buyer 2.5% platform fee at buyer's province.
- No hammer tax collected by BidVex.

**Questions:**
1. In a non-custodial vehicle auction, does BidVex have any liability
   to REMIT tax on the hammer sale even though the funds don't flow
   through BidVex? (Bill C-30 marketplace-facilitator vs
   direct-sale distinction.)
2. Provincial MSRP + used-vehicle levy interaction with GST/HST — any
   province where the platform fee itself is exempt?

---

## 11. Broker Fee Split — QC-only QST branch

**Current defect** (see `services/broker_fee_engine.py:150–151` and
`routes/broker_compliance.py:146`):
```
gst = subtotal_taxable * GST_RATE
qst = subtotal_taxable * QST_RATE if province == "QC" else 0.0
```
If buyer is in ON (HST 13%), the code computes GST 5% only — the
provincial 8% HST layer is NEVER added.

**Questions:**
1. This is unambiguously an under-collection bug. Confirm the correct
   treatment (HST 13% total on ON) and flag every past broker
   invoice for potential re-issue.
2. Which historical broker transactions are affected? Requires a
   data audit.

---

## 12. Zero-Rated / Exported-Service Handling

**Current behaviour:** `services/tax_rate_config.py` treats `INTL`
(non-Canadian buyer/seller) as 0% under ETA Schedule VI Part V §7
(zero-rated exported service).

**Questions:**
1. Under §7 an exported service is zero-rated only if the recipient is
   OUTSIDE Canada AND the recipient is NOT registered for GST/HST
   AND the service is performed for use OUTSIDE Canada. Current code
   only checks the first condition (province is INTL). Confirm this
   simplification is legally acceptable.
2. Buyer in USA using a Canadian seller's stripe checkout —
   destination-charge model requires the tax to follow the seller
   (Canadian), not the buyer (US). Current code follows the buyer →
   zero-rated. Confirm which is correct.

---

## 13. Invoice Labels / Registration Numbers

**Current behaviour** (`services/invoice_generator.py`):
- Invoices ALWAYS show `GST/TPS #` and `QST #` regardless of buyer
  province.
- No `HST #` label ever shown, even for ON/NS/NB/NL/PE buyers.

**Questions:**
1. Are separate labels required for HST provinces on the invoice PDF
   (e.g., `HST # 12345 RT 0001` for ON)? CRA Form invoice
   requirements — §169 for input tax credits.
2. Is BidVex's QST number (`1233530880TQ0001`) valid on invoices
   issued to non-QC buyers?
3. `BUSINESS_NUMBER` shown alongside GST/QST on all footers — is
   that CRA-compliant for HST invoices?

---

## 14. Tax on Stripe Processing Gross-Up

**Current behaviour:** Buyer pays a Stripe processing "gross-up"
recovery via `services/payment_cost_engine.py`. Tax IS computed on
(BP + processing_recovery) at the buyer's province — the recovery
amount itself becomes taxable.

**Questions:**
1. Is the Stripe gross-up recovery legally a "service fee" (BidVex
   supplies payment processing to buyer, taxable) or a
   "reimbursement of cost" (non-taxable pass-through)?
2. If it is a service fee, is the current taxation at buyer prov
   correct? Confirm the recipient identification.

---

## 15. Registration Status Fallbacks — silent-open defect

**Current defect** (see P6 audit §3b):
- `seller_is_business` defaults to `False` when the field is missing.
- `is_tax_registered` defaults to `False`.
- This silently classifies unknown-status sellers as "private, no
  hammer tax" — a POTENTIAL UNDER-COLLECTION defect if the seller is
  actually business-registered but the DB flag is missing.

**Questions:**
1. Is silently defaulting to "not tax-registered" acceptable, or does
   CRA require BidVex to HALT the transaction until registration
   status is confirmed?
2. What is the KYC / verification standard BidVex must meet before
   trusting the DB flag? (Related: is a missing flag a compliance
   incident that requires notification to CRA?)

---

## 16. Tax Rate Effective Date Handling

**Current behaviour:** `services/tax_rate_config.py::update_tax_rate`
snapshots the OLD rate into `db.tax_rate_config_history` on every
update. But **invoices generated AFTER a rate change still use the
NEW rate**, even for auctions that ended BEFORE the change.

**Questions:**
1. Should an invoice for an auction ending on 2026-03-01 use the tax
   rate in effect on 2026-03-01 (accrual) OR the rate at invoice
   issuance (cash basis)? CRA policy for accrual accounting.
2. If accrual: every invoice must stamp the `effective_from` of the
   rate used, and admin edits to the rate must never mutate historical
   invoices. Confirm the design.

---

## 17. Currency and Exchange Rate

**Current behaviour:** All auctions locked to CAD. `INTL` buyer
sees CAD invoice, zero-rated for GST/HST/QST.

**Questions:**
1. If a Canadian buyer holds a foreign-currency card, is the CAD
   amount charged the taxable base, or is the actual settled
   currency at Stripe's FX rate the base? Currently code uses CAD.
2. Any Section 159 (foreign currency conversion) implications?

---

## 18. Retroactive Correction of Under-/Over-Collection

**Current behaviour:** BidVex has no admin flow to reissue an
invoice with corrected tax if a rate defect is found.

**Questions:**
1. If Legal Review §11 confirms the broker QST-or-zero was an
   under-collection defect, what is the correct remediation path
   (customer-facing invoice reissue + collection of shortfall,
   BidVex-absorbs, do-nothing)?
2. Statute of limitations — how far back must BidVex go to correct?
3. Are historical over-collections (§3a QC-default fallbacks)
   refundable to the affected buyers/sellers, or does BidVex remit
   them to CRA regardless?

---

## Next Steps
**No code changes.** File to be reviewed with a Canadian tax
practitioner. Every question above needs a WRITTEN legal opinion
before the P6.2 consolidation may implement its tax coverage.
