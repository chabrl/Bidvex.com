import React from 'react';
import { Badge } from './ui/badge';
import { Sparkles, ShieldCheck, User } from 'lucide-react';

/**
 * PrivateSaleBadge - Displays when a listing is from an individual (non-business) seller
 * Key marketing weapon for BidVex's "Disruptor Protocol"
 * 
 * Shows buyers they save ~15% on taxes when buying from individual sellers
 */
const PrivateSaleBadge = ({ 
  variant = 'default', // 'default', 'compact', 'inline'
  showSavingsPercentage = true,
  className = ''
}) => {
  if (variant === 'compact') {
    return (
      <Badge className={`bg-gradient-to-r from-green-500 to-emerald-500 text-white border-0 ${className}`}>
        <User className="h-3 w-3 mr-1" />
        Private Sale
      </Badge>
    );
  }

  if (variant === 'inline') {
    return (
      <span className={`inline-flex items-center gap-1 text-green-600 font-medium ${className}`}>
        <Sparkles className="h-4 w-4" />
        Private Sale - Tax Free Item!
      </span>
    );
  }

  // Default: Full banner style
  return (
    <div className={`bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/30 dark:to-emerald-900/30 border-2 border-green-300 dark:border-green-600 rounded-xl p-4 ${className}`}>
      <div className="flex items-start gap-3">
        <div className="p-2 bg-green-100 dark:bg-green-800 rounded-lg">
          <Sparkles className="h-6 w-6 text-green-600 dark:text-green-400" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="font-bold text-green-700 dark:text-green-300 text-lg">🎉 Private Sale</h4>
            {showSavingsPercentage && (
              <Badge className="bg-green-600 text-white border-0 text-xs">
                Save ~15% on Taxes!
              </Badge>
            )}
          </div>
          <p className="text-sm text-green-600 dark:text-green-400">
            This item is from an individual seller. <strong>No sales tax on the hammer price!</strong>
          </p>
          <div className="flex items-center gap-2 mt-2 text-xs text-green-500 dark:text-green-400">
            <ShieldCheck className="h-4 w-4" />
            <span>GST/QST only applies to the buyer&apos;s premium</span>
          </div>
        </div>
      </div>
    </div>
  );
};

/**
 * BusinessSellerBadge - Shows when a listing is from a registered business
 * Indicates that full taxes apply
 */
export const BusinessSellerBadge = ({ 
  variant = 'compact',
  className = '' 
}) => {
  if (variant === 'compact') {
    return (
      <Badge variant="outline" className={`border-blue-300 text-blue-600 ${className}`}>
        <ShieldCheck className="h-3 w-3 mr-1" />
        Business Seller
      </Badge>
    );
  }

  return (
    <div className={`bg-blue-50 border border-blue-200 rounded-lg p-3 ${className}`}>
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-blue-600" />
        <div>
          <span className="font-medium text-blue-700">Registered Business Seller</span>
        <p className="text-xs text-blue-500">Standard GST/QST applies</p>
        </div>
      </div>
    </div>
  );
};

export default PrivateSaleBadge;
