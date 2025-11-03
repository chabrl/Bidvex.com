import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const Footer = () => {
  const { i18n } = useTranslation();

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
            How It Works
          </Link>
          <span className="text-gray-600">|</span>
          <Link to="/privacy" className="hover:text-white transition-colors text-sm">
            Privacy Policy
          </Link>
          <span className="text-gray-600">|</span>
          <Link to="/terms" className="hover:text-white transition-colors text-sm">
            Terms of Service
          </Link>
          <span className="text-gray-600">|</span>
          <Link to="/cookies" className="hover:text-white transition-colors text-sm">
            Cookie Preferences
          </Link>
        </div>

        {/* Copyright & Language Selector */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-6 border-t border-gray-800">
          <p className="text-sm text-center md:text-left">
            © {new Date().getFullYear()} Bazario. All rights reserved.
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
            <a href="https://linkedin.com/company/bazario" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="LinkedIn">
              <Linkedin className="h-5 w-5" />
            </a>
            <a href="https://youtube.com/@bazario" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="YouTube">
              <Youtube className="h-5 w-5" />
            </a>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm">Language:</span>
            <button 
              onClick={toggleLanguage}
              className="px-3 py-1 rounded-md bg-gray-800 hover:bg-gray-700 transition-colors text-sm font-medium"
            >
              {i18n.language === 'en' ? 'English' : 'Français'}
            </button>
          </div>
        </div>

        {/* Copyright */}
        <div className="text-center text-sm text-gray-500 pt-6 border-t border-gray-800">
          © Bazario 2025. All rights reserved.
        </div>
      </div>
    </footer>
  );
};

export default Footer;
