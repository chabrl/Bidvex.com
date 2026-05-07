/**
 * StorageAutoBidModal — iter174
 * ==============================
 * Mirrors /app/frontend/src/components/AutoBidModal.js exactly (marketplace pattern):
 *   • Trigger button with purple "Premium" badge for free-tier users
 *   • Modal: Current Bid header, Max-Bid input, "How Auto-Bid Works" callout,
 *     Activate / Cancel footer.
 *   • Bilingual EN+FR per Quebec Bill 96 — every visible string shows both languages.
 *
 * Storage proxy is intrinsic to POST /api/storage-auctions/{id}/bid (every bid
 * IS a max_bid ceiling). "Activate Auto-Bid" here = submit a single proxy bid
 * with the user's chosen ceiling — the backend then auto-advances against
 * other proxies in $bid_increment steps.
 *
 * Premium gating: free / business / partner_basic users see the upsell card
 * with an "Upgrade to Premium" CTA; only premium / vip / vip_elite / partner_pro
 * see the activation form.
 */
import API_BASE from '../config';
import React, { useState } from 'react';
import { Bot } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import axios from 'axios';
import { toast } from 'sonner';
import { extractErrorMessage } from '../utils/errorHandler';
import { formatCurrency } from '../utils/currencyFormatter';
import { useNavigate } from 'react-router-dom';

const API = API_BASE;
const PREMIUM_TIERS = ['premium', 'vip', 'vip_elite', 'partner_pro', 'business'];

const StorageAutoBidModal = ({ auctionId, currentBid, bidIncrement = 10, onActivated }) => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [maxBid, setMaxBid] = useState('');
  const [loading, setLoading] = useState(false);

  if (!user) return null;

  const tier = (user.subscription_tier || 'free').toLowerCase();
  const isPremium = PREMIUM_TIERS.includes(tier);
  const minNext = (Number(currentBid) || 0) + (Number(bidIncrement) || 10);

  const handleActivate = async () => {
    const amount = parseFloat(maxBid);
    if (!Number.isFinite(amount) || amount < minNext) {
      toast.error(t('storage.autoBid.minBidToast', { amount: formatCurrency(minNext) }));
      return;
    }
    setLoading(true);
    try {
      const res = await axios.post(
        `${API}/storage-auctions/${auctionId}/bid`,
        { max_bid: amount },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(
        res.data?.you_are_winning
          ? t('storage.autoBid.leadingToast', { amount: formatCurrency(res.data.current_bid) })
          : t('storage.autoBid.outbidToast'),
      );
      setIsOpen(false);
      setMaxBid('');
      onActivated?.(res.data);
    } catch (error) {
      toast.error(extractErrorMessage(error) || t('storage.autoBid.failedToActivate'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button
        onClick={() => setIsOpen(true)}
        variant="outline"
        className="w-full"
        data-testid="storage-setup-autobid-btn"
      >
        <Bot className="h-4 w-4 mr-2" />
        {t('storage.autoBid.setupBtn')}
        {!isPremium && (
          <Badge className="ml-2 bg-purple-500 text-white text-xs" data-testid="storage-autobid-premium-badge">
            Premium
          </Badge>
        )}
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md" data-testid="storage-autobid-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-green-600" />
              {t('storage.autoBid.modalTitle')}
            </DialogTitle>
            <DialogDescription asChild>
              <div>
                <p>{t('storage.autoBid.modalDesc')}</p>
              </div>
            </DialogDescription>
          </DialogHeader>

          {!isPremium ? (
            <div className="py-4">
              <div
                className="p-4 bg-purple-50 border border-purple-200 rounded-md"
                data-testid="storage-autobid-upsell"
              >
                <p className="text-sm text-purple-800 leading-snug">
                  🔒 <strong>{t('storage.autoBid.premiumFeature')}</strong>
                  <br />
                  {t('storage.autoBid.premiumOnlyDesc')}
                </p>
                <Button
                  size="sm"
                  className="mt-3 bg-purple-600 hover:bg-purple-700 text-white"
                  onClick={() => { setIsOpen(false); navigate('/subscription'); }}
                  data-testid="storage-autobid-upgrade-btn"
                >
                  {t('storage.autoBid.upgradeToPremiumBtn')}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="space-y-1">
                <Label>{t('storage.autoBid.currentBid')}</Label>
                <div className="text-2xl font-bold text-primary">
                  {formatCurrency(currentBid || 0)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t('storage.autoBid.botIncrements', { amount: formatCurrency(bidIncrement) })}
                </p>
              </div>

              <div className="space-y-1">
                <Label htmlFor="storage-max-bid-amount">{t('storage.autoBid.maxBidAmount')}</Label>
                <Input
                  id="storage-max-bid-amount"
                  type="number"
                  step={bidIncrement}
                  min={minNext}
                  value={maxBid}
                  onChange={(e) => setMaxBid(e.target.value)}
                  placeholder={t('storage.autoBid.maxBidPlaceholder', { amount: formatCurrency(minNext) })}
                  className="text-lg"
                  data-testid="storage-autobid-max-input"
                />
                <p className="text-[11px] text-muted-foreground">
                  {t('storage.autoBid.botWillBidStepByStep')}
                </p>
              </div>

              <div className="p-4 bg-blue-50 border border-blue-200 rounded-md space-y-2">
                <p className="text-sm font-semibold text-blue-800">
                  {t('storage.autoBid.howAutoBidWorks')}
                </p>
                <ul className="text-xs text-blue-700 space-y-1 list-none">
                  <li>• {t('storage.autoBid.botWillBidForYouAutomaticallyWhenOutbid')}</li>
                  <li>• {t('storage.autoBid.followsAuctionIncrement', { amount: formatCurrency(bidIncrement) })}</li>
                  <li>• {t('storage.autoBid.stopsWhenYourMaxBidIsReached')}</li>
                  <li>• {t('storage.autoBid.youOnlyPayTheMinimumNeededToWin')}</li>
                </ul>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsOpen(false)}
              data-testid="storage-autobid-cancel-btn"
            >
              {t('storage.autoBid.cancelBtn')}
            </Button>
            {isPremium && (
              <Button
                onClick={handleActivate}
                disabled={loading || !maxBid}
                className="bg-green-600 hover:bg-green-700 text-white"
                data-testid="storage-autobid-activate-btn"
              >
                {loading ? (
                  <>{t('storage.autoBid.processing')}</>
                ) : (
                  <>
                    <Bot className="h-4 w-4 mr-2" />
                    {t('storage.autoBid.activateBtn')}
                  </>
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default StorageAutoBidModal;
