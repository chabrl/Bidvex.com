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
  marketplace:    'MKT',
  single:         'MKT',
  product:        'MKT',
  lots:           'LOT',
  multi_lot:      'LOT',
  multi_item:     'LOT',
  vehicle:        'VEH',
  vehicles:       'VEH',
  vehicle_dealer: 'VEH',
  storage:        'STO',
  storage_locker: 'STO',
  storage_unit:   'STO',
};

// Canonical (long-form) listing type used for content_type metadata.
const CANONICAL_TYPE = {
  MKT: 'marketplace',
  LOT: 'multi_lot',
  VEH: 'vehicle',
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
 * @param {object} listing  — listing payload (must have .id)
 * @param {object} [opts]   — { routeHint }
 * @returns {string|null}
 */
export const getCanonicalContentId = (listing, opts = {}) => {
  if (!listing || !listing.id) return null;
  const type = deriveListingType({ listing, routeHint: opts.routeHint });
  const prefix = TYPE_PREFIX[type] || 'MKT';
  return `BIDVEX-${prefix}-${listing.id}`;
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
