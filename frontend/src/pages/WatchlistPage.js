import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Heart, Clock, Eye, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';
import WatchlistButton from '../components/WatchlistButton';
import Countdown from 'react-countdown';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WatchlistPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [watchlist, setWatchlist] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWatchlist();
  }, []);

  const fetchWatchlist = async () => {
    try {
      const response = await axios.get(`${API}/watchlist`);
      setWatchlist(response.data);
    } catch (error) {
      console.error('Failed to fetch watchlist:', error);
      toast.error('Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveItem = () => {
    // Refresh watchlist after item is removed
    fetchWatchlist();
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
              <Heart className="h-8 w-8 text-red-500 fill-red-500" />
              My Watchlist
            </h1>
            <p className="text-muted-foreground">
              {watchlist.length} {watchlist.length === 1 ? 'item' : 'items'} saved
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => navigate('/marketplace')}
            className="hidden sm:flex"
          >
            Browse Marketplace
          </Button>
        </div>

        {/* Watchlist Grid */}
        {watchlist.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {watchlist.map((listing) => {
              const auctionEndDate = listing.auction_end_date ? new Date(listing.auction_end_date) : null;
              const isEnded = auctionEndDate && new Date() > auctionEndDate;
              const timeLeft = auctionEndDate ? auctionEndDate - new Date() : 0;
              const isUrgent = timeLeft > 0 && timeLeft < 3600000; // Less than 1 hour

              return (
                <Card 
                  key={listing.id} 
                  className="group overflow-hidden hover:shadow-xl transition-all duration-300 cursor-pointer"
                  onClick={() => navigate(`/listing/${listing.id}`)}
                >
                  {/* Image with Watchlist Button */}
                  <div className="relative h-56 bg-gray-100 overflow-hidden">
                    {listing.images?.[0] ? (
                      <img 
                        src={listing.images[0]} 
                        alt={listing.title} 
                        className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-6xl">📦</div>
                    )}
                    
                    {/* Watchlist Button - Top Right */}
                    <div className="absolute top-3 right-3 z-10">
                      <div 
                        className="bg-white dark:bg-gray-900 rounded-full p-2 shadow-lg"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <WatchlistButton 
                          listingId={listing.id} 
                          size="default"
                          className="hover:scale-110"
                        />
                      </div>
                    </div>

                    {/* Countdown Timer - Top Left */}
                    {auctionEndDate && !isEnded && (
                      <div className="absolute top-3 left-3 z-10">
                        <Badge className={`${isUrgent ? 'bg-red-600 animate-pulse' : 'bg-blue-600'} text-white border-0 shadow-lg`}>
                          <Clock className="h-3 w-3 mr-1" />
                          <Countdown
                            date={auctionEndDate}
                            renderer={({ days, hours, minutes }) => (
                              <span className="font-bold text-xs">
                                {days}d {hours}h {minutes}m
                              </span>
                            )}
                          />
                        </Badge>
                      </div>
                    )}

                    {/* Status Badge */}
                    {isEnded && (
                      <div className="absolute bottom-3 left-3">
                        <Badge variant="destructive">Auction Ended</Badge>
                      </div>
                    )}
                    {listing.is_promoted && (
                      <div className="absolute bottom-3 right-3">
                        <Badge className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white border-0">
                          <TrendingUp className="h-3 w-3 mr-1" />
                          Featured
                        </Badge>
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <CardContent className="p-4 space-y-3">
                    <h3 className="font-bold text-lg line-clamp-2 group-hover:text-primary transition-colors">
                      {listing.title}
                    </h3>
                    
                    {/* Price */}
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground uppercase">Current Bid</p>
                      <p className="text-2xl font-bold gradient-text">
                        ${listing.current_price?.toFixed(2) || listing.starting_price?.toFixed(2)}
                      </p>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Eye className="h-4 w-4" />
                        {listing.bid_count || 0} bids
                      </span>
                      {listing.category && (
                        <Badge variant="outline" className="text-xs">{listing.category}</Badge>
                      )}
                    </div>

                    {/* Action Button */}
                    <Button 
                      className="w-full gradient-button text-white border-0 font-semibold mt-3"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/listing/${listing.id}`);
                      }}
                    >
                      {isEnded ? 'View Details' : 'Place Bid'}
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        ) : (
          /* Empty State */
          <Card className="p-12">
            <div className="text-center space-y-4">
              <div className="w-24 h-24 mx-auto bg-gradient-to-br from-pink-100 to-red-50 dark:from-pink-950 dark:to-red-900 rounded-full flex items-center justify-center">
                <Heart className="h-12 w-12 text-pink-600" />
              </div>
              <div>
                <h3 className="text-2xl font-semibold mb-2">Your Watchlist is Empty</h3>
                <p className="text-muted-foreground max-w-md mx-auto">
                  Start saving items you're interested in to keep track of them easily. Click the heart icon on any listing to add it to your watchlist.
                </p>
              </div>
              <Button 
                className="gradient-button text-white border-0 font-semibold"
                onClick={() => navigate('/marketplace')}
              >
                Browse Marketplace
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};

export default WatchlistPage;
