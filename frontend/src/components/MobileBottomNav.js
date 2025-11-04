import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Home, Search, Heart, User, Plus, Package, X, FileText, Layers } from 'lucide-react';

const MobileBottomNav = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [showSellMenu, setShowSellMenu] = useState(false);

  const navItems = [
    { icon: Home, label: 'Home', path: '/', key: 'home' },
    { icon: Search, label: 'Search', path: '/marketplace', key: 'search' },
    { icon: Package, label: 'Lots', path: '/lots', key: 'lots' },
    { icon: Plus, label: 'Sell', path: '/create-listing', key: 'sell', requireAuth: true, hasMenu: true },
    { icon: Heart, label: 'Watchlist', path: '/watchlist', key: 'watchlist', requireAuth: true },
    { icon: User, label: 'Profile', path: '/settings', key: 'profile', dynamicPath: true }
  ];

  const isActive = (path) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  const handleNavigation = (item) => {
    if (item.key === 'sell' && item.hasMenu) {
      setShowSellMenu(!showSellMenu);
    } else if (item.key === 'profile') {
      // Handle profile navigation dynamically
      const profilePath = user ? '/settings' : '/auth';
      navigate(profilePath);
    } else {
      navigate(item.path);
      setShowSellMenu(false);
    }
  };

  const handleSellOption = (path) => {
    if (!user) {
      navigate('/auth');
    } else if (path === '/create-multi-item-listing' && user.account_type !== 'business') {
      // Show toast or message that business account is required
      alert('Business account required for multi-item listings');
    } else {
      navigate(path);
    }
    setShowSellMenu(false);
  };

  return (
    <>
      {/* Sell Menu Overlay */}
      {showSellMenu && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setShowSellMenu(false)}
        >
          <div 
            className="absolute bottom-16 left-0 right-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Create Listing</h3>
              <button 
                onClick={() => setShowSellMenu(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-2">
              <button
                onClick={() => handleSellOption('/create-listing')}
                className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <FileText className="h-6 w-6 text-primary" />
                <div className="text-left">
                  <p className="font-semibold">Single Item Listing</p>
                  <p className="text-xs text-muted-foreground">Sell one item at auction</p>
                </div>
              </button>
              <button
                onClick={() => handleSellOption('/create-multi-item-listing')}
                className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <Layers className="h-6 w-6 text-primary" />
                <div className="text-left">
                  <p className="font-semibold">Multi-Lot Listing</p>
                  <p className="text-xs text-muted-foreground">Create grouped auction with multiple lots</p>
                  {user && user.account_type !== 'business' && (
                    <p className="text-xs text-amber-500 mt-1">⚠️ Business account required</p>
                  )}
                </div>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 z-50 md:hidden">
        <div className="flex justify-around items-center h-16 max-w-screen-sm mx-auto px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            const canShow = !item.requireAuth || user;

            if (!canShow) return null;

            return (
              <button
                key={item.key}
                onClick={() => handleNavigation(item)}
                className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
                  active
                    ? 'text-primary'
                    : 'text-gray-500 dark:text-gray-400 hover:text-primary'
                } ${showSellMenu && item.key === 'sell' ? 'text-primary' : ''}`}
                aria-label={item.label}
              >
                <Icon className={`h-6 w-6 mb-1 ${active || (showSellMenu && item.key === 'sell') ? 'stroke-[2.5]' : ''}`} />
                <span className={`text-xs ${active || (showSellMenu && item.key === 'sell') ? 'font-semibold' : 'font-normal'}`}>
                  {item.label}
                </span>
              </button>
            );
          })}
        </div>
      </nav>
    </>
  );
};

export default MobileBottomNav;
