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

const injectFbPixel = (id) => {
  if (!id || window.__bv_fb_loaded) return;
  window.__bv_fb_loaded = true;
  /* eslint-disable */
  !function(f,b,e,v,n,t,s)
  {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}(window, document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  /* eslint-enable */
  try { window.fbq('init', id); window.fbq('track', 'PageView'); } catch (_) {}
};

const injectGtm = (id) => {
  if (!id || window.__bv_gtm_loaded) return;
  window.__bv_gtm_loaded = true;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({ 'gtm.start': new Date().getTime(), event: 'gtm.js' });
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtm.js?id=${id}`;
  document.head.appendChild(s);
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
