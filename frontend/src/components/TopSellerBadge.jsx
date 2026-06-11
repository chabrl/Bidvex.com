import React from 'react';
import { useTranslation } from 'react-i18next';
import { Star } from 'lucide-react';

/**
 * iter300 — Merit-based "Top Seller" badge (top 5 sellers by all-time GMV,
 * recalculated nightly). Gold styling, bilingual, hover tooltip.
 *
 * sizes: 'xs' (listing cards), 'sm' (seller info lines), 'md' (storefront hero)
 */
export const TopSellerBadge = ({ size = 'sm', className = '' }) => {
  const { i18n } = useTranslation();
  const isFrench = (i18n.language || 'en').startsWith('fr');

  const label = isFrench ? 'Meilleur Vendeur' : 'Top Seller';
  const tooltip = isFrench
    ? "Ce vendeur figure parmi les meilleurs vendeurs BidVex par volume de ventes"
    : "This seller is among BidVex's highest-rated sellers by total sales volume";

  const sizeClasses = {
    xs: 'text-[10px] px-1.5 py-0.5 gap-0.5',
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-sm px-3 py-1 gap-1.5',
  }[size] || 'text-xs px-2 py-0.5 gap-1';
  const starSize = { xs: 'h-2.5 w-2.5', sm: 'h-3 w-3', md: 'h-4 w-4' }[size] || 'h-3 w-3';

  return (
    <span
      title={tooltip}
      data-testid="top-seller-badge"
      className={`inline-flex items-center ${sizeClasses} rounded-full font-bold tracking-wide
        bg-gradient-to-r from-amber-400 to-yellow-300 text-amber-950
        border border-amber-500/60 shadow-sm cursor-help ${className}`}
    >
      <Star className={`${starSize} fill-amber-700 text-amber-700`} />
      {label}
    </span>
  );
};

export default TopSellerBadge;
