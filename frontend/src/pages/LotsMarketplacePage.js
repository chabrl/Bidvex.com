import API_BASE from '../config';
import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  Package, Clock, MapPin, Layers, Grid as GridIcon,
  List as ListIcon, Star, Sparkles, Eye, Building2
} from 'lucide-react';
import Countdown from 'react-countdown';
import SafeImage from '../components/SafeImage';
import WishlistHeartButton from '../components/WishlistHeartButton';
import MarketplaceSidebar from '../components/MarketplaceSidebar';
import { VerifiedBadge } from '../components/VerifiedBadge';
import { formatCurrency, formatListingPrice } from '../utils/currencyFormatter';
import { getLocalized } from '../utils/localization';
import { SellerRatingInline } from '../components/SellerReputation';
import { LoadingTimeout } from '../components/LoadingTimeout';
import { SellerAccountBadge } from '../components/PrivateSaleBadge';

import FilterBar from '../components/FilterBar/FilterBar';
// iter239 Mission 5 — Featured Listings carousel.
import FeaturedListingsBanner from '../components/FeaturedListingsBanner';
// iter268 Mission 4 — SEO meta tags
import SEO from '../components/SEO';
// iter236 Mission 2 — Map & radius search panel (lazy so Leaflet's chunk
// only loads when the user actually clicks "Search by Map").
const MapSearchPanel = React.lazy(() => import('../components/MapSearchPanel'));

const API = API_BASE;

const LotsMarketplacePage = () => {
  const { t, i18n } = useTranslation();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('grid');
  const [sidebarFilters, setSidebarFilters] = useState({});
  // iter236 Mission 2 — geo state (mirrors FlattenedMarketplace wiring).
  const [mapOpen, setMapOpen] = useState(false);
  const [geoFilter, setGeoFilter] = useState(null);
  const [geoListings, setGeoListings] = useState(null);
  // iter265 Mission 1.2 — Inline promoted-card injection on Lots grid.
  const [promotedInline, setPromotedInline] = useState([]);
  const PROMO_SLOTS = [3, 8, 18, 28, 38];
  const backendUrl = process.env.REACT_APP_BACKEND_URL
    ? `${process.env.REACT_APP_BACKEND_URL}/api`
    : '/api';

  // iter265 Mission 1.2 — Fetch promoted lots once on mount.
  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`${backendUrl}/promoted-listings?section=lots&limit=10`, { signal: ctrl.signal })
      .then(r => (r.ok ? r.json() : { items: [] }))
      .then(d => setPromotedInline(Array.isArray(d.items) ? d.items : []))
      .catch(() => setPromotedInline([]));
    return () => ctrl.abort();
  }, [backendUrl]);

  useEffect(() => {
    if (!geoFilter) {
      setGeoListings(null);
      return undefined;
    }
    const ctrl = new AbortController();
    const url = `${backendUrl}/marketplace/items/geo?lat=${geoFilter.lat}&lng=${geoFilter.lng}&radius_km=${geoFilter.radius_km}&limit=60`;
    fetch(url, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setGeoListings(d.items || []))
      .catch(() => undefined);
    return () => ctrl.abort();
  }, [geoFilter, backendUrl]);

  // Fetch listings whenever sidebar filters change
  useEffect(() => {
    const fetchListings = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        params.append('limit', '50');

        // Wire sidebar filters to API
        if (sidebarFilters.search) params.append('search', sidebarFilters.search);
        if (sidebarFilters.categories?.length) params.append('category', sidebarFilters.categories.join(','));
        if (sidebarFilters.regions?.length) params.append('region', sidebarFilters.regions.join(','));
        if (sidebarFilters.cities?.length) params.append('city', sidebarFilters.cities.join(','));
        if (sidebarFilters.auctioneers?.length) params.append('seller_id', sidebarFilters.auctioneers.join(','));

        const response = await axios.get(`${API}/multi-item-listings?${params.toString()}`, { timeout: 15000 });
        let data = response.data || [];

        // Sort: Featured items first
        data.sort((a, b) => {
          if (a.is_featured && !b.is_featured) return -1;
          if (!a.is_featured && b.is_featured) return 1;
          return 0;
        });

        setListings(data);
      } catch (error) {
        console.error('Failed to fetch listings:', error);
        setListings([]);
      } finally {
        setLoading(false);
      }
    };

    fetchListings();
  }, [sidebarFilters]);

  // Market stats from current listings
  const marketStats = useMemo(() => {
    const totalLots = listings.reduce((sum, l) => sum + (l.total_lots || 0), 0);
    const privateSales = listings.filter(l => !l.seller_is_tax_registered).length;
    return { totalLots, privateSalesCount: privateSales };
  }, [listings]);

  // Batch-fetch seller reputations
  const [sellerReps, setSellerReps] = useState({});
  useEffect(() => {
    const sellerIds = [...new Set(listings.map(l => l.seller_id).filter(Boolean))];
    if (sellerIds.length === 0) return;
    axios.post(`${API}/reviews/reputation/batch`, { seller_ids: sellerIds })
      .then(res => setSellerReps(res.data.reputations || {}))
      .catch(() => {});
  }, [listings]);

  const renderListingCard = (listing) => {
    // iter217 — Read from the enriched seller_account_type (set by the backend GET).
    // Fallback path supports old cached payloads that don't have the new fields yet.
    const acctType = listing.seller_account_type
      || (listing.seller_is_partner ? 'partner'
        : listing.seller_is_vehicle_dealer ? 'vehicle_dealer'
        : listing.seller_is_storage_facility ? 'storage_facility'
        : (listing.seller_is_business || listing.seller_is_tax_registered ? 'business' : 'individual'));
    const isPrivateSale = acctType === 'individual';
    const firstLot = listing.lots?.[0];
    const imageUrl = firstLot?.images?.[0] || listing.lots?.find(l => l.images?.length > 0)?.images?.[0];

    return (
      <Card
        key={listing.id}
        className="group overflow-hidden flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-[0_2px_12px_rgba(0,0,0,0.08)] hover:shadow-[0_10px_28px_rgba(0,0,0,0.14)] transition-all duration-150 hover:-translate-y-[3px] min-h-[420px]"
        data-testid="listing-card"
      >
        <Link to={`/lots/${listing.id}`} className="block relative">
          <div className="h-[200px] overflow-hidden bg-slate-100 dark:bg-slate-800">
            {imageUrl ? (
              <SafeImage src={imageUrl} alt={getLocalized(listing, "title")} width={400} height={200} loading="lazy" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Package className="h-16 w-16" style={{ color: '#94a3b8' }} />
              </div>
            )}
          </div>
          <div className="absolute top-3 left-3 flex flex-wrap gap-2">
            {listing.is_verified_firm && <VerifiedBadge />}
            {listing.is_featured && (
              <Badge className="bg-orange-500 text-white border-0 shadow-lg">
                <Star className="h-3 w-3 mr-1 fill-white" /> {t('marketplace.featured', 'FEATURED')}
              </Badge>
            )}
            {/* iter217 — seller-account badge (Partner / Dealer / Storage / Private) */}
            <SellerAccountBadge
              accountType={acctType === 'business' ? 'individual' : acctType}
              companyName={listing.seller_partner_company_name}
              variant="compact"
            />
            {acctType === 'business' && (
              <Badge className="bg-blue-600 text-white border-0 shadow-lg">
                <Building2 className="h-3 w-3 mr-1" /> {t('sellerBadge.businessSeller', 'Business Seller')}
              </Badge>
            )}
          </div>
          <Badge className="absolute top-3 right-3 bg-slate-900/80 text-white border-0" style={{ color: '#ffffff' }}>
            <Package className="h-3 w-3 mr-1" /> {t('listingDetail.lotsCount', { count: listing.total_lots, defaultValue: '{{count}} Lots' })}
          </Badge>
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

        <CardContent className="px-4 py-[14px] flex flex-col flex-1 gap-2" data-testid="listing-content">
          <Link to={`/lots/${listing.id}`}>
            <h3 className="text-[14px] font-semibold leading-[1.35] line-clamp-2 hover:text-cyan-600 transition-colors mb-1" style={{ color: '#1a1a1a' }}>
              {getLocalized(listing, "title")}
            </h3>
          </Link>
          <div className="flex items-center text-[12px] gap-2" style={{ color: '#6b7280' }}>
            <SellerRatingInline sellerId={listing.seller_id} reputation={sellerReps[listing.seller_id]} />
            <span className="inline-flex items-center gap-1 truncate">
              <MapPin className="h-3 w-3" />
              <span className="truncate">{listing.city}, {listing.region}</span>
            </span>
          </div>
          {isPrivateSale && (
            <div
              className="w-full text-center rounded-md px-[10px] py-[5px] mt-1"
              style={{ backgroundColor: '#e6f9f0', color: '#1a7a4a', fontSize: '11px', fontWeight: 600 }}
              data-testid="lot-card-savings-banner"
            >
              {t('sellerBadge.privateSaveTax', 'Save ~15% on Taxes!')}
            </div>
          )}
          <div className="flex-1" />
          <div className="flex items-baseline justify-between">
            <span
              className="text-[10px] font-bold uppercase tracking-[0.5px]"
              style={{ color: '#9ca3af' }}
            >
              {t('marketplace.startingFrom', 'Starting from')}
            </span>
            <div className="flex items-baseline gap-[6px]">
              <span className="text-[22px] font-extrabold text-[#0a1628] dark:text-white">
                {formatListingPrice(firstLot?.starting_price || 0, firstLot?.currency)}
              </span>
              <span
                className="inline-block text-[10px] rounded text-[#4a5568] dark:text-slate-300"
                style={{ backgroundColor: '#e8ecf2', padding: '2px 6px' }}
              >
                {firstLot?.currency || 'CAD'}
              </span>
            </div>
          </div>
        </CardContent>

        <CardFooter className="px-4 pb-[14px] pt-0 flex items-center w-full">
          <Link to={`/lots/${listing.id}`} className="flex-1 min-w-0">
            <Button
              className="w-full h-[40px] rounded-lg text-white font-bold text-[13px]"
              style={{ background: 'linear-gradient(135deg, #2d6be4, #1a4fc4)', border: 'none' }}
              data-testid="lot-quick-view-btn"
            >
              <Eye className="h-4 w-4 mr-2" /> {t('marketplace.viewAuction', 'View Auction')}
            </Button>
          </Link>
          <div className="ml-2 flex-shrink-0">
            <WishlistHeartButton auctionId={listing.id} wishlistCount={listing.wishlist_count || 0} />
          </div>
        </CardFooter>
      </Card>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="lots-marketplace-page">
      <SEO
        title="Lot Auctions — Multi-Item Auctions"
        description="Browse and bid on multi-item lot auctions. Find estate sale collections, business inventory, and bulk packages across Canada."
        path="/lots"
      />
      {/* iter283 — Cross-link to Marketplace per dual-visibility spec. */}
      <div className="bg-slate-100 dark:bg-slate-800/40 border-b border-slate-200 dark:border-slate-800 py-2 text-center text-[12px] text-slate-500 dark:text-slate-400"
           data-testid="lots-marketplace-crosslink">
        🛒 {t('lotsMarketplace.alsoInMarketplace',
            'All these listings are also available in the')}{' '}
        <Link to="/marketplace" className="underline hover:no-underline font-medium text-slate-700 dark:text-slate-200">
          {t('lotsMarketplace.marketplaceLink', 'Marketplace →')}
        </Link>
      </div>
      {/* Hero Header */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-900 via-slate-900 to-cyan-900 opacity-95" />
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-0 left-1/4 w-96 h-96 rounded-full blur-[150px] bg-cyan-500" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 rounded-full blur-[150px] bg-blue-500" />
        </div>
        <div className="relative container mx-auto max-w-7xl py-8 px-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <div className="p-3 bg-cyan-500/20 backdrop-blur rounded-xl border border-cyan-400/30">
                  <Layers className="h-8 w-8" style={{ color: '#67e8f9' }} />
                </div>
                <h1 className="text-3xl md:text-4xl font-bold" style={{ color: '#ffffff', textShadow: '0 2px 8px rgba(0,0,0,0.3)' }}>
                  {t('lotsMarketplace.title', 'Lots Auction')}
                </h1>
              </div>
              <p style={{ color: '#bfdbfe' }} className="max-w-2xl text-lg">
                {t('lotsMarketplace.subtitle', 'Browse and bid on grouped item lots from sellers')}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge className="bg-white/10 backdrop-blur border-cyan-400/30 px-4 py-2" style={{ color: '#FFFFFF' }}>
                <Sparkles className="h-4 w-4 mr-2 text-yellow-400" /> {t('lotsMarketplace.featuredFirst')}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Two-Column Layout: Sidebar + Content */}
      <div className="container mx-auto max-w-7xl px-4 py-6">
        <div className="flex gap-6">
          {/* Sidebar handles its own desktop/mobile rendering */}
          <MarketplaceSidebar onFiltersChange={setSidebarFilters} externalFilters={sidebarFilters} />

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            {/* iter239 Mission 5 — Featured Lots carousel. */}
            <FeaturedListingsBanner section="lots" limit={8} />
            {/* New FilterBar — category dropdown hidden because sidebar owns it */}
            <FilterBar
              onFilterChange={(newFilters) => {
                // Phase 5 Hotfix v5 — do NOT overwrite `categories` from
                // the top bar. Categories are owned exclusively by the
                // sidebar. Forward only fields the top bar actually owns.
                setSidebarFilters(prev => ({
                  ...prev,
                  search: newFilters.search || '',
                  province: newFilters.province || '',
                  condition: newFilters.condition || '',
                  sort: newFilters.sort || 'nearby_first',
                  tax_status: newFilters.tax_status || '',
                  private_sales_only: !!newFilters.private_sales_only,
                  zero_fee_only: !!newFilters.zero_fee_only,
                  no_taxes: !!newFilters.no_taxes,
                }));
              }}
              pageContext="lots"
              hideCategoryDropdown={true}
              sidebarCategoryChip={sidebarFilters?.categories || []}
              onClearSidebarCategory={(cat) => {
                setSidebarFilters(prev => ({
                  ...prev,
                  categories: (prev.categories || []).filter(c => c !== cat),
                }));
              }}
            />

            {/* Stats + View Toggle */}
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="hidden lg:flex items-center gap-4 text-sm" style={{ color: '#374151' }}>
                <span>
                  <strong style={{ color: '#2563eb' }}>{listings.length}</strong> auctions
                  (<strong style={{ color: '#2563eb' }}>{marketStats.totalLots}</strong> lots)
                </span>
                {marketStats.privateSalesCount > 0 && (
                  <span>
                    <strong style={{ color: '#15803d' }}>{marketStats.privateSalesCount}</strong> Tax-Free
                  </span>
                )}
              </div>
              <div className="flex gap-1 border-2 rounded-lg p-1 flex-shrink-0" style={{ borderColor: '#e5e7eb' }}>
                <Button variant={viewMode === 'grid' ? 'default' : 'ghost'} size="sm" onClick={() => setViewMode('grid')}
                  className={viewMode === 'grid' ? 'bg-blue-600 text-white' : ''} data-testid="view-grid">
                  <GridIcon className="h-4 w-4" />
                </Button>
                <Button variant={viewMode === 'list' ? 'default' : 'ghost'} size="sm" onClick={() => setViewMode('list')}
                  className={viewMode === 'list' ? 'bg-blue-600 text-white' : ''} data-testid="view-list">
                  <ListIcon className="h-4 w-4" />
                </Button>
              </div>
            </div>

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
            <React.Suspense fallback={<div className="w-full mb-4 p-4 text-center text-xs text-slate-500">Loading map…</div>}>
              {mapOpen && (
                <MapSearchPanel
                  open={mapOpen}
                  onClose={() => {
                    // iter282 hotfix — MUST clear geoFilter here because
                    // the conditional `{mapOpen && <MapSearchPanel/>}`
                    // unmounts the panel before its internal "clear on
                    // close" useEffect can fire onGeoChange(null).
                    // Without this, the lots grid stays empty until a
                    // page refresh.
                    setMapOpen(false);
                    setGeoFilter(null);
                  }}
                  onGeoChange={setGeoFilter}
                  backendUrl={backendUrl}
                  isFrench={i18n.language?.startsWith('fr')}
                />
              )}
            </React.Suspense>

            {/* Listings Grid */}
            {loading ? (
              <LoadingTimeout rows={6} variant="cards" />
            ) : (geoListings !== null ? geoListings : listings).length === 0 ? (
              <Card className="p-12 text-center" data-testid="no-results">
                <Package className="h-16 w-16 mx-auto mb-4" style={{ color: '#9ca3af' }} />
                <h3 className="text-xl font-semibold mb-2" style={{ color: '#1a1a1a' }}>
                  {t('lotsMarketplace.noLots', 'No auctions found')}
                </h3>
                <p style={{ color: '#6b7280' }} className="mb-4">
                  {t('lotsMarketplace.noLotsDesc', 'Try adjusting your filters or search terms')}
                </p>
              </Card>
            ) : (
              <div className={viewMode === 'grid'
                ? 'grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4 xl:gap-5'
                : 'flex flex-col gap-4'
              } data-testid="lots-results-grid">
                {(() => {
                  // iter265 Mission 1.2 — Splice promoted lots into PROMO_SLOTS.
                  const base = (geoListings !== null ? geoListings : listings);
                  const visibleIds = new Set(base.map(l => l.id));
                  const promoQueue = promotedInline.filter(p => !visibleIds.has(p.id));
                  const out = [];
                  let pIdx = 0;
                  base.forEach((listing, idx) => {
                    if (PROMO_SLOTS.includes(idx) && pIdx < promoQueue.length) {
                      const promo = promoQueue[pIdx];
                      pIdx += 1;
                      out.push(renderListingCard({ ...promo, _is_promoted_inline: true, _promo_key: `promo-${promo.id}` }));
                    }
                    out.push(renderListingCard(listing));
                  });
                  return out;
                })()}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LotsMarketplacePage;
