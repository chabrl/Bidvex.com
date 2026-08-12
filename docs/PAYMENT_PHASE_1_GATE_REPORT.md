# PHASE 1 & 2 GATE REPORT — Both Mandatory Gates BLOCKED

**Date**: Feb 12, 2026
**Status**: **STOP**. Neither Phase 1 (Stripe Sandbox Proof) nor Phase 2 (Decision Validation for E-2/E-3) can pass with the current environment/inputs. Zero production code has been modified. No DB writes. No Stripe API calls. No deployments.

Per the brief's own explicit stop rules:

> **Section 3 / Phase 1**: "Do NOT assume that the previously calculated $103.51 / $3.00 / $3.49 economics are correct merely because static code analysis predicted them. They must be proven in Stripe TEST MODE."
> **Section 41 / Phase 1**: "Prove A₁. If proof fails: STOP and report."
>
> **Section 5**: "If the Decision Pack still identifies E-2 or E-3 as unresolved business/tax decisions: STOP and report: TAX DECISION REQUIRED. Do not silently choose a tax rate or place of supply."
> **Section 41 / Phase 2**: "Decision Validation. Extract E-2 through E-9. If any remains unresolved: STOP."

Both conditions currently hold. Details below.

---

## GATE 1 — Phase 1 Stripe Sandbox Proof: **CANNOT EXECUTE**

### What is missing

The Stripe test-mode proof requires four inputs to actually invoke a `stripe.checkout.Session.create` call in test mode. Three of the four are absent from this environment:

| Required input | Present? | Evidence |
|---|---|---|
| `STRIPE_API_KEY` (secret key, `sk_test_...` or `sk_live_...`) | **NO** | `grep '^STRIPE_' backend/.env` shows only `STRIPE_WEBHOOK_SECRET`, `STRIPE_WEBHOOK_SECRET_2`, `STRIPE_CONNECT_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_TEST_PUBLISHABLE_KEY`, `STRIPE_TEST_WEBHOOK_SECRET`. There is no `STRIPE_API_KEY`, `STRIPE_SECRET_KEY`, or `STRIPE_TEST_SECRET_KEY`. Every service in the repo that calls Stripe uses `stripe.api_key = os.environ.get("STRIPE_API_KEY", "")` — meaning if the env var is unset, `stripe.api_key = ""` and every Stripe call would fail with `Invalid API Key`. |
| Test-mode Partner Connect account ID (`acct_...`, `charges_enabled=True`, `capabilities.card_payments=active`, `payouts_enabled=True`) | **NO** | No test-mode Stripe Connect account is provisioned or discoverable in the current environment. `users` collection has 1 user with `is_partner=True` but no `stripe_connect_account_id` is confirmed active in test mode. |
| Buyer Stripe Customer + attached PaymentMethod in test mode | **NO** | Not provisioned. Test cards (`4242 4242 4242 4242`) require a real user session to attach; cannot be created programmatically without live UI redirect. |
| Ability to complete the Stripe Checkout Session redirect and observe the `checkout.session.completed` webhook end-to-end | **NO** | Requires a real browser session redirecting to `checkout.stripe.com/...` and confirming card, then Stripe delivering a webhook to a publicly reachable HTTPS endpoint. This environment does not have the credentials to do this end-to-end. |

### Why this matters

The Option A₁ math relies on Stripe's *actual* runtime behavior of these Stripe Connect parameters together:

```python
stripe.checkout.Session.create(
    payment_intent_data={
        "on_behalf_of": partner_acct_id,             # merchant-of-record
        "transfer_data": {"destination": partner_acct_id, "amount": 10700},
        "application_fee_amount": 300,
    }
)
```

Specifically the interaction between:
- **`on_behalf_of`**: shifts Stripe rail fee ($3.49) to the Partner Connect account
- **`transfer_data.amount`** (explicit): overrides the automatic `charge − application_fee` transfer with an explicit lesser amount, keeping Stripe rail on the Partner
- **`application_fee_amount`**: BidVex retention

**Stripe's documentation is not fully deterministic on whether**:
- Stripe's rail fee is deducted BEFORE or AFTER the `transfer_data.amount` calculation
- Whether `transfer_data.amount` can lawfully be smaller than `charge − application_fee − stripe_fee` (some accounts reject this)
- Whether the Partner's Connect region (Canada vs. US) affects the fee attribution
- Whether the interaction with `capture_method="automatic"` (default) vs. `manual` changes the settlement timing

**Static code analysis in Phase 0 predicted the economics but the brief explicitly forbids trusting that prediction without sandbox proof.** Since I cannot invoke Stripe, I cannot pass Gate 1.

### What would unblock Gate 1

Provide the following (test-mode only — never share live keys):

1. **`STRIPE_API_KEY=sk_test_...`** — a Stripe test-mode secret key with permission to create Checkout Sessions on Connect
2. **`STRIPE_TEST_PARTNER_CONNECT_ACCT=acct_...`** — a test-mode Express or Standard connected account with card_payments + transfers capabilities activated
3. **`STRIPE_TEST_BUYER_CUSTOMER=cus_...`** with attached test `pm_card_visa` (or approval for me to create one via `stripe.PaymentMethod.attach`)
4. **Webhook endpoint tunnelling** (Stripe CLI `stripe listen --forward-to https://prod-verify-2.preview.emergentagent.com/api/webhooks/stripe`) OR pre-arranged access to `dashboard.stripe.com/test/logs` for out-of-band verification

Alternatively:

5. **You run the sandbox proof yourself** using the test script I'll provide (read-only creation of test-mode Session, immediately voided). Then share the exact cent values Stripe reported for the four checkpoints:
   - `checkout.session.amount_total`
   - `payment_intent.application_fee_amount`
   - Connected account balance transaction (transfer amount)
   - Stripe fee (`balance_transaction.fee` on the charge)

I can prepare the exact `curl`-with-idempotency-key one-liner you would run — that is READ-ONLY code (a script for you), not a production code change.

---

## GATE 2 — Phase 2 Decision Validation: **BLOCKED on E-2 and E-3**

### Current state of E-1 through E-10 in `/app/docs/PHASE_0_DECISION_PACK.md`

| Decision | Status in Decision Pack | Blocking? |
|---|---|---|
| **E-1** — Stripe Connect architecture | **AUTHORIZED** by user's brief (Section 3: "The preferred architecture from Phase 0 is: Destination charge + on_behalf_of = Partner connected account + application_fee_amount") — subject to Gate 1 sandbox proof | Not blocking, but downstream of Gate 1 |
| **E-2** — Partner Buyer Premium tax place-of-supply | Marked "**⚠️ Confirm with accountant**" — *recommended default* only, not confirmed | 🔴 **BLOCKING** |
| **E-3** — BidVex platform fee tax place-of-supply | Marked "**⚠️ Confirm with accountant**" — *recommended default* only, not confirmed | 🔴 **BLOCKING** |
| **E-4** — Cash/e-transfer Stripe recovery | Recommended: Keep current behavior. Not marked ⚠️. | Not blocking |
| **E-5** — Which frontend endpoint is used | **RESOLVED** by verified frontend inspection (HIGH confidence): all three paths live; `/auction-winner-checkout` primary | Not blocking |
| **E-6** — Storage seller commission | Recommended: 0% per iter443. Historical exposure $0 (verified). | Not blocking |
| **E-7** — Partner Pro live? | Recommended: Defer | Not blocking |
| **E-8** — Broker Stripe live? | Recommended: Confirm business need; likely defer | Not blocking (deferred) |
| **E-9** — Refund allocation policy | Recommended: Defer to Phase 4 | Not blocking (deferred) |
| **E-10** — Partner + BidVex BP stacking | **RESOLVED — Model 1** (7 evidence lines) | Not blocking |

**Grep evidence** in `/app/docs/PHASE_0_DECISION_PACK.md`:
```
9 occurrences of ⚠️ / "BUSINESS/TAX DECISION REQUIRED" / "Confirm with accountant"
```

The 9 occurrences cluster around E-2 and E-3 (the two tax questions). These are the two decisions that Phase 0 explicitly identified as requiring Canadian-tax-counsel review before any code touches tax logic.

### Why E-2 and E-3 must be authoritatively resolved before Phase 1 code changes

The brief's Section 5 is explicit:

> "Do not invent Canadian tax law. Separate: Technical finding / Business rule already documented in BidVex / Tax/legal question requiring confirmation. For every ambiguous tax item, clearly mark: BUSINESS/TAX DECISION REQUIRED. Do not implement tax behavior until the rule is explicitly established."

And Section 41 / Phase 2:

> "Extract E-2 through E-9. If any remains unresolved: STOP."

**E-2 and E-3 are still marked ⚠️. Phase 2 gate cannot pass.**

If I proceeded to implement my *recommended* defaults from Phase 0 (Partner BP taxed at buyer province when Partner registered; BidVex platform fee taxed at Partner province), I would be **inventing tax rules** — exactly what the brief forbids.

### What would unblock Gate 2

Explicit written decision from you (or your accountant's sign-off) on each:

**E-2 — Partner Buyer Premium tax**:
- Is the Partner Buyer Premium a taxable supply?
- Place of supply: **buyer's province** / **Partner's province** / **exempt / zero-rated**?
- Behavior when Partner is NOT tax-registered: **no tax** / **something else**?
- Behavior when Partner IS tax-registered: **charge at [which] province** and remit **by [which party]**?

**E-3 — BidVex Platform Fee tax**:
- Is BidVex's 3% platform fee a taxable supply to the Partner (B2B)?
- Place of supply: **Partner's province** (recipient rule) / **BidVex's province** (supplier rule) / **something else**?
- Who charges the tax, remits it, and who ultimately economically bears it: **Partner** / **BidVex** / **Buyer**?
- Should this tax be visible on the buyer's Stripe charge (current code) or on a separate Partner invoice (my recommendation)?

Once written, the answers should be committed to the Decision Pack (replacing the ⚠️ markers with **AUTHORIZED**) before I proceed.

---

## Other Findings Discovered While Attempting the Gate Checks

None. No files were opened beyond `backend/.env` (to check for `STRIPE_API_KEY`) and a re-scan of the existing Decision Pack. Zero code was executed against production or staging. Zero state changed.

---

## What Would I Do If Both Gates Passed?

If you provide the Stripe test credentials AND the E-2/E-3 tax rulings, my Phase 1-through-Final implementation plan is:

**Phase 1a**: Run the sandbox proof script (test-mode only). Capture and post exact Stripe cent values for the canonical Partner $100/10% case. If sandbox proof matches Option A₁ predictions (Buyer $110.00; Partner nets ~$103.51; BidVex nets ~$3.00; Stripe rail ~$3.49), record proof; else STOP.

**Phase 1b**: Verify E-2/E-3 tax behavior against the sandbox proof. If Partner's province rule applies to platform-fee tax, confirm the sandbox shows the fee tax NOT charged to the buyer.

**Phase 3** (P0 repairs): Once Phase 1a/1b pass and both gates are open, implement:
- Partner Stripe checkout redesign (add `on_behalf_of` to `create_destination_charge` and `create_connect_checkout_session`; recalibrate `application_fee_amount` to the Phase 2 tax rule)
- `settle_auction` seller-type resolver (replace 4 hardcoded `seller_account_type="individual"` sites)
- Storage SC=0 override on `calculate_general_checkout` when `custom_buyer_premium_rate=0.05` is forced OR when listing type is `storage_locker`
- Multi-quantity fix on `routes/payments.py:883` (call `resolve_hammer_total`)

**Phase 4-12**: Consolidation, receipts, refunds, golden tests, final audit — as spec'd in the brief.

**Phase 12 final gate**: I output either `SAFE TO DEPLOY` or `DO NOT DEPLOY` with exact justification. **You separately authorize deployment.**

---

## What I Have NOT Done

- No production code modified
- No DB writes
- No Stripe API calls made
- No migrations run
- No deployments
- No historical records touched
- No tax rules invented
- No Stripe architecture assumptions treated as verified truth
- No frontend code modified
- No refund created
- No test-mode charge created

---

## Awaiting

1. **`STRIPE_API_KEY` (test-mode secret key)** — added to `/app/backend/.env` OR I write the sandbox proof script for you to run
2. **Test-mode Partner Connect account ID** — that has `charges_enabled=True` and `capabilities.card_payments=active` in Stripe test mode
3. **Explicit E-2 answer** — Partner BP tax place-of-supply rule
4. **Explicit E-3 answer** — BidVex platform fee tax place-of-supply rule

Once received, I will:
1. Run Phase 1a sandbox proof
2. Update `/app/docs/PHASE_0_DECISION_PACK.md` to replace ⚠️ markers with **AUTHORIZED** for E-2 and E-3
3. Proceed through Phase 3 → Phase 12 as spec'd
4. Emit the final `SAFE TO DEPLOY` / `DO NOT DEPLOY` verdict at Phase 12

---

*End of Gate Report. Both gates BLOCKED. Zero production changes. Zero deployments. Awaiting your explicit unblock.*
