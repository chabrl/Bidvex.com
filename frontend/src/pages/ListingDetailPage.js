import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import Countdown from 'react-countdown';
import confetti from 'canvas-confetti';
import { Clock, MapPin, Eye, User, DollarSign, MessageCircle, TrendingUp } from 'lucide-react';
import PromotionManagerModal from '../components/PromotionManagerModal';
import WatchlistButton from '../components/WatchlistButton';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ListingDetailPage = () => {
  const { id } = useParams();
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [listing, setListing] = useState(null);
  const [seller, setSeller] = useState(null);
  const [bids, setBids] = useState([]);
  const [bidAmount, setBidAmount] = useState('');
  const [loading, setLoading] = useState(true);
  const [showPromotionModal, setShowPromotionModal] = useState(false);

  useEffect(() => {
    fetchListing();
    fetchBids();
  }, [id]);

  const fetchListing = async () => {
    try {
      const response = await axios.get(`${API}/listings/${id}`);
      setListing(response.data);
      
      const sellerResponse = await axios.get(`${API}/users/${response.data.seller_id}`);
      setSeller(sellerResponse.data);
    } catch (error) {
      console.error('Failed to fetch listing:', error);
      toast.error('Listing not found');
      navigate('/marketplace');
    } finally {
      setLoading(false);
    }
  };

  const fetchBids = async () => {
    try {
      const response = await axios.get(`${API}/bids/listing/${id}`);
      setBids(response.data);
    } catch (error) {
      console.error('Failed to fetch bids:', error);
    }
  };

  const handlePlaceBid = async (e) => {
    e.preventDefault();
    if (!token) {
      navigate('/auth', { state: { from: { pathname: `/listing/${id}` } } });
      return;
    }

    try {
      await axios.post(`${API}/bids`, {
        listing_id: id,
        amount: parseFloat(bidAmount),
      });
      
      toast.success('Bid placed successfully!');
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 }
      });
      
      fetchListing();
      fetchBids();
      setBidAmount('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to place bid');
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
      });
      
      window.location.href = response.data.url;
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Payment failed');
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

  const auctionEndDate = new Date(listing.auction_end_date);
  const isAuctionEnded = new Date() > auctionEndDate;
  
  // Debug logging for promote button visibility
  console.log('=== Promote Button Debug ===');
  console.log('User:', user);
  console.log('Listing seller_id:', listing.seller_id);
  console.log('User matches seller?', user && listing.seller_id === user.id);
  console.log('Is promoted?', listing.is_promoted);
  console.log('Should show promote button?', user && listing.seller_id === user.id && !listing.is_promoted);

  return (
    <div className="min-h-screen py-8 px-4" data-testid="listing-detail-page">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div className="aspect-square rounded-2xl overflow-hidden bg-gray-100">
              {listing.images && listing.images.length > 0 ? (
                <img
                  src={listing.images[0]}
                  alt={listing.title}
                  className="w-full h-full object-cover"
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
                  <div key={idx} className="aspect-square rounded-lg overflow-hidden bg-gray-100">
                    <img src={img} alt={`${listing.title} ${idx + 2}`} className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-6">
            <div>
              <div className="flex items-start justify-between mb-2">
                <h1 className="text-3xl font-bold" data-testid="listing-title">{listing.title}</h1>
                {listing.is_promoted && (
                  <Badge className="gradient-bg text-white border-0">Featured</Badge>
                )}
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

              <Separator className="my-4" />

              <div className="space-y-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">{t('marketplace.currentBid')}</p>
                  <p className="text-4xl font-bold gradient-text" data-testid="current-price">
                    ${listing.current_price.toFixed(2)}
                  </p>
                </div>

                {!isAuctionEnded && (
                  <div className="flex items-center gap-2 text-lg">
                    <Clock className="h-5 w-5 text-primary" />
                    <Countdown
                      date={auctionEndDate}
                      renderer={({ days, hours, minutes, seconds, completed }) => (
                        <span className={`font-semibold countdown-timer ${completed ? 'text-red-500' : 'text-primary'}`}>
                          {completed ? t('marketplace.ended') : `${days}d ${hours}h ${minutes}m ${seconds}s`}
                        </span>
                      )}
                    />
                  </div>
                )}

                {isAuctionEnded && (
                  <Badge variant="destructive" className="text-sm">Auction Ended</Badge>
                )}
              </div>
            </div>

            {user && listing.seller_id === user.id && !listing.is_promoted && (
              <Card className="glassmorphism border-2 border-primary/20">
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg mb-2">Boost Your Listing</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        Increase visibility and reach more potential buyers with promoted placement
                      </p>
                      <Button 
                        className="gradient-button text-white border-0"
                        onClick={() => setShowPromotionModal(true)}
                        data-testid="promote-listing-btn"
                      >
                        <TrendingUp className="mr-2 h-4 w-4" />
                        Promote This Listing
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {!isAuctionEnded && user && listing.seller_id !== user.id && (
              <Card className="glassmorphism">
                <CardContent className="p-6 space-y-4">
                  <form onSubmit={handlePlaceBid} className="space-y-3">
                    <div>
                      <label className="text-sm font-medium mb-2 block">{t('listing.yourBid')}</label>
                      <Input
                        type="number"
                        step="0.01"
                        min={listing.current_price + 0.01}
                        value={bidAmount}
                        onChange={(e) => setBidAmount(e.target.value)}
                        placeholder={`Min: $${(listing.current_price + 1).toFixed(2)}`}
                        required
                        data-testid="bid-amount-input"
                      />
                    </div>
                    <Button type="submit" className="w-full gradient-button text-white border-0" data-testid="place-bid-btn">
                      <DollarSign className="mr-2 h-4 w-4" />
                      {t('listing.placeBid')}
                    </Button>
                  </form>

                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => navigate(`/messages?seller=${listing.seller_id}&listing=${listing.id}`)}
                    data-testid="message-seller-btn"
                  >
                    <MessageCircle className="mr-2 h-4 w-4" />
                    Message Seller
                  </Button>

                  {listing.buy_now_price && (
                    <>
                      <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                          <span className="w-full border-t" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                          <span className="bg-background px-2 text-muted-foreground">Or</span>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={handleBuyNow}
                        data-testid="buy-now-btn"
                      >
                        {t('marketplace.buyNow')}: ${listing.buy_now_price.toFixed(2)}
                      </Button>
                    </>
                  )}
                </CardContent>
              </Card>
            )}

            {!user && (
              <Card className="glassmorphism">
                <CardContent className="p-6">
                  <p className="text-center mb-4">Sign in to place a bid</p>
                  <Button className="w-full gradient-button text-white border-0" onClick={() => navigate('/auth')}>
                    Sign In
                  </Button>
                </CardContent>
              </Card>
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

            <Card className="glassmorphism">
              <CardHeader>
                <CardTitle className="text-lg">Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{listing.description}</p>
              </CardContent>
            </Card>

            {bids.length > 0 && (
              <Card className="glassmorphism">
                <CardHeader>
                  <CardTitle className="text-lg">{t('listing.bidHistory')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {bids.slice(0, 5).map((bid) => (
                      <div key={bid.id} className="flex justify-between items-center py-2 border-b last:border-0">
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm">Bidder</span>
                        </div>
                        <span className="font-semibold">${bid.amount.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
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
    </div>
  );
};

export default ListingDetailPage;
