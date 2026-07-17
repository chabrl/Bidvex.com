import API_BASE from '../../config';
import ErrorBoundary from '../../components/ErrorBoundary';
import React, { useEffect, useState, useCallback } from 'react';
import SafeImage from '../../components/SafeImage';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { authHeaders } from '../../utils/authToken';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import {
  Loader2, Gavel, MapPin, Clock, ShieldCheck, AlertTriangle, Info,
  CreditCard, Banknote, Send,
} from 'lucide-react';
import StorageCountdown from './StorageCountdown';
import StorageFooterBanner from './StorageFooterBanner';
import StorageAutoBidModal from '../../components/StorageAutoBidModal';
import QuickBidButtons from '../../components/QuickBidButtons';
import StorageDepositBanner from './StorageDepositBanner';
import AuctionStatusBadge, { CountdownTimer } from '../../components/AuctionStatusBadge';
import ListingPromotionModal from '../../components/ListingPromotionModal';
// Phase 6.3 — new bidding suite components
// iter285 — `StorageBiddingPanel` was a duplicate bid widget below the
// Quick-Bid panel and confused buyers. Import removed alongside its render.
import StorageAuctionClock from '../../components/storage/StorageAuctionClock';
import ListingJsonLd from '../../components/seo/ListingJsonLd';
import SEO from '../../components/SEO';
import WatchlistButton from '../../components/WatchlistButton';
import { useMetaPixelTracking } from '../../hooks/useMetaPixelTracking';
import { TrendingUp } from 'lucide-react';
import { LangLink } from '../../components/LangLink';

const API = API_BASE;

const StorageAuctionDetail = () => {
  const { id } = useParams();
  const { token, user } = useAuth();
  // iter230 — centralized Meta Pixel tracking hook
  const { trackViewContent, trackAddToCart, trackBidSubmitted } =
    useMetaPixelTracking({ routeHint: 'storage' });
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');

  const [auction, setAuction] = useState(null);
  const [history, setHistory] = useState([]);
  const [pricing, setPricing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activePhoto, setActivePhoto] = useState(0);
  const [maxBid, setMaxBid] = useState('');
  const [submittingBid, setSubmittingBid] = useState(false);
  const [depositPaid, setDepositPaid] = useState(false);
  const [showPromoModal, setShowPromoModal] = useState(false);
  // Phase 6.3 — track the timestamp of the most recent soft-close extension
  // so the clock can flash a "+2 min added" banner for 8 seconds.
  const [lastExtendedAt, setLastExtendedAt] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [a, h, p] = await Promise.all([
        axios.get(`${API}/storage-auctions/${id}`),
        axios.get(`${API}/storage-auctions/${id}/bids`),
        axios.get(`${API}/storage-auctions/${id}/pricing?payment_method=stripe`),
      ]);
      setAuction(a.data);
      setHistory(h.data?.bids || []);
      setPricing(p.data);
      // Meta Pixel ViewContent — dedupe-safe per (listing, session).
      trackViewContent({ listing: a.data });
    } catch (err) {
      toast.error(t('storage.detail.auctionNotFound'));
    } finally {
      setLoading(false);
    }
  }, [id, isFr]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Refresh every 15s for live bid updates
  useEffect(() => {
    const t = setInterval(fetchData, 15000);
    return () => clearInterval(t);
  }, [fetchData]);

  const handlePlaceBid = async (overrideAmount) => {
    const amt = parseFloat(overrideAmount ?? maxBid);
    if (!Number.isFinite(amt) || amt <= 0) {
      toast.error(t('storage.detail.enterAValidMaxBid'));
      return;
    }
    if (!token) {
      toast.error(t('storage.detail.signInToPlaceABid'));
      return;
    }
    // Meta Pixel AddToCart — bid intent (dedupe-safe per session).
    trackAddToCart({ listing: auction || { id, listing_type: 'storage' }, bidAmount: amt });
    setSubmittingBid(true);
    try {
      const res = await axios.post(
        `${API}/storage-auctions/${id}/bid`,
        { max_bid: amt },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(
        res.data.you_are_winning
          ? (isFr ? `Vous êtes en tête à ${res.data.current_bid} $` : `You are winning at $${res.data.current_bid}`)
          : (t('storage.detail.bidPlacedYouVeBeenOutbidByAnExistingProx'))
      );
      // Meta Pixel InitiateCheckout — every successful bid commit.
      trackBidSubmitted({ listing: auction || { id, listing_type: 'storage' }, bidAmount: amt });
      if (res.data.soft_close_extended) {
        toast.info(t('storage.detail.auctionExtendedBy2MinutesSoftClose'));
        // Phase 6.3 — trigger the clock's flash banner.
        setLastExtendedAt(new Date().toISOString());
      }
      // iter179 FIX 4: update current bid IMMEDIATELY from the server response
      // so the displayed price doesn't lag behind the bid history.
      setAuction((prev) => prev ? ({
        ...prev,
        current_bid: res.data.current_bid ?? prev.current_bid,
        bid_count: (prev.bid_count || 0) + 1,
        end_time: res.data.end_time || prev.end_time,
      }) : prev);
      setMaxBid('');
      fetchData();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'object' ? (isFr ? detail.message_fr : detail.message_en) : (detail || 'Bid failed');
      toast.error(msg);
    } finally {
      setSubmittingBid(false);
    }
  };

  if (loading) return <div className="min-h-screen flex justify-center items-center"><Loader2 className="h-10 w-10 animate-spin text-blue-600" /></div>;
  if (!auction) return null;

  const photos = auction.photos || [];
  const minNext = (auction.current_bid || 0) + (auction.bid_increment || 10);
  const now = new Date();
  const startTime = auction.start_time ? new Date(auction.start_time) : null;
  const endTime = auction.end_time ? new Date(auction.end_time) : null;
  const isUpcoming = auction.status === 'upcoming' || (startTime && startTime > now);
  const isLive = !isUpcoming && auction.status === 'active' && (!endTime || endTime > now);
  const needsDeposit = !!auction.deposit_required && Number(auction.deposit_amount || 0) > 0 && !depositPaid;
  const facility = auction.facility || {};

  return (
    <div className="min-h-screen bg-sky-50 dark:bg-slate-900 py-6" data-testid="storage-auction-detail">
      <SEO
        title={auction.title || (auction.unit_number ? `Storage Auction ${auction.unit_number}` : 'Storage Unit Auction')}
        description={(auction.description || 'Bid on this storage unit auction — live on BidVex, no buyer fees.').slice(0, 155)}
        path={`/storage-auctions/${auction.id}`}
        type="product"
        image={(Array.isArray(auction.images) && auction.images[0]) || '/bidvex-og.png'}
      />
      <ListingJsonLd listing={auction} canonicalUrl={`https://bidvex.com/storage-auctions/${auction.id}`} />
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <LangLink to="/storage-auctions/browse" className="text-sm text-blue-600 hover:underline">
          ← {t('storage.detail.backToAuctions')}
        </LangLink>

        {/* Facility-owner-only "Boost Your Auction" CTA */}
        {user && (auction.facility_owner_id === user.id || user.role === 'admin' || user.role === 'super_admin') && auction.status !== 'ended' && (
          <div className="mt-3">
            <Button
              type="button"
              data-testid="boost-storage-auction-btn"
              onClick={() => setShowPromoModal(true)}
              className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              {t('storage.detail.boostYourAuction')}
            </Button>
            {auction.is_promoted && (
              <Badge className="ml-3 bg-amber-100 text-amber-800 border border-amber-300">
                {t('storage.detail.featured')} — {auction.promotion_tier}
              </Badge>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6 mt-4">
          {/* LEFT — gallery + details */}
          <div className="space-y-4">
            {/* Photo gallery */}
            <Card className="overflow-hidden">
              <div className="relative bg-slate-200 dark:bg-slate-800 h-80 flex items-center justify-center">
                {photos.length > 0 ? (
                  <SafeImage src={photos[activePhoto]} alt={`Unit ${auction.unit_number}`} className="w-full h-full object-contain" />
                ) : (
                  <span className="text-7xl opacity-50">🔒</span>
                )}
              </div>
              {photos.length > 1 && (
                <div className="flex gap-2 p-3 overflow-x-auto">
                  {photos.map((p, i) => (
                    <button
                      key={i}
                      onClick={() => setActivePhoto(i)}
                      className={`w-16 h-16 rounded-md overflow-hidden border-2 shrink-0 ${i === activePhoto ? 'border-blue-600' : 'border-transparent'}`}
                    >
                      <SafeImage src={p} alt="" className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </Card>

            {auction.video_url && (
              <Card className="p-4">
                <p className="font-semibold mb-2">{t('storage.detail.unitVideo')}</p>
                <video src={auction.video_url} controls className="w-full rounded-lg" />
              </Card>
            )}

            {/* Unit details */}
            <Card className="p-5">
              <div className="flex items-start justify-between gap-3">
                <h1 className="text-2xl font-bold mb-2">
                  Unit #{auction.unit_number} — {auction.unit_size}
                </h1>
                {/* iter343 BUG-5 — storage auctions are watchable */}
                <WatchlistButton itemId={auction.id} itemType="storage" size="default" />
              </div>
              <div className="flex flex-wrap gap-2 mb-3">
                <Badge variant="outline" className="capitalize">{(auction.unit_type || '').replace(/_/g, ' ')}</Badge>
                {auction.is_lien_unit && (
                  <Badge variant="outline" className="border-amber-400 text-amber-700 bg-amber-50">
                    {t('storage.detail.lienUnit')}
                  </Badge>
                )}
                <Badge variant="outline">📍 {auction.facility_city}, {auction.facility_province}</Badge>
              </div>
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <p>{isFr ? auction.description_fr : auction.description_en}</p>
              </div>
              {auction.is_lien_unit && (
                <div className="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/40 text-xs">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-amber-900 dark:text-amber-200 mb-1">⚠️ {t('storage.detail.lienNoticeTitle')}</p>
                      <p className="text-amber-900 dark:text-amber-200">{t('storage.detail.lienNoticeBody')}</p>
                    </div>
                  </div>
                </div>
              )}
            </Card>

            {/* Facility info */}
            <Card className="p-5">
              <h3 className="font-semibold flex items-center gap-2 mb-2">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                {facility.company_name || auction.facility_name}
                {facility.verified && (
                  <Badge className="bg-emerald-600 text-white text-[10px]">✓ {t('storage.detail.verified')}</Badge>
                )}
              </h3>
              <p className="text-sm text-muted-foreground flex items-center gap-1">
                <MapPin className="h-3 w-3" /> {auction.facility_city}, {auction.facility_province}
              </p>
            </Card>

            {/* Bid history */}
            <Card className="p-5">
              <h3 className="font-semibold mb-3">{t('storage.detail.bidHistory')} ({history.length})</h3>
              {history.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">{t('storage.detail.noBidsYet')}</p>
              ) : (
                <div className="divide-y">
                  {history.slice().reverse().map((b, i) => (
                    <div key={i} className="flex justify-between text-sm py-2">
                      <span className="text-muted-foreground">{b.bidder_label}</span>
                      <span className="font-mono font-bold">${Number(b.amount).toFixed(2)}</span>
                      <span className="text-xs text-muted-foreground">{new Date(b.placed_at).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* RIGHT — sticky bid box */}
          <aside className="lg:sticky lg:top-4 self-start space-y-4">
            <Card className="p-5">
              <div className="mb-3">
                <AuctionStatusBadge
                  status={auction.status}
                  startTime={auction.start_time}
                  endTime={auction.end_time}
                />
              </div>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">{t('storage.detail.currentBid2')}</p>
              <p className="text-4xl font-black text-blue-600 mb-1" data-testid="current-bid-display">
                ${Number(auction.current_bid || 0).toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground mb-3">
                {auction.bid_count || 0} {t('storage.detail.bids')}
              </p>

              <div className="bg-slate-50 dark:bg-slate-900/50 rounded-lg p-3 mb-4">
                {/* Phase 6.3 Task 2 — Live clock with 4 visual states + soft-close flash banner */}
                <StorageAuctionClock
                  endTime={auction.end_time}
                  extendedAt={lastExtendedAt}
                  extensionMinutes={auction.soft_close_extension_minutes || 2}
                />
              </div>

              {auction.soft_close_enabled && (
                <div className="text-[11px] bg-blue-50 dark:bg-blue-950/30 text-blue-800 dark:text-blue-300 p-2.5 rounded-md border border-blue-100 dark:border-blue-900/40 mb-4 flex items-start gap-1.5">
                  <Info className="h-3 w-3 mt-0.5 shrink-0" />
                  <span>{t('storage.detail.aBidInTheFinal2MinutesExtendsTheAuctionB')}</span>
                </div>
              )}

              {/* Deposit banner (FIX 1) — block bidding until deposit is held */}
              {isLive && auction.deposit_required && (
                <StorageDepositBanner
                  auction={auction}
                  onStatusChange={setDepositPaid}
                />
              )}

              {/* Upcoming state (FIX 4) — show countdown, disable bid button */}
              {isUpcoming && (
                <div
                  data-testid="storage-upcoming-banner"
                  className="text-center py-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-200 dark:border-blue-800 mb-4"
                >
                  <p className="font-bold text-blue-700 dark:text-blue-300 mb-1">
                    {t('storage.detail.auctionStartsIn')}
                  </p>
                  <p className="text-blue-600 dark:text-blue-400 text-xs italic mb-2">
                    {t('storage.detail.lEnchReCommenceDans')}
                  </p>
                  <CountdownTimer targetTime={auction.start_time} testId="storage-upcoming-countdown" />
                  <button
                    disabled
                    className="w-full mt-3 bg-gray-300 text-gray-500 cursor-not-allowed font-bold py-3 rounded-xl"
                    data-testid="storage-bid-disabled-upcoming"
                  >
                    {t('storage.detail.biddingNotYetOpenEnchResPasEncoreOuverte')}
                  </button>
                </div>
              )}

              {isLive && !needsDeposit && (
                <>
                  {/* Phase 6.2 Task 3 — Storage Auction deposit pre-auth notice.
                      Always visible on the bid panel so buyers know that
                      placing a bid creates a Stripe hold for the cleanout
                      security deposit. */}
                  <div
                    className="mb-3 rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-700 p-3 text-xs leading-snug"
                    data-testid="storage-bid-deposit-notice"
                  >
                    <p className="font-semibold text-amber-900 dark:text-amber-200 mb-1">
                      ⚠️ {t('storage.detail.depositAuthTitle', 'Storage Auction Terms')}
                    </p>
                    <p className="text-amber-800 dark:text-amber-300">
                      {t('storage.detail.depositAuthBody', {
                        defaultValue:
                          'Placing a bid requires an immediate pre-authorization hold of ${{amount}} CAD on your registered payment method. This hold is automatically released if you do not win, or held secure until full unit cleanout verification if you win.',
                        amount: Number(auction?.security_deposit_amount || auction?.storage_metadata?.security_deposit_amount || 100).toFixed(2),
                      })}
                    </p>
                  </div>

                  {/* Quick Bid pills (iter175) — one-tap +$X / +$Y / +$Z scaled by bid_increment */}
                  <div className="mb-3">
                    <QuickBidButtons
                      currentBid={auction.current_bid || 0}
                      bidIncrement={auction.bid_increment || 10}
                      loading={submittingBid}
                      onConfirm={async (amount) => {
                        setMaxBid(String(amount));
                        await new Promise(r => setTimeout(r, 30));
                        await handlePlaceBid(amount);
                      }}
                      testidPrefix="storage-quick-bid"
                    />
                  </div>

                  <label className="text-xs font-medium mb-1 block">
                    {t('storage.detail.yourBidVotreOffre')} (≥ ${minNext.toFixed(2)})
                  </label>
                  <div className="flex gap-2">
                    <Input
                      type="number"
                      inputMode="decimal"
                      min={minNext}
                      step={auction.bid_increment || 10}
                      value={maxBid}
                      onChange={e => setMaxBid(e.target.value)}
                      placeholder={`${minNext.toFixed(2)}`}
                      data-testid="max-bid-input"
                    />
                    <Button
                      onClick={async () => {
                        // Phase 6.2 Task 3 — Verify card-on-file before
                        // dispatching the bid. Block + prompt registration
                        // if none found.
                        try {
                          const apiBase = process.env.REACT_APP_BACKEND_URL || '';
                          const resp = await fetch(`${apiBase}/api/payment-methods`, {
                            credentials: 'include',
                            headers: authHeaders(),
                          });
                          if (resp.ok) {
                            const data = await resp.json();
                            const methods = Array.isArray(data) ? data : (data?.payment_methods || data?.cards || []);
                            if (!methods || methods.length === 0) {
                              if (typeof window !== 'undefined') {
                                window.alert(t('storage.detail.noCardOnFile', 'Please register a payment method before placing a storage auction bid.'));
                                window.location.href = '/payment-methods?return_to=' + encodeURIComponent(window.location.pathname);
                              }
                              return;
                            }
                          }
                        } catch (cardCheckErr) {
                          console.debug('[storage] card-on-file check failed (continuing):', cardCheckErr);
                        }
                        await handlePlaceBid();
                      }}
                      disabled={submittingBid}
                      className="bg-blue-600 hover:bg-blue-700 text-white"
                      data-testid="place-bid-btn"
                    >
                      {submittingBid ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Gavel className="h-4 w-4 mr-1" /> {t('storage.detail.bidEnchRir')}</>}
                    </Button>
                  </div>

                  {/* Setup Auto-Bid (mirrors marketplace) — purple Premium badge gates non-premium tiers */}
                  <div className="mt-3">
                    <StorageAutoBidModal
                      auctionId={auction.id}
                      currentBid={auction.current_bid || 0}
                      bidIncrement={auction.bid_increment || 10}
                      onActivated={() => { setMaxBid(''); fetchData(); }}
                    />
                  </div>
                </>
              )}
            </Card>

            {/* No buyer fees notice */}
            <Card className="p-4 bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/40">
              <p className="text-sm font-bold text-emerald-800 dark:text-emerald-200 mb-1">
                ✅ {t('storage.detail.noBuyerFees')}
              </p>
              <p className="text-xs text-emerald-800 dark:text-emerald-300">
                {t('storage.detail.bidvexChargesZeroFeesYouOnlyPayTheWinnin')}
              </p>
            </Card>

            {/* Payment methods */}
            <Card className="p-4">
              <p className="text-xs font-semibold mb-2 uppercase tracking-wider">{t('storage.detail.paymentMethodsAccepted')}</p>
              <div className="flex flex-wrap gap-2 text-xs">
                {(auction.payment_methods_accepted || []).includes('stripe') && (
                  <Badge variant="outline"><CreditCard className="h-3 w-3 mr-1" />Stripe</Badge>
                )}
                {(auction.payment_methods_accepted || []).includes('cash') && (
                  <Badge variant="outline"><Banknote className="h-3 w-3 mr-1" />{t('storage.detail.cash')}</Badge>
                )}
                {(auction.payment_methods_accepted || []).includes('etransfer') && (
                  <Badge variant="outline"><Send className="h-3 w-3 mr-1" />E-Transfer</Badge>
                )}
              </div>
              {pricing && (
                <p className="text-[10px] text-muted-foreground mt-2">
                  {t('storage.detail.ifStripe29030ProcessingFeeAddedOnTop')}
                </p>
              )}
            </Card>

            <div className="text-[10px] text-center text-muted-foreground">
              <LangLink to="/storage-auctions/terms" className="underline">{t('storage.detail.terms')}</LangLink>
              {' • '}
              <LangLink to="/storage-auctions/how-it-works" className="underline">{t('storage.detail.howItWorks')}</LangLink>
            </div>

            {/* iter285 — Duplicate `<StorageBiddingPanel>` removed. The
                Quick-Bid panel above (lines 360-432) is the canonical
                bid UI; rendering both confused buyers (the slider duplicate
                appeared empty by default, blocking submission). */}
          </aside>
        </div>
      </div>
      <StorageFooterBanner />

      {showPromoModal && (
        <ListingPromotionModal
          listingId={auction.id}
          listingTitle={`${t('storage.detail.unit')} ${auction.unit_number || ''}`.trim() || (auction.facility_name || 'Storage Auction')}
          listingType="storage"
          onClose={() => setShowPromoModal(false)}
        />
      )}
    </div>
  );
};

export default function StorageAuctionDetailWithErrorBoundary(props) {
  return (
    <ErrorBoundary scope="storage-auction-detail">
      <StorageAuctionDetail {...props} />
    </ErrorBoundary>
  );
}
