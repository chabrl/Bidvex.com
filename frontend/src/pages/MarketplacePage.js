import React from 'react';
import { useTranslation } from 'react-i18next';
import FlattenedMarketplace from '../components/FlattenedMarketplace';
import AnnouncementBanner from '../components/AnnouncementBanner';
import { Badge } from '../components/ui/badge';
import { Package, Sparkles, User, Zap, ShoppingBag } from 'lucide-react';

/**
 * Marketplace Page - Flattened Item-Centric View
 * 
 * This is the main marketplace view showing individual items/lots as standalone cards.
 * Key features:
 * - Individual item cards (not grouped by auction)
 * - Dynamic Private Sale / Business Sale badges
 * - Live countdown timers per item
 * - Quick Bid functionality
 * - "Show Private Sales Only" filter toggle
 */
const MarketplacePage = () => {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="marketplace-page">
      {/* Gradient Hero Header */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-900 via-slate-900 to-cyan-900 opacity-95" />
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full blur-[150px] bg-cyan-500" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 rounded-full blur-[150px] bg-blue-500" />
        </div>
        
        <div className="relative container mx-auto max-w-7xl py-10 px-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <div className="p-3 bg-cyan-500/20 backdrop-blur rounded-xl border border-cyan-400/30">
                  <ShoppingBag className="h-8 w-8 text-cyan-300" />
                </div>
                <h1 className="text-3xl md:text-4xl font-bold drop-shadow-lg" style={{ color: '#FFFFFF' }}>
                  {t('marketplace.title', 'Active Auctions')}
                </h1>
              </div>
              <p className="max-w-2xl text-lg drop-shadow-md" style={{ color: '#BFDBFE' }}>
                {t('marketplace.subtitle', 'Browse individual items from estate sales and multi-lot auctions. Each item has its own countdown timer and bidding.')}
              </p>
            </div>
            
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-white/10 backdrop-blur border-cyan-400/30 px-4 py-2" style={{ color: '#FFFFFF' }}>
                <Sparkles className="h-4 w-4 mr-2 text-yellow-400" />
                {t('marketplace.featuredFirst', 'Featured First')}
              </Badge>
              <Badge className="bg-green-500/20 backdrop-blur border-green-400/30 px-4 py-2" style={{ color: '#86EFAC' }}>
                <User className="h-4 w-4 mr-2" />
                {t('marketplace.privateSaleTax', 'Private Sale = Tax Savings!')}
              </Badge>
              <Badge className="bg-cyan-500/20 backdrop-blur border-cyan-400/30 px-4 py-2" style={{ color: '#67E8F9' }}>
                <Zap className="h-4 w-4 mr-2" />
                {t('marketplace.quickBid', 'Quick Bid')}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Announcements Banner */}
      <div className="container mx-auto max-w-7xl px-4">
        <AnnouncementBanner />
      </div>

      {/* Flattened Marketplace Component */}
      <FlattenedMarketplace 
        showFilters={true}
        showHeader={false}
        variant="full"
        limit={50}
      />
    </div>
  );
};

export default MarketplacePage;
