import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * ScrollToTop Component
 * 
 * A global utility component that resets the browser's scroll position
 * to the top-left corner (0, 0) on every route change.
 * 
 * This ensures users always see the top of the page when navigating,
 * preventing the "opening at the bottom" issue common in SPAs.
 * 
 * Works across all major browsers (Chrome, Safari, Firefox) and mobile devices.
 */
const ScrollToTop = () => {
  const { pathname } = useLocation();

  useEffect(() => {
    // Instant scroll to top on route change
    // Using 'instant' behavior to prevent any "jumping" effect
    // and ensure the scroll happens before content renders
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: 'instant'
    });
  }, [pathname]);

  return null; // This component doesn't render anything
};

export default ScrollToTop;
