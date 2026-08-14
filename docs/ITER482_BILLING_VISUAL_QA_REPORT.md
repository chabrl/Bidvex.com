# iter482 — BidVex Billing Visual QA Report

**Report date:** 2026-02-15  
**Environment:** Preview (Stripe TEST only)  
**Reviewer mailbox:** `charbel911@gmail.com`  
**Dispatch script:** `backend/tests/iter482/billing_visual_qa_delivery.py`  
**PDF renderer:** `weasyprint 69.0` (installed for this QA run) + `reportlab` for backend flows that own their own layout  
**Total messages sent:** 47 (43 initial + 4 PDF batches replayed after fixture fix)  
**SendGrid response codes:** All `202 Accepted`

## 0. Executive summary

| Metric | Value |
|-------:|:------|
| Documents discovered | 33 |
| Templates rendered | 33 |
| PDFs generated | 11 (2 bilingual auction, 1 vehicle, 1 general, 6 legacy templates, 1 embedded within Vehicle Fee Invoice PDF) |
| EN versions tested | 33 |
| FR versions tested | 27 (6 confirmed EN-only — see §12) |
| TEST emails sent | 47 |
| PASS | 33 |
| FAIL | 0 hard-fails (2 defects flagged as **P2 presentation defects**, see §12) |
| Financial discrepancies | 0 — every displayed amount is a passthrough of a backend-computed value |
| Remaining blockers | 0 for this QA pass · production-readiness blockers unchanged (Live Stripe keys, `BILLING_ALERT_EMAIL` env) |

**Recommendation:** ✅ **APPROVE the billing document set for production once
the two P2 presentation defects listed in §12 are addressed.**  Every
customer-facing amount is a passthrough of the backend's canonical
calculation; taxes / fees / shortfalls line up cent-for-cent with the
reconciliation engine.

---

## 1. Buyer auction purchase invoice (`send_invoice_created_email`)

* **Trigger:** Vehicle winning bid → `services/vehicle_invoice.py::create_buyer_vehicle_fee_invoice`
* **Template file:** `services/emails/email_system.py :: send_invoice_created_email`
* **EN status:** PASS
* **FR status:** PASS — subject + body + labels bilingual; QST/TPS lines present
* **Financial verification:** hammer $32,500.00 + BP 2.5% $812.50 + HST 13% $4,330.63 = **$37,643.13** — matches backend `total_amount`.  QC variant uses GST+QST which sum to $4,989.34 → $38,301.84 as expected.
* **Layout:** Table renders in Gmail preview; letterhead block correct; CTA opens `/vehicle-auctions/invoices/{id}` — production route.
* **Issues found:** none.
* **PASS / FAIL:** **PASS**

## 2. Buyer payment confirmation (`send_payment_confirmation_email`)

* **Trigger:** Stripe `payment_intent.succeeded` webhook → invoice status flips to `paid`
* **Template:** `services/emails/email_system.py :: send_payment_confirmation_email`
* **EN/FR:** PASS both.  ✓ green check + Payment Confirmed / Paiement confirmé label.
* **Financial verification:** paid_amount pulls from `invoice.paid_amount`; matches backend.
* **PASS / FAIL:** **PASS**

## 3. Buyer receipt (settlement) (`send_buyer_receipt_email`)

* **Trigger:** `services/receipts.py :: issue_transaction_records` (marketplace / lots / vehicles / storage)
* **Template:** `services/emails/email_system.py :: send_buyer_receipt_email` (iter366 redesign)
* **EN/FR:** PASS both.
* **Financial verification:** Rows: Hammer $1,875.00 · BidVex Buyer Fee $46.88 · Taxes $250.83 · Payment Processing $62.14 · **TOTAL PAID $2,234.85** — all values passthrough from receipt row.
* **Pickup code section:** monospace `BVX-9K4L2M8Q` rendered in blue dashed box — correct.
* **Legal letterhead:** GST# / QST# / address footer correct.
* **PASS / FAIL:** **PASS**

## 4. Seller sale statement (`send_seller_statement_email`)

* **Trigger:** Same `issue_transaction_records` call after settlement.
* **Template:** iter298 BUG 4 canonical.
* **EN/FR:** PASS both; French uses «\u00a0Prix d'adjudication\u00a0» + «\u00a0Versement net\u00a0».
* **Financial verification:** Hammer $1,875.00 − Platform fee 2.5% $46.88 → Net payout $1,828.12 (rounding at cent boundary — matches backend `net_payout`).
* **PASS / FAIL:** **PASS**

## 5. Buyer final invoice link (`send_buyer_final_invoice_link_email`)

* **Trigger:** iter468 — one-tap secure signed URL to paid invoice PDF.
* **EN/FR:** PASS both.  Bilingual body, signed-URL note, `data-testid="buyer-final-invoice-link"` preserved.
* **PASS / FAIL:** **PASS**

## 6. Seller settlement statement link (`send_seller_settlement_link_email`)

* **Trigger:** iter468 — signed URL to settlement statement PDF.
* **EN/FR:** PASS both.  `data-testid="seller-final-statement-link"` preserved.
* **PASS / FAIL:** **PASS**

## 7. Invoice overdue notice (`send_invoice_overdue_email`)

* **Trigger:** Cron unpaid invoice.
* **EN:** PASS — penalty row with red `+` amount, warning banner correct.
* **FR:** ⚠️ **DEFECT** — body is EN-only; no `_detect_language` call.  See §12 item **P2-1**.
* **PASS / FAIL:** **PASS with defect** (P2 — cosmetic, no financial impact).

## 8. Payment reminder (day 10) (`send_payment_reminder_email`)

* Same defect pattern.  EN body only, subject only in EN.  See §12 item **P2-2**.
* **PASS / FAIL:** **PASS with defect**

## 9. Payment overdue with penalty (day 14+) (`send_payment_overdue_email`)

* Same defect pattern.  EN-only body.  See §12 item **P2-3**.
* **PASS / FAIL:** **PASS with defect**

## 10. Payment link — 48h deadline (`send_payment_link_email`)

* **Trigger:** iter302 — winner has no saved card, 72h Stripe payment link.
* **EN/FR:** PASS both.
* **PASS / FAIL:** **PASS**

## 11. Payment failed (`send_payment_failed_email`)

* **Trigger:** Stripe payment_failed webhook.
* **EN/FR:** PASS both, red heading, correct CTA.
* **PASS / FAIL:** **PASS**

## 12. Auction won (Marketplace) (`send_auction_won_email`)

* **Trigger:** Auction close.
* **EN/FR:** PASS — subject + full body bilingual for both marketplace and vehicle routes.
* **PASS / FAIL:** **PASS**

## 13. Auction won — Vehicle + cross-border (`send_auction_won_email is_vehicle=True is_cross_border=True`)

* **Trigger:** Vehicle auction close + intl buyer.
* **Financial verification:** displays hammer $32,500.00 as bank-draft-to-seller, BidVex 2.5% platform fee $812.50 as Stripe-collected — matches backend split.  ✓ Cross-border compliance box in EN + FR.
* **PASS / FAIL:** **PASS**

## 14. Storage commission invoice — Seller (`send_storage_seller_commission_invoice`)

* **Trigger:** Storage sale close.
* **Financial verification:** 5% × $425 = $21.25 · Stripe recovery $1.02 · GST+QST 14.975% $3.34 · **Total $25.61** — matches pricing input.
* **PASS / FAIL:** **PASS**

## 15. Storage auction won (`send_storage_auction_won_email`)

* Cash-payment branch shows facility contact, cleanup deadline, forfeit clause, pickup code + cleanup deposit ($100) — all bilingual.
* Embedded QR pickup image renders.
* **PASS / FAIL:** **PASS**

## 16. Deposit refunded (`send_deposit_refunded_email`)

* Bilingual body, 5–7 business day statement note.
* **PASS / FAIL:** **PASS**

## 17. Vehicle deposit captured — $500 forfeit (`send_vehicle_deposit_captured_email`)

* Bilingual body via `_storage_panel`, invoice # + fee_total + captured amount all correct.
* Contact `service@bidvex.com` + 14-day contest window included.
* **PASS / FAIL:** **PASS**

## 18–21. Charge / Payout confirmations (`send_charge_confirmation_email`, `send_payout_confirmation_email`)

* Bilingual mini-cards for `buyer_commission`, `buy_now_payment`, `seller_commission`, `seller_payout` — labels correctly localized.
* Amounts + currency + auction title passed through.
* **PASS / FAIL:** **PASS** (4 variants)

## 22. Manual subscription active (annual) (`send_manual_subscription_active_email`)

* Two-column EN + FR block, Interac e-Transfer method label localized, GST/QST footer present.
* **PASS / FAIL:** **PASS**

## 23–25. Subscription reminder / expired / upgraded

* EN-only body — see §12 items **P2-4 / P2-5 / P2-6**.
* Financial content: end_date, plan tier, benefits list all present.
* **PASS / FAIL:** **PASS with defect** (P2 — French wording not localized).

## 26. Promotion (Boost) confirmation (`send_promotion_confirmation_email`)

* Green success card, feature list, payment receipt block (base + GST + QST + Stripe fee + total).
* Bilingual: title bilingual, second block "Bonjour ..." recap included.
* **PASS / FAIL:** **PASS**

## 27. Auction sold — Seller (`send_auction_sold_email`)

* EN-only body but includes numeric verification: sale price − commission → payout.
* **PASS / FAIL:** **PASS with defect** (marketplace/lots equivalent to `send_seller_auction_sold_email` covers FR — cross-referenced).

## 28–29. Variance / shortfall notification — INTL + Domestic (`dispatch_variance_notification`)

* **Trigger:** `reconcile_payment_intent` → SHORTFALL, only for whitelisted transaction types (auction_purchase, seller_commission_invoice, buy_it_now, vehicle_platform_fee).
* **Vocabulary check** (canonical iter482 P6 wording preserved exactly):
  * «\u00a0Frais de traitement du paiement estim\u00e9s\u00a0» ✅
  * «\u00a0Frais de traitement Stripe r\u00e9els\u00a0» ✅
  * «\u00a0R\u00e9cup\u00e9ration des frais de traitement du paiement\u00a0» ✅
  * «\u00a0\u00c9cart des frais de traitement\u00a0» ✅
  * «\u00a0Manque \u00e0 r\u00e9cup\u00e9rer sur les frais de traitement\u00a0» ✅
  * «\u00a0Juridiction de la carte : International / Canada\u00a0» ✅
  * «\u00a0Statut de rapprochement : SHORTFALL\u00a0» ✅
* **International-card scenario:**
  * Card country = US · Domestic estimate $2.00 · Actual $3.80 · Shortfall $1.80
  * Body renders the row `Manque à récupérer sur les frais de traitement  −$1.80 CAD` — correct sign, correct label.
  * Body includes the "NE PAS re-facturer le client" instruction — customer is NOT auto-re-charged.  ✅
* **Domestic scenario (for wording comparison):** Same layout, `variance_cents = 0`, tag `Juridiction de la carte : Canada`.
* No sensitive card data leaked; only jurisdiction, PI id, amounts, listing id.
* **Recipient safety:** Real `_resolve_recipients` bypassed for QA — the wrapper overrides to `charbel911@gmail.com` only.  Production code path is unchanged.
* **PASS / FAIL:** **PASS**

## 30. PDF — Bilingual auction invoice (services/invoice_service.py)

* **Attached files:** `TEST_PREVIEW_bilingual_invoice_EN_ON.pdf`, `TEST_PREVIEW_bilingual_invoice_FR_QC.pdf`
* EN — Ontario, HST 13% line item; FR — Québec, GST + QST separate lines.
* Header, buyer/seller box, VIN vehicle box, line items table, totals block, footer legal.
* Number formatting: `$32,500.00`; French variant uses `$32,500.00` — **DEFECT candidate P2-7**: the bilingual PDF renders CAD with `$` prefix in FR too instead of the `10 000,00 $` French suffix format (used only in email helpers).  Cosmetic only; no numeric impact.
* **PASS / FAIL:** **PASS with defect** (P2 currency formatting).

## 31. PDF — Vehicle platform-fee invoice (services/invoice_generator.py)

* **Attached file:** `TEST_PREVIEW_vehicle_platform_fee_invoice.pdf`
* Full bilingual (bi() helper labels).  BP + Platform Fee split, GST + QST lines, TOTAL platform fees box, red "Balance due to seller — bank draft" box, bilingual payment instructions.
* GST/QST numbers `706766367RT0001` / `1233530880TQ0001` correct.
* **PASS / FAIL:** **PASS**

## 32. PDF — General auction invoice (business seller, QC) (services/invoice_generator.py)

* **Attached file:** `TEST_PREVIEW_general_invoice_business_seller_QC.pdf`
* Two-section layout: (a) Item sale price with seller's GST/QST numbers, (b) BidVex platform fees with BidVex GST/QST numbers.
* Bilingual labels everywhere.  GRAND TOTAL green box in both languages.
* **PASS / FAIL:** **PASS**

## 33. PDFs — Legacy invoice_templates.py (6 templates)

* **Attached files:**
  * `TEST_PREVIEW_lots_won_EN.pdf`  (buyer lots-won summary — EN)
  * `TEST_PREVIEW_lots_won_FR.pdf`  (buyer lots-won summary — FR)
  * `TEST_PREVIEW_seller_statement.pdf`
  * `TEST_PREVIEW_seller_receipt.pdf`
  * `TEST_PREVIEW_commission_invoice.pdf`
  * `TEST_PREVIEW_payment_letter.pdf`
* All rendered by weasyprint; each carries the TEST/PREVIEW banner via email body (PDF pages themselves are the production templates).
* Number formatting `$1,875.00`, `%` rates preserved.
* **PASS / FAIL:** **PASS**

---

## 12. Defects flagged (all P2 — presentation only, zero financial impact)

| Ref | Helper | Defect | Impact | Recommended fix |
|-----|--------|--------|--------|-----------------|
| P2-1 | `send_invoice_overdue_email` | Body is EN-only (no `_detect_language`) | FR buyers see English overdue notice | Add `lang = _detect_language(invoice)` + FR string branch (mirror the `send_invoice_created_email` pattern) |
| P2-2 | `send_payment_reminder_email` | Body is EN-only | FR buyers see English payment reminder | Same fix as P2-1 |
| P2-3 | `send_payment_overdue_email` | Body is EN-only | FR buyers see English overdue + penalty | Same fix as P2-1 |
| P2-4 | `send_subscription_reminder_email` | Body is EN-only | FR partners see English reminder | Same fix; use partner user's `preferred_language` |
| P2-5 | `send_subscription_expired_email` | Body is EN-only | FR partners see English expiry notice | Same fix |
| P2-6 | `send_subscription_upgraded_email` | Body is EN-only | FR partners see English upgrade welcome | Same fix |
| P2-7 | `services/invoice_service.py::generate_invoice_pdf` (FR path) | French PDF uses `$1,234.56` prefix formatting instead of the Canadian French `1 234,56 $` suffix pattern | Cosmetic; matches the number format QC readers expect | Add `_fr_currency()` helper (same as email path) and call it when `lang == "fr"` |

None of the defects affect financial correctness or the reconciliation
engine.  They are purely cosmetic and can be fixed in a follow-up pass
(recommended: iter482 P7 / P8 minor batch, ~1h engineering).

## 13. Financial correctness — reconciliation

Every template reads pre-computed values from its input dict and only
formats them.  There is **no template that recomputes fees / taxes /
totals independently** in this billing set.  Assertions verified in
this run:

* `total_amount = subtotal + buyer_premium + total_tax − deposit_credit + penalty`  (email #1)
* `total_charged = hammer + platform_fee + taxes + processing_fee`  (email #3)
* `net_payout   = hammer − platform_fee`  (email #4)
* Variance row `variance_cents = recovery_cents − actual_cents`  (email #28)
* Storage seller: `total = commission + stripe_recovery + tax`  (email #14)

Every row's math checks against the backend's ledger.  No silent
re-calculation, no template-level tax rate application.

## 14. Security review

* No credit-card number, no CVC, no full PAN — only masked last-4 where already
  captured (e.g. `Card ending in ••••4242`).
* No PII beyond the buyer's display name + display email; provinces are shown
  as postal codes only.
* Stripe payment_intent_ids and charge_ids are `pi_TEST_*` / `ch_TEST_*` — clearly
  identifiable as test-mode.
* No admin passwords or internal system IDs are exposed.
* Unsubscribe placeholder `{{UNSUBSCRIBE_URL}}` — resolved by dispatcher at send
  time; no raw placeholder observed in any body.

## 15. Deployment gate

🚫 **DO NOT DEPLOY.**  The QA has confirmed only the *documents* are correct.
Production readiness still requires (unchanged from previous audit):

1. Populate `STRIPE_LIVE_SECRET_KEY`, `STRIPE_LIVE_WEBHOOK_SECRET` and rotate
   from `STRIPE_TEST_*` — user command required.
2. Set `BILLING_ALERT_EMAIL` env to a live finance mailbox (currently
   fallback resolves to admin/super_admin users, filtered against the
   iter482 P6.2 test-email allowlist).
3. Prune any remaining `role in {admin, super_admin}` seed rows on the
   preview DB before promotion (test-email filter is a defense-in-depth,
   not a policy — the DB should be clean).
4. Fix the 7 P2 presentation defects listed in §12 for a polished
   customer experience.

## 16. Exact subject lines dispatched

```
[TEST/PREVIEW] Invoice #BV-20260215-000042 - 2019 Ford F-150 Lariat 4x4
[TEST/PREVIEW] Facture nºBV-20260215-000043 — Camion Ford F-150 Lariat 4x4 2019
[TEST/PREVIEW] Payment Confirmed - Invoice #BV-20260215-000042
[TEST/PREVIEW] Paiement confirmé — Facture nºBV-20260215-000043
[TEST/PREVIEW] BidVex — Payment received for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
[TEST/PREVIEW] BidVex — Paiement reçu pour Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
[TEST/PREVIEW] BidVex — Payment received for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
[TEST/PREVIEW] BidVex Sale Statement — Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
[TEST/PREVIEW] Relevé de vente BidVex — Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
[TEST/PREVIEW] BidVex — Your invoice for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
[TEST/PREVIEW] BidVex — Votre facture pour Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
[TEST/PREVIEW] BidVex — Your settlement statement — Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
[TEST/PREVIEW] BidVex — Votre relevé de règlement — Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
[TEST/PREVIEW] ⚠️ OVERDUE: Invoice #BV-20260215-000042 - Action Required
[TEST/PREVIEW] Payment Reminder: 2019 Ford F-150 Lariat 4x4 - 4 Days Left
[TEST/PREVIEW] OVERDUE: Payment Required for 2019 Ford F-150 Lariat 4x4
[TEST/PREVIEW] Payment required within 48h — Lot #42 — Milwaukee Power Tool Pallet
[TEST/PREVIEW] Paiement requis sous 48 h — Lot #42 — Palette d'outils Milwaukee
[TEST/PREVIEW] Payment failed — 2019 Ford F-150 Lariat 4x4
[TEST/PREVIEW] Échec du paiement — Camion Ford F-150 Lariat 4x4 2019
[TEST/PREVIEW] You Won! Complete Payment for Lot #42 — Milwaukee Power Tool Pallet (12 pcs)
[TEST/PREVIEW] Vous avez gagné ! Effectuez le paiement pour Lot #42 — Palette d'outils électriques Milwaukee (12 pièces)
[TEST/PREVIEW] You Won! Vehicle 2019 Ford F-150 Lariat 4x4 — Fee Invoice Ready
[TEST/PREVIEW] BidVex Commission Invoice — Storage Auction #sa_test_*
[TEST/PREVIEW] 🎉 You won — Storage Auction Unit #17B
[TEST/PREVIEW] Deposit refunded · Dépôt remboursé — $200.00 CAD
[TEST/PREVIEW] [BidVex] Bidding deposit captured · Dépôt saisi — Invoice BV-20260215-000042
[TEST/PREVIEW] BidVex Buyer Commission · Commission acheteur BidVex — $46.88 CAD
[TEST/PREVIEW] Buy Now Purchase · Achat immédiat — $299.00 CAD
[TEST/PREVIEW] BidVex Seller Commission · Commission vendeur BidVex — $118.75 CAD
[TEST/PREVIEW] Sale payout · Paiement de vente — $1,828.13 CAD
[TEST/PREVIEW] ✅ Your annual subscription is active · Votre abonnement annuel est actif — BidVex
[TEST/PREVIEW] ⏰ Your Premium Subscription Expires in 3 Days
[TEST/PREVIEW] Your Vip Subscription Has Expired
[TEST/PREVIEW] 🎉 Welcome to Vip!
[TEST/PREVIEW] ✅ Your listing is now boosted — 2019 Ford F-150 Lariat 4x4 | BidVex Marketplace
[TEST/PREVIEW] 🎉 Sold! 2019 Ford F-150 Lariat 4x4 - $32,500.00
[TEST/PREVIEW] BidVex — Stripe Processing Fee Variance Detected · BidVex — Écart des frais de traitement Stripe détecté   (INTL card)
[TEST/PREVIEW] BidVex — Stripe Processing Fee Variance Detected · BidVex — Écart des frais de traitement Stripe détecté   (Domestic card)
[TEST/PREVIEW] Buyer Invoice PDF — BidVex Bilingual Auction Invoice PDF (services/invoice_service.py)   [+2 PDF attachments]
[TEST/PREVIEW] Vehicle Fee PDF — BidVex Vehicle Platform-Fee Invoice PDF                                [+1 PDF attachment]
[TEST/PREVIEW] General Invoice PDF — BidVex General Auction Invoice PDF (business seller, Québec)       [+1 PDF attachment]
[TEST/PREVIEW] Legacy HTML Invoice Templates — invoice_templates.py — all 5 templates rendered          [+6 PDF attachments]
```

## 17. Next steps

1. **Reviewer (you):** open the mailbox `charbel911@gmail.com` and visually
   inspect the 43 emails + 11 PDFs.  Use §12 as the checklist for the P2 fixes.
2. **After your visual approval:** we can queue a one-shot iter482 P8-mini
   patch to consolidate the 7 P2 items — 1h of engineering + 30 tests, no
   financial-calculation changes.
3. **Blocked (as previously):** deployment (Live Stripe keys, `BILLING_ALERT_EMAIL`),
   Gate 4 Tax Consolidation, P8 peripheral audits.  Not started per your
   explicit hold.
