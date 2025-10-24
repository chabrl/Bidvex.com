import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { DollarSign, Gavel, Trophy, Heart, TrendingUp, TrendingDown, Eye } from 'lucide-react';
import { toast } from 'sonner';
import Countdown from 'react-countdown';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BuyerDashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/buyer`);
      setDashboard(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4" data-testid="buyer-dashboard">
      <div className="max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">{t('dashboard.buyer.title')}</h1>
          <p className="text-muted-foreground">Track your bids and wins</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <StatCard
            icon={<Gavel className="h-6 w-6" />}
            title={t('dashboard.buyer.activeBids')}
            value={dashboard?.active_bids || 0}
            color="blue"
          />
          <StatCard
            icon={<Trophy className="h-6 w-6" />}
            title={t('dashboard.buyer.wonItems')}
            value={dashboard?.won_items || 0}
            color="green"
          />
          <StatCard
            icon={<DollarSign className="h-6 w-6" />}
            title="Total Bids"
            value={dashboard?.total_bids || 0}
            color="purple"
          />
        </div>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>My Bids Dashboard</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="all" className="space-y-4">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="all">All Bids</TabsTrigger>
                <TabsTrigger value="winning" className="text-green-600">Winning</TabsTrigger>
                <TabsTrigger value="losing" className="text-red-600">Losing</TabsTrigger>
                <TabsTrigger value="watching">Watching</TabsTrigger>
              </TabsList>

              <TabsContent value="all">
                {dashboard?.bids && dashboard.bids.length > 0 ? (
                  <div className="space-y-4">
                    {dashboard.bids.map((bid) => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      const isWinning = listing && listing.current_price === bid.amount;
                      const auctionEndDate = listing ? new Date(listing.auction_end_date) : null;
                      const isEnded = auctionEndDate && new Date() > auctionEndDate;
                      const timeLeft = auctionEndDate ? auctionEndDate - new Date() : 0;
                      const isUrgent = timeLeft > 0 && timeLeft < 3600000; // Less than 1 hour

                      return (
                        <Card key={bid.id} className={`overflow-hidden ${isWinning ? 'border-2 border-green-500' : 'border-2 border-gray-200'}`}>
                          {/* Status Badge - Top Left */}
                          <div className="relative">
                            <div className="absolute top-3 left-3 z-10">
                              {isWinning ? (
                                <Badge className="bg-green-600 text-white border-0 text-sm px-3 py-1.5">
                                  <TrendingUp className="h-4 w-4 mr-1" />
                                  WINNING
                                </Badge>
                              ) : (
                                <Badge variant="destructive" className="text-sm px-3 py-1.5">
                                  <TrendingDown className="h-4 w-4 mr-1" />
                                  OUTBID
                                </Badge>
                              )}
                            </div>

                            {/* Countdown - Top Right */}
                            {auctionEndDate && !isEnded && (
                              <div className="absolute top-3 right-3 z-10">
                                <Badge className={`${isUrgent ? 'bg-red-600 animate-pulse' : 'bg-blue-600'} text-white border-0 text-sm px-3 py-1.5`}>
                                  <Countdown
                                    date={auctionEndDate}
                                    renderer={({ days, hours, minutes }) => (
                                      <span className="font-bold">{days}d {hours}h {minutes}m</span>
                                    )}
                                  />
                                </Badge>
                              </div>
                            )}

                            {/* Image */}
                            <div className="w-full h-48 bg-gray-100">
                              {listing?.images?.[0] ? (
                                <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-6xl">📦</div>
                              )}
                            </div>
                          </div>

                          {/* Content Section */}
                          <CardContent className="p-4 space-y-4">
                            <h3 className="font-bold text-xl line-clamp-2">{listing?.title || 'Listing'}</h3>

                            {/* Bid Comparison - Clear Layout */}
                            <div className="grid grid-cols-2 gap-3 p-3 bg-accent/10 rounded-lg">
                              <div>
                                <p className="text-xs text-muted-foreground uppercase mb-1">Your Bid</p>
                                <p className="text-xl font-bold">${bid.amount.toFixed(2)}</p>
                              </div>
                              <div>
                                <p className="text-xs text-muted-foreground uppercase mb-1">Current Price</p>
                                <p className="text-xl font-bold gradient-text">${listing?.current_price.toFixed(2)}</p>
                              </div>
                            </div>

                            {/* Additional Info */}
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <Badge variant="outline">{listing?.bid_count || 0} bids</Badge>
                              {isEnded && <Badge variant="outline">Auction Ended</Badge>}
                            </div>
                          </CardContent>

                          {/* Action Buttons - Full Width on Mobile */}
                          <CardFooter className="p-4 pt-0 gap-2 flex-col sm:flex-row">
                            <Button 
                              variant="outline" 
                              className="w-full sm:flex-1" 
                              onClick={() => navigate(`/listing/${bid.listing_id}`)}
                            >
                              View Listing
                            </Button>
                            {!isWinning && !isEnded && (
                              <Button 
                                className="w-full sm:flex-1 gradient-button text-white border-0 font-semibold" 
                                onClick={() => navigate(`/listing/${bid.listing_id}`)}
                              >
                                Place Higher Bid
                              </Button>
                            )}
                          </CardFooter>
                        </Card>
                      );
                    })}
                  </div>
                ) : (
                  <Card className="p-12">
                    <div className="text-center space-y-4">
                      <div className="w-20 h-20 mx-auto bg-gradient-to-br from-primary/10 to-accent/10 rounded-full flex items-center justify-center">
                        <Gavel className="h-10 w-10 text-primary" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold mb-2">No Active Bids</h3>
                        <p className="text-muted-foreground">Start bidding on auctions to see them here!</p>
                      </div>
                      <Button className="gradient-button text-white border-0" onClick={() => navigate('/marketplace')}>
                        Browse Marketplace
                      </Button>
                    </div>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="winning">
                {dashboard?.bids?.filter(bid => {
                  const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                  return listing && listing.current_price === bid.amount;
                }).length > 0 ? (
                  <div className="space-y-4">
                    {dashboard.bids.filter(bid => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      return listing && listing.current_price === bid.amount;
                    }).map((bid) => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      return (
                        <Card key={bid.id} className="border-2 border-green-500 overflow-hidden">
                          <div className="relative h-32 bg-gradient-to-br from-green-50 to-green-100 dark:from-green-950 dark:to-green-900 flex items-center justify-center">
                            <Badge className="absolute top-3 left-3 bg-green-600 text-white text-sm px-3 py-1.5">
                              <Trophy className="h-4 w-4 mr-1" />
                              WINNING
                            </Badge>
                            <TrendingUp className="h-16 w-16 text-green-600 opacity-20" />
                          </div>
                          <CardContent className="p-4 space-y-3">
                            <h3 className="font-bold text-lg">{listing?.title}</h3>
                            <div className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-950 rounded-lg">
                              <div>
                                <p className="text-xs text-muted-foreground uppercase">Your Winning Bid</p>
                                <p className="text-2xl font-bold text-green-600">${bid.amount.toFixed(2)}</p>
                              </div>
                            </div>
                          </CardContent>
                          <CardFooter className="p-4 pt-0">
                            <Button className="w-full" variant="outline" onClick={() => navigate(`/listing/${bid.listing_id}`)}>
                              View Listing Details
                            </Button>
                          </CardFooter>
                        </Card>
                      );
                    })}
                  </div>
                ) : (
                  <Card className="p-12">
                    <div className="text-center space-y-4">
                      <div className="w-20 h-20 mx-auto bg-gradient-to-br from-green-100 to-green-50 dark:from-green-950 dark:to-green-900 rounded-full flex items-center justify-center">
                        <Trophy className="h-10 w-10 text-green-600" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold mb-2">No Winning Bids Yet</h3>
                        <p className="text-muted-foreground">Keep bidding to win amazing items!</p>
                      </div>
                    </div>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="losing">
                {dashboard?.bids?.filter(bid => {
                  const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                  return listing && listing.current_price > bid.amount;
                }).length > 0 ? (
                  <div className="space-y-4">
                    {dashboard.bids.filter(bid => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      return listing && listing.current_price > bid.amount;
                    }).map((bid) => {
                      const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                      return (
                        <Card key={bid.id} className="border-2 border-red-500 overflow-hidden">
                          <div className="relative h-32 bg-gradient-to-br from-red-50 to-red-100 dark:from-red-950 dark:to-red-900 flex items-center justify-center">
                            <Badge className="absolute top-3 left-3 bg-red-600 text-white text-sm px-3 py-1.5">
                              <TrendingDown className="h-4 w-4 mr-1" />
                              OUTBID
                            </Badge>
                            <AlertTriangle className="h-16 w-16 text-red-600 opacity-20" />
                          </div>
                          <CardContent className="p-4 space-y-3">
                            <h3 className="font-bold text-lg">{listing?.title}</h3>
                            <div className="grid grid-cols-2 gap-3">
                              <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded-lg">
                                <p className="text-xs text-muted-foreground uppercase mb-1">Your Bid</p>
                                <p className="text-lg font-bold">${bid.amount.toFixed(2)}</p>
                              </div>
                              <div className="p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                                <p className="text-xs text-muted-foreground uppercase mb-1">Current Bid</p>
                                <p className="text-lg font-bold text-red-600">${listing?.current_price.toFixed(2)}</p>
                              </div>
                            </div>
                          </CardContent>
                          <CardFooter className="p-4 pt-0">
                            <Button className="w-full gradient-button text-white border-0 font-semibold" onClick={() => navigate(`/listing/${bid.listing_id}`)}>
                              Place Higher Bid Now
                            </Button>
                          </CardFooter>
                        </Card>
                      );
                    })}
                  </div>
                ) : (
                  <Card className="p-12">
                    <div className="text-center space-y-4">
                      <div className="w-20 h-20 mx-auto bg-gradient-to-br from-blue-100 to-blue-50 dark:from-blue-950 dark:to-blue-900 rounded-full flex items-center justify-center">
                        <TrendingUp className="h-10 w-10 text-blue-600" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold mb-2">All Your Bids Are Leading!</h3>
                        <p className="text-muted-foreground">Great job! Keep an eye on your auctions.</p>
                      </div>
                    </div>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="watching">
                {dashboard?.watchlist && dashboard.watchlist.length > 0 ? (
                  <div className="space-y-4">
                    {dashboard.watchlist.map((listing) => (
                      <div key={listing.id} className="p-4 border rounded-lg hover:bg-accent/10 transition-colors">
                        <div className="flex gap-4">
                          <div className="w-20 h-20 rounded-lg overflow-hidden bg-gray-100">
                            {listing.images?.[0] ? (
                              <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">📦</div>
                            )}
                          </div>
                          <div className="flex-1">
                            <h3 className="font-semibold mb-1">{listing.title}</h3>
                            <p className="text-sm text-muted-foreground">Current Bid: <strong className="gradient-text">${listing.current_price.toFixed(2)}</strong></p>
                          </div>
                          <Button size="sm" variant="outline" onClick={() => navigate(`/listing/${listing.id}`)}>
                            <Eye className="h-4 w-4 mr-1" />
                            View
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Heart className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                    <p className="text-muted-foreground">No watchlist items yet</p>
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>Purchase History</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard?.bids && dashboard.bids.length > 0 ? (
              <div className="space-y-4">
                {dashboard.bids.slice(0, 5).map((bid) => {
                  const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                  if (!listing) return null;
                  
                  return (
                    <div
                      key={bid.id}
                      className="flex flex-col sm:flex-row gap-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                      data-testid={`bid-item-${bid.id}`}
                    >
                      <div className="w-full sm:w-24 h-24 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                        {listing.images && listing.images[0] ? (
                          <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">📦</div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <h3 className="font-semibold truncate">{listing.title}</h3>
                          <Badge variant={listing.status === 'active' ? 'default' : 'secondary'}>
                            {listing.status}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground mb-2">
                          <span>Your Bid: ${bid.amount.toFixed(2)}</span>
                          <span>Current: ${listing.current_price.toFixed(2)}</span>
                          {bid.amount >= listing.current_price && listing.status === 'active' && (
                            <Badge variant="default" className="text-xs">Winning</Badge>
                          )}
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/listing/${listing.id}`)}
                        >
                          View Listing
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12">
                <Gavel className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No bids yet</p>
                <Button onClick={() => navigate('/marketplace')} className="gradient-button text-white border-0">
                  Start Bidding
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const StatCard = ({ icon, title, value, color }) => (
  <Card className="glassmorphism">
    <CardContent className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-xl bg-${color}-100 dark:bg-${color}-900/20 text-${color}-600`}>
          {icon}
        </div>
      </div>
      <p className="text-2xl font-bold mb-1">{value}</p>
      <p className="text-sm text-muted-foreground">{title}</p>
    </CardContent>
  </Card>
);

export default BuyerDashboard;
