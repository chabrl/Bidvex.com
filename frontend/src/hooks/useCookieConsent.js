import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'bidvex_cookie_consent_v2';

const DEFAULT_CONSENT = {
  strictly_necessary: true,
  functionality: false,
  analytics: false,
  marketing: false,
};

/**
 * useCookieConsent — manages cookie preference state in localStorage.
 *
 * Privacy-by-Default:
 *   All non-essential categories start as false.
 *   Third-party scripts (GA, FB Pixel) must check `consent.analytics`
 *   or `consent.marketing` before loading.
 *
 * Usage:
 *   const { consent, hasConsented, acceptAll, refuseAll, saveCustom, resetConsent } = useCookieConsent();
 *   if (consent.analytics) { loadGoogleAnalytics(); }
 */
export function useCookieConsent() {
  const [consent, setConsent] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch { /* ignore */ }
    return null;
  });

  // Listen for cross-component resets via custom storage events
  useEffect(() => {
    const handler = (e) => {
      if (e.key === STORAGE_KEY) {
        if (e.newValue === null) {
          setConsent(null);
        } else {
          try { setConsent(JSON.parse(e.newValue)); } catch { /* ignore */ }
        }
      }
    };
    window.addEventListener('storage', handler);

    // Custom event for same-tab communication
    const customHandler = () => setConsent(null);
    window.addEventListener('bidvex-cookie-reset', customHandler);

    return () => {
      window.removeEventListener('storage', handler);
      window.removeEventListener('bidvex-cookie-reset', customHandler);
    };
  }, []);

  const hasConsented = consent !== null;

  const persist = useCallback((next) => {
    const record = { ...next, timestamp: new Date().toISOString() };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
    setConsent(record);
  }, []);

  const acceptAll = useCallback(() => {
    persist({
      strictly_necessary: true,
      functionality: true,
      analytics: true,
      marketing: true,
    });
  }, [persist]);

  const refuseAll = useCallback(() => {
    persist({ ...DEFAULT_CONSENT });
  }, [persist]);

  const saveCustom = useCallback((prefs) => {
    persist({ strictly_necessary: true, ...prefs });
  }, [persist]);

  const resetConsent = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setConsent(null);
    // Notify other hook instances in the same tab
    window.dispatchEvent(new Event('bidvex-cookie-reset'));
  }, []);

  // Gate helper — returns true only if the given category was explicitly accepted
  const isAllowed = useCallback((category) => {
    if (!consent) return false;
    return !!consent[category];
  }, [consent]);

  return { consent, hasConsented, acceptAll, refuseAll, saveCustom, resetConsent, isAllowed };
}

export { STORAGE_KEY, DEFAULT_CONSENT };
