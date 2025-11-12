import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Heart, Clock, Package, MapPin, Tag, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';
import WatchlistButton from '../components/WatchlistButton';
import Countdown from 'react-countdown';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WatchlistPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [watchlistData, setWatchlistData] = useState({
    listings: [],
    auctions: [],
    lots: [],
    total: 0
  });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');

  useEffect(() => {
    fetchWatchlist();
  }, []);

  const fetchWatchlist = async () => {
    try {
      const response = await axios.get(`${API}/watchlist`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
      });
      setWatchlistData(response.data);
    } catch (error) {
      console.error('Failed to fetch watchlist:', error);
      toast.error('Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  };

  // Render marketplace listing card
  const renderListingCard = (listing) => {
    const auctionEndDate = listing.auction_end_date ? new Date(listing.auction_end_date) : null;
    const isEnded = auctionEndDate && new Date() > auctionEndDate;

    return (
      <Card 
        key={listing.id}
        className="overflow-hidden hover:shadow-lg transition-all duration-200 group"
      >
        <div className="relative cursor-pointer" onClick={() => navigate(`/listing/${listing.id}`)}>
          <div className="absolute top-2 right-2 z-10" onClick={(e) => e.stopPropagation()}>
            <WatchlistButton itemId={listing.id} itemType="listing" size="default" />
          </div>
          <Badge className="absolute top-2 left-2 z-10 bg-red-500 hover:bg-red-600">Watched</Badge>
          <div className="aspect-video overflow-hidden bg-gray-100">
            {listing.images && listing.images.length > 0 ? (
              <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-6xl">📦</div>
            )}
          </div>
        </div>
        <CardContent className="p-4 space-y-3">
          <div>
            <h3 className="font-semibold line-clamp-2 mb-2">{listing.title}</h3>
            <div className="flex flex-wrap gap-2 mb-2">
              <Badge variant="secondary" className="text-xs"><Tag className="h-3 w-3 mr-1" />{listing.category}</Badge>
              <Badge variant="outline" className="text-xs">Marketplace</Badge>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <MapPin className="h-4 w-4" /><span className="truncate">{listing.city}, {listing.region}</span>
          </div>
          <div className="flex items-center justify-between pt-2 border-t">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              {isEnded ? (<span className="text-sm font-semibold text-red-500">Ended</span>) : (
                <Countdown date={auctionEndDate} renderer={({ days, hours, minutes }) => (
                  <span className="text-sm font-semibold text-primary">{days}d {hours}h {minutes}m</span>
                )} />
              )}
            </div>
            <span className="text-lg font-bold text-primary">${listing.current_price?.toFixed(2)}</span>
          </div>
          <Button 
            onClick={() => navigate(`/listing/${listing.id}`)} 
            className="w-full mt-2"
            variant="outline"
          >
            {t('watchlist.viewListing', 'View Listing')}
          </Button>
        </CardContent>
      </Card>
    );
  };

  // Render multi-lot auction card
  const renderAuctionCard = (auction) => {
    const auctionEndDate = auction.auction_end_date ? new Date(auction.auction_end_date) : null;
    const isEnded = auctionEndDate && new Date() > auctionEndDate;

    return (
      <Card key={auction.id} className="overflow-hidden hover:shadow-lg transition-all duration-200 group">
        <div className="relative cursor-pointer" onClick={() => navigate(`/lots/${auction.id}`)}>
          <div className="absolute top-2 right-2 z-10" onClick={(e) => e.stopPropagation()}>
            <WatchlistButton itemId={auction.id} itemType="auction" size="default" />
          </div>
          <Badge className="absolute top-2 left-2 z-10 bg-red-500 hover:bg-red-600">Watched</Badge>
          <div className="aspect-video overflow-hidden bg-gray-100">
            {auction.lots && auction.lots[0]?.images && auction.lots[0].images.length > 0 ? (
              <img src={auction.lots[0].images[0]} alt={auction.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-6xl">🎯</div>
            )}
          </div>
        </div>
        <CardContent className="p-4 space-y-3">
          <div>
            <h3 className="font-semibold line-clamp-2 mb-2">{auction.title}</h3>
            <div className="flex flex-wrap gap-2 mb-2">
              <Badge variant="secondary" className="text-xs"><Tag className="h-3 w-3 mr-1" />{auction.category}</Badge>
              <Badge variant="default" className="text-xs bg-purple-500">Multi-Lot</Badge>
              {auction.is_featured && (<Badge className="text-xs bg-orange-500">⭐ Featured</Badge>)}
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Package className="h-4 w-4" /><span>{auction.total_lots} Lots</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <MapPin className="h-4 w-4" /><span className="truncate">{auction.city}, {auction.region}</span>
          </div>
          <div className="flex items-center justify-between pt-2 border-t">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              {isEnded ? (<span className="text-sm font-semibold text-red-500">Ended</span>) : (
                <Countdown date={auctionEndDate} renderer={({ days, hours, minutes }) => (
                  <span className="text-sm font-semibold text-primary">{days}d {hours}h {minutes}m</span>
                )} />
              )}
            </div>
          </div>
          <Button 
            onClick={() => navigate(`/lots/${auction.id}`)} 
            className="w-full mt-2"
            variant="outline"
          >
            {t('watchlist.goToAuction', 'Go to Auction')}
          </Button>
        </CardContent>
      </Card>
    );
  };

  // Render individual lot card
  const renderLotCard = (lotItem) => {
    const lot = lotItem.lot;
    const auctionId = lotItem.auction_id;
    return (
      <Card key={`${auctionId}:${lot.lot_number}`} className="overflow-hidden hover:shadow-lg transition-all duration-200 group">
        <div className="relative cursor-pointer" onClick={() => navigate(`/lots/${auctionId}#lot-${lot.lot_number}`)}>
          <div className="absolute top-2 right-2 z-10" onClick={(e) => e.stopPropagation()}>
            <WatchlistButton itemId={`${auctionId}:${lot.lot_number}`} itemType="lot" size="default" />
          </div>
          <Badge className="absolute top-2 left-2 z-10 bg-red-500 hover:bg-red-600">Watched</Badge>
          <div className="aspect-video overflow-hidden bg-gray-100">
            {lot.images && lot.images.length > 0 ? (
              <img src={lot.images[0]} alt={lot.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-6xl">🎲</div>
            )}
          </div>
        </div>
        <CardContent className="p-4 space-y-3">
          <div>
            <Badge variant="outline" className="mb-2 text-xs">Lot #{lot.lot_number}</Badge>
            <h3 className="font-semibold line-clamp-2 mb-1">{lot.title}</h3>
            <p className="text-xs text-muted-foreground line-clamp-1">From: {lotItem.auction_title}</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Package className="h-4 w-4" /><span>Qty: {lot.quantity}</span>
          </div>
          <div className="flex items-center justify-between pt-2 border-t">
            <span className="text-sm text-muted-foreground">Current:</span>
            <span className="text-lg font-bold text-primary">${lot.current_price?.toFixed(2)}</span>
          </div>
          <Button 
            onClick={() => navigate(`/lots/${auctionId}#lot-${lot.lot_number}`)} 
            className="w-full mt-2"
            variant="outline"
          >
            {t('watchlist.viewLot', 'View Lot')}
          </Button>
        </CardContent>
      </Card>
    );
  };

  if (loading) {
    return (<div className="min-h-screen flex items-center justify-center"><div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div></div>);
  }

  const totalItems = watchlistData.total || 0;
  const hasItems = totalItems > 0;

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2 flex items-center gap-3"><Heart className="h-8 w-8 text-red-500 fill-red-500" />My Watchlist</h1>
            <p className="text-muted-foreground">{totalItems} {totalItems === 1 ? 'item' : 'items'} saved</p>
          </div>
          <Button variant="outline" onClick={() => navigate('/marketplace')} className="hidden sm:flex gap-2"><TrendingUp className="h-4 w-4" />Browse Marketplace</Button>
        </div>
        {hasItems ? (
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-4 mb-6">
              <TabsTrigger value="all">All ({totalItems})</TabsTrigger>
              <TabsTrigger value="auctions">Auctions ({watchlistData.auctions?.length || 0})</TabsTrigger>
              <TabsTrigger value="lots">Lots ({watchlistData.lots?.length || 0})</TabsTrigger>
              <TabsTrigger value="marketplace">Marketplace ({watchlistData.listings?.length || 0})</TabsTrigger>
            </TabsList>
            <TabsContent value="all" className="space-y-8">
              {watchlistData.auctions && watchlistData.auctions.length > 0 && (
                <div><h2 className="text-2xl font-semibold mb-4">Multi-Lot Auctions</h2><div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">{watchlistData.auctions.map(renderAuctionCard)}</div></div>
              )}
              {watchlistData.lots && watchlistData.lots.length > 0 && (
                <div><h2 className="text-2xl font-semibold mb-4">Individual Lots</h2><div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">{watchlistData.lots.map(renderLotCard)}</div></div>
              )}
              {watchlistData.listings && watchlistData.listings.length > 0 && (
                <div><h2 className="text-2xl font-semibold mb-4">Marketplace Items</h2><div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">{watchlistData.listings.map(renderListingCard)}</div></div>
              )}
            </TabsContent>
            <TabsContent value="auctions">{watchlistData.auctions && watchlistData.auctions.length > 0 ? (<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">{watchlistData.auctions.map(renderAuctionCard)}</div>) : (<div className="text-center py-12"><p className="text-muted-foreground">No auctions in your watchlist</p></div>)}</TabsContent>
            <TabsContent value="lots">{watchlistData.lots && watchlistData.lots.length > 0 ? (<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">{watchlistData.lots.map(renderLotCard)}</div>) : (<div className="text-center py-12"><p className="text-muted-foreground">No lots in your watchlist</p></div>)}</TabsContent>
            <TabsContent value="marketplace">{watchlistData.listings && watchlistData.listings.length > 0 ? (<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">{watchlistData.listings.map(renderListingCard)}</div>) : (<div className="text-center py-12"><p className="text-muted-foreground">No marketplace items in your watchlist</p></div>)}</TabsContent>
          </Tabs>
        ) : (
          <Card className="p-12">
            <div className="text-center space-y-4">
              <Heart className="h-16 w-16 mx-auto text-muted-foreground opacity-50" />
              <h3 className="text-xl font-semibold">
                {t('watchlist.emptyTitle', "You're not watching any items yet")}
              </h3>
              <p className="text-muted-foreground max-w-md mx-auto">
                {t('watchlist.emptyDescription', "Start exploring auctions or listings to track your favorites.")}
              </p>
              <div className="flex gap-3 justify-center pt-4">
                <Button onClick={() => navigate('/marketplace')}>
                  {t('watchlist.browseMarketplace', 'Browse Marketplace')}
                </Button>
                <Button variant="outline" onClick={() => navigate('/lots')}>
                  {t('watchlist.viewAuctions', 'View Auctions')}
                </Button>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};

export default WatchlistPage;
