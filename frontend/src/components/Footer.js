import React from 'react';
import { Link } from 'react-router-dom';
import { Mail, Instagram, Twitter, Linkedin, Youtube } from 'lucide-react';

const Footer = () => {
  return (
    <footer className="bg-gray-900 text-gray-300 py-12 mt-20">
      <div className="max-w-7xl mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8 mb-8">
          {/* Product */}
          <div>
            <h3 className="text-white font-semibold mb-4">Product</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="/marketplace" className="hover:text-white transition-colors">Marketplace</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Plugins</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Bazario Reviews</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Pricing</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Bazario for Enterprise</Link></li>
            </ul>
          </div>

          {/* Capabilities */}
          <div>
            <h3 className="text-white font-semibold mb-4">Capabilities</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="#" className="hover:text-white transition-colors">Cascade</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Tab</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Cascade on JetBrains</Link></li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h3 className="text-white font-semibold mb-4">Company</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="#" className="hover:text-white transition-colors">About Us</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Blog</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Careers</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Contact</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Partnerships</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Terms of Service</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Privacy Policy</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Security</Link></li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h3 className="text-white font-semibold mb-4">Resources</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="#" className="hover:text-white transition-colors">Docs</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Changelog</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Releases</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Support</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Brand</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Referrals</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">2025 Gartner Magic Quadrant</Link></li>
            </ul>
          </div>

          {/* Connect */}
          <div>
            <h3 className="text-white font-semibold mb-4">Connect</h3>
            <ul className="space-y-2 text-sm">
              <li><Link to="#" className="hover:text-white transition-colors">Contact</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Upcoming Events</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Hackathons</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Community</Link></li>
              <li><Link to="#" className="hover:text-white transition-colors">Students</Link></li>
            </ul>
          </div>
        </div>

        {/* Social Links */}
        <div className="flex flex-wrap gap-6 items-center justify-center mb-8 py-8 border-t border-gray-800">
          <a href="mailto:support@bazario.com" className="hover:text-white transition-colors" aria-label="Email">
            <Mail className="h-5 w-5" />
          </a>
          <a href="https://instagram.com" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="Instagram">
            <Instagram className="h-5 w-5" />
          </a>
          <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="Twitter">
            <Twitter className="h-5 w-5" />
          </a>
          <a href="https://linkedin.com" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="LinkedIn">
            <Linkedin className="h-5 w-5" />
          </a>
          <a href="https://youtube.com" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors" aria-label="YouTube">
            <Youtube className="h-5 w-5" />
          </a>
        </div>

        {/* Copyright */}
        <div className="text-center text-sm text-gray-500 border-t border-gray-800 pt-8">
          © 2025 Cognition, Inc. All rights reserved.
        </div>
      </div>
    </footer>
  );
};

export default Footer;
