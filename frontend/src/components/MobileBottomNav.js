import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import { Car, Warehouse, Heart, Plus, Package, X, FileText, Layers } from 'lucide-react';

const MobileBottomNav = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { user } = useAuth();
  const { canCreateMultiLot } = useFeatureFlags();
  const [showSellMenu, setShowSellMenu] = useState(false);

  // iter178 — Order: Vehicles | Lots | Storage | Sell | Watchlist
  // (Search removed — available via navbar search icon.)
  const navItems = [
    { icon: Car,       labelKey: 'mobileNav.vehicles', path: '/vehicle-auctions', key: 'vehicles' },
    { icon: Package,   labelKey: 'mobileNav.lots',     path: '/lots',             key: 'lots' },
    { icon: Warehouse, labelKey: 'mobileNav.storage',  path: '/storage-auctions', key: 'storage' },
    { icon: Plus,      labelKey: 'mobileNav.sell',     path: '/create-listing',   key: 'sell', requireAuth: true, hasMenu: true },
    { icon: Heart,     labelKey: 'mobileNav.watchlist',path: '/watchlist',        key: 'watchlist', requireAuth: true },
  ];

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const handleNavigation = (item) => {
    if (item.key === 'sell' && item.hasMenu) {
      setShowSellMenu(!showSellMenu);
    } else {
      navigate(item.path);
      setShowSellMenu(false);
    }
  };

  const handleSellOption = (path) => {
    if (!user) {
      navigate('/auth');
    } else {
      navigate(path);
    }
    setShowSellMenu(false);
  };

  return (
    <>
      {showSellMenu && (
        <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={() => setShowSellMenu(false)}>
          <div className="absolute bottom-16 left-0 right-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">{t('mobileNav.createListing')}</h3>
              <button onClick={() => setShowSellMenu(false)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-2">
              <button onClick={() => handleSellOption('/create-listing')} className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors border border-gray-200 dark:border-gray-700" data-testid="mobile-sell-single">
                <div className="p-3 rounded-full bg-primary/10 flex-shrink-0">
                  <FileText className="h-6 w-6 text-primary" />
                </div>
                <div className="text-left flex-1 min-w-0">
                  <p className="font-semibold truncate">{t('mobileNav.singleItem')}</p>
                  <p className="text-xs text-muted-foreground line-clamp-2">{t('mobileNav.singleItemDesc')}</p>
                </div>
              </button>
              <button onClick={() => handleSellOption('/create-multi-item-listing')} className="w-full flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors border border-gray-200 dark:border-gray-700" data-testid="mobile-sell-multi">
                <div className="p-3 rounded-full bg-purple-500/10 flex-shrink-0">
                  <Layers className="h-6 w-6 text-purple-600" />
                </div>
                <div className="text-left flex-1 min-w-0">
                  <p className="font-semibold truncate">{t('mobileNav.multiLot')}</p>
                  <p className="text-xs text-muted-foreground line-clamp-2">{t('mobileNav.multiLotDesc')}</p>
                </div>
              </button>
            </div>
          </div>
        </div>
      )}

      <nav className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 z-50 lg:hidden safe-area-bottom">
        <div className="flex justify-around items-center h-14 sm:h-16 max-w-screen-sm mx-auto px-1 sm:px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            const canShow = !item.requireAuth || user;
            if (!canShow) return null;
            return (
              <button
                key={item.key}
                onClick={() => handleNavigation(item)}
                data-testid={`mobile-nav-${item.key}`}
                className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
                  active ? 'text-primary' : 'text-gray-500 dark:text-gray-400 hover:text-primary'
                } ${showSellMenu && item.key === 'sell' ? 'text-primary' : ''}`}
                aria-label={t(item.labelKey)}
              >
                <Icon className={`h-5 w-5 sm:h-6 sm:w-6 mb-0.5 sm:mb-1 ${active || (showSellMenu && item.key === 'sell') ? 'stroke-[2.5]' : ''}`} />
                <span className={`text-[10px] sm:text-xs ${active || (showSellMenu && item.key === 'sell') ? 'font-semibold' : 'font-normal'}`}>
                  {t(item.labelKey)}
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
