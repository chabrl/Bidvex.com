import API_BASE from '../config';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Badge } from './ui/badge';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Separator } from './ui/separator';
import BidConfirmationDialog from './BidConfirmationDialog';
import SafeImage from './SafeImage';
import FilterBar from './FilterBar/FilterBar';
import { 
  Clock, 
  Gavel, 
  Package, 
  TrendingUp, 
  Star,
  Sparkles,
  MapPin,
  User,
  Search,
  Filter,
  ShieldCheck,
  Zap,
  ChevronRight,
  Eye,
  DollarSign,
  Timer,
  ExternalLink,
  Receipt,
  Scale,
  X,
  Flame
} from 'lucide-react';
import { toast } from 'sonner';
import { formatCurrency } from '../utils/currencyFormatter';
// iter233 — Display-only "Lot price × Quantity" multiplier helper.
import { computeDisplayPrice } from '../utils/priceUtils';
import { SellerAccountBadge } from './PrivateSaleBadge';
import { getLocalized } from '../utils/localization';
// iter238 Mission 1.3 — Dismissible location banner shown for signed-in users without a city on file.
import LocationBanner from './LocationBanner';
// iter239 Mission 5 — Featured Listings carousel banner.
import FeaturedListingsBanner from './FeaturedListingsBanner';
// iter236 Mission 2 — Map & radius search panel (lazy-loaded so Leaflet
// CSS/JS doesn't enter the marketplace's critical render path).
const MapSearchPanel = React.lazy(() => import('./MapSearchPanel'));
import { useCategories } from '../hooks/useCategories';
import { useMarketplaceItems } from '../hooks/useMarketplaceItems';
import { SellerRatingInline } from './SellerReputation';
import { useInsightsTracker } from '../hooks/useInsightsTracker';
import useMarketplaceSync from '../hooks/useMarketplaceSync';

const API = API_BASE;

// iter239 — Module-scope backend URL prevents accidental useEffect re-firing
// when this value is included in dependency arrays (the literal would
// recreate a new string per render under React Refresh).
const BACKEND_URL = API_BASE;

/**
 * FlattenedMarketplace - Item-Centric Discovery View
 * 
 * Key Features:
 * - Displays individual items/lots as standalone cards
 * - Dynamic Private Sale / Business Sale badges
 * - Live countdown timers per item
 * - Quick Bid functionality without leaving page
 * - "Show Private Sales Only" filter toggle
 * - Universal search across all lots
 * - Link to parent auction for related items
 */
const FlattenedMarketplace = ({ 
  limit = 50, 
  showFilters = true,
  showHeader = true,
  variant = 'full', // 'full', 'compact', 'homepage'
  externalFilters = {},
  onClearSidebarCategory = null
}) => {
  const { t, i18n } = useTranslation();
  const isFrench = i18n.language?.startsWith('fr');
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const { trackView: insightView, trackClick: insightClick, trackSearch: insightSearch } = useInsightsTracker();
  const queryClient = useQueryClient();

  // Real-time marketplace sync — update cached cards on bid/extension events
  const handleMarketplaceUpdate = useCallback((msg) => {
    const { listing_id, current_price, bid_count, new_auction_end } = msg;
    queryClient.setQueriesData({ queryKey: ['marketplace-items'] }, (old) => {
      if (!old?.pages) return old;
      return {
        ...old,
        pages: old.pages.map(page => ({
          ...page,
          items: (page.items || []).map(item => {
            if (item.id !== listing_id) return item;
            const updated = { ...item };
            if (current_price != null) updated.current_price = current_price;
            if (bid_count != null) updated.bid_count = bid_count;
            if (new_auction_end) updated.auction_end_date = new_auction_end;
            return updated;
          })
        }))
      };
    });
  }, [queryClient]);

  useMarketplaceSync(handleMarketplaceUpdate);
  
  // Filters
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    min_price: '',
    max_price: '',
    condition: '',
    sort: 'ending_soon',
    private_sales_only: false,
    zero_fee_only: false
  });
  
  // Quick Bid Modal State
  const [quickBidOpen, setQuickBidOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [bidAmount, setBidAmount] = useState('');
  const [bidConfirmOpen, setBidConfirmOpen] = useState(false);
  const [placingBid, setPlacingBid] = useState(false);

  // Compare mode state
  const [compareIds, setCompareIds] = useState([]);
  const toggleCompare = (id) => {
    setCompareIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : prev.length < 4 ? [...prev, id] : prev
    );
  };
  
  // React Query: categories
  const { data: categories = [] } = useCategories();
  
  // Debounced filters — prevents API call on every keystroke
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const debounceTimerRef = useRef(null);

  // Merge sidebar external filters with internal filters
  const mergedFilters = {
    ...filters,
    ...(externalFilters.categories?.length ? { categories: externalFilters.categories.join(',') } : {}),
    ...(externalFilters.regions?.length ? { regions: externalFilters.regions.join(',') } : {}),
    ...(externalFilters.cities?.length ? { cities: externalFilters.cities.join(',') } : {}),
    ...(externalFilters.auctioneers?.length ? { seller_id: externalFilters.auctioneers.join(',') } : {}),
    ...(externalFilters.search ? { search: externalFilters.search } : {}),
    ...(filters.zero_fee_only ? { zero_fee_only: 'true' } : {}),
  };

  // Debounce filter changes by 300ms
  useEffect(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedFilters(mergedFilters);
    }, 300);
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [filters, externalFilters]);

  // React Query: infinite marketplace items with cursor pagination
  const {
    data: marketplaceData,
    isLoading: loading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch: refetchItems,
  } = useMarketplaceItems(debouncedFilters, limit);

  // iter236 Mission 2 — Map-based geo filter state.
  // When `geoFilter` is non-null, override the cached `items` list with a
  // dedicated /api/marketplace/items/geo fetch. Stays decoupled from the
  // primary cached endpoint so geo doesn't pollute the warm cache.
  const [mapOpen, setMapOpen] = useState(false);
  const [geoFilter, setGeoFilter] = useState(null); // {lat,lng,radius_km} | null
  const [geoItems, setGeoItems] = useState(null);   // null = pass-through

  // iter239 Mission 5 — Inline promoted-card injection at grid indices 3,8,18,28…
  const [promotedInline, setPromotedInline] = useState([]);

  // Positions in the grid where we splice a promoted card.
  const PROMO_SLOTS = [3, 8, 18, 28, 38];

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${BACKEND_URL}/promoted-listings?section=marketplace&limit=10`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setPromotedInline(Array.isArray(d.items) ? d.items : []))
      .catch(() => setPromotedInline([]));
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    if (!geoFilter) {
      setGeoItems(null);
      return undefined;
    }
    const ctrl = new AbortController();
    const url = `${BACKEND_URL}/marketplace/items/geo?lat=${geoFilter.lat}&lng=${geoFilter.lng}&radius_km=${geoFilter.radius_km}&limit=60`;
    fetch(url, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setGeoItems(d.items || []))
      .catch(() => undefined);
    return () => ctrl.abort();
  }, [geoFilter]);

  // Flatten pages into a single items array
  const allItems = (marketplaceData?.pages ?? []).flatMap((page) => page.items ?? []);
  const baseItems = filters.private_sales_only
    ? allItems.filter((item) => !item.seller_is_business)
    : allItems;
  // iter236 Mission 2 — Geo override takes priority when map filter active.
  const items = geoItems !== null ? geoItems : baseItems;
  const total = marketplaceData?.pages?.[0]?.total ?? 0;
  const hasMore = hasNextPage;

  // Batch-fetch seller reputations for all visible items
  const [sellerReps, setSellerReps] = useState({});
  useEffect(() => {
    const sellerIds = [...new Set(allItems.map(i => i.seller_id).filter(Boolean))];
    if (sellerIds.length === 0) return;
    axios.post(`${API}/reviews/reputation/batch`, { seller_ids: sellerIds })
      .then(res => setSellerReps(res.data.reputations || {}))
      .catch(() => {});
  }, [allItems.length]); // re-fetch when items change

  const trackClick = async (itemId) => {
    try {
      await axios.post(`${API}/marketplace/items/${itemId}/track-click`);
      // Also log to user insights for AI profiling
      const item = allItems?.find(i => i.id === itemId);
      insightClick(itemId, item?.category);
    } catch (error) {
      console.error('Error tracking click:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    if (key === 'search' && value) insightSearch(value);
  };

  const openQuickBid = (item, e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!token) {
      navigate('/auth', { state: { from: { pathname: '/marketplace' } } });
      return;
    }
    
    setSelectedItem(item);
    const minBid = (item.current_price || item.starting_price || 0) + 10;
    setBidAmount(minBid.toFixed(2));
    setQuickBidOpen(true);
  };

  const handleQuickBidSubmit = () => {
    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error(isFrench ? 'Veuillez entrer un montant valide' : 'Please enter a valid bid amount');
      return;
    }

    if (amount <= (selectedItem?.current_price || 0)) {
      toast.error(isFrench ? "L'offre doit être supérieure au prix actuel" : 'Bid must be higher than current price');
      return;
    }

    // BUG FIX (Bug 2): Close the QuickBid modal FIRST to prevent two Radix Dialog
    // overlays from stacking and producing a black screen. The BidConfirmation
    // dialog then opens cleanly with a single overlay.
    setQuickBidOpen(false);
    setTimeout(() => setBidConfirmOpen(true), 0);
  };

  const confirmBid = async () => {
    if (!selectedItem || !token) return;
    
    setPlacingBid(true);
    try {
      // Detect single-item vs multi-item listing
      const isMultiItem = selectedItem.auction_id && selectedItem.lot_number != null;
      const url = isMultiItem
        ? `${API}/multi-item-listings/${selectedItem.auction_id}/lots/${selectedItem.lot_number}/bid`
        : `${API}/bids`;
      const body = isMultiItem
        ? { amount: parseFloat(bidAmount) }
        : { listing_id: selectedItem.id, amount: parseFloat(bidAmount) };

      const response = await axios.post(url, body, 
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      toast.success('Bid placed successfully!');
      setBidConfirmOpen(false);
      setQuickBidOpen(false);
      setSelectedItem(null);
      setBidAmount('');
      
      // Refresh items via React Query
      refetchItems();
    } catch (error) {
      const detail = error.response?.data?.detail;
      let message = 'Failed to place bid';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map(e => (typeof e === 'string' ? e : e?.msg || '')).filter(Boolean).join(', ') || message;
      } else if (detail && typeof detail === 'object') {
        message = detail.msg || JSON.stringify(detail);
      }
      toast.error(message);
    } finally {
      setPlacingBid(false);
    }
  };

  return (
    <div className={`overflow-x-hidden ${variant === 'homepage' ? '' : variant === 'full' ? '' : 'container mx-auto px-4 py-8'}`}>
      {/* iter238 Mission 1.3 — Dismissible location banner for users without a city on file. */}
      <LocationBanner />

      {/* iter239 Mission 5 — Featured Listings horizontal snap-scroll carousel. */}
      <FeaturedListingsBanner section="marketplace" limit={8} />

      {/* Header */}
      {showHeader && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
                {t('marketplace.browseItems', 'Browse Individual Items')}
              </h1>
              <p className="text-slate-600 dark:text-slate-400">
                {t('marketplace.itemsFromAuctions', 'Individual lots from active auctions')}
              </p>
            </div>
            <Badge className="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200 dark:border-green-700">
              {total} items
            </Badge>
          </div>
        </div>
      )}

      {/* Filters — New FilterBar Component */}
      {showFilters && (
        <div className="mb-4">
          <FilterBar
            onFilterChange={(newFilters) => {
              // iter217 Phase 4 — Forward ALL FilterBar fields, including
              // province + pill filters. Previously only 6 fields were
              // forwarded, so the top-bar dropdowns visually changed but
              // the grid never re-filtered.
              setFilters(prev => ({
                ...prev,
                search: newFilters.search,
                category: newFilters.category,
                condition: newFilters.condition,
                sort: newFilters.sort,
                private_sales_only: newFilters.private_sales_only,
                zero_fee_only: newFilters.zero_fee_only,
                province: newFilters.province,
                partner_only: newFilters.partner_only,
                lots_auction: newFilters.lots_auction,
                no_taxes: newFilters.no_taxes,
                tax_status: newFilters.tax_status,
              }));
            }}
            pageContext="marketplace"
            // Phase 5 Hotfix v5 — when the parent page wires the
            // MarketplaceSidebar (externalFilters.categories), the top-bar
            // category dropdown becomes a duplicate. Hide it and surface
            // the sidebar selection as a removable chip instead.
            hideCategoryDropdown={!!(externalFilters && externalFilters.categories)}
            sidebarCategoryChip={externalFilters?.categories || []}
            onClearSidebarCategory={onClearSidebarCategory}
          />
        </div>
      )}

      {/* iter239 — Duplicate quick-pill row removed. The 4 official pills
          (Private Sales / Verified Seller / Partners / Lots Auction) are
          now rendered exclusively by FilterBar above. No-Taxes pill
          deprecated per user spec. */}

      {/* iter236 Mission 2 — Map search toggle + panel */}
      <div className="mb-2 flex items-center justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setMapOpen((o) => !o)}
          className="text-xs"
          data-testid="map-search-toggle-btn"
        >
          <MapPin className="h-3.5 w-3.5 mr-1" />
          {mapOpen
            ? (i18n.language?.startsWith('fr') ? 'Masquer la carte' : 'Hide Map')
            : (i18n.language?.startsWith('fr') ? '📍 Recherche par carte' : '📍 Search by Map')}
        </Button>
      </div>
      {mapOpen && (
        <React.Suspense fallback={<div className="w-full mb-4 p-4 text-center text-xs text-slate-500">Loading map…</div>}>
          <MapSearchPanel
            open={mapOpen}
            onClose={() => setMapOpen(false)}
            onGeoChange={setGeoFilter}
            backendUrl={backendUrl}
            isFrench={i18n.language?.startsWith('fr')}
          />
        </React.Suspense>
      )}
      {/* Items Grid — iter220 Task 2: matches VehicleAuctionsPage breakpoints
          (sm:2 / lg:3 / xl:4) so wider workspaces (≥1280px) get 4 columns
          and tablets get 2 instead of jumping straight to 3. */}
      {loading && items.length === 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4 xl:gap-5" data-testid="marketplace-results-grid-loading">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="animate-pulse min-h-[420px]">
              <div className="h-[200px] bg-gray-200 dark:bg-slate-700 rounded-t-lg"></div>
              <CardContent className="p-4 space-y-2">
                <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded"></div>
                <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-3/4"></div>
                <div className="h-8 bg-gray-200 dark:bg-slate-700 rounded mt-4"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 bg-slate-50 dark:bg-slate-800 rounded-xl" data-testid="marketplace-empty-state">
          <Search className="h-12 w-12 text-slate-400 dark:text-slate-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold mb-2 text-slate-900 dark:text-white">{t('marketplace.noItemsFound', 'No listings found')}</h3>
          <p className="text-slate-600 dark:text-slate-400 mb-4">
            {t('marketplace.tryAdjusting', 'Try adjusting your filters or search terms.')}
          </p>
          <Button onClick={() => setFilters({
            search: '',
            category: '',
            min_price: '',
            max_price: '',
            condition: '',
            sort: 'ending_soon',
            private_sales_only: false
          })} className="bg-blue-600 text-white hover:bg-blue-700" data-testid="marketplace-empty-clear-filters-btn">
            {t('marketplace.clearAllFilters')}
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4 xl:gap-5" data-testid="marketplace-results-grid">
          {(() => {
            // iter239 Mission 5 — Splice promoted listings into the grid at
            // PROMO_SLOTS (3, 8, 18, 28, 38). Skips promos that are already
            // present in `items` to avoid duplicate rendering.
            const visibleIds = new Set(items.map((i) => i.id));
            const promoQueue = promotedInline.filter((p) => !visibleIds.has(p.id));
            const out = [];
            let pIdx = 0;
            items.forEach((item, idx) => {
              if (PROMO_SLOTS.includes(idx) && pIdx < promoQueue.length) {
                const promo = promoQueue[pIdx];
                pIdx += 1;
                out.push(
                  <ItemCard
                    key={`promo-${promo.id}`}
                    item={{ ...promo, _is_promoted_inline: true }}
                    onQuickBid={openQuickBid}
                    trackClick={trackClick}
                    isComparing={compareIds.includes(promo.id)}
                    onToggleCompare={toggleCompare}
                    sellerRep={sellerReps[promo.seller_id]}
                  />
                );
              }
              out.push(
                <ItemCard
                  key={item.id}
                  item={item}
                  onQuickBid={openQuickBid}
                  trackClick={trackClick}
                  isComparing={compareIds.includes(item.id)}
                  onToggleCompare={toggleCompare}
                  sellerRep={sellerReps[item.seller_id]}
                />
              );
            });
            return out;
          })()}
        </div>
      )}

      {/* Load More */}
      {hasMore && !loading && (
        <div className="text-center mt-8">
          <Button 
            onClick={() => fetchNextPage()} 
            variant="outline"
            className="px-8"
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? t('common.loading') : t('marketplace.loadMore')}
          </Button>
        </div>
      )}

      {/* Quick Bid Modal */}
      <Dialog open={quickBidOpen} onOpenChange={setQuickBidOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-cyan-500" />
              Quick Bid
            </DialogTitle>
            <DialogDescription>
              Place a bid on &quot;{selectedItem && getLocalized(selectedItem, 'title')}&quot;
            </DialogDescription>
          </DialogHeader>

          {selectedItem && (
            <div className="space-y-4">
              {/* Item Preview */}
              <div className="flex gap-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                {selectedItem.images?.[0] && (
                  <SafeImage 
                    src={selectedItem.images[0]} 
                    alt={selectedItem.title}
                    width={80}
                    height={80}
                    className="w-20 h-20 object-cover rounded-lg"
                  />
                )}
                <div className="flex-1">
                  <h4 className="font-semibold line-clamp-1">{selectedItem.title}</h4>
                  <p className="text-sm text-muted-foreground">
                    Current: {formatCurrency(selectedItem.current_price, selectedItem.currency)} <span className="ml-1"><span data-testid="currency-code-selected" className={`text-[10px] font-bold px-1.5 py-0 rounded-full ${selectedItem.currency === 'USD' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{selectedItem.currency || 'CAD'}</span></span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {selectedItem.bid_count || 0} bids
                  </p>
                </div>
              </div>

              {/* Seller Type Badge */}
              {!selectedItem.seller_is_business && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-green-600" />
                    <span className="font-medium text-green-700 dark:text-green-400">
                      {t('marketplace.noTaxOnHammer')}
                    </span>
                  </div>
                </div>
              )}

              {/* Bid Input */}
              <div>
                <label className="text-sm font-medium mb-2 block">Your Bid Amount ($)</label>
                <Input
                  type="number"
                  step="0.01"
                  min={(selectedItem.current_price || 0) + 1}
                  value={bidAmount}
                  onChange={(e) => setBidAmount(e.target.value)}
                  placeholder={`Min: ${formatCurrency((selectedItem.current_price || 0) + 10)}`}
                  className="text-lg font-semibold"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Minimum bid: {formatCurrency((selectedItem.current_price || 0) + 10)}
                </p>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setQuickBidOpen(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleQuickBidSubmit}
              className="bg-gradient-to-r from-blue-600 to-cyan-500 text-white"
            >
              <Receipt className="h-4 w-4 mr-2" />
              Review Total Cost
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bid Confirmation Dialog with Cost Breakdown */}
      {selectedItem && (
        <BidConfirmationDialog
          isOpen={bidConfirmOpen}
          onClose={() => {
            // BUG FIX (Bug 2): full state cleanup so no stale overlay/pointer-events lingers
            setBidConfirmOpen(false);
            setPlacingBid(false);
          }}
          onConfirm={confirmBid}
          bidAmount={parseFloat(bidAmount) || 0}
          listingTitle={selectedItem && getLocalized(selectedItem, 'title')}
          sellerIsBusiness={selectedItem.seller_is_business || false}
          region={selectedItem.region || 'QC'}
          loading={placingBid}
          /* HOTFIX — Quick Bid premium desync. Previously the Quick Bid modal
             rendered the BidConfirmationDialog without any tier context, so it
             defaulted to `buyerTier="basic"` which the backend resolves to the
             standard 5% rate. The ListingDetailPage already forwards these
             props from the user session; we now mirror them here so VIP / Premium
             subscribers see the correct discounted rate (3.0% / 3.5%) in the
             marketplace Quick Bid flow. */
          buyerTier={user?.subscription_tier || 'standard'}
          sellerTier={selectedItem.seller_subscription_tier || 'standard'}
          category={selectedItem.category || 'general'}
          buyersPremiumRate={selectedItem.custom_buyer_premium_rate}
          currency={selectedItem.currency || 'CAD'}
        />
      )}

      {/* Floating Compare Bar */}
      {compareIds.length > 0 && (
        <div className="fixed bottom-28 sm:bottom-24 md:bottom-6 left-1/2 -translate-x-1/2 z-[60] bg-slate-900 dark:bg-slate-800 text-white rounded-full shadow-2xl px-5 py-3 flex items-center gap-3 border border-cyan-500/30" data-testid="compare-floating-bar">
          <Scale className="h-4 w-4 text-cyan-400 shrink-0" />
          <span className="text-sm font-medium whitespace-nowrap">{compareIds.length} selected</span>
          <Button
            size="sm"
            onClick={() => navigate(`/compare?ids=${compareIds.join(',')}`)}
            className="bg-cyan-500 hover:bg-cyan-600 text-white rounded-full h-8 px-4 text-xs font-bold"
            data-testid="compare-go-btn"
          >
            Compare
          </Button>
          <button onClick={() => setCompareIds([])} className="text-slate-400 hover:text-white" data-testid="compare-clear-btn">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
};

/**
 * ItemCard - Individual item card component
 */
const ItemCard = ({ item, onQuickBid, trackClick, isComparing, onToggleCompare, sellerRep }) => {
  const { t, i18n } = useTranslation();
  const isFrench = i18n.language?.startsWith('fr');
  const [timeLeft, setTimeLeft] = useState('');
  const [isUrgent, setIsUrgent] = useState(false);

  useEffect(() => {
    const calculateTimeLeft = () => {
      if (!item.auction_end_date) return 'N/A';
      
      const end = new Date(item.auction_end_date);
      const now = new Date();
      const diff = end - now;
      
      if (diff <= 0) return t('marketplace.timeEnded', 'Ended');
      
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      
      // Set urgent if less than 1 hour
      setIsUrgent(diff < 60 * 60 * 1000);
      
      if (days > 0) return `${days}d ${hours}h`;
      if (hours > 0) return `${hours}h ${minutes}m`;
      return `${minutes}m ${seconds}s`;
    };

    setTimeLeft(calculateTimeLeft());
    const timer = setInterval(() => setTimeLeft(calculateTimeLeft()), 1000);
    return () => clearInterval(timer);
  }, [item.auction_end_date, t]);

  const getPromotionBadge = () => {
    if (item.promotion_tier === 'premium') {
      return (
        <Badge className="bg-gradient-to-r from-yellow-400 to-orange-500 text-white font-bold text-xs">
          <Sparkles className="h-3 w-3 mr-1" />
          PREMIUM
        </Badge>
      );
    }
    if (item.promotion_tier === 'standard' || item.is_featured) {
      return (
        <Badge className="bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold text-xs">
          <Star className="h-3 w-3 mr-1" />
          FEATURED
        </Badge>
      );
    }
    if (item.is_promoted) {
      return (
        <Badge className="bg-slate-600 text-white text-xs">
          <TrendingUp className="h-3 w-3 mr-1" />
          Sponsored
        </Badge>
      );
    }
    return null;
  };

  // iter222 Repair 2 — Badge resolution by ITEM TYPE first, seller profile
  // second. Previously a seller who happened to be a vehicle dealer would
  // tag their non-vehicle listings (e.g. storage lockers, retail surplus) with
  // the "Vehicle Dealer / Concessionnaire" badge. We now derive the badge
  // strictly from `listing_type` + `category` and only fall back to the
  // seller profile when those two signals are silent.
  const _resolveAcctType = () => {
    const lt = (item.listing_type || '').toLowerCase();
    const cat = (item.category || '').toLowerCase();
    const isVehicleItem =
      lt === 'vehicle' ||
      cat === 'vehicle' || cat === 'vehicles' || cat === 'car' || cat === 'auto' || cat === 'automobile' ||
      cat === 'truck' || cat === 'motorcycle';

    // 1) Item-driven: storage locker is ALWAYS a storage_facility card,
    //    regardless of whether the seller account is a dealer or partner.
    if (lt === 'storage_locker' || cat === 'storage_locker') return 'storage_facility';

    // 2) Item-driven: only render Vehicle Dealer when the item itself is
    //    flagged as a vehicle. Otherwise the dealer badge is irrelevant.
    if (isVehicleItem) {
      if (item.seller_is_vehicle_dealer || item.seller_account_type === 'vehicle_dealer') {
        return 'vehicle_dealer';
      }
    }

    // 3) Seller-profile fallback (legacy path) — Partner overrides.
    if (item.seller_account_type) {
      const sat = item.seller_account_type;
      // Block stale vehicle_dealer leakage on non-vehicle items.
      if (sat === 'vehicle_dealer' && !isVehicleItem) {
        return item.seller_is_business ? 'business' : 'individual';
      }
      return sat;
    }
    if (item.seller_is_partner) return 'partner';
    if (item.seller_is_storage_facility) return 'storage_facility';
    return item.seller_is_business ? 'business' : 'individual';
  };
  const acctType = _resolveAcctType();
  const isPrivateSale = acctType === 'individual';
  const isPartner = acctType === 'partner';
  // Smart routing: vehicles -> /vehicle-auctions/:id, storage -> /storage-auctions/:id, lots -> /lots/:id, default -> /listing/:id
  const getDetailLink = (item) => {
    const cat = (item.category || '').toLowerCase();
    const lt = (item.listing_type || '').toLowerCase();
    // iter222 — storage lockers from `listings` collection route to the
    // dedicated storage detail page so the storage-specific bidding UI
    // (deposit hold, cleanout deadline, etc.) renders correctly.
    if (lt === 'storage_locker' || cat === 'storage_locker') {
      return `/storage-auctions/${item.id}`;
    }
    if (cat === 'vehicle' || cat === 'vehicles' || cat === 'car' || cat === 'auto') {
      return `/vehicle-auctions/${item.id}`;
    }
    return item.auction_id ? `/lots/${item.auction_id}` : `/listing/${item.id}`;
  };
  const detailLink = getDetailLink(item);

  return (
    <Card
      className="group overflow-hidden flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-[0_2px_12px_rgba(0,0,0,0.08)] hover:shadow-[0_10px_28px_rgba(0,0,0,0.14)] transition-all duration-150 hover:-translate-y-[3px] min-h-[420px]"
      data-testid={item._is_promoted_inline ? 'marketplace-item-card-promoted' : 'marketplace-item-card'}
    >
      {/* Image Container — fixed 200px height per iter236 spec */}
      <Link
        to={detailLink}
        onClick={() => trackClick(item.id)}
        className="block"
      >
        <div className="relative h-[200px] bg-slate-100 dark:bg-slate-800 overflow-hidden">
          {item.images?.[0] ? (
            <SafeImage
              src={item.images[0]}
              alt={getLocalized(item, 'title')}
              width={400}
              height={208}
              loading="lazy"
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Package className="h-16 w-16 text-gray-300" />
            </div>
          )}

          {/* Top Left - Badges stack */}
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1.5">
            {item.status === 'ended' && item.highest_bidder_id && (
              <Badge className="bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-900 border-0 shadow-lg text-xs font-bold" data-testid="winner-badge">
                WINNER / GAGNANT
              </Badge>
            )}
            {/* iter217 Phase 4 — Single source of truth for seller-type badge */}
            <SellerAccountBadge
              accountType={acctType === 'business' ? 'individual' : acctType}
              companyName={item.seller_partner_company_name}
              variant="compact"
            />
            {acctType === 'business' && (
              <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">
                <ShieldCheck className="h-3 w-3 mr-1" />
                {t('marketplace.business')}
              </Badge>
            )}
            {/* Multi-Lot Badge */}
            {item.listing_type === 'multi_lot' && (
              <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200 text-xs" data-testid="multi-lot-badge">
                {isFrench ? 'Partie d\'une enchère' : 'Part of Auction'}
              </Badge>
            )}
            {/* New Listing Badge */}
            {item.created_at && (Date.now() - new Date(item.created_at).getTime()) < 86400000 * 3 && (
              <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-xs" data-testid="new-badge">
                {isFrench ? 'Nouveau' : 'New'}
              </Badge>
            )}
          </div>

          {/* Top Right - Promotion Badge */}
          {getPromotionBadge() && (
            <div className="absolute top-3 right-3 z-10">
              {getPromotionBadge()}
            </div>
          )}

          {/* Compare checkbox */}
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggleCompare(item.id); }}
            className={`absolute ${getPromotionBadge() ? 'top-10' : 'top-3'} right-3 z-20 w-7 h-7 rounded-full flex items-center justify-center transition-all shadow-md ${
              isComparing
                ? 'bg-cyan-500 text-white scale-110'
                : 'bg-white/80 dark:bg-slate-800/80 text-slate-500 opacity-0 group-hover:opacity-100'
            }`}
            data-testid={`compare-toggle-${item.id}`}
            title="Add to compare"
          >
            <Scale className="h-3.5 w-3.5" />
          </button>

          {/* Bottom - Timer + Urgency Badge */}
          <div className="absolute bottom-3 left-3 right-3 flex justify-between items-center">
            <div className="flex items-center gap-1.5">
              {isUrgent && timeLeft !== t('marketplace.timeEnded', 'Ended') && (
                <div className="bg-red-600 text-white px-2 py-1.5 rounded-full text-xs font-bold flex items-center gap-1 shadow-lg animate-pulse" data-testid="ending-soon-badge">
                  <Flame className="h-3.5 w-3.5" />
                  {t('marketplace.endingSoon')}
                </div>
              )}
              <div className={`px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-1.5 shadow-lg ${
                isUrgent 
                  ? 'bg-red-500 text-white animate-pulse' 
                  : 'bg-slate-900/80 backdrop-blur text-white'
              }`} data-testid="countdown-timer">
                <Timer className="h-3.5 w-3.5" />
                {timeLeft}
              </div>
            </div>
            
            {item.bid_count > 0 && (
              <div className="bg-slate-900/80 backdrop-blur text-white px-2 py-1 rounded-full text-xs">
                <Gavel className="h-3 w-3 inline mr-1" />
                {item.bid_count} {t('marketplace.bids')}
              </div>
            )}
          </div>
        </div>
      </Link>

      <CardContent className="px-4 py-[14px] flex flex-col flex-1 gap-2" data-testid="item-card">
        {/* Title — 14px / 600 / 2-line clamp per iter236 spec */}
        <Link
          to={detailLink}
          onClick={() => trackClick(item.id)}
          className="block"
        >
          <h3
            className="text-[14px] font-semibold leading-[1.35] line-clamp-2 text-slate-900 dark:text-white hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors mb-1"
            data-testid="item-title"
          >
            {getLocalized(item, 'title')}
          </h3>
        </Link>

        {/* Seller + location single line */}
        <div className="flex items-center text-[12px] text-slate-500 dark:text-slate-400 gap-2">
          <SellerRatingInline sellerId={item.seller_id} reputation={sellerRep} />
          {item.city && (
            <span className="inline-flex items-center gap-1 truncate">
              <MapPin className="h-3 w-3 flex-shrink-0" />
              <span className="truncate">{item.city}, {item.region}</span>
            </span>
          )}
        </div>

        {/* Savings pill — Private Sale */}
        {isPrivateSale && (
          <div
            className="w-full text-center rounded-md px-[10px] py-[5px] mt-1"
            style={{ backgroundColor: '#e6f9f0', color: '#1a7a4a', fontSize: '11px', fontWeight: 600 }}
            data-testid="card-savings-banner"
          >
            {t('marketplace.noTaxOnItem')}
          </div>
        )}
        {/* iter217 Phase 4 — Buyer's Premium hint on partner cards */}
        {isPartner && typeof item.buyer_premium_rate === 'number' && (
          <div className="rounded-md px-3 py-1 text-[11px] font-medium" style={{ background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1d4ed8' }}>
            {t('marketplace.partnerBpHint', {
              pct: (item.buyer_premium_rate * 100).toFixed(1).replace(/\.0$/, ''),
              defaultValue: "Buyer's Premium: {{pct}}% — GST/QST applicable",
            })}
          </div>
        )}

        {/* Spacer to push pricing and actions to the bottom */}
        <div className="flex-1" />

        {/* Pricing */}
        <div className="space-y-1">
          {(() => {
            // iter233 — Compute display total when `price_multiplied_by_quantity` is set
            // on the listing/lot. Falls back to per-unit price when not multiplied.
            const dp = computeDisplayPrice({
              ...item,
              hammer_price: item.hammer_price ?? item.final_hammer_price ?? null,
              current_bid: item.current_price ?? item.current_bid ?? null,
              starting_price: item.starting_price ?? null,
            });
            const statusLower = (item.status || '').toLowerCase();
            const isEnded = ['ended', 'sold', 'closed', 'completed'].includes(statusLower);
            const hasBids = Number(item.current_price ?? item.current_bid ?? 0) > 0;
            let label;
            if (isEnded) {
              label = isFrench ? 'Prix total' : 'Total Price';
            } else if (hasBids) {
              label = isFrench ? 'Offre totale' : 'Total Bid';
            } else {
              label = isFrench ? 'Total de départ' : 'Starting Total';
            }
            const labelText = dp.isMultiplied
              ? `${label} (× ${dp.quantity}${isFrench ? ' unités' : ' units'})`
              : (isFrench ? 'OFFRE ACTUELLE' : 'CURRENT BID');

            return (
              <>
                <div className="flex items-baseline justify-between">
                  <span
                    className="text-[10px] font-bold uppercase text-slate-500 dark:text-slate-400 tracking-[0.5px]"
                    data-testid="card-price-label"
                  >
                    {labelText}
                  </span>
                  <div className="flex items-baseline gap-[6px]">
                    <span
                      className="text-[22px] font-extrabold text-[#0a1628] dark:text-white"
                      data-testid="card-display-price"
                    >
                      {formatCurrency(dp.totalPrice, item.currency)}
                    </span>
                    <span
                      className="inline-block text-[10px] rounded text-[#4a5568] dark:text-slate-300"
                      style={{ backgroundColor: '#e8ecf2', padding: '2px 6px' }}
                      data-testid="listing-currency-badge"
                    >
                      {item.currency || 'CAD'}
                    </span>
                  </div>
                </div>
                {dp.isMultiplied && (
                  <>
                    <div className="flex items-center justify-end" data-testid="card-unit-price-subtext">
                      <span className="text-[11px] text-slate-500 dark:text-slate-400">
                        ({formatCurrency(dp.unitPrice, item.currency)} {isFrench ? 'par unité' : 'per unit'})
                      </span>
                    </div>
                    <div className="flex items-center justify-end pt-0.5" data-testid="card-lot-multiplier-badge">
                      <Badge className="bg-amber-100 text-amber-800 border border-amber-300 hover:bg-amber-200 text-[10px] font-semibold uppercase tracking-wider">
                        {isFrench ? 'Prix lot × Qté' : 'Lot Price × Qty'}
                      </Badge>
                    </div>
                  </>
                )}
              </>
            );
          })()}

          {item.buy_now_enabled && item.buy_now_price && (
            <div className="flex items-center justify-between mt-1 mb-3" data-testid="card-buy-now-row">
              <span className="text-[12px] text-slate-500 dark:text-slate-400">{t('marketplace.buyNowLabel')}</span>
              <span className="text-[13px] font-semibold" style={{ color: '#2d6be4' }}>
                {formatCurrency(item.buy_now_price)}
              </span>
            </div>
          )}
        </div>

        {/* Parent Auction Link */}
        {item.auction_id && item.lot_number && (
          <div className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200 dark:border-slate-700">
            Lot #{item.lot_number} of{' '}
            <Link
              to={`/lots/${item.auction_id}`}
              className="text-cyan-600 dark:text-cyan-400 hover:underline inline-flex items-center gap-1"
            >
              {getLocalized(item, 'parent_auction_title') || t('marketplace.viewAuction')}
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        )}

        {/* iter236 — Action row: full-flex Quick Bid + 40×40 circular Eye/Watch button. */}
        <div
          className="flex items-center w-full mt-auto pt-1"
          data-testid="marketplace-card-actions"
        >
          <Button
            onClick={(e) => onQuickBid(item, e)}
            size="sm"
            className="flex-1 min-w-0 h-[40px] rounded-lg text-white font-bold text-[13px]"
            style={{ background: 'linear-gradient(135deg, #2d6be4, #1a4fc4)', border: 'none' }}
            data-testid="quick-bid-btn"
          >
            <Zap className="h-3.5 w-3.5 mr-1 flex-shrink-0" />
            <span className="truncate">{t('marketplace.quickBid')}</span>
          </Button>
          <Link
            to={detailLink}
            aria-label={t('common.view')}
            title={t('common.view')}
            className="ml-2 flex-shrink-0 w-10 h-10 inline-flex items-center justify-center rounded-full text-slate-500 hover:text-[#2d6be4] hover:border-[#2d6be4] transition-colors"
            style={{ border: '1.5px solid #e2e8f0' }}
            data-testid="view-item-btn"
          >
            <Eye className="h-4 w-4" />
          </Link>
        </div>
      </CardContent>
    </Card>
  );
};

export default FlattenedMarketplace;
