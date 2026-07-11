/**
 * MarketingPixelLoader — iter178 (FIX 7)
 * =======================================
 * On app boot, fetches /api/site-config and injects Facebook Pixel + GTM
 * snippets if the admin has saved IDs in site_config.marketing.
 *
 * Exposes window.bvTrackEvent(name, params) for the rest of the app to call:
 *   bvTrackEvent('ViewContent', { content_ids: [id], value, currency: 'CAD' })
 *   bvTrackEvent('AddToCart',   { value, currency: 'CAD' })
 *   bvTrackEvent('Purchase',    { value, currency: 'CAD' })
 * A single global function fans out to both fbq and dataLayer (GTM).
 */
import { useEffect } from 'react';
import axios from 'axios';
import API_BASE from '../config';
import { initMetaPixel } from '../utils/metaPixel';

const injectFbPixel = (id) => {
  if (!id || window.__bv_fb_loaded) return;
  window.__bv_fb_loaded = true;
  // iter341 — SINGLE injection point: utils/metaPixel owns the fbq bootstrap
  // (consent-gated, CAPI-deduped). Re-initializing here with the same ID was
  // the source of Meta's "Duplicate Pixel ID" console warning.
  initMetaPixel();
};

const injectGtm = (id) => {
  if (!id || window.__bv_gtm_loaded) return;

  const isGA4 = /^G-/i.test(id);   // GA4 / gtag.js
  const isGTM = /^GTM-/i.test(id); // Tag Manager container

  // Skip if the hardcoded GA4 tag in index.html already loaded the same ID
  if (isGA4 && (window.__bv_ga4_loaded || (Array.isArray(window.dataLayer) && window.dataLayer.some(e => e && e[0] === 'config' && e[1] === id)))) {
    window.__bv_gtm_loaded = true;
    return;
  }

  window.__bv_gtm_loaded = true;
  window.dataLayer = window.dataLayer || [];

  if (isGA4) {
    // GA4 / gtag.js path
    const s = document.createElement('script');
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
    document.head.appendChild(s);
    function gtag(){ window.dataLayer.push(arguments); }
    window.gtag = window.gtag || gtag;
    window.gtag('js', new Date());
    window.gtag('config', id);
    window.__bv_ga4_loaded = true;
  } else if (isGTM) {
    // Google Tag Manager path
    window.dataLayer.push({ 'gtm.start': new Date().getTime(), event: 'gtm.js' });
    const s = document.createElement('script');
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(id)}`;
    document.head.appendChild(s);
  } else {
    // Unknown format — do nothing rather than load the wrong loader
    // eslint-disable-next-line no-console
    console.warn('[Marketing] Unknown Google tag ID format:', id);
  }
};

// Public fan-out event helper
window.bvTrackEvent = (name, params = {}) => {
  try { window.fbq && window.fbq('track', name, params); } catch (_) {}
  try { window.dataLayer && window.dataLayer.push({ event: name, ...params }); } catch (_) {}
};

const MarketingPixelLoader = () => {
  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/site-config`);
        const m = r.data?.marketing || {};
        injectFbPixel(m.fb_pixel_id);
        injectGtm(m.gtm_id);
      } catch (_) {
        /* silent — marketing is optional */
      }
    })();
  }, []);
  return null;
};

export default MarketingPixelLoader;
