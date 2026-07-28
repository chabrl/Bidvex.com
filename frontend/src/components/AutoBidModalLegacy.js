import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { Bot, Settings, Zap } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { usePlatformTermsGate } from '../contexts/PlatformTermsGateContext';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Switch } from './ui/switch';
import axios from 'axios';
import { toast } from 'sonner';
import { extractErrorMessage } from '../utils/errorHandler';
import { formatCurrency } from '../utils/currencyFormatter';
import { useTranslation } from 'react-i18next';
import InfoTip from './InfoTip';

const API = API_BASE;

const AutoBidModal = ({ listingId, currentBid, minimumIncrement, onAutoBidSetup }) => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { runWithTermsGate } = usePlatformTermsGate();
  const [isOpen, setIsOpen] = useState(false);
  const [maxBid, setMaxBid] = useState('');
  const [loading, setLoading] = useState(false);
  const [autoBidActive, setAutoBidActive] = useState(false);
  const [existingAutoBid, setExistingAutoBid] = useState(null);

  useEffect(() => {
    if (user && isOpen) {
      checkExistingAutoBid();
    }
  }, [user, isOpen, listingId]);

  const checkExistingAutoBid = async () => {
    try {
      const response = await axios.get(`${API}/bids/auto-bid`);
      const existing = response.data.auto_bids.find(ab => ab.listing_id === listingId && ab.is_active);
      if (existing) {
        setExistingAutoBid(existing);
        setAutoBidActive(true);
        setMaxBid(existing.max_bid.toString());
      }
    } catch (error) {
      console.error('Failed to fetch auto-bids:', error);
    }
  };

  const handleSetupAutoBid = async () => {
    if (!user) {
      toast.error('Please login to use Auto-Bid Bot');
      return;
    }

    // Check subscription tier
    if (user.subscription_tier === 'free') {
      toast.error('Auto-Bid Bot is a Premium feature', {
        description: 'Upgrade to Premium or VIP to use Auto-Bid Bot'
      });
      return;
    }

    const amount = parseFloat(maxBid);
    if (isNaN(amount) || amount <= currentBid) {
      toast.error(`Max bid must be higher than current bid of ${formatCurrency(currentBid)}`);
      return;
    }

    setLoading(true);
    try {
      const response = await runWithTermsGate(() => axios.post(`${API}/bids/auto-bid`, null, {
        params: {
          listing_id: listingId,
          max_bid: amount
        }
      }));

      toast.success('Auto-Bid Bot activated!', {
        description: `Will bid up to ${formatCurrency(amount)} using ${minimumIncrement > 0 ? 'seller\'s increment schedule' : 'standard increments'}`
      });

      setAutoBidActive(true);
      setIsOpen(false);
      
      if (onAutoBidSetup) {
        onAutoBidSetup(amount);
      }
    } catch (error) {
      // iter404 — silent no-op when the inline T&C modal is cancelled.
      if (error?.termsGateCancelled) { setLoading(false); return; }
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to setup Auto-Bid Bot');
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivate = async () => {
    setLoading(true);
    try {
      await axios.delete(`${API}/bids/auto-bid/${listingId}`);
      toast.success('Auto-Bid Bot deactivated');
      setAutoBidActive(false);
      setExistingAutoBid(null);
      setMaxBid('');
      setIsOpen(false);
    } catch (error) {
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to deactivate Auto-Bid Bot');
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  const isPremium = user.subscription_tier === 'premium' || user.subscription_tier === 'vip';

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
        variant={autoBidActive ? "default" : "outline"}
        className={autoBidActive ? "bg-green-600 hover:bg-green-700 text-white" : ""}
      >
        <Bot className="h-4 w-4 mr-2" />
        {autoBidActive ? 'Auto-Bid Active' : 'Setup Auto-Bid'}
        {!isPremium && (
          <Badge className="ml-2 bg-purple-500 text-white text-xs">
            Premium
          </Badge>
        )}
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-green-600" />
              Auto-Bid Bot Setup
            </DialogTitle>
            <DialogDescription>
              Set a maximum bid and let the bot automatically bid for you.
              {!isPremium && (
                <div className="mt-2 p-3 bg-purple-50 border border-purple-200 rounded-md">
                  <p className="text-sm text-purple-800">
                    🔒 <strong>Premium Feature:</strong> Auto-Bid Bot is available for Premium and VIP members.
                  </p>
                  <Button size="sm" className="mt-2 bg-purple-600 hover:bg-purple-700 text-white">
                    Upgrade to Premium
                  </Button>
                </div>
              )}
            </DialogDescription>
          </DialogHeader>

          {isPremium && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t("bidding.currentBid")}</Label>
                <div className="text-2xl font-bold text-primary">
                  {formatCurrency(currentBid)}
                </div>
                <p className="text-xs text-muted-foreground">
                  Bot will follow seller's increment: {formatCurrency(minimumIncrement)}
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="max-bid-amount">{t("bidding.maxBidAmount")}
                  <InfoTip en="The bot will bid in small increments up to this amount. You won't pay more than this." fr="Le robot enchérira par petits incréments jusqu'à ce montant. Vous ne paierez pas plus que ce montant." />
                </Label>
                <Input
                  id="max-bid-amount"
                  type="number"
                  step="0.01"
                  min={currentBid + minimumIncrement}
                  value={maxBid}
                  onChange={(e) => setMaxBid(e.target.value)}
                  placeholder={`Enter max bid (min: ${formatCurrency(currentBid + minimumIncrement)})`}
                  className="text-lg"
                  disabled={!isPremium}
                />
              </div>

              <div className="p-4 bg-blue-50 border border-blue-200 rounded-md space-y-2">
                <p className="text-sm font-medium text-blue-800">How Auto-Bid Works:</p>
                <ul className="text-xs text-blue-700 space-y-1">
                  <li>• Bot will bid for you automatically when outbid</li>
                  <li>• Follows seller's increment schedule</li>
                  <li>• Stops when your max bid is reached</li>
                  <li>• You can deactivate anytime</li>
                </ul>
              </div>

              {autoBidActive && existingAutoBid && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-md">
                  <p className="text-sm font-medium text-green-800">
                    ✅ Auto-Bid Currently Active
                  </p>
                  <p className="text-xs text-green-700 mt-1">
                    Max Bid: {formatCurrency(existingAutoBid.max_bid)}
                  </p>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Cancel
            </Button>
            {isPremium && (
              <>
                {autoBidActive ? (
                  <Button
                    onClick={handleDeactivate}
                    disabled={loading}
                    variant="destructive"
                  >
                    {loading ? 'Deactivating...' : 'Deactivate Auto-Bid'}
                  </Button>
                ) : (
                  <Button
                    onClick={handleSetupAutoBid}
                    disabled={loading || !maxBid}
                    className="bg-green-600 hover:bg-green-700 text-white"
                  >
                    {loading ? (
                      <>Processing...</>
                    ) : (
                      <>
                        <Bot className="h-4 w-4 mr-2" />
                        Activate Auto-Bid
                      </>
                    )}
                  </Button>
                )}
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default AutoBidModal;
