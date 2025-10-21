import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Search, Filter, Clock } from 'lucide-react';
import Countdown from 'react-countdown';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MarketplacePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [listings, setListings] = useState([]);
  const [categories, setCategories] = useState([]);
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    city: '',
    condition: '',
    min_price: '',
    max_price: '',
    sort: '-created_at',
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCategories();
    fetchListings();
  }, [filters]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const fetchListings = async () => {
    try {
      setLoading(true);
      const params = Object.entries(filters)
        .filter(([_, value]) => value !== '')
        .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});
      
      const response = await axios.get(`${API}/listings`, { params });
      setListings(response.data);
    } catch (error) {
      console.error('Failed to fetch listings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value });
  };

  return (
    <div className="min-h-screen py-8 px-4" data-testid="marketplace-page">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold mb-4">{t('marketplace.title')}</h1>
          
          <div className="flex flex-col md:flex-row gap-4 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
              <Input
                placeholder={t('marketplace.search')}
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
              <option value="">{t('marketplace.category')}: All</option>
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
              <option value="-created_at">{t('marketplace.newest')}</option>
              <option value="auction_end_date">{t('marketplace.ending')}</option>
              <option value="current_price">{t('marketplace.priceLow')}</option>
              <option value="-current_price">{t('marketplace.priceHigh')}</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[...Array(8)].map((_, i) => (
              <Card key={i} className="animate-pulse">
                <div className="h-48 bg-gray-200 rounded-t-lg"></div>
                <CardContent className="p-4 space-y-2">
                  <div className="h-4 bg-gray-200 rounded"></div>
                  <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : listings.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-lg text-muted-foreground">No listings found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {listings.map((listing) => (
              <ListingCard key={listing.id} listing={listing} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const ListingCard = ({ listing }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const auctionEndDate = new Date(listing.auction_end_date);

  return (
    <Card
      className="card-hover cursor-pointer glassmorphism overflow-hidden"
      onClick={() => navigate(`/listing/${listing.id}`)}
      data-testid={`listing-card-${listing.id}`}
    >
      <div className="relative h-48 overflow-hidden bg-gray-100">
        {listing.images && listing.images.length > 0 ? (
          <img
            src={listing.images[0]}
            alt={listing.title}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/10 to-accent/10">
            <span className="text-4xl">📦</span>
          </div>
        )}
        {listing.is_promoted && (
          <Badge className="absolute top-2 right-2 gradient-bg text-white border-0">
            Featured
          </Badge>
        )}
      </div>
      
      <CardContent className="p-4">
        <h3 className="font-semibold text-lg mb-2 line-clamp-1">{listing.title}</h3>
        <div className="space-y-1 text-sm text-muted-foreground">
          <p>{listing.city}, {listing.region}</p>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            <Countdown
              date={auctionEndDate}
              renderer={({ days, hours, minutes, completed }) => (
                <span className={`font-medium ${completed ? 'text-red-500' : 'text-primary'}`}>
                  {completed ? t('marketplace.ended') : `${days}d ${hours}h ${minutes}m`}
                </span>
              )}
            />
          </div>
        </div>
      </CardContent>
      
      <CardFooter className="p-4 pt-0 flex justify-between items-center">
        <div>
          <p className="text-xs text-muted-foreground">{t('marketplace.currentBid')}</p>
          <p className="text-xl font-bold gradient-text">${listing.current_price.toFixed(2)}</p>
        </div>
        <Badge variant="outline">{listing.bid_count} {t('marketplace.bids')}</Badge>
      </CardFooter>
    </Card>
  );
};

export default MarketplacePage;
