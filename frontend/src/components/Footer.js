import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCookieConsent } from '../hooks/useCookieConsent';
import axios from 'axios';

const API = API_BASE;

// Inline SVG social icons (no external deps)
const SocialIcons = {
  x: (props) => (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
    </svg>
  ),
  facebook: (props) => (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
    </svg>
  ),
  instagram: (props) => (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
    </svg>
  ),
  linkedin: (props) => (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
    </svg>
  ),
  tiktok: (props) => (
    <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
    </svg>
  ),
};

const SOCIAL_PLATFORM_CONFIG = [
  { key: 'x', label: 'X', Icon: SocialIcons.x },
  { key: 'facebook', label: 'Facebook', Icon: SocialIcons.facebook },
  { key: 'instagram', label: 'Instagram', Icon: SocialIcons.instagram },
  { key: 'linkedin', label: 'LinkedIn', Icon: SocialIcons.linkedin },
  { key: 'tiktok', label: 'TikTok', Icon: SocialIcons.tiktok },
];

const Footer = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { resetConsent } = useCookieConsent();
  const [footerLinks, setFooterLinks] = useState(null);
  const [socialLinks, setSocialLinks] = useState(null);
  const language = i18n.language || 'en';

  useEffect(() => {
    fetchFooterLinks();
  }, [language]);

  useEffect(() => {
    fetchSocialLinks();
  }, []);

  const fetchFooterLinks = async () => {
    try {
      const response = await axios.get(`${API}/site-config/legal-pages?language=${language}`);
      if (response.data.success) {
        setFooterLinks(response.data.pages);
      }
    } catch (error) {
      console.error('[Footer] Error fetching links:', error);
    }
  };

  const fetchSocialLinks = async () => {
    try {
      const response = await axios.get(`${API}/site-config/social-links`);
      setSocialLinks(response.data?.social_links || {});
    } catch (error) {
      console.error('[Footer] Error fetching social links:', error);
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
    // Prioritize i18n translations for proper accents, fall back to API title if translation key matches default
    const i18nTitle = t(`footer.${pageKey}`, { defaultValue: '' });
    const title = i18nTitle || linkData?.title || defaultTitle;
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
    <footer className="bg-gray-900 text-gray-300 pt-12 pb-6 mt-20" style={{ minHeight: '320px' }} data-testid="site-footer">
      <div className="max-w-7xl mx-auto px-4">

        {/* iter231 — 4-column compliance footer (Google Merchant transparency) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 mb-8">

          {/* Corporate Info */}
          <div data-testid="footer-col-corporate">
            <h3 className="text-white font-bold mb-3 text-sm uppercase tracking-wider">
              {language === 'fr' ? 'Entreprise' : 'Corporate'}
            </h3>
            <address className="not-italic text-xs leading-relaxed mb-3 text-gray-400">
              <strong className="text-gray-200">BidVex Inc.</strong><br />
              761 Rue Chalifoux<br />
              Sherbrooke (Québec) J1G 0A8<br />
              Canada
            </address>
            <ul className="space-y-1.5 text-sm">
              <li><Link to="/contact-us" className="hover:text-white transition-colors" data-testid="footer-contact-us">
                {language === 'fr' ? 'Nous joindre' : 'Contact Us'}
              </Link></li>
              <li>{renderLink('about', language === 'fr' ? 'À propos' : 'About Us', '/about')}</li>
              <li>{renderLink('careers', language === 'fr' ? 'Carrières' : 'Careers', '/careers')}</li>
              <li>{renderLink('community', language === 'fr' ? 'Communauté' : 'Community', '/community')}</li>
              <li><a href="mailto:support@bidvex.com" className="hover:text-white transition-colors text-sm">
                {language === 'fr' ? 'Presse' : 'Press'}
              </a></li>
            </ul>
          </div>

          {/* Legal Policies */}
          <div data-testid="footer-col-legal">
            <h3 className="text-white font-bold mb-3 text-sm uppercase tracking-wider">
              {language === 'fr' ? 'Politiques légales' : 'Legal Policies'}
            </h3>
            <ul className="space-y-1.5 text-sm">
              <li>{renderLink('terms_of_service', language === 'fr' ? 'Conditions générales' : 'Terms of Service', '/terms-of-service')}</li>
              <li>{renderLink('privacy_policy', language === 'fr' ? 'Politique de confidentialité' : 'Privacy Policy', '/privacy-policy')}</li>
              <li><Link to="/refund-policy" className="hover:text-white transition-colors text-sm" data-testid="footer-refund-policy">
                {language === 'fr' ? 'Politique de remboursement' : 'Refund & Return Policy'}
              </Link></li>
              <li>{renderLink(
                'prohibited_items',
                language === 'fr' ? 'Articles interdits' : 'Prohibited Items',
                language === 'fr' ? '/articles-interdits' : '/prohibited-items',
              )}</li>
              <li><button onClick={resetConsent} className="hover:text-white transition-colors text-sm" data-testid="footer-cookie-settings">
                {t('footer.cookieSettings', language === 'fr' ? 'Paramètres des témoins' : 'Cookie Settings')}
              </button></li>
            </ul>
          </div>

          {/* Marketplace Tools */}
          <div data-testid="footer-col-marketplace">
            <h3 className="text-white font-bold mb-3 text-sm uppercase tracking-wider">
              {language === 'fr' ? 'Marketplace' : 'Marketplace'}
            </h3>
            <ul className="space-y-1.5 text-sm">
              <li>{renderLink('how_it_works', language === 'fr' ? 'Comment ça marche' : 'How It Works', '/how-it-works')}</li>
              <li><Link to={language === 'fr' ? '/devenir-courtier' : '/become-a-broker'} className="hover:text-white transition-colors text-sm" data-testid="footer-become-a-broker">
                {language === 'fr' ? 'Devenir courtier' : 'Become a Broker'}
              </Link></li>
              <li><Link to={language === 'fr' ? '/courtiers' : '/brokers'} className="hover:text-white transition-colors text-sm" data-testid="footer-broker-directory">
                {language === 'fr' ? 'Répertoire des courtiers' : 'Broker Directory'}
              </Link></li>
              <li><Link to="/vehicle-auctions" className="hover:text-white transition-colors text-sm" data-testid="footer-vehicles-link">
                {language === 'fr' ? 'Encans de véhicules' : 'Vehicle Auctions'}
              </Link></li>
              <li><Link to="/storage-auctions" className="hover:text-white transition-colors text-sm" data-testid="footer-storage-link">
                {language === 'fr' ? 'Encans d\'entreposage' : 'Storage Auctions'}
              </Link></li>
            </ul>
          </div>

          {/* Support */}
          <div data-testid="footer-col-support">
            <h3 className="text-white font-bold mb-3 text-sm uppercase tracking-wider">
              {language === 'fr' ? 'Support' : 'Support'}
            </h3>
            <ul className="space-y-1.5 text-sm">
              <li><a href="mailto:support@bidvex.com" className="hover:text-white transition-colors flex items-center gap-1.5" data-testid="footer-email-support">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                support@bidvex.com
              </a></li>
              <li><a href="tel:+14506343099" className="hover:text-white transition-colors flex items-center gap-1.5" data-testid="footer-phone-support">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                +1 (450) 634-3099
              </a></li>
              <li><a href="mailto:support@bidvex.com?subject=Dispute%20Resolution" className="hover:text-white transition-colors" data-testid="footer-disputes">
                {language === 'fr' ? 'Résolution des différends' : 'Dispute Resolutions'}
              </a></li>
              <li><a href="mailto:support@bidvex.com?subject=Legal%20%26%20Compliance" className="hover:text-white transition-colors" data-testid="footer-legal-inbox">
                {language === 'fr' ? 'Juridique et conformité' : 'Legal & Compliance'}
              </a></li>
              <li><a href="mailto:support@bidvex.com?subject=Broker%20%26%20Dealer" className="hover:text-white transition-colors" data-testid="footer-brokers-inbox">
                {language === 'fr' ? 'Boîte courtiers' : 'Broker Inbox'}
              </a></li>
            </ul>
          </div>
        </div>

        {/* Compliance microdata strip — visible & crawlable by Google trust signals */}
        <div className="border-t border-gray-800 pt-4 pb-2 text-[11px] text-gray-500 leading-relaxed text-center" data-testid="footer-compliance-strip">
          {language === 'fr' ? (
            <>
              BidVex Inc. — Société constituée fédéralement au Canada · Numéro de société 1175252874 · Siège social à Sherbrooke (Québec).
              Plateforme d'encans en ligne. Les véhicules sont vendus par l'entremise de courtiers licenciés (SAAQ/OPC, OMVIC, AMVIC, VSA).
              Toutes les ventes sont fermes, « tel quel, où il se trouve ».
            </>
          ) : (
            <>
              BidVex Inc. — Federally incorporated in Canada · Corporation Number 1175252874 · Headquartered in Sherbrooke, Québec.
              Online auction marketplace. Vehicles sold through licensed brokers (SAAQ/OPC, OMVIC, AMVIC, VSA).
              All sales final, &ldquo;as-is, where-is&rdquo;.
            </>
          )}
        </div>

        {/* Social Media Icons */}
        {socialLinks && SOCIAL_PLATFORM_CONFIG.some(p => socialLinks[p.key]) && (
          <div className="flex justify-center items-center gap-4 my-4" data-testid="footer-social-links">
            {SOCIAL_PLATFORM_CONFIG.map(({ key, label, Icon }) =>
              socialLinks[key] ? (
                <a
                  key={key}
                  href={socialLinks[key]}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={label}
                  className="text-gray-400 hover:text-white transition-colors duration-200"
                  data-testid={`footer-social-${key}`}
                >
                  <Icon className="h-5 w-5" />
                </a>
              ) : null
            )}
          </div>
        )}

        {/* Copyright & Language Selector */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-4 border-t border-gray-800">
          <p className="text-sm text-center md:text-left" data-testid="footer-copyright">
            &copy; {new Date().getFullYear()} BidVex Inc. {t('footer.allRightsReserved', 'All rights reserved')}.
          </p>
          <button
            onClick={toggleLanguage}
            className="text-sm px-4 py-2 rounded-md bg-gray-800 hover:bg-gray-700 transition-colors"
            aria-label="Toggle language"
          >
            {i18n.language === 'fr' ? '🇨🇦 Français' : '🇨🇦 English'}
          </button>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
