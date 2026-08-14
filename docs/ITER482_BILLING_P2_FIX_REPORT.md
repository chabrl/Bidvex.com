# iter482 — BidVex Billing P2 Presentation Fix Report

**Report date:** 2026-02-15  
**Environment:** Preview (Stripe TEST only)  
**Reviewer mailbox:** `charbel911@gmail.com`  
**Scope:** iter482 P2 — presentation-only fixes to the 7 defects reported
in `docs/ITER482_BILLING_VISUAL_QA_REPORT.md`.  
**Corrected TEST/PREVIEW emails sent:** **49** (SendGrid `202 Accepted` on every send)

> **No financial calculation, tax logic, Stripe payment logic, reconciliation
> logic, or auction-settlement logic was modified.**  All changes are strictly
> presentation/localization additions.  1,195 billing-related regression tests
> pass, including 15 new tests locking in this fix.

---

## 1. Files changed

| # | File | Type of change |
|---|------|----------------|
| 1 | `backend/services/emails/email_system.py` | Made 6 helpers language-aware (EN + FR bodies + FR subjects).  Added optional `lang: Optional[str] = None` kwarg to the 5 helpers that don't already take a dict.  `send_invoice_overdue_email` reads `_detect_language(invoice)`. |
| 2 | `backend/services/invoice_service.py` | Extended `_fmt_currency(amount, currency="CAD", lang="en")` with a Canadian French branch (NBSP thousands separator, comma decimal, `$` suffix — BNQ 9921-500 compliant).  Threaded `lang` through the 5 call sites inside `generate_invoice_pdf`. |
| 3 | `backend/services/scheduler.py` | Two call-sites (`send_subscription_reminder_email` / `_expired_email`) now pass `lang=_detect_language(user)`. |
| 4 | `backend/services/scheduled_jobs.py` | Two call-sites (`send_payment_reminder_email` / `_overdue_email`) now pass `lang=_detect_language(winner, listing)`. |
| 5 | `backend/routes/settlement.py` | Immediate-reminder call now passes `lang=_detect_language(winner, doc)`. |
| 6 | `backend/tests/iter482/test_p2_billing_presentation_fixes.py` | **NEW** — 15 regression tests. |
| 7 | `backend/tests/iter482/billing_visual_qa_delivery.py` | Extended fixtures to fire FR variants of the 6 fixed helpers so the QA mailbox receives both languages. |
| 8 | `docs/ITER482_BILLING_P2_FIX_REPORT.md` | **NEW** — this file. |

No production code path outside of the helpers listed above was touched.
Financial, tax, Stripe, reconciliation, and settlement modules were not modified.

---

## 2. Defect ↔ Fix mapping (with PASS/FAIL)

| Ref | Defect | Fix summary | Regression tests | Status |
|-----|--------|-------------|------------------|--------|
| P2-1 | `send_invoice_overdue_email` EN-only | Reads `_detect_language(invoice)` → renders EN or FR subject + body (title, penalty label, warning box, CTA).  FR uses `_format_currency_fr` for all amounts. | `test_p2_1_invoice_overdue_fr_via_language_hint`, `test_p2_1_invoice_overdue_en_default_preserved` | ✅ **PASS** |
| P2-2 | `send_payment_reminder_email` EN-only | Added optional `lang` kwarg.  FR renders full body ("Bonjour {name}", "Rappel de paiement", "Payer maintenant", etc.), FR subject.  Amounts via `_format_currency_fr`. | `test_p2_2_payment_reminder_fr`, `test_p2_2_payment_reminder_en_default` | ✅ **PASS** |
| P2-3 | `send_payment_overdue_email` EN-only | Added optional `lang` kwarg.  FR renders "Paiement en retard" title + "Pénalité de retard (2 %/mois)" line + "Payer maintenant" CTA; FR subject "EN RETARD : paiement requis pour …". | `test_p2_3_payment_overdue_fr`, `test_p2_3_payment_overdue_en_default` | ✅ **PASS** |
| P2-4 | `send_subscription_reminder_email` EN-only | Added optional `lang` kwarg.  FR body: "Bonjour {name}", "Abonnement bientôt expiré", localized "Jours restants" row, "Voir mon abonnement" CTA; FR subject "⏰ Votre abonnement … expire dans N jour(s)". | `test_p2_4_subscription_reminder_fr`, `test_p2_4_subscription_reminder_en_default` | ✅ **PASS** |
| P2-5 | `send_subscription_expired_email` EN-only | Added optional `lang` kwarg.  FR body: "Abonnement expiré" title, localized "Ce qui a changé :" bullet list, "Renouveler mon abonnement" CTA; FR subject "Votre abonnement … est expiré". | `test_p2_5_subscription_expired_fr`, `test_p2_5_subscription_expired_en_default` | ✅ **PASS** |
| P2-6 | `send_subscription_upgraded_email` EN-only | Added optional `lang` kwarg.  FR body: "🎉 Abonnement mis à jour", localized "Vos avantages …" benefit list, "Commencer à explorer" CTA; FR subject "🎉 Bienvenue chez … !". | `test_p2_6_subscription_upgraded_fr`, `test_p2_6_subscription_upgraded_en_default` | ✅ **PASS** |
| P2-7 | Bilingual PDF FR currency format | `_fmt_currency()` extended with `lang` param.  FR: `32 500,00 $` (NBSP thousands, comma decimal, `$` suffix — BNQ 9921-500).  EN: unchanged (`$32,500.00`).  All 5 `_fmt_currency` call sites inside `generate_invoice_pdf` now pass `lang`. | `test_p2_7_bilingual_pdf_fr_currency_format`, `test_p2_7_bilingual_pdf_end_to_end_fr_renders_canadian_french_numbers` (pdfplumber-verified) | ✅ **PASS** |

Backward-compat guard: `test_all_six_helpers_still_default_to_en_when_lang_omitted`
proves that omitting the new `lang` kwarg yields the exact same EN behavior as before.

---

## 3. Test summary

| Metric | Value |
|-------:|:------|
| iter482 tests **before** this fix pass | 47 |
| iter482 tests **after** this fix pass | 62 |
| **New regression tests added (this batch)** | **15** |
| Golden-matrix + P7 exact-cent + P7.5 + iter482 (all billing critical) | **1,195 passing** (0 failures, 2 pre-existing deprecation warnings) |

Command used:
```
cd /app/backend && python -m pytest tests/p7/ tests/p7_5/ tests/iter482/ \
    tests/test_iter482_golden_matrix.py --tb=no -q
```

---

## 4. Confirmation of scope

* ✅ **Financial calculations were NOT changed.** (Every displayed amount is
  still a passthrough of the backend's canonical `payment_result` /
  `receipt` / `invoice` dict values.)
* ✅ **Tax logic was NOT changed.** (`tax_engine.py`, `fee_calculator.py`,
  `vehicle_pricing.py` untouched.)
* ✅ **Stripe payment logic was NOT changed.** (`payments.py`, `webhooks.py`,
  `payment_cost_engine.py` untouched.)
* ✅ **Reconciliation logic was NOT changed.**
  (`stripe_reconciliation_service.py`, `variance_notification_service.py`
  untouched.)
* ✅ **Auction settlement logic was NOT changed.** (The only change in
  `routes/settlement.py` is threading `lang` from an already-loaded user
  dict into an email helper — no ledger, no state transition, no charge.)
* ✅ **TEST/PREVIEW safety wrapper is preserved.** All 49 sends went through
  `install_safety_wrapper()`; `original_recipient` retained in the SendGrid
  `qa_original_to` custom-arg for audit.
* ✅ **Canonical iter482 French vocabulary preserved.** No changes to
  variance-notification wording.

---

## 5. Corrected TEST emails sent

**Total:** 49 messages, all to `charbel911@gmail.com` only, all
`[TEST/PREVIEW]` prefixed, all with the TEST/PREVIEW warning banner
in the body.

### 5.a Corrected PDFs generated

| # | PDF | Generator | Language(s) verified |
|---|-----|-----------|----------------------|
| 1 | `TEST_PREVIEW_bilingual_invoice_EN_ON.pdf` | `services/invoice_service.py::generate_invoice_pdf` | EN — `$32,500.00` |
| 2 | `TEST_PREVIEW_bilingual_invoice_FR_QC.pdf` | `services/invoice_service.py::generate_invoice_pdf` | **FR (P2-7 fixed)** — `32 500,00 $` (Canadian French) |
| 3 | `TEST_PREVIEW_vehicle_platform_fee_invoice.pdf` | `services/invoice_generator.py` | Bilingual labels |
| 4 | `TEST_PREVIEW_general_invoice_business_seller_QC.pdf` | `services/invoice_generator.py` | Bilingual labels |
| 5 | `TEST_PREVIEW_lots_won_EN.pdf` | `invoice_templates.py::lots_won_template` | EN |
| 6 | `TEST_PREVIEW_lots_won_FR.pdf` | `invoice_templates.py::lots_won_template` | FR |
| 7 | `TEST_PREVIEW_seller_statement.pdf` | `invoice_templates.py::seller_statement_template` | EN |
| 8 | `TEST_PREVIEW_seller_receipt.pdf` | `invoice_templates.py::seller_receipt_template` | EN |
| 9 | `TEST_PREVIEW_commission_invoice.pdf` | `invoice_templates.py::commission_invoice_template` | EN |
| 10 | `TEST_PREVIEW_payment_letter.pdf` | `invoice_templates.py::payment_letter_template` | EN |

**Total corrected PDFs generated:** 10.

### 5.b Exact subject-line manifest

```
 1  [TEST/PREVIEW] Invoice #BV-20260215-000042 - 2019 Ford F-150 Lariat 4x4
 2  [TEST/PREVIEW] Facture nºBV-20260215-000043 — Camion Ford F-150 Lariat 4x4 2019
 3  [TEST/PREVIEW] Payment Confirmed - Invoice #BV-20260215-000042
 4  [TEST/PREVIEW] Paiement confirmé — Facture nºBV-20260215-000043
 5  [TEST/PREVIEW] BidVex — Payment received for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
 6  [TEST/PREVIEW] BidVex — Paiement reçu pour Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
 7  [TEST/PREVIEW] BidVex — Payment received for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)     ← lots section
 8  [TEST/PREVIEW] BidVex Sale Statement — Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
 9  [TEST/PREVIEW] Relevé de vente BidVex — Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
10  [TEST/PREVIEW] BidVex — Your invoice for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
11  [TEST/PREVIEW] BidVex — Votre facture pour Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
12  [TEST/PREVIEW] BidVex — Your settlement statement — Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
13  [TEST/PREVIEW] BidVex — Votre relevé de règlement — Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
14  [TEST/PREVIEW] ⚠️ OVERDUE: Invoice #BV-20260215-000042 - Action Required                   ← P2-1 EN
15  [TEST/PREVIEW] ⚠️ EN RETARD : Facture nºBV-20260215-000043 — action requise                ← P2-1 FR (NEW)
16  [TEST/PREVIEW] Payment Reminder: 2019 Ford F-150 Lariat 4x4 - 4 Days Left                  ← P2-2 EN
17  [TEST/PREVIEW] Rappel de paiement : Camion Ford F-150 Lariat 4x4 2019 — 4 jour(s) restant(s) ← P2-2 FR (NEW)
18  [TEST/PREVIEW] OVERDUE: Payment Required for 2019 Ford F-150 Lariat 4x4                     ← P2-3 EN
19  [TEST/PREVIEW] EN RETARD : paiement requis pour Camion Ford F-150 Lariat 4x4 2019           ← P2-3 FR (NEW)
20  [TEST/PREVIEW] Payment required within 48h — Lot #42 — Milwaukee Power Tool Pallet
21  [TEST/PREVIEW] Paiement requis sous 48 h — Lot #42 — Palette d'outils Milwaukee
22  [TEST/PREVIEW] Payment failed — 2019 Ford F-150 Lariat 4x4
23  [TEST/PREVIEW] Échec du paiement — Camion Ford F-150 Lariat 4x4 2019
24  [TEST/PREVIEW] You Won! Complete Payment for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
25  [TEST/PREVIEW] Vous avez gagné ! Effectuez le paiement pour Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
26  [TEST/PREVIEW] You Won! Vehicle 2019 Ford F-150 Lariat 4x4 — Fee Invoice Ready
27  [TEST/PREVIEW] BidVex Commission Invoice — Storage Auction #sa_test_…
28  [TEST/PREVIEW] 🎉 You won — Storage Auction Unit #17B
29  [TEST/PREVIEW] Deposit refunded · Dépôt remboursé — $200.00 CAD
30  [TEST/PREVIEW] [BidVex] Bidding deposit captured · Dépôt saisi — Invoice BV-20260215-000042
31  [TEST/PREVIEW] BidVex Buyer Commission · Commission acheteur BidVex — $46.88 CAD
32  [TEST/PREVIEW] Buy Now Purchase · Achat immédiat — $299.00 CAD
33  [TEST/PREVIEW] BidVex Seller Commission · Commission vendeur BidVex — $118.75 CAD
34  [TEST/PREVIEW] Sale payout · Paiement de vente — $1,828.13 CAD
35  [TEST/PREVIEW] ✅ Your annual subscription is active · Votre abonnement annuel est actif — BidVex
36  [TEST/PREVIEW] ⏰ Your Premium Subscription Expires in 3 Days                                  ← P2-4 EN
37  [TEST/PREVIEW] ⏰ Votre abonnement Premium expire dans 3 jour(s)                              ← P2-4 FR (NEW)
38  [TEST/PREVIEW] Your Vip Subscription Has Expired                                              ← P2-5 EN
39  [TEST/PREVIEW] Votre abonnement Vip est expiré                                                ← P2-5 FR (NEW)
40  [TEST/PREVIEW] 🎉 Welcome to Vip!                                                              ← P2-6 EN
41  [TEST/PREVIEW] 🎉 Bienvenue chez Vip !                                                        ← P2-6 FR (NEW)
42  [TEST/PREVIEW] ✅ Your listing is now boosted — 2019 Ford F-150 Lariat 4x4 | BidVex Marketplace
43  [TEST/PREVIEW] 🎉 Sold! 2019 Ford F-150 Lariat 4x4 - $32,500.00
44  [TEST/PREVIEW] BidVex — Stripe Processing Fee Variance Detected · BidVex — Écart des frais de traitement Stripe détecté (INTL)
45  [TEST/PREVIEW] BidVex — Stripe Processing Fee Variance Detected · BidVex — Écart des frais de traitement Stripe détecté (Domestic)
46  [TEST/PREVIEW] Buyer Invoice PDF — BidVex Bilingual Auction Invoice PDF (services/invoice_service.py)   [+2 PDFs]
47  [TEST/PREVIEW] Vehicle Fee PDF — BidVex Vehicle Platform-Fee Invoice PDF                               [+1 PDF]
48  [TEST/PREVIEW] General Invoice PDF — BidVex General Auction Invoice PDF (business seller, Québec)     [+1 PDF]
49  [TEST/PREVIEW] Legacy HTML Invoice Templates — invoice_templates.py — all 5 templates rendered        [+6 PDFs]
```

Lines 15, 17, 19, 37, 39, 41 are the **six new FR variants** that only exist because of this P2 fix pass.  Line 46's `TEST_PREVIEW_bilingual_invoice_FR_QC.pdf` attachment now uses Canadian French currency formatting per P2-7.

---

## 6. Remaining presentation defects

**None flagged in this pass.**  All 7 originally-reported P2 defects are
resolved, verified by unit + end-to-end tests, and re-delivered to the QA
mailbox for personal review.

---

## 7. Deployment gate

🚫 **DO NOT DEPLOY.**  
Unchanged production-readiness blockers:

1. Populate `STRIPE_LIVE_SECRET_KEY` + `STRIPE_LIVE_WEBHOOK_SECRET`.
2. Set `BILLING_ALERT_EMAIL` to a live finance mailbox.
3. Prune any remaining `admin` / `super_admin` seed rows on the preview DB
   before promotion.

## 8. Next steps

1. **Reviewer (you):** open `charbel911@gmail.com` and visually compare
   messages 14/15, 16/17, 18/19, 36/37, 38/39, 40/41 for the EN/FR pairs
   of the 6 fixed helpers.  Open the FR PDF attachment on message 46 to
   verify Canadian French currency formatting.
2. **After your visual approval:** we can proceed to P8 (peripheral flows
   audit) or Gate 4 (Tax Engine Consolidation) on your explicit signal.
3. **Still blocked (as previously):** Gate 4, P8, P9, deployment — awaiting
   your explicit go-ahead.
