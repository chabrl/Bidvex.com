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

const MonsterBidButton = ({ listingId, currentBid, minimumIncrement, onBidPlaced }) => {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [bidAmount, setBidAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [monsterBidsUsed, setMonsterBidsUsed] = useState(0);
  const [subscriptionInfo, setSubscriptionInfo] = useState(null);

  useEffect(() => {
    if (user && isOpen) {
      fetchSubscriptionInfo();
      setMonsterBidsUsed(user.monster_bids_used?.[listingId] || 0);
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

  const handleMonsterBid = async () => {
    if (!user) {
      toast.error('Please login to place a Monster Bid');
      return;
    }

    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount <= currentBid) {
      toast.error(`Monster Bid must be higher than current bid of $${currentBid.toFixed(2)}`);
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

      toast.success('⚡ Monster Bid placed successfully!', {
        description: response.data.message
      });

      setMonsterBidsUsed(prev => prev + 1);
      setIsOpen(false);
      setBidAmount('');
      
      if (onBidPlaced) {
        onBidPlaced(amount, 'monster');
      }
    } catch (error) {
      console.error('Monster Bid error:', error);
      toast.error(error.response?.data?.detail || 'Failed to place Monster Bid');
    } finally {
      setLoading(false);
    }
  };

  const canUseMonsterBid = () => {
    if (!user) return false;
    const tier = user.subscription_tier || 'free';
    if (tier === 'free') {
      return monsterBidsUsed < 1;
    }
    return true; // Premium and VIP have unlimited
  };

  const getRemainingBids = () => {
    if (!user) return 0;
    const tier = user.subscription_tier || 'free';
    if (tier === 'free') {
      return Math.max(0, 1 - monsterBidsUsed);
    }
    return '∞'; // Unlimited
  };

  if (!user) return null;

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
        disabled={!canUseMonsterBid()}
        className="relative bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white border-0 group overflow-hidden"
      >
        <Zap className="h-4 w-4 mr-2 group-hover:animate-pulse" />
        Monster Bid
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
              <Zap className="h-5 w-5 text-purple-600" />
              Place a Monster Bid
            </DialogTitle>
            <DialogDescription>
              Override standard bid increments with a Monster Bid!
              {user.subscription_tier === 'free' && (
                <div className="mt-2 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                  <p className="text-sm text-yellow-800">
                    🆓 <strong>Free Tier:</strong> You get 1 Monster Bid per auction.
                  </p>
                  <p className="text-xs text-yellow-700 mt-1">
                    Upgrade to Premium for unlimited Monster Bids!
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
              <Label htmlFor="monster-bid-amount">Your Monster Bid Amount</Label>
              <Input
                id="monster-bid-amount"
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
              <div className="p-3 bg-purple-50 border border-purple-200 rounded-md">
                <p className="text-sm font-medium text-purple-800">
                  Your Subscription: <Badge className="ml-1">{subscriptionInfo.subscription_tier.toUpperCase()}</Badge>
                </p>
                <p className="text-xs text-purple-700 mt-1">
                  Monster Bids Remaining: {getRemainingBids() === '∞' ? 'Unlimited' : getRemainingBids()}
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleMonsterBid}
              disabled={loading || !bidAmount}
              className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white"
            >
              {loading ? (
                <>Processing...</>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2" />
                  Place Monster Bid
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default MonsterBidButton;
