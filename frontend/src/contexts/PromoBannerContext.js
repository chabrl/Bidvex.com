/**
 * iter256 — PromoBannerContext
 *
 * Lightweight context that tracks the live rendered height of the
 * platform-wide promotional banner stack. Consumers (the fixed Navbar
 * and the global content spacer) read `bannerHeight` and shift their
 * own `top` / spacer height accordingly so the red promo banner is
 * NEVER trapped behind the fixed white navigation header on mobile.
 *
 * Why a context (not a CSS var or a window event)?
 *   - React-native ResizeObserver works seamlessly inside the banner
 *     component which already owns its DOM ref.
 *   - The Navbar is rendered as a sibling, so it can't traverse to the
 *     banner ref directly; the context bridges that gap with zero
 *     prop-drilling.
 *   - Re-renders are bounded — bannerHeight only changes when the
 *     banner stack mounts, unmounts, or wraps onto a new line.
 *
 * Provider lives at the top of `App.js` so EVERY route inherits the
 * dynamic stack. Outside the provider, `useBannerHeight()` safely
 * returns 0 (no jank in unit tests that mount components in isolation).
 */
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

const PromoBannerContext = createContext({
  bannerHeight: 0,
  setBannerHeight: () => {},
});

export const PromoBannerProvider = ({ children }) => {
  const [bannerHeight, setBannerHeightState] = useState(0);

  // Stable setter so the banner's ResizeObserver effect doesn't tear
  // down on every render of the provider.
  const setBannerHeight = useCallback((next) => {
    setBannerHeightState((prev) => {
      const rounded = Math.max(0, Math.round(Number(next) || 0));
      return rounded === prev ? prev : rounded;
    });
  }, []);

  const value = useMemo(
    () => ({ bannerHeight, setBannerHeight }),
    [bannerHeight, setBannerHeight]
  );

  return (
    <PromoBannerContext.Provider value={value}>
      {children}
    </PromoBannerContext.Provider>
  );
};

export const usePromoBanner = () => useContext(PromoBannerContext);

export const useBannerHeight = () => useContext(PromoBannerContext).bannerHeight;

export default PromoBannerContext;
