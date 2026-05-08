/**
 * iter202 Phase A — Vehicle Auctions Buyer Experience
 * ====================================================
 * Replaces the old VehicleAuctionsPage with the new buyer-focused layout:
 *
 *   ┌──────────────────────────────────────────────────────┐
 *   │ HERO          — VehicleHero (dark navy, stats strip) │
 *   │ CATEGORY BAR  — VehicleCategoryPills (15 cats)       │
 *   │ TOOLBAR       — sort dropdown, view toggle, count    │
 *   │ GRID          — 3-col VehicleListingCard rich cards  │
 *   │ EMPTY STATES  — zero / filtered / error variants     │
 *   │ LEGAL FOOTER  — bilingual disclaimer (reused Phase 2)│
 *   └──────────────────────────────────────────────────────┘
 *
 * Sprint constraints honoured:
 *   #2 Feature flag — gated upstream by VehicleAuctionsRoute
 *   #3 Reuse        — VehicleLegalFooter, /api/vehicles/categories
 *   #4 Single timer — useVehicleCountdown drives all card countdowns
 *   #6 Quick bid    — bid increments deferred to Phase B (detail page)
 *   #8 Image dims   — explicit aspect-[16/10] + width/height attrs on <img>
 *   #9 Bilingual    — every string via useTranslation()
 *  #10 Empty states — VehicleEmptyState handles zero / filtered / error
 *
 * Sidebar drawer (Phase B) deliberately not wired here — only the category
 * pills + sort dropdown ship in Phase A. The sidebar arrives in Phase B.
 */
import API_BASE from '../../config';
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import {
  Loader2, Grid3x3, List as ListIcon, ArrowDownUp, ChevronDown,
  Building2, PlusCircle, User, DollarSign, Car,
} from 'lucide-react';
import VehicleHero from '../../components/vehicles/VehicleHero';
import VehicleCategoryPills from '../../components/vehicles/VehicleCategoryPills';
import VehicleListingCard from '../../components/vehicles/VehicleListingCard';
import VehicleEmptyState from '../../components/vehicles/VehicleEmptyState';
import VehicleLegalFooter from '../../components/vehicles/VehicleLegalFooter';
import useVehicleCountdown from '../../hooks/useVehicleCountdown';

const API = API_BASE;

const SORT_OPTIONS = [
  { value: 'end_time-asc',     labelKey: 'vehiclePage.sort.endingSoon',  defaultLabel: 'Ending soon' },
  { value: 'end_time-desc',    labelKey: 'vehiclePage.sort.endingLater', defaultLabel: 'Ending later' },
  { value: 'created_at-desc',  labelKey: 'vehiclePage.sort.newest',      defaultLabel: 'Newest listings' },
  { value: 'current_bid-desc', labelKey: 'vehiclePage.sort.priceHigh',   defaultLabel: 'Price: high to low' },
  { value: 'current_bid-asc',  labelKey: 'vehiclePage.sort.priceLow',    defaultLabel: 'Price: low to high' },
  { value: 'mileage-asc',      labelKey: 'vehiclePage.sort.mileageLow',  defaultLabel: 'Lowest mileage' },
];

const VehicleAuctionsPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  // Categories (loaded once)
  const [categories, setCategories] = useState([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);

  // Listings state
  const [vehicles, setVehicles] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(1);

  // Filters
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || searchParams.get('make') || '');
  const [activeMakeFilter, setActiveMakeFilter] = useState(searchParams.get('make') || '');
  const [categoryId, setCategoryId] = useState(searchParams.get('category_id') || null);
  const [subcategoryId, setSubcategoryId] = useState(searchParams.get('subcategory_id') || null);
  const [sort, setSort] = useState(searchParams.get('sort') || 'end_time-asc');
  const [viewMode, setViewMode] = useState('grid');

  // Shared countdown — single timer per page (sprint constraint #4)
  const { format: formatCountdown } = useVehicleCountdown();

  // Load categories once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/vehicles/categories`);
        if (!cancelled) setCategories(res.data?.items || []);
      } catch (e) {
        // Non-fatal — pills will render empty/skeleton
      } finally {
        if (!cancelled) setCategoriesLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Sync filters to URL
  useEffect(() => {
    const next = new URLSearchParams();
    if (activeMakeFilter) next.set('make', activeMakeFilter);
    if (categoryId) next.set('category_id', categoryId);
    if (subcategoryId) next.set('subcategory_id', subcategoryId);
    if (sort && sort !== 'end_time-asc') next.set('sort', sort);
    setSearchParams(next, { replace: true });
  }, [activeMakeFilter, categoryId, subcategoryId, sort, setSearchParams]);

  const fetchVehicles = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '12');
      params.set('promoted_first', 'true');
      const [sortBy, sortOrder] = sort.split('-');
      params.set('sort_by', sortBy);
      params.set('sort_order', sortOrder);
      if (activeMakeFilter) params.set('make', activeMakeFilter);
      if (categoryId) params.set('category_id', categoryId);
      if (subcategoryId) params.set('subcategory_id', subcategoryId);
      const res = await axios.get(`${API}/vehicles?${params.toString()}`);
      setVehicles(res.data?.vehicles || []);
      setTotal(res.data?.total || 0);
    } catch (e) {
      setError(true);
      setVehicles([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, sort, activeMakeFilter, categoryId, subcategoryId]);

  useEffect(() => { fetchVehicles(); }, [fetchVehicles]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 12)), [total]);

  const handleSearch = (q) => {
    setActiveMakeFilter((q || '').trim());
    setPage(1);
  };

  const handleCategoryChange = (cId, scId /* , catObj */) => {
    setCategoryId(cId || null);
    setSubcategoryId(scId || null);
    setPage(1);
  };

  const clearAllFilters = () => {
    setActiveMakeFilter('');
    setSearchQuery('');
    setCategoryId(null);
    setSubcategoryId(null);
    setSort('end_time-asc');
    setPage(1);
  };

  const hasFilters = !!(activeMakeFilter || categoryId || subcategoryId);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="vehicle-auctions-page">
      {/* HERO */}
      <VehicleHero
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onSearch={handleSearch}
      />

      {/* SELLER CTA STRIP */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 dark:from-emerald-700 dark:to-teal-700 py-4" data-testid="seller-cta-section">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3 text-white">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <DollarSign className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-bold">
                  {t('vehiclePage.sellerCtaTitle', 'Want to sell your vehicle?')}
                </h3>
                <p className="text-emerald-100 text-xs sm:text-sm">
                  {t('vehiclePage.sellerCtaBody', 'Join our verified seller network — Private, Dealer, or Auctioneer.')}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 w-full sm:w-auto justify-center">
              <button
                onClick={() => navigate('/vehicle-auctions/seller/register')}
                className="inline-flex items-center gap-1.5 rounded-lg bg-white text-emerald-700 hover:bg-emerald-50 font-semibold text-xs sm:text-sm px-3 py-2"
                data-testid="btn-seller-register"
              >
                <User className="h-4 w-4" />
                {t('vehiclePage.becomeSeller', 'Become a seller')}
              </button>
              <button
                onClick={() => navigate('/vehicle-auctions/create')}
                className="inline-flex items-center gap-1.5 rounded-lg bg-transparent border border-white text-white hover:bg-white/15 font-semibold text-xs sm:text-sm px-3 py-2"
                data-testid="btn-create-listing"
              >
                <PlusCircle className="h-4 w-4" />
                {t('vehiclePage.listVehicle', 'List a vehicle')}
              </button>
              <button
                onClick={() => navigate('/vehicle-auctions/my-listings')}
                className="inline-flex items-center gap-1.5 rounded-lg bg-transparent border border-white text-white hover:bg-white/15 font-semibold text-xs sm:text-sm px-3 py-2"
                data-testid="btn-my-listings"
              >
                <Building2 className="h-4 w-4" />
                {t('vehiclePage.myListings', 'My listings')}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* CATEGORY PILLS */}
      <VehicleCategoryPills
        categories={categories}
        loading={categoriesLoading}
        selectedCategoryId={categoryId}
        selectedSubcategoryId={subcategoryId}
        onChange={handleCategoryChange}
      />

      {/* TOOLBAR + GRID */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-5" data-testid="vehicle-toolbar">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              {loading
                ? t('vehiclePage.loadingResults', 'Loading auctions…')
                : t('vehiclePage.resultsCount', '{{count}} auctions', { count: total })}
            </span>
            {hasFilters && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="text-xs font-semibold text-cyan-600 hover:text-cyan-700 hover:underline"
                data-testid="vehicle-toolbar-clear-filters"
              >
                {t('vehiclePage.clearAll', 'Clear all')}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* Sort */}
            <label className="relative text-sm">
              <span className="sr-only">{t('vehiclePage.sortLabel', 'Sort by')}</span>
              <ArrowDownUp className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
              <select
                value={sort}
                onChange={(e) => { setSort(e.target.value); setPage(1); }}
                className="appearance-none pl-9 pr-9 h-10 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-100 font-semibold text-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500"
                data-testid="vehicle-toolbar-sort"
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {t(o.labelKey, o.defaultLabel)}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            </label>
            {/* View toggle */}
            <div className="hidden sm:inline-flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden" data-testid="vehicle-toolbar-view-toggle">
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`h-10 px-3 inline-flex items-center text-sm font-semibold ${viewMode === 'grid' ? 'bg-[#0B2545] text-white' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300'}`}
                aria-pressed={viewMode === 'grid'}
                data-testid="vehicle-view-grid"
              >
                <Grid3x3 className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('list')}
                className={`h-10 px-3 inline-flex items-center text-sm font-semibold ${viewMode === 'list' ? 'bg-[#0B2545] text-white' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300'}`}
                aria-pressed={viewMode === 'list'}
                data-testid="vehicle-view-list"
              >
                <ListIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Loading skeletons */}
        {loading && (
          <div className={`grid gap-5 ${viewMode === 'grid' ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3' : 'grid-cols-1'}`} data-testid="vehicle-grid-loading">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
                <div className="aspect-[16/10] bg-slate-100 dark:bg-slate-800 animate-pulse" />
                <div className="p-4 space-y-3">
                  <div className="h-5 w-3/4 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                  <div className="h-3 w-1/2 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                  <div className="grid grid-cols-2 gap-2">
                    <div className="h-3 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                    <div className="h-3 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                  </div>
                  <div className="flex justify-between items-end pt-2">
                    <div className="h-7 w-24 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                    <div className="h-9 w-20 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <VehicleEmptyState variant="error" onRetry={fetchVehicles} />
        )}

        {/* Filtered no results */}
        {!loading && !error && vehicles.length === 0 && hasFilters && (
          <VehicleEmptyState variant="filtered-no-results" onClearFilters={clearAllFilters} />
        )}

        {/* Zero listings (no filters, real empty state) */}
        {!loading && !error && vehicles.length === 0 && !hasFilters && (
          <VehicleEmptyState variant="zero-listings" />
        )}

        {/* Results grid */}
        {!loading && !error && vehicles.length > 0 && (
          <>
            <div
              className={`grid gap-5 ${viewMode === 'grid' ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3' : 'grid-cols-1'}`}
              data-testid="vehicle-grid"
            >
              {vehicles.map((v) => {
                const cd = formatCountdown(v.end_time, { endedLabel: t('vehicleCard.ended', 'Ended') });
                return (
                  <VehicleListingCard
                    key={v.id}
                    vehicle={v}
                    countdown={cd}
                    onClick={() => navigate(`/vehicle-auctions/${v.id}`)}
                    onQuickView={(vh) => navigate(`/vehicle-auctions/${vh.id}`)}
                  />
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-8 flex items-center justify-center gap-2" data-testid="vehicle-pagination">
                <button
                  type="button"
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800"
                  data-testid="vehicle-pagination-prev"
                >
                  {t('vehiclePage.prev', 'Previous')}
                </button>
                <span className="text-sm text-slate-600 dark:text-slate-300 px-2" data-testid="vehicle-pagination-status">
                  {t('vehiclePage.pageOf', 'Page {{page}} of {{pages}}', { page, pages: totalPages })}
                </span>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800"
                  data-testid="vehicle-pagination-next"
                >
                  {t('vehiclePage.next', 'Next')}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Bilingual legal footer (reused from Phase 2) */}
      <VehicleLegalFooter />
    </div>
  );
};

export default VehicleAuctionsPage;
