import API_BASE from '../config';
import React, { useState, useEffect, useRef } from 'react';
import SafeImage from '../components/SafeImage';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { formatCurrency } from '../utils/currencyFormatter';
// iter233 — Display-only "Lot price × Quantity" multiplier helper.
import { computeDisplayPrice } from '../utils/priceUtils';
import { 
  Package, Clock, MapPin, User, Calendar, 
  ArrowLeft, Gavel, AlertCircle, TrendingUp,
  Grid as GridIcon, List as ListIcon, Menu, X, Flame, Heart, Info,
  Zap, ShoppingCart, Loader2, Truck, Building2, Shield, DollarSign,
  Scale, Wrench, HardHat, CheckCircle, XCircle, FileText,
  CreditCard, Banknote, Send
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import Countdown from 'react-countdown';
import Lightbox from 'react-image-lightbox';
import 'react-image-lightbox/style.css';
import AutoBidModal from '../components/AutoBidModal';
import SubscriptionBadge from '../components/SubscriptionBadge';
import SellerTierBadge from '../components/SellerTierBadge';
import WishlistHeartButton from '../components/WishlistHeartButton';
import AuctioneerInfo from '../components/AuctioneerInfo';
import WatchlistButton from '../components/WatchlistButton';
import ShareButton from '../components/ShareButton';
import MessageSellerModal from '../components/MessageSellerModal';
import BidErrorGuide from '../components/BidErrorGuide';
import VerificationRequiredModal from '../components/VerificationRequiredModal';
import PrivateSaleBadge, { BusinessSellerBadge, SellerAccountBadge } from '../components/PrivateSaleBadge';
import PublicBidHistory from '../components/PublicBidHistory';
import ListingJsonLd from '../components/seo/ListingJsonLd';
import SEO from '../components/SEO';
import { useMetaPixelTracking } from '../hooks/useMetaPixelTracking';
import ListingPromotionModal from '../components/ListingPromotionModal';
import { HighStakesIndicator, HighStakesTimer, getHighStakesCardStyles, isHighStakes } from '../components/HighStakesBidCard';
import { TrustScoreDisplay, TrustBadge } from '../components/SellerTrustScore';
import { SellerReputationCard, SellerReviewsList } from '../components/SellerReputation';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '../components/ui/sheet';
import { extractErrorMessage } from '../utils/errorHandler';
import { useCurrency } from '../contexts/CurrencyContext';
import { getLocalized, getBuyerPremiumText } from '../utils/localization';
import { LangLink } from '../components/LangLink';
// iter367 P1 — Multi-lot page redesign: live activity ticker + bid
// increment table + grid sort controls.
import MultiLotActivityTicker from '../components/MultiLotActivityTicker';
import BidIncrementTable from '../components/BidIncrementTable';
// iter368 — Compact lot card replaces the legacy 500-line inline card.
import CompactLotCard from '../components/CompactLotCard';

const API = API_BASE;

const MultiItemListingDetailPage = () => {
  const { id } = useParams();
  // iter367 P0 — Read ?lot= query param so item-card deep-links open
  // the correct lot (previously they landed on the parent auction).
  const [searchParams] = useSearchParams();
  const targetLotParam = searchParams.get('lot');
  const { user } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { formatPrice, currency } = useCurrency();
  // iter230 — centralized Meta Pixel tracking hook
  const { trackViewContent, trackAddToCart, trackBidSubmitted } =
    useMetaPixelTracking({ routeHint: 'multi_lot' });
  const [listing, setListing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bidAmounts, setBidAmounts] = useState({});
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('lotViewMode') || 'grid');
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxImages, setLightboxImages] = useState([]);
  const [photoIndex, setPhotoIndex] = useState(0);
  const [showLotIndex, setShowLotIndex] = useState(false);
  const [activeLotId, setActiveLotId] = useState(null);
  const [incrementInfo, setIncrementInfo] = useState(null);
  const [messageModalOpen, setMessageModalOpen] = useState(false);
  const [showPromoModal, setShowPromoModal] = useState(false);
  const [ratingModalOpen, setRatingModalOpen] = useState(false);
  const [autoBidModalOpen, setAutoBidModalOpen] = useState(false);
  const [selectedLot, setSelectedLot] = useState(null);
  const [showFullTerms, setShowFullTerms] = useState(false);
  const [buyNowLoading, setBuyNowLoading] = useState({});
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [paymentModalLot, setPaymentModalLot] = useState(null);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState('stripe');
  const [verificationModalOpen, setVerificationModalOpen] = useState(false);
  const [verificationAction, setVerificationAction] = useState('bid');
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [termsAcceptedPersistent, setTermsAcceptedPersistent] = useState(false);
  const [sellerInfo, setSellerInfo] = useState(null);
  const [showBidHistory, setShowBidHistory] = useState(false);
  // iter367 P1 — Lot sorting for the redesigned grid.
  const [lotSort, setLotSort] = useState('ending_soonest'); // ending_soonest | most_bids | highest_price | lowest_price | newest
  const [descriptionExpanded, setDescriptionExpanded] = useState(false);
  // iter368 — Compact-card auto-bid entry point (opens legacy modal).
  const [autoBidLot, setAutoBidLot] = useState(null);
  const lotRefs = useRef({});

  // Check if user has already accepted terms for this auction
  useEffect(() => {
    const checkTermsStatus = async () => {
      if (user && id) {
        try {
          const response = await axios.get(`${API}/multi-item-listings/${id}/terms-status`, {
            headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
          });
          if (response.data.has_accepted) {
            setAgreedToTerms(true);
            setTermsAcceptedPersistent(true);
          }
        } catch (error) {
          // Silently fail - user hasn't accepted yet
        }
      }
    };
    checkTermsStatus();
  }, [user, id]);

  // Function to accept terms and persist to database
  const acceptAuctionTerms = async () => {
    if (!user) return;
    try {
      await axios.post(`${API}/multi-item-listings/${id}/accept-terms`, {}, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });
      setAgreedToTerms(true);
      setTermsAcceptedPersistent(true);
      toast.success('Terms accepted for this auction');
    } catch (error) {
      toast.error('Failed to save terms acceptance');
    }
  };

  useEffect(() => {
    fetchListing();
    fetchIncrementInfo();
  }, [id]);

  const fetchIncrementInfo = async () => {
    try {
      const response = await axios.get(`${API}/multi-item-listings/${id}/increment-info`);
      setIncrementInfo(response.data);
    } catch (error) {
      console.error('Failed to fetch increment info:', error);
    }
  };

  const getMinimumIncrement = (currentBid) => {
    // iter368 — Walk the server-supplied schedule instead of hardcoding
    // tier boundaries client-side. This guarantees the Quick Bid, the
    // increment table, and the placement guard rail all use the exact
    // same ladder the backend enforces at /place-bid.
    if (!incrementInfo) return 5;
    if (incrementInfo.increment_option === 'fixed' && incrementInfo.fixed_increment) {
      return Number(incrementInfo.fixed_increment);
    }
    const schedule = incrementInfo.schedule || [];
    const bid = Number(currentBid || 0);
    for (const row of schedule) {
      const lo = Number(row.min ?? 0);
      const hi = row.max == null ? Infinity : Number(row.max);
      // Boundaries are half-open [lo, hi): matches server calculators.
      if (bid >= lo && bid < hi) return Number(row.step);
    }
    // If the bid exceeds the top tier's range or the schedule is empty,
    // fall back to the highest tier's step (or a conservative default).
    if (schedule.length > 0) return Number(schedule[schedule.length - 1].step);
    return 5;
  };

  useEffect(() => {
    const handleScroll = () => {
      if (!listing) return;
      
      // Find which lot is currently in view
      for (const lot of listing.lots) {
        const ref = lotRefs.current[lot.lot_number];
        if (ref) {
          const rect = ref.getBoundingClientRect();
          if (rect.top >= 0 && rect.top <= window.innerHeight / 2) {
            setActiveLotId(lot.lot_number);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [listing]);

  const fetchListing = async (retryCount = 0) => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/multi-item-listings/${id}`);
      
      // Sort lots by ending soonest first (High-Velocity ordering)
      if (response.data.lots && response.data.lots.length > 0) {
        const now = new Date();
        response.data.lots.sort((a, b) => {
          const endA = a.lot_end_time ? new Date(a.lot_end_time) : new Date('9999-12-31');
          const endB = b.lot_end_time ? new Date(b.lot_end_time) : new Date('9999-12-31');
          const endedA = endA <= now ? 1 : 0;
          const endedB = endB <= now ? 1 : 0;
          // Ended lots go last, then sort by end time ascending
          if (endedA !== endedB) return endedA - endedB;
          return endA - endB;
        });
      }
      
      setListing(response.data);
      if (response.data.lots.length > 0) {
        // iter367 P0 — Deep-link support: if ?lot=N is present, focus
        // that lot and scroll to it once refs are mounted. Otherwise
        // default to the first lot as before.
        // iter368 — On grid return, prefer the saved sessionStorage
        // snapshot (scrollY + sort + view mode) over a fresh scroll.
        let savedState = null;
        try {
          const raw = window.sessionStorage.getItem(`bidvex_grid_state:${id}`);
          if (raw) savedState = JSON.parse(raw);
        } catch { /* ignore */ }
        if (savedState) {
          if (savedState.lotSort) setLotSort(savedState.lotSort);
          if (savedState.viewMode) setViewMode(savedState.viewMode);
          if (typeof savedState.descriptionExpanded === 'boolean') setDescriptionExpanded(savedState.descriptionExpanded);
        }
        const targetLotNum = targetLotParam != null ? Number(targetLotParam) : null;
        const matched =
          (targetLotNum != null && response.data.lots.find(l => l.lot_number === targetLotNum)) ||
          response.data.lots[0];
        setActiveLotId(matched.lot_number);
        setSelectedLot(matched);
        // Scroll behaviour priority:
        //   (1) grid-return snapshot (sessionStorage) — takes precedence
        //       even when ?lot= is present, because the URL param is
        //       carried by "Back to grid" navigation but we want to
        //       restore scrollY, not re-scroll into the anchor.
        //   (2) explicit ?lot=N deep-link → smooth-scroll to that lot
        //   (3) default → let the page start at the top
        if (savedState && typeof savedState.scrollY === 'number') {
          // iter368 — the compact-card grid can be tall (dozens of 350 px
          // cards) but React may not have painted them all by the time we
          // fire the first scrollTo. Force-scroll multiple times with an
          // exponential back-off to defeat React Router's scroll-restore
          // + layout shifts from lazy images.
          const targetY = savedState.scrollY;
          let attempts = 0;
          const tick = () => {
            attempts += 1;
            window.scrollTo({ top: targetY, behavior: 'instant' });
            if (attempts >= 6) {
              try { window.sessionStorage.removeItem(`bidvex_grid_state:${id}`); } catch { /* ignore */ }
              return;
            }
            setTimeout(tick, 120 * attempts);
          };
          setTimeout(tick, 60);
        } else if (targetLotNum != null && matched.lot_number === targetLotNum) {
          setTimeout(() => {
            const ref = lotRefs.current[matched.lot_number];
            if (ref) ref.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 350);
        }
      }

      // Meta Pixel ViewContent — dedupe-safe per (listing, session).
      trackViewContent({ listing: response.data });

      // Fetch seller info for tax status badge
      if (response.data.seller_id) {
        try {
          const sellerRes = await axios.get(`${API}/users/${response.data.seller_id}/profile-summary`);
          setSellerInfo(sellerRes.data);
        } catch (e) {
          console.log('Could not fetch seller info for tax badge');
        }
      }
    } catch (error) {
      if (retryCount < 1) {
        console.warn(`Listing fetch failed, retrying in 2s (attempt ${retryCount + 1})...`);
        await new Promise(r => setTimeout(r, 2000));
        return fetchListing(retryCount + 1);
      }
      console.error('Failed to fetch listing:', error);
      toast.error('Failed to load listing');
      navigate('/lots');
    } finally {
      setLoading(false);
    }
  };

  const handleViewModeChange = (mode) => {
    setViewMode(mode);
    localStorage.setItem('lotViewMode', mode);
  };

  const openLightbox = (images, index) => {
    setLightboxImages(images);
    setPhotoIndex(index);
    setLightboxOpen(true);
  };

  const scrollToLot = (lotNumber) => {
    const ref = lotRefs.current[lotNumber];
    if (ref) {
      ref.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveLotId(lotNumber);
      // Set selectedLot for bid history display
      const lot = listing?.lots?.find(l => l.lot_number === lotNumber);
      if (lot) {
        setSelectedLot(lot);
      }
    }
    if (window.innerWidth < 768) {
      setShowLotIndex(false);
    }
  };

  const handleBidChange = (lotNumber, value) => {
    setBidAmounts({ ...bidAmounts, [lotNumber]: value });
  };

  const handlePlaceBid = async (lotNumber, bidType = 'normal') => {
    if (!user) {
      toast.error('Please sign in to place a bid');
      navigate('/auth');
      return;
    }

    // Check if user agreed to terms
    if ((listing.auction_terms_en || listing.auction_terms_fr) && !agreedToTerms) {
      toast.error(t('bid.mustAgreeToTerms', 'You must agree to the auction terms before placing a bid'));
      return;
    }

    const bidAmount = parseFloat(bidAmounts[lotNumber]);
    const lot = listing.lots.find(l => l.lot_number === lotNumber);

    if (!bidAmount || bidAmount <= lot.current_price) {
      toast.error(`Bid must be higher than current price of ${formatCurrency(lot.current_price)}`);
      return;
    }

    // Validate increment for normal bids
    if (bidType === 'normal') {
      const minIncrement = getMinimumIncrement(lot.current_price);
      const minimumBid = lot.current_price + minIncrement;
      
      if (bidAmount < minimumBid) {
        toast.error(`Minimum bid is ${formatCurrency(minimumBid)} (increment: ${formatCurrency(minIncrement)})`);
        return;
      }
    }

    // Meta Pixel AddToCart — bid intent (parent-scoped content_id matches catalog 1:1).
    trackAddToCart({ listing, bidAmount });

    try {
      await axios.post(
        `${API}/multi-item-listings/${id}/lots/${lotNumber}/bid`,
        { amount: bidAmount, bid_type: bidType },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      toast.success('Bid placed successfully!');
      // Meta Pixel InitiateCheckout — fires on every successful bid commit.
      // lotNumber is carried in `contents[]` while content_ids stay parent-scoped.
      trackBidSubmitted({ listing, bidAmount, lotNumber });
      fetchListing();
      setBidAmounts({ ...bidAmounts, [lotNumber]: '' });
    } catch (error) {
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to place bid');
    }
  };

  // Buy Now Handler — opens payment method selection modal
  const handleBuyNow = (lot) => {
    if (!user) {
      toast.error('Please login to purchase');
      navigate('/auth');
      return;
    }

    // Check verification requirements
    if (user.role !== 'admin' && (!user.phone_verified || !user.has_payment_method)) {
      setVerificationAction('bid');
      setVerificationModalOpen(true);
      return;
    }

    setPaymentModalLot(lot);
    setSelectedPaymentMethod('stripe');
    setPaymentModalOpen(true);
  };

  // Confirm Buy Now — executes the actual purchase
  const confirmBuyNow = async () => {
    if (!paymentModalLot) return;
    const lot = paymentModalLot;
    setPaymentModalOpen(false);
    setBuyNowLoading(prev => ({ ...prev, [lot.lot_number]: true }));
    
    try {
      const response = await axios.post(
        `${API}/buy-now`,
        {
          listing_id: id,
          lot_number: lot.lot_number,
          quantity: 1,
          payment_method: selectedPaymentMethod
        },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      
      const isOffline = selectedPaymentMethod === 'cash' || selectedPaymentMethod === 'etransfer';
      
      if (isOffline) {
        toast.success(
          selectedPaymentMethod === 'etransfer'
            ? `Order confirmed! E-Transfer instructions sent to your email.`
            : `Order confirmed! Please arrange pickup with the seller.`,
          { duration: 6000 }
        );
      } else {
        toast.success(`Congratulations! You purchased "${getLocalized(lot, 'title')}" for ${formatCurrency(lot.buy_now_price)}!`);
      }
      
      // Refresh listing to update lot status
      fetchListing();
      
      // Redirect to messages if handshake was created
      if (response.data.conversation_id) {
        toast.info('A chat with the seller has been created. Redirecting...');
        setTimeout(() => {
          navigate(`/messages?conversation=${response.data.conversation_id}`);
        }, 2000);
      }
    } catch (error) {
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to complete purchase');
    } finally {
      setBuyNowLoading(prev => ({ ...prev, [lot.lot_number]: false }));
      setPaymentModalLot(null);
    }
  };

  const isAuctionEnded = (endDate) => {
    return new Date(endDate) < new Date();
  };

  const hasActiveBids = (lot) => {
    return lot.current_price > lot.starting_price;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!listing) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-16 w-16 mx-auto text-red-500 mb-4" />
          <h2 className="text-2xl font-bold mb-2">{t('listingDetail.notFoundTitle', 'Listing Not Found')}</h2>
          <Button onClick={() => navigate('/lots')}>{t('listingDetail.backToLots', 'Back to Lots Marketplace')}</Button>
        </div>
      </div>
    );
  }

  const isPreviewMode = listing.status === 'upcoming';
  const auctionEnded = isAuctionEnded(listing.auction_end_date);
  const totalStartingValue = listing.lots.reduce((sum, lot) => sum + lot.starting_price, 0);
  const totalCurrentValue = listing.lots.reduce((sum, lot) => sum + lot.current_price, 0);
  const auctionStartDate = listing.auction_start_date ? new Date(listing.auction_start_date) : null;

  return (
    <div className="min-h-screen py-8 px-4">
      <SEO
        title={listing.title || 'Multi-Lot Auction'}
        description={(listing.description || `Bid on ${listing.title || 'this multi-lot auction'} — live lot auction on BidVex.`).slice(0, 155)}
        path={`/lots/${listing.id}`}
        type="product"
        image={(Array.isArray(listing.images) && listing.images[0]) || '/bidvex-og.png'}
      />
      <ListingJsonLd listing={listing} canonicalUrl={`https://bidvex.com/lots/${listing.id}`} />
      <div className="max-w-7xl mx-auto">
        {/* Preview Mode Banner */}
        {isPreviewMode && (
          <div className="mb-6 p-4 bg-amber-50 dark:bg-amber-950 border-2 border-amber-500 rounded-lg">
            <div className="flex items-center gap-3">
              <Clock className="h-6 w-6 text-amber-600 dark:text-amber-400" />
              <div className="flex-1">
                <h3 className="font-bold text-amber-900 dark:text-amber-100">
                  Preview Mode - Auction Not Yet Live
                </h3>
                <p className="text-sm text-amber-700 dark:text-amber-300">
                  Bidding opens in{' '}
                  {auctionStartDate && (
                    <Countdown 
                      date={auctionStartDate}
                      renderer={({ days, hours, minutes, completed }) => (
                        <span className="font-semibold">
                          {completed ? 'moments' : `${days}d ${hours}h ${minutes}m`}
                        </span>
                      )}
                    />
                  )}
                  . You can preview lots and favorite this auction.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-6">
          {/* Main Content */}
          <div className="flex-1">
            {/* Back Button */}
            <Button 
              variant="ghost" 
              onClick={() => navigate('/lots')}
              className="mb-4"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              {t('listingDetail.backToLots', 'Back to Lots Marketplace')}
            </Button>

            {/* Header Card */}
            <Card className="mb-8">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex gap-2 items-center mb-2 justify-between">
                      <div className="flex gap-2 items-center">
                        <Package className="h-6 w-6" style={{ color: '#2563eb' }} />
                        <Badge 
                          variant={isPreviewMode ? "secondary" : auctionEnded ? "secondary" : "default"}
                          className={`${isPreviewMode ? "bg-amber-500 text-white font-bold" : auctionEnded ? "bg-slate-500 text-white font-bold" : "bg-blue-600 text-white font-bold"} auction-status-badge`}
                          style={{ color: '#ffffff', fontWeight: 700 }}
                        >
                          {isPreviewMode
                            ? t('listingDetail.comingSoon', 'Coming Soon')
                            : auctionEnded
                              ? t('listingDetail.auctionEnded', 'Auction Ended')
                              : t('listingDetail.activeAuction', 'Active Auction')}
                        </Badge>
                        <Badge 
                          variant="outline" 
                          className="lots-count-badge font-bold text-slate-800 dark:text-slate-100 border-slate-400 dark:border-slate-500 bg-slate-100 dark:bg-slate-700"
                        >
                          {t('listingDetail.lotsCount', { count: listing.total_lots, defaultValue_one: '{{count}} Lot', defaultValue: '{{count}} Lots' })}
                        </Badge>
                      </div>
                      {user && (
                        <WishlistHeartButton
                          auctionId={listing.id}
                          size="large"
                          showCount={true}
                          wishlistCount={listing.wishlist_count || 0}
                        />
                      )}
                    </div>
                    <CardTitle className="text-3xl mb-4 text-slate-900 dark:text-white" style={{ fontWeight: 700 }}>{getLocalized(listing, 'title')}</CardTitle>
                    {/* iter367 P1 — Collapsible description (long copy no
                        longer pushes the lot grid below the fold). */}
                    {(() => {
                      const desc = getLocalized(listing, 'description') || '';
                      const shouldTruncate = desc.length > 260;
                      const visible = descriptionExpanded || !shouldTruncate ? desc : desc.slice(0, 260) + '…';
                      return (
                        <div className="mb-4 text-slate-600 dark:text-slate-300" data-testid="multi-lot-description">
                          <p className="whitespace-pre-wrap">{visible}</p>
                          {shouldTruncate && (
                            <button
                              type="button"
                              onClick={() => setDescriptionExpanded((v) => !v)}
                              className="text-cyan-600 dark:text-cyan-400 text-xs font-semibold uppercase tracking-wide mt-1 hover:underline"
                              data-testid="multi-lot-description-toggle"
                            >
                              {descriptionExpanded
                                ? t('common.showLess', 'Show less')
                                : t('common.readMore', 'Read more')}
                            </button>
                          )}
                        </div>
                      );
                    })()}

                    {/* iter217 — Seller-type badge (Partner / Dealer / Storage / Private Sale) */}
                    {(() => {
                      const acctType = listing?.seller_account_type
                        || (listing?.seller_is_partner ? 'partner'
                          : listing?.seller_is_vehicle_dealer ? 'vehicle_dealer'
                          : listing?.seller_is_storage_facility ? 'storage_facility'
                          : (sellerInfo?.is_tax_registered ? 'business' : 'individual'));
                      if (acctType === 'business') {
                        return <BusinessSellerBadge variant="default" className="mb-4" />;
                      }
                      return (
                        <SellerAccountBadge
                          accountType={acctType}
                          companyName={listing?.seller_partner_company_name}
                          className="mb-4"
                        />
                      );
                    })()}

                    {/* Auctioneer Info Section with Seller Tier Badge */}
                    {listing.seller_id && (
                      <div className="mb-6">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <p className="text-sm text-muted-foreground">{t('listingDetail.hostedBy', 'Hosted by')}</p>
                            {sellerInfo?.subscription_tier && (
                              <SellerTierBadge tier={sellerInfo.subscription_tier} size="small" />
                            )}
                          </div>
                          {user && user.id !== listing.seller_id && (
                            <Button
                              size="sm"
                              onClick={() => setMessageModalOpen(true)}
                              className="gap-2"
                            >
                              📨 {t('listingDetail.messageSeller', 'Message Seller')}
                            </Button>
                          )}
                        </div>
                        <AuctioneerInfo sellerId={listing.seller_id} variant="full" />
                        
                        {/* Seller Trust Score Display */}
                        <div className="mt-4">
                          <TrustScoreDisplay sellerId={listing.seller_id} variant="compact" showBadge={true} />
                        </div>

                        {/* Seller Reputation Breakdown */}
                        <div className="mt-4">
                          <SellerReputationCard sellerId={listing.seller_id} />
                        </div>

                        {/* Recent Reviews */}
                        <div className="mt-4">
                          <SellerReviewsList sellerId={listing.seller_id} />
                        </div>

                        {/* View all reviews link */}
                        <LangLink
                          to={`/store/${listing.seller_id}`}
                          className="block text-center text-sm font-medium text-cyan-600 dark:text-cyan-400 hover:underline mt-3"
                          data-testid="view-all-reviews-link"
                        >
                          {t('listingDetail.viewAllReviews', 'View all reviews')} &rarr;
                        </LangLink>

                        {/* iter189 Feature 2 — Lots Promote Button (owner-only, unpromoted only) */}
                        {user && user.id === listing.seller_id && !listing.is_promoted && (
                          <div className="mt-4 p-4 rounded-lg border-2 border-amber-200 dark:border-amber-800 bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/30" data-testid="promote-lots-section">
                            <div className="flex items-start gap-3">
                              <TrendingUp className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                              <div className="flex-1">
                                <h4 className="font-semibold text-sm text-amber-900 dark:text-amber-100 mb-1">
                                  {i18n.language === 'fr' ? 'Boostez votre vente aux enchères par lots' : 'Boost Your Lot Auction'}
                                </h4>
                                <p className="text-xs text-amber-800 dark:text-amber-200 mb-3">
                                  {i18n.language === 'fr'
                                    ? 'Augmentez la visibilité et attirez plus d’acheteurs potentiels sur tous vos lots.'
                                    : 'Increase visibility and reach more potential buyers across all your lots.'}
                                </p>
                                <Button
                                  size="sm"
                                  onClick={() => setShowPromoModal(true)}
                                  className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white border-0"
                                  data-testid="promote-lots-btn"
                                >
                                  <TrendingUp className="mr-2 h-4 w-4" />
                                  {i18n.language === 'fr' ? 'Promouvoir cette vente' : 'Promote This Auction'}
                                </Button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Documents Section */}
                    {listing.documents && (listing.documents.terms_conditions || listing.documents.important_info || listing.documents.catalogue) && (
                      <Card className="mb-6">
                        <CardHeader>
                          <CardTitle className="text-lg">📄 Documents</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                          {listing.documents.terms_conditions && (
                            <Button
                              variant="outline"
                              className="w-full justify-start"
                              onClick={() => {
                                const link = document.createElement('a');
                                link.href = `data:${listing.documents.terms_conditions.content_type};base64,${listing.documents.terms_conditions.base64_content}`;
                                link.download = listing.documents.terms_conditions.filename;
                                link.click();
                              }}
                            >
                              📃 Terms & Conditions
                            </Button>
                          )}
                          {listing.documents.important_info && (
                            <Button
                              variant="outline"
                              className="w-full justify-start"
                              onClick={() => {
                                const link = document.createElement('a');
                                link.href = `data:${listing.documents.important_info.content_type};base64,${listing.documents.important_info.base64_content}`;
                                link.download = listing.documents.important_info.filename;
                                link.click();
                              }}
                            >
                              ℹ️ Important Information
                            </Button>
                          )}
                          {listing.documents.catalogue && (
                            <Button
                              variant="outline"
                              className="w-full justify-start"
                              onClick={() => {
                                const link = document.createElement('a');
                                link.href = `data:${listing.documents.catalogue.content_type};base64,${listing.documents.catalogue.base64_content}`;
                                link.download = listing.documents.catalogue.filename;
                                link.click();
                              }}
                            >
                              📚 Catalogue
                            </Button>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* Shipping Section */}
                    {listing.shipping_info && listing.shipping_info.available && (
                      <Card className="mb-6">
                        <CardHeader>
                          <CardTitle className="text-lg">🚚 Shipping Options</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          {listing.shipping_info.methods && listing.shipping_info.methods.length > 0 && (
                            <div>
                              <p className="text-sm font-semibold mb-2">Available Methods:</p>
                              <div className="space-y-2">
                                {listing.shipping_info.methods.map(method => (
                                  <div key={method} className="flex justify-between items-center p-2 bg-muted rounded">
                                    <span className="capitalize">{method.replace('_', ' ')}</span>
                                    {listing.shipping_info.rates && listing.shipping_info.rates[method] && (
                                      <span className="font-semibold">${listing.shipping_info.rates[method]}</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {listing.shipping_info.delivery_time && (
                            <div>
                              <p className="text-sm font-semibold">Estimated Delivery:</p>
                              <p className="text-sm text-muted-foreground">{listing.shipping_info.delivery_time}</p>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* Visit Availability Section */}
                    {listing.visit_availability && listing.visit_availability.offered && (
                      <Card className="mb-6 border-green-200 bg-green-50 dark:bg-green-900/10">
                        <CardHeader>
                          <CardTitle className="text-lg flex items-center gap-2">
                            🏠 Visit Before Auction
                            <Badge variant="secondary" className="bg-green-500 text-white">Available</Badge>
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          {listing.visit_availability.dates && (
                            <div>
                              <p className="text-sm font-semibold">Available Dates:</p>
                              <p className="text-sm">{listing.visit_availability.dates}</p>
                            </div>
                          )}
                          {listing.visit_availability.instructions && (
                            <div>
                              <p className="text-sm font-semibold">Instructions:</p>
                              <p className="text-sm text-muted-foreground">{listing.visit_availability.instructions}</p>
                            </div>
                          )}
                          {user && user.id !== listing.seller_id && (
                            <Button
                              className="w-full gradient-button text-white"
                              onClick={() => setMessageModalOpen(true)}
                            >
                              📅 Request Visit
                            </Button>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* =========================================== */}
                    {/* SELLER OBLIGATIONS - PUBLIC DISPLAY */}
                    {/* =========================================== */}
                    
                    {/* 1. Financial & Refund Sidebar */}
                    {listing.seller_obligations && (
                      <Card className="mb-6 border-2 border-blue-200 dark:border-blue-700 bg-gradient-to-br from-blue-50 to-slate-50 dark:from-blue-900/20 dark:to-slate-900/20 shadow-lg">
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg flex items-center gap-2 text-blue-800 dark:text-blue-300">
                            <DollarSign className="h-5 w-5" />
                            Financial & Payment Terms
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          {/* Currency Exchange Rate */}
                          {listing.seller_obligations.custom_exchange_rate && (
                            <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-blue-200 dark:border-blue-700">
                              <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">Payment Basis</p>
                              <p className="text-lg font-bold text-blue-700 dark:text-blue-300">
                                1 USD = {listing.seller_obligations.custom_exchange_rate} CAD
                              </p>
                            </div>
                          )}

                          {/* Refund Status Badge */}
                          <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Refund Policy</span>
                            {listing.seller_obligations.refund_policy === 'non_refundable' ? (
                              <Badge className="bg-red-600 text-white border-0 font-bold px-3 py-1">
                                <XCircle className="h-3.5 w-3.5 mr-1" />
                                Final Sale - Non-Refundable
                              </Badge>
                            ) : (
                              <Badge className="bg-green-600 text-white border-0 font-bold px-3 py-1">
                                <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                Refundable (See Terms)
                              </Badge>
                            )}
                          </div>

                          {/* Removal Deadline */}
                          {listing.seller_obligations.removal_deadline_days && (
                            <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-300 dark:border-amber-700">
                              <div className="flex items-center gap-2">
                                <Calendar className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                                <div>
                                  <p className="text-xs text-amber-600 dark:text-amber-400 uppercase tracking-wider">Removal Deadline</p>
                                  <p className="font-bold text-amber-800 dark:text-amber-200">
                                    {listing.seller_obligations.removal_deadline_days} Days after auction close
                                  </p>
                                  {listing.seller_obligations.removal_deadline_custom && (
                                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                                      Note: {listing.seller_obligations.removal_deadline_custom}
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* 2. Logistics & Facility Infobox */}
                    {listing.seller_obligations && (
                      <Card className="mb-6 border-2 border-purple-200 dark:border-purple-700 bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 shadow-lg">
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg flex items-center gap-2 text-purple-800 dark:text-purple-300">
                            <Building2 className="h-5 w-5" />
                            Logistics & Facility
                          </CardTitle>
                          <p className="text-xs text-purple-600 dark:text-purple-400 mt-1">
                            📋 Official Site Capabilities Report
                          </p>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          {/* Facility Address */}
                          {listing.seller_obligations.facility_address && (
                            <div className="flex items-start gap-3 p-3 bg-white dark:bg-slate-800 rounded-lg border border-purple-200 dark:border-purple-700">
                              <MapPin className="h-5 w-5 text-purple-600 dark:text-purple-400 flex-shrink-0 mt-0.5" />
                              <div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">Pickup Location</p>
                                <p className="font-semibold text-slate-800 dark:text-slate-200">{listing.seller_obligations.facility_address}</p>
                              </div>
                            </div>
                          )}

                          {/* Site Capabilities Grid */}
                          <div className="grid grid-cols-2 gap-3">
                            {/* Overhead Crane */}
                            {listing.seller_obligations.has_overhead_crane && (
                              <div className="flex items-center gap-2 p-3 bg-green-100 dark:bg-green-900/30 rounded-lg border border-green-300 dark:border-green-700">
                                <span className="text-2xl">🏗️</span>
                                <div>
                                  <p className="font-semibold text-green-800 dark:text-green-300 text-sm">Overhead Crane</p>
                                  {listing.seller_obligations.crane_capacity && (
                                    <p className="text-xs text-green-600 dark:text-green-400">{listing.seller_obligations.crane_capacity} tons</p>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Loading Dock */}
                            {listing.seller_obligations.has_loading_dock && (
                              <div className="flex items-center gap-2 p-3 bg-green-100 dark:bg-green-900/30 rounded-lg border border-green-300 dark:border-green-700">
                                <span className="text-2xl">🚛</span>
                                <div>
                                  <p className="font-semibold text-green-800 dark:text-green-300 text-sm">Loading Dock</p>
                                  {listing.seller_obligations.loading_dock_type && (
                                    <p className="text-xs text-green-600 dark:text-green-400 capitalize">{listing.seller_obligations.loading_dock_type} dock</p>
                                  )}
                                </div>
                              </div>
                            )}

                            {/* Forklift */}
                            {listing.seller_obligations.has_forklift_available && (
                              <div className="flex items-center gap-2 p-3 bg-green-100 dark:bg-green-900/30 rounded-lg border border-green-300 dark:border-green-700">
                                <span className="text-2xl">🚜</span>
                                <p className="font-semibold text-green-800 dark:text-green-300 text-sm">Forklift Available</p>
                              </div>
                            )}

                            {/* Scale on Site */}
                            {listing.seller_obligations.has_scale_on_site && (
                              <div className="flex items-center gap-2 p-3 bg-green-100 dark:bg-green-900/30 rounded-lg border border-green-300 dark:border-green-700">
                                <span className="text-2xl">⚖️</span>
                                <p className="font-semibold text-green-800 dark:text-green-300 text-sm">Scale on Site</p>
                              </div>
                            )}

                            {/* Tailgate Access */}
                            {listing.seller_obligations.has_tailgate_access && (
                              <div className="flex items-center gap-2 p-3 bg-green-100 dark:bg-green-900/30 rounded-lg border border-green-300 dark:border-green-700">
                                <span className="text-2xl">🚛</span>
                                <p className="font-semibold text-green-800 dark:text-green-300 text-sm">Tailgate Access</p>
                              </div>
                            )}

                            {/* Ground Level Only */}
                            {listing.seller_obligations.ground_level_loading_only && (
                              <div className="flex items-center gap-2 p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg border border-blue-300 dark:border-blue-700">
                                <span className="text-2xl">📦</span>
                                <p className="font-semibold text-blue-800 dark:text-blue-300 text-sm">Ground Level Only</p>
                              </div>
                            )}
                          </div>

                          {/* PPE/Safety Requirements */}
                          {listing.seller_obligations.authorized_personnel_only && (
                            <div className="p-4 bg-amber-100 dark:bg-amber-900/30 rounded-lg border-2 border-amber-400 dark:border-amber-600">
                              <div className="flex items-center gap-2 mb-2">
                                <span className="text-2xl">🛡️</span>
                                <p className="font-bold text-amber-800 dark:text-amber-300">PPE/ID Required for Entry</p>
                              </div>
                              {listing.seller_obligations.safety_requirements && (
                                <p className="text-sm text-amber-700 dark:text-amber-400 ml-8">
                                  {listing.seller_obligations.safety_requirements}
                                </p>
                              )}
                            </div>
                          )}

                          {/* Warning: Tailgate Truck Required */}
                          {listing.seller_obligations.ground_level_loading_only && !listing.seller_obligations.has_loading_dock && (
                            <div className="p-3 bg-orange-100 dark:bg-orange-900/30 rounded-lg border-2 border-orange-400 dark:border-orange-600">
                              <p className="font-bold text-orange-700 dark:text-orange-300 flex items-center gap-2">
                                <AlertCircle className="h-5 w-5" />
                                ⚠️ Note: Requires Tailgate Truck for Pickup
                              </p>
                            </div>
                          )}

                          {/* Shipping/Rigging Status */}
                          <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                            <div className="flex items-center justify-between">
                              <span className="text-sm font-medium text-slate-700 dark:text-slate-300 flex items-center gap-2">
                                <Truck className="h-4 w-4" />
                                Seller Provides Shipping/Rigging
                              </span>
                              {listing.seller_obligations.provides_shipping === 'yes' ? (
                                <Badge className="bg-green-600 text-white border-0">Yes</Badge>
                              ) : (
                                <Badge className="bg-slate-500 text-white border-0">Buyer Pickup</Badge>
                              )}
                            </div>
                            {listing.seller_obligations.provides_shipping === 'yes' && listing.seller_obligations.shipping_details && (
                              <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 pl-6">
                                {listing.seller_obligations.shipping_details}
                              </p>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* 3. Shipping & Logistics Tab Content */}
                    {listing.seller_obligations && (listing.seller_obligations.additional_site_notes || listing.seller_obligations.shipping_details) && (
                      <Card className="mb-6 border-2 border-slate-200 dark:border-slate-700">
                        <CardHeader className="pb-3 bg-slate-50 dark:bg-slate-800/50">
                          <CardTitle className="text-lg flex items-center gap-2 text-slate-800 dark:text-slate-200">
                            <FileText className="h-5 w-5" />
                            Seller&apos;s Specific Terms
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4 pt-4">
                          {/* Additional Site Notes */}
                          {listing.seller_obligations.additional_site_notes && (
                            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-700">
                              <p className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">📝 Additional Site Notes:</p>
                              <p className="text-sm text-slate-700 dark:text-slate-300">
                                {listing.seller_obligations.additional_site_notes}
                              </p>
                            </div>
                          )}

                          {/* Rigging/Shipping Details */}
                          {listing.seller_obligations.provides_shipping === 'yes' && listing.seller_obligations.shipping_details && (
                            <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-700">
                              <p className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">🚚 Rigging/Shipping Details:</p>
                              <p className="text-sm text-slate-700 dark:text-slate-300">
                                Seller provides rigging: <strong>Yes</strong> - {listing.seller_obligations.shipping_details}
                              </p>
                            </div>
                          )}

                          {/* Refund Terms */}
                          {listing.seller_obligations.refund_policy === 'refundable' && listing.seller_obligations.refund_terms && (
                            <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-700">
                              <p className="text-sm font-semibold text-purple-800 dark:text-purple-300 mb-2">💰 Refund Terms:</p>
                              <p className="text-sm text-slate-700 dark:text-slate-300">
                                {listing.seller_obligations.refund_terms}
                              </p>
                            </div>
                          )}

                          {/* Legal Shield Disclaimer */}
                          <div className="p-4 bg-slate-100 dark:bg-slate-800 rounded-lg border-2 border-slate-300 dark:border-slate-600 mt-4">
                            <div className="flex items-start gap-3">
                              <Shield className="h-5 w-5 text-slate-600 dark:text-slate-400 flex-shrink-0 mt-0.5" />
                              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                                <strong>Bidder Agreement:</strong> By bidding on this item, you agree to the removal deadlines 
                                and facility requirements specified by the seller above. Failure to comply with pickup 
                                deadlines may result in storage fees or forfeiture of the item.
                              </p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Public Bid History - Transparency Feature */}
                    {selectedLot && (
                      <PublicBidHistory 
                        listingId={listing.id}
                        lotNumber={selectedLot.lot_number}
                        currentPrice={selectedLot.current_price}
                        sellerExchangeRate={listing.seller_obligations?.custom_exchange_rate}
                      />
                    )}

                    {/* Auction Terms & Conditions - Enhanced with Show More/Less and Agreement */}
                    {(listing.auction_terms_en || listing.auction_terms_fr) && (
                      <Card className="mb-6 border-2 border-primary/20">
                        <CardHeader>
                          <CardTitle className="text-lg flex items-center justify-between">
                            <span className="flex items-center gap-2">
                              📝 {t('auction.termsAndConditions', 'Terms & Conditions')}
                              <Badge variant="outline" className="text-xs">Required</Badge>
                            </span>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => window.open(`${API}/multi-item-listings/${listing.id}/terms/pdf`, '_blank')}
                            >
                              📄 {t('common.downloadPDF', 'Download PDF')}
                            </Button>
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          {listing.auction_terms_en && (
                            <div>
                              <p className="text-sm font-semibold mb-2">{t('auction.englishTerms', 'English Terms')}:</p>
                              <div className={`prose prose-sm max-w-none dark:prose-invert ${!showFullTerms ? 'max-h-32 overflow-hidden relative' : 'max-h-96 overflow-y-auto'} border rounded-lg p-4 bg-muted/30`}>
                                <div dangerouslySetInnerHTML={{ 
                                  __html: showFullTerms 
                                    ? listing.auction_terms_en 
                                    : (listing.auction_terms_en.substring(0, 300) + (listing.auction_terms_en.length > 300 ? '...' : ''))
                                }} />
                                {!showFullTerms && listing.auction_terms_en.length > 300 && (
                                  <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-muted/30 to-transparent" />
                                )}
                              </div>
                              {listing.auction_terms_en.length > 300 && (
                                <Button
                                  variant="link"
                                  size="sm"
                                  onClick={() => setShowFullTerms(!showFullTerms)}
                                  className="mt-2 text-primary"
                                >
                                  {showFullTerms ? t('common.showLess', 'Show Less') : t('common.showMore', 'Show More')} ▼
                                </Button>
                              )}
                            </div>
                          )}
                          {listing.auction_terms_fr && (
                            <div className="pt-4 border-t">
                              <p className="text-sm font-semibold mb-2">{t('auction.frenchTerms', 'Termes en Français')}:</p>
                              <div className={`prose prose-sm max-w-none dark:prose-invert ${!showFullTerms ? 'max-h-32 overflow-hidden relative' : 'max-h-96 overflow-y-auto'} border rounded-lg p-4 bg-muted/30`}>
                                <div dangerouslySetInnerHTML={{ 
                                  __html: showFullTerms 
                                    ? listing.auction_terms_fr 
                                    : (listing.auction_terms_fr.substring(0, 300) + (listing.auction_terms_fr.length > 300 ? '...' : ''))
                                }} />
                                {!showFullTerms && listing.auction_terms_fr.length > 300 && (
                                  <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-muted/30 to-transparent" />
                                )}
                              </div>
                            </div>
                          )}

                          {/* Agreement Checkbox - Persistent One-Time Click */}
                          <div className={`mt-6 p-4 rounded-lg border-2 ${
                            termsAcceptedPersistent 
                              ? 'bg-green-50 dark:bg-green-900/20 border-green-300 dark:border-green-700' 
                              : 'bg-primary/5 border-primary/20'
                          }`}>
                            {termsAcceptedPersistent ? (
                              <div className="flex items-center gap-3">
                                <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400" />
                                <div>
                                  <p className="text-sm font-semibold text-green-700 dark:text-green-300">
                                    ✅ Terms Accepted for This Auction
                                  </p>
                                  <p className="text-xs text-green-600 dark:text-green-400">
                                    You can bid on any lot in this auction without re-accepting terms.
                                  </p>
                                </div>
                              </div>
                            ) : (
                              <>
                                <label className="flex items-start gap-3 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={agreedToTerms}
                                    onChange={(e) => {
                                      setAgreedToTerms(e.target.checked);
                                      if (e.target.checked) {
                                        acceptAuctionTerms();
                                      }
                                    }}
                                    className="mt-1 h-5 w-5 rounded border-primary text-primary focus:ring-primary cursor-pointer"
                                  />
                                  <span className="text-sm font-medium leading-tight">
                                    {t('auction.agreeToTerms', "I have read and agree to the auction's Terms & Conditions")} *
                                  </span>
                                </label>
                                {!agreedToTerms && (
                                  <p className="text-xs text-muted-foreground mt-2 ml-8">
                                    ⚠️ {t('auction.mustAgreeBeforeBid', 'You must agree to the terms before placing a bid')}
                                  </p>
                                )}
                              </>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {(!listing.auction_terms_en && !listing.auction_terms_fr) && (
                      <Card className="mb-6">
                        <CardContent className="p-4 text-center text-muted-foreground">
                          <p>{t('auction.noTermsProvided', 'No terms provided by seller')}</p>
                        </CardContent>
                      </Card>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4" style={{ color: '#6b7280' }} />
                        <span style={{ color: '#374151' }}>{listing.city}, {listing.region}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Package className="h-4 w-4" style={{ color: '#6b7280' }} />
                        <span style={{ color: '#374151' }}>{listing.category}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4" style={{ color: '#6b7280' }} />
                        <span style={{ color: '#374151' }}>
                          {!auctionEnded ? (
                            <>
                              {t('listingDetail.endsIn', 'Ends in:')} <Countdown date={new Date(listing.auction_end_date)} />
                            </>
                          ) : (
                            t('listingDetail.auctionEnded', 'Auction Ended')
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 rounded-lg" style={{ backgroundColor: '#f1f5f9' }}>
                  <div className="text-center">
                    <p className="text-2xl font-bold" style={{ color: '#2563eb' }}>{listing.total_lots}</p>
                    <p className="text-sm" style={{ color: '#6b7280' }}>{t('listingDetail.totalLots', 'Total Lots')}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold" style={{ color: '#2563eb' }}>{formatCurrency(totalStartingValue)}</p>
                    <p className="text-sm" style={{ color: '#6b7280' }}>{t('listingDetail.totalStartingValue', 'Total Starting Value')}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold" style={{ color: '#16a34a' }}>{formatCurrency(totalCurrentValue)}</p>
                    <p className="text-sm" style={{ color: '#6b7280' }}>{t('listingDetail.currentTotalValue', 'Current Total Value')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* iter367 P1 — Redesign row: Live Activity Ticker + Bid
                Increment Table.  Sits above the lot grid so buyers see
                the freshest activity + know the exact next-bid amount. */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              <MultiLotActivityTicker
                auctionId={id}
                onLotClick={(lotNum) => scrollToLot(lotNum)}
              />
              <BidIncrementTable auctionId={id} defaultOpen={false} />
            </div>

            {/* View Mode Toggle + iter367 sort controls */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
              <h2 className="text-2xl font-bold" style={{ color: '#1a1a1a' }}>{t('listingDetail.availableLots', 'Available Lots')}</h2>
              <div className="flex flex-wrap items-center gap-2">
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 uppercase tracking-wide mr-1">
                  {t('listingDetail.sortBy', 'Sort:')}
                </label>
                <select
                  value={lotSort}
                  onChange={(e) => setLotSort(e.target.value)}
                  className="h-9 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 text-sm font-medium focus:ring-2 focus:ring-cyan-500 focus:outline-none"
                  data-testid="lot-sort-select"
                >
                  <option value="ending_soonest">{t('listingDetail.sort.endingSoonest', 'Ending soonest')}</option>
                  <option value="most_bids">{t('listingDetail.sort.mostBids', 'Most active')}</option>
                  <option value="highest_price">{t('listingDetail.sort.highest', 'Highest price')}</option>
                  <option value="lowest_price">{t('listingDetail.sort.lowest', 'Lowest price')}</option>
                  <option value="newest">{t('listingDetail.sort.newest', 'Newest')}</option>
                </select>
                <Button
                  variant={viewMode === 'grid' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleViewModeChange('grid')}
                  className={viewMode === 'grid' ? 'gradient-button text-white' : ''}
                  data-testid="lots-view-grid"
                >
                  <GridIcon className="h-4 w-4 mr-2" />
                  Grid
                </Button>
                <Button
                  variant={viewMode === 'list' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleViewModeChange('list')}
                  className={viewMode === 'list' ? 'gradient-button text-white' : ''}
                  data-testid="lots-view-list"
                >
                  <ListIcon className="h-4 w-4 mr-2" />
                  List
                </Button>
              </div>
            </div>

            {/* Lots Display — iter367 P1: sort with a stable comparator */}
            <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 gap-6' : 'space-y-6'}>
              {[...listing.lots].sort((a, b) => {
                const aEnd = a.lot_end_time ? new Date(a.lot_end_time).getTime() : Number.MAX_SAFE_INTEGER;
                const bEnd = b.lot_end_time ? new Date(b.lot_end_time).getTime() : Number.MAX_SAFE_INTEGER;
                const aBids = a.bid_count || 0;
                const bBids = b.bid_count || 0;
                const aPrice = Number(a.current_price ?? a.starting_price ?? 0);
                const bPrice = Number(b.current_price ?? b.starting_price ?? 0);
                switch (lotSort) {
                  case 'most_bids':      return bBids - aBids;
                  case 'highest_price':  return bPrice - aPrice;
                  case 'lowest_price':   return aPrice - bPrice;
                  case 'newest':         return (b.lot_number || 0) - (a.lot_number || 0);
                  case 'ending_soonest':
                  default:               return aEnd - bEnd;
                }
              }).map((lot) => (
                <CompactLotCard
                  key={lot.lot_number}
                  lot={lot}
                  auctionId={id}
                  listing={listing}
                  currentUserId={user?.id}
                  onOpenAutoBid={(l) => setAutoBidLot(l)}
                  onBuyNow={(l) => handleBuyNow(l)}
                  onNavigate={() => {
                    // iter368 — snapshot grid state so returning restores it exactly.
                    try {
                      window.sessionStorage.setItem(
                        `bidvex_grid_state:${id}`,
                        JSON.stringify({
                          scrollY: window.scrollY,
                          lotSort,
                          viewMode,
                          descriptionExpanded,
                        }),
                      );
                    } catch { /* ignore */ }
                  }}
                />
              ))}
            </div>

            {/* Location Info */}
            <Card className="mt-8">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MapPin className="h-5 w-5" />
                  Location & Pickup
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground mb-2">{listing.location}</p>
                <p className="text-sm text-muted-foreground">
                  {listing.city}, {listing.region}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Lot Index Sidebar (Desktop) */}
          <div className="hidden lg:block w-64 flex-shrink-0">
            <div className="sticky top-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">{t('listingDetail.lotIndex', 'Lot Index')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {listing.lots.map((lot) => (
                    <div
                      key={lot.lot_number}
                      onClick={() => scrollToLot(lot.lot_number)}
                      className={`p-3 rounded-lg cursor-pointer transition-all ${
                        activeLotId === lot.lot_number
                          ? 'bg-gradient-to-r from-[#009BFF] to-[#0056A6] text-white shadow-md'
                          : 'bg-muted hover:bg-muted/80'
                      }`}
                    >
                      <div className="flex items-start justify-between mb-1">
                        <p className="font-semibold text-sm">Lot #{lot.lot_number}</p>
                        {hasActiveBids(lot) && (
                          <Flame className="h-4 w-4 text-amber-400" />
                        )}
                      </div>
                      <p className="text-xs truncate mb-1">{getLocalized(lot, 'title')}</p>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span>Qty: {lot.quantity}</span>
                        <span className="font-semibold">{formatCurrency(lot.current_price)}</span>
                      </div>
                      {lot.lot_end_time && !auctionEnded && (
                        <div className="flex items-center gap-1 text-xs">
                          <Clock className="h-3 w-3" />
                          <Countdown 
                            date={new Date(lot.lot_end_time)}
                            renderer={({ hours, minutes, seconds, completed }) => (
                              completed ? <span className="text-red-400">Ended</span> : 
                              <span className="font-mono">{hours}h {minutes}m {seconds}s</span>
                            )}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>

      {/* Floating FAB (Mobile) - Uses Sheet for drawer */}
      <div className="lg:hidden fixed bottom-20 right-6 z-50">
        <Sheet open={showLotIndex} onOpenChange={setShowLotIndex}>
          <SheetTrigger asChild>
            <Button
              size="lg"
              className="gradient-button text-white border-0 shadow-lg rounded-full w-14 h-14 p-0 hover:scale-110 transition-transform duration-200"
              data-testid="mobile-lot-index-fab"
            >
              <Menu className="h-6 w-6" />
            </Button>
          </SheetTrigger>
          <SheetContent side="bottom" className="h-[70vh] rounded-t-2xl">
            <SheetHeader className="pb-4">
              <SheetTitle className="flex items-center gap-2">
                <Package className="h-5 w-5 text-primary" />
                Lot Index ({listing.lots.length} lots)
              </SheetTitle>
            </SheetHeader>
            <div className="overflow-y-auto space-y-2 pr-2" style={{ maxHeight: 'calc(70vh - 100px)' }}>
              {listing.lots.map((lot) => {
                const lotIsHighStakes = isHighStakes(lot.current_price);
                return (
                  <div
                    key={lot.lot_number}
                    onClick={() => {
                      scrollToLot(lot.lot_number);
                      setShowLotIndex(false);
                    }}
                    className={`p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                      activeLotId === lot.lot_number
                        ? 'bg-gradient-to-r from-[#009BFF] to-[#0056A6] text-white shadow-md'
                        : lotIsHighStakes 
                          ? 'bg-amber-50 dark:bg-amber-900/20 border-2 border-amber-400 hover:shadow-md'
                          : 'bg-muted hover:bg-muted/80 hover:shadow-sm'
                    }`}
                    data-testid={`mobile-lot-item-${lot.lot_number}`}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-sm">Lot #{lot.lot_number}</p>
                        {lotIsHighStakes && (
                          <Badge className="bg-gradient-to-r from-amber-500 to-red-500 text-white text-xs px-1.5 py-0">
                            HIGH STAKES
                          </Badge>
                        )}
                      </div>
                      {hasActiveBids(lot) && (
                        <Flame className={`h-4 w-4 ${activeLotId === lot.lot_number ? 'text-white' : 'text-amber-500'}`} />
                      )}
                    </div>
                    <p className="text-xs truncate mb-1">{getLocalized(lot, 'title')}</p>
                    <div className="flex items-center justify-between text-xs">
                      <span>Qty: {lot.quantity}</span>
                      <span className={`font-bold ${lotIsHighStakes && activeLotId !== lot.lot_number ? 'text-amber-600' : ''}`}>
                        {formatCurrency(lot.current_price)}
                      </span>
                    </div>
                    {lot.lot_end_time && !auctionEnded && (
                      <div className="flex items-center gap-1 text-xs mt-1">
                        <Clock className="h-3 w-3" />
                        <Countdown 
                          date={new Date(lot.lot_end_time)}
                          renderer={({ hours, minutes, seconds, completed }) => (
                            completed ? <span className="text-red-400 font-bold">Ended</span> : 
                            <span className={`font-mono ${lotIsHighStakes ? 'text-red-500 font-bold' : ''}`}>
                              {hours}h {minutes}m {seconds}s
                            </span>
                          )}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </SheetContent>
        </Sheet>
      </div>

      {/* Image Lightbox */}
      {lightboxOpen && lightboxImages.length > 0 && (
        <Lightbox
          mainSrc={lightboxImages[photoIndex]}
          nextSrc={lightboxImages[(photoIndex + 1) % lightboxImages.length]}
          prevSrc={lightboxImages[(photoIndex + lightboxImages.length - 1) % lightboxImages.length]}
          onCloseRequest={() => setLightboxOpen(false)}
          onMovePrevRequest={() =>
            setPhotoIndex((photoIndex + lightboxImages.length - 1) % lightboxImages.length)
          }
          onMoveNextRequest={() =>
            setPhotoIndex((photoIndex + 1) % lightboxImages.length)
          }
          imageTitle={`Image ${photoIndex + 1} of ${lightboxImages.length}`}
          enableZoom={true}
        />
      )}

      {/* Message Seller Modal */}
      {listing && (
        <MessageSellerModal
          isOpen={messageModalOpen}
          onClose={() => setMessageModalOpen(false)}
          sellerId={listing.seller_id}
          listingId={listing.id}
          listingTitle={getLocalized(listing, 'title')}
        />
      )}

      {/* iter189 Feature 2 — Lots Promotion Modal */}
      {showPromoModal && listing && (
        <ListingPromotionModal
          onClose={() => setShowPromoModal(false)}
          listingId={listing.id}
          listingTitle={getLocalized(listing, 'title')}
          listingType="lots"
        />
      )}

      {/* Verification Required Modal */}
      <VerificationRequiredModal
        isOpen={verificationModalOpen}
        onClose={() => setVerificationModalOpen(false)}
        action={verificationAction}
      />

      {/* Payment Method Selection Dialog */}
      <Dialog open={paymentModalOpen} onOpenChange={setPaymentModalOpen}>
        <DialogContent className="sm:max-w-md" data-testid="payment-method-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-[#06B6D4]" />
              {t('checkout.selectPayment', 'Select Payment Method')}
            </DialogTitle>
          </DialogHeader>

          {paymentModalLot && (
            <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 mb-2">
              <p className="font-medium text-sm">{getLocalized(paymentModalLot, 'title')}</p>
              <p className="text-lg font-bold text-[#1E3A8A] dark:text-white" data-testid="payment-dialog-price">
                {formatCurrency(paymentModalLot.buy_now_price)}
              </p>
            </div>
          )}

          <div className="space-y-2" data-testid="payment-method-options">
            {/* Stripe */}
            <label data-testid="lot-payment-method-stripe"
              className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                selectedPaymentMethod === 'stripe' ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
              }`}>
              <input type="radio" name="lotPaymentMethod" value="stripe" checked={selectedPaymentMethod === 'stripe'}
                onChange={() => setSelectedPaymentMethod('stripe')} className="mt-1 accent-blue-600" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <CreditCard className="h-4 w-4 text-blue-600" />
                  <span className="font-medium">{t('checkout.creditCard', 'Credit Card')}</span>
                  <span className="text-[10px] bg-blue-600 text-white px-1.5 py-0.5 rounded-full font-medium">{t('checkout.recommended', 'Recommended')}</span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{t('checkout.stripeDesc', 'Secure payment via Stripe. Visa, Mastercard, Amex.')}</p>
              </div>
            </label>
            {/* Cash */}
            <label data-testid="lot-payment-method-cash"
              className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                selectedPaymentMethod === 'cash' ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
              }`}>
              <input type="radio" name="lotPaymentMethod" value="cash" checked={selectedPaymentMethod === 'cash'}
                onChange={() => setSelectedPaymentMethod('cash')} className="mt-1 accent-emerald-600" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Banknote className="h-4 w-4 text-emerald-600" />
                  <span className="font-medium">{t('checkout.cash', 'Cash')}</span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{t('checkout.cashDesc', 'Pay in person at local pickup.')}</p>
              </div>
            </label>
            {/* E-Transfer */}
            <label data-testid="lot-payment-method-etransfer"
              className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all ${
                selectedPaymentMethod === 'etransfer' ? 'border-purple-500 bg-purple-50/50 dark:bg-purple-950/20' : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
              }`}>
              <input type="radio" name="lotPaymentMethod" value="etransfer" checked={selectedPaymentMethod === 'etransfer'}
                onChange={() => setSelectedPaymentMethod('etransfer')} className="mt-1 accent-purple-600" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Send className="h-4 w-4 text-purple-600" />
                  <span className="font-medium">{t('checkout.etransfer', 'Interac E-Transfer')}</span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">{t('checkout.etransferDesc', 'Instructions will be sent via email.')}</p>
              </div>
            </label>
          </div>

          <DialogFooter className="mt-2">
            <Button variant="outline" onClick={() => setPaymentModalOpen(false)} data-testid="payment-dialog-cancel">
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button
              onClick={confirmBuyNow}
              data-testid="payment-dialog-confirm"
              className={
                selectedPaymentMethod === 'stripe' ? 'bg-blue-600 hover:bg-blue-700' :
                selectedPaymentMethod === 'cash' ? 'bg-emerald-600 hover:bg-emerald-700' :
                'bg-purple-600 hover:bg-purple-700'
              }
            >
              {selectedPaymentMethod === 'stripe' ? (
                <><CreditCard className="h-4 w-4 mr-1.5" />{t('checkout.payNow', 'Pay Now')}</>
              ) : selectedPaymentMethod === 'cash' ? (
                <><Banknote className="h-4 w-4 mr-1.5" />{t('checkout.confirmOrder', 'Confirm Order')}</>
              ) : (
                <><Send className="h-4 w-4 mr-1.5" />{t('checkout.confirmEtransfer', 'Confirm E-Transfer')}</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MultiItemListingDetailPage;
