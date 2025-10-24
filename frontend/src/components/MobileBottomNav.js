import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Home, Search, Heart, User, Plus } from 'lucide-react';

const MobileBottomNav = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const navItems = [
    { icon: Home, label: 'Home', path: '/', key: 'home' },
    { icon: Search, label: 'Search', path: '/marketplace', key: 'search' },
    { icon: Plus, label: 'Sell', path: '/create-listing', key: 'sell', requireAuth: true },
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
    if (item.key === 'profile') {
      // Handle profile navigation dynamically
      const profilePath = user ? '/settings' : '/auth';
      navigate(profilePath);
    } else {
      navigate(item.path);
    }
  };

  return (
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
              }`}
              aria-label={item.label}
            >
              <Icon className={`h-6 w-6 mb-1 ${active ? 'stroke-[2.5]' : ''}`} />
              <span className={`text-xs ${active ? 'font-semibold' : 'font-normal'}`}>
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default MobileBottomNav;
