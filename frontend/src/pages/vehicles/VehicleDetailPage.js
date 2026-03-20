/**
 * Vehicle Detail Page
 * Shows full vehicle details with live bidding panel
 * Includes trust indicators, legal disclaimers, and transparent auction rules
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
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

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Format helpers
const formatPrice = (price) => {
  const { t } = useTranslation();
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
  }).format(price);
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
        <img
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
            <img src={photo.url} alt="" className="w-full h-full object-cover" />
          </button>
        ))}
      </div>
    </div>
  );
};

// Bidding Panel Component
const BiddingPanel = ({ vehicle, onBidPlaced }) => {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [bidAmount, setBidAmount] = useState('');
  const [bidding, setBidding] = useState(false);
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [depositPaid, setDepositPaid] = useState(false);
  
  // Real-time bidding data
  const { 
    currentBid, 
    bidCount, 
    timeRemaining, 
    reserveMet, 
    connected 
  } = useVehicleBidding(vehicle?.id, !!vehicle);
  
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
    
    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount < minBid) {
      toast.error(`Minimum bid is ${formatPrice(minBid)}`);
      return;
    }
    
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
          toast.success('Deposit confirmed');
        }
      }
      
      // Place bid
      const response = await axios.post(`${API}/vehicle-bids`, {
        vehicle_id: vehicle.id,
        amount,
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(`Bid placed: ${formatPrice(amount)}`);
      onBidPlaced?.(response.data);
      setBidAmount((amount + (vehicle?.bid_increment || 100)).toString());
      
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
      <Card className="sticky top-4 border-2 border-blue-100 dark:border-blue-900 shadow-xl">
        <CardHeader className="bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-t-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm">Current Bid</p>
              <p className="text-3xl font-bold">{formatPrice(displayBid)}</p>
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
              <div className="flex gap-4">
                {timeRemaining.days > 0 && (
                  <div className="text-center">
                    <p className="text-2xl font-bold">{timeRemaining.days}</p>
                    <p className="text-xs text-blue-200">Days</p>
                  </div>
                )}
                <div className="text-center">
                  <p className="text-2xl font-bold">{timeRemaining.hours}</p>
                  <p className="text-xs text-blue-200">Hours</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">{timeRemaining.minutes}</p>
                  <p className="text-xs text-blue-200">Min</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">{timeRemaining.seconds}</p>
                  <p className="text-xs text-blue-200">Sec</p>
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
          
          {/* Bid Input */}
          {!isEnded && (
            <div className="space-y-3">
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
                    step={vehicle?.bid_increment || 100}
                    data-testid="bid-input"
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Minimum bid: {formatPrice(minBid)} (increment: {formatPrice(vehicle?.bid_increment || 100)})
                </p>
              </div>
              
              {/* Pricing Breakdown */}
              {user && bidAmount && parseFloat(bidAmount) > 0 && (
                <PricingEstimate 
                  vehicleId={vehicle?.id} 
                  bidAmount={parseFloat(bidAmount)}
                  province={vehicle?.location_province}
                />
              )}
              
              {/* Deposit Notice */}
              {vehicle?.requires_deposit && !depositPaid && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-sm text-blue-700 flex items-center gap-2">
                    <CreditCard className="h-4 w-4" />
                    Refundable deposit of {formatPrice(vehicle.deposit_amount)} required
                  </p>
                </div>
              )}
              
              <Button 
                onClick={handleBid}
                disabled={bidding || !user}
                className="w-full h-14 text-lg bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800"
                data-testid="place-bid-btn"
              >
                {bidding ? (
                  <>Processing...</>
                ) : !user ? (
                  <>{t("auction.loginToBid")}</>
                ) : (
                  <>
                    <Gavel className="h-5 w-5 mr-2" />
                    Place Bid
                  </>
                )}
              </Button>
              
              {/* Buy Now */}
              {vehicle?.buy_now_price && displayBid < vehicle.buy_now_price && (
                <Button variant="outline" className="w-full h-12">
                  Buy Now: {formatPrice(vehicle.buy_now_price)}
                </Button>
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
    </>
  );
};

// Main Page Component
const VehicleDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [vehicle, setVehicle] = useState(null);
  const [seller, setSeller] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchVehicle = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/vehicles/${id}`);
      setVehicle(response.data);
      setSeller(response.data.seller);
    } catch (err) {
      setError(err.response?.data?.detail || 'Vehicle not found');
    } finally {
      setLoading(false);
    }
  }, [id]);

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

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="vehicle-detail-page">
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <Button 
            variant="ghost" 
            onClick={() => navigate('/vehicle-auctions')}
            className="mb-2"
          >
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to Auctions
          </Button>
          
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white">
                  {vehicle.year} {vehicle.make} {vehicle.model}
                </h1>
                {vehicle.auction_type === 'live' && <LiveAuctionBadge />}
              </div>
              {vehicle.trim && (
                <p className="text-lg text-slate-500">{vehicle.trim}</p>
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
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left Column - Images & Details */}
          <div className="lg:col-span-2 space-y-6">
            {/* Image Gallery */}
            <ImageGallery media={vehicle.media} />
            
            {/* Tabs */}
            <Tabs defaultValue="details">
              <TabsList className="w-full justify-start bg-transparent flex-wrap">
                <TabsTrigger value="details" className="bg-transparent">Details</TabsTrigger>
                <TabsTrigger value="condition" className="bg-transparent">Condition</TabsTrigger>
                <TabsTrigger value="history" className="bg-transparent">Bid History</TabsTrigger>
                <TabsTrigger value="seller" className="bg-transparent">Seller</TabsTrigger>
                <TabsTrigger value="rules" className="bg-transparent">Auction Rules</TabsTrigger>
                <TabsTrigger value="pricing" className="bg-transparent">Pricing</TabsTrigger>
              </TabsList>
              
              {/* Details Tab */}
              <TabsContent value="details" className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>{t("vehicles.vehicleSpecifications")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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
                
                {/* Documentation */}
                <Card>
                  <CardHeader>
                    <CardTitle>{t("vehicles.documentation")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="text-center p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <p className="text-sm text-slate-500 mb-1">Title Status</p>
                        <Badge className={vehicle.title_status === 'clean' ? 'bg-green-500' : 'bg-yellow-500'}>
                          {vehicle.title_status}
                        </Badge>
                      </div>
                      <div className="text-center p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <p className="text-sm text-slate-500 mb-1">Ownership</p>
                        <Badge variant="outline" className="capitalize">
                          {vehicle.ownership_status}
                        </Badge>
                      </div>
                      <div className="text-center p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <p className="text-sm text-slate-500 mb-1">Lien Status</p>
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
                              {formatPrice(bid.amount)}
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
                />
                
                {/* Fee Transparency */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Info className="h-5 w-5 text-slate-600" />
                      Fee Transparency
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-blue-50 dark:bg-blue-950/30 rounded-lg p-4">
                        <h4 className="font-semibold text-blue-800 dark:text-blue-200 mb-2">Buyer Premium</h4>
                        <ul className="space-y-1 text-sm text-blue-700 dark:text-blue-300">
                          <li>Standard: 5%</li>
                          <li>Premium: 3.5%</li>
                          <li>VIP Elite: 3%</li>
                        </ul>
                      </div>
                      <div className="bg-green-50 dark:bg-green-950/30 rounded-lg p-4">
                        <h4 className="font-semibold text-green-800 dark:text-green-200 mb-2">Seller Commission</h4>
                        <ul className="space-y-1 text-sm text-green-700 dark:text-green-300">
                          <li>Standard: 4%</li>
                          <li>Premium: 2.5%</li>
                          <li>VIP Elite: 2%</li>
                        </ul>
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 text-center">
                      Platform fee of 2.5% applies to all transactions. Taxes calculated based on buyer's province.
                    </p>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>

          {/* Right Column - Bidding Panel */}
          <div className="space-y-4">
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
      </div>
    </div>
  );
};

export default VehicleDetailPage;
