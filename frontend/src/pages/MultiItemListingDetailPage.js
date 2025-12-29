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
  Zap, ShoppingCart, Loader2
} from 'lucide-react';
import Countdown from 'react-countdown';
import Lightbox from 'react-image-lightbox';
import 'react-image-lightbox/style.css';
import MonsterBidButton from '../components/MonsterBidButton';
import AutoBidModal from '../components/AutoBidModal';
import SubscriptionBadge from '../components/SubscriptionBadge';
import WishlistHeartButton from '../components/WishlistHeartButton';
import AuctioneerInfo from '../components/AuctioneerInfo';
import WatchlistButton from '../components/WatchlistButton';
import ShareButton from '../components/ShareButton';
import MessageSellerModal from '../components/MessageSellerModal';
import BidErrorGuide from '../components/BidErrorGuide';
import VerificationRequiredModal from '../components/VerificationRequiredModal';
import { extractErrorMessage } from '../utils/errorHandler';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MultiItemListingDetailPage = () => {
  const { id } = useParams();
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
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
  const lotRefs = useRef({});

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
      toast.success(bidType === 'monster' ? '⚡ Monster Bid placed!' : 'Bid placed successfully!');
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
                        <Package className="h-6 w-6 text-primary" />
                        <Badge 
                          variant={isPreviewMode ? "secondary" : auctionEnded ? "secondary" : "default"}
                          className={isPreviewMode ? "bg-amber-500 text-white" : ""}
                        >
                          {isPreviewMode ? 'Coming Soon' : auctionEnded ? 'Auction Ended' : 'Active Auction'}
                        </Badge>
                        <Badge variant="outline">{listing.total_lots} Lots</Badge>
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
                    <CardTitle className="text-3xl mb-4">{listing.title}</CardTitle>
                    <p className="text-muted-foreground mb-4">{listing.description}</p>

                    {/* Auctioneer Info Section */}
                    {listing.seller_id && (
                      <div className="mb-6">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-sm text-muted-foreground">Hosted by</p>
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

                          {/* Agreement Checkbox - Prominent and Required */}
                          <div className="mt-6 p-4 bg-primary/5 border-2 border-primary/20 rounded-lg">
                            <label className="flex items-start gap-3 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={agreedToTerms}
                                onChange={(e) => setAgreedToTerms(e.target.checked)}
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
                        <MapPin className="h-4 w-4 text-muted-foreground" />
                        <span>{listing.city}, {listing.region}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Package className="h-4 w-4 text-muted-foreground" />
                        <span>{listing.category}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span>
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
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-muted rounded-lg">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-primary">{listing.total_lots}</p>
                    <p className="text-sm text-muted-foreground">Total Lots</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-primary">${totalStartingValue.toFixed(2)}</p>
                    <p className="text-sm text-muted-foreground">Total Starting Value</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-600">${totalCurrentValue.toFixed(2)}</p>
                    <p className="text-sm text-muted-foreground">Current Total Value</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* View Mode Toggle */}
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">Available Lots</h2>
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
                                <MonsterBidButton
                                  listingId={lot.id}
                                  currentBid={lot.current_price}
                                  minimumIncrement={getMinimumIncrement(lot.current_price)}
                                  onBidPlaced={(amount) => {
                                    fetchListing();
                                  }}
                                />
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
    </div>
  );
};

export default MultiItemListingDetailPage;
