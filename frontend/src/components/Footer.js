import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Footer = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [footerLinks, setFooterLinks] = useState(null);
  const language = i18n.language || 'en';

  useEffect(() => {
    fetchFooterLinks();
  }, [language]);

  const fetchFooterLinks = async () => {
    try {
      const response = await axios.get(`${API}/site-config/legal-pages?language=${language}`);
      
      if (response.data.success) {
        setFooterLinks(response.data.pages);
      }
    } catch (error) {
      console.error('[Footer] Error fetching links:', error);
      // Keep default links on error
    }
  };

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'fr' : 'en';
    i18n.changeLanguage(newLang);
  };

  const handleLinkClick = (e, link) => {
    // Handle different link types
    if (link.link_type === 'chatbot') {
      e.preventDefault();
      // Trigger AI chatbot (assuming you have a global handler)
      const event = new CustomEvent('openAIChatbot');
      window.dispatchEvent(event);
    } else if (link.link_type === 'mailto' && link.link_value) {
      // mailto links work naturally
      return;
    }
    // Regular page links work naturally via Link component
  };

  const renderLink = (pageKey, defaultTitle, defaultPath) => {
    const linkData = footerLinks?.[pageKey];
    const title = linkData?.title || t(`footer.${pageKey}`, defaultTitle);
    const linkType = linkData?.link_type || 'page';
    const linkValue = linkData?.link_value || defaultPath;

    if (linkType === 'mailto') {
      return (
        <a 
          href={`mailto:${linkValue}`} 
          className="hover:text-white transition-colors text-sm"
        >
          {title}
        </a>
      );
    } else if (linkType === 'chatbot') {
      return (
        <button
          onClick={(e) => handleLinkClick(e, linkData)}
          className="hover:text-white transition-colors text-sm"
        >
          {title}
        </button>
      );
    } else {
      return (
        <Link 
          to={linkValue} 
          className="hover:text-white transition-colors text-sm"
        >
          {title}
        </Link>
      );
    }
  };

  return (
    <footer className="bg-gray-900 text-gray-300 py-8 mt-20">
      <div className="max-w-7xl mx-auto px-4">
        {/* Essential Links - Dynamic */}
        <div className="flex flex-wrap justify-center items-center gap-6 mb-6">
          {renderLink('how_it_works', 'How It Works', '/how-it-works')}
          <span className="text-gray-600">|</span>
          {renderLink('privacy_policy', 'Privacy Policy', '/privacy-policy')}
          <span className="text-gray-600">|</span>
          {renderLink('terms_of_service', 'Terms of Service', '/terms-of-service')}
          <span className="text-gray-600">|</span>
          {renderLink('support', 'Contact Support', 'mailto:support@bidvex.com')}
        </div>

        {/* Copyright & Language Selector */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-6 border-t border-gray-800">
          <p className="text-sm text-center md:text-left">
            © {new Date().getFullYear()} BidVex. {t('footer.allRightsReserved', 'All rights reserved')}.
          </p>
          <button
            onClick={toggleLanguage}
            className="text-sm px-4 py-2 rounded-md bg-gray-800 hover:bg-gray-700 transition-colors"
            aria-label="Toggle language"
          >
            {i18n.language === 'en' ? '🇫🇷 Français' : '🇺🇸 English'}
          </button>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
