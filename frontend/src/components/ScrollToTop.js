import { useEffect, useLayoutEffect } from 'react';
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

  // Use useLayoutEffect for synchronous DOM mutation before paint
  // This ensures scroll happens immediately before the browser paints
  useLayoutEffect(() => {
    // Force scroll to absolute top - use multiple methods for browser compatibility
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0; // For Safari compatibility
  }, [pathname]);

  // Also handle cases where content loads async
  useEffect(() => {
    // Small timeout to catch any async content rendering
    const timeoutId = setTimeout(() => {
      if (window.scrollY !== 0) {
        window.scrollTo(0, 0);
      }
    }, 50);
    
    return () => clearTimeout(timeoutId);
  }, [pathname]);

  return null; // This component doesn't render anything
};

export default ScrollToTop;
