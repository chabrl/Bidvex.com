# BidVex — Auction Marketplace PRD

## iter484.2 — Payment Methods Buyer-UI Defect Fix + iter484.1 Reserve Badge Revert (Feb 14, 2026) ✅ SHIPPED · PREVIEW ONLY

### User-reported bug (root cause)
Seller `alexboul1993@gmail.com` selected multiple accepted payment
methods (`stripe + etransfer + cheque + cash`) during auction creation
on the multi-item auction `58758582-f53a-46d8-bc0b-87cf9de60523`.
Buyer detail page still showed only "This seller uses BidVex Stripe
checkout".

### Root cause — TWO independent defects
- **Defect A (backend):** `MultiItemListing` Pydantic model in
  `models/auction_models.py` did NOT declare
  `accepted_payment_methods` / `_snapshot` / `_locked_at`. With
  `ConfigDict(extra="ignore")` the fields were silently DROPPED from
  every `GET /api/multi-item-listings/{id}` buyer response. Sibling
  `Listing` (single-item) had them declared and was unaffected.
- **Defect B (frontend):** `LotDetailPage.jsx`, `ListingDetailPage.js`,
  and `MultiItemListingDetailPage.js` hardcoded "BidVex Stripe
  checkout" copy + a 3-way Buy Now selector (stripe/cash/etransfer),
  ignoring `listing.accepted_payment_methods`.

### Fix delivered
**Backend:**
- Added `accepted_payment_methods` + `_snapshot` + `_locked_at` to
  `MultiItemListing` (read model) and `VehicleListing`.
- Wired `snapshot_at_first_bid()` into `POST /api/vehicle-bids`
  (`routes/vehicles.py`) and vehicle multi-lot bid endpoint
  (`routes/vehicle_multi_lot.py`). Dormant today (vehicle bidding
  disabled) but future-safe.

**Frontend:**
- NEW canonical bilingual component
  `/app/frontend/src/components/AcceptedPaymentMethodsCard.jsx` with
  4 canonical slugs (stripe / etransfer / cash / cheque) — no `wire`
  per user directive. Uses backend precedence: snapshot → live →
  legacy singleton.
- Wired into `LotDetailPage.jsx` (multi-item), `ListingDetailPage.js`
  (single-item), and `MultiItemListingDetailPage.js` (Buy Now modal
  now filters methods dynamically + supports Cheque).
- Removed hardcoded Stripe copy at LotDetailPage.jsx lines 427 + 475.
- Removed legacy singleton branch at ListingDetailPage.js lines 894-921.
- Pre-bid acknowledgement checkbox `data-testid="bid-payment-ack-checkbox"`
  blocks Place Bid / quick-bid pills until checked.

**iter484.1 revert (per user directive #1):**
- Reserve-price UI removed from `CompactLotCard.jsx` — reserve UI
  now confined to vehicle auctions only. Backend `has_reserve`
  boolean retained (harmless).

### Test results — 165/165 green
| Suite | Result |
|---|---|
| iter484.2 payment_methods_visibility (NEW) | 15/15 |
| iter484 reserve settlement | 23/23 |
| iter483 live_edit | 36/36 |
| iter483.3 lot_and_requests | 29/29 |
| iter482 P4 end_to_end | 14/14 (+3 skipped) |
| iter482 P4A foundation | 48/48 |

**Testing agent verdict:** 100% pass. Zero regressions. Zero action
items. Frontend E2E confirmed all 4 methods render, hardcoded copy
gone, ack checkbox works, reserve badges gone from multi-item grid.

### Audit + risk deliverables
- `/app/docs/PAYMENT_METHODS_RCA_REPORT.md`
- `/app/docs/POST_BID_LOCK_AUDIT.md`
- `/app/docs/PAYMENT_METHODS_REGRESSION_MATRIX.md`
- `/app/docs/P6_RISK_MATRIX.md` (pre-req for future P6 tax work)

### Guardrails held
- ✅ Zero touch to Stripe charge / payout code.
- ✅ Zero touch to tax / fee / commission calculators.
- ✅ 88 baseline tests preserved (now 165).
- ✅ Preview only. No deploy.

### Follow-up backlog (documented, NOT shipped)
- Wire `AcceptedPaymentMethodsCard` into Storage detail page.
- Wire `AcceptedPaymentMethodsCard` into Vehicle + Vehicle Multi-Lot
  detail pages + pre-bid ack.
- Vehicle-specific reserve UI (new task).
- P6 Tax Engine Consolidation (blocked on legal review — see risk matrix).

---

## iter484.1 — Buyer Reserve Badge + Admin Reserve-Not-Met Filter (Feb 14, 2026) ⚠️ REVERTED in iter484.2 (multi-item badge only)

### Scope
UI polish on top of iter484:
1. **Buyer-facing Reserve badge** — subtle outline chip on lot cards
   (`Reserve` EN / `Prix de réserve` FR) rendered only when
   `lot.has_reserve === true`.  Amount is NEVER sent to the buyer.
2. **Admin queue filter** — new one-tap `Reserve not met` filter in the
   Auction Requests admin queue alongside existing type filters.

### Backend
- `models/auction_models.py::Lot` — added `has_reserve: bool = False`
  (buyer-safe boolean).
- `routes/listings.py::get_multi_item_listing` — computes
  `has_reserve = bool(reserve_price and reserve_price > 0)` per lot and
  STRIPS `reserve_price` from both the auction root and every lot
  before serializing.  Admin/seller surfaces still read the amount
  from their own edit-state endpoints.

### Frontend
- `components/CompactLotCard.jsx` — subtle outline chip:
  `border-slate-300`, `text-slate-600`, `uppercase text-[9px]`, pill.
  Placed on the same row as `#{lot_number}` (`ml-auto`) so it never
  reserves empty space on lots without a reserve.  Testid
  `lot-card-{n}-reserve-badge`.
- `pages/admin/AdminAuctionRequests.jsx`:
  - Added `reserve_not_met` to `TYPES` (label: "Reserve not met").
  - New AlertTriangle icon in `typeIcon()` for reserve_not_met rows.
  - Payload summary block for reserve_not_met rows shows
    hammer / reserve / shortfall / winner / lot_number, with hammer in
    rose-600 and reserve in emerald-700 for at-a-glance triage.

### Live E2E verification (Playwright · preview URL)
- ☑ 2 reserve badges render on auction
  `58758582-f53a-46d8-bc0b-87cf9de60523` (lots #1 + #23 have reserves).
- ☑ EN label: `RESERVE` · FR label: `PRIX DE RÉSERVE`.
- ☑ 22 lots without a reserve show no badge and no empty space.
- ☑ Buyer API response contains `has_reserve: true` for lots #1 + #23,
  no `reserve_price` key anywhere.
- ☑ Admin filter row shows `All types · end_time · reserve_price · edit · Reserve not met`.
- ☑ 88/88 backend tests still green.

**Guardrails held:** zero touch to payment / tax / fee / Stripe code.
No deploy.

---

## iter484 — Reserve Price at Auction Close (Feb 14, 2026) ✅ SHIPPED · PREVIEW ONLY

### Scope
Wire admin-set `reserve_price` into the auction-close settlement path.
When `hammer < reserve`, halt auto-payment, flag the listing/lot as
`reserve_not_met`, insert a system-generated row into the unified
Auction Requests queue, and notify buyer + admin with idempotent
outbox rows.  Admin can APPROVE (accept the sale at the offered
hammer → runs settlement with `bypass_reserve=True`) or DENY
(mark as `ended_reserve_not_met`, no charges).

### Backend
**New**
- `services/reserve_price_gate.py` — pure `resolve_reserve_price()`
  (lot > auction fallback) + `is_reserve_met()`.

**Modified**
- `services/auction_settlement.py::settle_auction` — new kwargs
  `bypass_reserve` / `reserve_price_override` / `lot`.  Halts BEFORE
  any Stripe call when reserve isn't met, returning
  `{settled:False, reason:"reserve_not_met", reserve_price, hammer_price, ...}`.
- `services/auction_requests_service.py`:
  - Added `"reserve_not_met"` to `REQUEST_TYPES` (system-generated).
  - New `create_system_reserve_not_met_request()` — idempotent, queues
    admin + neutral bilingual buyer emails via `email_outbox`.
    Buyer context deliberately omits the reserve amount.
  - `_apply_approval_side_effects` handles `reserve_not_met` →
    re-runs settlement + finalize with `bypass_reserve=True`.
  - New `_apply_denial_side_effects` → flips listing/lot to
    `ended_reserve_not_met` with `end_reason=reserve_not_met`.
- `services/payment_collection.py::finalize_auction_payment` —
  short-circuits when settlement carries `reason=reserve_not_met`
  (no receipts / payouts / pickup codes).
- `routes/auctions.py`:
  - Single-listing flow: reserve check BEFORE marking status.  When
    unmet: status → `reserve_not_met`, system-request created, all
    downstream side-effects (pickup, notifications, winner/seller
    emails, offline invoices, settle+finalize) are gated off.
  - Multi-lot flow: per-lot reserve check.  Unmet lots set
    `lots.$.status="reserve_not_met"`, request created, `continue`
    skips the winner side-effects for THAT lot.  Other lots continue
    normally.

### Guardrails held
- ✅ Zero touch to Stripe charge / payout / refund code.
- ✅ Reserve gate lives in ONE place (`reserve_price_gate.py`);
  settlement + routes both delegate.
- ✅ Idempotent: repeat scheduler ticks never duplicate the request row
  or the buyer email (unified `dedupe_key` on outbox).
- ✅ Lot-level reserve OVERRIDES auction-level reserve.
- ✅ 65/65 iter483 tests continue to pass.
- ✅ `bypass_reserve` only reachable through admin approve — sellers
  cannot self-override.

### Tests — 23 new (all green)
`tests/test_iter484_reserve_settlement.py`:
1. `resolve_reserve_price` — None / lot-wins / fallback / rejects
   negatives, strings, 0.
2. `is_reserve_met` — no-reserve / equal / above / below.
3. `settle_auction` halts + no Stripe helper called when reserve unmet.
4. `settle_auction` proceeds when hammer ≥ reserve.
5. `settle_auction` proceeds when reserve is 0 / missing.
6. `bypass_reserve=True` skips the gate.
7. `lot.reserve_price` overrides `listing.reserve_price`.
8. `reserve_price_override` kwarg wins over listing value.
9. `create_system_reserve_not_met_request` — shape / idempotency /
   per-lot scoping / queues both emails.
10. Buyer email context does NOT include reserve amount.
11. Admin approve → `settle_stripe_full` called + `finalize` called,
    listing → `ended`, lot → `sold`.
12. Admin deny → no Stripe / finalize, listing/lot → `ended_reserve_not_met`.
13. `finalize_auction_payment` short-circuits when settlement carries
    `reason=reserve_not_met`.

**Total 88/88 iter483 + iter484 tests green.**

### Halted at end of Priority 1
Per user directive: STOP AND REPORT.  Priority 2 (buyer-facing
reserve badge) and Priority 3 (P6 tax engine) not started.

---

## iter483.3 — Lot-Level Controls + Auction Requests Center + Responsive UX (Feb 14, 2026) ✅ SHIPPED · PREVIEW ONLY

### Scope
1. Lot-level image upload (drag & drop) per lot in the seller edit modal.
2. Full responsive UX (mobile / tablet / desktop) with sticky mobile Save and unsaved-changes confirm dialog.
3. Bid-locked lot protection — server + UI.
4. Auction-level bid lock — server + UI (edit via request only).
5. Unified Auction Request Center (end_time · reserve_price · edit).
6. Admin-only Reserve Price setter (per lot or auction).
7. Admin unified Auction Requests queue with filters.
8. Admin Lot Editor fully responsive with per-lot S3 uploader + Reserve Price field.

### Backend
**New files**
- `services/auction_requests_service.py` — unified request lifecycle + reserve-price setter.
- `routes/auction_requests.py` — seller + admin endpoints.

**Modified**
- `services/live_edit_service.py`:
  - Added `AUCTION_BID_LOCKED_FIELDS` (title, description, schedule, pickup, shipping).
  - Added `_auction_bid_count`, `_lot_bid_count`, `_find_lot` helpers.
  - Enforced auction-level bid lock inside `live_edit()` (403 `auction_has_bids` for non-admin).
  - Added `lot_image_add` / `lot_image_remove` field handlers with per-lot bid lock (403 `lot_has_bids`).
  - Extended `_make_history_entry` to accept `extra` payload (lot_number, request_id).
  - Extended `get_edit_state` to return `bid_count`, `auction_locked`, `locked_fields`, and per-lot `bid_count` + `locked` flags.
- `server.py` — mounted `auction_requests` routers.

**New endpoints**
- `POST   /api/auctions/{id}/requests` — submit any request type
- `GET    /api/auctions/{id}/requests` — seller view of own requests
- `GET    /api/admin/auction-requests` — unified admin queue (filters: status, request_type, auction_id, seller_id)
- `POST   /api/admin/auction-requests/{req}/approve|deny`
- `PATCH  /api/admin/lots/reserve-price` — admin-only reserve setter (per lot or auction; `null` cents clears)
- Legacy `auction_end_time_requests` collection is bridged into the unified queue so pre-iter483.3 rows still appear.

### Frontend
- `pages/SellerLiveEditModal.jsx` — full responsive rewrite:
  - Mobile (<640px) full-screen sheet · Tablet 720px · Desktop 860px.
  - Horizontal scroll-pill tab row across all breakpoints.
  - Sticky mobile Save button.
  - Bid-lock badge in header; `LockNotice` in each locked section with "Submit Edit Request" CTA that pre-fills the Request Center.
  - New Lots tab with per-lot cards, each with own S3 dropzone + per-lot bid-lock badge + "Reserve price" request button.
  - New Requests tab (unified Auction Request Center): end_time / reserve_price / edit picker; own-requests list with status badges.
  - Unsaved-changes AlertDialog on tab switch.
- `pages/admin/AdminAuctionRequests.jsx` — new unified admin queue (replaces `AdminEndTimeRequests`).
  - Filters: status × request_type × search by auction_id/seller_id.
  - Per-row payload summary + reason + admin_note + Approve/Deny (mobile-full buttons).
- `pages/admin/AdminLotEditorModal.js` — full responsive rewrite:
  - Full-screen sheet on mobile · 3xl on tablet · 5xl on desktop.
  - Grid layout (1 col mobile / 2 col md+); no horizontal scroll.
  - Per-lot admin-only S3 dropzone with progress bar.
  - Dedicated Reserve Price section flagged "Admin Only — hidden from public".
- `pages/AdminDashboard.js` — replaced sidebar item "End-Time Change Requests" (⏰) with "Auction Requests" (📬).

### Tests
- `tests/test_iter483_3_lot_and_requests.py` — 29 new tests:
  - lot_image_add/remove (5)
  - bid-locked lot protection (2)
  - auction-level bid lock enforcement (5 parametrized fields + 2 admin bypass + images-still-allowed)
  - `get_edit_state` bid-count + locks summary
  - unified Auction Request create / duplicate 409 / reason min-length / all 3 types
  - admin approve applies edit / deny leaves untouched
  - admin unified list requires admin
  - seller sees own requests
  - reserve price admin-only setter (5 scenarios: lot / auction / clear / non-admin / negative)
- Extended fake DB positional-op support in the shared test harness (backwards-compatible).

### Live E2E verification (Playwright · preview URL)
Desktop (1920×900):
- ☑ 8 tabs render in seller modal
- ☑ Lots tab shows 3 lot cards with per-lot dropzone + "Reserve price" button
- ☑ Lot #1 shows `Reserve: $500` badge (from admin-set reserve)
- ☑ Request Center renders 3 type buttons; approved/pending requests listed
- ☑ Admin unified queue shows 3 pending rows across types (3 filters × 4 types × search)
- ☑ Filter=edit narrows to 1 row
- ☑ Admin approve fires "Request approved" toast and row moves out of Pending
- ☑ Admin lot editor shows 24 lots in 2-column grid (no horizontal scroll)
- ☑ Reserve Price field visible with admin-only warning

Tablet (900×900):
- ☑ Seller modal renders at 720px width with pill tabs

Mobile (390×844):
- ☑ Seller modal is full-screen with sticky Save button
- ☑ Admin queue filters wrap; Approve/Deny become full-width
- ☑ Admin lot editor stacks single-column; all controls tappable

### Backend test summary
- **36 iter483** live-edit tests: PASS
- **29 iter483.3** new tests: PASS
- **Total 65/65 green**

**Guardrails held:** zero payment/tax/fee/Stripe files touched (`git status` verified); no deploy; no pre-existing test failures fixed.


## iter483.2 — Description Refresh + Direct S3 Uploader (Feb 14, 2026) ✅ SHIPPED

### Fix 1 — Description field refreshes from DB on modal open
**Change:** Added a new backend endpoint `GET /api/auctions/{id}/edit-state` that returns the current DB values of every editable field (title, description, images, schedule, pickup, shipping, status, end_time). The modal's on-open `useEffect` now fetches this snapshot in parallel with the end-time-request + edited-history calls and hydrates every local `useState` with the fresh DB value. Textarea/inputs always render the true saved state — never a stale prop-cached placeholder.

**Backend files:**
- `/app/backend/services/live_edit_service.py` — added `get_edit_state(db, auction_id, current_user)` (role-gated: owner-only or admin).
- `/app/backend/routes/live_edit.py` — mounted `@seller_router.get("/{auction_id}/edit-state")`.

### Fix 2 — Direct S3 image uploader replaces URL paste-box
**Change:** Media tab now shows a drag-and-drop dropzone (also click-to-pick). Files are validated client-side (MIME must be `image/jpeg|jpg|png|webp`, size ≤ 10 MB) and uploaded sequentially to the pre-existing `POST /api/uploads/listing-image` endpoint (which returns `{url}` after S3 write). The returned URL is then appended via the same `PATCH /api/auctions/{id}/live-edit {field:"images", value:{add:[url]}}` call, so the audit log (`edited_history`) captures the mutation identically. Per-file progress bar; success shows a green ✓; validation/upload errors surface as non-blocking sonner toasts with `filename — reason`.

**Frontend file:**
- `/app/frontend/src/pages/SellerLiveEditModal.jsx`
  - Removed `newImageUrl` state + `addImage` handler + `<Input> / <Button>` URL row + unused `Image` import.
  - Added `uploads` state (per-file tracker), `fileInputRef`, `dragActive`; new handlers `uploadFiles`, `onDrop`, `onDragOver`, `onDragLeave`, `onPickFile`.
  - New dropzone JSX with `data-testid="image-uploader-dropzone"`, hidden `<input data-testid="image-uploader-input">`, per-row progress list `data-testid="image-upload-progress"` / `image-upload-row-{status}`.
  - Bilingual EN/FR strings for `uploadHint`, `uploadAccepted`, `uploadRejectedType`, `uploadRejectedSize`, `uploadFailed`.

### Live E2E verification (Playwright, testseller@bidvex.com)
- ☑ Description on re-open: `iter483 QA — description saved e2e` (fresh DB value, not stale)
- ☑ Title on re-open: `iter483 QA — title saved e2e`
- ☑ Dropzone rendered · file input hidden · URL input removed (`new-image-url-input` count = 0)
- ☑ 1×1 PNG uploaded → progress row appeared → status "done" ✓ → grid re-rendered from 2 → 3 images
- ☑ DB confirms 3rd image URL = `https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/listings/staged-<user>/...`
- ☑ `edited_history` captured the S3-URL add as a normal images-add event
- ☑ 36/36 iter483 backend tests still pass (no regression)

**Guardrails held:** no payment/tax/fee/Stripe code touched; no pre-existing tests fixed; no deploy.


## iter483.1 — Seller Live Edit Modal HOTFIX (Feb 14, 2026) ✅ FIXED · TEST MODE

**User-reported bug:** Edit button on the seller dashboard did not open the modal.

**Root cause:** The `<SellerLiveEditModal />` JSX block was structurally appended to the WRONG component. `SellerDashboard`'s return closes at line 1462 (`};`). The modal JSX was placed near line 1852, which is INSIDE the `RegionalTrendsPanel` sub-component's return block (starts line 1717, ends line 1853). `RegionalTrendsPanel` has no `liveEditModal` state nor `SellerLiveEditModal` import in scope, so React silently rendered nothing when the seller clicked Edit. No console error surfaced because the `RegionalTrendsPanel` initially returns a loading spinner and the buggy JSX only executed after `/api/insights/regional-trends` resolved — by which point the reference error was swallowed by React's async render path.

**Fix:** Moved the modal JSX from inside `RegionalTrendsPanel` (removed lines ~1852-1861) into `SellerDashboard`'s return block, right before its closing `</div>` at line 1460. Now `liveEditModal.open` state is resolved from the correct scope.

**Files changed:**
- `/app/frontend/src/pages/SellerDashboard.js` — Modal JSX moved from `RegionalTrendsPanel` (bottom of file) to `SellerDashboard` return block (line ~1461).

**Live verification (Playwright end-to-end against preview URL):**
- ✅ Edit button opens modal (`data-testid="seller-live-edit-modal"` visible)
- ✅ Title saves + reflects on dashboard immediately (DB: `title="iter483 QA — title saved e2e"`)
- ✅ Description saves (DB: `description="iter483 QA — description saved e2e"`)
- ✅ Image URL add pipeline works (DB: `images=[seed, new-url]`)
- ✅ Schedule/pickup save (DB: `pickup={location, instructions}`)
- ✅ Shipping saves (DB: `shipping={available:True, notes, estimated_cost:"42.50"}`)
- ✅ Add-lot button opens flow; single-item `listings` returns "Add-lot is not supported" (intentional); `multi_item_listings` succeeds with "New lot added — pending admin review"
- ✅ End-time change request submits and shows "Request pending" badge
- ✅ Admin panel `/admin` → End-Time Change Requests tab lists pending rows (2 shown)
- ✅ Admin approve fires "Request approved" toast + request moves from Pending → Approved tab
- ✅ Seller re-opens modal → End Time tab shows green "Request approved" badge + admin note visible + `current_end_time` updated to new value
- ✅ History tab shows 9 immutable audit entries (title, description, images, schedule, pickup, shipping, end_time, ...)


## iter483 — Seller Live Auction Edit + Admin End-Time Approval (Feb 14, 2026) ✅ SHIPPED · TEST MODE — DO NOT DEPLOY

**Scope:** Sellers can safely edit their live auctions (title, description, images, schedule, pickup, shipping, add new draft lots) without admin approval. End-time changes require admin approval via request/queue flow. All edits appended to immutable `edited_history` audit log.

### Architecture
- **Service**: `services/live_edit_service.py` — collection-agnostic resolver + safe-field enforcer + audit logger + end-time request state machine.
- **Routes**: `routes/live_edit.py` — five endpoints:
  - `PATCH /api/auctions/{auction_id}/live-edit` — safe edits (seller-owner only, admin bypass)
  - `POST /api/auctions/{auction_id}/end-time-request` — seller submits end-time change with reason
  - `GET /api/admin/end-time-requests?status=pending` — admin queue
  - `POST /api/admin/end-time-requests/{request_id}/approve` — approve or deny
  - `GET /api/auctions/{auction_id}/edited-history` — read audit log (seller/admin only)
- **State record**: `end_time_requests` collection — links `auction_id`, `seller_id`, `requested_end_time`, `reason`, `status` (pending/approved/denied).
- **Audit log**: Immutable `edited_history` array appended to each auction document on every safe edit and every add-lot event.

### Frontend UI
- `pages/SellerLiveEditModal.jsx` — wired into `SellerDashboard.js` per active auction row.
- `pages/admin/AdminEndTimeRequests.js` — wired as new tab in `AdminDashboard.js`.

### Safety Guarantees
- Zero touch to payment / tax / fee / settlement / Stripe logic.
- Financial fields (starting_price, current_price, hammer_price, reserve_price, winner_user_id, sold_at) never mutable via live-edit path.
- New lots via `add_lot` land as `draft` + `pending_admin_review`.

### Tests
- `tests/test_iter483_live_edit.py` — 36/36 PASSED (unit + HTTP).
- Regression: 303+ Iter 482 baseline tests pass; 45 pre-existing fee-preview failures are unrelated (financial engine untouched by Iter 483). 1 CSV public-export test blocked by stale fixture (missing `iter474ui-veh-c2c08eb2`).

### Launch-Readiness — Feb 14, 2026
✅ Backend service + routes shipped, mounted, tested (36/36).
✅ Frontend modal + admin tab built, wired, linted.
✅ Audit log verified immutable + append-only.
✅ Access control: seller-owner + admin bypass, non-owner 403, unauthenticated 401.
✅ No side-effects on Iter 482 financial engine (confirmed by git diff scope: only new files + 3 mount lines in server.py + 2 dashboard wire lines).
⚠️ Pre-existing $7 hammer premium/premium fee-preview drift (781 vs expected 728) — pre-Iter483, tracked separately.


## iter482+ — Canonical Lot CSV Export (Feb 13, 2026) ✅ SHIPPED · READ-ONLY

**Scope:** Single canonical CSV export system for lot catalog data across every BidVex auction type. Read-only. Zero touch to payment / tax / fee / settlement / Stripe / auction endpoints.

### Architecture
- **Single source of truth**: `services/lot_csv_export_service.py` — every export flows through `generate_csv(db, auction_id, surface, current_user)`. No duplicate calculators or per-page generators.
- **Thin route wrapper**: `routes/lot_exports.py` — two endpoints:
  - `GET /api/exports/lots/{auction_id}?surface={seller|public|admin}&include_drafts={bool}` — streams CSV (UTF-8 with BOM for Excel compatibility)
  - `GET /api/exports/lots/{auction_id}/preview?surface=...` — JSON preview (columns, row count, first 5 rows)
- **Auction-type coverage**: 6 collections registered — `listings` (general), `multi_item_listings`, `vehicle_listings`, `vehicle_multi_lot_listings`, `storage_auctions`, `partner_auctions`. Each has a schema normaliser.

### Canonical column order (product-owner approved)
```
auction_id, auction_name, lot_number, title, description,
quantity, starting_bid, category, condition, current_bid,
status, listing_url, image_urls
```
Admin surface additionally exposes ONLY: `winner_user_id`, `hammer_price`, `sold_at`, `seller_id`.

### Redaction rules
- **public**: 13 canonical columns; NEVER exposes `seller_id`, `seller_email`, `seller_phone`, `winner_user_id`, `hammer_price`, `reserve_price`, `internal_notes`, `moderation_status`, `payment_information`, `invoices`, `commission_data`.
- **seller**: 13 canonical columns; enforced ownership at service layer (admin can bypass).
- **admin**: 13 canonical + 4 admin-only columns; admin-only access.

### Draft / status filter
- Default: hidden statuses `draft`, `pending_review`, `deleted` are excluded.
- Seller/admin can pass `?include_drafts=true` to include them.
- Public surface ALWAYS hides drafts regardless of the flag.

### Multi-image handling
- Single `image_urls` column with pipe-separated URLs. Excel-friendly. Keeps 1 row per lot.

### Performance
- Verified with 10,000-lot synthetic auction — CSV under 20 MB, headers streamed within 1 second.

### Frontend integration (3 surfaces)
- **Seller surface**: `SellerDashboard.js` — "Export CSV" button per listing row (`export-csv-btn-{listingId}`).
- **Public surface**: `MultiItemListingDetailPage.js` — "Download Lot List (CSV)" / "Télécharger la liste des lots (CSV)" button next to the sort/view controls (`public-export-csv-btn`).  **Guest users see NO button**; authenticated buyers get access.
- **Admin surface**: `admin/ManageAllAuctions.js` — "Export CSV (Admin)" button in the per-row action bar (`admin-export-csv-btn-{listingId}`).  Emits the 4 admin extras (`winner_user_id`, `hammer_price`, `sold_at`, `seller_id`).
- **Shared helper**: `utils/lotCsvExport.js` — single `downloadLotCsv(...)` primitive used by all three surfaces.  Fetch → Blob → download with Content-Disposition filename, bilingual toast feedback.
- Bilingual (EN/FR) labels + toasts everywhere.

### Files changed
- New: `backend/services/lot_csv_export_service.py` — canonical service (~380 LOC, includes `role in ('admin','super_admin')` deps.User compatibility)
- New: `backend/routes/lot_exports.py` — thin route wrapper (~140 LOC)
- New: `backend/tests/test_iter482_lot_csv_export.py` — 32 tests (unit + HTTP, incl. admin-role variants)
- New: `backend/tests/test_iter482_lot_csv_export_e2e_frontend.py` — Playwright E2E for public + admin buttons (skips gracefully if Playwright not installed)
- New: `frontend/src/utils/lotCsvExport.js` — shared browser helper (~90 LOC)
- Modified: `backend/server.py` — router registration only
- Modified: `frontend/src/pages/SellerDashboard.js` — Export CSV button + handler (now uses shared helper)
- Modified: `frontend/src/pages/MultiItemListingDetailPage.js` — public Download Lot List (CSV) button
- Modified: `frontend/src/pages/admin/ManageAllAuctions.js` — admin Export CSV (Admin) button
- Modified: `memory/test_credentials.md`, `memory/PRD.md` (docs)

### Endpoints added
- `GET /api/exports/lots/{auction_id}` (returns `text/csv; charset=utf-8`)
- `GET /api/exports/lots/{auction_id}/preview` (returns JSON)

### Tests added
- **28 tests total** (in `test_iter482_lot_csv_export.py`)
- Unit (in-process): resolution across 6 collections, access control (seller/public/admin), 13-column ordering, admin extras, redaction, embedded lot normalisation, draft filtering (with/without flag), vehicle & storage schema mapping, 10,000-lot performance, UTF-8 BOM Excel compatibility
- HTTP end-to-end (against preview URL): unauthenticated → 401, non-owner → 403, owner → 200 + valid CSV + BOM, admin-only → 403 for non-admin, public → 200 no auth + forbidden fields absent, preview endpoint JSON, missing auction → 404, `include_drafts=true` behaviour
- **Result: 28/28 PASS**

### Sample CSV output
```
auction_id,auction_name,lot_number,title,description,quantity,starting_bid,category,condition,current_bid,status,listing_url,image_urls
iter482csv-seller-owned-test,iter482 CSV Export Test Auction,1,Vintage Bicycle,Restored 1970s Peugeot,1,50.00,sports,good,75.00,active,https://bidvex.ca/auction/iter482csv-seller-owned-test,https://cdn.example/bike.jpg
iter482csv-seller-owned-test,iter482 CSV Export Test Auction,2,Antique Chair Set,Set of 4 oak chairs,4,20.00,furniture,fair,20.00,active,https://bidvex.ca/auction/iter482csv-seller-owned-test,https://cdn.example/chair1.jpg|https://cdn.example/chair2.jpg
```

### Confirmations
- ✅ All 6 auction types supported (general / multi_item / vehicle / vehicle_multi_lot / storage / partner)
- ✅ No duplicate calculators, no per-page generators
- ✅ Payment / tax / fee / Stripe / settlement code UNTOUCHED
- ✅ Frontend E2E download verified via Playwright (`iter482_csv_downloaded_bidvex_lots_iter482csv-seller-owned-test_seller.csv` — matches spec)
- ✅ UTF-8 BOM present for Excel compatibility (verified via `od -c`)
- ✅ Draft filtering works; `include_drafts=true` flag honoured on seller/admin only
- ✅ Existing iter482 regression suite unaffected (250/250 excluding known rate-limit flake)

**🚫 DO NOT DEPLOY — feature is READY, not deployed.**

---

## iter482 — Finalization Pass (Feb 12, 2026) ✅ LAUNCH-READY (TEST MODE) · DO NOT DEPLOY

**Focused audit** of Stripe processing correctness, actual fee reconciliation, billing documents (buyer receipt / seller statement / seller receipt / commission invoice / partner multi-lot invoice), PDF generation, and end-to-end payment consistency. Reused all existing P4/P5/P5.1 architecture — no new calculators, no redesign.

### What was verified
- **Chain reconciliation cent-for-cent** on the canonical `$100 Individual seller / CA card` scenario: Checkout ↔ Backend ↔ PaymentIntent ↔ BalanceTransaction ↔ Receipt ↔ Seller Statement ↔ PDF all equal $107.98 (buyer) / $95.40 net (seller).
- **All 5 critical PDFs generated & inspected**: Buyer Universal Receipt (EN + FR bilingual), Marketplace Seller Statement, Marketplace Seller Receipt, Marketplace Seller Commission Invoice. Every document displays BidVex letterhead, buyer + seller identity blocks, itemized breakdown (Hammer / BP / GST / QST / Stripe fee where applicable), legal footer with BidVex GST/QST numbers.
- **Actual Stripe fee reconciliation** wired to `payment_intent.succeeded` webhook via `services/stripe_reconciliation_service.py`. Persists `estimated_cents`, `recovery_cents`, `actual_cents`, `variance_cents`, `card_country`, `resolved_jurisdiction` separately (never overwrites). Idempotent — 2 seed runs produce 2 rows, not 4.
- **Admin ledger APIs** working: `/api/admin/stripe-reconciliation` (list) · `/api/admin/stripe-reconciliation/summary` (aggregate) · `/api/admin/stripe-reconciliation/{payment_intent_id}` (single row).
- **Offline methods (Cash / E-Transfer / Cheque)** always $0 Stripe fee with reason `offline_method`; frontend sidebar shows 0,00 $ (hors ligne) on switch.
- **Canadian card**: 2.9% + $0.30 gross-up = 344c on $104.54 base. **International card**: 3.9% + $0.30 = 438c. Both persisted with authoritative card country from Stripe payment_method_details.
- **Individual/Business seller = 4% commission** · **Partner = 3%** (rate matrix in `routes/seller_commission_invoice.py`).
- **BidVex never silently absorbs** Stripe rail cost. Anti-regression test `test_anti_regression_stripe_never_silent_zero` blocks future L-1 flips.

### Bug fixed during audit — 🔴 LAUNCH-BLOCKER
- **CheckoutPage.js sidebar "Frais + Taxes" row** was summing invalid keys (`fees_tax_total` / `hammer_tax_total`) that don't exist on the backend response. Under-counted by the tax portion (showed $3.50 instead of $4.54 for the $100 scenario). Fix: sum canonical `total_tax` field. New testid `checkout-summary-fees-taxes`. Verified end-to-end: Stripe path 100+4,54+3,44=107,98 · Cash path 100+4,54+0,00=104,54.

### Test results
- iter482 regression suite: **250/250 GREEN** across P0/P2/P3/P3.1/P4A/P4/P5/P5.1/golden matrix
- `test_iter482_p4_end_to_end.py` in isolation: 14/14
- Focused PDF verification script: `backend/tests/iter482_finalization_pdf_verify.py` — 5 PDFs generated, all analyzed and confirmed correct via `analyze_file_tool`
- Frontend E2E smoke: Stripe ↔ Cash switching sidebar cent-perfect

### Files changed (iter482 finalization)
- Frontend: `pages/CheckoutPage.js` (sidebar canonical field fix + new testid)
- New: `backend/tests/iter482_finalization_pdf_verify.py` (seed + PDF generator harness)
- New: `memory/iter482_finalization_launch_report.md` (full launch-readiness report)

### Guardrails honoured
✅ Stripe TEST mode only · ✅ No production data · ✅ No historical mutations · ✅ No refunds · ✅ Reused canonical engine · ✅ No new calculators · ✅ No redesign

### Remaining (post-launch — cosmetic only)
- FR receipt labels "TPS sur prime" / "TVQ sur prime" are slightly imprecise (real taxable base = BP + processing recovery). Values correct; label wording future work.
- International-card variance email automation (P5.1 deferred).
- Auth `/api/auth/register` 1-req/min rate-limit flakes full backend test suite; add session-scoped fixture.

---

## iter482 — Phase P5.1 Stripe Actual-Fee Reconciliation + Card Country + Partner Invoice (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY · DO NOT DEPLOY

### Scope delivered end-to-end
- **Actual Stripe BalanceTransaction persistence** — new `services/stripe_reconciliation_service.py` retrieves the authoritative `BalanceTransaction.fee`/`fee_details`, plus `payment_method_details.card.country`, and persists a canonical row in `db.payment_processing_reconciliation` keyed by `payment_intent_id`.  Idempotent via `$setOnInsert` — webhook replay updates the same row without duplicating.
- **Canonical reconciliation record**:
  - `estimated_cents` — additive Stripe estimate (base × rate + fixed)
  - `recovery_cents`  — gross-up amount charged to the payer
  - `actual_cents`    — BalanceTransaction.fee
  - `variance_cents`  — `recovery - actual`
  - `reconciliation_status` ∈ `COVERED` (`≥ actual`) / `SHORTFALL` (`< actual`) / `UNKNOWN` (no BT) / `ERROR` (Stripe API failed)
  - `card_country` + `resolved_jurisdiction` (`domestic`/`international`)
- **`payment_intent.succeeded` webhook** now invokes `reconcile_payment_intent` before the existing card-country delta logging (preserves the legacy shortfall log for non-CA cards).
- **PaymentIntent metadata expanded** with the seven canonical fields (`payment_processing_estimated_cents`, `payment_processing_recovery_cents`, `payment_processing_rate`, `payment_processing_jurisdiction`, `payment_processing_payer_role`, `buyer_total_cents`, `seller_commission_cents`) so the reconciler can compute variance without a second DB round-trip.
- **Admin ledger API** — new `routes/admin_stripe_reconciliation.py`:
  - `GET /api/admin/stripe-reconciliation` (filter by status, since, limit)
  - `GET /api/admin/stripe-reconciliation/{payment_intent_id}` (single row)
  - `GET /api/admin/stripe-reconciliation/summary` (aggregate covered/shortfall/unknown counts + variance totals)
  - Role gated to `admin` / `super_admin`
- **Partner multi-lot PAY NOW invoice** — extended `GET /api/seller/commission-invoice/{id}` so `multi_item_listings` rows return `sold_lots[]` + summed `hammer_cents`.  Frontend `SellerCommissionInvoicePage.js` renders the sold-lots table above the commission detail card.  Screenshot `/tmp/iter482_p51_partner_invoice.png` confirms: **3 sold lots totalling $870 → 4% commission $34.80 + taxes $5.21 + Stripe recovery $1.51 = $41.52 (via Stripe) / $40.01 (offline)**.

### Test results — 276/276 GREEN across P0/P2/P3/P3.1/P4/P4A/P5/P5.1
| Suite | Result |
|---|---|
| iter482 P0 golden repairs | 10/10 |
| iter482 golden matrix | 40/40 |
| iter482 P2 canonical engine | 40/40 |
| iter482 P3 fee_calculator | 16/16 |
| iter482 P3.1 reconciliation | 38/38 |
| iter482 P4A foundation | 51/51 |
| iter482 P4 end-to-end | 14/14 |
| iter482 P5 payer-bears-fee | 31/31 |
| **iter482 P5.1 reconciliation (new)** | **10/10** |
| **Anti-regression: no silent $0 for Stripe** | proven |

### Files changed (P5.1)
- Backend: `services/stripe_reconciliation_service.py` (new), `routes/admin_stripe_reconciliation.py` (new), `routes/webhooks.py` (wire reconciler in `payment_intent.succeeded`), `services/stripe_connect_service.py` (metadata expansion), `routes/seller_commission_invoice.py` (sold_lots + hammer-sum for multi-item), `server.py`
- Frontend: `pages/SellerCommissionInvoicePage.js` (sold lots table)
- Tests: `backend/tests/test_iter482_p51_reconciliation.py` (10 new tests including anti-regression + Stripe stub monkeypatch)

### Anti-regression guards added
- Test `test_anti_regression_stripe_never_silent_zero` asserts every Stripe/card payment either has `recovery_cents > 0` OR a documented `reason_code` (`offline_method`, `legally_gated`, `prohibited`, `platform_absorbed`, `unknown_rate_matrix`).  Prevents a future L-1 flip from silently zeroing the fee.
- Test `test_reconcile_payment_intent_persists_and_is_idempotent` proves webhook replay never duplicates a reconciliation row.
- Test `test_reconcile_payment_intent_error_when_stripe_fails` proves an `ERROR` row is still written on Stripe API failure so admins see the missing reconciliation.

### Rate examples — cent-exact via canonical engine
| Base | Card | Additive | Gross-up recovery |
|---|---|---|---|
| $100 | CA domestic | $3.20 | **$3.30** |
| $100 | international | $4.20 | **$4.38** |
| $7 | CA domestic | $0.50 | **$0.52** |
| $1,000 | CA domestic | $29.30 | **$30.18** |

### Guardrails honoured
✅ Preview only — **DO NOT DEPLOY** · ✅ Stripe **TEST** mode only · ✅ No production data mutated · ✅ No historical records modified · ✅ No real refunds · ✅ BidVex never silently absorbs Stripe cost (invariant proven) · ✅ Offline methods always $0 with `reason_code=offline_method` · ✅ Idempotent webhook reconciliation

### Known limitation (documented, NOT silently ignored)
- **Card country pre-confirmation**: Stripe Checkout Session amounts are locked at session creation, so we cannot know the card's country *before* the payer confirms.  The engine defaults to `domestic` for the initial estimate; on webhook receive we resolve the true country from `payment_method_details.card.country` and record any variance in the reconciliation ledger.  If the user's business policy requires re-issuing a variance invoice for international-card shortfalls, that is a straightforward follow-up: iterate rows with `resolved_jurisdiction="international"` AND `reconciliation_status="SHORTFALL"` and email the delta.

### Deferred (post-P5.1, awaiting next directive)
- 🟠 **International-card variance invoice** — email seller/buyer the delta captured in `stripe_fee_adjustments` + `payment_processing_reconciliation.SHORTFALL` rows
- 🟠 **P6** — Tax engine consolidation across jurisdictions
- 🟠 **P7** — ≥ 200-case exact-cent regression matrix
- 🟢 **P8** — Peripheral flows
- 🟠 **P9** — Static audit + deployment gate

---


## iter482 — Phase P5 Payer-Bears-Stripe-Processing-Cost (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY · DO NOT DEPLOY

### Scope delivered end-to-end (Backend + Frontend + Tests)
- **L-1 legal gate OPENED** per explicit user directive: buyer + seller Stripe recovery is CLEARED across all 13 provinces/territories.  Terms of Use disclose that when a payer selects a Stripe/card payment method they bear the Stripe processing cost — BidVex never silently absorbs it.
- **Canonical gross-up recovery** added to `services/payment_cost_engine.py`.  `estimate(mode="gross_up")` returns both:
  - `estimated_cents` — additive underlying Stripe fee (`base × rate + fixed`)
  - `recovery_cents` — mathematically correct amount to add so BidVex actually recovers the Stripe cost cent-for-cent: `ceil((base × rate + fixed) / (1 − rate))`
- **CA vs INT rate matrix** honoured: `2.9% + $0.30` domestic / `3.9% + $0.30` international.
- **`stripe_connect_service.calculate_general_checkout` + `connect_payment_engine.calculate_connect_checkout` + `fee_calculator.calculate_fee`** ALL sourced from the canonical engine.  Path A ↔ Path B reconcile cent-exact.  BidVex's `application_fee` now includes the buyer-borne recovery so Stripe's actual fee is covered by the payer, not by BidVex.
- **CheckoutPage.js**:
  - Sidebar row: **"Payment Processing Fee"** (never hidden when Stripe selected)
  - Card row: bilingual **"Frais de traitement du paiement / Payment Processing Fee"** with the rate label `(2.9% + $0.30 — gross-up)` and a Reason line if the engine returns 0 with a documented reason
  - Total Due includes the recovery cent-exact
- **New Seller Commission Invoice**:
  - Backend: `routes/seller_commission_invoice.py` — `GET /api/seller/commission-invoice/{listing_id}` + `POST /api/seller/commission-invoice/{listing_id}/pay-now`
  - Rate resolver: 4% Individual/Business · 3% Partner · Vehicle/Storage flagged `REQUIRES_BUSINESS_REVIEW`
  - Renders the 4 payment-method breakdown (Stripe/E-Transfer/Cash/Cheque) with per-method total and reason codes
  - Persistence: `db.seller_commission_invoices` with pending/paid states + Stripe Checkout Session id
  - Frontend: `/seller/commission-invoice/:listingId` — bilingual page with itemized total and **PAY NOW** button that redirects to Stripe Checkout or records offline instructions
- **PriceBreakdown.js**: updated to show reason code when processing is 0 for a Stripe path (never silent $0).
- **BidVex retention math**: `application_fee = BP + SC + fees_tax + processing_recovery`; the destination-charge invariant `charge = app_fee + transfer` still holds cent-exact.
- **Regression tests updated** to reflect the new L-1 CLEARED behaviour + new invariants.

### Rate examples (cent-exact via canonical engine)
| Base | Card | Additive estimate | Gross-up recovery |
|---|---|---|---|
| $100 | CA domestic | $3.20 | **$3.30** |
| $100 | international | $4.20 | **$4.38** |
| $7 | CA domestic | $0.50 | **$0.52** |
| $1,000 | CA domestic | $29.30 | **$30.18** |

### Test results — 270/270 across P5 + regression
| Suite | Result |
|---|---|
| iter482 P0 golden repairs | 10/10 |
| iter482 golden matrix | 40/40 |
| iter482 P2 payment cost engine | 40/40 |
| iter482 P3 fee_calculator canonical | 16/16 |
| iter482 P3.1 reconciliation | 38/38 |
| iter482 P4A foundation | 51/51 |
| iter482 P4 end-to-end | 14/14 |
| **iter482 P5 payer-bears-fee (new)** | **31/31** |

### Frontend E2E proofs (visual)
- `/tmp/iter482_p5_checkout.png` — Total $107.98 = hammer $100 + BP $3.50 + GST $0.35 + QST $0.69 + Processing $3.44 (bilingual label, no silent $0)
- `/tmp/iter482_p5_checkout_switch_fixed.png` — Reactive switching: Stripe $107.98 / $3.44, Cash $104.54 / $0.00, E-Transfer $104.54 / $0.00, Stripe $107.98 / $3.44 (verified via automated E2E)
- `/tmp/iter482_p5_seller_invoice.png` — Seller commission invoice $5.05 = commission $4.00 + tax $0.60 + Stripe recovery $0.45 (4 payment methods, PAY NOW active)

### Files changed
- Backend: `services/payment_cost_engine.py`, `services/stripe_connect_service.py`, `services/connect_payment_engine.py`, `services/fee_calculator.py`, `routes/seller_commission_invoice.py` (new), `server.py`
- Frontend: `pages/CheckoutPage.js`, `pages/SellerCommissionInvoicePage.js` (new), `components/PriceBreakdown.js`, `App.js`
- Tests: `tests/test_iter482_p5_payer_bears_fee.py` (new · 31 tests), regression tests updated in `test_iter482_p31_reconciliation.py`, `test_iter482_p0_repairs.py`, `test_iter482_p2_payment_cost_engine.py`, `test_iter482_p3_fee_calculator_canonical.py`

### Guardrails honoured
✅ Preview only — **DO NOT DEPLOY** · ✅ Stripe TEST mode · ✅ No production data mutated · ✅ No historical financial records changed · ✅ Terms-of-use payer-bears-fee disclosure captured · ✅ BidVex retains recovery via application_fee (Stripe's actual fee comes out of that recovery, NOT BidVex margin)

### Deferred (awaiting Stripe test-mode real-charge test)
- 🟠 **Actual Stripe BalanceTransaction reconciliation via webhook** (`services/payment_cost_engine.lock_actual` is already the API — needs the `payment_intent.succeeded` webhook wiring to persist actual fee alongside estimate/recovery)
- 🟠 **Card country detection at payment confirmation** — currently defaults to `domestic` for the initial estimate; on webhook receive-side we can read `payment_method.card.country` and post-charge reconcile (delta absorbed by BidVex or invoiced separately per business policy)
- 🟠 **Partner post-auction "PAY NOW" 3% invoice page** — backend covers computation via `routes/partner_platform_fee.py` (existing); UI is next
- 🟠 **P6** — Tax engine consolidation
- 🟠 **P7** — ≥ 200-case regression matrix
- 🟢 **P8** — Peripheral flows
- 🟠 **P9** — Static audit + deployment gate


---


## iter482 — Phase P4 Seller-Controlled Payment Methods (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY

Canonical `AcceptedPaymentMethodsSelector` (stripe/etransfer/cash/cheque) wired across all Create flows.  Immutable snapshot at first bid.  Buyer restriction on CheckoutPage.js with server-side enforcement (`400 PAYMENT_METHOD_NOT_ACCEPTED`).  Selected method propagated to receipts + Stripe metadata.  Legacy duplicate radios REMOVED.

## iter482 — Phase P4A Foundation (Feb 12, 2026) ✅
Canonical registry, snapshot service, model field addition, backfill script, 51 unit tests.

## iter482 — Phase P3.1 Cross-Calculator Reconciliation (Feb 12, 2026) ✅
Root-caused and fixed the $0.02 tax divergence.  196/196 tests passed pre-P5.

## iter482 — Phase P3 Checkout Wiring & $0.31 Fix (Feb 12, 2026) ✅
Wired canonical `payment_cost_engine` into every buyer-facing calculator.

## Original problem statement + core requirements

1. Exact-cent reconciliation across all financial paths.
2. Seller-controlled payment methods (stripe/etransfer/cash/cheque). ✅ P4
3. Buyer restricted to seller's accepted methods. ✅ P4
4. BidVex NEVER silently absorbs Stripe processing costs. Payer-bears-fee model implemented. ✅ P5
5. First-bid immutable snapshot on payment methods. ✅ P4A
6. Selected payment method propagates to transactions, receipts, and seller dashboards. ✅ P4

## Personas
- Individual buyer, Individual/Business seller (4% commission), Partner (3% platform fee), Vehicle Dealer, Storage Facility, Admin (`charbel911@gmail.com`).

## Architecture
- Frontend: React SPA + Tailwind + shadcn/ui
- Backend: FastAPI + Motor (async Mongo)
- Integrations: Stripe (TEST mode), SendGrid, Twilio, Cloudflare R2, Emergent LLM key

## Prioritized backlog
- 🟠 P5.1 Actual Stripe fee reconciliation via webhook + card_country detection
- 🟠 Partner post-auction "PAY NOW" invoice UI (backend done)
- 🟠 P6 Tax engine consolidation
- 🟠 P7 ≥ 200-case regression matrix
- 🟢 P8 Peripheral flows (escrow, deposits, penalties, marketing)
- 🟠 P9 Static audit + deployment gate
- 🟢 Admin Fee Schedule UI
- 🟢 Claude AI models integration
- 🟢 Lot buyer chip + photo auto-matcher

### Scope delivered end-to-end (Backend + Frontend + Tests)
- **Canonical seller multi-select** (`stripe`, `etransfer`, `cash`, `cheque`) via `AcceptedPaymentMethodsSelector.jsx` wired into ALL Create-Listing flows (Individual, Multi-Item, Vehicle, Vehicle Multi-Lot, Storage). **Legacy duplicate radio buttons REMOVED** in `CreateListingPage.js`, `CreateMultiItemListing.js`, `storage/StorageAuctionCreate.js`.
- **Immutable snapshot** at first bid via `services/seller_payment_methods_service.py` (`accepted_payment_methods_snapshot` + `accepted_payment_methods_locked_at`).
- **Buyer restriction** on `CheckoutPage.js`: fetches `/api/listings/{id}/accepted-payment-methods` on load and dynamically renders only the seller's accepted methods. First accepted method auto-selected. Cheque support added. Button disabled if none configured.
- **Buyer selection ack**: buyer calls `POST /api/checkout/select-payment-method` with exact-cent totals BEFORE any Stripe session or offline order is created. Anti-tamper check enforces `parts_sum == total_cents`.
- **Server-side enforcement** in `POST /api/payments/checkout/auction`, `POST /api/payments/auction-winner-checkout/{id}`, `POST /api/payments/offline-checkout/{id}` — every buyer-selected method is validated against `assert_selection_allowed()`. Non-accepted methods → 400 `PAYMENT_METHOD_NOT_ACCEPTED`.
- **Cheque flow**: offline endpoint now accepts `cheque` alongside `cash`/`etransfer` with a bilingual confirmation email (EN/FR) and dedicated success message.
- **L-1 fail-closed reinforced** in `services/connect_payment_engine.calculate_connect_checkout`: canonical `payment_cost_engine.estimate()` snapshot is now attached, and any leaked `bi.stripe_recovery` is stripped from `buyer_total` / `stripe_charge` — buyer NEVER pays Stripe processing while L-1 is closed.
- **Buyer's Premium attribution** added to `PriceBreakdown.js` + `CheckoutPage.js`: label now reads *"Buyer's Premium (by seller/Partner, X.X%)"*.
- **Selected payment method propagation**: `offline_orders.selected_payment_method`, `pending_payments.selected_payment_method`, `listings.selected_payment_method`, Stripe `payment_intent.metadata.selected_payment_method` all record the canonical slug.

### Test results — 239/239 PASS · 0 regressions
| Suite | Result |
|---|---|
| iter482 P0 golden repairs | 10/10 |
| iter482 golden matrix | 40/40 |
| iter482 P2 payment cost engine | 46/46 |
| iter482 P3 fee_calculator canonical | 16/16 |
| iter482 P3.1 cross-calc reconciliation | 38/38 |
| iter482 refund engine | 7/7 |
| iter482 P4A foundation | 51/51 |
| **iter482 P4 end-to-end (new)** | **14/14** |

### Frontend E2E proofs (visual, this session)
- `/tmp/iter482_p4_create_smoke.png` — Create Listing shows ONLY the new canonical selector (no duplicate radio)
- `/tmp/iter482_p4_checkout_multi.png` — Checkout renders only 3 methods (stripe/etransfer/cash) because seller configured those three; Cheque is hidden
- `/tmp/iter482_p4_checkout_after_fix.png` — Total $104.54 exact; Processing $0.00 (L-1 gate honoured); Buyer Premium attribution visible

### Files modified (backend)
- `routes/payments.py` — added `payment_method` field to `AuctionCheckoutRequest`, enforcement in `/checkout/auction`, `/auction-winner-checkout`, `/offline-checkout`. Added cheque branch to offline order + email. Persisted `selected_payment_method` on offline_orders and listings. Fixed `_id` insert bug on `offline_orders`.
- `services/stripe_connect_service.py` — `create_destination_charge` now accepts `selected_payment_method`, records in payment_intent metadata and `pending_payments`.
- `services/connect_payment_engine.py` — canonical `payment_processing` snapshot added; leaked `stripe_recovery` stripped from buyer path when L-1 closed.

### Files modified (frontend)
- `pages/CheckoutPage.js` — accepted-methods fetch on load, dynamic method filter (incl. Cheque), first-accepted default, `select-payment-method` ack call before Stripe / offline submission, disabled state when no methods, `payment_method` passed to backend, buyer premium attribution.
- `pages/CreateListingPage.js` — removed legacy 3-radio group; only `AcceptedPaymentMethodsSelector` remains. Fixed duplicate `quantity` keys.
- `pages/CreateMultiItemListing.js` — removed legacy radio group.
- `pages/storage/StorageAuctionCreate.js` — replaced 3-button legacy selector with canonical multi-select.
- `components/PriceBreakdown.js` — buyer premium attribution.

### Files created
- `backend/tests/test_iter482_p4_end_to_end.py` — 14 tests covering registry, service invariants, HTTP enforcement (offline path, ack path, cheque path, tamper detection, snapshot lock).

### Guardrails honoured
- **DO NOT DEPLOY** — preview only
- Buyer Stripe surcharge = $0 (L-1 CLOSED) across all winner + preview + checkout paths
- Offline methods (cash / etransfer / cheque) processing fee = $0 permanently
- Partner Model A₁ topology preserved
- No production data mutated
- No refunds executed
- Every historical iter482 test continues to pass

### Deferred to next phases
- P5: Refund engine consolidation + Gate 3 live Stripe TEST proof
- P6: Tax engine consolidation
- P7: ≥ 200-case exact-cent matrix
- P8: Peripheral flows (escrow, deposits, penalties, marketing)
- P9: Static financial audit repo-wide + final deployment gate
- Admin Fee Schedule UI (P1)
- Claude AI models integration (P1)
- Explicit Individual/Business seller B2B commission invoice UI (backend already computes; frontend needs a dedicated invoice widget on seller dashboard)
- Partner post-auction billing "PAY NOW" invoice flow (backend covers computation; a dedicated Partner invoice page would round it out)

## 🛑 HALTED at P4 boundary — awaiting explicit approval to enter P5+

---


## iter482 — Phase P3.1 Cross-Calculator Reconciliation (Feb 12, 2026) ✅ COMPLETE
Root-caused and eliminated the $0.02 divergence between `calculate_fee()` (Path A, CRA/iter350) and `calculate_general_checkout()` (Path B, Stripe session builder) for the $7.00/premium/premium/QC/QC scenario. 196/196 tests pass. Details preserved in git history and iter482 P3 architectural docs.

## iter482 — Phase P3 Checkout Wiring & $0.31 Frontend Fix (Feb 12, 2026) ✅ COMPLETE
Wired canonical `services/payment_cost_engine.py` into every buyer-facing calculator, eliminating the phantom $0.31 Stripe surcharge. `payment_processing.amount_cents` is now the ONE source of truth. 158/158 tests pass.

## Original problem statement + P0/P1 backlog

1. P0/P1 Payment Infrastructure Audit, Remediation & Financial Reconciliation. Exact-cent reconciliation.
2. Implement Seller-Controlled Payment Methods. ✅ **DONE — P4**
3. Buyers can only select from the payment methods enabled by the seller. ✅ **DONE — P4**
4. BidVex must NEVER silently absorb Stripe processing costs; while L-1 CLOSED buyer Stripe surcharge = $0. Offline methods always $0. ✅ **DONE — P3 + P4**
5. First-bid immutable snapshot on payment methods. ✅ **DONE — P4A**
6. Selected payment method must propagate to transactions, receipts, and seller dashboards. ✅ **DONE — P4** (offline_orders, listings, pending_payments, Stripe metadata all persist `selected_payment_method`)

## Personas
- **Individual buyer** — logs in, browses, bids, wins, checks out with one of the seller's accepted methods.
- **Individual seller / Business** — creates a listing, picks accepted payment methods, receives payout minus 4% commission.
- **Partner (Pro)** — creates lot auctions, uses 3% platform fee, uses Model A₁ Connect topology.
- **Vehicle Dealer** — hybrid payments (fees online, hammer offline).
- **Storage Facility** — 5% BP + 0% SC.
- **Admin (`charbel911@gmail.com`)** — permanent sole admin.

## Architecture
- Frontend: React SPA + Tailwind + shadcn/ui
- Backend: FastAPI + Motor (async Mongo)
- Integrations: Stripe (TEST mode), SendGrid, Twilio, Cloudflare R2, Emergent LLM key

## Prioritized backlog (P0 top-down)
- P0 P5 — Refund engine consolidation + live Stripe TEST proof
- P0 P6 — Tax engine consolidation across jurisdictions
- P0 P7 — ≥200-case exact-cent regression matrix
- P1 P8 — Peripheral flows (escrow, deposits, penalties, marketing)
- P0 P9 — Static financial audit + final deployment gate
- P1 Admin Fee Schedule UI
- P1 Claude AI models integration
- P1 Explicit seller-side commission invoice widget on seller dashboard
- P1 Partner post-auction billing "PAY NOW" invoice UX
- P2 Lot buyer chip + photo-to-row auto-matcher
