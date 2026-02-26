/**
 * Modern Vehicle Filter Component
 * Glassmorphism design with progressive disclosure
 * Touch-first, WCAG AA compliant for dark mode
 */

import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import {
  Car, Search, Filter, Grid, List, Clock, MapPin,
  DollarSign, ChevronDown, X, SlidersHorizontal, Sparkles,
  Zap, Award, Gauge, Settings2
} from 'lucide-react';

// Accent color for selections
const ACCENT_COLOR = '#007AFF';

// Monochrome SVG logos for vehicle makes (currentColor for light/dark mode)
const VEHICLE_LOGOS = {
  Toyota: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3.14.69 4.22 1.78C13.14 7.86 10.58 9 8 9c-.35 0-.69-.02-1.03-.06A6.95 6.95 0 0112 5zm0 14c-3.87 0-7-3.13-7-7 0-1.5.47-2.89 1.27-4.03.75.62 1.64 1.1 2.62 1.37.19.05.38.1.58.13C5.83 10.09 5.5 11.01 5.5 12c0 3.59 2.91 6.5 6.5 6.5s6.5-2.91 6.5-6.5c0-.99-.22-1.93-.62-2.77a7.34 7.34 0 002.73-1.27A6.95 6.95 0 0119 12c0 3.87-3.13 7-7 7z"/>
    </svg>
  ),
  Honda: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M3 6h18v2H3V6zm0 5h18v2H3v-2zm0 5h18v2H3v-2z"/>
    </svg>
  ),
  Ford: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <ellipse cx="12" cy="12" rx="10" ry="6" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <text x="12" y="14" textAnchor="middle" fontSize="6" fill="currentColor" fontFamily="serif" fontStyle="italic">Ford</text>
    </svg>
  ),
  Chevrolet: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M2 10h8v4H2v-4zm12 0h8v4h-8v-4zM10 8h4v8h-4V8z"/>
    </svg>
  ),
  Tesla: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M12 2L8 6h3v14h2V6h3L12 2z"/>
    </svg>
  ),
  Nissan: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="4" y="10" width="16" height="4" fill="currentColor"/>
    </svg>
  ),
  Hyundai: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <ellipse cx="12" cy="12" rx="10" ry="6" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 12c0-2.21 1.79-4 4-4s4 1.79 4 4" fill="none" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  BMW: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M12 2v10h10M12 12H2v10" fill="none" stroke="currentColor" strokeWidth="1"/>
    </svg>
  ),
  'Mercedes-Benz': (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M12 2v10l8.66 5M12 12L3.34 17M12 12l8.66 5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Audi: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <circle cx="5" cy="12" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.2"/>
      <circle cx="9.5" cy="12" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.2"/>
      <circle cx="14.5" cy="12" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.2"/>
      <circle cx="19" cy="12" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.2"/>
    </svg>
  ),
  Lexus: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <ellipse cx="12" cy="12" rx="10" ry="6" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M12 6l-3 12h6l-3-12z" fill="currentColor"/>
    </svg>
  ),
  Acura: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M12 4L4 18h16L12 4zm0 4l5 10H7l5-10z"/>
    </svg>
  ),
  Infiniti: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M12 4l8 16H4L12 4zm0 3l-5 10h10L12 7z" fill="none" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Porsche: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <rect x="3" y="6" width="18" height="12" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M7 10h10v4H7v-4z" fill="currentColor"/>
    </svg>
  ),
  Volkswagen: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 8l4 8 4-8M6 14l6-4 6 4" fill="none" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
  Mazda: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <ellipse cx="12" cy="12" rx="10" ry="5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M12 7c-3 0-5 2.5-5 5s2 5 5 5 5-2.5 5-5-2-5-5-5z" fill="none" stroke="currentColor" strokeWidth="1"/>
    </svg>
  ),
  Subaru: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <ellipse cx="12" cy="12" rx="10" ry="6" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="8" cy="10" r="1.5" fill="currentColor"/>
      <circle cx="12" cy="10" r="1.5" fill="currentColor"/>
      <circle cx="16" cy="10" r="1.5" fill="currentColor"/>
      <circle cx="10" cy="14" r="1.5" fill="currentColor"/>
      <circle cx="14" cy="14" r="1.5" fill="currentColor"/>
    </svg>
  ),
  Jeep: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <rect x="3" y="8" width="18" height="8" rx="1" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="7" cy="12" r="2" fill="currentColor"/>
      <circle cx="12" cy="12" r="2" fill="currentColor"/>
      <circle cx="17" cy="12" r="2" fill="currentColor"/>
    </svg>
  ),
  RAM: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <path d="M4 8h16v8H4V8zm2 2v4h12v-4H6z"/>
    </svg>
  ),
  GMC: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <rect x="2" y="8" width="20" height="8" rx="1" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <text x="12" y="14" textAnchor="middle" fontSize="6" fill="currentColor" fontWeight="bold">GMC</text>
    </svg>
  ),
  Kia: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <ellipse cx="12" cy="12" rx="10" ry="5" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <text x="12" y="14" textAnchor="middle" fontSize="6" fill="currentColor" fontWeight="bold">KIA</text>
    </svg>
  ),
  Volvo: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
      <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M6 12h12M12 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  ),
};

// Vehicle makes with clean typography (no emojis)
const VEHICLE_MAKES = {
  popular: ['Toyota', 'Honda', 'Ford', 'Chevrolet', 'Tesla', 'Nissan', 'Hyundai'],
  luxury: ['BMW', 'Mercedes-Benz', 'Audi', 'Lexus', 'Acura', 'Infiniti', 'Porsche'],
  other: ['Volkswagen', 'Mazda', 'Subaru', 'Jeep', 'RAM', 'GMC', 'Kia', 'Volvo']
};

// Logo component with fallback
const MakeLogo = ({ make }) => {
  const logo = VEHICLE_LOGOS[make];
  if (logo) {
    return <span className="text-slate-500 dark:text-slate-400 flex-shrink-0">{logo}</span>;
  }
  return <Car className="w-4 h-4 text-slate-400 flex-shrink-0" />;
};

// Body types without emojis
const BODY_TYPES = [
  { value: 'sedan', label: 'Sedan' },
  { value: 'suv', label: 'SUV / Crossover' },
  { value: 'truck', label: 'Truck / Pickup' },
  { value: 'coupe', label: 'Coupe' },
  { value: 'hatchback', label: 'Hatchback' },
  { value: 'van', label: 'Van / Minivan' },
  { value: 'convertible', label: 'Convertible' },
  { value: 'wagon', label: 'Wagon' }
];

// Provinces
const PROVINCES = [
  { value: 'ON', label: 'Ontario' },
  { value: 'QC', label: 'Quebec' },
  { value: 'BC', label: 'British Columbia' },
  { value: 'AB', label: 'Alberta' },
  { value: 'MB', label: 'Manitoba' },
  { value: 'SK', label: 'Saskatchewan' },
  { value: 'NS', label: 'Nova Scotia' },
  { value: 'NB', label: 'New Brunswick' }
];

// Status pills
const STATUS_PILLS = [
  { id: 'all', label: 'All', icon: Sparkles },
  { id: 'ending_soon', label: 'Ending Soon', icon: Clock },
  { id: 'live', label: 'Live Now', icon: Zap },
  { id: 'no_reserve', label: 'No Reserve', icon: Award }
];

// Modern Select Trigger with glassmorphism
const GlassSelectTrigger = React.forwardRef(({ children, className, ...props }, ref) => (
  <SelectTrigger
    ref={ref}
    className={`
      min-h-[48px] px-4
      bg-white/5 dark:bg-white/5
      backdrop-blur-xl
      border border-white/10 dark:border-white/10
      hover:border-[#007AFF]/50 focus:border-[#007AFF]
      rounded-xl
      text-slate-900 dark:text-[#E0E0E0]
      transition-all duration-200
      ${className}
    `}
    {...props}
  >
    {children}
  </SelectTrigger>
));

// Modern Select Content with glassmorphism
const GlassSelectContent = ({ children, ...props }) => (
  <SelectContent
    className="
      bg-[#1a1a1a]/95 dark:bg-[#1a1a1a]/95
      backdrop-blur-2xl
      border border-white/10
      rounded-xl
      shadow-2xl
      max-h-[320px]
    "
    {...props}
  >
    {children}
  </SelectContent>
);

// Price Range Slider Component
const PriceRangeSlider = ({ minValue, maxValue, onMinChange, onMaxChange }) => {
  const [priceRange, setPriceRange] = useState([minValue || 0, maxValue || 100000]);
  
  const handleSliderChange = useCallback((values) => {
    setPriceRange(values);
    onMinChange(values[0]);
    onMaxChange(values[1]);
  }, [onMinChange, onMaxChange]);

  const formatPrice = (price) => {
    if (price >= 1000) {
      return `$${(price / 1000).toFixed(0)}k`;
    }
    return `$${price}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <span className="text-sm text-[#E0E0E0]">{formatPrice(priceRange[0])}</span>
        <span className="text-sm text-[#E0E0E0]">{formatPrice(priceRange[1])}</span>
      </div>
      <Slider
        value={priceRange}
        onValueChange={handleSliderChange}
        min={0}
        max={150000}
        step={1000}
        className="[&_[role=slider]]:bg-[#007AFF] [&_[role=slider]]:border-0 [&_[role=slider]]:w-5 [&_[role=slider]]:h-5"
      />
      <div className="flex gap-2">
        <Input
          type="number"
          placeholder="Min"
          value={priceRange[0] || ''}
          onChange={(e) => handleSliderChange([parseInt(e.target.value) || 0, priceRange[1]])}
          className="h-10 bg-white/5 border-white/10 rounded-lg text-center text-sm"
        />
        <Input
          type="number"
          placeholder="Max"
          value={priceRange[1] || ''}
          onChange={(e) => handleSliderChange([priceRange[0], parseInt(e.target.value) || 150000])}
          className="h-10 bg-white/5 border-white/10 rounded-lg text-center text-sm"
        />
      </div>
    </div>
  );
};

// Year Range Slider Component
const YearRangeSlider = ({ minValue, maxValue, onMinChange, onMaxChange }) => {
  const currentYear = new Date().getFullYear();
  const [yearRange, setYearRange] = useState([minValue || 2010, maxValue || currentYear + 1]);
  
  const handleSliderChange = useCallback((values) => {
    setYearRange(values);
    onMinChange(values[0]);
    onMaxChange(values[1]);
  }, [onMinChange, onMaxChange]);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <span className="text-sm text-[#E0E0E0]">{yearRange[0]}</span>
        <span className="text-sm text-[#E0E0E0]">{yearRange[1]}</span>
      </div>
      <Slider
        value={yearRange}
        onValueChange={handleSliderChange}
        min={1990}
        max={currentYear + 1}
        step={1}
        className="[&_[role=slider]]:bg-[#007AFF] [&_[role=slider]]:border-0 [&_[role=slider]]:w-5 [&_[role=slider]]:h-5"
      />
    </div>
  );
};

const VehicleFilterModern = ({
  filters,
  onFilterChange,
  total,
  viewMode,
  onViewModeChange,
  searchQuery,
  onSearchChange
}) => {
  const [showMoreFilters, setShowMoreFilters] = useState(false);

  const handleFilterChange = useCallback((key, value) => {
    onFilterChange(key, value === 'all' ? '' : value);
  }, [onFilterChange]);

  const activeFilterCount = [
    filters.make && filters.make !== 'all',
    filters.body_type && filters.body_type !== 'all',
    filters.province && filters.province !== 'all',
    filters.year_min || filters.year_max,
    filters.price_min || filters.price_max,
    filters.max_mileage && filters.max_mileage !== 'all',
    filters.transmission && filters.transmission !== 'all'
  ].filter(Boolean).length;

  return (
    <div className="relative mb-8" data-testid="vehicle-filter-modern">
      {/* Glassmorphism Container */}
      <Card className="
        relative overflow-hidden
        bg-white/80 dark:bg-[#121212]/80
        backdrop-blur-2xl
        border border-white/20 dark:border-white/5
        shadow-2xl
        rounded-2xl
      ">
        {/* Header */}
        <div className="
          px-6 py-5
          border-b border-black/5 dark:border-white/5
          bg-gradient-to-r from-slate-900/5 to-transparent dark:from-white/5 dark:to-transparent
        ">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="
                w-12 h-12 
                bg-gradient-to-br from-[#007AFF] to-[#5856D6]
                rounded-2xl 
                flex items-center justify-center
                shadow-lg shadow-[#007AFF]/20
              ">
                <SlidersHorizontal className="h-6 w-6 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Find Your Vehicle
                </h3>
                <p className="text-sm text-slate-500 dark:text-[#E0E0E0]/60">
                  {total} active auctions
                </p>
              </div>
            </div>
            
            {/* View Toggle */}
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-500 dark:text-[#E0E0E0]/60 hidden sm:block">View</span>
              <div className="flex items-center bg-black/5 dark:bg-white/5 rounded-xl p-1">
                <button
                  onClick={() => onViewModeChange('grid')}
                  className={`
                    p-2.5 rounded-lg transition-all duration-200
                    ${viewMode === 'grid' 
                      ? 'bg-[#007AFF] text-white shadow-lg' 
                      : 'text-slate-500 dark:text-[#E0E0E0]/60 hover:text-slate-900 dark:hover:text-white'
                    }
                  `}
                  aria-label="Grid view"
                >
                  <Grid className="h-4 w-4" />
                </button>
                <button
                  onClick={() => onViewModeChange('list')}
                  className={`
                    p-2.5 rounded-lg transition-all duration-200
                    ${viewMode === 'list' 
                      ? 'bg-[#007AFF] text-white shadow-lg' 
                      : 'text-slate-500 dark:text-[#E0E0E0]/60 hover:text-slate-900 dark:hover:text-white'
                    }
                  `}
                  aria-label="List view"
                >
                  <List className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <CardContent className="p-6 space-y-6">
          {/* Status Pills - Horizontal Scroll on Mobile */}
          <div className="flex items-center gap-3 overflow-x-auto pb-2 scrollbar-hide">
            {STATUS_PILLS.map((status) => {
              const Icon = status.icon;
              const isActive = filters.auction_status === status.id || (status.id === 'all' && !filters.auction_status);
              return (
                <button
                  key={status.id}
                  onClick={() => handleFilterChange('auction_status', status.id === 'all' ? '' : status.id)}
                  className={`
                    flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium
                    whitespace-nowrap transition-all duration-200 min-h-[44px]
                    ${isActive 
                      ? 'bg-[#007AFF] text-white shadow-lg shadow-[#007AFF]/30' 
                      : 'bg-black/5 dark:bg-white/5 text-slate-600 dark:text-[#E0E0E0] hover:bg-black/10 dark:hover:bg-white/10'
                    }
                  `}
                >
                  <Icon className="h-4 w-4" />
                  {status.label}
                </button>
              );
            })}
          </div>

          {/* Separator */}
          <div className="h-px bg-black/5 dark:bg-white/5" />

          {/* Primary Filters - 4 Essential Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Vehicle Make */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide">
                Make
              </label>
              <Select 
                value={filters.make || 'all'} 
                onValueChange={(v) => handleFilterChange('make', v)}
              >
                <GlassSelectTrigger data-testid="make-filter-modern">
                  <div className="flex items-center gap-2">
                    <Car className="h-4 w-4 text-[#007AFF]" />
                    <SelectValue placeholder="All Makes" />
                  </div>
                </GlassSelectTrigger>
                <GlassSelectContent>
                  <SelectItem value="all" className="min-h-[44px]">All Makes</SelectItem>
                  
                  <div className="px-3 py-2 text-xs font-medium text-[#E0E0E0]/40 uppercase tracking-wider">
                    Popular
                  </div>
                  {VEHICLE_MAKES.popular.map(make => (
                    <SelectItem key={make} value={make} className="min-h-[44px]">
                      <span className="flex items-center gap-2.5">
                        <MakeLogo make={make} />
                        {make}
                      </span>
                    </SelectItem>
                  ))}
                  
                  <div className="h-px bg-white/5 my-1" />
                  <div className="px-3 py-2 text-xs font-medium text-[#E0E0E0]/40 uppercase tracking-wider">
                    Luxury
                  </div>
                  {VEHICLE_MAKES.luxury.map(make => (
                    <SelectItem key={make} value={make} className="min-h-[44px]">
                      <span className="flex items-center gap-2.5">
                        <MakeLogo make={make} />
                        {make}
                      </span>
                    </SelectItem>
                  ))}
                  
                  <div className="h-px bg-white/5 my-1" />
                  <div className="px-3 py-2 text-xs font-medium text-[#E0E0E0]/40 uppercase tracking-wider">
                    Other
                  </div>
                  {VEHICLE_MAKES.other.map(make => (
                    <SelectItem key={make} value={make} className="min-h-[44px]">
                      <span className="flex items-center gap-2.5">
                        <MakeLogo make={make} />
                        {make}
                      </span>
                    </SelectItem>
                  ))}
                </GlassSelectContent>
              </Select>
            </div>

            {/* Body Type */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide">
                Body Type
              </label>
              <Select 
                value={filters.body_type || 'all'} 
                onValueChange={(v) => handleFilterChange('body_type', v)}
              >
                <GlassSelectTrigger>
                  <SelectValue placeholder="All Types" />
                </GlassSelectTrigger>
                <GlassSelectContent>
                  <SelectItem value="all" className="min-h-[44px]">All Types</SelectItem>
                  {BODY_TYPES.map(type => (
                    <SelectItem key={type.value} value={type.value} className="min-h-[44px]">
                      {type.label}
                    </SelectItem>
                  ))}
                </GlassSelectContent>
              </Select>
            </div>

            {/* Location */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide">
                Location
              </label>
              <Select 
                value={filters.province || 'all'} 
                onValueChange={(v) => handleFilterChange('province', v)}
              >
                <GlassSelectTrigger>
                  <div className="flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-slate-400" />
                    <SelectValue placeholder="All Provinces" />
                  </div>
                </GlassSelectTrigger>
                <GlassSelectContent>
                  <SelectItem value="all" className="min-h-[44px]">All Provinces</SelectItem>
                  {PROVINCES.map(province => (
                    <SelectItem key={province.value} value={province.value} className="min-h-[44px]">
                      {province.label}
                    </SelectItem>
                  ))}
                </GlassSelectContent>
              </Select>
            </div>

            {/* Sort By */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide">
                Sort By
              </label>
              <Select 
                value={filters.sort_by || 'end_time'} 
                onValueChange={(v) => handleFilterChange('sort_by', v)}
              >
                <GlassSelectTrigger data-testid="sort-select-modern">
                  <SelectValue placeholder="Ending Soon" />
                </GlassSelectTrigger>
                <GlassSelectContent>
                  <SelectItem value="end_time" className="min-h-[44px]">Ending Soon</SelectItem>
                  <SelectItem value="created_at" className="min-h-[44px]">Newest Listed</SelectItem>
                  <SelectItem value="current_bid" className="min-h-[44px]">Price: Low to High</SelectItem>
                  <SelectItem value="year" className="min-h-[44px]">Year: Newest</SelectItem>
                  <SelectItem value="mileage" className="min-h-[44px]">Mileage: Lowest</SelectItem>
                </GlassSelectContent>
              </Select>
            </div>
          </div>

          {/* More Filters Toggle */}
          <Button
            variant="ghost"
            onClick={() => setShowMoreFilters(!showMoreFilters)}
            className={`
              w-full min-h-[48px] rounded-xl
              border border-dashed
              transition-all duration-200
              ${showMoreFilters 
                ? 'border-[#007AFF] bg-[#007AFF]/5 text-[#007AFF]' 
                : 'border-slate-300 dark:border-white/10 text-slate-600 dark:text-[#E0E0E0]/60 hover:border-[#007AFF]/50 hover:text-[#007AFF]'
              }
            `}
          >
            <Filter className="h-4 w-4 mr-2" />
            {showMoreFilters ? 'Hide Filters' : 'More Filters'}
            {activeFilterCount > 0 && !showMoreFilters && (
              <Badge className="ml-2 bg-[#007AFF] text-white text-xs px-2">
                {activeFilterCount}
              </Badge>
            )}
            <ChevronDown className={`h-4 w-4 ml-2 transition-transform duration-200 ${showMoreFilters ? 'rotate-180' : ''}`} />
          </Button>

          {/* Extended Filters Panel */}
          <AnimatePresence>
            {showMoreFilters && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: 'easeInOut' }}
                className="overflow-hidden"
              >
                <div className="pt-4 space-y-6">
                  {/* Separator */}
                  <div className="h-px bg-black/5 dark:bg-white/5" />
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {/* Price Range with Slider */}
                    <div className="space-y-3">
                      <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide flex items-center gap-2">
                        <DollarSign className="h-3.5 w-3.5" />
                        Price Range (CAD)
                      </label>
                      <PriceRangeSlider
                        minValue={filters.price_min}
                        maxValue={filters.price_max}
                        onMinChange={(v) => handleFilterChange('price_min', v)}
                        onMaxChange={(v) => handleFilterChange('price_max', v)}
                      />
                    </div>

                    {/* Year Range with Slider */}
                    <div className="space-y-3">
                      <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide flex items-center gap-2">
                        <Clock className="h-3.5 w-3.5" />
                        Year Range
                      </label>
                      <YearRangeSlider
                        minValue={filters.year_min}
                        maxValue={filters.year_max}
                        onMinChange={(v) => handleFilterChange('year_min', v)}
                        onMaxChange={(v) => handleFilterChange('year_max', v)}
                      />
                    </div>

                    {/* Mileage & Transmission */}
                    <div className="space-y-4">
                      {/* Max Mileage */}
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide flex items-center gap-2">
                          <Gauge className="h-3.5 w-3.5" />
                          Max Mileage
                        </label>
                        <Select 
                          value={filters.max_mileage || 'all'} 
                          onValueChange={(v) => handleFilterChange('max_mileage', v)}
                        >
                          <GlassSelectTrigger>
                            <SelectValue placeholder="Any Mileage" />
                          </GlassSelectTrigger>
                          <GlassSelectContent>
                            <SelectItem value="all" className="min-h-[44px]">Any Mileage</SelectItem>
                            <SelectItem value="25000" className="min-h-[44px]">Under 25,000 km</SelectItem>
                            <SelectItem value="50000" className="min-h-[44px]">Under 50,000 km</SelectItem>
                            <SelectItem value="100000" className="min-h-[44px]">Under 100,000 km</SelectItem>
                            <SelectItem value="150000" className="min-h-[44px]">Under 150,000 km</SelectItem>
                          </GlassSelectContent>
                        </Select>
                      </div>

                      {/* Transmission */}
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-500 dark:text-[#E0E0E0]/60 uppercase tracking-wide flex items-center gap-2">
                          <Settings2 className="h-3.5 w-3.5" />
                          Transmission
                        </label>
                        <Select 
                          value={filters.transmission || 'all'} 
                          onValueChange={(v) => handleFilterChange('transmission', v)}
                        >
                          <GlassSelectTrigger>
                            <SelectValue placeholder="Any" />
                          </GlassSelectTrigger>
                          <GlassSelectContent>
                            <SelectItem value="all" className="min-h-[44px]">Any</SelectItem>
                            <SelectItem value="automatic" className="min-h-[44px]">Automatic</SelectItem>
                            <SelectItem value="manual" className="min-h-[44px]">Manual</SelectItem>
                            <SelectItem value="cvt" className="min-h-[44px]">CVT</SelectItem>
                          </GlassSelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Active Filters Tags */}
          {activeFilterCount > 0 && (
            <>
              <div className="h-px bg-black/5 dark:bg-white/5" />
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs text-slate-500 dark:text-[#E0E0E0]/40 uppercase tracking-wide">
                  Active:
                </span>
                {filters.make && filters.make !== 'all' && (
                  <Badge 
                    variant="secondary" 
                    className="bg-[#007AFF]/10 text-[#007AFF] hover:bg-[#007AFF]/20 cursor-pointer min-h-[32px] px-3"
                    onClick={() => handleFilterChange('make', 'all')}
                  >
                    {filters.make} <X className="h-3 w-3 ml-1.5" />
                  </Badge>
                )}
                {filters.body_type && filters.body_type !== 'all' && (
                  <Badge 
                    variant="secondary" 
                    className="bg-[#007AFF]/10 text-[#007AFF] hover:bg-[#007AFF]/20 cursor-pointer min-h-[32px] px-3"
                    onClick={() => handleFilterChange('body_type', 'all')}
                  >
                    {filters.body_type} <X className="h-3 w-3 ml-1.5" />
                  </Badge>
                )}
                {filters.province && filters.province !== 'all' && (
                  <Badge 
                    variant="secondary" 
                    className="bg-[#007AFF]/10 text-[#007AFF] hover:bg-[#007AFF]/20 cursor-pointer min-h-[32px] px-3"
                    onClick={() => handleFilterChange('province', 'all')}
                  >
                    {filters.province} <X className="h-3 w-3 ml-1.5" />
                  </Badge>
                )}
                {(filters.price_min || filters.price_max) && (
                  <Badge 
                    variant="secondary" 
                    className="bg-[#007AFF]/10 text-[#007AFF] hover:bg-[#007AFF]/20 cursor-pointer min-h-[32px] px-3"
                    onClick={() => {
                      handleFilterChange('price_min', '');
                      handleFilterChange('price_max', '');
                    }}
                  >
                    ${filters.price_min || '0'} - ${filters.price_max || 'Max'} <X className="h-3 w-3 ml-1.5" />
                  </Badge>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-slate-500 dark:text-[#E0E0E0]/40 hover:text-red-500"
                  onClick={() => {
                    ['make', 'body_type', 'province', 'price_min', 'price_max', 'year_min', 'year_max', 'max_mileage', 'transmission', 'auction_status'].forEach(key => {
                      handleFilterChange(key, '');
                    });
                  }}
                >
                  Clear All
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default VehicleFilterModern;
