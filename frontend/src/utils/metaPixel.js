/**
 * BidVex — Meta Pixel + Conversions API funnel wrapper.
 *
 * Funnel stages this module supports (matches Meta Commerce Manager schema):
 *   1. ViewContent       — fires once per (listing, session) on detail-page mount
 *   2. AddToCart         — fires once per (listing, session) on first "Bid Now"
 *                          / "Place Bid" CTA interaction (intent signal)
 *   3. InitiateCheckout  — fires every time the user submits a bid (commit)
 *   4. Purchase          — fires once per (listing, session) on payment success.
 *                          Backend CAPI fires the matching server-side event with
 *                          the SAME `event_id` so Meta deduplicates.
 *
 * `content_ids` are ALWAYS sourced from `getCanonicalContentId(...)` in
 * `utils/metaContentId.js` — the single source of truth. Format must match
 * exactly what `backend/services/meta_feed_mapper.py::_content_id()` writes
 * to the catalog feed.
 *
 * Init/consent: pixel only loads when REACT_APP_META_PIXEL_ID is set AND
 * the user has granted analytics consent (CASL compliance via the cookie
 * banner). Events emitted before consent are queued in memory and replayed
 * once the pixel boots; if consent is never granted the queue is silently
 * dropped.
 */
import {
  getCanonicalContentId,
  getCanonicalContentType,
  getCanonicalListingType,
  buildEventId,
} from './metaContentId';

const PIXEL_ID = process.env.REACT_APP_META_PIXEL_ID;

// Canonical CASL consent key. The CookieConsentBanner writes 'true' here
// when analytics is accepted, 'false' on refusal / revocation.
const CONSENT_KEY_CANONICAL = 'bidvex_analytics_consent';
const CONSENT_KEY_BANNER_STORE = 'bidvex_cookie_consent_v2';
const CONSENT_KEY_PRIMARY = 'cookieConsent';
const CONSENT_KEY_ANALYTICS = 'analytics_consent';

let _initAttempted = false;
let _initialized = false;
let _lastPageViewPath = null;
const _queue = [];

// ── SPA dedupe protection (per-tab, per-session) ────────────────────
// React Router can re-mount the same detail page across navigations and
// React StrictMode double-invokes effects in dev. Without dedup, Meta
// would see multiple ViewContent or AddToCart events for the same
// listing in one session — inflating funnel counts and degrading EMQ.
// Keys are scoped per event-kind to allow `AddToCart` and `ViewContent`
// to fire independently.
//
// Storage is sessionStorage-backed (survives intra-tab navigation, dies
// with the tab) plus in-memory fallback when sessionStorage is unavailable
// (private mode, server-side render).
const _DEDUPE_KEY = 'bidvex_meta_pixel_session_dedupe_v1';
let _memoryDedupe = null;

const _readDedupeSet = () => {
  if (_memoryDedupe) return _memoryDedupe;
  if (typeof window === 'undefined') {
    _memoryDedupe = new Set();
    return _memoryDedupe;
  }
  try {
    const raw = window.sessionStorage.getItem(_DEDUPE_KEY);
    _memoryDedupe = new Set(raw ? JSON.parse(raw) : []);
  } catch (e) {
    _memoryDedupe = new Set();
  }
  return _memoryDedupe;
};

const _persistDedupeSet = () => {
  if (typeof window === 'undefined' || !_memoryDedupe) return;
  try {
    window.sessionStorage.setItem(
      _DEDUPE_KEY,
      JSON.stringify(Array.from(_memoryDedupe)),
    );
  } catch (e) {
    // sessionStorage full / unavailable — in-memory still works
  }
};

const _wasFired = (kind, contentId) => {
  if (!kind || !contentId) return false;
  const key = `${kind}:${contentId}`;
  return _readDedupeSet().has(key);
};

const _markFired = (kind, contentId) => {
  if (!kind || !contentId) return;
  const key = `${kind}:${contentId}`;
  _readDedupeSet().add(key);
  _persistDedupeSet();
};

/**
 * Clears the in-session dedupe cache. Exposed for testing + for the
 * cookie-banner revocation flow.
 */
export const __resetDedupe = () => {
  _memoryDedupe = new Set();
  if (typeof window !== 'undefined') {
    try { window.sessionStorage.removeItem(_DEDUPE_KEY); } catch (e) { /* noop */ }
  }
};

const _hasConsent = () => {
  if (typeof window === 'undefined') return false;
  try {
    const canonical = window.localStorage.getItem(CONSENT_KEY_CANONICAL);
    if (canonical === 'true') return true;
    if (canonical === 'false') return false;
    const bannerRaw = window.localStorage.getItem(CONSENT_KEY_BANNER_STORE);
    if (bannerRaw) {
      try {
        const parsed = JSON.parse(bannerRaw);
        if (parsed && parsed.analytics === true) return true;
        if (parsed && parsed.analytics === false) return false;
      } catch (parseErr) {
        console.debug('[meta-pixel] consent JSON parse failed:', parseErr);
      }
    }
    const v1 = window.localStorage.getItem(CONSENT_KEY_PRIMARY);
    const v2 = window.localStorage.getItem(CONSENT_KEY_ANALYTICS);
    return v1 === 'accepted' || v1 === 'all' || v2 === 'true' || v2 === 'accepted';
  } catch (consentReadErr) {
    console.debug('[meta-pixel] consent read failed:', consentReadErr);
    return false;
  }
};

const _loadFbqScript = () => {
  _installFbqStub();
  // Load the real fbevents.js exactly once (the stub never auto-loads it).
  if (!document.querySelector('script[src*="fbevents.js"]')) {
    const t = document.createElement('script');
    t.async = true;
    t.src = 'https://connect.facebook.net/en_US/fbevents.js';
    const s = document.getElementsByTagName('script')[0];
    if (s && s.parentNode) s.parentNode.insertBefore(t, s);
    else document.head.appendChild(t);
  }
};

/**
 * iter342 — fbq stub with a built-in `init` dedupe guard.
 *
 * The duplicate "Duplicate Pixel ID" warning was NOT caused by our JS: the
 * admin's GTM container (GTM-MQ34GTF4) carries its own Meta Pixel tag that
 * calls fbq('init', …) twice per page load. We cannot edit the GTM
 * container from code, so the stub itself swallows any repeat init for a
 * pixel ID already initialised this page load — guaranteeing exactly ONE
 * fbq('init') per pixel per page load regardless of the caller (our code,
 * GTM, or any third-party snippet).
 *
 * Installed at module import time so it exists BEFORE GTM's snippet runs
 * (GTM's bootstrap keeps a pre-existing window.fbq: `if (f.fbq) return`).
 */
const _installFbqStub = () => {
  if (typeof window === 'undefined' || window.fbq) return;
  const seenInits = new Set();
  const n = function () {
    if (arguments[0] === 'init') {
      const id = String(arguments[1] || '');
      if (seenInits.has(id)) {
        console.debug('[meta-pixel] duplicate fbq(init) swallowed for pixel', id);
        return;
      }
      seenInits.add(id);
      window._fbPixelInitialized = true;
    }
    if (n.callMethod) n.callMethod.apply(n, arguments);
    else n.queue.push(arguments);
  };
  window.fbq = n;
  if (!window._fbq) window._fbq = n;
  n.push = n;
  n.loaded = true;
  n.version = '2.0';
  n.queue = [];
};

// Install the guarded stub as early as possible (module import runs before
// MarketingPixelLoader fetches site-config and injects GTM).
if (typeof window !== 'undefined') _installFbqStub();

const _flushQueue = () => {
  if (!_initialized || typeof window === 'undefined' || !window.fbq) return;
  while (_queue.length) {
    const { name, params, custom, eventId } = _queue.shift();
    try {
      const opts = eventId ? { eventID: eventId } : undefined;
      if (custom) window.fbq('trackCustom', name, params, opts);
      else window.fbq('track', name, params, opts);
    } catch (flushErr) {
      console.debug('[meta-pixel] flush event swallowed:', name, flushErr);
    }
  }
};

/** Initializes the pixel if env var + consent are present. Safe to call repeatedly. */
export const initMetaPixel = () => {
  if (_initAttempted || _initialized) return;
  if (typeof window === 'undefined') return;
  if (!PIXEL_ID) {
    // eslint-disable-next-line no-console
    console.warn('[BidVex] Meta Pixel ID not configured. Set REACT_APP_META_PIXEL_ID in .env');
    _initAttempted = true;
    return;
  }
  if (!_hasConsent()) return; // defer until consent

  _initAttempted = true;
  try {
    // iter342 — window-scoped guard: fbq('init') must run exactly ONCE per
    // page load, or Meta logs "Duplicate Pixel ID". Survives repeated
    // callers (App boot, MarketingPixelLoader, consent re-grants).
    if (window._fbPixelInitialized) {
      _initialized = true;
      _flushQueue();
      return;
    }
    window._fbPixelInitialized = true;
    _loadFbqScript();
    window.fbq('init', PIXEL_ID);
    // Initial PageView — record the path so the route-change tracker
    // (trackPageView) never double-fires for the landing route.
    _lastPageViewPath = `${window.location.pathname}${window.location.search}`;
    window.fbq('track', 'PageView');
    _initialized = true;
    _flushQueue();
  } catch (initErr) {
    console.debug('[meta-pixel] init failed (swallowed):', initErr);
  }
};

/**
 * PageView — SINGLE entry point for SPA route-change tracking (iter342).
 * Dedupes by path: fires exactly once per distinct route, never on
 * re-renders, and never duplicates the initial PageView fired by init.
 */
export const trackPageView = (path) => {
  if (typeof window === 'undefined' || typeof window.fbq !== 'function') return;
  const p = path || `${window.location.pathname}${window.location.search}`;
  if (p === _lastPageViewPath) return;
  _lastPageViewPath = p;
  try { window.fbq('track', 'PageView'); }
  catch (e) { console.debug('[meta-pixel] PageView swallowed:', e); }
};

export const notifyConsentGranted = () => {
  if (typeof window !== 'undefined') {
    try { window.localStorage.setItem(CONSENT_KEY_CANONICAL, 'true'); }
    catch (e) { console.debug('[meta-pixel] consent localStorage write failed:', e); }
  }
  if (_initialized) return; // iter341 — already live, never re-init
  _initAttempted = false;
  initMetaPixel();
};

export const revokeConsent = () => {
  if (typeof window === 'undefined') return;
  try { window.localStorage.setItem(CONSENT_KEY_CANONICAL, 'false'); }
  catch (e) { console.debug('[meta-pixel] revoke localStorage write failed:', e); }
  try { if (window.fbq) window.fbq('consent', 'revoke'); }
  catch (e) { console.debug('[meta-pixel] revoke fbq() failed:', e); }
  _queue.length = 0;
  _initialized = false;
  __resetDedupe();
};

const _enqueue = (name, params, custom = false, eventId = null) => {
  if (typeof window === 'undefined') return;
  if (_initialized && window.fbq) {
    try {
      const opts = eventId ? { eventID: eventId } : undefined;
      if (custom) window.fbq('trackCustom', name, params, opts);
      else window.fbq('track', name, params, opts);
    } catch (trackErr) {
      console.debug('[meta-pixel] trackEvent swallowed:', name, trackErr);
    }
    return;
  }
  _queue.push({ name, params, custom, eventId });
  if (_queue.length > 50) _queue.shift();
};

export const trackEvent = (eventName, params = {}, eventId = null) =>
  _enqueue(eventName, params, false, eventId);
export const trackCustomEvent = (eventName, params = {}, eventId = null) =>
  _enqueue(eventName, params, true, eventId);

// ── Listing → price extractor ───────────────────────────────────────
const _extractPrice = (listing) => {
  if (!listing) return 0;
  const candidates = [
    listing.current_bid,
    listing.current_price,
    listing.starting_bid,
    listing.starting_price,
  ];
  for (const v of candidates) {
    if (typeof v === 'number' && v > 0) return v;
  }
  return 0;
};

// ── Public funnel events ────────────────────────────────────────────

/**
 * ViewContent — fires on detail-page mount. Dedupe-safe per (listing, session).
 *
 * @param {object} listing — listing payload from API
 * @param {object} [opts]  — { routeHint }
 */
export const trackViewContent = (listing, opts = {}) => {
  if (!listing || !listing.id) return;
  const contentId = getCanonicalContentId(listing, opts);
  if (!contentId) return;
  if (_wasFired('ViewContent', contentId)) {
    console.debug('[meta-pixel] ViewContent deduped:', contentId);
    return;
  }
  _markFired('ViewContent', contentId);

  const contentType = getCanonicalContentType(listing, opts);
  const value = _extractPrice(listing);
  const params = {
    content_ids: [contentId],
    content_type: contentType,
    content_name: listing.title || '',
    content_category: listing.category || '',
    value: parseFloat(Number(value).toFixed(2)),
    currency: listing.currency || 'CAD',
    city: listing.city || listing.location?.city || '',
    region: listing.region || listing.province || listing.location?.province || '',
    country: 'CA',
  };
  const eventId = buildEventId({
    eventName: 'ViewContent',
    contentId,
    discriminator: `s${_sessionStamp()}`,
  });
  trackEvent('ViewContent', params, eventId);
};

export const trackAddToWishlist = (listing, price, opts = {}) => {
  if (!listing || !listing.id) return;
  const contentId = getCanonicalContentId(listing, opts);
  if (!contentId) return;
  trackEvent('AddToWishlist', {
    content_ids: [contentId],
    content_type: getCanonicalContentType(listing, opts),
    value: parseFloat(Number(price || _extractPrice(listing) || 0).toFixed(2)),
    currency: listing.currency || 'CAD',
  });
};

/**
 * AddToCart — fires when the user clicks the "Bid Now" / "Place Bid" CTA
 * (intent signal). Dedupe-safe per (listing, session) — multiple bid
 * attempts during the same session emit only ONE AddToCart event, which
 * aligns with Meta's funnel optimization recommendations.
 *
 * @param {object} args
 * @param {object} args.listing      — listing payload
 * @param {number} args.bidAmount    — intended bid amount (CAD)
 * @param {string} [args.routeHint]
 */
export const trackAddToCart = ({ listing, bidAmount, routeHint } = {}) => {
  if (!listing || !listing.id) return;
  const contentId = getCanonicalContentId(listing, { routeHint });
  if (!contentId) return;
  if (_wasFired('AddToCart', contentId)) {
    console.debug('[meta-pixel] AddToCart deduped:', contentId);
    return;
  }
  _markFired('AddToCart', contentId);

  const params = {
    content_ids: [contentId],
    content_type: getCanonicalContentType(listing, { routeHint }),
    content_name: listing.title || '',
    content_category: listing.category || '',
    value: parseFloat(Number(bidAmount || _extractPrice(listing) || 0).toFixed(2)),
    currency: listing.currency || 'CAD',
    num_items: 1,
  };
  const eventId = buildEventId({
    eventName: 'AddToCart',
    contentId,
    discriminator: `s${_sessionStamp()}`,
  });
  trackEvent('AddToCart', params, eventId);
};

/**
 * InitiateCheckout — fires every time a bid is successfully submitted to
 * the backend. NOT dedupe-protected: multiple InitiateCheckout signals
 * during a bidding war strengthen Meta's optimization signal.
 *
 * @param {object} args
 * @param {object} args.listing      — listing payload
 * @param {number} args.bidAmount    — submitted bid amount (CAD)
 * @param {number} [args.lotNumber]  — sub-lot # for multi-item auctions
 * @param {string} [args.routeHint]
 */
export const trackInitiateCheckout = ({ listing, bidAmount, lotNumber, routeHint } = {}) => {
  if (!listing || !listing.id) return;
  const contentId = getCanonicalContentId(listing, { routeHint });
  if (!contentId) return;

  const params = {
    content_ids: [contentId],
    content_type: getCanonicalContentType(listing, { routeHint }),
    content_name: listing.title || '',
    content_category: listing.category || '',
    value: parseFloat(Number(bidAmount || _extractPrice(listing) || 0).toFixed(2)),
    currency: listing.currency || 'CAD',
    num_items: 1,
  };
  if (lotNumber != null) params.contents = [{ id: contentId, quantity: 1, item_price: params.value }];

  // Each bid is a distinct InitiateCheckout — discriminator is bid amount +
  // millisecond timestamp to ensure uniqueness across rapid re-bids.
  const eventId = buildEventId({
    eventName: 'InitiateCheckout',
    contentId,
    discriminator: `${Math.round(Number(bidAmount || 0) * 100)}_${Date.now()}`,
  });
  trackEvent('InitiateCheckout', params, eventId);
};

/**
 * Purchase — fires once per (listing, session) when payment is confirmed.
 * The `event_id` MUST match what backend CAPI emits so Meta deduplicates.
 *
 * @param {object} args
 * @param {string} args.listingId        — listing UUID
 * @param {string} args.listingType      — canonical type ('marketplace'|'vehicle'|'storage'|'multi_lot')
 * @param {number} args.totalCharged     — full CAD amount the buyer paid
 * @param {string} [args.eventId]        — server-supplied deterministic event_id
 * @param {string} [args.title]
 * @param {string} [args.category]
 */
export const trackPurchase = ({
  listingId,
  listingType,
  totalCharged,
  eventId,
  title,
  category,
} = {}) => {
  if (!listingId) return;
  const fakeListing = { id: listingId, listing_type: listingType, title, category };
  const contentId = getCanonicalContentId(fakeListing, { routeHint: listingType });
  if (!contentId) return;
  if (_wasFired('Purchase', contentId)) {
    console.debug('[meta-pixel] Purchase deduped:', contentId);
    return;
  }
  _markFired('Purchase', contentId);

  const params = {
    content_ids: [contentId],
    content_type: getCanonicalContentType(fakeListing, { routeHint: listingType }),
    content_name: title || '',
    content_category: category || '',
    value: parseFloat(Number(totalCharged || 0).toFixed(2)),
    currency: 'CAD',
    num_items: 1,
  };
  const finalEventId =
    eventId ||
    buildEventId({
      eventName: 'Purchase',
      contentId,
      discriminator: `local_${Date.now()}`,
    });
  trackEvent('Purchase', params, finalEventId);
};

export const trackSearch = ({ searchString, category, city, province }) => {
  trackEvent('Search', {
    search_string: searchString || '',
    content_category: category || '',
    city: city || '',
    region: province || '',
    country: 'CA',
  });
};

// ── Internals exposed for unit tests / debugging ────────────────────
const _sessionStamp = () => {
  // Date stamp (UTC YYYYMMDD) — gives a coarse session bucket without
  // needing to coordinate with auth. Combined with the per-listing dedupe
  // set, this caps each user to N ViewContent / AddToCart per content per
  // day, which matches Meta's recommended pixel hygiene.
  try {
    const d = new Date();
    return `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, '0')}${String(d.getUTCDate()).padStart(2, '0')}`;
  } catch (e) {
    return '0';
  }
};

// Re-export canonical helpers so callers don't need to import 2 modules.
export {
  getCanonicalContentId,
  getCanonicalContentType,
  getCanonicalListingType,
  buildEventId,
};

// Backwards-compat: legacy helper used by older call sites. Prefer
// `getCanonicalContentId(listing, opts)` going forward.
export const buildContentId = (listingType, listingId) => {
  if (!listingId) return null;
  return getCanonicalContentId({ id: listingId, listing_type: listingType }, { routeHint: listingType });
};

export const __debug = {
  pixelId: PIXEL_ID,
  isInitialized: () => _initialized,
  queueLength: () => _queue.length,
  dedupeSet: () => Array.from(_readDedupeSet()),
};
