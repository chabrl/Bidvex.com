# iter474 — Dashboard Financial-Document Access (Preview Verification)

**Prepared**: Feb 2026
**Scope**: Dashboard-only wire-up for **existing** buyer & seller financial documents. No new generators, no auto-email flows, no changes to PDF contents / payments / Stripe / escrow / fees / taxes / production data / deployment.
**Environments**:
- Preview backend: `https://prod-verify-2.preview.emergentagent.com`
- **Not deployed.** No production writes.

---

## 1) Supported-Document Matrix (Step 1 audit — mandatory)

Discovered by inspecting: `services/final_document_delivery.py`, `services/receipts.py`, `services/cloud_storage.py`, `services/pdf_invoice.py`, `services/invoice_generator.py`, `routes/invoices.py`, `routes/receipts.py`, `routes/webhooks.py`, and `iter472_document_delivery_qa_report.md`.

### Buyer documents

| Section | Invoice (PDF) | Buyer Receipt | Payment Letter |
|---|---|---|---|
| **marketplace** (single-item) | ✅ `db.invoices.type=marketplace_purchase` (auto on Stripe webhook — buyer_id, listing_id) | ⚠ JSON row only in `db.receipts` — no PDF renderer wired → **Not available yet** | ❌ No generator wired for section |
| **lots** (multi_item_listings, multi-lot) | ✅ `db.invoices.invoice_type=lots_won` (order-level, ONE PDF covers all lots — labelled "Order Invoice") | ⚠ JSON row only → **Not available yet** | ✅ `db.invoices.invoice_type=payment_letter` (order-level) |
| **vehicles** (vehicle_listings, multi-lot) | ✅ `db.invoices.invoice_type=vehicle_fees` (auto on Stripe webhook — buyer_id, auction_id) | ⚠ JSON row only → **Not available yet** | ❌ No generator wired for section |
| **storage** (storage_auctions) | ❌ No PDF generator wired for section → **Not available yet** | ⚠ JSON row only → **Not available yet** | ❌ No generator wired for section |

### Seller documents

| Section | Statement (PDF) | Seller Receipt (PDF) | Commission Invoice (PDF) |
|---|---|---|---|
| **marketplace** | ❌ No generator | ❌ No generator | ❌ No generator |
| **lots** (multi_item_listings) | ✅ `db.invoices.invoice_type=seller_statement` (order-level, labelled "Settlement Statement") | ✅ `db.invoices.invoice_type=seller_receipt` | ✅ `db.invoices.invoice_type=commission_invoice` |
| **vehicles** | ❌ No seller-side generator wired | ❌ | ❌ |
| **storage** | ❌ | ❌ | ❌ |

### Gaps (documented — NOT implemented)

| Gap | Detail |
|---|---|
| G1 | Buyer receipt PDF renderer does not exist for any section — `db.receipts` rows are JSON only. Rendered as "Not available yet" everywhere. |
| G2 | Buyer payment letter does not exist for marketplace / vehicles / storage. Only multi-lot orders receive one. |
| G3 | Vehicle seller statement / receipt / commission-invoice PDFs are not generated. |
| G4 | Marketplace seller statement / receipt / commission-invoice PDFs are not generated. |
| G5 | Storage section has no PDF generators at all (buyer or seller). |

No new generators were introduced to fill these gaps — the popover surfaces exactly what already exists.

---

## 2) New API endpoints (read-only wrappers)

Both live under `routes/dashboard.py` and use the **existing** `db.invoices` corpus + the **existing** `services.cloud_storage.generate_signed_url` (absolute HTTPS, expires + sig, no localhost, no relative paths).

### `GET /api/dashboard/documents/purchase?section&listing_id&lot_number`

Ownership gates (both must pass before any signed URL is generated):
1. `db.receipts.find_one({user_id: current_user.id, type: "buyer_receipt", section, listing_id, [lot_number]})` — the buyer must actually own a paid receipt for this row (403 otherwise, no information disclosure).
2. The candidate PDF in `db.invoices` must carry `buyer_id == current_user.id` (or `user_id`) — document-level gate.

Response shape:
```json
{
  "section": "lots", "listing_id": "…", "lot_number": 1, "multi_lot": true,
  "documents": {
    "invoice":        {"available": true,  "signed_url": "https://…", "label_key": "order_invoice",  "invoice_number": "BV-INV-…"},
    "receipt":        {"available": false, "reason": "not_supported_for_section"},
    "payment_letter": {"available": true,  "signed_url": "https://…", "label_key": "payment_letter", "invoice_number": "BV-PL-…"}
  }
}
```

### `GET /api/dashboard/documents/sale?section&listing_id`

Ownership gates:
1. `db.receipts.find_one({user_id: current_user.id, type: "seller_statement", section, listing_id})` — 403 otherwise.
2. For section=`lots`: `db.multi_item_listings.find_one({id: listing_id}).seller_id` must match `current_user.id`.
3. Each candidate PDF in `db.invoices` must carry `user_id == current_user.id`.

Returns the same three-key shape for `{statement, seller_receipt, commission_invoice}`.

---

## 3) Preview seed (removable)

`/app/backend/tests/seed_iter474_documents_matrix.py` — writes are marked with `iter474ui_seed: True`; `--cleanup` removes exactly those.

Seeded actors:
| Role | Email | Password |
|---|---|---|
| Buyer A | `testbuyer@bidvex.com` | `TestBuyer2026!` |
| Buyer B (cross-buyer) | `iter474_buyer_b@test.com` | `IterTestPwd!123` |
| Seller A | `testseller@bidvex.com` | `TestSeller2026!` |
| Seller B (cross-seller) | `iter474_seller_b@test.com` | `IterTestPwd!123` |

Seeded rows:
- Marketplace: 1 paid listing (Buyer A ← Seller A). Buyer PDF `marketplace_purchase`.
- Multi-lot: 1 auction, 3 lots (Buyer A wins all 3, Seller A). One shared order-level `lots_won` PDF + `payment_letter` PDF + seller `statement`+`receipt`+`commission_invoice` PDFs.
- Vehicle multi-lot: 1 auction, Lot #1 sold to Buyer A. Buyer `vehicle_fees` PDF only.
- Storage: 1 auction (Buyer A ← Seller A). No PDFs (per audit gap G5).

Removal: `python3 /app/backend/tests/seed_iter474_documents_matrix.py --cleanup`

---

## 4) Automated verification — 18/18 pass

Script: `/app/backend/tests/live_verify_iter474_dashboard_documents.py`
Report: `/app/test_reports/iter474_dashboard_documents.json`

| # | Test | Result |
|---|---|---|
| T1[marketplace] | Buyer A → invoice available, receipt+payment_letter unavailable | ✅ |
| T1[lots] | Buyer A → invoice + payment_letter available, receipt unavailable, label_key=`order_invoice`, `multi_lot=true` | ✅ |
| T1[vehicles] | Buyer A → invoice available, receipt+payment_letter unavailable | ✅ |
| T1[storage] | Buyer A → all three `not_supported_for_section` | ✅ |
| **T2** | Multi-lot lots 1/2/3 → **all 3 rows return the SAME order-level invoice_id** (no duplicate PDFs) | ✅ |
| **T3** | Cross-buyer: Buyer B → 403 on Buyer A's row | ✅ |
| **T4** | Cross-role: Buyer A calling seller endpoint → 403 | ✅ |
| T5 | Seller A lots → all three PDFs available, label_key=`settlement_statement`, multi_lot=true | ✅ |
| T5b[marketplace] | Seller A marketplace → 200, all three unavailable (gap G4) | ✅ |
| T5b[vehicles] | Seller A vehicles → 200, all three unavailable (gap G3) | ✅ |
| T5b[storage] | Seller A storage → 200, all three unavailable (gap G5) | ✅ |
| **T6** | Cross-seller: Seller B → 403 on Seller A's sale | ✅ |
| T7a | Signed URL is absolute HTTPS, no localhost/127.0.0.1, ends in `/api/invoices/download/{id}?expires=…&sig=…` | ✅ |
| T7b | Click-through → 200 `application/pdf` | ✅ |
| **T8** | Expired `expires` timestamp → 403 | ✅ |
| **T9** | Forged / wrong signature → 403 | ✅ |
| T10[en] | EN request → `order_invoice` label_key | ✅ |
| T10[fr] | FR request → `order_invoice` label_key (labels rendered client-side) | ✅ |

---

## 5) UI verification (screenshots inline in conversation)

**Buyer dashboard — Multi-lot Documents popover (FR)**
- "Télécharger la fact[ure de commande]" → available (BV-INV-…) — Order Invoice label
- "Télécharger [le reçu]" → strikethrough "Non disponible pour le moment"
- "Télécharger la lettre [de paiement]" → available (BV-PL-…)
- Footer note: **"Ce document couvre plusieurs lots de la même commande."**

**Buyer dashboard — Vehicle Documents popover (FR)**
- "Télécharger la fact[ure de commande]" → available (BV-VEH-…)
- "Télécharger [le reçu]" → strikethrough Not available yet
- "Télécharger la lettre [de paiement]" → strikethrough Not available yet

**Seller dashboard — Multi-lot Documents popover (FR)**
- "Télécharger le rele[vé de règlement]" → available (BV-STMT-…) — Settlement Statement label
- "Télécharger le reç[u du vendeur]" → available (BV-RCPT-…)
- "Télécharger la fac[ture de commission]" → available (BV-COMM-…)
- Footer note: **"Ce document couvre plusieurs lots de la même commande."**

Data-testid coverage: `documents-btn-{outcome_id|listing_id[-lot#]}`, `documents-popover-*`, `document-link-{kind}-*`, `document-unavailable-{kind}-*`, `documents-multi-lot-note-*`, `documents-error-*`.

---

## 6) Security guarantees (verified)

| Guarantee | How enforced | Verification |
|---|---|---|
| Buyer cannot receive seller docs | Seller endpoint requires `type=seller_statement` receipt owned by current_user | T4 → 403 |
| Buyer cannot receive another buyer's docs | Buyer endpoint requires `type=buyer_receipt` receipt with `user_id=current_user.id` **and** invoice `buyer_id/user_id` match | T3 → 403 |
| Seller cannot receive another seller's docs | Seller endpoint requires seller_statement receipt owned by user **and** `multi_item_listings.seller_id` match **and** invoice `user_id` match | T6 → 403 |
| Signed URL generated ONLY after ownership check | All `generate_signed_url` calls occur strictly after both gates in the endpoint | Code review + T3/T4/T6 no URLs emitted on 403 |
| No duplicate order-level PDFs | Same order → same `db.invoices` row for all lot rows | T2 → same invoice_id across lots 1/2/3 |
| No internal API path exposed | Only signed absolute HTTPS URLs shown; internal endpoint discovered via public download route only | T7a/T7b |
| No expired links usable | Signature check + expiry check on download endpoint | T8 → 403 |
| No forged signatures usable | HMAC sig check | T9 → 403 |
| No permanent public links | Every URL includes short-lived `expires` + `sig` | T7a |

---

## 7) Unsupported gaps carried forward (not implemented — deferred by directive)

- **G1** Buyer receipt PDF renderer for any section. UI displays "Not available yet / Non disponible pour le moment".
- **G2** Buyer payment letter for marketplace / vehicles / storage.
- **G3** Vehicle seller statement / receipt / commission-invoice PDFs.
- **G4** Marketplace seller statement / receipt / commission-invoice PDFs.
- **G5** Storage-section PDFs (buyer + seller).

Per user directive: no auto-email flow was invented to compensate.

---

## 8) Preview-environment note (not a code issue)

The backend runtime `APP_URL` env var currently resolves to a stale preview host (`1a5f2821-…`) different from the caller-facing preview host (`prod-verify-2.…`). The resolver correctly emits absolute HTTPS URLs — they simply point at the stale host. The T7b click-through was verified by preserving `expires + sig + invoice_id` while rewriting the host to the caller-facing preview URL (200 `application/pdf` confirmed). This is a preview-env drift, not a code correctness issue. Production will resolve through `FRONTEND_URL=https://bidvex.com` at deploy time.

---

## 9) Files changed / created (preview only, no deploy)

| File | Change |
|---|---|
| `backend/routes/dashboard.py` | Added `/documents/purchase` + `/documents/sale` endpoints; enriched lot outcomes with `section` field |
| `frontend/src/components/DocumentsPopover.js` | NEW — reusable Documents popover with EN/FR labels |
| `frontend/src/pages/BuyerDashboard.js` | Added DocumentsPopover to each paid won-item row |
| `frontend/src/pages/SellerDashboard.js` | Added DocumentsPopover to each paid/historical outcome card |
| `backend/tests/seed_iter474_documents_matrix.py` | NEW — removable preview seed (`--cleanup` supported) |
| `backend/tests/live_verify_iter474_dashboard_documents.py` | NEW — 18-test verification harness |
| `test_reports/iter474_dashboard_documents.json` | Test results (18/18 pass) |
| `test_reports/iter474_dashboard_documents_report.md` | This report |

🛑 **Not deployed.** Ready for user review.
