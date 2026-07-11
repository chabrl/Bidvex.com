import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { trackPageView } from '../utils/metaPixel';

/**
 * iter342 — thin route-change listener. ALL pixel logic (init, PageView
 * dedupe) lives in utils/metaPixel.js, the single source of truth.
 */
const FbPixelTracker = () => {
  const location = useLocation();

  useEffect(() => {
    trackPageView(`${location.pathname}${location.search}`);
  }, [location.pathname, location.search]);

  return null;
};

export default FbPixelTracker;
