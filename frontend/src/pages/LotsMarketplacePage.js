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
import WishlistHeartButton from '../components/WishlistHeartButton';
import MarketplaceSidebar from '../components/MarketplaceSidebar';
import { VerifiedBadge } from '../components/VerifiedBadge';
import { formatCurrency } from '../utils/currencyFormatter';
import { SellerRatingInline } from '../components/SellerReputation';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LotsMarketplacePage = () => {
  const { t } = useTranslation();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('grid');
  const [sidebarFilters, setSidebarFilters] = useState({});

  // Fetch listings whenever sidebar filters change
  useEffect(() => {
    const fetchListings = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        params.append('limit', '50');

        // Wire sidebar filters to API
        if (sidebarFilters.search) params.append('search', sidebarFilters.search);
        if (sidebarFilters.categories?.length) params.append('category', sidebarFilters.categories[0]);
        if (sidebarFilters.regions?.length) params.append('region', sidebarFilters.regions[0]);
        if (sidebarFilters.cities?.length) params.append('city', sidebarFilters.cities[0]);
        if (sidebarFilters.auctioneers?.length) params.append('seller_id', sidebarFilters.auctioneers.join(','));

        const response = await axios.get(`${API}/multi-item-listings?${params.toString()}`);
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
    const isPrivateSale = !listing.seller_is_tax_registered;
    const firstLot = listing.lots?.[0];
    const imageUrl = firstLot?.images?.[0] || listing.lots?.find(l => l.images?.length > 0)?.images?.[0];

    return (
      <Card
        key={listing.id}
        className="group overflow-hidden hover:shadow-xl transition-all duration-300 border-slate-200 dark:border-slate-700"
        data-testid="listing-card"
      >
        <Link to={`/lots/${listing.id}`} className="block relative">
          <div className="aspect-[4/3] overflow-hidden bg-slate-100 dark:bg-slate-800">
            {imageUrl ? (
              <img src={imageUrl} alt={listing.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
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
                <Star className="h-3 w-3 mr-1 fill-white" /> FEATURED
              </Badge>
            )}
            {isPrivateSale ? (
              <Badge className="bg-green-500 text-white border-0 shadow-lg">Private Sale</Badge>
            ) : (
              <Badge className="bg-blue-600 text-white border-0 shadow-lg">
                <Building2 className="h-3 w-3 mr-1" /> Business
              </Badge>
            )}
          </div>
          <Badge className="absolute top-3 right-3 bg-slate-900/80 text-white border-0" style={{ color: '#ffffff' }}>
            <Package className="h-3 w-3 mr-1" /> {listing.total_lots} Lots
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

        <CardContent className="p-4" data-testid="listing-content">
          <Link to={`/lots/${listing.id}`}>
            <h3 className="font-semibold text-lg mb-2 line-clamp-2 hover:text-cyan-600 transition-colors" style={{ color: '#1a1a1a', fontWeight: 600 }}>
              {listing.title}
            </h3>
          </Link>
          <div className="flex items-center gap-1 text-sm mb-3" style={{ color: '#6b7280' }}>
            <MapPin className="h-4 w-4" style={{ color: '#6b7280' }} />
            <span style={{ color: '#6b7280' }}>{listing.city}, {listing.region}</span>
          </div>
          {/* Seller Rating */}
          <div className="mb-2">
            <SellerRatingInline sellerId={listing.seller_id} reputation={sellerReps[listing.seller_id]} />
          </div>
          {isPrivateSale && (
            <div className="rounded-lg px-3 py-2 text-xs mb-3" style={{ backgroundColor: '#dcfce7', border: '1px solid #86efac' }}>
              <span style={{ color: '#15803d', fontWeight: 500 }}>Save ~15% - No tax on item price!</span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider" style={{ color: '#9ca3af' }}>{t('marketplace.startingFrom', 'Starting from')}</p>
              <p className="text-xl font-bold" style={{ background: 'linear-gradient(to right, #2563eb, #06b6d4)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
                {formatCurrency(firstLot?.starting_price || 0)}
              </p>
            </div>
            <WishlistHeartButton auctionId={listing.id} wishlistCount={listing.wishlist_count || 0} />
          </div>
        </CardContent>

        <CardFooter className="p-4 pt-0 flex gap-2">
          <Link to={`/lots/${listing.id}`} className="flex-1">
            <Button className="w-full bg-gradient-to-r from-blue-600 to-cyan-500 text-white hover:from-blue-700 hover:to-cyan-600">
              <Eye className="h-4 w-4 mr-2" /> View Auction
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
                <Sparkles className="h-4 w-4 mr-2 text-yellow-400" /> Featured First
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Two-Column Layout: Sidebar + Content */}
      <div className="container mx-auto max-w-7xl px-4 py-6">
        <div className="flex gap-6">
          {/* Desktop Sidebar only */}
          <div className="hidden lg:block">
            <MarketplaceSidebar onFiltersChange={setSidebarFilters} />
          </div>

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            {/* Filter + stats bar — sticky on scroll */}
            <div className="sticky top-0 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur -mx-4 px-4 py-3 mb-4 border-b border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between gap-3">
                <div className="lg:hidden flex-shrink-0">
                  <MarketplaceSidebar onFiltersChange={setSidebarFilters} />
                </div>
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
            </div>

            {/* Listings Grid */}
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent"></div>
              </div>
            ) : listings.length === 0 ? (
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
                ? 'grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4'
                : 'flex flex-col gap-4'
              }>
                {listings.map(listing => renderListingCard(listing))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LotsMarketplacePage;
