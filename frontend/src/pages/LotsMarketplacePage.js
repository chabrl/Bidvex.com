import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetClose, SheetFooter 
} from '../components/ui/sheet';
import { 
  Search, Package, Clock, MapPin, Layers, Grid as GridIcon, 
  List as ListIcon, Tag, Star, TrendingUp, Sparkles, Filter,
  ChevronDown, X, BarChart3, DollarSign, Users, Zap, Eye,
  Building2, Globe, Map, SlidersHorizontal
} from 'lucide-react';
import Countdown from 'react-countdown';
import WishlistHeartButton from '../components/WishlistHeartButton';
import { getCurrencyIcon } from '../utils/currency';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Regional data structure
const REGIONS_DATA = {
  Canada: {
    provinces: {
      'Quebec': ['Montreal', 'Quebec City', 'Laval', 'Gatineau', 'Longueuil', 'Sherbrooke', 'Trois-Rivières'],
      'Ontario': ['Toronto', 'Ottawa', 'Mississauga', 'Hamilton', 'London', 'Markham', 'Vaughan'],
      'British Columbia': ['Vancouver', 'Victoria', 'Surrey', 'Burnaby', 'Richmond', 'Kelowna'],
      'Alberta': ['Calgary', 'Edmonton', 'Red Deer', 'Lethbridge', 'Medicine Hat'],
    }
  },
  'United States': {
    provinces: {
      'New York': ['New York City', 'Buffalo', 'Rochester', 'Albany', 'Syracuse'],
      'California': ['Los Angeles', 'San Francisco', 'San Diego', 'Sacramento', 'San Jose'],
      'Texas': ['Houston', 'Dallas', 'Austin', 'San Antonio', 'Fort Worth'],
      'Florida': ['Miami', 'Orlando', 'Tampa', 'Jacksonville', 'Fort Lauderdale'],
    }
  }
};

const LotsMarketplacePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  
  // State
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [viewMode, setViewMode] = useState('grid');
  const [showFilters, setShowFilters] = useState(false);
  
  // Regional filter state
  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedProvince, setSelectedProvince] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  
  // Filters
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    currency: '',
    sort: '-featured',
    min_price: '',
    max_price: '',
    private_sales_only: false,
  });

  // Market stats
  const [marketStats, setMarketStats] = useState({
    totalLots: 0,
    avgStartingPrice: 0,
    privateSalesCount: 0,
  });

  // Fetch categories
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await axios.get(`${API}/categories`);
        setCategories(response.data || []);
      } catch (error) {
        console.error('Failed to fetch categories:', error);
      }
    };
    fetchCategories();
  }, []);

  // Fetch listings with all filters
  useEffect(() => {
    const fetchListings = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        
        if (filters.search) params.append('search', filters.search);
        if (filters.category) params.append('category', filters.category);
        if (filters.currency) params.append('currency', filters.currency);
        if (selectedProvince) params.append('region', selectedProvince);
        if (selectedCity) params.append('city', selectedCity);
        if (filters.min_price) params.append('min_price', filters.min_price);
        if (filters.max_price) params.append('max_price', filters.max_price);
        if (filters.sort) params.append('sort', filters.sort);
        params.append('limit', '50');

        const response = await axios.get(`${API}/multi-item-listings?${params.toString()}`);
        let data = response.data || [];
        
        // Sort: Featured items first, then by selected sort
        data = data.sort((a, b) => {
          // Featured items always first
          if (a.is_featured && !b.is_featured) return -1;
          if (!a.is_featured && b.is_featured) return 1;
          
          // Then by private sales if filter is on
          if (filters.private_sales_only) {
            const aPrivate = !a.seller_is_tax_registered;
            const bPrivate = !b.seller_is_tax_registered;
            if (aPrivate && !bPrivate) return -1;
            if (!aPrivate && bPrivate) return 1;
          }
          
          return 0;
        });

        // Filter for private sales only if enabled
        if (filters.private_sales_only) {
          data = data.filter(listing => !listing.seller_is_tax_registered);
        }

        setListings(data);

        // Calculate market stats
        const totalLots = data.reduce((sum, l) => sum + (l.total_lots || 0), 0);
        const avgPrice = data.length > 0 
          ? data.reduce((sum, l) => sum + (l.lots?.[0]?.starting_price || 0), 0) / data.length 
          : 0;
        const privateSales = data.filter(l => !l.seller_is_tax_registered).length;
        
        setMarketStats({
          totalLots,
          avgStartingPrice: avgPrice,
          privateSalesCount: privateSales,
        });

      } catch (error) {
        console.error('Failed to fetch listings:', error);
        setListings([]);
      } finally {
        setLoading(false);
      }
    };

    fetchListings();
  }, [filters, selectedProvince, selectedCity]);

  // Handle filter changes
  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  // Handle regional selection
  const handleCountryChange = (country) => {
    setSelectedCountry(country);
    setSelectedProvince('');
    setSelectedCity('');
  };

  const handleProvinceChange = (province) => {
    setSelectedProvince(province);
    setSelectedCity('');
  };

  // Get available provinces based on selected country
  const availableProvinces = useMemo(() => {
    if (!selectedCountry || !REGIONS_DATA[selectedCountry]) return [];
    return Object.keys(REGIONS_DATA[selectedCountry].provinces);
  }, [selectedCountry]);

  // Get available cities based on selected province
  const availableCities = useMemo(() => {
    if (!selectedCountry || !selectedProvince) return [];
    return REGIONS_DATA[selectedCountry]?.provinces[selectedProvince] || [];
  }, [selectedCountry, selectedProvince]);

  // Clear all filters
  const clearAllFilters = () => {
    setFilters({
      search: '',
      category: '',
      currency: '',
      sort: '-featured',
      min_price: '',
      max_price: '',
      private_sales_only: false,
    });
    setSelectedCountry('');
    setSelectedProvince('');
    setSelectedCity('');
  };

  // Get region display text
  const getRegionDisplayText = () => {
    if (selectedCity) return selectedCity;
    if (selectedProvince) return selectedProvince;
    if (selectedCountry) return selectedCountry;
    return 'All Regions';
  };

  // Render listing card
  const renderListingCard = (listing) => {
    const isPrivateSale = !listing.seller_is_tax_registered;
    const firstLot = listing.lots?.[0];
    const imageUrl = firstLot?.images?.[0] || listing.lots?.find(l => l.images?.length > 0)?.images?.[0];

    return (
      <Card 
        key={listing.id} 
        className="group overflow-hidden hover:shadow-xl transition-all duration-300 border-slate-200 dark:border-slate-700"
        data-testid="listing-card"
      >
        {/* Image Section */}
        <Link to={`/lots/${listing.id}`} className="block relative">
          <div className="aspect-[4/3] overflow-hidden bg-slate-100 dark:bg-slate-800">
            {imageUrl ? (
              <img 
                src={imageUrl} 
                alt={listing.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Package className="h-16 w-16" style={{ color: '#94a3b8' }} />
              </div>
            )}
          </div>

          {/* Badges Overlay */}
          <div className="absolute top-3 left-3 flex flex-wrap gap-2">
            {listing.is_featured && (
              <Badge className="bg-orange-500 text-white border-0 shadow-lg">
                <Star className="h-3 w-3 mr-1 fill-white" />
                FEATURED
              </Badge>
            )}
            {isPrivateSale ? (
              <Badge className="bg-green-500 text-white border-0 shadow-lg">
                Private Sale
              </Badge>
            ) : (
              <Badge className="bg-blue-600 text-white border-0 shadow-lg">
                <Building2 className="h-3 w-3 mr-1" />
                Business
              </Badge>
            )}
          </div>

          {/* Lot Count Badge */}
          <Badge 
            className="absolute top-3 right-3 bg-slate-900/80 text-white border-0"
            style={{ color: '#ffffff' }}
          >
            <Package className="h-3 w-3 mr-1" />
            {listing.total_lots} Lots
          </Badge>

          {/* Timer Badge */}
          <div className="absolute bottom-3 left-3 bg-slate-900/80 backdrop-blur text-white px-3 py-1.5 rounded-full text-sm flex items-center gap-2">
            <Clock className="h-3.5 w-3.5" style={{ color: '#fbbf24' }} />
            <Countdown 
              date={new Date(listing.auction_end_date)} 
              renderer={({ days, hours, minutes }) => (
                <span style={{ color: '#ffffff' }}>{days}d {hours}h {minutes}m</span>
              )}
            />
          </div>
        </Link>

        {/* Content Section */}
        <CardContent className="p-4" data-testid="listing-content">
          <Link to={`/lots/${listing.id}`}>
            <h3 
              className="font-semibold text-lg mb-2 line-clamp-2 hover:text-cyan-600 transition-colors"
              style={{ color: '#1a1a1a', fontWeight: 600 }}
            >
              {listing.title}
            </h3>
          </Link>

          {/* Location */}
          <div className="flex items-center gap-1 text-sm mb-3" style={{ color: '#6b7280' }}>
            <MapPin className="h-4 w-4" style={{ color: '#6b7280' }} />
            <span style={{ color: '#6b7280' }}>{listing.city}, {listing.region}</span>
          </div>

          {/* Tax Savings Banner */}
          {isPrivateSale && (
            <div 
              className="rounded-lg px-3 py-2 text-xs mb-3"
              style={{ backgroundColor: '#dcfce7', border: '1px solid #86efac' }}
            >
              <span style={{ color: '#15803d', fontWeight: 500 }}>
                🎉 Save ~15% - No tax on item price!
              </span>
            </div>
          )}

          {/* Pricing */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider" style={{ color: '#9ca3af' }}>Starting From</p>
              <p 
                className="text-xl font-bold"
                style={{ 
                  background: 'linear-gradient(to right, #2563eb, #06b6d4)',
                  WebkitBackgroundClip: 'text',
                  backgroundClip: 'text',
                  color: 'transparent'
                }}
              >
                ${(firstLot?.starting_price || 0).toFixed(2)}
              </p>
            </div>
            <WishlistHeartButton 
              auctionId={listing.id}
              wishlistCount={listing.wishlist_count || 0}
            />
          </div>
        </CardContent>

        {/* Footer Actions */}
        <CardFooter className="p-4 pt-0 flex gap-2">
          <Link to={`/lots/${listing.id}`} className="flex-1">
            <Button 
              className="w-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white hover:from-blue-700 hover:to-cyan-600"
            >
              <Eye className="h-4 w-4 mr-2" />
              View Auction
            </Button>
          </Link>
        </CardFooter>
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="lots-marketplace-page">
      {/* Hero Header */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-900 via-slate-900 to-cyan-900 opacity-95" />
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full blur-[150px] bg-cyan-500" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 rounded-full blur-[150px] bg-blue-500" />
        </div>
        
        <div className="relative container mx-auto max-w-7xl py-8 px-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-3 bg-cyan-500/20 backdrop-blur rounded-xl border border-cyan-400/30">
              <Layers className="h-8 w-8" style={{ color: '#67e8f9' }} />
            </div>
            <h1 className="text-3xl md:text-4xl font-bold" style={{ color: '#ffffff', textShadow: '0 2px 8px rgba(0,0,0,0.3)' }}>
              {t('lotsMarketplace.title', 'Lots Auction')}
            </h1>
          </div>
          <p style={{ color: '#bfdbfe' }} className="max-w-2xl text-lg mb-6">
            {t('lotsMarketplace.subtitle', 'Browse and bid on grouped item lots from sellers')}
          </p>

          {/* Main Search Bar */}
          <div className="relative max-w-2xl">
            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5" style={{ color: '#6b7280' }} />
            <Input
              placeholder={t('lotsMarketplace.search', 'Search auctions, categories, locations...')}
              value={filters.search}
              onChange={(e) => handleFilterChange('search', e.target.value)}
              className="pl-12 pr-4 py-6 text-lg rounded-xl border-2 border-white/20 bg-white/10 backdrop-blur text-white placeholder:text-white/60 focus:bg-white focus:text-slate-900 focus:placeholder:text-slate-400 transition-all"
              style={{ fontSize: '16px' }}
              data-testid="search-input"
            />
          </div>
        </div>
      </div>

      {/* Filters Section */}
      <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 sticky top-16 z-40">
        <div className="container mx-auto max-w-7xl px-4 py-4">
          <div className="flex flex-wrap items-center gap-3">
            
            {/* Country Filter */}
            <div className="relative">
              <select
                value={selectedCountry}
                onChange={(e) => handleCountryChange(e.target.value)}
                className="appearance-none pl-10 pr-8 py-2.5 border-2 rounded-lg bg-white dark:bg-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 cursor-pointer"
                style={{ color: '#1a1a1a', borderColor: '#d1d5db', minWidth: '140px' }}
              >
                <option value="">🌍 Country</option>
                {Object.keys(REGIONS_DATA).map(country => (
                  <option key={country} value={country}>{country}</option>
                ))}
              </select>
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
            </div>

            {/* Province Filter */}
            <div className="relative">
              <select
                value={selectedProvince}
                onChange={(e) => handleProvinceChange(e.target.value)}
                disabled={!selectedCountry}
                className="appearance-none pl-10 pr-8 py-2.5 border-2 rounded-lg bg-white dark:bg-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ color: '#1a1a1a', borderColor: '#d1d5db', minWidth: '160px' }}
              >
                <option value="">📍 Province/State</option>
                {availableProvinces.map(province => (
                  <option key={province} value={province}>{province}</option>
                ))}
              </select>
              <Map className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
            </div>

            {/* City Filter */}
            <div className="relative">
              <select
                value={selectedCity}
                onChange={(e) => setSelectedCity(e.target.value)}
                disabled={!selectedProvince}
                className="appearance-none pl-10 pr-8 py-2.5 border-2 rounded-lg bg-white dark:bg-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ color: '#1a1a1a', borderColor: '#d1d5db', minWidth: '150px' }}
              >
                <option value="">🏙️ City</option>
                {availableCities.map(city => (
                  <option key={city} value={city}>{city}</option>
                ))}
              </select>
              <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
            </div>

            {/* Category Filter */}
            <div className="relative">
              <select
                value={filters.category}
                onChange={(e) => handleFilterChange('category', e.target.value)}
                className="appearance-none pl-10 pr-8 py-2.5 border-2 rounded-lg bg-white dark:bg-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 cursor-pointer"
                style={{ color: '#1a1a1a', borderColor: '#d1d5db', minWidth: '140px' }}
              >
                <option value="">📦 Category</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.name_en}>{cat.name_en}</option>
                ))}
              </select>
              <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
            </div>

            {/* Sort Filter with Smart Sort */}
            <div className="relative">
              <select
                value={filters.sort}
                onChange={(e) => handleFilterChange('sort', e.target.value)}
                className="appearance-none pl-10 pr-8 py-2.5 border-2 rounded-lg bg-white dark:bg-slate-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 cursor-pointer"
                style={{ color: '#1a1a1a', borderColor: '#d1d5db', minWidth: '180px' }}
              >
                <option value="-featured">⭐ Featured First</option>
                <option value="auction_end_date">⏰ Ending Soon</option>
                <option value="-created_at">🆕 Newest First</option>
                <option value="starting_price">💰 Price: Low to High</option>
                <option value="-starting_price">💎 Price: High to Low</option>
              </select>
              <TrendingUp className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: '#6b7280' }} />
            </div>

            {/* Private Sales Only Toggle */}
            <Button
              variant={filters.private_sales_only ? 'default' : 'outline'}
              onClick={() => handleFilterChange('private_sales_only', !filters.private_sales_only)}
              className={filters.private_sales_only 
                ? 'bg-green-600 hover:bg-green-700 text-white border-green-600' 
                : 'border-2 hover:bg-green-50 hover:border-green-300'
              }
              style={!filters.private_sales_only ? { color: '#15803d', borderColor: '#86efac' } : {}}
            >
              {filters.private_sales_only ? '✓ ' : ''}Tax-Free First
              <Badge className="ml-2 bg-white/20 text-inherit border-0">Save 15%</Badge>
            </Button>

            {/* Clear Filters */}
            {(filters.search || filters.category || selectedCountry || filters.private_sales_only) && (
              <Button
                variant="ghost"
                onClick={clearAllFilters}
                className="text-red-500 hover:text-red-700 hover:bg-red-50"
              >
                <X className="h-4 w-4 mr-1" />
                Clear All
              </Button>
            )}

            {/* View Mode Toggle */}
            <div className="ml-auto flex gap-1 border-2 rounded-lg p-1" style={{ borderColor: '#e5e7eb' }}>
              <Button
                variant={viewMode === 'grid' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('grid')}
                className={viewMode === 'grid' ? 'bg-blue-600 text-white' : ''}
              >
                <GridIcon className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === 'list' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('list')}
                className={viewMode === 'list' ? 'bg-blue-600 text-white' : ''}
              >
                <ListIcon className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Market Insight Bar */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-slate-800 dark:to-slate-800 border-b border-slate-200 dark:border-slate-700">
        <div className="container mx-auto max-w-7xl px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" style={{ color: '#2563eb' }} />
              <span style={{ color: '#1e40af', fontWeight: 600 }}>Market Insight:</span>
              <span style={{ color: '#374151' }}>
                Found <strong style={{ color: '#2563eb' }}>{listings.length}</strong> auctions 
                (<strong style={{ color: '#2563eb' }}>{marketStats.totalLots}</strong> lots) in{' '}
                <strong style={{ color: '#2563eb' }}>{getRegionDisplayText()}</strong>
              </span>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4" style={{ color: '#16a34a' }} />
                <span style={{ color: '#374151' }}>
                  Avg. Starting: <strong style={{ color: '#16a34a' }}>${marketStats.avgStartingPrice.toFixed(2)}</strong>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4" style={{ color: '#15803d' }} />
                <span style={{ color: '#374151' }}>
                  <strong style={{ color: '#15803d' }}>{marketStats.privateSalesCount}</strong> Tax-Free Sales
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content - Search Results Grid */}
      <div className="container mx-auto max-w-7xl px-4 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
          </div>
        ) : listings.length === 0 ? (
          <Card className="p-12 text-center">
            <Package className="h-16 w-16 mx-auto mb-4" style={{ color: '#9ca3af' }} />
            <h3 className="text-xl font-semibold mb-2" style={{ color: '#1a1a1a' }}>
              {t('lotsMarketplace.noLots', 'No auctions found')}
            </h3>
            <p style={{ color: '#6b7280' }} className="mb-4">
              {t('lotsMarketplace.noLotsDesc', 'Try adjusting your filters or search terms')}
            </p>
            <Button onClick={clearAllFilters} className="bg-blue-600 text-white hover:bg-blue-700">
              Clear All Filters
            </Button>
          </Card>
        ) : (
          <div className={viewMode === 'grid' 
            ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6'
            : 'flex flex-col gap-4'
          }>
            {listings.map(listing => renderListingCard(listing))}
          </div>
        )}
      </div>
    </div>
  );
};

export default LotsMarketplacePage;
