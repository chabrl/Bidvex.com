import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Fires Meta (Facebook) Pixel PageView on every SPA route change.
 * The initial PageView is already fired in /public/index.html; this covers
 * subsequent in-app navigations (React Router push/replace).
 */
const FbPixelTracker = () => {
  const location = useLocation();

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.fbq !== 'function') return;
    try {
      window.fbq('track', 'PageView');
    } catch {
      /* swallow — never let analytics break the app */
    }
  }, [location.pathname, location.search]);

  return null;
};

export default FbPixelTracker;
