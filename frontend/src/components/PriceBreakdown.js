import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Info, Calculator, AlertTriangle, Loader2 } from 'lucide-react';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * PriceBreakdown Component
 * 
 * Displays a real-time cost breakdown including:
 * - Your Bid
 * - Buyer's Premium
 * - Taxes (GST/QST for Quebec)
 * - Estimated Total
 * 
 * For VEHICLE auctions, shows special note about hybrid payment method.
 * 
 * @param {number} bidAmount - The user's bid amount
 * @param {string} category - Auction category ('vehicle', 'general', etc.)
 * @param {string} buyerTier - User's subscription tier ('basic', 'premium', 'vip')
 * @param {string} sellerTier - Seller's subscription tier
 * @param {boolean} sellerIsBusiness - Whether seller is a registered business
 * @param {boolean} compact - Compact mode for modals
 * @param {string} className - Additional CSS classes
 */
const PriceBreakdown = ({ 
  bidAmount, 
  category = 'general',
  buyerTier = 'basic',
  sellerTier = 'basic',
  sellerIsBusiness = false,
  compact = false,
  className = ''
}) => {
  const { t, i18n } = useTranslation();
  const [breakdown, setBreakdown] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const isVehicle = ['vehicle', 'car', 'auto', 'automobile', 'truck', 'motorcycle', 'suv', 'van']
    .some(keyword => category.toLowerCase().includes(keyword));

  const debounceTimer = useRef(null);

  // Debounced API call to avoid excessive requests while typing
  useEffect(() => {
    if (!bidAmount || bidAmount <= 0) {
      setBreakdown(null);
      return;
    }

    // Clear previous timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Set new timer for debounced API call
    debounceTimer.current = setTimeout(async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await axios.post(`${API}/payments/tax/calculate`, {
          hammer_price: parseFloat(bidAmount),
          category: category,
          buyer_tier: buyerTier,
          seller_tier: sellerTier,
          seller_is_business: sellerIsBusiness
        });

        setBreakdown(response.data);
      } catch (err) {
        console.error('Failed to fetch price breakdown:', err);
        setError('Unable to calculate fees');
        setBreakdown(null);
      } finally {
        setLoading(false);
      }
    }, 300);

    // Cleanup on unmount
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, [bidAmount, category, buyerTier, sellerTier, sellerIsBusiness]);

  // Format currency
  const formatCurrency = (amount) => {
    if (amount === undefined || amount === null) return '$0.00';
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD'
    }).format(amount);
  };

  // Don't render if no bid amount
  if (!bidAmount || bidAmount <= 0) {
    return null;
  }

  // Loading state
  if (loading && !breakdown) {
    return (
      <Card className={`border-dashed ${className}`} data-testid="price-breakdown-loading">
        <CardContent className={compact ? 'p-3' : 'p-4'}>
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Calculating...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className={`border-destructive/50 ${className}`} data-testid="price-breakdown-error">
        <CardContent className={compact ? 'p-3' : 'p-4'}>
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  // No breakdown available
  if (!breakdown) {
    return null;
  }

  // Determine totals based on payment type
  const isVehiclePayment = breakdown.payment_type === 'vehicle';
  
  return (
    <Card 
      className={`bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-700 ${className}`}
      data-testid="price-breakdown"
    >
      <CardContent className={compact ? 'p-3 space-y-2' : 'p-4 space-y-3'}>
        {/* Header */}
        <div className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
          <Calculator className="h-4 w-4" />
          <span>{i18n.language === 'fr' ? 'Détail des coûts' : 'Cost Breakdown'}</span>
          {loading && <Loader2 className="h-3 w-3 animate-spin ml-auto" />}
        </div>

        <Separator className="bg-slate-200 dark:bg-slate-700" />

        {/* Line Items */}
        <div className="space-y-2 text-sm">
          {/* Your Bid */}
          <div className="flex justify-between items-center">
            <span className="text-slate-600 dark:text-slate-400">
              {i18n.language === 'fr' ? 'Votre enchère' : 'Your Bid'}
            </span>
            <span className="font-medium">{formatCurrency(bidAmount)}</span>
          </div>

          {/* Buyer's Premium */}
          <div className="flex justify-between items-center">
            <span className="text-slate-600 dark:text-slate-400">
              {i18n.language === 'fr' ? 'Prime acheteur' : "Buyer's Premium"}
              <span className="text-xs text-slate-400 ml-1">
                ({(breakdown.buyer_premium_rate * 100).toFixed(1)}%)
              </span>
            </span>
            <span className="text-slate-700 dark:text-slate-300">
              +{formatCurrency(breakdown.buyer_premium)}
            </span>
          </div>

          {/* Platform Fee (Vehicle only) */}
          {isVehiclePayment && breakdown.platform_fee > 0 && (
            <div className="flex justify-between items-center">
              <span className="text-slate-600 dark:text-slate-400">
                {i18n.language === 'fr' ? 'Frais plateforme' : 'Platform Fee'}
                <span className="text-xs text-slate-400 ml-1">(2.5%)</span>
              </span>
              <span className="text-slate-700 dark:text-slate-300">
                +{formatCurrency(breakdown.platform_fee)}
              </span>
            </div>
          )}

          {/* Taxes */}
          <div className="flex justify-between items-center">
            <span className="text-slate-600 dark:text-slate-400">
              {i18n.language === 'fr' ? 'Taxes (TPS/TVQ)' : 'Taxes (GST/QST)'}
            </span>
            <span className="text-slate-700 dark:text-slate-300">
              {isVehiclePayment ? (
                <>+{formatCurrency(breakdown.bidvex_fees_tax_total)}</>
              ) : (
                <>+{formatCurrency(
                  (breakdown.buyer_pays_fees_tax || 0) + 
                  (breakdown.buyer_pays_hammer_tax || 0)
                )}</>
              )}
            </span>
          </div>

          {/* Tax breakdown tooltip for business sellers */}
          {!isVehiclePayment && breakdown.hammer_tax_applicable && (
            <div className="flex items-start gap-1 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 p-2 rounded">
              <Info className="h-3 w-3 mt-0.5 flex-shrink-0" />
              <span>
                {i18n.language === 'fr' 
                  ? 'Les taxes sur le prix d\'achat sont collectées pour le vendeur professionnel.'
                  : 'Tax on item price is collected on behalf of the business seller.'}
              </span>
            </div>
          )}

          <Separator className="bg-slate-200 dark:bg-slate-700" />

          {/* Estimated Total */}
          <div className="flex justify-between items-center">
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              {i18n.language === 'fr' ? 'Total estimé' : 'Estimated Total'}
            </span>
            <span className="font-bold text-lg text-primary">
              {isVehiclePayment 
                ? formatCurrency(breakdown.stripe_charge_total)
                : formatCurrency(breakdown.buyer_total)
              }
            </span>
          </div>
        </div>

        {/* Vehicle Exception Note */}
        {isVehiclePayment && (
          <>
            <Separator className="bg-slate-200 dark:bg-slate-700" />
            <div className="flex items-start gap-2 p-2 bg-blue-50 dark:bg-blue-950/30 rounded-md">
              <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-blue-700 dark:text-blue-300">
                <p className="font-medium mb-1">
                  {i18n.language === 'fr' ? 'Paiement véhicule' : 'Vehicle Payment'}
                </p>
                <p>
                  {i18n.language === 'fr' 
                    ? `Seuls les frais BidVex et taxes sont payés en ligne. Le prix d'achat (${formatCurrency(bidAmount)}) est payé directement au vendeur.`
                    : `Only BidVex fees and taxes are paid online. Hammer price (${formatCurrency(bidAmount)}) paid directly to seller.`
                  }
                </p>
              </div>
            </div>
            
            {/* Balance Due to Seller */}
            <div className="flex justify-between items-center text-sm bg-slate-100 dark:bg-slate-800 p-2 rounded">
              <span className="text-slate-600 dark:text-slate-400">
                {i18n.language === 'fr' ? 'Solde dû au vendeur' : 'Balance due to seller'}
              </span>
              <Badge variant="outline" className="font-mono">
                {formatCurrency(breakdown.seller_balance_due)}
              </Badge>
            </div>
          </>
        )}

        {/* Subscription Savings Hint */}
        {buyerTier === 'basic' && (
          <div className="text-xs text-center text-slate-500 dark:text-slate-400 pt-1">
            {i18n.language === 'fr' 
              ? '💡 Les membres Premium économisent 1.5% sur les frais'
              : '💡 Premium members save 1.5% on fees'}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default PriceBreakdown;
