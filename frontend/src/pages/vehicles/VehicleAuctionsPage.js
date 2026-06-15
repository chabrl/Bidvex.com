/**
 * iter202 Phase B — Vehicle Auctions Buyer Experience (with Sidebar Filter Drawer)
 * =================================================================================
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────┐
 *   │ HERO          (VehicleHero)                           │
 *   │ SELLER CTA    (emerald strip)                         │
 *   │ CATEGORY BAR  (VehicleCategoryPills)                  │
 *   │ ┌─────────────┬──────────────────────────────────┐    │
 *   │ │ SIDEBAR 280 │ TOOLBAR + GRID + EMPTY/PAGER     │    │
 *   │ │ desktop only│                                  │    │
 *   │ └─────────────┴──────────────────────────────────┘    │
 *   │ LEGAL FOOTER  (VehicleLegalFooter — Phase 2 reuse)    │
 *   │ + Floating "Filters" button on mobile/tablet (B1)     │
 *   └──────────────────────────────────────────────────────┘
 *
 * URL-sync: every active filter is reflected in `?key=value` query params,
 * deep-linkable, and browser back/forward restores state via React Router.
 *
 * Debounce per spec:
 *   • Sliders / numerics  : 300ms
 *   • Text inputs         : 500ms (handled by VehicleSidebar)
 *   • Checkboxes          : immediate
 *
 * Constraints honoured (Phase A + B):
 *   #2 Feature flag — gated upstream by VehicleAuctionsRoute
 *   #3 Reuse        — VehicleHero, VehicleCategoryPills, VehicleListingCard,
 *                     VehicleEmptyState, VehicleLegalFooter, VehicleSidebar
 *   #4 Single timer — useVehicleCountdown drives all card countdowns
 *   #8 Image dims   — handled inside VehicleListingCard
 *   #9 Bilingual    — every string via t()
 *  #10 Empty states — VehicleEmptyState handles zero/filtered/error
 */
import API_BASE from '../../config';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import {
  Grid3x3, List as ListIcon, ArrowDownUp, ChevronDown, Filter,
  Building2, PlusCircle, User, DollarSign,
} from 'lucide-react';
import VehicleHero from '../../components/vehicles/VehicleHero';
import VehicleCategoryPills from '../../components/vehicles/VehicleCategoryPills';
import VehicleListingCard from '../../components/vehicles/VehicleListingCard';
import VehicleEmptyState from '../../components/vehicles/VehicleEmptyState';
import VehicleLegalFooter from '../../components/vehicles/VehicleLegalFooter';
import VehicleSidebar from '../../components/vehicles/VehicleSidebar';
import useVehicleCountdown from '../../hooks/useVehicleCountdown';
// iter294 P1 — Live multi-lot feed widget.
import LiveMultiLotFeedWidget from '../../components/LiveMultiLotFeedWidget';

const API = API_BASE;

const SORT_OPTIONS = [
  { value: 'end_time-asc',     labelKey: 'vehiclePage.sort.endingSoon',  defaultLabel: 'Ending soon' },
  { value: 'end_time-desc',    labelKey: 'vehiclePage.sort.endingLater', defaultLabel: 'Ending later' },
  { value: 'created_at-desc',  labelKey: 'vehiclePage.sort.newest',      defaultLabel: 'Newest listings' },
  { value: 'current_bid-desc', labelKey: 'vehiclePage.sort.priceHigh',   defaultLabel: 'Price: high to low' },
  { value: 'current_bid-asc',  labelKey: 'vehiclePage.sort.priceLow',    defaultLabel: 'Price: low to high' },
  { value: 'mileage-asc',      labelKey: 'vehiclePage.sort.mileageLow',  defaultLabel: 'Lowest mileage' },
];

// Sidebar filter keys that mirror /api/vehicles query params
const SIDEBAR_FILTER_KEYS = [
  'province', 'auction_status', 'price_min', 'price_max', 'year_min', 'year_max',
  'make', 'transmission', 'fuel_type', 'title_status', 'max_mileage',
  'seller_type', 'no_buyer_premium',
];

const buildInitialFilters = (sp) => {
  const f = {};
  for (const k of SIDEBAR_FILTER_KEYS) {
    const v = sp.get(k);
    if (v !== null && v !== '') f[k] = v;
  }
  return f;
};

const VehicleAuctionsPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  // Categories (loaded once)
  const [categories, setCategories] = useState([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);

  // Listings state
  const [vehicles, setVehicles] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(() => parseInt(searchParams.get('page') || '1', 10));

  // Top-level filters
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryId, setCategoryId] = useState(searchParams.get('category_id') || null);
  const [subcategoryId, setSubcategoryId] = useState(searchParams.get('subcategory_id') || null);
  const [sort, setSort] = useState(searchParams.get('sort') || 'end_time-asc');
  const [viewMode, setViewMode] = useState('grid');

  // Sidebar filters (initial from URL)
  const [sidebarFilters, setSidebarFilters] = useState(() => buildInitialFilters(searchParams));

  // Mobile drawer open state
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Shared countdown — single global timer (sprint constraint #4)
  const { format: formatCountdown } = useVehicleCountdown();

  // Load categories once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/vehicles/categories`);
        if (!cancelled) setCategories(res.data?.items || []);
      } catch (catErr) {
        // non-fatal — degraded UI: filter dropdown will show "All categories"
        console.debug('[VehicleAuctionsPage] categories load failed:', catErr);
      } finally {
        if (!cancelled) setCategoriesLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // URL ←→ state sync — reflect every active filter in query params
  useEffect(() => {
    const next = new URLSearchParams();
    if (categoryId) next.set('category_id', categoryId);
    if (subcategoryId) next.set('subcategory_id', subcategoryId);
    if (sort && sort !== 'end_time-asc') next.set('sort', sort);
    if (page && page !== 1) next.set('page', String(page));
    Object.entries(sidebarFilters).forEach(([k, v]) => {
      if (v !== null && v !== '' && v !== false) next.set(k, String(v));
    });
    setSearchParams(next, { replace: true });
  }, [categoryId, subcategoryId, sort, page, sidebarFilters, setSearchParams]);

  // Browser back/forward — react to URL changes
  useEffect(() => {
    setCategoryId(searchParams.get('category_id') || null);
    setSubcategoryId(searchParams.get('subcategory_id') || null);
    setSort(searchParams.get('sort') || 'end_time-asc');
    setPage(parseInt(searchParams.get('page') || '1', 10));
    setSidebarFilters(buildInitialFilters(searchParams));
  }, [searchParams]);

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
      if (categoryId) params.set('category_id', categoryId);
      if (subcategoryId) params.set('subcategory_id', subcategoryId);
      // Sidebar filters
      Object.entries(sidebarFilters).forEach(([k, v]) => {
        if (v !== null && v !== '' && v !== false && k !== 'no_buyer_premium') {
          params.set(k, String(v));
        }
      });
      const res = await axios.get(`${API}/vehicles?${params.toString()}`);
      let list = res.data?.vehicles || [];
      // Client-side filter — buyer-premium toggle
      if (sidebarFilters.no_buyer_premium) {
        list = list.filter((v) => !v.buyer_premium && !v.has_buyer_premium);
      }
      setVehicles(list);
      setTotal(res.data?.total || 0);
    } catch (e) {
      setError(true);
      setVehicles([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, sort, categoryId, subcategoryId, sidebarFilters]);

  useEffect(() => { fetchVehicles(); }, [fetchVehicles]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 12)), [total]);

  const handleSearch = (q) => {
    setSidebarFilters((p) => ({ ...p, make: (q || '').trim() || null }));
    setPage(1);
  };

  const handleCategoryChange = (cId, scId) => {
    setCategoryId(cId || null);
    setSubcategoryId(scId || null);
    setPage(1);
  };

  const handleFilterChange = (key, value) => {
    setSidebarFilters((p) => {
      const next = { ...p };
      if (value === null || value === '' || value === false) delete next[key];
      else next[key] = value;
      return next;
    });
    setPage(1);
  };

  const clearAllFilters = () => {
    setSidebarFilters({});
    setSearchQuery('');
    setCategoryId(null);
    setSubcategoryId(null);
    setSort('end_time-asc');
    setPage(1);
    setDrawerOpen(false);
  };

  const hasActiveFilters = !!(
    categoryId || subcategoryId ||
    Object.keys(sidebarFilters).length > 0
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 overflow-x-hidden" data-testid="vehicle-auctions-page">
      {/* HERO (navy, full bleed) — iter303 Directive 3: hero sits flush
          against the CTA strip with zero whitespace below. */}
      <VehicleHero
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onSearch={handleSearch}
      />

      {/* SELLER CTA STRIP — iter303 Directive 3: tightened responsive
          layout. Headline + buttons stack on mobile; buttons render as
          a 2×2 grid with "Become a broker →" full width at the bottom. */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 dark:from-emerald-700 dark:to-teal-700 py-4 sm:py-5" data-testid="seller-cta-section">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
            <div className="flex items-center gap-3 text-white">
              <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center flex-shrink-0">
                <DollarSign className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-bold">{t('vehiclePage.sellerCtaTitle', 'Want to sell your vehicle?')}</h3>
                <p className="text-emerald-100 text-xs sm:text-sm">{t('vehiclePage.sellerCtaBody', 'Join our verified seller network — Private, Dealer, or Auctioneer.')}</p>
              </div>
            </div>
            {/* Desktop: single row, wraps if needed. Mobile: 2×2 grid +
                "Become a broker →" full-width below. */}
            <div className="grid grid-cols-2 lg:flex lg:flex-wrap gap-2 w-full lg:w-auto" data-testid="seller-cta-buttons">
              <button onClick={() => navigate('/vehicle-auctions/seller/register')} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white text-emerald-700 hover:bg-emerald-50 font-semibold text-xs sm:text-sm px-3 py-2 min-h-[40px]" data-testid="btn-seller-register">
                <User className="h-4 w-4" />{t('vehiclePage.becomeSeller', 'Become a seller')}
              </button>
              <button onClick={() => navigate('/vehicle-auctions/create')} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-transparent border border-white text-white hover:bg-white/15 font-semibold text-xs sm:text-sm px-3 py-2 min-h-[40px]" data-testid="btn-create-listing">
                <PlusCircle className="h-4 w-4" />{t('vehiclePage.listVehicle', 'List a vehicle')}
              </button>
              <button onClick={() => navigate('/vehicle-auctions/my-listings')} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-transparent border border-white text-white hover:bg-white/15 font-semibold text-xs sm:text-sm px-3 py-2 min-h-[40px]" data-testid="btn-my-listings">
                <Building2 className="h-4 w-4" />{t('vehiclePage.myListings', 'My listings')}
              </button>
              <button onClick={() => navigate(i18n?.language?.startsWith('fr') ? '/courtiers' : '/brokers')} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-amber-400 text-emerald-900 hover:bg-amber-300 font-semibold text-xs sm:text-sm px-3 py-2 min-h-[40px]" data-testid="btn-find-broker">
                🤝 {i18n?.language?.startsWith('fr') ? 'Trouver un courtier' : 'Find a Broker'}
              </button>
              <button onClick={() => navigate(i18n?.language?.startsWith('fr') ? '/devenir-courtier' : '/become-a-broker')} className="col-span-2 lg:col-span-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-transparent border border-white text-white hover:bg-white/15 font-semibold text-xs sm:text-sm px-3 py-2 min-h-[40px]" data-testid="btn-become-broker">
                {i18n?.language?.startsWith('fr') ? 'Devenir courtier →' : 'Become a broker →'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* iter303 Directive 3 — soft diagonal SVG divider transitioning
          the green CTA banner into the page background. */}
      <div className="relative w-full overflow-hidden -mb-px" aria-hidden data-testid="cta-divider">
        <svg viewBox="0 0 1440 36" preserveAspectRatio="none" className="w-full h-6 sm:h-9 block" xmlns="http://www.w3.org/2000/svg">
          <path d="M0,0 L1440,0 L1440,12 C1080,36 360,0 0,28 Z" className="fill-emerald-600 dark:fill-emerald-700" />
        </svg>
      </div>

      {/* iter294 P1 — Live multi-lot feed widget. Renders nothing
          when there are zero live AND zero upcoming events. */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-2">
        <LiveMultiLotFeedWidget />
      </div>

      {/* CATEGORY PILLS */}
      <VehicleCategoryPills
        categories={categories}
        loading={categoriesLoading}
        selectedCategoryId={categoryId}
        selectedSubcategoryId={subcategoryId}
        onChange={handleCategoryChange}
      />

      {/* MAIN — sidebar + grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <div className="flex gap-6">
          {/* Sidebar (desktop sticky 280px + mobile drawer) */}
          <VehicleSidebar
            isOpen={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            filters={sidebarFilters}
            onChange={handleFilterChange}
            onChangeDebounced={handleFilterChange}
            onApply={() => setDrawerOpen(false)}
            onClear={clearAllFilters}
            categoryId={categoryId}
            resultCount={total}
          />

          {/* Right side — toolbar + grid */}
          <div className="flex-1 min-w-0">
            {/* Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 mb-5" data-testid="vehicle-toolbar">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {loading
                    ? t('vehiclePage.loadingResults', 'Loading auctions…')
                    : t('vehiclePage.resultsCount', '{{count}} auctions', { count: total })}
                </span>
                {hasActiveFilters && (
                  <button type="button" onClick={clearAllFilters} className="text-xs font-semibold text-cyan-600 hover:text-cyan-700 hover:underline" data-testid="vehicle-toolbar-clear-filters">
                    {t('vehiclePage.clearAll', 'Clear all')}
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2">
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
                      <option key={o.value} value={o.value}>{t(o.labelKey, o.defaultLabel)}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
                </label>
                <div className="hidden sm:inline-flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden" data-testid="vehicle-toolbar-view-toggle">
                  <button type="button" onClick={() => setViewMode('grid')} className={`h-10 px-3 inline-flex items-center text-sm font-semibold ${viewMode === 'grid' ? 'bg-[#0B2545] text-white' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300'}`} aria-pressed={viewMode === 'grid'} data-testid="vehicle-view-grid">
                    <Grid3x3 className="h-4 w-4" />
                  </button>
                  <button type="button" onClick={() => setViewMode('list')} className={`h-10 px-3 inline-flex items-center text-sm font-semibold ${viewMode === 'list' ? 'bg-[#0B2545] text-white' : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300'}`} aria-pressed={viewMode === 'list'} data-testid="vehicle-view-list">
                    <ListIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Loading skeletons */}
            {loading && (
              <div className={`grid gap-4 sm:gap-5 ${viewMode === 'grid' ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4' : 'grid-cols-1'}`} data-testid="vehicle-grid-loading">
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

            {!loading && error && (
              <VehicleEmptyState variant="error" onRetry={fetchVehicles} />
            )}
            {!loading && !error && vehicles.length === 0 && hasActiveFilters && (
              <VehicleEmptyState variant="filtered-no-results" onClearFilters={clearAllFilters} />
            )}
            {!loading && !error && vehicles.length === 0 && !hasActiveFilters && (
              <VehicleEmptyState variant="zero-listings" />
            )}

            {!loading && !error && vehicles.length > 0 && (
              <>
                <div
                  className={`grid gap-4 sm:gap-5 ${viewMode === 'grid' ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4' : 'grid-cols-1'}`}
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

                {totalPages > 1 && (
                  <div className="mt-8 flex items-center justify-center gap-2" data-testid="vehicle-pagination">
                    <button type="button" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800" data-testid="vehicle-pagination-prev">
                      {t('vehiclePage.prev', 'Previous')}
                    </button>
                    <span className="text-sm text-slate-600 dark:text-slate-300 px-2" data-testid="vehicle-pagination-status">
                      {t('vehiclePage.pageOf', 'Page {{page}} of {{pages}}', { page, pages: totalPages })}
                    </span>
                    <button type="button" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800" data-testid="vehicle-pagination-next">
                      {t('vehiclePage.next', 'Next')}
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Floating "Filters" FAB — mobile/tablet only (B1) */}
      <button
        type="button"
        onClick={() => setDrawerOpen(true)}
        className="lg:hidden fixed bottom-20 right-4 z-[60] inline-flex items-center gap-2 rounded-full bg-[#0B2545] hover:bg-[#0E2B52] text-white font-semibold text-sm px-4 py-3 shadow-lg shadow-black/20"
        data-testid="vehicle-filters-fab"
      >
        <Filter className="h-4 w-4" />
        {t('vehicleSidebar.title', 'Filters')}
        {Object.keys(sidebarFilters).length > 0 && (
          <span className="inline-flex items-center justify-center min-w-[20px] h-5 rounded-full bg-cyan-500 text-white text-[10px] font-bold px-1.5">
            {Object.keys(sidebarFilters).length}
          </span>
        )}
      </button>

      {/* Bilingual legal footer (reused from Phase 2) */}
      <VehicleLegalFooter />
    </div>
  );
};

export default VehicleAuctionsPage;
