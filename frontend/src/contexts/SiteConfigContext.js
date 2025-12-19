import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * SiteConfigContext
 * 
 * Provides global site configuration including:
 * - Branding (logo, colors, typography)
 * - Homepage layout (section visibility and order)
 * - Hero banners
 * 
 * Injects CSS variables for theming across the entire application.
 */

const DEFAULT_CONFIG = {
  branding: {
    logo_url: null,
    logo_type: 'default',
    primary_color: '#3B82F6',
    secondary_color: '#10B981',
    accent_color: '#8B5CF6',
    surface_color: '#F8FAFC',
    font_family: 'Inter',
  },
  homepage_layout: {
    sections: [
      { id: 'hero_banner', name: 'Hero Banner', visible: true, order: 0 },
      { id: 'homepage_banner', name: 'Banner Carousel', visible: true, order: 1 },
      { id: 'ending_soon', name: 'Ending Soon', visible: true, order: 2 },
      { id: 'featured', name: 'Featured Auctions', visible: true, order: 3 },
      { id: 'browse_items', name: 'Browse Individual Items', visible: true, order: 4 },
      { id: 'new_listings', name: 'New Listings', visible: true, order: 5 },
      { id: 'recently_sold', name: 'Recently Sold', visible: true, order: 6 },
      { id: 'recently_viewed', name: 'Recently Viewed', visible: true, order: 7 },
      { id: 'hot_items', name: 'Hot Items', visible: true, order: 8 },
      { id: 'top_sellers', name: 'Top Sellers', visible: true, order: 9 },
      { id: 'how_it_works', name: 'How It Works', visible: true, order: 10 },
      { id: 'trust_features', name: 'Trust Features', visible: true, order: 11 },
    ]
  },
  hero_banners: []
};

const SiteConfigContext = createContext({
  config: DEFAULT_CONFIG,
  loading: true,
  error: null,
  refreshConfig: () => {},
  isSectionVisible: () => true,
  getSectionOrder: () => 0,
});

export const useSiteConfig = () => {
  const context = useContext(SiteConfigContext);
  if (!context) {
    throw new Error('useSiteConfig must be used within a SiteConfigProvider');
  }
  return context;
};

// Helper to convert hex to RGB for CSS
const hexToRgb = (hex) => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (result) {
    return `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`;
  }
  return null;
};

export const SiteConfigProvider = ({ children }) => {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchConfig = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/site-config`);
      setConfig(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch site config:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch config on mount
  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Refresh config periodically (every 30 seconds for quick updates)
  useEffect(() => {
    const interval = setInterval(fetchConfig, 30 * 1000);
    return () => clearInterval(interval);
  }, [fetchConfig]);

  // Apply CSS variables when branding changes
  useEffect(() => {
    if (config?.branding) {
      const root = document.documentElement;
      const branding = config.branding;
      
      // Primary color
      if (branding.primary_color) {
        root.style.setProperty('--primary', branding.primary_color);
        const rgb = hexToRgb(branding.primary_color);
        if (rgb) root.style.setProperty('--primary-rgb', rgb);
      }
      
      // Secondary color
      if (branding.secondary_color) {
        root.style.setProperty('--secondary', branding.secondary_color);
        const rgb = hexToRgb(branding.secondary_color);
        if (rgb) root.style.setProperty('--secondary-rgb', rgb);
      }
      
      // Accent color
      if (branding.accent_color) {
        root.style.setProperty('--accent', branding.accent_color);
        const rgb = hexToRgb(branding.accent_color);
        if (rgb) root.style.setProperty('--accent-rgb', rgb);
      }
      
      // Surface color
      if (branding.surface_color) {
        root.style.setProperty('--surface', branding.surface_color);
      }
      
      // Font family
      if (branding.font_family) {
        root.style.setProperty('--font-family', `"${branding.font_family}", sans-serif`);
        // Also load the Google Font
        const fontLink = document.getElementById('google-font-link');
        if (fontLink) {
          fontLink.href = `https://fonts.googleapis.com/css2?family=${branding.font_family.replace(' ', '+')}:wght@300;400;500;600;700&display=swap`;
        } else {
          const link = document.createElement('link');
          link.id = 'google-font-link';
          link.rel = 'stylesheet';
          link.href = `https://fonts.googleapis.com/css2?family=${branding.font_family.replace(' ', '+')}:wght@300;400;500;600;700&display=swap`;
          document.head.appendChild(link);
        }
      }
    }
  }, [config?.branding]);

  /**
   * Check if a homepage section is visible
   */
  const isSectionVisible = useCallback((sectionId) => {
    if (!config?.homepage_layout?.sections) return true;
    const section = config.homepage_layout.sections.find(s => s.id === sectionId);
    return section ? section.visible : true;
  }, [config?.homepage_layout?.sections]);

  /**
   * Get the order of a homepage section
   */
  const getSectionOrder = useCallback((sectionId) => {
    if (!config?.homepage_layout?.sections) return 0;
    const section = config.homepage_layout.sections.find(s => s.id === sectionId);
    return section ? section.order : 0;
  }, [config?.homepage_layout?.sections]);

  const value = {
    config,
    loading,
    error,
    refreshConfig: fetchConfig,
    isSectionVisible,
    getSectionOrder,
  };

  return (
    <SiteConfigContext.Provider value={value}>
      {children}
    </SiteConfigContext.Provider>
  );
};

export default SiteConfigContext;
