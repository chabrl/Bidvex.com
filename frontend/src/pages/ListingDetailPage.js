import API_BASE from '../config';
import ErrorBoundary from '../components/ErrorBoundary';
import SafeImage from '../components/SafeImage';
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { usePlatformTermsGate } from '../contexts/PlatformTermsGateContext';
import { extractErrorMessage } from '../utils/errorHandler';
import { formatCurrency, formatPercent, formatListingPrice } from '../utils/currencyFormatter';
import { getLocalized } from '../utils/localization';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from 'sonner';
import Countdown from 'react-countdown';
import confetti from 'canvas-confetti';
import { Clock, MapPin, Eye, User, DollarSign, MessageCircle, TrendingUp, Wifi, WifiOff, AlertCircle, CheckCircle2, Shield, Star } from 'lucide-react';
import PromotionManagerModal from '../components/PromotionManagerModal';
import WatchlistButton from '../components/WatchlistButton';
import SocialShare from '../components/SocialShare';
import AutoBidModal from '../components/AutoBidModalLegacy';
import MaskedBidHistory from '../components/MaskedBidHistory';
import MessageSellerModal from '../components/MessageSellerModal';
import RateSellerModal from '../components/RateSellerModal';
import AuctioneerInfo from '../components/AuctioneerInfo';
import BidConfirmationDialog from '../components/BidConfirmationDialog';
import PriceBreakdown from '../components/PriceBreakdown';
import AcceptedPaymentMethodsCard, { resolveAcceptedMethods } from '../components/AcceptedPaymentMethodsCard';
import PrivateSaleBadge, { BusinessSellerBadge, SellerAccountBadge } from '../components/PrivateSaleBadge';
// iter300 — Top Seller merit badge + dispute filing
import { TopSellerBadge } from '../components/TopSellerBadge';
import { FileDisputeButton } from '../components/FileDisputeButton';
import { VerifiedBadge } from '../components/VerifiedBadge';
import PartnerBadge from '../components/PartnerBadge';
import SEO from '../components/SEO';
import SecurityDepositBanner from '../components/SecurityDepositBanner';
import ListingPromotionModal from '../components/ListingPromotionModal';
import QuickBidButtons from '../components/QuickBidButtons';
import { useTrustStatus, BidBlocker } from '../components/TrustVerification';
import { SellerReputationCard, SellerReviewsList } from '../components/SellerReputation';
import { CrossBorderAdvisoryPanel, CrossBorderBidModal } from '../components/legal/LegalComplianceSections';
// iter297 P1 — Buyer Confirm Pickup CTA + deposit-release flow.
import PickupConfirmButton from '../components/PickupConfirmButton';
import { VehicleFeeBreakdown, SellerContactGate } from '../components/vehicles/VehicleFeeBreakdown';
import { CostBreakdown } from '../components/CostBreakdown'; // iter210 Step 6
import Lightbox from 'yet-another-react-lightbox';
import Zoom from 'yet-another-react-lightbox/plugins/zoom';
import Counter from 'yet-another-react-lightbox/plugins/counter';
import 'yet-another-react-lightbox/styles.css';
import 'yet-another-react-lightbox/plugins/counter.css';
import InfoTip from '../components/InfoTip';
import ListingLogisticsDetails from '../components/ListingLogisticsDetails';
import { useRealtimeBidding } from '../hooks/useRealtimeBidding';
// iter302 Directive 1 — Winner & Settlement Panel (seller view, ended listings)
import SettlementPanel from '../components/SettlementPanel';
import { LangLink } from '../components/LangLink';

const API = API_BASE;

const ListingDetailPage = () => {
  const { id } = useParams();
  const { t, i18n } = useTranslation();
  const { user, token } = useAuth();
  const { runWithTermsGate } = usePlatformTermsGate();
  const navigate = useNavigate();
  const [listing, setListing] = useState(null);
  const [seller, setSeller] = useState(null);
  const [bids, setBids] = useState([]);
  const [bidAmount, setBidAmount] = useState('');
  const [loading, setLoading] = useState(true);
  const [showPromotionModal, setShowPromotionModal] = useState(false);
  const [messageModalOpen, setMessageModalOpen] = useState(false);
  const [rateSellerModalOpen, setRateSellerModalOpen] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [photoIndex, setPhotoIndex] = useState(0);
  const [featureFlags, setFeatureFlags] = useState({ enable_buy_now: true });
  const [bidConfirmDialogOpen, setBidConfirmDialogOpen] = useState(false);
  const [pendingBidAmount, setPendingBidAmount] = useState(0);
  const [placingBid, setPlacingBid] = useState(false);
  const [showVerificationPrompt, setShowVerificationPrompt] = useState(false);
  const [depositAuthorized, setDepositAuthorized] = useState(false);
  const [showPromoModal, setShowPromoModal] = useState(false);
  // iter484.2 — Buyer must acknowledge accepted payment methods before bidding
  const [paymentAck, setPaymentAck] = useState(false);
  
  // Cross-border & settlement state
  const [crossBorderModalOpen, setCrossBorderModalOpen] = useState(false);
  const [crossBorderAccepted, setCrossBorderAccepted] = useState(false);
  const [settlementData, setSettlementData] = useState(null);
  const [sellerContactData, setSellerContactData] = useState(null);
  const [feePreview, setFeePreview] = useState(null);
  
  // Trust status for bid blocking
  const { isVerified, canBid, loading: trustLoading, refresh: refreshTrustStatus } = useTrustStatus();
  
  // Real-time bidding hook - provides instant updates via WebSocket
  const {
    currentPrice: realtimePrice,
    bidCount: realtimeBidCount,
    bidStatus,
    isConnected,
    connectionHealth,
    lastUpdate,
    auctionEndDate: realtimeEndDate,  // Anti-sniping extended end time (Date object)
    auctionEndEpoch,                   // Unix timestamp (timezone-safe primary source)
    serverTimeOffset,                  // Client-server time difference
    timeExtended
  } = useRealtimeBidding(id);

  const fetchFeatureFlags = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/marketplace/feature-flags`);
      setFeatureFlags(response.data);
    } catch (error) {
      console.error('Failed to fetch feature flags:', error);
    }
  }, []);

  const fetchListing = useCallback(async (retryCount = 0) => {
    try {
      const response = await axios.get(`${API}/listings/${id}`);
      const data = response.data;
      
      // Identity Guard: redirect vehicles to the proper VehicleDetailView
      const cat = (data.category || '').toLowerCase();
      if (cat === 'vehicle' || cat === 'vehicles' || cat === 'car' || cat === 'auto') {
        navigate(`/vehicle-auctions/${id}`, { replace: true });
        return;
      }
      
      setListing(data);

      // Meta Pixel ViewContent — dedupe-safe per (listing, session)
      import('../utils/metaPixel').then(({ trackViewContent }) => {
        trackViewContent(data, { routeHint: 'marketplace' });
      }).catch((pixelErr) => {
        console.debug('[ListingDetailPage] ViewContent pixel emit failed:', pixelErr);
      });

      const sellerResponse = await axios.get(`${API}/users/${data.seller_id}`);
      setSeller(sellerResponse.data);
    } catch (error) {
      if (retryCount < 1) {
        console.warn(`Listing fetch failed, retrying in 2s (attempt ${retryCount + 1})...`);
        await new Promise(r => setTimeout(r, 2000));
        return fetchListing(retryCount + 1);
      }
      console.error('Failed to fetch listing:', error);
      toast.error('Listing not found');
      navigate('/marketplace');
    } finally {
      setLoading(false);
    }
  }, [id, navigate]);

  const fetchBids = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/bids/listing/${id}`);
      setBids(response.data);
    } catch (error) {
      console.error('Failed to fetch bids:', error);
    }
  }, [id]);

  // Initial data load — runs once per listing id. Deferred a tick so no
  // state setters fire synchronously inside the effect body.
  useEffect(() => {
    const initTimer = setTimeout(() => {
      fetchListing();
      fetchBids();
      fetchFeatureFlags();
    }, 0);
    return () => clearTimeout(initTimer);
  }, [fetchListing, fetchBids, fetchFeatureFlags]);

  // Fetch settlement status for won auctions
  const fetchSettlement = useCallback(async () => {
    if (!token || !id) return;
    try {
      const res = await axios.get(`${API}/vehicle-settlement/${id}/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSettlementData(res.data);
      if (res.data?.contact_revealed) {
        const contactRes = await axios.get(`${API}/auctions/${id}/seller-contact`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSellerContactData(contactRes.data?.seller);
      }
    } catch { /* no settlement yet */ }
  }, [token, id]);

  // Fetch fee preview for vehicle-category listings
  const fetchFeePreview = useCallback(async (price) => {
    if (!price || price <= 0) return;
    try {
      const res = await axios.get(`${API}/vehicle-settlement/fee-preview/${price}`);
      setFeePreview(res.data);
    } catch { /* silent */ }
  }, []);

  // Check if listing is cross-border (non-Canadian)
  const isCrossBorder = listing && listing.country && listing.country !== 'CA' && listing.country !== 'Canada';
  const isVehicleCategory = listing && ['vehicle', 'vehicles', 'vehicle parts'].includes((listing.category || '').toLowerCase());
  const isAuctionWon = listing && listing.status === 'sold' && listing.winner_id === user?.id;

  // Fetch settlement when auction is won. The fetchers are async
  // (state updates land in a later microtask, not synchronously).
  useEffect(() => {
    if (!isAuctionWon) return;
    const settlementTimer = setTimeout(() => {
      fetchSettlement();
      if (listing?.current_price) fetchFeePreview(listing.current_price);
    }, 0);
    return () => clearTimeout(settlementTimer);
  }, [isAuctionWon, listing?.current_price, fetchSettlement, fetchFeePreview]);

  const handlePlaceBid = async (e) => {
    e.preventDefault();
    if (!token) {
      navigate('/auth', { state: { from: { pathname: `/listing/${id}` } } });
      return;
    }

    // iter212 — Storage Facility users may browse but may not bid on non-storage
    // listings. Show a single inline toast only on click (no banner while browsing).
    const isStorageFacility = !!(user && (user.account_type === 'storage_facility' || user.is_storage_facility === true) && user.role !== 'admin' && user.role !== 'super_admin');
    if (isStorageFacility) {
      toast.error(
        i18n.language === 'fr'
          ? 'Les facilités d\'entreposage ne peuvent enchérir que sur les enchères d\'unités d\'entreposage.'
          : 'Storage facilities can only bid on storage-unit auctions.',
        { duration: 6000 }
      );
      return;
    }

    // Check trust verification status
    if (!canBid) {
      toast.error(
        i18n.language === 'fr' 
          ? 'Veuillez vérifier votre compte avant de placer une enchère.'
          : 'Please verify your account before placing a bid.'
      );
      navigate('/profile/settings?tab=payments');
      return;
    }

    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error('Please enter a valid bid amount');
      return;
    }

    // iter484.2 — Buyer must acknowledge accepted payment methods
    // BEFORE the confirmation dialog opens.
    if (!paymentAck) {
      toast.error(
        i18n.language === 'fr'
          ? 'Veuillez confirmer que vous comprenez les modes de paiement acceptés avant d\u2019enchérir.'
          : 'Please acknowledge the accepted payment methods before placing a bid.'
      );
      return;
    }

    // Cross-border bid intercept — require disclosure acceptance
    if (isCrossBorder && !crossBorderAccepted) {
      setCrossBorderModalOpen(true);
      setPendingBidAmount(amount);
      return;
    }

    // Meta Pixel AddToCart — intent signal fired when user clicks "Place Bid"
    // CTA, BEFORE the confirmation dialog. Dedup-safe per (listing, session).
    try {
      const { trackAddToCart } = await import('../utils/metaPixel');
      trackAddToCart({
        listing,
        bidAmount: amount,
        routeHint: 'marketplace',
      });
    } catch (pixelErr) {
      console.debug('[ListingDetailPage] AddToCart pixel emit failed:', pixelErr);
    }

    // Show bid confirmation dialog with cost breakdown
    setPendingBidAmount(amount);
    setBidConfirmDialogOpen(true);
  };

  const confirmPlaceBid = async () => {
    setPlacingBid(true);
    try {
      const bidPayload = {
        listing_id: id,
        amount: pendingBidAmount,
      };
      if (isCrossBorder && crossBorderAccepted) {
        bidPayload.cross_border_disclosure_accepted = true;
      }
      const response = await runWithTermsGate(() => axios.post(`${API}/bids`, bidPayload));
      
      setBidConfirmDialogOpen(false);
      toast.success('Bid placed successfully!');
      // Meta Pixel InitiateCheckout — every successful bid submission is a
      // distinct funnel-commit signal. NOT dedup-protected: bidding wars
      // strengthen Meta's optimization data.
      try {
        const { trackInitiateCheckout } = await import('../utils/metaPixel');
        trackInitiateCheckout({
          listing,
          bidAmount: pendingBidAmount || parseFloat(bidAmount) || 0,
          routeHint: 'marketplace',
        });
      } catch (pixelErr) {
        console.debug('[ListingDetailPage] InitiateCheckout pixel emit failed:', pixelErr);
      }
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 }
      });
      
      // Check if anti-sniping extension was applied
      if (response.data.extension_applied && response.data.new_auction_end) {
        toast.info('⏰ Auction Extended!', {
          description: 'Your bid triggered the 2-minute anti-sniping extension.',
          duration: 5000
        });
      }
      
      fetchListing();
      fetchBids();
      setBidAmount('');
      setPendingBidAmount(0);
    } catch (error) {
      // iter404 — user cancelled the inline platform-terms modal; stay silent.
      if (error?.termsGateCancelled) {
        setBidConfirmDialogOpen(false);
        return;
      }
      const errorMessage = extractErrorMessage(error);
      
      // Show clear error message
      if (errorMessage?.toLowerCase().includes('auction has ended')) {
        toast.error('Auction has ended', {
          description: 'This auction is no longer accepting bids.',
          duration: 5000
        });
        // Refresh listing to update UI
        fetchListing();
      } else {
        toast.error(errorMessage || 'Failed to place bid');
      }
    } finally {
      setPlacingBid(false);
    }
  };

  const handleBuyNow = async () => {
    if (!token) {
      navigate('/auth', { state: { from: { pathname: `/listing/${id}` } } });
      return;
    }

    try {
      const response = await axios.post(`${API}/payments/checkout`, {
        listing_id: id,
        origin_url: window.location.origin,
        buy_now: true,
      });
      
      window.location.href = response.data.url;
    } catch (error) {
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Payment failed');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  if (!listing) return null;

  // CRITICAL: Use epoch timestamp as SINGLE SOURCE OF TRUTH (timezone-safe)
  // This prevents UI/Logic sync conflicts caused by timezone interpretation issues
  // Priority: WebSocket epoch > WebSocket Date > listing.auction_end_date
  
  // Calculate effective end date using epoch timestamp (immune to timezone issues)
  const getEffectiveEndDate = () => {
    // Priority 1: Use epoch timestamp from WebSocket (most reliable)
    if (auctionEndEpoch) {
      return new Date(auctionEndEpoch * 1000);
    }
    // Priority 2: Use Date object from WebSocket
    if (realtimeEndDate) {
      return realtimeEndDate;
    }
    // Priority 3: Parse ISO string from API response
    if (listing?.auction_end_date) {
      // Parse as UTC to avoid timezone issues
      const dateStr = listing.auction_end_date;
      if (typeof dateStr === 'string') {
        // Ensure proper UTC parsing
        if (dateStr.endsWith('Z') || dateStr.includes('+')) {
          return new Date(dateStr);
        }
        // No timezone indicator - assume UTC
        return new Date(dateStr + 'Z');
      }
      return new Date(dateStr);
    }
    return new Date();
  };
  
  const effectiveEndDate = getEffectiveEndDate();
  
  // Only mark as ended if BOTH countdown is complete AND we're not waiting for WebSocket sync
  // This prevents false "Auction has ended" when anti-sniping extensions occur
  const now = new Date();
  const timeRemaining = effectiveEndDate - now;
  const isAuctionEnded = timeRemaining <= 0 && bidStatus !== 'EXTENDING';
  
  // Debug logging with epoch timestamps
  console.log('=== Auction Status Debug (Timezone-Safe) ===');
  console.log('Epoch timestamp (primary):', auctionEndEpoch);
  console.log('Server time offset (seconds):', serverTimeOffset);
  console.log('Listing end date (API):', listing.auction_end_date);
  console.log('Real-time end date:', realtimeEndDate?.toISOString());
  console.log('Effective end date:', effectiveEndDate.toISOString());
  console.log('Time remaining (ms):', timeRemaining);
  console.log('Is auction ended:', isAuctionEnded);
  console.log('Time extended:', timeExtended);

  return (
    <div className="min-h-screen py-8 px-4" data-testid="listing-detail-page">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div 
              className="aspect-square rounded-2xl overflow-hidden bg-gray-100 cursor-zoom-in hover:opacity-95 transition-opacity"
              onClick={() => {
                setPhotoIndex(0);
                setLightboxOpen(true);
              }}
              data-testid="listing-detail-main-image-wrapper"
            >
              {listing.images && listing.images.length > 0 ? (
                <SafeImage
                  src={listing.images[0]}
                  alt={getLocalized(listing, 'title')}
                  className="w-full h-full object-cover"
                  data-testid="listing-detail-primary-image"
                  loading="eager"
                  fetchPriority="high"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/10 to-accent/10">
                  <span className="text-9xl">📦</span>
                </div>
              )}
            </div>
            
            {listing.images && listing.images.length > 1 && (
              <div className="grid grid-cols-4 gap-2">
                {listing.images.slice(1, 5).map((img, idx) => (
                  <div 
                    key={idx} 
                    className="aspect-square rounded-lg overflow-hidden bg-gray-100 cursor-zoom-in hover:opacity-90 transition-opacity"
                    onClick={() => {
                      setPhotoIndex(idx + 1);
                      setLightboxOpen(true);
                    }}
                  >
                    <SafeImage src={img} alt={`${getLocalized(listing, 'title')} ${idx + 2}`} className="w-full h-full object-cover" loading="lazy" />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-6">
            <div>
              {/* iter258 Mission 5 — SEO meta + Product JSON-LD on the
                  listing detail page. og:type=product, image=first
                  photo, schema.org Product → Offer with current_price. */}
              <SEO
                title={`${getLocalized(listing, 'title')} — BidVex Auction`}
                description={`Bid on ${getLocalized(listing, 'title')} currently listed at $${listing.current_price || listing.starting_price || 0} CAD. Auction ends ${listing.auction_end_date || listing.auction_end_time || 'soon'}. Located in ${listing.city || listing.region || 'Canada'}.`}
                path={`/listing/${listing.id}`}
                type="product"
                image={(listing.images && listing.images[0]) || '/bidvex-og.png'}
                jsonLd={{
                  '@context': 'https://schema.org',
                  '@type': 'Product',
                  name: getLocalized(listing, 'title'),
                  description: (getLocalized(listing, 'description') || '').slice(0, 5000),
                  image: (listing.images || []).slice(0, 3),
                  offers: {
                    '@type': 'Offer',
                    url: `https://bidvex.com/listing/${listing.id}`,
                    priceCurrency: listing.currency || 'CAD',
                    price: listing.current_price || listing.starting_price || 0,
                    priceValidUntil: listing.auction_end_date || listing.auction_end_time || undefined,
                    availability: 'https://schema.org/InStock',
                    seller: { '@type': 'Organization', name: 'BidVex Inc.' },
                  },
                  auctionStatus: 'ActiveAuction',
                  startTime: listing.created_at,
                  endTime: listing.auction_end_date || listing.auction_end_time,
                }}
              />
              <div className="flex items-start justify-between gap-4 mb-2">
                <div className="flex-1 min-w-0">
                  <h1 className="text-3xl font-bold" data-testid="listing-title">{getLocalized(listing, 'title')}</h1>
                  {/* iter299 P0 — Bill 96: surface the French title as a
                      subtitle whenever it exists and isn't already the
                      main displayed title. */}
                  {listing.title_fr && listing.title_fr !== getLocalized(listing, 'title') && (
                    <p className="text-lg text-slate-500 mt-0.5" data-testid="listing-title-fr-subtitle">
                      {listing.title_fr}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {/* Watchlist Button */}
                  <WatchlistButton listingId={listing.id} size="large" showLabel={true} />
                  
                  {/* Social Share Button */}
                  <SocialShare 
                    title={getLocalized(listing, 'title')}
                    url={window.location.href}
                    description={`Check out this auction on BidVex: ${getLocalized(listing, 'title')} - Current bid: $${listing.current_price}`}
                  />
                  
                  {listing.is_promoted && (
                    <Badge className="gradient-bg text-white border-0">Featured</Badge>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-4 text-sm text-muted-foreground mb-4">
                <div className="flex items-center gap-1">
                  <MapPin className="h-4 w-4" />
                  <span>{listing.city}, {listing.region}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Eye className="h-4 w-4" />
                  <span>{listing.views} {t('listing.views')}</span>
                </div>
              </div>

              {/* iter217 — Seller-type badge (Partner / Dealer / Storage / Private Sale) */}
              {(() => {
                const acctType = listing?.seller_account_type
                  || (listing?.seller_is_partner ? 'partner'
                    : listing?.seller_is_vehicle_dealer ? 'vehicle_dealer'
                    : listing?.seller_is_storage_facility ? 'storage_facility'
                    : (seller?.is_tax_registered ? 'business' : 'individual'));
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

              {/* iter300 — merit-based Top Seller badge (prominent in seller panel) */}
              {listing?.seller_is_top_seller && (
                <div className="mb-4"><TopSellerBadge size="md" /></div>
              )}

              {/* iter300 P1 — File a Dispute (buyer/seller of payment_collected
                  listings, 7-day window — the button self-hides otherwise) */}
              {user && listing?.id && (
                <div className="mb-4">
                  <FileDisputeButton listingId={listing.id} section="marketplace" />
                </div>
              )}

              {/* Verified Auction Firm Badge — fetched from API (compact, sits below the main badge) */}
              {listing?.seller_id && !listing?.seller_is_partner && (
                <div className="mb-4"><PartnerBadge sellerId={listing.seller_id} size="md" /></div>
              )}

              {/* Cross-Border Advisory Panel — for non-Canadian listings */}
              {isCrossBorder && (
                <div className="mb-4">
                  <CrossBorderAdvisoryPanel />
                </div>
              )}

              {/* Auction Won: Settlement Gate + Fee Breakdown */}
              {isAuctionWon && (
                <div className="mb-4 space-y-3" data-testid="auction-won-settlement">
                  <SellerContactGate
                    settlementStatus={settlementData?.settlement_status || 'PENDING_CLOSE'}
                    sellerData={sellerContactData}
                  />
                  {feePreview && (
                    <VehicleFeeBreakdown
                      hammerPrice={listing.current_price}
                      feeData={feePreview}
                    />
                  )}
                </div>
              )}

              <Separator className="my-4" />

              <div className="space-y-4">
                {/* Real-time connection status indicator */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {isConnected ? (
                      <>
                        <Wifi className="h-4 w-4 text-green-500" />
                        <span className="text-xs text-green-600 font-medium">{t('listingDetail.liveUpdatesActive', 'Live Updates Active')}</span>
                      </>
                    ) : (
                      <>
                        <WifiOff className="h-4 w-4 text-orange-500 animate-pulse" />
                        <span className="text-xs text-orange-600 font-medium">{t('listingDetail.reconnecting', 'Reconnecting…')}</span>
                      </>
                    )}
                  </div>
                  {lastUpdate && (
                    <span className="text-xs text-muted-foreground">
                      {t('listingDetail.updatedAt', { time: new Date(lastUpdate).toLocaleTimeString(), defaultValue: 'Updated {{time}}' })}
                    </span>
                  )}
                </div>

                {/* Current bid with real-time price */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">{t('marketplace.currentBid')}</p>
                    <p className="text-4xl font-bold gradient-text" data-testid="current-price">
                      {formatListingPrice(realtimePrice ?? listing.current_price, listing.currency)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {realtimeBidCount ?? listing.bid_count ?? 0} {(realtimeBidCount ?? listing.bid_count ?? 0) === 1 ? 'bid' : 'bids'} placed
                    </p>
                    {/* iter220 Task 5 — Per-item bid warning. When a listing
                        has quantity > 1 AND multiply_hammer_by_quantity is on,
                        bids are PER ITEM and the buyer's total = hammer × qty.
                        Shown directly under the current price so it's
                        impossible to miss before placing a bid. */}
                    {(listing.quantity || 1) > 1 && listing.multiply_hammer_by_quantity && (
                      <div
                        className="mt-3 p-3 rounded-lg border-2 border-amber-500 bg-amber-50 dark:bg-amber-950/30"
                        data-testid="per-item-bid-warning"
                      >
                        <p className="text-sm font-bold text-amber-900 dark:text-amber-200 leading-snug">
                          {i18n.language?.startsWith('fr')
                            ? `⚠️ Note : Votre mise est par article. Coût total = Prix d'adjudication × Quantité (${listing.quantity}).`
                            : `⚠️ Note: Your bid is per item. Total cost = Hammer Price × Quantity (${listing.quantity}).`}
                        </p>
                      </div>
                    )}
                  </div>
                  
                  {/* Bidding status badge */}
                  {user && (() => {
                    const isSeller = user.id === listing.seller_id;
                    // Use real-time bid count first (WebSocket) then fall back to fetched snapshot
                    const hasBids = (realtimeBidCount ?? listing.bid_count ?? 0) > 0 || !!listing.highest_bidder_id;
                    // BUG 2 FIX — sellers can never be "outbid" on their own listing.
                    // Show a "Bid Received" badge instead when there's at least one bid.
                    if (isSeller) {
                      if (!hasBids) return null;
                      return (
                        <Badge
                          className="bg-sky-500 text-white px-4 py-2 text-sm font-bold"
                          data-testid="seller-bid-received-badge"
                        >
                          <CheckCircle2 className="h-4 w-4 mr-1" />
                          Bid Received / Enchère reçue
                        </Badge>
                      );
                    }
                    if (bidStatus && bidStatus !== 'VIEWER' && bidStatus !== 'NO_BIDS') {
                      if (bidStatus === 'LEADING') {
                        return (
                          <Badge className="bg-green-500 text-white px-4 py-2 text-sm font-bold animate-pulse" data-testid="bidder-leading-badge">
                            <CheckCircle2 className="h-4 w-4 mr-1" />
                            LEADING
                          </Badge>
                        );
                      }
                      if (bidStatus === 'OUTBID') {
                        return (
                          <Badge className="bg-red-500 text-white px-4 py-2 text-sm font-bold" data-testid="bidder-outbid-badge">
                            <AlertCircle className="h-4 w-4 mr-1" />
                            OUTBID
                          </Badge>
                        );
                      }
                    }
                    return null;
                  })()}
                </div>

                {!isAuctionEnded && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-lg">
                      <Clock className={`h-5 w-5 ${timeExtended ? 'text-orange-500 animate-pulse' : 'text-primary'}`} />
                      <Countdown
                        key={effectiveEndDate?.getTime()} // Re-render countdown when end date changes
                        date={effectiveEndDate}
                        renderer={({ days, hours, minutes, seconds, completed }) => (
                          <span className={`font-semibold countdown-timer ${completed ? 'text-red-500' : timeExtended ? 'text-orange-500' : 'text-primary'}`}>
                            {completed ? t('marketplace.ended') : `${days}d ${hours}h ${minutes}m ${seconds}s`}
                          </span>
                        )}
                      />
                      {timeExtended && (
                        <Badge className="bg-orange-100 text-orange-700 text-xs ml-2 animate-pulse">
                          ⏰ Extended
                        </Badge>
                      )}
                    </div>
                    {timeExtended && (
                      <p className="text-xs text-orange-600">
                        Auction extended due to last-minute bidding activity
                      </p>
                    )}
                  </div>
                )}

                {isAuctionEnded && (
                  <Badge variant="destructive" className="text-sm">{t('listingDetail.auctionEnded', 'Auction Ended')}</Badge>
                )}
              </div>
            </div>

            {/* iter297 P1 — Buyer Confirm Pickup CTA (auto-hides when
                the actor isn't a party or the listing isn't ended). */}
            {isAuctionEnded && (
              <div className="mt-4">
                <PickupConfirmButton
                  listing={listing}
                  currentUser={user}
                  onConfirmed={() => fetchListing()}
                />
              </div>
            )}

            {/* iter302 Directive 1 — ended listing with a winner: the Promote
                block is replaced by the Winner & Settlement Panel. */}
            {user && listing.seller_id === user.id && isAuctionEnded && (listing.winner_id || listing.status === 'sold') ? (
              <SettlementPanel listingId={id} />
            ) : user && listing.seller_id === user.id && !listing.is_promoted ? (
              <Card className="glassmorphism border-2 border-primary/20">
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg mb-2">{t('listingDetail.boostYourListing', 'Boost Your Listing')}</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        {t('listingDetail.boostYourListingBody', 'Increase visibility and reach more potential buyers with promoted placement')}
                      </p>
                      <Button 
                        className="gradient-button text-white border-0"
                        onClick={() => setShowPromoModal(true)}
                        data-testid="promote-listing-btn"
                      >
                        <TrendingUp className="mr-2 h-4 w-4" />
                        Promote This Listing
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ) : null}

            {!isAuctionEnded && user && listing.seller_id !== user.id && (
              <Card className="glassmorphism">
                <CardContent className="p-6 space-y-4">
                  {/* Trust Verification Check */}
                  {!canBid && !trustLoading && (
                    <Alert className="border-amber-200 bg-amber-50 dark:bg-amber-950/30">
                      <Shield className="h-4 w-4 text-amber-600" />
                      <AlertDescription className="flex flex-col gap-3">
                        <span className="text-amber-700 dark:text-amber-400">
                          {t('listing.verificationRequired', 
                            { defaultValue: i18n.language === 'fr' 
                              ? 'Vous devez vérifier votre compte avant de pouvoir enchérir.'
                              : 'You must verify your account before you can bid.' })}
                        </span>
                        <Button 
                          size="sm" 
                          onClick={() => navigate('/settings?tab=payments')}
                          className="w-fit"
                          data-testid="verify-to-bid-btn"
                        >
                          <Shield className="mr-2 h-4 w-4" />
                          {i18n.language === 'fr' ? 'Vérifier maintenant' : 'Verify Now'}
                        </Button>
                      </AlertDescription>
                    </Alert>
                  )}
                  
                  {/* Security Deposit Banner for High-Value Auctions */}
                  <SecurityDepositBanner
                    listingId={id}
                    startingPrice={listing.starting_price || 0}
                    currency={listing.currency || 'CAD'}
                    onDepositStatusChange={setDepositAuthorized}
                  />
                  
                  <form onSubmit={handlePlaceBid} className="space-y-3">
                    {/* Quick Bid pills (iter175) — one-tap +$X / +$Y / +$Z */}
                    {canBid && !((listing.starting_price || 0) >= 10000 && !depositAuthorized) && (
                      <QuickBidButtons
                        currentBid={realtimePrice ?? listing.current_price ?? 0}
                        bidIncrement={listing.bid_increment || 1}
                        loading={placingBid}
                        disabled={!canBid}
                        onConfirm={(amount) => {
                          setBidAmount(String(amount));
                          setPendingBidAmount(amount);
                          if (isCrossBorder && !crossBorderAccepted) {
                            setCrossBorderModalOpen(true);
                          } else {
                            setBidConfirmDialogOpen(true);
                          }
                        }}
                        testidPrefix="marketplace-quick-bid"
                      />
                    )}

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm font-medium">{t('listing.yourBid')}
                          <InfoTip en="Enter an amount higher than the current bid. You'll see a full cost breakdown before confirming." fr="Entrez un montant supérieur à l'enchère actuelle. Vous verrez un détail complet des coûts avant de confirmer." />
                        </label>
                        <Badge variant="outline" className="text-xs font-mono" data-testid="bid-currency-badge">
                          {t('currency.bidIn', { currency: listing.currency || 'CAD' })}
                        </Badge>
                      </div>
                      <Input
                        type="number"
                        step="0.01"
                        min={(realtimePrice ?? listing.current_price) + 0.01}
                        value={bidAmount}
                        onChange={(e) => setBidAmount(e.target.value)}
                        placeholder={`Min: ${formatListingPrice((realtimePrice ?? listing.current_price) + 1, listing.currency)}`}
                        required
                        disabled={!canBid || ((listing.starting_price || 0) >= 10000 && !depositAuthorized)}
                        data-testid="bid-amount-input"
                      />
                    </div>

                    {/* iter210 Step 6 — Live cost breakdown for any auction type */}
                    {bidAmount && parseFloat(bidAmount) > 0 && (
                      <CostBreakdown
                        hammerPrice={parseFloat(bidAmount)}
                        quantity={listing.quantity || 1}
                        multiplyByQuantity={!!listing.multiply_hammer_by_quantity}
                        auctionType={listing.category_type || (listing.is_vehicle ? 'vehicle' : 'lots')}
                        sellerUserId={listing.seller_id}
                        paymentMethod={(listing.payment_method || 'stripe').replace('-', '_')}
                        sellerAccountType={
                          listing.seller_account_type ||
                          (listing.is_vehicle ? 'vehicle_dealer' :
                           listing.is_partner_listing ? 'partner' :
                           listing.is_storage_listing ? 'storage_facility' : 'individual')
                        }
                        buyerTier={user?.subscription_tier || 'standard'}
                        currency={listing.currency || 'CAD'}
                        className="mt-2"
                      />
                    )}

                    {/* iter217 — Deposit Notice (i18n-conditional, no raw EN:/FR:) */}
                    {listing.requires_deposit && listing.deposit_amount > 0 ? (
                      <div className="p-3 bg-amber-50 border border-amber-300 rounded-md text-xs leading-relaxed" data-testid="bid-deposit-required-notice">
                        <p className="font-semibold text-amber-900 mb-1">⚠️ {t('listingDetail.depositRequired', 'Deposit required')}</p>
                        <p className="text-amber-800">
                          {t('listingDetail.depositRequiredFull', {
                            amount: listing.deposit_type === 'percentage'
                              ? t('listingDetail.depositOfPercentage', { pct: listing.deposit_amount })
                              : t('listingDetail.depositOfFixed', { amount: Number(listing.deposit_amount).toFixed(2), currency: listing.currency || 'CAD' }),
                            defaultValue: 'A deposit of {{amount}} is required to bid on this auction. It is charged to your card immediately on your first bid; refunded automatically if you do not win; credited toward your total if you win.',
                          })}
                        </p>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-500 px-1" data-testid="bid-no-deposit-notice">
                        {t('listingDetail.noDepositRequired', 'No deposit is required to bid on this auction.')}
                      </div>
                    )}

                    {/* iter484.2 — Data-driven Accepted Payment Methods card
                        (bilingual). Replaces the legacy singleton branch that
                        only showed Stripe OR Cash OR E-Transfer — ignoring
                        `listing.accepted_payment_methods` entirely. */}
                    <AcceptedPaymentMethodsCard listing={listing} variant="inline" />

                    {/* Real-time Price Breakdown */}
                    <PriceBreakdown
                      bidAmount={parseFloat(bidAmount) || 0}
                      category={listing.category}
                      buyerTier={user?.subscription_tier || 'basic'}
                      sellerTier={seller?.subscription_tier || 'basic'}
                      sellerIsBusiness={seller?.is_tax_registered || seller?.account_type === 'business'}
                      compact={true}
                      buyersPremiumRate={listing.custom_buyer_premium_rate}
                    />
                    
                    {/* Vehicle Fee Notice — bilingual */}
                    {isVehicleCategory && parseFloat(bidAmount) > 0 && (
                      <div className="text-[10px] text-slate-500 dark:text-slate-400 p-2 bg-slate-50 dark:bg-slate-800/50 rounded border border-slate-200 dark:border-slate-700" data-testid="vehicle-fee-notice">
                        <p>Platform Fee: ${(parseFloat(bidAmount) * 0.025).toFixed(2)} + Processing / Frais de plateforme : {(parseFloat(bidAmount) * 0.025).toFixed(2)} $ + Traitement</p>
                      </div>
                    )}
                    
                    {/* Cross-border warning badge */}
                    {isCrossBorder && (
                      <div className="text-[10px] font-medium text-blue-600 dark:text-blue-400 flex items-center gap-1" data-testid="cross-border-badge">
                        Cross-border listing / Annonce transfrontalière
                      </div>
                    )}

                    {/* iter484.2 — Pre-bid Acknowledgement of accepted payment methods */}
                    <label
                      className="flex items-start gap-2 text-[11px] leading-snug text-slate-600 dark:text-slate-300 cursor-pointer select-none px-1"
                      data-testid="listing-payment-ack-label"
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 h-3.5 w-3.5 accent-emerald-600 flex-shrink-0"
                        checked={paymentAck}
                        onChange={(e) => setPaymentAck(e.target.checked)}
                        data-testid="bid-payment-ack-checkbox"
                      />
                      <span>
                        {i18n.language?.startsWith('fr')
                          ? 'Je comprends les modes de paiement acceptés pour cette enchère et j\u2019accepte de compléter le paiement en utilisant l\u2019un des modes approuvés par le vendeur si je gagne.'
                          : 'I understand the accepted payment methods for this auction and agree to complete payment using one of the seller\u2019s approved methods if I win.'}
                      </span>
                    </label>

                    <Button 
                      type="submit" 
                      className="w-full gradient-button text-white border-0" 
                      disabled={!canBid || !paymentAck || ((listing.starting_price || 0) >= 10000 && !depositAuthorized)}
                      style={i18n.language === 'fr' ? { letterSpacing: '-0.02em', fontSize: '0.875rem' } : {}}
                      data-testid="place-bid-btn"
                    >
                      {canBid ? (
                        ((listing.starting_price || 0) >= 10000 && !depositAuthorized) ? (
                          // iter283-deposit-btn-fit — Compact locale-aware label
                          // (was stacking EN + FR, clipped on mobile).
                          <span
                            className="flex flex-col items-center justify-center gap-0.5 leading-tight py-1 px-2 min-w-0 max-w-full text-center"
                            data-testid="bid-btn-deposit-required"
                          >
                            <span className="flex items-center gap-2 text-sm font-bold break-words">
                              <Shield className="h-4 w-4 flex-shrink-0" />
                              <span>
                                {i18n.language?.startsWith('fr')
                                  ? 'Retenue de sécurité requise'
                                  : 'Security Hold Required'}
                              </span>
                            </span>
                            <span className="text-[11px] font-normal opacity-80">
                              {i18n.language?.startsWith('fr')
                                ? "500 $ retenus sur votre carte"
                                : "$500 hold on your card"}
                            </span>
                          </span>
                        ) : (
                          <>
                            <DollarSign className="mr-2 h-4 w-4" />
                            {t('listing.placeBid')}
                          </>
                        )
                      ) : (
                        <>
                          <Shield className="mr-2 h-4 w-4" />
                          {i18n.language === 'fr' ? 'Vérification requise' : 'Verification Required'}
                        </>
                      )}
                    </Button>
                  </form>

                  {/* Premium Bidding Features */}
                  <div className="space-y-3 pt-2">
                    <Separator />
                    <div className="flex gap-2">
                      <AutoBidModal
                        listingId={listing.id}
                        currentBid={listing.current_price}
                        minimumIncrement={1}
                        onAutoBidSetup={() => {
                          fetchListing();
                          toast.success('🤖 Auto-Bid Bot activated!');
                        }}
                      />
                    </div>
                  </div>

                  <Separator />

                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => setMessageModalOpen(true)}
                    data-testid="message-seller-btn"
                  >
                    <MessageCircle className="mr-2 h-4 w-4" />
                    📨 Message Seller
                  </Button>

                  {listing.buy_now_price && featureFlags.enable_buy_now && (
                    <>
                      <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                          <span className="w-full border-t" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                          <span className="bg-background px-2 text-muted-foreground">Or</span>
                        </div>
                      </div>
                      {/* iter220 Task 5 — Buy Now math breakdown.
                          When quantity > 1 AND multiply_hammer_by_quantity is
                          on, the BUY NOW unit price multiplies too. We render
                          the formula directly under the CTA so buyers see
                          exactly what they're charged before clicking. */}
                      {(listing.quantity || 1) > 1 && listing.multiply_hammer_by_quantity && (
                        <div
                          className="p-2.5 rounded-md bg-slate-100 dark:bg-slate-800 text-xs leading-relaxed"
                          data-testid="buy-now-breakdown"
                        >
                          <div className="font-semibold text-slate-700 dark:text-slate-200 mb-1">
                            {i18n.language?.startsWith('fr') ? 'Décomposition' : 'Breakdown'}
                          </div>
                          <div className="text-slate-600 dark:text-slate-400">
                            {formatListingPrice(listing.buy_now_price, listing.currency)} {' × '} {listing.quantity}
                            {' = '}
                            <span className="font-bold text-slate-900 dark:text-white">
                              {formatListingPrice(listing.buy_now_price * listing.quantity, listing.currency)}
                            </span>
                            <span className="text-[10px] ml-1">
                              ({i18n.language?.startsWith('fr') ? 'avant prime + taxes' : 'before premium + taxes'})
                            </span>
                          </div>
                        </div>
                      )}
                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={handleBuyNow}
                        data-testid="buy-now-btn"
                      >
                        {t('marketplace.buyNow')}: {
                          (listing.quantity || 1) > 1 && listing.multiply_hammer_by_quantity
                            ? formatListingPrice(listing.buy_now_price * listing.quantity, listing.currency)
                            : formatListingPrice(listing.buy_now_price, listing.currency)
                        }
                        {(listing.quantity || 1) > 1 && listing.multiply_hammer_by_quantity && (
                          <span className="ml-1 text-[10px] opacity-75">
                            ({formatListingPrice(listing.buy_now_price, listing.currency)} × {listing.quantity})
                          </span>
                        )}
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {!user && (
              <Card className="glassmorphism">
                <CardContent className="p-6">
                  <p className="text-center mb-4">{t('listingDetail.signInToPlaceBid', 'Sign in to place a bid')}</p>
                  <Button className="w-full gradient-button text-white border-0" onClick={() => navigate('/auth')}>
                    Sign In
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Buyer's Premium Transparency Banner */}
            {listing.custom_buyer_premium_rate != null && listing.custom_buyer_premium_rate > 0 && (
              <Alert className="border-amber-200 bg-amber-50 dark:bg-amber-950/20" data-testid="buyers-premium-banner">
                <DollarSign className="h-4 w-4 text-amber-600" />
                <AlertDescription className="text-amber-800 dark:text-amber-300 text-sm font-medium">
                  A {formatPercent(listing.custom_buyer_premium_rate * 100, 1)} buyer&apos;s premium applies to this lot
                  <InfoTip en="The buyer's premium is an additional fee on top of the hammer price, paid by the buyer. It covers platform services and seller-set premiums." fr="La prime acheteur est un frais supplémentaire au prix marteau, payé par l'acheteur. Elle couvre les services de la plateforme et les primes fixées par le vendeur." />
                </AlertDescription>
              </Alert>
            )}

            <Card className="glassmorphism">
              <CardHeader>
                <CardTitle className="text-lg">{t('listing.details')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Category:</span>
                  <span className="font-medium">{listing.category}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('listing.condition')}:</span>
                  <span className="font-medium capitalize">{listing.condition.replace('_', ' ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Bids:</span>
                  <span className="font-medium">{listing.bid_count}</span>
                </div>
                {seller && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('listing.seller')}:</span>
                    <span className="font-medium">{seller.name}</span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Auctioneer/Seller Info & Rating */}
            {listing.seller_id && (
              <Card className="glassmorphism">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{t('listingDetail.sellerInformation', 'Seller Information')}</CardTitle>
                    {user && user.id !== listing.seller_id && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setRateSellerModalOpen(true)}
                      >
                        <Star className="h-3.5 w-3.5 mr-1" /> Rate Seller
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <AuctioneerInfo sellerId={listing.seller_id} variant="full" />

                  {/* iter283 — Public seller info: company name + website,
                      surfaced only for verified business sellers (partner /
                      vehicle dealer / storage facility). Hidden for
                      private/individual sellers (privacy). */}
                  {(listing?.seller_company_name || listing?.seller_website) && (
                    <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-3 py-2.5 space-y-1"
                         data-testid="seller-public-info">
                      {listing?.seller_company_name && (
                        <div className="text-sm font-medium text-slate-700 dark:text-slate-200"
                             data-testid="seller-public-company">
                          {listing.seller_company_name}
                        </div>
                      )}
                      {listing?.seller_website && (
                        <a
                          href={listing.seller_website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-cyan-600 dark:text-cyan-400 hover:underline break-all inline-block"
                          data-testid="seller-public-website"
                        >
                          {listing.seller_website}
                        </a>
                      )}
                    </div>
                  )}

                  {/* Seller Reputation Breakdown */}
                  <SellerReputationCard sellerId={listing.seller_id} />

                  {/* Recent Reviews */}
                  <SellerReviewsList sellerId={listing.seller_id} />

                  {/* View all reviews link */}
                  <LangLink
                    to={`/store/${listing.seller_id}`}
                    className="block text-center text-sm font-medium text-cyan-600 dark:text-cyan-400 hover:underline pt-1"
                    data-testid="view-all-reviews-link"
                  >
                    View all reviews &rarr;
                  </LangLink>
                </CardContent>
              </Card>
            )}

            <Card className="glassmorphism">
              <CardHeader>
                <CardTitle className="text-lg">Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{getLocalized(listing, 'description')}</p>
              </CardContent>
            </Card>

            {/* FEATURE PATCH v9 / Feature 2 — Logistics details (Visit, Shipping, Pickup, Item Details, Quantity) */}
            <ListingLogisticsDetails listing={listing} />

            {bids.length > 0 && (
              <Card className="glassmorphism">
                <CardHeader>
                  <CardTitle className="text-lg">{t('listing.bidHistory', 'Bid History')}</CardTitle>
                </CardHeader>
                <CardContent>
                  {/* iter371 — Masked bid history (Law 25 / PIPEDA compliant):
                      shows initials only + masked IP + relative time. */}
                  <MaskedBidHistory listingId={id} limit={20} />
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      <PromotionManagerModal
        open={showPromotionModal}
        onClose={() => setShowPromotionModal(false)}
        listingId={listing?.id}
        listingTitle={listing?.title}
      />

      {/* Pay-As-You-Go Promotion Checkout */}
      {showPromoModal && (
        <ListingPromotionModal
          onClose={() => setShowPromoModal(false)}
          listingId={listing?.id}
          listingTitle={listing?.title}
          listingType={
            listing?.is_multi_item || listing?.listing_type === 'lots' ? 'lots' : 'marketplace'
          }
        />
      )}
      {/* Message Seller Modal */}
      {listing && (
        <MessageSellerModal
          isOpen={messageModalOpen}
          onClose={() => setMessageModalOpen(false)}
          sellerId={listing.seller_id}
          listingId={listing.id}
          listingTitle={listing.title}
        />
      )}

      {/* Rate Seller Modal */}
      {listing && (
        <RateSellerModal
          isOpen={rateSellerModalOpen}
          onClose={() => setRateSellerModalOpen(false)}
          sellerId={listing.seller_id}
          auctionId={listing.id}
          auctionType="single"
          auctionTitle={listing.title}
        />
      )}

      {/* Photo Lightbox — iter369 enhanced with Zoom + Counter plugins */}
      {lightboxOpen && listing?.images && (
        <Lightbox
          open={lightboxOpen}
          close={() => setLightboxOpen(false)}
          slides={listing.images.map(img => ({ src: img }))}
          index={photoIndex}
          plugins={[Zoom, Counter]}
          carousel={{ finite: false, preload: 2 }}
          animation={{ fade: 260, swipe: 400 }}
          zoom={{ maxZoomPixelRatio: 4, scrollToZoom: true, doubleClickMaxStops: 2 }}
          counter={{ container: { style: { top: 'unset', bottom: 16, right: 16, left: 'unset' } } }}
          styles={{
            container: {
              backgroundColor: 'rgba(0, 0, 0, 0.96)',
              position: 'fixed', inset: 0, width: '100vw', height: '100vh', zIndex: 9999,
            },
          }}
        />
      )}

      {/* Bid Confirmation Dialog with Cost Breakdown */}
      <BidConfirmationDialog
        isOpen={bidConfirmDialogOpen}
        onClose={() => {
          setBidConfirmDialogOpen(false);
          setPendingBidAmount(0);
        }}
        onConfirm={confirmPlaceBid}
        bidAmount={pendingBidAmount}
        quantity={listing?.quantity || 1}
        multiplyByQuantity={!!listing?.multiply_hammer_by_quantity}
        listingTitle={listing?.title}
        category={listing?.category || 'general'}
        sellerIsBusiness={seller?.is_tax_registered || seller?.account_type === 'business' || false}
        buyerTier={user?.subscription_tier || 'basic'}
        sellerTier={seller?.subscription_tier || 'basic'}
        region={listing?.region || 'QC'}
        loading={placingBid}
        buyersPremiumRate={listing?.custom_buyer_premium_rate}
        currency={listing?.currency || 'CAD'}
        paymentMethod={listing?.payment_method || 'stripe'}
        requiresDeposit={!!listing?.requires_deposit}
        depositAmount={listing?.deposit_amount || 0}
        depositType={listing?.deposit_type || 'fixed'}
      />

      {/* Cross-Border Bid Intercept Modal */}
      <CrossBorderBidModal
        isOpen={crossBorderModalOpen}
        onAccept={() => {
          setCrossBorderAccepted(true);
          setCrossBorderModalOpen(false);
          // Resume bid flow
          setBidConfirmDialogOpen(true);
        }}
        onCancel={() => {
          setCrossBorderModalOpen(false);
          setPendingBidAmount(0);
        }}
      />
    </div>
  );
};

export default function ListingDetailPageWithErrorBoundary(props) {
  return (
    <ErrorBoundary scope="listing-detail">
      <ListingDetailPage {...props} />
    </ErrorBoundary>
  );
}
