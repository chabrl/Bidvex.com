/**
 * Vehicle Auctions Marketplace Page
 * Main browse page for vehicle auctions - Automotive-inspired design
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
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
  Award, Shield, Zap, TrendingUp, Eye, Heart, RefreshCw,
  ChevronDown, X, SlidersHorizontal, Sparkles, FileText
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
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState('grid');
  const [vehicleAuctionsEnabled, setVehicleAuctionsEnabled] = useState(false);
  
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
    auction_status: searchParams.get('auction_status') || '',
    max_mileage: searchParams.get('max_mileage') || '',
    transmission: searchParams.get('transmission') || '',
  });
  
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Check if vehicle auctions are enabled globally
  useEffect(() => {
    const checkVehicleAuctionsStatus = async () => {
      try {
        const response = await axios.get(`${API}/vehicles/system/status`);
        setVehicleAuctionsEnabled(response.data.vehicle_auctions_enabled || false);
      } catch (error) {
        // Default to disabled if can't reach endpoint
        setVehicleAuctionsEnabled(false);
      }
    };
    checkVehicleAuctionsStatus();
  }, []);

  const fetchVehicles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', page.toString());
      params.set('limit', '12');
      
      Object.entries(filters).forEach(([key, value]) => {
        // Skip "all" placeholder values and empty values
        if (value && value !== 'all') params.set(key, value);
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
          
          {/* System Status Notice - View Only Mode */}
          {!vehicleAuctionsEnabled && (
            <div className="mt-6 p-4 bg-amber-500/20 border border-amber-500/40 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-amber-500/30 rounded-full flex items-center justify-center">
                  <Eye className="h-5 w-5 text-amber-300" />
                </div>
                <div>
                  <h4 className="text-amber-200 font-semibold">Discovery Mode</h4>
                  <p className="text-amber-300/80 text-sm">
                    Vehicle auctions are currently in preview mode. Browse and discover vehicles while we finalize permits.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Premium Filter Card */}
        <div className="relative mb-8">
          {/* Decorative gradient border */}
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500 rounded-2xl opacity-20 blur-sm" />
          
          <Card className="relative bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border-0 shadow-2xl rounded-2xl overflow-hidden">
            {/* Header with gradient accent */}
            <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                    <SlidersHorizontal className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h3 className="text-white font-semibold">Find Your Vehicle</h3>
                    <p className="text-slate-400 text-sm">Search across {total} active auctions</p>
                  </div>
                </div>
                
                {/* View Toggle - Premium Style */}
                <div className="flex items-center gap-2">
                  <span className="text-slate-400 text-sm mr-2">View:</span>
                  <div className="flex items-center bg-slate-800 rounded-lg p-1">
                    <button
                      onClick={() => setViewMode('grid')}
                      className={`p-2 rounded-md transition-all ${
                        viewMode === 'grid' 
                          ? 'bg-blue-500 text-white shadow-lg' 
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      <Grid className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => setViewMode('list')}
                      className={`p-2 rounded-md transition-all ${
                        viewMode === 'list' 
                          ? 'bg-blue-500 text-white shadow-lg' 
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      <List className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
            
            <CardContent className="p-6 space-y-6">
              {/* Auction Status Pills */}
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Status:</span>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'all', label: 'All Auctions', icon: Sparkles },
                    { id: 'ending_soon', label: 'Ending Soon', icon: Clock },
                    { id: 'live', label: 'Live Now', icon: Zap },
                    { id: 'no_reserve', label: 'No Reserve', icon: Award },
                    { id: 'buy_now', label: 'Buy Now', icon: DollarSign },
                  ].map((status) => {
                    const Icon = status.icon;
                    const isActive = filters.auction_status === status.id || (status.id === 'all' && !filters.auction_status);
                    return (
                      <button
                        key={status.id}
                        onClick={() => handleFilterChange('auction_status', status.id === 'all' ? '' : status.id)}
                        className={`
                          group flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium
                          transition-all duration-200 ease-out
                          ${isActive 
                            ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/25 scale-105' 
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 hover:scale-102'
                          }
                        `}
                      >
                        <Icon className={`h-4 w-4 ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-600'}`} />
                        {status.label}
                      </button>
                    );
                  })}
                </div>
              </div>
              
              {/* Main Filters Row */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                {/* Vehicle Make - Prominent Searchable */}
                <div className="md:col-span-4">
                  <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                    Vehicle Make
                  </label>
                  <Select value={filters.make || 'all'} onValueChange={(v) => handleFilterChange('make', v)}>
                    <SelectTrigger 
                      className="w-full h-12 bg-transparent border-2 border-slate-200 dark:border-slate-700 hover:border-blue-400 focus:border-blue-500 transition-colors rounded-xl"
                      data-testid="make-filter"
                    >
                      <div className="flex items-center gap-2">
                        <Car className="h-5 w-5 text-blue-500" />
                        <SelectValue placeholder="Select Make" />
                      </div>
                    </SelectTrigger>
                    <SelectContent className="max-h-80 bg-white dark:bg-slate-900">
                      <SelectItem value="all">
                        <span className="flex items-center gap-2">
                          <span className="text-lg">🚗</span> All Makes
                        </span>
                      </SelectItem>
                      <div className="px-2 py-1.5 text-xs font-semibold text-slate-400 uppercase">Popular</div>
                      <SelectItem value="Toyota"><span className="flex items-center gap-2">🇯🇵 Toyota</span></SelectItem>
                      <SelectItem value="Honda"><span className="flex items-center gap-2">🇯🇵 Honda</span></SelectItem>
                      <SelectItem value="Ford"><span className="flex items-center gap-2">🇺🇸 Ford</span></SelectItem>
                      <SelectItem value="Chevrolet"><span className="flex items-center gap-2">🇺🇸 Chevrolet</span></SelectItem>
                      <SelectItem value="Tesla"><span className="flex items-center gap-2">⚡ Tesla</span></SelectItem>
                      <div className="px-2 py-1.5 text-xs font-semibold text-slate-400 uppercase">Luxury</div>
                      <SelectItem value="BMW"><span className="flex items-center gap-2">🇩🇪 BMW</span></SelectItem>
                      <SelectItem value="Mercedes-Benz"><span className="flex items-center gap-2">🇩🇪 Mercedes-Benz</span></SelectItem>
                      <SelectItem value="Audi"><span className="flex items-center gap-2">🇩🇪 Audi</span></SelectItem>
                      <SelectItem value="Lexus"><span className="flex items-center gap-2">🇯🇵 Lexus</span></SelectItem>
                      <SelectItem value="Acura"><span className="flex items-center gap-2">🇯🇵 Acura</span></SelectItem>
                      <SelectItem value="Infiniti"><span className="flex items-center gap-2">🇯🇵 Infiniti</span></SelectItem>
                      <div className="px-2 py-1.5 text-xs font-semibold text-slate-400 uppercase">Other</div>
                      <SelectItem value="Nissan">Nissan</SelectItem>
                      <SelectItem value="Hyundai">Hyundai</SelectItem>
                      <SelectItem value="Kia">Kia</SelectItem>
                      <SelectItem value="Volkswagen">Volkswagen</SelectItem>
                      <SelectItem value="Mazda">Mazda</SelectItem>
                      <SelectItem value="Subaru">Subaru</SelectItem>
                      <SelectItem value="Jeep">Jeep</SelectItem>
                      <SelectItem value="RAM">RAM</SelectItem>
                      <SelectItem value="GMC">GMC</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Body Type */}
                <div className="md:col-span-2">
                  <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                    Body Type
                  </label>
                  <Select value={filters.body_type || 'all'} onValueChange={(v) => handleFilterChange('body_type', v)}>
                    <SelectTrigger className="w-full h-12 bg-transparent border-2 border-slate-200 dark:border-slate-700 hover:border-blue-400 rounded-xl">
                      <SelectValue placeholder="All Types" />
                    </SelectTrigger>
                    <SelectContent className="bg-white dark:bg-slate-900">
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="sedan">🚗 Sedan</SelectItem>
                      <SelectItem value="suv">🚙 SUV / Crossover</SelectItem>
                      <SelectItem value="truck">🛻 Truck / Pickup</SelectItem>
                      <SelectItem value="coupe">🏎️ Coupe</SelectItem>
                      <SelectItem value="hatchback">🚘 Hatchback</SelectItem>
                      <SelectItem value="van">🚐 Van / Minivan</SelectItem>
                      <SelectItem value="convertible">🏎️ Convertible</SelectItem>
                      <SelectItem value="wagon">🚗 Wagon</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Province */}
                <div className="md:col-span-2">
                  <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                    Location
                  </label>
                  <Select value={filters.province || 'all'} onValueChange={(v) => handleFilterChange('province', v)}>
                    <SelectTrigger className="w-full h-12 bg-transparent border-2 border-slate-200 dark:border-slate-700 hover:border-blue-400 rounded-xl">
                      <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-slate-400" />
                        <SelectValue placeholder="Province" />
                      </div>
                    </SelectTrigger>
                    <SelectContent className="bg-white dark:bg-slate-900">
                      <SelectItem value="all">All Provinces</SelectItem>
                      <SelectItem value="ON">🍁 Ontario</SelectItem>
                      <SelectItem value="QC">⚜️ Quebec</SelectItem>
                      <SelectItem value="BC">🌲 British Columbia</SelectItem>
                      <SelectItem value="AB">🏔️ Alberta</SelectItem>
                      <SelectItem value="MB">Manitoba</SelectItem>
                      <SelectItem value="SK">Saskatchewan</SelectItem>
                      <SelectItem value="NS">Nova Scotia</SelectItem>
                      <SelectItem value="NB">New Brunswick</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Sort */}
                <div className="md:col-span-2">
                  <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                    Sort By
                  </label>
                  <Select value={filters.sort_by} onValueChange={(v) => handleFilterChange('sort_by', v)}>
                    <SelectTrigger className="w-full h-12 bg-transparent border-2 border-slate-200 dark:border-slate-700 hover:border-blue-400 rounded-xl" data-testid="sort-select">
                      <SelectValue placeholder="Sort by" />
                    </SelectTrigger>
                    <SelectContent className="bg-white dark:bg-slate-900">
                      <SelectItem value="end_time">⏰ Ending Soon</SelectItem>
                      <SelectItem value="created_at">✨ Newest Listed</SelectItem>
                      <SelectItem value="current_bid">💰 Price: Low → High</SelectItem>
                      <SelectItem value="year">📅 Year: Newest</SelectItem>
                      <SelectItem value="mileage">🛣️ Mileage: Low → High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                {/* More Filters Button */}
                <div className="md:col-span-2 flex items-end">
                  <Button 
                    variant="outline"
                    onClick={() => setShowFilters(!showFilters)}
                    className={`
                      w-full h-12 rounded-xl border-2 transition-all duration-200
                      ${showFilters 
                        ? 'bg-blue-50 border-blue-500 text-blue-600 dark:bg-blue-900/30 dark:border-blue-400 dark:text-blue-400' 
                        : 'border-slate-200 dark:border-slate-700 hover:border-blue-400'
                      }
                    `}
                  >
                    <Filter className="h-4 w-4 mr-2" />
                    {showFilters ? 'Less Filters' : 'More Filters'}
                    <ChevronDown className={`h-4 w-4 ml-2 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
                  </Button>
                </div>
              </div>
              
              {/* Extended Filters Panel */}
              <AnimatePresence>
                {showFilters && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="pt-6 border-t border-slate-200 dark:border-slate-700">
                      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                        {/* Year Range */}
                        <div className="col-span-2">
                          <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                            Year Range
                          </label>
                          <div className="flex items-center gap-2">
                            <Input
                              type="number"
                              placeholder="From"
                              value={filters.year_min}
                              onChange={(e) => handleFilterChange('year_min', e.target.value)}
                              className="h-10 bg-transparent border-2 border-slate-200 dark:border-slate-700 rounded-xl placeholder:text-slate-400"
                            />
                            <span className="text-slate-400">—</span>
                            <Input
                              type="number"
                              placeholder="To"
                              value={filters.year_max}
                              onChange={(e) => handleFilterChange('year_max', e.target.value)}
                              className="h-10 bg-transparent border-2 border-slate-200 dark:border-slate-700 rounded-xl placeholder:text-slate-400"
                            />
                          </div>
                        </div>
                        
                        {/* Price Range */}
                        <div className="col-span-2">
                          <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                            Price Range (CAD)
                          </label>
                          <div className="flex items-center gap-2">
                            <div className="relative flex-1">
                              <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                              <Input
                                type="number"
                                placeholder="Min"
                                value={filters.price_min}
                                onChange={(e) => handleFilterChange('price_min', e.target.value)}
                                className="h-10 pl-9 bg-transparent border-2 border-slate-200 dark:border-slate-700 rounded-xl placeholder:text-slate-400"
                              />
                            </div>
                            <span className="text-slate-400">—</span>
                            <div className="relative flex-1">
                              <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                              <Input
                                type="number"
                                placeholder="Max"
                                value={filters.price_max}
                                onChange={(e) => handleFilterChange('price_max', e.target.value)}
                                className="h-10 pl-9 bg-transparent border-2 border-slate-200 dark:border-slate-700 rounded-xl placeholder:text-slate-400"
                              />
                            </div>
                          </div>
                        </div>
                        
                        {/* Mileage */}
                        <div>
                          <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                            Max Mileage
                          </label>
                          <Select value={filters.max_mileage || 'all'} onValueChange={(v) => handleFilterChange('max_mileage', v)}>
                            <SelectTrigger className="h-10 bg-transparent border-2 border-slate-200 dark:border-slate-700 rounded-xl">
                              <SelectValue placeholder="Any" />
                            </SelectTrigger>
                            <SelectContent className="bg-white dark:bg-slate-900">
                              <SelectItem value="all">Any Mileage</SelectItem>
                              <SelectItem value="25000">Under 25,000 km</SelectItem>
                              <SelectItem value="50000">Under 50,000 km</SelectItem>
                              <SelectItem value="100000">Under 100,000 km</SelectItem>
                              <SelectItem value="150000">Under 150,000 km</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        
                        {/* Transmission */}
                        <div>
                          <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 block">
                            Transmission
                          </label>
                          <Select value={filters.transmission || 'all'} onValueChange={(v) => handleFilterChange('transmission', v)}>
                            <SelectTrigger className="h-10 bg-transparent border-2 border-slate-200 dark:border-slate-700 rounded-xl">
                              <SelectValue placeholder="Any" />
                            </SelectTrigger>
                            <SelectContent className="bg-white dark:bg-slate-900">
                              <SelectItem value="all">Any</SelectItem>
                              <SelectItem value="automatic">Automatic</SelectItem>
                              <SelectItem value="manual">Manual</SelectItem>
                              <SelectItem value="cvt">CVT</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
              
              {/* Active Filters & Clear */}
              {(filters.make !== 'all' && filters.make) || 
               (filters.body_type !== 'all' && filters.body_type) || 
               (filters.province !== 'all' && filters.province) ||
               filters.year_min || filters.year_max || 
               filters.price_min || filters.price_max ? (
                <div className="flex items-center gap-3 pt-4 border-t border-slate-200 dark:border-slate-700">
                  <span className="text-sm text-slate-500">Active Filters:</span>
                  <div className="flex flex-wrap gap-2">
                    {filters.make && filters.make !== 'all' && (
                      <Badge 
                        variant="secondary" 
                        className="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 hover:bg-blue-200 cursor-pointer"
                        onClick={() => handleFilterChange('make', 'all')}
                      >
                        {filters.make} <X className="h-3 w-3 ml-1" />
                      </Badge>
                    )}
                    {filters.body_type && filters.body_type !== 'all' && (
                      <Badge 
                        variant="secondary" 
                        className="bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 hover:bg-purple-200 cursor-pointer"
                        onClick={() => handleFilterChange('body_type', 'all')}
                      >
                        {filters.body_type} <X className="h-3 w-3 ml-1" />
                      </Badge>
                    )}
                    {filters.province && filters.province !== 'all' && (
                      <Badge 
                        variant="secondary" 
                        className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-200 cursor-pointer"
                        onClick={() => handleFilterChange('province', 'all')}
                      >
                        {filters.province} <X className="h-3 w-3 ml-1" />
                      </Badge>
                    )}
                    {(filters.year_min || filters.year_max) && (
                      <Badge 
                        variant="secondary" 
                        className="bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400 hover:bg-orange-200 cursor-pointer"
                        onClick={() => { handleFilterChange('year_min', ''); handleFilterChange('year_max', ''); }}
                      >
                        Year: {filters.year_min || '*'} - {filters.year_max || '*'} <X className="h-3 w-3 ml-1" />
                      </Badge>
                    )}
                    {(filters.price_min || filters.price_max) && (
                      <Badge 
                        variant="secondary" 
                        className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 hover:bg-emerald-200 cursor-pointer"
                        onClick={() => { handleFilterChange('price_min', ''); handleFilterChange('price_max', ''); }}
                      >
                        ${filters.price_min || '0'} - ${filters.price_max || '∞'} <X className="h-3 w-3 ml-1" />
                      </Badge>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={clearFilters}
                    className="ml-auto text-slate-500 hover:text-red-500"
                  >
                    <RefreshCw className="h-4 w-4 mr-1" /> Clear All
                  </Button>
                </div>
              ) : null}
            </CardContent>
          </Card>
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
