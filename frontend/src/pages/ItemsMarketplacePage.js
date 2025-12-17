import React from 'react';
import { useTranslation } from 'react-i18next';
import DecomposedMarketplace from '../components/DecomposedMarketplace';
import { Badge } from '../components/ui/badge';
import { Package, Sparkles } from 'lucide-react';

/**
 * Items Marketplace Page
 * Shows individual items from multi-item auctions in an item-centric view.
 * This is the recommended view for buyers who want to browse individual lots.
 */
const ItemsMarketplacePage = () => {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Page Header */}
      <div className="bg-gradient-to-r from-primary/10 to-primary/5 py-8 px-4">
        <div className="container mx-auto max-w-7xl">
          <div className="flex items-center gap-3 mb-2">
            <Package className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">Individual Items Marketplace</h1>
          </div>
          <p className="text-muted-foreground max-w-2xl">
            Browse and bid on individual items from estate sales and multi-item auctions. 
            Each item is sold separately with its own countdown timer.
          </p>
          <div className="flex gap-2 mt-4">
            <Badge variant="outline" className="bg-white">
              <Sparkles className="h-3 w-3 mr-1 text-yellow-500" />
              Promoted items shown first
            </Badge>
            <Badge variant="outline" className="bg-white">
              Buy Now available on select items
            </Badge>
          </div>
        </div>
      </div>

      {/* Decomposed Marketplace Component */}
      <div className="container mx-auto max-w-7xl py-8 px-4">
        <DecomposedMarketplace />
      </div>
    </div>
  );
};

export default ItemsMarketplacePage;
