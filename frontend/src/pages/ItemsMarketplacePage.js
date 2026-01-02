import React from 'react';
import { useTranslation } from 'react-i18next';
import FlattenedMarketplace from '../components/FlattenedMarketplace';
import { Badge } from '../components/ui/badge';
import { Package, Sparkles, User, Zap } from 'lucide-react';

/**
 * Items Marketplace Page - Flattened Item-Centric View
 * 
 * Shows individual items/lots as standalone cards with:
 * - Dynamic Private Sale / Business Sale badges
 * - Live countdown timers per item
 * - Quick Bid functionality
 * - "Show Private Sales Only" filter toggle
 * - Links to parent auction for related items
 */
const ItemsMarketplacePage = () => {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
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
                  <Package className="h-8 w-8 text-cyan-300" />
                </div>
                <h1 className="text-3xl md:text-4xl font-bold text-white drop-shadow-lg">
                  Browse Individual Items
                </h1>
              </div>
              <p className="text-blue-100 max-w-2xl text-lg drop-shadow-md">
                Discover unique items from estate sales and multi-lot auctions. 
                Each item has its own countdown timer and bidding.
              </p>
            </div>
            
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-white/10 backdrop-blur text-white border-cyan-400/30 px-4 py-2">
                <Sparkles className="h-4 w-4 mr-2 text-yellow-400" />
                Featured First
              </Badge>
              <Badge className="bg-green-500/20 backdrop-blur text-green-300 border-green-400/30 px-4 py-2">
                <User className="h-4 w-4 mr-2" />
                Private Sale = Tax Savings!
              </Badge>
              <Badge className="bg-cyan-500/20 backdrop-blur text-cyan-300 border-cyan-400/30 px-4 py-2">
                <Zap className="h-4 w-4 mr-2" />
                Quick Bid
              </Badge>
            </div>
          </div>
        </div>
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

export default ItemsMarketplacePage;
