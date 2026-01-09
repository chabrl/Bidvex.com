import React, { useState, useEffect, useRef } from 'react';
import { History, TrendingUp, Clock, User, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { useCurrency } from '../contexts/CurrencyContext';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * PublicBidHistory - Transparent bid history display with masked bidder identities
 * Features:
 * - Masked bidder names (B***r1, A***n4)
 * - Live updates via polling (WebSocket-ready)
 * - Shows bid time, amount, and competition indicators
 */
const PublicBidHistory = ({ listingId, lotNumber, currentPrice, sellerExchangeRate }) => {
  const [bids, setBids] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const { formatPrice, currency } = useCurrency();
  const pollIntervalRef = useRef(null);

  // Mask bidder name for privacy (e.g., "John Smith" -> "J***n S.")
  const maskBidderName = (name, index) => {
    if (!name) return `Bidder ${index + 1}`;
    const parts = name.split(' ');
    if (parts.length >= 2) {
      const firstName = parts[0];
      const lastName = parts[parts.length - 1];
      return `${firstName[0]}***${firstName.slice(-1)} ${lastName[0]}.`;
    }
    // Single name
    if (name.length <= 3) return `${name[0]}***`;
    return `${name[0]}***${name.slice(-1)}`;
  };

  // Fetch bid history
  const fetchBidHistory = async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    try {
      let endpoint = lotNumber 
        ? `${API}/multi-item-listings/${listingId}/lots/${lotNumber}/bids`
        : `${API}/bids/listing/${listingId}`;
      
      const response = await axios.get(endpoint);
      const bidData = response.data || [];
      
      // Sort by amount descending (highest first) and add index for masking
      const sortedBids = bidData
        .sort((a, b) => b.amount - a.amount)
        .map((bid, index) => ({
          ...bid,
          maskedName: maskBidderName(bid.bidder_name || bid.bidder?.name, index),
          rank: index + 1
        }));
      
      setBids(sortedBids);
    } catch (error) {
      console.error('Failed to fetch bid history:', error);
      // Don't clear existing bids on error
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Initial fetch and polling for live updates
  useEffect(() => {
    fetchBidHistory();
    
    // Poll every 10 seconds for live updates
    pollIntervalRef.current = setInterval(() => {
      fetchBidHistory();
    }, 10000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [listingId, lotNumber]);

  // Format time ago
  const getTimeAgo = (timestamp) => {
    const now = new Date();
    const bidTime = new Date(timestamp);
    const diffMs = now - bidTime;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const displayBids = expanded ? bids : bids.slice(0, 5);
  const totalBids = bids.length;
  const uniqueBidders = new Set(bids.map(b => b.bidder_id)).size;

  if (loading) {
    return (
      <Card className="bg-white/80 dark:bg-slate-800/80 backdrop-blur border-slate-200 dark:border-slate-700">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <History className="h-5 w-5 text-blue-600" />
            Bid History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-600 border-t-transparent" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white/80 dark:bg-slate-800/80 backdrop-blur border-slate-200 dark:border-slate-700" data-testid="public-bid-history">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <History className="h-5 w-5 text-blue-600" />
            Bid History
            {totalBids > 0 && (
              <Badge variant="secondary" className="ml-2">
                {totalBids} bid{totalBids !== 1 ? 's' : ''}
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fetchBidHistory(true)}
            disabled={refreshing}
            className="text-slate-500 hover:text-slate-700"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        {totalBids > 0 && (
          <div className="flex items-center gap-4 text-sm text-slate-500 dark:text-slate-400 mt-2">
            <span className="flex items-center gap-1">
              <User className="h-4 w-4" />
              {uniqueBidders} bidder{uniqueBidders !== 1 ? 's' : ''}
            </span>
            <span className="flex items-center gap-1">
              <TrendingUp className="h-4 w-4 text-green-500" />
              {formatPrice(currentPrice, sellerExchangeRate)} current
            </span>
          </div>
        )}
      </CardHeader>
      
      <CardContent>
        {bids.length === 0 ? (
          <div className="text-center py-8 text-slate-500 dark:text-slate-400">
            <History className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p className="font-medium">No bids yet</p>
            <p className="text-sm">Be the first to place a bid!</p>
          </div>
        ) : (
          <div className="space-y-2">
            {displayBids.map((bid, index) => (
              <div
                key={bid.id || index}
                className={`flex items-center justify-between p-3 rounded-lg transition-all duration-200 ${
                  index === 0 
                    ? 'bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border border-green-200 dark:border-green-800' 
                    : 'bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-700/50'
                }`}
                data-testid={`bid-entry-${index}`}
              >
                <div className="flex items-center gap-3">
                  {/* Rank Badge */}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                    index === 0 
                      ? 'bg-green-500 text-white' 
                      : index === 1 
                      ? 'bg-slate-400 text-white' 
                      : index === 2 
                      ? 'bg-amber-600 text-white' 
                      : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                  }`}>
                    {bid.rank}
                  </div>
                  
                  {/* Bidder Info */}
                  <div>
                    <p className={`font-semibold ${index === 0 ? 'text-green-700 dark:text-green-400' : 'text-slate-900 dark:text-white'}`}>
                      {bid.maskedName}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {getTimeAgo(bid.created_at || bid.timestamp)}
                    </p>
                  </div>
                </div>

                {/* Bid Amount */}
                <div className="text-right">
                  <p className={`font-bold text-lg ${index === 0 ? 'text-green-600 dark:text-green-400' : 'text-slate-900 dark:text-white'}`}>
                    {formatPrice(bid.amount, sellerExchangeRate)}
                  </p>
                  {bid.bid_type && bid.bid_type !== 'normal' && (
                    <Badge variant="outline" className="text-xs">
                      {bid.bid_type === 'auto' ? 'Auto-Bid' : bid.bid_type}
                    </Badge>
                  )}
                </div>
              </div>
            ))}

            {/* Show More/Less Button */}
            {totalBids > 5 && (
              <Button
                variant="ghost"
                className="w-full mt-2 text-blue-600 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <>
                    <ChevronUp className="h-4 w-4 mr-2" />
                    Show Less
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-4 w-4 mr-2" />
                    View All {totalBids} Bids
                  </>
                )}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default PublicBidHistory;
