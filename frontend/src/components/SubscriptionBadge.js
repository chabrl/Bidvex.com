import React from 'react';
import { Crown, Star, User } from 'lucide-react';
import { Badge } from './ui/badge';

const SubscriptionBadge = ({ tier, size = "default", showIcon = true }) => {
  const tierConfig = {
    free: {
      label: 'Free',
      icon: User,
      className: 'bg-gray-100 text-gray-700 border-gray-300',
    },
    premium: {
      label: 'Premium',
      icon: Star,
      className: 'bg-purple-100 text-purple-700 border-purple-300',
    },
    vip: {
      label: 'VIP',
      icon: Crown,
      className: 'bg-gradient-to-r from-yellow-400 to-orange-500 text-white border-0',
    },
  };

  const config = tierConfig[tier?.toLowerCase()] || tierConfig.free;
  const Icon = config.icon;

  const sizeClasses = {
    small: 'text-xs px-2 py-0.5',
    default: 'text-sm px-3 py-1',
    large: 'text-base px-4 py-1.5',
  };

  return (
    <Badge className={`${config.className} ${sizeClasses[size]} flex items-center gap-1 font-semibold`}>
      {showIcon && <Icon className="h-3 w-3" />}
      {config.label}
    </Badge>
  );
};

export default SubscriptionBadge;
