# iter475 — Full PDF Generation Engines for All Sections & Roles

**Prepared**: Feb 2026
**Status**: ✅ **COMPLETE — 62/62 backend tests pass, UI verified**
**Scope**: Close every previously-unsupported document gap (G1–G5) from the iter474 audit by building real PDF generators, wiring them to the dashboard availability endpoints, and reconciling every generated total against the persisted settlement receipts.
**Not deployed** — preview only.

---

## 1) What was built

### Shared PDF helper module
- **`services/pdf_generators/common.py`** — `DocumentSpec` + `render_document` + settlement readers (`load_receipt`, `load_receipts_for_buyer`, `load_receipts_for_seller`) + `sum_field` (pure sum, no recomputation).
- **`services/pdf_generators/universal_receipt.py`** — one PDF template renders a BidVex buyer receipt for any of the 4 sections (marketplace / lots / vehicles / storage), aggregating multi-lot rows into an order-level receipt.
- **`services/pdf_generators/sections.py`** — nine section-specific generators (marketplace / vehicles / storage × statement + receipt + commission invoice) + storage buyer invoice.

### Fetch-or-generate helper (`routes/dashboard.py`)
`_fetch_or_generate_invoice(...)` — checks `db.invoices` by `(invoice_type, owner_id, listing_id[, lot_number])`. If cached, returns the existing signed URL (**idempotent — no duplicate PDF regeneration**). Otherwise calls the requested generator, stores the PDF via `cloud_storage.store_invoice_pdf`, persists a new `db.invoices` row, and returns the signed URL.

### Endpoint wiring (existing endpoints — no new routes)
- `GET /api/dashboard/documents/purchase` now auto-generates the **storage buyer invoice** and the **universal receipt** (for all four sections) on first hit.
- `GET /api/dashboard/documents/sale` now auto-generates **marketplace / vehicles / storage seller statement + receipt + commission invoice** on first hit. Multi-lot `lots` section continues to use the pre-existing legacy generator (unchanged).

### Frontend
- **No changes required.** The existing `DocumentsPopover` already flips a document row from disabled to active when the backend returns `available: true`.

---

## 2) Guardrails honoured

| Guarantee | How enforced |
|---|---|
| **No new math** | Every dollar figure in every new PDF is read verbatim from `db.receipts` via `sum_field` (pure sum) or per-row projection. No fee/tax/commission recomputation. |
| **Reconciliation** | Every PDF's TOTAL row equals the corresponding `db.receipts` field summed (verified below). |
| **Owner-only** | Buyer endpoint requires `db.receipts.type=buyer_receipt` scoped to `current_user.id`. Seller endpoint requires `db.receipts.type=seller_statement` scoped to `current_user.id` **plus** matching `seller_id` on the listing (for `lots`/`vehicles`). |
| **Cross-user 403** | Buyer B → 403 on Buyer A's row (verified). Seller B → 403 on Seller A's sale (verified). |
| **Bilingual EN/FR** | `?lang=en\|fr` on both endpoints; language cached with the invoice row so re-download always returns the language it was first generated in. |
| **Signed URL** | Every download is generated via existing `services.cloud_storage.generate_signed_url` (absolute HTTPS, `expires + sig`, 15-min expiry, no localhost, no relative paths). |
| **Idempotent** | Repeated requests for the same document return the same `invoice_id`. |
| **No email / payment / Stripe / escrow / fees / taxes / production writes** | All changes are read-only against the settlement domain; the only new writes are cached PDFs into `db.invoices`. |

---

## 3) Verification — 62/62 pass

Report: `/app/test_reports/iter475_new_pdf_generators.json`
Script: `/app/backend/tests/live_verify_iter475_new_pdf_generators.py`

### Availability matrix (before → after)

| Section | Role | Doc kind | Before iter475 | After iter475 |
|---|---|---|---|---|
| Storage | Buyer | Invoice | ❌ Not available | ✅ `storage_buyer_invoice` |
| Marketplace | Buyer | Receipt | ❌ | ✅ `universal_receipt_marketplace` |
| Lots | Buyer | Receipt | ❌ | ✅ `universal_receipt_lots` |
| Vehicles | Buyer | Receipt | ❌ | ✅ `universal_receipt_vehicles` |
| Storage | Buyer | Receipt | ❌ | ✅ `universal_receipt_storage` |
| Marketplace | Seller | Statement | ❌ | ✅ `mkt_seller_statement` |
| Marketplace | Seller | Seller Receipt | ❌ | ✅ `mkt_seller_receipt` |
| Marketplace | Seller | Commission Invoice | ❌ | ✅ `mkt_commission_invoice` |
| Vehicles | Seller | Statement | ❌ | ✅ `veh_seller_statement` |
| Vehicles | Seller | Seller Receipt | ❌ | ✅ `veh_seller_receipt` |
| Vehicles | Seller | Commission Invoice | ❌ | ✅ `veh_commission_invoice` |
| Storage | Seller | Statement | ❌ | ✅ `sto_seller_statement` |
| Storage | Seller | Seller Receipt | ❌ | ✅ `sto_seller_receipt` |
| Storage | Seller | Commission Invoice | ❌ | ✅ `sto_commission_invoice` |

Every one of the 14 previously-missing PDFs now returns **HTTP 200 `application/pdf`** with `%PDF-` magic bytes.

### Financial reconciliation (extracted from generated PDFs via pypdf)

| PDF | Reconciles against | Verified value |
|---|---|---|
| Marketplace buyer receipt | `Σ receipts.total_charged` | 120.00 ✅ |
| Lots buyer receipt | `Σ receipts.total_charged` (3 lots) | 360.00 ✅ |
| Vehicles buyer receipt | `Σ receipts.total_charged` | 120.00 ✅ |
| Storage buyer receipt | `Σ receipts.total_charged` | 120.00 ✅ |
| Marketplace seller statement | `Σ receipts.net_payout` | 95.00 ✅ |
| Vehicles seller statement | `Σ receipts.net_payout` | 95.00 ✅ |
| Storage seller statement | `Σ receipts.net_payout` | 95.00 ✅ |

Reconciliation for the multi-lot `seller_statement` was skipped because that section uses the pre-existing legacy generator (unchanged in iter475).

### Cross-user + idempotency

| Test | Result |
|---|---|
| Buyer B → Buyer A's storage row → 403 | ✅ |
| Seller B → Seller A's storage sale → 403 | ✅ |
| Repeated request for same storage buyer invoice returns same `invoice_id` | ✅ |
| Signed URL is absolute HTTPS, no localhost, ends in `/api/invoices/download/{id}?expires=…&sig=…` | ✅ |
| Click-through returns `200 application/pdf` with `%PDF-` magic | ✅ (28/28 across every generated document) |

### UI verification (screenshots inline in conversation)

- **Buyer Storage popover** — Invoice + Universal Receipt both active with real invoice numbers (BV-STORAG-… + BV-UNIVER-…), Payment Letter correctly stays "Non disponible pour le moment" (per audit: payment letters exist only for multi-lot orders).
- **Seller Historical settlement popover** — Statement + Seller Receipt + Commission Invoice all active (BV-STO_SE-* / BV-STO_CO-* invoice numbers). This is exactly the row the user's screenshot flagged as "Not available yet".

---

## 4) Files changed / added

| File | Change |
|---|---|
| `backend/services/pdf_generators/__init__.py` | NEW — package marker |
| `backend/services/pdf_generators/common.py` | NEW — `DocumentSpec` + `render_document` + settlement readers + `sum_field` |
| `backend/services/pdf_generators/universal_receipt.py` | NEW — universal buyer receipt for all 4 sections |
| `backend/services/pdf_generators/sections.py` | NEW — storage buyer invoice + 9 seller PDF generators |
| `backend/routes/dashboard.py` | Added `_fetch_or_generate_invoice` helper; wired new PDFs into `/documents/purchase` and `/documents/sale` |
| `backend/tests/live_verify_iter475_new_pdf_generators.py` | NEW — 62-test verification harness |
| `test_reports/iter475_new_pdf_generators.json` | Test results (62/62 pass) |
| `test_reports/iter475_new_pdf_generators_report.md` | This report |

---

## 5) Note on the deployed environment

The current deployment (`https://launchapp-4-r-1774886029.emergent.host`) still reports "Not available yet" for these documents. This iteration is preview-only. **Redeploy required** to push the fix to production.

🛑 **Not deployed. Preview only.**
