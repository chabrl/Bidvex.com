/**
 * Vehicle Auctions Marketplace Page
 * Main browse page for vehicle auctions - Automotive-inspired design
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Car, Search, Filter, Grid, List, Clock, MapPin, Gauge,
  Fuel, Settings2, Calendar, DollarSign, ChevronRight,
  Award, Shield, Zap, TrendingUp, Eye, Heart, RefreshCw
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Vehicle body type icons
const bodyTypeIcons = {
  sedan: '🚗',
  suv: '🚙',
  truck: '🛻',
  coupe: '🏎️',
  convertible: '🏎️',
  van: '🚐',
  motorcycle: '🏍️',
  other: '🚘',
};

// Format price
const formatPrice = (price) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price);
};

// Format mileage
const formatMileage = (mileage) => {
  return new Intl.NumberFormat('en-CA').format(mileage) + ' km';
};

// Time remaining formatter
const formatTimeRemaining = (endTime) => {
  if (!endTime) return 'N/A';
  const end = new Date(endTime);
  const now = new Date();
  const diff = end - now;
  
  if (diff <= 0) return 'Ended';
  
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};

// Vehicle Card Component
const VehicleCard = ({ vehicle, onClick }) => {
  const [imageError, setImageError] = useState(false);
  const mainImage = vehicle.media?.find(m => m.category === 'front')?.url || 
                    vehicle.media?.[0]?.url;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
    >
      <Card 
        className="overflow-hidden cursor-pointer group bg-white dark:bg-slate-900 border-0 shadow-lg hover:shadow-2xl transition-all duration-300"
        onClick={onClick}
        data-testid={`vehicle-card-${vehicle.id}`}
      >
        {/* Image Container */}
        <div className="relative aspect-[16/10] bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-900 overflow-hidden">
          {mainImage && !imageError ? (
            <img
              src={mainImage}
              alt={vehicle.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Car className="h-16 w-16 text-slate-300" />
            </div>
          )}
          
          {/* Overlay Badges */}
          <div className="absolute top-3 left-3 flex flex-col gap-2">
            {vehicle.auction_type === 'live' && (
              <Badge className="bg-red-500 text-white animate-pulse">
                <Zap className="h-3 w-3 mr-1" /> LIVE
              </Badge>
            )}
            {vehicle.reserve_met && (
              <Badge className="bg-green-500 text-white">
                <Award className="h-3 w-3 mr-1" /> Reserve Met
              </Badge>
            )}
            {vehicle.title_status === 'clean' && (
              <Badge className="bg-emerald-500 text-white">
                <Shield className="h-3 w-3 mr-1" /> Clean Title
              </Badge>
            )}
          </div>
          
          {/* Time Remaining */}
          <div className="absolute bottom-3 right-3">
            <Badge variant="secondary" className="bg-black/70 text-white backdrop-blur-sm">
              <Clock className="h-3 w-3 mr-1" />
              {formatTimeRemaining(vehicle.end_time)}
            </Badge>
          </div>
          
          {/* Bid Count */}
          <div className="absolute bottom-3 left-3">
            <Badge variant="secondary" className="bg-white/90 text-slate-900 backdrop-blur-sm">
              <TrendingUp className="h-3 w-3 mr-1" />
              {vehicle.bid_count || 0} bids
            </Badge>
          </div>
        </div>
        
        {/* Content */}
        <CardContent className="p-4 space-y-3">
          {/* Year Make Model */}
          <div>
            <h3 className="font-bold text-lg text-slate-900 dark:text-white group-hover:text-blue-600 transition-colors line-clamp-1">
              {vehicle.year} {vehicle.make} {vehicle.model}
            </h3>
            {vehicle.trim && (
              <p className="text-sm text-slate-500">{vehicle.trim}</p>
            )}
          </div>
          
          {/* Specs Grid */}
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <Gauge className="h-4 w-4" />
              <span>{formatMileage(vehicle.mileage)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <Fuel className="h-4 w-4" />
              <span className="capitalize">{vehicle.fuel_type}</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <Settings2 className="h-4 w-4" />
              <span className="capitalize">{vehicle.transmission}</span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
              <MapPin className="h-4 w-4" />
              <span>{vehicle.location_city}, {vehicle.location_province}</span>
            </div>
          </div>
          
          {/* Price Section */}
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-end justify-between">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wide">Current Bid</p>
              <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {vehicle.current_bid > 0 ? formatPrice(vehicle.current_bid) : formatPrice(vehicle.starting_price)}
              </p>
            </div>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700">
              Bid Now <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
};

// Main Page Component
const VehicleAuctionsPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState('grid');
  
  // Filters
  const [filters, setFilters] = useState({
    make: searchParams.get('make') || '',
    year_min: searchParams.get('year_min') || '',
    year_max: searchParams.get('year_max') || '',
    price_min: searchParams.get('price_min') || '',
    price_max: searchParams.get('price_max') || '',
    body_type: searchParams.get('body_type') || '',
    province: searchParams.get('province') || '',
    sort_by: searchParams.get('sort_by') || 'end_time',
    sort_order: searchParams.get('sort_order') || 'asc',
  });
  
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const fetchVehicles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', page.toString());
      params.set('limit', '12');
      
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      
      const response = await axios.get(`${API}/vehicles?${params}`);
      setVehicles(response.data.vehicles || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      console.error('Failed to fetch vehicles:', error);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    fetchVehicles();
  }, [fetchVehicles]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({
      make: '',
      year_min: '',
      year_max: '',
      price_min: '',
      price_max: '',
      body_type: '',
      province: '',
      sort_by: 'end_time',
      sort_order: 'asc',
    });
    setSearchQuery('');
    setPage(1);
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="vehicle-auctions-page">
      {/* Hero Header */}
      <div className="relative bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }} />
        </div>
        
        <div className="relative max-w-7xl mx-auto px-4 py-16">
          <div className="flex items-center gap-3 mb-4">
            <Car className="h-10 w-10 text-blue-400" />
            <Badge className="bg-blue-500/20 text-blue-300 border-blue-400/30">
              Enterprise Vehicle Auctions
            </Badge>
          </div>
          
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            Vehicle Auctions
          </h1>
          <p className="text-xl text-blue-200 max-w-2xl mb-8">
            Professional automotive auctions for dealers, auctioneers, and private buyers.
            Verified sellers. Clean titles. Transparent bidding.
          </p>
          
          {/* Search Bar */}
          <div className="flex flex-col sm:flex-row gap-4 max-w-2xl">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
              <Input
                type="text"
                placeholder="Search by make, model, or VIN..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-12 h-14 bg-white/10 border-white/20 text-white placeholder:text-slate-400 focus:bg-white/20"
                data-testid="vehicle-search-input"
              />
            </div>
            <Button 
              size="lg" 
              className="h-14 px-8 bg-blue-500 hover:bg-blue-600"
              onClick={() => handleFilterChange('make', searchQuery)}
            >
              Search
            </Button>
          </div>
          
          {/* Quick Stats */}
          <div className="flex flex-wrap gap-6 mt-8">
            <div className="flex items-center gap-2">
              <Eye className="h-5 w-5 text-blue-400" />
              <span className="text-slate-300">{total} Active Auctions</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-green-400" />
              <span className="text-slate-300">Verified Sellers</span>
            </div>
            <div className="flex items-center gap-2">
              <Award className="h-5 w-5 text-yellow-400" />
              <span className="text-slate-300">Title Guarantee</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Filters Bar */}
        <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 mb-6">
          <div className="flex flex-wrap items-center gap-4">
            {/* Sort */}
            <Select value={filters.sort_by} onValueChange={(v) => handleFilterChange('sort_by', v)}>
              <SelectTrigger className="w-40" data-testid="sort-select">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="end_time">Ending Soon</SelectItem>
                <SelectItem value="created_at">Newest</SelectItem>
                <SelectItem value="current_bid">Price: Low to High</SelectItem>
                <SelectItem value="year">Year: Newest</SelectItem>
                <SelectItem value="mileage">Mileage: Low to High</SelectItem>
              </SelectContent>
            </Select>
            
            {/* Body Type */}
            <Select value={filters.body_type} onValueChange={(v) => handleFilterChange('body_type', v)}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Body Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="sedan">Sedan</SelectItem>
                <SelectItem value="suv">SUV</SelectItem>
                <SelectItem value="truck">Truck</SelectItem>
                <SelectItem value="coupe">Coupe</SelectItem>
                <SelectItem value="van">Van</SelectItem>
              </SelectContent>
            </Select>
            
            {/* Province */}
            <Select value={filters.province} onValueChange={(v) => handleFilterChange('province', v)}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="Province" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Provinces</SelectItem>
                <SelectItem value="QC">Quebec</SelectItem>
                <SelectItem value="ON">Ontario</SelectItem>
                <SelectItem value="BC">British Columbia</SelectItem>
                <SelectItem value="AB">Alberta</SelectItem>
              </SelectContent>
            </Select>
            
            {/* More Filters Toggle */}
            <Button 
              variant="outline" 
              onClick={() => setShowFilters(!showFilters)}
              className="gap-2"
            >
              <Filter className="h-4 w-4" />
              More Filters
            </Button>
            
            {/* Clear Filters */}
            <Button variant="ghost" onClick={clearFilters} className="gap-2">
              <RefreshCw className="h-4 w-4" />
              Clear
            </Button>
            
            <div className="flex-1" />
            
            {/* View Toggle */}
            <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
              <Button
                variant={viewMode === 'grid' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('grid')}
              >
                <Grid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === 'list' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('list')}
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          </div>
          
          {/* Extended Filters */}
          <AnimatePresence>
            {showFilters && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 mt-4 border-t">
                  <div>
                    <label className="text-sm text-slate-500 mb-1 block">Year From</label>
                    <Input
                      type="number"
                      placeholder="2015"
                      value={filters.year_min}
                      onChange={(e) => handleFilterChange('year_min', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm text-slate-500 mb-1 block">Year To</label>
                    <Input
                      type="number"
                      placeholder="2024"
                      value={filters.year_max}
                      onChange={(e) => handleFilterChange('year_max', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm text-slate-500 mb-1 block">Min Price</label>
                    <Input
                      type="number"
                      placeholder="$0"
                      value={filters.price_min}
                      onChange={(e) => handleFilterChange('price_min', e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-sm text-slate-500 mb-1 block">Max Price</label>
                    <Input
                      type="number"
                      placeholder="$100,000"
                      value={filters.price_max}
                      onChange={(e) => handleFilterChange('price_max', e.target.value)}
                    />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Results */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <Card key={i} className="overflow-hidden animate-pulse">
                <div className="aspect-[16/10] bg-slate-200 dark:bg-slate-800" />
                <CardContent className="p-4 space-y-3">
                  <div className="h-6 bg-slate-200 dark:bg-slate-800 rounded" />
                  <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-2/3" />
                  <div className="h-8 bg-slate-200 dark:bg-slate-800 rounded w-1/2" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : vehicles.length === 0 ? (
          <div className="text-center py-16">
            <Car className="h-16 w-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
              No Vehicles Found
            </h3>
            <p className="text-slate-500 mb-6">
              Try adjusting your filters or check back later for new listings.
            </p>
            <Button onClick={clearFilters}>Clear Filters</Button>
          </div>
        ) : (
          <>
            <div className={`grid gap-6 ${
              viewMode === 'grid' 
                ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3' 
                : 'grid-cols-1'
            }`}>
              {vehicles.map((vehicle) => (
                <VehicleCard
                  key={vehicle.id}
                  vehicle={vehicle}
                  onClick={() => navigate(`/vehicle-auctions/${vehicle.id}`)}
                />
              ))}
            </div>
            
            {/* Pagination */}
            {total > 12 && (
              <div className="flex justify-center gap-2 mt-8">
                <Button
                  variant="outline"
                  disabled={page === 1}
                  onClick={() => setPage(p => p - 1)}
                >
                  Previous
                </Button>
                <span className="flex items-center px-4 text-slate-600">
                  Page {page} of {Math.ceil(total / 12)}
                </span>
                <Button
                  variant="outline"
                  disabled={page >= Math.ceil(total / 12)}
                  onClick={() => setPage(p => p + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default VehicleAuctionsPage;
