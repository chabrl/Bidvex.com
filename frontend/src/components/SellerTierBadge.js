import React from 'react';
import { Shield, Star, Crown } from 'lucide-react';
import { Badge } from './ui/badge';

/**
 * SellerTierBadge - Displays seller subscription tier with professional verified-style badges
 * Used on lot pages to build buyer trust
 * Premium: Silver/Platinum theme with shield icon
 * VIP: Gold/Diamond theme with crown icon
 */
const SellerTierBadge = ({ tier, size = "default", showLabel = true }) => {
  // Don't show badge for free tier
  if (!tier || tier === 'free') return null;

  const tierConfig = {
    premium: {
      label: 'Premium Seller',
      shortLabel: 'Premium',
      icon: Shield,
      className: 'bg-gradient-to-r from-slate-400 to-slate-600 text-white border-0 shadow-sm',
      iconClass: 'text-white',
    },
    vip: {
      label: 'VIP Seller',
      shortLabel: 'VIP',
      icon: Crown,
      className: 'bg-gradient-to-r from-yellow-500 via-amber-500 to-orange-500 text-white border-0 shadow-md',
      iconClass: 'text-white',
    },
  };

  const config = tierConfig[tier?.toLowerCase()];
  if (!config) return null;

  const Icon = config.icon;

  const sizeClasses = {
    small: 'text-xs px-2 py-0.5',
    default: 'text-sm px-3 py-1',
    large: 'text-base px-4 py-1.5',
  };

  const iconSizes = {
    small: 'h-3 w-3',
    default: 'h-4 w-4',
    large: 'h-5 w-5',
  };

  return (
    <Badge 
      className={`${config.className} ${sizeClasses[size]} flex items-center gap-1.5 font-semibold`}
      data-testid={`seller-tier-badge-${tier}`}
    >
      <Icon className={`${iconSizes[size]} ${config.iconClass}`} />
      {showLabel && (size === 'small' ? config.shortLabel : config.label)}
    </Badge>
  );
};

export default SellerTierBadge;
