# P7.5 — Meta + Google Commerce Conversion Tracking Report

**Status:** IMPLEMENTATION VERIFIED — PLATFORM PROPAGATION PENDING
**Environment:** PREVIEW ONLY. **No deploy performed.**
**Scope:** Meta Pixel + Meta CAPI + GA4 ecommerce + Google Ads +
Enhanced Conversions + canonical catalog-ID alignment.
**Guard-rails honoured:**
- Zero changes to tax / fee / commission / auction settlement /
  Stripe payment / escrow / payout / reserve-price logic.
- Zero changes to the 1,049 P7 golden regression tests.
- Zero deployment.

---

## 1. Existing architecture discovered

### Meta Pixel (browser)
| File                                       | Role                                                              |
|--------------------------------------------|-------------------------------------------------------------------|
| `frontend/public/index.html`               | GA4 `G-D57B90DGSQ` and Ads `AW-18140095337` gtag bootstrap        |
| `frontend/src/utils/metaPixel.js`          | CASL-consent-gated `fbq` boot, dedupe, event emitters, event_id   |
| `frontend/src/utils/metaContentId.js`      | Canonical `content_id` derivation (single source of truth)        |
| `frontend/src/hooks/useMetaPixelTracking.js` | Reusable hook per detail page                                   |
| `frontend/src/components/MarketingPixelLoader.js` | Loads GTM/GA4 from `/api/site-config.marketing` at boot     |

Detail pages already wired for Pixel funnel:
- `ListingDetailPage.js` (marketplace)
- `MultiItemListingDetailPage.js` (general multi-lot parent)
- `vehicles/VehicleDetailPage.js` (single vehicle)
- `storage/StorageAuctionDetail.js` (storage single)
- `PaymentSuccessPage.js` (Purchase)

Detail pages **MISSING** any Pixel tracking (repaired):
- `vehicles/VehicleMultiLotDetailPage.js`
- `components/CompactLotCard.jsx` (inline lot bidding UI)

### Meta Conversions API (server)
| File                                       | Role                                                              |
|--------------------------------------------|-------------------------------------------------------------------|
| `backend/services/analytics_tracker.py`    | CAPI Purchase (`track_listing_purchase`, `track_broker_purchase`) |
| `backend/routes/payments.py::get_checkout_status` | Fires CAPI Purchase when Stripe reports `payment_status=paid`; idempotency stamped in `payment_transactions.meta_purchase_emitted` |

### Meta / Google catalog feeds
| File                                       | Role                                                              |
|--------------------------------------------|-------------------------------------------------------------------|
| `backend/services/meta_feed_mapper.py`     | Emits catalog items — parent for singletons, per-lot for multi-lot |
| `backend/services/google_feed_mapper.py`   | Reuses Meta items → RSS/g:namespace XML                            |
| `backend/routes/feeds.py`                  | HTTP feed endpoints, decomposition switch on `ltype`               |

### GA4 & Google Ads
| File                                       | Role                                                              |
|--------------------------------------------|-------------------------------------------------------------------|
| `frontend/src/utils/analytics_events.js`   | gtag wrappers — had only `partner_registration` conversion helper |

**Ecommerce events (`view_item` / `add_to_cart` / `purchase`) were NOT
fired anywhere in the repo prior to P7.5.** Google Merchant Center could
not attribute any browser signal to the feed — this is the concrete root
cause of the 0 % product-view match rate on multi-lot pages combined with
the missing GA4 ecommerce layer.

### Enhanced Conversions
Not present anywhere before this pass.

### Stripe webhook
`backend/routes/webhooks.py` handles all Stripe events. The
authoritative "payment succeeded" path is `checkout.session.completed`
→ `_handle_checkout_completed`. The **PaymentSuccessPage → /payments/status
polling** is the point where CAPI Purchase is emitted (idempotent via
`meta_purchase_emitted`). No business logic was touched here.

---

## 2. Final tracking architecture

Single event bus per commerce action → fans out to both Meta and Google.

```
Listing / lot detail page mount
    └─▶ useMetaPixelTracking.trackViewContent({ listing, lot? })
            ├─▶ Meta Pixel ViewContent  (event_id: bidvex_viewcontent_<CID>_s<YYYYMMDD>)
            └─▶ GA4 view_item           (items[0].item_id = <CID>)

Bid intent (Place a Bid CTA / inline quick-bid)
    └─▶ useMetaPixelTracking.trackAddToCart({ listing, lot?, bidAmount })
            ├─▶ Meta Pixel AddToCart    (dedupe per (listing, session))
            └─▶ GA4 add_to_cart

Bid commit (POST /bids succeeds)
    └─▶ useMetaPixelTracking.trackBidSubmitted({ listing, lot?, bidAmount })
            └─▶ Meta Pixel InitiateCheckout (per-bid, NOT deduped)

Stripe payment_status = "paid"
    └─▶ /payments/status/{session_id}
            ├─▶ Backend CAPI Purchase (deterministic event_id from session_id + <CID>)
            └─▶ Response includes { meta_content_id, meta_purchase_event_id,
                                    listing_type, listing_title, listing_category }

PaymentSuccessPage receives the status
    └─▶ useMetaPixelTracking.trackPurchase({ ..., identity, lotContentId })
            ├─▶ Google Enhanced Conversions   (gtag('set','user_data', {sha256_email,sha256_phone}))
            ├─▶ Meta Pixel Purchase           (same event_id as CAPI → Meta dedupes)
            ├─▶ GA4 purchase                  (transaction_id = Stripe session_id)
            └─▶ Google Ads Purchase           (optional — only when
                                               REACT_APP_GOOGLE_ADS_PURCHASE_LABEL is set;
                                               otherwise attribution flows via the
                                               GA4↔Ads link)
```

**Chosen strategy:** `native code with shared canonical helpers`. GTM
container (`GTM-MQ34GTF4`) remains present but is not required for the
Pixel + GA4 events documented above. Native code path is authoritative
because it can reach the runtime `listing.id` / `lot.lot_number` values
that GTM tags cannot introspect. All events pass a `content_id` that
matches the Meta + Google catalog rows byte-for-byte (see
`P7_5_CANONICAL_ID_MAP.md`).

---

## 3. Meta implementation (browser Pixel)

- Pixel base: unchanged (`REACT_APP_META_PIXEL_ID=825987810565038`).
- Consent gating: unchanged (CASL — `bidvex_analytics_consent`).
- Events emitted (all funnel-mapped, dedupe-safe per session where
  Meta's spec allows):
    - `ViewContent` — detail page mount (parent OR lot).
    - `AddToCart` — bid intent CTA.
    - `AddToWishlist` — watchlist add.
    - `InitiateCheckout` — successful bid commit.
    - `Purchase` — Stripe payment success confirmed.

- **P7.5 fix — per-lot `content_ids`** on multi-lot pages via
  `getLotContentId(parent, lot, {routeHint})`. The generated string
  matches the catalog decomposition (`LOT-<parent>-L<lot_number>` or
  `VML-<parent>-<lot_id[:8]>`) exactly.

- Deduplication: `event_id` built by `buildEventId()` in
  `utils/metaContentId.js`. Format: `bidvex_<event>_<content_id>_<disc>`.

## 4. Meta CAPI implementation (server)

- Unchanged wire path (`/payments/status/{session_id}` polling).
- Idempotency: `payment_transactions.meta_purchase_emitted` flag.
- **P7.5 fix — per-lot Purchase**: `track_listing_purchase(..., lot_ref)`
  now switches on `canonical_lot_content_id(listing_type, listing_id,
  lot_ref)` when the transaction carries `lot_number` / `lot_id`.
- User matching: SHA-256-hashed email/phone/city/state/country/zip +
  hashed `external_id`; `client_ip` + `client_ua` cleartext (Meta hashes
  server-side); `fbp` + `fbc` pass-through when supplied.

## 5. Google / GA4 implementation

- Bootstrap: `gtag('config','G-D57B90DGSQ')` in `index.html`. Unchanged.
- **New helpers in `utils/analytics_events.js`:**
    - `trackGA4ViewItem({ contentId, value, itemName, itemCategory, currency })`
    - `trackGA4AddToCart(...)`
    - `trackGA4Purchase({ contentId, value, transactionId, ... })`
    - `trackGoogleAdsPurchase({ value, transactionId, currency })` —
      no-op unless `REACT_APP_GOOGLE_ADS_PURCHASE_LABEL` is set.
    - `setEnhancedConversionsUserData({ email, phone })` — SHA-256 hex,
      shipped via `gtag('set', 'user_data', {...})`.
- **Payload shape frozen** by `tests/p7_5/test_canonical_content_id.py`:
  `items[0].item_id === Meta content_ids[0]` on every commerce action.

## 6. Google Ads implementation

- Ads account: `AW-18140095337` loaded from `index.html`. Unchanged.
- Partner registration conversion still supported via
  `trackPartnerRegistrationConversion(label)`.
- **Purchase conversion** wired but **DORMANT by default**. To activate:
    1. In Google Ads → Conversions → New conversion action → Website →
       purchase-type action.
    2. Copy the label (portion after the slash in `AW-…/label`).
    3. Set `REACT_APP_GOOGLE_ADS_PURCHASE_LABEL=<label>` in
       `frontend/.env`.
    4. Restart frontend — no code change required.
- Without a label, GA4 `purchase` events still drive Ads attribution via
  the GA4 ↔ Ads link (no visible degradation).

## 7. Enhanced Conversions status

- **Implemented for Purchase** — see `setEnhancedConversionsUserData`.
- Requires Enhanced Conversions to be enabled on the conversion action
  in Google Ads UI. Without that UI toggle, Google discards the
  `user_data` payload — code path is safe.
- Hashing: SHA-256 hex, trimmed + lower-cased, computed via
  `window.crypto.subtle.digest` client-side. Raw PII never leaves the
  browser.

---

## 8. Canonical catalog ID

See dedicated file: [`/app/docs/P7_5_CANONICAL_ID_MAP.md`](P7_5_CANONICAL_ID_MAP.md).

Summary:
- Singleton (marketplace / vehicle single / storage single) → **raw
  `listing.id`** (UUID string).
- Multi-lot general → **`LOT-<parent_id>-L<lot_number>`** per lot.
- Vehicle multi-lot → **`VML-<parent_id>-<lot_id[:8]>`** per lot.

## 9. Example real catalog ID (illustrative — not a live listing)

```
Multi-lot parent:  b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21
Meta catalog id:   LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3
Google feed id:    LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3
```

## 10. Example Meta content_id

```json
{
  "event_name": "AddToCart",
  "content_ids": ["LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3"],
  "content_type": "product",
  "currency": "CAD",
  "value": 125.00
}
```

## 11. Example GA4 item_id

```json
{
  "event": "add_to_cart",
  "currency": "CAD",
  "value": 125.00,
  "items": [{
    "item_id":       "LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3",
    "item_name":     "1985 Yamaha Motorcycle",
    "item_category": "vehicles",
    "price":         125.00,
    "quantity":      1
  }]
}
```

## 12. Event ID strategy

- Deterministic — same input → same output across browser + server.
- Format: `bidvex_<event_lowercase>_<content_id>_<discriminator?>`
- Purchase discriminator: `session_<stripe_session_id>` (Stripe session
  is unique per checkout, so a single Purchase is emitted regardless of
  webhook retries or `/payments/status` polling loops).

## 13. Deduplication strategy

| Event              | Browser side dedupe                            | Server ↔ Browser dedupe                     |
|--------------------|------------------------------------------------|---------------------------------------------|
| ViewContent        | sessionStorage: `ViewContent:<CID>`            | n/a (client-only)                           |
| AddToCart          | sessionStorage: `AddToCart:<CID>`              | n/a (client-only)                           |
| InitiateCheckout   | never dedupes (bidding-war signal)             | n/a                                         |
| Purchase           | sessionStorage: `Purchase:<CID>`               | Meta dedup key = deterministic `event_id`   |
| CAPI Purchase      | n/a                                            | idempotent via `meta_purchase_emitted` DB flag |

## 14. Exact files / functions changed

| Path                                                                | Change                                                                                           |
|---------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| `frontend/src/utils/metaContentId.js`                               | Added `VML` prefix + `getLotContentId(parent, lot, opts)`. Canonical singleton helper unchanged. |
| `frontend/src/utils/metaPixel.js`                                   | `trackViewContent`, `trackAddToCart`, `trackInitiateCheckout` now accept optional `lot`; content_ids resolve to per-lot id when passed. Re-exports `getLotContentId`. |
| `frontend/src/utils/analytics_events.js`                            | Added `trackGA4ViewItem`, `trackGA4AddToCart`, `trackGA4Purchase`, `trackGoogleAdsPurchase`, `setEnhancedConversionsUserData` (SHA-256 via SubtleCrypto). |
| `frontend/src/hooks/useMetaPixelTracking.js`                        | Extended: passes `lot` through, fires GA4 view_item/add_to_cart/purchase in parallel with matching Meta events, wires Enhanced Conversions on Purchase. |
| `frontend/src/pages/MultiItemListingDetailPage.js`                  | `trackAddToCart` / `trackBidSubmitted` now include `lot` → per-lot content_id.                   |
| `frontend/src/pages/vehicles/VehicleMultiLotDetailPage.js`          | Added `useMetaPixelTracking({routeHint:'vehicle_multi_lot'})`, per-lot ViewContent effect, per-lot AddToCart + InitiateCheckout on bid. (**Previously fired NOTHING.**) |
| `frontend/src/components/CompactLotCard.jsx`                        | Inline lot bidding now fires per-lot AddToCart + InitiateCheckout. (**Previously fired NOTHING.**) |
| `frontend/src/pages/PaymentSuccessPage.js`                          | Passes `identity` (from AuthContext) → Enhanced Conversions user_data; passes `lotContentId` from backend response.                     |
| `frontend/src/pages/ListingDetailPage.js`                           | GA4 `view_item` + `add_to_cart` added alongside existing Meta events.                            |
| `backend/services/analytics_tracker.py`                             | Added `canonical_lot_content_id(listing_type, parent_id, lot_ref)`; `track_listing_purchase` now accepts `lot_ref` and emits per-lot CAPI Purchase. |
| `backend/routes/payments.py::get_checkout_status`                   | Resolves `lot_ref` from `payment_transactions` / Stripe session metadata; returns `meta_content_id` (per-lot when applicable); passes `lot_ref` to CAPI. |
| `backend/tests/p7_5/test_canonical_content_id.py`                   | **NEW** — 23 tests locking the canonical ID contract across Meta / Google / GA4 / CAPI.          |
| `backend/tests/p7_5/__init__.py`                                    | **NEW** — package marker.                                                                        |
| `docs/P7_5_CANONICAL_ID_MAP.md`                                     | **NEW** — canonical ID reference.                                                                |
| `docs/P7_5_CONVERSION_TRACKING_REPORT.md`                           | **NEW** — this document.                                                                         |

**Untouched (per strict scope guard-rails):**
- Every tax file (`services/tax_engine.py`, `services/tax_rate_config.py`,
  `services/broker_fee_engine.py`, `routes/invoices.py`, …).
- Every fee/commission file (`services/fee_calculator.py`,
  `services/auction_settlement.py`, `services/connect_payment_engine.py`, …).
- Every Stripe business-logic file (`services/stripe_connect_service.py`,
  the entire `_handle_*` handler chain in `routes/webhooks.py`, …).
- The 1,049 P7 golden regression tests + their snapshots.

## 15. Tests run

| Test suite                                                        | Passing | Notes                                                            |
|-------------------------------------------------------------------|---------|------------------------------------------------------------------|
| `tests/p7/` (P7 cent-perfect financial regression)                | 1049    | Unchanged; zero impact.                                          |
| `tests/test_meta_pixel_funnel.py`                                 | ✅       | Existing Meta CAPI contract preserved.                           |
| `tests/test_iter218_meta_pixel_integration.py`                    | ✅       | Existing integration test preserved.                             |
| `tests/test_conversion_pipeline_phase5.py`                        | ✅       | CAPI structured-log fallback preserved.                          |
| `tests/p7_5/test_canonical_content_id.py`                         | 23      | **NEW** — canonical ID contract + GA4 payload shape + bilingual stability. |
| Combined Meta pixel + P7.5                                        | 58 + 23 | Additive; no baseline regression.                                |

Total confirmed passing test count from suites touched this iteration:
**1,130 (1,049 P7 + 58 Meta CAPI + 23 P7.5)**.

## 16. E2E test results

**Preview E2E is IMPLEMENTATION-LEVEL VERIFIED via automated regression
(pytest) + static contract tests. LIVE BROWSER FLOW verification
(Stripe test payment redirected back to /payment-success) can be run
by the user by:**

1. Sign in as `testbuyer@bidvex.com`.
2. Open a preview multi-lot auction (any `/lots/<id>` link).
3. Confirm DevTools → Network → `facebook.com/tr` shows `ViewContent`
   fires with `content_ids=["LOT-<parent>-L<n>"]`.
4. Click inline **Place Bid** on any active lot → `AddToCart` fires
   with the same per-lot `content_ids`.
5. Submit bid → `InitiateCheckout` fires with same per-lot `content_ids`.
6. Complete a Stripe test checkout → on `/payment-success`:
    - Meta Pixel `Purchase` fires with `event_id =
      bidvex_purchase_<CID>_session_<stripe_session_id>`.
    - GA4 `purchase` fires with `transaction_id=<stripe_session_id>`
      and `items[0].item_id=<CID>`.
    - Enhanced Conversions `set user_data` fires with the SHA-256
      email/phone of the signed-in buyer.
    - Backend CAPI `Purchase` fires with the **same** `event_id`
      (deterministic — Meta will deduplicate the browser + server
      pair).

## 17. Platform verification results

- **Meta Events Manager** — cannot be inspected from the preview
  container (external UI). See "Propagation Pending" below.
- **Meta Test Events tool** — `META_CAPI_TEST_EVENT_CODE` env var
  supported by `services/analytics_tracker._send_to_meta`; when set,
  every CAPI event is diverted to Meta's Test Events console for
  live inspection.
- **GA4 DebugView** — accessible only with the GA4 property owner's
  Google account. See "Propagation Pending" below.

## 18. Remaining propagation delays / manual verification steps

The following are external to this repository and must be verified in
platform UIs after the frontend is exposed to real traffic (or via
Meta's Test Events tool for immediate feedback):

- **Meta catalog match rate** — was 36.4 %. Expected to rise once the
  per-lot pixel events reach Meta and the catalog decomposed rows
  attribute. Meta refreshes the match-rate metric hourly.
- **Product-view match rate** — was 0 %. This should recover to
  matching-live percentages as soon as multi-lot users generate
  `ViewContent` events with per-lot IDs.
- **Google Merchant Center** — Google recrawls the RSS feed on its own
  schedule (typically 24 h). No change to feed content in this pass;
  match should carry through unchanged.
- **Google Ads** — if the user creates a Purchase conversion action
  and pastes the label into `REACT_APP_GOOGLE_ADS_PURCHASE_LABEL`,
  Ads will start receiving native Purchase conversions on top of the
  GA4-imported ones.

## 19. Any unresolved issues

None blocking. Two follow-ups are surfaced for the user's decision:

1. **Google Ads Purchase conversion label** — dormant until the label
   is supplied via env. No implementation blocker; GA4 attribution
   is fully functional without it.
2. **Meta Test Events code** — `META_CAPI_TEST_EVENT_CODE` remains
   unset in `backend/.env`. Setting it once briefly gives instant
   confirmation in Meta's Test Events tab.

---

**Confirmation of guard-rails (verbatim):**

- ✅ No changes to tax logic.
- ✅ No changes to fee calculations.
- ✅ No changes to commission rules.
- ✅ No changes to Stripe payment / capture / payout / settlement
  business logic.
- ✅ No changes to escrow / deposits / penalties / reserve-price logic.
- ✅ No changes to the 1,049 P7 golden regression tests or their
  snapshot fixtures.
- ✅ No P6 work started.
- ✅ No deployment performed. All changes remain in PREVIEW.
