# Post-Bid Payment Methods Lock — Pre-Implementation Audit
**Requested by:** platform owner (Option A approval, additional requirements #1–3).
**Purpose:** confirm the post-first-bid lock is enforced everywhere BEFORE we implement the buyer UI fix.
**Scope:** all write paths that could mutate `accepted_payment_methods` + all bid paths that should snapshot at first bid + all read paths that should honour the snapshot.
**Baseline:** 88 backend tests passing. No files modified during this audit.

---

## Executive Verdict

**Post-bid lock:** ✅ Enforced on the current live auction categories (Single-Item, Multi-Item, Storage).
**Snapshot-at-first-bid:** ✅ Wired for those 3 categories.
**Post-bid lock:** ⚠️ **NOT enforced** on the currently-DISABLED Vehicle and Vehicle-Multi-Lot bid paths (P1 defect — dormant code, fires only if `vehicle_bidding_enabled=True`).
**Snapshot honoured on read:** ✅ Verified via `effective_methods()` precedence: `snapshot → live → legacy`.
**BUT:** the serialization bug in `MultiItemListing` (Defect A of the main RCA) means the snapshot is present in Mongo but **stripped from the buyer response** — so even correct locking is invisible to the buyer today.

---

## 1. Write-Side Guards — can the seller change methods after first bid?

| Endpoint | File | Guard | Verdict |
|---|---|---|---|
| `POST /api/listings/{id}/accepted-payment-methods` | `routes/seller_payment_methods.py:270` | `guard_edit()` → `PaymentMethodsLockedError` → HTTP 409 | ✅ **CORRECT** |
| `PUT /api/listings/{id}` (single-item update) | `routes/listings.py:1003` | `allowed_fields` whitelist (line 1011) — `accepted_payment_methods` NOT in list → silently dropped | ✅ **CORRECT** (via whitelist) |
| `PATCH /api/auctions/{id}/live-edit` (seller live edit) | `services/live_edit_service.py:60` | `PERMITTED_FIELDS = {title, description, images, schedule, pickup, shipping, lot_image_add, lot_image_remove}` — `accepted_payment_methods` NOT in list → rejected | ✅ **CORRECT** (via whitelist) |
| `POST /api/auctions/{id}/requests` (unified auction requests) | `routes/auction_requests.py` | `TYPES = {edit, end_time, reserve_price}` — no `accepted_payment_methods` type | ✅ **CORRECT** (no request type) |
| Admin lot editor (multi-item) | `routes/admin_ops.py`, `routes/admin_listing_edit.py` | Grep confirms zero references to `accepted_payment_methods` | ✅ **CORRECT** (no admin-only bypass exposed) |

**Bottom line:** the only path that can write `accepted_payment_methods` post-create is the guarded seller endpoint at `POST /api/listings/{id}/accepted-payment-methods`, and it correctly rejects post-bid mutations with 409.

## 2. Snapshot-At-First-Bid Wiring

| Category | Bid endpoint | Snapshot call | File / Line | Verdict |
|---|---|---|---|---|
| Single-item (`listings`) | `POST /api/listings/{id}/bids` | `snapshot_at_first_bid(listing)` when `new_bid_count == 1` | `routes/auctions_bids.py:311` | ✅ **CORRECT** |
| Multi-item / Partner (`multi_item_listings`) | `POST /api/multi-item-listings/{id}/lots/{n}/bid` | `snapshot_at_first_bid(listing)` when `total_bids == 1` (sum across ALL lots) | `routes/auctions_bids.py:1210` | ✅ **CORRECT** — auction-level, first bid on ANY lot triggers lock |
| Storage (`storage_auctions`) | `POST /api/storage-auctions/{id}/bid` | `snapshot_at_first_bid(fresh)` when `original_bid_count == 0` | `services/storage_auction_service.py:301` | ✅ **CORRECT** |
| **Vehicle single (`vehicle_listings`)** | `POST /api/vehicle-bids` | ❌ **NOT CALLED** | `routes/vehicles.py:1932` | ⚠️ **DEFECT** — currently DORMANT because `vehicle_bidding_enabled=False` platform-wide (`routes/vehicles.py:211`). Fires if bidding is ever enabled. |
| **Vehicle Multi-Lot (`vehicle_multi_lot_auctions`)** | `POST /api/vehicle-multi-lot-auctions/{event_id}/lots/{lot_id}/bid` | ❌ **NOT CALLED** | `routes/vehicle_multi_lot.py:354` | ⚠️ **DEFECT** — grep confirms no `snapshot_at_first_bid` import in the file. Vehicle multi-lot bidding is currently gated by the same `vehicle_bidding_enabled` flag. |

## 3. Read-Side Snapshot Precedence

**Canonical read helper:** `services/seller_payment_methods_service.py::effective_methods()` lines 61–89.

Precedence:
```
1. accepted_payment_methods_snapshot   (immutable, set at first bid)   ← WINS if present
2. accepted_payment_methods            (live seller list)
3. payment_method                      (legacy singleton, wrapped in list)
4. Raise PaymentMethodsMissingError
```

| Read surface | Uses `effective_methods()`? | Notes |
|---|---|---|
| `GET /api/listings/{id}/accepted-payment-methods` (buyer, all collections) | ✅ Yes (line 126) | Correctly honours snapshot |
| Buyer selection ack (`POST /api/checkout/select-payment-method`) | ✅ Yes (line 200 via `assert_selection_allowed`) | Snapshot enforced on tender |
| Server-side enforcement on checkout | ✅ Yes (`routes/payments.py` via `assert_selection_allowed`) | Snapshot enforced |
| Serialization on `GET /api/listings/{id}` | ⚠️ Indirect — `Listing` model declares the field so it flows through | ✅ WORKS (single-item) |
| Serialization on `GET /api/multi-item-listings/{id}` | ❌ **BROKEN** — `MultiItemListing` model does NOT declare either field, so both `accepted_payment_methods` and `_snapshot` are dropped by Pydantic `extra="ignore"` | 🔴 **DEFECT A** (in main RCA) |
| Serialization on `GET /api/vehicles/{id}` | ✅ Returns raw dict (no Pydantic wrapper) | Flows through |
| Serialization on `GET /api/vehicle-multi-lot-auctions/{event_id}` | ✅ Returns via `_serialise(doc)` — needs quick verification but no Pydantic model drop | Flows through |
| Serialization on `GET /api/storage-auctions/{id}` | ✅ Returns raw dict | Flows through |

## 4. Historical Records — is `_snapshot` used at settlement?

The user asked: *"Ensure `accepted_payment_methods_snapshot` is used for winner, settlement, and historical records."*

| Path | Reads snapshot correctly? | Notes |
|---|---|---|
| Winner checkout gate | ✅ Via `assert_selection_allowed(listing, method)` in `routes/payments.py:893, 1963, 2106` | `effective_methods()` prioritises snapshot |
| Offline order persistence (`offline_orders.selected_payment_method`) | ✅ Uses buyer-selected slug, validated against snapshot | |
| Stripe metadata (`payment_intent.metadata.selected_payment_method`) | ✅ Uses buyer-selected slug, validated against snapshot | `services/stripe_connect_service.py` |
| Auction settlement (`auction_settlement.py`) | ⚠️ Reads listing doc — snapshot is present at the DB layer so downstream is safe. No direct `_snapshot` reference in this file (validation happens upstream at checkout). | Acceptable — the tender was already validated before settlement. |
| Receipts / invoices | ⚠️ Templates use `listing.get("selected_payment_method")` (buyer-selected slug persisted at ack time). No template reads `_snapshot` directly. Since selection is snapshot-validated, this is safe. | Acceptable. |

## 5. Snapshot Missing on Pre-P4A Listings

`services/seller_payment_methods_service.py::snapshot_at_first_bid()` handles the legacy case: if the listing has no `accepted_payment_methods` (pre-iter482 P4A), it falls back to wrapping the legacy `payment_method` singleton into a single-element list and snapshots that. No fail-open — if BOTH are missing, `PaymentMethodsMissingError` is raised.

Backfill script exists: `/app/backend/scripts/iter482_p4a_backfill_accepted_payment_methods.py`.

## 6. Reserve Price UI Scope Reminder

User directive: *"Reserve-price UI remains vehicle-only."*

**Current state on preview (iter484.1):** Reserve badge is shipped on **multi-item lot cards** (`CompactLotCard.jsx`) via `has_reserve` boolean, NOT on vehicle-only surfaces.

This appears to CONFLICT with the directive. Options:
- **a.** Keep the shipped multi-item badge (user was informed and approved iter484.1 earlier this session).
- **b.** Revert the multi-item reserve badge and confine reserve UI to vehicles only (requires new work — vehicles do not yet have the badge component).
- **c.** Leave the multi-item badge for now, and add the vehicle badge as a follow-up under Vehicle-P0.

**Recommendation:** confirm with user before touching iter484.1 code — the badge is already live in preview and does not conflict with the current payment-methods fix. Flagged as a separate decision.

## 7. Recommended Actions Before Fix

| # | Action | Priority |
|---|---|---|
| 1 | Fix Defect A (backend model) — Extend `MultiItemListing` to declare `accepted_payment_methods` + `_snapshot` + `_locked_at`. Same for `VehicleListing` / VML models if needed. | P0 — REQUIRED |
| 2 | Fix Defect B (frontend hardcoded copy) — Build `AcceptedPaymentMethodsCard`, wire into 3 detail pages, remove Stripe hardcoded strings, add ack checkbox. | P0 — REQUIRED |
| 3 | Wire `snapshot_at_first_bid` into vehicle bid + vehicle-multi-lot bid endpoints for future-safety. | P1 — Currently dormant (vehicle_bidding_enabled=False). Small fix (~10 lines). Recommend include. |
| 4 | Add regression test asserting `guard_edit` raises `PaymentMethodsLockedError` for locked listings. | P1 — Already covered by existing iter482 P4A tests. Verify. |
| 5 | Clarify reserve-price UI scope with user (§6). | Decision — no code change until confirmed. |

---

## Guardrails Held During Audit
- ✅ No files modified. All 88 backend tests still passing.
- ✅ No Stripe / tax / fee / commission code touched.
- ✅ Preview only.
