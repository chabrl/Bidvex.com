import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
  Package, Clock, MapPin, User, Calendar, 
  ArrowLeft, Gavel, AlertCircle, TrendingUp,
  Grid as GridIcon, List as ListIcon, Menu, X, Flame, Heart, Info,
  Zap, ShoppingCart, Loader2, Truck, Building2, Shield, DollarSign,
  Scale, Wrench, HardHat, CheckCircle, XCircle, FileText
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
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
import PrivateSaleBadge, { BusinessSellerBadge } from '../components/PrivateSaleBadge';
import PublicBidHistory from '../components/PublicBidHistory';
import { extractErrorMessage } from '../utils/errorHandler';
import { useCurrency } from '../contexts/CurrencyContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MultiItemListingDetailPage = () => {
  const { id } = useParams();
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { formatPrice, currency } = useCurrency();
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
  const [ratingModalOpen, setRatingModalOpen] = useState(false);
  const [autoBidModalOpen, setAutoBidModalOpen] = useState(false);
  const [selectedLot, setSelectedLot] = useState(null);
  const [showFullTerms, setShowFullTerms] = useState(false);
  const [buyNowLoading, setBuyNowLoading] = useState({});
  const [verificationModalOpen, setVerificationModalOpen] = useState(false);
  const [verificationAction, setVerificationAction] = useState('bid');
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [termsAcceptedPersistent, setTermsAcceptedPersistent] = useState(false);
  const [sellerInfo, setSellerInfo] = useState(null);
  const [showBidHistory, setShowBidHistory] = useState(false);
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
    if (!incrementInfo) return 5; // Default fallback
    
    const option = incrementInfo.increment_option;
    if (option === 'simplified') {
      if (currentBid <= 100) return 1;
      if (currentBid <= 1000) return 5;
      if (currentBid <= 10000) return 25;
      return 100;
    } else {
      // Tiered
      if (currentBid < 100) return 5;
      if (currentBid < 500) return 10;
      if (currentBid < 1000) return 25;
      if (currentBid < 5000) return 50;
      if (currentBid < 10000) return 100;
      if (currentBid < 50000) return 250;
      if (currentBid < 100000) return 500;
      return 1000;
    }
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

  const fetchListing = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/multi-item-listings/${id}`);
      setListing(response.data);
      if (response.data.lots.length > 0) {
        setActiveLotId(response.data.lots[0].lot_number);
      }
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
      toast.error(`Bid must be higher than current price of $${lot.current_price.toFixed(2)}`);
      return;
    }

    // Validate increment for normal bids
    if (bidType === 'normal') {
      const minIncrement = getMinimumIncrement(lot.current_price);
      const minimumBid = lot.current_price + minIncrement;
      
      if (bidAmount < minimumBid) {
        toast.error(`Minimum bid is $${minimumBid.toFixed(2)} (increment: $${minIncrement.toFixed(2)})`);
        return;
      }
    }

    try {
      await axios.post(
        `${API}/multi-item-listings/${id}/lots/${lotNumber}/bid`,
        { amount: bidAmount, bid_type: bidType },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      toast.success('Bid placed successfully!');
      fetchListing();
      setBidAmounts({ ...bidAmounts, [lotNumber]: '' });
    } catch (error) {
      const errorMessage = extractErrorMessage(error);
      toast.error(errorMessage || 'Failed to place bid');
    }
  };

  // Buy Now Handler
  const handleBuyNow = async (lot) => {
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

    setBuyNowLoading(prev => ({ ...prev, [lot.lot_number]: true }));
    
    try {
      const response = await axios.post(
        `${API}/buy-now`,
        {
          listing_id: id,
          lot_number: lot.lot_number,
          quantity: 1
        },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      
      toast.success(`🎉 Congratulations! You purchased "${lot.title}" for $${lot.buy_now_price.toFixed(2)}!`);
      
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
          <h2 className="text-2xl font-bold mb-2">Listing Not Found</h2>
          <Button onClick={() => navigate('/lots')}>Back to Lots Marketplace</Button>
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
              Back to Lots Marketplace
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
                          {isPreviewMode ? 'Coming Soon' : auctionEnded ? 'Auction Ended' : 'Active Auction'}
                        </Badge>
                        <Badge 
                          variant="outline" 
                          className="lots-count-badge font-bold text-slate-800 dark:text-slate-100 border-slate-400 dark:border-slate-500 bg-slate-100 dark:bg-slate-700"
                        >
                          {listing.total_lots} Lots
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
                    <CardTitle className="text-3xl mb-4 text-slate-900 dark:text-white" style={{ fontWeight: 700 }}>{listing.title}</CardTitle>
                    <p className="mb-4 text-slate-600 dark:text-slate-300">{listing.description}</p>

                    {/* Private Sale / Business Seller Badge */}
                    {sellerInfo && !sellerInfo.is_tax_registered && (
                      <PrivateSaleBadge className="mb-4" />
                    )}
                    {sellerInfo && sellerInfo.is_tax_registered && (
                      <BusinessSellerBadge variant="default" className="mb-4" />
                    )}

                    {/* Auctioneer Info Section with Seller Tier Badge */}
                    {listing.seller_id && (
                      <div className="mb-6">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <p className="text-sm text-muted-foreground">Hosted by</p>
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
                              📨 Message Seller
                            </Button>
                          )}
                        </div>
                        <AuctioneerInfo sellerId={listing.seller_id} variant="full" />
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
                              Ends in: <Countdown date={new Date(listing.auction_end_date)} />
                            </>
                          ) : (
                            'Auction Ended'
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
                    <p className="text-sm" style={{ color: '#6b7280' }}>Total Lots</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold" style={{ color: '#2563eb' }}>${totalStartingValue.toFixed(2)}</p>
                    <p className="text-sm" style={{ color: '#6b7280' }}>Total Starting Value</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold" style={{ color: '#16a34a' }}>${totalCurrentValue.toFixed(2)}</p>
                    <p className="text-sm" style={{ color: '#6b7280' }}>Current Total Value</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* View Mode Toggle */}
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold" style={{ color: '#1a1a1a' }}>Available Lots</h2>
              <div className="flex gap-2">
                <Button
                  variant={viewMode === 'grid' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleViewModeChange('grid')}
                  className={viewMode === 'grid' ? 'gradient-button text-white' : ''}
                >
                  <GridIcon className="h-4 w-4 mr-2" />
                  Grid
                </Button>
                <Button
                  variant={viewMode === 'list' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => handleViewModeChange('list')}
                  className={viewMode === 'list' ? 'gradient-button text-white' : ''}
                >
                  <ListIcon className="h-4 w-4 mr-2" />
                  List
                </Button>
              </div>
            </div>

            {/* Lots Display */}
            <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 gap-6' : 'space-y-6'}>
              {listing.lots.map((lot) => (
                <Card 
                  key={lot.lot_number} 
                  ref={(el) => (lotRefs.current[lot.lot_number] = el)}
                  className={`border-2 hover:border-primary transition-colors ${
                    hasActiveBids(lot) ? 'border-amber-300 shadow-amber-100' : ''
                  }`}
                >
                  <CardContent className="pt-6">
                    <div className={viewMode === 'grid' ? 'space-y-4' : 'flex gap-6'}>
                      {/* Images */}
                      {lot.images && lot.images.length > 0 && (
                        <div className={viewMode === 'grid' ? 'w-full' : 'w-1/3 flex-shrink-0'}>
                          <div className="grid grid-cols-2 gap-2">
                            {lot.images.slice(0, 4).map((img, idx) => (
                              <div 
                                key={idx} 
                                className="aspect-square rounded-lg overflow-hidden bg-gray-100 cursor-pointer hover:opacity-80 transition-opacity"
                                onClick={() => openLightbox(lot.images, idx)}
                              >
                                <img 
                                  src={img} 
                                  alt={`${lot.title} - ${idx + 1}`}
                                  className="w-full h-full object-cover"
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Lot Details */}
                      <div className="flex-1">
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex-1">
                            <h3 className="text-xl font-bold mb-2">
                              Lot #{lot.lot_number} - {lot.title}
                            </h3>
                            <div className="flex gap-2 flex-wrap">
                              <Badge variant="outline">
                                Quantity: {lot.quantity}
                              </Badge>
                              <Badge variant="secondary">
                                {lot.condition.replace('_', ' ').toUpperCase()}
                              </Badge>
                              {hasActiveBids(lot) && (
                                <Badge variant="default" className="bg-amber-500 hover:bg-amber-600">
                                  <Flame className="h-3 w-3 mr-1" />
                                  Active Bidding
                                </Badge>
                              )}
                            </div>
                          </div>
                          
                          {/* Share and Watch Buttons */}
                          <div className="flex gap-2">
                            <WatchlistButton 
                              itemId={`${id}:${lot.lot_number}`}
                              itemType="lot"
                              size="default"
                              showLabel={true}
                            />
                            <ShareButton 
                              url={`${window.location.origin}/lots/${id}?lot=${lot.lot_number}`}
                              title={`Lot #${lot.lot_number} - ${lot.title}`}
                              description={`${lot.description} - Starting at $${lot.starting_price}`}
                            />
                          </div>
                        </div>

                        <p className="text-muted-foreground mb-4">{lot.description}</p>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                          <div>
                            <p className="text-sm text-muted-foreground">Starting Price</p>
                            <p className="text-lg font-semibold">${lot.starting_price.toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Current Price</p>
                            <p className="text-lg font-semibold text-green-600">${lot.current_price.toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Price Increase</p>
                            <p className="text-lg font-semibold text-blue-600">
                              <TrendingUp className="inline h-4 w-4 mr-1" />
                              ${(lot.current_price - lot.starting_price).toFixed(2)}
                            </p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Total Value</p>
                            <p className="text-lg font-semibold">
                              ${(lot.current_price * lot.quantity).toFixed(2)}
                            </p>
                          </div>
                        </div>

                        {/* Buyer's Premium Display - Fee Transparency */}
                        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-3 mb-4">
                          <div className="flex items-center justify-between flex-wrap gap-2">
                            <div className="flex items-center gap-2">
                              <DollarSign className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                              <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                                Buyer&apos;s Premium:
                              </span>
                              <span className="font-bold text-blue-700 dark:text-blue-300">
                                5%
                              </span>
                              <span className="text-xs text-green-600 dark:text-green-400 font-medium bg-green-100 dark:bg-green-900/30 px-2 py-0.5 rounded">
                                (3.5% for Premium Members)
                              </span>
                            </div>
                            <div className="text-right">
                              <p className="text-xs text-slate-500 dark:text-slate-400">Est. Total Out-of-Pocket:</p>
                              <p className="text-sm font-bold text-blue-700 dark:text-blue-300">
                                ${(lot.current_price * 1.05).toFixed(2)}
                              </p>
                            </div>
                          </div>
                        </div>

                        {/* Lot Countdown Timer */}
                        {lot.lot_end_time && !auctionEnded && (
                          <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-4">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Clock className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                                <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
                                  This lot ends in:
                                </span>
                              </div>
                              <div className="text-lg font-bold text-blue-600 dark:text-blue-400">
                                <Countdown 
                                  date={new Date(lot.lot_end_time)}
                                  renderer={({ days, hours, minutes, seconds, completed }) => {
                                    if (completed) {
                                      return <span className="text-red-600">Ended</span>;
                                    }
                                    return (
                                      <span>
                                        {days > 0 && `${days}d `}
                                        {hours}h {minutes}m {seconds}s
                                      </span>
                                    );
                                  }}
                                />
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Buy Now Section */}
                        {lot.buy_now_enabled && lot.buy_now_price && lot.lot_status !== 'sold_out' && !auctionEnded && (
                          <div className="bg-gradient-to-r from-[#06B6D4]/10 to-[#1E3A8A]/10 border-2 border-[#06B6D4] rounded-lg p-4 mb-4">
                            <div className="flex items-center justify-between flex-wrap gap-4">
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-[#06B6D4] flex items-center justify-center">
                                  <Zap className="h-5 w-5 text-white" />
                                </div>
                                <div>
                                  <p className="text-sm font-medium text-[#06B6D4]">⚡ Buy Now Available</p>
                                  <p className="text-2xl font-bold text-[#1E3A8A] dark:text-white">
                                    ${lot.buy_now_price.toFixed(2)}
                                  </p>
                                  {lot.available_quantity && lot.available_quantity < lot.quantity && (
                                    <p className="text-xs text-amber-600">
                                      Only {lot.available_quantity} left!
                                    </p>
                                  )}
                                </div>
                              </div>
                              <Button
                                onClick={() => handleBuyNow(lot)}
                                disabled={buyNowLoading[lot.lot_number] || lot.lot_status === 'sold_out'}
                                className="bg-gradient-to-r from-[#06B6D4] to-[#1E3A8A] hover:opacity-90 text-white px-6 py-3 h-auto"
                              >
                                {buyNowLoading[lot.lot_number] ? (
                                  <>
                                    <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                                    Processing...
                                  </>
                                ) : (
                                  <>
                                    <ShoppingCart className="h-5 w-5 mr-2" />
                                    Buy Now
                                  </>
                                )}
                              </Button>
                            </div>
                            <p className="text-xs text-muted-foreground mt-2">
                              Skip the bidding - purchase instantly at the fixed price
                            </p>
                          </div>
                        )}

                        {/* Sold Out Badge */}
                        {lot.lot_status === 'sold_out' && (
                          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4 text-center">
                            <Badge variant="destructive" className="text-lg px-4 py-1">
                              SOLD OUT
                            </Badge>
                            <p className="text-sm text-red-600 dark:text-red-400 mt-2">
                              This item has been purchased via Buy Now
                            </p>
                          </div>
                        )}

                        {/* Bidding Section */}
                        {isPreviewMode && (
                          <div className="bg-amber-50 dark:bg-amber-950 border border-amber-300 rounded-lg p-4 text-center mt-4">
                            <Clock className="h-6 w-6 mx-auto text-amber-600 dark:text-amber-400 mb-2" />
                            <p className="text-sm font-semibold text-amber-900 dark:text-amber-100">
                              Bidding opens in{' '}
                              {auctionStartDate && (
                                <Countdown 
                                  date={auctionStartDate}
                                  renderer={({ days, hours, minutes, completed }) => (
                                    <span>{completed ? 'moments' : `${days}d ${hours}h ${minutes}m`}</span>
                                  )}
                                />
                              )}
                            </p>
                            <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                              You can preview details and favorite this auction now
                            </p>
                          </div>
                        )}

                        {!isPreviewMode && !auctionEnded && (
                          <div className="space-y-3 mt-4">
                            {/* Increment Info */}
                            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-blue-50 dark:bg-blue-900/20 px-3 py-2 rounded-md">
                              <Info className="h-3 w-3" />
                              <span>
                                Minimum increment: ${getMinimumIncrement(lot.current_price).toFixed(2)} 
                                {incrementInfo && ` (${incrementInfo.increment_option === 'tiered' ? 'Tiered' : 'Simplified'} schedule)`}
                              </span>
                            </div>

                            {/* Standard Bid Input */}
                            <div className="flex gap-2">
                              <input
                                type="number"
                                step="0.01"
                                min={lot.current_price + getMinimumIncrement(lot.current_price)}
                                placeholder={`Min: $${(lot.current_price + getMinimumIncrement(lot.current_price)).toFixed(2)}`}
                                value={bidAmounts[lot.lot_number] || ''}
                                onChange={(e) => handleBidChange(lot.lot_number, e.target.value)}
                                className="flex-1 px-4 py-2 border border-input rounded-md bg-background"
                                disabled={(listing.auction_terms_en || listing.auction_terms_fr) && !agreedToTerms}
                              />
                              <Button 
                                onClick={() => handlePlaceBid(lot.lot_number, 'normal')}
                                className="gradient-button text-white border-0"
                                disabled={(listing.auction_terms_en || listing.auction_terms_fr) && !agreedToTerms}
                                title={!agreedToTerms && (listing.auction_terms_en || listing.auction_terms_fr) ? t('auction.mustAgreeToTermsFirst', 'Please agree to terms & conditions first') : ''}
                              >
                                <Gavel className="mr-2 h-4 w-4" />
                                {t('bid.placeBid', 'Place Bid')}
                              </Button>
                            </div>
                            {!agreedToTerms && (listing.auction_terms_en || listing.auction_terms_fr) && (
                              <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950 px-3 py-2 rounded-md">
                                <Info className="h-3 w-3" />
                                <span>{t('auction.agreeToTermsToPlaceBid', 'Please scroll up and agree to the Terms & Conditions to place a bid')}</span>
                              </div>
                            )}

                            {/* Bid Error Guide */}
                            <div className="mt-2">
                              <BidErrorGuide compact={true} />
                            </div>

                            {/* Premium Bidding Options */}
                            {user && (
                              <div className="flex flex-wrap gap-2">
                                <AutoBidModal
                                  listingId={lot.id}
                                  currentBid={lot.current_price}
                                  minimumIncrement={getMinimumIncrement(lot.current_price)}
                                  onAutoBidSetup={() => {
                                    fetchListing();
                                  }}
                                />
                                {user.subscription_tier && (
                                  <div className="flex items-center">
                                    <SubscriptionBadge tier={user.subscription_tier} size="small" />
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {auctionEnded && !isPreviewMode && (
                          <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 text-center">
                            <AlertCircle className="h-6 w-6 mx-auto text-muted-foreground mb-2" />
                            <p className="text-sm text-muted-foreground">Bidding has ended for this lot</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
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
                  <CardTitle className="text-lg">Lot Index</CardTitle>
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
                      <p className="text-xs truncate mb-1">{lot.title}</p>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span>Qty: {lot.quantity}</span>
                        <span className="font-semibold">${lot.current_price.toFixed(2)}</span>
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

      {/* Floating FAB (Mobile) - Enhanced with pulse animation */}
      <div className="lg:hidden fixed bottom-20 right-6 z-50">
        <Button
          size="lg"
          onClick={() => setShowLotIndex(!showLotIndex)}
          className="gradient-button text-white border-0 shadow-lg rounded-full w-14 h-14 p-0 animate-pulse-subtle hover:scale-110 transition-transform duration-200"
          style={{
            animation: showLotIndex ? 'none' : 'pulse-subtle 2s cubic-bezier(0.4, 0, 0.6, 1) 3'
          }}
        >
          {showLotIndex ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </Button>
      </div>

      {/* Mobile Lot Index Overlay - Enhanced with backdrop blur and smooth transitions */}
      {showLotIndex && (
        <div 
          className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity duration-200"
          onClick={() => setShowLotIndex(false)}
          style={{
            animation: 'fadeIn 200ms ease-in-out'
          }}
        >
          <div 
            className="absolute bottom-0 left-0 right-0 bg-background rounded-t-2xl shadow-2xl max-h-[70vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            style={{
              animation: 'slideUp 200ms ease-out'
            }}
          >
            {/* Drag indicator */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-12 h-1 bg-muted-foreground/30 rounded-full"></div>
            </div>
            
            <div className="px-6 pb-6 overflow-y-auto" style={{ maxHeight: 'calc(70vh - 60px)' }}>
              <div className="flex items-center justify-between mb-4 sticky top-0 bg-background py-2">
                <h3 className="text-lg font-bold">Lot Index</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowLotIndex(false)}
                  className="hover:bg-muted"
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
              <div className="space-y-2">
                {listing.lots.map((lot) => (
                  <div
                    key={lot.lot_number}
                    onClick={() => {
                      scrollToLot(lot.lot_number);
                      setShowLotIndex(false);
                    }}
                    className={`p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                      activeLotId === lot.lot_number
                        ? 'bg-gradient-to-r from-[#009BFF] to-[#0056A6] text-white shadow-md'
                        : 'bg-muted hover:bg-muted/80 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-1">
                      <p className="font-semibold text-sm">Lot #{lot.lot_number}</p>
                      {hasActiveBids(lot) && (
                        <Flame className="h-4 w-4 text-amber-400" />
                      )}
                    </div>
                    <p className="text-xs truncate mb-1">{lot.title}</p>
                    <div className="flex items-center justify-between text-xs">
                      <span>Qty: {lot.quantity}</span>
                      <span className="font-semibold">${lot.current_price.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

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
          listingTitle={listing.title}
        />
      )}

      {/* Verification Required Modal */}
      <VerificationRequiredModal
        isOpen={verificationModalOpen}
        onClose={() => setVerificationModalOpen(false)}
        action={verificationAction}
      />
    </div>
  );
};

export default MultiItemListingDetailPage;
