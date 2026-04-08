import { useCallback, useRef } from 'react';
import API_BASE from '../config';

/**
 * User Insights Tracking Hook
 * Logs user interactions (views, clicks, bids, searches) to the backend
 * for personalized recommendations and behavioral profiling.
 */
export const useInsightsTracker = () => {
  const queueRef = useRef([]);
  const flushTimerRef = useRef(null);

  const flush = useCallback(async () => {
    if (queueRef.current.length === 0) return;
    const batch = [...queueRef.current];
    queueRef.current = [];

    try {
      await fetch(`${API_BASE}/api/insights/track-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(batch),
      });
    } catch (e) {
      // Silent fail — tracking should never block UX
    }
  }, []);

  const track = useCallback((eventType, data = {}) => {
    queueRef.current.push({
      event_type: eventType,
      listing_id: data.listingId || null,
      category: data.category || null,
      price: data.price || null,
      search_query: data.searchQuery || null,
      region: data.region || null,
      city: data.city || null,
      metadata: data.metadata || null,
    });

    // Debounce flush: send batch every 2 seconds
    if (flushTimerRef.current) clearTimeout(flushTimerRef.current);
    flushTimerRef.current = setTimeout(flush, 2000);

    // Immediate flush if batch gets large
    if (queueRef.current.length >= 10) flush();
  }, [flush]);

  const trackView = useCallback((listingId, category, region) => {
    track('view', { listingId, category, region });
  }, [track]);

  const trackClick = useCallback((listingId, category) => {
    track('click', { listingId, category });
  }, [track]);

  const trackBid = useCallback((listingId, price, category) => {
    track('bid', { listingId, price, category });
  }, [track]);

  const trackSearch = useCallback((query) => {
    track('search', { searchQuery: query });
  }, [track]);

  const trackPaymentPreference = useCallback((paymentMethod, listingId) => {
    track('payment_preference', { listingId, metadata: { payment_method: paymentMethod } });
  }, [track]);

  const trackOpcInterest = useCallback((listingId, bpPercent) => {
    track('opc_interest', { listingId, metadata: { bp_percent: bpPercent, zero_fee: bpPercent === 0 } });
  }, [track]);

  return { track, trackView, trackClick, trackBid, trackSearch, trackPaymentPreference, trackOpcInterest };
};
