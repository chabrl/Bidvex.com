# Payment Methods Buyer-UI Defect — Root Cause Analysis
**Status:** RCA ONLY — no code changes yet. Reproduce → confirm → fix plan.
**Scope:** buyer-facing display of `accepted_payment_methods` on auction / lot detail pages.
**Baseline:** 88 backend tests passing. Preserve throughout fix.
**Reported by:** platform owner. Reproduced against seller `alexboul1993@gmail.com` on preview.

---

## 1. Reproduction — cent-perfect

**Seller:** `alexboul1993@gmail.com` (`seller_id = 0f258fed-4d56-4c0d-ae7a-52d0dd53bf67`)
**Auction:** `58758582-f53a-46d8-bc0b-87cf9de60523` — "Bicycles, Furniture and Extra Goods"
**Auction collection:** `multi_item_listings`

**Direct MongoDB read** (source of truth):
```python
db.multi_item_listings.find_one({"id": "58758582-..."})
# → {
#     "payment_method": "stripe",   # LEGACY singleton
#     "accepted_payment_methods": ["stripe", "etransfer", "cheque", "cash"]   # ✅ SELLER SELECTED FOUR
# }
```

**Buyer-facing API** `GET /api/multi-item-listings/58758582-...`:
```json
{
  "id": "58758582-...",
  "payment_method": "stripe",
  "accepted_payment_methods": null,           // ❌ LOST — DB had 4 methods
  "accepted_payment_methods_snapshot": null   // ❌ LOST
}
```

**Buyer sees on `/lots/58758582-.../lot/1`:**
```
Payment: This seller uses BidVex Stripe checkout
No deposit is required to bid on this auction. This seller uses BidVex Stripe checkout.
```
No mention of E-Transfer, Cheque, or Cash — even though the seller
explicitly selected all four.

---

## 2. Root Cause — TWO independent defects layered on top of each other

### 🔴 Defect A — Backend: `MultiItemListing` Pydantic model silently drops `accepted_payment_methods`

**File:** `/app/backend/models/auction_models.py` lines 343–413
**Model:** `MultiItemListing`
**Config:** `model_config = ConfigDict(extra="ignore")`

The model declares:
```python
class MultiItemListing(BaseModel):
    model_config = ConfigDict(extra="ignore")   # ← extras are DROPPED
    ...
    payment_method: Optional[str] = None        # legacy singleton, ok
    # accepted_payment_methods: ← NOT DECLARED  ⚠️
    # accepted_payment_methods_snapshot: ← NOT DECLARED  ⚠️
```

Compare with `Listing` (single-item) at lines 83–178 which DOES declare both:
```python
class Listing(BaseModel):
    ...
    payment_method: Optional[str] = None
    accepted_payment_methods: Optional[List[str]] = None            # ✅
    accepted_payment_methods_snapshot: Optional[List[str]] = None   # ✅
    accepted_payment_methods_locked_at: Optional[datetime] = None   # ✅
```

**Serialization pipeline** (`routes/listings.py::get_multi_item_listing`, line 1841):
```python
return MultiItemListing(**listing)   # extra="ignore" → drops accepted_payment_methods
```

Because `MultiItemListing` never declared the field, Pydantic silently
strips it before the response is serialized. The DB has the correct
value, the buyer never sees it. This affects **every multi-item /
partner / vehicle-multi-lot auction** on the platform — the exact
category `alexboul1993@gmail.com` uses.

The `MultiItemListingCreate` model at lines 286–340 correctly accepts
`accepted_payment_methods` on **write**, which is why the value lands
in MongoDB. The regression is purely on the **read/serialize** side.

### 🔴 Defect B — Frontend: buyer-facing pages hardcode Stripe copy

**File 1:** `/app/frontend/src/pages/LotDetailPage.jsx` (multi-item lot detail)

- Line 427 (fee breakdown card):
  ```jsx
  <span key="pay">This seller uses BidVex Stripe checkout</span>
  ```
- Line 475–476 (deposit notice):
  ```jsx
  <>No deposit is required to bid on this auction.
     This seller uses BidVex Stripe checkout. …</>
  ```
Both strings are unconditional. `listing.accepted_payment_methods` is
never read by this page.

**File 2:** `/app/frontend/src/pages/ListingDetailPage.js` (single-item detail)

- Lines 895–921 branch on the legacy singleton only:
  ```jsx
  {(listing.payment_method === 'cash' || listing.payment_method === 'e-transfer')
    ? <div>Payment method: {method}</div>
    : <div>Payment method: Stripe (BidVex)</div>
  }
  ```
`accepted_payment_methods` is ignored. If the seller picked `stripe +
cash + etransfer + cheque`, the buyer sees ONLY the first singleton.

**File 3:** `/app/frontend/src/pages/MultiItemListingDetailPage.js`
(multi-item grid) — the Buy Now dialog (lines 1747–1791) hardcodes a
3-way selector: `stripe`, `cash`, `etransfer`. `cheque` never appears
and the list is not driven by `listing.accepted_payment_methods`.

---

## 3. Full pipeline trace

| Stage | File | Behaviour | Status |
|---|---|---|---|
| 1. Seller writes on create | `frontend/src/pages/CreateMultiItemListing.js:743` | POSTs `accepted_payment_methods: [...]` array | ✅ CORRECT |
| 2. Backend validates on create | `backend/models/auction_models.py::MultiItemListingCreate._vapm` line 333 | Canonicalises via `payment_methods_registry.normalise_list` | ✅ CORRECT |
| 3. DB persistence | `backend/routes/listings.py:1563–1565` | Writes `accepted_payment_methods`, `accepted_payment_methods_source` | ✅ CORRECT (`{...}` sample above proves it) |
| 4. Backend edit path | `services/live_edit_service.py` | `accepted_payment_methods` is NOT in the safe-edit whitelist → seller can't change post-create except via admin. `MultiItemListingCreate` is only used on create; edits go through `PATCH /live-edit`. | ⚠️ Not a bug for this defect, but flagged for P4B follow-up |
| 5. **API serialisation for buyer** | `backend/routes/listings.py::get_multi_item_listing` line 1841 | `return MultiItemListing(**listing)` — model does not declare `accepted_payment_methods` → **dropped by Pydantic `extra="ignore"`** | 🔴 **DEFECT A** |
| 6. Frontend fetch | `LotDetailPage.jsx:88` | `GET /api/multi-item-listings/{id}` returns `accepted_payment_methods: null` (see §1) | (data already lost) |
| 7. Frontend render | `LotDetailPage.jsx:427, 475` | Hardcodes "BidVex Stripe checkout" ignoring the (null) field | 🔴 **DEFECT B** |
| 8. Bid submission | `frontend/src/pages/MultiItemListingDetailPage.js:476` + `backend/routes/auctions_bids.py:1206` | Bid write correctly snapshots `accepted_payment_methods_snapshot` on first bid — the P4B lock works. | ✅ CORRECT |
| 9. Winner checkout | `frontend/src/pages/CheckoutPage.js:147` | Fetches `GET /api/listings/{id}/accepted-payment-methods` **DIRECTLY from `seller_payment_methods_service`** — bypasses the leaky Pydantic model. **This is why checkout works.** | ✅ CORRECT |

**Why the bug was invisible on checkout:** `CheckoutPage.js` uses a
different endpoint (`/api/listings/{id}/accepted-payment-methods` in
`routes/seller_payment_methods.py:107`) that reads directly from Mongo
and does NOT go through the leaky `MultiItemListing` model. The
defect only manifests on the pre-bid discovery surface (lot / listing
detail pages) — which is exactly where the buyer needs the info the
most.

---

## 4. Blast radius

| Surface | Model used | `accepted_payment_methods` correctly emitted? |
|---|---|---|
| Single-item listing detail — `GET /api/listings/{id}` | `Listing` | ✅ YES (field is declared) |
| Multi-item / partner detail — `GET /api/multi-item-listings/{id}` | `MultiItemListing` | 🔴 NO — silently dropped |
| Vehicle detail — `GET /api/vehicles/{id}` | (uses vehicle_models.py) | ⚠️ NEEDS AUDIT (field declared at line 419 — likely ok) |
| Vehicle multi-lot — `GET /api/vehicle-multi-lot-events/{id}` | (uses different model) | ⚠️ NEEDS AUDIT |
| Storage auction detail — `GET /api/storage-auctions/{id}` | (uses different model) | ⚠️ NEEDS AUDIT |
| Winner checkout — `GET /api/listings/{id}/accepted-payment-methods` | Raw dict from `seller_payment_methods_service` | ✅ YES |
| Frontend single-item detail | Hardcoded singleton branch | 🔴 Doesn't read `accepted_payment_methods` |
| Frontend multi-item / lot detail | Hardcoded Stripe copy | 🔴 Doesn't read `accepted_payment_methods` |

---

## 5. Proposed Fix (BLOCK 1 — DATA PIPELINE)

### 5.1 Backend model repair (fixes Defect A everywhere)

**Edit:** `/app/backend/models/auction_models.py`, `MultiItemListing` class.
**Add three fields** (mirroring `Listing`):
```python
accepted_payment_methods: Optional[List[str]] = None
accepted_payment_methods_snapshot: Optional[List[str]] = None
accepted_payment_methods_locked_at: Optional[datetime] = None
```

**Optional but recommended — Lot model:** Since payment methods are
auction-level (not lot-level) in BidVex today, no change is required
on `Lot`. Confirmed with `MultiItemListingCreate.accepted_payment_methods`
at lines 305–308 which lives at the auction level.

**Audit other detail endpoints in the same pass:**
- `GET /api/vehicles/{id}` — verify `VehicleListing` model declares the field.
- `GET /api/vehicle-multi-lot-events/{id}` — verify.
- `GET /api/storage-auctions/{id}` — verify.

**No tax / fee / Stripe / commission code touched.**

### 5.2 Verification query (post-fix)
```bash
curl "$API/api/multi-item-listings/58758582-..." | jq .accepted_payment_methods
# Expected: ["stripe","etransfer","cheque","cash"]
```

---

## 6. Proposed Fix (BLOCK 2 — BUYER UI)

### 6.1 New reusable component

**Create:** `/app/frontend/src/components/AcceptedPaymentMethodsCard.jsx`

A dedicated buyer-facing card that:
- Renders **only** the methods present in `listing.accepted_payment_methods` (or its snapshot if locked).
- Renders every method with its canonical bilingual label + icon:
  - `stripe` → "Stripe Checkout" / "Paiement Stripe"
  - `etransfer` → "Interac E-Transfer" / "Virement Interac"
  - `cash` → "Cash on Pickup" / "Comptant à la collecte"
  - `cheque` → "Certified Cheque" / "Chèque certifié"
  - `wire` (if seen in registry — see 6.4) → "Wire Transfer" / "Virement bancaire"
- Displays "No accepted payment methods configured by seller" fallback if empty.
- Bilingual (EN/FR) via `useTranslation`.
- `data-testid="accepted-payment-methods-card"` and per-method `data-testid="apm-method-{slug}"`.

**Source-of-truth read order:** `accepted_payment_methods_snapshot` (locked at first bid) → `accepted_payment_methods` (live) → `payment_method` (legacy singleton, as single-element list).

### 6.2 Buyer Cost Transparency block

Extend the existing "Fee Breakdown" area (LotDetailPage.jsx lines 411–439) to always render, **before bidding**, the following in one card:
- Current Bid (already present)
- Buyer Premium % + amount (already present via `feesPreview`)
- Deposit Requirement (already present)
- **Accepted Payment Methods** (NEW — via the component in 6.1)

### 6.3 Buyer acknowledgement checkbox (required pre-bid)

Wire a mandatory acknowledgement checkbox into the bid form:
```
☐ I understand the accepted payment methods for this auction and
   agree to complete payment using one of the seller's approved
   methods if I win.
```
EN + FR strings via i18n.
`data-testid="bid-payment-ack-checkbox"`.
Bid submit button is `disabled` until:
1. Bid amount ≥ nextValidBid, AND
2. Acknowledgement is checked.
No backend enforcement needed — buyer is soft-gated at UI. (Backend
already enforces method allowlist server-side on checkout via
`assert_selection_allowed`.)

### 6.4 Remove hardcoded copy

**LotDetailPage.jsx:**
- Line 426–427: replace with `<AcceptedPaymentMethodsCard listing={listing} />` inside the fee breakdown.
- Line 475–476: strip "This seller uses BidVex Stripe checkout" from the deposit fallback text. The dedicated payment card carries that info now.

**ListingDetailPage.js:**
- Lines 894–921: replace the singleton `payment_method === 'cash' | 'e-transfer'` branch with `<AcceptedPaymentMethodsCard listing={listing} />`.
- Line 1303: keep the deposit checkout modal usage of `listing?.payment_method` as-is (it's a distinct concern — actual checkout payment routing).

**MultiItemListingDetailPage.js:**
- Lines 1747–1791 (Buy Now modal): filter the hardcoded stripe / cash / etransfer options through `listing.accepted_payment_methods` so a seller who accepts `cheque` sees a Cheque option AND a seller who ONLY accepts `stripe` never sees Cash.
- Line 423: replace `setSelectedPaymentMethod('stripe')` unconditional default with `setSelectedPaymentMethod(acceptedList[0] || 'stripe')`.

### 6.5 Payment methods registry — verify canonical slugs

**File:** `/app/backend/services/payment_methods_registry.py`
Confirm the canonical slug set: `{stripe, etransfer, cash, cheque}`.
If the product spec requires "Wire Transfer" as an explicit option
(per your reproduction copy), a `wire` slug will need to be added to
the registry (and the seller-side `AcceptedPaymentMethodsSelector.jsx`).
**Ask before extending the registry** — the audit could not find a
current `wire` slug on the backend.

---

## 7. Regression Tests

**New tests** (`/app/backend/tests/test_iter484_payment_methods_visibility.py`):
1. `test_multi_item_listing_api_emits_accepted_payment_methods` — seeds
   an auction with 4 methods; asserts the buyer GET returns all 4.
2. `test_multi_item_listing_api_snapshot_takes_precedence_when_locked`
   — asserts locked snapshot overrides live edits.
3. `test_single_item_listing_still_emits_field` — regression on
   existing `Listing` behaviour.
4. `test_none_when_missing_falls_back_to_legacy_singleton` — a
   pre-P4 listing with only `payment_method` returns a 1-element
   list to the buyer.

**Frontend tests** (Playwright, `test_iter484_payment_methods_ui.py`):
1. Seed the alexboul1993 auction OR a fresh idempotent seed.
2. Visit `/lots/{auctionId}/lot/1` and assert:
   - `accepted-payment-methods-card` visible
   - 4 `apm-method-{stripe|etransfer|cash|cheque}` rows visible
   - No text "BidVex Stripe checkout" in the fee breakdown card
3. Toggle a seller edit that removes `etransfer` (via admin route).
   Re-fetch and assert 3 methods visible.
4. Submit a bid without checking the acknowledgement — assert
   button is disabled.
5. Check acknowledgement + bid amount → assert bid submits.

---

## 8. Guardrails held

- ✅ No Stripe charge / payout code touched.
- ✅ No tax / fee / commission calculators touched.
- ✅ No changes to `/checkout/*`, `/offline-checkout/*`, `/payments/*` server-side enforcement.
- ✅ 88 baseline backend tests preserved.
- ✅ Preview only. No deploy.

---

## 9. Implementation order (once approved)

1. **[Backend]** Extend `MultiItemListing` Pydantic model (Defect A). Add regression test #1. Verify with `curl`.
2. **[Backend]** Audit vehicle / vehicle-multi-lot / storage models for the same class of leak. Fix if present.
3. **[Frontend]** Build `AcceptedPaymentMethodsCard` component.
4. **[Frontend]** Wire into LotDetailPage.jsx (multi-item / partner).
5. **[Frontend]** Wire into ListingDetailPage.js (single-item).
6. **[Frontend]** Wire into MultiItemListingDetailPage.js Buy Now dialog.
7. **[Frontend]** Add pre-bid acknowledgement checkbox.
8. **[Regression]** Run `pytest tests/test_iter484_reserve_settlement.py tests/test_iter482_p4_end_to_end.py tests/test_iter482_p4a_foundation.py` — expect 88+ green.
9. **[E2E]** Playwright verification with the alexboul1993 auction.
