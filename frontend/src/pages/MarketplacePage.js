import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Search, Filter, Clock, MapPin, Grid3x3, List } from 'lucide-react';
import Countdown from 'react-countdown';
import LocationSearchMap from '../components/LocationSearchMap';
import WatchlistButton from '../components/WatchlistButton';
import SocialShare from '../components/SocialShare';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MarketplacePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [listings, setListings] = useState([]);
  const [categories, setCategories] = useState([]);
  const [viewMode, setViewMode] = useState(() => {
    return localStorage.getItem('bidvex_view_mode') || 'grid';
  });
  
  // Enhanced filters with session persistence
  const [filters, setFilters] = useState(() => {
    const saved = localStorage.getItem('bidvex_marketplace_filters');
    return saved ? JSON.parse(saved) : {
      search: '',
      category: '',
      city: '',
      condition: '',
      min_price: '',
      max_price: '',
      status: '', // New: 'active', 'upcoming', 'ended'
      seller_rating: '', // New: min rating filter
      location: '', // New: location filter
      sort: '-created_at',
    };
  });
  
  const [loading, setLoading] = useState(true);
  const [showLocationSearch, setShowLocationSearch] = useState(false);
  const [locationParams, setLocationParams] = useState(null);

  // Save filters to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('bidvex_marketplace_filters', JSON.stringify(filters));
  }, [filters]);

  // Save view mode to localStorage
  useEffect(() => {
    localStorage.setItem('bidvex_view_mode', viewMode);
  }, [viewMode]);

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
      
      if (locationParams) {
        // Use location-based search
        const response = await axios.post(`${API}/listings/search/location`, {
          ...locationParams,
          category: filters.category || null,
          min_price: filters.min_price ? parseFloat(filters.min_price) : null,
          max_price: filters.max_price ? parseFloat(filters.max_price) : null,
        });
        setListings(response.data);
      } else {
        // Use regular search
        const params = Object.entries(filters)
          .filter(([_, value]) => value !== '')
          .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});
        
        const response = await axios.get(`${API}/listings`, { params });
        setListings(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch listings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLocationSearch = (params) => {
    setLocationParams(params);
    setShowLocationSearch(false);
  };

  const clearLocationSearch = () => {
    setLocationParams(null);
  };

  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value });
  };

  return (
    <div className="min-h-screen py-8 px-4" data-testid="marketplace-page">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-3xl md:text-4xl font-bold">{t('marketplace.title')}</h1>
            
            {/* Grid/List Toggle */}
            <div className="flex gap-2 bg-muted rounded-lg p-1">
              <Button
                variant={viewMode === 'grid' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('grid')}
                className="gap-2"
                title="Grid View"
              >
                <Grid3x3 className="h-4 w-4" />
                <span className="hidden sm:inline">Grid</span>
              </Button>
              <Button
                variant={viewMode === 'list' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('list')}
                className="gap-2"
                title="List View"
              >
                <List className="h-4 w-4" />
                <span className="hidden sm:inline">List</span>
              </Button>
            </div>
          </div>
          
          <div className="flex flex-col gap-4 mb-6">
            <div className="flex gap-2">
              <Button
                variant={!showLocationSearch ? "default" : "outline"}
                onClick={() => setShowLocationSearch(false)}
                data-testid="search-by-text-btn"
              >
                <Search className="mr-2 h-4 w-4" />
                Text Search
              </Button>
              <Button
                variant={showLocationSearch ? "default" : "outline"}
                onClick={() => setShowLocationSearch(true)}
                data-testid="search-by-location-btn"
              >
                <MapPin className="mr-2 h-4 w-4" />
                Location Search
              </Button>
              {locationParams && (
                <Button variant="ghost" onClick={clearLocationSearch} size="sm">
                  Clear Location Filter
                </Button>
              )}
            </div>

            {showLocationSearch ? (
              <LocationSearchMap onLocationSearch={handleLocationSearch} />
            ) : (
              <div className="space-y-4">
                {/* Search Bar */}
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

                {/* Filter Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                  {/* Category Filter */}
                  <select
                    value={filters.category}
                    onChange={(e) => handleFilterChange('category', e.target.value)}
                    className="px-4 py-2 border border-input rounded-md bg-background text-sm"
                    data-testid="category-filter"
                  >
                    <option value="">Category: All</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.name_en}>
                        {cat.name_en}
                      </option>
                    ))}
                  </select>

                  {/* Status Filter */}
                  <select
                    value={filters.status}
                    onChange={(e) => handleFilterChange('status', e.target.value)}
                    className="px-4 py-2 border border-input rounded-md bg-background text-sm"
                    data-testid="status-filter"
                  >
                    <option value="">Status: All</option>
                    <option value="active">Live</option>
                    <option value="upcoming">Upcoming</option>
                    <option value="ended">Ended</option>
                  </select>

                  {/* Condition Filter */}
                  <select
                    value={filters.condition}
                    onChange={(e) => handleFilterChange('condition', e.target.value)}
                    className="px-4 py-2 border border-input rounded-md bg-background text-sm"
                    data-testid="condition-filter"
                  >
                    <option value="">Condition: All</option>
                    <option value="new">New</option>
                    <option value="like-new">Like New</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                    <option value="used">Used</option>
                  </select>

                  {/* Seller Rating Filter */}
                  <select
                    value={filters.seller_rating}
                    onChange={(e) => handleFilterChange('seller_rating', e.target.value)}
                    className="px-4 py-2 border border-input rounded-md bg-background text-sm"
                    data-testid="rating-filter"
                  >
                    <option value="">Min Rating: All</option>
                    <option value="4.5">4.5+ Stars</option>
                    <option value="4.0">4.0+ Stars</option>
                    <option value="3.5">3.5+ Stars</option>
                    <option value="3.0">3.0+ Stars</option>
                  </select>
                </div>

                {/* Price Range & Sort Row */}
                <div className="flex flex-col md:flex-row gap-3">
                  {/* Price Range */}
                  <div className="flex gap-2 flex-1">
                    <Input
                      type="number"
                      placeholder="Min Price"
                      value={filters.min_price}
                      onChange={(e) => handleFilterChange('min_price', e.target.value)}
                      className="flex-1 text-sm"
                      data-testid="min-price-input"
                    />
                    <span className="flex items-center text-muted-foreground">-</span>
                    <Input
                      type="number"
                      placeholder="Max Price"
                      value={filters.max_price}
                      onChange={(e) => handleFilterChange('max_price', e.target.value)}
                      className="flex-1 text-sm"
                      data-testid="max-price-input"
                    />
                  </div>

                  {/* Sort Dropdown */}
                  <select
                    value={filters.sort}
                    onChange={(e) => handleFilterChange('sort', e.target.value)}
                    className="px-4 py-2 border border-input rounded-md bg-background text-sm md:w-64"
                    data-testid="sort-filter"
                  >
                    <option value="-created_at">Recently Added</option>
                    <option value="auction_end_date">Ending Soon</option>
                    <option value="-current_price">Highest Bid</option>
                    <option value="current_price">Lowest Bid</option>
                    <option value="-views">Most Viewed</option>
                  </select>

                  {/* Clear Filters Button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setFilters({
                        search: '',
                        category: '',
                        city: '',
                        condition: '',
                        min_price: '',
                        max_price: '',
                        status: '',
                        seller_rating: '',
                        location: '',
                        sort: '-created_at',
                      });
                      localStorage.removeItem('bidvex_marketplace_filters');
                    }}
                    className="whitespace-nowrap"
                  >
                    Clear Filters
                  </Button>
                </div>

                {/* Active Filters Display */}
                {Object.entries(filters).some(([key, value]) => value && key !== 'sort') && (
                  <div className="flex flex-wrap gap-2 items-center pt-2">
                    <span className="text-sm text-muted-foreground">Active filters:</span>
                    {Object.entries(filters).map(([key, value]) => {
                      if (!value || key === 'sort') return null;
                      return (
                        <Badge key={key} variant="secondary" className="gap-1">
                          {key.replace('_', ' ')}: {value}
                          <button
                            onClick={() => handleFilterChange(key, '')}
                            className="ml-1 hover:text-destructive"
                          >
                            ×
                          </button>
                        </Badge>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
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
          <div className={viewMode === 'grid' ? 
            "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6" : 
            "flex flex-col gap-4"
          }>
            {listings.map((listing) => (
              <ListingCard key={listing.id} listing={listing} viewMode={viewMode} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const ListingCard = ({ listing, viewMode = 'grid' }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const auctionEndDate = new Date(listing.auction_end_date);

  if (viewMode === 'list') {
    // List View Layout
    return (
      <Card
        className="card-hover cursor-pointer glassmorphism overflow-hidden flex flex-col md:flex-row"
        onClick={() => navigate(`/listing/${listing.id}`)}
        data-testid={`listing-card-${listing.id}`}
      >
        {/* Image */}
        <div className="relative w-full md:w-64 h-48 md:h-auto bg-gray-100 flex-shrink-0">
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
          
          {/* Watchlist Button */}
          <div 
            className="absolute top-2 left-2 z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-white dark:bg-gray-900 rounded-full p-2 shadow-lg">
              <WatchlistButton listingId={listing.id} size="small" />
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-4 flex flex-col">
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1">
              <h3 className="font-semibold text-xl mb-2">{listing.title}</h3>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white text-xs font-bold">
                  {listing.seller_name?.charAt(0) || 'S'}
                </div>
                <span className="text-sm">{listing.seller_name || 'Seller'}</span>
                {listing.seller_verified && (
                  <Badge className="h-4 px-1 text-[10px] bg-blue-600 text-white border-0">✓</Badge>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              {listing.is_promoted && (
                <Badge className="gradient-bg text-white border-0">Featured</Badge>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4 mb-3 flex-wrap">
            <div className="flex items-center gap-2 p-2 bg-accent/10 rounded-md">
              <Clock className="h-4 w-4 text-primary" />
              <Countdown
                date={auctionEndDate}
                renderer={({ days, hours, minutes, completed }) => (
                  <span className={`text-sm font-semibold ${completed ? 'text-red-500' : 'text-primary'}`}>
                    {completed ? t('marketplace.ended') : `${days}d ${hours}h ${minutes}m left`}
                  </span>
                )}
              />
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">{listing.city}, {listing.region}</span>
            </div>
            <Badge variant="outline" className="text-sm">{listing.bid_count} bids</Badge>
          </div>

          <div className="flex items-center justify-between mt-auto pt-3 border-t gap-3">
            <div className="flex-1">
              <p className="text-xs text-muted-foreground">{t('marketplace.currentBid')}</p>
              <p className="text-3xl font-bold gradient-text">${listing.current_price.toFixed(2)}</p>
              {listing.buy_now_price && (
                <p className="text-sm text-green-600 font-semibold">Buy Now: ${listing.buy_now_price.toFixed(2)}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <div onClick={(e) => e.stopPropagation()}>
                <SocialShare 
                  title={listing.title}
                  url={`${window.location.origin}/listing/${listing.id}`}
                  description={`Check out this auction on BidVex: ${listing.title}`}
                />
              </div>
              <Button 
                className="gradient-button text-white border-0 px-8"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/listing/${listing.id}`);
                }}
              >
                {t('marketplace.viewDetails', 'View Details')}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    );
  }

  // Grid View Layout (Original)
  return (
    <Card
      className="card-hover cursor-pointer glassmorphism overflow-hidden"
      onClick={() => navigate(`/listing/${listing.id}`)}
      data-testid={`listing-card-${listing.id}`}
    >
      <div className="relative h-56 md:h-48 overflow-hidden bg-gray-100">
        {listing.images && listing.images.length > 0 ? (
          <img
            src={listing.images[0]}
            alt={listing.title}
            className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/10 to-accent/10">
            <span className="text-4xl">📦</span>
          </div>
        )}
        
        {/* Watchlist Button - Top Left */}
        <div 
          className="absolute top-2 left-2 z-10"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bg-white dark:bg-gray-900 rounded-full p-2 shadow-lg hover:scale-110 transition-transform">
            <WatchlistButton listingId={listing.id} size="small" />
          </div>
        </div>

        <div className="absolute top-2 right-2 flex flex-col gap-1">
          {listing.is_promoted && (
            <Badge className="gradient-bg text-white border-0">
              Featured
            </Badge>
          )}
          {listing.buy_now_price && (
            <Badge className="bg-green-600 text-white border-0">
              Buy Now
            </Badge>
          )}
        </div>
        <div className="absolute bottom-2 left-2 flex items-center gap-1 bg-black/60 backdrop-blur-sm px-2 py-1 rounded-md">
          <MapPin className="h-3 w-3 text-white" />
          <span className="text-xs text-white font-medium">{listing.city}, {listing.region}</span>
        </div>
      </div>
      
      <CardContent className="p-4">
        <h3 className="font-semibold text-lg mb-2 line-clamp-2">{listing.title}</h3>
        
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white text-xs font-bold">
              {listing.seller_name?.charAt(0) || 'S'}
            </div>
            <span className="text-xs">{listing.seller_name || 'Seller'}</span>
            {listing.seller_verified && (
              <Badge className="h-4 px-1 text-[10px] bg-blue-600 text-white border-0">✓</Badge>
            )}
          </div>
          <Badge variant="outline" className="text-xs">{listing.bid_count} bids</Badge>
        </div>

        <div className="flex items-center gap-2 mb-3 p-2 bg-accent/10 rounded-md">
          <Clock className="h-4 w-4 text-primary" />
          <Countdown
            date={auctionEndDate}
            renderer={({ days, hours, minutes, completed }) => (
              <span className={`text-sm font-semibold ${completed ? 'text-red-500' : 'text-primary'}`}>
                {completed ? t('marketplace.ended') : `${days}d ${hours}h ${minutes}m left`}
              </span>
            )}
          />
        </div>
      </CardContent>
      
      <CardFooter className="p-4 pt-0 flex justify-between items-center border-t gap-2">
        <div className="flex-1">
          <p className="text-xs text-muted-foreground">{t('marketplace.currentBid')}</p>
          <p className="text-2xl font-bold gradient-text">${listing.current_price.toFixed(2)}</p>
          {listing.buy_now_price && (
            <p className="text-xs text-green-600">Buy Now: ${listing.buy_now_price.toFixed(2)}</p>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <div onClick={(e) => e.stopPropagation()}>
            <SocialShare 
              title={listing.title}
              url={`${window.location.origin}/listing/${listing.id}`}
              description={`Check out this auction on BidVex: ${listing.title}`}
              className="w-full"
            />
          </div>
          <Button 
            size="sm" 
            className="gradient-button text-white border-0 w-full"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/listing/${listing.id}`);
            }}
          >
            {t('marketplace.viewDetails', 'View')}
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};

export default MarketplacePage;
