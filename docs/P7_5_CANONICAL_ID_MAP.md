# P7.5 — Canonical Product / Catalog ID Map

**Status:** VERIFIED — locked by 23 regression tests (`tests/p7_5/`).
**Scope:** Meta Commerce Catalog, Google Merchant Center, GA4 ecommerce, Meta Pixel + CAPI.
**Rule:** the same string MUST appear in ALL of:

- Meta catalog feed `id`
- Google Merchant feed `<g:id>`
- Meta Pixel `content_ids[0]`
- Meta CAPI `content_ids[0]`
- GA4 ecommerce `items[0].item_id`
- Google Ads Enhanced Conversions events

---

## 1. MongoDB source of truth

BidVex stores a **UUID string in the `id` field** on every listing document
(NOT the Mongo `_id` ObjectId). Feed mappers and pixel helpers only ever
read the `id` field:

| Collection                    | Doc `id` field  | Used for                                    |
|-------------------------------|-----------------|---------------------------------------------|
| `listings`                    | `listing.id`    | Marketplace single listing                  |
| `multi_item_listings`         | `listing.id`    | Multi-lot parent auction                    |
| `multi_item_listings.lots[]`  | `lot.lot_number`| Per-lot decomposition (int sequence 1…N)    |
| `vehicles` / `vehicle_listings` | `vehicle.id`  | Vehicle single listing                      |
| `vehicle_multi_lot_auctions`  | `event.id`      | Vehicle multi-lot parent event              |
| `vehicle_multi_lot_auctions.lots[]` | `lot.id`  | Per-lot vehicle UUID                        |
| `storage_auctions`            | `storage.id`    | Storage locker single listing               |

---

## 2. Canonical ID formats

All formats produced by:

- **Feed (Meta + Google, backend):** `services/meta_feed_mapper.py::_content_id`
  and `map_multi_lot_listing_to_meta_items` (parent + per-lot decomposition).
- **Pixel + GA4 (frontend):** `utils/metaContentId.js::getCanonicalContentId`
  / `getLotContentId`.
- **CAPI (backend):** `services/analytics_tracker.py::canonical_content_id`
  / `canonical_lot_content_id`.

| BidVex surface                | Canonical ID format                       | Example                                       |
|-------------------------------|-------------------------------------------|-----------------------------------------------|
| Marketplace single listing    | `<listing.id>` (raw UUID)                 | `9c8f5d2a-1e3b-4b21-b7de-abcdef012345`        |
| Vehicle single listing        | `<vehicle.id>` (raw UUID)                 | `veh-2b1e-40c1-a6a1-5f8f8d3c4a11`             |
| Storage single listing        | `<storage.id>` (raw UUID)                 | `stg-6a91-11ee-9812-0a3d76b1c1c9`             |
| Multi-lot **parent** (general)| `<listing.id>` (raw UUID) — legacy view   | `mli-71a2-c9e1-84fd-1234567890ab`             |
| Multi-lot **per lot** (general) | `LOT-<parent_id>-L<lot_number>`         | `LOT-mli-71a2-c9e1-84fd-1234567890ab-L1`      |
| Vehicle multi-lot **parent**  | `<event.id>` (raw UUID) — legacy view     | `vml-2f7c-486f-b2f9-abcdef012345`             |
| Vehicle multi-lot **per lot** | `VML-<event.id>-<lot_id[:8]>`             | `VML-vml-2f7c-486f-b2f9-abcdef012345-0123abcd`|

**Purchasable-row rule (Meta + Google):** For multi-lot auctions the
CATALOG only exposes per-lot rows (Meta + Google both list purchasable
lots, not the parent event). Parent rows are only surfaced for
single-listing types. Pixel + GA4 events therefore MUST use the
per-lot format on any multi-lot bid / view.

---

## 3. Live-preview example

The example below is illustrative — the exact IDs vary by seed. Any
production preview listing follows the same rule.

**Multi-lot general auction (5 lots):**

- Parent record — `multi_item_listings.id`:
  ```
  b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21
  ```
- Meta / Google catalog rows emitted (5 items):
  ```
  LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L1
  LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L2
  LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3
  LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L4
  LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L5
  ```
- Meta Pixel `content_ids` (when a buyer bids on lot 3):
  ```
  ["LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3"]
  ```
- GA4 `items[0].item_id`:
  ```
  "LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3"
  ```
- Meta CAPI `content_ids[0]` (via `track_listing_purchase(..., lot_ref=3)`):
  ```
  "LOT-b25d1c8e-1f45-4d69-9b2c-4c48f4b73a21-L3"
  ```

All 5 surfaces are BYTE-IDENTICAL.

---

## 4. Frontend → Backend contract map

| Frontend caller                                          | Content id produced                                     | Backend equivalent                                                       |
|----------------------------------------------------------|---------------------------------------------------------|--------------------------------------------------------------------------|
| `getCanonicalContentId({id})`                            | `<id>`                                                  | `canonical_content_id(listing_type, id)`                                 |
| `getLotContentId(parent, lot, {routeHint:"multi_lot"})`  | `LOT-<parent.id>-L<lot.lot_number>`                     | `canonical_lot_content_id("lots"\|"multi_lot", parent_id, lot_number)`   |
| `getLotContentId(event, lot, {routeHint:"vehicle_multi_lot"})` | `VML-<event.id>-<lot.id[:8]>`                     | `canonical_lot_content_id("vehicle_multi_lot", event_id, lot_id)`        |

---

## 5. What locks this contract

- **23 P7.5 regression tests** in `/app/backend/tests/p7_5/test_canonical_content_id.py`
  cross-check:
    - Singleton IDs match the feed mapper output.
    - Multi-lot IDs match the feed decomposition.
    - GA4 `items[].item_id` == Meta `content_ids[0]` for the same catalog row.
    - Language (EN/FR) has no influence on the resolved ID.
- **P7 financial regression matrix** (1,049 tests) — untouched; no
  fee, tax or settlement code was modified.
- **Meta Pixel funnel tests** (`test_meta_pixel_funnel.py`,
  `test_iter218_meta_pixel_integration.py`) still pass, confirming the
  existing Meta CAPI ↔ Pixel deduplication contract survives the
  per-lot addition.

---

## 6. Do NOT
- Do not prefix `<listing.id>` for singleton listings — Google Merchant
  Center compares `<g:id>` to the landing-page id and rejects mismatches.
- Do not use `_id` (Mongo ObjectId) on any surface — the frontend never
  sees ObjectIds.
- Do not mutate case, add whitespace, or URL-encode the id — Meta match
  is byte-exact after Unicode normalisation.
- Do not fire ViewContent / AddToCart with the parent listing id on a
  multi-lot page — this is the specific bug that produced the 0%
  product-view match rate; use `getLotContentId(...)` instead.
