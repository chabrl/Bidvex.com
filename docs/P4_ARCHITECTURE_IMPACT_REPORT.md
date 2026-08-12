# BidVex Seller-Controlled Payment-Method Architecture Impact Report
### iter482 Phase P4 — READ-ONLY audit · No code modified · Awaiting approval

Prepared: Feb 12, 2026
Status: **PROPOSAL — awaiting user sign-off before ANY code change**
Guardrails honoured: DO NOT DEPLOY · L-1 CLOSED · Partner 3% unchanged · No production data touched · No live Stripe charges · No refunds executed

---

## §1  Current Stripe Architecture (as of iter482 P3.1)

### 1.1 What exists today
| Flow | Entry point | Stripe primitive | Charge topology |
|------|-------------|------------------|-----------------|
| Standard auction win (individual/enterprise seller) | `routes/payments.py::/checkout/auction` → `services/stripe_connect_service.create_destination_charge` | `checkout.Session` (mode=payment) | Destination charge: `application_fee_amount` + `transfer_data.destination = seller_connect_acct` |
| Partner auction win | Same route, `is_partner_listing=True` branch | `checkout.Session` | Destination charge + `on_behalf_of=partner_acct` (Model A₁) — Stripe rail borne by Partner |
| Vehicle fees (BidVex-only rail) | `services/vehicle_payment.py` + `stripe_connect_service.create_vehicle_payment_session` | `checkout.Session` | Direct charge to BidVex; hammer paid offline by Bank Draft |
| Storage buyer BP charge | `services/storage_deposit_service` + settlement path | `PaymentIntent` off-session on saved PM | Direct charge |
| Bid pre-authorization hold | `services/bid_authorization_service.py` | **`PaymentIntent(capture_method="manual", confirm=True, off_session=True)`** | Direct hold on buyer's saved card, then `PaymentIntent.capture()` |
| Broker deposit | `services/broker_deposit_service.py` | **`PaymentIntent(capture_method="manual")`** | Same manual-capture pattern |
| Storage deposit | `services/storage_deposit_service.py` | `PaymentIntent` off-session | Direct charge |
| Escrow hold-until-pickup | `services/escrow_service.py` | (uses upstream PI; no separate primitive) | Funds sit on platform until pickup code entered, then `transfer` to seller |
| Subscription (annual Premium/VIP) | `services/subscription_service.py` | `checkout.Session` (mode=subscription) → `Subscription.create` | Recurring; direct to BidVex |
| Dealer annual subscription | `services/dealer_subscription_service.py` | `Subscription.create` with LAUNCH50 coupon | Direct to BidVex |
| Auction settlement re-charge | **`services/auction_settlement.py::_charge_card`** | **`PaymentIntent(confirm=True, off_session=True)` on saved payment_method** | Direct or destination — full support for both |
| Refund | `services/refund_engine.py` | `Refund.create(refund_application_fee=True, reverse_transfer=True)` | Model A₁ compatible |

### 1.2 Payment-method configuration today
- `models/storage_auction.py` already declares `PAYMENT_METHODS = ["stripe", "cash", "etransfer"]` and requires the storage-facility seller to pick ONE per auction (`payment_method: str`).
- `models/auction_models.py` line 195/279/355 has `payment_method: str = "stripe"` — **single value only**, not a list.
- `routes/listings.py` line 282–290 validates that a partner seller who picks non-stripe has a `partner_stripe_payment_method_id` saved (so BidVex can still bill them).
- `db.payment_methods` collection: 1:1 buyer → Stripe `pm_xxx`. `db.users.stripe_customer_id` holds the customer id.
- **There is NO `accepted_payment_methods` list field today** — sellers can only pick one method. This is the core gap the new spec closes.

### 1.3 Legal gate today (P3.1 canonical)
- `services/payment_cost_engine.py::_LEGAL_GATE_MATRIX`
  - `BUYER × every province` = `REQUIRES_TAX_LEGAL_REVIEW` → buyer-facing surcharge = $0
  - `PARTNER × every province` = `CLEARED` (B2B recovery permitted)
  - `PLATFORM` = `CLEARED` (self-absorb OK)
- `payment_processing.amount_cents = 0` on every buyer-facing snapshot.
- **This must stay CLOSED** for the new Stripe-selected flow's UI too until legal review clears it.

### 1.4 Cent-exact reconciliation status (P3.1 baseline)
- 196/196 iter482 unit tests + 40/40 live-API smoke = clean.
- Path A (`calculate_fee`) and Path B (`calculate_general_checkout`) produce identical `buyer_total_charged` for all Individual scenarios.
- Historical $7.64 phantom bug is gone: buyer_total = $7.28 exact.

---

## §2  Proposed Payment-Method Architecture

### 2.1 Data model additions
```python
# models/auction_models.py — new canonical field on EVERY auction model
accepted_payment_methods: List[str] = Field(default_factory=list)
# ALLOWED = {"stripe", "cash", "etransfer", "cheque"}
# Constraint: len(accepted_payment_methods) >= 1
# Snapshot: locked at first bid; immutable thereafter.

# db.listings / db.multi_item_listings / db.vehicle_listings / db.storage_auctions
# Field added to each.  Backfill script: default to ["stripe"] for pre-P4 rows.
```

### 2.2 Buyer selection field on transaction
```python
# db.transactions / db.auction_settlements
buyer_selected_payment_method: str  # one of accepted_payment_methods
buyer_payment_terms_ack_at: datetime  # explicit consent timestamp
buyer_payment_terms_ack_totals: {     # exact amounts the buyer agreed to (integer cents)
   "hammer_cents": int,
   "buyer_premium_cents": int,
   "buyer_tax_cents": int,
   "payment_processing_cents": int,   # $0 until L-1 opens
   "total_cents": int,
}
```

### 2.3 New auction payment state machine (see §14)

### 2.4 Backend module boundaries
- **NEW** `services/seller_payment_methods.py` — validates the list, snapshots it, gates seller-side edits.
- **NEW** `services/buyer_payment_selection.py` — buyer picks method, records terms ack, kicks Stripe flow if `stripe`.
- **REUSE** `services/payment_cost_engine.py` — no changes; already fail-closed correctly.
- **REUSE** `services/auction_settlement.py::_charge_card` — already implements PI + saved PM + off-session capture.
- **REUSE** `services/bid_authorization_service.py` PaymentIntent(manual capture) pattern — proven, ships to production for bid holds.

### 2.5 Stripe primitive per role
| Role | New primitive | Rationale |
|------|---------------|-----------|
| Buyer authorizes at auction win, seller settles later | **PaymentIntent(capture_method="manual", confirm=True, off_session=True)** on the buyer's saved PaymentMethod | Bid-hold pattern; PI is HELD until seller clicks SETTLE; capture window = 7 days (see §5) |
| Fallback 48h auto-capture | **`PaymentIntent.capture(pi_id)`** with idempotency key | Same PI, no new authorization needed |
| Fallback expires before 48h passes (edge) | New PI created via `_charge_card` with `off_session=True` | Requires prior consent-record proof |
| Partner-side B2B billing (recovery of 3% + Stripe rail) | Separate PI/Invoice against Partner (post-auction) | Model A₁ Partner remains merchant of record; BidVex bills Partner |

**The DECISION**: use **PaymentIntent(manual capture)** at auction end. This matches the existing bid-hold code path exactly, requires ZERO new integrations, and gives us a 7-day window.

---

## §3  Manual-Capture Feasibility

### 3.1 Feasibility verdict — **HIGHLY FEASIBLE** ✅
BidVex is already running `PaymentIntent(capture_method="manual")` in production via `bid_authorization_service.py` (bid holds) and `broker_deposit_service.py`. The primitive is proven in this stack.

### 3.2 What it gives us
- Card is authorized (funds reserved on issuer's side) but not charged.
- BidVex holds the authorization for up to **7 days** (Stripe default; up to 25 days on some card networks with `capture_method=manual` + optional `capture_method=automatic_async` — needs case-by-case verification per network).
- On `PaymentIntent.capture(pi_id)`, funds are moved from the reservation into the charge. This is the SETTLE PAYMENT click.
- No new customer authentication in most cases (SCA already handled at authorization).

### 3.3 What it costs
- Stripe processing fee (2.9% + $0.30 CAD domestic; 3.9% + $0.30 international) applies AT CAPTURE, not at authorization.
- Auth-only holds may still show a temporary reduction in the buyer's available balance.

### 3.4 What it requires
- Stored buyer `Customer` + `PaymentMethod` (BidVex already has these via `stripe_customer_service.py`).
- Explicit off-session consent recorded (Stripe Setup: SCA + mandate). BidVex must persist consent evidence per Strong Customer Authentication rules.

---

## §4  Save-Payment-Method / Off-Session Feasibility

### 4.1 Feasibility verdict — **FEASIBLE, ALREADY IMPLEMENTED** ✅
`services/auction_settlement.py::_charge_card` and `services/bid_authorization_service.py` already build PaymentIntents with `off_session=True` using stored `payment_method_id`. Refund engine already handles reversal.

### 4.2 SetupIntent alternative (if we chose to)
| SetupIntent path | PaymentIntent-manual path (**RECOMMENDED**) |
|---|---|
| No funds held at auction end | Funds reserved on card at auction end |
| Buyer's balance untouched until capture | Buyer sees hold on statement (slight friction) |
| Seller may find zero funds available at settle (buyer spent) | Auth guarantees settle succeeds up to auth amount |
| Requires future PI creation → new SCA challenge possible | Capture uses existing auth → no new SCA |

**Recommendation: PaymentIntent-manual is superior for THIS use case** because BidVex must guarantee the seller will get paid when they click SETTLE.

### 4.3 Consent evidence to store (for auto-capture fallback)
```
mandate_id: str   # from PaymentIntent.mandate on off-session PI
customer_acceptance: {"type": "online", "online": {...}}
authorized_amount_cents: int
authorization_created_at: datetime
authorization_expires_at: datetime  # 7 days from creation
consent_ip_address: str
consent_user_agent: str
```

---

## §5  Authorization-Window Limitations (**CRITICAL**)

### 5.1 Stripe capture window rules (verified against Stripe docs)
- **Default: 7 calendar days** for `capture_method="manual"` PIs.
- Amex: 7 days (identical).
- Debit cards: often shorter (2 days on some networks).
- **After the window**, calling `.capture()` returns HTTP 400 with `payment_intent_authorization_expired`. The auth releases automatically.

### 5.2 The 48-hour seller-settle deadline is SAFE within the 7-day auth window ✅
Fallback auto-capture at 48h leaves 5 days of slack for retries, disputes, and manual admin intervention.

### 5.3 What we MUST design for
1. **Explicit expiration state**: `PAYMENT_AUTHORIZATION_EXPIRED` in the state machine.
2. **Pre-capture recheck**: at the SETTLE PAYMENT click, backend calls `PaymentIntent.retrieve(pi_id)`. If `status != "requires_capture"`, refuse to charge and surface the correct state.
3. **Recovery via new PI**: if auth expired, use `_charge_card` off-session with the saved PM (needs the recorded consent from §4.3) OR ask buyer to re-authorize.
4. **Idempotency on capture**: every capture call carries an idempotency key like `capture-{pi_id}` so double-clicks and duplicate webhooks converge.

### 5.4 Automatic-async captures (Stripe experimental)
Stripe now supports `capture_method="automatic_async"` for some flows, which can extend the effective window to ~25 days. **Not adopted** in this proposal — the 7-day default with explicit expiration handling is cleaner and matches BidVex's existing bid-hold pattern.

---

## §6  Stripe Fee Incidence — Comprehensive Mapping

### 6.1 The universal rule (per user directive)
> "BidVex must NOT silently absorb Stripe processing costs. Whenever a payer chooses Stripe/card, the applicable Stripe processing cost must ultimately be borne by that payer, subject to applicable law, Stripe rules, and the applicable legal gate."

### 6.2 Fee incidence matrix — every flow, post-P4
| Flow | Payer | Stripe rail bears? | Recovery permitted? | How recovery works |
|------|-------|--------------------|---------------------|--------------------|
| **Individual/Enterprise auction — buyer pays via card** | Buyer | Platform (destination-charge from platform account) | **Gated closed** (L-1 REQUIRES_TAX_LEGAL_REVIEW). When opened, buyer bears via `payment_processing` add-on line. | See §6.3 |
| **Individual/Enterprise auction — buyer pays cash/etransfer/cheque** | Buyer (offline) | Nobody — no Stripe rail | N/A | No processing charge at all |
| **Partner auction — buyer pays via card** | Buyer | Partner (Model A₁: `on_behalf_of=partner_acct`) | Partner bears rail; BidVex bills Partner for 3% platform fee separately (P4 phase). | Partner Connect balance deducted at settlement |
| **Vehicle fees — buyer pays via card** | Buyer | Platform (direct charge to BidVex) | Buyer bears via gross-up (currently) — **must be rewired to `payment_cost_engine`** as part of P4. Fail-closed until L-1 opens. | Same as Individual buyer flow |
| **Storage BP — buyer pays via card** | Buyer | Platform | Same as Vehicle | Same |
| **Deposits (bid, storage, broker)** | Buyer/Bidder | Platform (auth-only; captured only on default) | Buyer bears at capture (deposit is B2C penalty). Legal review required. | Captured PI on default event |
| **Escrow release transfer** | (BidVex→seller) | Not a Stripe charge — internal Transfer | N/A | Zero Stripe fee for Transfers between BidVex ↔ Connect |
| **Refunds** | (BidVex→buyer) | Platform absorbs Stripe rail loss (Stripe does NOT refund fees) | N/A — no counter-recovery | Documented cost of doing business (Stripe policy) |
| **Chargebacks/disputes** | Platform (buyer's issuer) | Platform loses $15 CAD dispute fee + refunded amount | N/A | Absorbed |
| **Consumer subscriptions (Premium / VIP)** | Buyer subscriber | Platform (direct charge) | Buyer bears via gross-up in subscription price OR add-on line — needs L-2 legal review | Recurring PI; needs `payment_cost_engine` snapshot on `subscription_invoices` |
| **Partner annual subscription** | Partner | Platform (or Partner Connect if we route via on_behalf_of) | B2B CLEARED — Partner bears rail transparently | Add processing line to Partner invoice |
| **Dealer annual subscription** | Dealer | Platform | B2B — needs L-3 legal review | Same shape |
| **Marketing payments (feature/highlight)** | Buyer/Seller | Platform | Needs L-4 legal review | Same shape |

### 6.3 Buyer-side Stripe recovery on card flows (post-legal-open architecture)
When L-1 opens, the recovery amount MUST come from `payment_cost_engine.estimate(payer_role=BUYER, jurisdiction=X)`:
- The engine returns `estimated_cents = int(amount × pct) + fixed_cents` for the buyer's `(method, currency, card_class)` cell.
- The recovery is ADDED to `buyer_total` as a SEPARATE line (never rolled into BP).
- Card-class detection (domestic vs international) happens post-3DS via `stripe.PaymentMethod.retrieve()`; the initial estimate uses `domestic`, and the final capture uses the ACTUAL rate from `BalanceTransaction.fee_details`.

### 6.4 Actual-vs-estimated reconciliation
`payment_cost_engine.lock_actual(...)` is already defined for this — it takes the Stripe `BalanceTransaction.fee_details[].amount` where `type == "stripe_fee"` and locks the actual cost onto the receipt post-settlement. Any diff between estimate and actual goes to a "cost adjustment" ledger row (BidVex absorbs the last-cent variance; the buyer is never surprise-billed).

---

## §7  Connect Implications

### 7.1 What stays the same
- Every seller with a Connect account: unchanged. `stripe_connect_account_id` remains the destination for `transfer_data.destination`.
- Partner path Model A₁ (`on_behalf_of` + destination charge) unchanged.

### 7.2 What changes
- **Buyer's `PaymentMethod` must be attachable off-session** to enable manual-capture on card. `stripe_customer_service.attach_payment_method(...)` already handles this.
- **Partner receipts** now need a `stripe_processing_charge_borne_by_partner` line — this is the Gate 2 finding formalized: Partner's Connect balance is debited by Stripe at capture; BidVex must persist that this cost is borne by Partner, not platform.
- **Direct charges** (non-Connect flows like Vehicle fees) require the platform's own Stripe account to hold sufficient funds if buyer disputes; unchanged.

### 7.3 Connect account requirements
- **Buyer**: standard `Customer` + `PaymentMethod`. No Connect account needed.
- **Individual seller**: `stripe_connect_account_id` (Standard or Express) — unchanged.
- **Partner**: `stripe_connect_account_id` (Standard, so they can be invoiced for the 3% platform fee) — unchanged.
- **Storage/Vehicle/Broker**: unchanged (unique flows already documented in Gate 2 audit).

---

## §8  Refund Implications

### 8.1 Current refund engine
`services/refund_engine.py` handles:
- Full refund with `refund_application_fee=True` + `reverse_transfer=True` (Model A₁).
- Partial refund (proportional application-fee reversal).
- Idempotency via `refund_{payment_intent_id}_{amount_cents}`.

### 8.2 New scenarios introduced by seller-controlled methods
| Scenario | Refund behavior |
|---|---|
| Buyer paid cash/etransfer/cheque, seller wants to refund | No Stripe involvement. Manual reconciliation in `db.transactions` + admin-issued refund voucher. |
| Buyer's card was authorized (manual capture) but seller cancels BEFORE capture | Call `PaymentIntent.cancel(pi_id)`. No fees charged. |
| Buyer's card was captured, refund AFTER | Existing engine handles this. Stripe does NOT refund the processing fee (documented BidVex loss). |
| Fallback auto-capture happened at 48h + refund happens later | Same as above — full refund minus Stripe rail. |
| Authorization expired, no capture, buyer wants refund | Nothing to refund — no capture happened. Cancel PI (idempotent). |
| Partial refund with recovery-fee borne by buyer (post-L-1) | Recovery-fee prorated with hammer; MUST NOT be refunded 1:1 with buyer premium unless legal review confirms. |

### 8.3 Refund idempotency guarantees
- Every refund call uses `idempotency_key = "refund-{pi_id}-{amount_cents}"`.
- `db.refunds` gains a unique index on `(payment_intent_id, amount_cents, purpose)`.

---

## §9  Dispute (Chargeback) Implications

### 9.1 Dispute event → BidVex flow
1. Stripe webhook `charge.dispute.created` arrives.
2. Auction transaction is flagged `PAYMENT_DISPUTED`.
3. Escrow (if applicable) is FROZEN — no seller payout while dispute is open.
4. Admin gets an alert with the buyer's chargeback reason.
5. BidVex uploads evidence (auction terms, buyer_payment_terms_ack, IP/UA, delivery/pickup evidence) via `stripe.Dispute.update`.
6. Stripe resolves: `charge.dispute.closed` → `status = won | lost | warning_closed`.
7. **`dispute.lost`**: chargeback amount + $15 dispute fee debited from platform. Seller payout permanently reversed. `db.disputes` records the loss.

### 9.2 New disputes-related fields
```python
# db.transactions
dispute_status: Optional[str]  # None | "under_review" | "won" | "lost"
dispute_amount_cents: int = 0
dispute_evidence_bundle_id: Optional[str]
```

### 9.3 Chargeback protection considerations
- The `buyer_payment_terms_ack_totals` field (§2.2) is CRITICAL evidence — proves the buyer agreed to the exact amount.
- The `payment_processing.amount_cents` fail-closed to $0 pre-L-1 means BidVex can never be accused of surcharge fraud during this phase.

---

## §10  Tax / Legal Implications

### 10.1 L-1 through L-9 gates (unchanged from P3)
All buyer-facing Stripe surcharge is fail-closed to $0 until legal review clears. Post-P4 this doesn't change — the seller can enable Stripe as an accepted method, but the recovery amount stays $0 until L-1 opens.

### 10.2 Tax on offline methods (cash/etransfer/cheque)
- No Stripe rail = no processing charge to recover.
- Tax on BP + hammer_tax + sc_tax follow the same CRA Place-of-Supply rules as P3.1.
- Buyer_total = hammer + BP + hammer_tax (if seller registered) + bp_tax.
- Seller receives = hammer − SC − sc_tax [+ hammer_tax passthrough].
- BidVex's fee income is unchanged whether buyer paid cash or card.

### 10.3 Provincial variation
- QC: Combined 14.975% (GST 5% + QST 9.975%), per-line rounding.
- ON: HST 13%, per-line.
- Other provinces: table-driven via `services/tax_rate_config.py`.
- Cross-province: recipient rule (buyer's province for BP, seller's for SC).

### 10.4 What the seller sees on their statement
Independent of payment method, the seller receives `hammer − SC − sc_tax` (+ hammer_tax if passthrough). This is a POLICY change from pre-P3.1 (where seller received `hammer − SC` and buyer bore sc_tax) — carried through P4 unchanged.

### 10.5 Legal review items generated by P4
| # | Item | Blocks |
|---|------|--------|
| L-1 | Buyer-side Stripe surcharge disclosure + recovery legality | Buyer card path recovery > $0 |
| L-10 (new) | Off-session mandate storage retention (privacy) | Auto-capture flow |
| L-11 (new) | Seller-controlled payment-method disclosure copy | Legal boilerplate on listing page |
| L-12 (new) | Cash/e-transfer AML compliance (FINTRAC over $10,000 CAD threshold) | Large-value non-card auctions |

---

## §11  Database Changes

### 11.1 New collections
| Collection | Purpose | Indexes |
|---|---|---|
| `db.buyer_payment_authorizations` | Store PI hold state, mandate, consent evidence | `(pi_id, unique)`, `(auction_id, buyer_id)`, `(authorization_expires_at)` for the auto-capture cron |
| `db.seller_settle_events` | Idempotency log for SETTLE PAYMENT clicks | `(auction_id, event_id, unique)` |
| `db.payment_state_transitions` | Audit trail for state machine | `(auction_id, created_at)` |

### 11.2 Mutated collections
| Collection | New fields |
|---|---|
| `db.listings` / `db.multi_item_listings` / `db.vehicle_listings` / `db.storage_auctions` | `accepted_payment_methods: List[str]` (immutable-snapshot on first bid) |
| `db.transactions` | `buyer_selected_payment_method`, `buyer_payment_terms_ack_at`, `buyer_payment_terms_ack_totals`, `payment_authorization_id`, `payment_state`, `authorization_expires_at`, `settle_deadline_at` |
| `db.receipts` | `stripe_actual_fee_cents` (locked at post-settlement) |
| `db.pending_payments` | `capture_method` (`manual` / `automatic`) |

### 11.3 Migration plan
- **NO historical row is rewritten.**
- Backfill script: for existing listings, `accepted_payment_methods = ["stripe"]` default (matches historical behavior).
- Existing `payment_method` singleton field stays present + treated as `buyer_selected_payment_method` for legacy rows.
- New listings created post-P4 write both the array + the buyer's chosen singleton.

### 11.4 Immutability rules
- Once first bid lands → `accepted_payment_methods` becomes IMMUTABLE (locked on `listings.accepted_payment_methods_snapshot`).
- Once buyer selects → `buyer_selected_payment_method` becomes IMMUTABLE.
- Terms ack timestamp + totals: IMMUTABLE (never overwritten).

---

## §12  Frontend Changes

### 12.1 Listing creation (seller)
- **New multi-select** on `CreateListingPage.js`, `CreateMultiItemPage.js`, `CreateVehicleAuctionPage.js`, `StorageFacility/CreateAuctionPage.jsx`:
  ```
  ☑ Card (Stripe)   ☑ Cash   ☑ E-transfer   ☑ Cheque
  ```
- Validation: at least ONE must be checked. Seller card-eligibility not gated (any seller can accept card).
- data-testid: `accepted-payment-methods-checkbox-stripe`, `-cash`, `-etransfer`, `-cheque`.
- Backend contract: `accepted_payment_methods: string[]`.

### 12.2 Buyer selection at checkout
- **New `CheckoutPaymentSelector` component** in `pages/CheckoutPage.js`:
  ```
  Payment method (choose one):
   ○ Card
   ○ Cash — pay seller on pickup
   ○ E-Transfer — email address will be provided
   ○ Cheque — mailing address will be provided
  ```
- Only options present in `listing.accepted_payment_methods` render as enabled.
- data-testid: `buyer-payment-method-radio-stripe|cash|etransfer|cheque`.
- Below the radio: full amount breakdown using existing `PriceBreakdown` component. The `payment_processing` row respects `payment_processing.amount_cents` (still 0 pre-L-1).
- Explicit consent checkbox: `☐ I agree to pay the total amount shown above via [selected method]` (data-testid: `buyer-payment-terms-ack-checkbox`).
- SUBMIT button disabled until (a) method selected + (b) consent checked.

### 12.3 Seller dashboard SETTLE PAYMENT
- **New `PaymentStatusCard`** on `pages/SellerDashboard.js` per auction:
  ```
  Payment Method:  Card
  Status:         🟡 Card secured — awaiting settle
  Authorization:  Expires in 4 days 12 hours
  Amount:         $126.48
  
  [SETTLE PAYMENT]  [ Refund Instead ]
  ```
- Button click → `POST /api/payments/settle/{auction_id}` (backend recomputes NOTHING from mutable values; uses the immutable `buyer_payment_terms_ack_totals`).
- data-testid: `settle-payment-btn-{auction_id}`, `payment-status-badge-{auction_id}`, `authorization-expires-at-{auction_id}`.

### 12.4 Buyer receipt (post-settle)
- Existing `MyReceiptPage.jsx` updated to render `stripe_actual_fee_cents` when > 0 (post-L-1 only).

---

## §13  Backend Changes

### 13.1 New endpoints
| Endpoint | Purpose | Auth |
|---|---|---|
| `POST /api/checkout/select-payment-method` | Buyer picks method + acknowledges terms; if stripe, creates PI(manual capture) | Buyer |
| `POST /api/payments/settle/{auction_id}` | Seller captures PI (idempotent) | Seller/Admin |
| `POST /api/payments/mark-received/{auction_id}` | Seller confirms cash/etransfer/cheque received; marks PAID (no Stripe call) | Seller |
| `GET /api/payments/authorization-status/{auction_id}` | Poll authorization state | Both parties + admin |
| `POST /api/payments/cancel-authorization/{auction_id}` | Cancel PI before capture (dispute-safe) | Admin or seller pre-settle |

### 13.2 Modified endpoints
- `POST /api/listings` (and multi-item, vehicle, storage variants): accept `accepted_payment_methods: string[]`.
- `POST /api/payments/checkout` (existing): now branches by `buyer_selected_payment_method`:
  - `stripe` → PaymentIntent(manual capture)
  - `cash | etransfer | cheque` → immediate transaction row, no Stripe call
- `PATCH /api/listings/{id}`: reject any change to `accepted_payment_methods` if `first_bid_placed_at` is set.

### 13.3 New cron/background jobs
| Job | Trigger | Action |
|---|---|---|
| Auto-capture 48h | Cron every 5 min | For each auction where `settle_deadline_at < now()` AND `payment_state == "AUTHORIZATION_HELD"`, run capture; log to `db.payment_state_transitions`. |
| Authorization expiring alert | Cron every 1 hr | For each auction where `authorization_expires_at - now() < 24h` AND state == "AUTHORIZATION_HELD", email seller + buyer. |
| Authorization expired sweep | Cron every 1 hr | For each auction where `authorization_expires_at < now()` AND state == "AUTHORIZATION_HELD", transition to `PAYMENT_AUTHORIZATION_EXPIRED`; attempt off-session re-charge via `_charge_card` if consent evidence present. |

### 13.4 Webhook handlers
| Stripe event | Handler action |
|---|---|
| `payment_intent.amount_capturable_updated` | Log authorization amount confirmed; no state change |
| `payment_intent.canceled` | Transition to `PAYMENT_CANCELED` |
| `payment_intent.succeeded` (after capture) | Transition to `PAID`; issue receipt; trigger escrow release |
| `payment_intent.payment_failed` (during off-session recharge) | Transition to `PAYMENT_FAILED`; email both parties |
| `charge.dispute.created` | Transition to `DISPUTED`; freeze escrow |
| `charge.refunded` | Transition to `REFUNDED` (or `PARTIALLY_REFUNDED`) |

### 13.5 Idempotency
- Every state-change endpoint has `Idempotency-Key` header support.
- Duplicate webhooks: `db.stripe_webhook_events` gains a unique index on `(event_id)` — replay = no-op.
- Duplicate SETTLE clicks: `db.seller_settle_events` unique on `(auction_id, seller_id, session_id)`.

---

## §14  Exact State Machine

```
                      ┌──────────────────┐
                      │  PAYMENT_PENDING │  ← auction just ended, buyer hasn't selected method
                      └────────┬─────────┘
                               │  buyer selects method + acks terms
                     ┌─────────┴──────────┐
                     │                    │
                stripe                 cash/etransfer/cheque
                     │                    │
                     ▼                    ▼
    ┌───────────────────────────┐  ┌──────────────────────────┐
    │ AUTHORIZATION_HELD        │  │ AWAITING_OFFLINE_PAYMENT │
    │ (PI status=requires_      │  │                          │
    │  capture, expires in 7d)  │  │                          │
    └─────────┬─────┬───────────┘  └────────┬─────────────────┘
              │     │                       │ seller confirms received
              │     │                       ▼
              │     │              ┌────────────────┐
              │     │              │      PAID      │
              │     │              └────────────────┘
              │     │
              │     │  Seller clicks SETTLE (or 48h auto)
              │     ▼
              │  ┌─────────────┐  capture fails
              │  │  CAPTURING  │────────────────┐
              │  └──────┬──────┘                │
              │         │ capture succeeds      ▼
              │         ▼                ┌───────────────────┐
              │  ┌────────────┐          │ PAYMENT_FAILED    │
              │  │    PAID    │          └────────┬──────────┘
              │  └──────┬─────┘                   │
              │         │                         │ retry (once)
              │         │                         └──────► CAPTURING
              │
              │ 7-day authorization window expires (no capture)
              ▼
    ┌──────────────────────────────┐
    │ PAYMENT_AUTHORIZATION_EXPIRED │
    └────────────┬─────────────────┘
                 │ (a) consent evidence + saved PM → attempt off-session PI recreate
                 │ (b) no consent → PAYMENT_DEFAULT
                 ▼
       ┌─────────────────────┐   attempt fails
       │  OFFSESSION_RETRY   │───────────────► PAYMENT_DEFAULT
       └──────────┬──────────┘
                  │ succeeds
                  ▼
             ┌────────┐
             │  PAID  │
             └────────┘

Terminal states: PAID, REFUNDED, PARTIALLY_REFUNDED, PAYMENT_FAILED,
                 PAYMENT_DEFAULT, PAYMENT_CANCELED, DISPUTED

Transitions guarded by:
  * Idempotency key on every state change
  * Immutable buyer_payment_terms_ack_totals for capture amount
  * Server-time comparison for expiration windows
  * Webhook signature verification (Stripe HMAC)
```

State machine invariants:
1. `PAID` is reached ONLY via successful capture OR seller "mark received" (offline).
2. `AUTHORIZATION_HELD → PAID` amount MUST equal `buyer_payment_terms_ack_totals.total_cents`.
3. No state transition creates a Stripe charge greater than the acknowledged total.
4. Every terminal state is idempotent — re-hits are 200-noops.

---

## §15  Test Plan (blueprint — pytest + live-API + Stripe TEST-mode)

### 15.1 Golden-matrix expansion
Extend the 196-test iter482 suite with **P4 scenarios**:

```
For each seller_type ∈ {individual, enterprise, partner, storage_facility, vehicle_dealer}:
  For each hammer ∈ {$5, $100, $1000, $10000}:
    For each quantity ∈ {1, 2, 10}:
      For each accepted_payment_methods combo ∈ {full 4, stripe-only, cash-only,
                                                 cash+etransfer, stripe+cash, ...}:
        For each buyer_selected ∈ accepted:
          Assert: buyer_total_cents cent-exact, state=PAYMENT_PENDING → …
```
Estimated matrix size: 5 × 4 × 3 × 15 × ~2 ≈ **1800 unit assertions**. Trimmed to ~500 by removing redundant combos.

### 15.2 Live Stripe TEST-mode integration tests (new file `tests/live_test_iter482_p4_stripe_manual_capture.py`)
| Test | Steps | Success criteria |
|---|---|---|
| T1: happy card path | authorize → seller settle → capture → PAID | PI.status=succeeded, receipt.buyer_total = ack_total, escrow.pickup_code present |
| T2: authorize → cancel before capture | authorize → cancel | PI.status=canceled, no fee, state=PAYMENT_CANCELED |
| T3: authorize → 48h auto-capture | authorize → freeze time +48h → cron capture | PI.status=succeeded, state=PAID |
| T4: authorization expires → offsession retry succeeds | authorize → +7d1s → cron → new PI off-session | New PI.status=succeeded, state=PAID |
| T5: authorization expires → offsession retry fails (declined) | authorize → +7d1s → cron → new PI declined | state=PAYMENT_DEFAULT |
| T6: duplicate settle click | authorize → settle × 2 | Second call returns 200 no-op, single Stripe capture |
| T7: duplicate webhook | authorize → settle → webhook.replay | State unchanged, no double-charge |
| T8: refund full | PAID → refund | state=REFUNDED, refund_id present, application_fee reversed |
| T9: refund partial | PAID → refund $10 | state=PARTIALLY_REFUNDED, prorated app_fee reversal |
| T10: dispute created | PAID → dispute.created webhook | state=DISPUTED, escrow FROZEN |
| T11: dispute lost | DISPUTED → dispute.closed(lost) | state=CHARGEBACK_LOST, seller payout reversed, $15 fee charged to platform |
| T12: buyer selects cash | select cash → seller marks received | state=PAID, no PI created, receipt generated |
| T13: buyer tries to select method not in accepted | select cheque when seller accepts only stripe | 400 `PAYMENT_METHOD_NOT_ACCEPTED` |
| T14: seller tries to remove stripe after bidder | patch accepted_payment_methods post-first-bid | 400 `PAYMENT_METHODS_LOCKED` |
| T15: on Partner listing, verify Model A₁ topology | Partner card path | PI.on_behalf_of=partner_acct, transfer_data.destination=partner, application_fee=platform_fee+fee_tax |

### 15.3 Cent-exact reconciliation tests (extend `test_iter482_p31_reconciliation.py`)
- Test `buyer_payment_terms_ack_totals.total_cents == PI.amount == stripe.charge.amount == receipt.buyer_total_cents` across every T1–T15 above.
- Actual Stripe fee reconciled via `BalanceTransaction.fee_details` — must match `payment_cost_engine.lock_actual()` output within $0 tolerance (last-cent variance absorbed by platform ledger row).

### 15.4 State-machine transition tests
- Each edge in §14 diagram has a positive test (transition happens) and a negative test (invalid source state returns 409).

### 15.5 Regression protection
Reuse existing 196-test iter482 suite unchanged. P4 adds ~50 unit + 15 live-Stripe + 20 state-machine tests = **~85 new tests**. Target: 281/281 PASS post-P4.

### 15.6 Frontend E2E tests (`testing_agent_v3_fork`)
| Test | Path |
|---|---|
| Seller creates listing accepting card+cash | Login testseller → CreateListingPage → check `stripe` + `cash` → submit → verify DB row |
| Buyer sees only enabled methods | Login testbuyer → view listing where seller accepted only cash → CheckoutPage shows cash radio only |
| Buyer explicit terms consent gate | Consent checkbox must be checked before SUBMIT enables |
| Seller settle → PAID transition | Login testseller → auction row → click SETTLE PAYMENT → status becomes PAID |
| Authorization expiring badge | Seed a listing with `authorization_expires_at = now+2h` → dashboard shows amber badge |

---

## Cross-Cutting Concerns

### Idempotency (universal)
- Every write: `Idempotency-Key` header propagated to Stripe.
- Every webhook: `event.id` unique in `db.stripe_webhook_events`.
- Every state transition: `db.payment_state_transitions` insert-only (append-only ledger).

### Observability
- New CloudWatch/Sentry metric per state transition.
- Dashboards: authorization-window-remaining, capture-success-rate, offline-payment-received-latency.

### Retention & Privacy
- Mandate + consent evidence: 7-year retention (CRA + Stripe requirement).
- Terms-ack IP/UA: retained until dispute window closes (120 days post-transaction).
- GDPR/Law-25: consent evidence exportable via existing data-request pipeline.

### Rollout guardrails
- Feature flag `SELLER_CONTROLLED_PAYMENT_METHODS`: OFF by default, admin-only initially.
- Backfill script pre-flight: verifies zero data corruption on 100 rows in preview before running against production.
- Blue-green cutover: legacy `payment_method` singleton kept in sync with `buyer_selected_payment_method` for 90 days.

---

## Summary — Decisions Requiring Sign-Off

| # | Decision | Recommendation |
|---|----------|----------------|
| D1 | Stripe primitive at auction end | **PaymentIntent(capture_method="manual", off_session=True)** on buyer's saved PM |
| D2 | Fallback primitive if authorization expires | **`_charge_card` off-session re-creation** with recorded consent evidence |
| D3 | Buyer-side surcharge recovery pre-L-1 | **$0 (unchanged, gated closed)** |
| D4 | Recovery UI copy pre-L-1 | Row hidden (as P3 established) |
| D5 | Seller edits `accepted_payment_methods` post-first-bid | **BLOCKED (immutable snapshot)** |
| D6 | Existing listings backfill | Default to `["stripe"]` (matches historical) |
| D7 | Buyer's terms ack storage | **Persist exact integer-cents totals + timestamp + IP + UA** |
| D8 | Duplicate-webhook safety | Unique index on `stripe_webhook_events.event_id` + idempotency-key on every downstream write |
| D9 | Rollout | Feature-flagged behind `SELLER_CONTROLLED_PAYMENT_METHODS`, preview-only until legal + finance sign-off |
| D10 | Test target | 281/281 tests (196 baseline + ~85 new) + 15 live Stripe TEST-mode integration tests |

**Awaiting user approval on D1–D10 before ANY code modification.**

--- 

## Guardrails Confirmation (repeat)

- **DO NOT DEPLOY** ✅ preview-only until approval
- **DO NOT touch production data** ✅ no data mutations in this audit
- **DO NOT charge real cards** ✅ all future testing routes through Stripe TEST keys
- **DO NOT execute live refunds** ✅ none in this scope
- **DO NOT change the 3% Partner platform fee** ✅ unchanged in every code path referenced
- **DO NOT enable buyer Stripe recovery before L-1** ✅ fail-closed remains authoritative
- **DO NOT create duplicate fee calculators** ✅ new code reuses `payment_cost_engine` + `calculate_general_checkout` + `_charge_card`
- **DO NOT hardcode Stripe fees** ✅ rates come from `payment_cost_engine._RATE_MATRIX`
- **DO NOT silently default seller payment methods** ✅ new field is required at listing creation; migration explicit
- **DO NOT silently default seller type** ✅ `seller_type_resolver.py` remains fail-closed
- **DO NOT recalculate historical invoices** ✅ backfill is additive; existing rows untouched
- **DO NOT change historical financial records** ✅ immutable
- All financial calculations use **integer cents** ✅ enforced by `_to_cents()`
- All Stripe fees reconcile against **`BalanceTransaction.fee_details`** via `payment_cost_engine.lock_actual()` ✅

**STOP.** Report complete. Standing by for approval to implement.
