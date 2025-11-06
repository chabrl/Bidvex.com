import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Search, Package, Clock, MapPin, Layers, Grid as GridIcon, List as ListIcon } from 'lucide-react';
import Countdown from 'react-countdown';
import { Swiper, SwiperSlide } from 'swiper/react';
import { Autoplay } from 'swiper/modules';
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

  return (
    <div className="w-full h-full relative">
      <Swiper
        modules={[Autoplay]}
        autoplay={{
          delay: 3000,
          disableOnInteraction: false,
          pauseOnMouseEnter: true,
        }}
        loop={true}
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
                    className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer glassmorphism"
                    onClick={() => navigate(`/lots/${listing.id}`)}
                    data-testid={`lot-card-${listing.id}`}
                  >
                    <div className="flex flex-col md:flex-row">
                      <div className="w-full md:w-1/3 aspect-video md:aspect-square bg-gradient-to-br from-primary/10 to-accent/10 flex items-center justify-center relative">
                        <Layers className="h-16 w-16 text-primary opacity-50" />
                        <Badge className="absolute top-2 right-2 gradient-bg text-white border-0">
                          <Package className="mr-1 h-3 w-3" />
                          {listing.total_lots} {t('lotsMarketplace.items', 'Items')}
                        </Badge>
                      </div>
                      
                      <div className="flex-1 p-6">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1">
                            <h3 className="text-xl font-bold mb-2">{listing.title}</h3>
                            <p className="text-muted-foreground text-sm line-clamp-2 mb-3">{listing.description}</p>
                          </div>
                          <Badge variant={isEnded ? 'secondary' : 'default'} className="ml-2">
                            {isEnded ? t('lotsMarketplace.ended', 'Ended') : t('lotsMarketplace.active', 'Active')}
                          </Badge>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div>
                            <p className="text-xs text-muted-foreground">{t('lotsMarketplace.location', 'Location')}</p>
                            <p className="text-sm font-medium">{listing.city}, {listing.region}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">{t('lotsMarketplace.totalBid', 'Current Bid')}</p>
                            <p className="text-lg font-bold gradient-text">${totalCurrent.toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">{t('lotsMarketplace.totalValue', 'Starting Value')}</p>
                            <p className="text-sm font-medium">${totalStarting.toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">{t('lotsMarketplace.endsIn', 'Ends In')}</p>
                            {!isEnded ? (
                              <p className="text-sm font-medium">
                                <Countdown date={auctionEndDate} />
                              </p>
                            ) : (
                              <p className="text-sm text-muted-foreground">{t('lotsMarketplace.auctionEnded', 'Auction Ended')}</p>
                            )}
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