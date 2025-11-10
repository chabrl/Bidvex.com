import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Search, Package, Clock, MapPin, Layers, Grid as GridIcon, List as ListIcon, Tag } from 'lucide-react';
import Countdown from 'react-countdown';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Autoplay } from 'swiper/modules';
import WatchlistButton from '../components/WatchlistButton';
import { getCurrencyIcon } from '../utils/currency';
import 'swiper/css';
import 'swiper/css/autoplay';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Image Carousel Component
const ImageCarousel = ({ lots, totalLots }) => {
  const { t } = useTranslation();
  
  // Collect all images from all lots
  const allImages = lots.reduce((images, lot) => {
    if (lot.images && Array.isArray(lot.images)) {
      return [...images, ...lot.images];
    }
    return images;
  }, []);

  // If no images, show placeholder
  if (allImages.length === 0) {
    return (
      <div className="w-full h-full bg-gradient-to-br from-primary/10 to-accent/10 flex items-center justify-center relative">
        <Layers className="h-16 w-16 text-primary opacity-50" />
        <Badge className="absolute top-2 right-2 gradient-bg text-white border-0 z-10">
          <Package className="mr-1 h-3 w-3" />
          {totalLots} {t('lotsMarketplace.items', 'Items')}
        </Badge>
      </div>
    );
  }

  // Only enable loop mode if there are 3 or more images
  const shouldLoop = allImages.length >= 3;
  
  return (
    <div className="w-full h-full relative">
      <Swiper
        modules={[Autoplay]}
        autoplay={{
          delay: 3000,
          disableOnInteraction: false,
          pauseOnMouseEnter: true,
        }}
        loop={shouldLoop}
        speed={800}
        className="w-full h-full"
      >
        {allImages.map((image, index) => (
          <SwiperSlide key={index}>
            <div className="w-full h-full">
              <img
                src={image}
                alt={`Lot item ${index + 1}`}
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.parentElement.innerHTML = '<div class="w-full h-full bg-gradient-to-br from-primary/10 to-accent/10 flex items-center justify-center"><div class="text-primary opacity-50">Image unavailable</div></div>';
                }}
              />
            </div>
          </SwiperSlide>
        ))}
      </Swiper>
      <Badge className="absolute top-2 right-2 gradient-bg text-white border-0 z-10">
        <Package className="mr-1 h-3 w-3" />
        {totalLots} {t('lotsMarketplace.items', 'Items')}
      </Badge>
    </div>
  );
};

const LotsMarketplacePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [listings, setListings] = useState([]);
  const [upcomingListings, setUpcomingListings] = useState([]);
  const [categories, setCategories] = useState([]);
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    sort: '-created_at',
  });
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('lotsViewMode') || 'grid');

  useEffect(() => {
    fetchCategories();
    fetchLots();
    fetchUpcomingLots();
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

  const fetchUpcomingLots = async () => {
    try {
      const response = await axios.get(`${API}/multi-item-listings?status=upcoming`);
      setUpcomingListings(response.data);
    } catch (error) {
      console.error('Failed to fetch upcoming lots:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value });
  };

  const handleViewModeChange = (mode) => {
    setViewMode(mode);
    localStorage.setItem('lotsViewMode', mode);
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

            <div className="flex gap-2">
              <Button
                variant={viewMode === 'grid' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleViewModeChange('grid')}
                className={viewMode === 'grid' ? 'gradient-button text-white' : ''}
              >
                <GridIcon className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === 'list' ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleViewModeChange('list')}
                className={viewMode === 'list' ? 'gradient-button text-white' : ''}
              >
                <ListIcon className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Coming Soon Section */}
        {upcomingListings.length > 0 && (
          <div className="mb-12">
            <div className="flex items-center gap-3 mb-6">
              <Clock className="h-6 w-6 text-amber-500" />
              <h2 className="text-2xl font-bold">
                {t('lotsMarketplace.comingSoon', 'Coming Soon')}
              </h2>
            </div>
            <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : 'space-y-4'}>
              {upcomingListings.map((listing) => {
                const auctionStartDate = new Date(listing.auction_start_date);
                
                if (viewMode === 'list') {
                  return (
                    <Card
                      key={listing.id}
                      className="overflow-hidden hover:shadow-amber-200 hover:border-amber-300 transition-all duration-200 cursor-pointer glassmorphism relative border-amber-200"
                      onClick={() => navigate(`/lots/${listing.id}`)}
                      data-testid={`upcoming-lot-card-${listing.id}`}
                    >
                      <div className="flex flex-col md:flex-row">
                        <div className="w-full md:w-1/3 aspect-video md:aspect-square overflow-hidden relative">
                          <div className="absolute inset-0 bg-black/10 z-[5]"></div>
                          <ImageCarousel lots={listing.lots} totalLots={listing.total_lots} />
                          <div className="absolute top-3 right-3 z-10" onClick={(e) => e.stopPropagation()}>
                            <div className="bg-white/90 backdrop-blur-sm rounded-full p-2 shadow-md hover:bg-white transition-colors">
                              <WatchlistButton listingId={listing.id} size="default" />
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex-1 p-6">
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex-1 min-w-0">
                              <h3 className="text-xl font-bold mb-2 line-clamp-1" title={listing.title}>
                                {listing.title}
                              </h3>
                              <p className="text-muted-foreground text-sm line-clamp-2 mb-3 hidden lg:block">
                                {listing.description}
                              </p>
                            </div>
                            <Badge className="ml-3 flex-shrink-0 bg-amber-500 hover:bg-amber-600 text-white">
                              <Clock className="h-3 w-3 mr-1" />
                              {t('lotsMarketplace.comingSoon', 'Coming Soon')}
                            </Badge>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                            <div className="flex items-center gap-2">
                              <Tag className="h-4 w-4 text-primary flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="text-xs text-muted-foreground">Category</p>
                                <p className="text-sm font-medium text-primary truncate">
                                  {listing.category || 'General'}
                                </p>
                              </div>
                            </div>
                            
                            <div className="flex items-center gap-2">
                              <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="text-xs text-muted-foreground">Location</p>
                                <p className="text-sm font-medium truncate">
                                  {listing.city}, {listing.region}
                                </p>
                              </div>
                            </div>
                            
                            <div className="flex items-center gap-2">
                              <Package className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                              <div>
                                <p className="text-xs text-muted-foreground">Items</p>
                                <p className="text-sm font-medium">
                                  {listing.total_lots} {listing.total_lots === 1 ? 'Lot' : 'Lots'}
                                </p>
                              </div>
                            </div>
                            
                            <div className="flex items-center gap-2">
                              <Clock className="h-4 w-4 text-amber-500 flex-shrink-0" />
                              <div>
                                <p className="text-xs text-muted-foreground">Starts In</p>
                                <p className="text-sm font-semibold text-amber-600">
                                  <Countdown 
                                    date={auctionStartDate}
                                    renderer={({ days, hours, minutes, completed }) => (
                                      <span>
                                        {completed ? 'Live Now!' : `${days}d ${hours}h ${minutes}m`}
                                      </span>
                                    )}
                                  />
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                }

                // Grid View for Upcoming
                return (
                  <Card
                    key={listing.id}
                    className="overflow-hidden hover:shadow-amber-200 hover:border-amber-300 transition-all duration-200 cursor-pointer glassmorphism flex flex-col h-full relative border-amber-200"
                    onClick={() => navigate(`/lots/${listing.id}`)}
                    data-testid={`upcoming-lot-card-${listing.id}`}
                  >
                    <div className="absolute top-3 right-3 z-10" onClick={(e) => e.stopPropagation()}>
                      <div className="bg-white/90 backdrop-blur-sm rounded-full p-2 shadow-md hover:bg-white transition-colors">
                        <WatchlistButton listingId={listing.id} size="default" />
                      </div>
                    </div>

                    <div className="aspect-video overflow-hidden relative">
                      <div className="absolute inset-0 bg-black/10 z-[5]"></div>
                      <ImageCarousel lots={listing.lots} totalLots={listing.total_lots} />
                    </div>
                    
                    <CardHeader className="pb-3">
                      <CardTitle className="line-clamp-2 min-h-[3.5rem] leading-tight" title={listing.title}>
                        {listing.title}
                      </CardTitle>
                    </CardHeader>
                    
                    <CardContent className="space-y-3 flex-grow">
                      <div className="flex items-center gap-2">
                        <Tag className="h-4 w-4 text-primary flex-shrink-0" />
                        <span className="text-sm font-medium text-primary truncate">
                          {listing.category || 'General'}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        <span className="text-sm text-muted-foreground truncate">
                          {listing.city}, {listing.region}
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <Package className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        <span className="text-sm text-muted-foreground">
                          {listing.total_lots} {listing.total_lots === 1 ? 'Lot' : 'Lots'}
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-2 pt-2 border-t">
                        <Clock className="h-4 w-4 text-amber-500 flex-shrink-0" />
                        <div className="flex flex-col">
                          <span className="text-xs text-muted-foreground">Starts in</span>
                          <Countdown
                            date={auctionStartDate}
                            renderer={({ days, hours, minutes, completed }) => (
                              <span className="font-semibold text-sm text-amber-600">
                                {completed ? 'Live Now!' : `${days}d ${hours}h ${minutes}m`}
                              </span>
                            )}
                          />
                        </div>
                      </div>
                    </CardContent>
                    
                    <CardFooter className="mt-auto">
                      <Button 
                        className="w-full bg-amber-500 hover:bg-amber-600 text-white border-0 opacity-70 cursor-not-allowed"
                        disabled
                      >
                        <Clock className="h-4 w-4 mr-2" />
                        {t('lotsMarketplace.biddingOpensSoon', 'Bidding Opens Soon')}
                      </Button>
                    </CardFooter>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

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
          <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : 'space-y-4'}>
            {listings.map((listing) => {
              const auctionEndDate = new Date(listing.auction_end_date);
              const isEnded = new Date() > auctionEndDate;
              const totalStarting = getTotalStartingPrice(listing.lots);
              const totalCurrent = getTotalCurrentPrice(listing.lots);

              if (viewMode === 'list') {
                return (
                  <Card
                    key={listing.id}
                    className="overflow-hidden hover:shadow-lg transition-all duration-200 cursor-pointer glassmorphism relative"
                    onClick={() => navigate(`/lots/${listing.id}`)}
                    data-testid={`lot-card-${listing.id}`}
                  >
                    <div className="flex flex-col md:flex-row">
                      <div className="w-full md:w-1/3 aspect-video md:aspect-square overflow-hidden relative">
                        <ImageCarousel lots={listing.lots} totalLots={listing.total_lots} />
                        {/* Favorite Button on Image */}
                        <div className="absolute top-3 right-3 z-10" onClick={(e) => e.stopPropagation()}>
                          <div className="bg-white/90 backdrop-blur-sm rounded-full p-2 shadow-md hover:bg-white transition-colors">
                            <WatchlistButton listingId={listing.id} size="default" />
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex-1 p-6">
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex-1 min-w-0">
                            <h3 
                              className="text-xl font-bold mb-2 line-clamp-1" 
                              title={listing.title}
                            >
                              {listing.title}
                            </h3>
                            <p className="text-muted-foreground text-sm line-clamp-2 mb-3 hidden lg:block">
                              {listing.description}
                            </p>
                          </div>
                          <Badge 
                            variant={isEnded ? 'secondary' : 'default'} 
                            className="ml-3 flex-shrink-0"
                          >
                            {isEnded ? t('lotsMarketplace.ended', 'Ended') : t('lotsMarketplace.active', 'Active')}
                          </Badge>
                        </div>

                        {/* Metadata Grid - No Pricing */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                          {/* Category */}
                          <div className="flex items-center gap-2">
                            <Tag className="h-4 w-4 text-primary flex-shrink-0" />
                            <div className="min-w-0">
                              <p className="text-xs text-muted-foreground">Category</p>
                              <p className="text-sm font-medium text-primary truncate">
                                {listing.category || 'General'}
                              </p>
                            </div>
                          </div>
                          
                          {/* Location */}
                          <div className="flex items-center gap-2">
                            <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                            <div className="min-w-0">
                              <p className="text-xs text-muted-foreground">Location</p>
                              <p className="text-sm font-medium truncate">
                                {listing.city}, {listing.region}
                              </p>
                            </div>
                          </div>
                          
                          {/* Lot Count */}
                          <div className="flex items-center gap-2">
                            <Package className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                            <div>
                              <p className="text-xs text-muted-foreground">Items</p>
                              <p className="text-sm font-medium">
                                {listing.total_lots} {listing.total_lots === 1 ? 'Lot' : 'Lots'}
                              </p>
                            </div>
                          </div>
                          
                          {/* Time Remaining */}
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-primary flex-shrink-0" />
                            <div>
                              <p className="text-xs text-muted-foreground">Ends In</p>
                              {!isEnded ? (
                                <p className="text-sm font-semibold text-primary">
                                  <Countdown 
                                    date={auctionEndDate}
                                    renderer={({ days, hours, minutes, completed }) => (
                                      <span>
                                        {completed ? 'Ended' : `${days}d ${hours}h ${minutes}m`}
                                      </span>
                                    )}
                                  />
                                </p>
                              ) : (
                                <p className="text-sm text-destructive font-semibold">Ended</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </Card>
                );
              }

              return (
                <Card
                  key={listing.id}
                  className="overflow-hidden hover:shadow-lg transition-all duration-200 cursor-pointer glassmorphism flex flex-col h-full relative"
                  onClick={() => navigate(`/lots/${listing.id}`)}
                  data-testid={`lot-card-${listing.id}`}
                >
                  {/* Favorite Button - Absolute positioned on image */}
                  <div className="absolute top-3 right-3 z-10" onClick={(e) => e.stopPropagation()}>
                    <div className="bg-white/90 backdrop-blur-sm rounded-full p-2 shadow-md hover:bg-white transition-colors">
                      <WatchlistButton listingId={listing.id} size="default" />
                    </div>
                  </div>

                  <div className="aspect-video overflow-hidden">
                    <ImageCarousel lots={listing.lots} totalLots={listing.total_lots} />
                  </div>
                  
                  <CardHeader className="pb-3">
                    <CardTitle 
                      className="line-clamp-2 min-h-[3.5rem] leading-tight"
                      title={listing.title}
                    >
                      {listing.title}
                    </CardTitle>
                  </CardHeader>
                  
                  <CardContent className="space-y-3 flex-grow">
                    {/* Category */}
                    <div className="flex items-center gap-2">
                      <Tag className="h-4 w-4 text-primary flex-shrink-0" />
                      <span className="text-sm font-medium text-primary truncate">
                        {listing.category || 'General'}
                      </span>
                    </div>

                    {/* Location */}
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm text-muted-foreground truncate">
                        {listing.city}, {listing.region}
                      </span>
                    </div>
                    
                    {/* Lot Count */}
                    <div className="flex items-center gap-2">
                      <Package className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm text-muted-foreground">
                        {listing.total_lots} {listing.total_lots === 1 ? 'Lot' : 'Lots'}
                      </span>
                    </div>
                    
                    {/* Time Remaining */}
                    {!isEnded ? (
                      <div className="flex items-center gap-2 pt-2 border-t">
                        <Clock className="h-4 w-4 text-primary flex-shrink-0" />
                        <div className="flex flex-col">
                          <span className="text-xs text-muted-foreground">Ends in</span>
                          <Countdown
                            date={auctionEndDate}
                            renderer={({ days, hours, minutes, completed }) => (
                              <span className={`font-semibold text-sm ${completed ? 'text-red-500' : 'text-primary'}`}>
                                {completed ? t('marketplace.ended', 'Ended') : `${days}d ${hours}h ${minutes}m`}
                              </span>
                            )}
                          />
                        </div>
                      </div>
                    ) : (
                      <Badge variant="destructive" className="w-fit">
                        {t('marketplace.ended', 'Auction Ended')}
                      </Badge>
                    )}
                  </CardContent>
                  
                  <CardFooter className="mt-auto">
                    <Button className="w-full gradient-button text-white border-0 hover:scale-105 transition-transform">
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