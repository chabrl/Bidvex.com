import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * FeatureFlagsContext
 * 
 * Provides global marketplace feature flags to the entire application.
 * These flags are fetched from the public /api/marketplace/feature-flags endpoint
 * and can be toggled by admins in the Marketplace Settings panel.
 * 
 * Features controlled:
 * - enable_buy_now: Show/hide Buy Now buttons globally
 * - allow_all_users_multi_lot: Allow non-business users to create multi-lot auctions
 * - enable_anti_sniping: Enable auction time extension on last-minute bids
 * - anti_sniping_window_minutes: The window for anti-sniping extension
 * - minimum_bid_increment: Minimum bid increment for auctions
 */

const FeatureFlagsContext = createContext({
  flags: {
    enable_buy_now: true,
    allow_all_users_multi_lot: true,
    enable_anti_sniping: true,
    anti_sniping_window_minutes: 2,
    minimum_bid_increment: 1.0,
  },
  loading: true,
  error: null,
  refreshFlags: () => {},
  canCreateMultiLot: () => true,
});

export const useFeatureFlags = () => {
  const context = useContext(FeatureFlagsContext);
  if (!context) {
    throw new Error('useFeatureFlags must be used within a FeatureFlagsProvider');
  }
  return context;
};

export const FeatureFlagsProvider = ({ children }) => {
  const [flags, setFlags] = useState({
    enable_buy_now: true,
    allow_all_users_multi_lot: true,
    enable_anti_sniping: true,
    anti_sniping_window_minutes: 2,
    minimum_bid_increment: 1.0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchFlags = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/marketplace/feature-flags`);
      setFlags(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch feature flags:', err);
      setError(err.message);
      // Keep default values on error
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch flags on mount
  useEffect(() => {
    fetchFlags();
  }, [fetchFlags]);

  // Refresh flags periodically (every 5 minutes) to catch admin changes
  useEffect(() => {
    const interval = setInterval(fetchFlags, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchFlags]);

  /**
   * Check if a user can create multi-lot auctions
   * @param {object} user - The user object with account_type
   * @returns {boolean} - Whether the user can create multi-lot auctions
   */
  const canCreateMultiLot = useCallback((user) => {
    if (!user) return false;
    
    // Business accounts can always create multi-lot auctions
    if (user.account_type === 'business') return true;
    
    // Personal accounts can only create if the flag is enabled
    return flags.allow_all_users_multi_lot === true;
  }, [flags.allow_all_users_multi_lot]);

  const value = {
    flags,
    loading,
    error,
    refreshFlags: fetchFlags,
    canCreateMultiLot,
  };

  return (
    <FeatureFlagsContext.Provider value={value}>
      {children}
    </FeatureFlagsContext.Provider>
  );
};

export default FeatureFlagsContext;
