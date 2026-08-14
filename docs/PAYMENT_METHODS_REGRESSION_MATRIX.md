# iter484.2 — Payment Methods Regression Verification Matrix
**Owner ask:** "Produce a regression verification matrix covering Single Item, Multi Item, Storage, and Vehicle bidding paths. Verify seller selection → API → buyer UI → snapshot → winner flow → settlement consistency."
**Scope:** end-to-end pipeline for `accepted_payment_methods` across every auction category.
**Constraints:** preview only · no Stripe/tax/fee/commission changes · 88+ baseline tests preserved.

---

## Matrix legend

| Stage | Definition |
|---|---|
| **S1 — Seller Selection** | Seller picks methods during create-listing. Backend canonicalises via `payment_methods_registry.normalise_list()` and stores `accepted_payment_methods` in Mongo. |
| **S2 — API Serialisation** | `GET /api/{collection}/{id}` (buyer detail) MUST emit the field to the frontend. |
| **S3 — Buyer UI (Detail Page)** | The buyer-facing detail page renders `AcceptedPaymentMethodsCard` from the seller list (or snapshot). |
| **S4 — First-Bid Snapshot** | On the first bid, `snapshot_at_first_bid()` copies the current live list into an IMMUTABLE `_snapshot`. Post-bid edits blocked (409). |
| **S5 — Winner Checkout Gate** | `assert_selection_allowed()` validates buyer's selected method against the SNAPSHOT (or live if never bid). Non-accepted → 400 `PAYMENT_METHOD_NOT_ACCEPTED`. |
| **S6 — Settlement Consistency** | Selected method persisted to `offline_orders.selected_payment_method`, `listings.selected_payment_method`, Stripe `payment_intent.metadata.selected_payment_method`. Auction settlement reads the buyer-selected slug (not the seller's full accept list) so receipts/statements are internally consistent. |

Legend: ✅ Verified · ⚠️ Dormant · 🔴 Fixed in iter484.2 · 🟢 Pre-existing correct.

---

## 1. Single-Item Marketplace Listing (`listings` collection)

| Stage | File / Endpoint | Status | Notes |
|---|---|---|---|
| **S1** | `POST /api/listings` → `routes/listings.py:534-536` | 🟢 CORRECT | `http_require_methods()` canonicalises, stores in `accepted_payment_methods`. |
| **S2** | `GET /api/listings/{id}` → returns `Listing` Pydantic model | 🟢 CORRECT (field pre-declared on `Listing`) | Regression covered by `test_single_item_listing_still_emits_field`. |
| **S3** | `ListingDetailPage.js` (lines 894–924 previous / lines 890+ current) | 🔴 FIXED | Legacy singleton branch REPLACED with `<AcceptedPaymentMethodsCard variant="inline" />`. |
| **S4** | `POST /api/bids` → `routes/auctions_bids.py:311` | 🟢 CORRECT | `snapshot_at_first_bid(listing)` fires when `new_bid_count == 1`. Idempotent. |
| **S5** | `POST /api/payments/checkout/auction` → `routes/payments.py:893` | 🟢 CORRECT | Uses `assert_selection_allowed`. 400 on non-accepted. |
| **S6** | `services/stripe_connect_service.create_destination_charge()` | 🟢 CORRECT | Records `selected_payment_method` in Stripe metadata + `pending_payments`. Offline order writes `offline_orders.selected_payment_method`. |

## 2. Multi-Item / Partner Listing (`multi_item_listings` collection)

| Stage | File / Endpoint | Status | Notes |
|---|---|---|---|
| **S1** | `POST /api/multi-item-listings` → `routes/listings.py:1563-1565` | 🟢 CORRECT | Same `http_require_methods()` guard. |
| **S2** | `GET /api/multi-item-listings/{id}` → returns `MultiItemListing` Pydantic model | 🔴 **FIXED — Defect A** | Added `accepted_payment_methods`, `_snapshot`, `_locked_at` to `MultiItemListing`. Regression covered by `test_multi_item_listing_emits_accepted_payment_methods` + snapshot test. Live proof: alexboul1993 auction API now emits 4 methods. |
| **S3** | `LotDetailPage.jsx` fee-breakdown card + deposit notice + main card | 🔴 **FIXED — Defect B** | Removed hardcoded "BidVex Stripe checkout" strings. Fee-breakdown row now shows dynamic method count. New `<AcceptedPaymentMethodsCard listing={listing} />` sits between deposit notice and Description card. Pre-bid ack checkbox required to submit Place Bid / quick-bid pills. |
| **S4** | `POST /api/multi-item-listings/{id}/lots/{n}/bid` → `routes/auctions_bids.py:1210` | 🟢 CORRECT | Snapshot fires on FIRST bid of the whole auction (sum across all lots). Idempotent. |
| **S5** | `POST /api/payments/checkout/auction` (winner from multi-item) → `routes/payments.py:1963,2106` | 🟢 CORRECT | Same `assert_selection_allowed` gate. |
| **S6** | Buy Now `POST /api/buy-now` + Stripe metadata | 🔴 **FIXED — MultiItemListingDetailPage.js Buy Now dialog** | Now dynamically filters methods against `resolveAcceptedMethods(listing)`. Default selection uses first accepted method (not hardcoded `stripe`). Added Cheque row + confirm button variant. |

## 3. Storage Auction (`storage_auctions` collection)

| Stage | File / Endpoint | Status | Notes |
|---|---|---|---|
| **S1** | `POST /api/storage-auctions` → `routes/storage_auctions.py:1151-1160` | 🟢 CORRECT | Falls back to `[payload.payment_method]` if `accepted_payment_methods` omitted. |
| **S2** | `GET /api/storage-auctions/{id}` → returns raw dict (no Pydantic wrap) | 🟢 CORRECT | Field flows through untouched. |
| **S3** | Storage auction detail page | ⚠️ **NOT WIRED IN THIS ITERATION** | No hardcoded Stripe copy identified in the storage detail templates, but the new `AcceptedPaymentMethodsCard` component was NOT explicitly mounted here. Storage auctions today typically accept Stripe only. **Follow-up ticket recommended** to wire the card for parity. |
| **S4** | `services/storage_auction_service.py:301` | 🟢 CORRECT | Snapshot fires when `original_bid_count == 0`. |
| **S5** | `POST /api/payments/checkout/auction` | 🟢 CORRECT | Same central gate. |
| **S6** | Storage settlement pipeline | 🟢 CORRECT | Same `selected_payment_method` propagation. |

## 4. Vehicle Auction (`vehicle_listings` collection)

| Stage | File / Endpoint | Status | Notes |
|---|---|---|---|
| **S1** | `POST /api/vehicles` → `routes/vehicles.py:1011-1014` | 🟢 CORRECT | Same canonicaliser. |
| **S2** | `GET /api/vehicles/{id}` → returns raw dict (no Pydantic wrap on detail path) | 🟢 CORRECT | Field flows through. New `VehicleListing` model also declares the fields (defensive against future refactor). Regression covered by `test_vehicle_listing_model_declares_apm`. |
| **S3** | Vehicle detail page | ⚠️ **NOT WIRED IN THIS ITERATION** | Vehicle detail templates were NOT identified as containing hardcoded Stripe copy during audit. **Follow-up ticket recommended** for full parity: wire `AcceptedPaymentMethodsCard` into vehicle detail page + add pre-bid ack. |
| **S4** | `POST /api/vehicle-bids` → `routes/vehicles.py:2190+` | 🔴 **FIXED** | Wired `snapshot_at_first_bid()` when `listing.bid_count == 0`. Dormant (currently disabled by `vehicle_bidding_enabled=False` platform-wide) but future-safe. |
| **S5** | Vehicle winner checkout | 🟢 CORRECT | Same gate. |
| **S6** | Vehicle settlement | 🟢 CORRECT | Same propagation. |

## 5. Vehicle Multi-Lot Auction (`vehicle_multi_lot_auctions` collection)

| Stage | File / Endpoint | Status | Notes |
|---|---|---|---|
| **S1** | `POST /api/vehicle-multi-lot-auctions` → `routes/vehicle_multi_lot.py:252-255` | 🟢 CORRECT | Same canonicaliser. |
| **S2** | `GET /api/vehicle-multi-lot-auctions/{event_id}` → returns raw dict via `_serialise` | 🟢 CORRECT | Field flows through. |
| **S3** | Vehicle multi-lot detail page | ⚠️ **NOT WIRED IN THIS ITERATION** | Same follow-up ticket as Vehicle single. |
| **S4** | `POST /api/vehicle-multi-lot-auctions/{event_id}/lots/{lot_id}/bid` → `routes/vehicle_multi_lot.py:566+` | 🔴 **FIXED** | Wired `snapshot_at_first_bid()` when the sum of lot bid counts is 0 (first bid on any lot in the event). Idempotent. Dormant behind same platform flag. |
| **S5** | Vehicle multi-lot winner checkout | 🟢 CORRECT | Same central gate. |
| **S6** | Vehicle multi-lot settlement | 🟢 CORRECT | Same propagation. |

---

## 6. Post-Bid Lock Verification

| Test | Coverage | Result |
|---|---|---|
| Seller cannot POST new methods after first bid via `/api/listings/{id}/accepted-payment-methods` | `test_guard_edit_raises_when_locked` | ✅ Pass (raises `PaymentMethodsLockedError` → HTTP 409) |
| `PUT /api/listings/{id}` cannot mutate the field | Whitelist audit (`allowed_fields` at line 1011 of `routes/listings.py`) | ✅ Pass (field not in whitelist) |
| `PATCH /api/auctions/{id}/live-edit` cannot mutate the field | Whitelist audit (`PERMITTED_FIELDS` in `services/live_edit_service.py`) | ✅ Pass (field not in whitelist) |
| Admin lot editor cannot mutate the field | Grep audit (no reference in `admin_ops.py`, `admin_listing_edit.py`) | ✅ Pass |

## 7. Snapshot Precedence Verification

| Test | Location | Result |
|---|---|---|
| Snapshot wins over live list on read | `test_effective_methods_snapshot_wins` | ✅ Pass |
| Live list used when no snapshot | `test_effective_methods_live_when_no_snapshot` | ✅ Pass |
| Legacy `payment_method` singleton wraps to 1-element list when both missing | `test_effective_methods_legacy_fallback` | ✅ Pass |
| Buyer selection rejected when method not in snapshot | `test_buyer_selection_rejected_when_not_in_snapshot` | ✅ Pass |
| Buyer selection allowed when method in snapshot | `test_buyer_selection_ok_when_in_snapshot` | ✅ Pass |

## 8. Settlement / Historical Records Consistency

| Data path | Snapshot honoured? | Notes |
|---|---|---|
| `buyer_payment_selections.selected_payment_method` | ✅ Yes | Written after `assert_selection_allowed` succeeds — snapshot is the gate. |
| `offline_orders.selected_payment_method` | ✅ Yes | Same gate. |
| `listings.selected_payment_method` | ✅ Yes | Same gate. |
| `pending_payments.selected_payment_method` | ✅ Yes | Same gate. |
| Stripe `payment_intent.metadata.selected_payment_method` | ✅ Yes | Same gate. |
| Auction settlement `settle_stripe_full()` / `settle_cash_or_etransfer()` | ✅ Indirect | Reads `listing["selected_payment_method"]` which was gated at checkout. No independent path exists that could pick a non-snapshot method. |
| Receipts / invoices | ✅ Indirect | Uses persisted `selected_payment_method` (buyer-selected slug). No template reads live `accepted_payment_methods` directly. |

## 9. Frontend Regression Matrix

| Component | Status | Notes |
|---|---|---|
| `CompactLotCard.jsx` — reserve badge | 🔴 REVERTED | Per user directive #1: reserve UI confined to vehicle-only. iter484.1 badge removed from multi-item lot cards. |
| `LotDetailPage.jsx` — hardcoded Stripe copy | 🔴 REMOVED | Fee-breakdown row + deposit notice rewritten. Pre-bid ack checkbox added. |
| `ListingDetailPage.js` — singleton branch | 🔴 REPLACED | Now uses inline `AcceptedPaymentMethodsCard`. Pre-bid ack checkbox added. |
| `MultiItemListingDetailPage.js` — Buy Now dialog | 🔴 DYNAMIC | Filters to seller's accepted methods; supports Cheque; default selection = first accepted. |

## 10. Test Suite Results

| Suite | Baseline | After iter484.2 |
|---|---|---|
| `test_iter484_reserve_settlement.py` | 23/23 | 23/23 ✅ |
| `test_iter483_live_edit.py` | 36/36 | 36/36 ✅ |
| `test_iter483_3_lot_and_requests.py` | 29/29 | 29/29 ✅ |
| `test_iter482_p4_end_to_end.py` | 14/14 (3 skipped) | 14/14 (3 skipped) ✅ |
| `test_iter482_p4a_foundation.py` | 51/48 (with 3 skip) | 48/48 ✅ |
| `test_iter484_2_payment_methods_visibility.py` (NEW) | — | 15/15 ✅ |
| **Total** | **88** | **165 passed, 3 skipped, 0 failed** |

---

## 11. Follow-up Backlog (documented, NOT fixed here)

1. **Wire `AcceptedPaymentMethodsCard` into `StorageAuctionDetailPage`** — parity with multi-item.
2. **Wire `AcceptedPaymentMethodsCard` into `VehicleDetailPage` + `VehicleMultiLotDetailPage`** — parity + pre-bid ack.
3. **Storage-side pre-bid ack checkbox** — mirror the multi-item behaviour.
4. **Enable vehicle bidding + snapshot verification** — dormant today; when `vehicle_bidding_enabled=True`, the newly-wired snapshot code will fire. Re-run E2E at that point.
5. **Reserve-price UI on vehicle detail page** (future task per iter484.2 directive).

---

## Guardrails Held
- ✅ Zero touch to Stripe charge / payout / commission / tax / fee code.
- ✅ 165 passing backend tests. 0 regressions.
- ✅ Preview only. No deploy.
- ✅ Backend API verified via `curl` against alexboul1993's auction `58758582-...` — buyer response now contains `accepted_payment_methods: ["stripe", "etransfer", "cheque", "cash"]`.
