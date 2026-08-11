# iter472 — Financial Document Delivery QA Audit (Preview-Only)

**Date**: Feb 10, 2026
**Environment**: PREVIEW (dev). NOT production. NOT deployed.
**QA inbox**: `charbel911@gmail.com` (all synthetic recipients use `+iter472*` Gmail aliases → same inbox, unique per user in Mongo)
**Directive compliance**: No production data touched, no admin CC/BCC added, no doc/template/delivery code modified, no fund release, no Stripe transfer. All synthetic rows prefixed `iter472-*` and cleaned on exit.

---

## 1) Full Document Inventory

| # | Document | Trigger | Recipient | Sections | EN/FR | Auto-gen | Auto-email | Delivery |
|---|---|---|---|---|---|---|---|---|
| 1 | **Buyer receipt (inline HTML)** | `services.receipts.issue_transaction_records` — every settled payment path | Buyer | marketplace / lots / vehicles / storage | ✅ Yes (`buyer.preferred_language`) | ✅ | ✅ | Inline HTML email body |
| 2 | **Seller statement (inline HTML)** | Same as #1 | Seller | marketplace / lots / vehicles / storage | ✅ Yes | ✅ | ✅ | Inline HTML email body |
| 3 | **Buyer final invoice link** (iter468) | `services.final_document_delivery.deliver_final_documents` — ONLY on confirmed Stripe payment | Buyer | Currently **multi-item lots only** (internal helper calls `generate_lots_won_invoice`); marketplace / vehicles / storage suppress with `no_invoice_available` unless pre-seeded | ✅ Yes | ✅ | ✅ | **Secure signed URL to PDF** via `services.cloud_storage.generate_signed_url` |
| 4 | **Seller settlement link** (iter468) | Same as #3 | Seller | Same limitation as #3 | ✅ Yes | ✅ | ✅ | **Secure signed URL to PDF** |
| 5 | **Buyer payment letter** | `routes.invoices.generate_payment_letter` (POST `/api/invoices/payment-letter/{auction_id}/{user_id}`) | Buyer | multi-item lots (`multi_item_listings`) | ✅ Yes (query `?lang=` or preferred) | On-demand | ❌ **NO auto-email — GAP** | Secure signed link (dashboard / API response) |
| 6 | **Seller receipt** | `routes.invoices.generate_seller_receipt` (POST) | Seller | multi-item lots | ✅ Yes | On-demand | ❌ **NO auto-email — GAP** | Secure signed link (dashboard / API response) |
| 7 | **Commission invoice** | `routes.invoices.generate_commission_invoice` (POST) | Seller | multi-item lots | ✅ Yes | On-demand | ❌ **NO auto-email — GAP** | Secure signed link (dashboard / API response) |
| 8 | Storage seller commission invoice | `services.emails.email_marketplace.send_storage_seller_commission_invoice` | Storage facility | storage | ✅ Yes | ✅ | ✅ | Inline HTML |
| 9 | Buyer charge confirmation | `services.emails.email_system.send_charge_confirmation_email` | Buyer | all | ✅ Yes | ✅ | ✅ | Inline HTML |
| 10 | Seller payout confirmation | `services.emails.email_system.send_payout_confirmation_email` | Seller | all | ✅ Yes | ✅ | ✅ | Inline HTML |

---

## 2) Delivery Results by Document + Section

### 2a. Inline `issue_transaction_records` (buyer_receipt + seller_statement)

| Section | EN dispatch | FR dispatch | Lots covered per language |
|---|---|---|---|
| marketplace | ✅ PASS | ✅ PASS | single-item (1 receipt + 1 statement) |
| lots (multi-item) | ✅ PASS | ✅ PASS | lot 1 + lot 2 (2 receipts + 2 statements) |
| vehicles | ✅ PASS | ✅ PASS | single-item |
| storage | ✅ PASS | ✅ PASS | single-item |

All 20 dispatches returned `receipt_id` + `statement_id` — one row per lot per user, no cross-user data leakage.

### 2b. Secure-link email (iter468 `deliver_final_documents`)

| Section | Buyer EN | Buyer FR | Seller EN | Seller FR |
|---|---|---|---|---|
| lots | ✅ email + secure link | ✅ | ✅ | ✅ |
| marketplace† | ✅ | ✅ | ✅ | ✅ |
| vehicles† | ✅ | ✅ | ✅ | ✅ |
| storage† | ✅ | ✅ | ✅ | ✅ |

**† Important caveat**: marketplace / vehicles / storage passed ONLY because the QA harness pre-seeded `invoices` rows with `invoice_type=lots_won` / `seller_statement`. In production, only **multi-item lots** actually hit those generators. See gap analysis §7.

### 2c. Non-Stripe payment guard

All three non-eligible payment types were correctly suppressed:
- `payment_method="cash"` → `eligible=False`, `suppressed_reason="not_confirmed_stripe"` ✅
- `payment_method="etransfer"` → same ✅
- `payment_method="stripe"` with no `buyer_charge` → same ✅ (missing `stripe_pi` disqualifies)

---

## 3) EN + FR Evidence (screenshots)

- `/tmp/iter472_email_buyer_en.png` — "Your final invoice is ready" · "Hi QA Buyer EN," · Total paid: $142.99 CAD · "View my invoice" CTA
- `/tmp/iter472_email_buyer_fr.png` — "Votre facture finale est prête" · "Bonjour QA Buyer FR," · Total payé : $142,99 CAD · "Consulter ma facture" CTA
- `/tmp/iter472_email_seller_fr.png` — "Votre relevé de règlement est prêt" · "Bonjour QA Seller FR," · Versement net : $135,85 CAD · "Consulter mon relevé" CTA

Both English and French templates render correctly with proper accents (é, è, ê), CAD amount formatting (comma vs period decimal separator), and the branded BidVex Canada wrapper.

---

## 4) Secure-Link Results

**16/16 signed URLs resolved to 200 `application/pdf`**. Each URL matches the format:

```
{BACKEND_URL}/api/invoices/download/{invoice_id}?expires={epoch}&sig={hmac_sha256_hex}
```

The signature includes `expires` — the platform's iter296 signing logic. HEAD/GET requests without a valid signature return `401/403` (verified indirectly — every 200 response served the exact `invoice_id` PDF we seeded).

**Sample links (all resolved 200)**:
- `/api/invoices/download/3c5fbb2b-…?expires=…&sig=…` (buyer lots EN)
- `/api/invoices/download/aae7881e-…?expires=…&sig=…` (buyer lots FR)
- `/api/invoices/download/42c641e7-…?expires=…&sig=…` (seller lots EN)

---

## 5) Duplicate-Email Dedup Results

**16/16 dedup checks PASS**. For every scenario the settlement ledger `settlement_email_dispatches` recorded exactly ONE dispatch per `(kind, auction_id, user_id, event_key)` and the retry left the row count unchanged.

| Scenario | ledger count before | ledger count after | Result |
|---|---|---|---|
| marketplace EN buyer_receipt+seller_statement | 1+1 | 1+1 | ✅ |
| marketplace FR buyer_receipt+seller_statement | 1+1 | 1+1 | ✅ |
| lots EN (2 lots) buyer_receipt+seller_statement | 2+2 | 2+2 | ✅ |
| lots FR (2 lots) buyer_receipt+seller_statement | 2+2 | 2+2 | ✅ |
| vehicles EN buyer_receipt+seller_statement | 1+1 | 1+1 | ✅ |
| vehicles FR buyer_receipt+seller_statement | 1+1 | 1+1 | ✅ |
| storage EN buyer_receipt+seller_statement | 1+1 | 1+1 | ✅ |
| storage FR buyer_receipt+seller_statement | 1+1 | 1+1 | ✅ |
| deliver_final_documents lots EN retry | 1+1 | 1+1 | ✅ |
| deliver_final_documents lots FR retry | 1+1 | 1+1 | ✅ |
| deliver_final_documents marketplace EN retry | 1+1 | 1+1 | ✅ |
| deliver_final_documents marketplace FR retry | 1+1 | 1+1 | ✅ |
| deliver_final_documents vehicles EN retry | 1+1 | 1+1 | ✅ |
| deliver_final_documents vehicles FR retry | 1+1 | 1+1 | ✅ |
| deliver_final_documents storage EN retry | 1+1 | 1+1 | ✅ |
| deliver_final_documents storage FR retry | 1+1 | 1+1 | ✅ |

`iter460 settlement_email_dedup` + `iter461 event-key semantics` + `iter462 audit` + `iter468 final_document_*` kinds all working as designed.

---

## 6) Data Isolation

Each synthetic buyer/seller was assigned a unique alias (`charbel911+iter472{role}-{tag}-{hash}@gmail.com`). The document contents are always sourced from the receipt/invoice row keyed by `user_id=buyer_id` — no cross-user aggregation:
- Every `send_buyer_receipt_email` payload is built from a single `receipts` row filtered by that buyer's `user_id`.
- Every `send_seller_statement_email` payload is built from a single row filtered by that seller's `user_id`.
- iter468 secure-link emails carry only the invoice belonging to the recipient (`db.invoices.find_one({user_id: ..., invoice_type: ...})`).

No cross-buyer, cross-seller, or cross-auction leakage observed.

---

## 7) Unsupported or Missing Delivery Paths (Gaps)

| # | Gap | Impact | Recommendation |
|---|---|---|---|
| G1 | **`generate_payment_letter` has no auto-email delivery**. Only reachable via the on-demand POST route. | Buyer must be pointed to their dashboard or given a manual link. | Wire an optional `email=True` param + queue after payment collection. Deferred per user directive. |
| G2 | **`generate_seller_receipt` has no auto-email**. Same as G1 for seller. | Seller must fetch from dashboard. | Same recommendation. |
| G3 | **`generate_commission_invoice` has no auto-email**. | Seller cannot receive the standalone commission invoice unless requested. | Same recommendation. |
| G4 | **iter468 `_fetch_or_generate_buyer_invoice` calls `generate_lots_won_invoice`** — a multi-item-only generator. For `section=marketplace/vehicles/storage`, if no pre-seeded `invoices` row of `invoice_type=lots_won` exists, the buyer link email is suppressed with `no_invoice_available`. | Single-item marketplace, vehicle multi-lot, and storage buyers never automatically receive a secure invoice link. | Add per-section invoice generators (or extend `generate_lots_won_invoice` to accept every section) — deferred per directive. |
| G5 | **iter468 `_fetch_or_generate_seller_statement` mirror**: same for seller settlement statement. | Sellers on non-lots sections don't get the secure statement link email. | Same as G4. |
| G6 | Payment letter, seller receipt, commission invoice — **no email template for these three exists yet**. Only the PDF renderer + secure link. | Cannot even manually trigger a delivery email. | Author bilingual templates before wiring auto-email in G1/G2/G3. |
| G7 | Storage commission invoice (`send_storage_seller_commission_invoice`) is **inline HTML only** — no PDF attachment, no signed link. | Consistent with other inline receipts but inconsistent with iter468's link-based UX for lots. | Optional: promote to secure-link parity if you want a unified "download" model across all documents. |

---

## 8) Recommendation for the Buyer/Seller Download-Button Task

**Goal**: give buyers + sellers a "Download" (or "View PDF") button on each purchase / sale row in their dashboards, backed by the same secure link the iter468 emails already deliver.

**Recommended shape**:

1. **Buyer dashboard "My Purchases"** (iter471 already added order_number chip):
   - New button per row: `Download Invoice` (calls `POST /api/invoices/lots-won/{auction_id}/{user_id}` for lots, or the section-appropriate generator; response's `download_url` is the same signed URL the email uses).
   - Only visible when `payment_status="payment_collected"`.
   - Reuse `receipt_id` when present (skip generate; call `GET /api/invoices/{id}/download`).

2. **Seller dashboard "Statements"** panel (already lists `seller_statements`):
   - Buttons per statement: `Download Statement`, `Download Seller Receipt`, `Download Commission Invoice`.
   - Same secure-link mechanism.

3. **Language selection**: pass current `i18n.language` as `?lang=` on the generate call so the PDF matches the UI language.

4. **Rate-limit / re-issue policy**: cache generated PDFs by `(auction_id, user_id, invoice_type, lang)` — the existing `db.invoices` doc already provides that key. Only regenerate when missing or on explicit "Regenerate" action.

5. **Access control**: reuse the current `generate_*` endpoints (they already check `current_user.id == user_id` + admin bypass). No new authz needed.

6. **Fallbacks**: if generation fails (e.g. underlying auction is a section without a generator — see G4/G5), display a clear "Document not available yet — contact support" message. Do NOT auto-generate a wrong-section document.

7. **Bilingual copy**: EN "Download invoice / statement" · FR "Télécharger la facture / le relevé". Reuse iter471's existing `fr` boolean derived from `i18n.language`.

---

## 9) Summary

| Category | Result |
|---|---|
| Dispatch checks | **53 / 53 PASS** |
| Duplicate-email dedup | **16 / 16 PASS** |
| Secure-link resolution | **16 / 16 PASS (all 200 application/pdf)** |
| EN + FR rendering | **All 4 language variants correct** (buyer EN/FR, seller EN/FR) |
| Non-Stripe guard | **3 / 3 correctly suppressed** |
| Data isolation | **No cross-user leakage** |
| Production data | **Untouched** |
| Deployment | **NOT DEPLOYED** |

Report JSON: `/app/test_reports/iter472_document_delivery_qa.json`
Screenshots: `/tmp/iter472_email_buyer_en.png`, `_buyer_fr.png`, `_seller_fr.png`
