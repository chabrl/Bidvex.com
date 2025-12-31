import React, { useState, useEffect } from 'react';
import { Zap, Sparkles } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PowerBidButton = ({ listingId, currentBid, minimumIncrement, onBidPlaced }) => {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [bidAmount, setBidAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [powerBidsUsed, setPowerBidsUsed] = useState(0);
  const [subscriptionInfo, setSubscriptionInfo] = useState(null);

  useEffect(() => {
    if (user && isOpen) {
      fetchSubscriptionInfo();
      setPowerBidsUsed(user.monster_bids_used?.[listingId] || 0);
    }
  }, [user, isOpen, listingId]);

  const fetchSubscriptionInfo = async () => {
    try {
      const response = await axios.get(`${API}/subscription/status`);
      setSubscriptionInfo(response.data);
    } catch (error) {
      console.error('Failed to fetch subscription info:', error);
    }
  };

  const handlePowerBid = async () => {
    if (!user) {
      toast.error('Please login to place a Power Bid');
      return;
    }

    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount <= currentBid) {
      toast.error(`Power Bid must be higher than current bid of $${currentBid.toFixed(2)}`);
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/bids/monster`, null, {
        params: {
          listing_id: listingId,
          amount: amount
        }
      });

      toast.success('⚡ Power Bid placed successfully!', {
        description: response.data.message
      });

      setPowerBidsUsed(prev => prev + 1);
      setIsOpen(false);
      setBidAmount('');
      
      if (onBidPlaced) {
        onBidPlaced(amount, 'monster');
      }
    } catch (error) {
      console.error('Power Bid error:', error);
      toast.error(error.response?.data?.detail || 'Failed to place Power Bid');
    } finally {
      setLoading(false);
    }
  };

  const canUsePowerBid = () => {
    if (!user) return false;
    const tier = user.subscription_tier || 'free';
    if (tier === 'free') {
      return powerBidsUsed < 1;
    }
    return true; // Premium and VIP have unlimited
  };

  const getRemainingBids = () => {
    if (!user) return 0;
    const tier = user.subscription_tier || 'free';
    if (tier === 'free') {
      return Math.max(0, 1 - powerBidsUsed);
    }
    return '∞'; // Unlimited
  };

  if (!user) return null;

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
        disabled={!canUsePowerBid()}
        className="relative bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white border-0 group overflow-hidden"
      >
        <Zap className="h-4 w-4 mr-2 group-hover:animate-pulse" />
        Power Bid
        {user.subscription_tier === 'free' && (
          <Badge className="ml-2 bg-yellow-400 text-black text-xs">
            {getRemainingBids()} left
          </Badge>
        )}
        <Sparkles className="absolute top-0 right-0 h-3 w-3 text-yellow-300 animate-pulse" />
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-[#06B6D4]" />
              Place a Power Bid
            </DialogTitle>
            <DialogDescription>
              Override standard bid increments with a Power Bid!
              {user.subscription_tier === 'free' && (
                <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-sm text-blue-800">
                    🆓 <strong>Free Tier:</strong> You get 1 Power Bid per auction.
                  </p>
                  <p className="text-xs text-blue-700 mt-1">
                    Upgrade to BidVex Premium for unlimited Power Bids!
                  </p>
                </div>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Current Bid</Label>
              <div className="text-2xl font-bold text-primary">
                ${currentBid.toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground">
                Standard minimum increment: ${minimumIncrement.toFixed(2)}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="power-bid-amount">Your Power Bid Amount</Label>
              <Input
                id="power-bid-amount"
                type="number"
                step="0.01"
                min={currentBid + 0.01}
                value={bidAmount}
                onChange={(e) => setBidAmount(e.target.value)}
                placeholder={`Enter amount higher than $${currentBid.toFixed(2)}`}
                className="text-lg"
              />
            </div>

            {subscriptionInfo && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                <p className="text-sm font-medium text-blue-800">
                  Your Subscription: <Badge className="ml-1">{subscriptionInfo.subscription_tier.toUpperCase()}</Badge>
                </p>
                <p className="text-xs text-blue-700 mt-1">
                  Power Bids Remaining: {getRemainingBids() === '∞' ? 'Unlimited' : getRemainingBids()}
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handlePowerBid}
              disabled={loading || !bidAmount}
              className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] hover:from-[#1E3A8A]/90 hover:to-[#06B6D4]/90 text-white"
            >
              {loading ? (
                <>Processing...</>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2" />
                  Place Power Bid
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default PowerBidButton;
