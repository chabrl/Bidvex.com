/**
 * analytics_events.js — Centralised gtag helpers for Google Analytics 4
 * and Google Ads conversion events.
 *
 * The Global Site Tag (G-… for GA4 and AW-18140095337 for Ads) is loaded
 * from `public/index.html` and exposes `window.gtag`. The helpers below
 * guard against environments where the tag failed to load (ad-blockers,
 * cookie-consent rejection, server-side renders, etc.) so callers can
 * always invoke them without try/catch.
 *
 * P7.5 additions:
 * ──────────────────────────────────────────────────────────────────────
 * Recommended GA4 ecommerce events (view_item / add_to_cart / purchase)
 * are wired here. The `items[].item_id` value MUST equal the exact
 * BidVex catalog ID that appears in:
 *   - Meta Commerce Manager catalog feed (services/meta_feed_mapper.py)
 *   - Google Merchant Center feed (services/google_feed_mapper.py)
 * The same `getCanonicalContentId` / `getLotContentId` helpers used by
 * the Meta Pixel are reused so all three surfaces stay byte-identical.
 *
 * Enhanced Conversions for Web (Google Ads) is a small wrapper around
 * `gtag('set', 'user_data', {...})` that ships hashed email/phone.
 * Hashing is done client-side via SubtleCrypto SHA-256 before the value
 * ever leaves the browser (Google requires SHA-256 hex, lowercase).
 *
 * ──────────────────────────────────────────────────────────────────────
 * Adding more conversion events later
 * ──────────────────────────────────────────────────────────────────────
 * Once Google Ads gives you a new Conversion Label (e.g.
 *   `AW-18140095337/AbC-DeFG_hIjKlMn`),
 * either call `trackPartnerRegistrationConversion("AbC-DeFG_hIjKlMn")`
 * directly or wire it into the relevant component success handler.
 */

const ADS_ACCOUNT_ID = 'AW-18140095337';

// Optional Google Ads Purchase conversion label (from Google Ads →
// Conversions → New action). When set, `trackGoogleAdsPurchase` fires
// the `AW-…/label` conversion in addition to GA4 `purchase`. Without
// it, GA4 `purchase` alone still drives Ads attribution via the
// GA4↔Ads link. Empty string / missing = no-op (graceful).
const ADS_PURCHASE_LABEL = process.env.REACT_APP_GOOGLE_ADS_PURCHASE_LABEL || '';

/** Returns the gtag function if it exists, otherwise a no-op. */
const safeGtag = (...args) => {
  if (typeof window === 'undefined') return;
  if (typeof window.gtag !== 'function') {
    // eslint-disable-next-line no-console
    console.debug('[analytics] gtag unavailable — event dropped:', args[1]);
    return;
  }
  try {
    window.gtag(...args);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn('[analytics] gtag threw:', err);
  }
};

/**
 * Fire a Google Ads conversion event for a successful Partner Registration.
 *
 * Usage (from a component, once the registration POST succeeds):
 *
 *   import { trackPartnerRegistrationConversion } from '../utils/analytics_events';
 *   // ...
 *   trackPartnerRegistrationConversion('AbC-DeFG_hIjKlMn');
 *
 * Or, with `value` / `currency` overrides:
 *
 *   trackPartnerRegistrationConversion('AbC-DeFG_hIjKlMn', {
 *     value: 1.0,
 *     currency: 'CAD',
 *     transaction_id: someUniqueId,
 *   });
 *
 * @param {string} conversionLabel
 *   The 16+ char conversion label from Google Ads (the bit AFTER the slash
 *   in `AW-XXXX/<label>`). Required.
 * @param {object} [extras]
 *   Optional override fields: { value, currency, transaction_id, ... }.
 */
export const trackPartnerRegistrationConversion = (conversionLabel, extras = {}) => {
  if (!conversionLabel || typeof conversionLabel !== 'string') {
    // eslint-disable-next-line no-console
    console.warn('[analytics] trackPartnerRegistrationConversion missing conversionLabel — skipped');
    return;
  }
  const payload = {
    send_to: `${ADS_ACCOUNT_ID}/${conversionLabel}`,
    value: 1.0,
    currency: 'CAD',
    ...extras,
  };
  safeGtag('event', 'conversion', payload);
};

/**
 * Generic helper for any other conversion event we add later.
 * Example: trackAdsConversion('AbC-DeFG_hIjKlMn', { value: 19.99, currency: 'CAD' });
 */
export const trackAdsConversion = (conversionLabel, extras = {}) => {
  if (!conversionLabel) return;
  safeGtag('event', 'conversion', {
    send_to: `${ADS_ACCOUNT_ID}/${conversionLabel}`,
    ...extras,
  });
};

/** Wrapper for GA4 custom events (non-Ads). */
export const trackGAEvent = (eventName, params = {}) => {
  if (!eventName) return;
  safeGtag('event', eventName, params);
};

// ─────────────────────────────────────────────────────────────────
// P7.5 — GA4 Ecommerce Events
// ─────────────────────────────────────────────────────────────────
// The `items[]` array MUST carry the BidVex catalog ID exactly:
//   • single listings  →  `<listing.id>` (raw UUID)
//   • multi-lot lots   →  `LOT-<parent>-L<lot_number>` (general)
//   • vehicle multi-lot→  `VML-<parent>-<lot_id[:8]>`
// Callers pass a pre-resolved `contentId` to keep this layer free of
// listing-type inference.
// ─────────────────────────────────────────────────────────────────

/**
 * GA4 `view_item` — fires on detail page mount.
 *
 * @param {object} args
 * @param {string} args.contentId    — canonical catalog ID
 * @param {number} args.value        — item value (current bid or price)
 * @param {string} [args.itemName]   — listing.title
 * @param {string} [args.itemCategory]
 * @param {string} [args.currency='CAD']
 */
export const trackGA4ViewItem = ({
  contentId,
  value,
  itemName,
  itemCategory,
  currency = 'CAD',
} = {}) => {
  if (!contentId) return;
  safeGtag('event', 'view_item', {
    currency,
    value: parseFloat(Number(value || 0).toFixed(2)),
    items: [{
      item_id: String(contentId),
      item_name: itemName || '',
      item_category: itemCategory || '',
      price: parseFloat(Number(value || 0).toFixed(2)),
      quantity: 1,
    }],
  });
};

/**
 * GA4 `add_to_cart` — fires on the qualifying commerce action.
 * For BidVex this is the "Place Bid" CTA (bid intent).
 */
export const trackGA4AddToCart = ({
  contentId,
  value,
  itemName,
  itemCategory,
  currency = 'CAD',
} = {}) => {
  if (!contentId) return;
  safeGtag('event', 'add_to_cart', {
    currency,
    value: parseFloat(Number(value || 0).toFixed(2)),
    items: [{
      item_id: String(contentId),
      item_name: itemName || '',
      item_category: itemCategory || '',
      price: parseFloat(Number(value || 0).toFixed(2)),
      quantity: 1,
    }],
  });
};

/**
 * GA4 `purchase` — fires ONLY on confirmed Stripe payment success.
 * `transactionId` MUST be the Stripe session_id (or an equally unique,
 * deterministic id) so GA4 dedupes duplicate purchase events.
 */
export const trackGA4Purchase = ({
  contentId,
  value,
  transactionId,
  itemName,
  itemCategory,
  currency = 'CAD',
} = {}) => {
  if (!contentId || !transactionId) return;
  const numericValue = parseFloat(Number(value || 0).toFixed(2));
  safeGtag('event', 'purchase', {
    transaction_id: String(transactionId),
    currency,
    value: numericValue,
    items: [{
      item_id: String(contentId),
      item_name: itemName || '',
      item_category: itemCategory || '',
      price: numericValue,
      quantity: 1,
    }],
  });
};

/**
 * Google Ads Purchase conversion — fires only when
 * `REACT_APP_GOOGLE_ADS_PURCHASE_LABEL` is set. Uses the same
 * transaction_id GA4 uses so Ads dedupes across replays.
 *
 * iter482 P2-followup — Defense-in-depth idempotence: the function
 * self-guards against firing more than once per (browser tab, transactionId)
 * via `sessionStorage`. Callers may also install their own upstream
 * guard (as `PaymentSuccessPage` does) — either alone is sufficient,
 * both together makes duplicate firing impossible short of clearing
 * session storage manually.
 */
const GOOGLE_ADS_TRACKED_KEY_PREFIX = 'bidvex_gads_conversion_';

export const trackGoogleAdsPurchase = ({
  value,
  transactionId,
  currency = 'CAD',
} = {}) => {
  if (!ADS_PURCHASE_LABEL || !transactionId) return;
  // Self-guard: skip if this exact transaction was already reported
  // from this browser tab.
  const guardKey = `${GOOGLE_ADS_TRACKED_KEY_PREFIX}${transactionId}`;
  try {
    if (typeof window !== 'undefined'
        && window.sessionStorage
        && window.sessionStorage.getItem(guardKey)) {
      return;
    }
  } catch (_e) { /* sessionStorage may be blocked */ }
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      window.sessionStorage.setItem(guardKey, String(Date.now()));
    }
  } catch (_e) { /* ignore */ }
  safeGtag('event', 'conversion', {
    send_to: `${ADS_ACCOUNT_ID}/${ADS_PURCHASE_LABEL}`,
    value: parseFloat(Number(value || 0).toFixed(2)),
    currency,
    transaction_id: String(transactionId),
  });
};

// ─────────────────────────────────────────────────────────────────
// P7.5 — Google Enhanced Conversions for Web
// ─────────────────────────────────────────────────────────────────
// Ships SHA-256-hashed customer identifiers via
// gtag('set', 'user_data', {...}) so Google can match the conversion
// against a signed-in user account (only used when Enhanced Conversions
// is enabled for the conversion action in Google Ads).
// Hashing is performed client-side; raw PII never leaves the browser.
// ─────────────────────────────────────────────────────────────────
const _sha256Hex = async (value) => {
  if (typeof value !== 'string' || !value) return null;
  const normalized = value.trim().toLowerCase();
  if (!normalized) return null;
  if (
    typeof window === 'undefined' ||
    !window.crypto ||
    !window.crypto.subtle ||
    typeof window.crypto.subtle.digest !== 'function' ||
    typeof TextEncoder === 'undefined'
  ) {
    return null;
  }
  try {
    const buf = new TextEncoder().encode(normalized);
    const digest = await window.crypto.subtle.digest('SHA-256', buf);
    const bytes = new Uint8Array(digest);
    let hex = '';
    for (let i = 0; i < bytes.length; i += 1) {
      hex += bytes[i].toString(16).padStart(2, '0');
    }
    return hex;
  } catch (e) {
    console.debug('[analytics] Enhanced Conversions hash failed:', e);
    return null;
  }
};

const _phoneDigits = (raw) => {
  if (!raw) return null;
  const d = String(raw).replace(/[^0-9]/g, '');
  return d || null;
};

/**
 * Sets Google Enhanced Conversions user_data. Safe to call before or
 * after the `purchase` gtag event fires — Google associates it with
 * the same session's next conversion event.
 *
 * @param {object} identity
 * @param {string} [identity.email]
 * @param {string} [identity.phone]
 */
export const setEnhancedConversionsUserData = async (identity = {}) => {
  const email = identity.email ? String(identity.email) : null;
  const phone = _phoneDigits(identity.phone);
  const [emailHash, phoneHash] = await Promise.all([
    _sha256Hex(email),
    _sha256Hex(phone),
  ]);
  const userData = {};
  if (emailHash) userData.sha256_email_address = emailHash;
  if (phoneHash) userData.sha256_phone_number = phoneHash;
  if (Object.keys(userData).length === 0) return;
  safeGtag('set', 'user_data', userData);
};

export default {
  trackPartnerRegistrationConversion,
  trackAdsConversion,
  trackGAEvent,
  trackGA4ViewItem,
  trackGA4AddToCart,
  trackGA4Purchase,
  trackGoogleAdsPurchase,
  setEnhancedConversionsUserData,
};
