/**
 * AuctionRulesDisplay.js
 * Auction rules, anti-sniping, bid increments, and transparency displays
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';
import {
  Clock, TrendingUp, Shield, Zap, Info, AlertTriangle,
  ChevronRight, History, Users, Lock, CheckCircle,
  Timer, ArrowUp, RefreshCw, Eye
} from 'lucide-react';

// Format currency
const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
  }).format(amount || 0);
};

// Bid Increment Table
const BID_INCREMENTS = [
  { range: '$0 - $99', increment: '$5' },
  { range: '$100 - $499', increment: '$10' },
  { range: '$500 - $999', increment: '$25' },
  { range: '$1,000 - $4,999', increment: '$50' },
  { range: '$5,000 - $9,999', increment: '$100' },
  { range: '$10,000 - $49,999', increment: '$250' },
  { range: '$50,000 - $99,999', increment: '$500' },
  { range: '$100,000+', increment: '$1,000' },
];

// Get minimum increment based on current bid
const getMinimumIncrement = (currentBid) => {
  if (currentBid < 100) return 5;
  if (currentBid < 500) return 10;
  if (currentBid < 1000) return 25;
  if (currentBid < 5000) return 50;
  if (currentBid < 10000) return 100;
  if (currentBid < 50000) return 250;
  if (currentBid < 100000) return 500;
  return 1000;
};

// Anti-Sniping Notice
export const AntiSnipingNotice = ({ timeExtended, extensionReason, newEndTime }) => {
  if (!timeExtended) return null;

  return (
    <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/30 animate-pulse" data-testid="anti-sniping-notice">
      <Timer className="h-5 w-5 text-blue-600" />
      <AlertTitle className="text-blue-800 dark:text-blue-200">Auction Extended!</AlertTitle>
      <AlertDescription className="text-blue-700 dark:text-blue-300">
        <p>
          {extensionReason || 'A bid was placed in the final 2 minutes.'} 
          The auction has been extended to give all bidders a fair chance.
        </p>
        {newEndTime && (
          <p className="mt-1 font-semibold">
            New end time: {new Date(newEndTime).toLocaleString()}
          </p>
        )}
      </AlertDescription>
    </Alert>
  );
};

// Anti-Sniping Rules Card
export const AntiSnipingRulesCard = ({ compact = false }) => {
  if (compact) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="outline" className="gap-1 cursor-help">
              <Shield className="h-3 w-3" />
              Anti-Sniping Protected
            </Badge>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p>Bids in the last 2 minutes extend the auction by 2 minutes, giving all bidders a fair chance.</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <Card className="border-blue-100 dark:border-blue-900" data-testid="anti-sniping-rules">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Shield className="h-5 w-5 text-blue-600" />
          Anti-Sniping Protection
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 text-sm">
          <p className="text-slate-600 dark:text-slate-400">
            To ensure fair bidding, we automatically extend auctions when bids are placed 
            in the final moments:
          </p>
          <ul className="space-y-2">
            <li className="flex items-start gap-2">
              <CheckCircle className="h-4 w-4 text-blue-500 mt-0.5" />
              <span>Bids in final <strong>2 minutes</strong> trigger a 2-minute extension</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-4 w-4 text-blue-500 mt-0.5" />
              <span>Extensions continue until no bids in final 2 minutes</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-4 w-4 text-blue-500 mt-0.5" />
              <span>All bidders are notified of extensions in real-time</span>
            </li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

// Minimum Bid Display
export const MinimumBidDisplay = ({ currentBid, minBid, increment }) => {
  const calculatedIncrement = increment || getMinimumIncrement(currentBid);
  const calculatedMinBid = minBid || (currentBid + calculatedIncrement);

  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3" data-testid="minimum-bid-display">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">Minimum Next Bid</p>
          <p className="text-xl font-bold text-blue-600">
            {formatCurrency(calculatedMinBid)}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Increment</p>
          <Badge variant="outline" className="font-mono">
            +{formatCurrency(calculatedIncrement)}
          </Badge>
        </div>
      </div>
    </div>
  );
};

// Bid Increment Schedule
export const BidIncrementSchedule = ({ currentBid, expanded = false }) => {
  const currentIncrement = getMinimumIncrement(currentBid || 0);

  return (
    <Card className="border-slate-200" data-testid="bid-increment-schedule">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <ArrowUp className="h-5 w-5 text-slate-600" />
          Bid Increment Schedule
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {BID_INCREMENTS.map((tier, index) => {
            const isCurrentTier = tier.increment === `$${currentIncrement.toLocaleString()}`;
            return (
              <div 
                key={index}
                className={`flex justify-between items-center py-2 px-3 rounded ${
                  isCurrentTier 
                    ? 'bg-blue-50 border border-blue-200 dark:bg-blue-950/30' 
                    : 'bg-slate-50 dark:bg-slate-800/50'
                }`}
              >
                <span className={`text-sm ${isCurrentTier ? 'font-semibold text-blue-700' : 'text-slate-600'}`}>
                  {tier.range}
                </span>
                <Badge className={isCurrentTier ? 'bg-blue-500' : 'bg-slate-400'}>
                  {tier.increment}
                </Badge>
              </div>
            );
          })}
        </div>
        {currentBid > 0 && (
          <p className="text-xs text-slate-500 mt-3 text-center">
            Current bid: {formatCurrency(currentBid)} → Next increment: {formatCurrency(currentIncrement)}
          </p>
        )}
      </CardContent>
    </Card>
  );
};

// Bid History Component
export const BidHistory = ({ bids = [], showCount = 10, anonymized = true }) => {
  const displayBids = bids.slice(0, showCount);

  if (displayBids.length === 0) {
    return (
      <Card className="border-slate-200" data-testid="bid-history-empty">
        <CardContent className="p-8 text-center">
          <History className="h-12 w-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500">No bids yet. Be the first to bid!</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-slate-200" data-testid="bid-history">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center justify-between">
          <span className="flex items-center gap-2">
            <History className="h-5 w-5 text-slate-600" />
            Bid History
          </span>
          <Badge variant="outline">{bids.length} total bids</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {displayBids.map((bid, index) => (
            <div 
              key={bid.id || index}
              className={`flex items-center justify-between p-3 rounded-lg ${
                index === 0 
                  ? 'bg-green-50 border border-green-200 dark:bg-green-950/30' 
                  : 'bg-slate-50 dark:bg-slate-800/50'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  index === 0 
                    ? 'bg-green-500 text-white' 
                    : 'bg-slate-200 text-slate-600'
                }`}>
                  {index + 1}
                </div>
                <div>
                  <p className={`font-medium ${index === 0 ? 'text-green-700' : 'text-slate-700'}`}>
                    {anonymized ? bid.bidder_name : bid.bidder_email}
                  </p>
                  <p className="text-xs text-slate-500">
                    {new Date(bid.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className={`font-bold ${index === 0 ? 'text-green-600' : 'text-slate-700'}`}>
                  {formatCurrency(bid.amount)}
                </p>
                {index === 0 && (
                  <Badge className="bg-green-500 text-xs">Leading</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
        
        {bids.length > showCount && (
          <Button variant="ghost" className="w-full mt-3 text-slate-500">
            View all {bids.length} bids <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        )}
      </CardContent>
    </Card>
  );
};

// Reserve Status Display
export const ReserveStatusDisplay = ({ hasReserve, reserveMet, prominent = false }) => {
  if (!hasReserve) {
    return (
      <div className={`flex items-center gap-2 ${prominent ? 'p-3 bg-emerald-50 dark:bg-emerald-950/30 rounded-lg border border-emerald-200' : ''}`} data-testid="no-reserve-status">
        <CheckCircle className="h-5 w-5 text-emerald-600" />
        <div>
          <p className={`font-semibold text-emerald-700 ${prominent ? '' : 'text-sm'}`}>No Reserve Auction</p>
          {prominent && (
            <p className="text-sm text-emerald-600">
              This vehicle will sell to the highest bidder regardless of price.
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div 
      className={`flex items-center gap-2 ${prominent ? 'p-3 rounded-lg border' : ''} ${
        reserveMet 
          ? (prominent ? 'bg-green-50 dark:bg-green-950/30 border-green-200' : '')
          : (prominent ? 'bg-amber-50 dark:bg-amber-950/30 border-amber-200' : '')
      }`}
      data-testid="reserve-status"
    >
      {reserveMet ? (
        <>
          <CheckCircle className="h-5 w-5 text-green-600" />
          <div>
            <p className={`font-semibold text-green-700 ${prominent ? '' : 'text-sm'}`}>Reserve Met!</p>
            {prominent && (
              <p className="text-sm text-green-600">
                The reserve price has been met. This vehicle will sell to the highest bidder.
              </p>
            )}
          </div>
        </>
      ) : (
        <>
          <AlertTriangle className="h-5 w-5 text-amber-600" />
          <div>
            <p className={`font-semibold text-amber-700 ${prominent ? '' : 'text-sm'}`}>Reserve Not Met</p>
            {prominent && (
              <p className="text-sm text-amber-600">
                Bidding has not reached the seller's minimum price. Continue bidding!
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
};

// Active Bidders Count
export const ActiveBiddersCount = ({ count, watchersCount }) => (
  <div className="flex items-center gap-4" data-testid="active-bidders">
    {count > 0 && (
      <div className="flex items-center gap-2">
        <Users className="h-4 w-4 text-blue-500" />
        <span className="text-sm text-slate-600">{count} bidders</span>
      </div>
    )}
    {watchersCount > 0 && (
      <div className="flex items-center gap-2">
        <Eye className="h-4 w-4 text-slate-400" />
        <span className="text-sm text-slate-500">{watchersCount} watching</span>
      </div>
    )}
  </div>
);

// Auction Rules Summary Card
export const AuctionRulesSummary = ({ vehicle }) => (
  <Card className="border-slate-200" data-testid="auction-rules-summary">
    <CardHeader className="pb-2">
      <CardTitle className="text-base flex items-center gap-2">
        <Info className="h-5 w-5 text-slate-600" />
        Auction Rules
      </CardTitle>
    </CardHeader>
    <CardContent className="space-y-3">
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-blue-500" />
          <span>Anti-sniping protection</span>
        </div>
        <div className="flex items-center gap-2">
          <Lock className="h-4 w-4 text-green-500" />
          <span>Binding bids</span>
        </div>
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-purple-500" />
          <span>Tiered increments</span>
        </div>
        <div className="flex items-center gap-2">
          <Eye className="h-4 w-4 text-slate-500" />
          <span>Transparent history</span>
        </div>
      </div>
      
      {vehicle?.requires_deposit && (
        <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-2 text-sm text-blue-700">
          <strong>Deposit Required:</strong> {formatCurrency(vehicle.deposit_amount)} (refundable)
        </div>
      )}
    </CardContent>
  </Card>
);

// Live Status Indicator
export const LiveStatusIndicator = ({ isLive, endTime, extended = false }) => {
  if (!isLive) return null;

  return (
    <div className="flex items-center gap-2" data-testid="live-status">
      <div className="relative">
        <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
        <div className="absolute inset-0 w-3 h-3 bg-red-500 rounded-full animate-ping" />
      </div>
      <span className="text-sm font-semibold text-red-600">LIVE AUCTION</span>
      {extended && (
        <Badge className="bg-blue-500 text-xs animate-pulse">
          <RefreshCw className="h-3 w-3 mr-1" />
          Extended
        </Badge>
      )}
    </div>
  );
};

export default {
  AntiSnipingNotice,
  AntiSnipingRulesCard,
  MinimumBidDisplay,
  BidIncrementSchedule,
  BidHistory,
  ReserveStatusDisplay,
  ActiveBiddersCount,
  AuctionRulesSummary,
  LiveStatusIndicator,
  getMinimumIncrement
};
