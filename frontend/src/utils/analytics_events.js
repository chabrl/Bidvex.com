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
 * ──────────────────────────────────────────────────────────────────────
 * Adding more conversion events later
 * ──────────────────────────────────────────────────────────────────────
 * Once Google Ads gives you a new Conversion Label (e.g.
 *   `AW-18140095337/AbC-DeFG_hIjKlMn`),
 * either call `trackPartnerRegistrationConversion("AbC-DeFG_hIjKlMn")`
 * directly or wire it into the relevant component success handler.
 */

const ADS_ACCOUNT_ID = 'AW-18140095337';

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

export default {
  trackPartnerRegistrationConversion,
  trackAdsConversion,
  trackGAEvent,
};
