/**
 * iter371 — ScrollToTop hardened.
 *
 * Resets scroll to the top on every route change with three failsafes so
 * that async content (image lazy-load, layout shifts, React Router's own
 * scroll restore) can't leave the user mid-page:
 *   1. `useLayoutEffect` — fires before the browser paints. Immediate reset.
 *   2. `requestAnimationFrame` — catches the first paint after mount.
 *   3. Delayed timeouts (60 ms + 300 ms + 700 ms) — catches late layout
 *      shifts from lazy-loaded images, iframes, ads, etc.
 *
 * The reset is skipped when the URL contains an anchor (`#foo`) so the
 * browser's native hash-scroll still works, and when the URL carries a
 * `?buy_now=1` or `?lot=N` param that a page consumes for a deep-link
 * scroll (MultiItemListingDetailPage uses these to smooth-scroll into a
 * specific lot from external routes).
 */
import { useEffect, useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';

const forceScrollTop = () => {
  try {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  } catch { /* older browsers */ }
  window.scrollTo(0, 0);
  if (document.documentElement) document.documentElement.scrollTop = 0;
  if (document.body) document.body.scrollTop = 0;
};

const ScrollToTop = () => {
  const { pathname, hash, search } = useLocation();

  // Skip when the URL has an anchor (browser handles it) or when a page
  // uses ?lot=N to deep-link scroll into a specific lot.
  const skip = !!hash || /[?&](lot|buy_now|target_lot)=/.test(search);

  useLayoutEffect(() => {
    if (skip) return;
    forceScrollTop();
  }, [pathname, skip]);

  useEffect(() => {
    if (skip) return;
    // Chain of failsafes for async content settlement.
    const raf = requestAnimationFrame(forceScrollTop);
    const t1 = setTimeout(forceScrollTop, 60);
    const t2 = setTimeout(forceScrollTop, 300);
    const t3 = setTimeout(forceScrollTop, 700);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [pathname, skip]);

  return null;
};

export default ScrollToTop;
