import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
  Package, Clock, MapPin, User, Calendar, 
  ArrowLeft, Gavel, AlertCircle, TrendingUp,
  Grid, List, ZoomIn, Menu, X, Flame
} from 'lucide-react';
import Countdown from 'react-countdown';
import Lightbox from 'react-image-lightbox';
import 'react-image-lightbox/style.css';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MultiItemListingDetailPage = () => {
  const { id } = useParams();
  const { user } = useAuth();
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
  const lotRefs = useRef({});

  useEffect(() => {
    fetchListing();
  }, [id]);

  const fetchListing = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/multi-item-listings/${id}`);
      setListing(response.data);
    } catch (error) {
      console.error('Failed to fetch listing:', error);
      toast.error('Failed to load listing');
      navigate('/lots');
    } finally {
      setLoading(false);
    }
  };

  const handleBidChange = (lotNumber, value) => {
    setBidAmounts({ ...bidAmounts, [lotNumber]: value });
  };

  const handlePlaceBid = async (lotNumber) => {
    if (!user) {
      toast.error('Please sign in to place a bid');
      navigate('/auth');
      return;
    }

    const bidAmount = parseFloat(bidAmounts[lotNumber]);
    const lot = listing.lots.find(l => l.lot_number === lotNumber);

    if (!bidAmount || bidAmount <= lot.current_price) {
      toast.error(`Bid must be higher than current price of $${lot.current_price}`);
      return;
    }

    try {
      await axios.post(
        `${API}/multi-item-listings/${id}/lots/${lotNumber}/bid`,
        { amount: bidAmount },
        { headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } }
      );
      toast.success('Bid placed successfully!');
      fetchListing();
      setBidAmounts({ ...bidAmounts, [lotNumber]: '' });
    } catch (error) {
      console.error('Bid failed:', error);
      toast.error(error.response?.data?.detail || 'Failed to place bid');
    }
  };

  const isAuctionEnded = (endDate) => {
    return new Date(endDate) < new Date();
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

  const auctionEnded = isAuctionEnded(listing.auction_end_date);
  const totalStartingValue = listing.lots.reduce((sum, lot) => sum + lot.starting_price, 0);
  const totalCurrentValue = listing.lots.reduce((sum, lot) => sum + lot.current_price, 0);

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-7xl mx-auto">
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
                <div className="flex items-center gap-2 mb-2">
                  <Package className="h-6 w-6 text-primary" />
                  <Badge variant={auctionEnded ? "secondary" : "default"}>
                    {auctionEnded ? 'Auction Ended' : 'Active Auction'}
                  </Badge>
                  <Badge variant="outline">{listing.total_lots} Lots</Badge>
                </div>
                <CardTitle className="text-3xl mb-4">{listing.title}</CardTitle>
                <p className="text-muted-foreground mb-4">{listing.description}</p>

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

        {/* Lots List */}
        <div className="space-y-6">
          <h2 className="text-2xl font-bold mb-4">Available Lots</h2>
          {listing.lots.map((lot) => (
            <Card key={lot.lot_number} className="border-2 hover:border-primary transition-colors">
              <CardContent className="pt-6">
                <div className="flex flex-col md:flex-row gap-6">
                  {/* Images */}
                  {lot.images && lot.images.length > 0 && (
                    <div className="w-full md:w-1/3">
                      <div className="grid grid-cols-2 gap-2">
                        {lot.images.slice(0, 4).map((img, idx) => (
                          <div key={idx} className="aspect-square rounded-lg overflow-hidden bg-gray-100">
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
                      <div>
                        <h3 className="text-xl font-bold mb-1">
                          Lot #{lot.lot_number} - {lot.title}
                        </h3>
                        <Badge variant="outline" className="mb-2">
                          Quantity: {lot.quantity}
                        </Badge>
                        <Badge variant="secondary" className="ml-2">
                          {lot.condition.replace('_', ' ').toUpperCase()}
                        </Badge>
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

                    {/* Bidding Section */}
                    {!auctionEnded && (
                      <div className="flex gap-2 mt-4">
                        <input
                          type="number"
                          step="0.01"
                          min={lot.current_price + 0.01}
                          placeholder={`Min: $${(lot.current_price + 1).toFixed(2)}`}
                          value={bidAmounts[lot.lot_number] || ''}
                          onChange={(e) => handleBidChange(lot.lot_number, e.target.value)}
                          className="flex-1 px-4 py-2 border border-input rounded-md bg-background"
                        />
                        <Button 
                          onClick={() => handlePlaceBid(lot.lot_number)}
                          className="gradient-button text-white border-0"
                        >
                          <Gavel className="mr-2 h-4 w-4" />
                          Place Bid
                        </Button>
                      </div>
                    )}

                    {auctionEnded && (
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
    </div>
  );
};

export default MultiItemListingDetailPage;
