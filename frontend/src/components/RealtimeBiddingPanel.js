import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useRealtimeBidding } from '../hooks/useRealtimeBidding';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Gavel, 
  TrendingUp, 
  AlertCircle, 
  CheckCircle2, 
  Wifi, 
  WifiOff,
  Calculator,
  DollarSign
} from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

/**
 * Real-time bidding panel with quantity-based price calculations
 * Features:
 * - <200ms real-time updates via WebSocket
 * - LEADING/OUTBID status badges
 * - Quantity × Price transparency
 * - Confirmation modal for multi-quantity items
 * - Fallback polling on disconnect
 */
const RealtimeBiddingPanel = ({ listing, onBidPlaced }) => {
  const { user, login } = useAuth();
  const {
    currentPrice,
    bidCount,
    highestBidderId,
    bidStatus,
    isConnected,
    lastUpdate
  } = useRealtimeBidding(listing.id);

  const [bidAmount, setBidAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [agreedToTotal, setAgreedToTotal] = useState(false);

  const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
  const quantity = listing.quantity || 1;
  const isMultiQuantity = quantity > 1;

  // Calculate total value (price × quantity)
  const totalValue = useMemo(() => {
    const amount = parseFloat(bidAmount) || 0;
    return amount * quantity;
  }, [bidAmount, quantity]);

  // Calculate minimum bid (current price + increment)
  const minBidAmount = useMemo(() => {
    const current = currentPrice || listing.starting_price || 0;
    const increment = listing.minimum_bid_increment || 1;
    return (Math.floor((current + increment) * 100) / 100).toFixed(2);
  }, [currentPrice, listing.starting_price, listing.minimum_bid_increment]);

  // Auto-set minimum bid
  useEffect(() => {
    if (!bidAmount) {
      setBidAmount(minBidAmount);
    }
  }, [minBidAmount]);

  // Determine bid status for current user
  const userBidStatus = useMemo(() => {
    if (!user) return 'NOT_LOGGED_IN';
    if (bidStatus === 'LEADING') return 'LEADING';
    if (bidStatus === 'OUTBID') return 'OUTBID';
    if (highestBidderId && highestBidderId !== user.id) return 'NOT_BIDDING';
    return 'NO_BIDS';
  }, [user, bidStatus, highestBidderId]);

  const placeBid = async () => {
    if (!user) {
      toast.error('Please log in to place a bid');
      return;
    }

    const amount = parseFloat(bidAmount);
    
    if (isNaN(amount) || amount <= 0) {
      toast.error('Please enter a valid bid amount');
      return;
    }

    if (amount < parseFloat(minBidAmount)) {
      toast.error(`Minimum bid is $${minBidAmount}`);
      return;
    }

    // Show confirmation modal for multi-quantity items
    if (isMultiQuantity && !agreedToTotal) {
      setShowConfirmModal(true);
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(
        `${API_URL}/api/bids`,
        {
          listing_id: listing.id,
          amount: amount
        },
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`
          }
        }
      );

      if (response.status === 200) {
        toast.success('Bid placed successfully!');
        setBidAmount('');
        setAgreedToTotal(false);
        setShowConfirmModal(false);
        
        if (onBidPlaced) {
          onBidPlaced(response.data);
        }
      }
    } catch (error) {
      console.error('Bid error:', error);
      toast.error(
        error.response?.data?.detail || 
        'Failed to place bid. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmBid = () => {
    setAgreedToTotal(true);
    setShowConfirmModal(false);
    // Trigger bid placement
    setTimeout(() => placeBid(), 100);
  };

  return (
    <div className="space-y-4">
      {/* Connection Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <Wifi className="h-4 w-4 text-green-500" />
              <span className="text-xs text-green-600 font-medium">Live Updates Active</span>
            </>
          ) : (
            <>
              <WifiOff className="h-4 w-4 text-orange-500 animate-pulse" />
              <span className="text-xs text-orange-600 font-medium">Reconnecting...</span>
            </>
          )}
        </div>
        
        {lastUpdate && (
          <span className="text-xs text-muted-foreground">
            Updated {new Date(lastUpdate).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Current Price & Bid Status */}
      <div className="glassmorphism p-4 rounded-lg space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current Bid</p>
            <p className="text-3xl font-bold text-primary">
              ${(currentPrice || listing.starting_price || 0).toFixed(2)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {bidCount || 0} {bidCount === 1 ? 'bid' : 'bids'} placed
            </p>
          </div>

          {/* Bid Status Badge */}
          {user && (
            <div>
              {userBidStatus === 'LEADING' && (
                <Badge className="bg-green-500 text-white px-4 py-2 text-sm font-bold animate-pulse">
                  <CheckCircle2 className="h-4 w-4 mr-1" />
                  LEADING
                </Badge>
              )}
              {userBidStatus === 'OUTBID' && (
                <Badge className="bg-red-500 text-white px-4 py-2 text-sm font-bold">
                  <AlertCircle className="h-4 w-4 mr-1" />
                  OUTBID
                </Badge>
              )}
              {userBidStatus === 'NOT_BIDDING' && (
                <Badge variant="outline" className="px-4 py-2 text-sm">
                  Not Bidding
                </Badge>
              )}
              {userBidStatus === 'NO_BIDS' && (
                <Badge variant="secondary" className="px-4 py-2 text-sm">
                  No Bids Yet
                </Badge>
              )}
            </div>
          )}
        </div>

        {/* Quantity Warning for Multi-Item Lots */}
        {isMultiQuantity && (
          <Alert className="bg-yellow-50 border-yellow-300">
            <Calculator className="h-4 w-4 text-yellow-600" />
            <AlertDescription className="text-yellow-800">
              <strong>Multi-Item Lot:</strong> This lot contains <strong>{quantity} items</strong>.
              Your bid is per unit, and you will be committed to purchasing all items.
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Bid Input */}
      {user ? (
        <div className="space-y-3">
          <div className="space-y-2">
            <label className="text-sm font-medium flex items-center gap-2">
              <Gavel className="h-4 w-4" />
              Your Bid Amount {isMultiQuantity && '(per unit)'}
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="number"
                  step="0.01"
                  min={minBidAmount}
                  value={bidAmount}
                  onChange={(e) => setBidAmount(e.target.value)}
                  placeholder={`Min: $${minBidAmount}`}
                  className="pl-10"
                  disabled={loading}
                />
              </div>
              <Button
                onClick={placeBid}
                disabled={loading || !bidAmount || parseFloat(bidAmount) < parseFloat(minBidAmount)}
                className="gradient-button text-white border-0 min-w-[120px]"
              >
                {loading ? (
                  'Placing...'
                ) : (
                  <>
                    <TrendingUp className="h-4 w-4 mr-2" />
                    Place Bid
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Total Value Calculation */}
          {isMultiQuantity && bidAmount && (
            <div className="glassmorphism p-4 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Bid per unit:</span>
                  <span className="font-medium">${parseFloat(bidAmount).toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Quantity:</span>
                  <span className="font-medium">× {quantity} items</span>
                </div>
                <div className="border-t pt-2 mt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-700">Total Commitment:</span>
                    <span className="text-2xl font-bold text-primary">
                      ${totalValue.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 text-center">
                    You will be required to pay this amount if you win
                  </p>
                </div>
              </div>
            </div>
          )}

          <p className="text-xs text-muted-foreground text-center">
            Minimum bid: ${minBidAmount} • Next increment: ${listing.minimum_bid_increment || 1}
          </p>
        </div>
      ) : (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Please <button onClick={() => window.location.href = '/auth'} className="text-primary font-semibold underline">log in</button> to place a bid.
          </AlertDescription>
        </Alert>
      )}

      {/* Confirmation Modal for Multi-Quantity Items */}
      {showConfirmModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in duration-200">
            <div className="flex items-start gap-3">
              <div className="h-12 w-12 rounded-full bg-yellow-100 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="h-6 w-6 text-yellow-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-gray-900">
                  Confirm Multi-Item Purchase
                </h3>
                <p className="text-sm text-gray-600 mt-1">
                  Please review your total commitment before proceeding.
                </p>
              </div>
            </div>

            <div className="bg-gray-50 rounded-lg p-4 space-y-2 border-2 border-gray-200">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Lot contains:</span>
                <span className="font-semibold">{quantity} items</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Your bid per unit:</span>
                <span className="font-semibold">${parseFloat(bidAmount).toFixed(2)}</span>
              </div>
              <div className="border-t pt-2 mt-2">
                <div className="flex justify-between">
                  <span className="font-semibold text-gray-900">Total Amount:</span>
                  <span className="text-2xl font-bold text-primary">
                    ${totalValue.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-800">
                <strong>Note:</strong> By placing this bid, you agree to purchase all {quantity} items at your bid price if you win. 
                Your total payment obligation will be <strong>${totalValue.toFixed(2)}</strong>.
              </p>
            </div>

            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={() => {
                  setShowConfirmModal(false);
                  setAgreedToTotal(false);
                }}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirmBid}
                className="flex-1 gradient-button text-white border-0"
              >
                I Understand - Proceed
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RealtimeBiddingPanel;
