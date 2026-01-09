import React, { useState, useEffect } from 'react';
import { Flame, AlertTriangle, Clock, TrendingUp } from 'lucide-react';
import { Badge } from './ui/badge';
import { useCurrency } from '../contexts/CurrencyContext';
import { toast } from 'sonner';

/**
 * HighStakesUI - Visual triggers for expensive items ($10,000+ USD/CAD)
 * Features:
 * - Pulsing gold/crimson border when item exceeds threshold
 * - Red pulsing timer in final 60 minutes
 * - Live notification toasts for high-stakes bids
 */

// High-stakes threshold in USD
const HIGH_STAKES_THRESHOLD = 10000;

// Time threshold for urgency mode (60 minutes in milliseconds)
const URGENCY_TIME_THRESHOLD = 60 * 60 * 1000;

export const isHighStakes = (currentPrice) => {
  return currentPrice >= HIGH_STAKES_THRESHOLD;
};

export const isUrgencyMode = (endTime) => {
  if (!endTime) return false;
  const now = new Date();
  const end = new Date(endTime);
  const timeRemaining = end - now;
  return timeRemaining > 0 && timeRemaining <= URGENCY_TIME_THRESHOLD;
};

// High-Stakes Badge Component
export const HighStakesBadge = ({ currentPrice, className = '' }) => {
  const { formatPrice } = useCurrency();
  
  if (!isHighStakes(currentPrice)) return null;

  return (
    <Badge 
      className={`bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 text-white border-0 animate-pulse shadow-lg shadow-orange-500/50 ${className}`}
      data-testid="high-stakes-badge"
    >
      <Flame className="h-3 w-3 mr-1" />
      High-Stakes
    </Badge>
  );
};

// Urgency Timer Component with pulsing red effect
export const UrgencyTimer = ({ endTime, className = '' }) => {
  const [timeLeft, setTimeLeft] = useState(null);
  const [isUrgent, setIsUrgent] = useState(false);

  useEffect(() => {
    const updateTimer = () => {
      if (!endTime) return;
      
      const now = new Date();
      const end = new Date(endTime);
      const diff = end - now;
      
      if (diff <= 0) {
        setTimeLeft({ hours: 0, minutes: 0, seconds: 0, expired: true });
        setIsUrgent(false);
        return;
      }

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      
      setTimeLeft({ hours, minutes, seconds, expired: false });
      setIsUrgent(diff <= URGENCY_TIME_THRESHOLD);
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [endTime]);

  if (!timeLeft) return null;

  if (timeLeft.expired) {
    return (
      <div className={`flex items-center gap-2 text-slate-500 ${className}`}>
        <Clock className="h-4 w-4" />
        <span className="font-medium">Auction Ended</span>
      </div>
    );
  }

  if (isUrgent) {
    return (
      <div 
        className={`flex items-center gap-2 px-3 py-2 bg-red-600 text-white rounded-lg animate-pulse shadow-lg shadow-red-500/50 ${className}`}
        data-testid="urgency-timer"
      >
        <AlertTriangle className="h-5 w-5 animate-bounce" />
        <span className="font-bold text-lg">
          {timeLeft.hours > 0 && `${timeLeft.hours}h `}
          {String(timeLeft.minutes).padStart(2, '0')}m {String(timeLeft.seconds).padStart(2, '0')}s
        </span>
        <span className="text-sm opacity-90">ENDING SOON!</span>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-2 text-slate-600 dark:text-slate-400 ${className}`}>
      <Clock className="h-4 w-4" />
      <span className="font-medium">
        {timeLeft.hours}h {String(timeLeft.minutes).padStart(2, '0')}m {String(timeLeft.seconds).padStart(2, '0')}s
      </span>
    </div>
  );
};

// High-Stakes Card Wrapper - Adds pulsing border to lot cards
export const HighStakesWrapper = ({ children, currentPrice, endTime, className = '' }) => {
  const highStakes = isHighStakes(currentPrice);
  const urgent = isUrgencyMode(endTime);

  if (!highStakes && !urgent) {
    return <div className={className}>{children}</div>;
  }

  let borderClass = '';
  if (highStakes && urgent) {
    // Both high-stakes AND urgent - maximum intensity
    borderClass = 'ring-4 ring-red-500 ring-opacity-75 animate-pulse shadow-2xl shadow-red-500/30';
  } else if (highStakes) {
    // High-stakes only - gold pulsing border
    borderClass = 'ring-2 ring-amber-500 ring-opacity-60 shadow-xl shadow-amber-500/20';
  } else if (urgent) {
    // Urgent only - subtle red border
    borderClass = 'ring-2 ring-red-400 ring-opacity-50';
  }

  return (
    <div 
      className={`relative rounded-xl transition-all duration-300 ${borderClass} ${className}`}
      data-testid="high-stakes-wrapper"
    >
      {children}
      
      {/* High-stakes indicator corner badge */}
      {highStakes && (
        <div className="absolute -top-2 -right-2 z-10">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-amber-500 to-red-500 rounded-full blur animate-pulse" />
            <div className="relative px-2 py-1 bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-bold rounded-full flex items-center gap-1">
              <Flame className="h-3 w-3" />
              $10K+
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// High-Stakes Notification Toast Function
export const showHighStakesBidNotification = (lotTitle, bidAmount, bidderName = 'A bidder') => {
  const formattedAmount = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(bidAmount);

  toast.custom(
    (t) => (
      <div className="bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 text-white px-4 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-pulse">
        <div className="p-2 bg-white/20 rounded-full">
          <Flame className="h-6 w-6" />
        </div>
        <div>
          <p className="font-bold text-sm">High-Stakes Bid Placed!</p>
          <p className="text-sm opacity-90">
            {formattedAmount} on {lotTitle}
          </p>
        </div>
      </div>
    ),
    {
      duration: 5000,
      position: 'top-right',
    }
  );
};

// Price Display with High-Stakes styling
export const HighStakesPrice = ({ amount, className = '' }) => {
  const { formatPrice } = useCurrency();
  const highStakes = isHighStakes(amount);

  if (highStakes) {
    return (
      <span 
        className={`font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 ${className}`}
        data-testid="high-stakes-price"
      >
        {formatPrice(amount)}
      </span>
    );
  }

  return (
    <span className={`font-bold ${className}`}>
      {formatPrice(amount)}
    </span>
  );
};

export default {
  HighStakesBadge,
  UrgencyTimer,
  HighStakesWrapper,
  showHighStakesBidNotification,
  HighStakesPrice,
  isHighStakes,
  isUrgencyMode
};
