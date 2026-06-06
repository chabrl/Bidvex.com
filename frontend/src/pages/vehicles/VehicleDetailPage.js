import API_BASE from '../../config';
import ErrorBoundary from '../../components/ErrorBoundary';
/**
 * Vehicle Detail Page
 * Shows full vehicle details with live bidding panel
 * Includes trust indicators, legal disclaimers, and transparent auction rules
 */

import React, { useState, useEffect, useCallback } from 'react';
import SafeImage from '../../components/SafeImage';
import VehicleBidPanel from '../../components/broker/VehicleBidPanel';
import ListingJsonLd from '../../components/seo/ListingJsonLd';
import { useMetaPixelTracking } from '../../hooks/useMetaPixelTracking';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { authHeaders } from '../../utils/authToken';
import axios from 'axios';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Separator } from '../../components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import { Checkbox } from '../../components/ui/checkbox';
import {
  Car, Clock, MapPin, Gauge, Fuel, Settings2, Calendar,
  DollarSign, ChevronLeft, ChevronRight, Shield, Award,
  AlertTriangle, FileText, Camera, CheckCircle, XCircle,
  User, Building2, Zap, TrendingUp, Eye, History, Gavel,
  CreditCard, Lock, Info, Calculator, Star, Scale
} from 'lucide-react';
import useVehicleBidding from '../../hooks/useVehicleBidding';
import { PricingEstimate } from '../../components/vehicles/PricingBreakdown';
import ListingLogisticsDetails from '../../components/ListingLogisticsDetails';
import MessageSellerModal from '../../components/MessageSellerModal';
import { MessageSquare, ShieldCheck } from 'lucide-react';
import VehicleLegalFooter from '../../components/vehicles/VehicleLegalFooter';
import VehicleBuyerGateModal from '../../components/vehicles/VehicleBuyerGateModal';
import VehicleProvinceEligibilityDisplay from '../../components/vehicles/VehicleProvinceEligibilityDisplay';
// iter202 Phase B — new detail-page primitives (breadcrumb, gallery+lightbox, acq-cost, related)
import {
  VehicleBreadcrumb,
  VehiclePhotoGallery,
  VehicleAcquisitionCost,
  RelatedVehicles,
} from '../../components/vehicles/VehicleDetailPieces';
import { CostBreakdown } from '../../components/CostBreakdown'; // iter210 Step 6

// Trust & Legal Components
import {
  TrustIndicators,
  SellerTypeBadge,
  VerifiedSellerBadge,
  TitleStatusBadge,
  VINVerifiedBadge,
  SellerRatingBadge,
  ReserveStatusBadge,
  RunningStatusBadge,
  NoReserveBadge,
  LiveAuctionBadge,
  EndingSoonBadge
} from '../../components/vehicles/TrustBadges';
import { PricingCalculator, PricingEstimateInline } from '../../components/vehicles/PricingCalculator';
import {
  AsIsWhereIsDisclaimer,
  PlatformRoleDisclaimer,
  InspectionReminder,
  PaymentTermsDisplay,
  BindingBidNotice,
  TermsAcceptanceDialog,
  DepositNotice,
  LegalFooter
} from '../../components/vehicles/LegalDisclaimers';
import {
  AntiSnipingNotice,
  AntiSnipingRulesCard,
  MinimumBidDisplay,
  BidHistory,
  ReserveStatusDisplay,
  ActiveBiddersCount,
  AuctionRulesSummary,
  LiveStatusIndicator
} from '../../components/vehicles/AuctionRulesDisplay';
import { formatListingPrice } from '../../utils/currencyFormatter';
import SecurityDepositBanner from '../../components/SecurityDepositBanner';
import ListingPromotionModal from '../../components/ListingPromotionModal';

const API = API_BASE;

// Format helpers — uses listing currency
const formatPrice = (price, currency = 'CAD') => {
  return formatListingPrice(price, currency);
};

const formatMileage = (mileage) => {
  return new Intl.NumberFormat('en-CA').format(mileage) + ' km';
};

// Condition badge color
const getConditionColor = (condition) => {
  switch (condition) {
    case 'excellent': return 'bg-green-500';
    case 'good': return 'bg-blue-500';
    case 'fair': return 'bg-yellow-500';
    case 'poor': return 'bg-red-500';
    default: return 'bg-slate-400';
  }
};

// Image Gallery Component
const ImageGallery = ({ media = [] }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const photos = media.filter(m => m.type === 'photo');
  
  if (photos.length === 0) {
    return (
      <div className="aspect-[16/10] bg-slate-100 dark:bg-slate-800 rounded-xl flex items-center justify-center">
        <Car className="h-24 w-24 text-slate-300" />
      </div>
    );
  }
  
  return (
    <div className="space-y-4">
      {/* Main Image */}
      <div className="relative aspect-[16/10] bg-slate-100 dark:bg-slate-800 rounded-xl overflow-hidden">
        <SafeImage
          src={photos[currentIndex]?.url}
          alt={`Vehicle photo ${currentIndex + 1}`}
          className="w-full h-full object-cover"
        />
        
        {/* Navigation Arrows */}
        {photos.length > 1 && (
          <>
            <button
              onClick={() => setCurrentIndex(i => (i - 1 + photos.length) % photos.length)}
              className="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 bg-black/50 hover:bg-black/70 rounded-full flex items-center justify-center text-white transition-colors"
            >
              <ChevronLeft className="h-6 w-6" />
            </button>
            <button
              onClick={() => setCurrentIndex(i => (i + 1) % photos.length)}
              className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 bg-black/50 hover:bg-black/70 rounded-full flex items-center justify-center text-white transition-colors"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          </>
        )}
        
        {/* Counter */}
        <div className="absolute bottom-4 right-4 bg-black/70 text-white text-sm px-3 py-1 rounded-full">
          <Camera className="h-4 w-4 inline mr-1" />
          {currentIndex + 1} / {photos.length}
        </div>
        
        {/* Category Badge */}
        {photos[currentIndex]?.category && (
          <Badge className="absolute top-4 left-4 bg-white/90 text-slate-900">
            {photos[currentIndex].category.replace('_', ' ')}
          </Badge>
        )}
      </div>
      
      {/* Thumbnails */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {photos.map((photo, index) => (
          <button
            key={photo.id || index}
            onClick={() => setCurrentIndex(index)}
            className={`flex-shrink-0 w-20 h-14 rounded-lg overflow-hidden border-2 transition-all ${
              index === currentIndex 
                ? 'border-blue-500 ring-2 ring-blue-500/30' 
                : 'border-transparent hover:border-slate-300'
            }`}
          >
            <SafeImage src={photo.url} alt="" className="w-full h-full object-cover" />
          </button>
        ))}
      </div>
    </div>
  );
};

// Bidding Panel Component
const BiddingPanel = ({ vehicle, onBidPlaced }) => {
  const { user, token } = useAuth();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  // iter230 — centralized Meta Pixel tracking (replaces scattered dynamic imports)
  const { trackViewContent, trackAddToCart, trackBidSubmitted } =
    useMetaPixelTracking({ routeHint: 'vehicle' });
  const [bidAmount, setBidAmount] = useState('');
  const [bidding, setBidding] = useState(false);
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [depositPaid, setDepositPaid] = useState(false);
  const [depositAuthorized, setDepositAuthorized] = useState(false);
  const [showBuyNowModal, setShowBuyNowModal] = useState(false);
  const [buyNowPreview, setBuyNowPreview] = useState(null);
  const [buyNowLoading, setBuyNowLoading] = useState(false);
  const [buyNowProcessing, setBuyNowProcessing] = useState(false);
  // iter194 — Dealer license verification status (for licensed_only auctions)
  const [dealerLicenseStatus, setDealerLicenseStatus] = useState(null);

  // Fetch dealer license status if needed
  useEffect(() => {
    if (!user || !vehicle || vehicle.auction_access !== 'licensed_only') return;
    axios.get(`${API}/dealer-licenses/me`, { headers: authHeaders() })
      .then((r) => setDealerLicenseStatus(r.data?.status || 'none'))
      .catch(() => setDealerLicenseStatus('none'));
  }, [user, vehicle]);

  const isLicensedOnly = vehicle?.auction_access === 'licensed_only';
  const isLicenseVerified = dealerLicenseStatus === 'approved';
  
  // Real-time bidding data
  const { 
    currentBid, 
    bidCount, 
    timeRemaining, 
    reserveMet, 
    connected 
  } = useVehicleBidding(vehicle?.id, !!vehicle, vehicle);
  
  // Use real-time data or fallback to vehicle data
  const displayBid = currentBid || vehicle?.current_bid || vehicle?.starting_price || 0;
  const displayBidCount = bidCount || vehicle?.bid_count || 0;
  const minBid = Math.max(
    vehicle?.starting_price || 0,
    displayBid + (vehicle?.bid_increment || 100)
  );
  
  useEffect(() => {
    if (displayBid > 0) {
      setBidAmount(minBid.toString());
    }
  }, [minBid, displayBid]);

  const handleBid = async () => {
    if (!user) {
      navigate('/auth');
      return;
    }

    if (!termsAccepted) {
      setShowTermsModal(true);
      return;
    }

    // iter201 — Phase 3 / 3A — Province-aware buyer gate (skip parts_accessories per CEO #3)
    const isPartsListing = (vehicle?.category_id || '').toLowerCase() === 'parts_accessories';
    if (!isPartsListing && !buyerGateCleared) {
      try {
        const r = await axios.get(
          `${API}/vehicles/buyer-verification/me?listing_id=${encodeURIComponent(vehicle.id)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        const gs = r?.data?.gate_state;
        const sessionDismissed = (() => {
          try { return sessionStorage.getItem(`bidvex.buyer_gate.dismissed.${r?.data?.province}`) === '1'; } catch (_) { return false; }
        })();
        const cleared = gs === 'verified' || gs === 'qc_disclosure_acked' || (gs === 'open' && sessionDismissed) || gs === 'territory_advisory';
        if (!cleared) {
          setShowBuyerGateModal(true);
          return;
        }
        setBuyerGateCleared(true);
      } catch (_) {
        // Soft-fail: open modal which will fetch the state itself
        setShowBuyerGateModal(true);
        return;
      }
    }

    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount < minBid) {
      toast.error(`Minimum bid is ${formatPrice(minBid, vehicle?.currency)}`);
      return;
    }

    // Meta Pixel AddToCart — bid intent. Routes through useMetaPixelTracking
    // so content_ids[0] is always the canonical listing.id UUID.
    trackAddToCart({ listing: vehicle, bidAmount: amount });

    setBidding(true);
    try {
      // Check deposit if required
      if (vehicle.requires_deposit && !depositPaid) {
        const depositResp = await axios.post(
          `${API}/vehicle-bids/deposit?vehicle_id=${vehicle.id}`,
          {},
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (depositResp.data.message) {
          setDepositPaid(true);
          toast.success(
            i18n.language === 'fr'
              ? 'Retenue autorisée — 500 $ réservés sur votre carte'
              : 'Hold Authorized — $500 reserved on your card'
          );
        }
      }
      
      // Place bid
      const response = await axios.post(`${API}/vehicle-bids`, {
        vehicle_id: vehicle.id,
        amount,
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(`Bid placed: ${formatPrice(amount, vehicle?.currency)}`);
      // Meta Pixel InitiateCheckout — fires on every successful bid commit.
      trackBidSubmitted({ listing: vehicle, bidAmount: amount });
      onBidPlaced?.(response.data);
      // iter202 Phase B — auto-set the next bid amount using +$100 vehicle increment
      setBidAmount((amount + 100).toString());
      
    } catch (error) {
      const detail = error.response?.data?.detail;
      let message = 'Failed to place bid';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map(e => (typeof e === 'string' ? e : e?.msg || '')).filter(Boolean).join(', ') || message;
      } else if (detail && typeof detail === 'object') {
        message = detail.msg || JSON.stringify(detail);
      }
      toast.error(message);
    } finally {
      setBidding(false);
    }
  };

  const acceptTerms = async () => {
    try {
      await axios.post(`${API}/vehicles/${vehicle.id}/accept-terms`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTermsAccepted(true);
      setShowTermsModal(false);
      toast.success('Terms accepted');
    } catch (error) {
      toast.error('Failed to accept terms');
    }
  };

  const isEnded = timeRemaining?.ended || 
    (vehicle?.end_time && new Date(vehicle.end_time) < new Date());

  return (
    <>
      {/* iter202 Phase B — sticky on desktop (top: 80px per spec) */}
      <Card className="lg:sticky lg:top-20 border-2 border-blue-100 dark:border-blue-900 shadow-xl">
        <CardHeader className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-t-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm">Current Bid</p>
              <p className="text-3xl font-bold">{formatPrice(displayBid, vehicle?.currency)}</p>
            </div>
            {connected && (
              <Badge className="bg-green-500 animate-pulse">
                <Zap className="h-3 w-3 mr-1" /> LIVE
              </Badge>
            )}
          </div>
          
          {/* Time Remaining */}
          <div className="mt-4 bg-white/10 rounded-lg p-3">
            <div className="flex items-center gap-2 text-blue-100 text-sm mb-1">
              <Clock className="h-4 w-4" />
              Time Remaining
            </div>
            {isEnded ? (
              <p className="text-xl font-bold text-red-300">Auction Ended</p>
            ) : timeRemaining ? (
              /* iter283-responsive — equal-width countdown grid so the
                  timer fits in one row at 375px. */
              <div className="grid grid-cols-4 gap-1 sm:gap-2 w-full">
                <div className="text-center min-w-0">
                  <p className="text-xl sm:text-2xl font-bold text-white truncate">{timeRemaining.days || 0}</p>
                  <p className="text-[10px] sm:text-xs text-blue-200">Days</p>
                </div>
                <div className="text-center min-w-0">
                  <p className="text-xl sm:text-2xl font-bold text-white truncate">{timeRemaining.hours}</p>
                  <p className="text-[10px] sm:text-xs text-blue-200">Hours</p>
                </div>
                <div className="text-center min-w-0">
                  <p className="text-xl sm:text-2xl font-bold text-white truncate">{timeRemaining.minutes}</p>
                  <p className="text-[10px] sm:text-xs text-blue-200">Min</p>
                </div>
                <div className="text-center min-w-0">
                  <p className="text-xl sm:text-2xl font-bold text-white truncate">{timeRemaining.seconds}</p>
                  <p className="text-[10px] sm:text-xs text-blue-200">Sec</p>
                </div>
              </div>
            ) : (
              <p className="text-xl font-bold">Loading...</p>
            )}
          </div>
        </CardHeader>
        
        <CardContent className="p-6 space-y-4">
          {/* Stats */}
          <div className="grid grid-cols-2 gap-4 text-center">
            <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{displayBidCount}</p>
              <p className="text-sm text-slate-500">Bids</p>
            </div>
            <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3">
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{vehicle?.views_count || 0}</p>
              <p className="text-sm text-slate-500">Views</p>
            </div>
          </div>
          
          {/* Reserve Status */}
          {vehicle?.reserve_price && (
            <div className={`p-3 rounded-lg ${reserveMet || vehicle?.reserve_met ? 'bg-green-50 border border-green-200' : 'bg-yellow-50 border border-yellow-200'}`}>
              {reserveMet || vehicle?.reserve_met ? (
                <p className="text-green-700 font-medium flex items-center gap-2">
                  <CheckCircle className="h-5 w-5" /> Reserve Met
                </p>
              ) : (
                <p className="text-yellow-700 font-medium flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5" /> Reserve Not Met
                </p>
              )}
            </div>
          )}
          
          {/* iter285 — Bug 4 — Provincial registration eligibility for buyers.
              Renders below the bid panel so a buyer sees whether they can
              register the vehicle in their home province BEFORE bidding. */}
          <VehicleProvinceEligibilityDisplay
            listing={vehicle}
            buyerProvince={user?.profile?.province || user?.province}
            isFr={(i18n.language || '').toLowerCase().startsWith('fr')}
          />

          {/* Bid Input */}
          {!isEnded && (
            <div className="space-y-3">
              {/* iter229 — System-Proxy Compliance Gateway (vehicle-only) */}
              <VehicleBidPanel
                listingId={vehicle?.id}
                vehicleProvince={vehicle?.seller_province || vehicle?.province}
                currentHighestBid={vehicle?.current_bid || 0}
                lang={i18n.language?.startsWith('fr') ? 'fr' : 'en'}
                onBidSuccess={() => { try { window.location.reload(); } catch {} }}
              />

              {/* Security Deposit Banner for High-Value Vehicles */}
              <SecurityDepositBanner
                listingId={vehicle?.id}
                startingPrice={vehicle?.starting_price || 0}
                currency={vehicle?.currency || 'CAD'}
                onDepositStatusChange={setDepositAuthorized}
              />
              
              {/* iter258 Mission 3 — Broker Partnership gate for individual users.
                  Vehicles require a licensed broker or active broker partnership.
                  Hide the bid input + Quick Bid CTA and render an actionable
                  callout when the user is an individual with no broker link. */}
              {user && (
                ((user.account_type || 'individual').toLowerCase() === 'individual')
                && !user.is_broker_partner
                && !user.broker_id
                && (user.role !== 'admin')
              ) ? (
                <div
                  className="rounded-[10px] p-5 mb-4"
                  style={{
                    border: '2px solid #f6c90e',
                    backgroundColor: '#fffbeb',
                  }}
                  data-testid="vehicle-broker-gate"
                >
                  <p className="font-extrabold text-[#0a1628] mb-2" style={{ fontSize: 16 }}>
                    🚗 {t('vehicle.brokerGateTitle', 'Broker Partnership Required')}
                  </p>
                  <p className="mb-4" style={{ fontSize: 13, color: '#4a5568', lineHeight: 1.7 }}>
                    {t(
                      'vehicle.brokerGateBody',
                      'Vehicle auctions on BidVex are exclusively available to licensed broker partners or individuals linked to a verified broker, in compliance with Canadian provincial regulations (SAAQ, OMVIC, AMVIC, VSA).',
                    )}
                  </p>
                  {/* iter283-responsive — Stack CTAs on mobile, side-by-side at sm+. */}
                  <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2">
                    <Button
                      onClick={() => navigate('/become-a-broker')}
                      style={{ backgroundColor: '#0055FF', color: 'white' }}
                      className="font-bold w-full sm:w-auto"
                      data-testid="vehicle-broker-gate-become-cta"
                    >
                      {t('vehicle.becomeBroker', 'Become a Broker Partner')}
                    </Button>
                    <Button
                      onClick={() => navigate('/how-it-works#brokers')}
                      variant="outline"
                      style={{
                        border: '1.5px solid #0055FF',
                        color: '#0055FF',
                        backgroundColor: 'transparent',
                      }}
                      className="font-bold w-full sm:w-auto"
                      data-testid="vehicle-broker-gate-learn-cta"
                    >
                      {t('vehicle.learnMore', 'Learn More')}
                    </Button>
                  </div>
                </div>
              ) : (
              <>
              <div>
                <label className="text-sm text-slate-500 mb-1 block">Your Bid</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                  <Input
                    type="number"
                    value={bidAmount}
                    onChange={(e) => setBidAmount(e.target.value)}
                    className="pl-10 text-lg font-semibold"
                    min={minBid}
                    step={100}
                    disabled={(vehicle?.starting_price || 0) >= 10000 && !depositAuthorized}
                    data-testid="bid-input"
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Minimum bid: {formatPrice(minBid, vehicle?.currency)} (increment: {formatPrice(100, vehicle?.currency)})
                </p>
              </div>

              {/* iter202 Phase B — Quick-bid increments (+$100 / +$500 / +$1,000)
                  iter283-responsive — flex-wrap + justify-center so the
                  three pills never overflow on narrow viewports. */}
              <div className="flex flex-wrap gap-2 justify-center" data-testid="bid-quick-chips">
                {[100, 500, 1000].map((inc) => (
                  <button
                    key={inc}
                    type="button"
                    onClick={() => {
                      const base = parseFloat(bidAmount || minBid || 0);
                      const next = (Number.isFinite(base) ? base : minBid) + inc;
                      setBidAmount(String(Math.round(next)));
                    }}
                    className="flex-1 min-w-[90px] text-sm font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-cyan-500 hover:text-cyan-700 hover:bg-cyan-50 dark:hover:bg-cyan-950/40 py-2 transition-colors"
                    data-testid={`bid-quick-plus-${inc}`}
                  >
                    +${inc.toLocaleString()}
                  </button>
                ))}
              </div>

              {/* iter202 Phase B — Total Acquisition Cost (gross-up estimate)
                  iter283-bid-panel-dedup — This is the ONE breakdown that
                  renders during the bidding flow on a broker-required
                  vehicle. It shows the buyer EXACTLY what BidVex will
                  charge them (platform fee + QC tax on fee + Stripe
                  processing), and an "Est. total to acquire" line that
                  adds the hammer price for context. The seller is paid
                  the hammer price directly out-of-band.

                  The full invoice-style `<CostBreakdown />` (Hammer Price
                  → Total Charged) is intentionally REMOVED from the bid
                  panel — it conflicts mathematically (compounds tax on
                  the full hammer price instead of just on the unlock
                  fee) and rendering both side-by-side breaks payment
                  transparency. The full invoice still ships on the
                  post-win Checkout/Invoice surfaces where it's
                  legally accurate. */}
              {bidAmount && parseFloat(bidAmount) > 0 && (
                <VehicleAcquisitionCost
                  bid={parseFloat(bidAmount)}
                  currency={vehicle?.currency || 'CAD'}
                  province={vehicle?.location_province || 'ON'}
                />
              )}
              
              <Button 
                onClick={handleBid}
                disabled={bidding || !user || ((vehicle?.starting_price || 0) >= 10000 && !depositAuthorized) || (isLicensedOnly && !isLicenseVerified)}
                className="w-full h-14 text-lg bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800"
                style={i18n.language === 'fr' ? { letterSpacing: '-0.02em' } : {}}
                data-testid="place-bid-btn"
              >
                {bidding ? (
                  <>{t('common.processing', 'Processing...')}</>
                ) : !user ? (
                  <>{t("auction.loginToBid")}</>
                ) : (isLicensedOnly && !isLicenseVerified) ? (
                  <span className="flex items-center gap-2" data-testid="bid-btn-license-required">
                    <Shield className="h-5 w-5" />
                    {t('vehicleDealer.licenseRequired')}
                  </span>
                ) : ((vehicle?.starting_price || 0) >= 10000 && !depositAuthorized) ? (
                  // iter283-deposit-btn-fit — Compact, locale-aware copy.
                  // The legacy button stacked EN + FR translations into a
                  // single CTA, which overflowed both sides on 375px
                  // viewports (clipped to "Security Hold Requir" /
                  // "Retenue de sécurité requ"). Now: single language
                  // per render + short headline + amount on a second
                  // line. `min-w-0` + `break-words` so no future copy
                  // change re-introduces the clip.
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
                    <Gavel className="h-5 w-5 mr-2" />
                    {t('bid.placeBid', 'Place Bid')}
                  </>
                )}
              </Button>

              {/* iter194 — Licensed-only gate: prompt verification if not approved */}
              {isLicensedOnly && !isLicenseVerified && user && (
                <div className="mt-2 p-3 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/30 text-xs" data-testid="licensed-only-gate">
                  <p className="font-semibold text-amber-900 dark:text-amber-200 mb-1 flex items-center gap-1">
                    🔒 {t('vehicleDealer.licensedOnlyBadge')}
                  </p>
                  <p className="text-amber-800 dark:text-amber-300 mb-2">{t('vehicleDealer.licensedOnlyTooltip')}</p>
                  <Button
                    size="sm"
                    onClick={() => navigate('/vehicle-auctions/dealer-license')}
                    className="bg-blue-600 hover:bg-blue-700 text-white"
                    data-testid="verify-dealer-license-btn"
                  >
                    {t('vehicleDealer.verifyMyLicense')}
                  </Button>
                </div>
              )}
              
              {/* Buy Now */}
              {vehicle?.buy_now_price && displayBid < vehicle.buy_now_price && (
                <Button
                  variant="outline"
                  className="w-full h-12"
                  onClick={() => setShowBuyNowModal(true)}
                  data-testid="vehicle-buy-now-btn"
                >
                  {t('bid.buyNow', 'Buy Now')}: {formatPrice(vehicle.buy_now_price, vehicle?.currency)}
                </Button>
              )}
              </>
              )}
            </div>
          )}
          
          {/* Trust Badges */}
          <div className="grid grid-cols-2 gap-2 pt-4 border-t">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Shield className="h-4 w-4 text-green-500" />
              <span>{t("auction.buyerProtection")}</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Lock className="h-4 w-4 text-blue-500" />
              <span>{t("auction.securePayment")}</span>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Terms Modal */}
      <Dialog open={showTermsModal} onOpenChange={setShowTermsModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Bidding Terms & Conditions
            </DialogTitle>
            <DialogDescription>
              Please read and accept the following terms before placing your bid.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 my-4">
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <h4 className="font-semibold text-yellow-800 mb-2">As-Is, Where-Is</h4>
              <p className="text-sm text-yellow-700">
                All vehicles are sold &quot;As-Is, Where-Is&quot; without warranty. 
                BidVex is not the seller and makes no guarantees about vehicle condition.
              </p>
            </div>
            
            <div className="bg-slate-50 rounded-lg p-4 text-sm space-y-2">
              <p>By bidding, you acknowledge that:</p>
              <ul className="list-disc list-inside space-y-1 text-slate-600">
                <li>{t("vehicles.inspectVehicle")}</li>
                <li>{t("vehicles.sellerDisclosure")}</li>
                <li>BidVex does not handle title transfer or delivery</li>
                <li>{t("auction.allBidsLegallyBinding")}</li>
                <li>Deposits are refundable only to non-winning bidders</li>
              </ul>
            </div>
            
            <div className="flex items-start gap-3">
              <Checkbox 
                id="accept-terms"
                checked={termsAccepted}
                onCheckedChange={setTermsAccepted}
              />
              <label htmlFor="accept-terms" className="text-sm">
                I have read and accept the bidding terms, and I understand this is a binding agreement.
              </label>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowTermsModal(false)}>
              Cancel
            </Button>
            <Button onClick={acceptTerms} disabled={!termsAccepted}>
              Accept & Continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Vehicle Buy Now Modal */}
      <Dialog open={showBuyNowModal} onOpenChange={(o) => {
        setShowBuyNowModal(o);
        if (!o) { setBuyNowPreview(null); }
      }}>
        <DialogContent className="max-w-lg" data-testid="vehicle-buy-now-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-amber-500" />
              {t('bid.buyNowConfirm', 'Buy Now — Confirm')}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {t('vehicle.buyNowNotice',
                "BidVex never collects the vehicle price. Only the 2.5% platform fee (+ Stripe + tax) is charged now. You pay the seller directly for the vehicle."
              )}
              <br />
              <span className="text-[11px] opacity-80">
                BidVex ne perçoit jamais le prix du véhicule. Seuls les frais de plateforme de 2,5 % (+ Stripe + taxes) sont facturés maintenant. Vous payez le véhicule directement au vendeur.
              </span>
            </DialogDescription>
          </DialogHeader>
          <VehicleBuyNowBody
            vehicle={vehicle}
            preview={buyNowPreview}
            setPreview={setBuyNowPreview}
            loading={buyNowLoading}
            setLoading={setBuyNowLoading}
            processing={buyNowProcessing}
            setProcessing={setBuyNowProcessing}
            formatPrice={formatPrice}
            onClose={() => setShowBuyNowModal(false)}
          />
        </DialogContent>
      </Dialog>
    </>
  );
};

// Vehicle Buy Now body — fetches 2.5% fee preview + executes checkout
const VehicleBuyNowBody = ({ vehicle, preview, setPreview, loading, setLoading, processing, setProcessing, formatPrice, onClose }) => {
  const { t } = useTranslation();
  const API = `${API_BASE}/api`;

  React.useEffect(() => {
    if (!vehicle?.id || preview) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await axios.post(
          `${API}/payments/vehicle-buy-now-preview`,
          { listing_id: vehicle.id },
          { headers: authHeaders() },
        );
        if (!cancelled) setPreview(r.data);
      } catch (err) {
        if (!cancelled) toast.error(err?.response?.data?.detail || t('common.error'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [vehicle?.id]);

  const submit = async () => {
    setProcessing(true);
    try {
      const r = await axios.post(
        `${API}/payments/vehicle-buy-now-checkout`,
        { listing_id: vehicle.id },
        { headers: authHeaders() },
      );
      if (r.data?.requires_checkout && r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
        return;
      }
      toast.success(t('bid.buyNowSuccess', 'Vehicle purchased. Check your email for next steps.'));
      onClose();
      setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
      toast.error(err?.response?.data?.detail || t('common.error'));
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">{t('common.loading', 'Loading...')}</div>;
  }
  if (!preview) return null;

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
        <div className="flex justify-between items-center text-sm">
          <span>{t('bid.buyNowPrice', 'Buy Now Price (paid to seller directly)')}</span>
          <span className="font-bold">{formatPrice(preview.buy_now_price, vehicle?.currency)}</span>
        </div>
        <p className="text-[11px] text-muted-foreground mt-1">
          {t('vehicle.hammerDirect', 'Not charged by BidVex. The province-licensed dealer collects this directly.')}
        </p>
      </div>

      <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 space-y-1.5 text-xs">
        <div className="flex justify-between">
          <span>{t('bid.platformFee', 'Platform fee')} (2.5%)</span>
          <span>${preview.platform_fee.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>{t('bid.stripeRecovery', 'Stripe processing')}</span>
          <span>${preview.stripe_recovery.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>{preview.tax_label}</span>
          <span>${preview.tax_amount.toFixed(2)}</span>
        </div>
        <Separator />
        <div className="flex justify-between font-bold text-sm pt-1">
          <span>{t('bid.totalPlatformFee', 'Total charged now')}</span>
          <span>${preview.total_platform_fee.toFixed(2)}</span>
        </div>
      </div>

      {preview.has_deposit && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 text-xs space-y-1">
          <p className="font-semibold text-emerald-700 dark:text-emerald-400">
            {t('vehicle.depositCapture', 'Deposit on file')}: ${preview.deposit_amount.toFixed(2)}
          </p>
          <p>{t('vehicle.willCaptureFromDeposit', 'Captured from deposit')}: ${preview.will_capture_from_deposit.toFixed(2)}</p>
          {preview.will_charge_card_additional > 0 ? (
            <p>{t('vehicle.willChargeCard', 'Extra charged to card on file')}: ${preview.will_charge_card_additional.toFixed(2)}</p>
          ) : (
            <p>{t('vehicle.remainderReleased', 'Remainder of deposit auto-released back to your card.')}</p>
          )}
        </div>
      )}

      <DialogFooter className="gap-2">
        <Button variant="outline" onClick={onClose} disabled={processing} data-testid="vehicle-buy-now-cancel">
          {t('common.cancel', 'Cancel')}
        </Button>
        <Button onClick={submit} disabled={processing} data-testid="vehicle-buy-now-confirm">
          {processing ? t('common.processing', 'Processing...') : t('bid.confirmBuyNow', 'Confirm Buy Now')}
        </Button>
      </DialogFooter>
    </div>
  );
};



// iter202 Phase B — Mobile fixed-bottom bid bar
// Hidden on desktop. On mobile, becomes invisible when the full BidPanel is in view.
const MobileBidBar = ({ vehicle, onBidClick }) => {
  const { t } = useTranslation();
  const [hidden, setHidden] = React.useState(false);

  React.useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    // Sentinel = the bid input inside the desktop bid panel
    const sentinel = document.querySelector('[data-testid="vehicle-detail-bid-column"]') ||
                     document.querySelector('[data-testid="bid-input"]');
    if (!sentinel) return;
    const io = new IntersectionObserver(
      (entries) => {
        // When 25%+ of the bid column is visible → hide the mobile bar
        setHidden(entries.some((e) => e.isIntersecting && e.intersectionRatio > 0.25));
      },
      { threshold: [0, 0.25, 0.5, 1] }
    );
    io.observe(sentinel);
    return () => io.disconnect();
  }, [vehicle?.id]);

  const currentBid = vehicle?.current_bid > 0 ? vehicle.current_bid : (vehicle?.starting_price || 0);
  const currency = vehicle?.currency || 'CAD';

  return (
    <div
      className={`lg:hidden fixed bottom-0 left-0 right-0 z-30 bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 shadow-2xl transition-transform ${hidden ? 'translate-y-full' : 'translate-y-0'}`}
      data-testid="mobile-bid-bar"
      aria-hidden={hidden}
    >
      <div className="px-4 py-3 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {t('vehicleCard.currentBid', 'Current bid')}
          </p>
          <p className="text-base font-black text-[#0B2545] dark:text-cyan-300 leading-none mt-0.5 truncate">
            {formatListingPrice(currentBid, currency)}
          </p>
        </div>
        <button
          type="button"
          onClick={onBidClick}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#0B2545] hover:bg-[#0E2B52] text-white font-semibold text-sm px-4 py-2.5"
          data-testid="mobile-bid-bar-cta"
        >
          <Gavel className="h-4 w-4" />
          {t('bid.placeBid', 'Place Bid')}
        </button>
      </div>
    </div>
  );
};


// Main Page Component
const VehicleDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [vehicle, setVehicle] = useState(null);
  const [seller, setSeller] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showPromoModal, setShowPromoModal] = useState(false);
  // iter197 — Message Seller modal (winner-only after unlock fee paid)
  const [showMessageModal, setShowMessageModal] = useState(false);
  // iter201 — Phase 3 / 3A — Province-aware buyer gate
  const [showBuyerGateModal, setShowBuyerGateModal] = useState(false);
  const [buyerGateCleared, setBuyerGateCleared] = useState(false);

  // iter283-emergency-detail — `trackViewContent` was previously
  // referenced in `fetchVehicle` without being in lexical scope. It
  // belongs to a sibling component's hook call. The undefined
  // identifier threw ReferenceError synchronously inside the try
  // block, hit the catch, and surfaced as "Vehicle not found" even
  // on a 200 OK API response. Pulling the hook into the page-level
  // component fixes the crash AND keeps the Meta Pixel tracking we
  // already pay for (and the catalog feed parity per iter230 wiring).
  const { trackViewContent: trackVehicleView } =
    useMetaPixelTracking({ routeHint: 'vehicle' });

  const fetchVehicle = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/vehicles/${id}`);
      setVehicle(response.data);
      setSeller(response.data.seller);
      // Meta Pixel ViewContent — dedupe-safe per (listing, session).
      // Wrapped so a tracking failure NEVER kills the page render.
      try {
        trackVehicleView({ listing: response.data });
      } catch (_trackErr) {
        // Tracking is best-effort. Swallow.
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Vehicle not found');
    } finally {
      setLoading(false);
    }
  }, [id, trackVehicleView]);

  useEffect(() => {
    fetchVehicle();
  }, [fetchVehicle]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error || !vehicle) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Card className="p-8 text-center">
          <XCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">Vehicle Not Found</h2>
          <p className="text-slate-500 mb-4">{error}</p>
          <Button onClick={() => navigate('/vehicle-auctions')}>
            Back to Auctions
          </Button>
        </Card>
      </div>
    );
  }

  const condition = vehicle.condition_report || {};
  // iter202 Phase B — derive isEnded at top-level for the mobile fixed bar
  const isEnded = vehicle.end_time && new Date(vehicle.end_time) < new Date();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 overflow-x-hidden" data-testid="vehicle-detail-page">
      {/* iter231 — Schema.org Vehicle JSON-LD for Google Merchant + crawl alignment */}
      <ListingJsonLd listing={vehicle} canonicalUrl={`https://bidvex.com/vehicles/${vehicle.id}`} />
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b overflow-x-hidden">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-4">
          {/* iter202 Phase B — Breadcrumb (Home › Vehicle Auctions › Category › YMM)
              iter283-responsive — Scrolls horizontally on mobile rather
              than wrapping awkwardly. */}
          <div className="mb-3 overflow-x-auto whitespace-nowrap scrollbar-thin min-w-0">
            <VehicleBreadcrumb
              category={vehicle.category_id ? { id: vehicle.category_id, label_en: vehicle.category_label_en, label_fr: vehicle.category_label_fr } : null}
              vehicle={vehicle}
            />
          </div>
          <Button 
            variant="ghost" 
            onClick={() => navigate('/vehicle-auctions')}
            className="mb-2"
          >
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to Auctions
          </Button>
          
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-1">
                <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-900 dark:text-white break-words min-w-0">
                  {vehicle.year} {vehicle.make} {vehicle.model}
                </h1>
                {vehicle.auction_type === 'live' && <LiveAuctionBadge />}
              </div>
              {vehicle.trim && (
                <p className="text-base sm:text-lg text-slate-500 break-words">{vehicle.trim}</p>
              )}
            </div>
            
            {/* Trust Badges Header Row */}
            <div className="flex flex-wrap gap-2">
              <TitleStatusBadge status={vehicle.title_status} />
              <RunningStatusBadge isRunning={vehicle.condition_report?.is_running} />
              <VINVerifiedBadge vin={vehicle.vin} vinData={vehicle.vin_data} />
              {!vehicle.reserve_price && <NoReserveBadge />}
            </div>
          </div>
          
          {/* Seller Trust Indicators */}
          <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm text-slate-500">Seller:</span>
              <SellerTypeBadge sellerType={seller?.seller_type} size="sm" />
              <VerifiedSellerBadge isVerified={seller?.verification_status === 'approved'} />
              <SellerRatingBadge 
                rating={seller?.average_rating} 
                reviewCount={seller?.review_count}
                totalSold={seller?.total_sold}
              />
            </div>

            {/* iter189 Feature 2 — Vehicle Promote Button (owner-only, unpromoted only) */}
            {user && vehicle?.seller_user_id === user.id && !vehicle?.is_promoted && (
              <div className="mt-3 flex flex-wrap items-center gap-2" data-testid="promote-vehicle-section">
                <Button
                  size="sm"
                  onClick={() => setShowPromoModal(true)}
                  className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white border-0"
                  data-testid="promote-vehicle-btn"
                >
                  <TrendingUp className="mr-2 h-4 w-4" />
                  {i18n.language === 'fr' ? 'Promouvoir ce véhicule' : 'Promote This Vehicle'}
                </Button>
                <span className="text-xs text-slate-500">
                  {i18n.language === 'fr'
                    ? 'Augmentez la visibilité auprès des acheteurs.'
                    : 'Boost visibility and reach more buyers.'}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-3 sm:px-4 py-6 sm:py-8 pb-24 lg:pb-8 overflow-x-hidden">
        {/* iter202 Phase B — 60/40 split (5-col grid: 3 left + 2 right)
            iter283-responsive — Mobile: stacks (bid panel below content
            per spec); lg+: 60/40 sidebar layout. */}
        <div className="grid lg:grid-cols-5 gap-4 sm:gap-6 lg:gap-8">
          {/* Left Column - Images & Details (60%) */}
          <div className="lg:col-span-3 space-y-4 sm:space-y-6 min-w-0">
            {/* iter202 Phase B — VehiclePhotoGallery with lightbox (← → ESC swipe) */}
            <VehiclePhotoGallery
              media={(vehicle.media || []).filter(m => !m.type || m.type === 'photo')}
              title={`${vehicle.year || ''} ${vehicle.make || ''} ${vehicle.model || ''}`.trim()}
            />
            
            {/* Tabs */}
            <Tabs defaultValue="details">
              {/* iter283-responsive — Tab bar scrolls horizontally on
                  mobile instead of wrapping to two rows. */}
              <TabsList className="w-full justify-start bg-transparent flex flex-nowrap overflow-x-auto whitespace-nowrap scrollbar-thin">
                <TabsTrigger value="details" className="bg-transparent flex-shrink-0">Details</TabsTrigger>
                <TabsTrigger value="condition" className="bg-transparent flex-shrink-0">Condition</TabsTrigger>
                <TabsTrigger value="history" className="bg-transparent flex-shrink-0">Bid History</TabsTrigger>
                <TabsTrigger value="seller" className="bg-transparent flex-shrink-0">Seller</TabsTrigger>
                <TabsTrigger value="rules" className="bg-transparent flex-shrink-0">Auction Rules</TabsTrigger>
                <TabsTrigger value="pricing" className="bg-transparent flex-shrink-0">Pricing</TabsTrigger>
              </TabsList>
              
              {/* Details Tab */}
              <TabsContent value="details" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>{t("vehicles.vehicleSpecifications")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {/* iter283-responsive — 2/3/4 col grid per spec
                        (was 2/3 — needed an xl breakpoint). */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Year</p>
                        <p className="font-semibold">{vehicle.year}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Make</p>
                        <p className="font-semibold">{vehicle.make}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Model</p>
                        <p className="font-semibold">{vehicle.model}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Mileage</p>
                        <p className="font-semibold">{formatMileage(vehicle.mileage)}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Transmission</p>
                        <p className="font-semibold capitalize">{vehicle.transmission}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Fuel Type</p>
                        <p className="font-semibold capitalize">{vehicle.fuel_type}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Drivetrain</p>
                        <p className="font-semibold uppercase">{vehicle.drivetrain}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Exterior Color</p>
                        <p className="font-semibold">{vehicle.exterior_color}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-sm text-slate-500">Interior Color</p>
                        <p className="font-semibold">{vehicle.interior_color}</p>
                      </div>
                      {vehicle.engine_size && (
                        <div className="space-y-1">
                          <p className="text-sm text-slate-500">Engine</p>
                          <p className="font-semibold">{vehicle.engine_size}L {vehicle.cylinders ? `${vehicle.cylinders}cyl` : ''}</p>
                        </div>
                      )}
                      {vehicle.horsepower && (
                        <div className="space-y-1">
                          <p className="text-sm text-slate-500">Horsepower</p>
                          <p className="font-semibold">{vehicle.horsepower} HP</p>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
                
                {/* Description */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t("vehicles.description")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-slate-600 dark:text-slate-300 whitespace-pre-wrap">
                      {vehicle.description}
                    </p>
                    
                    {vehicle.features?.length > 0 && (
                      <div className="mt-4">
                        <h4 className="font-semibold mb-2">Features</h4>
                        <div className="flex flex-wrap gap-2">
                          {vehicle.features.map((feature, i) => (
                            <Badge key={i} variant="secondary">{feature}</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* FEATURE PATCH v9 / Feature 2 — Logistics (Visit / Shipping / Pickup) */}
                <ListingLogisticsDetails listing={vehicle} />
                
                {/* Documentation */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t("vehicles.documentation")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {/* iter283-responsive — tighter gap + min-w-0 on the
                        text-center boxes so badges never overflow the
                        375px viewport. */}
                    <div className="grid grid-cols-3 gap-2 sm:gap-4 text-sm">
                      <div className="text-center p-3 sm:p-4 bg-slate-50 dark:bg-slate-800 rounded-lg min-w-0">
                        <p className="text-xs sm:text-sm text-slate-500 mb-1 truncate">Title Status</p>
                        <Badge className={`${vehicle.title_status === 'clean' ? 'bg-green-500' : 'bg-yellow-500'} max-w-full break-words`}>
                          {vehicle.title_status}
                        </Badge>
                      </div>
                      <div className="text-center p-3 sm:p-4 bg-slate-50 dark:bg-slate-800 rounded-lg min-w-0">
                        <p className="text-xs sm:text-sm text-slate-500 mb-1 truncate">Ownership</p>
                        <Badge variant="outline" className="capitalize max-w-full break-words">
                          {vehicle.ownership_status}
                        </Badge>
                      </div>
                      <div className="text-center p-3 sm:p-4 bg-slate-50 dark:bg-slate-800 rounded-lg min-w-0">
                        <p className="text-xs sm:text-sm text-slate-500 mb-1 truncate">Lien Status</p>
                        <Badge className={vehicle.lien_status === 'clear' ? 'bg-green-500' : 'bg-yellow-500'}>
                          {vehicle.lien_status}
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
              
              {/* Condition Tab */}
              <TabsContent value="condition">
                <Card>
                  <CardHeader>
                    <CardTitle>{t("vehicles.conditionReport")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Running Status */}
                    <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      {condition.is_running ? (
                        <>
                          <CheckCircle className="h-8 w-8 text-green-500" />
                          <div>
                            <p className="font-semibold text-green-700">Vehicle is Running</p>
                            <p className="text-sm text-slate-500">Starts and drives normally</p>
                          </div>
                        </>
                      ) : (
                        <>
                          <XCircle className="h-8 w-8 text-red-500" />
                          <div>
                            <p className="font-semibold text-red-700">Non-Running Vehicle</p>
                            <p className="text-sm text-slate-500">May require towing</p>
                          </div>
                        </>
                      )}
                    </div>
                    
                    {/* Condition Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      {[
                        { label: 'Engine', value: condition.engine_condition },
                        { label: 'Transmission', value: condition.transmission_condition },
                        { label: 'Brakes', value: condition.brakes_condition },
                        { label: 'Suspension', value: condition.suspension_condition },
                        { label: 'Body', value: condition.body_condition },
                        { label: 'Paint', value: condition.paint_condition },
                        { label: 'Interior', value: condition.interior_condition },
                        { label: 'Tires', value: condition.tires_condition },
                      ].map((item, i) => (
                        <div key={i} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                          <span className="text-sm text-slate-600">{item.label}</span>
                          <Badge className={getConditionColor(item.value)}>
                            {item.value || 'Unknown'}
                          </Badge>
                        </div>
                      ))}
                    </div>
                    
                    {/* Damage Flags */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {[
                        { label: 'Accident History', value: condition.has_accident_history },
                        { label: 'Flood Damage', value: condition.has_flood_damage },
                        { label: 'Fire Damage', value: condition.has_fire_damage },
                        { label: 'Frame Damage', value: condition.has_frame_damage },
                      ].map((item, i) => (
                        <div key={i} className={`p-3 rounded-lg text-center ${item.value ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}`}>
                          {item.value ? (
                            <XCircle className="h-6 w-6 text-red-500 mx-auto mb-1" />
                          ) : (
                            <CheckCircle className="h-6 w-6 text-green-500 mx-auto mb-1" />
                          )}
                          <p className="text-sm font-medium">{item.label}</p>
                          <p className="text-xs text-slate-500">{item.value ? 'Yes' : 'No'}</p>
                        </div>
                      ))}
                    </div>
                    
                    {/* Notes */}
                    {(condition.mechanical_notes || condition.cosmetic_notes) && (
                      <div className="space-y-4">
                        {condition.mechanical_notes && (
                          <div>
                            <h4 className="font-semibold mb-2">Mechanical Notes</h4>
                            <p className="text-slate-600 text-sm">{condition.mechanical_notes}</p>
                          </div>
                        )}
                        {condition.cosmetic_notes && (
                          <div>
                            <h4 className="font-semibold mb-2">Cosmetic Notes</h4>
                            <p className="text-slate-600 text-sm">{condition.cosmetic_notes}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
              
              {/* Bid History Tab */}
              <TabsContent value="history">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <History className="h-5 w-5" />
                      Bid History
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {vehicle.recent_bids?.length > 0 ? (
                      <div className="space-y-2">
                        {vehicle.recent_bids.map((bid, i) => (
                          <div 
                            key={bid.id || i}
                            className={`flex items-center justify-between p-3 rounded-lg ${
                              i === 0 ? 'bg-blue-50 border border-blue-200' : 'bg-slate-50'
                            }`}
                          >
                            <div className="flex items-center gap-3">
                              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                                i === 0 ? 'bg-blue-500 text-white' : 'bg-slate-200'
                              }`}>
                                <User className="h-4 w-4" />
                              </div>
                              <div>
                                <p className="font-medium">{bid.bidder_name}</p>
                                <p className="text-xs text-slate-500">
                                  {new Date(bid.created_at).toLocaleString()}
                                </p>
                              </div>
                            </div>
                            <p className={`font-bold ${i === 0 ? 'text-blue-600' : ''}`}>
                              {formatPrice(bid.amount, vehicle?.currency)}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8">
                        <Gavel className="h-12 w-12 text-slate-300 mx-auto mb-4" />
                        <p className="text-slate-500">No bids yet. Be the first!</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
              
              {/* Seller Tab */}
              <TabsContent value="seller">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      {seller?.seller_type === 'dealer' ? (
                        <Building2 className="h-5 w-5" />
                      ) : (
                        <User className="h-5 w-5" />
                      )}
                      Seller Information
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {seller ? (
                      <div className="space-y-4">
                        <div className="flex items-center gap-4">
                          <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center">
                            {seller.seller_type === 'dealer' ? (
                              <Building2 className="h-8 w-8 text-slate-400" />
                            ) : (
                              <User className="h-8 w-8 text-slate-400" />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              <h3 className="font-semibold text-lg">
                                {seller.business_name || 'Private Seller'}
                              </h3>
                              <VerifiedSellerBadge isVerified={seller.verification_status === 'approved'} />
                            </div>
                            <SellerTypeBadge sellerType={seller.seller_type} />
                          </div>
                        </div>
                        
                        {/* Seller Rating Display */}
                        <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                          <SellerRatingBadge 
                            rating={seller.average_rating} 
                            reviewCount={seller.review_count}
                            totalSold={seller.total_sold}
                          />
                        </div>
                        
                        <div className="grid grid-cols-3 gap-4 text-center py-4 border-y">
                          <div>
                            <p className="text-2xl font-bold">{seller.total_sold || 0}</p>
                            <p className="text-sm text-slate-500">Vehicles Sold</p>
                          </div>
                          <div>
                            <p className="text-2xl font-bold">
                              {seller.average_rating ? (
                                <span className="flex items-center justify-center gap-1">
                                  {seller.average_rating.toFixed(1)}
                                  <Star className="h-5 w-5 text-yellow-500 fill-yellow-500" />
                                </span>
                              ) : 'N/A'}
                            </p>
                            <p className="text-sm text-slate-500">Rating</p>
                          </div>
                          <div>
                            <p className="text-2xl font-bold">
                              {new Date(seller.created_at).getFullYear()}
                            </p>
                            <p className="text-sm text-slate-500">Member Since</p>
                          </div>
                        </div>
                        
                        {/* Verification Status */}
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div className="flex items-center gap-2 text-green-600">
                            <CheckCircle className="h-4 w-4" />
                            <span>ID Verified</span>
                          </div>
                          <div className="flex items-center gap-2 text-green-600">
                            <CheckCircle className="h-4 w-4" />
                            <span>{t("vehicles.emailConfirmed")}</span>
                          </div>
                          <div className="flex items-center gap-2 text-green-600">
                            <CheckCircle className="h-4 w-4" />
                            <span>{t("vehicles.phoneVerified")}</span>
                          </div>
                          {seller.seller_type === 'dealer' && (
                            <div className="flex items-center gap-2 text-green-600">
                              <CheckCircle className="h-4 w-4" />
                              <span>{t("vehicles.licenseVerified")}</span>
                            </div>
                          )}
                        </div>

                        {/* iter201 — Phase 2 — Province-licensed dealer badge with masked licence */}
                        {seller.seller_type === 'dealer' && (seller.license_number || seller.dealer_license_number) && (
                          <div
                            className="mt-3 rounded-lg border-2 border-emerald-200 bg-emerald-50 dark:bg-emerald-950/30 dark:border-emerald-800 p-3 flex items-start gap-3"
                            data-testid="dealer-verified-badge"
                          >
                            <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                                {i18n.language === 'fr' ? 'Concessionnaire vérifié' : 'Verified Dealer'}
                              </p>
                              {(() => {
                                const lic = seller.dealer_license_number || seller.license_number || '';
                                const masked = lic.length > 4 ? `****${lic.slice(-3)}` : lic;
                                const province = seller.dealer_license_province || seller.license_province;
                                const regBody = (
                                  province === 'ON' ? 'OMVIC'
                                  : province === 'AB' ? 'AMVIC'
                                  : province === 'BC' ? 'VSA'
                                  : province === 'QC' ? 'SAAQ'
                                  : province === 'SK' ? 'FCAA'
                                  : province ? `${province} dealer authority` : 'Provincial dealer authority'
                                );
                                return (
                                  <p className="text-sm font-mono text-emerald-900 dark:text-emerald-100 mt-0.5" data-testid="dealer-license-masked">
                                    {regBody} #{masked}
                                  </p>
                                );
                              })()}
                              <p className="text-[11px] text-emerald-700/80 dark:text-emerald-300/80 mt-1">
                                {i18n.language === 'fr'
                                  ? 'Licence vérifiée par BidVex avec le régulateur provincial.'
                                  : 'Licence verified with the provincial regulator by BidVex.'}
                              </p>
                            </div>
                          </div>
                        )}

                        {/* iter197 — Message Seller (gated to winner who paid unlock fee) */}
                        {(() => {
                          const canMessage = !!user
                            && vehicle?.winner_id === user.id
                            && !!vehicle?.unlock_paid_at
                            && !!seller?.user_id;
                          if (!canMessage) return null;
                          return (
                            <div
                              className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:bg-blue-950/30 dark:border-blue-800"
                              data-testid="vehicle-message-seller-section"
                            >
                              <div className="flex items-start gap-3">
                                <MessageSquare className="h-5 w-5 mt-0.5 text-blue-600 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">
                                    {i18n.language === 'fr' ? 'Coordonnez votre ramassage' : 'Coordinate your pickup'}
                                  </p>
                                  <p className="text-xs text-blue-800/80 dark:text-blue-200/80 mt-0.5">
                                    {i18n.language === 'fr'
                                      ? 'Les frais de plateforme étant payés, vous pouvez écrire directement au concessionnaire pour organiser le ramassage.'
                                      : 'With the platform fee paid, you can message the dealer directly to arrange pickup.'}
                                  </p>
                                  <Button
                                    size="sm"
                                    className="mt-3 bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-60 disabled:cursor-not-allowed"
                                    disabled
                                    title={i18n.language === 'fr' ? 'Messagerie bientôt disponible' : 'Messaging coming soon'}
                                    data-testid="vehicle-message-seller-btn"
                                  >
                                    <MessageSquare className="mr-2 h-4 w-4" />
                                    {i18n.language === 'fr' ? 'Messagerie bientôt' : 'Messaging coming soon'}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    ) : (
                      <p className="text-slate-500">Seller information not available</p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
              
              {/* Auction Rules Tab */}
              <TabsContent value="rules" className="space-y-6">
                <AntiSnipingRulesCard />
                <AuctionRulesSummary vehicle={vehicle} />
                <AsIsWhereIsDisclaimer vehicle={vehicle} prominent />
                <InspectionReminder />
                <PaymentTermsDisplay />
                <BindingBidNotice />
                <PlatformRoleDisclaimer />
              </TabsContent>
              
              {/* Pricing Tab */}
              <TabsContent value="pricing" className="space-y-6">
                <PricingCalculator 
                  vehicleId={vehicle.id}
                  bidAmount={vehicle.current_bid || vehicle.starting_price}
                  province={vehicle.location_province}
                  showInput={true}
                  expanded={true}
                  listing={vehicle}
                />

                {/* iter283-vehicle-fee-cleanup —
                    The legacy "Fee Transparency" card (Buyer Premium
                    5%/3.5%/3% + Seller Commission 4%/2.5%/2% grid) was
                    REMOVED from this surface. Vehicles do not carry a
                    tier-based buyer premium (see test_iter283_vehicle_bp_zero)
                    so showing the matrix here misled buyers about the
                    pricing model. The same `<FeeTransparency>` content
                    remains valid on the Storage / Lots surfaces where
                    the tier matrix legitimately applies.

                    Replaced by the bilingual legal disclaimer card
                    required for Quebec / Canadian auto-dealer compliance. */}
                <Card data-testid="vehicle-legal-disclaimer-footer">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <Info className="h-4 w-4 text-slate-500 dark:text-slate-400 mt-0.5 flex-shrink-0" />
                      <p className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                        {i18n.language?.startsWith('fr') ? (
                          <>
                            Le prix d'adjudication du véhicule est payé
                            directement au vendeur. BidVex ne perçoit que les
                            frais de plateforme + les taxes applicables.
                            Taxe de transfert provinciale & immatriculation
                            sont à la charge de l'acheteur.
                          </>
                        ) : (
                          <>
                            Vehicle hammer price is paid directly to the
                            seller. BidVex collects only the Platform Fee +
                            applicable tax. Provincial transfer tax &
                            registration are buyer-paid.
                          </>
                        )}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>

          {/* Right Column - Bidding Panel (40% — sticky on scroll)
              iter283-responsive — Mobile: full-width block below the
              content. lg+: sticky right-column sidebar. `min-w-0` so
              the bid input never forces a horizontal scroll.

              Spec: "On mobile, the bid panel must stack BELOW the
              main content as a full-width block. On lg: and above,
              it should sit as a sticky right-column sidebar." */}
          <div
            className="lg:col-span-2 space-y-4 min-w-0 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto"
            data-testid="vehicle-detail-bid-column"
          >
            <BiddingPanel 
              vehicle={vehicle} 
              onBidPlaced={fetchVehicle}
            />
            
            {/* Location Card */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <MapPin className="h-5 w-5 text-slate-400" />
                  <div>
                    <p className="font-medium">{vehicle.location_city}, {vehicle.location_province}</p>
                    <p className="text-sm text-slate-500">{vehicle.location_postal_code}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            {/* Reserve Status */}
            <ReserveStatusDisplay 
              hasReserve={!!vehicle.reserve_price} 
              reserveMet={vehicle.reserve_met}
              prominent
            />
            
            {/* Anti-Sniping Badge */}
            <AntiSnipingRulesCard compact />
            
            {/* Legal Footer */}
            <LegalFooter />
          </div>
        </div>

        {/* iter202 Phase B — Similar Vehicles section */}
        {vehicle.category_id && (
          <RelatedVehicles categoryId={vehicle.category_id} excludeId={vehicle.id} />
        )}
      </div>

      {/* iter202 Phase B — Mobile fixed bid bar (hidden when full panel in view via IO) */}
      {!isEnded && (
        <MobileBidBar
          vehicle={vehicle}
          onBidClick={() => {
            const el = document.querySelector('[data-testid="bid-input"]');
            if (el) {
              el.scrollIntoView({ block: 'center', behavior: 'smooth' });
              setTimeout(() => el.focus?.(), 400);
            }
          }}
        />
      )}

      {/* iter189 Feature 2 — Vehicle Promotion Modal */}
      {showPromoModal && vehicle && (
        <ListingPromotionModal
          onClose={() => setShowPromoModal(false)}
          listingId={vehicle.id}
          listingTitle={`${vehicle.year} ${vehicle.make} ${vehicle.model}`}
          listingType="vehicle"
        />
      )}

      {/* iter197 — Message Seller modal (winner-only after unlock fee paid) */}
      {showMessageModal && seller?.user_id && (
        <MessageSellerModal
          isOpen={showMessageModal}
          onClose={() => setShowMessageModal(false)}
          sellerId={seller.user_id}
          listingId={vehicle.id}
          listingTitle={`${vehicle.year} ${vehicle.make} ${vehicle.model}`}
        />
      )}
      {/* iter201 — Phase 3 / 3A — Province-aware buyer gate */}
      {showBuyerGateModal && vehicle && (
        <VehicleBuyerGateModal
          open={showBuyerGateModal}
          onClose={() => setShowBuyerGateModal(false)}
          listingId={vehicle.id}
          onVerified={() => {
            setBuyerGateCleared(true);
            // Re-trigger the bid attempt now that gate is cleared
            setTimeout(() => handleBid(), 200);
          }}
        />
      )}
      {/* iter201 — Phase 2 — Bilingual legal footer (CEO Part 4) */}
      <VehicleLegalFooter />
    </div>
  );
};

export default function VehicleDetailPageWithErrorBoundary(props) {
  return (
    <ErrorBoundary scope="vehicle-detail">
      <VehicleDetailPage {...props} />
    </ErrorBoundary>
  );
}
