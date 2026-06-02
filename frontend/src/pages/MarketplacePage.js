import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import FlattenedMarketplace from '../components/FlattenedMarketplace';
import MarketplaceSidebar from '../components/MarketplaceSidebar';
import { Badge } from '../components/ui/badge';
import { ShoppingBag, Sparkles, User, Zap } from 'lucide-react';
// iter268 Mission 4 — SEO meta tags
import SEO from '../components/SEO';

const MarketplacePage = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const [sidebarFilters, setSidebarFilters] = useState({});

  // iter189 Bug 3: Reset filters on fresh navigation to /marketplace.
  // Prevents stale filter state from hiding listings when user re-enters the page.
  useEffect(() => {
    if (!location.search && !location.state?.preserveFilters) {
      setSidebarFilters({});
    }
  }, [location.key, location.search, location.state]);

  // Phase 5 Hotfix v5 — chip-driven removal of a single sidebar category.
  // The sidebar owns `categories`, the chip lives in the top bar — when the
  // user clicks the chip's ×, we send a partial filter delta back to the
  // sidebar so it can drop that one category.
  const handleClearSidebarCategory = (cat) => {
    setSidebarFilters(prev => ({
      ...prev,
      categories: (prev.categories || []).filter(c => c !== cat),
    }));
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="marketplace-page">
      <SEO
        title="Online Auction Marketplace — Canada"
        description="Buy and bid on thousands of items across Canada. Verified sellers, real-time bidding, and transparent fees. Join BidVex today."
        path="/marketplace"
      />
      {/* Hero */}
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
                {t('marketplace.subtitle', 'Browse individual items from estate sales and multi-lot auctions.')}
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

      {/* iter220 Task 2 — Layout unified with VehicleAuctionsPage:
          max-w-7xl + sm:px-6 lg:px-8 + py-6 sm:py-8 for consistent breathing
          room. Sidebar uses lg breakpoint so mobile+tablet gets the drawer. */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <div className="flex gap-6">
          {/* Sidebar handles its own desktop/mobile rendering */}
          <MarketplaceSidebar onFiltersChange={setSidebarFilters} externalFilters={sidebarFilters} />

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            <FlattenedMarketplace
              showFilters={true}
              showHeader={false}
              variant="full"
              limit={50}
              externalFilters={sidebarFilters}
              onClearSidebarCategory={handleClearSidebarCategory}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default MarketplacePage;
