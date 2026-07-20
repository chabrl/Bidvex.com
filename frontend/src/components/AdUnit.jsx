/**
 * iter364 — Google AdSense ad unit wrapper.
 *
 * Environment-aware rendering: on production (`www.bidvex.com` or the
 * launchapp production host) the real `<ins class="adsbygoogle">` tag is
 * emitted and `(adsbygoogle = window.adsbygoogle || []).push({})` fires;
 * on preview/dev a labelled placeholder box renders instead so the layout
 * gap matches without triggering AdSense errors (or wasting impressions).
 *
 * Publisher ID (LIVE): ca-pub-5626625571065443 (Charbel's approved AdSense).
 * The publisher ID can be overridden via REACT_APP_ADSENSE_CLIENT env var
 * (useful for staging accounts, sub-brands, or A-B tests). Per-slot IDs
 * come from REACT_APP_ADSENSE_SLOT_* env vars.
 */
import React, { useEffect, useRef } from 'react';

const PROD_HOSTS = new Set([
  'www.bidvex.com',
  'bidvex.com',
  'launchapp-4-r-1774886029.emergent.host',
]);

const isProdHost = () => {
  if (typeof window === 'undefined') return false;
  return PROD_HOSTS.has(window.location.hostname);
};

// Live publisher ID; env-var override supported.
const CLIENT = process.env.REACT_APP_ADSENSE_CLIENT || 'ca-pub-5626625571065443';
const isConfigured = CLIENT.startsWith('ca-pub-') && !CLIENT.includes('X');

export default function AdUnit({
  slot,
  format = 'auto',
  layout = null,
  layoutKey = null,
  style = {},
  className = '',
  testId = 'ad-unit',
  label = 'Advertisement',
}) {
  const initRef = useRef(false);
  const shouldRenderReal = isProdHost() && isConfigured && slot;

  useEffect(() => {
    if (!shouldRenderReal) return;
    if (initRef.current) return;
    initRef.current = true;
    try {
      // eslint-disable-next-line no-multi-assign
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (err) {
      // AdSense not yet loaded — script defer/async retry handles this.
      if (typeof console !== 'undefined') console.warn('[AdUnit] push failed:', err?.message);
    }
  }, [shouldRenderReal, slot]);

  // Dev / preview placeholder — shows the ad zone so layout QA is honest.
  if (!shouldRenderReal) {
    return (
      <div
        className={`ad-unit-container ad-unit-container--placeholder ${className}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f4f4f4',
          border: '2px dashed #cbd5e1',
          borderRadius: 8,
          color: '#94a3b8',
          fontSize: 12,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          margin: '16px 0',
          minHeight: 90,
          ...style,
        }}
        aria-label={label}
        data-testid={`${testId}-placeholder`}
      >
        {label} · Ad zone {slot ? `#${slot}` : '(unconfigured)'}
      </div>
    );
  }

  return (
    <div className={`ad-unit-container ${className}`} style={style} data-testid={testId}>
      <ins
        className="adsbygoogle"
        style={{ display: 'block', ...style }}
        data-ad-client={CLIENT}
        data-ad-slot={slot}
        data-ad-format={format}
        {...(layout    ? { 'data-ad-layout': layout }         : {})}
        {...(layoutKey ? { 'data-ad-layout-key': layoutKey }   : {})}
        data-full-width-responsive="true"
      />
    </div>
  );
}
