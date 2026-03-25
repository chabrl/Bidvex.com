import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Sheet, SheetContent, SheetTrigger } from '../components/ui/sheet';
import {
  Building2, ChevronDown, ChevronRight, MapPin, Tag,
  Filter, Search, X, Loader2
} from 'lucide-react';

const API = API_BASE;

const MarketplaceSidebar = ({ onFiltersChange, className = '' }) => {
  const [filterData, setFilterData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Selected filters
  const [selectedAuctioneers, setSelectedAuctioneers] = useState([]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedRegions, setSelectedRegions] = useState([]);
  const [selectedCities, setSelectedCities] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');

  // Accordion state
  const [expandedSections, setExpandedSections] = useState({ auctioneers: true, categories: true, locations: true });

  const fetchFilters = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/marketplace/filter-counts`);
      setFilterData(res.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchFilters(); }, [fetchFilters]);

  useEffect(() => {
    if (onFiltersChange) {
      onFiltersChange({
        auctioneers: selectedAuctioneers,
        categories: selectedCategories,
        regions: selectedRegions,
        cities: selectedCities,
        search: searchQuery,
      });
    }
  }, [selectedAuctioneers, selectedCategories, selectedRegions, selectedCities, searchQuery]);

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const toggleFilter = (list, setList, value) => {
    setList(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]);
  };

  const clearAll = () => {
    setSelectedAuctioneers([]);
    setSelectedCategories([]);
    setSelectedRegions([]);
    setSelectedCities([]);
    setSearchQuery('');
  };

  const activeCount = selectedAuctioneers.length + selectedCategories.length + selectedRegions.length + selectedCities.length;

  const SidebarContent = () => (
    <div className="space-y-1" data-testid="marketplace-sidebar">
      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <Input
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search items..."
            className="pl-8 h-8 text-xs bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700"
            data-testid="sidebar-search"
          />
        </div>
      </div>

      {/* Active Filters */}
      {activeCount > 0 && (
        <div className="px-3 pb-2">
          <button onClick={clearAll} className="text-[11px] text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1" data-testid="sidebar-clear-all">
            <X className="w-3 h-3" /> Clear all filters ({activeCount})
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-6"><Loader2 className="w-4 h-4 animate-spin text-slate-400" /></div>
      ) : (
        <>
          {/* Auctioneer Section */}
          {filterData?.auctioneers?.length > 0 && (
            <div className="border-b border-slate-100 dark:border-slate-800">
              <button onClick={() => toggleSection('auctioneers')}
                className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                data-testid="sidebar-section-auctioneers">
                <span className="flex items-center gap-1.5"><Building2 className="w-3.5 h-3.5" /> Auctioneer</span>
                {expandedSections.auctioneers ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
              {expandedSections.auctioneers && (
                <div className="px-3 pb-2 space-y-0.5">
                  {filterData.auctioneers.map(a => (
                    <label key={a.id} className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-xs" data-testid={`filter-auctioneer-${a.id}`}>
                      <input type="checkbox" checked={selectedAuctioneers.includes(a.id)}
                        onChange={() => toggleFilter(selectedAuctioneers, setSelectedAuctioneers, a.id)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                      <span className="flex-1 truncate text-slate-600 dark:text-slate-400">{a.name}</span>
                      <span className="text-[10px] text-slate-400 tabular-nums">({a.count})</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Category Section */}
          <div className="border-b border-slate-100 dark:border-slate-800">
            <button onClick={() => toggleSection('categories')}
              className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50"
              data-testid="sidebar-section-categories">
              <span className="flex items-center gap-1.5"><Tag className="w-3.5 h-3.5" /> Category</span>
              {expandedSections.categories ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
            {expandedSections.categories && (
              <div className="px-3 pb-2 space-y-0.5 max-h-[280px] overflow-y-auto">
                {(filterData?.categories || []).map(c => (
                  <label key={c.name} className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-xs" data-testid={`filter-category-${c.name}`}>
                    <input type="checkbox" checked={selectedCategories.includes(c.name)}
                      onChange={() => toggleFilter(selectedCategories, setSelectedCategories, c.name)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                    <span className="flex-1 truncate text-slate-600 dark:text-slate-400">{c.name}</span>
                    <span className="text-[10px] text-slate-400 tabular-nums">({c.count})</span>
                  </label>
                ))}
                {(!filterData?.categories || filterData.categories.length === 0) && (
                  <p className="text-[11px] text-slate-400 px-2 py-1">No categories yet</p>
                )}
              </div>
            )}
          </div>

          {/* Location Section */}
          <div>
            <button onClick={() => toggleSection('locations')}
              className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50"
              data-testid="sidebar-section-locations">
              <span className="flex items-center gap-1.5"><MapPin className="w-3.5 h-3.5" /> Location</span>
              {expandedSections.locations ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
            {expandedSections.locations && (
              <div className="px-3 pb-2 space-y-1 max-h-[300px] overflow-y-auto">
                {(filterData?.locations || []).map(loc => (
                  <div key={loc.region}>
                    <label className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-xs font-medium" data-testid={`filter-region-${loc.region}`}>
                      <input type="checkbox" checked={selectedRegions.includes(loc.region)}
                        onChange={() => toggleFilter(selectedRegions, setSelectedRegions, loc.region)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                      <span className="flex-1 text-slate-700 dark:text-slate-300">{loc.region}</span>
                      <span className="text-[10px] text-slate-400 tabular-nums">({loc.count})</span>
                    </label>
                    {selectedRegions.includes(loc.region) && loc.cities?.length > 0 && (
                      <div className="ml-5 space-y-0.5">
                        {loc.cities.map(city => (
                          <label key={city.name} className="flex items-center gap-2 px-2 py-1 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-[11px]" data-testid={`filter-city-${city.name}`}>
                            <input type="checkbox" checked={selectedCities.includes(city.name)}
                              onChange={() => toggleFilter(selectedCities, setSelectedCities, city.name)}
                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3 w-3" />
                            <span className="flex-1 text-slate-500 dark:text-slate-400">{city.name}</span>
                            <span className="text-[10px] text-slate-400">({city.count})</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {(!filterData?.locations || filterData.locations.length === 0) && (
                  <p className="text-[11px] text-slate-400 px-2 py-1">No locations yet</p>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <div className={`hidden lg:block w-[240px] flex-shrink-0 ${className}`}>
        <div className="sticky top-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden" data-testid="sidebar-desktop">
          <div className="px-3 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5" /> Filters
            </span>
            {filterData && (
              <span className="text-[10px] text-slate-400">{filterData.total_active_items} items</span>
            )}
          </div>
          <SidebarContent />
        </div>
      </div>

      {/* Mobile Filter Button + Sheet */}
      <div className="lg:hidden">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" data-testid="sidebar-mobile-trigger">
              <Filter className="w-3.5 h-3.5" />
              Filters
              {activeCount > 0 && (
                <Badge className="ml-1 h-4 w-4 p-0 flex items-center justify-center text-[10px] bg-blue-600 text-white">{activeCount}</Badge>
              )}
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[280px] p-0 pt-10">
            <div className="px-3 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <span className="text-xs font-semibold flex items-center gap-1.5">
                <Filter className="w-3.5 h-3.5" /> Filters
              </span>
              {filterData && (
                <span className="text-[10px] text-slate-400">{filterData.total_active_items} items</span>
              )}
            </div>
            <SidebarContent />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
};

export default MarketplaceSidebar;
