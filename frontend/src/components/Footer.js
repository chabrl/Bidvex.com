import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const Footer = () => {
  const { t, i18n } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'fr' : 'en';
    i18n.changeLanguage(newLang);
  };

  return (
    <footer className="bg-gray-900 text-gray-300 py-8 mt-20">
      <div className="max-w-7xl mx-auto px-4">
        {/* Essential Links */}
        <div className="flex flex-wrap justify-center items-center gap-6 mb-6">
          <Link to="/how-it-works" className="hover:text-white transition-colors text-sm">
            {t('footer.howItWorks', 'How It Works')}
          </Link>
          <span className="text-gray-600">|</span>
          <Link to="/privacy-policy" className="hover:text-white transition-colors text-sm">
            {t('footer.privacyPolicy', 'Privacy Policy')}
          </Link>
          <span className="text-gray-600">|</span>
          <Link to="/terms-of-service" className="hover:text-white transition-colors text-sm">
            {t('footer.termsOfService', 'Terms of Service')}
          </Link>
          <span className="text-gray-600">|</span>
          <a href="mailto:support@bidvex.com" className="hover:text-white transition-colors text-sm">
            {t('footer.contact', 'Contact Support')}
          </a>
        </div>

        {/* Copyright & Language Selector */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-6 border-t border-gray-800">
          <p className="text-sm text-center md:text-left">
            © {new Date().getFullYear()} BidVex. {t('footer.allRightsReserved')}.
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
