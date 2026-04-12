import API_BASE from '../config';
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useCategoryTree } from '../hooks/useCategoryTree';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Sheet, SheetContent, SheetTrigger } from '../components/ui/sheet';
import {
  Building2, ChevronDown, ChevronRight, ChevronLeft, MapPin, Tag,
  Filter, Search, X, Loader2, Check
} from 'lucide-react';

const API = API_BASE;

const MarketplaceSidebar = ({ onFiltersChange, className = '' }) => {
  const { t } = useTranslation();
  const { tree: categoryTree, isLoading: catTreeLoading, getName } = useCategoryTree();
  const [filterData, setFilterData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Selected filters
  const [selectedAuctioneers, setSelectedAuctioneers] = useState([]);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedRegions, setSelectedRegions] = useState([]);
  const [selectedCities, setSelectedCities] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');

  // Accordion state — which parent categories are expanded (desktop)
  const [expandedSections, setExpandedSections] = useState({ auctioneers: true, categories: true, locations: true });
  const [expandedParents, setExpandedParents] = useState({});

  // Mobile drill-down state
  const [mobileDrillParent, setMobileDrillParent] = useState(null);

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

  const toggleParent = (parentId) => {
    setExpandedParents(prev => ({ ...prev, [parentId]: !prev[parentId] }));
  };

  const toggleFilter = (list, setList, value) => {
    setList(prev => prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]);
  };

  // When a parent category is toggled: select/deselect parent + all children
  const toggleParentCategory = (parentNode) => {
    const allNames = [parentNode.nameEn, ...parentNode.children.map(c => c.nameEn)];
    const allSelected = allNames.every(n => selectedCategories.includes(n));
    if (allSelected) {
      setSelectedCategories(prev => prev.filter(n => !allNames.includes(n)));
    } else {
      setSelectedCategories(prev => [...new Set([...prev, ...allNames])]);
    }
  };

  // When a child category is toggled
  const toggleChildCategory = (childNameEn) => {
    toggleFilter(selectedCategories, setSelectedCategories, childNameEn);
  };

  const clearAll = () => {
    setSelectedAuctioneers([]);
    setSelectedCategories([]);
    setSelectedRegions([]);
    setSelectedCities([]);
    setSearchQuery('');
  };

  const activeCount = selectedAuctioneers.length + selectedCategories.length + selectedRegions.length + selectedCities.length;

  // ─── Desktop Tree Category Section ──────────────────────
  const DesktopCategoryTree = () => (
    <div className="border-b border-slate-100 dark:border-slate-800" data-testid="sidebar-category-tree">
      <button
        onClick={() => toggleSection('categories')}
        className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
        data-testid="sidebar-section-categories"
      >
        <span className="flex items-center gap-1.5"><Tag className="w-3.5 h-3.5" /> {t('filters.category', 'Category')}</span>
        {expandedSections.categories ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
      </button>
      {expandedSections.categories && (
        <ScrollArea className="max-h-[340px]">
          <div className="px-2 pb-2 space-y-0.5">
            {catTreeLoading ? (
              <div className="flex justify-center py-3"><Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" /></div>
            ) : categoryTree.length === 0 ? (
              <p className="text-[11px] text-slate-400 px-2 py-1">{t('filters.noCategories', 'No categories yet')}</p>
            ) : (
              categoryTree.map(parent => {
                const hasChildren = parent.children.length > 0;
                const isExpanded = expandedParents[parent.id];
                const parentSelected = selectedCategories.includes(parent.nameEn);
                const childrenSelected = parent.children.filter(c => selectedCategories.includes(c.nameEn)).length;
                const allChildrenSelected = hasChildren && childrenSelected === parent.children.length;

                return (
                  <div key={parent.id} data-testid={`cat-parent-${parent.id}`}>
                    {/* Parent row */}
                    <div className="flex items-center gap-1 group">
                      {hasChildren ? (
                        <button
                          onClick={() => toggleParent(parent.id)}
                          className="p-0.5 rounded hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors flex-shrink-0"
                          data-testid={`cat-expand-${parent.id}`}
                          aria-label={isExpanded ? 'Collapse' : 'Expand'}
                        >
                          {isExpanded
                            ? <ChevronDown className="w-3 h-3 text-slate-500" />
                            : <ChevronRight className="w-3 h-3 text-slate-400" />
                          }
                        </button>
                      ) : (
                        <span className="w-4" /> /* spacer for leaf parents */
                      )}
                      <label
                        className="flex items-center gap-1.5 flex-1 px-1.5 py-1.5 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                        data-testid={`cat-filter-${parent.nameEn}`}
                      >
                        <input
                          type="checkbox"
                          checked={hasChildren ? (parentSelected && allChildrenSelected) : parentSelected}
                          ref={el => {
                            if (el && hasChildren) el.indeterminate = childrenSelected > 0 && !allChildrenSelected;
                          }}
                          onChange={() => hasChildren ? toggleParentCategory(parent) : toggleChildCategory(parent.nameEn)}
                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5 flex-shrink-0"
                        />
                        <span className="text-sm flex-shrink-0" role="img" aria-hidden="true">{parent.icon}</span>
                        <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 truncate">{getName(parent)}</span>
                        {hasChildren && childrenSelected > 0 && (
                          <Badge variant="secondary" className="ml-auto h-4 min-w-[16px] px-1 text-[9px] font-medium bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
                            {childrenSelected}
                          </Badge>
                        )}
                      </label>
                    </div>

                    {/* Children (indented) */}
                    {hasChildren && isExpanded && (
                      <div className="ml-5 border-l border-slate-100 dark:border-slate-700/50 pl-1 space-y-0.5 mt-0.5">
                        {parent.children.map(child => (
                          <label
                            key={child.id}
                            className="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                            data-testid={`cat-filter-${child.nameEn}`}
                          >
                            <input
                              type="checkbox"
                              checked={selectedCategories.includes(child.nameEn)}
                              onChange={() => toggleChildCategory(child.nameEn)}
                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3 w-3 flex-shrink-0"
                            />
                            <span className="text-xs flex-shrink-0" role="img" aria-hidden="true">{child.icon}</span>
                            <span className="text-[11px] text-slate-600 dark:text-slate-400 truncate">{getName(child)}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>
      )}
    </div>
  );

  // ─── Mobile Drill-Down Category Panel ──────────────────────
  const MobileCategoryDrillDown = () => {
    if (mobileDrillParent) {
      const parent = categoryTree.find(p => p.id === mobileDrillParent);
      if (!parent) return null;
      return (
        <div className="px-3 pb-2" data-testid="mobile-category-drilldown">
          <button
            onClick={() => setMobileDrillParent(null)}
            className="flex items-center gap-1 text-xs text-blue-600 font-medium mb-2 hover:text-blue-700 transition-colors"
            data-testid="mobile-cat-back"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> {t('filters.allCategories', 'All Categories')}
          </button>
          <div className="flex items-center gap-2 px-2 py-2 mb-2 bg-slate-50 dark:bg-slate-800 rounded-lg">
            <span className="text-base">{parent.icon}</span>
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{getName(parent)}</span>
          </div>
          <div className="space-y-0.5">
            {parent.children.map(child => (
              <label
                key={child.id}
                className="flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                data-testid={`mobile-cat-child-${child.nameEn}`}
              >
                <input
                  type="checkbox"
                  checked={selectedCategories.includes(child.nameEn)}
                  onChange={() => toggleChildCategory(child.nameEn)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4 flex-shrink-0"
                />
                <span className="text-sm flex-shrink-0">{child.icon}</span>
                <span className="text-sm text-slate-600 dark:text-slate-400">{getName(child)}</span>
                {selectedCategories.includes(child.nameEn) && (
                  <Check className="w-3.5 h-3.5 text-blue-600 ml-auto" />
                )}
              </label>
            ))}
          </div>
        </div>
      );
    }

    // Parent list
    return (
      <div className="px-3 pb-2 space-y-0.5" data-testid="mobile-category-parents">
        {catTreeLoading ? (
          <div className="flex justify-center py-4"><Loader2 className="w-4 h-4 animate-spin text-slate-400" /></div>
        ) : categoryTree.length === 0 ? (
          <p className="text-sm text-slate-400 px-2 py-2">{t('filters.noCategories', 'No categories yet')}</p>
        ) : (
          categoryTree.map(parent => {
            const hasChildren = parent.children.length > 0;
            const childrenSelected = parent.children.filter(c => selectedCategories.includes(c.nameEn)).length;
            return (
              <div key={parent.id}>
                {hasChildren ? (
                  <button
                    onClick={() => setMobileDrillParent(parent.id)}
                    className="w-full flex items-center gap-2.5 px-3 py-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors text-left"
                    data-testid={`mobile-cat-parent-${parent.id}`}
                  >
                    <span className="text-lg flex-shrink-0">{parent.icon}</span>
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-200 flex-1">{getName(parent)}</span>
                    {childrenSelected > 0 && (
                      <Badge className="h-5 min-w-[20px] px-1.5 text-[10px] bg-blue-600 text-white">{childrenSelected}</Badge>
                    )}
                    <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
                  </button>
                ) : (
                  <label className="flex items-center gap-2.5 px-3 py-3 rounded-lg cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                    <input
                      type="checkbox"
                      checked={selectedCategories.includes(parent.nameEn)}
                      onChange={() => toggleChildCategory(parent.nameEn)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4 flex-shrink-0"
                    />
                    <span className="text-lg flex-shrink-0">{parent.icon}</span>
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{getName(parent)}</span>
                  </label>
                )}
              </div>
            );
          })
        )}
      </div>
    );
  };

  // ─── Shared sections (Auctioneers, Locations) ──────────────
  const AuctioneersSection = () => (
    filterData?.auctioneers?.length > 0 && (
      <div className="border-b border-slate-100 dark:border-slate-800">
        <button onClick={() => toggleSection('auctioneers')}
          className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          data-testid="sidebar-section-auctioneers">
          <span className="flex items-center gap-1.5"><Building2 className="w-3.5 h-3.5" /> {t('filters.auctioneer', 'Auctioneer')}</span>
          {expandedSections.auctioneers ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
        {expandedSections.auctioneers && (
          <div className="px-3 pb-2 space-y-0.5">
            {filterData.auctioneers.map(a => (
              <label key={a.id} className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-xs transition-colors" data-testid={`filter-auctioneer-${a.id}`}>
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
    )
  );

  const LocationsSection = () => (
    <div>
      <button onClick={() => toggleSection('locations')}
        className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
        data-testid="sidebar-section-locations">
        <span className="flex items-center gap-1.5"><MapPin className="w-3.5 h-3.5" /> {t('filters.location', 'Location')}</span>
        {expandedSections.locations ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
      </button>
      {expandedSections.locations && (
        <div className="px-3 pb-2 space-y-1 max-h-[300px] overflow-y-auto">
          {(filterData?.locations || []).map(loc => (
            <div key={loc.region}>
              <label className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-xs font-medium transition-colors" data-testid={`filter-region-${loc.region}`}>
                <input type="checkbox" checked={selectedRegions.includes(loc.region)}
                  onChange={() => toggleFilter(selectedRegions, setSelectedRegions, loc.region)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                <span className="flex-1 text-slate-700 dark:text-slate-300">{loc.region}</span>
                <span className="text-[10px] text-slate-400 tabular-nums">({loc.count})</span>
              </label>
              {selectedRegions.includes(loc.region) && loc.cities?.length > 0 && (
                <div className="ml-5 space-y-0.5">
                  {loc.cities.map(city => (
                    <label key={city.name} className="flex items-center gap-2 px-2 py-1 rounded cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 text-[11px] transition-colors" data-testid={`filter-city-${city.name}`}>
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
            <p className="text-[11px] text-slate-400 px-2 py-1">{t('filters.noLocations', 'No locations yet')}</p>
          )}
        </div>
      )}
    </div>
  );

  // ─── Desktop Sidebar Content ──────────────────────────────
  const DesktopSidebarContent = () => (
    <div className="space-y-0" data-testid="marketplace-sidebar">
      {/* Search */}
      <div className="px-3 py-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <Input
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            placeholder={t('filters.searchItems', 'Search items...')}
            className="pl-8 h-8 text-xs bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700"
            data-testid="sidebar-search"
          />
        </div>
      </div>

      {/* Active Filters */}
      {activeCount > 0 && (
        <div className="px-3 pb-2">
          <button onClick={clearAll} className="text-[11px] text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 transition-colors" data-testid="sidebar-clear-all">
            <X className="w-3 h-3" /> {t('filters.clearAll', 'Clear all filters')} ({activeCount})
          </button>
        </div>
      )}

      {loading && !filterData ? (
        <div className="flex justify-center py-6"><Loader2 className="w-4 h-4 animate-spin text-slate-400" /></div>
      ) : (
        <>
          <AuctioneersSection />
          <DesktopCategoryTree />
          <LocationsSection />
        </>
      )}
    </div>
  );

  // ─── Mobile Sidebar Content (Drill-down categories) ───────
  const MobileSidebarContent = () => (
    <div className="space-y-0" data-testid="marketplace-sidebar-mobile">
      {/* Search */}
      <div className="px-3 py-2.5">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <Input
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            placeholder={t('filters.searchItems', 'Search items...')}
            className="pl-9 h-10 text-sm bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700"
            data-testid="sidebar-search-mobile"
          />
        </div>
      </div>

      {/* Active Filters */}
      {activeCount > 0 && (
        <div className="px-3 pb-2">
          <button onClick={clearAll} className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1" data-testid="sidebar-clear-all-mobile">
            <X className="w-3.5 h-3.5" /> {t('filters.clearAll', 'Clear all filters')} ({activeCount})
          </button>
        </div>
      )}

      {/* Category section header */}
      <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
          <Tag className="w-3.5 h-3.5" /> {t('filters.category', 'Category')}
        </span>
      </div>
      <MobileCategoryDrillDown />

      {/* Auctioneers & Locations below categories on mobile */}
      <AuctioneersSection />
      <LocationsSection />
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <div className={`hidden lg:block w-[240px] flex-shrink-0 ${className}`}>
        <div className="sticky top-20 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm" data-testid="sidebar-desktop">
          <div className="px-3 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5" /> {t('filters.title', 'Filters')}
            </span>
            {filterData && (
              <span className="text-[10px] text-slate-400">{filterData.total_active_items} {t('filters.items', 'items')}</span>
            )}
          </div>
          <DesktopSidebarContent />
        </div>
      </div>

      {/* Mobile Filter Button + Sheet */}
      <div className="lg:hidden">
        <Sheet onOpenChange={() => setMobileDrillParent(null)}>
          <SheetTrigger asChild>
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" data-testid="sidebar-mobile-trigger">
              <Filter className="w-3.5 h-3.5" />
              {t('filters.title', 'Filters')}
              {activeCount > 0 && (
                <Badge className="ml-1 h-4 w-4 p-0 flex items-center justify-center text-[10px] bg-blue-600 text-white">{activeCount}</Badge>
              )}
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[300px] p-0 pt-10">
            <div className="px-3 py-2.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
              <span className="text-sm font-semibold flex items-center gap-1.5">
                <Filter className="w-4 h-4" /> {t('filters.title', 'Filters')}
              </span>
              {filterData && (
                <span className="text-[10px] text-slate-400">{filterData.total_active_items} {t('filters.items', 'items')}</span>
              )}
            </div>
            <ScrollArea className="h-[calc(100vh-100px)]">
              <MobileSidebarContent />
            </ScrollArea>
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
};

export default MarketplaceSidebar;
