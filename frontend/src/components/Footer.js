import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Facebook, Twitter, Instagram, Linkedin, Youtube } from 'lucide-react';

const Footer = () => {
  const { i18n } = useTranslation();

  const toggleLanguage = () => {
    const newLang = i18n.language === 'en' ? 'fr' : 'en';
    i18n.changeLanguage(newLang);
  };

  return (
    <footer className="bg-gray-900 text-gray-300 py-12 mt-20">
      <div className="max-w-7xl mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-8">
          {/* Marketplace */}
          <div>
            <h3 className="text-white font-semibold mb-4">Marketplace</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="/marketplace" className="hover:text-white transition-colors">Browse Auctions</Link></li>
              <li><Link to="/marketplace?category=electronics" className="hover:text-white transition-colors">Electronics</Link></li>
              <li><Link to="/marketplace?category=fashion" className="hover:text-white transition-colors">Fashion</Link></li>
              <li><Link to="/marketplace?category=collectibles" className="hover:text-white transition-colors">Collectibles</Link></li>
              <li><Link to="/marketplace" className="hover:text-white transition-colors">Featured Items</Link></li>
            </ul>
          </div>

          {/* Sell */}
          <div>
            <h3 className="text-white font-semibold mb-4">Sell</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="/create-listing" className="hover:text-white transition-colors">Create Listing</Link></li>
              <li><Link to="/create-multi-item" className="hover:text-white transition-colors">Multi-Item Listing</Link></li>
              <li><Link to="/seller-dashboard" className="hover:text-white transition-colors">Seller Dashboard</Link></li>
              <li><Link to="/affiliate" className="hover:text-white transition-colors">Affiliate Program</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Seller Guide</Link></li>
            </ul>
          </div>

          {/* Buy */}
          <div>
            <h3 className="text-white font-semibold mb-4">Buy</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="/buyer-dashboard" className="hover:text-white transition-colors">My Bids</Link></li>
              <li><Link to="/buyer-dashboard" className="hover:text-white transition-colors">Won Items</Link></li>
              <li><Link to="/buyer-dashboard" className="hover:text-white transition-colors">Watchlist</Link></li>
              <li><Link to="/messages" className="hover:text-white transition-colors">Messages</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Buyer Protection</Link></li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h3 className="text-white font-semibold mb-4">Resources</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="#" className="hover:text-white transition-colors">Help Center</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Safety Tips</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Buyer Guide</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Blog</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">FAQs</Link></li>
            </ul>
          </div>
        </div>

        {/* Company & Legal */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8 pb-8 border-b border-gray-800">
          <div>
            <h3 className="text-white font-semibold mb-4">Company</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="#" className="hover:text-white transition-colors">About Us</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Careers</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Partnerships</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Contact</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="text-white font-semibold mb-4">Legal</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="#" className="hover:text-white transition-colors">Terms of Service</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Privacy Policy</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Cookie Policy</Link></li>
            </ul>
          </div>
        </div>

        {/* Social Links & Language Selector */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 mb-6">
          <div className="flex gap-6 items-center">
            <a href="https://facebook.com/bazario" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="Facebook">
              <Facebook className="h-5 w-5" />
            </a>
            <a href="https://twitter.com/bazario" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="Twitter">
              <Twitter className="h-5 w-5" />
            </a>
            <a href="https://instagram.com/bazario" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="Instagram">
              <Instagram className="h-5 w-5" />
            </a>
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
