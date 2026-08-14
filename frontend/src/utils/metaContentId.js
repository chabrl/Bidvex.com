/**
 * BidVex — Canonical Meta content_id helper (single source of truth).
 *
 * EVERY pixel/CAPI event (ViewContent, AddToCart, InitiateCheckout, Purchase)
 * MUST resolve its `content_ids` via `getCanonicalContentId(...)` from this
 * module. The output format MUST match exactly what
 * `backend/services/meta_feed_mapper.py::_content_id()` writes to the Meta
 * Commerce catalog feed — otherwise Meta's match rate drops to 0%.
 *
 * Format: BIDVEX-{MKT|LOT|VEH|STO}-{listing_id}
 *
 * Listing-type derivation is route-first (most reliable signal because the
 * URL is set by React Router from a typed route), then listing-payload, then
 * a category-keyword fallback. Nullable DB `listing_type` values are NEVER
 * trusted in isolation.
 */
// Type → prefix. Mirror of meta_feed_mapper.py::TYPE_PREFIX.
const TYPE_PREFIX = {
  marketplace:      'MKT',
  single:           'MKT',
  product:          'MKT',
  lots:             'LOT',
  multi_lot:        'LOT',
  multi_item:       'LOT',
  vehicle:          'VEH',
  vehicles:         'VEH',
  vehicle_dealer:   'VEH',
  vehicle_multi_lot:'VML',
  storage:          'STO',
  storage_locker:   'STO',
  storage_unit:     'STO',
};

// Canonical (long-form) listing type used for content_type metadata.
const CANONICAL_TYPE = {
  MKT: 'marketplace',
  LOT: 'multi_lot',
  VEH: 'vehicle',
  VML: 'vehicle_multi_lot',
  STO: 'storage',
};

// Vehicle / car / auto category keywords (matches backend logic in
// ListingDetailPage's identity guard).
const _VEHICLE_KEYWORDS = ['vehicle', 'vehicles', 'car', 'auto', 'voiture'];

/**
 * Derive listing type from the most reliable signals available.
 *
 * Resolution order (each step short-circuits when it has a confident answer):
 *   1. Explicit `routeHint` (page passed e.g. routeHint: 'vehicle')
 *   2. window.location.pathname segment heuristics
 *   3. listing.listing_type (only when non-null)
 *   4. listing.category keyword sweep for vehicles
 *   5. Default: 'marketplace'
 */
export const deriveListingType = ({ listing, routeHint } = {}) => {
  // 1) explicit hint from caller — most reliable
  if (routeHint && TYPE_PREFIX[routeHint]) return routeHint;

  // 2) URL inference
  if (typeof window !== 'undefined' && window.location) {
    const path = (window.location.pathname || '').toLowerCase();
    if (path.includes('/vehicle-auctions/') || path.includes('/vehicles/')) return 'vehicle';
    if (path.includes('/storage-auctions/')) return 'storage';
    if (path.includes('/lots/') || path.includes('/multi-item-listings/')) return 'multi_lot';
    if (path.includes('/listing/') || path.includes('/listings/') || path.includes('/marketplace')) {
      return 'marketplace';
    }
  }

  // 3) non-null listing_type from DB
  if (listing && listing.listing_type && TYPE_PREFIX[listing.listing_type]) {
    return listing.listing_type;
  }

  // 4) category keyword sweep
  const cat = (listing && listing.category ? String(listing.category) : '').toLowerCase();
  if (cat && _VEHICLE_KEYWORDS.some((k) => cat.includes(k))) return 'vehicle';

  // 5) default
  return 'marketplace';
};

/**
 * Returns the canonical content_id string that MUST appear in every
 * pixel/CAPI event for this listing.
 *
 * iter224 hotfix — Format is now the RAW `listing.id` (UUID string). Earlier
 * iterations used a `BIDVEX-{TYPE}-{id}` token to embed type metadata, but
 * that broke Google Merchant Center's `id ↔ link page id` validation and
 * Meta catalog match rate. Per the directive, Pixel content_ids MUST equal
 * the catalog item id EXACTLY (no prefix, no reformatting). The backend
 * mapper (`services/meta_feed_mapper.py::_content_id`) returns the same.
 *
 * @param {object} listing  — listing payload (must have .id)
 * @returns {string|null}
 */
export const getCanonicalContentId = (listing) => {
  if (!listing || !listing.id) return null;
  return String(listing.id);
};

/**
 * P7.5 — Returns the canonical PER-LOT content_id used by Meta + Google
 * for multi-lot auctions. Must match the backend decomposition rule in
 * `services/meta_feed_mapper.py::map_multi_lot_listing_to_meta_items`:
 *
 *   general multi-lot (ltype "lots"):
 *     "LOT-{parent_id}-L{lot_number}"
 *   vehicle multi-lot (ltype "vehicle_multi_lot"):
 *     "VML-{parent_id}-{lot_id[:8]}"
 *
 * Returns `null` when the inputs are insufficient.
 *
 * @param {object} parentListing — parent auction payload (must have .id)
 * @param {object} lot           — lot payload (must have .lot_number for LOT,
 *                                 or .id for VML)
 * @param {object} [opts]        — { routeHint }
 * @returns {string|null}
 */
export const getLotContentId = (parentListing, lot, opts = {}) => {
  if (!parentListing || !parentListing.id || !lot) return null;
  const parentId = String(parentListing.id);
  const type = deriveListingType({ listing: parentListing, routeHint: opts.routeHint });
  if (type === 'vehicle_multi_lot') {
    const lotId = lot.id != null ? String(lot.id) : null;
    if (!lotId) return null;
    return `VML-${parentId}-${lotId.slice(0, 8)}`;
  }
  // General multi-lot fallback (also covers 'lots', 'multi_lot', 'multi_item').
  const lotNumber = lot.lot_number != null ? String(lot.lot_number) : null;
  if (!lotNumber) return null;
  return `LOT-${parentId}-L${lotNumber}`;
};

/**
 * Returns the canonical Meta `content_type` ("product" or "vehicle") for a
 * given listing. Meta requires this for catalog match scoring.
 */
export const getCanonicalContentType = (listing, opts = {}) => {
  const type = deriveListingType({ listing, routeHint: opts.routeHint });
  return type === 'vehicle' ? 'vehicle' : 'product';
};

/**
 * Returns the long-form canonical listing-type label ('marketplace', 'vehicle',
 * 'multi_lot', 'storage'). Useful for backend payloads.
 */
export const getCanonicalListingType = (listing, opts = {}) => {
  const type = deriveListingType({ listing, routeHint: opts.routeHint });
  const prefix = TYPE_PREFIX[type] || 'MKT';
  return CANONICAL_TYPE[prefix] || 'marketplace';
};

/**
 * Deterministic event_id generator — shared between browser pixel and
 * backend CAPI so Meta can deduplicate identical events. Format:
 *   bidvex_{eventName}_{contentId}_{discriminator?}
 *
 * - For Purchase, the discriminator is the Stripe `session_id` or
 *   `invoice_id`, ensuring a single Purchase event per checkout completion.
 * - For InitiateCheckout, the discriminator is a timestamp + random suffix.
 * - For ViewContent / AddToCart, the discriminator is the date-stamped
 *   session — these are dedup-protected client-side and don't strictly
 *   need server-side parity.
 */
export const buildEventId = ({ eventName, contentId, discriminator }) => {
  if (!eventName || !contentId) return null;
  const parts = ['bidvex', eventName.toLowerCase(), contentId];
  if (discriminator) parts.push(String(discriminator));
  return parts.join('_').replace(/\s+/g, '');
};

export const __debug_TYPE_PREFIX = TYPE_PREFIX;
