import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Search, Package, Clock, MapPin, Layers } from 'lucide-react';
import Countdown from 'react-countdown';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LotsMarketplacePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [listings, setListings] = useState([]);
  const [categories, setCategories] = useState([]);
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    sort: '-created_at',
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCategories();
    fetchLots();
  }, [filters]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const fetchLots = async () => {
    try {
      setLoading(true);
      const params = Object.entries(filters)
        .filter(([_, value]) => value !== '')
        .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});
      
      const response = await axios.get(`${API}/multi-item-listings`, { params });
      setListings(response.data);
    } catch (error) {
      console.error('Failed to fetch lots:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value });
  };

  const getTotalStartingPrice = (lots) => {
    return lots.reduce((sum, lot) => sum + lot.starting_price, 0);
  };

  const getTotalCurrentPrice = (lots) => {
    return lots.reduce((sum, lot) => sum + lot.current_price, 0);
  };

  return (
    <div className="min-h-screen py-8 px-4" data-testid="lots-marketplace-page">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Package className="h-8 w-8 text-primary" />
            <h1 className="text-3xl md:text-4xl font-bold">
              {t('lotsMarketplace.title', 'Lots Auction')}
            </h1>
          </div>
          <p className="text-muted-foreground mb-6">
            {t('lotsMarketplace.subtitle', 'Browse and bid on grouped item lots from sellers')}
          </p>
          
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
              <Input
                placeholder={t('lotsMarketplace.search', 'Search lots...')}
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                className="pl-10"
                data-testid="search-input"
              />
            </div>
        
            <select
              value={filters.category}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              className="px-4 py-2 border border-input rounded-md bg-background"
              data-testid="category-filter"
            >
              <option value="">{t('marketplace.category', 'Category')}: All</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.name_en}>
                  {cat.name_en}
                </option>
              ))}
            </select>

            <select
              value={filters.sort}
              onChange={(e) => handleFilterChange('sort', e.target.value)}
              className="px-4 py-2 border border-input rounded-md bg-background"
              data-testid="sort-filter"
            >
              <option value="-created_at">{t('marketplace.newest', 'Newest First')}</option>
              <option value="created_at">{t('marketplace.oldest', 'Oldest First')}</option>
              <option value="auction_end_date">{t('marketplace.endingSoon', 'Ending Soon')}</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
          </div>
        ) : listings.length === 0 ? (
          <Card className="p-12 text-center">
            <Package className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-xl font-semibold mb-2">
              {t('lotsMarketplace.noLots', 'No lots found')}
            </h3>
            <p className="text-muted-foreground">
              {t('lotsMarketplace.noLotsDesc', 'Try adjusting your filters or check back later')}
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {listings.map((listing) => {
              const auctionEndDate = new Date(listing.auction_end_date);
              const isEnded = new Date() > auctionEndDate;
              const totalStarting = getTotalStartingPrice(listing.lots);
              const totalCurrent = getTotalCurrentPrice(listing.lots);

              return (
                <Card
                  key={listing.id}
                  className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer glassmorphism"
                  onClick={() => navigate(`/lots/${listing.id}`)}
                  data-testid={`lot-card-${listing.id}`}
                >
                  <div className="aspect-video bg-gradient-to-br from-primary/10 to-accent/10 flex items-center justify-center relative">
                    <Layers className="h-16 w-16 text-primary opacity-50" />
                    <Badge className="absolute top-2 right-2 gradient-bg text-white border-0">
                      <Package className="mr-1 h-3 w-3" />
                      {listing.total_lots} {t('lotsMarketplace.items', 'Items')}
                    </Badge>
                  </div>
                  
                  <CardHeader>
                    <CardTitle className="line-clamp-2">{listing.title}</CardTitle>
                  </CardHeader>
                  
                  <CardContent className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <MapPin className="h-4 w-4" />
                      <span>{listing.city}, {listing.region}</span>
                    </div>
                    
                    <div className="space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">
                          {t('lotsMarketplace.totalBid', 'Total Current Bid')}:
                        </span>
                        <span className="font-bold text-lg gradient-text">
                          ${totalCurrent.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-xs text-muted-foreground">
                        <span>{t('lotsMarketplace.starting', 'Starting')}:</span>
                        <span>${totalStarting.toFixed(2)}</span>
                      </div>
                    </div>
                    
                    {!isEnded ? (
                      <div className="flex items-center gap-2 text-sm">
                        <Clock className="h-4 w-4 text-primary" />
                        <Countdown
                          date={auctionEndDate}
                          renderer={({ days, hours, minutes, seconds, completed }) => (
                            <span className={`font-semibold ${completed ? 'text-red-500' : 'text-primary'}`}>
                              {completed ? t('marketplace.ended', 'Ended') : `${days}d ${hours}h ${minutes}m ${seconds}s`}
                            </span>
                          )}
                        />
                      </div>
                    ) : (
                      <Badge variant="destructive">
                        {t('marketplace.ended', 'Auction Ended')}
                      </Badge>
                    )}

                    <div className="pt-2 border-t">
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {listing.description}
                      </p>
                    </div>
                  </CardContent>
                  
                  <CardFooter>
                    <Button className="w-full gradient-button text-white border-0">
                      {t('lotsMarketplace.viewLot', 'View Lot Details')}
                    </Button>
                  </CardFooter>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default LotsMarketplacePage;