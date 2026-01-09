import React from 'react';
import { AlertTriangle, Flame, TrendingUp } from 'lucide-react';
import Countdown from 'react-countdown';
import { Badge } from './ui/badge';

/**
 * HighStakesBidCard - Visual wrapper for lots with bids over $10,000 USD
 * Features:
 * - Pulsing gold/crimson border animation
 * - Urgent red countdown timer
 * - "HIGH STAKES" badge
 * - Psychological urgency triggers
 */
const HIGH_STAKES_THRESHOLD_USD = 10000;

export const isHighStakes = (currentBidUSD) => {
  return currentBidUSD >= HIGH_STAKES_THRESHOLD_USD;
};

const HighStakesIndicator = ({ currentBidUSD }) => {
  if (!isHighStakes(currentBidUSD)) return null;

  return (
    <Badge 
      className="bg-gradient-to-r from-amber-500 via-red-500 to-amber-500 text-white font-bold px-3 py-1 animate-pulse shadow-lg shadow-amber-500/50"
      data-testid="high-stakes-badge"
    >
      <Flame className="h-4 w-4 mr-1 inline" />
      HIGH STAKES
    </Badge>
  );
};

const HighStakesTimer = ({ endDate, currentBidUSD }) => {
  if (!isHighStakes(currentBidUSD)) return null;
  
  const isEndingSoon = () => {
    const now = new Date();
    const end = new Date(endDate);
    const hoursRemaining = (end - now) / (1000 * 60 * 60);
    return hoursRemaining <= 24;
  };

  return (
    <div 
      className={`rounded-lg p-3 mb-4 border-2 ${
        isEndingSoon() 
          ? 'bg-red-50 dark:bg-red-900/30 border-red-500 animate-pulse' 
          : 'bg-amber-50 dark:bg-amber-900/20 border-amber-500'
      }`}
      data-testid="high-stakes-timer"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className={`h-5 w-5 ${isEndingSoon() ? 'text-red-600' : 'text-amber-600'}`} />
          <span className={`text-sm font-bold uppercase ${isEndingSoon() ? 'text-red-700 dark:text-red-300' : 'text-amber-700 dark:text-amber-300'}`}>
            {isEndingSoon() ? 'ENDING SOON - ACT NOW!' : 'HIGH VALUE LOT'}
          </span>
        </div>
        <div className={`text-xl font-bold ${isEndingSoon() ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'}`}>
          <Countdown 
            date={new Date(endDate)}
            renderer={({ days, hours, minutes, seconds, completed }) => {
              if (completed) {
                return <span className="text-red-600">ENDED</span>;
              }
              if (isEndingSoon()) {
                return (
                  <span className="animate-pulse">
                    {hours}h {minutes}m {seconds}s
                  </span>
                );
              }
              return (
                <span>
                  {days > 0 && `${days}d `}{hours}h {minutes}m
                </span>
              );
            }}
          />
        </div>
      </div>
    </div>
  );
};

// CSS styles for pulsing border effect (to be added to card wrapper)
export const getHighStakesCardStyles = (currentBidUSD) => {
  if (!isHighStakes(currentBidUSD)) return '';
  
  return 'high-stakes-card ring-4 ring-amber-500/50 border-amber-500 shadow-xl shadow-amber-500/20';
};

// Export components
export { HighStakesIndicator, HighStakesTimer };
export default HighStakesIndicator;
