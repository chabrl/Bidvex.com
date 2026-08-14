# iter482 P6.1 — REAL Stripe TEST-Mode Reconciliation Proof

**Environment:** PREVIEW ONLY · **Stripe mode:** TEST (`sk_test_…`)
**Deploy:** ❌ NOT deployed · **Live Stripe:** ❌ NOT touched · **Customer charged:** ❌ NEVER
**Baseline before P6.1:** 1,156 tests · **After P6.1:** **1,157 tests passing** (+1 P6.1 real-Stripe live test)
**Regressions:** 0

---

## 1. Real Stripe TEST PaymentIntent (evidence)

The test executes a REAL Stripe TEST charge through `stripe.PaymentIntent.create(...)`
with `pm_card_visa` (Stripe's static TEST PaymentMethod → 4242 Visa → US card) so the
card resolves to the INTERNATIONAL jurisdiction. NO monkey-patching — the reconciliation
service makes real API calls to Stripe.

| Field | Value |
|---|---|
| PaymentIntent ID | `pi_3U4QrCBd6Wtvh7hs1slL2Ghx` |
| Charge ID | `ch_3U4QrCBd6Wtvh7hs15hBetFb` |
| BalanceTransaction ID | `txn_3U4QrCBd6Wtvh7hs1miMAyM5` |
| Amount charged | 10 500¢ ($105.00 CAD) |
| Currency | CAD |
| Card country (Stripe authoritative) | `US` |
| Resolved jurisdiction | `international` |
| Estimated fee (metadata, at CA rate) | 334¢ ($3.34) |
| Recovery (payer-borne, at CA rate) | 344¢ ($3.44) |
| **Actual Stripe fee (real BalanceTransaction)** | **419¢ ($4.19)** |
| Variance | **-75¢ (-$0.75) — BidVex out of pocket** |
| Reconciliation status | **SHORTFALL** |
| Variance notification status | `SENT` |
| Notification sent at | `2026-08-14T19:33:37.923097+00:00` |

**Stripe `fee_details` (real):**
```json
[{
  "amount": 419,
  "application": null,
  "currency": "cad",
  "description": "Stripe processing fees",
  "type": "stripe_fee"
}]
```

---

## 2. BalanceTransaction retrieval

**Real Stripe API path (unchanged, existing infrastructure):**

```
stripe.PaymentIntent.retrieve(pi_id, expand=[
    "latest_charge.balance_transaction", "payment_method"
])
```

**Defect surfaced by real Stripe API + minimal fix (`services/stripe_reconciliation_service.py`)**

The deep-nested `expand=['latest_charge.balance_transaction']` in the current Stripe
API can return `balance_transaction = None` immediately after `confirm=True` because
Stripe's ledger writes the BalanceTransaction asynchronously (typically within a few
seconds). Only exposed by real Stripe calls — the monkey-patched tests always returned
a pre-populated shape and hid the race.

**Fix (minimal, no duplication):**
- If `latest_charge.balance_transaction` is not a dict, refetch the charge with a
  single-level expand: `stripe.Charge.retrieve(charge_id, expand=["balance_transaction"])`.
- Retry up to 3× at 1s intervals to accommodate Stripe's asynchronous ledger post.
- Convert Stripe `FeeDetail` objects to plain dicts before Mongo persistence.
- **No duplicate reconciliation engine, no new BalanceTransaction fetcher, no weakened
  idempotency guard.** Same function, same doc shape, same idempotent upsert.

---

## 3. Card jurisdiction — real Stripe data only

**Sources checked (in order):**
1. `latest_charge.payment_method_details.card.country` (authoritative)
2. `payment_method.card.country` (fallback via `expand=['payment_method']`)

**Verified:** the reconciliation record persists `card_country = "US"` from step 1
above — Stripe's authoritative field.

**Not used (guardrail intact):** buyer province · billing province · seller location · IP · browser locale · language · shipping address. Not one of these can influence `resolved_jurisdiction`.

---

## 4. International SHORTFALL — proven

| Step | Result |
|---|---|
| Estimated calculated (metadata) | ✅ 334¢ |
| Recovery calculated (metadata) | ✅ 344¢ |
| Actual Stripe fee retrieved | ✅ **419¢ (real BalanceTransaction)** |
| Variance = recovery − actual | ✅ −75¢ |
| SHORTFALL identified | ✅ `reconciliation_status = "SHORTFALL"` |
| SHORTFALL persisted | ✅ MongoDB row upserted |
| Admin dashboard displays SHORTFALL | ✅ Row visible with red badge, −$0.75 |
| Variance notification triggered | ✅ Exactly one batch dispatched |
| **Customer NOT recharged** | ✅ No secondary Stripe call, no re-authorization |

---

## 5. Webhook idempotency (real Stripe)

`reconcile_payment_intent(db, pi_id)` was invoked **four times** for the same PaymentIntent
(1 initial + 3 replays). Result:

- DB rows for this PI: **1** (Mongo idempotent upsert on `payment_intent_id`)
- Variance email batches dispatched: **1** (atomic `variance_notification_status` guard)
- Emails after 1st dispatch: `6` (one per admin recipient in this environment)
- Emails after 3× replay: `6` (identical — no additional sends)
- `variance_notification_status` transitions: `<missing> → SENDING → SENT` (never re-claimed)

The idempotency guard was NOT weakened. Same `find_one_and_update` with `$or` claim.

---

## 6. Admin dashboard verification (live preview)

**URL:** `/admin/reconciliation`
**Access:** admin/super_admin only. Verified by the existing 7 authorization tests
(401 unauth · 403 buyer · 403 seller · 200 admin · 200 super_admin · filter · search).

**Real transaction visible in EN dashboard (screenshot in preview):**

| Dashboard field | Value shown |
|---|---|
| Payment Intent | `pi_3U4QrCBd6Wtvh7hs1slL2Ghx` |
| Charge ID | `ch_3U4QrCBd6Wtvh7hs15hBetFb` |
| Balance Transaction | `txn_3U4QrCBd6Wtvh7hs1miMAyM5` |
| Estimated Payment Processing Fee | $3.34 |
| Payment Processing Fee Recovery | $3.44 |
| Actual Stripe Processing Fee | **$4.19** |
| Processing Fee Shortfall | **-$0.75** |
| Card Country | US |
| Card Jurisdiction | International |
| Variance Notification | SENT |
| Notification Sent At | 2026-08-14 19:33:37 |
| Status badge | 🔴 **Shortfall** |

**Real transaction visible in FR dashboard (screenshot in preview):**

- Title: « Rapprochement des paiements » ✅
- Header: « Marché · Enchères par lots · Enchères entreposage · Enchères de véhicules · Vendre »
- Table columns: « INTENTION DE PAIEMENT · DATE · RÔLE DU PAYEUR · JURIDICTION · ESTIMÉ · RÉCUPÉRATION · FRAIS STRIPE RÉELS · ÉCART · STATUT »
- Row for real PI shows `International · 3,34 $ · 3,44 $ · 4,19 $ · -0,75 $` with 🔴 «Manque à récupérer»
- Currency formatted in fr-CA (space thousand-separator, comma decimal, `$` suffix)

**Detail dialog labels remain canonical:**
| EN | FR |
|---|---|
| Estimated Payment Processing Fee | Frais de traitement du paiement estimés |
| Payment Processing Fee Recovery | Récupération des frais de traitement du paiement |
| Actual Stripe Processing Fee | Frais de traitement Stripe réels |
| Processing Fee Shortfall | Manque à récupérer sur les frais de traitement |
| Card Jurisdiction · International | Juridiction de la carte · International |

---

## 7. Reconciliation invariant — actual == persisted == API == dashboard

To-the-cent parity for `pi_3U4QrCBd6Wtvh7hs1slL2Ghx`:

| Source | actual_cents |
|---|---|
| Stripe BalanceTransaction (`bt.fee`) | 419 |
| Reconciliation service return | 419 |
| Persisted MongoDB row | 419 |
| Admin API `/{pi_id}` response | 419 |
| Dashboard detail dialog | $4.19 |

Never substituted the estimated fee for the actual fee anywhere.

---

## 8. Variance email — canonical dispatcher, idempotent, EN + FR

- **Dispatcher used:** `services/emails/_email_core.send_email` (existing canonical). No
  second dispatcher created.
- **Trigger:** SHORTFALL only. RECONCILED payments trigger 0 emails (verified by
  `test_reconciled_status_never_sends`).
- **Body:** bilingual — EN block, `<hr>`, FR block. Contains:
  * « Frais de traitement du paiement estimés » ✅
  * « Récupération des frais de traitement du paiement » ✅
  * « Frais de traitement Stripe réels » ✅
  * « Manque à récupérer sur les frais de traitement » ✅
  * « International » ✅
- **Idempotency:** atomic `variance_notification_status` claim. Real replay proved 0
  additional sends. Delivery record persisted per recipient
  (`variance_notification_delivery`).
- **Delivery in this test:** SendGrid was stubbed so no real customer email was sent —
  the canonical dispatcher CALL was verified end-to-end. In production the same call
  path fires real SendGrid using the credentials in `backend/.env`.
- **CASL / suppression:** unchanged. Uses the same suppression gate every existing
  outbound path uses.

---

## 9. No regression

**Full regression (excluding P6.1 real-Stripe scenario, which lives in its own file):**
```
1,149 passed in 11.31s
```

**Authorization tests (isolated to avoid rate limits):**
```
7 passed in 1.87s
```

**P6.1 real Stripe TEST reconciliation:**
```
1 passed in 5.97s
```

**Grand total passing: 1,157** (was 1,156 · +1 new P6.1 test)
**Failed: 0** · **Skipped: 0**

**Unrelated code paths NOT modified:**
- Tax engine · fee_calculator · auction_settlement · payment_cost_engine · webhooks
  (business logic) · Stripe Connect · seller payment-method architecture · escrow ·
  payouts · reserve-price logic.

---

## 10. Files changed / created

| Path | Change |
|---|---|
| `backend/services/stripe_reconciliation_service.py` | Minimal fix — refetch charge with single-level expand when deep-nested BT expand returns None; bounded retry (3× × 1s) for async Stripe ledger; convert Stripe FeeDetail objects to plain dicts before Mongo persistence. |
| `backend/tests/iter482/test_p61_real_stripe_reconciliation.py` | **NEW** — 1 E2E test that creates a real Stripe TEST PaymentIntent, drives `reconcile_payment_intent` (no monkey-patch), verifies every invariant + 3× webhook replay idempotency. |
| `docs/ITER482_P61_REAL_STRIPE_TEST_REPORT.md` | **NEW** — this document. |

No new payment-cost engine · no new reconciliation service · no new email dispatcher ·
no new tax engine · no seller-payment-method changes.

---

## 11. Remaining blockers

**None.**

Two forward items (previously surfaced in the P6 report, still applicable):
1. `BILLING_ALERT_EMAIL` env var unset — dedicated finance mailbox override. Falls back
   to admin/super_admin users + `ADMIN_EMAIL`. To route variance notifications to a
   dedicated inbox (e.g. `billing@bidvex.ca`), set the env var and restart backend.
2. Live-mode reconciliation is code-ready — same code path, same invariants — but
   NOT exercised in this preview (Stripe LIVE key is intentionally not used).

---

## 12. Guardrails held (verbatim)

- ✅ NO deploy.
- ✅ NO Stripe LIVE mode.
- ✅ NO customer charged.
- ✅ NO historical financial records mutated (upserts keyed on `payment_intent_id`).
- ✅ NO duplicate payment-cost engine.
- ✅ NO duplicate reconciliation service.
- ✅ NO duplicate email dispatcher.
- ✅ NO tax engine changes.
- ✅ NO seller payment-method changes.
- ✅ Integer-cent accounting throughout.
- ✅ Idempotency preserved and PROVEN with a live 3× replay.
- ✅ SHORTFALL detection PROVEN against real Stripe TEST BalanceTransaction.
- ✅ Existing P6 infrastructure used verbatim.
