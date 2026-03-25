import API_BASE from '../config';
/**
 * SiteModeContext - Provides site mode state across the application
 * Used to enforce maintenance/coming soon mode globally
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const API = `${API_BASE}/api`;

const SiteModeContext = createContext({
  mode: 'live',
  message: null,
  expectedBack: null,
  socialLinks: null,
  loading: true,
  isMaintenanceOrComingSoon: false,
  refresh: () => {}
});

export const SiteModeProvider = ({ children }) => {
  const [mode, setMode] = useState('live');
  const [message, setMessage] = useState(null);
  const [expectedBack, setExpectedBack] = useState(null);
  const [socialLinks, setSocialLinks] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchSiteMode = async () => {
    try {
      const response = await axios.get(`${API}/site-mode`);
      setMode(response.data.mode || 'live');
      setMessage(response.data.message);
      setExpectedBack(response.data.expected_back);
      setSocialLinks(response.data.social_links);
    } catch (error) {
      console.error('Error fetching site mode:', error);
      // Default to live mode on error
      setMode('live');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSiteMode();
    
    // Refresh every 30 seconds to catch mode changes
    const interval = setInterval(fetchSiteMode, 30000);
    return () => clearInterval(interval);
  }, []);

  const isMaintenanceOrComingSoon = mode === 'maintenance' || mode === 'coming_soon';

  return (
    <SiteModeContext.Provider value={{
      mode,
      message,
      expectedBack,
      socialLinks,
      loading,
      isMaintenanceOrComingSoon,
      refresh: fetchSiteMode
    }}>
      {children}
    </SiteModeContext.Provider>
  );
};

export const useSiteMode = () => {
  const context = useContext(SiteModeContext);
  if (!context) {
    throw new Error('useSiteMode must be used within a SiteModeProvider');
  }
  return context;
};

export default SiteModeContext;
